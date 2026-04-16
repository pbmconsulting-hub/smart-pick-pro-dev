"""Integration tests for Stripe Connect onboarding and payout SLA scheduling flows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import tournament.database as tdb
from tournament.manager import (
    create_tournament,
    create_user_connect_onboarding,
    evaluate_user_payout_eligibility,
    list_due_payout_entries,
    process_due_payouts,
    submit_entry,
    sync_user_connect_status_from_stripe,
    upsert_user_connect_status,
)


def _make_roster() -> list[dict]:
    active = [
        {"player_id": f"A{i}", "player_name": f"Player {i}", "salary": 5500, "is_legend": False}
        for i in range(8)
    ]
    legend = {"player_id": "L001", "player_name": "MJ", "salary": 15000, "is_legend": True}
    return active + [legend]


def test_connect_onboarding_sync_and_kyc_eligibility(isolated_db, monkeypatch):
    monkeypatch.setattr(
        "tournament.stripe.create_connect_account",
        lambda user_email: {"success": True, "account_id": "acct_kyc_1", "error": ""},
    )
    monkeypatch.setattr(
        "tournament.stripe.create_connect_onboarding_link",
        lambda account_id, refresh_path="/", return_path="/": {
            "success": True,
            "url": "https://example.com/onboarding",
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

    onboarding = create_user_connect_onboarding("winner@test.com", refresh_path="/r", return_path="/done")
    assert onboarding["success"] is True
    assert onboarding["stripe_connect_account_id"] == "acct_kyc_1"

    # Seed paid payouts above KYC threshold for current year.
    tid = create_tournament("KYC Threshold", "Pro", 20.0, 1, 24, "2099-06-01T20:00:00")
    ok, _, entry_id = submit_entry(tid, "winner@test.com", "Winner", _make_roster())
    assert ok is True

    with tdb.get_tournament_connection() as conn:
        conn.execute(
            "UPDATE tournaments SET status='resolved', resolved_at=datetime('now') WHERE tournament_id = ?",
            (int(tid),),
        )
        conn.execute(
            "UPDATE tournament_entries SET payout_amount=650.0, payout_status='paid' WHERE entry_id = ?",
            (int(entry_id),),
        )
        conn.commit()

    before_sync = evaluate_user_payout_eligibility("winner@test.com")
    assert before_sync["allowed"] is False
    assert any("onboarding" in reason.lower() or "enabled" in reason.lower() for reason in before_sync["reasons"])

    synced = sync_user_connect_status_from_stripe("winner@test.com")
    assert synced["success"] is True

    after_sync = evaluate_user_payout_eligibility("winner@test.com")
    assert after_sync["allowed"] is True


def test_due_payout_listing_and_processing(isolated_db):
    tid = create_tournament("Due Payouts", "Pro", 20.0, 1, 24, "2099-06-01T20:00:00")
    ok, _, entry_id = submit_entry(tid, "due@test.com", "Due User", _make_roster())
    assert ok is True

    upsert = upsert_user_connect_status(
        "due@test.com",
        stripe_connect_account_id="acct_due_1",
        onboarding_status="verified",
        details_submitted=True,
        payouts_enabled=True,
        requirements={"currently_due": []},
        kyc_verified=True,
    )
    assert upsert["success"] is True

    past = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    with tdb.get_tournament_connection() as conn:
        conn.execute(
            "UPDATE tournaments SET status='resolved', resolved_at=? WHERE tournament_id = ?",
            (past, int(tid)),
        )
        conn.execute(
            "UPDATE tournament_entries SET payout_amount=150.0, payout_status='pending', rank=1 WHERE entry_id = ?",
            (int(entry_id),),
        )
        conn.commit()

    due = list_due_payout_entries(sla_hours=24, limit=50)
    assert any(int(row.get("entry_id", 0)) == int(entry_id) for row in due)

    with patch("tournament.payout_runner.create_winner_payout_transfer") as mock_transfer:
        mock_transfer.return_value = {"success": True, "transfer_id": "tr_due_1"}
        result = process_due_payouts(sla_hours=24, max_tournaments=10)

    assert result["success"] is True
    assert int(result["processed_tournaments"]) >= 1
    assert int(result["transferred"]) >= 1
