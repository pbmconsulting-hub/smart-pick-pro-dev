"""
conftest.py - Pytest configuration and fixtures for tournament tests

Provides:
- test database setup/teardown
- mock objects (user, tournament, entry)
- shared fixtures
- Mock classes for backend services
- Enums for archetypes and rarity tiers
"""

import pytest
import sqlite3
import tempfile
import json
import hashlib
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
import sys
from enum import Enum


# ========== Enums and Constants ==========

class Archetype(Enum):
    """Player archetype classifications."""
    UNICORN = "UNICORN"
    ELITE_SCORER = "ELITE_SCORER"
    LOCKDOWN_DEFENDER = "LOCKDOWN_DEFENDER"
    PLAYMAKER = "PLAYMAKER"
    REBOUNDER = "REBOUNDER"
    ROLE_PLAYER = "ROLE_PLAYER"
    BENCH = "BENCH"
    SIXTH_MAN = "SIXTH_MAN"
    VETERAN_MIN = "VETERAN_MIN"
    PROSPECT = "PROSPECT"
    INJURY_RETURN = "INJURY_RETURN"


class RarityTier(Enum):
    """Player rarity classifications."""
    COMMON = "COMMON"
    RARE = "RARE"
    ELITE = "ELITE"


class TournamentAccess:
    """Tournament access court types."""
    OPEN_COURT = "open_court"
    PRO_COURT = "pro_court"
    ELITE_COURT = "elite_court"


# Mock out heavy dependencies before any imports
sys.modules['streamlit'] = MagicMock()
sys.modules['st'] = MagicMock()
sys.modules['nba_api'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['pandas'] = MagicMock()
sys.modules['numpy'] = MagicMock()
sys.modules['sklearn'] = MagicMock()
sys.modules['xgboost'] = MagicMock()
sys.modules['catboost'] = MagicMock()

# Mock parent engine modules so tournament/__init__.py loads without parent app
_mock_game_pred = MagicMock()
_mock_game_pred.BLOWOUT_MARGIN_THRESHOLD = 15
_mock_game_pred.LEAGUE_AVG_DRTG = 110.0
_mock_game_pred.LEAGUE_AVG_ORTG = 110.0
_mock_game_pred.LEAGUE_AVG_PACE = 100.0
_mock_game_pred._calculate_expected_possessions = MagicMock(return_value=100.0)
_mock_game_pred._score_from_possession_model = MagicMock(return_value=105.0)
_mock_game_pred._simulate_single_game = MagicMock(return_value=(108, 102, False))

_mock_engine_sim = MagicMock()
_mock_engine_sim.run_quantum_matrix_simulation = MagicMock(
    return_value={"simulated_results": list(range(10, 40))}
)

sys.modules.setdefault('engine', MagicMock())
sys.modules['engine.game_prediction'] = _mock_game_pred
sys.modules['engine.simulation'] = _mock_engine_sim

# Mock parent data/tracking modules
_mock_data = MagicMock()
_mock_data.data_manager = MagicMock()
_mock_data.data_manager.load_players_data = MagicMock(return_value=[])
sys.modules.setdefault('data', _mock_data)
sys.modules.setdefault('data.data_manager', _mock_data.data_manager)
sys.modules.setdefault('tracking', MagicMock())
sys.modules.setdefault('tracking.database', MagicMock())


@pytest.fixture
def temp_db():
    """Create temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE tournaments (
        tournament_id INTEGER PRIMARY KEY,
        sport TEXT, name TEXT, status TEXT, entry_fee REAL,
        lock_time INTEGER, seed TEXT, prize_pool REAL, created_at TIMESTAMP
    )""")

    cursor.execute("""
    CREATE TABLE entries (
        entry_id INTEGER PRIMARY KEY,
        tournament_id INTEGER, user_id INTEGER, roster_json TEXT,
        salary_spent INTEGER, total_fp REAL, placement INTEGER,
        prize REAL, lp INTEGER, created_at TIMESTAMP
    )""")

    cursor.execute("""
    CREATE TABLE player_profiles (
        player_id INTEGER PRIMARY KEY,
        name TEXT, sport TEXT, stats_json TEXT,
        scoring INTEGER, playmaking INTEGER, rebounding INTEGER,
        defense INTEGER, consistency INTEGER, clutch INTEGER,
        overall INTEGER, archetype TEXT, tier TEXT, salary INTEGER,
        team TEXT, position TEXT
    )""")

    conn.commit()
    conn.close()
    yield db_path
    Path(db_path).unlink()


