"""Tournament Stripe webhook helpers.

These helpers persist checkout events in the isolated tournament database so
paid entry verification can work even without direct Stripe API access.
"""

from __future__ import annotations

import json
from typing import Any

from tournament.database import get_tournament_connection, initialize_tournament_database
from tournament.events import log_event


def upsert_checkout_session(
    session_id: str,
    *,
    tournament_id: int | None = None,
    user_email: str = "",
    payment_intent_id: str = "",
    payment_status: str = "unknown",
    stripe_event_id: str = "",
    raw_event: dict[str, Any] | None = None,
) -> bool:
    """Insert or update a Stripe checkout session persistence row."""
    sid = str(session_id or "").strip()
    if not sid:
        return False

    initialize_tournament_database()
    try:
        with get_tournament_connection() as conn:
            conn.execute(
                """
                INSERT INTO stripe_checkout_sessions
                    (session_id, tournament_id, user_email, payment_intent_id, payment_status,
                     stripe_event_id, raw_event_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(session_id) DO UPDATE SET
                    tournament_id = CASE
                        WHEN excluded.tournament_id IS NULL THEN stripe_checkout_sessions.tournament_id
                        ELSE excluded.tournament_id
                    END,
                    user_email = CASE
                        WHEN excluded.user_email = '' THEN stripe_checkout_sessions.user_email
                        ELSE excluded.user_email
                    END,
                    payment_intent_id = CASE
                        WHEN excluded.payment_intent_id = '' THEN stripe_checkout_sessions.payment_intent_id
                        ELSE excluded.payment_intent_id
                    END,
                    payment_status = CASE
                        WHEN excluded.payment_status = '' THEN stripe_checkout_sessions.payment_status
                        ELSE excluded.payment_status
                    END,
                    stripe_event_id = CASE
                        WHEN excluded.stripe_event_id = '' THEN stripe_checkout_sessions.stripe_event_id
                        ELSE excluded.stripe_event_id
                    END,
                    raw_event_json = CASE
                        WHEN excluded.raw_event_json = '' THEN stripe_checkout_sessions.raw_event_json
                        ELSE excluded.raw_event_json
                    END,
                    updated_at = datetime('now')
                """,
                (
                    sid,
                    int(tournament_id) if tournament_id is not None else None,
                    str(user_email or "").strip().lower(),
                    str(payment_intent_id or "").strip(),
                    str(payment_status or "unknown").strip().lower(),
                    str(stripe_event_id or "").strip(),
                    json.dumps(raw_event or {}),
                ),
            )
            conn.commit()
        return True
    except Exception:
        return False


def get_checkout_session_record(session_id: str) -> dict | None:
    """Return one persisted checkout session row by session_id."""
    sid = str(session_id or "").strip()
    if not sid:
        return None

    initialize_tournament_database()
    with get_tournament_connection() as conn:
        row = conn.execute(
            """
            SELECT session_id, tournament_id, user_email, payment_intent_id,
                   payment_status, stripe_event_id, raw_event_json, created_at, updated_at
            FROM stripe_checkout_sessions
            WHERE session_id = ?
            """,
            (sid,),
        ).fetchone()
        if not row:
            return None

    item = dict(row)
    try:
        item["raw_event"] = json.loads(item.get("raw_event_json") or "{}")
    except Exception:
        item["raw_event"] = {}
    return item


def process_stripe_event(event: dict[str, Any]) -> dict:
    """Process one Stripe webhook event and persist supported checkout records."""
    event_type = str(event.get("type", "")).strip()
    event_id = str(event.get("id", "")).strip()

    if event_type != "checkout.session.completed":
        return {
            "success": True,
            "handled": False,
            "event_type": event_type,
            "reason": "ignored_event_type",
        }

    data_object = event.get("data", {}).get("object", {})
    session_id = str(data_object.get("id", "")).strip()
    if not session_id:
        return {
            "success": False,
            "handled": False,
            "event_type": event_type,
            "error": "Missing checkout session id",
        }

    metadata = dict(data_object.get("metadata") or {})
    tournament_id_raw = metadata.get("tournament_id")
    tournament_id = None
    if tournament_id_raw not in (None, ""):
        try:
            tournament_id = int(tournament_id_raw)
        except Exception:
            tournament_id = None

    payment_intent = data_object.get("payment_intent")
    if isinstance(payment_intent, dict):
        payment_intent_id = str(payment_intent.get("id", ""))
    else:
        payment_intent_id = str(payment_intent or "")

    payment_status = str(data_object.get("payment_status", "unknown")).strip().lower()
    customer_email = str(
        metadata.get("customer_email")
        or data_object.get("customer_details", {}).get("email", "")
        or data_object.get("customer_email", "")
    ).strip().lower()

    saved = upsert_checkout_session(
        session_id,
        tournament_id=tournament_id,
        user_email=customer_email,
        payment_intent_id=payment_intent_id,
        payment_status=payment_status,
        stripe_event_id=event_id,
        raw_event=event,
    )

    if not saved:
        return {
            "success": False,
            "handled": False,
            "event_type": event_type,
            "error": "Failed to persist checkout session",
        }

    log_event(
        "stripe.checkout.completed",
        f"Persisted checkout session {session_id}",
        tournament_id=tournament_id,
        user_email=customer_email,
        metadata={
            "session_id": session_id,
            "payment_intent_id": payment_intent_id,
            "payment_status": payment_status,
            "stripe_event_id": event_id,
        },
    )

    return {
        "success": True,
        "handled": True,
        "event_type": event_type,
        "session_id": session_id,
        "tournament_id": tournament_id,
        "customer_email": customer_email,
        "payment_intent_id": payment_intent_id,
        "payment_status": payment_status,
    }
