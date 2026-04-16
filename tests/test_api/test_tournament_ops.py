"""tests/test_api/test_tournament_ops.py - API tests for tournament ops route."""

from __future__ import annotations

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


def _make_paid_roster() -> list[dict]:
    active = [
        {"player_id": f"A{i}", "player_name": f"Player {i}", "salary": 5500, "is_legend": False}
        for i in range(8)
    ]
    legend = {"player_id": "L001", "player_name": "MJ", "salary": 15000, "is_legend": True}
    return active + [legend]


def _configure_temp_tournament_db(monkeypatch, tmp_path):
    import tournament.database as tdb

    monkeypatch.setattr(tdb, "DB_DIRECTORY", tmp_path)
    monkeypatch.setattr(tdb, "TOURNAMENT_DB_PATH", tmp_path / "tournament.db")
    assert tdb.initialize_tournament_database() is True


class TestTournamentOpsSportsAndSubscriptionsRoutes:
    def test_sports_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/sports")
            assert resp.status_code == 401

    def test_sports_list_returns_supported_rows(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/sports",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            assert int(payload.get("count", 0)) >= 1
            rows = list(payload.get("rows") or [])
            assert any(str(r.get("sport", "")).lower() == "nba" for r in rows)

    def test_subscription_upsert_and_get_round_trip(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            upsert_resp = client.post(
                "/ops/tournament/subscriptions/status",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "user_email": "ops-sub@test.com",
                    "premium_active": True,
                    "legend_pass_active": False,
                    "source": "api_test",
                },
            )
            assert upsert_resp.status_code == 200
            upsert_payload = upsert_resp.json()
            assert upsert_payload.get("ok") is True
            assert upsert_payload.get("result", {}).get("success") is True

            get_resp = client.get(
                "/ops/tournament/subscriptions/status/ops-sub@test.com",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert get_resp.status_code == 200
            get_payload = get_resp.json()
            assert get_payload.get("ok") is True
            result = get_payload.get("result", {})
            assert result.get("user_email") == "ops-sub@test.com"
            assert bool(result.get("premium_active")) is True

    def test_access_check_and_create_tournament_with_sport(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            access_resp = client.post(
                "/ops/tournament/access/check",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "user_email": "ops-access@test.com",
                    "court_tier": "Open",
                    "user_age": 25,
                    "state_code": "CA",
                },
            )
            assert access_resp.status_code == 200
            access_payload = access_resp.json()
            assert access_payload.get("ok") is True
            assert bool(access_payload.get("result", {}).get("allowed", False)) is True

            create_resp = client.post(
                "/ops/tournament/tournaments/create",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "tournament_name": "API Sport Create",
                    "court_tier": "Open",
                    "entry_fee": 0.0,
                    "min_entries": 2,
                    "max_entries": 10,
                    "lock_time": "2099-06-01T20:00:00",
                    "reveal_mode": "instant",
                    "sport": "nfl",
                },
            )
            assert create_resp.status_code == 200
            create_payload = create_resp.json()
            assert create_payload.get("ok") is True
            tid = int(create_payload.get("result", {}).get("tournament_id", 0))
            assert tid > 0

        from tournament.manager import get_tournament

        created = get_tournament(tid)
        assert isinstance(created, dict)
        assert str(created.get("sport", "")).lower() == "nfl"


class TestTournamentOpsConnectAndPayoutScheduleRoutes:
    def test_connect_and_due_payout_endpoints_require_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            assert client.post("/ops/tournament/connect/onboarding", json={"user_email": "a@test.com"}).status_code == 401
            assert client.post("/ops/tournament/connect/sync/a@test.com").status_code == 401
            assert client.get("/ops/tournament/connect/status/a@test.com").status_code == 401
            assert client.post("/ops/tournament/payouts/eligibility", json={"user_email": "a@test.com"}).status_code == 401
            assert client.get("/ops/tournament/payouts/due").status_code == 401
            assert client.post("/ops/tournament/payouts/process-due", json={}).status_code == 401

    def test_connect_onboarding_sync_and_due_payout_process(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        monkeypatch.setattr(
            "tournament.stripe.create_connect_account",
            lambda user_email: {"success": True, "account_id": "acct_api_1", "error": ""},
        )
        monkeypatch.setattr(
            "tournament.stripe.create_connect_onboarding_link",
            lambda account_id, refresh_path="/", return_path="/": {
                "success": True,
                "url": "https://example.com/connect",
                "expires_at": "2099-01-01T00:00:00Z",
                "error": "",
            },
        )
        monkeypatch.setattr(
            "tournament.stripe.get_connect_account_status",
            lambda account_id: {
                "success": True,
                "account_id": str(account_id),
                "details_submitted": True,
                "payouts_enabled": True,
                "charges_enabled": True,
                "requirements": {"currently_due": [], "eventually_due": [], "past_due": [], "pending_verification": []},
                "error": "",
            },
        )

        from tournament.manager import create_tournament, submit_entry
        import tournament.database as tdb

        tid = create_tournament("API Due", "Pro", 20.0, 1, 24, "2099-06-01T20:00:00")
        ok, _, entry_id = submit_entry(tid, "api-connect@test.com", "API Connect", _make_paid_roster())
        assert ok is True
        with tdb.get_tournament_connection() as conn:
            conn.execute("UPDATE tournaments SET status='resolved', resolved_at=datetime('now', '-30 hours') WHERE tournament_id=?", (tid,))
            conn.execute("UPDATE tournament_entries SET payout_amount=120.0, payout_status='pending', rank=1 WHERE entry_id=?", (entry_id,))
            conn.commit()

        with _make_client() as client:
            onboarding = client.post(
                "/ops/tournament/connect/onboarding",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"user_email": "api-connect@test.com", "refresh_path": "/refresh", "return_path": "/done"},
            )
            assert onboarding.status_code == 200
            assert onboarding.json().get("ok") is True

            sync_resp = client.post(
                "/ops/tournament/connect/sync/api-connect@test.com",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert sync_resp.status_code == 200
            assert sync_resp.json().get("ok") is True

            status_resp = client.get(
                "/ops/tournament/connect/status/api-connect@test.com",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert status_resp.status_code == 200
            status_payload = status_resp.json()
            assert status_payload.get("ok") is True
            assert bool(status_payload.get("result", {}).get("payouts_enabled", False)) is True

            eligibility_resp = client.post(
                "/ops/tournament/payouts/eligibility",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"user_email": "api-connect@test.com"},
            )
            assert eligibility_resp.status_code == 200
            assert eligibility_resp.json().get("ok") is True

            due_resp = client.get(
                "/ops/tournament/payouts/due?sla_hours=24&limit=100",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert due_resp.status_code == 200
            due_payload = due_resp.json()
            assert due_payload.get("ok") is True
            assert int(due_payload.get("count", 0)) >= 1

            process_resp = client.post(
                "/ops/tournament/payouts/process-due",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"sla_hours": 24, "max_tournaments": 10},
            )
            assert process_resp.status_code == 200
            process_payload = process_resp.json()
            assert process_payload.get("ok") is True
            assert process_payload.get("result", {}).get("success") is True


class TestTournamentOpsFinalizePendingRoute:
    def test_returns_503_when_admin_key_not_configured(self):
        _skip_if_no_fastapi()
        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/finalize",
                headers={"x-tournament-admin-key": "anything"},
                json={"checkout_session_id": "cs_any"},
            )
            assert resp.status_code == 503

    def test_returns_401_for_invalid_admin_key(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/finalize",
                headers={"x-tournament-admin-key": "wrong-key"},
                json={"checkout_session_id": "cs_any"},
            )
            assert resp.status_code == 401

    def test_finalize_pending_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, get_pending_paid_entry, save_pending_paid_entry

        tid = create_tournament("API Finalize", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api@test.com",
            display_name="API User",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_1",
        )

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/finalize",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"checkout_session_id": "cs_api_1", "payment_reference": "pi_api_1"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("ok") is True
            assert data.get("result", {}).get("success") is True
            assert isinstance(data.get("result", {}).get("entry_id"), int)

        pending = get_pending_paid_entry("cs_api_1")
        assert pending is not None
        assert pending["status"] == "finalized"
        assert pending["payment_intent_id"] == "pi_api_1"

    def test_finalize_pending_not_found_returns_404(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/finalize",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"checkout_session_id": "cs_missing"},
            )
            assert resp.status_code == 404
            assert "not found" in str(resp.json().get("detail", "")).lower()


class TestTournamentOpsPendingListAndCleanupRoute:
    def test_pending_list_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending")
            assert resp.status_code == 401

    def test_pending_list_returns_rows_with_status_filter(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import mark_pending_paid_entry_finalized, save_pending_paid_entry

        assert save_pending_paid_entry(
            tournament_id=500,
            user_email="pending@test.com",
            display_name="Pending",
            roster=_make_paid_roster(),
            checkout_session_id="cs_list_pending",
        )
        assert save_pending_paid_entry(
            tournament_id=501,
            user_email="final@test.com",
            display_name="Final",
            roster=_make_paid_roster(),
            checkout_session_id="cs_list_final",
        )
        assert mark_pending_paid_entry_finalized("cs_list_final", "pi_list_final")

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/pending",
                params={"status": "pending", "limit": 50},
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("ok") is True
            assert data.get("count") >= 1
            assert any(str(r.get("checkout_session_id", "")) == "cs_list_pending" for r in data.get("rows", []))
            assert all(str(r.get("status", "")) == "pending" for r in data.get("rows", []))

    def test_pending_list_invalid_status_returns_400(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/pending",
                params={"status": "bad-status"},
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert resp.status_code == 400

    def test_pending_cleanup_expires_old_rows(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        import tournament.database as tdb
        from tournament.manager import get_pending_paid_entry, save_pending_paid_entry

        assert save_pending_paid_entry(
            tournament_id=700,
            user_email="old@test.com",
            display_name="Old",
            roster=_make_paid_roster(),
            checkout_session_id="cs_cleanup_old",
        )

        with tdb.get_tournament_connection() as conn:
            conn.execute(
                "UPDATE pending_paid_entries SET created_at='2099-06-01 00:00:00' WHERE checkout_session_id='cs_cleanup_old'"
            )
            conn.commit()

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/cleanup",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"max_age_hours": 1},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            assert int(payload.get("result", {}).get("expired", 0)) >= 1

        item = get_pending_paid_entry("cs_cleanup_old")
        assert item is not None
        assert item["status"] == "expired"


class TestTournamentOpsEventsRoute:
    def test_events_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/events")
            assert resp.status_code == 401

    def test_events_returns_filtered_rows(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.events import log_event

        log_event("pending.finalized", "ok-a", tournament_id=99, severity="info")
        log_event("pending.finalize_failed", "warn-a", tournament_id=99, severity="warning")
        log_event("pending.finalize_failed", "warn-b", tournament_id=100, severity="warning")

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/events",
                params={"tournament_id": 99, "event_type": "pending.finalize_failed", "severity": "warning"},
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            assert payload.get("count") == 1
            rows = payload.get("rows", [])
            assert len(rows) == 1
            assert str(rows[0].get("event_type", "")) == "pending.finalize_failed"
            assert str(rows[0].get("severity", "")) == "warning"
            assert int(rows[0].get("tournament_id", 0)) == 99

    def test_events_invalid_severity_returns_400(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/events",
                params={"severity": "critical"},
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert resp.status_code == 400


class TestTournamentOpsPendingDiagnosticsRoute:
    def test_pending_diagnostics_not_found(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/pending/cs_missing",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert resp.status_code == 404

    def test_pending_diagnostics_recommends_finalize(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, save_pending_paid_entry
        from tournament.webhooks import upsert_checkout_session

        tid = create_tournament("API Diag", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-diag@test.com",
            display_name="API Diag",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_diag_1",
        )
        assert upsert_checkout_session(
            "cs_api_diag_1",
            tournament_id=tid,
            user_email="api-diag@test.com",
            payment_intent_id="pi_api_diag_1",
            payment_status="paid",
        )

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/pending/cs_api_diag_1",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("recommended_action") == "finalize_now"
            assert result.get("can_finalize") is True


class TestTournamentOpsPendingReconcileRoute:
    def test_pending_reconcile_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile", json={"limit": 20})
            assert resp.status_code == 401

    def test_pending_reconcile_marks_stale_row(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, get_pending_paid_entry, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Reconcile", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-reconcile@test.com",
            display_name="API Reconcile",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_reconcile_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-reconcile@test.com",
            display_name="API Reconcile",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_reconcile_1",
        )
        assert ok is True

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"limit": 20},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            assert int(payload.get("result", {}).get("reconciled", 0)) >= 1

        item = get_pending_paid_entry("cs_api_reconcile_1")
        assert item is not None
        assert item["status"] == "finalized"

    def test_pending_reconcile_dry_run_no_mutation(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, get_pending_paid_entry, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Reconcile Dry", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-reconcile-dry@test.com",
            display_name="API Reconcile Dry",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_reconcile_dry_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-reconcile-dry@test.com",
            display_name="API Reconcile Dry",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_reconcile_dry_1",
        )
        assert ok is True

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"limit": 20, "dry_run": True},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert bool(result.get("dry_run")) is True
            assert int(result.get("candidates", 0)) >= 1
            assert int(result.get("reconciled", 0)) == 0

        item = get_pending_paid_entry("cs_api_reconcile_dry_1")
        assert item is not None
        assert item["status"] == "pending"

    def test_pending_reconcile_max_actions_and_priority(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Reconcile Cap", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        for sid in ("cs_api_cap_1", "cs_api_cap_2"):
            assert save_pending_paid_entry(
                tournament_id=tid,
                user_email=f"{sid}@test.com",
                display_name=sid,
                roster=_make_paid_roster(),
                checkout_session_id=sid,
            )
            ok, _, _ = submit_paid_entry_after_checkout(
                tournament_id=tid,
                user_email=f"{sid}@test.com",
                display_name=sid,
                roster=_make_paid_roster(),
                checkout_session_id=sid,
            )
            assert ok is True

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"limit": 20, "max_actions": 1, "priority": "oldest_first"},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert int(result.get("candidates", 0)) >= 2
            assert int(result.get("attempted", 0)) == 1
            assert len(str(result.get("attempted_sessions_sha256", ""))) == 64


class TestTournamentOpsReconcileDigestVerifyRoute:
    def test_digest_verify_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/verify-digest",
                json={"session_ids": ["cs_a"], "digest": "abc"},
            )
            assert resp.status_code == 401

    def test_digest_verify_match(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import compute_reconcile_digest

        session_ids = ["cs_a", "cs_b"]
        digest = compute_reconcile_digest(session_ids=session_ids, strict_order=True)

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/verify-digest",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"session_ids": session_ids, "digest": digest, "strict_order": True},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert result.get("match") is True

    def test_digest_verify_includes_reference_mismatch_details(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import compute_reconcile_digest

        digest = compute_reconcile_digest(session_ids=["cs_a", "cs_b"], strict_order=True)

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/verify-digest",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "session_ids": ["cs_a", "cs_c"],
                    "reference_session_ids": ["cs_a", "cs_b"],
                    "digest": digest,
                    "strict_order": True,
                },
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert result.get("match") is False
            assert result.get("first_mismatch_index") == 1

    def test_digest_verify_missing_digest_returns_400(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/verify-digest",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"session_ids": ["cs_a"], "digest": ""},
            )
            assert resp.status_code == 400


class TestTournamentOpsReconcileEventDigestVerifyRoute:
    def test_event_digest_verify_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/verify-event-digest",
                json={"event_id": 1, "session_ids": ["cs_a"]},
            )
            assert resp.status_code == 401

    def test_event_digest_verify_match(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.events import list_events
        from tournament.manager import create_tournament, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Event Verify", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-event@test.com",
            display_name="API Event",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_event_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-event@test.com",
            display_name="API Event",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_event_1",
        )
        assert ok is True

        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        events = list_events(event_type="pending.reconcile_summary", limit=20)
        assert len(events) >= 1
        event_id = int(events[0]["event_id"])

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/verify-event-digest",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"event_id": event_id, "session_ids": attempted, "scope": "attempted", "strict_order": True},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert result.get("match") is True


class TestTournamentOpsReconcileLatestEventDigestVerifyRoute:
    def test_latest_event_digest_verify_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/verify-latest-event-digest",
                json={"session_ids": ["cs_a"]},
            )
            assert resp.status_code == 401

    def test_latest_event_digest_verify_match(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Latest Event Verify", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-event-latest@test.com",
            display_name="API Event Latest",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_event_latest_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-event-latest@test.com",
            display_name="API Event Latest",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_event_latest_1",
        )
        assert ok is True

        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/verify-latest-event-digest",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"session_ids": attempted, "scope": "attempted", "strict_order": True},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert result.get("match") is True


class TestTournamentOpsReconcileVerificationReportRoute:
    def test_report_export_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/export-verification-report",
                json={"session_ids": ["cs_a"]},
            )
            assert resp.status_code == 401

    def test_report_export_match(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Report Verify", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-report@test.com",
            display_name="API Report",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_report_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-report@test.com",
            display_name="API Report",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_report_1",
        )
        assert ok is True

        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/export-verification-report",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"session_ids": attempted, "scope": "attempted", "strict_order": True},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert result.get("match") is True
            assert len(str(result.get("signature", ""))) == 64


class TestTournamentOpsReconcileVerificationEnvelopeRoute:
    def test_envelope_export_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/export-verification-envelope",
                json={"session_ids": ["cs_a"]},
            )
            assert resp.status_code == 401

    def test_envelope_export_match(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Envelope Verify", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-envelope@test.com",
            display_name="API Envelope",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_envelope_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-envelope@test.com",
            display_name="API Envelope",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_envelope_1",
        )
        assert ok is True

        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/export-verification-envelope",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"session_ids": attempted, "scope": "attempted", "strict_order": True},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert result.get("match") is True
            verify_payload = dict(result.get("verify_payload") or {})
            assert isinstance(verify_payload.get("report"), dict)
            assert len(str(verify_payload.get("signature", ""))) == 64


class TestTournamentOpsLatestReconcileSummaryRoute:
    def test_latest_summary_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/latest-summary")
            assert resp.status_code == 401

    def test_latest_summary_returns_result(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Latest Summary", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-latest-summary@test.com",
            display_name="API Latest Summary",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_latest_summary_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-latest-summary@test.com",
            display_name="API Latest Summary",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_latest_summary_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/pending/reconcile/latest-summary?scope=attempted",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert int(result.get("event_id", 0)) > 0


class TestTournamentOpsReconcileReportSignatureVerifyRoute:
    def test_signature_verify_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/verify-report-signature",
                json={"report": {}, "signature": "abc", "signature_type": "sha256"},
            )
            assert resp.status_code == 401

    def test_signature_verify_match(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, export_reconcile_verification_report, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Signature Verify", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-signature@test.com",
            display_name="API Signature",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_signature_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-signature@test.com",
            display_name="API Signature",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_signature_1",
        )
        assert ok is True
        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted, scope="attempted")

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/verify-report-signature",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "report": dict(report_result.get("report") or {}),
                    "signature": str(report_result.get("signature", "")),
                    "signature_type": str(report_result.get("signature_type", "sha256")),
                },
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert result.get("match") is True

    def test_signature_verify_key_id_mismatch_returns_400(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "k_expected")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, export_reconcile_verification_report, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Signature Key Mismatch", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-signature-key@test.com",
            display_name="API Signature Key",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_signature_key_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-signature-key@test.com",
            display_name="API Signature Key",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_signature_key_1",
        )
        assert ok is True
        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted, scope="attempted")

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/verify-report-signature",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "report": dict(report_result.get("report") or {}),
                    "signature": str(report_result.get("signature", "")),
                    "signature_type": str(report_result.get("signature_type", "hmac_sha256")),
                    "key_id": "k_wrong",
                },
            )
            assert resp.status_code == 400


