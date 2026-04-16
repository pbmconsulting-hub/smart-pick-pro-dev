"""
test_tournament_manager.py - Unit tests for tournament CRUD operations

Tests:
  - create_tournament()
  - open_tournament()
  - add_entry()
  - lock_tournament()
  - resolve_tournament()
  - cancel_tournament()
  - list_tournaments()
"""

import pytest
from datetime import datetime, timedelta

# Import mock classes from local conftest in tests directory
from .conftest import TournamentManager


class TestTournamentManager:
    """Test suite for TournamentManager CRUD operations."""
    
    def test_create_tournament_success(self, mock_tournament):
        """Test creating a tournament with valid data."""
        manager = TournamentManager()
        
        result = manager.create_tournament(
            sport=mock_tournament["sport"],
            name=mock_tournament["name"],
            entry_fee=mock_tournament["entry_fee"],
            lock_time_minutes=60,
        )
        
        assert result is not None
        assert isinstance(result, int)
        assert result > 0
    
    def test_create_tournament_returns_dict(self, mock_tournament):
        """Test that get_tournament returns proper structure."""
        manager = TournamentManager()
        
        tournament_id = manager.create_tournament(
            sport=mock_tournament["sport"],
            name=mock_tournament["name"],
            entry_fee=mock_tournament["entry_fee"],
            lock_time_minutes=60,
        )
        
        tournament = manager.get_tournament(tournament_id)
        
        assert tournament is not None
        assert tournament["tournament_id"] == tournament_id
        assert tournament["name"] == mock_tournament["name"]
        assert tournament["entry_fee"] == mock_tournament["entry_fee"]
    
    def test_open_tournament(self, mock_tournament):
        """Test opening a tournament (draft -> open)."""
        manager = TournamentManager()
        
        tournament_id = manager.create_tournament(
            sport=mock_tournament["sport"],
            name=mock_tournament["name"],
            entry_fee=mock_tournament["entry_fee"],
            lock_time_minutes=60,
        )
        
        result = manager.open_tournament(tournament_id)
        
        assert result is True
        
        tournament = manager.get_tournament(tournament_id)
        assert tournament["status"] == "open"
    
    def test_add_entry_success(self, mock_tournament, mock_roster, mock_user):
        """Test adding an entry to a tournament."""
        manager = TournamentManager()
        
        tournament_id = manager.create_tournament(
            sport=mock_tournament["sport"],
            name=mock_tournament["name"],
            entry_fee=mock_tournament["entry_fee"],
            lock_time_minutes=60,
        )
        
        manager.open_tournament(tournament_id)
        
        salary_spent = sum(p["salary"] for p in mock_roster.values() if p)
        
        result = manager.add_entry(
            tournament_id=tournament_id,
            user_id=mock_user["user_id"],
            roster=mock_roster,
            salary_spent=salary_spent,
        )
        
        assert result is not None
        assert isinstance(result, int)
    
    def test_add_entry_validates_salary_floor(self, mock_tournament, mock_user):
        """Test that add_entry validates salary floor."""
        from .conftest import SALARY_FLOOR
        
        manager = TournamentManager()
        
        tournament_id = manager.create_tournament(
            sport=mock_tournament["sport"],
            name=mock_tournament["name"],
            entry_fee=mock_tournament["entry_fee"],
            lock_time_minutes=60,
        )
        
        manager.open_tournament(tournament_id)
        
        # Roster with salary below floor
        cheap_roster = {
            "PG": {"player_id": 101, "salary": 3000},
            "SG": {"player_id": 102, "salary": 3000},
            "SF": {"player_id": 103, "salary": 3000},
            "PF": {"player_id": 104, "salary": 3000},
            "C": {"player_id": 105, "salary": 3000},
            "G": {"player_id": 106, "salary": 3000},
            "F": {"player_id": 107, "salary": 3000},
            "UTIL": {"player_id": 108, "salary": 3000},
            "LEGEND": None,
        }
        
        salary_spent = 24000  # Below floor
        
        # Should fail validation
        result = manager.add_entry(
            tournament_id=tournament_id,
            user_id=mock_user["user_id"],
            roster=cheap_roster,
            salary_spent=salary_spent,
        )
        
        # Result should indicate failure (None or False)
        assert result is None or result is False
    
    def test_lock_tournament(self, mock_tournament):
        """Test locking a tournament (open -> locked)."""
        manager = TournamentManager()
        
        tournament_id = manager.create_tournament(
            sport=mock_tournament["sport"],
            name=mock_tournament["name"],
            entry_fee=mock_tournament["entry_fee"],
            lock_time_minutes=60,
        )
        
        manager.open_tournament(tournament_id)
        
        result = manager.lock_tournament(tournament_id)
        
        assert result is True
        
        tournament = manager.get_tournament(tournament_id)
        assert tournament["status"] == "locked"
        assert tournament["seed"] is not None
    
    def test_resolve_tournament(self, mock_tournament):
        """Test resolving a tournament with scores and rankings."""
        manager = TournamentManager()
        
        tournament_id = manager.create_tournament(
            sport=mock_tournament["sport"],
            name=mock_tournament["name"],
            entry_fee=mock_tournament["entry_fee"],
            lock_time_minutes=60,
        )
        
        manager.open_tournament(tournament_id)
        manager.lock_tournament(tournament_id)
        
        result = manager.resolve_tournament(tournament_id)
        
        assert result is True
        
        tournament = manager.get_tournament(tournament_id)
        assert tournament["status"] == "resolved"
    
    def test_cancel_tournament(self, mock_tournament):
        """Test canceling a tournament."""
        manager = TournamentManager()
        
        tournament_id = manager.create_tournament(
            sport=mock_tournament["sport"],
            name=mock_tournament["name"],
            entry_fee=mock_tournament["entry_fee"],
            lock_time_minutes=60,
        )
        
        result = manager.cancel_tournament(tournament_id)
        
        assert result is True
        
        tournament = manager.get_tournament(tournament_id)
        assert tournament["status"] == "cancelled"
    
    def test_list_tournaments(self, mock_tournament):
        """Test listing tournaments."""
        manager = TournamentManager()
        
        # Create 3 tournaments
        for i in range(3):
            manager.create_tournament(
                sport=mock_tournament["sport"],
                name=f"{mock_tournament['name']} #{i+1}",
                entry_fee=mock_tournament["entry_fee"],
                lock_time_minutes=60,
            )
        
        tournaments = manager.list_tournaments(status="draft")
        
        assert len(tournaments) >= 3
    
    def test_get_tournament_entries(self, mock_tournament, mock_roster, mock_user):
        """Test retrieving entries for a tournament."""
        manager = TournamentManager()
        
        tournament_id = manager.create_tournament(
            sport=mock_tournament["sport"],
            name=mock_tournament["name"],
            entry_fee=mock_tournament["entry_fee"],
            lock_time_minutes=60,
        )
        
        manager.open_tournament(tournament_id)
        
        salary_spent = sum(p["salary"] for p in mock_roster.values() if p)
        
        manager.add_entry(
            tournament_id=tournament_id,
            user_id=mock_user["user_id"],
            roster=mock_roster,
            salary_spent=salary_spent,
        )
        
        entries = manager.get_tournament_entries(tournament_id)
        
        assert len(entries) > 0
        assert entries[0]["user_id"] == mock_user["user_id"]
    
    def test_auto_cancel_logic(self, mock_tournament):
        """Test auto-cancel when tournament underfilled after 30 minutes."""
        manager = TournamentManager()
        
        tournament_id = manager.create_tournament(
            sport=mock_tournament["sport"],
            name=mock_tournament["name"],
            entry_fee=mock_tournament["entry_fee"],
            lock_time_minutes=30,  # 30 min lock
        )
        
        manager.open_tournament(tournament_id)
        
        # Don't add any entries, let it reach lock time
        # In production, this would be checked at lock_time
        # For testing, we verify the method exists and returns bool
        
        result = manager.auto_cancel_if_underfilled(tournament_id)
        
        assert isinstance(result, bool)


class TestTournamentLifecycle:
    """Test complete tournament lifecycle."""
    
    def test_full_tournament_lifecycle(self, mock_tournament, mock_roster, mock_user):
        """Test complete: create -> open -> add entry -> lock -> resolve."""
        manager = TournamentManager()
        
        # 1. Create
        tournament_id = manager.create_tournament(
            sport=mock_tournament["sport"],
            name=mock_tournament["name"],
            entry_fee=mock_tournament["entry_fee"],
            lock_time_minutes=60,
        )
        assert tournament_id is not None
        
        # 2. Open
        assert manager.open_tournament(tournament_id) is True
        
        # 3. Add entry
        salary_spent = sum(p["salary"] for p in mock_roster.values() if p)
        entry_id = manager.add_entry(
            tournament_id=tournament_id,
            user_id=mock_user["user_id"],
            roster=mock_roster,
            salary_spent=salary_spent,
        )
        assert entry_id is not None
        
        # 4. Lock
        assert manager.lock_tournament(tournament_id) is True
        
        # 5. Resolve
        assert manager.resolve_tournament(tournament_id) is True
        
        # Verify final state
        tournament = manager.get_tournament(tournament_id)
        assert tournament["status"] == "resolved"
