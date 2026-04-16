"""Integration tests for tournament.payout — real math."""

from tournament.payout import (
    championship_night_payout,
    compute_scaled_payouts,
    elite_court_payout,
)


class TestComputeScaledPayouts:
    def test_cancelled_below_min(self):
        result = compute_scaled_payouts(
            entry_fee=50.0, entries=5, min_entries=12, max_entries=24,
            rake_percent=0.20, full_field_template=[400, 225, 140]
        )
        assert result["status"] == "cancelled"
        assert result["prize_pool"] == 0.0
        assert result["payouts"] == []

    def test_ok_at_min_entries(self):
        result = compute_scaled_payouts(
            entry_fee=50.0, entries=12, min_entries=12, max_entries=24,
            rake_percent=0.20, full_field_template=[400, 225, 140, 95, 60, 40]
        )
        assert result["status"] == "ok"
        assert result["entries"] == 12
        assert result["prize_pool"] > 0

    def test_gross_equals_fee_times_entries(self):
        result = compute_scaled_payouts(
            entry_fee=20.0, entries=15, min_entries=10, max_entries=24,
            rake_percent=0.20, full_field_template=[200, 120, 80, 40]
        )
        assert result["gross"] == 20.0 * 15

    def test_rake_percent_applied(self):
        result = compute_scaled_payouts(
            entry_fee=100.0, entries=20, min_entries=10, max_entries=20,
            rake_percent=0.15, full_field_template=[500, 300, 200]
        )
        assert result["rake"] == round(100.0 * 20 * 0.15, 2)

    def test_payouts_sum_to_prize_pool(self):
        result = compute_scaled_payouts(
            entry_fee=50.0, entries=24, min_entries=12, max_entries=24,
            rake_percent=0.20, full_field_template=[400, 225, 140, 95, 60, 40]
        )
        assert result["status"] == "ok"
        assert round(sum(result["payouts"]), 2) == result["prize_pool"]

    def test_first_place_gets_most(self):
        result = compute_scaled_payouts(
            entry_fee=50.0, entries=24, min_entries=12, max_entries=24,
            rake_percent=0.20, full_field_template=[400, 225, 140, 95, 60, 40]
        )
        payouts = result["payouts"]
        assert payouts[0] > payouts[1]

    def test_entries_capped_at_max(self):
        result = compute_scaled_payouts(
            entry_fee=10.0, entries=100, min_entries=5, max_entries=20,
            rake_percent=0.10, full_field_template=[100, 50]
        )
        assert result["entries"] == 20


class TestEliteCourtPayout:
    def test_full_field(self):
        result = elite_court_payout(24)
        assert result["status"] == "ok"
        assert len(result["payouts"]) == 6
        assert round(sum(result["payouts"]), 2) == result["prize_pool"]

    def test_below_min_cancels(self):
        result = elite_court_payout(5)
        assert result["status"] == "cancelled"


class TestChampionshipNightPayout:
    def test_full_field(self):
        result = championship_night_payout(32)
        assert result["status"] == "ok"
        assert len(result["payouts"]) == 8
        assert round(sum(result["payouts"]), 2) == result["prize_pool"]

    def test_below_min_cancels(self):
        result = championship_night_payout(10)
        assert result["status"] == "cancelled"

    def test_half_field(self):
        result = championship_night_payout(16)
        assert result["status"] == "ok"
        assert result["prize_pool"] > 0
