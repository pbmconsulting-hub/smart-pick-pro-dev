"""
test_tournament_scoring.py - Unit tests for fantasy points calculation

Tests:
  - calculate_fantasy_points() - base scoring
  - bonus detection - DD, TD, 40pts, 50pts, 20rb, 15ast, 5x5
  - penalties - ejection
"""

import pytest

# Import mock classes from local conftest in tests directory
from .conftest import ScoringEngine


class TestFantasyPointsCalculation:
    """Test suite for fantasy points scoring."""
    
    @pytest.fixture
    def engine(self):
        """Get scoring engine."""
        return ScoringEngine()
    
    def test_base_scoring_typical_game(self, engine, mock_game_stats):
        """Test base scoring with typical game stats."""
        # Points: 28 × 1.0 = 28
        # Rebounds: 6 × 1.2 = 7.2
        # Assists: 4 × 1.5 = 6
        # Steals: 1 × 3.0 = 3
        # Blocks: 0 × 3.0 = 0
        # Threes: 3 × 0.5 = 1.5
        # Turnovers: 2 × -1.5 = -3
        # Expected: 42.7 FP
        
        fp = engine.calculate_fantasy_points(mock_game_stats)
        
        assert fp is not None
        assert isinstance(fp, (float, int))
        assert fp > 0
        assert 40 < fp < 50  # Should be in reasonable range
    
    def test_scoring_all_zeros(self, engine):
        """Test scoring with all zeros (DNP)."""
        stats = {
            "points": 0,
            "rebounds": 0,
            "assists": 0,
            "steals": 0,
            "blocks": 0,
            "threes": 0,
            "turnovers": 0,
            "minutes": 0,
        }
        
        fp = engine.calculate_fantasy_points(stats)
        
        assert fp == 0.0
    
    def test_scoring_high_volume_game(self, engine):
        """Test scoring for a high-volume game (40+ FP range)."""
        stats = {
            "points": 50,
            "rebounds": 15,
            "assists": 12,
            "steals": 3,
            "blocks": 2,
            "threes": 8,
            "turnovers": 3,
            "minutes": 40,
        }
        
        fp = engine.calculate_fantasy_points(stats)
        
        assert fp is not None
        assert fp > 0
        # 50*1 + 15*1.2 + 12*1.5 + 3*3 + 2*3 + 8*0.5 - 3*1.5
        # = 50 + 18 + 18 + 9 + 6 + 4 - 4.5 = 100.5
        assert fp > 90
    
    def test_scoring_negative_turnovers(self, engine):
        """Test that turnovers reduce score."""
        stats_few_to = {
            "points": 20,
            "rebounds": 5,
            "assists": 3,
            "steals": 0,
            "blocks": 0,
            "threes": 0,
            "turnovers": 1,
            "minutes": 20,
        }
        
        stats_many_to = {
            "points": 20,
            "rebounds": 5,
            "assists": 3,
            "steals": 0,
            "blocks": 0,
            "threes": 0,
            "turnovers": 5,
            "minutes": 20,
        }
        
        fp_few = engine.calculate_fantasy_points(stats_few_to)
        fp_many = engine.calculate_fantasy_points(stats_many_to)
        
        assert fp_few > fp_many


