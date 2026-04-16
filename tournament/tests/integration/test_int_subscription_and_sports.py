"""Integration tests for subscription enforcement and sport router scaffolding."""

from __future__ import annotations

import tournament.database as tdb
import tournament.manager as manager
from tournament.manager import (
    create_tournament,
    evaluate_user_tournament_access,
    get_supported_tournament_sports,
    get_tournament,
    get_user_subscription_status,
    resolve_tournament,
    submit_entry,
    upsert_user_subscription_status,
)


def _make_open_roster() -> list[dict]:
    return [
        {"player_id": f"P{i}", "player_name": f"Player {i}", "salary": 5000, "is_legend": False}
        for i in range(8)
    ]


def _seed_profiles(roster: list[dict]) -> None:
    profiles = []
    for p in roster:
        profiles.append(
            {
                "player_id": str(p.get("player_id")),
                "player_name": str(p.get("player_name")),
                "team": "TST",
                "position": "UTIL",
                "overall_rating": 60,
                "archetype": "Versatile",
                "rarity_tier": "Bench",
                "salary": int(p.get("salary", 5000)),
                "is_legend": False,
            }
        )
    tdb.upsert_player_profiles(profiles)


def test_subscription_status_roundtrip_and_access_enforcement(isolated_db):
    put = upsert_user_subscription_status(
        "sub-user@test.com",
        premium_active=False,
        legend_pass_active=False,
        source="test",
    )
    assert put["success"] is True

    status = get_user_subscription_status("sub-user@test.com")
    assert status["premium_active"] is False

    denied = evaluate_user_tournament_access(
        user_email="sub-user@test.com",
        court_tier="Pro",
        user_age=25,
        state_code="CA",
    )
    assert denied["allowed"] is False
    assert any("Premium" in reason for reason in denied["reasons"])

    upsert_user_subscription_status(
        "sub-user@test.com",
        premium_active=True,
        legend_pass_active=False,
        source="test",
    )
    allowed = evaluate_user_tournament_access(
        user_email="sub-user@test.com",
        court_tier="Pro",
        user_age=25,
        state_code="CA",
    )
    assert allowed["allowed"] is True


def test_supported_sports_and_sport_persistence(isolated_db):
    supported = get_supported_tournament_sports()
    codes = {str(item.get("sport")) for item in supported}
    assert {"nba", "mlb", "nfl"}.issubset(codes)

    tid = create_tournament(
        "MLB Test",
        "Open",
        0.0,
        1,
        64,
        "2099-06-01T20:00:00",
        sport="mlb",
    )
    row = get_tournament(tid)
    assert row is not None
    assert str(row.get("sport", "")) == "mlb"


def test_non_nba_sport_resolution_uses_router_scoring(isolated_db, monkeypatch):
    monkeypatch.setattr(
        manager,
        "simulate_player_full_line",
        lambda profile, env, seed: {
            "hits": 2,
            "runs": 1,
            "rbi": 1,
            "home_runs": 0,
            "stolen_bases": 0,
        },
    )

    roster = _make_open_roster()
    _seed_profiles(roster)

    tid = create_tournament(
        "MLB Resolve",
        "Open",
        0.0,
        1,
        64,
        "2099-06-01T20:00:00",
        sport="mlb",
    )
    ok, _, _ = submit_entry(tid, "mlb@test.com", "MLB User", roster)
    assert ok is True

    result = resolve_tournament(tid)
    assert result["success"] is True
    assert str(result.get("sport", "")) == "mlb"
