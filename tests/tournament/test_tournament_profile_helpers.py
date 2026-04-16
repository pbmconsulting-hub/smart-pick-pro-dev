from pathlib import Path

import tournament.database as tdb
from tournament.manager import (
    create_tournament,
    get_user_career_stats,
    list_user_entries,
)


def _configure_temp_db(monkeypatch, tmp_path: Path):
    db_file = tmp_path / "tournament_test.db"
    monkeypatch.setattr(tdb, "DB_DIRECTORY", tmp_path)
    monkeypatch.setattr(tdb, "TOURNAMENT_DB_PATH", db_file)
    assert tdb.initialize_tournament_database() is True


def test_user_profile_helpers(monkeypatch, tmp_path):
    _configure_temp_db(monkeypatch, tmp_path)

    tid = create_tournament(
        tournament_name="History",
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
                (tournament_id, user_email, display_name, roster_json, total_score, rank, lp_awarded, payout_amount)
            VALUES (?, 'u@example.com', 'U', '[]', 88.8, 2, 10, 0.0)
            """,
            (tid,),
        )
        conn.execute(
            """
            INSERT INTO user_career_stats
                (user_email, display_name, lifetime_entries, lifetime_wins, lifetime_top5, lifetime_earnings, lifetime_lp, career_level)
            VALUES ('u@example.com', 'U', 4, 1, 2, 25.0, 120, 5)
            """
        )
        conn.commit()

    entries = list_user_entries("u@example.com")
    career = get_user_career_stats("u@example.com")

    assert len(entries) == 1
    assert entries[0]["tournament_name"] == "History"
    assert int(career["lifetime_entries"]) == 4
    assert int(career["lifetime_lp"]) == 120
