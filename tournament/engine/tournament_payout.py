"""
Tournament Payout Engine (Phase 0)

Dynamic prize distribution based on field size.
Scales from min field (12 players) to max (32 players).
"""

from typing import Dict, List, Any


class PayoutCalculator:
    """Calculate dynamic prize pools and payouts."""
    
    # Prize pool percentages of total rake (what doesn't go to prize pool)
    # $500 entry × N players = total collected
    # Take Stripe rake (~3.5%) + house edge (15%) = 18.5% rake
    # Remaining 81.5% → prize pool
    
    HOUSE_EDGE = 0.15  # 15% to operator
    STRIPE_RAKE = 0.035  # ~3.5% Stripe fee
    TOTAL_RAKE = HOUSE_EDGE + STRIPE_RAKE  # ~18.5%
    PRIZE_POOL_PCT = 1.0 - TOTAL_RAKE  # ~81.5%
    
    # Payout distribution (% of prize pool) by placement
    # Scales based on field size
    PAYOUT_STRUCTURES = {
        12: {
            # 12-player
            1: 0.40,
            2: 0.25,
            3: 0.15,
            4: 0.12,
            5: 0.08,
        },
        24: {
            # 24-player (full field)
            1: 0.30,
            2: 0.18,
            3: 0.12,
            4: 0.10,
            5: 0.08,
            6: 0.07,
            7: 0.06,
            8: 0.05,
            9: 0.02,
            10: 0.02,
        },
        32: {
            # 32-player (championship)
            1: 0.25,
            2: 0.15,
            3: 0.10,
            4: 0.08,
            5: 0.07,
            6: 0.06,
            7: 0.05,
            8: 0.05,
            9: 0.04,
            10: 0.03,
            11: 0.03,
            12: 0.02,
            13: 0.01,
            14: 0.01,
        },
    }
    
    def __init__(self, entry_fee: float = 5.0):
        """
        Initialize calculator.
        
        Args:
            entry_fee: Per-entry fee in dollars
        """
        self.entry_fee = entry_fee
    
    def calculate_pool(self, num_entries: int) -> Dict[str, float]:
        """
        Calculate prize pool from number of entries.
        
        Args:
            num_entries: Number of tournament entries
        
        Returns:
            {
                "total_collected": X,
                "stripe_rake": Y,
                "house_edge": Z,
                "prize_pool": W,
            }
        """
        total_collected = self.entry_fee * num_entries
        stripe_rake = total_collected * self.STRIPE_RAKE
        house_edge = total_collected * self.HOUSE_EDGE
        prize_pool = total_collected * self.PRIZE_POOL_PCT
        
        return {
            "total_collected": round(total_collected, 2),
            "stripe_rake": round(stripe_rake, 2),
            "house_edge": round(house_edge, 2),
            "prize_pool": round(prize_pool, 2),
        }
    
    def get_payout_structure(self, num_entries: int) -> Dict[int, float]:
        """
        Get payout structure for entry count.
        Interpolates if needed.
        
        Args:
            num_entries: Number of entries
        
        Returns:
            {1: pct, 2: pct, ...} where sum(pct) ≤ 1.0
        """
        # Find closest structure
        keys = sorted(self.PAYOUT_STRUCTURES.keys())
        
        for key in keys:
            if num_entries <= key:
                return self.PAYOUT_STRUCTURES[key]
        
        # Default to largest structure
        return self.PAYOUT_STRUCTURES[max(keys)]
    
    def calculate_payouts(
        self,
        num_entries: int,
        sorted_scores: List[Tuple[str, float]],  # [(entry_id, score), ...]
    ) -> List[Dict[str, Any]]:
        """
        Calculate payouts for all entries.
        
        Args:
            num_entries: Total entries
            sorted_scores: Sorted list of (entry_id, score) tuples (highest first)
        
        Returns:
            [
                {
                    "placement": 1,
                    "entry_id": "X",
                    "score": 123.4,
                    "prize": 150.00,
                    "lp_awarded": 50,
                },
                ...
            ]
        """
        pool_info = self.calculate_pool(num_entries)
        prize_pool = pool_info["prize_pool"]
        
        payout_structure = self.get_payout_structure(num_entries)
        
        payouts = []
        for idx, (entry_id, score) in enumerate(sorted_scores):
            placement = idx + 1
            
            if placement in payout_structure:
                payout_pct = payout_structure[placement]
                prize = prize_pool * payout_pct
            else:
                prize = 0.0
            
            # LP awarded = placement + base (more LP for better finish)
            lp_awarded = max(1, 100 - (placement - 1) * 5)
            
            payouts.append({
                "placement": placement,
                "entry_id": entry_id,
                "score": score,
                "prize": round(prize, 2),
                "lp_awarded": lp_awarded,
            })
        
        return payouts


if __name__ == "__main__":
    # Test
    calc = PayoutCalculator(entry_fee=5.0)
    
    print("📊 Prize Pool Breakdown")
    for num_entries in [12, 24, 32]:
        pool = calc.calculate_pool(num_entries)
        print(f"\n{num_entries} entries @ $5 each:")
        print(f"  Total: ${pool['total_collected']}")
        print(f"  Prize Pool: ${pool['prize_pool']} ({pool['prize_pool'] / pool['total_collected'] * 100:.1f}%)")
        print(f"  House: ${pool['house_edge']}")
        print(f"  Stripe: ${pool['stripe_rake']}")
    
    # Test payouts
    print("\n💰 Sample Payouts (24-player, $5 entry):")
    sorted_scores = [
        ("entry_1", 250.5),
        ("entry_2", 240.3),
        ("entry_3", 235.1),
        ("entry_24", 50.0),
    ]
    payouts = calc.calculate_payouts(24, sorted_scores[:3])
    for payout in payouts:
        print(f"  #{payout['placement']}: ${payout['prize']} + {payout['lp_awarded']} LP")
