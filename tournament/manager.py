"""Standalone tournament lifecycle manager.

This module only depends on the isolated tournament package.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

import tournament.database as tournament_db
from tournament.events import list_events, log_event
from tournament.gate import evaluate_tournament_access
from tournament.notifications import (
    notify_badges_earned,
    notify_level_up,
    notify_results_posted,
    send_notification,
)
from tournament.payout import compute_scaled_payouts
from tournament.scoring import score_player_total
from tournament.simulation import generate_tournament_seed, simulate_player_full_line, simulate_tournament_environment
from tournament.sports.router import get_sport_handler, list_supported_sports, normalize_sport_code


DEFAULT_PAYOUT_TEMPLATE = {
    "Open": [0],
    "Pro": [200, 120, 80, 40],
    "Elite": [400, 225, 140, 95, 60, 40],
    "Championship": [500, 325, 275, 220, 180, 150, 145, 125],
}


def _loads_json(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _row_to_dict(row: Any) -> dict:
    if not row:
        return {}
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except Exception:
        return {}


def _load_signing_key_registry() -> dict[str, str]:
    raw = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEYS_JSON", "") or "").strip()
    if not raw:
        return {}
    parsed = _loads_json(raw, {})
    if not isinstance(parsed, dict):
        return {}

    out: dict[str, str] = {}
    for key_id, secret in parsed.items():
        k = str(key_id or "").strip()
        s = str(secret or "").strip()
        if k and s:
            out[k] = s
    return out


def _secret_fingerprint(secret: str) -> str:
    text = str(secret or "").strip()
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def get_reconcile_signing_key_registry_status() -> dict:
    """Return safe, non-secret key-registry metadata for ops diagnostics."""
    registry = _load_signing_key_registry()
    default_key_id = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "") or "").strip()
    fallback_key = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "") or "").strip()
    signature_version = int(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "1") or 1)

    keys = []
    for key_id in sorted(registry.keys()):
        secret = str(registry.get(key_id, "") or "")
        keys.append(
            {
                "key_id": key_id,
                "is_default": bool(default_key_id and key_id == default_key_id),
                "fingerprint": _secret_fingerprint(secret),
                "secret_length": len(secret),
            }
        )

    return {
        "success": True,
        "signature_version": signature_version,
        "default_key_id": default_key_id,
        "registry_count": len(keys),
        "fallback_key_configured": bool(fallback_key),
        "keys": keys,
    }


def _resolve_signing_secret(
    *,
    requested_key_id: str = "",
    explicit_signing_key: str = "",
) -> tuple[str, str, str]:
    registry = _load_signing_key_registry()
    selected_key_id = str(requested_key_id or "").strip()

    if explicit_signing_key:
        return str(explicit_signing_key), selected_key_id, "explicit"

    if selected_key_id and selected_key_id in registry:
        return str(registry[selected_key_id]), selected_key_id, "registry"

    env_default_key_id = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "") or "").strip()
    if not selected_key_id and env_default_key_id:
        selected_key_id = env_default_key_id

    if selected_key_id and selected_key_id in registry:
        return str(registry[selected_key_id]), selected_key_id, "registry"

    fallback = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "") or "").strip()
    if fallback:
        return fallback, selected_key_id, "fallback"

    return "", selected_key_id, "unresolved"


def create_tournament(
    tournament_name: str,
    court_tier: str,
    entry_fee: float,
    min_entries: int,
    max_entries: int,
    lock_time: str,
    reveal_mode: str = "instant",
    payout_template: list[float] | None = None,
    sport: str = "nba",
) -> int:
    """Create a new tournament record in the standalone DB."""
    tournament_db.initialize_tournament_database()
    template = payout_template or DEFAULT_PAYOUT_TEMPLATE.get(court_tier, [])
    sport_code = normalize_sport_code(sport)
    tid = 0

    with tournament_db.get_tournament_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tournaments
                (tournament_name, sport, court_tier, status, entry_fee, max_entries, min_entries,
                 lock_time, reveal_mode, payout_structure_json)
            VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?, ?)
            """,
            (
                tournament_name,
                sport_code,
                court_tier,
                float(entry_fee),
                int(max_entries),
                int(min_entries),
                lock_time,
                reveal_mode,
                json.dumps(template),
            ),
        )
        conn.commit()
        tid = int(cursor.lastrowid)

    log_event(
        "tournament.created",
        f"Tournament #{tid} created: {tournament_name}",
        tournament_id=tid,
        metadata={
            "court_tier": court_tier,
            "sport": sport_code,
            "entry_fee": float(entry_fee),
            "min_entries": int(min_entries),
            "max_entries": int(max_entries),
        },
    )
    return tid


def get_tournament(tournament_id: int) -> dict | None:
    """Fetch a tournament row as a dict."""
    tournament_db.initialize_tournament_database()
    with tournament_db.get_tournament_connection() as conn:
        row = conn.execute(
            "SELECT * FROM tournaments WHERE tournament_id = ?",
            (int(tournament_id),),
        ).fetchone()
        return dict(row) if row else None


def list_open_tournaments() -> list[dict]:
    """List open tournaments by nearest lock time."""
    tournament_db.initialize_tournament_database()
    with tournament_db.get_tournament_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM tournaments
            WHERE status = 'open'
            ORDER BY lock_time ASC, tournament_id ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def list_tournaments(status: str | None = None) -> list[dict]:
    """List tournaments optionally filtered by status."""
    tournament_db.initialize_tournament_database()
    with tournament_db.get_tournament_connection() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM tournaments WHERE status = ? ORDER BY lock_time DESC, tournament_id DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tournaments ORDER BY lock_time DESC, tournament_id DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def list_player_profiles(include_legends: bool = True, limit: int | None = None) -> list[dict]:
    """List tournament player profiles from the isolated DB."""
    tournament_db.initialize_tournament_database()
    sql = "SELECT profile_json FROM player_profiles"
    params: list[Any] = []

    sql += " ORDER BY overall_rating DESC, salary DESC"
    if limit is not None and limit > 0:
        sql += " LIMIT ?"
        params.append(int(limit))

    with tournament_db.get_tournament_connection() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        profiles = [_loads_json(r["profile_json"], {}) for r in rows]
        if include_legends:
            return [p for p in profiles if p]
        return [p for p in profiles if p and not bool(p.get("is_legend", False))]


def load_tournament_entries(tournament_id: int) -> list[dict]:
    """Load tournament entries with parsed rosters."""
    tournament_db.initialize_tournament_database()
    with tournament_db.get_tournament_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM tournament_entries WHERE tournament_id = ? ORDER BY created_at ASC",
            (int(tournament_id),),
        ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["roster"] = _loads_json(item.get("roster_json"), [])
            out.append(item)
        return out


def get_tournament_scoreboard(tournament_id: int) -> list[dict]:
    """Return ranked scoreboard rows for a resolved tournament."""
    tournament_db.initialize_tournament_database()
    with tournament_db.get_tournament_connection() as conn:
        rows = conn.execute(
            """
            SELECT entry_id, user_email, display_name, total_score, rank, lp_awarded, payout_amount, created_at
            FROM tournament_entries
            WHERE tournament_id = ?
            ORDER BY COALESCE(rank, 9999) ASC, total_score DESC, created_at ASC
            """,
            (int(tournament_id),),
        ).fetchall()
        return [dict(r) for r in rows]


def get_tournament_simulated_scores(tournament_id: int) -> list[dict]:
    """Return simulated player scores for one tournament, best-first."""
    tournament_db.initialize_tournament_database()
    with tournament_db.get_tournament_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                player_id,
                player_name,
                line_json,
                fantasy_points,
                bonuses_json,
                penalties_json,
                total_fp,
                created_at
            FROM simulated_scores
            WHERE tournament_id = ?
            ORDER BY total_fp DESC, player_name ASC
            """,
            (int(tournament_id),),
        ).fetchall()

    out: list[dict] = []
    for row in rows:
        item = dict(row)
        item["line"] = _loads_json(item.get("line_json"), {})
        item["bonuses"] = _loads_json(item.get("bonuses_json"), {})
        item["penalties"] = _loads_json(item.get("penalties_json"), {})
        out.append(item)
    return out


def get_tournament_live_snapshot(tournament_id: int, user_email: str = "", top_n: int = 25) -> dict:
    """Return a live-friendly tournament snapshot for scoreboard/profile surfaces."""
    tournament = get_tournament(tournament_id)
    if not tournament:
        return {"success": False, "error": "Tournament not found", "tournament_id": int(tournament_id)}

    entries = load_tournament_entries(tournament_id)
    sim_rows = get_tournament_simulated_scores(tournament_id)
    sim_map = {str(r.get("player_id", "")): float(r.get("total_fp", 0.0) or 0.0) for r in sim_rows}

    scored_entries: list[dict] = []
    for row in entries:
        roster = list(row.get("roster") or [])
        computed_score = round(sum(sim_map.get(str(p.get("player_id", "")), 0.0) for p in roster), 2)
        stored_score = float(row.get("total_score", 0.0) or 0.0)
        display_score = stored_score if stored_score > 0 else computed_score
        scored_entries.append(
            {
                **row,
                "display_name": str(row.get("display_name", "") or row.get("user_email", "Unknown")),
                "roster_count": len(roster),
                "computed_score": computed_score,
                "display_score": round(display_score, 2),
            }
        )

    scored_entries.sort(
        key=lambda r: (
            int(r.get("rank", 999999) or 999999),
            -float(r.get("display_score", 0.0) or 0.0),
            str(r.get("created_at", "")),
        )
    )

    for idx, row in enumerate(scored_entries, start=1):
        row["live_rank"] = int(row.get("rank") or idx)

    normalized_email = str(user_email or "").strip().lower()
    my_entries = [r for r in scored_entries if str(r.get("user_email", "")).strip().lower() == normalized_email] if normalized_email else []

    return {
        "success": True,
        "tournament": tournament,
        "entry_count": len(scored_entries),
        "leaderboard": scored_entries[: max(1, int(top_n))],
        "my_entries": my_entries,
        "top_players": sim_rows[:20],
    }


def get_staged_reveal_snapshot(tournament_id: int, now: datetime | None = None) -> dict:
    """Return a staged-reveal snapshot for Championship Night.

    Uses the tournament reveal engine to determine the current phase,
    filter scores to only the stats revealed so far, and compute a
    partial leaderboard.
    """
    from tournament.engine.tournament_reveal import (
        compute_partial_leaderboard,
        filter_scores_for_phase,
        get_current_phase,
        get_next_phase,
    )

    tournament = get_tournament(tournament_id)
    if not tournament:
        return {"success": False, "error": "Tournament not found"}

    reveal_mode = str(tournament.get("reveal_mode", "instant"))
    if reveal_mode != "staged":
        return get_tournament_live_snapshot(tournament_id)

    lock_time_raw = str(tournament.get("lock_time", "") or "")
    try:
        lock_time = datetime.strptime(lock_time_raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        lock_time = datetime.now(timezone.utc)

    phase = get_current_phase(lock_time, now)
    next_phase = get_next_phase(lock_time, now)

    sim_rows = get_tournament_simulated_scores(tournament_id)
    sim_results: dict[str, dict] = {}
    for row in sim_rows:
        pid = str(row.get("player_id", ""))
        line_data = _loads_json(row.get("line_json"), {})
        sim_results[pid] = {
            **line_data,
            "fantasy_points": float(row.get("fantasy_points", 0.0)),
            "bonuses": _loads_json(row.get("bonuses_json"), {"total": 0.0, "triggered": []}),
            "penalties": _loads_json(row.get("penalties_json"), {"total": 0.0, "triggered": []}),
            "total_fp": float(row.get("total_fp", 0.0)),
        }

    filtered_scores = filter_scores_for_phase(sim_results, phase)

    entries = load_tournament_entries(tournament_id)
    partial_board = compute_partial_leaderboard(entries, filtered_scores)

    return {
        "success": True,
        "tournament": tournament,
        "reveal_mode": "staged",
        "phase": phase,
        "next_phase": next_phase,
        "partial_leaderboard": partial_board,
        "filtered_scores": filtered_scores,
        "entry_count": len(entries),
    }


def list_user_entries(user_email: str, limit: int = 100) -> list[dict]:
    """List one user's tournament entries across all tournaments."""
    tournament_db.initialize_tournament_database()
    email = (user_email or "").strip().lower()
    with tournament_db.get_tournament_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                e.entry_id,
                e.tournament_id,
                t.tournament_name,
                t.court_tier,
                t.status,
                t.entry_fee,
                e.roster_json,
                e.total_score,
                e.rank,
                e.lp_awarded,
                e.payout_amount,
                e.created_at
            FROM tournament_entries e
            JOIN tournaments t ON t.tournament_id = e.tournament_id
            WHERE e.user_email = ?
            ORDER BY e.created_at DESC
            LIMIT ?
            """,
            (email, max(1, int(limit))),
        ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["roster"] = _loads_json(item.get("roster_json"), [])
            out.append(item)
        return out


def get_user_head_to_head(user_email: str, limit: int = 20) -> list[dict]:
    """Return head-to-head matchup aggregates versus opponents in shared tournaments."""
    tournament_db.initialize_tournament_database()
    normalized_email = str(user_email or "").strip().lower()
    if not normalized_email:
        return []

    with tournament_db.get_tournament_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                opp.user_email AS opponent_email,
                COALESCE(NULLIF(opp.display_name, ''), opp.user_email) AS opponent_name,
                COUNT(*) AS matchups,
                AVG(COALESCE(me.total_score, 0.0)) AS your_avg_score,
                AVG(COALESCE(opp.total_score, 0.0)) AS opponent_avg_score,
                SUM(
                    CASE
                        WHEN COALESCE(me.total_score, 0.0) > COALESCE(opp.total_score, 0.0) THEN 1
                        ELSE 0
                    END
                ) AS wins
            FROM tournament_entries me
            JOIN tournament_entries opp
              ON opp.tournament_id = me.tournament_id
             AND opp.entry_id != me.entry_id
            WHERE me.user_email = ?
            GROUP BY opp.user_email, opponent_name
            ORDER BY matchups DESC, wins DESC, your_avg_score DESC
            LIMIT ?
            """,
            (normalized_email, max(1, int(limit))),
        ).fetchall()

    out: list[dict] = []
    for row in rows:
        item = dict(row)
        matchups = int(item.get("matchups", 0) or 0)
        wins = int(item.get("wins", 0) or 0)
        item["win_pct"] = round((float(wins) / float(matchups) * 100.0), 1) if matchups > 0 else 0.0
        out.append(item)
    return out


def get_user_best_rosters(user_email: str, limit: int = 5) -> dict:
    """Return a user's top-scoring rosters and consistency metrics."""
    entries = list_user_entries(user_email, limit=500)
    if not entries:
        return {
            "entries": [],
            "average_score": 0.0,
            "score_std_dev": 0.0,
            "boom_threshold": 0.0,
            "boom_rate": 0.0,
            "bust_threshold": 0.0,
            "bust_rate": 0.0,
        }

    scores = [float(item.get("total_score", 0.0) or 0.0) for item in entries]
    avg_score = sum(scores) / float(len(scores))
    variance = sum((s - avg_score) ** 2 for s in scores) / float(len(scores))
    std_dev = variance ** 0.5
    boom_threshold = avg_score + std_dev
    bust_threshold = max(0.0, avg_score - std_dev)
    boom_count = sum(1 for s in scores if s >= boom_threshold)
    bust_count = sum(1 for s in scores if s <= bust_threshold)

    ranked = sorted(entries, key=lambda x: float(x.get("total_score", 0.0) or 0.0), reverse=True)
    top_entries = []
    for row in ranked[: max(1, int(limit))]:
        roster = list(row.get("roster") or [])
        top_entries.append(
            {
                "entry_id": int(row.get("entry_id", 0) or 0),
                "tournament_id": int(row.get("tournament_id", 0) or 0),
                "tournament_name": str(row.get("tournament_name", "")),
                "court_tier": str(row.get("court_tier", "")),
                "score": float(row.get("total_score", 0.0) or 0.0),
                "rank": row.get("rank"),
                "payout_amount": float(row.get("payout_amount", 0.0) or 0.0),
                "roster": roster,
                "roster_players": [str(p.get("player_name", p.get("player_id", ""))) for p in roster],
            }
        )

    return {
        "entries": top_entries,
        "average_score": round(avg_score, 2),
        "score_std_dev": round(std_dev, 2),
        "boom_threshold": round(boom_threshold, 2),
        "boom_rate": round(float(boom_count) / float(len(scores)) * 100.0, 1),
        "bust_threshold": round(bust_threshold, 2),
        "bust_rate": round(float(bust_count) / float(len(scores)) * 100.0, 1),
    }


def get_user_progression_snapshot(user_email: str, limit: int = 40) -> dict:
    """Return rank/score progression and derived skill percentiles for profile visualizations."""
    tournament_db.initialize_tournament_database()
    normalized_email = str(user_email or "").strip().lower()
    if not normalized_email:
        return {
            "series": [],
            "global_rank": 0,
            "skills": {},
        }

    with tournament_db.get_tournament_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                e.entry_id,
                e.tournament_id,
                t.tournament_name,
                e.total_score,
                e.rank,
                e.lp_awarded,
                e.created_at
            FROM tournament_entries e
            JOIN tournaments t ON t.tournament_id = e.tournament_id
            WHERE e.user_email = ?
            ORDER BY e.created_at ASC, e.entry_id ASC
            LIMIT ?
            """,
            (normalized_email, max(1, int(limit))),
        ).fetchall()

    series: list[dict] = []
    cumulative_lp = 0
    for idx, row in enumerate(rows, start=1):
        item = dict(row)
        lp = int(item.get("lp_awarded", 0) or 0)
        cumulative_lp += lp
        series.append(
            {
                "index": idx,
                "entry_id": int(item.get("entry_id", 0) or 0),
                "tournament_id": int(item.get("tournament_id", 0) or 0),
                "tournament_name": str(item.get("tournament_name", "")),
                "score": float(item.get("total_score", 0.0) or 0.0),
                "rank": int(item.get("rank", 0) or 0),
                "lp_awarded": lp,
                "cumulative_lp": cumulative_lp,
                "created_at": str(item.get("created_at", "")),
            }
        )

    career = get_user_career_stats(normalized_email)
    board = list_career_leaderboard(limit=1000)
    global_rank = next((int(r.get("rank", 0) or 0) for r in board if str(r.get("user_email", "")).strip().lower() == normalized_email), 0)

    lifetime_entries = max(1, int(career.get("lifetime_entries", 0) or 0))
    lifetime_wins = int(career.get("lifetime_wins", 0) or 0)
    lifetime_top5 = int(career.get("lifetime_top5", 0) or 0)
    lifetime_lp = int(career.get("lifetime_lp", 0) or 0)
    earnings = float(career.get("lifetime_earnings", 0.0) or 0.0)

    projection_accuracy = min(99, max(1, int((float(lifetime_top5) / float(lifetime_entries)) * 100.0)))
    contrarian_edge = min(99, max(1, int((float(lifetime_wins) / float(lifetime_entries)) * 160.0)))
    money_management = min(99, max(1, int((earnings / max(1.0, float(lifetime_entries) * 20.0)) * 100.0)))
    game_flow = min(99, max(1, int((float(lifetime_lp) / max(1.0, float(lifetime_entries) * 50.0)) * 100.0)))
    late_adjustments = min(99, max(1, int((projection_accuracy * 0.6) + (contrarian_edge * 0.4))))

    return {
        "series": series,
        "global_rank": global_rank,
        "skills": {
            "Projection Accuracy": projection_accuracy,
            "Contrarian Edge": contrarian_edge,
            "Money Management": money_management,
            "Game Flow": game_flow,
            "Late Adjustments": late_adjustments,
        },
    }


def get_user_career_stats(user_email: str) -> dict:
    """Return one user's career stats snapshot from isolated DB."""
    tournament_db.initialize_tournament_database()
    email = (user_email or "").strip().lower()
    with tournament_db.get_tournament_connection() as conn:
        row = conn.execute(
            "SELECT * FROM user_career_stats WHERE user_email = ?",
            (email,),
        ).fetchone()
        if not row:
            return {
                "user_email": email,
                "display_name": "",
                "lifetime_entries": 0,
                "lifetime_wins": 0,
                "lifetime_top5": 0,
                "lifetime_earnings": 0.0,
                "lifetime_lp": 0,
                "career_level": 1,
            }
        return dict(row)


def list_career_leaderboard(limit: int = 100) -> list[dict]:
    """Return leaderboard rows ranked by lifetime LP then wins and earnings."""
    tournament_db.initialize_tournament_database()
    with tournament_db.get_tournament_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                user_email,
                display_name,
                lifetime_entries,
                lifetime_wins,
                lifetime_top5,
                lifetime_earnings,
                lifetime_lp,
                career_level,
                updated_at
            FROM user_career_stats
            ORDER BY lifetime_lp DESC, lifetime_wins DESC, lifetime_earnings DESC, updated_at DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()

    ranked = []
    for idx, row in enumerate(rows, start=1):
        item = dict(row)
        item["rank"] = idx
        ranked.append(item)
    return ranked


def list_season_lp_leaderboard(
    year: int,
    month: int | None = None,
    quarter: int | None = None,
    limit: int = 100,
) -> list[dict]:
    """Return season-scoped LP standings from resolved tournament_entries.

    - ``month`` (1–12): filter to that calendar month.
    - ``quarter`` (1–4): filter to the 3-month quarter window.
    - Neither set: full calendar year.

    Returns rows with ``rank``, ``user_email``, ``display_name``, ``season_lp``,
    ``wins``, ``top5``, ``entries``, ``earnings``.
    """
    tournament_db.initialize_tournament_database()

    if month is not None:
        month = max(1, min(12, int(month)))
        start = f"{int(year)}-{month:02d}-01"
        end = f"{int(year) + 1}-01-01" if month == 12 else f"{int(year)}-{month + 1:02d}-01"
    elif quarter is not None:
        quarter = max(1, min(4, int(quarter)))
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 3
        start = f"{int(year)}-{start_month:02d}-01"
        end = f"{int(year) + 1}-01-01" if end_month > 12 else f"{int(year)}-{end_month:02d}-01"
    else:
        start = f"{int(year)}-01-01"
        end = f"{int(year) + 1}-01-01"

    with tournament_db.get_tournament_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                e.user_email,
                COALESCE(cs.display_name, e.user_email) AS display_name,
                COUNT(*) AS entries,
                SUM(CASE WHEN e.rank = 1 THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN e.rank <= 5 THEN 1 ELSE 0 END) AS top5,
                SUM(COALESCE(e.payout_amount, 0)) AS earnings,
                SUM(COALESCE(e.lp_awarded, 0)) AS season_lp
            FROM tournament_entries e
            JOIN tournaments t ON t.tournament_id = e.tournament_id
            LEFT JOIN user_career_stats cs ON LOWER(cs.user_email) = LOWER(e.user_email)
            WHERE t.status = 'resolved'
              AND COALESCE(t.resolved_at, t.lock_time) >= ?
              AND COALESCE(t.resolved_at, t.lock_time) < ?
            GROUP BY LOWER(e.user_email)
            ORDER BY season_lp DESC, wins DESC, earnings DESC
            LIMIT ?
            """,
            (start, end, max(1, int(limit))),
        ).fetchall()

    ranked: list[dict] = []
    for idx, row in enumerate(rows, start=1):
        item = dict(row)
        item["rank"] = idx
        item["season_lp"] = int(item.get("season_lp", 0) or 0)
        item["wins"] = int(item.get("wins", 0) or 0)
        item["top5"] = int(item.get("top5", 0) or 0)
        item["entries"] = int(item.get("entries", 0) or 0)
        item["earnings"] = round(float(item.get("earnings", 0.0) or 0.0), 2)
        ranked.append(item)
    return ranked


def distribute_season_end_rewards(
    year: int,
    month: int,
    *,
    top_pct: float = 0.10,
    bonus_lp: int = 100,
) -> dict:
    """Award bonus LP and a season-end badge to the top ``top_pct`` monthly LP earners.

    Returns a summary with ``awarded_count``, ``total_bonus_lp``, ``season_key``,
    and per-user ``players`` detail list.
    """
    season_key = f"{int(year)}-{int(month):02d}"
    board = list_season_lp_leaderboard(year=int(year), month=int(month), limit=1000)
    if not board:
        return {"awarded_count": 0, "total_bonus_lp": 0, "season_key": season_key, "players": []}

    cutoff = max(1, int(round(len(board) * max(0.01, min(1.0, float(top_pct))))))
    top_players = board[:cutoff]
    award_key = f"season_reward_{season_key}"

    tournament_db.initialize_tournament_database()
    awarded_details: list[dict] = []

    with tournament_db.get_tournament_connection() as conn:
        for player in top_players:
            email = str(player.get("user_email", "")).strip().lower()
            if not email:
                continue
            conn.execute(
                """
                INSERT INTO user_career_stats (user_email, lifetime_lp, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(user_email) DO UPDATE SET
                    lifetime_lp = user_career_stats.lifetime_lp + ?,
                    updated_at = datetime('now')
                """,
                (email, int(bonus_lp), int(bonus_lp)),
            )
            _grant_badge_award(
                conn,
                user_email=email,
                award_key=award_key,
                award_name=f"Season Reward {season_key}",
                context={
                    "year": int(year),
                    "month": int(month),
                    "season_lp": int(player.get("season_lp", 0) or 0),
                    "rank": int(player.get("rank", 0) or 0),
                    "bonus_lp": int(bonus_lp),
                },
            )
            awarded_details.append(
                {
                    "user_email": email,
                    "display_name": str(player.get("display_name", "")),
                    "rank": int(player.get("rank", 0) or 0),
                    "season_lp": int(player.get("season_lp", 0) or 0),
                    "bonus_lp": int(bonus_lp),
                }
            )
        conn.commit()

    total_bonus = len(awarded_details) * int(bonus_lp)
    log_event(
        "season.rewards_distributed",
        f"Season-end rewards for {season_key}: {len(awarded_details)} player(s) awarded {bonus_lp} bonus LP each",
        metadata={"season_key": season_key, "awarded_count": len(awarded_details), "total_bonus_lp": total_bonus},
    )
    return {
        "season_key": season_key,
        "awarded_count": len(awarded_details),
        "total_bonus_lp": total_bonus,
        "players": awarded_details,
    }


def qualify_for_championship(
    season_label: str,
    *,
    top_n: int = 8,
    year: int | None = None,
    month: int | None = None,
    lock_offset_hours: int = 24,
    entry_fee: float = 0.0,
    max_entries: int = 32,
    sport: str = "nba",
) -> dict:
    """Qualify the top ``top_n`` season LP earners into a Championship tournament.

    Creates a Championship-tier tournament and inserts free entries for each qualifier.
    Returns a summary with ``tournament_id``, ``qualifiers`` count, and per-user details.
    """
    from datetime import timedelta

    now_utc = datetime.now(timezone.utc)
    year = int(year) if year is not None else now_utc.year
    month = int(month) if month is not None else now_utc.month

    board = list_season_lp_leaderboard(year=year, month=month, limit=int(top_n))
    if not board:
        return {"success": False, "error": "No LP earners found for season window", "season_label": season_label}

    lock_time = now_utc + timedelta(hours=max(1, int(lock_offset_hours)))
    lock_time_str = lock_time.strftime("%Y-%m-%d %H:%M:%S")

    tournament_id = create_tournament(
        f"Championship Night — {season_label}",
        "Championship",
        float(entry_fee),
        2,
        int(max(int(max_entries), len(board))),
        lock_time_str,
        sport=str(sport),
    )

    submitted: list[dict] = []
    errors: list[str] = []
    tournament_db.initialize_tournament_database()
    with tournament_db.get_tournament_connection() as conn:
        for player in board:
            email = str(player.get("user_email", "")).strip().lower()
            display = str(player.get("display_name", "") or email)
            if not email:
                continue
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO tournament_entries
                        (tournament_id, user_email, display_name, roster_json, created_at)
                    VALUES (?, ?, ?, '[]', datetime('now'))
                    """,
                    (tournament_id, email, display),
                )
                conn.commit()
                submitted.append(
                    {
                        "user_email": email,
                        "display_name": display,
                        "entry_id": int(cursor.lastrowid or 0),
                        "rank": int(player.get("rank", 0) or 0),
                        "season_lp": int(player.get("season_lp", 0) or 0),
                    }
                )
            except Exception as exc:  # pragma: no cover
                errors.append(f"{email}: {exc}")

    log_event(
        "championship.qualified",
        f"Championship qualification for {season_label}: {len(submitted)} qualifier(s) for tournament #{tournament_id}",
        tournament_id=tournament_id,
        metadata={"season_label": season_label, "qualifiers": len(submitted), "errors": errors},
    )
    return {
        "success": True,
        "season_label": season_label,
        "tournament_id": tournament_id,
        "qualifiers": len(submitted),
        "entries": submitted,
        "errors": errors,
    }


def get_supported_tournament_sports() -> list[dict]:
    """Return all sport handlers available to the tournament router."""
    return list_supported_sports()


def upsert_user_subscription_status(
    user_email: str,
    *,
    premium_active: bool,
    legend_pass_active: bool,
    premium_expires_at: str = "",
    legend_pass_expires_at: str = "",
    source: str = "manual",
    raw_payload: dict | None = None,
) -> dict:
    """Persist user subscription status snapshot for enforcement and diagnostics."""
    tournament_db.initialize_tournament_database()
    email = str(user_email or "").strip().lower()
    if not email:
        return {"success": False, "error": "user_email is required"}

    with tournament_db.get_tournament_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_subscription_status
                (user_email, premium_active, legend_pass_active, premium_expires_at,
                 legend_pass_expires_at, source, raw_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(user_email) DO UPDATE SET
                premium_active = excluded.premium_active,
                legend_pass_active = excluded.legend_pass_active,
                premium_expires_at = excluded.premium_expires_at,
                legend_pass_expires_at = excluded.legend_pass_expires_at,
                source = excluded.source,
                raw_json = excluded.raw_json,
                updated_at = datetime('now')
            """,
            (
                email,
                1 if premium_active else 0,
                1 if legend_pass_active else 0,
                str(premium_expires_at or "").strip(),
                str(legend_pass_expires_at or "").strip(),
                str(source or "manual"),
                json.dumps(raw_payload or {}),
            ),
        )
        conn.commit()

    log_event(
        "subscription.status_upserted",
        f"Subscription status updated for {email}",
        user_email=email,
        metadata={
            "premium_active": bool(premium_active),
            "legend_pass_active": bool(legend_pass_active),
            "source": str(source or "manual"),
        },
    )
    return {"success": True, "user_email": email}


def get_user_subscription_status(user_email: str) -> dict:
    """Read one user's subscription status snapshot."""
    tournament_db.initialize_tournament_database()
    email = str(user_email or "").strip().lower()
    if not email:
        return {
            "user_email": "",
            "premium_active": False,
            "legend_pass_active": False,
            "premium_expires_at": "",
            "legend_pass_expires_at": "",
            "source": "",
            "raw": {},
            "updated_at": "",
        }

    with tournament_db.get_tournament_connection() as conn:
        row = conn.execute(
            """
            SELECT
                user_email,
                premium_active,
                legend_pass_active,
                premium_expires_at,
                legend_pass_expires_at,
                source,
                raw_json,
                updated_at
            FROM user_subscription_status
            WHERE user_email = ?
            """,
            (email,),
        ).fetchone()

    if not row:
        return {
            "user_email": email,
            "premium_active": False,
            "legend_pass_active": False,
            "premium_expires_at": "",
            "legend_pass_expires_at": "",
            "source": "",
            "raw": {},
            "updated_at": "",
        }

    item = dict(row)
    return {
        "user_email": str(item.get("user_email", "") or "").strip().lower(),
        "premium_active": bool(int(item.get("premium_active", 0) or 0)),
        "legend_pass_active": bool(int(item.get("legend_pass_active", 0) or 0)),
        "premium_expires_at": str(item.get("premium_expires_at", "") or ""),
        "legend_pass_expires_at": str(item.get("legend_pass_expires_at", "") or ""),
        "source": str(item.get("source", "") or ""),
        "raw": _loads_json(item.get("raw_json"), {}),
        "updated_at": str(item.get("updated_at", "") or ""),
    }


def evaluate_user_tournament_access(
    *,
    user_email: str,
    court_tier: str,
    user_age: int,
    state_code: str,
    blocked_states: set[str] | None = None,
) -> dict:
    """Evaluate access using persisted subscription snapshot + core gate rules."""
    status = get_user_subscription_status(user_email)
    result = evaluate_tournament_access(
        court_tier,
        is_premium=bool(status.get("premium_active", False)),
        has_legend_pass=bool(status.get("legend_pass_active", False)),
        user_age=int(user_age),
        state_code=str(state_code or ""),
        blocked_states=blocked_states,
        subscription_status=status,
    )
    return {
        **result,
        "user_email": str(user_email or "").strip().lower(),
        "subscription_status": status,
    }


def _parse_iso_utc(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _compute_user_paid_payout_total(user_email: str, year: int | None = None) -> float:
    tournament_db.initialize_tournament_database()
    email = str(user_email or "").strip().lower()
    if not email:
        return 0.0

    target_year = int(year or datetime.now(timezone.utc).year)
    with tournament_db.get_tournament_connection() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(e.payout_amount), 0.0) AS total
            FROM tournament_entries e
            LEFT JOIN tournaments t ON t.tournament_id = e.tournament_id
            WHERE e.user_email = ?
              AND e.payout_status = 'paid'
              AND e.payout_amount > 0
              AND strftime('%Y', COALESCE(t.resolved_at, e.created_at)) = ?
            """,
            (email, str(target_year)),
        ).fetchone()
    return round(float((row or {"total": 0.0})["total"] or 0.0), 2)


def upsert_user_connect_status(
    user_email: str,
    *,
    stripe_connect_account_id: str,
    onboarding_status: str = "not_started",
    details_submitted: bool = False,
    payouts_enabled: bool = False,
    requirements: dict | None = None,
    kyc_verified: bool = False,
    kyc_verified_at: str = "",
) -> dict:
    """Persist Stripe Connect onboarding + KYC status for one user."""
    tournament_db.initialize_tournament_database()
    email = str(user_email or "").strip().lower()
    connect_id = str(stripe_connect_account_id or "").strip()
    if not email:
        return {"success": False, "error": "user_email is required"}
    if not connect_id:
        return {"success": False, "error": "stripe_connect_account_id is required"}

    verified_at = str(kyc_verified_at or "").strip()
    if bool(kyc_verified) and not verified_at:
        verified_at = datetime.now(timezone.utc).isoformat()

    with tournament_db.get_tournament_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_career_stats (
                user_email,
                stripe_connect_account_id,
                stripe_connect_onboarding_status,
                stripe_connect_details_submitted,
                stripe_connect_payouts_enabled,
                stripe_connect_requirements_json,
                stripe_connect_kyc_verified,
                stripe_connect_kyc_verified_at,
                stripe_connect_last_synced_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(user_email) DO UPDATE SET
                stripe_connect_account_id = excluded.stripe_connect_account_id,
                stripe_connect_onboarding_status = excluded.stripe_connect_onboarding_status,
                stripe_connect_details_submitted = excluded.stripe_connect_details_submitted,
                stripe_connect_payouts_enabled = excluded.stripe_connect_payouts_enabled,
                stripe_connect_requirements_json = excluded.stripe_connect_requirements_json,
                stripe_connect_kyc_verified = excluded.stripe_connect_kyc_verified,
                stripe_connect_kyc_verified_at = excluded.stripe_connect_kyc_verified_at,
                stripe_connect_last_synced_at = datetime('now'),
                updated_at = datetime('now')
            """,
            (
                email,
                connect_id,
                str(onboarding_status or "not_started").strip().lower(),
                1 if bool(details_submitted) else 0,
                1 if bool(payouts_enabled) else 0,
                json.dumps(requirements or {}),
                1 if bool(kyc_verified) else 0,
                verified_at,
            ),
        )
        conn.commit()

    log_event(
        "connect.status_upserted",
        f"Connect status updated for {email}",
        user_email=email,
        metadata={
            "stripe_connect_account_id": connect_id,
            "onboarding_status": str(onboarding_status or "not_started").strip().lower(),
            "details_submitted": bool(details_submitted),
            "payouts_enabled": bool(payouts_enabled),
            "kyc_verified": bool(kyc_verified),
        },
    )
    return {"success": True, "user_email": email, "stripe_connect_account_id": connect_id}


def get_user_connect_status(
    user_email: str,
    *,
    compliance_year: int | None = None,
    kyc_threshold_usd: float = 600.0,
) -> dict:
    """Return one user's Stripe Connect + KYC compliance snapshot."""
    tournament_db.initialize_tournament_database()
    email = str(user_email or "").strip().lower()
    if not email:
        return {
            "user_email": "",
            "stripe_connect_account_id": "",
            "onboarding_status": "not_started",
            "details_submitted": False,
            "payouts_enabled": False,
            "requirements": {},
            "kyc_verified": False,
            "kyc_verified_at": "",
            "last_synced_at": "",
            "compliance_year": int(compliance_year or datetime.now(timezone.utc).year),
            "paid_payout_total_usd": 0.0,
            "kyc_threshold_usd": float(kyc_threshold_usd),
            "kyc_required": False,
            "compliant": False,
        }

    with tournament_db.get_tournament_connection() as conn:
        row = conn.execute(
            """
            SELECT
                user_email,
                stripe_connect_account_id,
                stripe_connect_onboarding_status,
                stripe_connect_details_submitted,
                stripe_connect_payouts_enabled,
                stripe_connect_requirements_json,
                stripe_connect_kyc_verified,
                stripe_connect_kyc_verified_at,
                stripe_connect_last_synced_at
            FROM user_career_stats
            WHERE user_email = ?
            """,
            (email,),
        ).fetchone()

    item = dict(row) if row else {}
    paid_total = _compute_user_paid_payout_total(email, year=compliance_year)
    threshold = float(kyc_threshold_usd)
    kyc_required = bool(paid_total >= threshold)
    payouts_enabled = bool(int(item.get("stripe_connect_payouts_enabled", 0) or 0))
    kyc_verified = bool(int(item.get("stripe_connect_kyc_verified", 0) or 0))

    return {
        "user_email": email,
        "stripe_connect_account_id": str(item.get("stripe_connect_account_id", "") or ""),
        "onboarding_status": str(item.get("stripe_connect_onboarding_status", "not_started") or "not_started"),
        "details_submitted": bool(int(item.get("stripe_connect_details_submitted", 0) or 0)),
        "payouts_enabled": payouts_enabled,
        "requirements": _loads_json(item.get("stripe_connect_requirements_json"), {}),
        "kyc_verified": kyc_verified,
        "kyc_verified_at": str(item.get("stripe_connect_kyc_verified_at", "") or ""),
        "last_synced_at": str(item.get("stripe_connect_last_synced_at", "") or ""),
        "compliance_year": int(compliance_year or datetime.now(timezone.utc).year),
        "paid_payout_total_usd": paid_total,
        "kyc_threshold_usd": threshold,
        "kyc_required": kyc_required,
        "compliant": bool((not kyc_required) or (kyc_verified and payouts_enabled)),
    }


