"""Standalone Stripe handlers for tournament entry, refund, and payouts."""

from __future__ import annotations

import os

try:
    import stripe as _stripe
    _STRIPE_AVAILABLE = True
except ImportError:
    _stripe = None
    _STRIPE_AVAILABLE = False

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
APP_URL = os.environ.get("APP_URL", "http://localhost:8501").rstrip("/")


def _configure_stripe() -> bool:
    if not _STRIPE_AVAILABLE:
        return False
    if not STRIPE_SECRET_KEY:
        return False
    _stripe.api_key = STRIPE_SECRET_KEY
    return True


def create_tournament_entry_checkout_session(
    tournament_id: int,
    fee_usd: float,
    customer_email: str = "",
    success_path: str = "/",
    cancel_path: str = "/",
) -> dict:
    """Create one-time Stripe checkout session for tournament entry."""
    if not _configure_stripe():
        return {
            "success": False,
            "url": "",
            "session_id": "",
            "error": "Stripe is not configured",
        }

    try:
        success_url = f"{APP_URL}{success_path}?session_id={{CHECKOUT_SESSION_ID}}&tournament_id={int(tournament_id)}"
        cancel_url = f"{APP_URL}{cancel_path}?cancelled=true&tournament_id={int(tournament_id)}"

        params = {
            "mode": "payment",
            "line_items": [
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": int(round(float(fee_usd) * 100)),
                        "product_data": {
                            "name": f"Tournament Entry #{int(tournament_id)}",
                            "description": "Smart Pick Pro tournament entry fee",
                        },
                    },
                    "quantity": 1,
                }
            ],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {
                "type": "tournament_entry",
                "tournament_id": str(int(tournament_id)),
            },
        }
        if customer_email:
            params["customer_email"] = customer_email
            params["metadata"]["customer_email"] = customer_email.strip().lower()

        session = _stripe.checkout.Session.create(**params)
        return {
            "success": True,
            "url": session.url,
            "session_id": session.id,
            "error": "",
        }
    except Exception as exc:
        return {
            "success": False,
            "url": "",
            "session_id": "",
            "error": str(exc),
        }


def create_tournament_refund(payment_intent_id: str) -> dict:
    """Create refund for a tournament entry payment."""
    if not _configure_stripe():
        return {"success": False, "refund_id": "", "error": "Stripe is not configured"}
    if not payment_intent_id:
        return {"success": False, "refund_id": "", "error": "payment_intent_id is required"}

    try:
        refund = _stripe.Refund.create(payment_intent=payment_intent_id)
        return {"success": True, "refund_id": refund.id, "error": ""}
    except Exception as exc:
        return {"success": False, "refund_id": "", "error": str(exc)}


def get_checkout_session_details(session_id: str) -> dict:
    """Fetch checkout session details and normalize payment verification fields."""
    if not _configure_stripe():
        return {
            "success": False,
            "session_id": "",
            "tournament_id": "",
            "customer_email": "",
            "payment_intent_id": "",
            "paid": False,
            "error": "Stripe is not configured",
        }

    sid = str(session_id or "").strip()
    if not sid:
        return {
            "success": False,
            "session_id": "",
            "tournament_id": "",
            "customer_email": "",
            "payment_intent_id": "",
            "paid": False,
            "error": "session_id is required",
        }

    try:
        session = _stripe.checkout.Session.retrieve(sid)
        metadata = dict(session.get("metadata") or {})

        payment_intent = session.get("payment_intent")
        if isinstance(payment_intent, dict):
            payment_intent_id = str(payment_intent.get("id", ""))
        else:
            payment_intent_id = str(payment_intent or "")

        payment_status = str(session.get("payment_status", "")).strip().lower()
        paid = payment_status == "paid"

        return {
            "success": True,
            "session_id": str(session.get("id", sid)),
            "tournament_id": str(metadata.get("tournament_id", "")),
            "customer_email": str(
                metadata.get("customer_email")
                or session.get("customer_details", {}).get("email", "")
                or session.get("customer_email", "")
            ).strip().lower(),
            "payment_intent_id": payment_intent_id,
            "paid": paid,
            "error": "",
        }
    except Exception as exc:
        return {
            "success": False,
            "session_id": sid,
            "tournament_id": "",
            "customer_email": "",
            "payment_intent_id": "",
            "paid": False,
            "error": str(exc),
        }