@pytest.fixture
def mock_user():
    """Mock user object."""
    return {
        "user_id": 1,
        "name": "Test User",
        "tier": "premium",
        "has_legend_pass": True,
        "state": "CA",
    }


@pytest.fixture
def mock_tournament():
    """Mock tournament object."""
    return {
        "tournament_id": 1,
        "sport": "nba",
        "name": "Lakers vs Celtics",
        "status": "open",
        "entry_fee": 5.0,
        "lock_time": datetime.now() + timedelta(hours=1),
        "seed": "d7a89f3c2b1e9d6a4f5c3b8e1a9d7c2b",
        "prize_pool": 100.0,
    }


@pytest.fixture
def mock_roster():
    """Mock 9-player roster."""
    return {
        "PG": {"player_id": 101, "name": "Luka Doncic", "salary": 11000},
        "SG": {"player_id": 102, "name": "Devin Booker", "salary": 10000},
        "SF": {"player_id": 103, "name": "LeBron James", "salary": 11000},
        "PF": {"player_id": 104, "name": "Kevin Durant", "salary": 10500},
        "C": {"player_id": 105, "name": "Jokic", "salary": 10500},
        "G": {"player_id": 106, "name": "Curry", "salary": 11000},
        "F": {"player_id": 107, "name": "Giannis", "salary": 11000},
        "UTIL": {"player_id": 108, "name": "Jayson Tatum", "salary": 10500},
        "LEGEND": {"player_id": 900001, "name": "Michael Jordan", "salary": 15000},
    }


@pytest.fixture
def mock_game_stats():
    """Mock player game stats."""
    return {
        "player_id": 101,
        "game_date": "2026-04-15",
        "points": 28,
        "rebounds": 6,
        "assists": 4,
        "steals": 1,
        "blocks": 0,
        "threes": 3,
        "turnovers": 2,
        "minutes": 35,
    }


@pytest.fixture
def mock_player_profile():
    """Mock player profile with attributes."""
    return {
        "player_id": 101,
        "name": "Luka Doncic",
        "sport": "nba",
        "stats": {
            "ppg": 28.5,
            "rpg": 9.2,
            "apg": 8.1,
            "spg": 1.4,
            "bpg": 0.5,
            "3pm": 3.2,
        },
        "scoring": 95,
        "playmaking": 92,
        "rebounding": 85,
        "defense": 65,
        "consistency": 88,
        "clutch": 90,
        "overall": 92,
        "archetype": "UNICORN",
        "tier": "ELITE",
        "salary": 11000,
        "team": "DAL",
        "position": "PG",
    }


# ========== Mock Backend Classes for Testing ==========

SALARY_FLOOR = 40000


