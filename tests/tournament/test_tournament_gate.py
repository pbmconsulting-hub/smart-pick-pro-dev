from tournament.gate import evaluate_tournament_access


def test_gate_blocks_restricted_state():
    result = evaluate_tournament_access(
        "Open",
        is_premium=False,
        has_legend_pass=False,
        user_age=30,
        state_code="WA",
    )
    assert result["allowed"] is False
    assert result["blocked"] is True


def test_gate_requires_premium_for_paid_tier():
    result = evaluate_tournament_access(
        "Elite",
        is_premium=False,
        has_legend_pass=False,
        user_age=30,
        state_code="TX",
    )
    assert result["allowed"] is False
    assert result["requires_premium"] is True


def test_gate_requires_legend_pass_for_championship():
    result = evaluate_tournament_access(
        "Championship",
        is_premium=True,
        has_legend_pass=False,
        user_age=30,
        state_code="TX",
    )
    assert result["allowed"] is False
    assert result["requires_legend_pass"] is True


def test_gate_allows_valid_paid_user():
    result = evaluate_tournament_access(
        "Elite",
        is_premium=True,
        has_legend_pass=False,
        user_age=30,
        state_code="TX",
    )
    assert result["allowed"] is True