class TestTournamentOpsReconcileReportSignatureReceiptRoute:
    def test_signature_receipt_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/verify-report-signature/receipt",
                json={"report": {}, "signature": "abc", "signature_type": "sha256"},
            )
            assert resp.status_code == 401

    def test_signature_receipt_and_list(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, export_reconcile_verification_report, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Signature Receipt", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-signature-receipt@test.com",
            display_name="API Signature Receipt",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_signature_receipt_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-signature-receipt@test.com",
            display_name="API Signature Receipt",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_signature_receipt_1",
        )
        assert ok is True
        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted, scope="attempted")

        with _make_client() as client:
            receipt_resp = client.post(
                "/ops/tournament/pending/reconcile/verify-report-signature/receipt",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "report": dict(report_result.get("report") or {}),
                    "signature": str(report_result.get("signature", "")),
                    "signature_type": str(report_result.get("signature_type", "hmac_sha256")),
                    "actor_email": "api-auditor@test.com",
                },
            )
            assert receipt_resp.status_code == 200
            receipt_payload = receipt_resp.json()
            assert receipt_payload.get("ok") is True
            receipt_result = receipt_payload.get("result", {})
            assert receipt_result.get("success") is True
            assert int(receipt_result.get("receipt_event_id", 0)) > 0

            list_resp = client.get(
                "/ops/tournament/pending/reconcile/signature-receipts?outcome=matched&limit=50",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert list_resp.status_code == 200
            list_payload = list_resp.json()
            assert list_payload.get("ok") is True
            assert int(list_payload.get("count", 0)) >= 1


class TestTournamentOpsReconcileSigningKeysStatusRoute:
    def test_signing_keys_status_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/signing-keys/status")
            assert resp.status_code == 401

    def test_signing_keys_status_returns_result(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEYS_JSON", '{"k_a":"abc"}')
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "k_a")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/pending/reconcile/signing-keys/status",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert int(result.get("registry_count", 0)) >= 1


class TestTournamentOpsReconcileSignatureReceiptsExportRoute:
    def test_receipts_export_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile/signature-receipts/export", json={})
            assert resp.status_code == 401

    def test_receipts_export_returns_digest(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, export_reconcile_verification_report, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Receipt Export", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-receipt-export@test.com",
            display_name="API Receipt Export",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_receipt_export_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-receipt-export@test.com",
            display_name="API Receipt Export",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_receipt_export_1",
        )
        assert ok is True
        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted, scope="attempted")

        with _make_client() as client:
            receipt_resp = client.post(
                "/ops/tournament/pending/reconcile/verify-report-signature/receipt",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "report": dict(report_result.get("report") or {}),
                    "signature": str(report_result.get("signature", "")),
                    "signature_type": str(report_result.get("signature_type", "hmac_sha256")),
                    "actor_email": "api-receipt-export-auditor@test.com",
                },
            )
            assert receipt_resp.status_code == 200

            export_resp = client.post(
                "/ops/tournament/pending/reconcile/signature-receipts/export",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"limit": 100, "outcome": "all", "include_csv": True},
            )
            assert export_resp.status_code == 200
            payload = export_resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert len(str(result.get("digest_sha256", ""))) == 64


