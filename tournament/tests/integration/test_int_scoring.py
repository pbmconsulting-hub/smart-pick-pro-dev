"""Integration tests for tournament.scoring — pure functions, real code."""

from tournament.scoring import (
    calculate_fantasy_points,
    check_bonuses,
    check_penalties,
    score_player_total,
    tiebreak_key,
)


class TestCalculateFantasyPoints:
    def test_typical_line(self):
        line = {"points": 25, "rebounds": 8, "assists": 6, "steals": 2, "blocks": 1, "threes": 3, "turnovers": 3}
        fp = calculate_fantasy_points(line)
        expected = 25 * 1.0 + 8 * 1.2 + 6 * 1.5 + 2 * 3.0 + 1 * 3.0 + 3 * 0.5 - 3 * 1.5
        assert fp == round(expected, 2)

    def test_zeros(self):
        assert calculate_fantasy_points({}) == 0.0

    def test_turnovers_reduce_score(self):
        base = calculate_fantasy_points({"points": 10})
        with_to = calculate_fantasy_points({"points": 10, "turnovers": 5})
        assert with_to < base


class TestCheckBonuses:
    def test_double_double(self):
        line = {"points": 20, "rebounds": 12, "assists": 3, "steals": 1, "blocks": 0}
        result = check_bonuses(line)
        assert "double_double" in result["triggered"]
        assert result["total"] >= 2.0

    def test_triple_double(self):
        line = {"points": 15, "rebounds": 11, "assists": 10, "steals": 2, "blocks": 0}
        result = check_bonuses(line)
        assert "triple_double" in result["triggered"]

    def test_50_point_game(self):
        line = {"points": 55, "rebounds": 5, "assists": 3, "steals": 1, "blocks": 0}
        result = check_bonuses(line)
        assert "points_50" in result["triggered"]

    def test_40_point_game(self):
        line = {"points": 42, "rebounds": 5, "assists": 3, "steals": 1, "blocks": 0}
        result = check_bonuses(line)
        assert "points_40" in result["triggered"]
        assert "points_50" not in result["triggered"]

    def test_20_rebounds(self):
        line = {"points": 10, "rebounds": 22, "assists": 2, "steals": 0, "blocks": 0}
        result = check_bonuses(line)
        assert "rebounds_20" in result["triggered"]

    def test_15_assists(self):
        line = {"points": 10, "rebounds": 5, "assists": 16, "steals": 0, "blocks": 0}
        result = check_bonuses(line)
        assert "assists_15" in result["triggered"]

    def test_five_by_five(self):
        line = {"points": 10, "rebounds": 8, "assists": 7, "steals": 6, "blocks": 5}
        result = check_bonuses(line)
        assert "five_by_five" in result["triggered"]
        assert result["total"] >= 10.0

    def test_no_bonuses(self):
        line = {"points": 8, "rebounds": 4, "assists": 3, "steals": 1, "blocks": 0}
        result = check_bonuses(line)
        assert result["triggered"] == []
        assert result["total"] == 0.0


class TestCheckPenalties:
    def test_deterministic_with_seed(self):
        profile = {"tech_rate": 0.01, "foul_prone": False}
        r1 = check_penalties(profile, seed=42)
        r2 = check_penalties(profile, seed=42)
        assert r1 == r2

    def test_different_seeds_may_differ(self):
        profile = {"tech_rate": 0.99, "foul_prone": True}
        results = {check_penalties(profile, seed=s)["total"] for s in range(100)}
        assert len(results) > 1  # at least some variation

    def test_penalty_total_non_positive(self):
        for seed in range(50):
            result = check_penalties({"tech_rate": 0.02, "foul_prone": True}, seed=seed)
            assert result["total"] <= 0.0


class TestScorePlayerTotal:
    def test_returns_combined(self):
        profile = {"tech_rate": 0.0, "foul_prone": False}
        line = {"points": 30, "rebounds": 10, "assists": 8, "steals": 2, "blocks": 1, "threes": 4, "turnovers": 3}
        result = score_player_total(profile, line, seed=99)
        assert "fantasy_points" in result
        assert "bonuses" in result
        assert "penalties" in result
        assert "total_fp" in result
        assert isinstance(result["total_fp"], float)

    def test_total_equals_sum(self):
        profile = {"tech_rate": 0.0, "foul_prone": False}
        line = {"points": 20, "rebounds": 5, "assists": 5, "steals": 1, "blocks": 0, "threes": 2, "turnovers": 2}
        result = score_player_total(profile, line, seed=12345)
        expected = result["fantasy_points"] + result["bonuses"]["total"] + result["penalties"]["total"]
        assert result["total_fp"] == round(expected, 2)


class TestTiebreakKey:
    def test_higher_score_wins(self):
        a = {"highest_player_score": 60.0, "unique_players": 8, "salary_used": 45000, "created_at": "2025-01-01"}
        b = {"highest_player_score": 50.0, "unique_players": 8, "salary_used": 45000, "created_at": "2025-01-01"}
        assert tiebreak_key(a) < tiebreak_key(b)

    def test_earlier_entry_wins_on_tie(self):
        a = {"highest_player_score": 60.0, "unique_players": 8, "salary_used": 45000, "created_at": "2025-01-01T10:00:00"}
        b = {"highest_player_score": 60.0, "unique_players": 8, "salary_used": 45000, "created_at": "2025-01-01T12:00:00"}
        assert tiebreak_key(a) < tiebreak_key(b)
