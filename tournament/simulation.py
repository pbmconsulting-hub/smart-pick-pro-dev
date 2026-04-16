"""Tournament simulation wrappers using existing Engine A and Engine B."""

from __future__ import annotations

import hashlib
import random
import secrets
from typing import Any

from engine.game_prediction import (
    BLOWOUT_MARGIN_THRESHOLD,
    LEAGUE_AVG_DRTG,
    LEAGUE_AVG_ORTG,
    LEAGUE_AVG_PACE,
    _calculate_expected_possessions,
    _score_from_possession_model,
    _simulate_single_game,
)
from engine.simulation import run_quantum_matrix_simulation

STAT_TYPES = ["points", "rebounds", "assists", "steals", "blocks", "turnovers", "threes"]

STAT_CV = {
    "points": 0.25,
    "rebounds": 0.30,
    "assists": 0.35,
    "steals": 0.50,
    "blocks": 0.55,
    "turnovers": 0.35,
    "threes": 0.40,
}


def generate_tournament_seed() -> tuple[str, int]:
    """Generate a cryptographically strong seed for post-lock simulation."""
    raw_seed = secrets.token_hex(32)
    seed_int = int(hashlib.sha256(raw_seed.encode("utf-8")).hexdigest()[:8], 16)
    return raw_seed, seed_int


def _classify_environment(margin: float, total: float, went_to_ot: bool) -> str:
    if went_to_ot:
        return "Overtime Thriller"
    if margin > 20:
        return "Blowout"
    if total > 235:
        return "Shootout"
    if total < 200:
        return "Defensive Grind"
    if margin < 5:
        return "Nail-Biter"
    return "Standard Game"


def simulate_tournament_environment(seed_int: int) -> dict[str, Any]:
    """Use Engine A to build one global environment for a tournament."""
    random.seed(seed_int)

    home_ortg = random.gauss(LEAGUE_AVG_ORTG, 3.0)
    away_ortg = random.gauss(LEAGUE_AVG_ORTG, 3.0)
    home_drtg = random.gauss(LEAGUE_AVG_DRTG, 3.0)
    away_drtg = random.gauss(LEAGUE_AVG_DRTG, 3.0)
    home_pace = random.gauss(LEAGUE_AVG_PACE, 2.0)
    away_pace = random.gauss(LEAGUE_AVG_PACE, 2.0)

    expected_poss = _calculate_expected_possessions(home_pace, away_pace)

    home_adj_ortg = home_ortg * (LEAGUE_AVG_DRTG / max(away_drtg, 95.0))
    away_adj_ortg = away_ortg * (LEAGUE_AVG_DRTG / max(home_drtg, 95.0))

    home_base = _score_from_possession_model(home_adj_ortg, expected_poss)
    away_base = _score_from_possession_model(away_adj_ortg, expected_poss)

    home_score, away_score, went_to_ot = _simulate_single_game(
        home_adj_ortg=home_adj_ortg,
        home_drtg=home_drtg,
        home_pace=home_pace,
        away_adj_ortg=away_adj_ortg,
        away_drtg=away_drtg,
        away_pace=away_pace,
        expected_possessions=expected_poss,
        home_base_score=home_base,
        away_base_score=away_base,
    )

    margin = abs(home_score - away_score)
    total = home_score + away_score

    if margin > 20:
        blowout_risk = 0.65
        pace_adj = 0.95
    elif margin > BLOWOUT_MARGIN_THRESHOLD:
        blowout_risk = 0.40
        pace_adj = 0.97
    elif margin > 8:
        blowout_risk = 0.20
        pace_adj = 1.00
    elif went_to_ot:
        blowout_risk = 0.05
        pace_adj = 1.08
    else:
        blowout_risk = 0.10
        pace_adj = 1.00

    if total > 235:
        pace_adj *= 1.04
    elif total < 200:
        pace_adj *= 0.96

    return {
        "home_score": round(home_score),
        "away_score": round(away_score),
        "went_to_ot": bool(went_to_ot),
        "margin": round(margin),
        "total": round(total),
        "blowout_risk_factor": round(blowout_risk, 3),
        "pace_adjustment_factor": round(pace_adj, 4),
        "vegas_spread": round(home_score - away_score, 1),
        "game_total": round(total, 1),
        "environment_label": _classify_environment(margin, total, bool(went_to_ot)),
    }