class TestTournamentOpsReconcileSignatureReceiptsArtifactHeadRoute:
    def test_artifact_head_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/signature-receipts/artifact-head")
            assert resp.status_code == 401

    def test_artifact_head_returns_result(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, export_reconcile_signature_receipts_artifact, export_reconcile_verification_report, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Artifact Head", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-artifact-head@test.com",
            display_name="API Artifact Head",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_artifact_head_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-artifact-head@test.com",
            display_name="API Artifact Head",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_artifact_head_1",
        )
        assert ok is True
        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted, scope="attempted")

        with _make_client() as client:
            receipt_resp = client.post(
                "/ops/tournament/pending/reconcile/verify-report-signature/receipt",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "report": dict(report_result.get("report") or {}),
                    "signature": str(report_result.get("signature", "")),
                    "signature_type": str(report_result.get("signature_type", "hmac_sha256")),
                    "actor_email": "api-artifact-head-auditor@test.com",
                },
            )
            assert receipt_resp.status_code == 200

            export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)

            head_resp = client.get(
                "/ops/tournament/pending/reconcile/signature-receipts/artifact-head",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert head_resp.status_code == 200
            head_payload = head_resp.json()
            assert head_payload.get("ok") is True
            result = head_payload.get("result", {})
            assert result.get("success") is True
            assert len(str(result.get("digest_sha256", ""))) == 64


class TestTournamentOpsReconcileSignatureReceiptsVerifyChainRoute:
    def test_verify_chain_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/signature-receipts/verify-chain")
            assert resp.status_code == 401

    def test_verify_chain_returns_result(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, export_reconcile_signature_receipts_artifact, export_reconcile_verification_report, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Verify Chain", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-verify-chain@test.com",
            display_name="API Verify Chain",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_verify_chain_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-verify-chain@test.com",
            display_name="API Verify Chain",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_verify_chain_1",
        )
        assert ok is True
        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted, scope="attempted")

        with _make_client() as client:
            receipt_resp = client.post(
                "/ops/tournament/pending/reconcile/verify-report-signature/receipt",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "report": dict(report_result.get("report") or {}),
                    "signature": str(report_result.get("signature", "")),
                    "signature_type": str(report_result.get("signature_type", "hmac_sha256")),
                    "actor_email": "api-verify-chain-auditor@test.com",
                },
            )
            assert receipt_resp.status_code == 200

            export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)

            verify_resp = client.get(
                "/ops/tournament/pending/reconcile/signature-receipts/verify-chain?limit=200",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert verify_resp.status_code == 200
            verify_payload = verify_resp.json()
            assert verify_payload.get("ok") is True
            result = verify_payload.get("result", {})
            assert result.get("success") is True


class TestTournamentOpsReconcileSignatureChainCheckpointRoute:
    def test_checkpoint_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile/signature-receipts/checkpoint", json={})
            assert resp.status_code == 401

    def test_checkpoint_returns_result(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, export_reconcile_signature_receipts_artifact, export_reconcile_verification_report, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Checkpoint", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-checkpoint@test.com",
            display_name="API Checkpoint",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_checkpoint_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-checkpoint@test.com",
            display_name="API Checkpoint",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_checkpoint_1",
        )
        assert ok is True
        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted, scope="attempted")

        with _make_client() as client:
            receipt_resp = client.post(
                "/ops/tournament/pending/reconcile/verify-report-signature/receipt",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "report": dict(report_result.get("report") or {}),
                    "signature": str(report_result.get("signature", "")),
                    "signature_type": str(report_result.get("signature_type", "hmac_sha256")),
                    "actor_email": "api-checkpoint-auditor@test.com",
                },
            )
            assert receipt_resp.status_code == 200

            artifact = export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
            checkpoint_resp = client.post(
                "/ops/tournament/pending/reconcile/signature-receipts/checkpoint",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "label": "api_checkpoint",
                    "expected_previous_digest": str(artifact.get("digest_sha256", "")),
                    "require_head": True,
                },
            )
            assert checkpoint_resp.status_code == 200
            checkpoint_payload = checkpoint_resp.json()
            assert checkpoint_payload.get("ok") is True
            result = checkpoint_payload.get("result", {})
            assert result.get("success") is True
            assert len(str(result.get("checkpoint_digest", ""))) == 64


