from pathlib import Path

import tournament.database as tdb
from tournament.events import log_event
from tournament.exports import (
    export_tournament_entries_csv,
    export_tournament_events_csv,
    export_tournament_scores_csv,
)
from tournament.manager import create_tournament


def _configure_temp_db(monkeypatch, tmp_path: Path):
    db_file = tmp_path / "tournament_test.db"
    monkeypatch.setattr(tdb, "DB_DIRECTORY", tmp_path)
    monkeypatch.setattr(tdb, "TOURNAMENT_DB_PATH", db_file)
    assert tdb.initialize_tournament_database() is True


def test_exports_generate_csv(monkeypatch, tmp_path):
    _configure_temp_db(monkeypatch, tmp_path)

    tid = create_tournament(
        tournament_name="Export",
        court_tier="Open",
        entry_fee=0.0,
        min_entries=1,
        max_entries=12,
        lock_time="2026-04-20T20:00:00",
    )

    with tdb.get_tournament_connection() as conn:
        conn.execute(
            """
            INSERT INTO tournament_entries
                (tournament_id, user_email, display_name, roster_json, total_score, rank)
            VALUES (?, 'u@example.com', 'U', '[]', 101.5, 1)
            """,
            (tid,),
        )
        conn.execute(
            """
            INSERT INTO simulated_scores
                (tournament_id, player_id, player_name, line_json, fantasy_points, total_fp)
            VALUES (?, 'P1', 'Player One', '{"points":20,"rebounds":8,"assists":5,"steals":1,"blocks":1,"turnovers":2,"threes":3}', 42.0, 45.0)
            """,
            (tid,),
        )
        conn.commit()

    log_event("unit.export", "export test", tournament_id=tid)

    entries_csv = export_tournament_entries_csv(tid)
    scores_csv = export_tournament_scores_csv(tid)
    events_csv = export_tournament_events_csv(tournament_id=tid)

    assert "entry_id" in entries_csv
    assert "u@example.com" in entries_csv
    assert "player_id" in scores_csv
    assert "Player One" in scores_csv
    assert "unit.export" in events_csv
