from pathlib import Path

import tournament.database as tdb
from tournament.events import list_events, log_event
from tournament.notifications import list_user_notifications, send_notification


def _configure_temp_db(monkeypatch, tmp_path: Path):
    db_file = tmp_path / "tournament_test.db"
    monkeypatch.setattr(tdb, "DB_DIRECTORY", tmp_path)
    monkeypatch.setattr(tdb, "TOURNAMENT_DB_PATH", db_file)
    assert tdb.initialize_tournament_database() is True


def test_log_and_list_events(monkeypatch, tmp_path):
    _configure_temp_db(monkeypatch, tmp_path)

    eid = log_event(
        "unit.test",
        "hello event",
        tournament_id=7,
        entry_id=3,
        user_email="u@example.com",
        metadata={"k": 1},
    )
    assert eid > 0

    events = list_events(tournament_id=7, limit=10)
    assert len(events) >= 1
    assert events[0]["event_type"] == "unit.test"
    assert events[0]["metadata"]["k"] == 1


def test_send_and_list_notifications(monkeypatch, tmp_path):
    _configure_temp_db(monkeypatch, tmp_path)

    nid = send_notification(
        "entry_accepted",
        "entry accepted",
        tournament_id=1,
        entry_id=2,
        user_email="notify@example.com",
    )
    assert nid > 0

    notifications = list_user_notifications("notify@example.com")
    assert len(notifications) == 1
    assert notifications[0]["event_type"].startswith("notification.")