class TestTournamentOpsReconcileSignatureCheckpointVerifyRoute:
    def test_verify_checkpoint_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/signature-receipts/verify-checkpoint")
            assert resp.status_code == 401

    def test_verify_checkpoint_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, export_reconcile_signature_receipts_artifact, export_reconcile_verification_report, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Verify Checkpoint", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-verify-checkpoint@test.com",
            display_name="API Verify Checkpoint",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_verify_checkpoint_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-verify-checkpoint@test.com",
            display_name="API Verify Checkpoint",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_verify_checkpoint_1",
        )
        assert ok is True
        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted, scope="attempted")

        with _make_client() as client:
            receipt_resp = client.post(
                "/ops/tournament/pending/reconcile/verify-report-signature/receipt",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "report": dict(report_result.get("report") or {}),
                    "signature": str(report_result.get("signature", "")),
                    "signature_type": str(report_result.get("signature_type", "hmac_sha256")),
                    "actor_email": "api-verify-checkpoint-auditor@test.com",
                },
            )
            assert receipt_resp.status_code == 200

            artifact = export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
            checkpoint_resp = client.post(
                "/ops/tournament/pending/reconcile/signature-receipts/checkpoint",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "label": "api_verify_checkpoint",
                    "expected_previous_digest": str(artifact.get("digest_sha256", "")),
                    "require_head": True,
                },
            )
            assert checkpoint_resp.status_code == 200

            verify_resp = client.get(
                "/ops/tournament/pending/reconcile/signature-receipts/verify-checkpoint?require_current_head=true&require_signature_payload=true",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert verify_resp.status_code == 200
            payload = verify_resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert result.get("status") == "ok"
            assert bool((result.get("signature_verification") or {}).get("match", False)) is True


class TestTournamentOpsReconcileComplianceStatusRoute:
    def test_compliance_status_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/compliance-status")
            assert resp.status_code == 401

    def test_compliance_status_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, export_reconcile_signature_receipts_artifact, export_reconcile_verification_report, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Compliance Status", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-compliance-status@test.com",
            display_name="API Compliance Status",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_compliance_status_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-compliance-status@test.com",
            display_name="API Compliance Status",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_compliance_status_1",
        )
        assert ok is True
        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted, scope="attempted")

        with _make_client() as client:
            receipt_resp = client.post(
                "/ops/tournament/pending/reconcile/verify-report-signature/receipt",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "report": dict(report_result.get("report") or {}),
                    "signature": str(report_result.get("signature", "")),
                    "signature_type": str(report_result.get("signature_type", "hmac_sha256")),
                    "actor_email": "api-compliance-status-auditor@test.com",
                },
            )
            assert receipt_resp.status_code == 200

            export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)

            status_resp = client.get(
                "/ops/tournament/pending/reconcile/compliance-status?chain_limit=200",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert status_resp.status_code == 200
            payload = status_resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert result.get("artifact_chain", {}).get("status") == "ok"


class TestTournamentOpsReconcileSignatureCheckpointHistoryVerifyRoute:
    def test_verify_checkpoint_history_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/signature-receipts/verify-checkpoint-history")
            assert resp.status_code == 401

    def test_verify_checkpoint_history_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, export_reconcile_signature_receipts_artifact, export_reconcile_verification_report, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Verify Checkpoint History", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-verify-checkpoint-history@test.com",
            display_name="API Verify Checkpoint History",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_verify_checkpoint_history_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-verify-checkpoint-history@test.com",
            display_name="API Verify Checkpoint History",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_verify_checkpoint_history_1",
        )
        assert ok is True
        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted, scope="attempted")

        with _make_client() as client:
            receipt_resp = client.post(
                "/ops/tournament/pending/reconcile/verify-report-signature/receipt",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "report": dict(report_result.get("report") or {}),
                    "signature": str(report_result.get("signature", "")),
                    "signature_type": str(report_result.get("signature_type", "hmac_sha256")),
                    "actor_email": "api-verify-checkpoint-history-auditor@test.com",
                },
            )
            assert receipt_resp.status_code == 200

            artifact = export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
            checkpoint_resp = client.post(
                "/ops/tournament/pending/reconcile/signature-receipts/checkpoint",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "label": "api_verify_checkpoint_history",
                    "expected_previous_digest": str(artifact.get("digest_sha256", "")),
                    "require_head": True,
                },
            )
            assert checkpoint_resp.status_code == 200

            verify_resp = client.get(
                "/ops/tournament/pending/reconcile/signature-receipts/verify-checkpoint-history?limit=200&require_signature_payload=true",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert verify_resp.status_code == 200
            payload = verify_resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True


class TestTournamentOpsReconcileComplianceStatusArtifactRoute:
    def test_compliance_artifact_head_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/compliance-status/artifact-head")
            assert resp.status_code == 401

    def test_compliance_artifact_export_and_head_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Compliance Artifact", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-compliance-artifact@test.com",
            display_name="API Compliance Artifact",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_compliance_artifact_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-compliance-artifact@test.com",
            display_name="API Compliance Artifact",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_compliance_artifact_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        with _make_client() as client:
            export_resp = client.post(
                "/ops/tournament/pending/reconcile/compliance-status/export",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "chain_limit": 200,
                    "include_json": True,
                    "auto_chain": True,
                    "persist_event": True,
                },
            )
            assert export_resp.status_code == 200
            export_payload = export_resp.json()
            assert export_payload.get("ok") is True
            export_result = export_payload.get("result", {})
            assert export_result.get("success") is True
            assert len(str(export_result.get("digest_sha256", ""))) == 64

            head_resp = client.get(
                "/ops/tournament/pending/reconcile/compliance-status/artifact-head",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert head_resp.status_code == 200
            head_payload = head_resp.json()
            assert head_payload.get("ok") is True
            head_result = head_payload.get("result", {})
            assert head_result.get("success") is True
            assert str(head_result.get("digest_sha256", "")) == str(export_result.get("digest_sha256", ""))


class TestTournamentOpsReconcileComplianceStatusVerifyChainRoute:
    def test_compliance_verify_chain_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/compliance-status/verify-chain")
            assert resp.status_code == 401

    def test_compliance_verify_chain_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Compliance Chain Verify", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-compliance-chain-verify@test.com",
            display_name="API Compliance Chain Verify",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_compliance_chain_verify_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-compliance-chain-verify@test.com",
            display_name="API Compliance Chain Verify",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_compliance_chain_verify_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        with _make_client() as client:
            export_resp = client.post(
                "/ops/tournament/pending/reconcile/compliance-status/export",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"chain_limit": 200, "include_json": False, "auto_chain": True, "persist_event": True},
            )
            assert export_resp.status_code == 200

            verify_resp = client.get(
                "/ops/tournament/pending/reconcile/compliance-status/verify-chain?limit=200",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert verify_resp.status_code == 200
            payload = verify_resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True


class TestTournamentOpsReconcileComplianceStatusPruneRoute:
    def test_compliance_prune_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile/compliance-status/prune", json={})
            assert resp.status_code == 401

    def test_compliance_prune_dry_run(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/compliance-status/prune",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"max_age_days": 30, "dry_run": True},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert result.get("dry_run") is True

    def test_compliance_prune_with_keep_latest(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/compliance-status/prune",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"max_age_days": 30, "dry_run": True, "keep_latest": 2},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert int(result.get("keep_latest", 0) or 0) == 2


class TestTournamentOpsReconcileComplianceCheckpointRoute:
    def test_compliance_checkpoint_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile/compliance-status/checkpoint", json={})
            assert resp.status_code == 401

    def test_compliance_checkpoint_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Compliance Checkpoint", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-compliance-checkpoint@test.com",
            display_name="API Compliance Checkpoint",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_compliance_checkpoint_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-compliance-checkpoint@test.com",
            display_name="API Compliance Checkpoint",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_compliance_checkpoint_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        with _make_client() as client:
            export_resp = client.post(
                "/ops/tournament/pending/reconcile/compliance-status/export",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"chain_limit": 200, "include_json": False, "auto_chain": True, "persist_event": True},
            )
            assert export_resp.status_code == 200
            export_result = export_resp.json().get("result", {})

            checkpoint_resp = client.post(
                "/ops/tournament/pending/reconcile/compliance-status/checkpoint",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "label": "api_compliance_checkpoint",
                    "expected_previous_digest": str(export_result.get("digest_sha256", "")),
                    "require_head": True,
                },
            )
            assert checkpoint_resp.status_code == 200
            payload = checkpoint_resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert len(str(result.get("checkpoint_digest", ""))) == 64


class TestTournamentOpsReconcileComplianceCheckpointVerifyRoute:
    def test_compliance_verify_checkpoint_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/compliance-status/verify-checkpoint")
            assert resp.status_code == 401

    def test_compliance_verify_checkpoint_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Compliance Verify Checkpoint", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-compliance-verify-checkpoint@test.com",
            display_name="API Compliance Verify Checkpoint",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_compliance_verify_checkpoint_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-compliance-verify-checkpoint@test.com",
            display_name="API Compliance Verify Checkpoint",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_compliance_verify_checkpoint_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        with _make_client() as client:
            client.post(
                "/ops/tournament/pending/reconcile/compliance-status/export",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"chain_limit": 200, "include_json": False, "auto_chain": True, "persist_event": True},
            )
            client.post(
                "/ops/tournament/pending/reconcile/compliance-status/checkpoint",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"label": "api_verify_compliance_checkpoint", "require_head": True},
            )

            verify_resp = client.get(
                "/ops/tournament/pending/reconcile/compliance-status/verify-checkpoint?require_current_head=true&require_signature_payload=true",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert verify_resp.status_code == 200
            payload = verify_resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True


class TestTournamentOpsReconcileComplianceCheckpointHistoryVerifyRoute:
    def test_compliance_verify_checkpoint_history_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/compliance-status/verify-checkpoint-history")
            assert resp.status_code == 401

    def test_compliance_verify_checkpoint_history_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Compliance Checkpoint History", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-compliance-checkpoint-history@test.com",
            display_name="API Compliance Checkpoint History",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_compliance_checkpoint_history_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-compliance-checkpoint-history@test.com",
            display_name="API Compliance Checkpoint History",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_compliance_checkpoint_history_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        with _make_client() as client:
            client.post(
                "/ops/tournament/pending/reconcile/compliance-status/export",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"chain_limit": 200, "include_json": False, "auto_chain": True, "persist_event": True},
            )
            client.post(
                "/ops/tournament/pending/reconcile/compliance-status/checkpoint",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"label": "api_verify_compliance_checkpoint_history", "require_head": True},
            )

            verify_resp = client.get(
                "/ops/tournament/pending/reconcile/compliance-status/verify-checkpoint-history?limit=200&require_signature_payload=true",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert verify_resp.status_code == 200
            payload = verify_resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True


class TestTournamentOpsReconcileComplianceReadinessRoute:
    def test_compliance_readiness_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/compliance-status/readiness")
            assert resp.status_code == 401

    def test_compliance_readiness_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Compliance Readiness", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-compliance-readiness@test.com",
            display_name="API Compliance Readiness",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_compliance_readiness_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-compliance-readiness@test.com",
            display_name="API Compliance Readiness",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_compliance_readiness_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        with _make_client() as client:
            client.post(
                "/ops/tournament/pending/reconcile/compliance-status/export",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"chain_limit": 200, "include_json": False, "auto_chain": True, "persist_event": True},
            )
            client.post(
                "/ops/tournament/pending/reconcile/compliance-status/checkpoint",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"label": "api_readiness_checkpoint", "require_head": True},
            )

            readiness_resp = client.get(
                "/ops/tournament/pending/reconcile/compliance-status/readiness?chain_limit=200&warning_threshold=80&error_threshold=60&policy_name=api_test&persist_event=true",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert readiness_resp.status_code == 200
            payload = readiness_resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert str((result.get("policy") or {}).get("name", "")) == "api_test"
            assert str(result.get("status", "")) in {"ready", "warning", "blocked"}
            assert 0 <= int(result.get("score", 0) or 0) <= 100

            readiness_monitor_resp = client.get(
                "/ops/tournament/pending/reconcile/compliance-status/readiness?policy_name=api_test&persist_event=true&monitor_transition=true&transition_cooldown_minutes=30&notify_users=false",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert readiness_monitor_resp.status_code == 200
            monitor_payload = readiness_monitor_resp.json()
            assert monitor_payload.get("ok") is True
            monitor_result = monitor_payload.get("result", {})
            assert monitor_result.get("success") is True
            assert "transition" in monitor_result


class TestTournamentOpsReconcileComplianceReadinessPoliciesRoute:
    def test_compliance_readiness_policies_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/compliance-status/readiness-policies")
            assert resp.status_code == 401

    def test_compliance_readiness_policies_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv(
            "TOURNAMENT_RECONCILE_COMPLIANCE_POLICIES_JSON",
            '{"api_custom":{"chain_limit":150,"warning_threshold":85,"error_threshold":70,"monitor_transition":true,"transition_cooldown_minutes":45,"issue_penalty":33,"warning_penalty":6,"check_failure_penalty_default":7,"check_failure_penalties":{"signing_key_ready":19}}}',
        )
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/pending/reconcile/compliance-status/readiness-policies",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            policies = dict(result.get("policies") or {})
            assert "default" in policies
            assert "api_custom" in policies
            api_custom = dict(policies.get("api_custom") or {})
            assert int(api_custom.get("transition_cooldown_minutes", 0) or 0) == 45
            assert int(api_custom.get("issue_penalty", 0) or 0) == 33


class TestTournamentOpsReconcileComplianceReadinessPolicySnapshotRoute:
    def test_compliance_readiness_policy_snapshot_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile/compliance-status/readiness-policy-snapshot", json={})
            assert resp.status_code == 401

    def test_compliance_readiness_policy_snapshot_export_head_verify_chain_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        monkeypatch.setenv(
            "TOURNAMENT_RECONCILE_COMPLIANCE_POLICIES_JSON",
            '{"api_snapshot":{"chain_limit":140,"warning_threshold":84,"error_threshold":66,"monitor_transition":true}}',
        )
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            export_resp = client.post(
                "/ops/tournament/pending/reconcile/compliance-status/readiness-policy-snapshot",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "policy_name": "api_snapshot",
                    "include_registry": True,
                    "auto_chain": True,
                    "persist_event": True,
                },
            )
            assert export_resp.status_code == 200
            export_payload = export_resp.json()
            assert export_payload.get("ok") is True
            export_result = export_payload.get("result", {})
            assert export_result.get("success") is True
            assert len(str(export_result.get("digest_sha256", ""))) == 64

            head_resp = client.get(
                "/ops/tournament/pending/reconcile/compliance-status/readiness-policy-snapshot-head?policy_name=api_snapshot",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert head_resp.status_code == 200
            head_payload = head_resp.json()
            assert head_payload.get("ok") is True
            head_result = head_payload.get("result", {})
            assert head_result.get("success") is True
            assert str(head_result.get("digest_sha256", "")) == str(export_result.get("digest_sha256", ""))

            verify_resp = client.get(
                "/ops/tournament/pending/reconcile/compliance-status/readiness-policy-snapshot-verify-chain?limit=200&policy_name=api_snapshot",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert verify_resp.status_code == 200
            verify_payload = verify_resp.json()
            assert verify_payload.get("ok") is True
            verify_result = verify_payload.get("result", {})
            assert verify_result.get("success") is True
            assert str(verify_result.get("status", "")) in {"ok", "broken", "empty"}

            prune_resp = client.post(
                "/ops/tournament/pending/reconcile/compliance-status/readiness-policy-snapshot/prune",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "policy_name": "api_snapshot",
                    "max_age_days": 30,
                    "dry_run": True,
                    "keep_latest": 1,
                },
            )
            assert prune_resp.status_code == 200
            prune_payload = prune_resp.json()
            assert prune_payload.get("ok") is True
            assert prune_payload.get("result", {}).get("success") is True

            checkpoint_resp = client.post(
                "/ops/tournament/pending/reconcile/compliance-status/readiness-policy-snapshot/checkpoint",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "policy_name": "api_snapshot",
                    "label": "api_snapshot_checkpoint",
                    "require_head": True,
                },
            )
            assert checkpoint_resp.status_code == 200
            checkpoint_payload = checkpoint_resp.json()
            assert checkpoint_payload.get("ok") is True
            checkpoint_result = checkpoint_payload.get("result", {})
            assert checkpoint_result.get("success") is True
            assert int(checkpoint_result.get("event_id", 0) or 0) > 0

            checkpoint_verify_resp = client.get(
                "/ops/tournament/pending/reconcile/compliance-status/readiness-policy-snapshot/verify-checkpoint?policy_name=api_snapshot&require_current_head=true&require_signature_payload=true",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert checkpoint_verify_resp.status_code == 200
            checkpoint_verify_payload = checkpoint_verify_resp.json()
            assert checkpoint_verify_payload.get("ok") is True
            assert str(checkpoint_verify_payload.get("result", {}).get("status", "")) in {"ok", "stale", "broken", "empty"}

            checkpoint_history_resp = client.get(
                "/ops/tournament/pending/reconcile/compliance-status/readiness-policy-snapshot/verify-checkpoint-history?limit=200&policy_name=api_snapshot&require_signature_payload=true",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert checkpoint_history_resp.status_code == 200
            checkpoint_history_payload = checkpoint_history_resp.json()
            assert checkpoint_history_payload.get("ok") is True
            assert checkpoint_history_payload.get("result", {}).get("success") is True

            readiness_artifact_export_resp = client.post(
                "/ops/tournament/pending/reconcile/compliance-status/readiness-evaluation-artifact",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "policy_name": "api_snapshot",
                    "chain_limit": 200,
                    "warning_threshold": 80,
                    "error_threshold": 60,
                    "include_json": True,
                    "include_snapshot": True,
                    "persist_readiness_event": False,
                    "auto_chain": True,
                    "persist_event": True,
                },
            )
            assert readiness_artifact_export_resp.status_code == 200
            readiness_artifact_export_payload = readiness_artifact_export_resp.json()
            assert readiness_artifact_export_payload.get("ok") is True
            readiness_artifact_export_result = readiness_artifact_export_payload.get("result", {})
            assert readiness_artifact_export_result.get("success") is True
            assert len(str(readiness_artifact_export_result.get("digest_sha256", ""))) == 64

            readiness_artifact_head_resp = client.get(
                "/ops/tournament/pending/reconcile/compliance-status/readiness-evaluation-artifact-head?policy_name=api_snapshot",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert readiness_artifact_head_resp.status_code == 200
            readiness_artifact_head_payload = readiness_artifact_head_resp.json()
            assert readiness_artifact_head_payload.get("ok") is True
            readiness_artifact_head_result = readiness_artifact_head_payload.get("result", {})
            assert readiness_artifact_head_result.get("success") is True

            readiness_artifact_chain_resp = client.get(
                "/ops/tournament/pending/reconcile/compliance-status/readiness-evaluation-artifact-verify-chain?limit=200&policy_name=api_snapshot",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert readiness_artifact_chain_resp.status_code == 200
            readiness_artifact_chain_payload = readiness_artifact_chain_resp.json()
            assert readiness_artifact_chain_payload.get("ok") is True
            assert readiness_artifact_chain_payload.get("result", {}).get("success") is True


class TestTournamentOpsReconcileComplianceEnvelopeRoute:
    def test_compliance_envelope_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile/compliance-status/export-envelope", json={})
            assert resp.status_code == 401

    def test_compliance_envelope_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Compliance Envelope", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-compliance-envelope@test.com",
            display_name="API Compliance Envelope",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_compliance_envelope_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-compliance-envelope@test.com",
            display_name="API Compliance Envelope",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_compliance_envelope_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        with _make_client() as client:
            envelope_resp = client.post(
                "/ops/tournament/pending/reconcile/compliance-status/export-envelope",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "chain_limit": 200,
                    "include_json": False,
                    "auto_chain": True,
                    "persist_event": True,
                    "create_checkpoint": True,
                    "checkpoint_label": "api_compliance_envelope",
                    "checkpoint_note": "api_test",
                    "require_current_head": False,
                    "require_signature_payload": True,
                },
            )
            assert envelope_resp.status_code == 200
            payload = envelope_resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert len(str(result.get("envelope_digest", ""))) == 64
            verify_payload = dict(result.get("verify_payload") or {})
            assert len(str(verify_payload.get("artifact_digest_sha256", ""))) == 64
            assert int(verify_payload.get("checkpoint_event_id", 0) or 0) > 0


class TestTournamentOpsReconcileSignatureReceiptsPruneRoute:
    def test_receipts_prune_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile/signature-receipts/prune", json={})
            assert resp.status_code == 401

    def test_receipts_prune_dry_run(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/signature-receipts/prune",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"max_age_days": 30, "dry_run": True},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert result.get("dry_run") is True


class TestTournamentOpsReconcileSignatureChainCheckpointRoute:
    def test_chain_checkpoint_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile/signature-receipts/checkpoint", json={})
            assert resp.status_code == 401

    def test_chain_checkpoint_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import create_tournament, export_reconcile_signature_receipts_artifact, export_reconcile_verification_report, reconcile_pending_paid_entries, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("API Chain Checkpoint", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-chain-checkpoint@test.com",
            display_name="API Chain Checkpoint",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_chain_checkpoint_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-chain-checkpoint@test.com",
            display_name="API Chain Checkpoint",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_chain_checkpoint_1",
        )
        assert ok is True
        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted, scope="attempted")

        with _make_client() as client:
            receipt_resp = client.post(
                "/ops/tournament/pending/reconcile/verify-report-signature/receipt",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "report": dict(report_result.get("report") or {}),
                    "signature": str(report_result.get("signature", "")),
                    "signature_type": str(report_result.get("signature_type", "hmac_sha256")),
                    "actor_email": "api-chain-checkpoint-auditor@test.com",
                },
            )
            assert receipt_resp.status_code == 200

            artifact = export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
            checkpoint_resp = client.post(
                "/ops/tournament/pending/reconcile/signature-receipts/checkpoint",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "label": "api_checkpoint",
                    "expected_previous_digest": str(artifact.get("digest_sha256", "")),
                    "require_head": True,
                },
            )
            assert checkpoint_resp.status_code == 200
            payload = checkpoint_resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert len(str(result.get("checkpoint_digest", ""))) == 64


class TestTournamentOpsReadinessEvaluationArtifactPruneRoute:
    def test_prune_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile/compliance-status/readiness-evaluation-artifact/prune", json={})
            assert resp.status_code == 401

    def test_prune_dry_run(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/compliance-status/readiness-evaluation-artifact/prune",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"max_age_days": 30, "dry_run": True, "keep_latest": 1},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert result.get("dry_run") is True


class TestTournamentOpsReadinessEvaluationArtifactCheckpointRoute:
    def test_checkpoint_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile/compliance-status/readiness-evaluation-artifact/checkpoint", json={})
            assert resp.status_code == 401

    def test_checkpoint_no_head_returns_400_or_404(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/compliance-status/readiness-evaluation-artifact/checkpoint",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"label": "api_test", "require_head": True},
            )
            assert resp.status_code in {400, 404}


class TestTournamentOpsReadinessEvaluationArtifactVerifyCheckpointRoute:
    def test_verify_checkpoint_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/compliance-status/readiness-evaluation-artifact/verify-checkpoint")
            assert resp.status_code == 401

    def test_verify_checkpoint_empty(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/pending/reconcile/compliance-status/readiness-evaluation-artifact/verify-checkpoint",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            assert str(payload.get("result", {}).get("status", "")) in {"ok", "stale", "broken", "empty"}


class TestTournamentOpsReadinessEvaluationArtifactVerifyCheckpointHistoryRoute:
    def test_verify_history_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/compliance-status/readiness-evaluation-artifact/verify-checkpoint-history")
            assert resp.status_code == 401

    def test_verify_history_empty_ok(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/pending/reconcile/compliance-status/readiness-evaluation-artifact/verify-checkpoint-history",
                headers={"x-tournament-admin-key": "expected-key"},
                params={"limit": 50},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert "ok" in result
            assert "broken" in result


class TestTournamentOpsReadinessEvaluationArtifactEnvelopeRoute:
    def test_envelope_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile/compliance-status/readiness-evaluation-artifact/export-envelope", json={})
            assert resp.status_code == 401

    def test_envelope_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        from tournament.manager import (
            create_tournament,
            export_reconcile_compliance_status_artifact,
            reconcile_pending_paid_entries,
            save_pending_paid_entry,
            submit_paid_entry_after_checkout,
        )

        tid = create_tournament("API RA Envelope", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        assert save_pending_paid_entry(
            tournament_id=tid,
            user_email="api-ra-envelope@test.com",
            display_name="API RA Envelope",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_ra_envelope_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="api-ra-envelope@test.com",
            display_name="API RA Envelope",
            roster=_make_paid_roster(),
            checkout_session_id="cs_api_ra_envelope_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        export_reconcile_compliance_status_artifact(chain_limit=50, include_json=False, auto_chain=True, persist_event=True)

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/compliance-status/readiness-evaluation-artifact/export-envelope",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "policy_name": "default",
                    "chain_limit": 50,
                    "include_json": False,
                    "include_snapshot": False,
                    "persist_event": True,
                    "create_checkpoint": True,
                    "checkpoint_label": "api_test_envelope",
                    "require_current_head": False,
                    "require_signature_payload": False,
                },
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            vp = dict(result.get("verify_payload") or {})
            assert len(str(vp.get("artifact_digest_sha256", ""))) == 64


class TestTournamentOpsCompositeGovernanceSnapshotRoute:
    def test_composite_snapshot_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile/composite-governance-snapshot/export", json={})
            assert resp.status_code == 401

    def test_composite_snapshot_lifecycle_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            export_resp = client.post(
                "/ops/tournament/pending/reconcile/composite-governance-snapshot/export",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "policy_name": "default",
                    "chain_limit": 200,
                    "warning_threshold": 80,
                    "error_threshold": 60,
                    "include_json": False,
                    "include_snapshot": False,
                    "auto_chain": True,
                    "persist_event": True,
                },
            )
            assert export_resp.status_code == 200
            export_payload = export_resp.json()
            assert export_payload.get("ok") is True
            export_result = export_payload.get("result", {})
            assert export_result.get("success") is True
            assert len(str(export_result.get("digest_sha256", ""))) == 64

            head_resp = client.get(
                "/ops/tournament/pending/reconcile/composite-governance-snapshot/artifact-head?policy_name=default",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert head_resp.status_code == 200
            head_payload = head_resp.json()
            assert head_payload.get("ok") is True
            assert head_payload.get("result", {}).get("success") is True

            chain_resp = client.get(
                "/ops/tournament/pending/reconcile/composite-governance-snapshot/verify-chain?limit=200&policy_name=default",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert chain_resp.status_code == 200
            chain_payload = chain_resp.json()
            assert chain_payload.get("ok") is True
            assert chain_payload.get("result", {}).get("success") is True


class TestTournamentOpsCompositeGovernanceSnapshotPruneRoute:
    def test_composite_prune_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile/composite-governance-snapshot/prune", json={})
            assert resp.status_code == 401

    def test_composite_prune_dry_run(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/composite-governance-snapshot/prune",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"policy_name": "default", "max_age_days": 30, "dry_run": True, "keep_latest": 1},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert result.get("dry_run") is True


class TestTournamentOpsCompositeGovernanceSnapshotCheckpointRoute:
    def test_composite_checkpoint_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile/composite-governance-snapshot/checkpoint", json={})
            assert resp.status_code == 401

    def test_composite_checkpoint_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            export_resp = client.post(
                "/ops/tournament/pending/reconcile/composite-governance-snapshot/export",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"policy_name": "default", "auto_chain": True, "persist_event": True},
            )
            assert export_resp.status_code == 200

            ckpt_resp = client.post(
                "/ops/tournament/pending/reconcile/composite-governance-snapshot/checkpoint",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"policy_name": "default", "label": "api_composite_ckpt", "require_head": True},
            )
            assert ckpt_resp.status_code == 200
            payload = ckpt_resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            assert len(str(result.get("checkpoint_digest", ""))) == 64


class TestTournamentOpsCompositeGovernanceSnapshotVerifyCheckpointRoute:
    def test_composite_verify_checkpoint_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/composite-governance-snapshot/verify-checkpoint")
            assert resp.status_code == 401

    def test_composite_verify_checkpoint_empty_or_ok(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/pending/reconcile/composite-governance-snapshot/verify-checkpoint",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            assert str(payload.get("result", {}).get("status", "")) in {"ok", "stale", "broken", "empty"}


class TestTournamentOpsCompositeGovernanceSnapshotVerifyCheckpointHistoryRoute:
    def test_composite_verify_history_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/composite-governance-snapshot/verify-checkpoint-history")
            assert resp.status_code == 401

    def test_composite_verify_history_empty_ok(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/pending/reconcile/composite-governance-snapshot/verify-checkpoint-history",
                headers={"x-tournament-admin-key": "expected-key"},
                params={"limit": 50},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert "ok" in result
            assert "broken" in result


class TestTournamentOpsCompositeGovernanceSnapshotEnvelopeRoute:
    def test_composite_envelope_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile/composite-governance-snapshot/export-envelope", json={})
            assert resp.status_code == 401

    def test_composite_envelope_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/pending/reconcile/composite-governance-snapshot/export-envelope",
                headers={"x-tournament-admin-key": "expected-key"},
                json={
                    "policy_name": "default",
                    "chain_limit": 50,
                    "include_json": False,
                    "include_snapshot": False,
                    "persist_event": True,
                    "create_checkpoint": True,
                    "checkpoint_label": "api_test_composite_envelope",
                    "require_current_head": False,
                    "require_signature_payload": False,
                },
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert result.get("success") is True
            vp = dict(result.get("verify_payload") or {})
            assert len(str(vp.get("artifact_digest_sha256", ""))) == 64
            assert int(vp.get("checkpoint_event_id", 0) or 0) >= 0


class TestTournamentOpsGovernanceAttestationSealRoute:
    def test_attestation_seal_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/pending/reconcile/governance-attestation-seal/export", json={})
            assert resp.status_code == 401

    def test_attestation_seal_lifecycle_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            export_resp = client.post(
                "/ops/tournament/pending/reconcile/governance-attestation-seal/export",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"policy_name": "default", "chain_limit": 50, "persist_event": True},
            )
            assert export_resp.status_code == 200
            export_payload = export_resp.json()
            assert export_payload.get("ok") is True
            assert export_payload.get("result", {}).get("success") is True

            head_resp = client.get(
                "/ops/tournament/pending/reconcile/governance-attestation-seal/artifact-head?policy_name=default",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert head_resp.status_code == 200

            chain_resp = client.get(
                "/ops/tournament/pending/reconcile/governance-attestation-seal/verify-chain?limit=200&policy_name=default",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert chain_resp.status_code == 200

            prune_resp = client.post(
                "/ops/tournament/pending/reconcile/governance-attestation-seal/prune",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"policy_name": "default", "max_age_days": 30, "dry_run": True, "keep_latest": 1},
            )
            assert prune_resp.status_code == 200

            ckpt_resp = client.post(
                "/ops/tournament/pending/reconcile/governance-attestation-seal/checkpoint",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"policy_name": "default", "label": "api_attestation_ckpt", "require_head": True},
            )
            assert ckpt_resp.status_code == 200
            assert ckpt_resp.json().get("ok") is True

            ckpt_verify_resp = client.get(
                "/ops/tournament/pending/reconcile/governance-attestation-seal/verify-checkpoint?policy_name=default&require_current_head=true",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert ckpt_verify_resp.status_code == 200

            ckpt_hist_resp = client.get(
                "/ops/tournament/pending/reconcile/governance-attestation-seal/verify-checkpoint-history?limit=100&policy_name=default",
                headers={"x-tournament-admin-key": "expected-key"},
            )
            assert ckpt_hist_resp.status_code == 200


class TestTournamentOpsGovernanceRepairDiagnosticsRoute:
    def test_diagnostics_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/governance/repair-diagnostics")
            assert resp.status_code == 401

    def test_diagnostics_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/pending/reconcile/governance/repair-diagnostics",
                headers={"x-tournament-admin-key": "expected-key"},
                params={"limit": 50, "policy_name": "default"},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            result = payload.get("result", {})
            assert "status" in result
            assert "recommended_actions" in result


class TestTournamentOpsGovernanceEnforcementCheckRoute:
    def test_enforcement_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/pending/reconcile/governance/enforcement-check")
            assert resp.status_code == 401

    def test_enforcement_success(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/pending/reconcile/governance/enforcement-check",
                headers={"x-tournament-admin-key": "expected-key"},
                params={"action": "financial_ops", "policy_name": "default", "block_on_warning": False, "require_attestation_seal": False},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            assert "blocked" in payload.get("result", {})


class TestTournamentOpsSeasonAndChampionshipRoutes:
    def test_season_leaderboard_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.get("/ops/tournament/season/leaderboard?year=2026")
            assert resp.status_code == 401

    def test_season_distribute_rewards_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/season/distribute-rewards", json={"year": 2026, "month": 4})
            assert resp.status_code == 401

    def test_championship_qualify_requires_auth(self, monkeypatch):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")

        with _make_client() as client:
            resp = client.post("/ops/tournament/championship/qualify", json={"season_label": "2026 April"})
            assert resp.status_code == 401

    def test_season_leaderboard_empty(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.get(
                "/ops/tournament/season/leaderboard",
                headers={"x-tournament-admin-key": "expected-key"},
                params={"year": 2099, "month": 1},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            assert payload.get("rows") == []

    def test_season_distribute_rewards_no_data(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/season/distribute-rewards",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"year": 2099, "month": 6, "top_pct": 0.10, "bonus_lp": 100},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("ok") is True
            assert payload["result"]["awarded_count"] == 0

    def test_championship_qualify_no_data_returns_400(self, monkeypatch, tmp_path):
        _skip_if_no_fastapi()
        monkeypatch.setenv("TOURNAMENT_ADMIN_API_KEY", "expected-key")
        _configure_temp_tournament_db(monkeypatch, tmp_path)

        with _make_client() as client:
            resp = client.post(
                "/ops/tournament/championship/qualify",
                headers={"x-tournament-admin-key": "expected-key"},
                json={"season_label": "2099 Empty", "year": 2099, "month": 1},
            )
            assert resp.status_code == 400
