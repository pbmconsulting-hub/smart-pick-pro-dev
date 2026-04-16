"""Integration tests for tournament.gate — real access evaluation."""

from tournament.gate import evaluate_tournament_access, BLOCKED_STATES_DEFAULT, AGE_21_STATES


class TestEvaluateTournamentAccess:
    def test_open_court_free_user_allowed(self):
        result = evaluate_tournament_access(
            "Open", is_premium=False, has_legend_pass=False, user_age=25, state_code="CA"
        )
        assert result["allowed"] is True
        assert result["blocked"] is False

    def test_pro_court_requires_premium(self):
        result = evaluate_tournament_access(
            "Pro", is_premium=False, has_legend_pass=False, user_age=25, state_code="CA"
        )
        assert result["allowed"] is False
        assert result["requires_premium"] is True

    def test_pro_court_premium_allowed(self):
        result = evaluate_tournament_access(
            "Pro", is_premium=True, has_legend_pass=False, user_age=25, state_code="CA"
        )
        assert result["allowed"] is True

    def test_elite_premium_allowed(self):
        result = evaluate_tournament_access(
            "Elite", is_premium=True, has_legend_pass=False, user_age=25, state_code="CA"
        )
        assert result["allowed"] is True

    def test_championship_requires_legend_pass(self):
        result = evaluate_tournament_access(
            "Championship", is_premium=True, has_legend_pass=False, user_age=25, state_code="CA"
        )
        assert result["allowed"] is False
        assert result["requires_legend_pass"] is True

    def test_championship_with_legend_pass(self):
        result = evaluate_tournament_access(
            "Championship", is_premium=True, has_legend_pass=True, user_age=25, state_code="CA"
        )
        assert result["allowed"] is True


class TestGeoBlocking:
    def test_all_blocked_states(self):
        for state in BLOCKED_STATES_DEFAULT:
            result = evaluate_tournament_access(
                "Open", is_premium=False, has_legend_pass=False, user_age=25, state_code=state
            )
            assert result["allowed"] is False
            assert result["blocked"] is True

    def test_allowed_states(self):
        for state in ("CA", "TX", "NY", "FL", "IL"):
            result = evaluate_tournament_access(
                "Open", is_premium=False, has_legend_pass=False, user_age=25, state_code=state
            )
            assert result["blocked"] is False

    def test_case_insensitive_state(self):
        result = evaluate_tournament_access(
            "Open", is_premium=False, has_legend_pass=False, user_age=25, state_code="wa"
        )
        assert result["blocked"] is True


class TestAgeRequirement:
    def test_under_18_denied(self):
        result = evaluate_tournament_access(
            "Open", is_premium=False, has_legend_pass=False, user_age=16, state_code="CA"
        )
        assert result["allowed"] is False

    def test_exactly_18_allowed(self):
        result = evaluate_tournament_access(
            "Open", is_premium=False, has_legend_pass=False, user_age=18, state_code="CA"
        )
        assert result["allowed"] is True

    def test_age_21_states(self):
        for state in AGE_21_STATES:
            result = evaluate_tournament_access(
                "Open", is_premium=False, has_legend_pass=False, user_age=19, state_code=state
            )
            assert result["allowed"] is False
            assert result["min_age"] == 21

    def test_age_21_state_at_21(self):
        result = evaluate_tournament_access(
            "Open", is_premium=False, has_legend_pass=False, user_age=21, state_code="MA"
        )
        assert result["allowed"] is True


class TestResponseShape:
    def test_all_keys_present(self):
        result = evaluate_tournament_access(
            "Open", is_premium=False, has_legend_pass=False, user_age=25, state_code="CA"
        )
        assert set(result.keys()) == {
            "allowed", "reasons", "min_age", "blocked", "requires_premium", "requires_legend_pass"
        }
