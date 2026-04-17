"""Tests for tournament/stripe.py — subscription checkout functions."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


class TestCreateLegendPassCheckoutSession:
    """Tests for create_legend_pass_checkout_session."""

    def test_missing_price_id_returns_error(self):
        from tournament.stripe import create_legend_pass_checkout_session
        with patch.dict(os.environ, {"STRIPE_LEGEND_PASS_PRICE_ID": ""}, clear=False):
            # Force re-read
            import tournament.stripe as mod
            original = mod.STRIPE_LEGEND_PASS_PRICE_ID
            mod.STRIPE_LEGEND_PASS_PRICE_ID = ""
            try:
                result = create_legend_pass_checkout_session(customer_email="test@example.com")
                assert result["success"] is False
                assert "STRIPE_LEGEND_PASS_PRICE_ID" in result["error"]
            finally:
                mod.STRIPE_LEGEND_PASS_PRICE_ID = original

    def test_stripe_not_configured(self):
        from tournament.stripe import create_legend_pass_checkout_session
        import tournament.stripe as mod
        original_price = mod.STRIPE_LEGEND_PASS_PRICE_ID
        original_key = mod.STRIPE_SECRET_KEY
        mod.STRIPE_LEGEND_PASS_PRICE_ID = "price_test_123"
        mod.STRIPE_SECRET_KEY = ""
        try:
            result = create_legend_pass_checkout_session(customer_email="test@example.com")
            assert result["success"] is False
            assert "not configured" in result["error"].lower()
        finally:
            mod.STRIPE_LEGEND_PASS_PRICE_ID = original_price
            mod.STRIPE_SECRET_KEY = original_key


class TestCreatePremiumCheckoutSession:
    """Tests for create_premium_checkout_session."""

    def test_missing_price_id_returns_error(self):
        from tournament.stripe import create_premium_checkout_session
        import tournament.stripe as mod
        original = mod.STRIPE_PREMIUM_PRICE_ID
        mod.STRIPE_PREMIUM_PRICE_ID = ""
        try:
            result = create_premium_checkout_session(customer_email="test@example.com")
            assert result["success"] is False
            assert "STRIPE_PREMIUM_PRICE_ID" in result["error"]
        finally:
            mod.STRIPE_PREMIUM_PRICE_ID = original

    def test_stripe_not_configured(self):
        from tournament.stripe import create_premium_checkout_session
        import tournament.stripe as mod
        original_price = mod.STRIPE_PREMIUM_PRICE_ID
        original_key = mod.STRIPE_SECRET_KEY
        mod.STRIPE_PREMIUM_PRICE_ID = "price_test_456"
        mod.STRIPE_SECRET_KEY = ""
        try:
            result = create_premium_checkout_session(customer_email="test@example.com")
            assert result["success"] is False
            assert "not configured" in result["error"].lower()
        finally:
            mod.STRIPE_PREMIUM_PRICE_ID = original_price
            mod.STRIPE_SECRET_KEY = original_key


class TestGetSubscriptionDetails:
    """Tests for get_subscription_details."""

    def test_stripe_not_configured(self):
        from tournament.stripe import get_subscription_details
        import tournament.stripe as mod
        original_key = mod.STRIPE_SECRET_KEY
        mod.STRIPE_SECRET_KEY = ""
        try:
            result = get_subscription_details("sub_123")
            assert result["success"] is False
            assert "not configured" in result["error"].lower()
        finally:
            mod.STRIPE_SECRET_KEY = original_key

    def test_empty_subscription_id(self):
        """get_subscription_details with empty id returns an error."""
        from tournament.stripe import get_subscription_details
        result = get_subscription_details("")
        assert result["success"] is False
        # Either "not configured" or "subscription_id is required" depending on env
        assert result["error"] != ""
