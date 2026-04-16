"""
Hall of Fame Legends Database (Phase 1)

20 hardcoded legendary players. Career-prime stats. Never change.

Legend tiers:
  - All legends: 90–99 OVR
  - Salary: $12,000–$15,000 (separate budget)
  - Archetype: Derived from prime-season stats
  - Rarity: 25% ownership cap (vs 33% for active players)
"""

from data.dataclasses import PlayerProfile
from engine.tournament_profiles import Archetype, RarityTier

# ============================================================================
# 20 LEGENDS (Career-Prime-Season Stats)
# ============================================================================

LEGENDS = [
    # 1. MICHAEL JORDAN - GoatStatus: ∞
    {
        "player_id": 900001,
        "name": "Michael Jordan",
        "position": "SG",
        "franchise": "CHI",
        "era": "90s",
        "overall": 99,
        "salary": 15000,
        "archetype": Archetype.ELITE_SCORER,
        
        # 1988-89: 32.5 PPG, 8.0 RPG, 8.0 APG, 2.9 SPG, 0.8 BPG
        "ppg": 32.5,
        "rpg": 8.0,
        "apg": 8.0,
        "spg": 2.9,
        "bpg": 0.8,
        "tpg": 2.8,
        "threes_pg": 0.9,
        "fg_pct": 0.540,
        "ft_pct": 0.850,
        "ts_pct": 0.603,
        "usage_rate": 0.38,
        "minutes_pg": 40.0,
        
        "attr_scoring": 99,
        "attr_playmaking": 80,
        "attr_rebounding": 75,
        "attr_defense": 96,
        "attr_consistency": 95,
        "attr_clutch": 99,
    },
    
    # 2. LEBRON JAMES (PRIME) - Greatest All-Around
    {
        "player_id": 900002,
        "name": "LeBron James (Peak)",
        "position": "SF/PF",
        "franchise": "MIA",
        "era": "2010s",
        "overall": 99,
        "salary": 15000,
        "archetype": Archetype.UNICORN,
        
        # 2011-12: 27.1 PPG, 8.0 RPG, 6.2 APG, 1.9 SPG, 0.8 BPG
        "ppg": 27.1,
        "rpg": 8.0,
        "apg": 6.2,
        "spg": 1.9,
        "bpg": 0.8,
        "tpg": 2.4,
        "threes_pg": 2.3,
        "fg_pct": 0.565,
        "ft_pct": 0.758,
        "ts_pct": 0.643,
        "usage_rate": 0.33,
        "minutes_pg": 37.5,
        
        "attr_scoring": 94,
        "attr_playmaking": 90,
        "attr_rebounding": 88,
        "attr_defense": 92,
        "attr_consistency": 94,
        "attr_clutch": 98,
    },
    
    # 3. KOBE BRYANT - Black Mamba
    {
        "player_id": 900003,
        "name": "Kobe Bryant",
        "position": "SG",
        "franchise": "LAL",
        "era": "2000s",
        "overall": 97,
        "salary": 14500,
        "archetype": Archetype.ELITE_SCORER,
        
        # 2005-06: 35.4 PPG, 5.2 RPG, 6.0 APG, 1.4 SPG, 0.4 BPG
        "ppg": 35.4,
        "rpg": 5.2,
        "apg": 6.0,
        "spg": 1.4,
        "bpg": 0.4,
        "tpg": 2.8,
        "threes_pg": 1.8,
        "fg_pct": 0.450,
        "ft_pct": 0.852,
        "ts_pct": 0.556,
        "usage_rate": 0.39,
        "minutes_pg": 40.9,
        
        "attr_scoring": 98,
        "attr_playmaking": 78,
        "attr_rebounding": 65,
        "attr_defense": 82,
        "attr_consistency": 92,
        "attr_clutch": 97,
    },
    
    # 4. SHAQUILLE O'NEAL - The Big Diesel
    {
        "player_id": 900004,
        "name": "Shaquille O'Neal",
        "position": "C",
        "franchise": "LAL",
        "era": "2000s",
        "overall": 97,
        "salary": 14500,
        "archetype": Archetype.GLASS_CLEANER,
        
        # 1999-2000: 29.7 PPG, 13.6 RPG, 3.0 APG, 0.5 SPG, 2.2 BPG
        "ppg": 29.7,
        "rpg": 13.6,
        "apg": 3.0,
        "spg": 0.5,
        "bpg": 2.2,
        "tpg": 2.5,
        "threes_pg": 0.0,
        "fg_pct": 0.574,
        "ft_pct": 0.530,
        "ts_pct": 0.647,
        "usage_rate": 0.32,
        "minutes_pg": 40.9,
        
        "attr_scoring": 96,
        "attr_playmaking": 70,
        "attr_rebounding": 99,
        "attr_defense": 88,
        "attr_consistency": 85,
        "attr_clutch": 88,
    },
    
    # 5. STEPHEN CURRY (PRIME) - Sharpshooter King
    {
        "player_id": 900005,
        "name": "Stephen Curry (Prime)",
        "position": "PG",
        "franchise": "GSW",
        "era": "2010s",
        "overall": 96,
        "salary": 14000,
        "archetype": Archetype.SHARPSHOOTER,
        
        # 2015-16: 30.1 PPG, 5.4 RPG, 6.7 APG, 2.2 SPG, 0.2 BPG
        "ppg": 30.1,
        "rpg": 5.4,
        "apg": 6.7,
        "spg": 2.2,
        "bpg": 0.2,
        "tpg": 2.1,
        "threes_pg": 5.0,
        "fg_pct": 0.504,
        "ft_pct": 0.905,
        "ts_pct": 0.669,
        "usage_rate": 0.34,
        "minutes_pg": 34.2,
        
        "attr_scoring": 97,
        "attr_playmaking": 88,
        "attr_rebounding": 60,
        "attr_defense": 72,
        "attr_consistency": 93,
        "attr_clutch": 95,
    },
    
    # 6. TIM DUNCAN - "The Big Fundamental"
    {
        "player_id": 900006,
        "name": "Tim Duncan",
        "position": "PF/C",
        "franchise": "SAS",
        "era": "2000s",
        "overall": 96,
        "salary": 14000,
        "archetype": Archetype.TWO_WAY_STAR,
        
        # 2001-02: 25.5 PPG, 13.0 RPG, 3.7 APG, 0.7 SPG, 2.5 BPG
        "ppg": 25.5,
        "rpg": 13.0,
        "apg": 3.7,
        "spg": 0.7,
        "bpg": 2.5,
        "tpg": 2.0,
        "threes_pg": 0.2,
        "fg_pct": 0.505,
        "ft_pct": 0.752,
        "ts_pct": 0.620,
        "usage_rate": 0.30,
        "minutes_pg": 39.5,
        
        "attr_scoring": 88,
        "attr_playmaking": 76,
        "attr_rebounding": 95,
        "attr_defense": 92,
        "attr_consistency": 96,
        "attr_clutch": 92,
    },
    
    # 7. MAGIC JOHNSON - Floor General Extreme
    {
        "player_id": 900007,
        "name": "Magic Johnson",
        "position": "PG",
        "franchise": "LAL",
        "era": "80s",
        "overall": 96,
        "salary": 14000,
        "archetype": Archetype.FLOOR_GENERAL,
        
        # 1984-85: 18.3 PPG, 6.2 RPG, 12.6 APG, 1.4 SPG, 0.3 BPG
        "ppg": 18.3,
        "rpg": 6.2,
        "apg": 12.6,
        "spg": 1.4,
        "bpg": 0.3,
        "tpg": 3.0,
        "threes_pg": 0.4,
        "fg_pct": 0.524,
        "ft_pct": 0.831,
        "ts_pct": 0.620,
        "usage_rate": 0.28,
        "minutes_pg": 38.3,
        
        "attr_scoring": 85,
        "attr_playmaking": 99,
        "attr_rebounding": 78,
        "attr_defense": 76,
        "attr_consistency": 90,
        "attr_clutch": 94,
    },
    
    # 8. KAREEM ABDUL-JABBAR - Skyhook Legend
    {
        "player_id": 900008,
        "name": "Kareem Abdul-Jabbar",
        "position": "C",
        "franchise": "LAL",
        "era": "80s",
        "overall": 96,
        "salary": 14000,
        "archetype": Archetype.ELITE_SCORER,
        
        # 1975-76: 27.7 PPG, 16.9 RPG, 5.0 APG, 1.6 SPG, 2.1 BPG
        "ppg": 27.7,
        "rpg": 16.9,
        "apg": 5.0,
        "spg": 1.6,
        "bpg": 2.1,
        "tpg": 2.5,
        "threes_pg": 0.0,
        "fg_pct": 0.551,
        "ft_pct": 0.721,
        "ts_pct": 0.614,
        "usage_rate": 0.35,
        "minutes_pg": 38.3,
        
        "attr_scoring": 96,
        "attr_playmaking": 75,
        "attr_rebounding": 98,
        "attr_defense": 85,
        "attr_consistency": 94,
        "attr_clutch": 88,
    },
    
    # 9. WILT CHAMBERLAIN - Statistical Anomaly
    {
        "player_id": 900009,
        "name": "Wilt Chamberlain",
        "position": "C",
        "franchise": "LAL",
        "era": "60s",
        "overall": 98,
        "salary": 14500,
        "archetype": Archetype.UNICORN,
        
        # 1966-67: 41.7 PPG, 24.2 RPG, 6.3 APG, 0.8 SPG, 1.8 BPG
        "ppg": 41.7,
        "rpg": 24.2,
        "apg": 6.3,
        "spg": 0.8,
        "bpg": 1.8,
        "tpg": 2.8,
        "threes_pg": 0.0,
        "fg_pct": 0.683,
        "ft_pct": 0.510,
        "ts_pct": 0.690,
        "usage_rate": 0.45,
        "minutes_pg": 45.0,
        
        "attr_scoring": 99,
        "attr_playmaking": 70,
        "attr_rebounding": 99,
        "attr_defense": 70,
        "attr_consistency": 60,
        "attr_clutch": 75,
    },
    
    # 10. LARRY BIRD - Sharpshooter Forward
    {
        "player_id": 900010,
        "name": "Larry Bird",
        "position": "SF",
        "franchise": "BOS",
        "era": "80s",
        "overall": 95,
        "salary": 13500,
        "archetype": Archetype.SHARPSHOOTER,
        
        # 1984-85: 28.7 PPG, 10.5 RPG, 6.6 APG, 1.6 SPG, 0.8 BPG
        "ppg": 28.7,
        "rpg": 10.5,
        "apg": 6.6,
        "spg": 1.6,
        "bpg": 0.8,
        "tpg": 2.6,
        "threes_pg": 2.0,
        "fg_pct": 0.522,
        "ft_pct": 0.882,
        "ts_pct": 0.636,
        "usage_rate": 0.33,
        "minutes_pg": 38.3,
        
        "attr_scoring": 95,
        "attr_playmaking": 82,
        "attr_rebounding": 85,
        "attr_defense": 84,
        "attr_consistency": 92,
        "attr_clutch": 94,
    },
    
    # 11. HAKEEM OLAJUWON - Dream Shake
    {
        "player_id": 900011,
        "name": "Hakeem Olajuwon",
        "position": "C",
        "franchise": "HOU",
        "era": "90s",
        "overall": 95,
        "salary": 13500,
        "archetype": Archetype.TWO_WAY_STAR,
        
        # 1993-94: 27.3 PPG, 11.9 RPG, 3.9 APG, 1.6 SPG, 3.7 BPG
        "ppg": 27.3,
        "rpg": 11.9,
        "apg": 3.9,
        "spg": 1.6,
        "bpg": 3.7,
        "tpg": 2.3,
        "threes_pg": 0.0,
        "fg_pct": 0.522,
        "ft_pct": 0.777,
        "ts_pct": 0.624,
        "usage_rate": 0.32,
        "minutes_pg": 40.3,
        
        "attr_scoring": 92,
        "attr_playmaking": 74,
        "attr_rebounding": 92,
        "attr_defense": 96,
        "attr_consistency": 90,
        "attr_clutch": 90,
    },
    
    # 12. KEVIN GARNETT - Versatile Beast
    {
        "player_id": 900012,
        "name": "Kevin Garnett",
        "position": "PF",
        "franchise": "MIN",
        "era": "2000s",
        "overall": 94,
        "salary": 13000,
        "archetype": Archetype.TWO_WAY_STAR,
        
        # 2003-04: 24.2 PPG, 13.9 RPG, 2.0 APG, 1.3 SPG, 2.2 BPG
        "ppg": 24.2,
        "rpg": 13.9,
        "apg": 2.0,
        "spg": 1.3,
        "bpg": 2.2,
        "tpg": 2.0,
        "threes_pg": 0.6,
        "fg_pct": 0.508,
        "ft_pct": 0.790,
        "ts_pct": 0.603,
        "usage_rate": 0.30,
        "minutes_pg": 39.2,
        
        "attr_scoring": 88,
        "attr_playmaking": 68,
        "attr_rebounding": 96,
        "attr_defense": 94,
        "attr_consistency": 90,
        "attr_clutch": 88,
    },
    
    # 13. CHARLES BARKLEY - Round Mound of Rebound
    {
        "player_id": 900013,
        "name": "Charles Barkley",
        "position": "PF",
        "franchise": "PHX",
        "era": "90s",
        "overall": 93,
        "salary": 13000,
        "archetype": Archetype.GLASS_CLEANER,
        
        # 1992-93: 25.6 PPG, 12.2 RPG, 3.5 APG, 1.4 SPG, 1.0 BPG
        "ppg": 25.6,
        "rpg": 12.2,
        "apg": 3.5,
        "spg": 1.4,
        "bpg": 1.0,
        "tpg": 3.0,
        "threes_pg": 0.3,
        "fg_pct": 0.516,
        "ft_pct": 0.728,
        "ts_pct": 0.602,
        "usage_rate": 0.31,
        "minutes_pg": 37.0,
        
        "attr_scoring": 88,
        "attr_playmaking": 72,
        "attr_rebounding": 97,
        "attr_defense": 82,
        "attr_consistency": 86,
        "attr_clutch": 88,
    },
    
    # 14. ALLEN IVERSON - The Answer (Boom/Bust)
    {
        "player_id": 900014,
        "name": "Allen Iverson",
        "position": "PG",
        "franchise": "PHI",
        "era": "2000s",
        "overall": 92,
        "salary": 12500,
        "archetype": Archetype.BOOM_BUST,
        
        # 2004-05: 30.7 PPG, 3.6 RPG, 7.0 APG, 2.2 SPG, 0.2 BPG
        "ppg": 30.7,
        "rpg": 3.6,
        "apg": 7.0,
        "spg": 2.2,
        "bpg": 0.2,
        "tpg": 3.1,
        "threes_pg": 1.9,
        "fg_pct": 0.424,
        "ft_pct": 0.788,
        "ts_pct": 0.539,
        "usage_rate": 0.37,
        "minutes_pg": 42.5,
        
        "attr_scoring": 96,
        "attr_playmaking": 80,
        "attr_rebounding": 50,
        "attr_defense": 78,
        "attr_consistency": 38,
        "attr_clutch": 90,
    },
    
    # 15. JULIUS ERVING - Dr. J
    {
        "player_id": 900015,
        "name": "Julius Erving",
        "position": "SF",
        "franchise": "PHI",
        "era": "80s",
        "overall": 92,
        "salary": 12500,
        "archetype": Archetype.ELITE_SCORER,
        
        # 1980-81: 24.6 PPG, 7.9 RPG, 3.7 APG, 1.4 SPG, 1.5 BPG
        "ppg": 24.6,
        "rpg": 7.9,
        "apg": 3.7,
        "spg": 1.4,
        "bpg": 1.5,
        "tpg": 2.5,
        "threes_pg": 0.0,
        "fg_pct": 0.507,
        "ft_pct": 0.756,
        "ts_pct": 0.620,
        "usage_rate": 0.30,
        "minutes_pg": 38.0,
        
        "attr_scoring": 94,
        "attr_playmaking": 76,
        "attr_rebounding": 80,
        "attr_defense": 82,
        "attr_consistency": 88,
        "attr_clutch": 90,
    },
    
    # 16. DIRK NOWITZKI - The Big German
    {
        "player_id": 900016,
        "name": "Dirk Nowitzki",
        "position": "PF",
        "franchise": "DAL",
        "era": "2000s",
        "overall": 92,
        "salary": 12500,
        "archetype": Archetype.SHARPSHOOTER,
        
        # 2006-07: 24.6 PPG, 9.6 RPG, 3.4 APG, 0.8 SPG, 0.8 BPG
        "ppg": 24.6,
        "rpg": 9.6,
        "apg": 3.4,
        "spg": 0.8,
        "bpg": 0.8,
        "tpg": 2.0,
        "threes_pg": 1.9,
        "fg_pct": 0.504,
        "ft_pct": 0.873,
        "ts_pct": 0.620,
        "usage_rate": 0.29,
        "minutes_pg": 37.5,
        
        "attr_scoring": 92,
        "attr_playmaking": 74,
        "attr_rebounding": 82,
        "attr_defense": 68,
        "attr_consistency": 92,
        "attr_clutch": 92,
    },
    
    # 17. SCOTTIE PIPPEN - Two-Way Forward
    {
        "player_id": 900017,
        "name": "Scottie Pippen",
        "position": "SF",
        "franchise": "CHI",
        "era": "90s",
        "overall": 91,
        "salary": 12000,
        "archetype": Archetype.TWO_WAY_STAR,
        
        # 1995-96: 19.4 PPG, 6.7 RPG, 5.9 APG, 1.8 SPG, 0.8 BPG
        "ppg": 19.4,
        "rpg": 6.7,
        "apg": 5.9,
        "spg": 1.8,
        "bpg": 0.8,
        "tpg": 2.2,
        "threes_pg": 0.8,
        "fg_pct": 0.512,
        "ft_pct": 0.707,
        "ts_pct": 0.568,
        "usage_rate": 0.26,
        "minutes_pg": 38.7,
        
        "attr_scoring": 78,
        "attr_playmaking": 84,
        "attr_rebounding": 80,
        "attr_defense": 95,
        "attr_consistency": 88,
        "attr_clutch": 86,
    },
    
    # 18. ISIAH THOMAS - Microwave Guard
    {
        "player_id": 900018,
        "name": "Isiah Thomas",
        "position": "PG",
        "franchise": "DET",
        "era": "80s",
        "overall": 91,
        "salary": 12000,
        "archetype": Archetype.FLOOR_GENERAL,
        
        # 1984-85: 21.2 PPG, 2.3 RPG, 13.9 APG, 1.6 SPG, 0.1 BPG
        "ppg": 21.2,
        "rpg": 2.3,
        "apg": 13.9,
        "spg": 1.6,
        "bpg": 0.1,
        "tpg": 2.6,
        "threes_pg": 0.4,
        "fg_pct": 0.490,
        "ft_pct": 0.768,
        "ts_pct": 0.595,
        "usage_rate": 0.33,
        "minutes_pg": 39.0,
        
        "attr_scoring": 86,
        "attr_playmaking": 97,
        "attr_rebounding": 45,
        "attr_defense": 78,
        "attr_consistency": 86,
        "attr_clutch": 92,
    },
    
    # 19. PATRICK EWING - Georgetown Legend
    {
        "player_id": 900019,
        "name": "Patrick Ewing",
        "position": "C",
        "franchise": "NYK",
        "era": "90s",
        "overall": 90,
        "salary": 12000,
        "archetype": Archetype.GLASS_CLEANER,
        
        # 1989-90: 28.6 PPG, 10.4 RPG, 2.4 APG, 1.0 SPG, 1.9 BPG
        "ppg": 28.6,
        "rpg": 10.4,
        "apg": 2.4,
        "spg": 1.0,
        "bpg": 1.9,
        "tpg": 2.8,
        "threes_pg": 0.0,
        "fg_pct": 0.520,
        "ft_pct": 0.749,
        "ts_pct": 0.594,
        "usage_rate": 0.33,
        "minutes_pg": 39.5,
        
        "attr_scoring": 92,
        "attr_playmaking": 66,
        "attr_rebounding": 88,
        "attr_defense": 86,
        "attr_consistency": 84,
        "attr_clutch": 86,
    },
    
    # 20. BILL RUSSELL - Defense Anchor (NO 3PT ERA)
    {
        "player_id": 900020,
        "name": "Bill Russell",
        "position": "C",
        "franchise": "BOS",
        "era": "60s",
        "overall": 93,
        "salary": 12500,
        "archetype": Archetype.LOCKDOWN_DEFENDER,
        
        # 1963-64: 12.3 PPG, 24.7 RPG, 5.2 APG, N/A SPG, N/A BPG
        "ppg": 12.3,
        "rpg": 24.7,
        "apg": 5.2,
        "spg": 1.8,  # Estimated
        "bpg": 2.0,  # Estimated
        "tpg": 2.0,
        "threes_pg": 0.0,
        "fg_pct": 0.440,
        "ft_pct": 0.561,
        "ts_pct": 0.530,
        "usage_rate": 0.20,
        "minutes_pg": 38.0,
        
        "attr_scoring": 55,
        "attr_playmaking": 72,
        "attr_rebounding": 98,
        "attr_defense": 99,
        "attr_consistency": 94,
        "attr_clutch": 95,
    },
]

