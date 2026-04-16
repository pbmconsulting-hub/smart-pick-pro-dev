"""Integration tests for tournament.simulation — seed gen + simulation wrappers.

Engine A/B are mocked (parent app), but tournament.simulation code is real.
"""

from tournament.simulation import (
    STAT_TYPES,
    generate_tournament_seed,
    simulate_player_full_line,
    simulate_player_stat,
    simulate_tournament_environment,
)


class TestGenerateTournamentSeed:
    def test_returns_tuple(self):
        raw, seed_int = generate_tournament_seed()
        assert isinstance(raw, str)
        assert isinstance(seed_int, int)

    def test_raw_is_hex(self):
        raw, _ = generate_tournament_seed()
        int(raw, 16)  # should not raise

    def test_seeds_unique(self):
        seeds = {generate_tournament_seed()[0] for _ in range(20)}
        assert len(seeds) == 20


class TestSimulateTournamentEnvironment:
    def test_returns_dict(self):
        _, seed_int = generate_tournament_seed()
        env = simulate_tournament_environment(seed_int)
        assert isinstance(env, dict)

    def test_has_required_keys(self):
        _, seed_int = generate_tournament_seed()
        env = simulate_tournament_environment(seed_int)
        for key in ("home_score", "away_score", "blowout_risk_factor",
                     "pace_adjustment_factor", "environment_label",
                     "vegas_spread", "game_total"):
            assert key in env, f"Missing key: {key}"

    def test_deterministic(self):
        env1 = simulate_tournament_environment(42)
        env2 = simulate_tournament_environment(42)
        assert env1 == env2


class TestSimulatePlayerStat:
    def test_returns_int(self):
        profile = {
            "player_id": "P1", "ppg": 25.0, "rpg": 8.0, "apg": 6.0,
            "spg": 1.5, "bpg": 0.5, "tpg": 3.0, "threes_pg": 2.0,
            "attr_consistency": 80, "attr_clutch": 75,
            "hot_cold_label": "neutral", "minutes_pg": 34.0,
        }
        env = {
            "blowout_risk_factor": 0.10,
            "pace_adjustment_factor": 1.00,
            "vegas_spread": 3.0,
            "game_total": 220.0,
        }
        result = simulate_player_stat(profile, "points", env, seed=42)
        assert isinstance(result, int)
        assert result >= 0

    def test_zero_mean_returns_zero(self):
        profile = {"ppg": 0.0, "attr_consistency": 50, "attr_clutch": 50,
                    "hot_cold_label": "neutral", "minutes_pg": 0.0}
        env = {"blowout_risk_factor": 0.10, "pace_adjustment_factor": 1.0,
               "vegas_spread": 0.0, "game_total": 200.0}
        assert simulate_player_stat(profile, "points", env, seed=1) == 0


class TestSimulatePlayerFullLine:
    def test_returns_all_stats(self):
        profile = {
            "player_id": "P1", "ppg": 22.0, "rpg": 7.0, "apg": 5.0,
            "spg": 1.3, "bpg": 0.6, "tpg": 2.5, "threes_pg": 2.2,
            "attr_consistency": 70, "attr_clutch": 70,
            "hot_cold_label": "neutral", "minutes_pg": 33.0,
        }
        env = {
            "blowout_risk_factor": 0.10,
            "pace_adjustment_factor": 1.00,
            "vegas_spread": 3.0,
            "game_total": 220.0,
        }
        line = simulate_player_full_line(profile, env, tournament_seed=42)
        for stat in STAT_TYPES:
            assert stat in line
            assert isinstance(line[stat], int)

    def test_deterministic_same_seed(self):
        profile = {
            "player_id": "P1", "ppg": 20.0, "rpg": 6.0, "apg": 4.0,
            "spg": 1.0, "bpg": 0.5, "tpg": 2.0, "threes_pg": 1.5,
            "attr_consistency": 60, "attr_clutch": 60,
            "hot_cold_label": "neutral", "minutes_pg": 30.0,
        }
        env = {"blowout_risk_factor": 0.10, "pace_adjustment_factor": 1.0,
               "vegas_spread": 2.0, "game_total": 210.0}
        line1 = simulate_player_full_line(profile, env, tournament_seed=100)
        line2 = simulate_player_full_line(profile, env, tournament_seed=100)
        assert line1 == line2