def create_user_connect_onboarding(
    user_email: str,
    *,
    refresh_path: str = "/",
    return_path: str = "/",
) -> dict:
    """Create/connect Stripe Connect account and return onboarding URL."""
    email = str(user_email or "").strip().lower()
    if not email:
        return {"success": False, "error": "user_email is required"}

    from tournament.stripe import create_connect_account, create_connect_onboarding_link

    current = get_user_connect_status(email)
    account_id = str(current.get("stripe_connect_account_id", "") or "")
    if not account_id:
        account_result = create_connect_account(email)
        if not account_result.get("success", False):
            return {"success": False, "error": str(account_result.get("error", "Connect account creation failed"))}
        account_id = str(account_result.get("account_id", "") or "")

    link_result = create_connect_onboarding_link(
        account_id,
        refresh_path=str(refresh_path or "/"),
        return_path=str(return_path or "/"),
    )
    if not link_result.get("success", False):
        return {"success": False, "error": str(link_result.get("error", "Onboarding link creation failed"))}

    upsert_user_connect_status(
        email,
        stripe_connect_account_id=account_id,
        onboarding_status="onboarding_link_created",
        details_submitted=bool(current.get("details_submitted", False)),
        payouts_enabled=bool(current.get("payouts_enabled", False)),
        requirements=dict(current.get("requirements") or {}),
        kyc_verified=bool(current.get("kyc_verified", False)),
        kyc_verified_at=str(current.get("kyc_verified_at", "") or ""),
    )

    return {
        "success": True,
        "user_email": email,
        "stripe_connect_account_id": account_id,
        "onboarding_url": str(link_result.get("url", "") or ""),
        "expires_at": str(link_result.get("expires_at", "") or ""),
    }


def sync_user_connect_status_from_stripe(user_email: str) -> dict:
    """Refresh Stripe Connect account details and persist KYC/compliance flags."""
    email = str(user_email or "").strip().lower()
    current = get_user_connect_status(email)
    account_id = str(current.get("stripe_connect_account_id", "") or "")
    if not account_id:
        return {"success": False, "error": "No Stripe Connect account found for user"}

    from tournament.stripe import get_connect_account_status

    remote = get_connect_account_status(account_id)
    if not remote.get("success", False):
        return {"success": False, "error": str(remote.get("error", "Could not fetch Connect status"))}

    requirements = dict(remote.get("requirements") or {})
    currently_due = list(requirements.get("currently_due") or [])
    details_submitted = bool(remote.get("details_submitted", False))
    payouts_enabled = bool(remote.get("payouts_enabled", False))
    kyc_verified = bool(details_submitted and payouts_enabled and not currently_due)
    onboarding_status = "verified" if kyc_verified else ("in_review" if details_submitted else "pending")

    put = upsert_user_connect_status(
        email,
        stripe_connect_account_id=account_id,
        onboarding_status=onboarding_status,
        details_submitted=details_submitted,
        payouts_enabled=payouts_enabled,
        requirements=requirements,
        kyc_verified=kyc_verified,
        kyc_verified_at=(datetime.now(timezone.utc).isoformat() if kyc_verified else ""),
    )
    if not put.get("success", False):
        return put

    out = get_user_connect_status(email)
    return {"success": True, "result": out}


def evaluate_user_payout_eligibility(
    user_email: str,
    *,
    compliance_year: int | None = None,
    kyc_threshold_usd: float = 600.0,
) -> dict:
    """Evaluate whether user is payout-eligible under Connect/KYC rules."""
    status = get_user_connect_status(
        user_email,
        compliance_year=compliance_year,
        kyc_threshold_usd=kyc_threshold_usd,
    )
    reasons: list[str] = []
    if not str(status.get("stripe_connect_account_id", "") or ""):
        reasons.append("No Stripe Connect account on file")
    if not bool(status.get("details_submitted", False)):
        reasons.append("Connect onboarding details are incomplete")
    if not bool(status.get("payouts_enabled", False)):
        reasons.append("Stripe payouts are not enabled")
    if bool(status.get("kyc_required", False)) and not bool(status.get("kyc_verified", False)):
        reasons.append("KYC/1099 verification required for payouts above threshold")

    return {
        "success": True,
        "allowed": len(reasons) == 0,
        "reasons": reasons,
        "user_email": str(user_email or "").strip().lower(),
        "status": status,
    }


def list_due_payout_entries(
    *,
    sla_hours: int = 24,
    limit: int = 200,
    include_not_due: bool = False,
    now: datetime | None = None,
) -> list[dict]:
    """List payout rows due under SLA window from tournament resolution time."""
    tournament_db.initialize_tournament_database()
    now_dt = now or datetime.now(timezone.utc)
    hours = max(1, int(sla_hours))

    with tournament_db.get_tournament_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                e.entry_id,
                e.tournament_id,
                e.user_email,
                e.payout_amount,
                e.payout_status,
                t.tournament_name,
                t.resolved_at,
                t.lock_time
            FROM tournament_entries e
            JOIN tournaments t ON t.tournament_id = e.tournament_id
            WHERE t.status = 'resolved'
              AND COALESCE(e.payout_amount, 0) > 0
              AND COALESCE(e.payout_status, 'pending') <> 'paid'
            ORDER BY COALESCE(t.resolved_at, t.lock_time) ASC, e.entry_id ASC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()

    out: list[dict] = []
    for row in rows:
        item = dict(row)
        resolved_dt = _parse_iso_utc(str(item.get("resolved_at", "") or "")) or _parse_iso_utc(str(item.get("lock_time", "") or ""))
        if resolved_dt is None:
            continue

        due_at = resolved_dt + timedelta(hours=hours)
        is_due = due_at <= now_dt
        if not include_not_due and not is_due:
            continue

        overdue_hours = max(0.0, (now_dt - due_at).total_seconds() / 3600.0)
        item["due_at"] = due_at.isoformat()
        item["is_due"] = is_due
        item["is_overdue"] = bool(is_due and overdue_hours > 0)
        item["overdue_hours"] = round(float(overdue_hours), 2)
        out.append(item)

    out.sort(key=lambda r: (0 if bool(r.get("is_overdue", False)) else 1, str(r.get("due_at", "")), int(r.get("entry_id", 0) or 0)))
    return out[: max(1, int(limit))]


def process_due_payouts(
    *,
    sla_hours: int = 24,
    max_tournaments: int = 50,
    now: datetime | None = None,
) -> dict:
    """Process payouts for tournaments containing due payout rows."""
    due_rows = list_due_payout_entries(
        sla_hours=max(1, int(sla_hours)),
        limit=max(1, int(max_tournaments)) * 100,
        include_not_due=False,
        now=now,
    )
    tournament_ids: list[int] = []
    seen: set[int] = set()
    for row in due_rows:
        tid = int(row.get("tournament_id", 0) or 0)
        if tid <= 0 or tid in seen:
            continue
        seen.add(tid)
        tournament_ids.append(tid)
        if len(tournament_ids) >= max(1, int(max_tournaments)):
            break

    transferred = 0
    failed = 0
    processed = 0
    from tournament.payout_runner import process_resolved_tournament_payouts

    for tid in tournament_ids:
        result = process_resolved_tournament_payouts(int(tid))
        if result.get("success", False):
            processed += 1
            transferred += int(result.get("transferred", 0) or 0)
            failed += int(result.get("failed", 0) or 0)

    return {
        "success": True,
        "sla_hours": max(1, int(sla_hours)),
        "due_entries": len(due_rows),
        "processed_tournaments": processed,
        "transferred": transferred,
        "failed": failed,
    }


def list_championship_history(limit: int = 25) -> list[dict]:
    """Return championship winners ordered newest-first."""
    tournament_db.initialize_tournament_database()
    with tournament_db.get_tournament_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                championship_id,
                season_label,
                tournament_id,
                winner_email,
                winner_display_name,
                winning_score,
                payout_amount,
                roster_json,
                created_at
            FROM championship_history
            ORDER BY created_at DESC, championship_id DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()

    out: list[dict] = []
    for row in rows:
        item = dict(row)
        item["roster"] = _loads_json(item.get("roster_json"), [])
        out.append(item)
    return out


def get_championship_overview() -> dict:
    """Return a compact championship status summary for the record books page."""
    tournament_db.initialize_tournament_database()
    with tournament_db.get_tournament_connection() as conn:
        latest = conn.execute(
            """
            SELECT tournament_id, tournament_name, status, entry_fee, lock_time, created_at
            FROM tournaments
            WHERE court_tier = 'Championship'
            ORDER BY created_at DESC, tournament_id DESC
            LIMIT 1
            """
        ).fetchone()

        total_championships = conn.execute(
            "SELECT COUNT(*) AS c FROM tournaments WHERE court_tier = 'Championship'"
        ).fetchone()
        resolved_championships = conn.execute(
            "SELECT COUNT(*) AS c FROM tournaments WHERE court_tier = 'Championship' AND status = 'resolved'"
        ).fetchone()

        active_entries = 0
        estimated_purse = 0.0
        if latest is not None:
            active_entries_row = conn.execute(
                "SELECT COUNT(*) AS c FROM tournament_entries WHERE tournament_id = ?",
                (int(latest["tournament_id"]),),
            ).fetchone()
            active_entries = int((active_entries_row or {"c": 0})["c"] or 0)
            estimated_purse = float(latest["entry_fee"] or 0.0) * float(active_entries)

    return {
        "latest_tournament": dict(latest) if latest else None,
        "active_entries": active_entries,
        "estimated_purse": round(float(estimated_purse), 2),
        "total_championships": int((total_championships or {"c": 0})["c"] or 0),
        "resolved_championships": int((resolved_championships or {"c": 0})["c"] or 0),
    }


def get_season_awards_snapshot() -> dict:
    """Compute lightweight season awards directly from tournament/career data.

    Includes MVP, DPOY, GM of the Year, Clutch Award, Sharp, Money Maker,
    and Volume Grinder per the master plan Section IX.
    """
    tournament_db.initialize_tournament_database()
    with tournament_db.get_tournament_connection() as conn:
        mvp = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(display_name, ''), user_email) AS winner,
                AVG(total_score) AS value,
                COUNT(*) AS samples
            FROM tournament_entries
            GROUP BY user_email
            HAVING COUNT(*) >= 3
            ORDER BY value DESC
            LIMIT 1
            """
        ).fetchone()

        sharp = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(display_name, ''), user_email) AS winner,
                lifetime_entries,
                lifetime_wins,
                CASE
                    WHEN lifetime_entries > 0 THEN (CAST(lifetime_wins AS REAL) / CAST(lifetime_entries AS REAL))
                    ELSE 0.0
                END AS win_rate
            FROM user_career_stats
            WHERE lifetime_entries >= 5
            ORDER BY win_rate DESC, lifetime_entries DESC
            LIMIT 1
            """
        ).fetchone()

        money_maker = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(display_name, ''), user_email) AS winner,
                lifetime_earnings AS value
            FROM user_career_stats
            ORDER BY lifetime_earnings DESC
            LIMIT 1
            """
        ).fetchone()

        volume = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(display_name, ''), user_email) AS winner,
                lifetime_entries AS value
            FROM user_career_stats
            ORDER BY lifetime_entries DESC
            LIMIT 1
            """
        ).fetchone()

        # DPOY — highest total steals+blocks FP across all tournament entries
        dpoy = conn.execute(
            """
            SELECT
                e.user_email,
                COALESCE(NULLIF(e.display_name, ''), e.user_email) AS winner,
                SUM(
                    COALESCE(json_extract(ss.line_json, '$.steals'), 0) * 3.0 +
                    COALESCE(json_extract(ss.line_json, '$.blocks'), 0) * 3.0
                ) AS defensive_fp,
                COUNT(DISTINCT e.tournament_id) AS samples
            FROM tournament_entries e
            JOIN simulated_scores ss ON ss.tournament_id = e.tournament_id
            WHERE e.rank IS NOT NULL
            GROUP BY e.user_email
            HAVING COUNT(DISTINCT e.tournament_id) >= 3
            ORDER BY defensive_fp DESC
            LIMIT 1
            """
        ).fetchone()

        # GM of the Year — best salary efficiency (score per $1K salary)
        gm = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(e.display_name, ''), e.user_email) AS winner,
                AVG(e.total_score) AS avg_score,
                COUNT(*) AS samples
            FROM tournament_entries e
            JOIN tournaments t ON t.tournament_id = e.tournament_id
            WHERE e.rank IS NOT NULL AND t.status = 'resolved'
            GROUP BY e.user_email
            HAVING COUNT(*) >= 3
            ORDER BY avg_score DESC
            LIMIT 1
            """
        ).fetchone()

        # Clutch Award — most wins by <3 FP margin over 2nd place
        clutch = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(w.display_name, ''), w.user_email) AS winner,
                COUNT(*) AS clutch_wins
            FROM tournament_entries w
            JOIN tournament_entries r ON r.tournament_id = w.tournament_id AND r.rank = 2
            WHERE w.rank = 1 AND (w.total_score - r.total_score) < 3.0
                AND (w.total_score - r.total_score) > 0
            GROUP BY w.user_email
            ORDER BY clutch_wins DESC
            LIMIT 1
            """
        ).fetchone()

    mvp_d = _row_to_dict(mvp)
    sharp_d = _row_to_dict(sharp)
    money_d = _row_to_dict(money_maker)
    volume_d = _row_to_dict(volume)
    dpoy_d = _row_to_dict(dpoy)
    gm_d = _row_to_dict(gm)
    clutch_d = _row_to_dict(clutch)

    return {
        "mvp": {
            "winner": str(mvp_d.get("winner", "")),
            "average_score": round(float(mvp_d.get("value", 0.0) or 0.0), 2),
            "sample_size": int(mvp_d.get("samples", 0) or 0),
        },
        "dpoy": {
            "winner": str(dpoy_d.get("winner", "")),
            "defensive_fp": round(float(dpoy_d.get("defensive_fp", 0.0) or 0.0), 2),
            "sample_size": int(dpoy_d.get("samples", 0) or 0),
        },
        "gm_of_the_year": {
            "winner": str(gm_d.get("winner", "")),
            "avg_score": round(float(gm_d.get("avg_score", 0.0) or 0.0), 2),
            "sample_size": int(gm_d.get("samples", 0) or 0),
        },
        "clutch_award": {
            "winner": str(clutch_d.get("winner", "")),
            "clutch_wins": int(clutch_d.get("clutch_wins", 0) or 0),
        },
        "sharp": {
            "winner": str(sharp_d.get("winner", "")),
            "win_rate": round(float(sharp_d.get("win_rate", 0.0) or 0.0), 4),
            "entries": int(sharp_d.get("lifetime_entries", 0) or 0),
            "wins": int(sharp_d.get("lifetime_wins", 0) or 0),
        },
        "money_maker": {
            "winner": str(money_d.get("winner", "")),
            "earnings": round(float(money_d.get("value", 0.0) or 0.0), 2),
        },
        "volume_grinder": {
            "winner": str(volume_d.get("winner", "")),
            "entries": int(volume_d.get("value", 0) or 0),
        },
    }


def get_all_time_records() -> dict:
    """Return all-time records used by the record books page."""
    tournament_db.initialize_tournament_database()
    with tournament_db.get_tournament_connection() as conn:
        highest_score = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(display_name, ''), user_email) AS holder,
                MAX(total_score) AS value
            FROM tournament_entries
            """
        ).fetchone()

        best_avg = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(display_name, ''), user_email) AS holder,
                AVG(total_score) AS value,
                COUNT(*) AS sample_size
            FROM tournament_entries
            GROUP BY user_email
            HAVING COUNT(*) >= 3
            ORDER BY value DESC
            LIMIT 1
            """
        ).fetchone()

        most_tournaments = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(display_name, ''), user_email) AS holder,
                lifetime_entries AS value
            FROM user_career_stats
            ORDER BY lifetime_entries DESC
            LIMIT 1
            """
        ).fetchone()

        highest_win_rate = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(display_name, ''), user_email) AS holder,
                CASE
                    WHEN lifetime_entries > 0 THEN (CAST(lifetime_wins AS REAL) / CAST(lifetime_entries AS REAL))
                    ELSE 0.0
                END AS value,
                lifetime_entries AS sample_size
            FROM user_career_stats
            WHERE lifetime_entries >= 5
            ORDER BY value DESC, lifetime_entries DESC
            LIMIT 1
            """
        ).fetchone()

        total_winnings = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(display_name, ''), user_email) AS holder,
                lifetime_earnings AS value
            FROM user_career_stats
            ORDER BY lifetime_earnings DESC
            LIMIT 1
            """
        ).fetchone()

        best_roi = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(ucs.display_name, ''), ucs.user_email) AS holder,
                CASE
                    WHEN fees.total_fees > 0 THEN ((ucs.lifetime_earnings - fees.total_fees) / fees.total_fees)
                    ELSE 0.0
                END AS value,
                ucs.lifetime_entries AS sample_size
            FROM user_career_stats ucs
            JOIN (
                SELECT
                    te.user_email,
                    SUM(COALESCE(t.entry_fee, 0.0)) AS total_fees
                FROM tournament_entries te
                JOIN tournaments t ON t.tournament_id = te.tournament_id
                GROUP BY te.user_email
            ) fees ON fees.user_email = ucs.user_email
            WHERE ucs.lifetime_entries >= 3
            ORDER BY value DESC
            LIMIT 1
            """
        ).fetchone()

        badge_king = conn.execute(
            """
            SELECT
                al.user_email,
                COALESCE(NULLIF(ucs.display_name, ''), al.user_email) AS holder,
                COUNT(*) AS value
            FROM awards_log al
            LEFT JOIN user_career_stats ucs ON ucs.user_email = al.user_email
            WHERE LOWER(al.award_type) LIKE '%badge%'
            GROUP BY al.user_email, holder
            ORDER BY value DESC
            LIMIT 1
            """
        ).fetchone()

    highest_score_d = _row_to_dict(highest_score)
    best_avg_d = _row_to_dict(best_avg)
    most_tournaments_d = _row_to_dict(most_tournaments)
    highest_win_rate_d = _row_to_dict(highest_win_rate)
    total_winnings_d = _row_to_dict(total_winnings)
    best_roi_d = _row_to_dict(best_roi)
    badge_king_d = _row_to_dict(badge_king)

    return {
        "scoring": [
            {
                "name": "Highest Score",
                "holder": str(highest_score_d.get("holder", "-")),
                "value": round(float(highest_score_d.get("value", 0.0) or 0.0), 2),
            },
            {
                "name": "Best Average Score",
                "holder": str(best_avg_d.get("holder", "-")),
                "value": round(float(best_avg_d.get("value", 0.0) or 0.0), 2),
                "sample_size": int(best_avg_d.get("sample_size", 0) or 0),
            },
        ],
        "gameplay": [
            {
                "name": "Most Tournaments",
                "holder": str(most_tournaments_d.get("holder", "-")),
                "value": int(most_tournaments_d.get("value", 0) or 0),
            },
            {
                "name": "Highest Win %",
                "holder": str(highest_win_rate_d.get("holder", "-")),
                "value": round(float(highest_win_rate_d.get("value", 0.0) or 0.0), 4),
                "sample_size": int(highest_win_rate_d.get("sample_size", 0) or 0),
            },
            {
                "name": "Total Winnings",
                "holder": str(total_winnings_d.get("holder", "-")),
                "value": round(float(total_winnings_d.get("value", 0.0) or 0.0), 2),
            },
            {
                "name": "Best ROI",
                "holder": str(best_roi_d.get("holder", "-")),
                "value": round(float(best_roi_d.get("value", 0.0) or 0.0), 4),
                "sample_size": int(best_roi_d.get("sample_size", 0) or 0),
            },
            {
                "name": "Badges Earned",
                "holder": str(badge_king_d.get("holder", "-")),
                "value": int(badge_king_d.get("value", 0) or 0),
            },
        ],
    }


def list_badge_leaders(limit: int = 10) -> list[dict]:
    """Return badge leaderboard based on awards_log badge grants."""
    tournament_db.initialize_tournament_database()
    with tournament_db.get_tournament_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                al.user_email,
                COALESCE(NULLIF(ucs.display_name, ''), al.user_email) AS display_name,
                COUNT(*) AS badge_count,
                MAX(al.granted_at) AS last_badge_at
            FROM awards_log al
            LEFT JOIN user_career_stats ucs ON ucs.user_email = al.user_email
            WHERE LOWER(al.award_type) LIKE '%badge%'
            GROUP BY al.user_email, display_name
            ORDER BY badge_count DESC, last_badge_at DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()

    out: list[dict] = []
    for idx, row in enumerate(rows, start=1):
        item = dict(row)
        count = int(item.get("badge_count", 0) or 0)
        if count >= 25:
            milestone = "Master Badge Collector"
        elif count >= 15:
            milestone = "Elite Achievement Holder"
        elif count >= 8:
            milestone = "Gold Badge Rank"
        elif count >= 4:
            milestone = "Silver Badge Rank"
        elif count >= 1:
            milestone = "Bronze Badge Rank"
        else:
            milestone = "No badge milestone"
        item["rank"] = idx
        item["milestone"] = milestone
        out.append(item)
    return out


def list_hall_of_fame_candidates(
    limit: int = 20,
    min_lp: int = 2000,
    min_championship_wins: int = 5,
    min_wins: int = 50,
) -> list[dict]:
    """Return Hall of Fame candidates: 2,000+ LP, 5+ Championships, 50+ wins.

    Per Section IX of the master plan, the criteria are:
      - 2,000+ lifetime LP
      - 5+ Championship wins
      - 50+ lifetime wins
    """
    tournament_db.initialize_tournament_database()
    with tournament_db.get_tournament_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                ucs.user_email,
                COALESCE(NULLIF(ucs.display_name, ''), ucs.user_email) AS display_name,
                ucs.lifetime_entries,
                ucs.lifetime_wins,
                ucs.lifetime_top5,
                ucs.lifetime_earnings,
                ucs.lifetime_lp,
                ucs.career_level,
                CASE
                    WHEN ucs.lifetime_entries > 0 THEN (CAST(ucs.lifetime_wins AS REAL) / CAST(ucs.lifetime_entries AS REAL))
                    ELSE 0.0
                END AS win_rate,
                COALESCE(ch.championship_wins, 0) AS championship_wins
            FROM user_career_stats ucs
            LEFT JOIN (
                SELECT winner_email, COUNT(*) AS championship_wins
                FROM championship_history
                GROUP BY winner_email
            ) ch ON ch.winner_email = ucs.user_email
            WHERE ucs.lifetime_lp >= ?
              AND ucs.lifetime_wins >= ?
              AND COALESCE(ch.championship_wins, 0) >= ?
            ORDER BY ucs.lifetime_lp DESC, ucs.lifetime_wins DESC, ucs.lifetime_earnings DESC
            LIMIT ?
            """,
            (
                max(0, int(min_lp)),
                max(0, int(min_wins)),
                max(0, int(min_championship_wins)),
                max(1, int(limit)),
            ),
        ).fetchall()

    out: list[dict] = []
    for idx, row in enumerate(rows, start=1):
        item = dict(row)
        item["rank"] = idx
        out.append(item)
    return out


def _validate_entry(tournament: dict, roster: list[dict]) -> tuple[bool, str]:
    if not roster:
        return False, "Roster is required"

    # For paid tournaments we enforce 9 slots including legend.
    is_paid = float(tournament.get("entry_fee", 0.0)) > 0
    required_slots = 9 if is_paid else 8
    if len(roster) != required_slots:
        return False, f"Roster must include exactly {required_slots} players"

    seen = set()
    active_salary = 0
    legend_salary = 0
    for player in roster:
        pid = str(player.get("player_id", ""))
        if not pid:
            return False, "Each roster player must include player_id"
        if pid in seen:
            return False, "Roster cannot include duplicate players"
        seen.add(pid)

        sal = int(player.get("salary", 0) or 0)
        if bool(player.get("is_legend", False)):
            legend_salary += sal
        else:
            active_salary += sal

    if is_paid:
        if legend_salary <= 0:
            return False, "Paid tournaments require one legend"
        if active_salary > 50000:
            return False, "Active salary cap exceeded"
        if active_salary < 40000:
            return False, "Active salary floor not met"
        if legend_salary > 15000:
            return False, "Legend salary cap exceeded"

    return True, ""


def submit_entry(
    tournament_id: int,
    user_email: str,
    display_name: str,
    roster: list[dict],
    stripe_payment_intent_id: str = "",
) -> tuple[bool, str, int | None]:
    """Submit one user entry into a tournament."""
    tournament = get_tournament(tournament_id)
    if not tournament:
        log_event(
            "entry.submit_failed",
            f"Entry submit failed: tournament #{tournament_id} not found",
            tournament_id=tournament_id,
            user_email=user_email,
            severity="warning",
        )
        return False, "Tournament not found", None
    if tournament.get("status") != "open":
        log_event(
            "entry.submit_failed",
            f"Entry submit failed: tournament #{tournament_id} is not open",
            tournament_id=tournament_id,
            user_email=user_email,
            severity="warning",
        )
        return False, "Tournament is not open", None

    valid, reason = _validate_entry(tournament, roster)
    if not valid:
        log_event(
            "entry.submit_failed",
            f"Entry submit failed: {reason}",
            tournament_id=tournament_id,
            user_email=user_email,
            severity="warning",
        )
        return False, reason, None

    pending_success_event = None
    pending_success_notification = None
    success_payload = None
    deferred_failure_event = None
    failure_payload = None

    with tournament_db.get_tournament_connection() as conn:
        existing_entries = conn.execute(
            "SELECT COUNT(1) AS c FROM tournament_entries WHERE tournament_id = ?",
            (int(tournament_id),),
        ).fetchone()["c"]
        if int(existing_entries) >= int(tournament.get("max_entries", 0)):
            log_event(
                "entry.submit_failed",
                f"Entry submit failed: tournament #{tournament_id} full",
                tournament_id=tournament_id,
                user_email=user_email,
                severity="warning",
            )
            return False, "Tournament is full", None

        active_salary = sum(int(p.get("salary", 0) or 0) for p in roster if not bool(p.get("is_legend", False)))
        legend_salary = sum(int(p.get("salary", 0) or 0) for p in roster if bool(p.get("is_legend", False)))

        try:
            cursor = conn.execute(
                """
                INSERT INTO tournament_entries
                    (tournament_id, user_email, display_name, roster_json,
                     total_score, stripe_payment_intent_id, created_at)
                VALUES (?, ?, ?, ?, 0.0, ?, datetime('now'))
                """,
                (
                    int(tournament_id),
                    user_email.strip().lower(),
                    display_name.strip(),
                    json.dumps(roster),
                    stripe_payment_intent_id,
                ),
            )
            conn.commit()
            entry_id = int(cursor.lastrowid)
            pending_success_event = {
                "event_type": "entry.submitted",
                "message": f"Entry #{entry_id} submitted for tournament #{tournament_id}",
                "tournament_id": tournament_id,
                "entry_id": entry_id,
                "user_email": user_email,
                "metadata": {
                    "active_salary": active_salary,
                    "legend_salary": legend_salary,
                    "player_count": len(roster),
                },
            }
            pending_success_notification = {
                "notification_key": "entry_accepted",
                "message": f"Entry accepted for tournament #{tournament_id}",
                "tournament_id": tournament_id,
                "entry_id": entry_id,
                "user_email": user_email,
            }
            success_payload = (True, f"Entry submitted (${active_salary}+${legend_salary})", entry_id)
        except sqlite3.IntegrityError:
            conn.rollback()
            deferred_failure_event = {
                "event_type": "entry.submit_failed",
                "message": "Entry submit failed: duplicate entry for user",
                "tournament_id": tournament_id,
                "user_email": user_email,
                "severity": "warning",
            }
            failure_payload = (False, "User already entered this tournament", None)
        except Exception as exc:
            conn.rollback()
            deferred_failure_event = {
                "event_type": "entry.submit_failed",
                "message": f"Entry submit failed: {exc}",
                "tournament_id": tournament_id,
                "user_email": user_email,
                "severity": "error",
            }
            failure_payload = (False, f"Entry failed: {exc}", None)

    if deferred_failure_event:
        log_event(**deferred_failure_event)
        return failure_payload or (False, "Entry failed", None)

    if pending_success_event:
        log_event(**pending_success_event)
    if pending_success_notification:
        send_notification(**pending_success_notification)
    if success_payload:
        return success_payload

    return False, "Entry failed", None


def submit_paid_entry_after_checkout(
    tournament_id: int,
    user_email: str,
    display_name: str,
    roster: list[dict],
    checkout_session_id: str,
) -> tuple[bool, str, int | None]:
    """Finalize a paid entry after Stripe Checkout success callback."""
    tournament = get_tournament(tournament_id)
    if not tournament:
        return False, "Tournament not found", None

    if float(tournament.get("entry_fee", 0.0) or 0.0) <= 0.0:
        return False, "Tournament is not paid", None

    session_id = str(checkout_session_id or "").strip()
    if not session_id:
        return False, "checkout_session_id is required", None

    email = str(user_email or "").strip().lower()

    # Idempotent finalize: if this checkout/payment reference already created an
    # entry, return success with the existing entry id.
    with tournament_db.get_tournament_connection() as conn:
        existing = conn.execute(
            """
            SELECT entry_id, user_email
            FROM tournament_entries
            WHERE tournament_id = ? AND stripe_payment_intent_id = ?
            ORDER BY entry_id ASC
            LIMIT 1
            """,
            (int(tournament_id), session_id),
        ).fetchone()
        if existing:
            existing_email = str(existing["user_email"] or "").strip().lower()
            if existing_email and email and existing_email != email:
                return False, "checkout_session_id already used by a different user", None
            return True, "Entry already finalized", int(existing["entry_id"])

    # We persist the checkout session ID in stripe_payment_intent_id for now.
    # This keeps a durable payment reference in the isolated subsystem.
    ok, message, entry_id = submit_entry(
        tournament_id=tournament_id,
        user_email=user_email,
        display_name=display_name,
        roster=roster,
        stripe_payment_intent_id=session_id,
    )
    if not ok or not entry_id:
        return ok, message, entry_id

    try:
        from tournament.referrals import apply_first_paid_entry_referral_credit

        referral_result = apply_first_paid_entry_referral_credit(
            referred_user_email=email,
            paid_entry_id=int(entry_id),
            credit_amount=5.0,
            monthly_cap=50.0,
        )
        if referral_result.get("applied", False):
            amount = float(referral_result.get("credited_amount", 0.0) or 0.0)
            referrer = str(referral_result.get("referrer_email", "") or "")
            message = f"{message} | referral credit applied: ${amount:.2f} to {referrer}"
    except Exception:
        pass

    return ok, message, entry_id


def save_pending_paid_entry(
    tournament_id: int,
    user_email: str,
    display_name: str,
    roster: list[dict],
    checkout_session_id: str,
) -> bool:
    """Persist a pending paid entry keyed by Stripe checkout session id."""
    sid = str(checkout_session_id or "").strip()
    if not sid:
        return False

    with tournament_db.get_tournament_connection() as conn:
        try:
            conn.execute(
                """
                INSERT INTO pending_paid_entries
                    (checkout_session_id, tournament_id, user_email, display_name, roster_json,
                     status, payment_intent_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'pending', '', datetime('now'), datetime('now'))
                ON CONFLICT(checkout_session_id) DO UPDATE SET
                    tournament_id = excluded.tournament_id,
                    user_email = excluded.user_email,
                    display_name = excluded.display_name,
                    roster_json = excluded.roster_json,
                    status = 'pending',
                    updated_at = datetime('now')
                """,
                (
                    sid,
                    int(tournament_id),
                    str(user_email or "").strip().lower(),
                    str(display_name or "").strip(),
                    json.dumps(roster or []),
                ),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False


def get_pending_paid_entry(checkout_session_id: str) -> dict | None:
    """Read one pending paid entry payload by checkout session id."""
    sid = str(checkout_session_id or "").strip()
    if not sid:
        return None

    with tournament_db.get_tournament_connection() as conn:
        row = conn.execute(
            """
            SELECT pending_id, checkout_session_id, tournament_id, user_email,
                   display_name, roster_json, status, payment_intent_id,
                   created_at, updated_at
            FROM pending_paid_entries
            WHERE checkout_session_id = ?
            """,
            (sid,),
        ).fetchone()
        if not row:
            return None

    item = dict(row)
    item["roster"] = _loads_json(item.get("roster_json"), [])
    return item


def list_pending_paid_entries(status: str | None = None, limit: int = 200) -> list[dict]:
    """List pending paid entry records for operations visibility."""
    params: list[Any] = []
    query = (
        "SELECT pending_id, checkout_session_id, tournament_id, user_email, display_name, "
        "status, payment_intent_id, created_at, updated_at "
        "FROM pending_paid_entries"
    )

    if status:
        query += " WHERE status = ?"
        params.append(str(status).strip().lower())

    query += " ORDER BY updated_at DESC, pending_id DESC LIMIT ?"
    params.append(max(1, int(limit)))

    with tournament_db.get_tournament_connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def expire_stale_pending_paid_entries(max_age_hours: int = 24, now: datetime | None = None) -> int:
    """Mark old pending checkout records as expired and return count updated."""
    threshold = now or datetime.now(timezone.utc)
    if threshold.tzinfo is None:
        threshold = threshold.replace(tzinfo=timezone.utc)
    threshold = threshold - timedelta(hours=max(1, int(max_age_hours)))

    with tournament_db.get_tournament_connection() as conn:
        rows = conn.execute(
            """
            SELECT pending_id, created_at
            FROM pending_paid_entries
            WHERE status = 'pending'
            """
        ).fetchall()

        to_expire_ids: list[int] = []
        for row in rows:
            created_raw = str(row["created_at"] or "").strip()
            if not created_raw:
                continue

            try:
                # SQLite datetime('now') format: YYYY-MM-DD HH:MM:SS
                created_dt = datetime.fromisoformat(created_raw.replace(" ", "T"))
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            if created_dt <= threshold:
                to_expire_ids.append(int(row["pending_id"]))

        if not to_expire_ids:
            return 0

        placeholders = ",".join("?" for _ in to_expire_ids)
        cursor = conn.execute(
            f"""
            UPDATE pending_paid_entries
            SET status = 'expired', updated_at = datetime('now')
            WHERE pending_id IN ({placeholders})
            """,
            tuple(to_expire_ids),
        )
        conn.commit()
        return int(cursor.rowcount or 0)


def mark_pending_paid_entry_finalized(checkout_session_id: str, payment_intent_id: str = "") -> bool:
    """Mark a pending paid entry record as finalized after successful submit."""
    sid = str(checkout_session_id or "").strip()
    if not sid:
        return False

    with tournament_db.get_tournament_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE pending_paid_entries
            SET status = 'finalized',
                payment_intent_id = CASE
                    WHEN ? = '' THEN payment_intent_id
                    ELSE ?
                END,
                updated_at = datetime('now')
            WHERE checkout_session_id = ?
            """,
            (str(payment_intent_id or "").strip(), str(payment_intent_id or "").strip(), sid),
        )
        conn.commit()
        return int(cursor.rowcount or 0) > 0


def finalize_pending_paid_entry(checkout_session_id: str, payment_reference: str = "") -> dict:
    """Finalize one pending paid entry by checkout session id."""
    pending = get_pending_paid_entry(checkout_session_id)
    if not pending:
        log_event(
            "pending.finalize_failed",
            "Manual pending finalization failed: pending record not found",
            severity="warning",
            metadata={"checkout_session_id": str(checkout_session_id or "").strip()},
        )
        return {"success": False, "error": "Pending paid entry not found", "entry_id": None}

    ref = str(payment_reference or "").strip()
    if not ref:
        ref = str(pending.get("payment_intent_id", "") or "").strip()
    if not ref:
        ref = str(checkout_session_id or "").strip()

    ok, msg, entry_id = submit_paid_entry_after_checkout(
        tournament_id=int(pending.get("tournament_id", 0) or 0),
        user_email=str(pending.get("user_email", "")),
        display_name=str(pending.get("display_name", "")),
        roster=list(pending.get("roster", [])),
        checkout_session_id=ref,
    )
    if not ok:
        log_event(
            "pending.finalize_failed",
            f"Manual pending finalization failed: {msg}",
            tournament_id=int(pending.get("tournament_id", 0) or 0),
            user_email=str(pending.get("user_email", "")),
            severity="warning",
            metadata={
                "checkout_session_id": str(checkout_session_id or "").strip(),
                "payment_reference": ref,
            },
        )
        return {"success": False, "error": msg, "entry_id": None}

    mark_pending_paid_entry_finalized(str(checkout_session_id or ""), ref)
    log_event(
        "pending.finalized",
        f"Manual pending finalization succeeded for session {checkout_session_id}",
        tournament_id=int(pending.get("tournament_id", 0) or 0),
        entry_id=int(entry_id) if entry_id is not None else None,
        user_email=str(pending.get("user_email", "")),
        metadata={
            "checkout_session_id": str(checkout_session_id or "").strip(),
            "payment_reference": ref,
        },
    )
    return {"success": True, "message": msg, "entry_id": int(entry_id) if entry_id is not None else None}


