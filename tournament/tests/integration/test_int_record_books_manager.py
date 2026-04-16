"""Integration tests for record-book manager helpers."""

from __future__ import annotations

import json

import tournament.database as tdb
from tournament.manager import (
    get_all_time_records,
    get_championship_overview,
    get_season_awards_snapshot,
    list_badge_leaders,
    list_championship_history,
    list_hall_of_fame_candidates,
)


def _seed_records() -> None:
    with tdb.get_tournament_connection() as conn:
        conn.execute(
            """
            INSERT INTO tournaments
                (tournament_id, tournament_name, court_tier, status, entry_fee, max_entries, min_entries, lock_time, created_at)
            VALUES
                (101, 'Champ A', 'Championship', 'resolved', 50.0, 32, 8, '2099-01-01T00:00:00', '2099-01-01T00:00:00'),
                (102, 'Champ B', 'Championship', 'open', 75.0, 32, 8, '2099-02-01T00:00:00', '2099-02-01T00:00:00'),
                (201, 'Open C', 'Open', 'resolved', 5.0, 64, 8, '2099-01-10T00:00:00', '2099-01-10T00:00:00'),
                (202, 'Open D', 'Open', 'resolved', 5.0, 64, 8, '2099-01-11T00:00:00', '2099-01-11T00:00:00'),
                (203, 'Open E', 'Open', 'resolved', 5.0, 64, 8, '2099-01-12T00:00:00', '2099-01-12T00:00:00'),
                (204, 'Open F', 'Open', 'resolved', 5.0, 64, 8, '2099-01-13T00:00:00', '2099-01-13T00:00:00')
            """
        )

        conn.execute(
            """
            INSERT INTO championship_history
                (season_label, tournament_id, winner_email, winner_display_name, winning_score, payout_amount, roster_json, created_at)
            VALUES
                ('2026 S1', 101, 'alpha@test.com', 'Alpha', 301.2, 25000.0, ?, '2099-01-03T00:00:00'),
                ('2025 S4', 101, 'alpha@test.com', 'Alpha', 290.0, 20000.0, ?, '2098-10-03T00:00:00'),
                ('2025 S3', 101, 'alpha@test.com', 'Alpha', 285.5, 18000.0, ?, '2098-07-03T00:00:00'),
                ('2025 S2', 101, 'alpha@test.com', 'Alpha', 275.0, 15000.0, ?, '2098-04-03T00:00:00'),
                ('2025 S1', 101, 'alpha@test.com', 'Alpha', 270.0, 12000.0, ?, '2098-01-03T00:00:00')
            """,
            (json.dumps([{"player_id": "A1"}]),
             json.dumps([{"player_id": "A1"}]),
             json.dumps([{"player_id": "A1"}]),
             json.dumps([{"player_id": "A1"}]),
             json.dumps([{"player_id": "A1"}])),
        )

        entries = [
            (101, "alpha@test.com", "Alpha", 301.2, 1, 120, 25000.0, 50.0),
            (101, "beta@test.com", "Beta", 280.0, 2, 90, 10000.0, 50.0),
            (102, "alpha@test.com", "Alpha", 240.0, None, 0, 0.0, 75.0),
            (201, "alpha@test.com", "Alpha", 260.0, 1, 55, 450.0, 5.0),
            (202, "alpha@test.com", "Alpha", 250.0, 2, 45, 90.0, 5.0),
            (201, "beta@test.com", "Beta", 210.0, 4, 20, 20.0, 5.0),
            (203, "gamma@test.com", "Gamma", 180.0, 6, 10, 0.0, 5.0),
            (204, "beta@test.com", "Beta", 200.0, None, 0, 0.0, 5.0),
        ]
        for idx, (tid, email, name, score, rank, lp, payout, fee) in enumerate(entries, start=1):
            conn.execute(
                """
                INSERT INTO tournament_entries
                    (entry_id, tournament_id, user_email, display_name, roster_json, total_score, rank, lp_awarded, payout_amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (idx, tid, email, name, json.dumps([{"player_id": f"P{idx}"}]), score, rank, lp, payout),
            )

        conn.execute(
            """
            INSERT INTO user_career_stats
                (user_email, display_name, lifetime_entries, lifetime_wins, lifetime_top5, lifetime_earnings, lifetime_lp, career_level, updated_at)
            VALUES
                ('alpha@test.com', 'Alpha', 140, 62, 88, 25540.0, 2900, 18, datetime('now')),
                ('beta@test.com', 'Beta', 110, 24, 55, 10020.0, 1800, 12, datetime('now')),
                ('gamma@test.com', 'Gamma', 8, 1, 2, 40.0, 120, 3, datetime('now'))
            """
        )

        badge_rows = [
            ("alpha@test.com", "badge", "first_win", "First Win"),
            ("alpha@test.com", "badge", "hot_streak", "Hot Streak"),
            ("alpha@test.com", "badge", "money_maker", "Money Maker"),
            ("beta@test.com", "badge", "first_win", "First Win"),
        ]
        for user_email, award_type, award_key, award_name in badge_rows:
            conn.execute(
                """
                INSERT INTO awards_log
                    (user_email, award_type, award_key, award_name, context_json, granted_at)
                VALUES (?, ?, ?, ?, '{}', datetime('now'))
                """,
                (user_email, award_type, award_key, award_name),
            )

        conn.commit()


def test_championship_history_and_overview(isolated_db):
    _seed_records()

    history = list_championship_history(limit=10)
    assert len(history) == 1
    assert history[0]["winner_display_name"] == "Alpha"

    overview = get_championship_overview()
    assert overview["total_championships"] == 2
    assert overview["resolved_championships"] == 1
    assert overview["active_entries"] == 1


def test_awards_records_badges_and_hof(isolated_db):
    _seed_records()

    awards = get_season_awards_snapshot()
    assert awards["mvp"]["winner"] == "Alpha"
    assert awards["money_maker"]["winner"] == "Alpha"

    records = get_all_time_records()
    assert records["scoring"][0]["holder"] == "Alpha"
    assert any(item["name"] == "Best ROI" for item in records["gameplay"])

    badges = list_badge_leaders(limit=10)
    assert len(badges) >= 2
    assert badges[0]["display_name"] == "Alpha"
    assert badges[0]["badge_count"] == 3

    hof = list_hall_of_fame_candidates(limit=10)
    assert len(hof) == 1
    assert hof[0]["display_name"] == "Alpha"
