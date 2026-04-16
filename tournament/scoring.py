"""Tournament fantasy scoring, bonuses, and penalties."""

from __future__ import annotations

import random


def calculate_fantasy_points(line: dict) -> float:
    """Compute base fantasy points from a simulated stat line."""
    points = float(line.get("points", 0)) * 1.0
    rebounds = float(line.get("rebounds", 0)) * 1.2
    assists = float(line.get("assists", 0)) * 1.5
    steals = float(line.get("steals", 0)) * 3.0
    blocks = float(line.get("blocks", 0)) * 3.0
    threes_bonus = float(line.get("threes", 0)) * 0.5
    turnovers = float(line.get("turnovers", 0)) * -1.5
    return round(points + rebounds + assists + steals + blocks + threes_bonus + turnovers, 2)


def check_bonuses(line: dict) -> dict:
    """Return triggered bonus categories and cumulative bonus points."""
    categories = {
        "points": int(line.get("points", 0)),
        "rebounds": int(line.get("rebounds", 0)),
        "assists": int(line.get("assists", 0)),
        "steals": int(line.get("steals", 0)),
        "blocks": int(line.get("blocks", 0)),
    }

    double_digit_count = sum(1 for v in categories.values() if v >= 10)
    bonus_total = 0.0
    triggered: list[str] = []

    if double_digit_count >= 3:
        bonus_total += 5.0
        triggered.append("triple_double")
    elif double_digit_count >= 2:
        bonus_total += 2.0
        triggered.append("double_double")

    pts = categories["points"]
    if pts >= 50:
        bonus_total += 7.0
        triggered.append("points_50")
    elif pts >= 40:
        bonus_total += 3.0
        triggered.append("points_40")

    if categories["rebounds"] >= 20:
        bonus_total += 3.0
        triggered.append("rebounds_20")

    if categories["assists"] >= 15:
        bonus_total += 3.0
        triggered.append("assists_15")

    if sum(1 for v in categories.values() if v >= 5) >= 5:
        bonus_total += 10.0
        triggered.append("five_by_five")

    return {"total": round(bonus_total, 2), "triggered": triggered}


def check_penalties(profile: dict, seed: int) -> dict:
    """Apply ejection and foul-out random penalties with deterministic seed."""
    rng = random.Random(seed)
    tech_rate = float(profile.get("tech_rate", 0.01))
    foul_prone = bool(profile.get("foul_prone", False))

    ejection_prob = min(0.02, max(0.001, tech_rate))
    foul_out_prob = 0.03 if foul_prone else 0.008

    penalty_total = 0.0
    triggered: list[str] = []

    if rng.random() < ejection_prob:
        penalty_total -= 10.0
        triggered.append("ejection")

    if rng.random() < foul_out_prob:
        penalty_total -= 2.0
        triggered.append("foul_out")

    return {"total": round(penalty_total, 2), "triggered": triggered}


def score_player_total(profile: dict, line: dict, seed: int) -> dict:
    """Score one player line, including base FP, bonuses, and penalties."""
    fp = calculate_fantasy_points(line)
    bonuses = check_bonuses(line)
    penalties = check_penalties(profile, seed)
    total_fp = round(fp + bonuses["total"] + penalties["total"], 2)
    return {
        **line,
        "fantasy_points": fp,
        "bonuses": bonuses,
        "penalties": penalties,
        "total_fp": total_fp,
    }


def tiebreak_key(entry: dict) -> tuple:
    """Sort key for tie resolution: high ceiling, uniqueness, frugality, early entry."""
    highest_player_score = float(entry.get("highest_player_score", 0.0))
    unique_players = int(entry.get("unique_players", 0))
    salary_used = int(entry.get("salary_used", 0))
    created_at = str(entry.get("created_at", ""))
    return (-highest_player_score, -unique_players, salary_used, created_at)
