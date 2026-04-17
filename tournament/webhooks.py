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
    """Process one Stripe webhook event and persist supported checkout records.

    Handles:
    - ``checkout.session.completed`` — persists checkout session for paid entries
    - ``customer.subscription.updated`` — syncs premium / legend pass status
    - ``customer.subscription.deleted`` — marks subscription inactive
    - ``invoice.payment_failed`` — marks subscription as past-due
    """
    event_type = str(event.get("type", "")).strip()
    event_id = str(event.get("id", "")).strip()
    data_object = event.get("data", {}).get("object", {})

    # ── Checkout session completed (one-time tournament entry) ────────
    if event_type == "checkout.session.completed":
        return _handle_checkout_completed(event_type, event_id, data_object, event)

    # ── Subscription lifecycle ────────────────────────────────────────
    if event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        return _handle_subscription_change(event_type, event_id, data_object)

    if event_type == "invoice.payment_failed":
        return _handle_invoice_payment_failed(event_type, event_id, data_object)

    return {
        "success": True,
        "handled": False,
        "event_type": event_type,
        "reason": "ignored_event_type",
    }


def _handle_checkout_completed(
    event_type: str,
    event_id: str,
    data_object: dict[str, Any],
    full_event: dict[str, Any],
) -> dict:
    """Persist a checkout.session.completed event."""
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

    # If this is a subscription checkout (legend_pass or premium), sync status
    meta_type = str(metadata.get("type", "")).strip()
    if meta_type in ("legend_pass_subscription", "premium_subscription") and customer_email:
        _sync_subscription_from_checkout(meta_type, customer_email)

    saved = upsert_checkout_session(
        session_id,
        tournament_id=tournament_id,
        user_email=customer_email,
        payment_intent_id=payment_intent_id,
        payment_status=payment_status,
        stripe_event_id=event_id,
        raw_event=full_event,
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


def _handle_subscription_change(
    event_type: str,
    event_id: str,
    data_object: dict[str, Any],
) -> dict:
    """Handle subscription updated/deleted events to sync tournament access."""
    sub_id = str(data_object.get("id", "")).strip()
    status = str(data_object.get("status", "")).strip()
    metadata = dict(data_object.get("metadata") or {})
    meta_type = str(metadata.get("type", "")).strip()

    # Extract customer email
    customer = data_object.get("customer")
    if isinstance(customer, dict):
        customer_email = str(customer.get("email", "") or "").strip().lower()
    else:
        customer_email = str(metadata.get("customer_email", "") or "").strip().lower()

    if not customer_email:
        customer_email = str(data_object.get("customer_email", "") or "").strip().lower()

    if event_type == "customer.subscription.deleted":
        status = "canceled"

    is_active = status in ("active", "trialing")

    # Determine which product changed
    premium_active = None
    legend_pass_active = None
    premium_expires_at = ""
    legend_pass_expires_at = ""

    period_end = ""
    raw_end = data_object.get("current_period_end")
    if raw_end:
        try:
            from datetime import datetime, timezone
            period_end = datetime.fromtimestamp(int(raw_end), tz=timezone.utc).isoformat()
        except Exception:
            period_end = str(raw_end)

    if meta_type == "legend_pass_subscription":
        legend_pass_active = is_active
        legend_pass_expires_at = period_end
    elif meta_type == "premium_subscription":
        premium_active = is_active
        premium_expires_at = period_end
    else:
        # Try to infer from price/product
        items = data_object.get("items", {}).get("data", [])
        for item in items:
            price = item.get("price", {})
            price_id = str(price.get("id", "") or "").strip()
            from tournament.stripe import STRIPE_LEGEND_PASS_PRICE_ID, STRIPE_PREMIUM_PRICE_ID
            if price_id and price_id == STRIPE_LEGEND_PASS_PRICE_ID:
                legend_pass_active = is_active
                legend_pass_expires_at = period_end
            elif price_id and price_id == STRIPE_PREMIUM_PRICE_ID:
                premium_active = is_active
                premium_expires_at = period_end

    if customer_email and (premium_active is not None or legend_pass_active is not None):
        _upsert_subscription_status(
            customer_email,
            premium_active=premium_active,
            legend_pass_active=legend_pass_active,
            premium_expires_at=premium_expires_at,
            legend_pass_expires_at=legend_pass_expires_at,
            source=f"stripe_webhook:{event_type}",
        )

    log_event(
        f"stripe.{event_type.replace('.', '_')}",
        f"Subscription {sub_id} → {status}",
        user_email=customer_email,
        metadata={
            "subscription_id": sub_id,
            "status": status,
            "meta_type": meta_type,
            "stripe_event_id": event_id,
        },
    )

    return {
        "success": True,
        "handled": True,
        "event_type": event_type,
        "subscription_id": sub_id,
        "status": status,
        "customer_email": customer_email,
    }


def _handle_invoice_payment_failed(
    event_type: str,
    event_id: str,
    data_object: dict[str, Any],
) -> dict:
    """Handle failed invoice payments (mark subscription past_due)."""
    sub_id = str(data_object.get("subscription", "") or "").strip()
    customer_email = str(data_object.get("customer_email", "") or "").strip().lower()

    log_event(
        "stripe.invoice_payment_failed",
        f"Invoice payment failed for subscription {sub_id}",
        user_email=customer_email,
        severity="warning",
        metadata={
            "subscription_id": sub_id,
            "stripe_event_id": event_id,
        },
    )

    return {
        "success": True,
        "handled": True,
        "event_type": event_type,
        "subscription_id": sub_id,
        "customer_email": customer_email,
    }


# ── Internal helpers ──────────────────────────────────────────────────


def _sync_subscription_from_checkout(meta_type: str, customer_email: str) -> None:
    """Activate a subscription tier after a successful checkout."""
    premium_active = None
    legend_pass_active = None
    if meta_type == "legend_pass_subscription":
        legend_pass_active = True
    elif meta_type == "premium_subscription":
        premium_active = True
    if premium_active is not None or legend_pass_active is not None:
        _upsert_subscription_status(
            customer_email,
            premium_active=premium_active,
            legend_pass_active=legend_pass_active,
            source="stripe_checkout_completed",
        )


def _upsert_subscription_status(
    user_email: str,
    *,
    premium_active: bool | None = None,
    legend_pass_active: bool | None = None,
    premium_expires_at: str = "",
    legend_pass_expires_at: str = "",
    source: str = "stripe_webhook",
) -> None:
    """Persist subscription status changes to the tournament database.

    Only fields that are explicitly set (not None) are updated; the others
    are left unchanged.
    """
    try:
        from tournament.database import get_tournament_connection, initialize_tournament_database
        initialize_tournament_database()

        email = str(user_email or "").strip().lower()
        if not email:
            return

        with get_tournament_connection() as conn:
            existing = conn.execute(
                "SELECT premium_active, legend_pass_active, premium_expires_at, legend_pass_expires_at FROM user_subscription_status WHERE user_email = ?",
                (email,),
            ).fetchone()

            if existing:
                pa = int(premium_active) if premium_active is not None else int(existing["premium_active"] or 0)
                la = int(legend_pass_active) if legend_pass_active is not None else int(existing["legend_pass_active"] or 0)
                pe = premium_expires_at if premium_expires_at else str(existing["premium_expires_at"] or "")
                le = legend_pass_expires_at if legend_pass_expires_at else str(existing["legend_pass_expires_at"] or "")
            else:
                pa = int(premium_active) if premium_active is not None else 0
                la = int(legend_pass_active) if legend_pass_active is not None else 0
                pe = premium_expires_at
                le = legend_pass_expires_at

            conn.execute(
                """
                INSERT INTO user_subscription_status
                    (user_email, premium_active, legend_pass_active, premium_expires_at,
                     legend_pass_expires_at, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(user_email) DO UPDATE SET
                    premium_active = excluded.premium_active,
                    legend_pass_active = excluded.legend_pass_active,
                    premium_expires_at = excluded.premium_expires_at,
                    legend_pass_expires_at = excluded.legend_pass_expires_at,
                    source = excluded.source,
                    updated_at = datetime('now')
                """,
                (email, pa, la, pe, le, str(source)),
            )
            conn.commit()
    except Exception:
        pass  # Best-effort — log in calling code
