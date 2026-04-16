"""Integration tests for Phase 3B (Season LP Leaderboard / Season-end Rewards)
and Phase 3C (Championship Night Qualification)."""

from __future__ import annotations

import tournament.database as tdb
from tournament.manager import (
    create_tournament,
    distribute_season_end_rewards,
    list_season_lp_leaderboard,
    qualify_for_championship,
    submit_entry,
)


def _make_free_roster() -> list[dict]:
    """8-player free-tournament roster (no legend required)."""
    return [
        {"player_id": f"A{i}", "player_name": f"Player {i}", "salary": 5500, "is_legend": False}
        for i in range(8)
    ]


def _make_paid_roster() -> list[dict]:
    """9-player paid-tournament roster (8 active + 1 legend)."""
    active = [
        {"player_id": f"A{i}", "player_name": f"Player {i}", "salary": 5500, "is_legend": False}
        for i in range(8)
    ]
    return active + [{"player_id": "L001", "player_name": "MJ", "salary": 15000, "is_legend": True}]


def _force_resolve(tid: int, resolved_at: str = "2026-04-15 12:00:00") -> None:
    """Manually mark tournament resolved and assign ranks/LP to entries."""
    with tdb.get_tournament_connection() as conn:
        conn.execute(
            "UPDATE tournaments SET status='resolved', resolved_at=? WHERE tournament_id=?",
            (resolved_at, tid),
        )
        # Assign sequential ranks and LP to entries
        entries = conn.execute(
            "SELECT entry_id FROM tournament_entries WHERE tournament_id=? ORDER BY created_at ASC",
            (tid,),
        ).fetchall()
        lp_by_rank = {1: 15, 2: 10, 3: 7, 4: 5, 5: 3}
        for idx, row in enumerate(entries, start=1):
            eid = int(row["entry_id"])
            conn.execute(
                "UPDATE tournament_entries SET rank=?, lp_awarded=?, total_score=? WHERE entry_id=?",
                (idx, lp_by_rank.get(idx, 0), 100.0 - idx * 5, eid),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Phase 3B — Season LP leaderboard
# ---------------------------------------------------------------------------


def test_season_lp_leaderboard_monthly(isolated_db):
    """Resolved entries in a given month appear in the season LP leaderboard."""
    tid = create_tournament("Monthly LP Test", "Open", 0.0, 1, 50, "2026-04-30 23:59:00")
    roster = _make_free_roster()
    for email in ("alice@test.com", "bob@test.com", "carol@test.com"):
        submit_entry(tid, email, email.split("@")[0], roster)
    _force_resolve(tid, resolved_at="2026-04-15 12:00:00")

    board = list_season_lp_leaderboard(year=2026, month=4, limit=50)
    emails_in_board = {row["user_email"] for row in board}
    assert "alice@test.com" in emails_in_board or "bob@test.com" in emails_in_board
    # All entries have a non-negative season_lp
    for row in board:
        assert int(row["season_lp"]) >= 0
    # Ranks are sequential starting at 1
    for idx, row in enumerate(board, start=1):
        assert row["rank"] == idx


def test_season_lp_leaderboard_quarter_and_year(isolated_db):
    """Quarter and full-year scopes return entries from the appropriate window."""
    tid = create_tournament("Q2 LP Test", "Open", 0.0, 1, 50, "2026-05-31 12:00:00")
    roster = _make_free_roster()
    for email in ("dave@test.com", "eve@test.com"):
        submit_entry(tid, email, email.split("@")[0], roster)
    _force_resolve(tid, resolved_at="2026-05-15 12:00:00")

    # Q2 = April–June; May tournament should appear in Q2
    q2_board = list_season_lp_leaderboard(year=2026, quarter=2, limit=50)
    emails_q2 = {row["user_email"] for row in q2_board}
    assert "dave@test.com" in emails_q2 or "eve@test.com" in emails_q2

    # Full year listing should also include them
    year_board = list_season_lp_leaderboard(year=2026, limit=200)
    emails_year = {row["user_email"] for row in year_board}
    assert "dave@test.com" in emails_year or "eve@test.com" in emails_year


def test_season_lp_leaderboard_empty_for_future_month(isolated_db):
    """A month with no resolved tournaments returns an empty leaderboard."""
    board = list_season_lp_leaderboard(year=2099, month=1, limit=50)
    assert board == []


# ---------------------------------------------------------------------------
# Phase 3B — distribute_season_end_rewards
# ---------------------------------------------------------------------------


def test_distribute_season_end_rewards_awards_top_pct(isolated_db):
    """Top 10% of monthly LP earners receive bonus LP and season-reward badge."""
    tid = create_tournament("Season Rewards Test", "Open", 0.0, 1, 50, "2026-04-20 18:00:00")
    roster = _make_free_roster()
    participants = [f"player{i}@test.com" for i in range(10)]
    for email in participants:
        submit_entry(tid, email, email.split("@")[0], roster)
    _force_resolve(tid, resolved_at="2026-04-20 20:00:00")

    result = distribute_season_end_rewards(year=2026, month=4, top_pct=0.10, bonus_lp=150)
    assert result["season_key"] == "2026-04"
    assert result["awarded_count"] >= 1
    assert result["total_bonus_lp"] == result["awarded_count"] * 150
    for player in result["players"]:
        assert "@" in player["user_email"]
        assert player["bonus_lp"] == 150


def test_distribute_season_end_rewards_no_data(isolated_db):
    """Returns zero awards when no entries exist for the given month."""
    result = distribute_season_end_rewards(year=2099, month=6, top_pct=0.10, bonus_lp=100)
    assert result["awarded_count"] == 0
    assert result["total_bonus_lp"] == 0
    assert result["players"] == []


# ---------------------------------------------------------------------------
# Phase 3C — qualify_for_championship
# ---------------------------------------------------------------------------


def test_qualify_for_championship_creates_tournament_and_entries(isolated_db):
    """qualify_for_championship picks top LP earners and creates championship entries."""
    source_id = create_tournament("Qualifier Source", "Open", 0.0, 1, 50, "2026-04-25 20:00:00")
    roster = _make_free_roster()
    qualifiers = [f"qual{i}@test.com" for i in range(5)]
    for email in qualifiers:
        submit_entry(source_id, email, email.split("@")[0], roster)
    _force_resolve(source_id, resolved_at="2026-04-25 22:00:00")

    result = qualify_for_championship(
        "2026 April Championship",
        top_n=3,
        year=2026,
        month=4,
        lock_offset_hours=48,
        entry_fee=0.0,
        max_entries=16,
    )
    assert result["success"] is True
    assert result["season_label"] == "2026 April Championship"
    assert isinstance(result["tournament_id"], int)
    assert result["tournament_id"] > 0
    assert result["qualifiers"] >= 1
    assert len(result["entries"]) == result["qualifiers"]
    for entry in result["entries"]:
        assert "@" in entry["user_email"]
        assert entry["entry_id"] > 0


def test_qualify_for_championship_no_data_returns_error(isolated_db):
    """qualify_for_championship returns error dict when no LP data exists."""
    result = qualify_for_championship(
        "2099 Empty Championship",
        top_n=8,
        year=2099,
        month=1,
    )
    assert result["success"] is False
    assert "error" in result

