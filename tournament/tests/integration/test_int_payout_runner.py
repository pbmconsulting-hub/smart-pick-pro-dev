"""Integration tests for tournament.payout_runner — real refund/payout processing.

Stripe calls are mocked since we don't have real Stripe keys.
"""

from unittest.mock import patch

import tournament.database as tdb
from tournament.manager import create_tournament, submit_entry
from tournament.payout_runner import (
    process_cancelled_tournament_refunds,
    process_resolved_tournament_payouts,
)


def _make_roster():
    active = [
        {"player_id": f"A{i}", "player_name": f"Player {i}", "salary": 5500, "is_legend": False}
        for i in range(8)
    ]
    legend = {"player_id": "L001", "player_name": "MJ", "salary": 15000, "is_legend": True}
    return active + [legend]


def _cancel_tournament(tid):
    """Manually cancel a tournament in the DB for testing."""
    with tdb.get_tournament_connection() as conn:
        conn.execute("UPDATE tournaments SET status='cancelled' WHERE tournament_id=?", (tid,))
        conn.commit()


def _resolve_tournament_manual(tid):
    """Manually mark a tournament as resolved for testing."""
    with tdb.get_tournament_connection() as conn:
        conn.execute("UPDATE tournaments SET status='resolved' WHERE tournament_id=?", (tid,))
        conn.commit()


class TestProcessCancelledTournamentRefunds:
    def test_not_found(self, isolated_db):
        result = process_cancelled_tournament_refunds(99999)
        assert result["success"] is False

    def test_not_cancelled_rejected(self, isolated_db):
        tid = create_tournament("Refund", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        result = process_cancelled_tournament_refunds(tid)
        assert result["success"] is False

    @patch("tournament.payout_runner.create_tournament_refund")
    def test_refunds_paid_entries(self, mock_refund, isolated_db):
        mock_refund.return_value = {"success": True, "refund_id": "re_test123"}
        tid = create_tournament("Ref", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        submit_entry(tid, "a@t.com", "A", _make_roster(), stripe_payment_intent_id="pi_abc")
        _cancel_tournament(tid)
        result = process_cancelled_tournament_refunds(tid)
        assert result["success"] is True
        assert result["refunded"] == 1
        mock_refund.assert_called_once_with("pi_abc")

    def test_no_payment_intent_skipped(self, isolated_db):
        tid = create_tournament("Free", "Open", 0.0, 2, 64, "2099-06-01T20:00:00")
        submit_entry(tid, "a@t.com", "A", [
            {"player_id": f"A{i}", "player_name": f"P{i}", "salary": 5500, "is_legend": False}
            for i in range(8)
        ])
        _cancel_tournament(tid)
        result = process_cancelled_tournament_refunds(tid)
        assert result["success"] is True
        assert result["refunded"] == 0


class TestProcessResolvedTournamentPayouts:
    def test_not_found(self, isolated_db):
        result = process_resolved_tournament_payouts(99999)
        assert result["success"] is False

    def test_not_resolved_rejected(self, isolated_db):
        tid = create_tournament("Pay", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        result = process_resolved_tournament_payouts(tid)
        assert result["success"] is False

    @patch("tournament.payout_runner.create_winner_payout_transfer")
    def test_pays_winners_with_connect(self, mock_transfer, isolated_db):
        mock_transfer.return_value = {"success": True, "transfer_id": "tr_test"}
        tid = create_tournament("Payout", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        submit_entry(tid, "winner@t.com", "W", _make_roster())
        _resolve_tournament_manual(tid)

        # Set payout amount and connect account
        with tdb.get_tournament_connection() as conn:
            conn.execute(
                "UPDATE tournament_entries SET payout_amount=100.0, rank=1 WHERE tournament_id=?",
                (tid,),
            )
            conn.execute(
                """INSERT INTO user_career_stats (user_email, stripe_connect_account_id)
                   VALUES ('winner@t.com', 'acct_test123')
                   ON CONFLICT(user_email) DO UPDATE SET stripe_connect_account_id='acct_test123'""",
            )
            conn.commit()

        result = process_resolved_tournament_payouts(tid)
        assert result["success"] is True
        assert result["transferred"] == 1
