"""
Tournament Player Profiles Engine (Phase 0)

Builds player attributes, archetypes, salary, QME inputs from season stats.
Uses percentile ranks (1–99) as the core unit.

Dependencies:
  - Does NOT import parent app yet (for strict isolation)
  - At runtime, caller supplies raw player stats dict
"""

from typing import Dict, Any, Tuple, List, Optional
from dataclasses import dataclass
from enum import Enum
import math


class Archetype(str, Enum):
    """Player archetypes based on attribute signatures."""
    UNICORN = "🧬 Unicorn"
    BOOM_BUST = "🎰 Boom/Bust"
    ELITE_SCORER = "🗡️ Elite Scorer"
    FLOOR_GENERAL = "🧠 Floor General"
    GLASS_CLEANER = "🏗️ Glass Cleaner"
    TWO_WAY_STAR = "⚔️ Two-Way Star"
    LOCKDOWN_DEFENDER = "🛡️ Lockdown Defender"
    SHARPSHOOTER = "🎯 Sharpshooter"
    RISING_STAR = "🌟 Rising Star"
    GLUE_GUY = "🔧 Glue Guy"
    VERSATILE = "🏀 Versatile"


class RarityTier(str, Enum):
    """Player salary tiers."""
    SUPERSTAR = "🔴 Superstar"
    STAR = "🟠 Star"
    STARTER = "🟡 Starter"
    ROLE_PLAYER = "🟢 Role Player"
    BENCH = "🔵 Bench"
    LEGEND = "🐐 Legend"


@dataclass
class PlayerProfile:
    """Complete player profile for tournament."""
    player_id: int
    player_name: str
    team: str
    position: str
    secondary_position: Optional[str]
    age: int
    headshot_url: Optional[str]
    
    # Season Stats
    ppg: float
    rpg: float
    apg: float
    spg: float
    bpg: float
    tpg: float
    threes_pg: float
    fg_pct: float
    ft_pct: float
    ts_pct: float
    usage_rate: float
    minutes_pg: float
    
    # Attributes (1–99 percentile ranks)
    attr_scoring: int
    attr_playmaking: int
    attr_rebounding: int
    attr_defense: int
    attr_consistency: int
    attr_clutch: int
    
    # Derived
    overall_rating: int
    archetype: Archetype
    rarity_tier: RarityTier
    salary: int
    
    # QME Inputs
    fp_mean: float
    fp_std_dev: float
    
    # Form
    is_hot: bool
    is_cold: bool
    form_label: str
    
    # Status
    is_active: bool
    is_legend: bool
    injury_status: Optional[str]
    
    # Derived FP stats (cached)
    doubts_consistency_score: float  # For hot/cold detection


