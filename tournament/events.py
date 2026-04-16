"""Standalone tournament event and audit logging."""

from __future__ import annotations

import json
from typing import Any

from tournament.database import get_tournament_connection, initialize_tournament_database


def log_event(
    event_type: str,
    message: str,
    *,
    tournament_id: int | None = None,
    entry_id: int | None = None,
    user_email: str | None = None,
    severity: str = "info",
    metadata: dict[str, Any] | None = None,
) -> int:
    """Write one event row to the isolated tournament event log."""
    initialize_tournament_database()
    with get_tournament_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tournament_events
                (tournament_id, entry_id, user_email, event_type, severity, message, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                int(tournament_id) if tournament_id is not None else None,
                int(entry_id) if entry_id is not None else None,
                (user_email or "").strip().lower() or None,
                event_type,
                severity,
                message,
                json.dumps(metadata or {}),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_events(
    *,
    tournament_id: int | None = None,
    event_type: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """List recent events, optionally filtered by tournament or type."""
    initialize_tournament_database()

    query = (
        "SELECT event_id, tournament_id, entry_id, user_email, event_type, severity, message, metadata_json, created_at "
        "FROM tournament_events"
    )
    clauses = []
    params: list[Any] = []

    if tournament_id is not None:
        clauses.append("tournament_id = ?")
        params.append(int(tournament_id))
    if event_type:
        clauses.append("event_type = ?")
        params.append(str(event_type))

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += " ORDER BY event_id DESC LIMIT ?"
    params.append(max(1, int(limit)))

    with get_tournament_connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            try:
                item["metadata"] = json.loads(item.get("metadata_json") or "{}")
            except Exception:
                item["metadata"] = {}
            out.append(item)
        return out
