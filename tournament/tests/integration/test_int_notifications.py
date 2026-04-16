"""Integration tests for tournament.notifications — real DB notifications."""

from tournament.notifications import (
    NOTIFICATION_TYPES,
    list_user_notifications,
    send_notification,
)


class TestSendNotification:
    def test_returns_event_id(self, isolated_db):
        nid = send_notification("entry_accepted", "Your entry was accepted", user_email="a@b.com")
        assert isinstance(nid, int)
        assert nid > 0

    def test_known_key_maps_to_event_type(self, isolated_db):
        send_notification("payout_sent", "Payout!", user_email="u@x.com", tournament_id=1)
        from tournament.events import list_events
        events = list_events()
        types = [e["event_type"] for e in events]
        assert NOTIFICATION_TYPES["payout_sent"] in types

    def test_unknown_key_prefixed(self, isolated_db):
        send_notification("custom_thing", "yo", user_email="u@x.com")
        from tournament.events import list_events
        events = list_events()
        assert any(e["event_type"] == "notification.custom_thing" for e in events)


class TestListUserNotifications:
    def test_empty_for_unknown_user(self, isolated_db):
        assert list_user_notifications("nobody@x.com") == []

    def test_returns_only_user_notifications(self, isolated_db):
        send_notification("entry_accepted", "a", user_email="alice@x.com")
        send_notification("entry_accepted", "b", user_email="bob@x.com")
        send_notification("payout_sent", "c", user_email="alice@x.com")

        alice = list_user_notifications("alice@x.com")
        assert len(alice) == 2
        assert all(e["user_email"] == "alice@x.com" for e in alice)

    def test_limit_respected(self, isolated_db):
        for i in range(10):
            send_notification("entry_accepted", f"n{i}", user_email="u@x.com")
        limited = list_user_notifications("u@x.com", limit=3)
        assert len(limited) == 3
