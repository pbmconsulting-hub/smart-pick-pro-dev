"""Standalone tournament notification helpers built on event log rows."""

from __future__ import annotations

from tournament.events import list_events, log_event


NOTIFICATION_TYPES = {
    "entry_accepted": "notification.entry_accepted",
    "lock_warning": "notification.lock_warning",
    "player_locked": "notification.player_locked",
    "tournament_open": "notification.tournament_open",
    "tournament_resolved": "notification.tournament_resolved",
    "results_posted": "notification.results_posted",
    "badges_earned": "notification.badges_earned",
    "level_up": "notification.level_up",
    "connect_onboarding_required": "notification.connect_onboarding_required",
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


def notify_tournament_open(tournament_id: int, *, message: str | None = None) -> int:
    return send_notification(
        "tournament_open",
        message or f"Tournament #{int(tournament_id)} is now open for entries",
        tournament_id=int(tournament_id),
    )


def notify_player_locked(tournament_id: int, *, user_email: str | None = None) -> int:
    return send_notification(
        "player_locked",
        f"Tournament #{int(tournament_id)} has locked",
        tournament_id=int(tournament_id),
        user_email=user_email,
    )


def notify_results_posted(tournament_id: int, *, entry_id: int | None = None, user_email: str | None = None, rank: int | None = None) -> int:
    metadata = {"rank": rank} if rank is not None else None
    return send_notification(
        "results_posted",
        f"Results are in for tournament #{int(tournament_id)}",
        tournament_id=int(tournament_id),
        entry_id=entry_id,
        user_email=user_email,
        metadata=metadata,
    )


def notify_badges_earned(user_email: str, badge_keys: list[str], *, tournament_id: int | None = None) -> int:
    keys = [str(k) for k in (badge_keys or []) if str(k)]
    return send_notification(
        "badges_earned",
        f"You earned {len(keys)} badge(s): {', '.join(keys)}",
        tournament_id=tournament_id,
        user_email=user_email,
        metadata={"badge_keys": keys},
    )


def notify_level_up(user_email: str, new_level: int, *, tournament_id: int | None = None) -> int:
    return send_notification(
        "level_up",
        f"Level up! You reached Level {int(new_level)}",
        tournament_id=tournament_id,
        user_email=user_email,
        metadata={"new_level": int(new_level)},
    )
