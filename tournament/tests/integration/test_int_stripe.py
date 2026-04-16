"""Integration-style tests for tournament.stripe helpers with mocked Stripe SDK."""

from tournament import stripe as tstripe


class _FakeCheckoutSession:
    @staticmethod
    def retrieve(session_id):
        return {
            "id": session_id,
            "metadata": {
                "tournament_id": "42",
                "customer_email": "paid@test.com",
            },
            "payment_status": "paid",
            "payment_intent": "pi_123",
        }


class _FakeCheckout:
    Session = _FakeCheckoutSession


class _FakeStripe:
    checkout = _FakeCheckout


class TestGetCheckoutSessionDetails:
    def test_requires_session_id(self, monkeypatch):
        monkeypatch.setattr(tstripe, "_STRIPE_AVAILABLE", True)
        monkeypatch.setattr(tstripe, "STRIPE_SECRET_KEY", "sk_test_123")
        monkeypatch.setattr(tstripe, "_stripe", _FakeStripe)

        result = tstripe.get_checkout_session_details("")
        assert result["success"] is False
        assert "required" in result["error"].lower()

    def test_returns_not_configured_when_stripe_missing(self, monkeypatch):
        monkeypatch.setattr(tstripe, "_STRIPE_AVAILABLE", False)
        monkeypatch.setattr(tstripe, "STRIPE_SECRET_KEY", "")

        result = tstripe.get_checkout_session_details("cs_123")
        assert result["success"] is False
        assert "not configured" in result["error"].lower()

    def test_parses_paid_session(self, monkeypatch):
        monkeypatch.setattr(tstripe, "_STRIPE_AVAILABLE", True)
        monkeypatch.setattr(tstripe, "STRIPE_SECRET_KEY", "sk_test_123")
        monkeypatch.setattr(tstripe, "_stripe", _FakeStripe)

        result = tstripe.get_checkout_session_details("cs_test_123")
        assert result["success"] is True
        assert result["session_id"] == "cs_test_123"
        assert result["tournament_id"] == "42"
        assert result["customer_email"] == "paid@test.com"
        assert result["payment_intent_id"] == "pi_123"
        assert result["paid"] is True