def assess_pending_paid_entry(checkout_session_id: str) -> dict:
    """Return diagnostics and recommended next action for one pending paid entry."""
    sid = str(checkout_session_id or "").strip()
    if not sid:
        return {
            "success": False,
            "error": "checkout_session_id is required",
            "checkout_session_id": "",
            "recommended_action": "none",
        }

    pending = get_pending_paid_entry(sid)
    if not pending:
        return {
            "success": False,
            "error": "Pending paid entry not found",
            "checkout_session_id": sid,
            "recommended_action": "none",
        }

    tournament_id = int(pending.get("tournament_id", 0) or 0)
    tournament = get_tournament(tournament_id)

    checkout_record = None
    try:
        from tournament.webhooks import get_checkout_session_record

        checkout_record = get_checkout_session_record(sid)
    except Exception:
        checkout_record = None

    references = {sid}
    pending_ref = str(pending.get("payment_intent_id", "") or "").strip()
    if pending_ref:
        references.add(pending_ref)
    checkout_ref = str((checkout_record or {}).get("payment_intent_id", "") or "").strip()
    if checkout_ref:
        references.add(checkout_ref)

    existing_entry_id = None
    with tournament_db.get_tournament_connection() as conn:
        placeholders = ",".join("?" for _ in references)
        row = conn.execute(
            f"""
            SELECT entry_id
            FROM tournament_entries
            WHERE tournament_id = ?
              AND user_email = ?
              AND stripe_payment_intent_id IN ({placeholders})
            ORDER BY entry_id ASC
            LIMIT 1
            """,
            (
                tournament_id,
                str(pending.get("user_email", "") or "").strip().lower(),
                *tuple(references),
            ),
        ).fetchone()
        if row:
            existing_entry_id = int(row["entry_id"])

    pending_status = str(pending.get("status", "") or "").strip().lower()
    payment_status = str((checkout_record or {}).get("payment_status", "") or "").strip().lower()

    recommended_action = "investigate"
    can_finalize = False
    notes = []

    if existing_entry_id is not None and pending_status != "finalized":
        recommended_action = "mark_finalized"
        notes.append("Entry already exists; pending row is stale")
    elif pending_status == "finalized":
        recommended_action = "none"
        notes.append("Pending row already finalized")
    elif tournament is None:
        recommended_action = "investigate"
        notes.append("Tournament record missing")
    elif str(tournament.get("status", "")) != "open":
        recommended_action = "do_not_finalize"
        notes.append("Tournament is not open")
    elif payment_status in {"paid", "no_payment_required"}:
        recommended_action = "finalize_now"
        can_finalize = True
    elif checkout_record is None:
        recommended_action = "verify_with_stripe"
        notes.append("No persisted Stripe checkout record found")
    else:
        recommended_action = "await_payment"
        notes.append(f"Payment status is {payment_status or 'unknown'}")

    return {
        "success": True,
        "checkout_session_id": sid,
        "pending": {
            "pending_id": pending.get("pending_id"),
            "tournament_id": tournament_id,
            "user_email": pending.get("user_email"),
            "display_name": pending.get("display_name"),
            "status": pending_status,
            "payment_intent_id": pending.get("payment_intent_id"),
            "created_at": pending.get("created_at"),
            "updated_at": pending.get("updated_at"),
        },
        "tournament": {
            "tournament_id": int((tournament or {}).get("tournament_id", 0) or 0),
            "status": str((tournament or {}).get("status", "") or ""),
            "entry_fee": float((tournament or {}).get("entry_fee", 0.0) or 0.0),
        }
        if tournament
        else None,
        "checkout_record": {
            "session_id": (checkout_record or {}).get("session_id"),
            "payment_status": payment_status,
            "payment_intent_id": (checkout_record or {}).get("payment_intent_id"),
            "stripe_event_id": (checkout_record or {}).get("stripe_event_id"),
            "updated_at": (checkout_record or {}).get("updated_at"),
        }
        if checkout_record
        else None,
        "existing_entry_id": existing_entry_id,
        "recommended_action": recommended_action,
        "can_finalize": can_finalize,
        "notes": notes,
    }


def _normalize_reconcile_session_id(session_id: str, normalize_mode: str = "trim") -> str:
    text = str(session_id or "").strip()
    mode = str(normalize_mode or "trim").strip().lower()
    if mode == "trim_lower":
        return text.lower()
    return text


def _normalize_reconcile_session_ids(session_ids: list[str], normalize_mode: str = "trim") -> list[str]:
    mode = str(normalize_mode or "trim").strip().lower()
    if mode not in {"trim", "trim_lower"}:
        mode = "trim"
    return [
        _normalize_reconcile_session_id(str(s or ""), normalize_mode=mode)
        for s in list(session_ids or [])
        if str(s or "").strip()
    ]


def _first_mismatch(
    provided_ids: list[str],
    reference_ids: list[str],
    *,
    strict_order: bool,
) -> tuple[int | None, str, str]:
    left = list(provided_ids or [])
    right = list(reference_ids or [])
    if not strict_order:
        left = sorted(left)
        right = sorted(right)

    for idx in range(max(len(left), len(right))):
        provided_val = left[idx] if idx < len(left) else ""
        reference_val = right[idx] if idx < len(right) else ""
        if provided_val != reference_val:
            return idx, provided_val, reference_val
    return None, "", ""


def _load_reconcile_summary_event(event_id: int) -> dict[str, Any] | None:
    with tournament_db.get_tournament_connection() as conn:
        row = conn.execute(
            """
            SELECT event_id, event_type, metadata_json, created_at
            FROM tournament_events
            WHERE event_id = ?
            """,
            (int(event_id),),
        ).fetchone()

    if not row:
        return None

    metadata = _loads_json(str(row["metadata_json"] or "{}"), {})
    return {
        "event_id": int(row["event_id"]),
        "event_type": str(row["event_type"] or ""),
        "metadata": metadata,
        "created_at": str(row["created_at"] or ""),
    }


def _load_latest_reconcile_summary_event() -> dict[str, Any] | None:
    with tournament_db.get_tournament_connection() as conn:
        row = conn.execute(
            """
            SELECT event_id, event_type, metadata_json, created_at
            FROM tournament_events
            WHERE event_type = 'pending.reconcile_summary'
            ORDER BY event_id DESC
            LIMIT 1
            """
        ).fetchone()

    if not row:
        return None

    metadata = _loads_json(str(row["metadata_json"] or "{}"), {})
    return {
        "event_id": int(row["event_id"]),
        "event_type": str(row["event_type"] or ""),
        "metadata": metadata,
        "created_at": str(row["created_at"] or ""),
    }


def get_latest_reconcile_summary_event(scope: str = "attempted") -> dict:
    """Return metadata for the most recent reconcile summary event."""
    parsed_scope = str(scope or "attempted").strip().lower()
    if parsed_scope not in {"attempted", "candidates"}:
        parsed_scope = "attempted"

    latest = _load_latest_reconcile_summary_event()
    if not latest:
        return {
            "success": False,
            "error": "No reconcile summary event found",
            "event_id": 0,
            "scope": parsed_scope,
        }

    metadata = latest.get("metadata") or {}
    digest_key = "attempted_sessions_sha256" if parsed_scope == "attempted" else "candidate_sessions_sha256"

    return {
        "success": True,
        "event_id": int(latest.get("event_id", 0) or 0),
        "event_type": str(latest.get("event_type", "") or ""),
        "event_created_at": str(latest.get("created_at", "") or ""),
        "scope": parsed_scope,
        "event_digest_key": digest_key,
        "event_digest": str(metadata.get(digest_key, "") or "").strip(),
        "metadata": metadata,
    }


def compute_reconcile_digest(
    session_ids: list[str],
    strict_order: bool = True,
    normalize_mode: str = "trim",
) -> str:
    """Compute a deterministic SHA256 digest for a session-id list."""
    mode = str(normalize_mode or "trim").strip().lower()
    if mode not in {"trim", "trim_lower"}:
        mode = "trim"

    cleaned = _normalize_reconcile_session_ids(session_ids=session_ids, normalize_mode=mode)
    if not strict_order:
        cleaned = sorted(cleaned)
    return hashlib.sha256("|".join(cleaned).encode("utf-8")).hexdigest()


def verify_reconcile_digest(
    session_ids: list[str],
    digest: str,
    strict_order: bool = True,
    normalize_mode: str = "trim",
    reference_session_ids: list[str] | None = None,
) -> dict:
    """Verify a provided digest against a session-id list."""
    provided = str(digest or "").strip().lower()
    mode = str(normalize_mode or "trim").strip().lower()
    if mode not in {"trim", "trim_lower"}:
        mode = "trim"

    normalized_session_ids = _normalize_reconcile_session_ids(
        session_ids=session_ids,
        normalize_mode=mode,
    )

    if not provided:
        return {
            "success": False,
            "error": "digest is required",
            "match": False,
            "expected_digest": "",
            "provided_digest": "",
            "count": len(normalized_session_ids),
            "strict_order": bool(strict_order),
            "normalize_mode": mode,
            "order_insensitive_match": False,
            "mismatch_reason": "missing_digest",
        }

    expected = compute_reconcile_digest(
        session_ids=normalized_session_ids,
        strict_order=bool(strict_order),
        normalize_mode=mode,
    )

    order_insensitive_match = False
    mismatch_reason = ""
    if bool(strict_order) and expected != provided:
        relaxed = compute_reconcile_digest(
            session_ids=normalized_session_ids,
            strict_order=False,
            normalize_mode=mode,
        )
        order_insensitive_match = relaxed == provided
        mismatch_reason = "order_only" if order_insensitive_match else "digest_mismatch"

    result = {
        "success": True,
        "match": expected == provided,
        "expected_digest": expected,
        "provided_digest": provided,
        "count": len(normalized_session_ids),
        "strict_order": bool(strict_order),
        "normalize_mode": mode,
        "order_insensitive_match": bool(order_insensitive_match),
        "mismatch_reason": mismatch_reason,
        "normalized_session_ids_preview": normalized_session_ids[:10],
    }

    if reference_session_ids is not None:
        normalized_reference = _normalize_reconcile_session_ids(
            session_ids=list(reference_session_ids or []),
            normalize_mode=mode,
        )
        mismatch_index, provided_sid, reference_sid = _first_mismatch(
            provided_ids=normalized_session_ids,
            reference_ids=normalized_reference,
            strict_order=bool(strict_order),
        )
        provided_set = set(normalized_session_ids)
        reference_set = set(normalized_reference)
        result.update(
            {
                "reference_count": len(normalized_reference),
                "session_lists_match": normalized_session_ids == normalized_reference,
                "first_mismatch_index": mismatch_index,
                "first_mismatch_provided_session_id": provided_sid,
                "first_mismatch_reference_session_id": reference_sid,
                "missing_session_ids": sorted(reference_set - provided_set)[:10],
                "unexpected_session_ids": sorted(provided_set - reference_set)[:10],
            }
        )

    return result


def verify_reconcile_digest_for_event(
    event_id: int,
    session_ids: list[str],
    scope: str = "attempted",
    strict_order: bool = True,
    normalize_mode: str = "trim",
    reference_session_ids: list[str] | None = None,
) -> dict:
    """Verify a session list digest against one stored reconcile summary event."""
    eid = int(event_id or 0)
    if eid <= 0:
        return {
            "success": False,
            "error": "event_id must be a positive integer",
            "match": False,
            "event_id": eid,
        }

    parsed_scope = str(scope or "attempted").strip().lower()
    if parsed_scope not in {"attempted", "candidates"}:
        parsed_scope = "attempted"

    event = _load_reconcile_summary_event(eid)
    if not event:
        return {
            "success": False,
            "error": "Reconcile summary event not found",
            "match": False,
            "event_id": eid,
        }

    event_type = str(event.get("event_type", "") or "").strip()
    if event_type != "pending.reconcile_summary":
        return {
            "success": False,
            "error": "Event is not a reconcile summary event",
            "match": False,
            "event_id": eid,
            "event_type": event_type,
        }

    metadata = event.get("metadata") or {}
    digest_key = "attempted_sessions_sha256" if parsed_scope == "attempted" else "candidate_sessions_sha256"
    event_digest = str((metadata or {}).get(digest_key, "") or "").strip()
    if not event_digest:
        return {
            "success": False,
            "error": f"Digest not found for scope: {parsed_scope}",
            "match": False,
            "event_id": eid,
            "event_type": event_type,
            "scope": parsed_scope,
        }

    result = verify_reconcile_digest(
        session_ids=session_ids,
        digest=event_digest,
        strict_order=bool(strict_order),
        normalize_mode=str(normalize_mode or "trim"),
        reference_session_ids=reference_session_ids,
    )
    result["event_id"] = eid
    result["event_type"] = event_type
    result["scope"] = parsed_scope
    result["event_digest"] = event_digest
    result["event_created_at"] = str(event.get("created_at", "") or "")
    result["event_digest_key"] = digest_key
    return result


def verify_reconcile_digest_for_latest_event(
    session_ids: list[str],
    scope: str = "attempted",
    strict_order: bool = True,
    normalize_mode: str = "trim",
    reference_session_ids: list[str] | None = None,
) -> dict:
    """Verify a session list digest against the most recent reconcile summary event."""
    latest = _load_latest_reconcile_summary_event()
    if not latest:
        return {
            "success": False,
            "error": "No reconcile summary event found",
            "match": False,
            "event_id": 0,
        }

    return verify_reconcile_digest_for_event(
        event_id=int(latest.get("event_id", 0) or 0),
        session_ids=session_ids,
        scope=scope,
        strict_order=bool(strict_order),
        normalize_mode=str(normalize_mode or "trim"),
        reference_session_ids=reference_session_ids,
    )


def export_reconcile_verification_report(
    session_ids: list[str],
    scope: str = "attempted",
    strict_order: bool = True,
    normalize_mode: str = "trim",
    event_id: int | None = None,
    reference_session_ids: list[str] | None = None,
    signing_key: str = "",
) -> dict:
    """Generate a signed reconcile verification report for audit workflows."""
    chosen_event_id = int(event_id) if event_id is not None else 0
    if chosen_event_id > 0:
        verify_result = verify_reconcile_digest_for_event(
            event_id=chosen_event_id,
            session_ids=session_ids,
            scope=scope,
            strict_order=bool(strict_order),
            normalize_mode=str(normalize_mode or "trim"),
            reference_session_ids=reference_session_ids,
        )
    else:
        verify_result = verify_reconcile_digest_for_latest_event(
            session_ids=session_ids,
            scope=scope,
            strict_order=bool(strict_order),
            normalize_mode=str(normalize_mode or "trim"),
            reference_session_ids=reference_session_ids,
        )

    normalized_scope = str(scope or "attempted").strip().lower()
    if normalized_scope not in {"attempted", "candidates"}:
        normalized_scope = "attempted"

    key_id = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "") or "").strip()
    signature_version = int(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "1") or 1)

    report = {
        "report_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": normalized_scope,
        "strict_order": bool(strict_order),
        "normalize_mode": str(normalize_mode or "trim"),
        "event_id": int(verify_result.get("event_id", 0) or 0),
        "event_created_at": str(verify_result.get("event_created_at", "") or ""),
        "verification": verify_result,
        "signature_metadata": {
            "key_id": key_id,
            "signature_version": signature_version,
        },
    }

    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    secret, resolved_key_id, key_source = _resolve_signing_secret(
        requested_key_id=key_id,
        explicit_signing_key=str(signing_key or "").strip(),
    )
    if resolved_key_id and not key_id:
        key_id = resolved_key_id

    if secret:
        signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_type = "hmac_sha256"
        signed = True
    else:
        signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        signature_type = "sha256"
        signed = False

    return {
        "success": bool(verify_result.get("success", False)),
        "match": bool(verify_result.get("match", False)),
        "signed": signed,
        "signature_type": signature_type,
        "key_id": key_id,
        "key_source": key_source,
        "signature_version": signature_version,
        "signature": signature,
        "report": report,
    }


def export_reconcile_verification_envelope(
    session_ids: list[str],
    scope: str = "attempted",
    strict_order: bool = True,
    normalize_mode: str = "trim",
    event_id: int | None = None,
    reference_session_ids: list[str] | None = None,
    signing_key: str = "",
) -> dict:
    """Generate a report plus verification payload envelope for operators and external auditors."""
    report_result = export_reconcile_verification_report(
        session_ids=session_ids,
        scope=scope,
        strict_order=bool(strict_order),
        normalize_mode=str(normalize_mode or "trim"),
        event_id=event_id,
        reference_session_ids=reference_session_ids,
        signing_key=str(signing_key or ""),
    )

    report = dict(report_result.get("report") or {})
    signature = str(report_result.get("signature", "") or "")
    signature_type = str(report_result.get("signature_type", "") or "")
    key_id = str(report_result.get("key_id", "") or "")
    signature_version = int(report_result.get("signature_version", 1) or 1)

    verify_payload = {
        "report": report,
        "signature": signature,
        "signature_type": signature_type,
        "key_id": key_id,
        "signature_version": signature_version,
    }

    return {
        "success": bool(report_result.get("success", False)),
        "match": bool(report_result.get("match", False)),
        "envelope_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_result": report_result,
        "verify_payload": verify_payload,
    }


def verify_reconcile_verification_report_signature(
    report: dict[str, Any],
    signature: str,
    signature_type: str,
    key_id: str = "",
    signature_version: int | None = None,
    signing_key: str = "",
) -> dict:
    """Verify signature integrity for a reconcile verification report payload."""
    parsed_type = str(signature_type or "").strip().lower()
    if parsed_type not in {"sha256", "hmac_sha256"}:
        return {
            "success": False,
            "error": "Unsupported signature_type",
            "match": False,
            "signature_type": parsed_type,
        }

    provided = str(signature or "").strip().lower()
    if not provided:
        return {
            "success": False,
            "error": "signature is required",
            "match": False,
            "signature_type": parsed_type,
        }

    canonical = json.dumps(report or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    report_signature_meta = dict((report or {}).get("signature_metadata") or {})
    report_key_id = str(report_signature_meta.get("key_id", "") or "")
    report_signature_version = int(report_signature_meta.get("signature_version", 1) or 1)
    requested_key_id = str(key_id or "").strip()
    requested_signature_version = (
        int(signature_version)
        if signature_version is not None
        else None
    )

    if requested_key_id and requested_key_id != report_key_id:
        return {
            "success": False,
            "error": "key_id does not match report signature metadata",
            "match": False,
            "signature_type": parsed_type,
            "report_key_id": report_key_id,
            "requested_key_id": requested_key_id,
        }

    if requested_signature_version is not None and requested_signature_version != report_signature_version:
        return {
            "success": False,
            "error": "signature_version does not match report signature metadata",
            "match": False,
            "signature_type": parsed_type,
            "report_signature_version": report_signature_version,
            "requested_signature_version": requested_signature_version,
        }

    resolved_requested_key = requested_key_id or report_key_id
    secret, resolved_key_id, key_source = _resolve_signing_secret(
        requested_key_id=resolved_requested_key,
        explicit_signing_key=str(signing_key or "").strip(),
    )

    if parsed_type == "hmac_sha256":
        if not secret:
            return {
                "success": False,
                "error": "HMAC signing key not configured",
                "match": False,
                "signature_type": parsed_type,
            }
        expected = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    else:
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return {
        "success": True,
        "match": hmac.compare_digest(expected, provided),
        "signature_type": parsed_type,
        "key_id": report_key_id,
        "resolved_key_id": resolved_key_id,
        "key_source": key_source,
        "signature_version": report_signature_version,
        "provided_signature": provided,
        "expected_signature": expected,
        "report_event_id": int((report or {}).get("event_id", 0) or 0),
    }


def create_reconcile_verification_signature_receipt(
    report: dict[str, Any],
    signature: str,
    signature_type: str,
    key_id: str = "",
    signature_version: int | None = None,
    signing_key: str = "",
    actor_email: str = "",
    source: str = "ops_api",
) -> dict:
    """Verify signature and persist a receipt event for audit trails."""
    verify = verify_reconcile_verification_report_signature(
        report=report,
        signature=signature,
        signature_type=signature_type,
        key_id=key_id,
        signature_version=signature_version,
        signing_key=signing_key,
    )

    receipt_event_id = log_event(
        "pending.reconcile.signature_receipt",
        "Reconcile report signature verification receipt",
        tournament_id=(int((report or {}).get("tournament_id", 0)) if (report or {}).get("tournament_id") else None),
        user_email=(str(actor_email or "").strip().lower() or None),
        severity=("info" if bool(verify.get("success", False)) and bool(verify.get("match", False)) else "warning"),
        metadata={
            "source": str(source or "ops_api"),
            "report_event_id": int((report or {}).get("event_id", 0) or 0),
            "signature_type": str(signature_type or ""),
            "key_id": str(key_id or "").strip(),
            "signature_version": (int(signature_version) if signature_version is not None else None),
            "verify": verify,
        },
    )

    return {
        "success": bool(verify.get("success", False)),
        "match": bool(verify.get("match", False)),
        "receipt_event_id": int(receipt_event_id),
        "verify": verify,
    }


def list_reconcile_signature_receipts(limit: int = 100, outcome: str = "all") -> list[dict]:
    """List reconcile signature verification receipt events."""
    parsed_outcome = str(outcome or "all").strip().lower()
    if parsed_outcome not in {"all", "matched", "mismatched", "error"}:
        parsed_outcome = "all"

    rows = list_events(event_type="pending.reconcile.signature_receipt", limit=max(1, min(500, int(limit))))
    if parsed_outcome == "all":
        return rows

    filtered: list[dict] = []
    for row in rows:
        verify = dict((row.get("metadata") or {}).get("verify") or {})
        success = bool(verify.get("success", False))
        match = bool(verify.get("match", False))

        if parsed_outcome == "matched" and success and match:
            filtered.append(row)
        elif parsed_outcome == "mismatched" and success and not match:
            filtered.append(row)
        elif parsed_outcome == "error" and not success:
            filtered.append(row)
    return filtered


def get_latest_reconcile_signature_receipts_artifact_head() -> dict:
    """Return metadata for the most recent signature receipt artifact export event."""
    rows = list_events(event_type="pending.reconcile.signature_receipts_artifact", limit=1)
    if not rows:
        return {
            "success": False,
            "error": "No signature receipt artifact export found",
        }

    latest = rows[0]
    metadata = dict(latest.get("metadata") or {})
    return {
        "success": True,
        "event_id": int(latest.get("event_id", 0) or 0),
        "created_at": str(latest.get("created_at", "") or ""),
        "digest_sha256": str(metadata.get("digest_sha256", "") or ""),
        "chain_digest": str(metadata.get("chain_digest", "") or ""),
        "previous_digest": str(metadata.get("previous_digest", "") or ""),
        "count": int(metadata.get("count", 0) or 0),
        "outcome": str(metadata.get("outcome", "all") or "all"),
    }


def prune_reconcile_signature_receipts(
    max_age_days: int = 30,
    dry_run: bool = True,
    now: datetime | None = None,
) -> dict:
    """Delete old signature receipt events with optional dry-run preview."""
    age_days = max(1, int(max_age_days))
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is not None:
        current = current.astimezone(timezone.utc).replace(tzinfo=None)
    cutoff = current - timedelta(days=age_days)
    cutoff_sql = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    with tournament_db.get_tournament_connection() as conn:
        scanned = int(
            conn.execute(
                "SELECT COUNT(1) AS c FROM tournament_events WHERE event_type = ?",
                ("pending.reconcile.signature_receipt",),
            ).fetchone()["c"]
            or 0
        )
        candidate_rows = conn.execute(
            """
            SELECT event_id
            FROM tournament_events
            WHERE event_type = ?
              AND created_at < ?
            ORDER BY event_id ASC
            """,
            ("pending.reconcile.signature_receipt", cutoff_sql),
        ).fetchall()

        candidate_ids = [int(r["event_id"]) for r in candidate_rows]
        deleted = 0
        if not dry_run and candidate_ids:
            conn.executemany(
                "DELETE FROM tournament_events WHERE event_id = ?",
                [(eid,) for eid in candidate_ids],
            )
            conn.commit()
            deleted = len(candidate_ids)

    summary = {
        "success": True,
        "dry_run": bool(dry_run),
        "max_age_days": age_days,
        "cutoff": cutoff_sql,
        "scanned": scanned,
        "candidates": len(candidate_ids),
        "deleted": deleted,
    }

    log_event(
        "pending.reconcile.signature_receipts_pruned",
        (
            "Signature receipt prune summary: "
            f"dry_run={bool(dry_run)} scanned={scanned} "
            f"candidates={len(candidate_ids)} deleted={deleted}"
        ),
        severity="info",
        metadata=summary,
    )
    return summary


def export_reconcile_signature_receipts_artifact(
    limit: int = 100,
    outcome: str = "all",
    include_csv: bool = True,
    previous_digest: str = "",
    auto_chain: bool = True,
    persist_event: bool = True,
) -> dict:
    """Export signature receipt rows plus deterministic digest for compliance pipelines."""
    rows = list_reconcile_signature_receipts(limit=limit, outcome=outcome)
    normalized_rows = [
        {
            "event_id": int(r.get("event_id", 0) or 0),
            "created_at": str(r.get("created_at", "") or ""),
            "severity": str(r.get("severity", "") or ""),
            "user_email": str(r.get("user_email", "") or ""),
            "report_event_id": int((r.get("metadata") or {}).get("report_event_id", 0) or 0),
            "signature_type": str((r.get("metadata") or {}).get("signature_type", "") or ""),
            "key_id": str((r.get("metadata") or {}).get("key_id", "") or ""),
            "verify_success": bool(((r.get("metadata") or {}).get("verify") or {}).get("success", False)),
            "verify_match": bool(((r.get("metadata") or {}).get("verify") or {}).get("match", False)),
        }
        for r in rows
    ]

    canonical = json.dumps(normalized_rows, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    artifact_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    csv_text = ""
    if include_csv:
        header = [
            "event_id",
            "created_at",
            "severity",
            "user_email",
            "report_event_id",
            "signature_type",
            "key_id",
            "verify_success",
            "verify_match",
        ]
        lines = [",".join(header)]
        for item in normalized_rows:
            lines.append(
                ",".join(
                    [
                        str(item.get("event_id", 0)),
                        str(item.get("created_at", "")),
                        str(item.get("severity", "")),
                        str(item.get("user_email", "")),
                        str(item.get("report_event_id", 0)),
                        str(item.get("signature_type", "")),
                        str(item.get("key_id", "")),
                        str(bool(item.get("verify_success", False))).lower(),
                        str(bool(item.get("verify_match", False))).lower(),
                    ]
                )
            )
        csv_text = "\n".join(lines)

    resolved_previous = str(previous_digest or "").strip().lower()
    chain_source = "provided" if resolved_previous else "none"
    if not resolved_previous and bool(auto_chain):
        latest_head = get_latest_reconcile_signature_receipts_artifact_head()
        if latest_head.get("success"):
            resolved_previous = str(latest_head.get("digest_sha256", "") or "").strip().lower()
            chain_source = "latest_event"

    chain_input = f"{resolved_previous}:{artifact_digest}" if resolved_previous else artifact_digest
    chain_digest = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()

    result = {
        "success": True,
        "artifact_version": 2,
        "count": len(normalized_rows),
        "outcome": str(outcome or "all"),
        "digest_sha256": artifact_digest,
        "previous_digest": resolved_previous,
        "chain_source": chain_source,
        "chain_digest": chain_digest,
        "rows": normalized_rows,
        "csv": csv_text,
    }

    if bool(persist_event):
        event_id = log_event(
            "pending.reconcile.signature_receipts_artifact",
            "Signature receipts artifact exported",
            severity="info",
            metadata={
                "count": int(result.get("count", 0)),
                "outcome": str(result.get("outcome", "all")),
                "digest_sha256": str(result.get("digest_sha256", "")),
                "previous_digest": str(result.get("previous_digest", "")),
                "chain_digest": str(result.get("chain_digest", "")),
                "chain_source": str(result.get("chain_source", "none")),
                "include_csv": bool(include_csv),
                "artifact_version": int(result.get("artifact_version", 2)),
            },
        )
        result["artifact_event_id"] = int(event_id)

    return result


def create_reconcile_signature_chain_checkpoint(
    label: str = "",
    note: str = "",
    expected_previous_digest: str = "",
    require_head: bool = True,
    signing_key: str = "",
) -> dict:
    """Create a signed checkpoint anchored to the latest receipts artifact head."""
    head = get_latest_reconcile_signature_receipts_artifact_head()
    if not head.get("success", False):
        if bool(require_head):
            return {
                "success": False,
                "error": str(head.get("error", "No artifact head available")),
                "head": head,
            }
        head = {
            "success": True,
            "event_id": 0,
            "created_at": "",
            "digest_sha256": "",
            "chain_digest": "",
            "previous_digest": "",
            "count": 0,
            "outcome": "all",
        }

    expected = str(expected_previous_digest or "").strip().lower()
    current_digest = str(head.get("digest_sha256", "") or "").strip().lower()
    if expected and expected != current_digest:
        return {
            "success": False,
            "error": "expected_previous_digest does not match current artifact head",
            "expected_previous_digest": expected,
            "head_digest_sha256": current_digest,
        }

    key_id = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "") or "").strip()
    signature_version = int(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "1") or 1)
    payload = {
        "checkpoint_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": str(label or "").strip(),
        "note": str(note or "").strip(),
        "head": {
            "event_id": int(head.get("event_id", 0) or 0),
            "created_at": str(head.get("created_at", "") or ""),
            "digest_sha256": current_digest,
            "chain_digest": str(head.get("chain_digest", "") or "").strip().lower(),
            "previous_digest": str(head.get("previous_digest", "") or "").strip().lower(),
            "count": int(head.get("count", 0) or 0),
            "outcome": str(head.get("outcome", "all") or "all"),
        },
        "signature_metadata": {
            "key_id": key_id,
            "signature_version": signature_version,
        },
    }

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    secret, resolved_key_id, key_source = _resolve_signing_secret(
        requested_key_id=key_id,
        explicit_signing_key=str(signing_key or "").strip(),
    )
    if resolved_key_id and not key_id:
        key_id = resolved_key_id
        payload["signature_metadata"]["key_id"] = key_id

    if secret:
        signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_type = "hmac_sha256"
        signed = True
    else:
        signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        signature_type = "sha256"
        signed = False

    checkpoint_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    event_id = log_event(
        "pending.reconcile.signature_chain_checkpoint",
        "Signature receipts artifact chain checkpoint created",
        severity="info",
        metadata={
            "checkpoint_digest": checkpoint_digest,
            "signature": signature,
            "signature_type": signature_type,
            "signed": bool(signed),
            "key_id": key_id,
            "key_source": key_source,
            "signature_version": signature_version,
            "head_event_id": int(head.get("event_id", 0) or 0),
            "head_digest_sha256": current_digest,
            "label": str(label or "").strip(),
            "payload": payload,
        },
    )

    return {
        "success": True,
        "event_id": int(event_id),
        "checkpoint_digest": checkpoint_digest,
        "signature": signature,
        "signature_type": signature_type,
        "signed": bool(signed),
        "key_id": key_id,
        "key_source": key_source,
        "signature_version": signature_version,
        "payload": payload,
    }


def get_latest_reconcile_signature_chain_checkpoint() -> dict:
    """Return metadata for the most recent signature chain checkpoint event."""
    rows = list_events(event_type="pending.reconcile.signature_chain_checkpoint", limit=1)
    if not rows:
        return {
            "success": False,
            "error": "No signature chain checkpoint found",
        }

    latest = rows[0]
    metadata = dict(latest.get("metadata") or {})
    return {
        "success": True,
        "event_id": int(latest.get("event_id", 0) or 0),
        "created_at": str(latest.get("created_at", "") or ""),
        "checkpoint_digest": str(metadata.get("checkpoint_digest", "") or ""),
        "signature": str(metadata.get("signature", "") or ""),
        "signature_type": str(metadata.get("signature_type", "") or ""),
        "signed": bool(metadata.get("signed", False)),
        "key_id": str(metadata.get("key_id", "") or ""),
        "key_source": str(metadata.get("key_source", "") or ""),
        "signature_version": int(metadata.get("signature_version", 0) or 0),
        "head_event_id": int(metadata.get("head_event_id", 0) or 0),
        "head_digest_sha256": str(metadata.get("head_digest_sha256", "") or ""),
        "label": str(metadata.get("label", "") or ""),
        "payload": dict(metadata.get("payload") or {}),
    }


def get_latest_reconcile_compliance_status_artifact_head() -> dict:
    """Return metadata for the most recent compliance status artifact export event."""
    rows = list_events(event_type="pending.reconcile.compliance_status_artifact", limit=1)
    if not rows:
        return {
            "success": False,
            "error": "No compliance status artifact export found",
        }

    latest = rows[0]
    metadata = dict(latest.get("metadata") or {})
    return {
        "success": True,
        "event_id": int(latest.get("event_id", 0) or 0),
        "created_at": str(latest.get("created_at", "") or ""),
        "digest_sha256": str(metadata.get("digest_sha256", "") or ""),
        "chain_digest": str(metadata.get("chain_digest", "") or ""),
        "previous_digest": str(metadata.get("previous_digest", "") or ""),
        "chain_source": str(metadata.get("chain_source", "none") or "none"),
        "status": str(metadata.get("status", "") or ""),
        "artifact_version": int(metadata.get("artifact_version", 1) or 1),
    }


def verify_reconcile_signature_receipts_artifact_chain(limit: int = 200) -> dict:
    """Verify linkage and chain digests across signature receipt artifact export events."""
    rows = list_events(
        event_type="pending.reconcile.signature_receipts_artifact",
        limit=max(1, min(1000, int(limit))),
    )
    ordered = list(reversed(rows))
    if not ordered:
        return {
            "success": True,
            "count": 0,
            "valid_links": 0,
            "broken_links": 0,
            "status": "empty",
            "issues": [],
        }

    issues: list[dict[str, Any]] = []
    valid_links = 0
    previous_digest = ""

    for idx, event in enumerate(ordered):
        metadata = dict(event.get("metadata") or {})
        event_id = int(event.get("event_id", 0) or 0)
        digest = str(metadata.get("digest_sha256", "") or "").strip().lower()
        declared_previous = str(metadata.get("previous_digest", "") or "").strip().lower()
        declared_chain = str(metadata.get("chain_digest", "") or "").strip().lower()

        expected_previous = previous_digest
        expected_chain_input = f"{declared_previous}:{digest}" if declared_previous else digest
        expected_chain = hashlib.sha256(expected_chain_input.encode("utf-8")).hexdigest() if digest else ""

        event_issues = []
        if not digest:
            event_issues.append("missing_digest")
        if declared_previous != expected_previous:
            event_issues.append("previous_digest_mismatch")
        if declared_chain != expected_chain:
            event_issues.append("chain_digest_mismatch")

        if event_issues:
            issues.append(
                {
                    "event_id": event_id,
                    "issues": event_issues,
                    "declared_previous": declared_previous,
                    "expected_previous": expected_previous,
                    "declared_chain": declared_chain,
                    "expected_chain": expected_chain,
                    "digest_sha256": digest,
                }
            )
        else:
            valid_links += 1

        previous_digest = digest

    status = "ok" if not issues else "broken"
    result = {
        "success": True,
        "count": len(ordered),
        "valid_links": int(valid_links),
        "broken_links": int(len(issues)),
        "status": status,
        "head_event_id": int(ordered[-1].get("event_id", 0) or 0),
        "head_digest_sha256": str((ordered[-1].get("metadata") or {}).get("digest_sha256", "") or ""),
        "issues": issues[:50],
    }
    return result


def verify_reconcile_signature_chain_checkpoint(
    require_current_head: bool = False,
    require_signature_payload: bool = False,
) -> dict:
    """Verify the latest checkpoint event against the stored artifact head it references."""
    checkpoint = get_latest_reconcile_signature_chain_checkpoint()
    if not checkpoint.get("success", False):
        return {
            "success": True,
            "status": "empty",
            "issues": [],
            "checkpoint": checkpoint,
        }

    issues: list[str] = []
    warnings: list[str] = []
    head_event_id = int(checkpoint.get("head_event_id", 0) or 0)
    head_digest_sha256 = str(checkpoint.get("head_digest_sha256", "") or "").strip().lower()
    payload = dict(checkpoint.get("payload") or {})
    signature = str(checkpoint.get("signature", "") or "").strip().lower()
    signature_type = str(checkpoint.get("signature_type", "") or "").strip().lower()
    key_id = str(checkpoint.get("key_id", "") or "").strip()

    if not str(checkpoint.get("checkpoint_digest", "") or "").strip():
        issues.append("missing_checkpoint_digest")
    if not signature:
        issues.append("missing_signature")
    if not signature_type:
        issues.append("missing_signature_type")
    if head_event_id <= 0:
        issues.append("missing_head_event_id")
    if not head_digest_sha256:
        issues.append("missing_head_digest_sha256")

    referenced_head = None
    if head_event_id > 0:
        with tournament_db.get_tournament_connection() as conn:
            row = conn.execute(
                "SELECT event_id, event_type, created_at, metadata_json FROM tournament_events WHERE event_id = ?",
                (head_event_id,),
            ).fetchone()

        if row is None:
            issues.append("referenced_head_not_found")
        else:
            metadata = _loads_json(str(row["metadata_json"] or "{}"), {})
            referenced_head = {
                "event_id": int(row["event_id"] or 0),
                "event_type": str(row["event_type"] or ""),
                "created_at": str(row["created_at"] or ""),
                "digest_sha256": str(metadata.get("digest_sha256", "") or "").strip().lower(),
                "chain_digest": str(metadata.get("chain_digest", "") or "").strip().lower(),
                "previous_digest": str(metadata.get("previous_digest", "") or "").strip().lower(),
                "count": int(metadata.get("count", 0) or 0),
                "outcome": str(metadata.get("outcome", "all") or "all"),
            }
            if referenced_head["event_type"] != "pending.reconcile.signature_receipts_artifact":
                issues.append("referenced_head_wrong_event_type")
            if head_digest_sha256 and referenced_head["digest_sha256"] != head_digest_sha256:
                issues.append("referenced_head_digest_mismatch")

    signature_verification = {
        "available": False,
        "verified": False,
        "match": False,
        "reason": "payload_unavailable",
        "computed_checkpoint_digest": "",
        "computed_signature": "",
    }
    if payload:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        computed_checkpoint_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        signature_verification["available"] = True
        signature_verification["verified"] = True
        signature_verification["computed_checkpoint_digest"] = computed_checkpoint_digest

        checkpoint_digest = str(checkpoint.get("checkpoint_digest", "") or "").strip().lower()
        if checkpoint_digest and checkpoint_digest != computed_checkpoint_digest:
            issues.append("checkpoint_digest_mismatch")

        payload_head = dict(payload.get("head") or {})
        payload_head_event_id = int(payload_head.get("event_id", 0) or 0)
        payload_head_digest = str(payload_head.get("digest_sha256", "") or "").strip().lower()
        if payload_head_event_id and payload_head_event_id != head_event_id:
            issues.append("payload_head_event_mismatch")
        if payload_head_digest and payload_head_digest != head_digest_sha256:
            issues.append("payload_head_digest_mismatch")

        if signature_type == "hmac_sha256":
            secret, _, _ = _resolve_signing_secret(requested_key_id=key_id)
            if not secret:
                warnings.append("signing_secret_unavailable_for_checkpoint")
                signature_verification["verified"] = False
                signature_verification["reason"] = "signing_secret_unavailable"
            else:
                computed_signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
                signature_verification["computed_signature"] = computed_signature
                signature_verification["match"] = bool(signature and signature == computed_signature)
                signature_verification["reason"] = "verified"
                if signature and signature != computed_signature:
                    issues.append("checkpoint_signature_mismatch")
        elif signature_type == "sha256":
            computed_signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            signature_verification["computed_signature"] = computed_signature
            signature_verification["match"] = bool(signature and signature == computed_signature)
            signature_verification["reason"] = "verified"
            if signature and signature != computed_signature:
                issues.append("checkpoint_signature_mismatch")
        else:
            issues.append("unsupported_signature_type")
            signature_verification["reason"] = "unsupported_signature_type"
    else:
        warnings.append("checkpoint_payload_unavailable")
        if bool(require_signature_payload):
            issues.append("checkpoint_payload_unavailable")

    current_head = get_latest_reconcile_signature_receipts_artifact_head()
    current_head_match = False
    if current_head.get("success", False):
        current_head_match = bool(
            int(current_head.get("event_id", 0) or 0) == head_event_id
            and str(current_head.get("digest_sha256", "") or "").strip().lower() == head_digest_sha256
        )
        if not current_head_match:
            warnings.append("checkpoint_not_current_head")
            if bool(require_current_head):
                issues.append("checkpoint_not_current_head")
    elif head_event_id > 0:
        warnings.append("current_head_unavailable")

    if issues:
        status = "broken"
    elif warnings:
        status = "stale"
    else:
        status = "ok"

    return {
        "success": True,
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "current_head_match": bool(current_head_match),
        "signature_verification": signature_verification,
        "checkpoint": checkpoint,
        "referenced_head": referenced_head,
        "current_head": current_head,
    }