class TournamentManager:
    """Mock TournamentManager for testing."""

    def __init__(self):
        self.tournaments = {}
        self.next_id = 1

    def create_tournament(self, sport, name, entry_fee=5.0,
                          lock_time=None, lock_time_minutes=60):
        tid = self.next_id
        self.next_id += 1
        self.tournaments[tid] = {
            "tournament_id": tid,
            "sport": sport,
            "name": name,
            "status": "draft",
            "entry_fee": entry_fee,
            "lock_time": lock_time or datetime.now() + timedelta(minutes=lock_time_minutes),
            "seed": None,
            "entries": [],
        }
        return tid

    def get_tournament(self, tournament_id):
        return self.tournaments.get(tournament_id)

    def open_tournament(self, tournament_id):
        if tournament_id in self.tournaments:
            self.tournaments[tournament_id]["status"] = "open"
            return True
        return False

    def lock_tournament(self, tournament_id):
        if tournament_id in self.tournaments:
            self.tournaments[tournament_id]["status"] = "locked"
            self.tournaments[tournament_id]["seed"] = "a" * 64
            return True
        return False

    def resolve_tournament(self, tournament_id):
        if tournament_id in self.tournaments:
            self.tournaments[tournament_id]["status"] = "resolved"
            return True
        return False

    def cancel_tournament(self, tournament_id):
        if tournament_id in self.tournaments:
            self.tournaments[tournament_id]["status"] = "cancelled"
            return True
        return False

    def add_entry(self, tournament_id, user_id, roster, salary_spent=None):
        if tournament_id not in self.tournaments:
            return None
        if salary_spent is None:
            salary_spent = sum(
                p["salary"] for p in roster.values() if p and isinstance(p, dict)
            )
        if salary_spent < SALARY_FLOOR:
            return None
        entry = {
            "entry_id": len(self.tournaments[tournament_id]["entries"]),
            "user_id": user_id,
            "roster": roster,
            "salary_spent": salary_spent,
        }
        self.tournaments[tournament_id]["entries"].append(entry)
        return entry["entry_id"]

    def list_tournaments(self, status=None):
        results = list(self.tournaments.values())
        if status:
            results = [t for t in results if t["status"] == status]
        return results

    def get_tournament_entries(self, tournament_id):
        if tournament_id in self.tournaments:
            return self.tournaments[tournament_id]["entries"]
        return []

    def auto_cancel_if_underfilled(self, tournament_id):
        if tournament_id in self.tournaments:
            entries = self.tournaments[tournament_id]["entries"]
            if len(entries) < 2:
                self.tournaments[tournament_id]["status"] = "cancelled"
                return True
            return False
        return False


class TournamentGate:
    """Mock TournamentGate for testing."""

    BLOCKED_STATES = ["WA", "ID", "MT", "HI", "NV"]

    def can_user_access_tournament(self, user_tier, court_type, user_state,
                                   has_legend_pass=False):
        if user_state in self.BLOCKED_STATES:
            return (False, f"Tournament not available in {user_state}")

        tier_access = {
            "free": ["open_court"],
            "premium": ["open_court", "pro_court", "elite_court"],
        }
        allowed = tier_access.get(user_tier, [])
        if court_type not in allowed:
            return (False, "Premium subscription required to access this court")
        return (True, "Access granted")

    def can_user_roster_legend(self, user_tier, has_legend_pass=False):
        if user_tier == "free":
            return (False, "Premium subscription and Legend Pass required")
        if not has_legend_pass:
            return (False, "Legend Pass required ($4.99/mo)")
        return (True, "Legend roster access granted")

    def get_required_upgrades(self, user_tier, target_court=None,
                              has_legend_pass=False, want_legends=False):
        upgrades = {
            "current": user_tier,
            "required": None,
            "path": [],
        }
        if user_tier == "free":
            upgrades["required"] = "premium"
            upgrades["path"].append({"action": "upgrade", "to": "premium", "cost": 9.99})
        if want_legends and not has_legend_pass:
            upgrades["path"].append({"action": "add_legend_pass", "cost": 4.99})
        return upgrades


class ScoringEngine:
    """Mock ScoringEngine for testing."""

    SCORING_RULES = {
        "points": 1.0,
        "rebounds": 1.2,
        "assists": 1.5,
        "steals": 3.0,
        "blocks": 3.0,
        "threes": 0.5,
        "turnovers": -1.5,
    }

    def calculate_fantasy_points(self, stats):
        fp = 0.0
        for stat, value in stats.items():
            if stat in self.SCORING_RULES:
                fp += value * self.SCORING_RULES[stat]

        bonuses = self.check_bonuses(stats)
        fp += sum(b["bonus"] for b in bonuses)

        penalties = self.check_penalties(stats)
        fp += sum(p["penalty"] for p in penalties)

        return max(0, fp)

    def check_bonuses(self, stats):
        bonuses = []
        pts = stats.get("points", 0)
        reb = stats.get("rebounds", 0)
        ast = stats.get("assists", 0)
        stl = stats.get("steals", 0)
        blk = stats.get("blocks", 0)

        if pts >= 10 and reb >= 10:
            bonuses.append({"type": "double_double", "bonus": 2})
        if pts >= 10 and reb >= 10 and ast >= 10:
            bonuses.append({"type": "triple_double", "bonus": 5})
        if pts >= 40:
            bonuses.append({"type": "high_points_40", "bonus": 3})
        if pts >= 50:
            bonuses.append({"type": "high_points_50", "bonus": 7})
        if reb >= 20:
            bonuses.append({"type": "high_rebounds", "bonus": 3})
        if ast >= 15:
            bonuses.append({"type": "high_assists", "bonus": 3})
        if pts >= 5 and reb >= 5 and ast >= 5 and stl >= 5 and blk >= 5:
            bonuses.append({"type": "5x5", "bonus": 10})
        return bonuses

    def check_penalties(self, stats):
        penalties = []
        if stats.get("ejected", False):
            penalties.append({"type": "ejection", "penalty": -10})
        return penalties


