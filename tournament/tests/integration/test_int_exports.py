"""Integration tests for tournament.exports — real CSV generation."""

import csv
import io

import tournament.database as tdb
from tournament.events import log_event
from tournament.exports import (
    export_tournament_entries_csv,
    export_tournament_events_csv,
    export_tournament_scores_csv,
)
from tournament.manager import create_tournament, submit_entry


def _make_roster():
    active = [
        {"player_id": f"A{i}", "player_name": f"Player {i}", "salary": 5500, "is_legend": False}
        for i in range(8)
    ]
    legend = {"player_id": "L001", "player_name": "MJ", "salary": 15000, "is_legend": True}
    return active + [legend]


class TestExportTournamentEntriesCSV:
    def test_header_row(self, isolated_db):
        tid = create_tournament("CSV", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        csv_str = export_tournament_entries_csv(tid)
        reader = csv.reader(io.StringIO(csv_str))
        header = next(reader)
        assert "entry_id" in header
        assert "user_email" in header
        assert "total_score" in header

    def test_includes_entries(self, isolated_db):
        tid = create_tournament("CSV2", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        submit_entry(tid, "a@t.com", "A", _make_roster())
        submit_entry(tid, "b@t.com", "B", _make_roster())
        csv_str = export_tournament_entries_csv(tid)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 3  # header + 2 entries

    def test_empty_tournament(self, isolated_db):
        tid = create_tournament("Empty", "Open", 0, 8, 64, "2099-01-01T20:00:00")
        csv_str = export_tournament_entries_csv(tid)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 1  # header only


class TestExportTournamentScoresCSV:
    def test_header_present(self, isolated_db):
        tid = create_tournament("Scores", "Open", 0, 8, 64, "2099-01-01T20:00:00")
        csv_str = export_tournament_scores_csv(tid)
        reader = csv.reader(io.StringIO(csv_str))
        header = next(reader)
        assert "player_id" in header
        assert "fantasy_points" in header


class TestExportTournamentEventsCSV:
    def test_includes_events(self, isolated_db):
        log_event("test.export", "event 1", tournament_id=1)
        log_event("test.export", "event 2", tournament_id=1)
        csv_str = export_tournament_events_csv(tournament_id=1)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) >= 3  # header + 2+ events (create_tournament also logs)

    def test_all_events_export(self, isolated_db):
        log_event("a", "m1")
        log_event("b", "m2")
        csv_str = export_tournament_events_csv()
        assert len(csv_str) > 0