def verify_reconcile_signature_chain_checkpoint_history(
    limit: int = 200,
    require_signature_payload: bool = False,
) -> dict:
    """Verify integrity of recent checkpoint events, including signature checks when payload is available."""
    rows = list_events(
        event_type="pending.reconcile.signature_chain_checkpoint",
        limit=max(1, min(1000, int(limit))),
    )
    ordered = list(reversed(rows))
    if not ordered:
        return {
            "success": True,
            "count": 0,
            "ok": 0,
            "broken": 0,
            "stale": 0,
            "status": "empty",
            "issues": [],
            "rows": [],
        }

    entries: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []
    ok_count = 0
    broken_count = 0
    stale_count = 0

    for event in ordered:
        metadata = dict(event.get("metadata") or {})
        event_id = int(event.get("event_id", 0) or 0)
        created_at = str(event.get("created_at", "") or "")
        head_event_id = int(metadata.get("head_event_id", 0) or 0)
        head_digest_sha256 = str(metadata.get("head_digest_sha256", "") or "").strip().lower()
        payload = dict(metadata.get("payload") or {})
        signature = str(metadata.get("signature", "") or "").strip().lower()
        signature_type = str(metadata.get("signature_type", "") or "").strip().lower()
        key_id = str(metadata.get("key_id", "") or "").strip()

        issues: list[str] = []
        warnings: list[str] = []
        referenced_head = None

        if not str(metadata.get("checkpoint_digest", "") or "").strip():
            issues.append("missing_checkpoint_digest")
        if not signature:
            issues.append("missing_signature")
        if not signature_type:
            issues.append("missing_signature_type")
        if head_event_id <= 0:
            issues.append("missing_head_event_id")
        if not head_digest_sha256:
            issues.append("missing_head_digest_sha256")

        if head_event_id > 0:
            with tournament_db.get_tournament_connection() as conn:
                row = conn.execute(
                    "SELECT event_id, event_type, created_at, metadata_json FROM tournament_events WHERE event_id = ?",
                    (head_event_id,),
                ).fetchone()

            if row is None:
                issues.append("referenced_head_not_found")
            else:
                row_metadata = _loads_json(str(row["metadata_json"] or "{}"), {})
                referenced_head = {
                    "event_id": int(row["event_id"] or 0),
                    "event_type": str(row["event_type"] or ""),
                    "created_at": str(row["created_at"] or ""),
                    "digest_sha256": str(row_metadata.get("digest_sha256", "") or "").strip().lower(),
                    "chain_digest": str(row_metadata.get("chain_digest", "") or "").strip().lower(),
                    "previous_digest": str(row_metadata.get("previous_digest", "") or "").strip().lower(),
                    "count": int(row_metadata.get("count", 0) or 0),
                    "outcome": str(row_metadata.get("outcome", "all") or "all"),
                }
                if referenced_head["event_type"] != "pending.reconcile.signature_receipts_artifact":
                    issues.append("referenced_head_wrong_event_type")
                if head_digest_sha256 and referenced_head["digest_sha256"] != head_digest_sha256:
                    issues.append("referenced_head_digest_mismatch")

        signature_verification = {
            "available": False,
            "verified": False,
            "match": False,
            "reason": "payload_unavailable",
            "computed_checkpoint_digest": "",
            "computed_signature": "",
        }
        if payload:
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            computed_checkpoint_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            signature_verification["available"] = True
            signature_verification["verified"] = True
            signature_verification["computed_checkpoint_digest"] = computed_checkpoint_digest

            checkpoint_digest = str(metadata.get("checkpoint_digest", "") or "").strip().lower()
            if checkpoint_digest and checkpoint_digest != computed_checkpoint_digest:
                issues.append("checkpoint_digest_mismatch")

            payload_head = dict(payload.get("head") or {})
            payload_head_event_id = int(payload_head.get("event_id", 0) or 0)
            payload_head_digest = str(payload_head.get("digest_sha256", "") or "").strip().lower()
            if payload_head_event_id and payload_head_event_id != head_event_id:
                issues.append("payload_head_event_mismatch")
            if payload_head_digest and payload_head_digest != head_digest_sha256:
                issues.append("payload_head_digest_mismatch")

            if signature_type == "hmac_sha256":
                secret, _, _ = _resolve_signing_secret(requested_key_id=key_id)
                if not secret:
                    warnings.append("signing_secret_unavailable_for_checkpoint")
                    signature_verification["verified"] = False
                    signature_verification["reason"] = "signing_secret_unavailable"
                else:
                    computed_signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
                    signature_verification["computed_signature"] = computed_signature
                    signature_verification["match"] = bool(signature and signature == computed_signature)
                    signature_verification["reason"] = "verified"
                    if signature and signature != computed_signature:
                        issues.append("checkpoint_signature_mismatch")
            elif signature_type == "sha256":
                computed_signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                signature_verification["computed_signature"] = computed_signature
                signature_verification["match"] = bool(signature and signature == computed_signature)
                signature_verification["reason"] = "verified"
                if signature and signature != computed_signature:
                    issues.append("checkpoint_signature_mismatch")
            else:
                issues.append("unsupported_signature_type")
                signature_verification["reason"] = "unsupported_signature_type"
        else:
            warnings.append("checkpoint_payload_unavailable")
            if bool(require_signature_payload):
                issues.append("checkpoint_payload_unavailable")

        if issues:
            row_status = "broken"
            broken_count += 1
            issue_rows.append({"event_id": event_id, "issues": issues})
        elif warnings:
            row_status = "stale"
            stale_count += 1
        else:
            row_status = "ok"
            ok_count += 1

        entries.append(
            {
                "event_id": event_id,
                "created_at": created_at,
                "label": str(metadata.get("label", "") or ""),
                "status": row_status,
                "issues": issues,
                "warnings": warnings,
                "head_event_id": head_event_id,
                "head_digest_sha256": head_digest_sha256,
                "signature_verification": signature_verification,
                "referenced_head": referenced_head,
            }
        )

    overall_status = "ok" if broken_count == 0 else "broken"
    return {
        "success": True,
        "count": len(entries),
        "ok": int(ok_count),
        "broken": int(broken_count),
        "stale": int(stale_count),
        "status": overall_status,
        "issues": issue_rows[:50],
        "rows": entries,
    }


def verify_reconcile_compliance_status_artifact_chain(limit: int = 200) -> dict:
    """Verify linkage and chain digests across compliance status artifact export events."""
    rows = list_events(
        event_type="pending.reconcile.compliance_status_artifact",
        limit=max(1, min(1000, int(limit))),
    )
    ordered = list(reversed(rows))
    if not ordered:
        return {
            "success": True,
            "count": 0,
            "valid_links": 0,
            "broken_links": 0,
            "status": "empty",
            "issues": [],
        }

    issues: list[dict[str, Any]] = []
    valid_links = 0
    previous_digest = ""

    for event in ordered:
        metadata = dict(event.get("metadata") or {})
        event_id = int(event.get("event_id", 0) or 0)
        digest = str(metadata.get("digest_sha256", "") or "").strip().lower()
        declared_previous = str(metadata.get("previous_digest", "") or "").strip().lower()
        declared_chain = str(metadata.get("chain_digest", "") or "").strip().lower()

        expected_previous = previous_digest
        expected_chain_input = f"{declared_previous}:{digest}" if declared_previous else digest
        expected_chain = hashlib.sha256(expected_chain_input.encode("utf-8")).hexdigest() if digest else ""

        event_issues = []
        if not digest:
            event_issues.append("missing_digest")
        if declared_previous != expected_previous:
            event_issues.append("previous_digest_mismatch")
        if declared_chain != expected_chain:
            event_issues.append("chain_digest_mismatch")

        if event_issues:
            issues.append(
                {
                    "event_id": event_id,
                    "issues": event_issues,
                    "declared_previous": declared_previous,
                    "expected_previous": expected_previous,
                    "declared_chain": declared_chain,
                    "expected_chain": expected_chain,
                    "digest_sha256": digest,
                }
            )
        else:
            valid_links += 1

        previous_digest = digest

    status = "ok" if not issues else "broken"
    return {
        "success": True,
        "count": len(ordered),
        "valid_links": int(valid_links),
        "broken_links": int(len(issues)),
        "status": status,
        "head_event_id": int(ordered[-1].get("event_id", 0) or 0),
        "head_digest_sha256": str((ordered[-1].get("metadata") or {}).get("digest_sha256", "") or ""),
        "issues": issues[:50],
    }


def create_reconcile_compliance_chain_checkpoint(
    label: str = "",
    note: str = "",
    expected_previous_digest: str = "",
    require_head: bool = True,
    signing_key: str = "",
) -> dict:
    """Create a signed checkpoint anchored to the latest compliance artifact head."""
    head = get_latest_reconcile_compliance_status_artifact_head()
    if not head.get("success", False):
        if bool(require_head):
            return {
                "success": False,
                "error": str(head.get("error", "No compliance artifact head available")),
                "head": head,
            }
        head = {
            "success": True,
            "event_id": 0,
            "created_at": "",
            "digest_sha256": "",
            "chain_digest": "",
            "previous_digest": "",
            "chain_source": "none",
            "status": "",
            "artifact_version": 1,
        }

    expected = str(expected_previous_digest or "").strip().lower()
    current_digest = str(head.get("digest_sha256", "") or "").strip().lower()
    if expected and expected != current_digest:
        return {
            "success": False,
            "error": "expected_previous_digest does not match current compliance artifact head",
            "expected_previous_digest": expected,
            "head_digest_sha256": current_digest,
        }

    key_id = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "") or "").strip()
    signature_version = int(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "1") or 1)
    payload = {
        "checkpoint_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": str(label or "").strip(),
        "note": str(note or "").strip(),
        "head": {
            "event_id": int(head.get("event_id", 0) or 0),
            "created_at": str(head.get("created_at", "") or ""),
            "digest_sha256": current_digest,
            "chain_digest": str(head.get("chain_digest", "") or "").strip().lower(),
            "previous_digest": str(head.get("previous_digest", "") or "").strip().lower(),
            "chain_source": str(head.get("chain_source", "none") or "none"),
            "status": str(head.get("status", "") or ""),
            "artifact_version": int(head.get("artifact_version", 1) or 1),
        },
        "signature_metadata": {
            "key_id": key_id,
            "signature_version": signature_version,
        },
    }

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    secret, resolved_key_id, key_source = _resolve_signing_secret(
        requested_key_id=key_id,
        explicit_signing_key=str(signing_key or "").strip(),
    )
    if resolved_key_id and not key_id:
        key_id = resolved_key_id
        payload["signature_metadata"]["key_id"] = key_id

    if secret:
        signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_type = "hmac_sha256"
        signed = True
    else:
        signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        signature_type = "sha256"
        signed = False

    checkpoint_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    event_id = log_event(
        "pending.reconcile.compliance_chain_checkpoint",
        "Compliance artifact chain checkpoint created",
        severity="info",
        metadata={
            "checkpoint_digest": checkpoint_digest,
            "signature": signature,
            "signature_type": signature_type,
            "signed": bool(signed),
            "key_id": key_id,
            "key_source": key_source,
            "signature_version": signature_version,
            "head_event_id": int(head.get("event_id", 0) or 0),
            "head_digest_sha256": current_digest,
            "label": str(label or "").strip(),
            "payload": payload,
        },
    )

    return {
        "success": True,
        "event_id": int(event_id),
        "checkpoint_digest": checkpoint_digest,
        "signature": signature,
        "signature_type": signature_type,
        "signed": bool(signed),
        "key_id": key_id,
        "key_source": key_source,
        "signature_version": signature_version,
        "payload": payload,
    }


def get_latest_reconcile_compliance_chain_checkpoint() -> dict:
    """Return metadata for the most recent compliance chain checkpoint event."""
    rows = list_events(event_type="pending.reconcile.compliance_chain_checkpoint", limit=1)
    if not rows:
        return {
            "success": False,
            "error": "No compliance chain checkpoint found",
        }

    latest = rows[0]
    metadata = dict(latest.get("metadata") or {})
    return {
        "success": True,
        "event_id": int(latest.get("event_id", 0) or 0),
        "created_at": str(latest.get("created_at", "") or ""),
        "checkpoint_digest": str(metadata.get("checkpoint_digest", "") or ""),
        "signature": str(metadata.get("signature", "") or ""),
        "signature_type": str(metadata.get("signature_type", "") or ""),
        "signed": bool(metadata.get("signed", False)),
        "key_id": str(metadata.get("key_id", "") or ""),
        "key_source": str(metadata.get("key_source", "") or ""),
        "signature_version": int(metadata.get("signature_version", 0) or 0),
        "head_event_id": int(metadata.get("head_event_id", 0) or 0),
        "head_digest_sha256": str(metadata.get("head_digest_sha256", "") or ""),
        "label": str(metadata.get("label", "") or ""),
        "payload": dict(metadata.get("payload") or {}),
    }


def verify_reconcile_compliance_chain_checkpoint(
    require_current_head: bool = False,
    require_signature_payload: bool = False,
) -> dict:
    """Verify latest compliance checkpoint event against referenced compliance artifact head."""
    checkpoint = get_latest_reconcile_compliance_chain_checkpoint()
    if not checkpoint.get("success", False):
        return {
            "success": True,
            "status": "empty",
            "issues": [],
            "checkpoint": checkpoint,
        }

    issues: list[str] = []
    warnings: list[str] = []
    head_event_id = int(checkpoint.get("head_event_id", 0) or 0)
    head_digest_sha256 = str(checkpoint.get("head_digest_sha256", "") or "").strip().lower()
    payload = dict(checkpoint.get("payload") or {})
    signature = str(checkpoint.get("signature", "") or "").strip().lower()
    signature_type = str(checkpoint.get("signature_type", "") or "").strip().lower()
    key_id = str(checkpoint.get("key_id", "") or "").strip()

    if not str(checkpoint.get("checkpoint_digest", "") or "").strip():
        issues.append("missing_checkpoint_digest")
    if not signature:
        issues.append("missing_signature")
    if not signature_type:
        issues.append("missing_signature_type")
    if head_event_id <= 0:
        issues.append("missing_head_event_id")
    if not head_digest_sha256:
        issues.append("missing_head_digest_sha256")

    referenced_head = None
    if head_event_id > 0:
        with tournament_db.get_tournament_connection() as conn:
            row = conn.execute(
                "SELECT event_id, event_type, created_at, metadata_json FROM tournament_events WHERE event_id = ?",
                (head_event_id,),
            ).fetchone()

        if row is None:
            issues.append("referenced_head_not_found")
        else:
            metadata = _loads_json(str(row["metadata_json"] or "{}"), {})
            referenced_head = {
                "event_id": int(row["event_id"] or 0),
                "event_type": str(row["event_type"] or ""),
                "created_at": str(row["created_at"] or ""),
                "digest_sha256": str(metadata.get("digest_sha256", "") or "").strip().lower(),
                "chain_digest": str(metadata.get("chain_digest", "") or "").strip().lower(),
                "previous_digest": str(metadata.get("previous_digest", "") or "").strip().lower(),
                "status": str(metadata.get("status", "") or ""),
                "artifact_version": int(metadata.get("artifact_version", 1) or 1),
            }
            if referenced_head["event_type"] != "pending.reconcile.compliance_status_artifact":
                issues.append("referenced_head_wrong_event_type")
            if head_digest_sha256 and referenced_head["digest_sha256"] != head_digest_sha256:
                issues.append("referenced_head_digest_mismatch")

    signature_verification = {
        "available": False,
        "verified": False,
        "match": False,
        "reason": "payload_unavailable",
        "computed_checkpoint_digest": "",
        "computed_signature": "",
    }
    if payload:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        computed_checkpoint_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        signature_verification["available"] = True
        signature_verification["verified"] = True
        signature_verification["computed_checkpoint_digest"] = computed_checkpoint_digest

        checkpoint_digest = str(checkpoint.get("checkpoint_digest", "") or "").strip().lower()
        if checkpoint_digest and checkpoint_digest != computed_checkpoint_digest:
            issues.append("checkpoint_digest_mismatch")

        payload_head = dict(payload.get("head") or {})
        payload_head_event_id = int(payload_head.get("event_id", 0) or 0)
        payload_head_digest = str(payload_head.get("digest_sha256", "") or "").strip().lower()
        if payload_head_event_id and payload_head_event_id != head_event_id:
            issues.append("payload_head_event_mismatch")
        if payload_head_digest and payload_head_digest != head_digest_sha256:
            issues.append("payload_head_digest_mismatch")

        if signature_type == "hmac_sha256":
            secret, _, _ = _resolve_signing_secret(requested_key_id=key_id)
            if not secret:
                warnings.append("signing_secret_unavailable_for_checkpoint")
                signature_verification["verified"] = False
                signature_verification["reason"] = "signing_secret_unavailable"
            else:
                computed_signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
                signature_verification["computed_signature"] = computed_signature
                signature_verification["match"] = bool(signature and signature == computed_signature)
                signature_verification["reason"] = "verified"
                if signature and signature != computed_signature:
                    issues.append("checkpoint_signature_mismatch")
        elif signature_type == "sha256":
            computed_signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            signature_verification["computed_signature"] = computed_signature
            signature_verification["match"] = bool(signature and signature == computed_signature)
            signature_verification["reason"] = "verified"
            if signature and signature != computed_signature:
                issues.append("checkpoint_signature_mismatch")
        else:
            issues.append("unsupported_signature_type")
            signature_verification["reason"] = "unsupported_signature_type"
    else:
        warnings.append("checkpoint_payload_unavailable")
        if bool(require_signature_payload):
            issues.append("checkpoint_payload_unavailable")

    current_head = get_latest_reconcile_compliance_status_artifact_head()
    current_head_match = False
    if current_head.get("success", False):
        current_head_match = bool(
            int(current_head.get("event_id", 0) or 0) == head_event_id
            and str(current_head.get("digest_sha256", "") or "").strip().lower() == head_digest_sha256
        )
        if not current_head_match:
            warnings.append("checkpoint_not_current_head")
            if bool(require_current_head):
                issues.append("checkpoint_not_current_head")
    elif head_event_id > 0:
        warnings.append("current_head_unavailable")

    if issues:
        status = "broken"
    elif warnings:
        status = "stale"
    else:
        status = "ok"

    return {
        "success": True,
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "current_head_match": bool(current_head_match),
        "signature_verification": signature_verification,
        "checkpoint": checkpoint,
        "referenced_head": referenced_head,
        "current_head": current_head,
    }


def verify_reconcile_compliance_chain_checkpoint_history(
    limit: int = 200,
    require_signature_payload: bool = False,
) -> dict:
    """Verify integrity of recent compliance checkpoint events, including signature checks when possible."""
    rows = list_events(
        event_type="pending.reconcile.compliance_chain_checkpoint",
        limit=max(1, min(1000, int(limit))),
    )
    ordered = list(reversed(rows))
    if not ordered:
        return {
            "success": True,
            "count": 0,
            "ok": 0,
            "broken": 0,
            "stale": 0,
            "status": "empty",
            "issues": [],
            "rows": [],
        }

    entries: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []
    ok_count = 0
    broken_count = 0
    stale_count = 0

    for event in ordered:
        metadata = dict(event.get("metadata") or {})
        event_id = int(event.get("event_id", 0) or 0)
        created_at = str(event.get("created_at", "") or "")
        head_event_id = int(metadata.get("head_event_id", 0) or 0)
        head_digest_sha256 = str(metadata.get("head_digest_sha256", "") or "").strip().lower()
        payload = dict(metadata.get("payload") or {})
        signature = str(metadata.get("signature", "") or "").strip().lower()
        signature_type = str(metadata.get("signature_type", "") or "").strip().lower()
        key_id = str(metadata.get("key_id", "") or "").strip()

        issues: list[str] = []
        warnings: list[str] = []
        referenced_head = None

        if not str(metadata.get("checkpoint_digest", "") or "").strip():
            issues.append("missing_checkpoint_digest")
        if not signature:
            issues.append("missing_signature")
        if not signature_type:
            issues.append("missing_signature_type")
        if head_event_id <= 0:
            issues.append("missing_head_event_id")
        if not head_digest_sha256:
            issues.append("missing_head_digest_sha256")

        if head_event_id > 0:
            with tournament_db.get_tournament_connection() as conn:
                row = conn.execute(
                    "SELECT event_id, event_type, created_at, metadata_json FROM tournament_events WHERE event_id = ?",
                    (head_event_id,),
                ).fetchone()

            if row is None:
                issues.append("referenced_head_not_found")
            else:
                row_metadata = _loads_json(str(row["metadata_json"] or "{}"), {})
                referenced_head = {
                    "event_id": int(row["event_id"] or 0),
                    "event_type": str(row["event_type"] or ""),
                    "created_at": str(row["created_at"] or ""),
                    "digest_sha256": str(row_metadata.get("digest_sha256", "") or "").strip().lower(),
                    "chain_digest": str(row_metadata.get("chain_digest", "") or "").strip().lower(),
                    "previous_digest": str(row_metadata.get("previous_digest", "") or "").strip().lower(),
                    "status": str(row_metadata.get("status", "") or ""),
                    "artifact_version": int(row_metadata.get("artifact_version", 1) or 1),
                }
                if referenced_head["event_type"] != "pending.reconcile.compliance_status_artifact":
                    issues.append("referenced_head_wrong_event_type")
                if head_digest_sha256 and referenced_head["digest_sha256"] != head_digest_sha256:
                    issues.append("referenced_head_digest_mismatch")

        signature_verification = {
            "available": False,
            "verified": False,
            "match": False,
            "reason": "payload_unavailable",
            "computed_checkpoint_digest": "",
            "computed_signature": "",
        }
        if payload:
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            computed_checkpoint_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            signature_verification["available"] = True
            signature_verification["verified"] = True
            signature_verification["computed_checkpoint_digest"] = computed_checkpoint_digest

            checkpoint_digest = str(metadata.get("checkpoint_digest", "") or "").strip().lower()
            if checkpoint_digest and checkpoint_digest != computed_checkpoint_digest:
                issues.append("checkpoint_digest_mismatch")

            payload_head = dict(payload.get("head") or {})
            payload_head_event_id = int(payload_head.get("event_id", 0) or 0)
            payload_head_digest = str(payload_head.get("digest_sha256", "") or "").strip().lower()
            if payload_head_event_id and payload_head_event_id != head_event_id:
                issues.append("payload_head_event_mismatch")
            if payload_head_digest and payload_head_digest != head_digest_sha256:
                issues.append("payload_head_digest_mismatch")

            if signature_type == "hmac_sha256":
                secret, _, _ = _resolve_signing_secret(requested_key_id=key_id)
                if not secret:
                    warnings.append("signing_secret_unavailable_for_checkpoint")
                    signature_verification["verified"] = False
                    signature_verification["reason"] = "signing_secret_unavailable"
                else:
                    computed_signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
                    signature_verification["computed_signature"] = computed_signature
                    signature_verification["match"] = bool(signature and signature == computed_signature)
                    signature_verification["reason"] = "verified"
                    if signature and signature != computed_signature:
                        issues.append("checkpoint_signature_mismatch")
            elif signature_type == "sha256":
                computed_signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                signature_verification["computed_signature"] = computed_signature
                signature_verification["match"] = bool(signature and signature == computed_signature)
                signature_verification["reason"] = "verified"
                if signature and signature != computed_signature:
                    issues.append("checkpoint_signature_mismatch")
            else:
                issues.append("unsupported_signature_type")
                signature_verification["reason"] = "unsupported_signature_type"
        else:
            warnings.append("checkpoint_payload_unavailable")
            if bool(require_signature_payload):
                issues.append("checkpoint_payload_unavailable")

        if issues:
            row_status = "broken"
            broken_count += 1
            issue_rows.append({"event_id": event_id, "issues": issues})
        elif warnings:
            row_status = "stale"
            stale_count += 1
        else:
            row_status = "ok"
            ok_count += 1

        entries.append(
            {
                "event_id": event_id,
                "created_at": created_at,
                "label": str(metadata.get("label", "") or ""),
                "status": row_status,
                "issues": issues,
                "warnings": warnings,
                "head_event_id": head_event_id,
                "head_digest_sha256": head_digest_sha256,
                "signature_verification": signature_verification,
                "referenced_head": referenced_head,
            }
        )

    overall_status = "ok" if broken_count == 0 else "broken"
    return {
        "success": True,
        "count": len(entries),
        "ok": int(ok_count),
        "broken": int(broken_count),
        "stale": int(stale_count),
        "status": overall_status,
        "issues": issue_rows[:50],
        "rows": entries,
    }


def prune_reconcile_compliance_status_artifacts(
    max_age_days: int = 30,
    dry_run: bool = True,
    keep_latest: int | None = None,
    now: datetime | None = None,
) -> dict:
    """Delete old compliance artifact events with optional dry-run preview."""
    age_days = max(1, int(max_age_days))
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is not None:
        current = current.astimezone(timezone.utc).replace(tzinfo=None)
    cutoff = current - timedelta(days=age_days)
    cutoff_sql = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    with tournament_db.get_tournament_connection() as conn:
        scanned = int(
            conn.execute(
                "SELECT COUNT(1) AS c FROM tournament_events WHERE event_type = ?",
                ("pending.reconcile.compliance_status_artifact",),
            ).fetchone()["c"]
            or 0
        )
        candidate_rows = conn.execute(
            """
            SELECT event_id
            FROM tournament_events
            WHERE event_type = ?
              AND created_at < ?
            ORDER BY event_id ASC
            """,
            ("pending.reconcile.compliance_status_artifact", cutoff_sql),
        ).fetchall()

        keep_latest_ids: set[int] = set()
        keep_latest_int = None
        if keep_latest is not None:
            try:
                keep_latest_int = max(0, int(keep_latest))
            except Exception:
                keep_latest_int = 0
        if keep_latest_int and keep_latest_int > 0:
            keep_rows = conn.execute(
                """
                SELECT event_id
                FROM tournament_events
                WHERE event_type = ?
                ORDER BY event_id DESC
                LIMIT ?
                """,
                ("pending.reconcile.compliance_status_artifact", int(keep_latest_int)),
            ).fetchall()
            keep_latest_ids = {int(r["event_id"]) for r in keep_rows}

        candidate_ids = [int(r["event_id"]) for r in candidate_rows if int(r["event_id"]) not in keep_latest_ids]
        deleted = 0
        if not dry_run and candidate_ids:
            conn.executemany(
                "DELETE FROM tournament_events WHERE event_id = ?",
                [(eid,) for eid in candidate_ids],
            )
            conn.commit()
            deleted = len(candidate_ids)

    summary = {
        "success": True,
        "dry_run": bool(dry_run),
        "max_age_days": age_days,
        "cutoff": cutoff_sql,
        "scanned": scanned,
        "keep_latest": (None if keep_latest is None else max(0, int(keep_latest))),
        "candidates": len(candidate_ids),
        "deleted": deleted,
    }

    log_event(
        "pending.reconcile.compliance_status_artifacts_pruned",
        (
            "Compliance artifact prune summary: "
            f"dry_run={bool(dry_run)} scanned={scanned} "
            f"candidates={len(candidate_ids)} deleted={deleted}"
        ),
        severity="info",
        metadata=summary,
    )
    return summary


def get_reconcile_compliance_status(chain_limit: int = 200) -> dict:
    """Return a consolidated compliance snapshot for reconcile signing operations."""
    key_status = get_reconcile_signing_key_registry_status()
    artifact_head = get_latest_reconcile_signature_receipts_artifact_head()
    chain_verification = verify_reconcile_signature_receipts_artifact_chain(limit=chain_limit)
    compliance_chain_verification = verify_reconcile_compliance_status_artifact_chain(limit=chain_limit)
    checkpoint_verification = verify_reconcile_signature_chain_checkpoint(require_current_head=False)
    compliance_checkpoint_verification = verify_reconcile_compliance_chain_checkpoint(require_current_head=False)

    latest_prune = list_events(event_type="pending.reconcile.signature_receipts_pruned", limit=1)
    prune_status = {
        "success": False,
        "error": "No signature receipt prune event found",
    }
    if latest_prune:
        row = latest_prune[0]
        metadata = dict(row.get("metadata") or {})
        prune_status = {
            "success": True,
            "event_id": int(row.get("event_id", 0) or 0),
            "created_at": str(row.get("created_at", "") or ""),
            "dry_run": bool(metadata.get("dry_run", False)),
            "max_age_days": int(metadata.get("max_age_days", 0) or 0),
            "cutoff": str(metadata.get("cutoff", "") or ""),
            "scanned": int(metadata.get("scanned", 0) or 0),
            "candidates": int(metadata.get("candidates", 0) or 0),
            "deleted": int(metadata.get("deleted", 0) or 0),
        }

    issues: list[str] = []
    warnings: list[str] = []
    chain_status = str(chain_verification.get("status", "") or "")
    checkpoint_status = str(checkpoint_verification.get("status", "") or "")

    if chain_status == "broken":
        issues.append("artifact_chain_broken")
    elif chain_status == "empty":
        warnings.append("artifact_chain_empty")

    if checkpoint_status == "broken":
        issues.append("checkpoint_broken")
    elif checkpoint_status in {"empty", "stale"}:
        warnings.append(f"checkpoint_{checkpoint_status}")

    compliance_checkpoint_status = str(compliance_checkpoint_verification.get("status", "") or "")
    if compliance_checkpoint_status == "broken":
        issues.append("compliance_checkpoint_broken")
    elif compliance_checkpoint_status in {"empty", "stale"}:
        warnings.append(f"compliance_checkpoint_{compliance_checkpoint_status}")

    if int(key_status.get("registry_count", 0) or 0) <= 0 and not bool(key_status.get("fallback_key_configured", False)):
        warnings.append("no_signing_key_configured")

    compliance_artifact_head = get_latest_reconcile_compliance_status_artifact_head()
    latest_compliance_prune = list_events(event_type="pending.reconcile.compliance_status_artifacts_pruned", limit=1)
    compliance_prune_status = {
        "success": False,
        "error": "No compliance artifact prune event found",
    }
    if latest_compliance_prune:
        row = latest_compliance_prune[0]
        metadata = dict(row.get("metadata") or {})
        compliance_prune_status = {
            "success": True,
            "event_id": int(row.get("event_id", 0) or 0),
            "created_at": str(row.get("created_at", "") or ""),
            "dry_run": bool(metadata.get("dry_run", False)),
            "max_age_days": int(metadata.get("max_age_days", 0) or 0),
            "cutoff": str(metadata.get("cutoff", "") or ""),
            "scanned": int(metadata.get("scanned", 0) or 0),
            "candidates": int(metadata.get("candidates", 0) or 0),
            "deleted": int(metadata.get("deleted", 0) or 0),
        }

    compliance_chain_status = str(compliance_chain_verification.get("status", "") or "")
    if compliance_chain_status == "broken":
        issues.append("compliance_artifact_chain_broken")
    elif compliance_chain_status == "empty":
        warnings.append("compliance_artifact_chain_empty")

    if issues:
        overall_status = "error"
    elif warnings:
        overall_status = "warning"
    else:
        overall_status = "ok"

    return {
        "success": True,
        "status": overall_status,
        "issues": issues,
        "warnings": warnings,
        "artifact_head": artifact_head,
        "artifact_chain": chain_verification,
        "latest_checkpoint": checkpoint_verification,
        "latest_compliance_checkpoint": compliance_checkpoint_verification,
        "signing_keys": key_status,
        "latest_prune": prune_status,
        "latest_compliance_artifact": compliance_artifact_head,
        "compliance_artifact_chain": compliance_chain_verification,
        "latest_compliance_prune": compliance_prune_status,
    }


def export_reconcile_compliance_status_artifact(
    chain_limit: int = 200,
    include_json: bool = True,
    previous_digest: str = "",
    auto_chain: bool = True,
    persist_event: bool = True,
) -> dict:
    """Export compliance status snapshot as a deterministic artifact with optional chain linkage."""
    snapshot = get_reconcile_compliance_status(chain_limit=max(1, min(1000, int(chain_limit))))
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    artifact_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    resolved_previous = str(previous_digest or "").strip().lower()
    chain_source = "provided" if resolved_previous else "none"
    if not resolved_previous and bool(auto_chain):
        latest_head = get_latest_reconcile_compliance_status_artifact_head()
        if latest_head.get("success"):
            resolved_previous = str(latest_head.get("digest_sha256", "") or "").strip().lower()
            chain_source = "latest_event"

    chain_input = f"{resolved_previous}:{artifact_digest}" if resolved_previous else artifact_digest
    chain_digest = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()

    result = {
        "success": True,
        "artifact_version": 1,
        "chain_limit": max(1, min(1000, int(chain_limit))),
        "status": str(snapshot.get("status", "") or ""),
        "digest_sha256": artifact_digest,
        "previous_digest": resolved_previous,
        "chain_source": chain_source,
        "chain_digest": chain_digest,
        "snapshot": snapshot,
        "json": canonical if bool(include_json) else "",
    }

    if bool(persist_event):
        event_id = log_event(
            "pending.reconcile.compliance_status_artifact",
            "Reconcile compliance status artifact exported",
            severity="info",
            metadata={
                "artifact_version": int(result.get("artifact_version", 1)),
                "chain_limit": int(result.get("chain_limit", 200)),
                "status": str(result.get("status", "") or ""),
                "digest_sha256": str(result.get("digest_sha256", "") or ""),
                "previous_digest": str(result.get("previous_digest", "") or ""),
                "chain_source": str(result.get("chain_source", "none") or "none"),
                "chain_digest": str(result.get("chain_digest", "") or ""),
                "include_json": bool(include_json),
            },
        )
        result["artifact_event_id"] = int(event_id)

    return result


