"""Integration tests for tournament.database — real SQLite operations."""

import json
import sqlite3

import tournament.database as tdb


class TestInitializeDatabase:
    def test_creates_db_file(self, isolated_db):
        assert (isolated_db / "tournament.db").exists()

    def test_idempotent(self, isolated_db):
        assert tdb.initialize_tournament_database()
        assert tdb.initialize_tournament_database()

    def test_all_tables_exist(self, isolated_db):
        with tdb.get_tournament_connection() as conn:
            tables = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        expected = {
            "tournaments",
            "tournament_entries",
            "player_profiles",
            "simulated_scores",
            "user_career_stats",
            "championship_history",
            "awards_log",
            "tournament_events",
        }
        assert expected.issubset(tables)


class TestGetTournamentConnection:
    def test_returns_connection(self, isolated_db):
        conn = tdb.get_tournament_connection()
        assert isinstance(conn, sqlite3.Connection)
        conn.close()

    def test_row_factory_is_row(self, isolated_db):
        conn = tdb.get_tournament_connection()
        assert conn.row_factory is sqlite3.Row
        conn.close()


class TestUpsertPlayerProfiles:
    def test_insert_profiles(self, isolated_db):
        profiles = [
            {
                "player_id": "P001",
                "player_name": "Test Player",
                "team": "TST",
                "position": "PG",
                "overall_rating": 88,
                "archetype": "Elite Scorer",
                "rarity_tier": "Star",
                "salary": 9000,
            },
        ]
        count = tdb.upsert_player_profiles(profiles)
        assert count == 1

        with tdb.get_tournament_connection() as conn:
            row = conn.execute(
                "SELECT * FROM player_profiles WHERE player_id = 'P001'"
            ).fetchone()
        assert row is not None
        assert row["player_name"] == "Test Player"
        assert row["overall_rating"] == 88

    def test_upsert_updates_existing(self, isolated_db):
        p = {
            "player_id": "P002",
            "player_name": "V1",
            "team": "A",
            "position": "C",
            "overall_rating": 70,
            "archetype": "Versatile",
            "rarity_tier": "Starter",
            "salary": 5000,
        }
        tdb.upsert_player_profiles([p])
        p["player_name"] = "V2"
        p["overall_rating"] = 85
        tdb.upsert_player_profiles([p])

        with tdb.get_tournament_connection() as conn:
            row = conn.execute(
                "SELECT * FROM player_profiles WHERE player_id = 'P002'"
            ).fetchone()
        assert row["player_name"] == "V2"
        assert row["overall_rating"] == 85

    def test_empty_list_returns_zero(self, isolated_db):
        assert tdb.upsert_player_profiles([]) == 0

    def test_profile_json_stored(self, isolated_db):
        p = {
            "player_id": "P003",
            "player_name": "JSON Check",
            "team": "T",
            "position": "SG",
            "overall_rating": 60,
            "archetype": "Versatile",
            "rarity_tier": "Bench",
            "salary": 3000,
            "custom_field": "hello",
        }
        tdb.upsert_player_profiles([p])
        with tdb.get_tournament_connection() as conn:
            row = conn.execute(
                "SELECT profile_json FROM player_profiles WHERE player_id = 'P003'"
            ).fetchone()
        parsed = json.loads(row["profile_json"])
        assert parsed["custom_field"] == "hello"
