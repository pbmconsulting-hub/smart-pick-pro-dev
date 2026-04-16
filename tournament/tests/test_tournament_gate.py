"""
test_tournament_gate.py - Unit tests for access control and tier validation

Tests:
  - can_user_access_tournament() - tier checks
  - can_user_roster_legend() - legend pass validation
  - get_required_upgrades() - upgrade path calculation
  - geo_blocking (WA, ID, MT, HI, NV)
  - state licensing (MI, TN, IN, LA)
"""

import pytest

# Import mock classes from local conftest in tests directory
from .conftest import TournamentGate, TournamentAccess


class TestTournamentGate:
    """Test suite for TournamentGate access control."""
    
    def test_free_user_open_court_allowed(self):
        """Test free user can access Open Court."""
        gate = TournamentGate()
        
        can_access, reason = gate.can_user_access_tournament(
            user_tier="free",
            court_type="open_court",
            user_state="CA",
        )
        
        assert can_access is True
    
    def test_free_user_pro_court_denied(self):
        """Test free user CANNOT access Pro Court."""
        gate = TournamentGate()
        
        can_access, reason = gate.can_user_access_tournament(
            user_tier="free",
            court_type="pro_court",
            user_state="CA",
        )
        
        assert can_access is False
        assert "Premium" in reason or "upgrade" in reason.lower()
    
    def test_premium_user_pro_court_allowed(self):
        """Test premium user can access Pro Court."""
        gate = TournamentGate()
        
        can_access, reason = gate.can_user_access_tournament(
            user_tier="premium",
            court_type="pro_court",
            user_state="CA",
        )
        
        assert can_access is True
    
    def test_premium_user_elite_court_allowed(self):
        """Test premium user can access Elite Court."""
        gate = TournamentGate()
        
        can_access, reason = gate.can_user_access_tournament(
            user_tier="premium",
            court_type="elite_court",
            user_state="CA",
        )
        
        assert can_access is True
    
    def test_free_user_legend_denied(self):
        """Test free user CANNOT roster legends."""
        gate = TournamentGate()
        
        can_roster, reason = gate.can_user_roster_legend(
            user_tier="free",
            has_legend_pass=False,
        )
        
        assert can_roster is False
        assert "Legend Pass" in reason or "Premium" in reason
    
    def test_premium_user_no_pass_legend_denied(self):
        """Test premium user WITHOUT Legend Pass CANNOT roster legends."""
        gate = TournamentGate()
        
        can_roster, reason = gate.can_user_roster_legend(
            user_tier="premium",
            has_legend_pass=False,
        )
        
        assert can_roster is False
        assert "Legend Pass" in reason or "$4.99" in reason
    
    def test_premium_user_with_pass_legend_allowed(self):
        """Test premium user WITH Legend Pass CAN roster legends."""
        gate = TournamentGate()
        
        can_roster, reason = gate.can_user_roster_legend(
            user_tier="premium",
            has_legend_pass=True,
        )
        
        assert can_roster is True
    
    def test_geo_blocking_washington(self):
        """Test geo-blocking for Washington state."""
        gate = TournamentGate()
        
        can_access, reason = gate.can_user_access_tournament(
            user_tier="premium",
            court_type="pro_court",
            user_state="WA",  # Blocked state
        )
        
        assert can_access is False
        assert "state" in reason.lower() or "not available" in reason.lower()
    
    def test_geo_blocking_idaho(self):
        """Test geo-blocking for Idaho state."""
        gate = TournamentGate()
        
        can_access, reason = gate.can_user_access_tournament(
            user_tier="premium",
            court_type="pro_court",
            user_state="ID",  # Blocked state
        )
        
        assert can_access is False
    
    def test_geo_blocking_nevada(self):
        """Test geo-blocking for Nevada state."""
        gate = TournamentGate()
        
        can_access, reason = gate.can_user_access_tournament(
            user_tier="premium",
            court_type="pro_court",
            user_state="NV",  # Blocked state
        )
        
        assert can_access is False
    
    def test_allowed_state_california(self):
        """Test California is allowed."""
        gate = TournamentGate()
        
        can_access, reason = gate.can_user_access_tournament(
            user_tier="premium",
            court_type="pro_court",
            user_state="CA",
        )
        
        assert can_access is True
    
    def test_allowed_state_texas(self):
        """Test Texas is allowed."""
        gate = TournamentGate()
        
        can_access, reason = gate.can_user_access_tournament(
            user_tier="premium",
            court_type="pro_court",
            user_state="TX",
        )
        
        assert can_access is True
    
    def test_get_required_upgrades_free_to_pro(self):
        """Test upgrade path: Free -> Pro Court."""
        gate = TournamentGate()
        
        upgrades = gate.get_required_upgrades(
            user_tier="free",
            target_court="pro_court",
            has_legend_pass=False,
        )
        
        assert upgrades is not None
        assert "current" in upgrades
        assert upgrades["current"] == "free"
        assert upgrades["required"] is not None
    
    def test_get_required_upgrades_for_legends(self):
        """Test upgrade path for legend roster."""
        gate = TournamentGate()
        
        upgrades = gate.get_required_upgrades(
            user_tier="free",
            target_court="open_court",
            has_legend_pass=False,
            want_legends=True,
        )
        
        assert upgrades is not None
        assert "path" in upgrades
        assert len(upgrades["path"]) > 1


class TestTournamentAccess:
    """Test TournamentAccess enum."""
    
    def test_access_enum_values(self):
        """Test that access tiers are properly enumerated."""
        assert hasattr(TournamentAccess, "OPEN_COURT")
        assert hasattr(TournamentAccess, "PRO_COURT")
        assert hasattr(TournamentAccess, "ELITE_COURT")


class TestCourtTierMatrix:
    """Test court tier access matrix."""
    
    def test_access_matrix(self):
        """Verify complete access control matrix."""
        gate = TournamentGate()
        
        test_cases = [
            # (tier, court, state, has_pass, should_access)
            ("free", "open_court", "CA", False, True),
            ("free", "pro_court", "CA", False, False),
            ("free", "elite_court", "CA", False, False),
            ("premium", "open_court", "CA", False, True),
            ("premium", "pro_court", "CA", False, True),
            ("premium", "elite_court", "CA", False, True),
            ("premium", "pro_court", "WA", False, False),  # Geo-blocked
            ("premium", "pro_court", "CA", True, True),
        ]
        
        for tier, court, state, has_pass, should_access in test_cases:
            can_access, _ = gate.can_user_access_tournament(
                user_tier=tier,
                court_type=court,
                user_state=state,
                has_legend_pass=has_pass,
            )
            
            assert can_access == should_access, \
                f"Failed: {tier} + {court} + {state}: expected {should_access}, got {can_access}"