def export_reconcile_compliance_status_envelope(
    chain_limit: int = 200,
    include_json: bool = False,
    previous_digest: str = "",
    auto_chain: bool = True,
    persist_event: bool = True,
    create_checkpoint: bool = True,
    checkpoint_label: str = "ops_envelope",
    checkpoint_note: str = "",
    require_current_head: bool = False,
    require_signature_payload: bool = True,
    signing_key: str = "",
) -> dict:
    """Export compliance artifact plus checkpoint verification envelope for external interchange."""
    artifact = export_reconcile_compliance_status_artifact(
        chain_limit=max(1, min(1000, int(chain_limit))),
        include_json=bool(include_json),
        previous_digest=str(previous_digest or ""),
        auto_chain=bool(auto_chain),
        persist_event=bool(persist_event),
    )

    checkpoint: dict[str, Any] = {
        "success": False,
        "skipped": True,
        "reason": "create_checkpoint_disabled",
    }
    if bool(create_checkpoint):
        checkpoint = create_reconcile_compliance_chain_checkpoint(
            label=str(checkpoint_label or "ops_envelope").strip() or "ops_envelope",
            note=str(checkpoint_note or ""),
            expected_previous_digest=str(artifact.get("digest_sha256", "") or "").strip().lower(),
            require_head=bool(persist_event),
            signing_key=str(signing_key or ""),
        )

    verification = verify_reconcile_compliance_chain_checkpoint(
        require_current_head=bool(require_current_head),
        require_signature_payload=bool(require_signature_payload),
    )

    key_id = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "") or "").strip()
    signature_version = int(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "1") or 1)
    envelope_payload = {
        "envelope_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifact": artifact,
        "checkpoint": checkpoint,
        "verification": verification,
        "signature_metadata": {
            "key_id": key_id,
            "signature_version": signature_version,
        },
    }
    canonical = json.dumps(envelope_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    envelope_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    secret, resolved_key_id, key_source = _resolve_signing_secret(
        requested_key_id=key_id,
        explicit_signing_key=str(signing_key or "").strip(),
    )
    if resolved_key_id and not key_id:
        key_id = resolved_key_id
        envelope_payload["signature_metadata"]["key_id"] = key_id

    if secret:
        signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_type = "hmac_sha256"
        signed = True
    else:
        signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        signature_type = "sha256"
        signed = False

    return {
        "success": bool(artifact.get("success", False)),
        "match": str(verification.get("status", "") or "").lower() == "ok",
        "signed": bool(signed),
        "signature_type": signature_type,
        "key_id": key_id,
        "key_source": key_source,
        "signature_version": signature_version,
        "signature": signature,
        "envelope_digest": envelope_digest,
        "envelope": envelope_payload,
        "verify_payload": {
            "artifact_digest_sha256": str(artifact.get("digest_sha256", "") or ""),
            "checkpoint_event_id": int(checkpoint.get("event_id", 0) or 0),
            "checkpoint_digest": str(checkpoint.get("checkpoint_digest", "") or ""),
            "verification_status": str(verification.get("status", "") or ""),
            "signature": signature,
            "signature_type": signature_type,
            "key_id": key_id,
            "signature_version": signature_version,
        },
    }


def get_reconcile_compliance_readiness_policies() -> dict:
    """Return built-in and environment-overridden readiness policy configuration."""
    defaults = {
        "default": {
            "chain_limit": 200,
            "warning_threshold": 80,
            "error_threshold": 60,
            "monitor_transition": False,
            "transition_cooldown_minutes": 0,
            "issue_penalty": 30,
            "warning_penalty": 10,
            "check_failure_penalty_default": 8,
            "check_failure_penalties": {
                "signing_key_ready": 15,
            },
        },
        "strict": {
            "chain_limit": 300,
            "warning_threshold": 90,
            "error_threshold": 75,
            "monitor_transition": True,
            "transition_cooldown_minutes": 30,
            "issue_penalty": 35,
            "warning_penalty": 12,
            "check_failure_penalty_default": 10,
            "check_failure_penalties": {
                "signing_key_ready": 20,
            },
        },
        "relaxed": {
            "chain_limit": 100,
            "warning_threshold": 70,
            "error_threshold": 50,
            "monitor_transition": False,
            "transition_cooldown_minutes": 0,
            "issue_penalty": 20,
            "warning_penalty": 8,
            "check_failure_penalty_default": 6,
            "check_failure_penalties": {
                "signing_key_ready": 12,
            },
        },
    }

    raw = str(os.environ.get("TOURNAMENT_RECONCILE_COMPLIANCE_POLICIES_JSON", "") or "").strip()
    overrides = _loads_json(raw, {}) if raw else {}
    if not isinstance(overrides, dict):
        overrides = {}

    policies: dict[str, dict[str, Any]] = {}
    for name, cfg in defaults.items():
        policies[name] = dict(cfg)

    for key, value in overrides.items():
        name = str(key or "").strip().lower()
        if not name:
            continue
        parsed = dict(value or {}) if isinstance(value, dict) else {}
        if name not in policies:
            policies[name] = {
                "chain_limit": 200,
                "warning_threshold": 80,
                "error_threshold": 60,
                "monitor_transition": False,
                "transition_cooldown_minutes": 0,
                "issue_penalty": 30,
                "warning_penalty": 10,
                "check_failure_penalty_default": 8,
                "check_failure_penalties": {
                    "signing_key_ready": 15,
                },
            }
        if "chain_limit" in parsed:
            policies[name]["chain_limit"] = max(1, min(1000, int(parsed.get("chain_limit", 200) or 200)))
        if "warning_threshold" in parsed:
            policies[name]["warning_threshold"] = max(1, min(99, int(parsed.get("warning_threshold", 80) or 80)))
        if "error_threshold" in parsed:
            policies[name]["error_threshold"] = max(0, min(98, int(parsed.get("error_threshold", 60) or 60)))
        if "monitor_transition" in parsed:
            policies[name]["monitor_transition"] = bool(parsed.get("monitor_transition", False))
        if "transition_cooldown_minutes" in parsed:
            policies[name]["transition_cooldown_minutes"] = max(0, min(1440, int(parsed.get("transition_cooldown_minutes", 0) or 0)))
        if "issue_penalty" in parsed:
            policies[name]["issue_penalty"] = max(0, min(100, int(parsed.get("issue_penalty", 30) or 30)))
        if "warning_penalty" in parsed:
            policies[name]["warning_penalty"] = max(0, min(100, int(parsed.get("warning_penalty", 10) or 10)))
        if "check_failure_penalty_default" in parsed:
            policies[name]["check_failure_penalty_default"] = max(0, min(100, int(parsed.get("check_failure_penalty_default", 8) or 8)))
        if "check_failure_penalties" in parsed and isinstance(parsed.get("check_failure_penalties"), dict):
            resolved_penalties: dict[str, int] = {}
            for check_name, penalty in dict(parsed.get("check_failure_penalties") or {}).items():
                normalized_check = str(check_name or "").strip()
                if not normalized_check:
                    continue
                resolved_penalties[normalized_check] = max(0, min(100, int(penalty or 0)))
            if resolved_penalties:
                policies[name]["check_failure_penalties"] = resolved_penalties

    for cfg in policies.values():
        if int(cfg.get("error_threshold", 60) or 60) >= int(cfg.get("warning_threshold", 80) or 80):
            cfg["warning_threshold"] = min(99, int(cfg.get("error_threshold", 60) or 60) + 1)

    return {
        "success": True,
        "default_policy": "default",
        "count": len(policies),
        "policies": policies,
    }


def _resolve_reconcile_compliance_readiness_policy(policy_name: str = "default") -> dict:
    registry = get_reconcile_compliance_readiness_policies()
    policies = dict(registry.get("policies") or {})
    requested = str(policy_name or "default").strip().lower() or "default"
    resolved = requested if requested in policies else "default"
    cfg = dict(policies.get(resolved) or {})
    return {
        "requested": requested,
        "resolved": resolved,
        "found": requested in policies,
        "config": cfg,
        "registry": registry,
    }


def get_latest_reconcile_compliance_readiness_policy_snapshot_head(policy_name: str = "") -> dict:
    """Return metadata for the most recent readiness policy snapshot artifact."""
    rows = list_events(event_type="pending.reconcile.compliance_readiness_policy_snapshot", limit=200)
    normalized_policy = str(policy_name or "").strip().lower()
    for row in rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        return {
            "success": True,
            "event_id": int(row.get("event_id", 0) or 0),
            "created_at": str(row.get("created_at", "") or ""),
            "policy_name": row_policy,
            "policy_digest_sha256": str(metadata.get("policy_digest_sha256", "") or ""),
            "digest_sha256": str(metadata.get("digest_sha256", "") or ""),
            "chain_digest": str(metadata.get("chain_digest", "") or ""),
            "previous_digest": str(metadata.get("previous_digest", "") or ""),
            "chain_source": str(metadata.get("chain_source", "none") or "none"),
            "snapshot_version": int(metadata.get("snapshot_version", 1) or 1),
            "signed": bool(metadata.get("signed", False)),
            "signature_type": str(metadata.get("signature_type", "") or ""),
            "key_id": str(metadata.get("key_id", "") or ""),
            "signature_version": int(metadata.get("signature_version", 1) or 1),
        }

    return {
        "success": False,
        "error": (
            "No readiness policy snapshot found"
            if not normalized_policy
            else f"No readiness policy snapshot found for policy {normalized_policy}"
        ),
    }


def export_reconcile_compliance_readiness_policy_snapshot(
    policy_name: str = "default",
    include_registry: bool = False,
    previous_digest: str = "",
    auto_chain: bool = True,
    persist_event: bool = True,
    signing_key: str = "",
) -> dict:
    """Export deterministic signed readiness policy snapshot artifact with optional chain linkage."""
    resolution = _resolve_reconcile_compliance_readiness_policy(policy_name=str(policy_name or "default"))
    resolved_name = str(resolution.get("resolved", "default") or "default")
    policy_config = dict(resolution.get("config") or {})
    registry = dict((resolution.get("registry") or {}).get("policies") or {})

    payload = {
        "snapshot_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "requested_name": str(resolution.get("requested", "default") or "default"),
            "name": resolved_name,
            "found": bool(resolution.get("found", False)),
            "config": policy_config,
        },
        "registry": (registry if bool(include_registry) else {}),
    }

    policy_canonical = json.dumps(payload["policy"], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    policy_digest = hashlib.sha256(policy_canonical.encode("utf-8")).hexdigest()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    artifact_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    resolved_previous = str(previous_digest or "").strip().lower()
    chain_source = "provided" if resolved_previous else "none"
    if not resolved_previous and bool(auto_chain):
        latest_head = get_latest_reconcile_compliance_readiness_policy_snapshot_head(policy_name=resolved_name)
        if latest_head.get("success"):
            resolved_previous = str(latest_head.get("digest_sha256", "") or "").strip().lower()
            chain_source = "latest_event"

    chain_input = f"{resolved_previous}:{artifact_digest}" if resolved_previous else artifact_digest
    chain_digest = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()

    key_id = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "") or "").strip()
    signature_version = int(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "1") or 1)
    secret, resolved_key_id, key_source = _resolve_signing_secret(
        requested_key_id=key_id,
        explicit_signing_key=str(signing_key or "").strip(),
    )
    if resolved_key_id and not key_id:
        key_id = resolved_key_id

    if secret:
        signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_type = "hmac_sha256"
        signed = True
    else:
        signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        signature_type = "sha256"
        signed = False

    result = {
        "success": True,
        "snapshot_version": 1,
        "policy_name": resolved_name,
        "policy_digest_sha256": policy_digest,
        "digest_sha256": artifact_digest,
        "previous_digest": resolved_previous,
        "chain_source": chain_source,
        "chain_digest": chain_digest,
        "signed": bool(signed),
        "signature": signature,
        "signature_type": signature_type,
        "key_id": key_id,
        "key_source": key_source,
        "signature_version": signature_version,
        "snapshot": payload,
    }

    if bool(persist_event):
        event_id = log_event(
            "pending.reconcile.compliance_readiness_policy_snapshot",
            f"Readiness policy snapshot exported for policy={resolved_name}",
            severity="info",
            metadata={
                "snapshot_version": int(result.get("snapshot_version", 1)),
                "policy_name": str(resolved_name),
                "policy_digest_sha256": str(policy_digest),
                "digest_sha256": str(artifact_digest),
                "previous_digest": str(resolved_previous),
                "chain_source": str(chain_source),
                "chain_digest": str(chain_digest),
                "include_registry": bool(include_registry),
                "signed": bool(signed),
                "signature": str(signature),
                "signature_type": str(signature_type),
                "key_id": str(key_id),
                "key_source": str(key_source),
                "signature_version": int(signature_version),
            },
        )
        result["snapshot_event_id"] = int(event_id)

    return result


def verify_reconcile_compliance_readiness_policy_snapshot_chain(limit: int = 200, policy_name: str = "") -> dict:
    """Verify chain integrity for readiness policy snapshots, optionally scoped to one policy."""
    rows = list_events(
        event_type="pending.reconcile.compliance_readiness_policy_snapshot",
        limit=max(1, min(1000, int(limit))),
    )
    normalized_policy = str(policy_name or "").strip().lower()
    ordered_rows = list(reversed(rows))
    filtered: list[dict[str, Any]] = []
    for row in ordered_rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        filtered.append(row)

    if not filtered:
        return {
            "success": True,
            "count": 0,
            "valid_links": 0,
            "broken_links": 0,
            "status": "empty",
            "policy_name": normalized_policy,
            "issues": [],
        }

    issues: list[dict[str, Any]] = []
    valid_links = 0
    previous_digest = ""
    for event in filtered:
        metadata = dict(event.get("metadata") or {})
        event_id = int(event.get("event_id", 0) or 0)
        digest = str(metadata.get("digest_sha256", "") or "").strip().lower()
        declared_previous = str(metadata.get("previous_digest", "") or "").strip().lower()
        declared_chain = str(metadata.get("chain_digest", "") or "").strip().lower()

        expected_previous = previous_digest
        expected_chain_input = f"{declared_previous}:{digest}" if declared_previous else digest
        expected_chain = hashlib.sha256(expected_chain_input.encode("utf-8")).hexdigest() if digest else ""

        event_issues = []
        if not digest:
            event_issues.append("missing_digest")
        if declared_previous != expected_previous:
            event_issues.append("previous_digest_mismatch")
        if declared_chain != expected_chain:
            event_issues.append("chain_digest_mismatch")

        if event_issues:
            issues.append(
                {
                    "event_id": event_id,
                    "issues": event_issues,
                    "declared_previous": declared_previous,
                    "expected_previous": expected_previous,
                    "declared_chain": declared_chain,
                    "expected_chain": expected_chain,
                    "digest_sha256": digest,
                }
            )
        else:
            valid_links += 1

        previous_digest = digest

    return {
        "success": True,
        "count": len(filtered),
        "valid_links": int(valid_links),
        "broken_links": int(len(issues)),
        "status": ("ok" if not issues else "broken"),
        "policy_name": normalized_policy,
        "head_event_id": int(filtered[-1].get("event_id", 0) or 0),
        "head_digest_sha256": str((filtered[-1].get("metadata") or {}).get("digest_sha256", "") or ""),
        "issues": issues[:50],
    }


def prune_reconcile_compliance_readiness_policy_snapshots(
    max_age_days: int = 30,
    dry_run: bool = True,
    policy_name: str = "",
    keep_latest: int | None = None,
    now: datetime | None = None,
) -> dict:
    """Delete old readiness policy snapshot events with optional policy scope and retention keep-latest."""
    age_days = max(1, int(max_age_days))
    normalized_policy = str(policy_name or "").strip().lower()
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is not None:
        current = current.astimezone(timezone.utc).replace(tzinfo=None)
    cutoff = current - timedelta(days=age_days)
    cutoff_sql = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    with tournament_db.get_tournament_connection() as conn:
        scanned = int(
            conn.execute(
                "SELECT COUNT(1) AS c FROM tournament_events WHERE event_type = ?",
                ("pending.reconcile.compliance_readiness_policy_snapshot",),
            ).fetchone()["c"]
            or 0
        )
        candidate_rows = conn.execute(
            """
            SELECT event_id, metadata_json
            FROM tournament_events
            WHERE event_type = ?
              AND created_at < ?
            ORDER BY event_id ASC
            """,
            ("pending.reconcile.compliance_readiness_policy_snapshot", cutoff_sql),
        ).fetchall()

        filtered_ids: list[int] = []
        for row in candidate_rows:
            metadata = _loads_json(str(row["metadata_json"] or "{}"), {})
            row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
            if normalized_policy and row_policy != normalized_policy:
                continue
            filtered_ids.append(int(row["event_id"]))

        keep_latest_ids: set[int] = set()
        keep_latest_int = None
        if keep_latest is not None:
            try:
                keep_latest_int = max(0, int(keep_latest))
            except Exception:
                keep_latest_int = 0
        if keep_latest_int and keep_latest_int > 0:
            recent_rows = conn.execute(
                """
                SELECT event_id, metadata_json
                FROM tournament_events
                WHERE event_type = ?
                ORDER BY event_id DESC
                LIMIT ?
                """,
                ("pending.reconcile.compliance_readiness_policy_snapshot", int(max(keep_latest_int * 5, keep_latest_int))),
            ).fetchall()
            kept = 0
            for row in recent_rows:
                metadata = _loads_json(str(row["metadata_json"] or "{}"), {})
                row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
                if normalized_policy and row_policy != normalized_policy:
                    continue
                keep_latest_ids.add(int(row["event_id"]))
                kept += 1
                if kept >= int(keep_latest_int):
                    break

        candidate_ids = [eid for eid in filtered_ids if eid not in keep_latest_ids]
        deleted = 0
        if not dry_run and candidate_ids:
            conn.executemany(
                "DELETE FROM tournament_events WHERE event_id = ?",
                [(eid,) for eid in candidate_ids],
            )
            conn.commit()
            deleted = len(candidate_ids)

    summary = {
        "success": True,
        "dry_run": bool(dry_run),
        "policy_name": normalized_policy,
        "max_age_days": age_days,
        "cutoff": cutoff_sql,
        "scanned": scanned,
        "keep_latest": (None if keep_latest is None else max(0, int(keep_latest))),
        "candidates": len(candidate_ids),
        "deleted": deleted,
    }
    log_event(
        "pending.reconcile.compliance_readiness_policy_snapshots_pruned",
        (
            "Readiness policy snapshot prune summary: "
            f"policy={normalized_policy or 'all'} dry_run={bool(dry_run)} "
            f"candidates={len(candidate_ids)} deleted={deleted}"
        ),
        severity="info",
        metadata=summary,
    )
    return summary


def create_reconcile_compliance_readiness_policy_snapshot_checkpoint(
    policy_name: str = "default",
    label: str = "",
    note: str = "",
    expected_previous_digest: str = "",
    require_head: bool = True,
    signing_key: str = "",
) -> dict:
    """Create a signed checkpoint anchored to the latest readiness policy snapshot head."""
    normalized_policy = str(policy_name or "default").strip().lower() or "default"
    head = get_latest_reconcile_compliance_readiness_policy_snapshot_head(policy_name=normalized_policy)
    if not head.get("success", False):
        if bool(require_head):
            return {
                "success": False,
                "error": str(head.get("error", "No readiness policy snapshot head available")),
                "head": head,
            }
        head = {
            "success": True,
            "event_id": 0,
            "created_at": "",
            "policy_name": normalized_policy,
            "policy_digest_sha256": "",
            "digest_sha256": "",
            "chain_digest": "",
            "previous_digest": "",
            "chain_source": "none",
            "snapshot_version": 1,
            "signed": False,
            "signature_type": "",
            "key_id": "",
            "signature_version": 1,
        }

    expected = str(expected_previous_digest or "").strip().lower()
    current_digest = str(head.get("digest_sha256", "") or "").strip().lower()
    if expected and expected != current_digest:
        return {
            "success": False,
            "error": "expected_previous_digest does not match current readiness policy snapshot head",
            "expected_previous_digest": expected,
            "head_digest_sha256": current_digest,
            "policy_name": normalized_policy,
        }

    key_id = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "") or "").strip()
    signature_version = int(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "1") or 1)
    payload = {
        "checkpoint_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": str(label or "").strip(),
        "note": str(note or "").strip(),
        "policy_name": normalized_policy,
        "head": {
            "event_id": int(head.get("event_id", 0) or 0),
            "created_at": str(head.get("created_at", "") or ""),
            "policy_name": str(head.get("policy_name", normalized_policy) or normalized_policy).strip().lower(),
            "policy_digest_sha256": str(head.get("policy_digest_sha256", "") or "").strip().lower(),
            "digest_sha256": current_digest,
            "chain_digest": str(head.get("chain_digest", "") or "").strip().lower(),
            "previous_digest": str(head.get("previous_digest", "") or "").strip().lower(),
            "chain_source": str(head.get("chain_source", "none") or "none"),
            "snapshot_version": int(head.get("snapshot_version", 1) or 1),
        },
        "signature_metadata": {
            "key_id": key_id,
            "signature_version": signature_version,
        },
    }

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    secret, resolved_key_id, key_source = _resolve_signing_secret(
        requested_key_id=key_id,
        explicit_signing_key=str(signing_key or "").strip(),
    )
    if resolved_key_id and not key_id:
        key_id = resolved_key_id
        payload["signature_metadata"]["key_id"] = key_id

    if secret:
        signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_type = "hmac_sha256"
        signed = True
    else:
        signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        signature_type = "sha256"
        signed = False

    checkpoint_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    event_id = log_event(
        "pending.reconcile.compliance_readiness_policy_snapshot_checkpoint",
        f"Readiness policy snapshot checkpoint created for policy={normalized_policy}",
        severity="info",
        metadata={
            "policy_name": normalized_policy,
            "checkpoint_digest": checkpoint_digest,
            "signature": signature,
            "signature_type": signature_type,
            "signed": bool(signed),
            "key_id": key_id,
            "key_source": key_source,
            "signature_version": signature_version,
            "head_event_id": int(head.get("event_id", 0) or 0),
            "head_digest_sha256": current_digest,
            "label": str(label or "").strip(),
            "payload": payload,
        },
    )

    return {
        "success": True,
        "event_id": int(event_id),
        "policy_name": normalized_policy,
        "checkpoint_digest": checkpoint_digest,
        "signature": signature,
        "signature_type": signature_type,
        "signed": bool(signed),
        "key_id": key_id,
        "key_source": key_source,
        "signature_version": signature_version,
        "payload": payload,
    }


def get_latest_reconcile_compliance_readiness_policy_snapshot_checkpoint(policy_name: str = "") -> dict:
    """Return metadata for the most recent readiness policy snapshot checkpoint event."""
    rows = list_events(event_type="pending.reconcile.compliance_readiness_policy_snapshot_checkpoint", limit=200)
    normalized_policy = str(policy_name or "").strip().lower()
    for row in rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        return {
            "success": True,
            "event_id": int(row.get("event_id", 0) or 0),
            "created_at": str(row.get("created_at", "") or ""),
            "policy_name": row_policy,
            "checkpoint_digest": str(metadata.get("checkpoint_digest", "") or ""),
            "signature": str(metadata.get("signature", "") or ""),
            "signature_type": str(metadata.get("signature_type", "") or ""),
            "signed": bool(metadata.get("signed", False)),
            "key_id": str(metadata.get("key_id", "") or ""),
            "key_source": str(metadata.get("key_source", "") or ""),
            "signature_version": int(metadata.get("signature_version", 1) or 1),
            "head_event_id": int(metadata.get("head_event_id", 0) or 0),
            "head_digest_sha256": str(metadata.get("head_digest_sha256", "") or ""),
            "label": str(metadata.get("label", "") or ""),
            "payload": dict(metadata.get("payload") or {}),
        }

    return {
        "success": False,
        "error": (
            "No readiness policy snapshot checkpoint found"
            if not normalized_policy
            else f"No readiness policy snapshot checkpoint found for policy {normalized_policy}"
        ),
    }


def verify_reconcile_compliance_readiness_policy_snapshot_checkpoint(
    policy_name: str = "",
    require_current_head: bool = False,
    require_signature_payload: bool = False,
) -> dict:
    """Verify latest readiness policy snapshot checkpoint event against referenced snapshot head."""
    normalized_policy = str(policy_name or "").strip().lower()
    checkpoint = get_latest_reconcile_compliance_readiness_policy_snapshot_checkpoint(policy_name=normalized_policy)
    if not checkpoint.get("success", False):
        return {
            "success": True,
            "status": "empty",
            "issues": [],
            "checkpoint": checkpoint,
        }

    issues: list[str] = []
    warnings: list[str] = []
    head_event_id = int(checkpoint.get("head_event_id", 0) or 0)
    head_digest_sha256 = str(checkpoint.get("head_digest_sha256", "") or "").strip().lower()
    payload = dict(checkpoint.get("payload") or {})
    signature = str(checkpoint.get("signature", "") or "").strip().lower()
    signature_type = str(checkpoint.get("signature_type", "") or "").strip().lower()
    key_id = str(checkpoint.get("key_id", "") or "").strip()
    row_policy = str(checkpoint.get("policy_name", "") or "").strip().lower()

    if normalized_policy and row_policy != normalized_policy:
        issues.append("checkpoint_policy_mismatch")
    if not str(checkpoint.get("checkpoint_digest", "") or "").strip():
        issues.append("missing_checkpoint_digest")
    if not signature:
        issues.append("missing_signature")
    if not signature_type:
        issues.append("missing_signature_type")
    if head_event_id <= 0:
        issues.append("missing_head_event_id")
    if not head_digest_sha256:
        issues.append("missing_head_digest_sha256")

    referenced_head = None
    if head_event_id > 0:
        with tournament_db.get_tournament_connection() as conn:
            row = conn.execute(
                "SELECT event_id, event_type, created_at, metadata_json FROM tournament_events WHERE event_id = ?",
                (head_event_id,),
            ).fetchone()
        if row is None:
            issues.append("referenced_head_not_found")
        else:
            metadata = _loads_json(str(row["metadata_json"] or "{}"), {})
            referenced_head = {
                "event_id": int(row["event_id"] or 0),
                "event_type": str(row["event_type"] or ""),
                "created_at": str(row["created_at"] or ""),
                "policy_name": str(metadata.get("policy_name", "") or "").strip().lower(),
                "digest_sha256": str(metadata.get("digest_sha256", "") or "").strip().lower(),
                "chain_digest": str(metadata.get("chain_digest", "") or "").strip().lower(),
                "previous_digest": str(metadata.get("previous_digest", "") or "").strip().lower(),
                "snapshot_version": int(metadata.get("snapshot_version", 1) or 1),
            }
            if referenced_head["event_type"] != "pending.reconcile.compliance_readiness_policy_snapshot":
                issues.append("referenced_head_wrong_event_type")
            if head_digest_sha256 and referenced_head["digest_sha256"] != head_digest_sha256:
                issues.append("referenced_head_digest_mismatch")
            if row_policy and referenced_head["policy_name"] and row_policy != referenced_head["policy_name"]:
                issues.append("referenced_head_policy_mismatch")

    signature_verification = {
        "available": False,
        "verified": False,
        "match": False,
        "reason": "payload_unavailable",
        "computed_checkpoint_digest": "",
        "computed_signature": "",
    }
    if payload:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        computed_checkpoint_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        signature_verification["available"] = True
        signature_verification["verified"] = True
        signature_verification["computed_checkpoint_digest"] = computed_checkpoint_digest

        checkpoint_digest = str(checkpoint.get("checkpoint_digest", "") or "").strip().lower()
        if checkpoint_digest and checkpoint_digest != computed_checkpoint_digest:
            issues.append("checkpoint_digest_mismatch")

        payload_head = dict(payload.get("head") or {})
        payload_head_event_id = int(payload_head.get("event_id", 0) or 0)
        payload_head_digest = str(payload_head.get("digest_sha256", "") or "").strip().lower()
        if payload_head_event_id and payload_head_event_id != head_event_id:
            issues.append("payload_head_event_mismatch")
        if payload_head_digest and payload_head_digest != head_digest_sha256:
            issues.append("payload_head_digest_mismatch")

        if signature_type == "hmac_sha256":
            secret, _, _ = _resolve_signing_secret(requested_key_id=key_id)
            if not secret:
                warnings.append("signing_secret_unavailable_for_checkpoint")
                signature_verification["verified"] = False
                signature_verification["reason"] = "signing_secret_unavailable"
            else:
                computed_signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
                signature_verification["computed_signature"] = computed_signature
                signature_verification["match"] = bool(signature and signature == computed_signature)
                signature_verification["reason"] = "verified"
                if signature and signature != computed_signature:
                    issues.append("checkpoint_signature_mismatch")
        elif signature_type == "sha256":
            computed_signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            signature_verification["computed_signature"] = computed_signature
            signature_verification["match"] = bool(signature and signature == computed_signature)
            signature_verification["reason"] = "verified"
            if signature and signature != computed_signature:
                issues.append("checkpoint_signature_mismatch")
        else:
            issues.append("unsupported_signature_type")
            signature_verification["reason"] = "unsupported_signature_type"
    else:
        warnings.append("checkpoint_payload_unavailable")
        if bool(require_signature_payload):
            issues.append("checkpoint_payload_unavailable")

    current_head = get_latest_reconcile_compliance_readiness_policy_snapshot_head(policy_name=(row_policy or normalized_policy))
    current_head_match = False
    if current_head.get("success", False):
        current_head_match = bool(
            int(current_head.get("event_id", 0) or 0) == head_event_id
            and str(current_head.get("digest_sha256", "") or "").strip().lower() == head_digest_sha256
        )
        if not current_head_match:
            warnings.append("checkpoint_not_current_head")
            if bool(require_current_head):
                issues.append("checkpoint_not_current_head")
    elif head_event_id > 0:
        warnings.append("current_head_unavailable")

    status = "broken" if issues else ("stale" if warnings else "ok")
    return {
        "success": True,
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "current_head_match": bool(current_head_match),
        "signature_verification": signature_verification,
        "checkpoint": checkpoint,
        "referenced_head": referenced_head,
        "current_head": current_head,
    }


def verify_reconcile_compliance_readiness_policy_snapshot_checkpoint_history(
    limit: int = 200,
    policy_name: str = "",
    require_signature_payload: bool = False,
) -> dict:
    """Verify integrity of recent readiness policy snapshot checkpoint events."""
    rows = list_events(
        event_type="pending.reconcile.compliance_readiness_policy_snapshot_checkpoint",
        limit=max(1, min(1000, int(limit))),
    )
    normalized_policy = str(policy_name or "").strip().lower()
    ordered = list(reversed(rows))
    if normalized_policy:
        scoped: list[dict[str, Any]] = []
        for row in ordered:
            metadata = dict(row.get("metadata") or {})
            row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
            if row_policy != normalized_policy:
                continue
            scoped.append(row)
        ordered = scoped

    if not ordered:
        return {
            "success": True,
            "count": 0,
            "ok": 0,
            "broken": 0,
            "stale": 0,
            "status": "empty",
            "policy_name": normalized_policy,
            "issues": [],
            "rows": [],
        }

    entries: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []
    ok_count = 0
    broken_count = 0
    stale_count = 0

    for event in ordered:
        metadata = dict(event.get("metadata") or {})
        event_id = int(event.get("event_id", 0) or 0)
        created_at = str(event.get("created_at", "") or "")
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        head_event_id = int(metadata.get("head_event_id", 0) or 0)
        head_digest_sha256 = str(metadata.get("head_digest_sha256", "") or "").strip().lower()
        payload = dict(metadata.get("payload") or {})
        signature = str(metadata.get("signature", "") or "").strip().lower()
        signature_type = str(metadata.get("signature_type", "") or "").strip().lower()
        key_id = str(metadata.get("key_id", "") or "").strip()

        issues: list[str] = []
        warnings: list[str] = []
        referenced_head = None

        if not str(metadata.get("checkpoint_digest", "") or "").strip():
            issues.append("missing_checkpoint_digest")
        if not signature:
            issues.append("missing_signature")
        if not signature_type:
            issues.append("missing_signature_type")
        if head_event_id <= 0:
            issues.append("missing_head_event_id")
        if not head_digest_sha256:
            issues.append("missing_head_digest_sha256")

        if head_event_id > 0:
            with tournament_db.get_tournament_connection() as conn:
                row = conn.execute(
                    "SELECT event_id, event_type, created_at, metadata_json FROM tournament_events WHERE event_id = ?",
                    (head_event_id,),
                ).fetchone()
            if row is None:
                issues.append("referenced_head_not_found")
            else:
                row_metadata = _loads_json(str(row["metadata_json"] or "{}"), {})
                referenced_head = {
                    "event_id": int(row["event_id"] or 0),
                    "event_type": str(row["event_type"] or ""),
                    "created_at": str(row["created_at"] or ""),
                    "policy_name": str(row_metadata.get("policy_name", "") or "").strip().lower(),
                    "digest_sha256": str(row_metadata.get("digest_sha256", "") or "").strip().lower(),
                    "chain_digest": str(row_metadata.get("chain_digest", "") or "").strip().lower(),
                    "previous_digest": str(row_metadata.get("previous_digest", "") or "").strip().lower(),
                    "snapshot_version": int(row_metadata.get("snapshot_version", 1) or 1),
                }
                if referenced_head["event_type"] != "pending.reconcile.compliance_readiness_policy_snapshot":
                    issues.append("referenced_head_wrong_event_type")
                if head_digest_sha256 and referenced_head["digest_sha256"] != head_digest_sha256:
                    issues.append("referenced_head_digest_mismatch")
                if row_policy and referenced_head["policy_name"] and row_policy != referenced_head["policy_name"]:
                    issues.append("referenced_head_policy_mismatch")

        signature_verification = {
            "available": False,
            "verified": False,
            "match": False,
            "reason": "payload_unavailable",
            "computed_checkpoint_digest": "",
            "computed_signature": "",
        }
        if payload:
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            computed_checkpoint_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            signature_verification["available"] = True
            signature_verification["verified"] = True
            signature_verification["computed_checkpoint_digest"] = computed_checkpoint_digest

            checkpoint_digest = str(metadata.get("checkpoint_digest", "") or "").strip().lower()
            if checkpoint_digest and checkpoint_digest != computed_checkpoint_digest:
                issues.append("checkpoint_digest_mismatch")

            payload_head = dict(payload.get("head") or {})
            payload_head_event_id = int(payload_head.get("event_id", 0) or 0)
            payload_head_digest = str(payload_head.get("digest_sha256", "") or "").strip().lower()
            if payload_head_event_id and payload_head_event_id != head_event_id:
                issues.append("payload_head_event_mismatch")
            if payload_head_digest and payload_head_digest != head_digest_sha256:
                issues.append("payload_head_digest_mismatch")

            if signature_type == "hmac_sha256":
                secret, _, _ = _resolve_signing_secret(requested_key_id=key_id)
                if not secret:
                    warnings.append("signing_secret_unavailable_for_checkpoint")
                    signature_verification["verified"] = False
                    signature_verification["reason"] = "signing_secret_unavailable"
                else:
                    computed_signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
                    signature_verification["computed_signature"] = computed_signature
                    signature_verification["match"] = bool(signature and signature == computed_signature)
                    signature_verification["reason"] = "verified"
                    if signature and signature != computed_signature:
                        issues.append("checkpoint_signature_mismatch")
            elif signature_type == "sha256":
                computed_signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                signature_verification["computed_signature"] = computed_signature
                signature_verification["match"] = bool(signature and signature == computed_signature)
                signature_verification["reason"] = "verified"
                if signature and signature != computed_signature:
                    issues.append("checkpoint_signature_mismatch")
            else:
                issues.append("unsupported_signature_type")
                signature_verification["reason"] = "unsupported_signature_type"
        else:
            warnings.append("checkpoint_payload_unavailable")
            if bool(require_signature_payload):
                issues.append("checkpoint_payload_unavailable")

        if issues:
            row_status = "broken"
            broken_count += 1
            issue_rows.append({"event_id": event_id, "issues": issues})
        elif warnings:
            row_status = "stale"
            stale_count += 1
        else:
            row_status = "ok"
            ok_count += 1

        entries.append(
            {
                "event_id": event_id,
                "created_at": created_at,
                "policy_name": row_policy,
                "label": str(metadata.get("label", "") or ""),
                "status": row_status,
                "issues": issues,
                "warnings": warnings,
                "head_event_id": head_event_id,
                "head_digest_sha256": head_digest_sha256,
                "signature_verification": signature_verification,
                "referenced_head": referenced_head,
            }
        )

    return {
        "success": True,
        "count": len(entries),
        "ok": int(ok_count),
        "broken": int(broken_count),
        "stale": int(stale_count),
        "status": ("ok" if broken_count == 0 else "broken"),
        "policy_name": normalized_policy,
        "issues": issue_rows[:50],
        "rows": entries,
    }


def prune_reconcile_compliance_readiness_evaluation_artifacts(
    max_age_days: int = 30,
    dry_run: bool = True,
    policy_name: str = "",
    keep_latest: int | None = None,
    now: datetime | None = None,
) -> dict:
    """Delete old readiness evaluation artifact events with optional policy scope and keep-latest retention."""
    age_days = max(1, int(max_age_days))
    normalized_policy = str(policy_name or "").strip().lower()
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is not None:
        current = current.astimezone(timezone.utc).replace(tzinfo=None)
    cutoff = current - timedelta(days=age_days)
    cutoff_sql = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    with tournament_db.get_tournament_connection() as conn:
        scanned = int(
            conn.execute(
                "SELECT COUNT(1) AS c FROM tournament_events WHERE event_type = ?",
                ("pending.reconcile.compliance_readiness_evaluation_artifact",),
            ).fetchone()["c"]
            or 0
        )
        candidate_rows = conn.execute(
            """
            SELECT event_id, metadata_json
            FROM tournament_events
            WHERE event_type = ?
              AND created_at < ?
            ORDER BY event_id ASC
            """,
            ("pending.reconcile.compliance_readiness_evaluation_artifact", cutoff_sql),
        ).fetchall()

        filtered_ids: list[int] = []
        for row in candidate_rows:
            metadata = _loads_json(str(row["metadata_json"] or "{}"), {})
            row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
            if normalized_policy and row_policy != normalized_policy:
                continue
            filtered_ids.append(int(row["event_id"]))

        keep_latest_ids: set[int] = set()
        keep_latest_int = None
        if keep_latest is not None:
            try:
                keep_latest_int = max(0, int(keep_latest))
            except Exception:
                keep_latest_int = 0
        if keep_latest_int and keep_latest_int > 0:
            recent_rows = conn.execute(
                """
                SELECT event_id, metadata_json
                FROM tournament_events
                WHERE event_type = ?
                ORDER BY event_id DESC
                LIMIT ?
                """,
                ("pending.reconcile.compliance_readiness_evaluation_artifact", int(max(keep_latest_int * 5, keep_latest_int))),
            ).fetchall()
            kept = 0
            for row in recent_rows:
                metadata = _loads_json(str(row["metadata_json"] or "{}"), {})
                row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
                if normalized_policy and row_policy != normalized_policy:
                    continue
                keep_latest_ids.add(int(row["event_id"]))
                kept += 1
                if kept >= int(keep_latest_int):
                    break

        candidate_ids = [eid for eid in filtered_ids if eid not in keep_latest_ids]
        kept_count = len(filtered_ids) - len(candidate_ids)
        deleted = 0
        if not dry_run and candidate_ids:
            conn.executemany(
                "DELETE FROM tournament_events WHERE event_id = ?",
                [(eid,) for eid in candidate_ids],
            )
            conn.commit()
            deleted = len(candidate_ids)

    summary: dict[str, Any] = {
        "success": True,
        "dry_run": bool(dry_run),
        "policy_name": normalized_policy,
        "max_age_days": age_days,
        "cutoff": cutoff_sql,
        "scanned": scanned,
        "keep_latest": (None if keep_latest is None else max(0, int(keep_latest))),
        "candidates": len(candidate_ids),
        "kept": kept_count,
        "deleted": deleted,
    }
    log_event(
        "pending.reconcile.compliance_readiness_evaluation_artifacts_pruned",
        (
            "Readiness evaluation artifact prune summary: "
            f"policy={normalized_policy or 'all'} dry_run={bool(dry_run)} "
            f"candidates={len(candidate_ids)} deleted={deleted}"
        ),
        severity="info",
        metadata=summary,
    )
    return summary


def create_reconcile_compliance_readiness_evaluation_artifact_checkpoint(
    policy_name: str = "default",
    label: str = "",
    note: str = "",
    expected_previous_digest: str = "",
    require_head: bool = True,
    signing_key: str = "",
) -> dict:
    """Create a signed checkpoint anchored to the latest readiness evaluation artifact head."""
    normalized_policy = str(policy_name or "default").strip().lower() or "default"
    head = get_latest_reconcile_compliance_readiness_evaluation_artifact_head(policy_name=normalized_policy)
    if not head.get("success", False):
        if bool(require_head):
            return {
                "success": False,
                "error": str(head.get("error", "No readiness evaluation artifact head available")),
                "head": head,
            }
        head = {
            "success": True,
            "event_id": 0,
            "created_at": "",
            "policy_name": normalized_policy,
            "status": "",
            "score": 0,
            "policy_digest_sha256": "",
            "policy_snapshot_digest_sha256": "",
            "compliance_artifact_digest_sha256": "",
            "digest_sha256": "",
            "chain_digest": "",
            "previous_digest": "",
            "chain_source": "none",
            "artifact_version": 1,
        }

    expected = str(expected_previous_digest or "").strip().lower()
    current_digest = str(head.get("digest_sha256", "") or "").strip().lower()
    if expected and expected != current_digest:
        return {
            "success": False,
            "error": "expected_previous_digest does not match current readiness evaluation artifact head",
            "expected_previous_digest": expected,
            "head_digest_sha256": current_digest,
            "policy_name": normalized_policy,
        }

    key_id = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "") or "").strip()
    signature_version = int(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "1") or 1)
    payload = {
        "checkpoint_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": str(label or "").strip(),
        "note": str(note or "").strip(),
        "policy_name": normalized_policy,
        "head": {
            "event_id": int(head.get("event_id", 0) or 0),
            "created_at": str(head.get("created_at", "") or ""),
            "policy_name": str(head.get("policy_name", normalized_policy) or normalized_policy).strip().lower(),
            "status": str(head.get("status", "") or ""),
            "score": int(head.get("score", 0) or 0),
            "policy_digest_sha256": str(head.get("policy_digest_sha256", "") or "").strip().lower(),
            "policy_snapshot_digest_sha256": str(head.get("policy_snapshot_digest_sha256", "") or "").strip().lower(),
            "compliance_artifact_digest_sha256": str(head.get("compliance_artifact_digest_sha256", "") or "").strip().lower(),
            "digest_sha256": current_digest,
            "chain_digest": str(head.get("chain_digest", "") or "").strip().lower(),
            "previous_digest": str(head.get("previous_digest", "") or "").strip().lower(),
            "chain_source": str(head.get("chain_source", "none") or "none"),
            "artifact_version": int(head.get("artifact_version", 1) or 1),
        },
        "signature_metadata": {
            "key_id": key_id,
            "signature_version": signature_version,
        },
    }

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    secret, resolved_key_id, key_source = _resolve_signing_secret(
        requested_key_id=key_id,
        explicit_signing_key=str(signing_key or "").strip(),
    )
    if resolved_key_id and not key_id:
        key_id = resolved_key_id
        payload["signature_metadata"]["key_id"] = key_id

    if secret:
        signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_type = "hmac_sha256"
        signed = True
    else:
        signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        signature_type = "sha256"
        signed = False

    checkpoint_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    event_id = log_event(
        "pending.reconcile.compliance_readiness_evaluation_artifact_checkpoint",
        f"Readiness evaluation artifact checkpoint created for policy={normalized_policy}",
        severity="info",
        metadata={
            "policy_name": normalized_policy,
            "checkpoint_digest": checkpoint_digest,
            "signature": signature,
            "signature_type": signature_type,
            "signed": bool(signed),
            "key_id": key_id,
            "key_source": key_source,
            "signature_version": signature_version,
            "head_event_id": int(head.get("event_id", 0) or 0),
            "head_digest_sha256": current_digest,
            "label": str(label or "").strip(),
            "payload": payload,
        },
    )

    return {
        "success": True,
        "event_id": int(event_id),
        "policy_name": normalized_policy,
        "checkpoint_digest": checkpoint_digest,
        "signature": signature,
        "signature_type": signature_type,
        "signed": bool(signed),
        "key_id": key_id,
        "key_source": key_source,
        "signature_version": signature_version,
        "payload": payload,
    }


