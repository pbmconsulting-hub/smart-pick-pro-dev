"""Standalone tournament schedule automation."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from tournament.events import log_event
from tournament.manager import create_tournament, list_open_tournaments, resolve_tournament
from tournament.notifications import notify_player_locked, notify_tournament_open, send_notification


DEFAULT_WEEKLY_COURTS = [
    ("Open", 0.0, 8, 64),
    ("Pro", 20.0, 12, 24),
    ("Elite", 50.0, 12, 24),
]


def _iso_at_8pm(day: date) -> str:
    return datetime.combine(day, time(hour=20, minute=0, second=0)).isoformat()


def create_weekly_schedule(anchor_date: date | None = None, sport: str = "nba") -> list[int]:
    """Create Tue/Thu/Sat tournaments for the week containing anchor_date."""
    anchor = anchor_date or date.today()
    monday = anchor - timedelta(days=anchor.weekday())

    # Tuesday (1), Thursday (3), Saturday (5)
    target_days = [monday + timedelta(days=1), monday + timedelta(days=3), monday + timedelta(days=5)]

    created_ids: list[int] = []
    for day in target_days:
        day_label = day.isoformat()
        for tier, fee, min_e, max_e in DEFAULT_WEEKLY_COURTS:
            tid = create_tournament(
                tournament_name=f"{tier} {day_label}",
                court_tier=tier,
                entry_fee=fee,
                min_entries=min_e,
                max_entries=max_e,
                lock_time=_iso_at_8pm(day),
                reveal_mode="instant",
                sport=str(sport or "nba"),
            )
            created_ids.append(tid)
            log_event(
                "scheduler.tournament_created",
                f"Scheduled tournament #{tid} ({tier} {day_label})",
                tournament_id=tid,
                metadata={"tier": tier, "entry_fee": fee, "min_entries": min_e, "max_entries": max_e},
            )
            notify_tournament_open(tid)
    return created_ids


def resolve_locked_tournaments(now: datetime | None = None) -> list[dict]:
    """Resolve all open tournaments with lock_time <= now."""
    now_dt = now or datetime.utcnow()
    resolved: list[dict] = []

    for tournament in list_open_tournaments():
        lock_time_raw = str(tournament.get("lock_time", ""))
        try:
            lock_dt = datetime.fromisoformat(lock_time_raw)
        except ValueError:
            continue
        if lock_dt <= now_dt:
            notify_player_locked(int(tournament["tournament_id"]))
            result = resolve_tournament(int(tournament["tournament_id"]))
            resolved.append(result)
            log_event(
                "scheduler.resolve_attempt",
                f"Scheduler resolve attempted for tournament #{tournament['tournament_id']}",
                tournament_id=int(tournament["tournament_id"]),
                metadata={"success": bool(result.get("success")), "status": result.get("status")},
            )

            # Send lock warning notifications shortly before lock in future runs.
        elif 0 <= (lock_dt - now_dt).total_seconds() <= 300:
            send_notification(
                "lock_warning",
                f"Tournament #{tournament['tournament_id']} locks in under 5 minutes",
                tournament_id=int(tournament["tournament_id"]),
            )

    return resolved
