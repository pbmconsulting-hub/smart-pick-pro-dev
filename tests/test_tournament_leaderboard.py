"""Tests for engine/tournament_leaderboard.py — LP engine."""

from __future__ import annotations

import pytest

from engine.tournament_leaderboard import (
    base_lp_for_rank,
    compute_decay,
    compute_lp_award,
    compute_tournament_lp_awards,
    season_date_range,
    season_key,
    streak_bonus,
    tier_multiplier,
)


# ── base_lp_for_rank ─────────────────────────────────────────────────


class TestBaseLpForRank:
    def test_open_first(self):
        assert base_lp_for_rank("Open", 1) == 15

    def test_pro_first(self):
        assert base_lp_for_rank("Pro", 1) == 50

    def test_elite_first(self):
        assert base_lp_for_rank("Elite", 1) == 100

    def test_championship_first(self):
        assert base_lp_for_rank("Championship", 1) == 250

    def test_open_fifth(self):
        assert base_lp_for_rank("Open", 5) == 3

    def test_outside_top5_gets_participation(self):
        assert base_lp_for_rank("Open", 6) == 1

    def test_unknown_tier_gets_participation(self):
        assert base_lp_for_rank("Casual", 1) == 1

    def test_rank_zero_treated_as_one(self):
        # Rank 0 floors to 1 via max(1, ...)
        assert base_lp_for_rank("Open", 0) == 15


# ── tier_multiplier ───────────────────────────────────────────────────


class TestTierMultiplier:
    def test_free(self):
        assert tier_multiplier() == 1.0

    def test_premium(self):
        assert tier_multiplier(is_premium=True) == 1.10

    def test_legend_pass(self):
        assert tier_multiplier(has_legend_pass=True) == 1.25

    def test_both(self):
        assert tier_multiplier(is_premium=True, has_legend_pass=True) == 1.25


# ── streak_bonus ──────────────────────────────────────────────────────


class TestStreakBonus:
    def test_zero(self):
        assert streak_bonus(0) == 0

    def test_one(self):
        assert streak_bonus(1) == 0

    def test_two(self):
        assert streak_bonus(2) == 5

    def test_three(self):
        assert streak_bonus(3) == 20

    def test_five(self):
        assert streak_bonus(5) == 50

    def test_ten(self):
        assert streak_bonus(10) == 50


# ── compute_lp_award ─────────────────────────────────────────────────


class TestComputeLpAward:
    def test_basic_first_place(self):
        result = compute_lp_award("Elite", 1)
        assert result["base_lp"] == 100
        assert result["multiplier"] == 1.0
        assert result["streak_bonus"] == 0
        assert result["total_lp"] == 100

    def test_premium_first_place(self):
        result = compute_lp_award("Elite", 1, is_premium=True)
        assert result["multiplier"] == 1.10
        assert result["total_lp"] == 110  # 100 * 1.10

    def test_legend_pass_with_streak(self):
        result = compute_lp_award("Elite", 1, has_legend_pass=True, win_streak=3)
        # base=100, mult=1.25 → 125, streak bonus +20 → 145
        assert result["total_lp"] == 145

    def test_streak_only_for_first_place(self):
        result = compute_lp_award("Elite", 2, win_streak=5)
        assert result["streak_bonus"] == 0  # Not rank 1

    def test_minimum_one_lp(self):
        result = compute_lp_award("Open", 99)
        assert result["total_lp"] >= 1


# ── season_key & season_date_range ────────────────────────────────────


class TestSeasonHelpers:
    def test_season_key(self):
        assert season_key(2026, 4) == "2026-04"
        assert season_key(2026, 12) == "2026-12"

    def test_month_range(self):
        start, end = season_date_range(2026, month=3)
        assert start == "2026-03-01"
        assert end == "2026-04-01"

    def test_december_range(self):
        start, end = season_date_range(2026, month=12)
        assert start == "2026-12-01"
        assert end == "2027-01-01"

    def test_quarter_range(self):
        start, end = season_date_range(2026, quarter=1)
        assert start == "2026-01-01"
        assert end == "2026-04-01"

    def test_q4_range(self):
        start, end = season_date_range(2026, quarter=4)
        assert start == "2026-10-01"
        assert end == "2027-01-01"

    def test_full_year(self):
        start, end = season_date_range(2026)
        assert start == "2026-01-01"
        assert end == "2027-01-01"


# ── compute_decay ─────────────────────────────────────────────────────


class TestComputeDecay:
    def test_zero_weeks(self):
        result = compute_decay(1000, 0)
        assert result["decay_amount"] == 0
        assert result["new_lp"] == 1000

    def test_one_week(self):
        result = compute_decay(1000, 1)
        assert result["decay_rate"] == 0.02
        assert result["decay_amount"] == 20
        assert result["new_lp"] == 980

    def test_four_weeks_cap(self):
        result = compute_decay(1000, 4)
        assert result["decay_amount"] == 80
        assert result["new_lp"] == 920

    def test_beyond_cap(self):
        result = compute_decay(1000, 10)
        # Caps at 4 weeks
        assert result["inactive_weeks"] == 4
        assert result["decay_amount"] == 80

    def test_never_negative(self):
        result = compute_decay(5, 4)
        assert result["new_lp"] >= 0


# ── compute_tournament_lp_awards ──────────────────────────────────────


class TestComputeTournamentLpAwards:
    def test_basic_awards(self):
        entries = [
            {"user_email": "a@test.com", "rank": 1},
            {"user_email": "b@test.com", "rank": 2},
            {"user_email": "c@test.com", "rank": 3},
        ]
        results = compute_tournament_lp_awards("Pro", entries)
        assert len(results) == 3
        assert results[0]["total_lp"] == 50
        assert results[1]["total_lp"] == 35
        assert results[2]["total_lp"] == 25

    def test_premium_bonus(self):
        entries = [
            {"user_email": "a@test.com", "rank": 1, "is_premium": True},
        ]
        results = compute_tournament_lp_awards("Pro", entries)
        assert results[0]["total_lp"] == 55  # 50 * 1.10

    def test_skip_invalid_rank(self):
        entries = [
            {"user_email": "a@test.com", "rank": 0},
        ]
        results = compute_tournament_lp_awards("Pro", entries)
        assert len(results) == 0
