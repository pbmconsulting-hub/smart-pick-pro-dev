"""Staged score reveal engine for Championship Night.

Implements the 30-minute phased Q1→Q4→Final reveal experience
described in Section XVI of the master plan.

Phase timeline (offset from lock time):
    +0 min  — Q1: Points only
    +7 min  — Q2: + Rebounds, Assists
    +14 min — Halftime: Updated leaderboard + full analysis
    +20 min — Q3: + Steals, Blocks
    +25 min — Q4: + Turnovers, 3PM bonus
    +30 min — Final: Bonuses + Penalties + Final scores + Champion
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Phase definitions
# ---------------------------------------------------------------------------

REVEAL_PHASES: list[dict[str, Any]] = [
    {
        "phase": "Q1",
        "offset_minutes": 0,
        "stats_revealed": ["points"],
        "label": "Q1 — Scoring Revealed",
        "joseph_commentary": "The scoring is IN! Let's see who came to play tonight!",
    },
    {
        "phase": "Q2",
        "offset_minutes": 7,
        "stats_revealed": ["points", "rebounds", "assists"],
        "label": "Q2 — Rebounds & Assists Added",
        "joseph_commentary": "Glass cleaners EATING tonight! The playmakers are making their mark!",
    },
    {
        "phase": "Halftime",
        "offset_minutes": 14,
        "stats_revealed": ["points", "rebounds", "assists"],
        "label": "Halftime — Updated Leaderboard",
        "joseph_commentary": "Halftime analysis — here's where we stand. Some rosters are COOKING, others are in trouble!",
    },
    {
        "phase": "Q3",
        "offset_minutes": 20,
        "stats_revealed": ["points", "rebounds", "assists", "steals", "blocks"],
        "label": "Q3 — Defense Revealed",
        "joseph_commentary": "DEFENSE wins championships! The steals and blocks are reshuffling the board!",
    },
    {
        "phase": "Q4",
        "offset_minutes": 25,
        "stats_revealed": ["points", "rebounds", "assists", "steals", "blocks", "turnovers", "threes"],
        "label": "Q4 — Turnovers & Threes Added",
        "joseph_commentary": "Turnovers are KILLING some lineups! But those three-pointers are keeping others alive!",
    },
    {
        "phase": "Final",
        "offset_minutes": 30,
        "stats_revealed": ["points", "rebounds", "assists", "steals", "blocks", "turnovers", "threes"],
        "include_bonuses": True,
        "include_penalties": True,
        "label": "Final — Bonuses, Penalties & Champion Crowned",
        "joseph_commentary": "YOUR CHAMPION IS... 🏆🏆🏆",
    },
]

ALL_STAT_KEYS = ["points", "rebounds", "assists", "steals", "blocks", "turnovers", "threes"]


def get_current_phase(lock_time: datetime, now: datetime | None = None) -> dict[str, Any]:
    """Determine which reveal phase is active given lock_time and current time.

    Returns the phase dict augmented with ``is_final`` and ``elapsed_minutes``.
    """
    now = now or datetime.now(timezone.utc)

    if lock_time.tzinfo is None:
        lock_time = lock_time.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    elapsed = (now - lock_time).total_seconds() / 60.0

    if elapsed < 0:
        return {
            "phase": "Pre-Lock",
            "offset_minutes": 0,
            "stats_revealed": [],
            "label": "Tournament not yet locked",
            "joseph_commentary": "Hold tight — we haven't locked yet!",
            "is_final": False,
            "elapsed_minutes": round(elapsed, 1),
        }

    current = REVEAL_PHASES[0]
    for phase in REVEAL_PHASES:
        if elapsed >= phase["offset_minutes"]:
            current = phase
        else:
            break

    result = dict(current)
    result["is_final"] = current["phase"] == "Final"
    result["elapsed_minutes"] = round(elapsed, 1)
    return result


def get_next_phase(lock_time: datetime, now: datetime | None = None) -> dict[str, Any] | None:
    """Return the next upcoming phase, or None if Final has been reached."""
    now = now or datetime.now(timezone.utc)

    if lock_time.tzinfo is None:
        lock_time = lock_time.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    elapsed = (now - lock_time).total_seconds() / 60.0

    for phase in REVEAL_PHASES:
        if elapsed < phase["offset_minutes"]:
            result = dict(phase)
            result["minutes_until"] = round(phase["offset_minutes"] - elapsed, 1)
            return result
    return None


def filter_scores_for_phase(
    sim_results: dict[str, dict],
    phase: dict[str, Any],
) -> dict[str, dict]:
    """Filter simulated player scores to only show stats revealed in this phase.

    For each player, only stats in ``phase["stats_revealed"]`` are included.
    Bonuses/penalties are only included when the phase specifies them.
    """
    revealed = set(phase.get("stats_revealed") or [])
    include_bonuses = bool(phase.get("include_bonuses", False))
    include_penalties = bool(phase.get("include_penalties", False))

    filtered: dict[str, dict] = {}
    for pid, scores in sim_results.items():
        entry: dict[str, Any] = {}
        partial_fp = 0.0

        for stat_key in ALL_STAT_KEYS:
            if stat_key in revealed:
                val = scores.get(stat_key, 0)
                entry[stat_key] = val
                partial_fp += _stat_fp(stat_key, val)
            else:
                entry[stat_key] = "?"

        entry["partial_fp"] = round(partial_fp, 2)

        if include_bonuses:
            entry["bonuses"] = scores.get("bonuses", {"total": 0.0, "triggered": []})
            partial_fp += float((scores.get("bonuses") or {}).get("total", 0.0))
        else:
            entry["bonuses"] = {"total": "?", "triggered": []}

        if include_penalties:
            entry["penalties"] = scores.get("penalties", {"total": 0.0, "triggered": []})
            partial_fp += float((scores.get("penalties") or {}).get("total", 0.0))
        else:
            entry["penalties"] = {"total": "?", "triggered": []}

        if phase.get("phase") == "Final":
            entry["total_fp"] = float(scores.get("total_fp", 0.0))
        else:
            entry["total_fp"] = round(partial_fp, 2)

        filtered[pid] = entry
    return filtered


def compute_partial_leaderboard(
    entries: list[dict],
    filtered_scores: dict[str, dict],
) -> list[dict]:
    """Compute a partial leaderboard from filtered (phase-restricted) scores.

    Each entry dict should have ``roster`` (list of players with ``player_id``)
    and metadata like ``entry_id``, ``user_email``, ``display_name``.
    """
    board: list[dict] = []
    for entry in entries:
        roster = entry.get("roster") or []
        total = 0.0
        for player in roster:
            pid = str(player.get("player_id", ""))
            score = filtered_scores.get(pid, {})
            total += float(score.get("total_fp", 0.0))
        board.append({
            "entry_id": entry.get("entry_id"),
            "user_email": entry.get("user_email", ""),
            "display_name": entry.get("display_name", ""),
            "partial_score": round(total, 2),
        })
    board.sort(key=lambda r: -r["partial_score"])
    for idx, row in enumerate(board, start=1):
        row["rank"] = idx
    return board


# ---------------------------------------------------------------------------
# Internal scoring helpers (mirrors tournament scoring weights)
# ---------------------------------------------------------------------------

_STAT_WEIGHTS = {
    "points": 1.0,
    "rebounds": 1.2,
    "assists": 1.5,
    "steals": 3.0,
    "blocks": 3.0,
    "threes": 0.5,
    "turnovers": -1.5,
}


def _stat_fp(stat_key: str, value: Any) -> float:
    """Compute fantasy points for a single stat."""
    try:
        return float(value) * _STAT_WEIGHTS.get(stat_key, 0.0)
    except (TypeError, ValueError):
        return 0.0
