from tournament.profiles import build_player_profiles, classify_archetype, salary_from_profile


def test_build_player_profiles_includes_legends():
    players = [
        {
            "player_id": "1",
            "name": "Alpha Guard",
            "team": "AAA",
            "position": "PG",
            "points_avg": 28.0,
            "rebounds_avg": 5.0,
            "assists_avg": 8.5,
            "steals_avg": 1.4,
            "blocks_avg": 0.3,
            "turnovers_avg": 2.9,
            "threes_avg": 3.4,
            "minutes_avg": 35.0,
            "usage_rate": 31.0,
            "points_std": 5.8,
            "rebounds_std": 2.0,
            "assists_std": 2.8,
            "fg_pct": 0.49,
            "ft_pct": 0.86,
        }
    ]

    profiles = build_player_profiles(players, include_legends=True)
    assert len(profiles) >= 21

    active = [p for p in profiles if p.get("player_id") == "1"][0]
    assert 3000 <= active["salary"] <= 12000
    assert 30 <= active["overall_rating"] <= 99



def test_archetype_and_salary_rules():
    profile = {
        "attr_scoring": 93,
        "attr_playmaking": 88,
        "attr_rebounding": 75,
        "attr_defense": 81,
        "attr_consistency": 60,
        "overall_rating": 94,
        "apg": 8.1,
        "rpg": 7.2,
        "threes_pg": 2.4,
        "age": 28,
        "hot_cold_label": "hot",
        "is_legend": False,
    }
    profile["archetype"] = classify_archetype(profile)
    salary = salary_from_profile(profile)

    assert profile["archetype"] in {"Unicorn", "Two-Way Star", "Elite Scorer"}
    assert 3000 <= salary <= 12000
