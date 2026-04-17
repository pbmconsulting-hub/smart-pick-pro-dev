"""Static Hall of Fame legend pool for tournaments."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime

LEGEND_PROFILES = [
    {"player_id": "L001", "player_name": "Michael Jordan", "position": "SG", "legend_era": "90s", "overall_rating": 99, "salary": 15000, "archetype": "Elite Scorer"},
    {"player_id": "L002", "player_name": "LeBron James Peak", "position": "SF", "legend_era": "2010s", "overall_rating": 99, "salary": 15000, "archetype": "Unicorn"},
    {"player_id": "L003", "player_name": "Kobe Bryant", "position": "SG", "legend_era": "2000s", "overall_rating": 97, "salary": 14500, "archetype": "Elite Scorer"},
    {"player_id": "L004", "player_name": "Shaquille ONeal", "position": "C", "legend_era": "2000s", "overall_rating": 97, "salary": 14500, "archetype": "Glass Cleaner"},
    {"player_id": "L005", "player_name": "Stephen Curry Prime", "position": "PG", "legend_era": "2010s", "overall_rating": 96, "salary": 14000, "archetype": "Sharpshooter"},
    {"player_id": "L006", "player_name": "Tim Duncan", "position": "PF", "legend_era": "2000s", "overall_rating": 96, "salary": 14000, "archetype": "Two-Way Star"},
    {"player_id": "L007", "player_name": "Magic Johnson", "position": "PG", "legend_era": "80s", "overall_rating": 96, "salary": 14000, "archetype": "Floor General"},
    {"player_id": "L008", "player_name": "Kareem Abdul-Jabbar", "position": "C", "legend_era": "80s", "overall_rating": 96, "salary": 14000, "archetype": "Elite Scorer"},
    {"player_id": "L009", "player_name": "Wilt Chamberlain", "position": "C", "legend_era": "60s", "overall_rating": 98, "salary": 14500, "archetype": "Unicorn"},
    {"player_id": "L010", "player_name": "Larry Bird", "position": "SF", "legend_era": "80s", "overall_rating": 95, "salary": 13500, "archetype": "Sharpshooter"},
    {"player_id": "L011", "player_name": "Hakeem Olajuwon", "position": "C", "legend_era": "90s", "overall_rating": 95, "salary": 13500, "archetype": "Two-Way Star"},
    {"player_id": "L012", "player_name": "Kevin Garnett", "position": "PF", "legend_era": "2000s", "overall_rating": 94, "salary": 13000, "archetype": "Two-Way Star"},
    {"player_id": "L013", "player_name": "Charles Barkley", "position": "PF", "legend_era": "90s", "overall_rating": 93, "salary": 13000, "archetype": "Glass Cleaner"},
    {"player_id": "L014", "player_name": "Allen Iverson", "position": "PG", "legend_era": "2000s", "overall_rating": 92, "salary": 12500, "archetype": "Boom/Bust"},
    {"player_id": "L015", "player_name": "Julius Erving", "position": "SF", "legend_era": "80s", "overall_rating": 92, "salary": 12500, "archetype": "Elite Scorer"},
    {"player_id": "L016", "player_name": "Dirk Nowitzki", "position": "PF", "legend_era": "2000s", "overall_rating": 92, "salary": 12500, "archetype": "Sharpshooter"},
    {"player_id": "L017", "player_name": "Scottie Pippen", "position": "SF", "legend_era": "90s", "overall_rating": 91, "salary": 12000, "archetype": "Two-Way Star"},
    {"player_id": "L018", "player_name": "Isiah Thomas", "position": "PG", "legend_era": "80s", "overall_rating": 91, "salary": 12000, "archetype": "Floor General"},
    {"player_id": "L019", "player_name": "Patrick Ewing", "position": "C", "legend_era": "90s", "overall_rating": 90, "salary": 12000, "archetype": "Glass Cleaner"},
    {"player_id": "L020", "player_name": "Bill Russell", "position": "C", "legend_era": "60s", "overall_rating": 93, "salary": 12500, "archetype": "Lockdown Defender"},
]


def get_monthly_legends(month: int) -> list[dict]:
    """Return the 8 legends for a month with Jordan and LeBron always included."""
    if month == 1:
        return deepcopy(LEGEND_PROFILES)

    fixed_ids = {"L001", "L002"}
    rotatable = [l for l in LEGEND_PROFILES if l["player_id"] not in fixed_ids]
    start = ((month - 1) * 6) % len(rotatable)
    rotated = rotatable[start:] + rotatable[:start]
    selected = [l for l in LEGEND_PROFILES if l["player_id"] in fixed_ids] + rotated[:6]
    return deepcopy(selected)


def get_legends_for_tier(month: int, *, has_legend_pass: bool = False, is_premium: bool = False) -> list[dict]:
    """Return the legends a user can access based on their subscription tier.

    Legend Pass gate logic (Section III of the master plan):
      - Free users: no legends (empty list)
      - Premium ($9.99/mo) only: 3 cheapest legends that month
      - Premium + Legend Pass ($14.98/mo total): all 8 available that month

    January = all 20 available regardless (holiday bonus).
    """
    if not is_premium:
        return []

    monthly = get_monthly_legends(month)

    if has_legend_pass:
        return monthly

    # Premium-only: 3 cheapest legends
    sorted_by_salary = sorted(monthly, key=lambda l: (l.get("salary", 0), l.get("player_id", "")))
    return deepcopy(sorted_by_salary[:3])
