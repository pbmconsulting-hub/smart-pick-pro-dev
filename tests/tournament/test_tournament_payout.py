from tournament.payout import championship_night_payout, compute_scaled_payouts


def test_compute_scaled_payouts_cancel_below_min():
    result = compute_scaled_payouts(
        entry_fee=75.0,
        entries=12,
        min_entries=16,
        max_entries=32,
        rake_percent=0.20,
        full_field_template=[500, 325, 275, 220],
    )
    assert result["status"] == "cancelled"
    assert result["prize_pool"] == 0.0


def test_championship_night_hits_500_at_full_field():
    result = championship_night_payout(entries=32)
    assert result["status"] == "ok"
    assert result["payouts"][0] == 500.0
    assert result["prize_pool"] == 1920.0


def test_scaled_partial_field_half_fill_halves_first_prize():
    result = championship_night_payout(entries=16)
    assert result["status"] == "ok"
    assert result["payouts"][0] == 250.0
    assert result["prize_pool"] == 960.0
