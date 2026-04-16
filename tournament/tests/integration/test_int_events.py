"""Integration tests for tournament.events — real DB event logging."""

from tournament.events import list_events, log_event


class TestLogEvent:
    def test_returns_int_event_id(self, isolated_db):
        eid = log_event("test.event", "hello world")
        assert isinstance(eid, int)
        assert eid > 0

    def test_increments(self, isolated_db):
        e1 = log_event("test.a", "first")
        e2 = log_event("test.b", "second")
        assert e2 > e1

    def test_with_tournament_id(self, isolated_db):
        eid = log_event("test.tid", "msg", tournament_id=42)
        events = list_events(tournament_id=42)
        assert any(e["event_id"] == eid for e in events)

    def test_with_metadata(self, isolated_db):
        eid = log_event("test.meta", "msg", metadata={"key": "value"})
        events = list_events()
        match = [e for e in events if e["event_id"] == eid]
        assert len(match) == 1
        assert match[0]["metadata"]["key"] == "value"


class TestListEvents:
    def test_returns_list(self, isolated_db):
        assert isinstance(list_events(), list)

    def test_filter_by_type(self, isolated_db):
        log_event("alpha", "a")
        log_event("beta", "b")
        log_event("alpha", "c")
        alphas = list_events(event_type="alpha")
        assert all(e["event_type"] == "alpha" for e in alphas)
        assert len(alphas) == 2

    def test_limit(self, isolated_db):
        for i in range(10):
            log_event("bulk", f"event {i}")
        limited = list_events(limit=3)
        assert len(limited) == 3

    def test_order_desc(self, isolated_db):
        e1 = log_event("order", "first")
        e2 = log_event("order", "second")
        events = list_events(event_type="order")
        assert events[0]["event_id"] == e2  # most recent first