def _load_recent_stat_logs(profile: dict, stat_type: str) -> list[float]:
    """Optional bridge to existing cached logs; safe fallback to empty list."""
    stat_col = {
        "points": "points",
        "rebounds": "rebounds",
        "assists": "assists",
        "steals": "steals",
        "blocks": "blocks",
        "turnovers": "turnovers",
        "threes": "threes",
    }[stat_type]

    try:
        from tracking.database import load_player_game_logs_from_db  # lazy import

        rows = load_player_game_logs_from_db(str(profile.get("player_id", "")), days=90)
        values = []
        for row in rows:
            try:
                values.append(float(row.get(stat_col, 0.0) or 0.0))
            except (TypeError, ValueError):
                continue
        return values
    except Exception:
        return []


def simulate_player_stat(
    profile: dict,
    stat_type: str,
    env: dict,
    seed: int,
    number_of_simulations: int = 100,
) -> int:
    """Simulate one player stat with Engine B and choose clutch-based percentile."""
    stat_means = {
        "points": float(profile.get("ppg", 0.0)),
        "rebounds": float(profile.get("rpg", 0.0)),
        "assists": float(profile.get("apg", 0.0)),
        "steals": float(profile.get("spg", 0.0)),
        "blocks": float(profile.get("bpg", 0.0)),
        "turnovers": float(profile.get("tpg", 0.0)),
        "threes": float(profile.get("threes_pg", 0.0)),
    }
    mean = stat_means.get(stat_type, 0.0)
    if mean <= 0:
        return 0

    consistency = int(profile.get("attr_consistency", 50))
    cv_modifier = max(0.5, min(1.5, 1.0 + (50 - consistency) * 0.008))
    std_dev = max(0.5, mean * STAT_CV[stat_type] * cv_modifier)

    result = run_quantum_matrix_simulation(
        projected_stat_average=mean,
        stat_standard_deviation=std_dev,
        prop_line=0.0,
        number_of_simulations=number_of_simulations,
        blowout_risk_factor=float(env["blowout_risk_factor"]),
        pace_adjustment_factor=float(env["pace_adjustment_factor"]),
        matchup_adjustment_factor=1.0,
        home_away_adjustment=0.0,
        rest_adjustment_factor=1.0,
        stat_type=stat_type,
        projected_minutes=float(profile.get("minutes_pg", 30.0)),
        minutes_std=5.0,
        recent_game_logs=_load_recent_stat_logs(profile, stat_type),
        random_seed=int(seed),
        enable_fatigue_curve=True,
        vegas_spread=float(env["vegas_spread"]),
        game_total=float(env["game_total"]),
    )

    simulated = list(result.get("simulated_results", []))
    if not simulated:
        return max(0, int(round(mean)))
    sorted_results = sorted(simulated)

    rng = random.Random(seed + 99991)
    clutch = int(profile.get("attr_clutch", 50))
    low_pct = max(5, 50 - clutch // 2)
    high_pct = min(95, 50 + clutch // 2)

    hot_cold_label = str(profile.get("hot_cold_label", "neutral"))
    if hot_cold_label == "hot":
        low_pct = min(90, low_pct + 8)
        high_pct = min(98, high_pct + 5)
    elif hot_cold_label == "cold":
        low_pct = max(2, low_pct - 5)
        high_pct = max(40, high_pct - 8)

    chosen_pct = rng.randint(low_pct, high_pct)
    idx = int(chosen_pct / 100 * len(sorted_results))
    idx = max(0, min(len(sorted_results) - 1, idx))
    return max(0, int(round(sorted_results[idx])))


def simulate_player_full_line(profile: dict, env: dict, tournament_seed: int) -> dict[str, int]:
    """Simulate all tracked stat categories for one player."""
    player_hash = abs(hash(str(profile.get("player_id", "")))) % 100000
    base_seed = int(tournament_seed) + player_hash
    line: dict[str, int] = {}
    for idx, stat in enumerate(STAT_TYPES):
        line[stat] = simulate_player_stat(profile, stat, env, base_seed + (idx * 1000))
    return line
