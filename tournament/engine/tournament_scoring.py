"""
Tournament Scoring Engine (Phase 0)

Fantasy point calculation, bonuses, penalties for tournament entries.
"""

from typing import Dict, Any, List
from config import SCORING_CONFIG, BONUS_CONFIG, PENALTY_CONFIG


def calculate_fantasy_points(stat_line: Dict[str, int]) -> float:
    """
    Calculate base fantasy points from stat line (no bonuses).
    
    Stat line: {"points": X, "rebounds": Y, "assists": Z, ...}
    """
    fp = (
        stat_line.get("points", 0) * SCORING_CONFIG["points"] +
        stat_line.get("rebounds", 0) * SCORING_CONFIG["rebounds"] +
        stat_line.get("assists", 0) * SCORING_CONFIG["assists"] +
        stat_line.get("steals", 0) * SCORING_CONFIG["steals"] +
        stat_line.get("blocks", 0) * SCORING_CONFIG["blocks"] +
        stat_line.get("threes", 0) * SCORING_CONFIG["threes"] +
        stat_line.get("turnovers", 0) * SCORING_CONFIG["turnovers"]
    )
    return fp


def check_bonuses(stat_line: Dict[str, int]) -> Dict[str, Any]:
    """
    Check and award bonuses; return total bonus FP + breakdown.
    
    Returns:
        {
            "total": X,
            "bonuses": [
                {"name": "Double-Double", "fp": 2.0},
                ...
            ]
        }
    """
    bonuses_awarded = []
    total_bonus = 0.0
    
    points = stat_line.get("points", 0)
    rebounds = stat_line.get("rebounds", 0)
    assists = stat_line.get("assists", 0)
    steals = stat_line.get("steals", 0)
    blocks = stat_line.get("blocks", 0)
    
    # Count double-double categories (≥10)
    dd_count = sum([
        rebounds >= 10,
        assists >= 10,
        steals >= 10,
        blocks >= 10,
        points >= 10,  # Points also counts for DD
    ])
    
    # Triple-double replaces double-double
    if dd_count >= 3:
        bonuses_awarded.append({"name": "Triple-Double", "fp": BONUS_CONFIG["triple_double"]})
        total_bonus += BONUS_CONFIG["triple_double"]
    elif dd_count >= 2:
        bonuses_awarded.append({"name": "Double-Double", "fp": BONUS_CONFIG["double_double"]})
        total_bonus += BONUS_CONFIG["double_double"]
    
    # Points milestones
    if points >= 50:
        bonuses_awarded.append({"name": "50+ Points", "fp": BONUS_CONFIG["points_50"]})
        total_bonus += BONUS_CONFIG["points_50"]
    elif points >= 40:
        bonuses_awarded.append({"name": "40+ Points", "fp": BONUS_CONFIG["points_40"]})
        total_bonus += BONUS_CONFIG["points_40"]
    
    # Rebounds milestone
    if rebounds >= 20:
        bonuses_awarded.append({"name": "20+ Rebounds", "fp": BONUS_CONFIG["rebounds_20"]})
        total_bonus += BONUS_CONFIG["rebounds_20"]
    
    # Assists milestone
    if assists >= 15:
        bonuses_awarded.append({"name": "15+ Assists", "fp": BONUS_CONFIG["assists_15"]})
        total_bonus += BONUS_CONFIG["assists_15"]
    
    # 5×5 (5+ in 5 categories)
    categories_over_5 = sum([
        points >= 5,
        rebounds >= 5,
        assists >= 5,
        steals >= 5,
        blocks >= 5,
    ])
    if categories_over_5 >= 5:
        bonuses_awarded.append({"name": "5×5", "fp": BONUS_CONFIG["five_by_five"]})
        total_bonus += BONUS_CONFIG["five_by_five"]
    
    return {
        "total": total_bonus,
        "bonuses": bonuses_awarded,
    }


def check_penalties(player_profile: Any, seed: int) -> Dict[str, Any]:
    """
    Check and assess penalties (ejection, etc).
    Penalties are probabilistic based on player history.
    
    Returns:
        {
            "total": X,
            "penalties": [
                {"name": "Ejection", "fp": -10.0, "triggered": True},
                ...
            ]
        }
    """
    import random
    
    penalties_possible = []
    total_penalty = 0.0
    
    # Ejection (random, varies by player)
    random.seed(seed)
    base_ejection_prob = PENALTY_CONFIG["ejection_probability_base"]
    # Players with many technicals have higher ejection risk
    # Stub: assume 0.1% base for now
    ejection_prob = base_ejection_prob * (1 + random.random() * 0.5)  # 0.1% to 0.15%
    
    if random.random() < ejection_prob:
        penalties_possible.append({
            "name": "Ejection",
            "fp": PENALTY_CONFIG["ejection"],
            "triggered": True,
        })
        total_penalty += PENALTY_CONFIG["ejection"]
    else:
        penalties_possible.append({
            "name": "Ejection",
            "fp": PENALTY_CONFIG["ejection"],
            "triggered": False,
        })
    
    return {
        "total": total_penalty,
        "penalties": penalties_possible,
    }


def calculate_entry_score(roster: List[Any], sim_results: Dict[int, Dict[str, int]]) -> float:
    """
    Calculate total score for a tournament entry.
    
    Args:
        roster: List of player profiles in the entry
        sim_results: Dict {player_id: {"points": X, "rebounds": Y, ...}, ...}
    
    Returns:
        Total fantasy points (base + bonuses + penalties)
    """
    total_fp = 0.0
    
    for player_profile in roster:
        player_id = player_profile.player_id
        
        if player_id not in sim_results:
            continue
        
        stat_line = sim_results[player_id]
        
        # Base FP
        base_fp = calculate_fantasy_points(stat_line)
        
        # Bonuses
        bonuses = check_bonuses(stat_line)
        bonus_fp = bonuses["total"]
        
        # Penalties
        penalties = check_penalties(player_profile, player_id)
        penalty_fp = penalties["total"]
        
        player_total = base_fp + bonus_fp + penalty_fp
        total_fp += player_total
    
    return total_fp


if __name__ == "__main__":
    # Test
    sample_line = {
        "points": 42,
        "rebounds": 10,
        "assists": 8,
        "steals": 2,
        "blocks": 1,
        "turnovers": 2,
        "threes": 3,
    }
    
    base_fp = calculate_fantasy_points(sample_line)
    bonuses = check_bonuses(sample_line)
    penalties = check_penalties(None, 12345)
    
    print(f"✅ Base FP: {base_fp:.1f}")
    print(f"   Bonuses: +{bonuses['total']:.1f}")
    print(f"   Penalties: {penalties['total']:.1f}")
    print(f"   Total: {base_fp + bonuses['total'] + penalties['total']:.1f}")