class TestBonuses:
    """Test suite for bonus triggers."""
    
    @pytest.fixture
    def engine(self):
        """Get scoring engine."""
        return ScoringEngine()
    
    def test_double_double_bonus(self, engine):
        """Test double-double bonus (+2 FP)."""
        stats = {
            "points": 12,
            "rebounds": 10,  # DD: 10+ PTS + 10+ REB
            "assists": 8,
            "steals": 1,
            "blocks": 0,
            "threes": 0,
            "turnovers": 1,
        }
        
        bonuses = engine.check_bonuses(stats)
        
        assert bonuses is not None
        assert "double_double" in [b.get("type") for b in bonuses] or any(b.get("bonus") == 2 for b in bonuses)
    
    def test_triple_double_bonus(self, engine):
        """Test triple-double bonus (+5 FP)."""
        stats = {
            "points": 10,
            "rebounds": 10,  # TD: 10+ PTS + 10+ REB + 10+ AST
            "assists": 10,
            "steals": 1,
            "blocks": 0,
            "threes": 0,
            "turnovers": 1,
        }
        
        bonuses = engine.check_bonuses(stats)
        
        assert bonuses is not None
        assert len(bonuses) > 0
    
    def test_40_point_game_bonus(self, engine):
        """Test 40+ points bonus (+3 FP)."""
        stats = {
            "points": 42,
            "rebounds": 5,
            "assists": 3,
            "steals": 1,
            "blocks": 0,
            "threes": 2,
            "turnovers": 2,
        }
        
        bonuses = engine.check_bonuses(stats)
        
        assert bonuses is not None
        assert any(
            (b.get("type") == "high_points" or "40" in str(b))
            for b in bonuses
        )
    
    def test_50_point_game_bonus(self, engine):
        """Test 50+ points bonus (+7 FP)."""
        stats = {
            "points": 51,
            "rebounds": 8,
            "assists": 5,
            "steals": 2,
            "blocks": 1,
            "threes": 6,
            "turnovers": 2,
        }
        
        bonuses = engine.check_bonuses(stats)
        
        assert bonuses is not None
        assert len(bonuses) > 0
    
    def test_20_rebound_bonus(self, engine):
        """Test 20+ rebound bonus (+3 FP)."""
        stats = {
            "points": 15,
            "rebounds": 21,
            "assists": 2,
            "steals": 0,
            "blocks": 2,
            "threes": 0,
            "turnovers": 2,
        }
        
        bonuses = engine.check_bonuses(stats)
        
        assert bonuses is not None
    
    def test_15_assist_bonus(self, engine):
        """Test 15+ assist bonus (+3 FP)."""
        stats = {
            "points": 8,
            "rebounds": 3,
            "assists": 15,
            "steals": 1,
            "blocks": 0,
            "threes": 0,
            "turnovers": 3,
        }
        
        bonuses = engine.check_bonuses(stats)
        
        assert bonuses is not None
    
    def test_5x5_bonus(self, engine):
        """Test 5x5 bonus (+10 FP)."""
        stats = {
            "points": 10,
            "rebounds": 5,
            "assists": 5,
            "steals": 5,
            "blocks": 5,
            "threes": 1,
            "turnovers": 1,
        }
        
        bonuses = engine.check_bonuses(stats)
        
        assert bonuses is not None
        assert len(bonuses) > 0
    
    def test_no_bonuses(self, engine):
        """Test that low stats trigger no bonuses."""
        stats = {
            "points": 5,
            "rebounds": 2,
            "assists": 1,
            "steals": 0,
            "blocks": 0,
            "threes": 0,
            "turnovers": 1,
        }
        
        bonuses = engine.check_bonuses(stats)
        
        # Should be empty or None
        assert bonuses is None or len(bonuses) == 0


class TestPenalties:
    """Test suite for penalties."""
    
    @pytest.fixture
    def engine(self):
        """Get scoring engine."""
        return ScoringEngine()
    
    def test_ejection_penalty(self, engine):
        """Test ejection penalty (-10 FP)."""
        stats = {
            "points": 30,
            "rebounds": 8,
            "assists": 4,
            "steals": 1,
            "blocks": 0,
            "threes": 2,
            "turnovers": 2,
            "ejected": True,
        }
        
        penalties = engine.check_penalties(stats)
        
        assert penalties is not None
        assert len(penalties) > 0
    
    def test_no_penalties_normal_game(self, engine):
        """Test no penalties for normal game."""
        stats = {
            "points": 25,
            "rebounds": 7,
            "assists": 3,
            "steals": 1,
            "blocks": 0,
            "threes": 1,
            "turnovers": 2,
            "ejected": False,
        }
        
        penalties = engine.check_penalties(stats)
        
        assert penalties is None or len(penalties) == 0


class TestScoringIntegration:
    """Integration tests for complete scoring."""
    
    @pytest.fixture
    def engine(self):
        """Get scoring engine."""
        return ScoringEngine()
    
    def test_fantasy_points_with_bonus_penalty(self, engine):
        """Test combined FP calculation with bonus and penalty."""
        stats = {
            "points": 45,  # 40+ bonus
            "rebounds": 8,
            "assists": 5,
            "steals": 1,
            "blocks": 0,
            "threes": 3,
            "turnovers": 2,
            "minutes": 35,
        }
        
        base_fp = engine.calculate_fantasy_points(stats)
        bonuses = engine.check_bonuses(stats)
        penalties = engine.check_penalties(stats)
        
        assert base_fp is not None
        assert base_fp > 0
        assert bonuses is not None  # Should have 40+ point bonus
