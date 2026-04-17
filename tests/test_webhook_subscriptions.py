"""Tests for tournament/webhooks.py — subscription lifecycle event handling."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Mock heavy dependencies before importing the module
sys.modules.setdefault("streamlit", MagicMock())
sys.modules.setdefault("engine", MagicMock())
sys.modules.setdefault("engine.game_prediction", MagicMock())
sys.modules.setdefault("engine.simulation", MagicMock())
sys.modules.setdefault("data", MagicMock())
sys.modules.setdefault("data.data_manager", MagicMock())
sys.modules.setdefault("tracking", MagicMock())
sys.modules.setdefault("tracking.database", MagicMock())

import pytest

from tournament.webhooks import process_stripe_event


class TestProcessStripeEventSubscription:
    """Tests for subscription lifecycle handling in process_stripe_event."""

    def test_checkout_completed_still_handled(self):
        """Verify the original checkout.session.completed flow still works."""
        event = {
            "type": "checkout.session.completed",
            "id": "evt_test_123",
            "data": {
                "object": {
                    "id": "cs_test_abc",
                    "payment_intent": "pi_test_456",
                    "payment_status": "paid",
                    "metadata": {
                        "type": "tournament_entry",
                        "tournament_id": "7",
                        "customer_email": "player@example.com",
                    },
                },
            },
        }
        result = process_stripe_event(event)
        assert result["success"] is True
        assert result["handled"] is True
        assert result["event_type"] == "checkout.session.completed"
        assert result["session_id"] == "cs_test_abc"
        assert result["customer_email"] == "player@example.com"

    def test_subscription_updated_handled(self):
        """Verify customer.subscription.updated is now handled."""
        event = {
            "type": "customer.subscription.updated",
            "id": "evt_sub_updated",
            "data": {
                "object": {
                    "id": "sub_test_001",
                    "status": "active",
                    "current_period_end": 1750000000,
                    "metadata": {
                        "type": "legend_pass_subscription",
                        "customer_email": "legend@example.com",
                    },
                },
            },
        }
        result = process_stripe_event(event)
        assert result["success"] is True
        assert result["handled"] is True
        assert result["event_type"] == "customer.subscription.updated"
        assert result["subscription_id"] == "sub_test_001"
        assert result["status"] == "active"

    def test_subscription_deleted_marks_canceled(self):
        """Verify customer.subscription.deleted sets status to canceled."""
        event = {
            "type": "customer.subscription.deleted",
            "id": "evt_sub_deleted",
            "data": {
                "object": {
                    "id": "sub_test_002",
                    "status": "active",
                    "metadata": {
                        "type": "premium_subscription",
                        "customer_email": "premium@example.com",
                    },
                },
            },
        }
        result = process_stripe_event(event)
        assert result["success"] is True
        assert result["handled"] is True
        assert result["status"] == "canceled"

    def test_invoice_payment_failed_handled(self):
        """Verify invoice.payment_failed is handled."""
        event = {
            "type": "invoice.payment_failed",
            "id": "evt_invoice_fail",
            "data": {
                "object": {
                    "subscription": "sub_test_003",
                    "customer_email": "failing@example.com",
                },
            },
        }
        result = process_stripe_event(event)
        assert result["success"] is True
        assert result["handled"] is True
        assert result["subscription_id"] == "sub_test_003"

    def test_unrelated_event_ignored(self):
        """Verify unrelated event types are still ignored."""
        event = {
            "type": "charge.refunded",
            "id": "evt_refund_123",
            "data": {"object": {}},
        }
        result = process_stripe_event(event)
        assert result["success"] is True
        assert result["handled"] is False
        assert result["reason"] == "ignored_event_type"

    def test_legend_pass_checkout_syncs_subscription(self):
        """Verify a legend_pass_subscription checkout activates the pass."""
        event = {
            "type": "checkout.session.completed",
            "id": "evt_lp_checkout",
            "data": {
                "object": {
                    "id": "cs_legend_pass",
                    "payment_intent": "pi_lp_001",
                    "payment_status": "paid",
                    "metadata": {
                        "type": "legend_pass_subscription",
                        "customer_email": "legenduser@test.com",
                    },
                },
            },
        }
        result = process_stripe_event(event)
        assert result["success"] is True
        assert result["handled"] is True
        assert result["customer_email"] == "legenduser@test.com"