def get_latest_reconcile_compliance_readiness_evaluation_artifact_checkpoint(policy_name: str = "") -> dict:
    """Return metadata for the most recent readiness evaluation artifact checkpoint event."""
    rows = list_events(event_type="pending.reconcile.compliance_readiness_evaluation_artifact_checkpoint", limit=200)
    normalized_policy = str(policy_name or "").strip().lower()
    for row in rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        return {
            "success": True,
            "event_id": int(row.get("event_id", 0) or 0),
            "created_at": str(row.get("created_at", "") or ""),
            "policy_name": row_policy,
            "checkpoint_digest": str(metadata.get("checkpoint_digest", "") or ""),
            "signature": str(metadata.get("signature", "") or ""),
            "signature_type": str(metadata.get("signature_type", "") or ""),
            "signed": bool(metadata.get("signed", False)),
            "key_id": str(metadata.get("key_id", "") or ""),
            "key_source": str(metadata.get("key_source", "") or ""),
            "signature_version": int(metadata.get("signature_version", 1) or 1),
            "head_event_id": int(metadata.get("head_event_id", 0) or 0),
            "head_digest_sha256": str(metadata.get("head_digest_sha256", "") or ""),
            "label": str(metadata.get("label", "") or ""),
            "payload": dict(metadata.get("payload") or {}),
        }

    return {
        "success": False,
        "error": (
            "No readiness evaluation artifact checkpoint found"
            if not normalized_policy
            else f"No readiness evaluation artifact checkpoint found for policy {normalized_policy}"
        ),
    }


def verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint(
    policy_name: str = "",
    require_current_head: bool = False,
    require_signature_payload: bool = False,
) -> dict:
    """Verify latest readiness evaluation artifact checkpoint against referenced artifact head."""
    normalized_policy = str(policy_name or "").strip().lower()
    checkpoint = get_latest_reconcile_compliance_readiness_evaluation_artifact_checkpoint(policy_name=normalized_policy)
    if not checkpoint.get("success", False):
        return {
            "success": True,
            "status": "empty",
            "issues": [],
            "policy_name": normalized_policy,
            "error": str(checkpoint.get("error", "No checkpoint available")),
        }

    issues: list[str] = []
    payload = dict(checkpoint.get("payload") or {})
    head_in_checkpoint = dict(payload.get("head") or {})
    checkpoint_head_digest = str(head_in_checkpoint.get("digest_sha256", "") or "").strip().lower()
    checkpoint_digest = str(checkpoint.get("checkpoint_digest", "") or "").strip().lower()

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    recomputed_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if recomputed_digest != checkpoint_digest:
        issues.append("checkpoint_digest_mismatch")

    if bool(require_signature_payload) or checkpoint.get("signed", False):
        stored_sig = str(checkpoint.get("signature", "") or "").strip().lower()
        sig_type = str(checkpoint.get("signature_type", "sha256") or "sha256").strip().lower()
        if sig_type == "hmac_sha256":
            secret, _, _ = _resolve_signing_secret(
                requested_key_id=str(checkpoint.get("key_id", "") or ""),
            )
            if secret:
                expected_sig = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
                if expected_sig != stored_sig:
                    issues.append("checkpoint_signature_mismatch")
            elif bool(require_signature_payload):
                issues.append("checkpoint_signature_key_unavailable")

    current_head = get_latest_reconcile_compliance_readiness_evaluation_artifact_head(policy_name=normalized_policy)
    current_head_digest = str(current_head.get("digest_sha256", "") or "").strip().lower()
    is_current = current_head_digest == checkpoint_head_digest and bool(current_head.get("success", False))

    if bool(require_current_head) and not is_current:
        issues.append("checkpoint_not_current_head")

    status = "ok" if not issues else ("stale" if issues == ["checkpoint_not_current_head"] else "broken")

    return {
        "success": True,
        "status": status,
        "policy_name": normalized_policy,
        "issues": issues,
        "checkpoint_event_id": int(checkpoint.get("event_id", 0) or 0),
        "checkpoint_digest": checkpoint_digest,
        "checkpoint_signed": bool(checkpoint.get("signed", False)),
        "checkpoint_head_digest": checkpoint_head_digest,
        "current_head_digest": current_head_digest,
        "is_current": bool(is_current),
    }


def verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint_history(
    limit: int = 200,
    policy_name: str = "",
    require_signature_payload: bool = False,
) -> dict:
    """Verify integrity of recent readiness evaluation artifact checkpoint events."""
    rows = list_events(
        event_type="pending.reconcile.compliance_readiness_evaluation_artifact_checkpoint",
        limit=max(1, min(1000, int(limit))),
    )
    normalized_policy = str(policy_name or "").strip().lower()
    entries: list[dict[str, Any]] = []
    ok_count = 0
    broken_count = 0
    stale_count = 0
    issue_rows: list[dict[str, Any]] = []

    for row in rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        event_id = int(row.get("event_id", 0) or 0)
        created_at = str(row.get("created_at", "") or "")
        row_status = "ok"
        issues: list[str] = []

        payload = dict(metadata.get("payload") or {})
        checkpoint_digest = str(metadata.get("checkpoint_digest", "") or "").strip().lower()
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        recomputed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if recomputed != checkpoint_digest:
            issues.append("checkpoint_digest_mismatch")

        if bool(require_signature_payload) or bool(metadata.get("signed", False)):
            stored_sig = str(metadata.get("signature", "") or "").strip().lower()
            sig_type = str(metadata.get("signature_type", "sha256") or "sha256").strip().lower()
            if sig_type == "hmac_sha256":
                secret, _, _ = _resolve_signing_secret(
                    requested_key_id=str(metadata.get("key_id", "") or ""),
                )
                if secret:
                    expected_sig = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
                    if expected_sig != stored_sig:
                        issues.append("checkpoint_signature_mismatch")
                elif bool(require_signature_payload):
                    issues.append("checkpoint_signature_key_unavailable")

        if issues:
            row_status = "broken"
            broken_count += 1
            issue_rows.append({"event_id": event_id, "issues": issues})
        else:
            ok_count += 1

        head_event_id = int(metadata.get("head_event_id", 0) or 0)
        head_digest_sha256 = str(metadata.get("head_digest_sha256", "") or "")

        entries.append(
            {
                "event_id": event_id,
                "created_at": created_at,
                "policy_name": row_policy,
                "label": str(metadata.get("label", "") or ""),
                "status": row_status,
                "issues": issues,
                "head_event_id": head_event_id,
                "head_digest_sha256": head_digest_sha256,
            }
        )

    return {
        "success": True,
        "count": len(entries),
        "ok": int(ok_count),
        "broken": int(broken_count),
        "status": ("ok" if broken_count == 0 else "broken"),
        "policy_name": normalized_policy,
        "issues": issue_rows[:50],
        "rows": entries,
    }


def export_reconcile_compliance_readiness_evaluation_artifact_envelope(
    policy_name: str = "default",
    chain_limit: int | None = None,
    warning_threshold: int | None = None,
    error_threshold: int | None = None,
    include_json: bool = False,
    include_snapshot: bool = True,
    persist_readiness_event: bool = False,
    previous_digest: str = "",
    auto_chain: bool = True,
    persist_event: bool = True,
    create_checkpoint: bool = True,
    checkpoint_label: str = "ops_envelope",
    checkpoint_note: str = "",
    require_current_head: bool = False,
    require_signature_payload: bool = True,
    signing_key: str = "",
) -> dict:
    """Export readiness evaluation artifact + checkpoint verification envelope for external interchange."""
    artifact = export_reconcile_compliance_readiness_evaluation_artifact(
        policy_name=str(policy_name or "default"),
        chain_limit=chain_limit,
        warning_threshold=warning_threshold,
        error_threshold=error_threshold,
        include_json=bool(include_json),
        include_snapshot=bool(include_snapshot),
        persist_readiness_event=bool(persist_readiness_event),
        previous_digest=str(previous_digest or ""),
        auto_chain=bool(auto_chain),
        persist_event=bool(persist_event),
    )
    policy_resolved = str(artifact.get("policy_name", "default") or "default")

    checkpoint: dict[str, Any] = {
        "success": False,
        "skipped": True,
        "reason": "create_checkpoint_disabled",
    }
    if bool(create_checkpoint):
        checkpoint = create_reconcile_compliance_readiness_evaluation_artifact_checkpoint(
            policy_name=policy_resolved,
            label=str(checkpoint_label or "ops_envelope").strip() or "ops_envelope",
            note=str(checkpoint_note or ""),
            expected_previous_digest=str(artifact.get("digest_sha256", "") or "").strip().lower(),
            require_head=bool(persist_event),
            signing_key=str(signing_key or ""),
        )

    verification = verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint(
        policy_name=policy_resolved,
        require_current_head=bool(require_current_head),
        require_signature_payload=bool(require_signature_payload),
    )

    key_id = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "") or "").strip()
    signature_version = int(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "1") or 1)
    envelope_payload = {
        "envelope_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy_name": policy_resolved,
        "artifact": artifact,
        "checkpoint": checkpoint,
        "verification": verification,
        "signature_metadata": {
            "key_id": key_id,
            "signature_version": signature_version,
        },
    }
    canonical = json.dumps(envelope_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    envelope_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    secret, resolved_key_id, key_source = _resolve_signing_secret(
        requested_key_id=key_id,
        explicit_signing_key=str(signing_key or "").strip(),
    )
    if resolved_key_id and not key_id:
        key_id = resolved_key_id
        envelope_payload["signature_metadata"]["key_id"] = key_id

    if secret:
        signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_type = "hmac_sha256"
        signed = True
    else:
        signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        signature_type = "sha256"
        signed = False

    return {
        "success": bool(artifact.get("success", False)),
        "match": str(verification.get("status", "") or "").lower() == "ok",
        "signed": bool(signed),
        "signature_type": signature_type,
        "key_id": key_id,
        "key_source": key_source,
        "signature_version": signature_version,
        "signature": signature,
        "policy_name": policy_resolved,
        "envelope_digest": envelope_digest,
        "envelope": envelope_payload,
        "verify_payload": {
            "artifact_digest_sha256": str(artifact.get("digest_sha256", "") or ""),
            "artifact_policy_name": policy_resolved,
            "artifact_status": str(artifact.get("status", "") or ""),
            "artifact_score": int(artifact.get("score", 0) or 0),
            "checkpoint_event_id": int(checkpoint.get("event_id", 0) or 0),
            "checkpoint_digest": str(checkpoint.get("checkpoint_digest", "") or ""),
            "verification_status": str(verification.get("status", "") or ""),
            "signature": signature,
            "signature_type": signature_type,
            "key_id": key_id,
            "signature_version": signature_version,
        },
    }


def get_latest_reconcile_compliance_readiness_evaluation_artifact_head(policy_name: str = "") -> dict:
    """Return metadata for the most recent readiness evaluation artifact."""
    rows = list_events(event_type="pending.reconcile.compliance_readiness_evaluation_artifact", limit=200)
    normalized_policy = str(policy_name or "").strip().lower()
    for row in rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        return {
            "success": True,
            "event_id": int(row.get("event_id", 0) or 0),
            "created_at": str(row.get("created_at", "") or ""),
            "policy_name": row_policy,
            "status": str(metadata.get("status", "") or ""),
            "score": int(metadata.get("score", 0) or 0),
            "policy_digest_sha256": str(metadata.get("policy_digest_sha256", "") or ""),
            "policy_snapshot_digest_sha256": str(metadata.get("policy_snapshot_digest_sha256", "") or ""),
            "compliance_artifact_digest_sha256": str(metadata.get("compliance_artifact_digest_sha256", "") or ""),
            "digest_sha256": str(metadata.get("digest_sha256", "") or ""),
            "chain_digest": str(metadata.get("chain_digest", "") or ""),
            "previous_digest": str(metadata.get("previous_digest", "") or ""),
            "chain_source": str(metadata.get("chain_source", "none") or "none"),
            "artifact_version": int(metadata.get("artifact_version", 1) or 1),
        }

    return {
        "success": False,
        "error": (
            "No readiness evaluation artifact found"
            if not normalized_policy
            else f"No readiness evaluation artifact found for policy {normalized_policy}"
        ),
    }


def verify_reconcile_compliance_readiness_evaluation_artifact_chain(limit: int = 200, policy_name: str = "") -> dict:
    """Verify linkage and chain digests across readiness evaluation artifacts."""
    rows = list_events(
        event_type="pending.reconcile.compliance_readiness_evaluation_artifact",
        limit=max(1, min(1000, int(limit))),
    )
    normalized_policy = str(policy_name or "").strip().lower()
    ordered_rows = list(reversed(rows))
    filtered: list[dict[str, Any]] = []
    for row in ordered_rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        filtered.append(row)

    if not filtered:
        return {
            "success": True,
            "count": 0,
            "valid_links": 0,
            "broken_links": 0,
            "status": "empty",
            "policy_name": normalized_policy,
            "issues": [],
        }

    issues: list[dict[str, Any]] = []
    valid_links = 0
    previous_digest = ""
    for event in filtered:
        metadata = dict(event.get("metadata") or {})
        event_id = int(event.get("event_id", 0) or 0)
        digest = str(metadata.get("digest_sha256", "") or "").strip().lower()
        declared_previous = str(metadata.get("previous_digest", "") or "").strip().lower()
        declared_chain = str(metadata.get("chain_digest", "") or "").strip().lower()

        expected_previous = previous_digest
        expected_chain_input = f"{declared_previous}:{digest}" if declared_previous else digest
        expected_chain = hashlib.sha256(expected_chain_input.encode("utf-8")).hexdigest() if digest else ""

        event_issues = []
        if not digest:
            event_issues.append("missing_digest")
        if declared_previous != expected_previous:
            event_issues.append("previous_digest_mismatch")
        if declared_chain != expected_chain:
            event_issues.append("chain_digest_mismatch")

        if event_issues:
            issues.append(
                {
                    "event_id": event_id,
                    "issues": event_issues,
                    "declared_previous": declared_previous,
                    "expected_previous": expected_previous,
                    "declared_chain": declared_chain,
                    "expected_chain": expected_chain,
                    "digest_sha256": digest,
                }
            )
        else:
            valid_links += 1

        previous_digest = digest

    return {
        "success": True,
        "count": len(filtered),
        "valid_links": int(valid_links),
        "broken_links": int(len(issues)),
        "status": ("ok" if not issues else "broken"),
        "policy_name": normalized_policy,
        "head_event_id": int(filtered[-1].get("event_id", 0) or 0),
        "head_digest_sha256": str((filtered[-1].get("metadata") or {}).get("digest_sha256", "") or ""),
        "issues": issues[:50],
    }


def export_reconcile_composite_governance_snapshot(
    policy_name: str = "default",
    chain_limit: int | None = None,
    warning_threshold: int | None = None,
    error_threshold: int | None = None,
    include_json: bool = False,
    include_snapshot: bool = False,
    previous_digest: str = "",
    auto_chain: bool = True,
    persist_event: bool = True,
    signing_key: str = "",
) -> dict:
    """Export a composite governance snapshot pinning all four chain heads into a single signed record."""
    normalized_policy = str(policy_name or "default").strip().lower() or "default"

    sig_receipts_head = get_latest_reconcile_signature_receipts_artifact_head()
    compliance_head = get_latest_reconcile_compliance_status_artifact_head()
    readiness_snapshot_head = get_latest_reconcile_compliance_readiness_policy_snapshot_head(policy_name=normalized_policy)
    readiness_artifact_head = get_latest_reconcile_compliance_readiness_evaluation_artifact_head(policy_name=normalized_policy)

    snapshot_payload: dict[str, Any] = {
        "snapshot_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy_name": normalized_policy,
        "heads": {
            "signature_receipts_artifact": {
                "success": bool(sig_receipts_head.get("success", False)),
                "event_id": int(sig_receipts_head.get("event_id", 0) or 0),
                "digest_sha256": str(sig_receipts_head.get("digest_sha256", "") or ""),
                "chain_digest": str(sig_receipts_head.get("chain_digest", "") or ""),
            },
            "compliance_status_artifact": {
                "success": bool(compliance_head.get("success", False)),
                "event_id": int(compliance_head.get("event_id", 0) or 0),
                "digest_sha256": str(compliance_head.get("digest_sha256", "") or ""),
                "chain_digest": str(compliance_head.get("chain_digest", "") or ""),
            },
            "readiness_policy_snapshot": {
                "success": bool(readiness_snapshot_head.get("success", False)),
                "event_id": int(readiness_snapshot_head.get("event_id", 0) or 0),
                "digest_sha256": str(readiness_snapshot_head.get("digest_sha256", "") or ""),
                "chain_digest": str(readiness_snapshot_head.get("chain_digest", "") or ""),
                "policy_name": str(readiness_snapshot_head.get("policy_name", normalized_policy) or normalized_policy),
            },
            "readiness_evaluation_artifact": {
                "success": bool(readiness_artifact_head.get("success", False)),
                "event_id": int(readiness_artifact_head.get("event_id", 0) or 0),
                "digest_sha256": str(readiness_artifact_head.get("digest_sha256", "") or ""),
                "chain_digest": str(readiness_artifact_head.get("chain_digest", "") or ""),
                "status": str(readiness_artifact_head.get("status", "") or ""),
                "score": int(readiness_artifact_head.get("score", 0) or 0),
                "policy_name": str(readiness_artifact_head.get("policy_name", normalized_policy) or normalized_policy),
            },
        },
    }

    canonical = json.dumps(snapshot_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    snapshot_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    resolved_previous = str(previous_digest or "").strip().lower()
    chain_source = "provided" if resolved_previous else "none"
    if not resolved_previous and bool(auto_chain):
        latest_head = get_latest_reconcile_composite_governance_snapshot_head(policy_name=normalized_policy)
        if latest_head.get("success"):
            resolved_previous = str(latest_head.get("digest_sha256", "") or "").strip().lower()
            chain_source = "latest_event"

    chain_input = f"{resolved_previous}:{snapshot_digest}" if resolved_previous else snapshot_digest
    chain_digest = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()

    key_id = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "") or "").strip()
    signature_version = int(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "1") or 1)
    sign_payload = {
        "digest_sha256": snapshot_digest,
        "chain_digest": chain_digest,
        "previous_digest": resolved_previous,
        "policy_name": normalized_policy,
        "generated_at": str(snapshot_payload["generated_at"]),
        "signature_metadata": {"key_id": key_id, "signature_version": signature_version},
    }
    sign_canonical = json.dumps(sign_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    secret, resolved_key_id, key_source = _resolve_signing_secret(
        requested_key_id=key_id,
        explicit_signing_key=str(signing_key or "").strip(),
    )
    if resolved_key_id and not key_id:
        key_id = resolved_key_id
        sign_payload["signature_metadata"]["key_id"] = key_id

    if secret:
        signature = hmac.new(secret.encode("utf-8"), sign_canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_type = "hmac_sha256"
        signed = True
    else:
        signature = hashlib.sha256(sign_canonical.encode("utf-8")).hexdigest()
        signature_type = "sha256"
        signed = False

    result: dict[str, Any] = {
        "success": True,
        "snapshot_version": 1,
        "policy_name": normalized_policy,
        "digest_sha256": snapshot_digest,
        "previous_digest": resolved_previous,
        "chain_source": chain_source,
        "chain_digest": chain_digest,
        "signature": signature,
        "signature_type": signature_type,
        "signed": bool(signed),
        "key_id": key_id,
        "key_source": key_source,
        "signature_version": signature_version,
        "heads": dict(snapshot_payload["heads"]),
        "snapshot": (snapshot_payload if bool(include_snapshot) else {}),
        "json": (canonical if bool(include_json) else ""),
    }

    if bool(persist_event):
        event_id = log_event(
            "pending.reconcile.composite_governance_snapshot",
            f"Composite governance snapshot exported: policy={normalized_policy}",
            severity="info",
            metadata={
                "snapshot_version": 1,
                "policy_name": normalized_policy,
                "digest_sha256": snapshot_digest,
                "previous_digest": resolved_previous,
                "chain_source": chain_source,
                "chain_digest": chain_digest,
                "signature": signature,
                "signature_type": signature_type,
                "signed": bool(signed),
                "key_id": key_id,
                "key_source": key_source,
                "signature_version": signature_version,
                "heads": dict(snapshot_payload["heads"]),
                "include_json": bool(include_json),
                "include_snapshot": bool(include_snapshot),
            },
        )
        result["snapshot_event_id"] = int(event_id)

    return result


def get_latest_reconcile_composite_governance_snapshot_head(policy_name: str = "") -> dict:
    """Return metadata for the most recent composite governance snapshot."""
    rows = list_events(event_type="pending.reconcile.composite_governance_snapshot", limit=200)
    normalized_policy = str(policy_name or "").strip().lower()
    for row in rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        return {
            "success": True,
            "event_id": int(row.get("event_id", 0) or 0),
            "created_at": str(row.get("created_at", "") or ""),
            "policy_name": row_policy,
            "digest_sha256": str(metadata.get("digest_sha256", "") or ""),
            "chain_digest": str(metadata.get("chain_digest", "") or ""),
            "previous_digest": str(metadata.get("previous_digest", "") or ""),
            "chain_source": str(metadata.get("chain_source", "none") or "none"),
            "snapshot_version": int(metadata.get("snapshot_version", 1) or 1),
            "signed": bool(metadata.get("signed", False)),
            "signature_type": str(metadata.get("signature_type", "") or ""),
            "key_id": str(metadata.get("key_id", "") or ""),
            "signature_version": int(metadata.get("signature_version", 1) or 1),
            "heads": dict(metadata.get("heads") or {}),
        }
    return {
        "success": False,
        "error": (
            "No composite governance snapshot found"
            if not normalized_policy
            else f"No composite governance snapshot found for policy {normalized_policy}"
        ),
    }


def verify_reconcile_composite_governance_snapshot_chain(limit: int = 200, policy_name: str = "") -> dict:
    """Verify linkage and chain digests across composite governance snapshots."""
    rows = list_events(
        event_type="pending.reconcile.composite_governance_snapshot",
        limit=max(1, min(1000, int(limit))),
    )
    normalized_policy = str(policy_name or "").strip().lower()
    ordered_rows = list(reversed(rows))
    filtered: list[dict[str, Any]] = []
    for row in ordered_rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        filtered.append(row)

    if not filtered:
        return {"success": True, "status": "empty", "checked": 0, "ok": 0, "issues": []}

    issues: list[str] = []
    prev_digest = ""
    for row in filtered:
        metadata = dict(row.get("metadata") or {})
        event_id = int(row.get("event_id", 0) or 0)
        digest = str(metadata.get("digest_sha256", "") or "").strip().lower()
        chain_digest = str(metadata.get("chain_digest", "") or "").strip().lower()
        previous_digest = str(metadata.get("previous_digest", "") or "").strip().lower()
        chain_source = str(metadata.get("chain_source", "none") or "none")

        if chain_source in {"latest_event", "provided"} and prev_digest:
            if previous_digest != prev_digest:
                issues.append(f"event_id={event_id}: previous_digest mismatch (expected={prev_digest[:16]} got={previous_digest[:16]})")
        chain_input = f"{previous_digest}:{digest}" if previous_digest else digest
        expected_chain = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()
        if chain_digest != expected_chain:
            issues.append(f"event_id={event_id}: chain_digest mismatch")
        prev_digest = digest

    status = "ok" if not issues else "broken"
    return {
        "success": True,
        "status": status,
        "checked": len(filtered),
        "ok": len(filtered) - len(issues),
        "issues": issues[:50],
        "head_event_id": int(filtered[-1].get("event_id", 0) or 0),
        "head_digest_sha256": str((filtered[-1].get("metadata") or {}).get("digest_sha256", "") or ""),
    }


def prune_reconcile_composite_governance_snapshots(
    max_age_days: int = 30,
    dry_run: bool = True,
    policy_name: str = "",
    keep_latest: int | None = None,
    now: datetime | None = None,
) -> dict:
    """Prune stale composite governance snapshot events. Respects keep_latest retention."""
    rows = list_events(event_type="pending.reconcile.composite_governance_snapshot", limit=5000)
    normalized_policy = str(policy_name or "").strip().lower()
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=max(1, int(max_age_days)))

    policy_rows: list[dict[str, Any]] = []
    for row in rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        policy_rows.append(row)

    policy_rows_sorted = sorted(policy_rows, key=lambda r: int(r.get("event_id", 0) or 0))
    keep_set: set[int] = set()
    if keep_latest is not None and int(keep_latest) > 0:
        for row in policy_rows_sorted[-int(keep_latest):]:
            keep_set.add(int(row.get("event_id", 0) or 0))

    candidates: list[int] = []
    for row in policy_rows_sorted:
        event_id = int(row.get("event_id", 0) or 0)
        if event_id in keep_set:
            continue
        created_at_str = str(row.get("created_at", "") or "")
        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if created_at < cutoff:
            candidates.append(event_id)

    deleted = 0
    if not bool(dry_run) and candidates:
        with get_tournament_connection() as conn:
            for eid in candidates:
                conn.execute("DELETE FROM tournament_events WHERE event_id = ?", (eid,))
            conn.commit()
        deleted = len(candidates)

    log_event(
        "pending.reconcile.composite_governance_snapshots_pruned",
        f"Composite governance snapshot prune: policy={normalized_policy or 'all'} candidates={len(candidates)} deleted={deleted} dry_run={dry_run}",
        severity="info",
        metadata={
            "policy_name": normalized_policy or "all",
            "max_age_days": int(max_age_days),
            "dry_run": bool(dry_run),
            "keep_latest": keep_latest,
            "candidates": len(candidates),
            "deleted": deleted,
            "kept": len(keep_set),
        },
    )
    return {
        "success": True,
        "dry_run": bool(dry_run),
        "policy_name": normalized_policy or "all",
        "candidates": len(candidates),
        "deleted": deleted,
        "kept": len(keep_set),
        "max_age_days": int(max_age_days),
    }


def create_reconcile_composite_governance_snapshot_checkpoint(
    policy_name: str = "default",
    label: str = "",
    note: str = "",
    expected_previous_digest: str = "",
    require_head: bool = True,
    signing_key: str = "",
) -> dict:
    """Create a signed checkpoint anchored to the latest composite governance snapshot head."""
    normalized_policy = str(policy_name or "default").strip().lower() or "default"
    head = get_latest_reconcile_composite_governance_snapshot_head(policy_name=normalized_policy)
    if not head.get("success", False):
        if bool(require_head):
            return {
                "success": False,
                "error": str(head.get("error", "No composite governance snapshot head available")),
                "head": head,
            }
        head = {
            "success": True,
            "event_id": 0,
            "created_at": "",
            "policy_name": normalized_policy,
            "digest_sha256": "",
            "chain_digest": "",
            "previous_digest": "",
            "chain_source": "none",
            "snapshot_version": 1,
        }

    expected = str(expected_previous_digest or "").strip().lower()
    current_digest = str(head.get("digest_sha256", "") or "").strip().lower()
    if expected and expected != current_digest:
        return {
            "success": False,
            "error": "expected_previous_digest does not match current composite governance snapshot head",
            "expected_previous_digest": expected,
            "head_digest_sha256": current_digest,
            "policy_name": normalized_policy,
        }

    key_id = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "") or "").strip()
    signature_version = int(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "1") or 1)
    payload = {
        "checkpoint_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": str(label or "").strip(),
        "note": str(note or "").strip(),
        "policy_name": normalized_policy,
        "head": {
            "event_id": int(head.get("event_id", 0) or 0),
            "created_at": str(head.get("created_at", "") or ""),
            "policy_name": str(head.get("policy_name", normalized_policy) or normalized_policy).strip().lower(),
            "digest_sha256": current_digest,
            "chain_digest": str(head.get("chain_digest", "") or "").strip().lower(),
            "previous_digest": str(head.get("previous_digest", "") or "").strip().lower(),
            "chain_source": str(head.get("chain_source", "none") or "none"),
            "snapshot_version": int(head.get("snapshot_version", 1) or 1),
        },
        "signature_metadata": {
            "key_id": key_id,
            "signature_version": signature_version,
        },
    }

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    secret, resolved_key_id, key_source = _resolve_signing_secret(
        requested_key_id=key_id,
        explicit_signing_key=str(signing_key or "").strip(),
    )
    if resolved_key_id and not key_id:
        key_id = resolved_key_id
        payload["signature_metadata"]["key_id"] = key_id

    if secret:
        signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_type = "hmac_sha256"
        signed = True
    else:
        signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        signature_type = "sha256"
        signed = False

    checkpoint_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    event_id = log_event(
        "pending.reconcile.composite_governance_snapshot_checkpoint",
        f"Composite governance snapshot checkpoint created for policy={normalized_policy}",
        severity="info",
        metadata={
            "policy_name": normalized_policy,
            "checkpoint_digest": checkpoint_digest,
            "signature": signature,
            "signature_type": signature_type,
            "signed": bool(signed),
            "key_id": key_id,
            "key_source": key_source,
            "signature_version": signature_version,
            "head_event_id": int(head.get("event_id", 0) or 0),
            "head_digest_sha256": current_digest,
            "label": str(label or "").strip(),
            "payload": payload,
        },
    )

    return {
        "success": True,
        "event_id": int(event_id),
        "policy_name": normalized_policy,
        "checkpoint_digest": checkpoint_digest,
        "signature": signature,
        "signature_type": signature_type,
        "signed": bool(signed),
        "key_id": key_id,
        "key_source": key_source,
        "signature_version": signature_version,
        "head_event_id": int(head.get("event_id", 0) or 0),
        "head_digest_sha256": current_digest,
        "label": str(label or "").strip(),
    }


def get_latest_reconcile_composite_governance_snapshot_checkpoint(policy_name: str = "") -> dict:
    """Return metadata for the most recent composite governance snapshot checkpoint."""
    rows = list_events(event_type="pending.reconcile.composite_governance_snapshot_checkpoint", limit=200)
    normalized_policy = str(policy_name or "").strip().lower()
    for row in rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        return {
            "success": True,
            "event_id": int(row.get("event_id", 0) or 0),
            "created_at": str(row.get("created_at", "") or ""),
            "policy_name": row_policy,
            "checkpoint_digest": str(metadata.get("checkpoint_digest", "") or ""),
            "head_event_id": int(metadata.get("head_event_id", 0) or 0),
            "head_digest_sha256": str(metadata.get("head_digest_sha256", "") or ""),
            "label": str(metadata.get("label", "") or ""),
            "signed": bool(metadata.get("signed", False)),
            "signature_type": str(metadata.get("signature_type", "") or ""),
            "key_id": str(metadata.get("key_id", "") or ""),
        }
    return {
        "success": False,
        "error": (
            "No composite governance snapshot checkpoint found"
            if not normalized_policy
            else f"No composite governance snapshot checkpoint found for policy {normalized_policy}"
        ),
    }


def verify_reconcile_composite_governance_snapshot_checkpoint(
    policy_name: str = "",
    require_current_head: bool = False,
    require_signature_payload: bool = False,
) -> dict:
    """Verify the latest composite governance snapshot checkpoint against the current head."""
    normalized_policy = str(policy_name or "").strip().lower()
    ckpt = get_latest_reconcile_composite_governance_snapshot_checkpoint(policy_name=normalized_policy)
    if not ckpt.get("success", False):
        return {"success": True, "status": "empty", "error": str(ckpt.get("error", "No checkpoint found")), "policy_name": normalized_policy}

    head = get_latest_reconcile_composite_governance_snapshot_head(policy_name=normalized_policy)
    if not head.get("success", False):
        return {"success": True, "status": "broken", "error": "No governance snapshot head found", "policy_name": normalized_policy, "checkpoint": ckpt}

    ckpt_head_digest = str(ckpt.get("head_digest_sha256", "") or "").strip().lower()
    current_head_digest = str(head.get("digest_sha256", "") or "").strip().lower()

    if bool(require_current_head) and ckpt_head_digest != current_head_digest:
        return {
            "success": True,
            "status": "stale",
            "policy_name": normalized_policy,
            "checkpoint": ckpt,
            "head": head,
            "checkpoint_head_digest": ckpt_head_digest,
            "current_head_digest": current_head_digest,
        }

    status = "ok" if ckpt_head_digest == current_head_digest else "stale"

    if bool(require_signature_payload):
        ckpt_event_rows = list_events(event_type="pending.reconcile.composite_governance_snapshot_checkpoint", limit=200)
        for row in ckpt_event_rows:
            if int(row.get("event_id", 0) or 0) == int(ckpt.get("event_id", 0) or 0):
                meta = dict(row.get("metadata") or {})
                payload = dict(meta.get("payload") or {})
                if not payload:
                    return {"success": True, "status": "broken", "error": "Checkpoint payload missing", "policy_name": normalized_policy, "checkpoint": ckpt}
                canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                recomputed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                stored_digest = str(ckpt.get("checkpoint_digest", "") or "").strip().lower()
                if recomputed != stored_digest:
                    return {"success": True, "status": "broken", "error": "Checkpoint digest recompute mismatch", "policy_name": normalized_policy, "checkpoint": ckpt}
                break

    return {
        "success": True,
        "status": status,
        "policy_name": normalized_policy,
        "checkpoint": ckpt,
        "head": head,
        "checkpoint_head_digest": ckpt_head_digest,
        "current_head_digest": current_head_digest,
    }


def verify_reconcile_composite_governance_snapshot_checkpoint_history(
    limit: int = 200,
    policy_name: str = "",
    require_signature_payload: bool = False,
) -> dict:
    """Verify integrity of recent composite governance snapshot checkpoint events."""
    rows = list_events(event_type="pending.reconcile.composite_governance_snapshot_checkpoint", limit=max(1, min(1000, int(limit))))
    normalized_policy = str(policy_name or "").strip().lower()
    ok = 0
    broken = 0
    stale = 0
    issues: list[str] = []
    for row in rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        event_id = int(row.get("event_id", 0) or 0)
        stored_digest = str(metadata.get("checkpoint_digest", "") or "").strip().lower()
        payload = dict((metadata.get("payload") or {}))
        if bool(require_signature_payload) and not payload:
            broken += 1
            issues.append(f"event_id={event_id}: payload missing")
            continue
        if payload:
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            recomputed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if recomputed != stored_digest:
                broken += 1
                issues.append(f"event_id={event_id}: digest mismatch")
                continue
        ok += 1

    return {
        "success": True,
        "policy_name": normalized_policy or "all",
        "ok": ok,
        "broken": broken,
        "stale": stale,
        "total": ok + broken + stale,
        "issues": issues[:50],
    }