# ============================================================================
# MONTHLY ROTATION GROUPS
# ============================================================================

# January: ALL 20 available (holiday bonus)
LEGENDS_JANUARY = [leg["player_id"] for leg in LEGENDS]

# Other months: 8 available (2 always, 6 rotate)
LEGENDS_ALWAYS_AVAILABLE = [900001, 900002]  # Jordan + LeBron
LEGENDS_ROTATING = [leg["player_id"] for leg in LEGENDS[2:]]  # Remaining 18

# Monthly rotation (cycles through 6 at a time, 3-month cycle)
LEGENDS_MONTHLY_GROUPS = {
    "february": LEGENDS_ALWAYS_AVAILABLE + LEGENDS_ROTATING[0:6],
    "march": LEGENDS_ALWAYS_AVAILABLE + LEGENDS_ROTATING[6:12],
    "april": LEGENDS_ALWAYS_AVAILABLE + LEGENDS_ROTATING[12:18],
    "may": LEGENDS_ALWAYS_AVAILABLE + LEGENDS_ROTATING[0:6],  # Cycle repeats
    "june": LEGENDS_ALWAYS_AVAILABLE + LEGENDS_ROTATING[6:12],
    "july": LEGENDS_ALWAYS_AVAILABLE + LEGENDS_ROTATING[12:18],
    "august": LEGENDS_ALWAYS_AVAILABLE + LEGENDS_ROTATING[0:6],
    "september": LEGENDS_ALWAYS_AVAILABLE + LEGENDS_ROTATING[6:12],
    "october": LEGENDS_ALWAYS_AVAILABLE + LEGENDS_ROTATING[12:18],
    "november": LEGENDS_ALWAYS_AVAILABLE + LEGENDS_ROTATING[0:6],
    "december": LEGENDS_ALWAYS_AVAILABLE + LEGENDS_ROTATING[6:12],
    "january": LEGENDS_JANUARY,  # All 20 for holiday
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_legend_by_id(legend_id: int) -> dict:
    """Get legend profile by ID."""
    for leg in LEGENDS:
        if leg["player_id"] == legend_id:
            return leg
    return None

def get_legend_by_name(name: str) -> dict:
    """Get legend profile by name."""
    for leg in LEGENDS:
        if leg["name"].lower() == name.lower():
            return leg
    return None

def get_available_legends_for_month(month: str) -> list:
    """Get available legend IDs for a given month."""
    return LEGENDS_MONTHLY_GROUPS.get(month.lower(), LEGENDS_ALWAYS_AVAILABLE)

def get_legends_for_tier(tier: str) -> list:
    """Get legends in a specific salary tier."""
    tier_ranges = {
        "superstar": (11000, 12000),
        "star": (12001, 15000),
    }
    if tier not in tier_ranges:
        return []
    
    min_sal, max_sal = tier_ranges[tier]
    return [leg for leg in LEGENDS if min_sal <= leg["salary"] <= max_sal]

if __name__ == "__main__":
    print(f"✅ {len(LEGENDS)} Hall of Fame Legends loaded")
    print("\n🏀 Sample Legend:")
    mj = get_legend_by_name("Michael Jordan")
    print(f"  {mj['name']}: {mj['overall']} OVR, ${mj['salary']:,}")
    print(f"  Stats: {mj['ppg']} PPG, {mj['rpg']} RPG, {mj['apg']} APG")
    
    print(f"\n🌙 Available in February: {len(get_available_legends_for_month('february'))} legends")
    print(f"🎉 Available in January: {len(get_available_legends_for_month('january'))} legends (ALL)")
