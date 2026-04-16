"""Standalone tournament CSV export helpers."""

from __future__ import annotations

import csv
import io
import json

from tournament.database import get_tournament_connection, initialize_tournament_database
from tournament.events import list_events


def export_tournament_entries_csv(tournament_id: int) -> str:
    """Export tournament entries as CSV string."""
    initialize_tournament_database()
    output = io.StringIO()
    writer = csv.writer(output)

    with get_tournament_connection() as conn:
        rows = conn.execute(
            """
            SELECT entry_id, tournament_id, user_email, display_name, total_score, rank,
                   lp_awarded, payout_amount, stripe_payment_intent_id, stripe_refund_id,
                   stripe_transfer_id, refund_status, payout_status, created_at
            FROM tournament_entries
            WHERE tournament_id = ?
            ORDER BY COALESCE(rank, 9999) ASC, total_score DESC
            """,
            (int(tournament_id),),
        ).fetchall()

        writer.writerow([
            "entry_id",
            "tournament_id",
            "user_email",
            "display_name",
            "total_score",
            "rank",
            "lp_awarded",
            "payout_amount",
            "stripe_payment_intent_id",
            "stripe_refund_id",
            "stripe_transfer_id",
            "refund_status",
            "payout_status",
            "created_at",
        ])

        for r in rows:
            row = dict(r)
            writer.writerow([
                row.get("entry_id"),
                row.get("tournament_id"),
                row.get("user_email"),
                row.get("display_name"),
                row.get("total_score"),
                row.get("rank"),
                row.get("lp_awarded"),
                row.get("payout_amount"),
                row.get("stripe_payment_intent_id"),
                row.get("stripe_refund_id"),
                row.get("stripe_transfer_id"),
                row.get("refund_status"),
                row.get("payout_status"),
                row.get("created_at"),
            ])

    return output.getvalue()


def export_tournament_scores_csv(tournament_id: int) -> str:
    """Export simulated player score lines for a tournament."""
    initialize_tournament_database()
    output = io.StringIO()
    writer = csv.writer(output)

    with get_tournament_connection() as conn:
        rows = conn.execute(
            """
            SELECT sim_id, tournament_id, player_id, player_name, line_json, fantasy_points,
                   bonuses_json, penalties_json, total_fp, created_at
            FROM simulated_scores
            WHERE tournament_id = ?
            ORDER BY total_fp DESC
            """,
            (int(tournament_id),),
        ).fetchall()

        writer.writerow([
            "sim_id",
            "tournament_id",
            "player_id",
            "player_name",
            "points",
            "rebounds",
            "assists",
            "steals",
            "blocks",
            "turnovers",
            "threes",
            "fantasy_points",
            "total_fp",
            "created_at",
        ])

        for r in rows:
            row = dict(r)
            line = {}
            try:
                line = json.loads(row.get("line_json") or "{}")
            except Exception:
                line = {}
            writer.writerow([
                row.get("sim_id"),
                row.get("tournament_id"),
                row.get("player_id"),
                row.get("player_name"),
                line.get("points", 0),
                line.get("rebounds", 0),
                line.get("assists", 0),
                line.get("steals", 0),
                line.get("blocks", 0),
                line.get("turnovers", 0),
                line.get("threes", 0),
                row.get("fantasy_points"),
                row.get("total_fp"),
                row.get("created_at"),
            ])

    return output.getvalue()


def export_tournament_events_csv(tournament_id: int | None = None, limit: int = 500) -> str:
    """Export event/audit rows as CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    events = list_events(tournament_id=tournament_id, limit=limit)

    writer.writerow([
        "event_id",
        "tournament_id",
        "entry_id",
        "user_email",
        "event_type",
        "severity",
        "message",
        "metadata_json",
        "created_at",
    ])

    for e in events:
        writer.writerow([
            e.get("event_id"),
            e.get("tournament_id"),
            e.get("entry_id"),
            e.get("user_email"),
            e.get("event_type"),
            e.get("severity"),
            e.get("message"),
            json.dumps(e.get("metadata", {})),
            e.get("created_at"),
        ])

    return output.getvalue()