class ProfileBuilder:
    """Build player profiles from season stats."""
    
    # Attribute Formulas (percentile-based)
    ATTR_WEIGHTS = {
        "scoring": {
            "ppg": 0.50,
            "ts_pct": 0.30,
            "usage_rate": 0.20,
        },
        "playmaking": {
            "apg": 0.50,
            "assist_rate": 0.30,
            "ast_to": 0.20,
        },
        "rebounding": {
            "rpg": 0.50,
            "rebound_rate": 0.30,
            "off_reb_pct": 0.20,
        },
        "defense": {
            "spg": 0.25,
            "bpg": 0.25,
            "def_win_shares": 0.25,
            "inv_drtg": 0.25,
        },
        "consistency": {
            "fp_std_dev": 1.0,  # INVERSE: lower variance = higher consistency
        },
        "clutch": {
            "q4_ppg": 0.60,
            "close_game_plus_minus": 0.40,
        },
    }
    
    OVERALL_WEIGHTS = {
        "scoring": 0.30,
        "playmaking": 0.20,
        "rebounding": 0.15,
        "defense": 0.15,
        "consistency": 0.10,
        "clutch": 0.10,
    }
    
    # Salary Tiers
    SALARY_TIERS = {
        RarityTier.SUPERSTAR: (11000, 12000),
        RarityTier.STAR: (9000, 10900),
        RarityTier.STARTER: (6500, 8900),
        RarityTier.ROLE_PLAYER: (4500, 6400),
        RarityTier.BENCH: (3000, 4400),
        RarityTier.LEGEND: (12000, 15000),  # Fixed high range
    }
    
    # Archetype Modifiers (affect salary)
    ARCHETYPE_SALARY_MODS = {
        Archetype.BOOM_BUST: 0.92,
        Archetype.UNICORN: 1.05,
        Archetype.GLUE_GUY: 0.90,
        Archetype.SHARPSHOOTER: 1.02,
        Archetype.TWO_WAY_STAR: 1.03,
    }
    
    def __init__(self, all_players: List[Dict[str, Any]]):
        """
        Initialize builder with all players for percentile calculation.
        
        Args:
            all_players: List of dicts with season stats
        """
        self.all_players = all_players
        self._percentile_cache = {}
    
    def build_profile(
        self,
        player_stats: Dict[str, Any],
        is_legend: bool = False,
        legend_era: Optional[str] = None,
    ) -> PlayerProfile:
        """
        Build a complete profile for one player.
        
        Args:
            player_stats: {player_id, name, team, ppg, rpg, apg, ...}
            is_legend: If True, use fixed ratings (no percentile calc)
            legend_era: Era name for legends
        
        Returns:
            PlayerProfile
        """
        if is_legend:
            return self._build_legend_profile(player_stats, legend_era)
        
        # Calculate attributes (percentile ranks)
        scoring = self._calculate_attribute("scoring", player_stats)
        playmaking = self._calculate_attribute("playmaking", player_stats)
        rebounding = self._calculate_attribute("rebounding", player_stats)
        defense = self._calculate_attribute("defense", player_stats)
        consistency = self._calculate_attribute("consistency", player_stats)
        clutch = self._calculate_attribute("clutch", player_stats)
        
        # Calculate overall
        overall = self._calculate_overall(
            scoring, playmaking, rebounding, defense, consistency, clutch
        )
        
        # Classify archetype
        archetype = self._classify_archetype(
            overall, scoring, playmaking, rebounding, defense, consistency,
            player_stats.get("age", 25)
        )
        
        # Assign rarity tier
        rarity_tier = self._assign_rarity_tier(overall)
        
        # Calculate salary
        salary = self._calculate_salary(overall, archetype, rarity_tier)
        
        # Detect form (hot/cold)
        is_hot, is_cold, form_label = self._detect_form(player_stats)
        
        # Calculate QME inputs
        fp_mean = self._calculate_fp_mean(player_stats)
        fp_std_dev = self._calculate_fp_std_dev(player_stats, consistency)
        
        return PlayerProfile(
            player_id=player_stats["player_id"],
            player_name=player_stats["name"],
            team=player_stats["team"],
            position=player_stats["position"],
            secondary_position=player_stats.get("secondary_position"),
            age=player_stats.get("age", 25),
            headshot_url=player_stats.get("headshot_url"),
            ppg=player_stats["ppg"],
            rpg=player_stats["rpg"],
            apg=player_stats["apg"],
            spg=player_stats["spg"],
            bpg=player_stats["bpg"],
            tpg=player_stats["tpg"],
            threes_pg=player_stats["threes_pg"],
            fg_pct=player_stats.get("fg_pct", 0.450),
            ft_pct=player_stats.get("ft_pct", 0.750),
            ts_pct=player_stats.get("ts_pct", 0.550),
            usage_rate=player_stats.get("usage_rate", 0.25),
            minutes_pg=player_stats.get("minutes_pg", 30.0),
            attr_scoring=scoring,
            attr_playmaking=playmaking,
            attr_rebounding=rebounding,
            attr_defense=defense,
            attr_consistency=consistency,
            attr_clutch=clutch,
            overall_rating=overall,
            archetype=archetype,
            rarity_tier=rarity_tier,
            salary=salary,
            fp_mean=fp_mean,
            fp_std_dev=fp_std_dev,
            is_hot=is_hot,
            is_cold=is_cold,
            form_label=form_label,
            is_active=True,
            is_legend=False,
            injury_status=None,
            doubts_consistency_score=1.0 - (consistency / 100.0),
        )
    
    def _calculate_attribute(self, attr_type: str, player_stats: Dict) -> int:
        """Calculate percentile rank (1–99) for an attribute."""
        # Stub for Phase 0: Return based on basic heuristics
        # In full implementation, compare against all players
        
        if attr_type == "scoring":
            ppg = player_stats.get("ppg", 0)
            ts_pct = player_stats.get("ts_pct", 0.55)
            usage = player_stats.get("usage_rate", 0.25)
            # Simple: PPG-based percentile
            score = min(99, 20 + int(ppg * 2))  # 0 PPG → 20, 40 PPG → 99
            return min(99, max(1, score))
        
        elif attr_type == "consistency":
            # Higher consistency = lower variance
            # Stub: 50 (neutral) for now
            return 50
        
        elif attr_type == "clutch":
            ppg = player_stats.get("ppg", 0)
            # Stub: Star players have higher clutch
            return min(99, max(1, 40 + int(ppg)))
        
        # Default attributes
        return 50
    
    def _calculate_overall(
        self,
        scoring: int, playmaking: int, rebounding: int,
        defense: int, consistency: int, clutch: int
    ) -> int:
        """Calculate overall rating (1–99) from attributes."""
        overall = (
            self.OVERALL_WEIGHTS["scoring"] * scoring +
            self.OVERALL_WEIGHTS["playmaking"] * playmaking +
            self.OVERALL_WEIGHTS["rebounding"] * rebounding +
            self.OVERALL_WEIGHTS["defense"] * defense +
            self.OVERALL_WEIGHTS["consistency"] * consistency +
            self.OVERALL_WEIGHTS["clutch"] * clutch
        )
        return int(min(99, max(30, overall)))
    
    def _classify_archetype(
        self,
        overall: int, scoring: int, playmaking: int,
        rebounding: int, defense: int, consistency: int,
        age: int
    ) -> Archetype:
        """Classify archetype based on attribute signature."""
        # Simplified rules for Phase 0
        
        if overall >= 92 and min(scoring, playmaking, rebounding, defense) >= 70:
            return Archetype.UNICORN
        elif scoring >= 90 and consistency < 45:
            return Archetype.BOOM_BUST
        elif scoring >= 90:
            return Archetype.ELITE_SCORER
        elif playmaking >= 85:
            return Archetype.FLOOR_GENERAL
        elif rebounding >= 90:
            return Archetype.GLASS_CLEANER
        elif scoring >= 75 and defense >= 80:
            return Archetype.TWO_WAY_STAR
        elif defense >= 90 and scoring < 70:
            return Archetype.LOCKDOWN_DEFENDER
        elif age <= 23 and overall >= 75:
            return Archetype.RISING_STAR
        elif all(55 <= attr <= 79 for attr in [scoring, playmaking, defense]):
            return Archetype.GLUE_GUY
        else:
            return Archetype.VERSATILE
    
    def _assign_rarity_tier(self, overall: int) -> RarityTier:
        """Assign rarity tier based on overall rating."""
        if overall >= 92:
            return RarityTier.SUPERSTAR
        elif overall >= 82:
            return RarityTier.STAR
        elif overall >= 70:
            return RarityTier.STARTER
        elif overall >= 55:
            return RarityTier.ROLE_PLAYER
        else:
            return RarityTier.BENCH
    
    def _calculate_salary(
        self,
        overall: int,
        archetype: Archetype,
        rarity_tier: RarityTier
    ) -> int:
        """Calculate salary in dollars."""
        # Base salary
        base = 2000 + (overall * 100)
        
        # Apply archetype modifier
        mod = self.ARCHETYPE_SALARY_MODS.get(archetype, 1.0)
        salary = base * mod
        
        # Round to nearest $100
        salary = round(salary / 100) * 100
        
        # Clamp to tier range
        tier_min, tier_max = self.SALARY_TIERS[rarity_tier]
        return max(tier_min, min(tier_max, int(salary)))
    
    def _detect_form(self, player_stats: Dict) -> Tuple[bool, bool, str]:
        """Detect hot/cold form from last 5 games."""
        # Stub: Placeholder for Phase 0
        # In full implementation, compare recent avg to season avg
        last_5_avg = player_stats.get("last_5_games_avg_ppg", player_stats["ppg"])
        season_avg = player_stats["ppg"]
        
        if last_5_avg > season_avg * 1.15:
            return True, False, "🔥 Hot"
        elif last_5_avg < season_avg * 0.85:
            return False, True, "❄️ Cold"
        else:
            return False, False, "➡️ Neutral"
    
    def _calculate_fp_mean(self, player_stats: Dict) -> float:
        """Calculate mean fantasy points (using scoring formula)."""
        from config import SCORING_CONFIG
        
        pp = player_stats["ppg"] * SCORING_CONFIG["points"]
        rp = player_stats["rpg"] * SCORING_CONFIG["rebounds"]
        ap = player_stats["apg"] * SCORING_CONFIG["assists"]
        sp = player_stats["spg"] * SCORING_CONFIG["steals"]
        bp = player_stats["bpg"] * SCORING_CONFIG["blocks"]
        tp = player_stats["threes_pg"] * SCORING_CONFIG["threes"]
        to = player_stats["tpg"] * SCORING_CONFIG["turnovers"]
        
        return pp + rp + ap + sp + bp + tp + to
    
    def _calculate_fp_std_dev(self, player_stats: Dict, consistency: int) -> float:
        """Calculate FP standard deviation based on consistency."""
        # Stub: Placeholder
        fp_mean = self._calculate_fp_mean(player_stats)
        
        # High consistency (99) → 0.61× CV, Low (30) → 1.16× CV
        cv_mod = 1.0 + (50 - consistency) * 0.008
        cv_mod = max(0.5, min(1.5, cv_mod))
        
        base_cv = 0.20  # 20% CV baseline
        return fp_mean * base_cv * cv_mod
    
    def _build_legend_profile(
        self,
        legend_stats: Dict,
        legend_era: Optional[str]
    ) -> PlayerProfile:
        """Build profile for a Hall of Fame legend."""
        # Legends have fixed attributes
        archetype = Archetype(legend_stats.get("archetype", Archetype.VERSATILE))
        overall = legend_stats.get("overall", 95)
        rarity_tier = RarityTier.LEGEND
        salary = legend_stats.get("salary", 13500)
        
        fp_mean = self._calculate_fp_mean(legend_stats)
        fp_std_dev = self._calculate_fp_std_dev(legend_stats, 80)
        
        return PlayerProfile(
            player_id=legend_stats["player_id"],
            player_name=legend_stats["name"],
            team=legend_stats.get("franchise", ""),
            position=legend_stats["position"],
            secondary_position=None,
            age=0,  # N/A for legends
            headshot_url=legend_stats.get("headshot_url"),
            ppg=legend_stats["ppg"],
            rpg=legend_stats["rpg"],
            apg=legend_stats["apg"],
            spg=legend_stats["spg"],
            bpg=legend_stats["bpg"],
            tpg=legend_stats["tpg"],
            threes_pg=legend_stats["threes_pg"],
            fg_pct=legend_stats.get("fg_pct", 0.500),
            ft_pct=legend_stats.get("ft_pct", 0.750),
            ts_pct=legend_stats.get("ts_pct", 0.570),
            usage_rate=legend_stats.get("usage_rate", 0.30),
            minutes_pg=legend_stats.get("minutes_pg", 36.0),
            attr_scoring=legend_stats.get("attr_scoring", 95),
            attr_playmaking=legend_stats.get("attr_playmaking", 85),
            attr_rebounding=legend_stats.get("attr_rebounding", 85),
            attr_defense=legend_stats.get("attr_defense", 85),
            attr_consistency=legend_stats.get("attr_consistency", 90),
            attr_clutch=legend_stats.get("attr_clutch", 95),
            overall_rating=overall,
            archetype=archetype,
            rarity_tier=rarity_tier,
            salary=salary,
            fp_mean=fp_mean,
            fp_std_dev=fp_std_dev,
            is_hot=False,
            is_cold=False,
            form_label="🏆 Legend",
            is_active=True,
            is_legend=True,
            injury_status=None,
            doubts_consistency_score=0.1,  # High consistency
        )


if __name__ == "__main__":
    # Test
    sample_player = {
        "player_id": 1,
        "name": "LeBron James",
        "team": "LAL",
        "position": "SF",
        "age": 39,
        "ppg": 23.8,
        "rpg": 9.1,
        "apg": 3.9,
        "spg": 1.0,
        "bpg": 0.8,
        "tpg": 2.0,
        "threes_pg": 2.1,
        "ts_pct": 0.615,
        "usage_rate": 0.28,
        "minutes_pg": 30.5,
    }
    
    builder = ProfileBuilder([sample_player])
    profile = builder.build_profile(sample_player)
    print(f"✅ Profile built: {profile.player_name} ({profile.overall_rating} OVR)")
    print(f"   Archetype: {profile.archetype}")
    print(f"   Salary: ${profile.salary:,}")
    print(f"   FP Mean: {profile.fp_mean:.1f}")
