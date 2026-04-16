"""Tournament payout scaling logic."""

from __future__ import annotations


def compute_scaled_payouts(
    entry_fee: float,
    entries: int,
    min_entries: int,
    max_entries: int,
    rake_percent: float,
    full_field_template: list[float],
) -> dict:
    """Scale payout amounts from full-field template based on current fill."""
    if entries < min_entries:
        return {
            "status": "cancelled",
            "entries": entries,
            "gross": round(entry_fee * entries, 2),
            "rake": 0.0,
            "prize_pool": 0.0,
            "payouts": [],
        }

    entries = min(entries, max_entries)
    gross = round(entry_fee * entries, 2)
    rake = round(gross * rake_percent, 2)
    prize_pool = round(gross - rake, 2)

    full_pool = max(0.01, entry_fee * max_entries * (1.0 - rake_percent))
    scale = prize_pool / full_pool

    payouts = [round(amount * scale, 2) for amount in full_field_template]

    # Keep accounting exact by correcting the final slot for rounding residue.
    residue = round(prize_pool - sum(payouts), 2)
    if payouts:
        payouts[-1] = round(payouts[-1] + residue, 2)

    return {
        "status": "ok",
        "entries": entries,
        "gross": gross,
        "rake": rake,
        "prize_pool": prize_pool,
        "payouts": payouts,
    }


def elite_court_payout(entries: int) -> dict:
    """Elite court payout profile from the tournament plan."""
    full_field = [400, 225, 140, 95, 60, 40]
    return compute_scaled_payouts(
        entry_fee=50.0,
        entries=entries,
        min_entries=12,
        max_entries=24,
        rake_percent=0.20,
        full_field_template=full_field,
    )


def championship_night_payout(entries: int) -> dict:
    """Championship Night payout profile with $500 first at full field."""
    full_field = [500, 325, 275, 220, 180, 150, 145, 125]
    return compute_scaled_payouts(
        entry_fee=75.0,
        entries=entries,
        min_entries=16,
        max_entries=32,
        rake_percent=0.20,
        full_field_template=full_field,
    )
