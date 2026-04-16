from pathlib import Path

import tournament.database as tdb
from tournament.manager import create_tournament
from tournament.payout_runner import (
    process_cancelled_tournament_refunds,
    process_resolved_tournament_payouts,
)


def _configure_temp_db(monkeypatch, tmp_path: Path):
    db_file = tmp_path / "tournament_test.db"
    monkeypatch.setattr(tdb, "DB_DIRECTORY", tmp_path)
    monkeypatch.setattr(tdb, "TOURNAMENT_DB_PATH", db_file)
    assert tdb.initialize_tournament_database() is True


def test_process_cancelled_tournament_refunds(monkeypatch, tmp_path):
    _configure_temp_db(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "tournament.payout_runner.create_tournament_refund",
        lambda payment_intent_id: {"success": True, "refund_id": f"re_{payment_intent_id}"},
    )

    tid = create_tournament(
        tournament_name="Cancel Me",
        court_tier="Elite",
        entry_fee=50.0,
        min_entries=12,
        max_entries=24,
        lock_time="2026-04-20T20:00:00",
    )

    with tdb.get_tournament_connection() as conn:
        conn.execute("UPDATE tournaments SET status='cancelled' WHERE tournament_id = ?", (tid,))
        conn.execute(
            """
            INSERT INTO tournament_entries
                (tournament_id, user_email, display_name, roster_json, stripe_payment_intent_id)
            VALUES (?, 'u@example.com', 'U', '[]', 'pi_123')
            """,
            (tid,),
        )
        conn.commit()

    result = process_cancelled_tournament_refunds(tid)
    assert result["success"] is True
    assert result["refunded"] == 1


def test_process_resolved_tournament_payouts(monkeypatch, tmp_path):
    _configure_temp_db(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "tournament.payout_runner.create_winner_payout_transfer",
        lambda connect_account_id, amount_usd, tournament_id: {"success": True, "transfer_id": "tr_123"},
    )

    tid = create_tournament(
        tournament_name="Pay Me",
        court_tier="Elite",
        entry_fee=50.0,
        min_entries=12,
        max_entries=24,
        lock_time="2026-04-20T20:00:00",
    )

    with tdb.get_tournament_connection() as conn:
        conn.execute("UPDATE tournaments SET status='resolved' WHERE tournament_id = ?", (tid,))
        conn.execute(
            """
            INSERT INTO user_career_stats
                (user_email, display_name, stripe_connect_account_id)
            VALUES ('u@example.com', 'U', 'acct_123')
            """
        )
        conn.execute(
            """
            INSERT INTO tournament_entries
                (tournament_id, user_email, display_name, roster_json, payout_amount, rank)
            VALUES (?, 'u@example.com', 'U', '[]', 250.0, 1)
            """,
            (tid,),
        )
        conn.commit()

    result = process_resolved_tournament_payouts(tid)
    assert result["success"] is True
    assert result["transferred"] == 1