def export_reconcile_composite_governance_snapshot_envelope(
    policy_name: str = "default",
    chain_limit: int | None = None,
    warning_threshold: int | None = None,
    error_threshold: int | None = None,
    include_json: bool = False,
    include_snapshot: bool = False,
    previous_digest: str = "",
    auto_chain: bool = True,
    persist_event: bool = True,
    create_checkpoint: bool = True,
    checkpoint_label: str = "ops_envelope",
    checkpoint_note: str = "",
    require_current_head: bool = False,
    require_signature_payload: bool = True,
    signing_key: str = "",
) -> dict:
    """Export composite governance snapshot plus checkpoint verification envelope for external interchange."""
    artifact = export_reconcile_composite_governance_snapshot(
        policy_name=str(policy_name or "default"),
        chain_limit=chain_limit,
        warning_threshold=warning_threshold,
        error_threshold=error_threshold,
        include_json=bool(include_json),
        include_snapshot=bool(include_snapshot),
        previous_digest=str(previous_digest or ""),
        auto_chain=bool(auto_chain),
        persist_event=bool(persist_event),
        signing_key=str(signing_key or ""),
    )
    policy_resolved = str(artifact.get("policy_name", "default") or "default")

    checkpoint: dict[str, Any] = {
        "success": False,
        "skipped": True,
        "reason": "create_checkpoint_disabled",
    }
    if bool(create_checkpoint):
        checkpoint = create_reconcile_composite_governance_snapshot_checkpoint(
            policy_name=policy_resolved,
            label=str(checkpoint_label or "ops_envelope").strip() or "ops_envelope",
            note=str(checkpoint_note or ""),
            expected_previous_digest=str(artifact.get("digest_sha256", "") or "").strip().lower(),
            require_head=bool(persist_event),
            signing_key=str(signing_key or ""),
        )

    verification = verify_reconcile_composite_governance_snapshot_checkpoint(
        policy_name=policy_resolved,
        require_current_head=bool(require_current_head),
        require_signature_payload=bool(require_signature_payload),
    )

    key_id = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "") or "").strip()
    signature_version = int(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "1") or 1)
    envelope_payload = {
        "envelope_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy_name": policy_resolved,
        "artifact": artifact,
        "checkpoint": checkpoint,
        "verification": verification,
        "signature_metadata": {
            "key_id": key_id,
            "signature_version": signature_version,
        },
    }
    canonical = json.dumps(envelope_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    envelope_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    secret, resolved_key_id, key_source = _resolve_signing_secret(
        requested_key_id=key_id,
        explicit_signing_key=str(signing_key or "").strip(),
    )
    if resolved_key_id and not key_id:
        key_id = resolved_key_id
        envelope_payload["signature_metadata"]["key_id"] = key_id

    if secret:
        signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_type = "hmac_sha256"
        signed = True
    else:
        signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        signature_type = "sha256"
        signed = False

    return {
        "success": bool(artifact.get("success", False)),
        "match": str(verification.get("status", "") or "").lower() == "ok",
        "signed": bool(signed),
        "signature_type": signature_type,
        "key_id": key_id,
        "key_source": key_source,
        "signature_version": signature_version,
        "signature": signature,
        "policy_name": policy_resolved,
        "envelope_digest": envelope_digest,
        "envelope": envelope_payload,
        "verify_payload": {
            "artifact_digest_sha256": str(artifact.get("digest_sha256", "") or ""),
            "artifact_policy_name": policy_resolved,
            "checkpoint_event_id": int(checkpoint.get("event_id", 0) or 0),
            "checkpoint_digest": str(checkpoint.get("checkpoint_digest", "") or ""),
            "verification_status": str(verification.get("status", "") or ""),
            "signature": signature,
            "signature_type": signature_type,
            "key_id": key_id,
            "signature_version": signature_version,
        },
    }


def export_reconcile_governance_attestation_seal(
    policy_name: str = "default",
    chain_limit: int | None = None,
    warning_threshold: int | None = None,
    error_threshold: int | None = None,
    include_json: bool = False,
    include_snapshot: bool = False,
    previous_digest: str = "",
    auto_chain: bool = True,
    persist_event: bool = True,
    signing_key: str = "",
) -> dict:
    """Export top-level governance attestation over current envelope heads."""
    normalized_policy = str(policy_name or "default").strip().lower() or "default"
    resolved_chain_limit = (None if chain_limit is None else max(1, min(1000, int(chain_limit))))

    compliance_envelope = export_reconcile_compliance_status_envelope(
        chain_limit=(200 if resolved_chain_limit is None else int(resolved_chain_limit)),
        include_json=False,
        previous_digest="",
        auto_chain=True,
        persist_event=False,
        create_checkpoint=False,
        checkpoint_label="attestation_probe",
        checkpoint_note="",
        require_current_head=False,
        require_signature_payload=False,
        signing_key=str(signing_key or ""),
    )
    readiness_envelope = export_reconcile_compliance_readiness_evaluation_artifact_envelope(
        policy_name=normalized_policy,
        chain_limit=resolved_chain_limit,
        warning_threshold=warning_threshold,
        error_threshold=error_threshold,
        include_json=False,
        include_snapshot=False,
        persist_readiness_event=False,
        previous_digest="",
        auto_chain=True,
        persist_event=False,
        create_checkpoint=False,
        checkpoint_label="attestation_probe",
        checkpoint_note="",
        require_current_head=False,
        require_signature_payload=False,
        signing_key=str(signing_key or ""),
    )
    composite_envelope = export_reconcile_composite_governance_snapshot_envelope(
        policy_name=normalized_policy,
        chain_limit=resolved_chain_limit,
        warning_threshold=warning_threshold,
        error_threshold=error_threshold,
        include_json=False,
        include_snapshot=False,
        previous_digest="",
        auto_chain=True,
        persist_event=False,
        create_checkpoint=False,
        checkpoint_label="attestation_probe",
        checkpoint_note="",
        require_current_head=False,
        require_signature_payload=False,
        signing_key=str(signing_key or ""),
    )

    envelope_heads = {
        "compliance_status_envelope": {
            "success": bool(compliance_envelope.get("success", False)),
            "match": bool(compliance_envelope.get("match", False)),
            "envelope_digest": str(compliance_envelope.get("envelope_digest", "") or ""),
            "signature": str(compliance_envelope.get("signature", "") or ""),
            "signature_type": str(compliance_envelope.get("signature_type", "") or ""),
        },
        "readiness_evaluation_envelope": {
            "success": bool(readiness_envelope.get("success", False)),
            "match": bool(readiness_envelope.get("match", False)),
            "envelope_digest": str(readiness_envelope.get("envelope_digest", "") or ""),
            "signature": str(readiness_envelope.get("signature", "") or ""),
            "signature_type": str(readiness_envelope.get("signature_type", "") or ""),
            "policy_name": str(readiness_envelope.get("policy_name", normalized_policy) or normalized_policy),
        },
        "composite_governance_envelope": {
            "success": bool(composite_envelope.get("success", False)),
            "match": bool(composite_envelope.get("match", False)),
            "envelope_digest": str(composite_envelope.get("envelope_digest", "") or ""),
            "signature": str(composite_envelope.get("signature", "") or ""),
            "signature_type": str(composite_envelope.get("signature_type", "") or ""),
            "policy_name": str(composite_envelope.get("policy_name", normalized_policy) or normalized_policy),
        },
    }

    payload = {
        "seal_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy_name": normalized_policy,
        "envelope_heads": envelope_heads,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    seal_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    resolved_previous = str(previous_digest or "").strip().lower()
    chain_source = "provided" if resolved_previous else "none"
    if not resolved_previous and bool(auto_chain):
        latest_head = get_latest_reconcile_governance_attestation_seal_head(policy_name=normalized_policy)
        if latest_head.get("success"):
            resolved_previous = str(latest_head.get("digest_sha256", "") or "").strip().lower()
            chain_source = "latest_event"

    chain_input = f"{resolved_previous}:{seal_digest}" if resolved_previous else seal_digest
    chain_digest = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()

    key_id = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "") or "").strip()
    signature_version = int(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "1") or 1)
    sign_payload = {
        "digest_sha256": seal_digest,
        "chain_digest": chain_digest,
        "previous_digest": resolved_previous,
        "policy_name": normalized_policy,
        "generated_at": str(payload.get("generated_at", "") or ""),
        "signature_metadata": {"key_id": key_id, "signature_version": signature_version},
    }
    sign_canonical = json.dumps(sign_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    secret, resolved_key_id, key_source = _resolve_signing_secret(
        requested_key_id=key_id,
        explicit_signing_key=str(signing_key or "").strip(),
    )
    if resolved_key_id and not key_id:
        key_id = resolved_key_id
        sign_payload["signature_metadata"]["key_id"] = key_id

    if secret:
        signature = hmac.new(secret.encode("utf-8"), sign_canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_type = "hmac_sha256"
        signed = True
    else:
        signature = hashlib.sha256(sign_canonical.encode("utf-8")).hexdigest()
        signature_type = "sha256"
        signed = False

    result = {
        "success": True,
        "seal_version": 1,
        "policy_name": normalized_policy,
        "digest_sha256": seal_digest,
        "previous_digest": resolved_previous,
        "chain_source": chain_source,
        "chain_digest": chain_digest,
        "signature": signature,
        "signature_type": signature_type,
        "signed": bool(signed),
        "key_id": key_id,
        "key_source": key_source,
        "signature_version": signature_version,
        "envelope_heads": envelope_heads,
        "snapshot": (payload if bool(include_snapshot) else {}),
        "json": (canonical if bool(include_json) else ""),
    }

    if bool(persist_event):
        event_id = log_event(
            "pending.reconcile.governance_attestation_seal",
            f"Governance attestation seal exported: policy={normalized_policy}",
            severity="info",
            metadata={
                "seal_version": 1,
                "policy_name": normalized_policy,
                "digest_sha256": seal_digest,
                "previous_digest": resolved_previous,
                "chain_source": chain_source,
                "chain_digest": chain_digest,
                "signature": signature,
                "signature_type": signature_type,
                "signed": bool(signed),
                "key_id": key_id,
                "key_source": key_source,
                "signature_version": signature_version,
                "envelope_heads": envelope_heads,
                "include_json": bool(include_json),
                "include_snapshot": bool(include_snapshot),
            },
        )
        result["seal_event_id"] = int(event_id)

    return result


def get_latest_reconcile_governance_attestation_seal_head(policy_name: str = "") -> dict:
    """Return metadata for the most recent governance attestation seal."""
    rows = list_events(event_type="pending.reconcile.governance_attestation_seal", limit=200)
    normalized_policy = str(policy_name or "").strip().lower()
    for row in rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        return {
            "success": True,
            "event_id": int(row.get("event_id", 0) or 0),
            "created_at": str(row.get("created_at", "") or ""),
            "policy_name": row_policy,
            "digest_sha256": str(metadata.get("digest_sha256", "") or ""),
            "chain_digest": str(metadata.get("chain_digest", "") or ""),
            "previous_digest": str(metadata.get("previous_digest", "") or ""),
            "chain_source": str(metadata.get("chain_source", "none") or "none"),
            "seal_version": int(metadata.get("seal_version", 1) or 1),
            "signed": bool(metadata.get("signed", False)),
            "signature_type": str(metadata.get("signature_type", "") or ""),
            "key_id": str(metadata.get("key_id", "") or ""),
            "signature_version": int(metadata.get("signature_version", 1) or 1),
            "envelope_heads": dict(metadata.get("envelope_heads") or {}),
        }
    return {
        "success": False,
        "error": (
            "No governance attestation seal found"
            if not normalized_policy
            else f"No governance attestation seal found for policy {normalized_policy}"
        ),
    }


def verify_reconcile_governance_attestation_seal_chain(limit: int = 200, policy_name: str = "") -> dict:
    """Verify linkage and chain digests across governance attestation seals."""
    rows = list_events(
        event_type="pending.reconcile.governance_attestation_seal",
        limit=max(1, min(1000, int(limit))),
    )
    normalized_policy = str(policy_name or "").strip().lower()
    ordered_rows = list(reversed(rows))
    filtered: list[dict[str, Any]] = []
    for row in ordered_rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        filtered.append(row)

    if not filtered:
        return {"success": True, "status": "empty", "checked": 0, "ok": 0, "issues": []}

    issues: list[str] = []
    prev_digest = ""
    for row in filtered:
        metadata = dict(row.get("metadata") or {})
        event_id = int(row.get("event_id", 0) or 0)
        digest = str(metadata.get("digest_sha256", "") or "").strip().lower()
        chain_digest = str(metadata.get("chain_digest", "") or "").strip().lower()
        previous_digest = str(metadata.get("previous_digest", "") or "").strip().lower()
        chain_source = str(metadata.get("chain_source", "none") or "none")
        if chain_source in {"latest_event", "provided"} and prev_digest and previous_digest != prev_digest:
            issues.append(f"event_id={event_id}: previous_digest mismatch")
        chain_input = f"{previous_digest}:{digest}" if previous_digest else digest
        expected_chain = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()
        if chain_digest != expected_chain:
            issues.append(f"event_id={event_id}: chain_digest mismatch")
        prev_digest = digest

    status = "ok" if not issues else "broken"
    return {
        "success": True,
        "status": status,
        "checked": len(filtered),
        "ok": len(filtered) - len(issues),
        "issues": issues[:50],
        "head_event_id": int(filtered[-1].get("event_id", 0) or 0),
        "head_digest_sha256": str((filtered[-1].get("metadata") or {}).get("digest_sha256", "") or ""),
    }


def prune_reconcile_governance_attestation_seals(
    max_age_days: int = 30,
    dry_run: bool = True,
    policy_name: str = "",
    keep_latest: int | None = None,
    now: datetime | None = None,
) -> dict:
    """Prune stale governance attestation seal events."""
    rows = list_events(event_type="pending.reconcile.governance_attestation_seal", limit=5000)
    normalized_policy = str(policy_name or "").strip().lower()
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=max(1, int(max_age_days)))
    policy_rows: list[dict[str, Any]] = []
    for row in rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        policy_rows.append(row)

    policy_rows_sorted = sorted(policy_rows, key=lambda r: int(r.get("event_id", 0) or 0))
    keep_set: set[int] = set()
    if keep_latest is not None and int(keep_latest) > 0:
        for row in policy_rows_sorted[-int(keep_latest):]:
            keep_set.add(int(row.get("event_id", 0) or 0))

    candidates: list[int] = []
    for row in policy_rows_sorted:
        event_id = int(row.get("event_id", 0) or 0)
        if event_id in keep_set:
            continue
        created_at_str = str(row.get("created_at", "") or "")
        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if created_at < cutoff:
            candidates.append(event_id)

    deleted = 0
    if not bool(dry_run) and candidates:
        with get_tournament_connection() as conn:
            for eid in candidates:
                conn.execute("DELETE FROM tournament_events WHERE event_id = ?", (eid,))
            conn.commit()
        deleted = len(candidates)

    log_event(
        "pending.reconcile.governance_attestation_seals_pruned",
        f"Governance attestation seal prune: policy={normalized_policy or 'all'} candidates={len(candidates)} deleted={deleted} dry_run={dry_run}",
        severity="info",
        metadata={
            "policy_name": normalized_policy or "all",
            "max_age_days": int(max_age_days),
            "dry_run": bool(dry_run),
            "keep_latest": keep_latest,
            "candidates": len(candidates),
            "deleted": deleted,
            "kept": len(keep_set),
        },
    )
    return {
        "success": True,
        "dry_run": bool(dry_run),
        "policy_name": normalized_policy or "all",
        "candidates": len(candidates),
        "deleted": deleted,
        "kept": len(keep_set),
        "max_age_days": int(max_age_days),
    }


def create_reconcile_governance_attestation_seal_checkpoint(
    policy_name: str = "default",
    label: str = "",
    note: str = "",
    expected_previous_digest: str = "",
    require_head: bool = True,
    signing_key: str = "",
) -> dict:
    """Create signed checkpoint anchored to latest governance attestation seal head."""
    normalized_policy = str(policy_name or "default").strip().lower() or "default"
    head = get_latest_reconcile_governance_attestation_seal_head(policy_name=normalized_policy)
    if not head.get("success", False):
        if bool(require_head):
            return {
                "success": False,
                "error": str(head.get("error", "No governance attestation seal head available")),
                "head": head,
            }
        head = {
            "success": True,
            "event_id": 0,
            "created_at": "",
            "policy_name": normalized_policy,
            "digest_sha256": "",
            "chain_digest": "",
            "previous_digest": "",
            "chain_source": "none",
            "seal_version": 1,
        }

    expected = str(expected_previous_digest or "").strip().lower()
    current_digest = str(head.get("digest_sha256", "") or "").strip().lower()
    if expected and expected != current_digest:
        return {
            "success": False,
            "error": "expected_previous_digest does not match current governance attestation seal head",
            "expected_previous_digest": expected,
            "head_digest_sha256": current_digest,
            "policy_name": normalized_policy,
        }

    key_id = str(os.environ.get("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "") or "").strip()
    signature_version = int(os.environ.get("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "1") or 1)
    payload = {
        "checkpoint_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": str(label or "").strip(),
        "note": str(note or "").strip(),
        "policy_name": normalized_policy,
        "head": {
            "event_id": int(head.get("event_id", 0) or 0),
            "created_at": str(head.get("created_at", "") or ""),
            "policy_name": str(head.get("policy_name", normalized_policy) or normalized_policy).strip().lower(),
            "digest_sha256": current_digest,
            "chain_digest": str(head.get("chain_digest", "") or "").strip().lower(),
            "previous_digest": str(head.get("previous_digest", "") or "").strip().lower(),
            "chain_source": str(head.get("chain_source", "none") or "none"),
            "seal_version": int(head.get("seal_version", 1) or 1),
        },
        "signature_metadata": {
            "key_id": key_id,
            "signature_version": signature_version,
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    secret, resolved_key_id, key_source = _resolve_signing_secret(
        requested_key_id=key_id,
        explicit_signing_key=str(signing_key or "").strip(),
    )
    if resolved_key_id and not key_id:
        key_id = resolved_key_id
        payload["signature_metadata"]["key_id"] = key_id

    if secret:
        signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_type = "hmac_sha256"
        signed = True
    else:
        signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        signature_type = "sha256"
        signed = False

    checkpoint_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    event_id = log_event(
        "pending.reconcile.governance_attestation_seal_checkpoint",
        f"Governance attestation seal checkpoint created for policy={normalized_policy}",
        severity="info",
        metadata={
            "policy_name": normalized_policy,
            "checkpoint_digest": checkpoint_digest,
            "signature": signature,
            "signature_type": signature_type,
            "signed": bool(signed),
            "key_id": key_id,
            "key_source": key_source,
            "signature_version": signature_version,
            "head_event_id": int(head.get("event_id", 0) or 0),
            "head_digest_sha256": current_digest,
            "label": str(label or "").strip(),
            "payload": payload,
        },
    )
    return {
        "success": True,
        "event_id": int(event_id),
        "policy_name": normalized_policy,
        "checkpoint_digest": checkpoint_digest,
        "signature": signature,
        "signature_type": signature_type,
        "signed": bool(signed),
        "key_id": key_id,
        "key_source": key_source,
        "signature_version": signature_version,
        "head_event_id": int(head.get("event_id", 0) or 0),
        "head_digest_sha256": current_digest,
        "label": str(label or "").strip(),
    }


def get_latest_reconcile_governance_attestation_seal_checkpoint(policy_name: str = "") -> dict:
    """Return metadata for the most recent governance attestation seal checkpoint."""
    rows = list_events(event_type="pending.reconcile.governance_attestation_seal_checkpoint", limit=200)
    normalized_policy = str(policy_name or "").strip().lower()
    for row in rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        return {
            "success": True,
            "event_id": int(row.get("event_id", 0) or 0),
            "created_at": str(row.get("created_at", "") or ""),
            "policy_name": row_policy,
            "checkpoint_digest": str(metadata.get("checkpoint_digest", "") or ""),
            "head_event_id": int(metadata.get("head_event_id", 0) or 0),
            "head_digest_sha256": str(metadata.get("head_digest_sha256", "") or ""),
            "label": str(metadata.get("label", "") or ""),
            "signed": bool(metadata.get("signed", False)),
            "signature_type": str(metadata.get("signature_type", "") or ""),
            "key_id": str(metadata.get("key_id", "") or ""),
        }
    return {
        "success": False,
        "error": (
            "No governance attestation seal checkpoint found"
            if not normalized_policy
            else f"No governance attestation seal checkpoint found for policy {normalized_policy}"
        ),
    }


def verify_reconcile_governance_attestation_seal_checkpoint(
    policy_name: str = "",
    require_current_head: bool = False,
    require_signature_payload: bool = False,
) -> dict:
    """Verify latest governance attestation seal checkpoint against current seal head."""
    normalized_policy = str(policy_name or "").strip().lower()
    ckpt = get_latest_reconcile_governance_attestation_seal_checkpoint(policy_name=normalized_policy)
    if not ckpt.get("success", False):
        return {"success": True, "status": "empty", "error": str(ckpt.get("error", "No checkpoint found")), "policy_name": normalized_policy}

    head = get_latest_reconcile_governance_attestation_seal_head(policy_name=normalized_policy)
    if not head.get("success", False):
        return {"success": True, "status": "broken", "error": "No governance attestation seal head found", "policy_name": normalized_policy, "checkpoint": ckpt}

    ckpt_head_digest = str(ckpt.get("head_digest_sha256", "") or "").strip().lower()
    current_head_digest = str(head.get("digest_sha256", "") or "").strip().lower()
    if bool(require_current_head) and ckpt_head_digest != current_head_digest:
        return {
            "success": True,
            "status": "stale",
            "policy_name": normalized_policy,
            "checkpoint": ckpt,
            "head": head,
            "checkpoint_head_digest": ckpt_head_digest,
            "current_head_digest": current_head_digest,
        }

    status = "ok" if ckpt_head_digest == current_head_digest else "stale"
    if bool(require_signature_payload):
        ckpt_event_rows = list_events(event_type="pending.reconcile.governance_attestation_seal_checkpoint", limit=200)
        for row in ckpt_event_rows:
            if int(row.get("event_id", 0) or 0) == int(ckpt.get("event_id", 0) or 0):
                meta = dict(row.get("metadata") or {})
                payload = dict(meta.get("payload") or {})
                if not payload:
                    return {"success": True, "status": "broken", "error": "Checkpoint payload missing", "policy_name": normalized_policy, "checkpoint": ckpt}
                canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                recomputed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                stored_digest = str(ckpt.get("checkpoint_digest", "") or "").strip().lower()
                if recomputed != stored_digest:
                    return {"success": True, "status": "broken", "error": "Checkpoint digest recompute mismatch", "policy_name": normalized_policy, "checkpoint": ckpt}
                break

    return {
        "success": True,
        "status": status,
        "policy_name": normalized_policy,
        "checkpoint": ckpt,
        "head": head,
        "checkpoint_head_digest": ckpt_head_digest,
        "current_head_digest": current_head_digest,
    }


def verify_reconcile_governance_attestation_seal_checkpoint_history(
    limit: int = 200,
    policy_name: str = "",
    require_signature_payload: bool = False,
) -> dict:
    """Verify integrity of recent governance attestation seal checkpoint events."""
    rows = list_events(event_type="pending.reconcile.governance_attestation_seal_checkpoint", limit=max(1, min(1000, int(limit))))
    normalized_policy = str(policy_name or "").strip().lower()
    ok = 0
    broken = 0
    stale = 0
    issues: list[str] = []
    for row in rows:
        metadata = dict(row.get("metadata") or {})
        row_policy = str(metadata.get("policy_name", "") or "").strip().lower()
        if normalized_policy and row_policy != normalized_policy:
            continue
        event_id = int(row.get("event_id", 0) or 0)
        stored_digest = str(metadata.get("checkpoint_digest", "") or "").strip().lower()
        payload = dict((metadata.get("payload") or {}))
        if bool(require_signature_payload) and not payload:
            broken += 1
            issues.append(f"event_id={event_id}: payload missing")
            continue
        if payload:
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            recomputed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if recomputed != stored_digest:
                broken += 1
                issues.append(f"event_id={event_id}: digest mismatch")
                continue
        ok += 1

    return {
        "success": True,
        "policy_name": normalized_policy or "all",
        "ok": ok,
        "broken": broken,
        "stale": stale,
        "total": ok + broken + stale,
        "issues": issues[:50],
    }


def get_reconcile_chain_repair_diagnostics(limit: int = 200, policy_name: str = "") -> dict:
    """Return chain diagnostics with machine-readable repair recommendations."""
    normalized_policy = str(policy_name or "").strip().lower()
    checks = {
        "signature_receipts_chain": verify_reconcile_signature_receipts_artifact_chain(limit=max(1, min(1000, int(limit)))),
        "compliance_status_chain": verify_reconcile_compliance_status_artifact_chain(limit=max(1, min(1000, int(limit)))),
        "readiness_policy_snapshot_chain": verify_reconcile_compliance_readiness_policy_snapshot_chain(limit=max(1, min(1000, int(limit))), policy_name=normalized_policy),
        "readiness_evaluation_artifact_chain": verify_reconcile_compliance_readiness_evaluation_artifact_chain(limit=max(1, min(1000, int(limit))), policy_name=normalized_policy),
        "composite_governance_snapshot_chain": verify_reconcile_composite_governance_snapshot_chain(limit=max(1, min(1000, int(limit))), policy_name=normalized_policy),
        "governance_attestation_seal_chain": verify_reconcile_governance_attestation_seal_chain(limit=max(1, min(1000, int(limit))), policy_name=normalized_policy),
    }
    checkpoint_checks = {
        "signature_chain_checkpoint": verify_reconcile_signature_chain_checkpoint(require_current_head=False, require_signature_payload=False),
        "compliance_chain_checkpoint": verify_reconcile_compliance_chain_checkpoint(require_current_head=False, require_signature_payload=False),
        "readiness_policy_snapshot_checkpoint": verify_reconcile_compliance_readiness_policy_snapshot_checkpoint(policy_name=normalized_policy, require_current_head=False, require_signature_payload=False),
        "readiness_evaluation_artifact_checkpoint": verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint(policy_name=normalized_policy, require_current_head=False, require_signature_payload=False),
        "composite_governance_snapshot_checkpoint": verify_reconcile_composite_governance_snapshot_checkpoint(policy_name=normalized_policy, require_current_head=False, require_signature_payload=False),
        "governance_attestation_seal_checkpoint": verify_reconcile_governance_attestation_seal_checkpoint(policy_name=normalized_policy, require_current_head=False, require_signature_payload=False),
    }

    issues: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []

    def _add_recommendation(action: str, reason: str) -> None:
        entry = {"action": action, "reason": reason}
        if entry not in recommendations:
            recommendations.append(entry)

    for name, payload in checks.items():
        status = str(payload.get("status", "") or "").strip().lower()
        if status in {"broken", "empty"}:
            issues.append({"check": name, "status": status, "details": payload})
            if name == "signature_receipts_chain":
                _add_recommendation("export_reconcile_signature_receipts_artifact", "Rebuild signature receipts artifact chain head")
            elif name == "compliance_status_chain":
                _add_recommendation("export_reconcile_compliance_status_artifact", "Rebuild compliance status artifact chain head")
            elif name == "readiness_policy_snapshot_chain":
                _add_recommendation("export_reconcile_compliance_readiness_policy_snapshot", "Rebuild readiness policy snapshot chain head")
            elif name == "readiness_evaluation_artifact_chain":
                _add_recommendation("export_reconcile_compliance_readiness_evaluation_artifact", "Rebuild readiness evaluation artifact chain head")
            elif name == "composite_governance_snapshot_chain":
                _add_recommendation("export_reconcile_composite_governance_snapshot", "Rebuild composite governance snapshot chain head")
            elif name == "governance_attestation_seal_chain":
                _add_recommendation("export_reconcile_governance_attestation_seal", "Rebuild governance attestation seal chain head")

    for name, payload in checkpoint_checks.items():
        status = str(payload.get("status", "") or "").strip().lower()
        if status in {"broken", "empty", "stale"}:
            issues.append({"check": name, "status": status, "details": payload})
            if name == "signature_chain_checkpoint":
                _add_recommendation("create_reconcile_signature_chain_checkpoint", "Refresh signature chain checkpoint")
            elif name == "compliance_chain_checkpoint":
                _add_recommendation("create_reconcile_compliance_chain_checkpoint", "Refresh compliance chain checkpoint")
            elif name == "readiness_policy_snapshot_checkpoint":
                _add_recommendation("create_reconcile_compliance_readiness_policy_snapshot_checkpoint", "Refresh readiness policy snapshot checkpoint")
            elif name == "readiness_evaluation_artifact_checkpoint":
                _add_recommendation("create_reconcile_compliance_readiness_evaluation_artifact_checkpoint", "Refresh readiness evaluation artifact checkpoint")
            elif name == "composite_governance_snapshot_checkpoint":
                _add_recommendation("create_reconcile_composite_governance_snapshot_checkpoint", "Refresh composite governance snapshot checkpoint")
            elif name == "governance_attestation_seal_checkpoint":
                _add_recommendation("create_reconcile_governance_attestation_seal_checkpoint", "Refresh governance attestation seal checkpoint")

    status = "ok"
    if any(str(i.get("status", "")) == "broken" for i in issues):
        status = "error"
    elif issues:
        status = "warning"

    return {
        "success": True,
        "policy_name": normalized_policy,
        "status": status,
        "issue_count": len(issues),
        "recommendation_count": len(recommendations),
        "chain_checks": checks,
        "checkpoint_checks": checkpoint_checks,
        "issues": issues[:100],
        "recommended_actions": recommendations,
    }


def evaluate_reconcile_governance_enforcement(
    action: str = "financial_ops",
    policy_name: str = "default",
    block_on_warning: bool = False,
    require_attestation_seal: bool = False,
) -> dict:
    """Evaluate governance status and indicate whether critical operations should be blocked."""
    normalized_policy = str(policy_name or "default").strip().lower() or "default"
    compliance = get_reconcile_compliance_status(chain_limit=200)
    compliance_status = str(compliance.get("status", "error") or "error").strip().lower()
    blocked_reasons: list[str] = []

    if compliance_status == "error":
        blocked_reasons.append("compliance_status_error")
    elif bool(block_on_warning) and compliance_status == "warning":
        blocked_reasons.append("compliance_status_warning")

    attestation_check: dict[str, Any] = {
        "success": True,
        "status": "skipped",
        "reason": "require_attestation_seal_disabled",
    }
    if bool(require_attestation_seal):
        attestation_check = verify_reconcile_governance_attestation_seal_checkpoint(
            policy_name=normalized_policy,
            require_current_head=True,
            require_signature_payload=False,
        )
        if str(attestation_check.get("status", "") or "").strip().lower() != "ok":
            blocked_reasons.append("attestation_seal_not_current")

    blocked = len(blocked_reasons) > 0
    return {
        "success": True,
        "action": str(action or "financial_ops").strip().lower(),
        "policy_name": normalized_policy,
        "blocked": bool(blocked),
        "blocked_reasons": blocked_reasons,
        "compliance_status": compliance_status,
        "compliance_snapshot": compliance,
        "attestation_check": attestation_check,
        "block_on_warning": bool(block_on_warning),
        "require_attestation_seal": bool(require_attestation_seal),
    }


def export_reconcile_compliance_readiness_evaluation_artifact(
    policy_name: str = "default",
    chain_limit: int | None = None,
    warning_threshold: int | None = None,
    error_threshold: int | None = None,
    include_json: bool = False,
    include_snapshot: bool = True,
    persist_readiness_event: bool = False,
    previous_digest: str = "",
    auto_chain: bool = True,
    persist_event: bool = True,
    require_policy_snapshot_head: bool = False,
    require_compliance_artifact_head: bool = False,
) -> dict:
    """Export deterministic readiness evaluation artifact pinned to policy/compliance digests."""
    readiness = evaluate_reconcile_compliance_readiness(
        chain_limit=chain_limit,
        warning_threshold=warning_threshold,
        error_threshold=error_threshold,
        policy_name=str(policy_name or "default"),
        persist_event=bool(persist_readiness_event),
    )
    policy_resolved = str(((readiness.get("policy") or {}).get("name", "default") or "default")).strip().lower() or "default"

    policy_snapshot_head = get_latest_reconcile_compliance_readiness_policy_snapshot_head(policy_name=policy_resolved)
    if bool(require_policy_snapshot_head) and not policy_snapshot_head.get("success", False):
        return {
            "success": False,
            "error": str(policy_snapshot_head.get("error", "No readiness policy snapshot head available")),
            "policy_name": policy_resolved,
            "policy_snapshot_head": policy_snapshot_head,
        }

    compliance_head = get_latest_reconcile_compliance_status_artifact_head()
    if bool(require_compliance_artifact_head) and not compliance_head.get("success", False):
        return {
            "success": False,
            "error": str(compliance_head.get("error", "No compliance status artifact head available")),
            "policy_name": policy_resolved,
            "compliance_artifact_head": compliance_head,
        }

    artifact_payload = {
        "artifact_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy_name": policy_resolved,
        "status": str(readiness.get("status", "") or ""),
        "score": int(readiness.get("score", 0) or 0),
        "policy_digest_sha256": str(((readiness.get("policy") or {}).get("digest_sha256", "") or "")),
        "policy_snapshot_head": {
            "success": bool(policy_snapshot_head.get("success", False)),
            "event_id": int(policy_snapshot_head.get("event_id", 0) or 0),
            "digest_sha256": str(policy_snapshot_head.get("digest_sha256", "") or ""),
            "policy_digest_sha256": str(policy_snapshot_head.get("policy_digest_sha256", "") or ""),
        },
        "compliance_artifact_head": {
            "success": bool(compliance_head.get("success", False)),
            "event_id": int(compliance_head.get("event_id", 0) or 0),
            "digest_sha256": str(compliance_head.get("digest_sha256", "") or ""),
            "chain_digest": str(compliance_head.get("chain_digest", "") or ""),
        },
        "readiness": (dict(readiness) if bool(include_snapshot) else {
            "status": str(readiness.get("status", "") or ""),
            "score": int(readiness.get("score", 0) or 0),
            "issues": list(readiness.get("issues") or []),
            "warnings": list(readiness.get("warnings") or []),
            "checks": dict(readiness.get("checks") or {}),
            "policy": dict(readiness.get("policy") or {}),
            "score_breakdown": dict(readiness.get("score_breakdown") or {}),
        }),
    }

    canonical = json.dumps(artifact_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    artifact_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    resolved_previous = str(previous_digest or "").strip().lower()
    chain_source = "provided" if resolved_previous else "none"
    if not resolved_previous and bool(auto_chain):
        latest_head = get_latest_reconcile_compliance_readiness_evaluation_artifact_head(policy_name=policy_resolved)
        if latest_head.get("success"):
            resolved_previous = str(latest_head.get("digest_sha256", "") or "").strip().lower()
            chain_source = "latest_event"

    chain_input = f"{resolved_previous}:{artifact_digest}" if resolved_previous else artifact_digest
    chain_digest = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()

    result = {
        "success": True,
        "artifact_version": 1,
        "policy_name": policy_resolved,
        "status": str(readiness.get("status", "") or ""),
        "score": int(readiness.get("score", 0) or 0),
        "policy_digest_sha256": str(((readiness.get("policy") or {}).get("digest_sha256", "") or "")),
        "policy_snapshot_digest_sha256": str(artifact_payload.get("policy_snapshot_head", {}).get("digest_sha256", "") or ""),
        "compliance_artifact_digest_sha256": str(artifact_payload.get("compliance_artifact_head", {}).get("digest_sha256", "") or ""),
        "digest_sha256": artifact_digest,
        "previous_digest": resolved_previous,
        "chain_source": chain_source,
        "chain_digest": chain_digest,
        "artifact": artifact_payload,
        "json": (canonical if bool(include_json) else ""),
    }

    if bool(persist_event):
        event_id = log_event(
            "pending.reconcile.compliance_readiness_evaluation_artifact",
            (
                "Readiness evaluation artifact exported: "
                f"policy={policy_resolved} status={result['status']} score={result['score']}"
            ),
            severity=("info" if str(result["status"]) == "ready" else "warning"),
            metadata={
                "artifact_version": int(result.get("artifact_version", 1)),
                "policy_name": str(policy_resolved),
                "status": str(result.get("status", "")),
                "score": int(result.get("score", 0) or 0),
                "policy_digest_sha256": str(result.get("policy_digest_sha256", "")),
                "policy_snapshot_digest_sha256": str(result.get("policy_snapshot_digest_sha256", "")),
                "compliance_artifact_digest_sha256": str(result.get("compliance_artifact_digest_sha256", "")),
                "digest_sha256": str(result.get("digest_sha256", "")),
                "previous_digest": str(result.get("previous_digest", "")),
                "chain_source": str(result.get("chain_source", "none")),
                "chain_digest": str(result.get("chain_digest", "")),
                "include_json": bool(include_json),
                "include_snapshot": bool(include_snapshot),
            },
        )
        result["artifact_event_id"] = int(event_id)

    return result


def evaluate_reconcile_compliance_readiness(
    chain_limit: int | None = None,
    warning_threshold: int | None = None,
    error_threshold: int | None = None,
    policy_name: str = "default",
    persist_event: bool = False,
    monitor_transition: bool | None = None,
    transition_cooldown_minutes: int | None = None,
    notify_users: bool = False,
    transition_notify_emails: list[str] | None = None,
) -> dict:
    """Evaluate compliance readiness score with policy thresholds and optional audit event."""
    policy_resolution = _resolve_reconcile_compliance_readiness_policy(policy_name=str(policy_name or "default"))
    policy_cfg = dict(policy_resolution.get("config") or {})
    policy_name_resolved = str(policy_resolution.get("resolved", "default") or "default")
    policy_canonical = json.dumps(policy_cfg, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    policy_digest = hashlib.sha256(policy_canonical.encode("utf-8")).hexdigest()

    chain_limit_val = int(policy_cfg.get("chain_limit", 200) or 200) if chain_limit is None else int(chain_limit)
    warning_threshold_val = int(policy_cfg.get("warning_threshold", 80) or 80) if warning_threshold is None else int(warning_threshold)
    error_threshold_val = int(policy_cfg.get("error_threshold", 60) or 60) if error_threshold is None else int(error_threshold)
    monitor_transition_val = bool(policy_cfg.get("monitor_transition", False)) if monitor_transition is None else bool(monitor_transition)
    transition_cooldown_minutes_val = (
        int(policy_cfg.get("transition_cooldown_minutes", 0) or 0)
        if transition_cooldown_minutes is None
        else int(transition_cooldown_minutes)
    )

    issue_penalty = max(0, min(100, int(policy_cfg.get("issue_penalty", 30) or 30)))
    warning_penalty = max(0, min(100, int(policy_cfg.get("warning_penalty", 10) or 10)))
    check_failure_penalty_default = max(0, min(100, int(policy_cfg.get("check_failure_penalty_default", 8) or 8)))
    check_failure_penalties = dict(policy_cfg.get("check_failure_penalties") or {})

    chain_limit_int = max(1, min(1000, int(chain_limit_val)))
    warning_threshold_int = max(0, min(100, int(warning_threshold_val)))
    error_threshold_int = max(0, min(100, int(error_threshold_val)))
    if error_threshold_int >= warning_threshold_int:
        warning_threshold_int = min(100, error_threshold_int + 1)
    transition_cooldown_minutes_int = max(0, min(1440, int(transition_cooldown_minutes_val)))

    snapshot = get_reconcile_compliance_status(chain_limit=chain_limit_int)
    issues = list(snapshot.get("issues") or [])
    warnings = list(snapshot.get("warnings") or [])

    checks = {
        "signature_artifact_chain_ok": str(((snapshot.get("artifact_chain") or {}).get("status", "") or "")).lower() == "ok",
        "signature_checkpoint_ok": str(((snapshot.get("latest_checkpoint") or {}).get("status", "") or "")).lower() == "ok",
        "compliance_artifact_chain_ok": str(((snapshot.get("compliance_artifact_chain") or {}).get("status", "") or "")).lower() == "ok",
        "compliance_checkpoint_ok": str(((snapshot.get("latest_compliance_checkpoint") or {}).get("status", "") or "")).lower() == "ok",
        "signing_key_ready": bool(
            int(((snapshot.get("signing_keys") or {}).get("registry_count", 0) or 0)) > 0
            or bool((snapshot.get("signing_keys") or {}).get("fallback_key_configured", False))
        ),
    }

    score = 100
    score -= issue_penalty * len(issues)
    score -= warning_penalty * len(warnings)
    failed_checks: list[str] = []
    check_penalty_applied: dict[str, int] = {}
    for name, passed in checks.items():
        if not passed:
            failed_checks.append(name)
            penalty = max(0, min(100, int(check_failure_penalties.get(name, check_failure_penalty_default) or check_failure_penalty_default)))
            check_penalty_applied[name] = penalty
            score -= penalty
    score = max(0, min(100, int(score)))

    if score <= error_threshold_int or len(issues) > 0:
        readiness_status = "blocked"
    elif score <= warning_threshold_int or len(warnings) > 0:
        readiness_status = "warning"
    else:
        readiness_status = "ready"

    result = {
        "success": True,
        "policy": {
            "name": policy_name_resolved,
            "requested_name": str(policy_resolution.get("requested", "default") or "default"),
            "found": bool(policy_resolution.get("found", False)),
            "digest_sha256": policy_digest,
            "chain_limit": chain_limit_int,
            "warning_threshold": warning_threshold_int,
            "error_threshold": error_threshold_int,
            "monitor_transition": bool(monitor_transition_val),
            "transition_cooldown_minutes": int(transition_cooldown_minutes_int),
            "issue_penalty": int(issue_penalty),
            "warning_penalty": int(warning_penalty),
            "check_failure_penalty_default": int(check_failure_penalty_default),
            "check_failure_penalties": check_failure_penalties,
        },
        "score": score,
        "status": readiness_status,
        "issues": issues,
        "warnings": warnings,
        "checks": checks,
        "score_breakdown": {
            "issue_penalty_each": int(issue_penalty),
            "warning_penalty_each": int(warning_penalty),
            "issues_count": len(issues),
            "warnings_count": len(warnings),
            "failed_checks": failed_checks,
            "check_penalty_applied": check_penalty_applied,
        },
        "snapshot": snapshot,
    }

    previous_status = ""
    latest_policy_event_id = 0
    prior_rows = list_events(event_type="pending.reconcile.compliance_readiness_evaluated", limit=50)
    for row in prior_rows:
        metadata = dict(row.get("metadata") or {})
        if str(metadata.get("policy_name", "") or "") != str(result["policy"]["name"]):
            continue
        previous_status = str(metadata.get("status", "") or "")
        latest_policy_event_id = int(row.get("event_id", 0) or 0)
        break

    if bool(persist_event):
        event_id = log_event(
            "pending.reconcile.compliance_readiness_evaluated",
            (
                "Compliance readiness evaluated: "
                f"status={readiness_status} score={score} "
                f"issues={len(issues)} warnings={len(warnings)}"
            ),
            severity=("info" if readiness_status == "ready" else "warning"),
            metadata={
                "policy_name": str(result["policy"]["name"]),
                "policy_digest_sha256": str(policy_digest),
                "chain_limit": int(chain_limit_int),
                "warning_threshold": int(warning_threshold_int),
                "error_threshold": int(error_threshold_int),
                "score": int(score),
                "status": readiness_status,
                "issues": list(issues),
                "warnings": list(warnings),
                "checks": checks,
            },
        )
        result["event_id"] = int(event_id)

    transition = {
        "checked": bool(monitor_transition_val),
        "changed": False,
        "previous_status": previous_status,
        "current_status": readiness_status,
        "event_id": 0,
        "notified": 0,
        "notified_users": [],
        "latest_policy_event_id": int(latest_policy_event_id),
        "cooldown_minutes": int(transition_cooldown_minutes_int),
        "suppressed_by_cooldown": False,
        "cooldown_active": False,
        "cooldown_remaining_seconds": 0,
        "last_transition_event_id": 0,
    }
    if bool(monitor_transition_val):
        changed = bool(previous_status) and previous_status != readiness_status
        transition["changed"] = changed
        if changed:
            last_transition_rows = list_events(event_type="pending.reconcile.compliance_readiness_transition", limit=100)
            last_transition = None
            for row in last_transition_rows:
                metadata = dict(row.get("metadata") or {})
                if str(metadata.get("policy_name", "") or "") != str(result["policy"]["name"]):
                    continue
                last_transition = row
                break

            cooldown_active = False
            cooldown_remaining_seconds = 0
            if transition_cooldown_minutes_int > 0 and last_transition is not None:
                created_raw = str(last_transition.get("created_at", "") or "").strip()
                parsed_created = None
                if created_raw:
                    try:
                        parsed_created = datetime.fromisoformat(created_raw.replace(" ", "T")).astimezone(timezone.utc).replace(tzinfo=None)
                    except Exception:
                        try:
                            parsed_created = datetime.fromisoformat(created_raw.replace(" ", "T"))
                        except Exception:
                            parsed_created = None

                if parsed_created is not None:
                    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                    elapsed = max(0, int((now_utc - parsed_created).total_seconds()))
                    cooldown_seconds = int(transition_cooldown_minutes_int) * 60
                    if elapsed < cooldown_seconds:
                        cooldown_active = True
                        cooldown_remaining_seconds = max(0, cooldown_seconds - elapsed)

            if last_transition is not None:
                transition["last_transition_event_id"] = int(last_transition.get("event_id", 0) or 0)
            transition["cooldown_active"] = bool(cooldown_active)
            transition["cooldown_remaining_seconds"] = int(cooldown_remaining_seconds)

            if cooldown_active:
                transition["suppressed_by_cooldown"] = True
                return_result = result
                return_result["transition"] = transition
                return return_result

            transition_event_id = log_event(
                "pending.reconcile.compliance_readiness_transition",
                (
                    "Compliance readiness status transition: "
                    f"policy={result['policy']['name']} "
                    f"from={previous_status} to={readiness_status}"
                ),
                severity=("error" if readiness_status == "blocked" else "warning"),
                metadata={
                    "policy_name": str(result["policy"]["name"]),
                    "previous_status": previous_status,
                    "current_status": readiness_status,
                    "score": int(score),
                    "issues": list(issues),
                    "warnings": list(warnings),
                    "cooldown_minutes": int(transition_cooldown_minutes_int),
                },
            )
            transition["event_id"] = int(transition_event_id)

            if bool(notify_users):
                configured = str(os.environ.get("TOURNAMENT_RECONCILE_ALERT_EMAILS", "") or "")
                env_emails = [
                    e.strip().lower()
                    for e in configured.replace(";", ",").split(",")
                    if e.strip()
                ]
                provided = [str(e or "").strip().lower() for e in list(transition_notify_emails or []) if str(e or "").strip()]
                notify_targets = sorted({e for e in (provided + env_emails) if e})
                for email in notify_targets:
                    send_notification(
                        "compliance_readiness_transition",
                        (
                            "Compliance readiness changed "
                            f"from {previous_status} to {readiness_status} "
                            f"(policy={result['policy']['name']}, score={score})"
                        ),
                        user_email=email,
                        metadata={
                            "policy_name": str(result["policy"]["name"]),
                            "previous_status": previous_status,
                            "current_status": readiness_status,
                            "score": int(score),
                        },
                    )
                transition["notified"] = len(notify_targets)
                transition["notified_users"] = notify_targets

    result["transition"] = transition

    return result


def reconcile_pending_paid_entries(
    limit: int = 200,
    dry_run: bool = False,
    max_actions: int | None = None,
    priority: str = "paid_first_oldest",
) -> dict:
    """Auto-reconcile pending rows when an entry already exists for that checkout session."""
    pending_rows = list_pending_paid_entries(status="pending", limit=max(1, int(limit)))
    normalized_priority = str(priority or "paid_first_oldest").strip().lower()
    if normalized_priority not in {"paid_first_oldest", "oldest_first", "newest_first"}:
        normalized_priority = "paid_first_oldest"

    max_actions_int = None
    if max_actions is not None:
        try:
            max_actions_int = max(1, int(max_actions))
        except Exception:
            max_actions_int = None

    summary = {
        "scanned": len(pending_rows),
        "reconciled": 0,
        "candidates": 0,
        "attempted": 0,
        "skipped_due_to_cap": 0,
        "failed": 0,
        "dry_run": bool(dry_run),
        "priority": normalized_priority,
        "max_actions": max_actions_int,
        "digest_normalize_mode": "trim",
        "candidate_sessions_sha256": "",
        "attempted_sessions_sha256": "",
        "actions": [],
    }

    candidates: list[dict[str, Any]] = []

    def _created_sort_value(raw: str, *, newest: bool) -> datetime:
        text = str(raw or "").strip()
        if not text:
            return datetime.max if not newest else datetime.min
        try:
            dt = datetime.fromisoformat(text.replace(" ", "T"))
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            return datetime.max if not newest else datetime.min

    for row in pending_rows:
        sid = str(row.get("checkout_session_id", "") or "").strip()
        if not sid:
            continue

        try:
            diag = assess_pending_paid_entry(sid)
            action = str(diag.get("recommended_action", "") or "").strip().lower()
            if action != "mark_finalized":
                continue

            summary["candidates"] += 1

            payment_ref = str((diag.get("pending") or {}).get("payment_intent_id", "") or "").strip()
            if not payment_ref:
                payment_ref = str((diag.get("checkout_record") or {}).get("payment_intent_id", "") or "").strip()
            if not payment_ref:
                payment_ref = sid
            candidates.append(
                {
                    "checkout_session_id": sid,
                    "diag": diag,
                    "payment_ref": payment_ref,
                    "created_at": str((diag.get("pending") or {}).get("created_at", "") or ""),
                    "payment_status": str((diag.get("checkout_record") or {}).get("payment_status", "") or "")
                    .strip()
                    .lower(),
                }
            )
        except Exception:
            summary["failed"] += 1
            log_event(
                "pending.reconcile_failed",
                f"Pending reconcile raised exception for session {sid}",
                tournament_id=int(row.get("tournament_id", 0) or 0),
                user_email=str(row.get("user_email", "") or ""),
                severity="warning",
                metadata={
                    "checkout_session_id": sid,
                    "reason": "exception",
                },
            )

    if normalized_priority == "oldest_first":
        candidates.sort(key=lambda c: _created_sort_value(c.get("created_at", ""), newest=False))
    elif normalized_priority == "newest_first":
        candidates.sort(key=lambda c: _created_sort_value(c.get("created_at", ""), newest=True), reverse=True)
    else:
        candidates.sort(
            key=lambda c: (
                0 if str(c.get("payment_status", "")) in {"paid", "no_payment_required"} else 1,
                _created_sort_value(c.get("created_at", ""), newest=False),
            )
        )

    summary["candidates"] = len(candidates)
    candidate_ids = [str(c.get("checkout_session_id", "") or "").strip() for c in candidates]
    summary["candidate_sessions_sha256"] = compute_reconcile_digest(
        candidate_ids,
        strict_order=True,
        normalize_mode="trim",
    )

    selected = candidates[:max_actions_int] if max_actions_int is not None else candidates
    summary["attempted"] = len(selected)
    summary["skipped_due_to_cap"] = max(0, len(candidates) - len(selected))
    selected_ids = [str(c.get("checkout_session_id", "") or "").strip() for c in selected]
    summary["attempted_sessions_sha256"] = compute_reconcile_digest(
        selected_ids,
        strict_order=True,
        normalize_mode="trim",
    )

    for candidate in selected:
        sid = str(candidate.get("checkout_session_id", "") or "").strip()
        diag = candidate.get("diag") or {}
        payment_ref = str(candidate.get("payment_ref", "") or "").strip() or sid

        if dry_run:
            summary["actions"].append(
                {
                    "checkout_session_id": sid,
                    "action": "mark_finalized",
                    "entry_id": diag.get("existing_entry_id"),
                    "dry_run": True,
                }
            )
            continue

        updated = mark_pending_paid_entry_finalized(sid, payment_ref)
        if not updated:
            summary["failed"] += 1
            log_event(
                "pending.reconcile_failed",
                f"Pending reconcile failed for session {sid}",
                tournament_id=int((diag.get("pending") or {}).get("tournament_id", 0) or 0),
                user_email=str((diag.get("pending") or {}).get("user_email", "") or ""),
                severity="warning",
                metadata={
                    "checkout_session_id": sid,
                    "reason": "mark_finalized_update_failed",
                },
            )
            continue

        summary["reconciled"] += 1
        summary["actions"].append(
            {
                "checkout_session_id": sid,
                "action": "mark_finalized",
                "entry_id": diag.get("existing_entry_id"),
            }
        )
        log_event(
            "pending.reconciled",
            f"Pending reconcile marked finalized for session {sid}",
            tournament_id=int((diag.get("pending") or {}).get("tournament_id", 0) or 0),
            entry_id=(
                int(diag.get("existing_entry_id"))
                if diag.get("existing_entry_id") is not None
                else None
            ),
            user_email=str((diag.get("pending") or {}).get("user_email", "") or ""),
            metadata={
                "checkout_session_id": sid,
                "source": "reconcile_pending_paid_entries",
            },
        )

    log_event(
        "pending.reconcile_summary",
        (
            f"Pending reconcile summary: scanned={summary['scanned']} "
            f"candidates={summary['candidates']} attempted={summary['attempted']} "
            f"reconciled={summary['reconciled']} failed={summary['failed']}"
        ),
        metadata={
            "dry_run": bool(summary.get("dry_run")),
            "priority": str(summary.get("priority", "")),
            "max_actions": summary.get("max_actions"),
            "digest_normalize_mode": str(summary.get("digest_normalize_mode", "trim")),
            "candidate_sessions_sha256": str(summary.get("candidate_sessions_sha256", "")),
            "attempted_sessions_sha256": str(summary.get("attempted_sessions_sha256", "")),
            "skipped_due_to_cap": int(summary.get("skipped_due_to_cap", 0) or 0),
        },
    )

    return summary


def _lp_points(court_tier: str, rank: int) -> int:
    lp_map = {
        "Open": {1: 15, 2: 10, 3: 7, 4: 5, 5: 3},
        "Pro": {1: 50, 2: 35, 3: 25, 4: 15, 5: 10},
        "Elite": {1: 100, 2: 70, 3: 50, 4: 35, 5: 25},
        "Championship": {1: 250, 2: 175, 3: 125, 4: 75, 5: 50},
    }
    return int(lp_map.get(court_tier, {}).get(rank, 0))


def _load_profile(conn, player_id: str) -> dict | None:
    row = conn.execute(
        "SELECT profile_json FROM player_profiles WHERE player_id = ?",
        (str(player_id),),
    ).fetchone()
    if not row:
        return None
    return _loads_json(row["profile_json"], {})


def _award_exists(conn: sqlite3.Connection, user_email: str, award_key: str) -> bool:
    row = conn.execute(
        """
        SELECT award_id
        FROM awards_log
        WHERE user_email = ? AND award_key = ?
        LIMIT 1
        """,
        (str(user_email or "").strip().lower(), str(award_key or "").strip()),
    ).fetchone()
    return row is not None


def _grant_badge_award(
    conn: sqlite3.Connection,
    *,
    user_email: str,
    award_key: str,
    award_name: str,
    context: dict | None = None,
) -> bool:
    normalized_email = str(user_email or "").strip().lower()
    normalized_key = str(award_key or "").strip()
    if not normalized_email or not normalized_key:
        return False
    if _award_exists(conn, normalized_email, normalized_key):
        return False

    conn.execute(
        """
        INSERT INTO awards_log (user_email, award_type, award_key, award_name, context_json, granted_at)
        VALUES (?, 'badge', ?, ?, ?, datetime('now'))
        """,
        (
            normalized_email,
            normalized_key,
            str(award_name or normalized_key),
            json.dumps(context or {}),
        ),
    )

    stats_row = conn.execute(
        "SELECT badges_json FROM user_career_stats WHERE user_email = ?",
        (normalized_email,),
    ).fetchone()
    current_badges = _loads_json(stats_row["badges_json"] if stats_row else None, [])
    if not isinstance(current_badges, list):
        current_badges = []
    if normalized_key not in current_badges:
        current_badges.append(normalized_key)
        conn.execute(
            "UPDATE user_career_stats SET badges_json = ?, updated_at = datetime('now') WHERE user_email = ?",
            (json.dumps(current_badges), normalized_email),
        )
    return True


def _current_win_streak(conn: sqlite3.Connection, user_email: str, sample_limit: int = 20) -> int:
    rows = conn.execute(
        """
        SELECT e.rank
        FROM tournament_entries e
        JOIN tournaments t ON t.tournament_id = e.tournament_id
        WHERE e.user_email = ? AND e.rank IS NOT NULL
        ORDER BY COALESCE(t.resolved_at, t.lock_time, e.created_at) DESC, e.created_at DESC, e.entry_id DESC
        LIMIT ?
        """,
        (str(user_email or "").strip().lower(), max(1, int(sample_limit))),
    ).fetchall()
    streak = 0
    for row in rows:
        if int((row["rank"] if isinstance(row, sqlite3.Row) else row[0]) or 0) == 1:
            streak += 1
        else:
            break
    return streak


def _winner_tiers_last_n_days(conn: sqlite3.Connection, user_email: str, days: int = 31) -> set[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT t.court_tier
        FROM tournament_entries e
        JOIN tournaments t ON t.tournament_id = e.tournament_id
        WHERE e.user_email = ?
          AND e.rank = 1
          AND t.status = 'resolved'
          AND COALESCE(t.resolved_at, t.lock_time, e.created_at) >= datetime('now', ?)
        """,
        (str(user_email or "").strip().lower(), f"-{max(1, int(days))} day"),
    ).fetchall()
    return {str((r["court_tier"] if isinstance(r, sqlite3.Row) else r[0]) or "") for r in rows}


def resolve_tournament(tournament_id: int) -> dict:
    """Resolve tournament after lock with environment + player simulation."""
    tournament = get_tournament(tournament_id)
    if not tournament:
        log_event(
            "tournament.resolve_failed",
            f"Resolve failed: tournament #{tournament_id} not found",
            tournament_id=tournament_id,
            severity="error",
        )
        return {"success": False, "error": "Tournament not found"}
    if tournament.get("status") not in ("open", "locked"):
        log_event(
            "tournament.resolve_failed",
            f"Resolve failed: invalid status {tournament.get('status')}",
            tournament_id=tournament_id,
            severity="warning",
        )
        return {"success": False, "error": f"Invalid status: {tournament.get('status')}"}

    deferred_events = []
    deferred_notifications = []
    final_result = None

    with tournament_db.get_tournament_connection() as conn:
        entries = conn.execute(
            "SELECT * FROM tournament_entries WHERE tournament_id = ? ORDER BY created_at ASC",
            (int(tournament_id),),
        ).fetchall()
        entry_dicts = [dict(e) for e in entries]

        min_entries = int(tournament.get("min_entries", 0))
        if len(entry_dicts) < min_entries:
            conn.execute(
                "UPDATE tournaments SET status='cancelled', resolved_at=datetime('now') WHERE tournament_id = ?",
                (int(tournament_id),),
            )
            conn.commit()
            deferred_events.append(
                {
                    "event_type": "tournament.cancelled",
                    "message": f"Tournament #{tournament_id} cancelled: min entries not met",
                    "tournament_id": tournament_id,
                    "severity": "warning",
                    "metadata": {"entries": len(entry_dicts), "minimum": min_entries},
                }
            )
            final_result = {
                "success": True,
                "status": "cancelled",
                "reason": "min_entries_not_met",
                "entries": len(entry_dicts),
            }
            return final_result

        raw_seed, seed_int = generate_tournament_seed()
        env = simulate_tournament_environment(seed_int)
        sport_code = normalize_sport_code(str(tournament.get("sport", "nba") or "nba"))
        sport_handler = get_sport_handler(sport_code)

        unique_player_ids = set()
        parsed_entries: list[dict] = []
        entry_has_legend: dict[int, bool] = {}
        entry_has_five_by_five: dict[int, bool] = {}
        for row in entry_dicts:
            roster = _loads_json(row.get("roster_json"), [])
            parsed = {**row, "roster": roster}
            parsed_entries.append(parsed)
            entry_has_legend[int(row["entry_id"])] = any(bool(p.get("is_legend", False)) for p in roster)
            for player in roster:
                unique_player_ids.add(str(player.get("player_id", "")))

        participant_emails = sorted({str(r.get("user_email", "")).strip().lower() for r in parsed_entries if str(r.get("user_email", "")).strip()})
        prior_wins: dict[str, int] = {email: 0 for email in participant_emails}
        prior_levels: dict[str, int] = {email: 1 for email in participant_emails}
        for email in participant_emails:
            row = conn.execute(
                "SELECT lifetime_wins, career_level FROM user_career_stats WHERE user_email = ?",
                (email,),
            ).fetchone()
            prior_wins[email] = int((row["lifetime_wins"] if row else 0) or 0)
            prior_levels[email] = int((row["career_level"] if row else 1) or 1)

        sim_results: dict[str, dict] = {}
        for pid in sorted(unique_player_ids):
            profile = _load_profile(conn, pid)
            if not profile:
                continue
            line = simulate_player_full_line(profile, env, seed_int)
            if sport_code == "nba":
                scored = score_player_total(profile, line, seed=seed_int + abs(hash(pid)) % 100000)
            else:
                normalized_line = dict(sport_handler.normalize_stat_line(line))
                fp = float(sport_handler.score_line(normalized_line))
                scored = {
                    **normalized_line,
                    "fantasy_points": fp,
                    "bonuses": {"total": 0.0, "triggered": []},
                    "penalties": {"total": 0.0, "triggered": []},
                    "total_fp": fp,
                }
            sim_results[pid] = scored

            conn.execute(
                """
                INSERT INTO simulated_scores
                    (tournament_id, player_id, player_name, line_json, fantasy_points,
                     bonuses_json, penalties_json, total_fp, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(tournament_id, player_id) DO UPDATE SET
                    line_json=excluded.line_json,
                    fantasy_points=excluded.fantasy_points,
                    bonuses_json=excluded.bonuses_json,
                    penalties_json=excluded.penalties_json,
                    total_fp=excluded.total_fp,
                    created_at=datetime('now')
                """,
                (
                    int(tournament_id),
                    pid,
                    str(profile.get("player_name", "")),
                    json.dumps(
                        {
                            k: int(v)
                            for k, v in scored.items()
                            if isinstance(v, (int, float))
                            and k not in ("fantasy_points", "total_fp")
                        }
                    ),
                    float(scored.get("fantasy_points", 0.0)),
                    json.dumps(scored.get("bonuses", {})),
                    json.dumps(scored.get("penalties", {})),
                    float(scored.get("total_fp", 0.0)),
                ),
            )

        scored_entries: list[dict] = []
        for row in parsed_entries:
            total = 0.0
            highest = 0.0
            roster = row["roster"]
            has_five_by_five = False
            for player in roster:
                pid = str(player.get("player_id", ""))
                score_obj = dict(sim_results.get(pid, {}) or {})
                total_fp = float(score_obj.get("total_fp", 0.0))
                total += total_fp
                highest = max(highest, total_fp)
                bonus_triggers = list(((score_obj.get("bonuses") or {}).get("triggered") or []))
                if "five_by_five" in bonus_triggers:
                    has_five_by_five = True
            entry_has_five_by_five[int(row["entry_id"])] = has_five_by_five
            scored_entries.append({
                "entry_id": int(row["entry_id"]),
                "user_email": row.get("user_email", ""),
                "display_name": row.get("display_name", ""),
                "total_score": round(total, 2),
                "highest_player_score": highest,
                "created_at": row.get("created_at", ""),
            })

        scored_entries.sort(key=lambda r: (-r["total_score"], -r["highest_player_score"], r["created_at"]))

        payout_template = _loads_json(tournament.get("payout_structure_json"), [])
        payout = compute_scaled_payouts(
            entry_fee=float(tournament.get("entry_fee", 0.0)),
            entries=len(scored_entries),
            min_entries=int(tournament.get("min_entries", 0)),
            max_entries=int(tournament.get("max_entries", 0)),
            rake_percent=0.20,
            full_field_template=payout_template,
        )

        for idx, row in enumerate(scored_entries, start=1):
            payout_amount = float(payout.get("payouts", [])[idx - 1]) if idx <= len(payout.get("payouts", [])) else 0.0
            lp = _lp_points(str(tournament.get("court_tier", "Open")), idx)
            normalized_email = str(row.get("user_email", "")).strip().lower()
            conn.execute(
                """
                UPDATE tournament_entries
                SET total_score = ?, rank = ?, lp_awarded = ?, payout_amount = ?
                WHERE entry_id = ?
                """,
                (
                    row["total_score"],
                    idx,
                    lp,
                    payout_amount,
                    row["entry_id"],
                ),
            )

            conn.execute(
                """
                INSERT INTO user_career_stats
                    (user_email, display_name, lifetime_entries, lifetime_wins, lifetime_top5,
                     lifetime_earnings, lifetime_lp, career_level, updated_at)
                VALUES (?, ?, 1, ?, ?, ?, ?, 1, datetime('now'))
                ON CONFLICT(user_email) DO UPDATE SET
                    display_name = CASE
                        WHEN excluded.display_name IS NOT NULL AND excluded.display_name != ''
                        THEN excluded.display_name
                        ELSE user_career_stats.display_name
                    END,
                    lifetime_entries = user_career_stats.lifetime_entries + 1,
                    lifetime_wins = user_career_stats.lifetime_wins + excluded.lifetime_wins,
                    lifetime_top5 = user_career_stats.lifetime_top5 + excluded.lifetime_top5,
                    lifetime_earnings = user_career_stats.lifetime_earnings + excluded.lifetime_earnings,
                    lifetime_lp = user_career_stats.lifetime_lp + excluded.lifetime_lp,
                    career_level = CASE
                        WHEN (user_career_stats.lifetime_lp + excluded.lifetime_lp) >= 5000 THEN 30
                        WHEN (user_career_stats.lifetime_lp + excluded.lifetime_lp) >= 3500 THEN 25
                        WHEN (user_career_stats.lifetime_lp + excluded.lifetime_lp) >= 2000 THEN 20
                        WHEN (user_career_stats.lifetime_lp + excluded.lifetime_lp) >= 1000 THEN 15
                        WHEN (user_career_stats.lifetime_lp + excluded.lifetime_lp) >= 500 THEN 10
                        WHEN (user_career_stats.lifetime_lp + excluded.lifetime_lp) >= 100 THEN 5
                        ELSE user_career_stats.career_level
                    END,
                    updated_at = datetime('now')
                """,
                (
                    normalized_email,
                    str(row.get("display_name", "")),
                    1 if idx == 1 else 0,
                    1 if idx <= 5 else 0,
                    payout_amount,
                    lp,
                ),
            )

            stats_after = conn.execute(
                "SELECT career_level FROM user_career_stats WHERE user_email = ?",
                (normalized_email,),
            ).fetchone()
            current_level = int((stats_after["career_level"] if stats_after else prior_levels.get(normalized_email, 1)) or 1)
            previous_level = int(prior_levels.get(normalized_email, 1) or 1)
            if current_level > previous_level:
                deferred_notifications.append(
                    {
                        "notification_key": "level_up",
                        "message": f"Level up! You reached Level {current_level}",
                        "tournament_id": int(tournament_id),
                        "entry_id": int(row["entry_id"]),
                        "user_email": normalized_email,
                        "metadata": {"new_level": current_level, "previous_level": previous_level},
                    }
                )
                prior_levels[normalized_email] = current_level

            awarded_keys: list[str] = []
            if idx == 1 and int(prior_wins.get(normalized_email, 0) or 0) == 0:
                if _grant_badge_award(
                    conn,
                    user_email=normalized_email,
                    award_key="first_win",
                    award_name="First Win",
                    context={"tournament_id": int(tournament_id), "court_tier": str(tournament.get("court_tier", ""))},
                ):
                    awarded_keys.append("first_win")

            if idx == 1 and _current_win_streak(conn, normalized_email) >= 3:
                if _grant_badge_award(
                    conn,
                    user_email=normalized_email,
                    award_key="hot_streak",
                    award_name="Hot Streak",
                    context={"tournament_id": int(tournament_id), "streak": _current_win_streak(conn, normalized_email)},
                ):
                    awarded_keys.append("hot_streak")

            if idx == 1:
                tiers = _winner_tiers_last_n_days(conn, normalized_email, days=31)
                tiers.add(str(tournament.get("court_tier", "")))
                if {"Open", "Pro", "Elite"}.issubset(tiers):
                    if _grant_badge_award(
                        conn,
                        user_email=normalized_email,
                        award_key="triple_crown",
                        award_name="Triple Crown",
                        context={"tournament_id": int(tournament_id), "tiers": sorted(tiers)},
                    ):
                        awarded_keys.append("triple_crown")

            if bool(entry_has_five_by_five.get(int(row["entry_id"]), False)):
                if _grant_badge_award(
                    conn,
                    user_email=normalized_email,
                    award_key="five_by_five_club",
                    award_name="5x5 Club",
                    context={"tournament_id": int(tournament_id), "entry_id": int(row["entry_id"])},
                ):
                    awarded_keys.append("five_by_five_club")

            if idx == 1:
                winner_has_legend = bool(entry_has_legend.get(int(row["entry_id"]), False))
                field_has_legend = any(bool(v) for eid, v in entry_has_legend.items() if int(eid) != int(row["entry_id"]))
                if (not winner_has_legend) and field_has_legend:
                    if _grant_badge_award(
                        conn,
                        user_email=normalized_email,
                        award_key="legend_slayer",
                        award_name="Legend Slayer",
                        context={"tournament_id": int(tournament_id)},
                    ):
                        awarded_keys.append("legend_slayer")

            if idx == 1 and str(tournament.get("court_tier", "")) == "Championship":
                now_utc = datetime.now(timezone.utc)
                season_label = f"{now_utc.year} S{((now_utc.month - 1) // 3) + 1}"
                roster_row = next((p for p in parsed_entries if int(p.get("entry_id", 0) or 0) == int(row["entry_id"])), {})
                conn.execute(
                    """
                    INSERT INTO championship_history
                        (season_label, tournament_id, winner_email, winner_display_name, winning_score, payout_amount, roster_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (
                        season_label,
                        int(tournament_id),
                        normalized_email,
                        str(row.get("display_name", "")),
                        float(row.get("total_score", 0.0) or 0.0),
                        payout_amount,
                        json.dumps(list(roster_row.get("roster") or [])),
                    ),
                )
                if _grant_badge_award(
                    conn,
                    user_email=normalized_email,
                    award_key="championship_winner",
                    award_name="Championship Winner",
                    context={"tournament_id": int(tournament_id), "season_label": season_label},
                ):
                    awarded_keys.append("championship_winner")

            # --- Phase 3 additional badges ---

            # Century Club — 100+ total FP
            if float(row.get("total_score", 0.0) or 0.0) >= 100.0:
                if _grant_badge_award(
                    conn,
                    user_email=normalized_email,
                    award_key="century_club",
                    award_name="Century Club",
                    context={"tournament_id": int(tournament_id), "score": float(row.get("total_score", 0.0))},
                ):
                    awarded_keys.append("century_club")

            # Blowout Artist — win by 20+ FP
            if idx == 1 and len(scored_entries) >= 2:
                margin = float(row.get("total_score", 0.0) or 0.0) - float(scored_entries[1].get("total_score", 0.0) or 0.0)
                if margin >= 20.0:
                    if _grant_badge_award(
                        conn,
                        user_email=normalized_email,
                        award_key="blowout_artist",
                        award_name="Blowout Artist",
                        context={"tournament_id": int(tournament_id), "margin": round(margin, 2)},
                    ):
                        awarded_keys.append("blowout_artist")

            # Photo Finish — win by <1.0 FP
            if idx == 1 and len(scored_entries) >= 2:
                margin_pf = float(row.get("total_score", 0.0) or 0.0) - float(scored_entries[1].get("total_score", 0.0) or 0.0)
                if 0 < margin_pf < 1.0:
                    if _grant_badge_award(
                        conn,
                        user_email=normalized_email,
                        award_key="photo_finish",
                        award_name="Photo Finish",
                        context={"tournament_id": int(tournament_id), "margin": round(margin_pf, 2)},
                    ):
                        awarded_keys.append("photo_finish")

            # Diamond Manager — win spending <$42K active cap
            if idx == 1:
                entry_row = next((p for p in parsed_entries if int(p.get("entry_id", 0) or 0) == int(row["entry_id"])), {})
                roster = list(entry_row.get("roster") or [])
                active_salary = sum(int(p.get("salary", 0) or 0) for p in roster if not bool(p.get("is_legend", False)))
                if active_salary < 42000:
                    if _grant_badge_award(
                        conn,
                        user_email=normalized_email,
                        award_key="diamond_manager",
                        award_name="Diamond Manager",
                        context={"tournament_id": int(tournament_id), "active_salary": active_salary},
                    ):
                        awarded_keys.append("diamond_manager")

            # Underdog King — win with 0 Superstar-tier players
            if idx == 1:
                entry_row_ug = next((p for p in parsed_entries if int(p.get("entry_id", 0) or 0) == int(row["entry_id"])), {})
                roster_ug = list(entry_row_ug.get("roster") or [])
                has_superstar = any(str(p.get("rarity_tier", "")).strip() == "Superstar" for p in roster_ug)
                if not has_superstar:
                    if _grant_badge_award(
                        conn,
                        user_email=normalized_email,
                        award_key="underdog_king",
                        award_name="Underdog King",
                        context={"tournament_id": int(tournament_id)},
                    ):
                        awarded_keys.append("underdog_king")

            # Career-level milestone badges (LP thresholds)
            career_row = conn.execute(
                "SELECT lifetime_lp, lifetime_entries, lifetime_wins, lifetime_earnings FROM user_career_stats WHERE user_email = ?",
                (normalized_email,),
            ).fetchone()
            if career_row:
                c_lp = int(career_row["lifetime_lp"] or 0)
                c_entries = int(career_row["lifetime_entries"] or 0)
                c_wins = int(career_row["lifetime_wins"] or 0)
                c_earnings = float(career_row["lifetime_earnings"] or 0.0)

                if c_entries >= 50:
                    if _grant_badge_award(conn, user_email=normalized_email, award_key="grinder", award_name="Grinder",
                                          context={"lifetime_entries": c_entries}):
                        awarded_keys.append("grinder")
                if c_earnings >= 1000.0:
                    if _grant_badge_award(conn, user_email=normalized_email, award_key="money_maker", award_name="Money Maker",
                                          context={"lifetime_earnings": c_earnings}):
                        awarded_keys.append("money_maker")
                if c_lp >= 500:
                    if _grant_badge_award(conn, user_email=normalized_email, award_key="lp_climber", award_name="LP Climber",
                                          context={"lifetime_lp": c_lp}):
                        awarded_keys.append("lp_climber")
                if c_lp >= 1000:
                    if _grant_badge_award(conn, user_email=normalized_email, award_key="all_star_rank", award_name="All-Star Rank",
                                          context={"lifetime_lp": c_lp}):
                        awarded_keys.append("all_star_rank")
                if c_lp >= 2000:
                    if _grant_badge_award(conn, user_email=normalized_email, award_key="legend_rank", award_name="Legend Rank",
                                          context={"lifetime_lp": c_lp}):
                        awarded_keys.append("legend_rank")
                if c_lp >= 5000:
                    if _grant_badge_award(conn, user_email=normalized_email, award_key="goat_rank", award_name="GOAT Rank",
                                          context={"lifetime_lp": c_lp}):
                        awarded_keys.append("goat_rank")

                # Hall of Fame badge — 2,000+ LP, 5+ Championships, 50+ wins
                if c_lp >= 2000 and c_wins >= 50:
                    champ_count_row = conn.execute(
                        "SELECT COUNT(*) AS cnt FROM championship_history WHERE winner_email = ?",
                        (normalized_email,),
                    ).fetchone()
                    champ_count = int((champ_count_row["cnt"] if champ_count_row else 0) or 0)
                    if champ_count >= 5:
                        if _grant_badge_award(conn, user_email=normalized_email, award_key="hall_of_fame", award_name="Hall of Fame",
                                              context={"lifetime_lp": c_lp, "championship_wins": champ_count, "lifetime_wins": c_wins}):
                            awarded_keys.append("hall_of_fame")

            if awarded_keys:
                deferred_events.append(
                    {
                        "event_type": "awards.badges_granted",
                        "message": f"Granted {len(awarded_keys)} badge(s) to {normalized_email}",
                        "tournament_id": int(tournament_id),
                        "user_email": normalized_email,
                        "metadata": {"award_keys": awarded_keys, "entry_id": int(row["entry_id"]), "rank": int(idx)},
                    }
                )
                deferred_notifications.append(
                    {
                        "notification_key": "badges_earned",
                        "message": f"You earned {len(awarded_keys)} badge(s): {', '.join(awarded_keys)}",
                        "tournament_id": int(tournament_id),
                        "entry_id": int(row["entry_id"]),
                        "user_email": normalized_email,
                        "metadata": {"badge_keys": awarded_keys},
                    }
                )

            if idx == 1 and float(tournament.get("entry_fee", 0.0) or 0.0) > 0 and payout_amount > 0:
                status = get_user_connect_status(normalized_email)
                account_id = str(status.get("stripe_connect_account_id", "") or "")
                onboarding_status = str(status.get("onboarding_status", "") or "")
                if not account_id and onboarding_status in {"", "not_started"}:
                    upsert_user_connect_status(
                        normalized_email,
                        stripe_connect_account_id="",
                        onboarding_status="pending_winner_onboarding",
                    )
                    deferred_notifications.append(
                        {
                            "notification_key": "connect_onboarding_required",
                            "message": "You won a paid tournament. Complete Stripe Connect onboarding to receive payouts.",
                            "tournament_id": int(tournament_id),
                            "entry_id": int(row["entry_id"]),
                            "user_email": normalized_email,
                            "metadata": {"reason": "first_paid_win"},
                        }
                    )

        conn.execute(
            """
            UPDATE tournaments
            SET status='resolved', raw_seed=?, seed_int=?, environment_json=?, resolved_at=datetime('now')
            WHERE tournament_id = ?
            """,
            (
                raw_seed,
                int(seed_int),
                json.dumps(env),
                int(tournament_id),
            ),
        )

        conn.commit()

        deferred_events.append(
            {
                "event_type": "tournament.resolved",
                "message": f"Tournament #{tournament_id} resolved",
                "tournament_id": tournament_id,
                "metadata": {
                    "entries": len(scored_entries),
                    "sport": sport_code,
                    "environment": env,
                    "payout": payout,
                },
            }
        )

        for rank_idx, row in enumerate(scored_entries, start=1):
            deferred_notifications.append(
                {
                    "notification_key": "results_posted",
                    "message": f"Results are in for tournament #{tournament_id}. Score: {row['total_score']}",
                    "tournament_id": tournament_id,
                    "entry_id": row["entry_id"],
                    "user_email": row.get("user_email", ""),
                    "metadata": {
                        "rank": rank_idx,
                        "score": row["total_score"],
                    },
                }
            )

        final_result = {
            "success": True,
            "status": "resolved",
            "tournament_id": int(tournament_id),
            "entries": len(scored_entries),
            "sport": sport_code,
            "seed": raw_seed,
            "environment": env,
            "payout": payout,
        }

    for item in deferred_events:
        log_event(**item)
    for item in deferred_notifications:
        key = str(item.get("notification_key", "") or "")
        if key == "results_posted":
            notify_results_posted(
                int(item.get("tournament_id", 0) or 0),
                entry_id=item.get("entry_id"),
                user_email=item.get("user_email"),
                rank=(item.get("metadata") or {}).get("rank"),
            )
            continue
        if key == "badges_earned":
            notify_badges_earned(
                str(item.get("user_email", "") or ""),
                list((item.get("metadata") or {}).get("badge_keys") or []),
                tournament_id=item.get("tournament_id"),
            )
            continue
        if key == "level_up":
            notify_level_up(
                str(item.get("user_email", "") or ""),
                int((item.get("metadata") or {}).get("new_level", 1) or 1),
                tournament_id=item.get("tournament_id"),
            )
            continue
        send_notification(**item)
    return final_result or {"success": False, "error": "Resolve failed"}