def create_winner_payout_transfer(connect_account_id: str, amount_usd: float, tournament_id: int) -> dict:
    """Transfer winner payout to connected Stripe account."""
    if not _configure_stripe():
        return {"success": False, "transfer_id": "", "error": "Stripe is not configured"}
    if not connect_account_id:
        return {"success": False, "transfer_id": "", "error": "connect_account_id is required"}
    if amount_usd <= 0:
        return {"success": False, "transfer_id": "", "error": "amount_usd must be > 0"}

    try:
        transfer = _stripe.Transfer.create(
            amount=int(round(amount_usd * 100)),
            currency="usd",
            destination=connect_account_id,
            metadata={
                "type": "tournament_payout",
                "tournament_id": str(int(tournament_id)),
            },
        )
        return {"success": True, "transfer_id": transfer.id, "error": ""}
    except Exception as exc:
        return {"success": False, "transfer_id": "", "error": str(exc)}


def create_connect_account(user_email: str) -> dict:
    """Create a Stripe Connect Express account for payout onboarding."""
    if not _configure_stripe():
        return {"success": False, "account_id": "", "error": "Stripe is not configured"}

    email = str(user_email or "").strip().lower()
    if not email:
        return {"success": False, "account_id": "", "error": "user_email is required"}

    try:
        account = _stripe.Account.create(
            type="express",
            country=str(os.environ.get("TOURNAMENT_STRIPE_CONNECT_COUNTRY", "US") or "US").strip().upper(),
            email=email,
            capabilities={"transfers": {"requested": True}},
            metadata={"type": "tournament_winner", "user_email": email},
        )
        return {"success": True, "account_id": str(account.id), "error": ""}
    except Exception as exc:
        return {"success": False, "account_id": "", "error": str(exc)}


def create_connect_onboarding_link(
    connect_account_id: str,
    *,
    refresh_path: str = "/",
    return_path: str = "/",
) -> dict:
    """Create Stripe Connect onboarding link for an existing Connect account."""
    if not _configure_stripe():
        return {"success": False, "url": "", "expires_at": "", "error": "Stripe is not configured"}

    account_id = str(connect_account_id or "").strip()
    if not account_id:
        return {"success": False, "url": "", "expires_at": "", "error": "connect_account_id is required"}

    try:
        refresh_url = f"{APP_URL}{str(refresh_path or '/').strip() or '/'}"
        return_url = f"{APP_URL}{str(return_path or '/').strip() or '/'}"
        link = _stripe.AccountLink.create(
            account=account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding",
        )
        return {
            "success": True,
            "url": str(link.url),
            "expires_at": str(getattr(link, "expires_at", "") or ""),
            "error": "",
        }
    except Exception as exc:
        return {"success": False, "url": "", "expires_at": "", "error": str(exc)}


def get_connect_account_status(connect_account_id: str) -> dict:
    """Fetch Stripe Connect account status and requirement details."""
    if not _configure_stripe():
        return {
            "success": False,
            "account_id": "",
            "details_submitted": False,
            "payouts_enabled": False,
            "charges_enabled": False,
            "requirements": {},
            "error": "Stripe is not configured",
        }

    account_id = str(connect_account_id or "").strip()
    if not account_id:
        return {
            "success": False,
            "account_id": "",
            "details_submitted": False,
            "payouts_enabled": False,
            "charges_enabled": False,
            "requirements": {},
            "error": "connect_account_id is required",
        }

    try:
        account = _stripe.Account.retrieve(account_id)
        requirements = dict(account.get("requirements") or {})
        return {
            "success": True,
            "account_id": str(account.get("id", account_id) or account_id),
            "details_submitted": bool(account.get("details_submitted", False)),
            "payouts_enabled": bool(account.get("payouts_enabled", False)),
            "charges_enabled": bool(account.get("charges_enabled", False)),
            "requirements": {
                "currently_due": list(requirements.get("currently_due") or []),
                "eventually_due": list(requirements.get("eventually_due") or []),
                "past_due": list(requirements.get("past_due") or []),
                "pending_verification": list(requirements.get("pending_verification") or []),
            },
            "error": "",
        }
    except Exception as exc:
        return {
            "success": False,
            "account_id": account_id,
            "details_submitted": False,
            "payouts_enabled": False,
            "charges_enabled": False,
            "requirements": {},
            "error": str(exc),
        }
