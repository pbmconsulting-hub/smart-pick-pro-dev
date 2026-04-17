"""LP (Leaderboard Points) engine for the tournament system.

Provides the canonical LP award table, tier multipliers, streak bonuses,
season aggregation helpers, and decay logic used by the tournament resolver
and the Record Books UI.

This module is stateless — all persistence is handled by ``tournament.manager``
and ``tournament.database``.  Functions here return pure values so they can be
unit-tested without a database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# ── Base LP table per court tier ──────────────────────────────────────
#
# Keyed by (court_tier, finishing_rank).  Ranks beyond the map receive the
# ``_PARTICIPATION_LP`` floor.

_BASE_LP: dict[str, dict[int, int]] = {
    "Open": {1: 15, 2: 10, 3: 7, 4: 5, 5: 3},
    "Pro": {1: 50, 2: 35, 3: 25, 4: 15, 5: 10},
    "Elite": {1: 100, 2: 70, 3: 50, 4: 35, 5: 25},
    "Championship": {1: 250, 2: 175, 3: 125, 4: 75, 5: 50},
}

_PARTICIPATION_LP = 1  # Minimum LP for finishing outside top-5

# ── Tier multipliers ──────────────────────────────────────────────────
#
# Premium subscribers and Legend Pass holders earn a multiplier on base LP.

_TIER_MULTIPLIERS: dict[str, float] = {
    "free": 1.0,
    "premium": 1.10,       # +10 %
    "legend_pass": 1.25,   # +25 % (stacks on premium)
}

# ── Streak bonus thresholds ───────────────────────────────────────────
#
# Consecutive wins (rank == 1) earn bonus LP on top of the base award.

_STREAK_BONUS: list[tuple[int, int]] = [
    (5, 50),   # 5-win streak → +50 LP
    (3, 20),   # 3-win streak → +20 LP
    (2, 5),    # 2-win streak → +5 LP
]

# ── Season decay ──────────────────────────────────────────────────────

_DECAY_RATE_PER_INACTIVE_WEEK = 0.02   # 2 % per inactive week
_MAX_DECAY_WEEKS = 4                    # Cap at 4 weeks (8 % max)


# =====================================================================
# Public API
# =====================================================================


def base_lp_for_rank(court_tier: str, rank: int) -> int:
    """Return the raw LP award for *court_tier* and finishing *rank*.

    Ranks outside the explicit table receive ``_PARTICIPATION_LP``.
    """
    tier = str(court_tier or "Open").strip()
    return int(_BASE_LP.get(tier, {}).get(max(1, int(rank)), _PARTICIPATION_LP))


def tier_multiplier(
    *,
    is_premium: bool = False,
    has_legend_pass: bool = False,
) -> float:
    """Return the combined LP multiplier for a user's subscription tier."""
    mult = _TIER_MULTIPLIERS["free"]
    if is_premium:
        mult = max(mult, _TIER_MULTIPLIERS["premium"])
    if has_legend_pass:
        mult = max(mult, _TIER_MULTIPLIERS["legend_pass"])
    return round(float(mult), 4)


def streak_bonus(win_streak: int) -> int:
    """Return the bonus LP for a given consecutive-win streak length."""
    streak = max(0, int(win_streak))
    for threshold, bonus in _STREAK_BONUS:
        if streak >= threshold:
            return int(bonus)
    return 0


def compute_lp_award(
    court_tier: str,
    rank: int,
    *,
    is_premium: bool = False,
    has_legend_pass: bool = False,
    win_streak: int = 0,
) -> dict:
    """Compute the full LP award for a single tournament placement.

    Returns a dict with ``base_lp``, ``multiplier``, ``streak_bonus``,
    and ``total_lp``.
    """
    base = base_lp_for_rank(court_tier, rank)
    mult = tier_multiplier(is_premium=is_premium, has_legend_pass=has_legend_pass)
    bonus = streak_bonus(win_streak) if int(rank) == 1 else 0
    total = int(round(base * mult)) + bonus
    return {
        "base_lp": base,
        "multiplier": mult,
        "streak_bonus": bonus,
        "total_lp": max(1, total),
    }


# ── Season helpers ────────────────────────────────────────────────────


def season_key(year: int, month: int) -> str:
    """Return the canonical ``YYYY-MM`` season key."""
    return f"{int(year)}-{int(month):02d}"


def season_date_range(
    year: int,
    month: int | None = None,
    quarter: int | None = None,
) -> tuple[str, str]:
    """Return ISO date strings ``(start, end)`` bounding a season window.

    * If *month* is given, the window is that calendar month.
    * If *quarter* is given, the window is 3 months starting from Q1=Jan.
    * Otherwise the full calendar year is returned.
    """
    y = int(year)
    if month is not None:
        m = max(1, min(12, int(month)))
        start = f"{y}-{m:02d}-01"
        end = f"{y + 1}-01-01" if m == 12 else f"{y}-{m + 1:02d}-01"
    elif quarter is not None:
        q = max(1, min(4, int(quarter)))
        sm = (q - 1) * 3 + 1
        em = sm + 3
        start = f"{y}-{sm:02d}-01"
        end = f"{y + 1}-01-01" if em > 12 else f"{y}-{em:02d}-01"
    else:
        start = f"{y}-01-01"
        end = f"{y + 1}-01-01"
    return start, end


# ── Decay ─────────────────────────────────────────────────────────────


def compute_decay(
    current_lp: int,
    inactive_weeks: int,
) -> dict:
    """Compute the LP to subtract after *inactive_weeks* of no activity.

    Returns ``decay_amount`` and ``new_lp`` (never below zero).
    """
    weeks = max(0, min(int(inactive_weeks), _MAX_DECAY_WEEKS))
    rate = round(weeks * _DECAY_RATE_PER_INACTIVE_WEEK, 4)
    decay_amount = int(round(int(current_lp) * rate))
    new_lp = max(0, int(current_lp) - decay_amount)
    return {
        "decay_rate": rate,
        "decay_amount": decay_amount,
        "new_lp": new_lp,
        "inactive_weeks": weeks,
    }


# ── Batch award helper ────────────────────────────────────────────────


def compute_tournament_lp_awards(
    court_tier: str,
    ranked_entries: list[dict],
) -> list[dict]:
    """Compute LP awards for all entries in a resolved tournament.

    *ranked_entries* must be sorted by rank (1 = first place).
    Each entry dict should contain at minimum ``user_email`` and ``rank``.
    Optional keys: ``is_premium``, ``has_legend_pass``, ``win_streak``.

    Returns a list of dicts with ``user_email``, ``rank``, and LP detail.
    """
    results: list[dict] = []
    for entry in ranked_entries:
        rank = int(entry.get("rank", 0) or 0)
        if rank < 1:
            continue
        award = compute_lp_award(
            court_tier,
            rank,
            is_premium=bool(entry.get("is_premium", False)),
            has_legend_pass=bool(entry.get("has_legend_pass", False)),
            win_streak=int(entry.get("win_streak", 0) or 0),
        )
        results.append({
            "user_email": str(entry.get("user_email", "")),
            "rank": rank,
            **award,
        })
    return results
