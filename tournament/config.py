"""
Tournament System Configuration
Isolated config for tournament environment
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project root
TOURNAMENT_ROOT = Path(__file__).parent
PARENT_APP_ROOT = TOURNAMENT_ROOT.parent

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{TOURNAMENT_ROOT / 'tournament.db'}"
)

# Stripe (will be populated at launch)
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")

# Tournament Settings
TOURNAMENT_CONFIG = {
    "min_field_size": 12,
    "max_field_size": 32,
    "full_field": 24,
    "entry_fee_open_court": 0.0,  # Free
    "entry_fee_pro_court": 5.0,
    "entry_fee_elite_court": 25.0,
    "entry_fee_championship_night": 75.0,
    "entry_fee_grand_championship": 100.0,
    "max_entries_per_user": None,  # No limit
    "lock_time_offset_minutes": 30,  # Lock 30 min before game
    "championship_field_size": 32,
    "championship_min_entries": 16,
    "championship_reveal_mode": "staged",  # 30-minute phased reveal
}

# Roster Configuration
ROSTER_CONFIG = {
    "salary_cap_active": 50000,
    "salary_floor_active": 40000,
    "salary_cap_legend": 15000,
    "max_same_team": 3,
    "max_player_ownership_pct": 0.33,  # 33% of field
    "max_legend_ownership_pct": 0.25,  # 25% of field
}

# Scoring Formula
SCORING_CONFIG = {
    "points": 1.0,
    "rebounds": 1.2,
    "assists": 1.5,
    "steals": 3.0,
    "blocks": 3.0,
    "threes": 0.5,
    "turnovers": -1.5,
}

# Bonuses
BONUS_CONFIG = {
    "double_double": 2.0,
    "triple_double": 5.0,
    "points_40": 3.0,
    "points_50": 7.0,
    "rebounds_20": 3.0,
    "assists_15": 3.0,
    "five_by_five": 10.0,
}

# Penalties
PENALTY_CONFIG = {
    "ejection": -10.0,
    "ejection_probability_base": 0.001,  # 0.1% base
}

# Legend Configuration
LEGEND_CONFIG = {
    "total_legends": 20,
    "legends_available_per_month": 8,
    "always_available": ["Michael Jordan", "LeBron James (Peak)"],
    "salary_tier": "legend",  # Range $12K–$15K
}

# Simulation Settings
SIMULATION_CONFIG = {
    "num_micro_simulations": 100,  # Per stat per player
    "random_seed_bits": 32,  # 256-bit seed
}

# Premium Tiers
PREMIUM_TIERS = {
    "free": {
        "legend_access": False,
        "legend_slots": 0,
        "tournaments_per_month": 50,  # No limit functionally
    },
    "premium": {
        "legend_access": False,  # Requires Legend Pass add-on
        "legend_slots": 0,
        "tournaments_per_month": None,
        "price_monthly": 9.99,
    },
    "legend_pass": {
        "legend_access": True,
        "legend_slots": 1,
        "legend_count": 8,  # All 8 monthly legends
        "tournaments_per_month": None,
        "price_monthly": 4.99,
        "requires": "premium",  # Add-on to premium
    },
}

# Championship Night Configuration
CHAMPIONSHIP_CONFIG = {
    "entry_fee": 75.0,
    "field_size": 32,
    "min_entries": 16,
    "reveal_mode": "staged",
    "qualification_method": "lp_snapshot",  # Monthly LP snapshot
    "payout_template": [500, 325, 275, 220, 180, 150, 145, 125],
    "lp_multiplier": {
        1: 250,   # 1st place
        2: 175,   # 2nd place
        3: 125,   # 3rd place
        4: 75,    # 4th place
        5: 50,    # 5th place
    },
}

# Database Tables (for reference)
TABLES = {
    "tournaments": "Tournament metadata, lock times, seed",
    "entries": "User rosters, fees, scores, payouts",
    "player_profiles": "NBA player profiles, attributes, salary",
    "player_game_logs": "Historical player game data (KDE input)",
    "tournament_simulations": "Seed + environment + stat outcomes",
    "payouts": "Payout records (Stripe Connect)",
    "badges": "User badges earned (Phase 1+)",
    "leaderboard": "League points (LP) tracking",
}

# Environment (for logging/debugging)
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

if __name__ == "__main__":
    print("Tournament Configuration:")
    print(f"  Database: {DATABASE_URL}")
    print(f"  Tournament Root: {TOURNAMENT_ROOT}")
    print(f"  Parent App Root: {PARENT_APP_ROOT}")
    print(f"  Debug: {DEBUG}")
    print(f"  Roster Cap: ${ROSTER_CONFIG['salary_cap_active']:,}")
    print(f"  Entry Fee (Pro): ${TOURNAMENT_CONFIG['entry_fee_pro_court']}")
