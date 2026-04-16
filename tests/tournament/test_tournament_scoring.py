from tournament.scoring import calculate_fantasy_points, check_bonuses, score_player_total


def test_calculate_fantasy_points_math():
    line = {
        "points": 30,
        "rebounds": 10,
        "assists": 8,
        "steals": 2,
        "blocks": 1,
        "turnovers": 4,
        "threes": 5,
    }
    fp = calculate_fantasy_points(line)
    assert fp == 59.5


def test_check_bonuses_triple_double_and_milestones():
    line = {
        "points": 42,
        "rebounds": 12,
        "assists": 11,
        "steals": 1,
        "blocks": 0,
        "turnovers": 3,
        "threes": 4,
    }
    bonuses = check_bonuses(line)
    assert "triple_double" in bonuses["triggered"]
    assert "points_40" in bonuses["triggered"]
    assert bonuses["total"] == 8.0


def test_score_player_total_has_expected_keys():
    profile = {"tech_rate": 0.001, "foul_prone": False}
    line = {
        "points": 20,
        "rebounds": 6,
        "assists": 5,
        "steals": 1,
        "blocks": 1,
        "turnovers": 2,
        "threes": 3,
    }
    scored = score_player_total(profile, line, seed=123)
    assert "fantasy_points" in scored
    assert "bonuses" in scored
    assert "penalties" in scored
    assert "total_fp" in scored
