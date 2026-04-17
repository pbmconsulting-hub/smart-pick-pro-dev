"""Unit tests for tournament sports router and adapters."""

from __future__ import annotations

import pytest

from tournament.sports import mlb, nfl
from tournament.sports.router import get_sport_handler, list_supported_sports, normalize_sport_code


def test_normalize_sport_code_defaults_unknown_to_nba():
    assert normalize_sport_code("soccer") == "nba"
    assert normalize_sport_code("") == "nba"


def test_get_sport_handler_returns_expected_modules():
    assert get_sport_handler("mlb") is mlb
    assert get_sport_handler("NFL") is nfl


def test_list_supported_sports_exposes_router_catalog():
    supported = {item["sport"]: item["label"] for item in list_supported_sports()}
    assert supported == {"mlb": "MLB", "nba": "NBA", "nfl": "NFL"}


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (
            {"hits": 2, "runs": 1, "rbi": 3, "home_runs": 1, "stolen_bases": 1},
            23.0,
        ),
        (
            {"pass_yards": 250, "pass_tds": 2, "rush_yards": 40, "rush_tds": 1, "receptions": 0, "rec_yards": 0, "rec_tds": 0, "turnovers": 1},
            26.0,
        ),
    ],
)
def test_non_nba_adapters_score_expected_totals(line: dict, expected: float):
    handler = mlb if "hits" in line else nfl
    assert handler.score_line(line) == expected
