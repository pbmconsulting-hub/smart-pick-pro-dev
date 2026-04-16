"""Integration tests for tournament.profiles — real profile building."""

from tournament.profiles import (
    build_player_profiles,
    classify_archetype,
    rarity_tier,
    salary_from_profile,
)


def _make_player(**overrides):
    base = {
        "player_id": "T001",
        "name": "Test Guy",
        "team": "TST",
        "position": "SG",
        "age": 27,
        "ppg": 18.0,
        "rpg": 5.0,
        "apg": 4.0,
        "spg": 1.2,
        "bpg": 0.4,
        "tpg": 2.5,
        "threes_pg": 2.0,
        "fg_pct": 0.46,
        "ft_pct": 0.80,
        "usage_rate": 24.0,
        "minutes_pg": 32.0,
        "points_std": 6.0,
        "rebounds_std": 2.5,
        "assists_std": 2.0,
    }
    base.update(overrides)
    return base


class TestBuildPlayerProfiles:
    def test_returns_list(self):
        profiles = build_player_profiles([_make_player()])
        assert isinstance(profiles, list)
        assert len(profiles) >= 1

    def test_includes_legends_by_default(self):
        profiles = build_player_profiles([_make_player()])
        legends = [p for p in profiles if p.get("is_legend")]
        assert len(legends) == 20

    def test_exclude_legends(self):
        profiles = build_player_profiles([_make_player()], include_legends=False)
        legends = [p for p in profiles if p.get("is_legend")]
        assert len(legends) == 0

    def test_profile_has_all_attributes(self):
        profiles = build_player_profiles([_make_player()], include_legends=False)
        p = profiles[0]
        for key in ("attr_scoring", "attr_playmaking", "attr_rebounding",
                     "attr_defense", "attr_consistency", "attr_clutch"):
            assert key in p
            assert 1 <= p[key] <= 99

    def test_overall_rating_in_range(self):
        profiles = build_player_profiles([_make_player()], include_legends=False)
        assert 30 <= profiles[0]["overall_rating"] <= 99

    def test_salary_assigned(self):
        profiles = build_player_profiles([_make_player()], include_legends=False)
        assert profiles[0]["salary"] >= 3000

    def test_fp_mean_and_std(self):
        profiles = build_player_profiles([_make_player()], include_legends=False)
        p = profiles[0]
        assert "fp_mean" in p
        assert "fp_std_dev" in p
        assert p["fp_mean"] > 0

    def test_empty_input(self):
        profiles = build_player_profiles([], include_legends=True)
        assert len(profiles) == 20

    def test_multiple_active_players(self):
        players = [
            _make_player(player_id="A", name="A", ppg=30.0),
            _make_player(player_id="B", name="B", ppg=10.0),
            _make_player(player_id="C", name="C", ppg=20.0),
        ]
        profiles = build_player_profiles(players, include_legends=False)
        assert len(profiles) == 3


class TestClassifyArchetype:
    def test_elite_scorer(self):
        p = {"attr_scoring": 92, "attr_playmaking": 60, "attr_rebounding": 50,
             "attr_defense": 50, "attr_consistency": 60, "overall_rating": 85,
             "age": 27, "apg": 4.0, "rpg": 5.0, "threes_pg": 1.0}
        assert classify_archetype(p) == "Elite Scorer"

    def test_unicorn(self):
        p = {"attr_scoring": 95, "attr_playmaking": 90, "attr_rebounding": 85,
             "attr_defense": 80, "attr_consistency": 88, "overall_rating": 96,
             "age": 28, "apg": 7.0, "rpg": 10.0, "threes_pg": 2.0}
        assert classify_archetype(p) == "Unicorn"

    def test_boom_bust(self):
        p = {"attr_scoring": 92, "attr_playmaking": 60, "attr_rebounding": 50,
             "attr_defense": 50, "attr_consistency": 40, "overall_rating": 80,
             "age": 25, "apg": 3.0, "rpg": 4.0, "threes_pg": 1.0}
        assert classify_archetype(p) == "Boom/Bust"

    def test_versatile_default(self):
        p = {"attr_scoring": 50, "attr_playmaking": 50, "attr_rebounding": 50,
             "attr_defense": 50, "attr_consistency": 50, "overall_rating": 50,
             "age": 30, "apg": 2.0, "rpg": 3.0, "threes_pg": 0.5}
        assert classify_archetype(p) == "Versatile"


class TestRarityTier:
    def test_legend(self):
        assert rarity_tier(99, is_legend=True) == "Legend"

    def test_superstar(self):
        assert rarity_tier(95) == "Superstar"

    def test_star(self):
        assert rarity_tier(85) == "Star"

    def test_starter(self):
        assert rarity_tier(74) == "Starter"

    def test_role_player(self):
        assert rarity_tier(60) == "Role Player"

    def test_bench(self):
        assert rarity_tier(45) == "Bench"


class TestSalaryFromProfile:
    def test_high_overall_high_salary(self):
        p = {"overall_rating": 95, "archetype": "Elite Scorer", "is_legend": False, "hot_cold_label": "neutral"}
        sal = salary_from_profile(p)
        assert sal >= 9000

    def test_low_overall_floor(self):
        p = {"overall_rating": 40, "archetype": "Versatile", "is_legend": False, "hot_cold_label": "neutral"}
        sal = salary_from_profile(p)
        # base = 2000 + 40*100 = 6000, clamped to [3000, 12000]
        assert sal == 6000

    def test_legend_range(self):
        p = {"overall_rating": 99, "archetype": "Elite Scorer", "is_legend": True, "hot_cold_label": "neutral"}
        sal = salary_from_profile(p)
        assert 12000 <= sal <= 15000

    def test_hot_boost(self):
        base = {"overall_rating": 80, "archetype": "Versatile", "is_legend": False}
        neutral = salary_from_profile({**base, "hot_cold_label": "neutral"})
        hot = salary_from_profile({**base, "hot_cold_label": "hot"})
        assert hot >= neutral

    def test_cold_penalty(self):
        base = {"overall_rating": 80, "archetype": "Versatile", "is_legend": False}
        neutral = salary_from_profile({**base, "hot_cold_label": "neutral"})
        cold = salary_from_profile({**base, "hot_cold_label": "cold"})
        assert cold <= neutral
