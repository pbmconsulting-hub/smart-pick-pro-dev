"""Integration tests for tournament.webhooks persistence and event handling."""

from tournament.events import list_events
from tournament.webhooks import (
    get_checkout_session_record,
    process_stripe_event,
    upsert_checkout_session,
)


class TestUpsertCheckoutSession:
    def test_insert_and_get_record(self, isolated_db):
        ok = upsert_checkout_session(
            "cs_test_1",
            tournament_id=10,
            user_email="paid@test.com",
            payment_intent_id="pi_1",
            payment_status="paid",
            stripe_event_id="evt_1",
            raw_event={"k": "v"},
        )
        assert ok is True

        record = get_checkout_session_record("cs_test_1")
        assert record is not None
        assert record["tournament_id"] == 10
        assert record["user_email"] == "paid@test.com"
        assert record["payment_intent_id"] == "pi_1"
        assert record["payment_status"] == "paid"
        assert record["raw_event"]["k"] == "v"

    def test_upsert_updates_existing(self, isolated_db):
        upsert_checkout_session("cs_test_2", payment_status="open")
        upsert_checkout_session(
            "cs_test_2",
            payment_intent_id="pi_2",
            payment_status="paid",
        )
        record = get_checkout_session_record("cs_test_2")
        assert record is not None
        assert record["payment_intent_id"] == "pi_2"
        assert record["payment_status"] == "paid"


class TestProcessStripeEvent:
    def test_ignores_unhandled_event_type(self, isolated_db):
        result = process_stripe_event({"type": "customer.created", "id": "evt_x"})
        assert result["success"] is True
        assert result["handled"] is False
        assert result["reason"] == "ignored_event_type"

    def test_requires_session_id(self, isolated_db):
        result = process_stripe_event(
            {
                "type": "checkout.session.completed",
                "id": "evt_missing",
                "data": {"object": {}},
            }
        )
        assert result["success"] is False
        assert "missing" in result["error"].lower()

    def test_persists_checkout_completed_and_logs_event(self, isolated_db):
        event = {
            "id": "evt_checkout_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_paid_1",
                    "payment_status": "paid",
                    "payment_intent": "pi_paid_1",
                    "customer_email": "user@test.com",
                    "metadata": {
                        "tournament_id": "77",
                        "customer_email": "user@test.com",
                    },
                }
            },
        }

        result = process_stripe_event(event)
        assert result["success"] is True
        assert result["handled"] is True
        assert result["session_id"] == "cs_paid_1"
        assert result["payment_intent_id"] == "pi_paid_1"
        assert result["payment_status"] == "paid"

        record = get_checkout_session_record("cs_paid_1")
        assert record is not None
        assert record["tournament_id"] == 77
        assert record["user_email"] == "user@test.com"
        assert record["payment_intent_id"] == "pi_paid_1"

        events = list_events(event_type="stripe.checkout.completed")
        assert len(events) == 1
        assert events[0]["metadata"]["session_id"] == "cs_paid_1"
