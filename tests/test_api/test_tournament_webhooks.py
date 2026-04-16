"""tests/test_api/test_tournament_webhooks.py - API tests for tournament webhook route."""

import pytest


def _skip_if_no_fastapi():
    try:
        import fastapi  # noqa: F401
        import httpx  # noqa: F401
    except ImportError:
        pytest.skip("fastapi or httpx not installed")


def _make_client():
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


class TestTournamentWebhookRoute:
    def test_webhook_route_accepts_valid_json(self):
        _skip_if_no_fastapi()
        payload = {
            "id": "evt_test_1",
            "type": "customer.created",  # ignored but successful
            "data": {"object": {}},
        }
        with _make_client() as client:
            resp = client.post("/webhooks/tournament/stripe", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("ok") is True
            assert data.get("result", {}).get("handled") is False

    def test_webhook_invalid_payload_returns_400(self):
        _skip_if_no_fastapi()
        with _make_client() as client:
            resp = client.post(
                "/webhooks/tournament/stripe",
                content="not-json",
                headers={"content-type": "application/json"},
            )
            assert resp.status_code == 400

    def test_webhook_processing_failure_returns_400(self, monkeypatch):
        _skip_if_no_fastapi()

        def _fake_process_stripe_event(_event):
            return {"success": False, "error": "synthetic failure"}

        import tournament.webhooks as hooks
        monkeypatch.setattr(hooks, "process_stripe_event", _fake_process_stripe_event)

        with _make_client() as client:
            resp = client.post(
                "/webhooks/tournament/stripe",
                json={"id": "evt_fail", "type": "checkout.session.completed", "data": {"object": {"id": "cs_1"}}},
            )
            assert resp.status_code == 400
            assert "synthetic failure" in resp.json().get("detail", "")
