from datetime import date, datetime

from tournament.scheduler import create_weekly_schedule, resolve_locked_tournaments


def test_create_weekly_schedule_creates_nine(monkeypatch):
    created = []

    def fake_create_tournament(**kwargs):
        created.append(kwargs)
        return len(created)

    monkeypatch.setattr("tournament.scheduler.create_tournament", fake_create_tournament)

    ids = create_weekly_schedule(anchor_date=date(2026, 4, 15))
    assert len(ids) == 9
    assert len(created) == 9


def test_resolve_locked_tournaments(monkeypatch):
    monkeypatch.setattr(
        "tournament.scheduler.list_open_tournaments",
        lambda: [
            {"tournament_id": 1, "lock_time": "2026-04-15T18:00:00"},
            {"tournament_id": 2, "lock_time": "2026-04-15T22:00:00"},
        ],
    )
    monkeypatch.setattr("tournament.scheduler.resolve_tournament", lambda tid: {"id": tid, "success": True})

    out = resolve_locked_tournaments(now=datetime.fromisoformat("2026-04-15T20:00:00"))
    assert len(out) == 1
    assert out[0]["id"] == 1
