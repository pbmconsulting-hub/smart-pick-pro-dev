"""
Tournament Access Gate (Phase 1)

Controls who can enter tournaments based on:
  - Free user vs Premium user
  - Legend Pass ownership
  - Geo-blocking (state restrictions)
  - Entry cap logic

Tiers:
  - Free: Open Court only (no legends, no paid tournaments)
  - Premium: Pro Court + Elite Court, no legends
  - Premium + Legend Pass: All courts + legends
"""

from typing import Tuple, Optional, Dict, Any
from enum import Enum


class TournamentAccess(str, Enum):
    """Tournament access levels."""
    OPEN_COURT = "open_court"        # Free, no legends, no entry fee
    PRO_COURT = "pro_court"          # $5 entry, no legends, Premium+
    ELITE_COURT = "elite_court"      # $25 entry, no legends, Premium+
    CHAMPIONSHIP = "championship"    # Special, Premium+, limited field


class UserTier(str, Enum):
    """User subscription tier."""
    FREE = "free"
    PREMIUM = "premium"


class TournamentGate:
    """Control access to tournaments."""
    
    # Monthly cost
    TIER_PRICING = {
        UserTier.FREE: 0.0,
        UserTier.PREMIUM: 9.99,
    }
    
    LEGEND_PASS_PRICE = 4.99
    
    # Tournament type → min user tier required
    COURT_MIN_TIER = {
        TournamentAccess.OPEN_COURT: UserTier.FREE,
        TournamentAccess.PRO_COURT: UserTier.PREMIUM,
        TournamentAccess.ELITE_COURT: UserTier.PREMIUM,
        TournamentAccess.CHAMPIONSHIP: UserTier.PREMIUM,
    }
    
    # Legend availability by tier
    LEGEND_ACCESS = {
        UserTier.FREE: False,
        UserTier.PREMIUM: False,  # Requires Legend Pass add-on
    }
    
    LEGEND_PASS_UNLOCKS_LEGENDS = True
    
    # Geo-blocking (blocked states)
    BLOCKED_STATES = {
        "WA",  # Washington
        "ID",  # Idaho
        "MT",  # Montana
        "HI",  # Hawaii
        "NV",  # Nevada (requires gaming license)
    }
    
    STATES_REQUIRING_LICENSE = {
        "MI",  # Michigan
        "TN",  # Tennessee
        "IN",  # Indiana
        "LA",  # Louisiana
    }
    
    def __init__(self, db_connection):
        """
        Initialize gate.
        
        Args:
            db_connection: Database connection (for user tier checks)
        """
        self.conn = db_connection
    
    def can_user_access_tournament(
        self,
        user_id: int,
        tournament_type: str,
        user_tier: str = None,
        has_legend_pass: bool = False,
        user_state: str = None,
    ) -> Tuple[bool, str]:
        """
        Check if user can enter tournament.
        
        Args:
            user_id: User ID
            tournament_type: open_court, pro_court, elite_court, championship
            user_tier: Free or Premium (fetched from DB if None)
            has_legend_pass: If user has Legend Pass
            user_state: User state code (for geo-blocking)
        
        Returns:
            (allowed: bool, reason: str)
        """
        # 1. Geo-blocking
        if user_state and user_state.upper() in self.BLOCKED_STATES:
            return False, f"🚫 Smart Pick Pro is not available in {user_state}"
        
        # 2. Tier check
        if user_tier is None:
            user_tier = self._get_user_tier(user_id)
        
        min_tier = self.COURT_MIN_TIER.get(tournament_type, UserTier.FREE)
        if user_tier == UserTier.FREE and tournament_type != TournamentAccess.OPEN_COURT:
            return False, (
                f"💎 {tournament_type} requires Premium subscription ($9.99/mo)\n"
                f"   Upgrade to unlock all tournaments"
            )
        
        # 3. Legend access
        if tournament_type == TournamentAccess.CHAMPIONSHIP:
            # Championship likely involves legends
            if not has_legend_pass:
                return False, (
                    f"⚡ Legend Pass ($4.99/mo add-on) required for this tournament\n"
                    f"   Add to your Premium subscription to compete"
                )
        
        return True, "✅ Access granted"
    
    def can_user_roster_legend(
        self,
        user_id: int,
        has_legend_pass: bool = False,
        user_tier: str = None,
    ) -> Tuple[bool, str]:
        """
        Check if user can roster Hall of Fame legend.
        
        Args:
            user_id: User ID
            has_legend_pass: If user has Legend Pass
            user_tier: Free or Premium
        
        Returns:
            (allowed: bool, reason: str)
        """
        if user_tier is None:
            user_tier = self._get_user_tier(user_id)
        
        if user_tier == UserTier.FREE:
            return False, (
                "⚡ Legends require Premium subscription + Legend Pass\n"
                f"   Premium: $9.99/mo | Legend Pass: $4.99/mo add-on"
            )
        
        if user_tier == UserTier.PREMIUM and not has_legend_pass:
            return False, (
                "⚡ Legend Pass ($4.99/mo add-on) required\n"
                f"   Add to your Premium subscription"
            )
        
        return True, "✅ Can roster legends"
    
    def can_user_enter_tournament(
        self,
        user_id: int,
        tournament_id: int,
        user_tier: str = None,
        has_legend_pass: bool = False,
        user_state: str = None,
    ) -> Tuple[bool, str]:
        """
        Full check: can user enter tournament?
        
        Args:
            user_id: User ID
            tournament_id: Tournament ID
            user_tier: Free or Premium
            has_legend_pass: Legend Pass status
            user_state: User state
        
        Returns:
            (allowed: bool, reason: str)
        """
        # Fetch tournament type
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT tournament_type FROM tournaments WHERE tournament_id = ?",
            (tournament_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        
        if not row:
            return False, "❌ Tournament not found"
        
        tournament_type = row[0]
        
        # Check access
        return self.can_user_access_tournament(
            user_id, tournament_type, user_tier, has_legend_pass, user_state
        )
    
    def _get_user_tier(self, user_id: int) -> str:
        """Fetch user subscription tier from DB."""
        # Stub: In production, query user profiles / subscriptions table
        # For Phase 1, assume all are FREE
        return UserTier.FREE
    
    def get_user_status(self, user_id: int) -> Dict[str, Any]:
        """Get user's subscription status."""
        cursor = self.conn.cursor()
        
        # Stub: Fetch from users/subscriptions table
        # For now, return defaults
        cursor.close()
        
        return {
            "user_id": user_id,
            "tier": UserTier.FREE,
            "has_legend_pass": False,
            "premium_expires": None,
            "legend_pass_expires": None,
        }
    
    def upgrade_to_premium(
        self,
        user_id: int,
        stripe_subscription_id: str,
    ) -> bool:
        """Upgrade user to Premium tier."""
        # Stub: Update user subscription in DB
        return True
    
    def add_legend_pass(
        self,
        user_id: int,
        stripe_subscription_id: str,
    ) -> bool:
        """Add Legend Pass to user."""
        # Stub: Update user subscription in DB
        return True
    
    @staticmethod
    def get_required_upgrades(
        user_tier: str,
        tournament_type: str,
        has_legend_pass: bool = False,
    ) -> Dict[str, Any]:
        """
        Suggest what upgrades are needed.
        
        Returns:
            {
                "current": {...},
                "required": {...},
                "path": [list of upgrades],
            }
        """
        current = {
            "tier": user_tier,
            "has_legend_pass": has_legend_pass,
        }
        
        required = {}
        path = []
        
        # Are they Free?
        if user_tier == UserTier.FREE:
            if tournament_type != TournamentAccess.OPEN_COURT:
                required["tier"] = UserTier.PREMIUM
                path.append("Upgrade to Premium ($9.99/mo)")
        
        # Do they need Legend Pass?
        if tournament_type == TournamentAccess.CHAMPIONSHIP and not has_legend_pass:
            required["has_legend_pass"] = True
            path.append(f"Add Legend Pass ($4.99/mo add-on)")
        
        return {
            "current": current,
            "required": required,
            "path": path,
            "total_monthly": (
                (9.99 if required.get("tier") == UserTier.PREMIUM else 0) +
                (4.99 if required.get("has_legend_pass") else 0)
            )
        }


if __name__ == "__main__":
    import sqlite3
    from db.schema import create_all_tables
    
    # Test
    conn = sqlite3.connect(":memory:")
    create_all_tables(conn)
    
    gate = TournamentGate(conn)
    
    # Test 1: Free user, Open Court
    allowed, reason = gate.can_user_access_tournament(
        user_id=1,
        tournament_type=TournamentAccess.OPEN_COURT,
        user_tier="free"
    )
    print(f"✅ Free → Open Court: {allowed} ({reason})")
    
    # Test 2: Free user, Pro Court (should fail)
    allowed, reason = gate.can_user_access_tournament(
        user_id=1,
        tournament_type=TournamentAccess.PRO_COURT,
        user_tier="free"
    )
    print(f"❌ Free → Pro Court: {allowed}")
    print(f"   {reason}\n")
    
    # Test 3: Premium + Legend Pass
    allowed, reason = gate.can_user_roster_legend(
        user_id=2,
        has_legend_pass=True,
        user_tier="premium"
    )
    print(f"✅ Premium + Legend Pass → Legends: {allowed}")
    
    # Test 4: Geo-blocking
    allowed, reason = gate.can_user_access_tournament(
        user_id=3,
        tournament_type=TournamentAccess.PRO_COURT,
        user_tier="premium",
        user_state="WA"
    )
    print(f"❌ Washington user → any tournament: {allowed}")
    print(f"   {reason}")
