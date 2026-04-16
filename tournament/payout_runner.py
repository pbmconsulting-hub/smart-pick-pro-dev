"""Standalone tournament payout/refund processing orchestrator."""

from __future__ import annotations

from tournament.database import get_tournament_connection, initialize_tournament_database
from tournament.events import log_event
from tournament.notifications import send_notification
from tournament.stripe import create_tournament_refund, create_winner_payout_transfer


def process_cancelled_tournament_refunds(tournament_id: int) -> dict:
    """Refund all paid entries in a cancelled tournament."""
    initialize_tournament_database()
    refunded = 0
    failed = 0
    deferred_events = []
    deferred_notifications = []

    with get_tournament_connection() as conn:
        tournament = conn.execute(
            "SELECT * FROM tournaments WHERE tournament_id = ?",
            (int(tournament_id),),
        ).fetchone()
        if not tournament:
            log_event(
                "refund.run_failed",
                f"Refund run failed: tournament #{tournament_id} not found",
                tournament_id=tournament_id,
                severity="error",
            )
            return {"success": False, "error": "Tournament not found", "refunded": 0, "failed": 0}
        if str(tournament["status"]) != "cancelled":
            log_event(
                "refund.run_failed",
                f"Refund run failed: tournament #{tournament_id} not cancelled",
                tournament_id=tournament_id,
                severity="warning",
            )
            return {"success": False, "error": "Tournament is not cancelled", "refunded": 0, "failed": 0}

        rows = conn.execute(
            """
            SELECT entry_id, stripe_payment_intent_id, refund_status
            FROM tournament_entries
            WHERE tournament_id = ?
            """,
            (int(tournament_id),),
        ).fetchall()

        for row in rows:
            if str(row["refund_status"] or "none") == "refunded":
                continue
            payment_intent_id = str(row["stripe_payment_intent_id"] or "").strip()
            if not payment_intent_id:
                conn.execute(
                    "UPDATE tournament_entries SET refund_status='not_applicable' WHERE entry_id = ?",
                    (int(row["entry_id"]),),
                )
                continue

            result = create_tournament_refund(payment_intent_id)
            if result.get("success"):
                refunded += 1
                conn.execute(
                    """
                    UPDATE tournament_entries
                    SET stripe_refund_id = ?, refund_status = 'refunded'
                    WHERE entry_id = ?
                    """,
                    (str(result.get("refund_id", "")), int(row["entry_id"])),
                )
                deferred_events.append(
                    {
                        "event_type": "refund.processed",
                        "message": f"Refund processed for entry #{row['entry_id']}",
                        "tournament_id": tournament_id,
                        "entry_id": int(row["entry_id"]),
                        "metadata": {"refund_id": str(result.get("refund_id", ""))},
                    }
                )
                deferred_notifications.append(
                    {
                        "notification_key": "refund_sent",
                        "message": f"Your entry for tournament #{tournament_id} was refunded",
                        "tournament_id": tournament_id,
                        "entry_id": int(row["entry_id"]),
                    }
                )
            else:
                failed += 1
                conn.execute(
                    "UPDATE tournament_entries SET refund_status='failed' WHERE entry_id = ?",
                    (int(row["entry_id"]),),
                )
                deferred_events.append(
                    {
                        "event_type": "refund.failed",
                        "message": f"Refund failed for entry #{row['entry_id']}",
                        "tournament_id": tournament_id,
                        "entry_id": int(row["entry_id"]),
                        "severity": "error",
                    }
                )

        conn.commit()

    for item in deferred_events:
        log_event(**item)
    for item in deferred_notifications:
        send_notification(**item)

    return {"success": True, "refunded": refunded, "failed": failed}


