import json
from pathlib import Path

import tournament.database as tdb
from tournament.manager import create_tournament, resolve_tournament, submit_entry


def _configure_temp_db(monkeypatch, tmp_path: Path):
    db_file = tmp_path / "tournament_test.db"
    monkeypatch.setattr(tdb, "DB_DIRECTORY", tmp_path)
    monkeypatch.setattr(tdb, "TOURNAMENT_DB_PATH", db_file)
    assert tdb.initialize_tournament_database() is True
    return db_file


def test_create_and_submit_entry(monkeypatch, tmp_path):
    _configure_temp_db(monkeypatch, tmp_path)

    tid = create_tournament(
        tournament_name="Test Open",
        court_tier="Open",
        entry_fee=0.0,
        min_entries=1,
        max_entries=12,
        lock_time="2026-04-20T20:00:00",
    )
    assert tid > 0

    roster = [{"player_id": f"P{i}", "salary": 5000, "is_legend": False} for i in range(1, 9)]
    ok, msg, entry_id = submit_entry(tid, "user@example.com", "User", roster)
    assert ok is True
    assert entry_id is not None
    assert "Entry submitted" in msg


def test_resolve_tournament_cancel_when_min_not_met(monkeypatch, tmp_path):
    _configure_temp_db(monkeypatch, tmp_path)

    tid = create_tournament(
        tournament_name="Needs 2",
        court_tier="Open",
        entry_fee=0.0,
        min_entries=2,
        max_entries=12,
        lock_time="2026-04-20T20:00:00",
    )

    roster = [{"player_id": f"P{i}", "salary": 5000, "is_legend": False} for i in range(1, 9)]
    submit_entry(tid, "one@example.com", "One", roster)

    result = resolve_tournament(tid)
    assert result["success"] is True
    assert result["status"] == "cancelled"


def test_resolve_tournament_scores_entries(monkeypatch, tmp_path):
    _configure_temp_db(monkeypatch, tmp_path)

    # Speed and determinism for unit tests.
    monkeypatch.setattr("tournament.manager.generate_tournament_seed", lambda: ("abc" * 22, 1234))
    monkeypatch.setattr("tournament.manager.simulate_tournament_environment", lambda seed: {
        "blowout_risk_factor": 0.1,
        "pace_adjustment_factor": 1.0,
        "vegas_spread": 1.5,
        "game_total": 225.0,
        "environment_label": "Standard Game",
    })
    monkeypatch.setattr("tournament.manager.simulate_player_full_line", lambda profile, env, seed: {
        "points": 20,
        "rebounds": 8,
        "assists": 5,
        "steals": 1,
        "blocks": 1,
        "turnovers": 2,
        "threes": 3,
    })

    tid = create_tournament(
        tournament_name="Resolve Me",
        court_tier="Open",
        entry_fee=0.0,
        min_entries=1,
        max_entries=12,
        lock_time="2026-04-20T20:00:00",
    )

    with tdb.get_tournament_connection() as conn:
        for i in range(1, 9):
            profile = {
                "player_id": f"P{i}",
                "player_name": f"Player {i}",
                "ppg": 20.0,
                "rpg": 6.0,
                "apg": 5.0,
                "spg": 1.2,
                "bpg": 0.7,
                "tpg": 2.4,
                "threes_pg": 2.1,
                "minutes_pg": 33.0,
                "attr_consistency": 60,
                "attr_clutch": 70,
            }
            conn.execute(
                """
                INSERT INTO player_profiles
                    (player_id, player_name, team, position, overall_rating, archetype,
                     rarity_tier, salary, profile_json, updated_at)
                VALUES (?, ?, 'AAA', 'PG', 80, 'Versatile', 'Starter', 7000, ?, datetime('now'))
                """,
                (f"P{i}", f"Player {i}", json.dumps(profile)),
            )
        conn.commit()

    roster = [{"player_id": f"P{i}", "salary": 5000, "is_legend": False} for i in range(1, 9)]
    submit_entry(tid, "user@example.com", "User", roster)

    result = resolve_tournament(tid)
    assert result["success"] is True
    assert result["status"] == "resolved"
    assert result["entries"] == 1
