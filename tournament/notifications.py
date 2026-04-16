"""Standalone tournament notification helpers built on event log rows."""

from __future__ import annotations

from tournament.events import list_events, log_event


NOTIFICATION_TYPES = {
    "entry_accepted": "notification.entry_accepted",
    "lock_warning": "notification.lock_warning",
    "tournament_resolved": "notification.tournament_resolved",
    "payout_sent": "notification.payout_sent",
    "refund_sent": "notification.refund_sent",
}


def send_notification(
    notification_key: str,
    message: str,
    *,
    tournament_id: int | None = None,
    entry_id: int | None = None,
    user_email: str | None = None,
    metadata: dict | None = None,
) -> int:
    """Persist a user-facing notification as an event record."""
    event_type = NOTIFICATION_TYPES.get(notification_key, f"notification.{notification_key}")
    return log_event(
        event_type=event_type,
        message=message,
        tournament_id=tournament_id,
        entry_id=entry_id,
        user_email=user_email,
        severity="info",
        metadata=metadata or {},
    )


def list_user_notifications(user_email: str, limit: int = 50) -> list[dict]:
    """Return latest notification events for a specific user."""
    events = list_events(limit=max(1, limit * 4))
    email = (user_email or "").strip().lower()
    filtered = [
        e for e in events
        if str(e.get("event_type", "")).startswith("notification.")
        and str(e.get("user_email", "")).strip().lower() == email
    ]
    return filtered[:limit]
