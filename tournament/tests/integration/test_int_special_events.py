"""Integration tests for tournament.special_events."""

from tournament.special_events import (
    apply_scoring_multiplier,
    generate_rivalry_bracket,
    get_special_event_config,
    resolve_rivalry_round,
    score_special_event_entry,
    validate_special_event_roster,
)


def test_holiday_showcase_multiplier_config(isolated_db):
    cfg = get_special_event_config("holiday_showcase")
    assert cfg["scoring_multiplier"] == 1.25
    assert apply_scoring_multiplier(100.0, "holiday_showcase") == 125.0


def test_chaos_night_allows_positionless_roster(isolated_db):
    roster = [
        {"player_id": "1", "salary": 7000},
        {"player_id": "2", "salary": 7000},
        {"player_id": "3", "salary": 7000},
        {"player_id": "4", "salary": 7000},
        {"player_id": "5", "salary": 7000},
    ]
    out = validate_special_event_roster(roster, "chaos_night", field_size=24)
    assert out["valid"] is True


def test_rivalry_bracket_generate_and_resolve(isolated_db):
    entries = [{"entry_id": i} for i in range(1, 7)]
    bracket = generate_rivalry_bracket(entries, seed=42)
    assert len(bracket) == 4  # next power of two for 6 is 8 => 4 matches

    results = {1: 120.0, 2: 118.0, 3: 101.0, 4: 99.0, 5: 111.0, 6: 105.0}
    next_round = resolve_rivalry_round(bracket, results)
    assert len(next_round) >= 1
    assert int(next_round[0]["round"]) == 2


def test_score_special_event_entry_holiday_adjusts_total(isolated_db):
    profile = {"tech_rate": 0.0, "foul_prone": False}
    line = {
        "player_id": "p1",
        "points": 20,
        "rebounds": 5,
        "assists": 6,
        "steals": 2,
        "blocks": 1,
        "turnovers": 2,
        "threes": 3,
    }
    scored = score_special_event_entry(profile, line, seed=7, event_type="holiday_showcase")
    assert scored["event_type"] == "holiday_showcase"
    assert float(scored["adjusted_total_fp"]) >= float(scored["total_fp"])

