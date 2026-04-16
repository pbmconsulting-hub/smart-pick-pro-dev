"""Integration tests for resolve-time awards and live snapshot helpers."""

from __future__ import annotations

import tournament.database as tdb
import tournament.manager as manager
from tournament.manager import create_tournament, get_tournament_live_snapshot, resolve_tournament, submit_entry


def _make_roster(*, paid: bool) -> list[dict]:
    active = [
        {"player_id": f"A{i}", "player_name": f"Player {i}", "salary": 5500, "is_legend": False}
        for i in range(8)
    ]
    if not paid:
        return active
    return active + [{"player_id": "L001", "player_name": "MJ", "salary": 15000, "is_legend": True}]


def _seed_profiles(roster: list[dict]) -> None:
    profiles = []
    for player in roster:
        profiles.append(
            {
                "player_id": str(player.get("player_id", "")),
                "player_name": str(player.get("player_name", "")),
                "team": "TST",
                "position": "G",
                "overall_rating": 70,
                "archetype": "Versatile",
                "rarity_tier": "Bench",
                "salary": int(player.get("salary", 3000) or 3000),
                "is_legend": bool(player.get("is_legend", False)),
                "tech_rate": 0.0,
                "foul_prone": False,
            }
        )
    tdb.upsert_player_profiles(profiles)


def test_resolve_tournament_grants_badges_and_championship_history(isolated_db, monkeypatch):
    monkeypatch.setattr(
        manager,
        "simulate_player_full_line",
        lambda profile, env, seed: {
            "points": 24,
            "rebounds": 8,
            "assists": 7,
            "steals": 1,
            "blocks": 0,
            "turnovers": 2,
            "threes": 2,
        },
    )

    roster = _make_roster(paid=True)
    _seed_profiles(roster)

    tid = create_tournament("Champ Resolve Awards", "Championship", 20.0, 2, 24, "2099-06-01T20:00:00")
    ok1, _, _ = submit_entry(tid, "alpha@test.com", "Alpha", roster)
    ok2, _, _ = submit_entry(tid, "beta@test.com", "Beta", roster)
    assert ok1 is True
    assert ok2 is True

    result = resolve_tournament(tid)
    assert result["success"] is True
    assert result["status"] == "resolved"

    with tdb.get_tournament_connection() as conn:
        award_rows = conn.execute(
            """
            SELECT award_key
            FROM awards_log
            WHERE user_email = 'alpha@test.com'
              AND award_type = 'badge'
            """
        ).fetchall()
        history_rows = conn.execute(
            "SELECT tournament_id, winner_email FROM championship_history WHERE tournament_id = ?",
            (int(tid),),
        ).fetchall()

    keys = {str(row["award_key"]) for row in award_rows}
    assert "first_win" in keys
    assert "championship_winner" in keys
    assert len(history_rows) == 1
    assert str(history_rows[0]["winner_email"]) == "alpha@test.com"


def test_live_snapshot_returns_entries_and_top_players(isolated_db, monkeypatch):
    monkeypatch.setattr(
        manager,
        "simulate_player_full_line",
        lambda profile, env, seed: {
            "points": 18,
            "rebounds": 7,
            "assists": 5,
            "steals": 1,
            "blocks": 1,
            "turnovers": 1,
            "threes": 1,
        },
    )

    roster = _make_roster(paid=False)
    _seed_profiles(roster)

    tid = create_tournament("Open Snapshot", "Open", 0.0, 1, 64, "2099-06-01T20:00:00")
    ok, _, _ = submit_entry(tid, "alpha@test.com", "Alpha", roster)
    assert ok is True

    result = resolve_tournament(tid)
    assert result["success"] is True

    snapshot = get_tournament_live_snapshot(tid, user_email="alpha@test.com", top_n=10)
    assert snapshot["success"] is True
    assert int(snapshot["entry_count"]) == 1
    assert len(snapshot["leaderboard"]) == 1
    assert len(snapshot["my_entries"]) == 1
    assert len(snapshot["top_players"]) >= 1
