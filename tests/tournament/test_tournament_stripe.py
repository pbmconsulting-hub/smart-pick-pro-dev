from tournament import stripe as tournament_stripe


class _FakeSessionObj:
    id = "cs_test_123"
    url = "https://example.com/checkout"


class _FakeRefundObj:
    id = "re_test_123"


class _FakeTransferObj:
    id = "tr_test_123"


class _FakeConnectAccountObj:
    id = "acct_test_123"

    def get(self, key, default=None):
        data = {
            "id": self.id,
            "details_submitted": True,
            "payouts_enabled": True,
            "charges_enabled": True,
            "requirements": {"currently_due": [], "eventually_due": [], "past_due": [], "pending_verification": []},
        }
        return data.get(key, default)


class _FakeAccountLinkObj:
    url = "https://example.com/connect/onboarding"
    expires_at = "2099-01-01T00:00:00Z"


class _FakeStripe:
    api_key = ""

    class checkout:
        class Session:
            @staticmethod
            def create(**kwargs):
                return _FakeSessionObj()

    class Refund:
        @staticmethod
        def create(**kwargs):
            return _FakeRefundObj()

    class Transfer:
        @staticmethod
        def create(**kwargs):
            return _FakeTransferObj()

    class Account:
        @staticmethod
        def create(**kwargs):
            return _FakeConnectAccountObj()

        @staticmethod
        def retrieve(account_id):
            return _FakeConnectAccountObj()

    class AccountLink:
        @staticmethod
        def create(**kwargs):
            return _FakeAccountLinkObj()


def test_checkout_session_creation(monkeypatch):
    monkeypatch.setattr(tournament_stripe, "_STRIPE_AVAILABLE", True)
    monkeypatch.setattr(tournament_stripe, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(tournament_stripe, "_stripe", _FakeStripe)

    result = tournament_stripe.create_tournament_entry_checkout_session(
        tournament_id=99,
        fee_usd=75.0,
        customer_email="user@example.com",
        success_path="/ok",
        cancel_path="/cancel",
    )

    assert result["success"] is True
    assert result["session_id"] == "cs_test_123"


def test_refund_and_transfer(monkeypatch):
    monkeypatch.setattr(tournament_stripe, "_STRIPE_AVAILABLE", True)
    monkeypatch.setattr(tournament_stripe, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(tournament_stripe, "_stripe", _FakeStripe)

    refund = tournament_stripe.create_tournament_refund("pi_123")
    transfer = tournament_stripe.create_winner_payout_transfer("acct_123", 250.0, tournament_id=99)

    assert refund["success"] is True
    assert refund["refund_id"] == "re_test_123"
    assert transfer["success"] is True
    assert transfer["transfer_id"] == "tr_test_123"


def test_connect_onboarding_and_status(monkeypatch):
    monkeypatch.setattr(tournament_stripe, "_STRIPE_AVAILABLE", True)
    monkeypatch.setattr(tournament_stripe, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(tournament_stripe, "_stripe", _FakeStripe)

    account = tournament_stripe.create_connect_account("winner@test.com")
    assert account["success"] is True
    assert account["account_id"] == "acct_test_123"

    link = tournament_stripe.create_connect_onboarding_link("acct_test_123", refresh_path="/refresh", return_path="/return")
    assert link["success"] is True
    assert "connect/onboarding" in link["url"]

    status = tournament_stripe.get_connect_account_status("acct_test_123")
    assert status["success"] is True
    assert status["details_submitted"] is True
    assert status["payouts_enabled"] is True
