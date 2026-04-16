"""Integration tests for tournament.scheduler — real schedule creation."""

from datetime import date, datetime, timedelta

from tournament.manager import get_tournament, list_tournaments
from tournament.scheduler import create_weekly_schedule, resolve_locked_tournaments


class TestCreateWeeklySchedule:
    def test_creates_tournaments(self, isolated_db):
        ids = create_weekly_schedule(anchor_date=date(2099, 6, 3))  # Tuesday
        assert len(ids) > 0
        assert all(isinstance(i, int) for i in ids)

    def test_creates_3_days_x_3_tiers(self, isolated_db):
        ids = create_weekly_schedule(anchor_date=date(2099, 6, 3))
        assert len(ids) == 9  # 3 days * 3 tiers

    def test_tournaments_are_open(self, isolated_db):
        ids = create_weekly_schedule(anchor_date=date(2099, 6, 3))
        for tid in ids:
            t = get_tournament(tid)
            assert t["status"] == "open"

    def test_includes_all_tiers(self, isolated_db):
        ids = create_weekly_schedule(anchor_date=date(2099, 6, 3))
        tiers = {get_tournament(tid)["court_tier"] for tid in ids}
        assert tiers == {"Open", "Pro", "Elite"}


class TestResolveLockedTournaments:
    def test_no_tournaments_returns_empty(self, isolated_db):
        results = resolve_locked_tournaments(now=datetime(2099, 6, 5, 21, 0))
        assert results == []

    def test_resolves_past_lock(self, isolated_db):
        ids = create_weekly_schedule(anchor_date=date(2099, 6, 3))
        # All lock at 8pm; set now to 9pm on Saturday (latest day)
        far_future = datetime(2099, 6, 7, 21, 0)
        results = resolve_locked_tournaments(now=far_future)
        # All should be attempted (some will cancel due to min entries not met)
        assert len(results) == len(ids)

    def test_does_not_resolve_future_lock(self, isolated_db):
        create_weekly_schedule(anchor_date=date(2099, 6, 3))
        # Set now to Monday *before* the earliest lock (Tuesday 8pm)
        early = datetime(2099, 6, 2, 10, 0)
        results = resolve_locked_tournaments(now=early)
        assert len(results) == 0