def process_resolved_tournament_payouts(tournament_id: int) -> dict:
    """Process payout transfers for resolved tournament winners."""
    initialize_tournament_database()
    transferred = 0
    failed = 0
    deferred_events = []
    deferred_notifications = []

    with get_tournament_connection() as conn:
        tournament = conn.execute(
            "SELECT * FROM tournaments WHERE tournament_id = ?",
            (int(tournament_id),),
        ).fetchone()
        if not tournament:
            log_event(
                "payout.run_failed",
                f"Payout run failed: tournament #{tournament_id} not found",
                tournament_id=tournament_id,
                severity="error",
            )
            return {"success": False, "error": "Tournament not found", "transferred": 0, "failed": 0}
        if str(tournament["status"]) != "resolved":
            log_event(
                "payout.run_failed",
                f"Payout run failed: tournament #{tournament_id} not resolved",
                tournament_id=tournament_id,
                severity="warning",
            )
            return {"success": False, "error": "Tournament is not resolved", "transferred": 0, "failed": 0}

        rows = conn.execute(
            """
            SELECT entry_id, user_email, payout_amount, payout_status
            FROM tournament_entries
            WHERE tournament_id = ?
            ORDER BY rank ASC
            """,
            (int(tournament_id),),
        ).fetchall()

        for row in rows:
            payout_amount = float(row["payout_amount"] or 0.0)
            if payout_amount <= 0:
                conn.execute(
                    "UPDATE tournament_entries SET payout_status='not_applicable' WHERE entry_id = ?",
                    (int(row["entry_id"]),),
                )
                continue

            if str(row["payout_status"] or "pending") == "paid":
                continue

            user = conn.execute(
                "SELECT stripe_connect_account_id FROM user_career_stats WHERE user_email = ?",
                (str(row["user_email"]),),
            ).fetchone()
            connect_id = str(user["stripe_connect_account_id"] or "") if user else ""
            if not connect_id:
                failed += 1
                conn.execute(
                    "UPDATE tournament_entries SET payout_status='failed_no_connect' WHERE entry_id = ?",
                    (int(row["entry_id"]),),
                )
                deferred_events.append(
                    {
                        "event_type": "payout.failed",
                        "message": f"Payout failed (no connect account) for entry #{row['entry_id']}",
                        "tournament_id": tournament_id,
                        "entry_id": int(row["entry_id"]),
                        "severity": "warning",
                    }
                )
                continue

            result = create_winner_payout_transfer(connect_id, payout_amount, int(tournament_id))
            if result.get("success"):
                transferred += 1
                conn.execute(
                    """
                    UPDATE tournament_entries
                    SET stripe_transfer_id = ?, payout_status = 'paid'
                    WHERE entry_id = ?
                    """,
                    (str(result.get("transfer_id", "")), int(row["entry_id"])),
                )
                deferred_events.append(
                    {
                        "event_type": "payout.sent",
                        "message": f"Payout sent for entry #{row['entry_id']}",
                        "tournament_id": tournament_id,
                        "entry_id": int(row["entry_id"]),
                        "user_email": str(row["user_email"]),
                        "metadata": {"transfer_id": str(result.get("transfer_id", "")), "amount": payout_amount},
                    }
                )
                deferred_notifications.append(
                    {
                        "notification_key": "payout_sent",
                        "message": f"Payout sent for tournament #{tournament_id}: ${payout_amount:.2f}",
                        "tournament_id": tournament_id,
                        "entry_id": int(row["entry_id"]),
                        "user_email": str(row["user_email"]),
                    }
                )
            else:
                failed += 1
                conn.execute(
                    "UPDATE tournament_entries SET payout_status='failed' WHERE entry_id = ?",
                    (int(row["entry_id"]),),
                )
                deferred_events.append(
                    {
                        "event_type": "payout.failed",
                        "message": f"Payout failed for entry #{row['entry_id']}",
                        "tournament_id": tournament_id,
                        "entry_id": int(row["entry_id"]),
                        "user_email": str(row["user_email"]),
                        "severity": "error",
                    }
                )

        conn.commit()

    for item in deferred_events:
        log_event(**item)
    for item in deferred_notifications:
        send_notification(**item)

    return {"success": True, "transferred": transferred, "failed": failed}
