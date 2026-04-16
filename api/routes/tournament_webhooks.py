"""api/routes/tournament_webhooks.py - Tournament Stripe webhook endpoint."""

from __future__ import annotations

import os
from utils.logger import get_logger

_logger = get_logger(__name__)

try:
    import stripe
except Exception:
    stripe = None

try:
    from fastapi import APIRouter, HTTPException, Request

    router = APIRouter(prefix="/webhooks/tournament", tags=["tournament-webhooks"])
    _FASTAPI_AVAILABLE = True
except Exception:
    router = None
    _FASTAPI_AVAILABLE = False


if _FASTAPI_AVAILABLE:
    @router.post("/stripe")
    async def tournament_stripe_webhook(request: Request):
        """Process tournament Stripe webhook events and persist checkout records."""
        try:
            payload_bytes = await request.body()
            sig_header = request.headers.get("Stripe-Signature", "")
            webhook_secret = os.environ.get("TOURNAMENT_STRIPE_WEBHOOK_SECRET", "").strip()

            if webhook_secret and stripe is not None and sig_header:
                event = stripe.Webhook.construct_event(payload_bytes, sig_header, webhook_secret)
            else:
                try:
                    event = await request.json()
                except Exception as exc:
                    raise HTTPException(status_code=400, detail=f"Invalid webhook payload: {exc}")

            from tournament.webhooks import process_stripe_event

            result = process_stripe_event(event)
            if not result.get("success", False):
                raise HTTPException(status_code=400, detail=result.get("error", "Webhook processing failed"))
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament stripe webhook error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Webhook failure: {exc}")
