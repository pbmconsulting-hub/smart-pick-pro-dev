"""
Tournament Simulation Engine (Phase 0)

Two-tier wrapper around parent app engines:
  Tier 1: Game environment (Engine A: _simulate_single_game)
  Tier 2: Player stats (Engine B: run_quantum_matrix_simulation)

This module is a pure coordinator — all heavy lifting delegated to parent.
"""

from typing import Dict, Any, List, Optional, Tuple
import hashlib
import secrets
import random
from dataclasses import dataclass


@dataclass
class GameEnvironment:
    """Tournament-level game conditions."""
    home_score: int
    away_score: int
    margin: int
    total: int
    went_to_ot: bool
    blowout_risk_factor: float
    pace_adjustment_factor: float
    vegas_spread: float
    game_total: float
    environment_label: str


class TournamentsSimulationOrchestrator:
    """
    Orchestrates tournament simulation.
    
    In Phase 0, this is mostly a placeholder pending integration
    with parent app's engine/game_prediction.py and engine/simulation.py
    """
    
    def __init__(self, parent_app_root: Optional[str] = None):
        """
        Initialize.
        
        Args:
            parent_app_root: Path to parent Smart Pick Pro app
        """
        self.parent_app_root = parent_app_root
        self._engine_a = None
        self._engine_b = None
    
    def generate_tournament_seed(self) -> Tuple[str, int]:
        """
        Generate cryptographically-random seed for tournament.
        Called AFTER lock to ensure unpredictability.
        
        Returns:
            (hex_seed, int_seed)
        """
        raw = secrets.token_hex(32)  # 256 bits
        seed_int = int(hashlib.sha256(raw.encode()).hexdigest()[:8], 16)
        return raw, seed_int
    
    def simulate_tournament_environment(self, seed_int: int) -> GameEnvironment:
        """
        TIER 1: Simulate tournament-level game environment.
        
        Uses parent app's _simulate_single_game (Engine A) with
        league-average inputs to produce neutral game conditions.
        
        Args:
            seed_int: Random seed for deterministic output
        
        Returns:
            GameEnvironment with pace, margin, total, OT, blowout risk
        """
        # Placeholder for Phase 0
        # In Phase 1+, this will import and call:
        #   from engine.game_prediction import _simulate_single_game
        #   from engine.game_prediction import (LEAGUE_AVG_ORTG, LEAGUE_AVG_PACE, ...)
        
        random.seed(seed_int)
        
        # Simulate league-average game
        home_score = random.randint(100, 130)
        away_score = random.randint(100, 130)
        margin = abs(home_score - away_score)
        total = home_score + away_score
        went_to_ot = random.random() < 0.05  # 5% OT chance
        
        # Derive environment factors
        if went_to_ot:
            label = "⚡ Overtime Thriller"
            blowout_risk = 0.05
            pace = 1.08
        elif margin > 20:
            label = "💨 Blowout"
            blowout_risk = 0.65
            pace = 0.95
        elif total > 235:
            label = "🔥 Shootout"
            blowout_risk = 0.20
            pace = 1.04
        elif total < 200:
            label = "🧱 Defensive Grind"
            blowout_risk = 0.20
            pace = 0.96
        else:
            label = "🏀 Standard Game"
            blowout_risk = 0.15
            pace = 1.0
        
        return GameEnvironment(
            home_score=home_score,
            away_score=away_score,
            margin=margin,
            total=total,
            went_to_ot=went_to_ot,
            blowout_risk_factor=round(blowout_risk, 3),
            pace_adjustment_factor=round(pace, 4),
            vegas_spread=float(home_score - away_score),
            game_total=float(total),
            environment_label=label,
        )
    
    def simulate_player_stat(
        self,
        profile: "tournament_profiles.PlayerProfile",
        stat_type: str,
        env: GameEnvironment,
        seed: int,
    ) -> int:
        """
        TIER 2: Simulate one stat for one player.
        
        Uses parent app's run_quantum_matrix_simulation (Engine B).
        
        Args:
            profile: Player profile from tournament_profiles.py
            stat_type: "points", "rebounds", "assists", "steals", "blocks", "turnovers", "threes"
            env: GameEnvironment from Tier 1
            seed: Deterministic seed for this player/stat
        
        Returns:
            Simulated stat value (int)
        """
        # Placeholder for Phase 0
        # In Phase 1+, will import and call:
        #   from engine.simulation import run_quantum_matrix_simulation
        
        stat_map = {
            "points": ("ppg", 0.25),
            "rebounds": ("rpg", 0.30),
            "assists": ("apg", 0.35),
            "steals": ("spg", 0.50),
            "blocks": ("bpg", 0.55),
            "turnovers": ("tpg", 0.35),
            "threes": ("threes_pg", 0.40),
        }
        
        if stat_type not in stat_map:
            return 0
        
        stat_attr, base_cv = stat_map[stat_type]
        mean = getattr(profile, stat_attr)
        
        if mean <= 0:
            return 0
        
        # Consistency modifies CV
        consistency = profile.attr_consistency
        cv_mod = 1.0 + (50 - consistency) * 0.008
        cv_modifier = max(0.5, min(1.5, cv_mod))
        
        std_dev = mean * base_cv * cv_modifier
        std_dev = max(0.5, std_dev)
        
        # Simulate 100 outcomes
        random.seed(seed)
        outcomes = [random.gauss(mean, std_dev) for _ in range(100)]
        outcomes = sorted([max(0, o) for o in outcomes])
        
        # Pick based on Clutch attribute
        clutch = profile.attr_clutch
        low_pct = max(5, 50 - clutch // 2)
        high_pct = min(95, 50 + clutch // 2)
        
        # Hot/cold adjust
        if profile.is_hot:
            low_pct = min(90, low_pct + 8)
            high_pct = min(98, high_pct + 5)
        elif profile.is_cold:
            low_pct = max(2, low_pct - 5)
            high_pct = max(40, high_pct - 8)
        
        chosen_pct = random.randint(low_pct, high_pct)
        idx = int(chosen_pct / 100 * len(outcomes))
        idx = max(0, min(len(outcomes) - 1, idx))
        
        return max(0, round(outcomes[idx]))
    
    def simulate_player_full_line(
        self,
        profile: "tournament_profiles.PlayerProfile",
        env: GameEnvironment,
        tournament_seed: int,
    ) -> Dict[str, int]:
        """
        Simulate complete stat line for one player.
        
        Args:
            profile: Player profile
            env: Game environment
            tournament_seed: Tournament-level seed (base for per-player calcs)
        
        Returns:
            {"points": X, "rebounds": Y, "assists": Z, ...}
        """
        stats = {}
        stat_types = ["points", "rebounds", "assists", "steals", "blocks", "turnovers", "threes"]
        
        base_seed = tournament_seed + profile.player_id
        for i, stat in enumerate(stat_types):
            stats[stat] = self.simulate_player_stat(
                profile, stat, env, base_seed + (i * 1000)
            )
        
        return stats
    
    def resolve_tournament(
        self,
        tournament_id: int,
        entries: List[Dict[str, Any]],  # [{"entry_id": X, "roster": [profiles]}, ...]
        player_profiles: Dict[int, "tournament_profiles.PlayerProfile"],
    ) -> Dict[str, Any]:
        """
        Resolve entire tournament (called at lock).
        
        Args:
            tournament_id: Tournament ID
            entries: List of user entries (roster assignments)
            player_profiles: Dict of all rostered player profiles
        
        Returns:
            {
                "tournament_id": X,
                "seed": seed_int,
                "environment": GameEnvironment,
                "entry_scores": [{"entry_id": X, "total_fp": Y}, ...],
                "sim_results": {player_id: stats_dict, ...},
            }
        """
        # 1. Generate seed
        raw_seed, seed_int = self.generate_tournament_seed()
        
        # 2. Simulate environment (Tier 1)
        env = self.simulate_tournament_environment(seed_int)
        
        # 3. Simulate each unique player (Tier 2)
        sim_results = {}
        for player_id, profile in player_profiles.items():
            line = self.simulate_player_full_line(profile, env, seed_int)
            sim_results[player_id] = line
        
        # 4. Score each entry
        entry_scores = []
        for entry in entries:
            # Import scoring at runtime to avoid circular deps in Phase 0
            from engine.tournament_scoring import calculate_entry_score
            
            roster = entry["roster"]
            entry_fp = calculate_entry_score(roster, sim_results)
            entry_scores.append({
                "entry_id": entry["entry_id"],
                "total_fp": entry_fp,
            })
        
        # 5. Return results
        return {
            "tournament_id": tournament_id,
            "seed_int": seed_int,
            "environment": env,
            "entry_scores": entry_scores,
            "sim_results": sim_results,
        }


if __name__ == "__main__":
    # Test
    orch = TournamentsSimulationOrchestrator()
    raw_seed, seed_int = orch.generate_tournament_seed()
    print(f"✅ Seed generated: {seed_int}")
    
    env = orch.simulate_tournament_environment(seed_int)
    print(f"✅ Environment: {env.environment_label}")
    print(f"   Total: {env.total}, Margin: {env.margin}, OT: {env.went_to_ot}")