class PayoutCalculator:
    """Mock PayoutCalculator for testing."""

    HOUSE_EDGE = 0.15
    STRIPE_RAKE = 0.035
    TOTAL_RAKE = 0.185
    PRIZE_POOL_PCT = 0.815

    def calculate_pool(self, total_collected, num_players=None):
        return round(total_collected * self.PRIZE_POOL_PCT, 2)

    def calculate_payouts(self, prize_pool, num_players, placements=None):
        if placements is None:
            placements = [{"entry_id": i, "placement": i}
                          for i in range(1, num_players + 1)]

        payout_count = max(1, int(num_players * 0.25))

        # Build payout shares (descending)
        shares = []
        for i in range(payout_count):
            shares.append(max(0.05, 1.0 - i * 0.15))
        total_shares = sum(shares)

        results = []
        for entry in placements:
            place = entry["placement"]
            if place <= payout_count:
                prize = round(prize_pool * (shares[place - 1] / total_shares), 2)
            else:
                prize = 0
            results.append({
                "entry_id": entry["entry_id"],
                "placement": place,
                "prize": prize,
                "lp": max(5, 50 - (place - 1) * 5),
            })
        return results


class ProfileBuilder:
    """Mock ProfileBuilder for testing."""

    def build_profile(self, player_id, name, stats, **kwargs):
        scoring = self._percentile_from_stat(stats.get("ppg", 0), "ppg")
        playmaking = self._percentile_from_stat(stats.get("apg", 0), "apg")
        rebounding = self._percentile_from_stat(stats.get("rpg", 0), "rpg")
        defense = self._percentile_from_stat(
            stats.get("spg", 0) + stats.get("bpg", 0), "defense"
        )
        consistency = 75
        clutch = 80
        overall = int(round(
            (scoring + playmaking + rebounding + defense + consistency + clutch) / 6
        ))
        ppg = stats.get("ppg", 0)
        return {
            "player_id": player_id,
            "name": name,
            "scoring": scoring,
            "playmaking": playmaking,
            "rebounding": rebounding,
            "defense": defense,
            "consistency": consistency,
            "clutch": clutch,
            "overall": overall,
            "archetype": "UNICORN" if ppg > 25 else "ROLE_PLAYER",
            "tier": "ELITE" if ppg > 25 else "COMMON",
            "salary": 11000 if ppg > 25 else 5000,
        }

    def _percentile_from_stat(self, value, stat_type):
        if stat_type == "ppg":
            return min(99, max(1, int((value / 30) * 99)))
        elif stat_type == "apg":
            return min(99, max(1, int((value / 12) * 99)))
        elif stat_type == "rpg":
            return min(99, max(1, int((value / 15) * 99)))
        elif stat_type == "defense":
            # 4.0 combined spg+bpg is elite
            return min(99, max(1, int((value / 5.0) * 99)))
        return 50


class TournamentsSimulationOrchestrator:
    """Mock TournamentsSimulationOrchestrator for testing."""

    def generate_tournament_seed(self):
        return hashlib.sha256(os.urandom(32)).hexdigest()

    def simulate_tournament_environment(self, tournament_id, seed):
        return {
            "tournament_id": tournament_id,
            "seed": seed,
            "game_conditions": "normal",
        }

    def simulate_player_stat(self, player_id, tournament_id, environment, seed):
        return {
            "player_id": player_id,
            "points": 25,
            "rebounds": 8,
            "assists": 5,
        }

    def resolve_tournament(self, tournament_id, entries):
        return True
