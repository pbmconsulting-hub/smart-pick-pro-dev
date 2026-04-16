from tournament.simulation import (
    generate_tournament_seed,
    simulate_player_full_line,
    simulate_tournament_environment,
)


def test_generate_tournament_seed_shape():
    raw, seed = generate_tournament_seed()
    assert isinstance(raw, str)
    assert len(raw) == 64
    assert isinstance(seed, int)


def test_simulate_tournament_environment_is_deterministic_for_seed():
    env_a = simulate_tournament_environment(12345)
    env_b = simulate_tournament_environment(12345)
    assert env_a == env_b
    assert 0.0 <= env_a["blowout_risk_factor"] <= 1.0
    assert env_a["pace_adjustment_factor"] > 0.0


def test_simulate_player_full_line_with_mocked_engine(monkeypatch):
    def fake_run_quantum_matrix_simulation(**kwargs):
        mean = kwargs["projected_stat_average"]
        return {"simulated_results": [mean - 1, mean, mean + 1]}

    monkeypatch.setattr("tournament.simulation.run_quantum_matrix_simulation", fake_run_quantum_matrix_simulation)
    monkeypatch.setattr("tournament.simulation._load_recent_stat_logs", lambda profile, stat_type: [])

    profile = {
        "player_id": "42",
        "ppg": 24.0,
        "rpg": 8.0,
        "apg": 6.0,
        "spg": 1.5,
        "bpg": 0.8,
        "tpg": 3.1,
        "threes_pg": 2.9,
        "minutes_pg": 34.0,
        "attr_consistency": 62,
        "attr_clutch": 78,
        "hot_cold_label": "neutral",
    }
    env = {
        "blowout_risk_factor": 0.12,
        "pace_adjustment_factor": 1.01,
        "vegas_spread": 2.5,
        "game_total": 226.0,
    }

    line = simulate_player_full_line(profile, env, tournament_seed=99)
    assert set(line.keys()) == {"points", "rebounds", "assists", "steals", "blocks", "turnovers", "threes"}
    assert all(v >= 0 for v in line.values())
