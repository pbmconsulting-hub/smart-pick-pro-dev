"""Integration tests for profile analytics manager helpers."""

from __future__ import annotations

import json

import tournament.database as tdb
from tournament.manager import (
    get_user_best_rosters,
    get_user_head_to_head,
    get_user_progression_snapshot,
    list_user_entries,
)


def _seed_profile_analytics_data() -> None:
    with tdb.get_tournament_connection() as conn:
        conn.execute(
            """
            INSERT INTO tournaments
                (tournament_id, tournament_name, court_tier, status, entry_fee, max_entries, min_entries, lock_time, created_at, resolved_at)
            VALUES
                (301, 'Open Night A', 'Open', 'resolved', 5.0, 64, 8, '2099-01-01T20:00:00', '2099-01-01T20:00:00', '2099-01-01T23:00:00'),
                (302, 'Pro Night B', 'Pro', 'resolved', 20.0, 24, 8, '2099-01-02T20:00:00', '2099-01-02T20:00:00', '2099-01-02T23:00:00'),
                (303, 'Elite Night C', 'Elite', 'resolved', 50.0, 24, 8, '2099-01-03T20:00:00', '2099-01-03T20:00:00', '2099-01-03T23:00:00')
            """
        )

        rows = [
            (301, "alpha@test.com", "Alpha", 182.5, 1, 15, 120.0, ["A1", "A2", "A3"]),
            (301, "beta@test.com", "Beta", 170.1, 2, 10, 60.0, ["B1", "B2", "B3"]),
            (302, "alpha@test.com", "Alpha", 210.0, 2, 35, 150.0, ["A4", "A5", "A6"]),
            (302, "beta@test.com", "Beta", 215.4, 1, 50, 260.0, ["B4", "B5", "B6"]),
            (302, "gamma@test.com", "Gamma", 190.0, 3, 25, 80.0, ["G1", "G2", "G3"]),
            (303, "alpha@test.com", "Alpha", 240.8, 1, 100, 500.0, ["A7", "A8", "A9"]),
            (303, "gamma@test.com", "Gamma", 210.3, 2, 70, 260.0, ["G4", "G5", "G6"]),
        ]

        for idx, (tid, email, name, score, rank, lp, payout, players) in enumerate(rows, start=1):
            roster = [{"player_id": p, "player_name": p, "salary": 5000, "is_legend": False} for p in players]
            conn.execute(
                """
                INSERT INTO tournament_entries
                    (entry_id, tournament_id, user_email, display_name, roster_json, total_score, rank, lp_awarded, payout_amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (idx, tid, email, name, json.dumps(roster), score, rank, lp, payout),
            )

        conn.execute(
            """
            INSERT INTO user_career_stats
                (user_email, display_name, lifetime_entries, lifetime_wins, lifetime_top5, lifetime_earnings, lifetime_lp, career_level, updated_at)
            VALUES
                ('alpha@test.com', 'Alpha', 3, 2, 3, 770.0, 150, 6, datetime('now')),
                ('beta@test.com', 'Beta', 2, 1, 2, 320.0, 60, 4, datetime('now')),
                ('gamma@test.com', 'Gamma', 2, 0, 2, 340.0, 95, 4, datetime('now'))
            """
        )

        conn.commit()


def test_list_user_entries_includes_roster_payload(isolated_db):
    _seed_profile_analytics_data()

    entries = list_user_entries("alpha@test.com", limit=10)
    assert len(entries) == 3
    assert isinstance(entries[0].get("roster"), list)
    assert len(entries[0].get("roster")) >= 1


def test_head_to_head_analytics(isolated_db):
    _seed_profile_analytics_data()

    rows = get_user_head_to_head("alpha@test.com", limit=10)
    assert len(rows) >= 2

    opponents = {str(r.get("opponent_email")) for r in rows}
    assert "beta@test.com" in opponents
    assert "gamma@test.com" in opponents

    beta = next(r for r in rows if str(r.get("opponent_email")) == "beta@test.com")
    assert int(beta.get("matchups", 0) or 0) == 2


def test_best_rosters_and_progression(isolated_db):
    _seed_profile_analytics_data()

    best = get_user_best_rosters("alpha@test.com", limit=3)
    assert len(best["entries"]) == 3
    assert float(best["entries"][0]["score"]) >= float(best["entries"][1]["score"])
    assert float(best["average_score"]) > 0

    prog = get_user_progression_snapshot("alpha@test.com", limit=10)
    assert len(prog["series"]) == 3
    assert int(prog["series"][-1]["cumulative_lp"]) == 150
    assert isinstance(prog.get("skills"), dict)
    assert len(prog.get("skills")) >= 3
