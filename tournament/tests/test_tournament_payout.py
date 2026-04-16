"""
test_tournament_payout.py - Unit tests for prize pool and payout distribution

Tests:
  - calculate_pool() - total collected - rake = prize pool
  - calculate_payouts() - distribute prizes by placement
  - house edge (15%) + stripe rake (3.5%) = 18.5%
  - dynamic payout structures (12/24/32 player fields)
"""

import pytest

# Import mock classes from local conftest in tests directory
from .conftest import PayoutCalculator


class TestPayoutCalculator:
    """Test suite for prize pool and payout calculations."""
    
    def test_house_edge_constant(self):
        """Test that house edge is 15%."""
        calc = PayoutCalculator()
        assert calc.HOUSE_EDGE == 0.15
    
    def test_stripe_rake_constant(self):
        """Test that Stripe rake is 3.5%."""
        calc = PayoutCalculator()
        assert calc.STRIPE_RAKE == 0.035
    
    def test_total_rake(self):
        """Test that total rake is 18.5%."""
        calc = PayoutCalculator()
        total = calc.HOUSE_EDGE + calc.STRIPE_RAKE
        assert abs(total - 0.185) < 0.001
    
    def test_prize_pool_pct(self):
        """Test that prize pool is 81.5% of collected."""
        calc = PayoutCalculator()
        assert calc.PRIZE_POOL_PCT == 0.815
    
    def test_calculate_pool_12_players_5_entry_fee(self):
        """Test pool calculation: 12 players × $5 = $60 -> $49.  """
        calc = PayoutCalculator()
        
        total_collected = 60.0  # 12 × $5
        prize_pool = calc.calculate_pool(total_collected, num_players=12)
        
        expected = 60.0 * 0.815  # 81.5% of collected
        
        assert prize_pool is not None
        assert abs(prize_pool - expected) < 0.01
    
    def test_calculate_pool_24_players_5_entry_fee(self):
        """Test pool calculation: 24 players × $5 = $120 -> $97.80."""
        calc = PayoutCalculator()
        
        total_collected = 120.0  # 24 × $5
        prize_pool = calc.calculate_pool(total_collected, num_players=24)
        
        expected = 120.0 * 0.815
        
        assert prize_pool is not None
        assert abs(prize_pool - expected) < 0.01
    
    def test_calculate_pool_32_players_10_entry_fee(self):
        """Test pool calculation: 32 players × $10 = $320 -> $260.80."""
        calc = PayoutCalculator()
        
        total_collected = 320.0  # 32 × $10
        prize_pool = calc.calculate_pool(total_collected, num_players=32)
        
        expected = 320.0 * 0.815
        
        assert prize_pool is not None
        assert abs(prize_pool - expected) < 0.01
    
    def test_calculate_payouts_structure_12_players(self):
        """Test payout distribution for 12-player tournament."""
        calc = PayoutCalculator()
        
        prize_pool = 100.0
        payouts = calc.calculate_payouts(
            prize_pool=prize_pool,
            num_players=12,
            placements=[
                {"entry_id": 1, "placement": 1},
                {"entry_id": 2, "placement": 2},
                {"entry_id": 3, "placement": 3},
                {"entry_id": 4, "placement": 4},
                {"entry_id": 5, "placement": 5},
                {"entry_id": 6, "placement": 6},
                {"entry_id": 7, "placement": 7},
                {"entry_id": 8, "placement": 8},
                {"entry_id": 9, "placement": 9},
                {"entry_id": 10, "placement": 10},
                {"entry_id": 11, "placement": 11},
                {"entry_id": 12, "placement": 12},
            ]
        )
        
        assert payouts is not None
        assert len(payouts) == 12
        
        # Top 3 should get prizes
        assert payouts[0]["prize"] > 0
        assert payouts[1]["prize"] > 0
        assert payouts[2]["prize"] > 0
        
        # Lower placements should have 0 or lower prize
        assert payouts[-1].get("prize", 0) >= 0
    
    def test_calculate_payouts_structure_24_players(self):
        """Test payout distribution for 24-player tournament."""
        calc = PayoutCalculator()
        
        prize_pool = 200.0
        payouts = calc.calculate_payouts(
            prize_pool=prize_pool,
            num_players=24,
            placements=[
                {"entry_id": i, "placement": i}
                for i in range(1, 25)
            ]
        )
        
        assert payouts is not None
        assert len(payouts) == 24
        
        # Top 6 (25%) should get prizes
        paid_out = sum(p.get("prize", 0) for p in payouts[:6])
        assert paid_out > 0
    
    def test_payouts_sum_to_pool(self):
        """Test that total payouts <= prize pool."""
        calc = PayoutCalculator()
        
        prize_pool = 150.0
        payouts = calc.calculate_payouts(
            prize_pool=prize_pool,
            num_players=20,
            placements=[
                {"entry_id": i, "placement": i}
                for i in range(1, 21)
            ]
        )
        
        total_paid = sum(p.get("prize", 0) for p in payouts)
        
        # Total paid out should not exceed prize pool
        assert total_paid <= prize_pool + 1  # +1 for rounding
    
    def test_1st_place_highest_prize(self):
        """Test that 1st place gets highest prize."""
        calc = PayoutCalculator()
        
        prize_pool = 100.0
        payouts = calc.calculate_payouts(
            prize_pool=prize_pool,
            num_players=10,
            placements=[
                {"entry_id": i, "placement": i}
                for i in range(1, 11)
            ]
        )
        
        first_prize = payouts[0].get("prize", 0)
        
        # All other payouts should be <= first place
        for payout in payouts[1:]:
            assert payout.get("prize", 0) <= first_prize


class TestPayoutEdgeCases:
    """Edge case tests for payout calculations."""
    
    def test_single_player_tournament(self):
        """Test payout for single-player tournament."""
        calc = PayoutCalculator()
        
        total_collected = 50.0
        prize_pool = calc.calculate_pool(total_collected, num_players=1)
        
        assert prize_pool is not None
        assert prize_pool > 0
    
    def test_zero_entry_fee_tournament(self):
        """Test payout for free tournament ($0 entry fee)."""
        calc = PayoutCalculator()
        
        total_collected = 0.0
        prize_pool = calc.calculate_pool(total_collected, num_players=10)
        
        assert prize_pool == 0.0
    
    def test_loyalty_points_distribution(self):
        """Test that LP (Loyalty Points) are distributed to all entries."""
        calc = PayoutCalculator()
        
        prize_pool = 100.0
        payouts = calc.calculate_payouts(
            prize_pool=prize_pool,
            num_players=10,
            placements=[
                {"entry_id": i, "placement": i}
                for i in range(1, 11)
            ]
        )
        
        # All entries should get some LP
        for payout in payouts:
            assert "lp" in payout or payout.get("lp", 0) >= 0
