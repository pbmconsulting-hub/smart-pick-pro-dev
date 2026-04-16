"""Integration tests for tournament.manager — real lifecycle operations."""

import json
from datetime import datetime

import tournament.database as tdb
from tournament.events import list_events
from tournament.manager import (
    _validate_entry,
    assess_pending_paid_entry,
    compute_reconcile_digest,
    create_reconcile_compliance_chain_checkpoint,
    create_reconcile_signature_chain_checkpoint,
    create_reconcile_verification_signature_receipt,
    create_tournament,
    evaluate_reconcile_compliance_readiness,
    export_reconcile_compliance_readiness_evaluation_artifact,
    export_reconcile_compliance_readiness_evaluation_artifact_envelope,
    export_reconcile_compliance_readiness_policy_snapshot,
    get_reconcile_compliance_readiness_policies,
    get_latest_reconcile_compliance_readiness_evaluation_artifact_head,
    get_latest_reconcile_compliance_readiness_evaluation_artifact_checkpoint,
    get_latest_reconcile_compliance_readiness_policy_snapshot_checkpoint,
    get_latest_reconcile_compliance_readiness_policy_snapshot_head,
    export_reconcile_compliance_status_envelope,
    export_reconcile_compliance_status_artifact,
    export_reconcile_signature_receipts_artifact,
    expire_stale_pending_paid_entries,
    export_reconcile_verification_envelope,
    export_reconcile_verification_report,
    finalize_pending_paid_entry,
    get_reconcile_compliance_status,
    get_latest_reconcile_compliance_status_artifact_head,
    get_latest_reconcile_compliance_chain_checkpoint,
    get_latest_reconcile_summary_event,
    get_latest_reconcile_signature_receipts_artifact_head,
    get_latest_reconcile_signature_chain_checkpoint,
    get_pending_paid_entry,
    get_reconcile_signing_key_registry_status,
    get_tournament,
    get_tournament_scoreboard,
    get_user_career_stats,
    list_career_leaderboard,
    list_reconcile_signature_receipts,
    list_pending_paid_entries,
    list_open_tournaments,
    list_tournaments,
    list_user_entries,
    load_tournament_entries,
    mark_pending_paid_entry_finalized,
    prune_reconcile_compliance_readiness_policy_snapshots,
    prune_reconcile_compliance_readiness_evaluation_artifacts,
    prune_reconcile_compliance_status_artifacts,
    prune_reconcile_signature_receipts,
    reconcile_pending_paid_entries,
    save_pending_paid_entry,
    submit_entry,
    submit_paid_entry_after_checkout,
    verify_reconcile_digest,
    verify_reconcile_signature_chain_checkpoint,
    verify_reconcile_signature_chain_checkpoint_history,
    verify_reconcile_compliance_status_artifact_chain,
    verify_reconcile_compliance_chain_checkpoint,
    verify_reconcile_compliance_chain_checkpoint_history,
    create_reconcile_compliance_readiness_policy_snapshot_checkpoint,
    create_reconcile_compliance_readiness_evaluation_artifact_checkpoint,
    verify_reconcile_compliance_readiness_evaluation_artifact_chain,
    export_reconcile_composite_governance_snapshot,
    export_reconcile_composite_governance_snapshot_envelope,
    get_latest_reconcile_composite_governance_snapshot_head,
    verify_reconcile_composite_governance_snapshot_chain,
    prune_reconcile_composite_governance_snapshots,
    create_reconcile_composite_governance_snapshot_checkpoint,
    get_latest_reconcile_composite_governance_snapshot_checkpoint,
    verify_reconcile_composite_governance_snapshot_checkpoint,
    verify_reconcile_composite_governance_snapshot_checkpoint_history,
    export_reconcile_governance_attestation_seal,
    get_latest_reconcile_governance_attestation_seal_head,
    verify_reconcile_governance_attestation_seal_chain,
    prune_reconcile_governance_attestation_seals,
    create_reconcile_governance_attestation_seal_checkpoint,
    get_latest_reconcile_governance_attestation_seal_checkpoint,
    verify_reconcile_governance_attestation_seal_checkpoint,
    verify_reconcile_governance_attestation_seal_checkpoint_history,
    get_reconcile_chain_repair_diagnostics,
    evaluate_reconcile_governance_enforcement,
    verify_reconcile_compliance_readiness_policy_snapshot_checkpoint,
    verify_reconcile_compliance_readiness_policy_snapshot_checkpoint_history,
    verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint,
    verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint_history,
    verify_reconcile_compliance_readiness_policy_snapshot_chain,
    verify_reconcile_signature_receipts_artifact_chain,
    verify_reconcile_digest_for_event,
    verify_reconcile_digest_for_latest_event,
    verify_reconcile_verification_report_signature,
)
from tournament.webhooks import upsert_checkout_session


def _make_roster(*, paid=True):
    """Build a valid roster for a paid or free tournament."""
    active = [
        {"player_id": f"A{i}", "player_name": f"Player {i}", "salary": 5500, "is_legend": False}
        for i in range(8)
    ]
    if paid:
        legend = {"player_id": "L001", "player_name": "MJ", "salary": 15000, "is_legend": True}
        return active + [legend]
    return active


class TestCreateTournament:
    def test_returns_int_id(self, isolated_db):
        tid = create_tournament("Test Open", "Open", 0.0, 8, 64, "2099-01-01T20:00:00")
        assert isinstance(tid, int)
        assert tid > 0

    def test_tournament_persisted(self, isolated_db):
        tid = create_tournament("Persist", "Pro", 20.0, 12, 24, "2099-06-01T20:00:00")
        t = get_tournament(tid)
        assert t is not None
        assert t["tournament_name"] == "Persist"
        assert t["court_tier"] == "Pro"
        assert t["status"] == "open"

    def test_multiple_tournaments(self, isolated_db):
        t1 = create_tournament("A", "Open", 0, 8, 64, "2099-01-01T20:00:00")
        t2 = create_tournament("B", "Pro", 20, 12, 24, "2099-01-02T20:00:00")
        assert t2 > t1


class TestGetTournament:
    def test_none_for_missing(self, isolated_db):
        assert get_tournament(99999) is None

    def test_returns_dict(self, isolated_db):
        tid = create_tournament("X", "Open", 0, 8, 64, "2099-01-01T20:00:00")
        t = get_tournament(tid)
        assert isinstance(t, dict)
        assert t["tournament_id"] == tid


class TestListTournaments:
    def test_list_all(self, isolated_db):
        create_tournament("A", "Open", 0, 8, 64, "2099-01-01T20:00:00")
        create_tournament("B", "Pro", 20, 12, 24, "2099-01-02T20:00:00")
        assert len(list_tournaments()) == 2

    def test_filter_by_status(self, isolated_db):
        create_tournament("A", "Open", 0, 8, 64, "2099-01-01T20:00:00")
        assert len(list_tournaments(status="open")) == 1
        assert len(list_tournaments(status="resolved")) == 0


class TestListOpenTournaments:
    def test_returns_open_only(self, isolated_db):
        create_tournament("O", "Open", 0, 8, 64, "2099-01-01T20:00:00")
        opens = list_open_tournaments()
        assert len(opens) == 1
        assert opens[0]["status"] == "open"


class TestValidateEntry:
    def test_valid_paid_roster(self, isolated_db):
        t = {"entry_fee": 20.0}
        valid, msg = _validate_entry(t, _make_roster(paid=True))
        assert valid is True

    def test_empty_roster_rejected(self, isolated_db):
        t = {"entry_fee": 0.0}
        valid, msg = _validate_entry(t, [])
        assert valid is False

    def test_wrong_slot_count_paid(self, isolated_db):
        t = {"entry_fee": 20.0}
        valid, msg = _validate_entry(t, _make_roster(paid=True)[:5])
        assert valid is False
        assert "9 players" in msg

    def test_duplicate_player_rejected(self, isolated_db):
        t = {"entry_fee": 0.0}
        roster = [{"player_id": "X", "salary": 5000, "is_legend": False}] * 8
        valid, msg = _validate_entry(t, roster)
        assert valid is False
        assert "duplicate" in msg.lower()

    def test_paid_requires_legend(self, isolated_db):
        t = {"entry_fee": 20.0}
        roster = [
            {"player_id": f"A{i}", "salary": 5500, "is_legend": False}
            for i in range(9)
        ]
        valid, msg = _validate_entry(t, roster)
        assert valid is False
        assert "legend" in msg.lower()

    def test_salary_cap_exceeded(self, isolated_db):
        t = {"entry_fee": 20.0}
        roster = [
            {"player_id": f"A{i}", "salary": 7000, "is_legend": False}
            for i in range(8)
        ] + [{"player_id": "L001", "salary": 15000, "is_legend": True}]
        valid, msg = _validate_entry(t, roster)
        assert valid is False
        assert "cap" in msg.lower()

    def test_salary_floor_not_met(self, isolated_db):
        t = {"entry_fee": 20.0}
        roster = [
            {"player_id": f"A{i}", "salary": 3000, "is_legend": False}
            for i in range(8)
        ] + [{"player_id": "L001", "salary": 15000, "is_legend": True}]
        valid, msg = _validate_entry(t, roster)
        assert valid is False
        assert "floor" in msg.lower()


class TestSubmitEntry:
    def test_success(self, isolated_db):
        tid = create_tournament("Entry Test", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        ok, msg, eid = submit_entry(tid, "alice@test.com", "Alice", _make_roster(paid=True))
        assert ok is True
        assert eid is not None
        assert isinstance(eid, int)

    def test_tournament_not_found(self, isolated_db):
        ok, msg, eid = submit_entry(99999, "a@b.com", "A", _make_roster())
        assert ok is False
        assert eid is None

    def test_duplicate_user_rejected(self, isolated_db):
        tid = create_tournament("Dup", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        submit_entry(tid, "x@test.com", "X", _make_roster(paid=True))
        ok, msg, eid = submit_entry(tid, "x@test.com", "X", _make_roster(paid=True))
        assert ok is False
        assert eid is None
        assert "already entered" in msg.lower()

    def test_full_tournament_rejected(self, isolated_db):
        tid = create_tournament("Full", "Pro", 20.0, 2, 2, "2099-06-01T20:00:00")
        submit_entry(tid, "a@t.com", "A", _make_roster(paid=True))
        submit_entry(tid, "b@t.com", "B", _make_roster(paid=True))
        ok, msg, eid = submit_entry(tid, "c@t.com", "C", _make_roster(paid=True))
        assert ok is False
        assert "full" in msg.lower()


class TestSubmitPaidEntryAfterCheckout:
    def test_requires_paid_tournament(self, isolated_db):
        tid = create_tournament("Free", "Open", 0.0, 8, 64, "2099-06-01T20:00:00")
        ok, msg, eid = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="free@test.com",
            display_name="Free",
            roster=_make_roster(paid=False),
            checkout_session_id="cs_test_1",
        )
        assert ok is False
        assert "not paid" in msg.lower()
        assert eid is None

    def test_requires_checkout_session_id(self, isolated_db):
        tid = create_tournament("Paid", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        ok, msg, eid = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="paid@test.com",
            display_name="Paid",
            roster=_make_roster(paid=True),
            checkout_session_id="",
        )
        assert ok is False
        assert "required" in msg.lower()
        assert eid is None

    def test_success_stores_checkout_reference(self, isolated_db):
        tid = create_tournament("Paid", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        ok, msg, eid = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="paid@test.com",
            display_name="Paid",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_test_abc123",
        )
        assert ok is True
        assert isinstance(eid, int)

        with tdb.get_tournament_connection() as conn:
            row = conn.execute(
                "SELECT stripe_payment_intent_id FROM tournament_entries WHERE entry_id = ?",
                (int(eid),),
            ).fetchone()
        assert row is not None
        assert row["stripe_payment_intent_id"] == "cs_test_abc123"

    def test_idempotent_finalize_returns_existing_entry(self, isolated_db):
        tid = create_tournament("Paid", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        ok1, msg1, eid1 = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="paid@test.com",
            display_name="Paid",
            roster=_make_roster(paid=True),
            checkout_session_id="pi_same_1",
        )
        assert ok1 is True
        assert isinstance(eid1, int)

        ok2, msg2, eid2 = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="paid@test.com",
            display_name="Paid",
            roster=_make_roster(paid=True),
            checkout_session_id="pi_same_1",
        )
        assert ok2 is True
        assert eid2 == eid1
        assert "already finalized" in msg2.lower()

    def test_checkout_reference_conflict_user(self, isolated_db):
        tid = create_tournament("Paid", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="alpha@test.com",
            display_name="Alpha",
            roster=_make_roster(paid=True),
            checkout_session_id="pi_conflict_1",
        )

        ok, msg, eid = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="beta@test.com",
            display_name="Beta",
            roster=_make_roster(paid=True),
            checkout_session_id="pi_conflict_1",
        )
        assert ok is False
        assert eid is None
        assert "different user" in msg.lower()


class TestLoadTournamentEntries:
    def test_returns_entries(self, isolated_db):
        tid = create_tournament("Load", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        submit_entry(tid, "a@t.com", "A", _make_roster(paid=True))
        entries = load_tournament_entries(tid)
        assert len(entries) == 1
        assert "roster" in entries[0]
        assert isinstance(entries[0]["roster"], list)


class TestGetTournamentScoreboard:
    def test_empty_before_resolve(self, isolated_db):
        tid = create_tournament("SB", "Open", 0, 8, 64, "2099-01-01T20:00:00")
        sb = get_tournament_scoreboard(tid)
        assert sb == []


class TestListUserEntries:
    def test_returns_user_entries(self, isolated_db):
        tid = create_tournament("UE", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        submit_entry(tid, "user@test.com", "User", _make_roster(paid=True))
        entries = list_user_entries("user@test.com")
        assert len(entries) == 1
        assert entries[0]["tournament_id"] == tid


class TestGetUserCareerStats:
    def test_default_stats_for_unknown(self, isolated_db):
        stats = get_user_career_stats("nobody@test.com")
        assert stats["lifetime_entries"] == 0
        assert stats["lifetime_wins"] == 0
        assert stats["career_level"] == 1


class TestCareerLeaderboard:
    def test_returns_ranked_rows(self, isolated_db):
        with tdb.get_tournament_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_career_stats
                    (user_email, display_name, lifetime_entries, lifetime_wins, lifetime_top5,
                     lifetime_earnings, lifetime_lp, career_level, updated_at)
                VALUES
                    ('a@test.com', 'A', 10, 3, 4, 120.0, 450, 4, datetime('now')),
                    ('b@test.com', 'B', 9, 5, 5, 180.0, 800, 7, datetime('now')),
                    ('c@test.com', 'C', 7, 2, 3, 90.0, 450, 3, datetime('now'))
                """
            )
            conn.commit()

        board = list_career_leaderboard(limit=10)
        assert len(board) == 3
        assert board[0]["user_email"] == "b@test.com"
        assert board[0]["rank"] == 1
        assert board[1]["rank"] == 2
        assert board[2]["rank"] == 3

    def test_limit_respected(self, isolated_db):
        with tdb.get_tournament_connection() as conn:
            for i in range(12):
                conn.execute(
                    """
                    INSERT INTO user_career_stats (user_email, lifetime_lp, updated_at)
                    VALUES (?, ?, datetime('now'))
                    """,
                    (f"u{i}@test.com", i * 10),
                )
            conn.commit()

        board = list_career_leaderboard(limit=5)
        assert len(board) == 5
        assert board[0]["lifetime_lp"] >= board[-1]["lifetime_lp"]


class TestPendingPaidEntries:
    def test_save_and_get_pending_paid_entry(self, isolated_db):
        ok = save_pending_paid_entry(
            tournament_id=55,
            user_email="pending@test.com",
            display_name="Pending",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_pending_1",
        )
        assert ok is True

        item = get_pending_paid_entry("cs_pending_1")
        assert item is not None
        assert item["tournament_id"] == 55
        assert item["user_email"] == "pending@test.com"
        assert item["status"] == "pending"
        assert isinstance(item["roster"], list)
        assert len(item["roster"]) == 9

    def test_mark_pending_paid_entry_finalized(self, isolated_db):
        save_pending_paid_entry(
            tournament_id=56,
            user_email="final@test.com",
            display_name="Final",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_pending_2",
        )

        updated = mark_pending_paid_entry_finalized("cs_pending_2", "pi_final_2")
        assert updated is True

        item = get_pending_paid_entry("cs_pending_2")
        assert item is not None
        assert item["status"] == "finalized"
        assert item["payment_intent_id"] == "pi_final_2"

    def test_list_pending_paid_entries_all_and_filtered(self, isolated_db):
        save_pending_paid_entry(
            tournament_id=57,
            user_email="one@test.com",
            display_name="One",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_pending_3",
        )
        save_pending_paid_entry(
            tournament_id=58,
            user_email="two@test.com",
            display_name="Two",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_pending_4",
        )
        mark_pending_paid_entry_finalized("cs_pending_4", "pi_final_4")

        all_rows = list_pending_paid_entries(limit=20)
        assert len(all_rows) >= 2

        pending_rows = list_pending_paid_entries(status="pending", limit=20)
        finalized_rows = list_pending_paid_entries(status="finalized", limit=20)

        assert any(r["checkout_session_id"] == "cs_pending_3" for r in pending_rows)
        assert any(r["checkout_session_id"] == "cs_pending_4" for r in finalized_rows)

    def test_list_pending_paid_entries_limit(self, isolated_db):
        for i in range(8):
            save_pending_paid_entry(
                tournament_id=60 + i,
                user_email=f"u{i}@test.com",
                display_name=f"U{i}",
                roster=_make_roster(paid=True),
                checkout_session_id=f"cs_limit_{i}",
            )

        rows = list_pending_paid_entries(limit=3)
        assert len(rows) == 3

    def test_expire_stale_pending_paid_entries(self, isolated_db):
        save_pending_paid_entry(
            tournament_id=70,
            user_email="stale@test.com",
            display_name="Stale",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_stale_1",
        )

        with tdb.get_tournament_connection() as conn:
            conn.execute(
                "UPDATE pending_paid_entries SET created_at='2099-06-01 00:00:00' WHERE checkout_session_id='cs_stale_1'"
            )
            conn.commit()

        expired = expire_stale_pending_paid_entries(
            max_age_hours=24,
            now=datetime(2099, 6, 3, 10, 0),
        )
        assert expired == 1

        item = get_pending_paid_entry("cs_stale_1")
        assert item is not None
        assert item["status"] == "expired"

    def test_finalize_pending_paid_entry_success(self, isolated_db):
        tid = create_tournament("Paid Finalize", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="manual@test.com",
            display_name="Manual",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_manual_1",
        )

        result = finalize_pending_paid_entry("cs_manual_1", payment_reference="pi_manual_1")
        assert result["success"] is True
        assert isinstance(result["entry_id"], int)

        item = get_pending_paid_entry("cs_manual_1")
        assert item is not None
        assert item["status"] == "finalized"
        assert item["payment_intent_id"] == "pi_manual_1"

        events = list_events(event_type="pending.finalized", limit=20)
        assert any(
            str(e.get("metadata", {}).get("checkout_session_id", "")) == "cs_manual_1"
            and str(e.get("user_email", "")) == "manual@test.com"
            for e in events
        )

    def test_finalize_pending_paid_entry_not_found(self, isolated_db):
        result = finalize_pending_paid_entry("cs_missing")
        assert result["success"] is False
        assert "not found" in str(result["error"]).lower()

        events = list_events(event_type="pending.finalize_failed", limit=20)
        assert any(
            str(e.get("metadata", {}).get("checkout_session_id", "")) == "cs_missing"
            for e in events
        )

    def test_assess_pending_paid_entry_recommends_finalize_now(self, isolated_db):
        tid = create_tournament("Diag Paid", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="diag@test.com",
            display_name="Diag",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_diag_1",
        )
        assert upsert_checkout_session(
            "cs_diag_1",
            tournament_id=tid,
            user_email="diag@test.com",
            payment_intent_id="pi_diag_1",
            payment_status="paid",
        )

        result = assess_pending_paid_entry("cs_diag_1")
        assert result["success"] is True
        assert result["recommended_action"] == "finalize_now"
        assert result["can_finalize"] is True
        assert result.get("checkout_record") is not None

    def test_assess_pending_paid_entry_detects_stale_pending(self, isolated_db):
        tid = create_tournament("Diag Stale", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="stale-diag@test.com",
            display_name="Stale Diag",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_diag_2",
        )
        ok, _, entry_id = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="stale-diag@test.com",
            display_name="Stale Diag",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_diag_2",
        )
        assert ok is True
        assert isinstance(entry_id, int)

        result = assess_pending_paid_entry("cs_diag_2")
        assert result["success"] is True
        assert result["recommended_action"] == "mark_finalized"
        assert int(result.get("existing_entry_id") or 0) == int(entry_id)

    def test_reconcile_pending_paid_entries_marks_stale(self, isolated_db):
        tid = create_tournament("Diag Reconcile", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="reconcile@test.com",
            display_name="Reconcile",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_diag_reconcile_1",
        )
        ok, _, entry_id = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="reconcile@test.com",
            display_name="Reconcile",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_diag_reconcile_1",
        )
        assert ok is True
        assert isinstance(entry_id, int)

        summary = reconcile_pending_paid_entries(limit=20)
        assert int(summary.get("scanned", 0)) >= 1
        assert int(summary.get("reconciled", 0)) == 1
        assert int(summary.get("failed", 0)) == 0

        item = get_pending_paid_entry("cs_diag_reconcile_1")
        assert item is not None
        assert item["status"] == "finalized"

        events = list_events(event_type="pending.reconciled", limit=20)
        assert any(
            str(e.get("metadata", {}).get("checkout_session_id", "")) == "cs_diag_reconcile_1"
            for e in events
        )

    def test_reconcile_pending_paid_entries_dry_run_no_mutation(self, isolated_db):
        tid = create_tournament("Diag Reconcile Dry", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="reconcile-dry@test.com",
            display_name="Reconcile Dry",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_diag_reconcile_dry_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="reconcile-dry@test.com",
            display_name="Reconcile Dry",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_diag_reconcile_dry_1",
        )
        assert ok is True

        summary = reconcile_pending_paid_entries(limit=20, dry_run=True)
        assert int(summary.get("scanned", 0)) >= 1
        assert int(summary.get("candidates", 0)) >= 1
        assert int(summary.get("reconciled", 0)) == 0
        assert summary.get("dry_run") is True
        assert len(str(summary.get("attempted_sessions_sha256", ""))) == 64

        item = get_pending_paid_entry("cs_diag_reconcile_dry_1")
        assert item is not None
        assert item["status"] == "pending"

    def test_reconcile_pending_paid_entries_max_actions_cap(self, isolated_db):
        tid = create_tournament("Diag Reconcile Cap", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        for sid in ("cs_diag_cap_1", "cs_diag_cap_2"):
            save_pending_paid_entry(
                tournament_id=tid,
                user_email=f"{sid}@test.com",
                display_name=sid,
                roster=_make_roster(paid=True),
                checkout_session_id=sid,
            )
            ok, _, _ = submit_paid_entry_after_checkout(
                tournament_id=tid,
                user_email=f"{sid}@test.com",
                display_name=sid,
                roster=_make_roster(paid=True),
                checkout_session_id=sid,
            )
            assert ok is True

        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        assert int(summary.get("candidates", 0)) >= 2
        assert int(summary.get("attempted", 0)) == 1
        assert int(summary.get("reconciled", 0)) == 1
        assert int(summary.get("skipped_due_to_cap", 0)) >= 1
        assert len(str(summary.get("candidate_sessions_sha256", ""))) == 64
        assert len(str(summary.get("attempted_sessions_sha256", ""))) == 64

    def test_reconcile_pending_paid_entries_priority_paid_first(self, isolated_db):
        tid = create_tournament("Diag Reconcile Priority", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="priority-paid@test.com",
            display_name="Priority Paid",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_priority_paid",
        )
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="priority-unpaid@test.com",
            display_name="Priority Unpaid",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_priority_unpaid",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="priority-paid@test.com",
            display_name="Priority Paid",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_priority_paid",
        )
        assert ok is True
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="priority-unpaid@test.com",
            display_name="Priority Unpaid",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_priority_unpaid",
        )
        assert ok is True
        assert upsert_checkout_session(
            "cs_priority_paid",
            tournament_id=tid,
            user_email="priority-paid@test.com",
            payment_intent_id="pi_priority_paid",
            payment_status="paid",
        )
        assert upsert_checkout_session(
            "cs_priority_unpaid",
            tournament_id=tid,
            user_email="priority-unpaid@test.com",
            payment_intent_id="pi_priority_unpaid",
            payment_status="unpaid",
        )

        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="paid_first_oldest")
        actions = list(summary.get("actions", []))
        assert len(actions) == 1
        assert str(actions[0].get("checkout_session_id", "")) == "cs_priority_paid"

        summary_events = list_events(event_type="pending.reconcile_summary", limit=20)
        assert len(summary_events) >= 1
        assert any(
            len(str(e.get("metadata", {}).get("attempted_sessions_sha256", ""))) == 64
            for e in summary_events
        )

    def test_verify_reconcile_digest_matches(self, isolated_db):
        session_ids = ["cs_a", "cs_b", "cs_c"]
        digest = compute_reconcile_digest(session_ids=session_ids, strict_order=True)
        result = verify_reconcile_digest(session_ids=session_ids, digest=digest, strict_order=True)
        assert result["success"] is True
        assert result["match"] is True
        assert str(result["expected_digest"]) == str(digest)

    def test_verify_reconcile_digest_order_sensitive(self, isolated_db):
        ordered = ["cs_x", "cs_y"]
        reversed_ids = ["cs_y", "cs_x"]
        digest = compute_reconcile_digest(session_ids=ordered, strict_order=True)

        strict_result = verify_reconcile_digest(session_ids=reversed_ids, digest=digest, strict_order=True)
        relaxed_result = verify_reconcile_digest(session_ids=reversed_ids, digest=digest, strict_order=False)

        assert strict_result["success"] is True
        assert strict_result["match"] is False
        assert relaxed_result["success"] is True
        assert relaxed_result["match"] is True

    def test_verify_reconcile_digest_normalize_mode_trim_lower(self, isolated_db):
        digest = compute_reconcile_digest(["CS_A"], strict_order=True, normalize_mode="trim_lower")
        result = verify_reconcile_digest(["cs_a"], digest=digest, strict_order=True, normalize_mode="trim_lower")
        assert result["success"] is True
        assert result["match"] is True

    def test_verify_reconcile_digest_reference_mismatch_details(self, isolated_db):
        digest = compute_reconcile_digest(["cs_a", "cs_b"], strict_order=True)
        result = verify_reconcile_digest(
            ["cs_a", "cs_c"],
            digest=digest,
            strict_order=True,
            reference_session_ids=["cs_a", "cs_b"],
        )
        assert result["success"] is True
        assert result["match"] is False
        assert result["first_mismatch_index"] == 1
        assert result["first_mismatch_provided_session_id"] == "cs_c"
        assert result["first_mismatch_reference_session_id"] == "cs_b"
        assert "cs_b" in list(result.get("missing_session_ids", []))
        assert "cs_c" in list(result.get("unexpected_session_ids", []))

    def test_verify_reconcile_digest_for_event_matches_attempted(self, isolated_db):
        tid = create_tournament("Diag Event Verify", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="event-verify@test.com",
            display_name="Event Verify",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_event_verify_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="event-verify@test.com",
            display_name="Event Verify",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_event_verify_1",
        )
        assert ok is True

        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted_ids = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        summary_events = list_events(event_type="pending.reconcile_summary", limit=20)
        assert len(summary_events) >= 1

        event_id = int(summary_events[0]["event_id"])
        result = verify_reconcile_digest_for_event(
            event_id=event_id,
            session_ids=attempted_ids,
            scope="attempted",
            strict_order=True,
        )
        assert result["success"] is True
        assert result["match"] is True
        assert int(result.get("event_id", 0)) == event_id

    def test_verify_reconcile_digest_for_latest_event_matches_attempted(self, isolated_db):
        tid = create_tournament("Diag Latest Event Verify", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="event-latest@test.com",
            display_name="Event Latest",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_event_latest_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="event-latest@test.com",
            display_name="Event Latest",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_event_latest_1",
        )
        assert ok is True

        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted_ids = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]

        result = verify_reconcile_digest_for_latest_event(
            session_ids=attempted_ids,
            scope="attempted",
            strict_order=True,
        )
        assert result["success"] is True
        assert result["match"] is True
        assert int(result.get("event_id", 0)) > 0

    def test_export_reconcile_verification_report_uses_latest(self, isolated_db):
        tid = create_tournament("Diag Report Verify", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="report@test.com",
            display_name="Report",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_report_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="report@test.com",
            display_name="Report",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_report_1",
        )
        assert ok is True

        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted_ids = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]

        report = export_reconcile_verification_report(
            session_ids=attempted_ids,
            scope="attempted",
            strict_order=True,
        )
        assert report["success"] is True
        assert report["match"] is True
        assert report["signed"] is False
        assert str(report.get("signature_type")) == "sha256"
        assert len(str(report.get("signature", ""))) == 64
        assert int((report.get("report") or {}).get("event_id", 0)) > 0

    def test_export_reconcile_verification_report_hmac_signing(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "k_test_1")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "2")
        tid = create_tournament("Diag Report Verify HMAC", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="report-hmac@test.com",
            display_name="Report HMAC",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_report_hmac_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="report-hmac@test.com",
            display_name="Report HMAC",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_report_hmac_1",
        )
        assert ok is True

        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted_ids = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]

        report = export_reconcile_verification_report(session_ids=attempted_ids, scope="attempted")
        assert report["success"] is True
        assert report["signed"] is True
        assert str(report.get("signature_type")) == "hmac_sha256"
        assert str(report.get("key_id", "")) == "k_test_1"
        assert int(report.get("signature_version", 0)) == 2
        assert str((report.get("report") or {}).get("signature_metadata", {}).get("key_id", "")) == "k_test_1"
        assert int((report.get("report") or {}).get("signature_metadata", {}).get("signature_version", 0)) == 2
        assert len(str(report.get("signature", ""))) == 64

    def test_export_reconcile_verification_envelope_contains_verify_payload(self, isolated_db):
        tid = create_tournament("Diag Envelope Verify", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="envelope@test.com",
            display_name="Envelope",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_envelope_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="envelope@test.com",
            display_name="Envelope",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_envelope_1",
        )
        assert ok is True

        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted_ids = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]

        envelope = export_reconcile_verification_envelope(
            session_ids=attempted_ids,
            scope="attempted",
            strict_order=True,
        )
        assert envelope["success"] is True
        assert envelope["match"] is True
        assert int(envelope.get("envelope_version", 0)) == 1
        verify_payload = dict(envelope.get("verify_payload") or {})
        assert isinstance(verify_payload.get("report"), dict)
        assert len(str(verify_payload.get("signature", ""))) == 64

    def test_get_latest_reconcile_summary_event(self, isolated_db):
        tid = create_tournament("Diag Latest Summary", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="latest-summary@test.com",
            display_name="Latest Summary",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_latest_summary_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="latest-summary@test.com",
            display_name="Latest Summary",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_latest_summary_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        latest = get_latest_reconcile_summary_event(scope="attempted")
        assert latest["success"] is True
        assert int(latest.get("event_id", 0)) > 0
        assert len(str(latest.get("event_digest", ""))) == 64

    def test_verify_reconcile_verification_report_signature_sha256(self, isolated_db):
        tid = create_tournament("Diag Signature SHA", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-sha@test.com",
            display_name="Sig SHA",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_sha_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-sha@test.com",
            display_name="Sig SHA",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_sha_1",
        )
        assert ok is True

        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted_ids = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted_ids, scope="attempted")

        verify = verify_reconcile_verification_report_signature(
            report=dict(report_result.get("report") or {}),
            signature=str(report_result.get("signature", "")),
            signature_type=str(report_result.get("signature_type", "sha256")),
        )
        assert verify["success"] is True
        assert verify["match"] is True

    def test_verify_reconcile_verification_report_signature_hmac(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "k_test_hmac")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "3")
        tid = create_tournament("Diag Signature HMAC", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-hmac@test.com",
            display_name="Sig HMAC",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_hmac_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-hmac@test.com",
            display_name="Sig HMAC",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_hmac_1",
        )
        assert ok is True

        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted_ids = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted_ids, scope="attempted")

        verify = verify_reconcile_verification_report_signature(
            report=dict(report_result.get("report") or {}),
            signature=str(report_result.get("signature", "")),
            signature_type=str(report_result.get("signature_type", "hmac_sha256")),
            key_id="k_test_hmac",
            signature_version=3,
        )
        assert verify["success"] is True
        assert verify["match"] is True

    def test_verify_reconcile_verification_report_signature_key_id_mismatch(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "k_expected")
        tid = create_tournament("Diag Signature Key Mismatch", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-key-mismatch@test.com",
            display_name="Sig Key Mismatch",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_key_mismatch_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-key-mismatch@test.com",
            display_name="Sig Key Mismatch",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_key_mismatch_1",
        )
        assert ok is True
        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted_ids = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted_ids, scope="attempted")

        verify = verify_reconcile_verification_report_signature(
            report=dict(report_result.get("report") or {}),
            signature=str(report_result.get("signature", "")),
            signature_type=str(report_result.get("signature_type", "hmac_sha256")),
            key_id="k_wrong",
        )
        assert verify["success"] is False
        assert verify["match"] is False

    def test_verify_reconcile_verification_report_signature_registry_key(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEYS_JSON", '{"k_rot_1":"rotating-secret"}')
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "k_rot_1")

        tid = create_tournament("Diag Signature Registry", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-registry@test.com",
            display_name="Sig Registry",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_registry_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-registry@test.com",
            display_name="Sig Registry",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_registry_1",
        )
        assert ok is True

        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted_ids = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted_ids, scope="attempted")
        assert str(report_result.get("key_source", "")) == "registry"

        verify = verify_reconcile_verification_report_signature(
            report=dict(report_result.get("report") or {}),
            signature=str(report_result.get("signature", "")),
            signature_type=str(report_result.get("signature_type", "hmac_sha256")),
            key_id="k_rot_1",
        )
        assert verify["success"] is True
        assert verify["match"] is True
        assert str(verify.get("key_source", "")) == "registry"

    def test_create_and_list_reconcile_signature_receipts(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Diag Signature Receipt", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-receipt@test.com",
            display_name="Sig Receipt",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_receipt_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-receipt@test.com",
            display_name="Sig Receipt",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_receipt_1",
        )
        assert ok is True
        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted_ids = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted_ids, scope="attempted")

        receipt = create_reconcile_verification_signature_receipt(
            report=dict(report_result.get("report") or {}),
            signature=str(report_result.get("signature", "")),
            signature_type=str(report_result.get("signature_type", "hmac_sha256")),
            actor_email="auditor@test.com",
            source="integration_test",
        )
        assert receipt["success"] is True
        assert receipt["match"] is True
        assert int(receipt.get("receipt_event_id", 0)) > 0

        all_rows = list_reconcile_signature_receipts(limit=50, outcome="all")
        matched_rows = list_reconcile_signature_receipts(limit=50, outcome="matched")
        assert any(int(r.get("event_id", 0)) == int(receipt.get("receipt_event_id", 0)) for r in all_rows)
        assert any(int(r.get("event_id", 0)) == int(receipt.get("receipt_event_id", 0)) for r in matched_rows)

    def test_get_reconcile_signing_key_registry_status(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEYS_JSON", '{"k_one":"abc","k_two":"def"}')
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_KEY_ID", "k_one")
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNATURE_VERSION", "4")

        status = get_reconcile_signing_key_registry_status()
        assert status["success"] is True
        assert int(status.get("registry_count", 0)) == 2
        assert str(status.get("default_key_id", "")) == "k_one"
        assert int(status.get("signature_version", 0)) == 4
        keys = list(status.get("keys", []))
        assert any(str(k.get("key_id", "")) == "k_one" and bool(k.get("is_default", False)) for k in keys)

    def test_export_reconcile_signature_receipts_artifact(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Diag Receipt Artifact", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-artifact@test.com",
            display_name="Sig Artifact",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_artifact_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-artifact@test.com",
            display_name="Sig Artifact",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_artifact_1",
        )
        assert ok is True
        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted_ids = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted_ids, scope="attempted")
        receipt = create_reconcile_verification_signature_receipt(
            report=dict(report_result.get("report") or {}),
            signature=str(report_result.get("signature", "")),
            signature_type=str(report_result.get("signature_type", "hmac_sha256")),
            actor_email="artifact-auditor@test.com",
            source="integration_test",
        )
        assert receipt["success"] is True

        artifact = export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=True)
        assert artifact["success"] is True
        assert int(artifact.get("count", 0)) >= 1
        assert len(str(artifact.get("digest_sha256", ""))) == 64
        assert "event_id" in str(artifact.get("csv", ""))

    def test_export_reconcile_signature_receipts_artifact_chain_head(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Diag Receipt Chain", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-chain@test.com",
            display_name="Sig Chain",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_chain_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-chain@test.com",
            display_name="Sig Chain",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_chain_1",
        )
        assert ok is True
        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted_ids = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted_ids, scope="attempted")
        receipt = create_reconcile_verification_signature_receipt(
            report=dict(report_result.get("report") or {}),
            signature=str(report_result.get("signature", "")),
            signature_type=str(report_result.get("signature_type", "hmac_sha256")),
            actor_email="chain-auditor@test.com",
            source="integration_test",
        )
        assert receipt["success"] is True

        artifact_one = export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
        artifact_two = export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
        head = get_latest_reconcile_signature_receipts_artifact_head()

        assert artifact_one["success"] is True
        assert artifact_two["success"] is True
        assert str(artifact_two.get("previous_digest", "")) == str(artifact_one.get("digest_sha256", ""))
        assert len(str(artifact_two.get("chain_digest", ""))) == 64
        assert head["success"] is True
        assert str(head.get("digest_sha256", "")) == str(artifact_two.get("digest_sha256", ""))

    def test_prune_reconcile_signature_receipts_dry_run_and_delete(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Diag Receipt Prune", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-prune@test.com",
            display_name="Sig Prune",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_prune_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-prune@test.com",
            display_name="Sig Prune",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_prune_1",
        )
        assert ok is True
        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted_ids = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted_ids, scope="attempted")
        receipt = create_reconcile_verification_signature_receipt(
            report=dict(report_result.get("report") or {}),
            signature=str(report_result.get("signature", "")),
            signature_type=str(report_result.get("signature_type", "hmac_sha256")),
            actor_email="prune-auditor@test.com",
            source="integration_test",
        )
        assert int(receipt.get("receipt_event_id", 0)) > 0

        with tdb.get_tournament_connection() as conn:
            conn.execute(
                "UPDATE tournament_events SET created_at = '2000-01-01 00:00:00' WHERE event_id = ?",
                (int(receipt.get("receipt_event_id", 0)),),
            )
            conn.commit()

        dry_run = prune_reconcile_signature_receipts(max_age_days=30, dry_run=True)
        assert dry_run["success"] is True
        assert int(dry_run.get("candidates", 0)) >= 1
        assert int(dry_run.get("deleted", 0)) == 0

        execute = prune_reconcile_signature_receipts(max_age_days=30, dry_run=False)
        assert execute["success"] is True
        assert int(execute.get("deleted", 0)) >= 1

    def test_create_reconcile_signature_chain_checkpoint(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Diag Chain Checkpoint", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-checkpoint@test.com",
            display_name="Sig Checkpoint",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_checkpoint_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-checkpoint@test.com",
            display_name="Sig Checkpoint",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_checkpoint_1",
        )
        assert ok is True

        summary = reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        attempted_ids = [str(a.get("checkout_session_id", "")) for a in list(summary.get("actions", []))]
        report_result = export_reconcile_verification_report(session_ids=attempted_ids, scope="attempted")
        receipt = create_reconcile_verification_signature_receipt(
            report=dict(report_result.get("report") or {}),
            signature=str(report_result.get("signature", "")),
            signature_type=str(report_result.get("signature_type", "hmac_sha256")),
            actor_email="checkpoint-auditor@test.com",
            source="integration_test",
        )
        assert receipt["success"] is True

        artifact = export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
        checkpoint = create_reconcile_signature_chain_checkpoint(
            label="integration_checkpoint",
            expected_previous_digest=str(artifact.get("digest_sha256", "")),
            require_head=True,
        )
        assert checkpoint["success"] is True
        assert len(str(checkpoint.get("checkpoint_digest", ""))) == 64
        assert int(checkpoint.get("event_id", 0)) > 0

    def test_verify_reconcile_signature_receipts_artifact_chain_ok(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Diag Chain Verify OK", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-chain-ok@test.com",
            display_name="Sig Chain OK",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_chain_ok_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-chain-ok@test.com",
            display_name="Sig Chain OK",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_chain_ok_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        report_result = export_reconcile_verification_report(session_ids=["cs_sig_chain_ok_1"], scope="attempted")
        receipt = create_reconcile_verification_signature_receipt(
            report=dict(report_result.get("report") or {}),
            signature=str(report_result.get("signature", "")),
            signature_type=str(report_result.get("signature_type", "hmac_sha256")),
            actor_email="sig-chain-ok-auditor@test.com",
            source="integration_test",
        )
        assert receipt["success"] is True

        export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
        export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
        verify = verify_reconcile_signature_receipts_artifact_chain(limit=50)
        assert verify["success"] is True
        assert str(verify.get("status", "")) == "ok"
        assert int(verify.get("broken_links", 0)) == 0

    def test_verify_reconcile_signature_receipts_artifact_chain_detects_break(self, isolated_db, monkeypatch):
        import tournament.database as tdb

        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Diag Chain Verify Break", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-chain-break@test.com",
            display_name="Sig Chain Break",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_chain_break_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-chain-break@test.com",
            display_name="Sig Chain Break",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_chain_break_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        report_result = export_reconcile_verification_report(session_ids=["cs_sig_chain_break_1"], scope="attempted")
        receipt = create_reconcile_verification_signature_receipt(
            report=dict(report_result.get("report") or {}),
            signature=str(report_result.get("signature", "")),
            signature_type=str(report_result.get("signature_type", "hmac_sha256")),
            actor_email="sig-chain-break-auditor@test.com",
            source="integration_test",
        )
        assert receipt["success"] is True

        artifact_one = export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
        artifact_two = export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
        assert int(artifact_two.get("artifact_event_id", 0)) > 0

        with tdb.get_tournament_connection() as conn:
            row = conn.execute(
                "SELECT metadata_json FROM tournament_events WHERE event_id = ?",
                (int(artifact_two.get("artifact_event_id", 0)),),
            ).fetchone()
            metadata = json.loads(str(row["metadata_json"] or "{}"))
            metadata["previous_digest"] = "bad_previous"
            conn.execute(
                "UPDATE tournament_events SET metadata_json = ? WHERE event_id = ?",
                (json.dumps(metadata), int(artifact_two.get("artifact_event_id", 0))),
            )
            conn.commit()

        verify = verify_reconcile_signature_receipts_artifact_chain(limit=50)
        assert verify["success"] is True
        assert str(verify.get("status", "")) == "broken"
        assert int(verify.get("broken_links", 0)) >= 1

    def test_verify_reconcile_signature_chain_checkpoint_ok(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Diag Checkpoint Verify OK", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-checkpoint-ok@test.com",
            display_name="Sig Checkpoint OK",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_checkpoint_ok_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-checkpoint-ok@test.com",
            display_name="Sig Checkpoint OK",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_checkpoint_ok_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        report_result = export_reconcile_verification_report(session_ids=["cs_sig_checkpoint_ok_1"], scope="attempted")
        receipt = create_reconcile_verification_signature_receipt(
            report=dict(report_result.get("report") or {}),
            signature=str(report_result.get("signature", "")),
            signature_type=str(report_result.get("signature_type", "hmac_sha256")),
            actor_email="sig-checkpoint-ok-auditor@test.com",
            source="integration_test",
        )
        assert receipt["success"] is True

        artifact = export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
        checkpoint = create_reconcile_signature_chain_checkpoint(
            label="verify_ok",
            expected_previous_digest=str(artifact.get("digest_sha256", "")),
            require_head=True,
        )
        assert checkpoint["success"] is True

        latest_checkpoint = get_latest_reconcile_signature_chain_checkpoint()
        verify = verify_reconcile_signature_chain_checkpoint(require_current_head=True, require_signature_payload=True)
        assert latest_checkpoint["success"] is True
        assert verify["success"] is True
        assert str(verify.get("status", "")) == "ok"
        assert bool(verify.get("current_head_match", False)) is True
        signature_verification = dict(verify.get("signature_verification") or {})
        assert bool(signature_verification.get("available", False)) is True
        assert bool(signature_verification.get("verified", False)) is True
        assert bool(signature_verification.get("match", False)) is True

    def test_verify_reconcile_signature_chain_checkpoint_detects_stale_and_compliance_warning(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Diag Checkpoint Verify Stale", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-checkpoint-stale@test.com",
            display_name="Sig Checkpoint Stale",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_checkpoint_stale_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-checkpoint-stale@test.com",
            display_name="Sig Checkpoint Stale",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_checkpoint_stale_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        report_result = export_reconcile_verification_report(session_ids=["cs_sig_checkpoint_stale_1"], scope="attempted")
        receipt = create_reconcile_verification_signature_receipt(
            report=dict(report_result.get("report") or {}),
            signature=str(report_result.get("signature", "")),
            signature_type=str(report_result.get("signature_type", "hmac_sha256")),
            actor_email="sig-checkpoint-stale-auditor@test.com",
            source="integration_test",
        )
        assert receipt["success"] is True

        artifact = export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
        checkpoint = create_reconcile_signature_chain_checkpoint(
            label="verify_stale",
            expected_previous_digest=str(artifact.get("digest_sha256", "")),
            require_head=True,
        )
        assert checkpoint["success"] is True

        export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
        verify = verify_reconcile_signature_chain_checkpoint(require_current_head=False)
        compliance = get_reconcile_compliance_status(chain_limit=50)
        assert verify["success"] is True
        assert str(verify.get("status", "")) == "stale"
        assert bool(verify.get("current_head_match", False)) is False
        assert compliance["success"] is True
        assert str(compliance.get("status", "")) == "warning"
        assert "checkpoint_stale" in list(compliance.get("warnings", []))

    def test_verify_reconcile_signature_chain_checkpoint_detects_signature_tamper(self, isolated_db, monkeypatch):
        import tournament.database as tdb

        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Diag Checkpoint Verify Tamper", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-checkpoint-tamper@test.com",
            display_name="Sig Checkpoint Tamper",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_checkpoint_tamper_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-checkpoint-tamper@test.com",
            display_name="Sig Checkpoint Tamper",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_checkpoint_tamper_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        report_result = export_reconcile_verification_report(session_ids=["cs_sig_checkpoint_tamper_1"], scope="attempted")
        receipt = create_reconcile_verification_signature_receipt(
            report=dict(report_result.get("report") or {}),
            signature=str(report_result.get("signature", "")),
            signature_type=str(report_result.get("signature_type", "hmac_sha256")),
            actor_email="sig-checkpoint-tamper-auditor@test.com",
            source="integration_test",
        )
        assert receipt["success"] is True

        artifact = export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
        checkpoint = create_reconcile_signature_chain_checkpoint(
            label="verify_tamper",
            expected_previous_digest=str(artifact.get("digest_sha256", "")),
            require_head=True,
        )
        assert checkpoint["success"] is True

        checkpoint_event_id = int(checkpoint.get("event_id", 0) or 0)
        with tdb.get_tournament_connection() as conn:
            row = conn.execute(
                "SELECT metadata_json FROM tournament_events WHERE event_id = ?",
                (checkpoint_event_id,),
            ).fetchone()
            metadata = json.loads(str(row["metadata_json"] or "{}"))
            payload = dict(metadata.get("payload") or {})
            head = dict(payload.get("head") or {})
            head["digest_sha256"] = "bad_digest"
            payload["head"] = head
            metadata["payload"] = payload
            conn.execute(
                "UPDATE tournament_events SET metadata_json = ? WHERE event_id = ?",
                (json.dumps(metadata), checkpoint_event_id),
            )
            conn.commit()

        verify = verify_reconcile_signature_chain_checkpoint(require_current_head=False, require_signature_payload=True)
        assert verify["success"] is True
        assert str(verify.get("status", "")) == "broken"
        assert "checkpoint_digest_mismatch" in list(verify.get("issues", []))
        assert "checkpoint_signature_mismatch" in list(verify.get("issues", []))

    def test_verify_reconcile_signature_chain_checkpoint_history_ok(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Diag Checkpoint History OK", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-checkpoint-history-ok@test.com",
            display_name="Sig Checkpoint History OK",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_checkpoint_history_ok_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-checkpoint-history-ok@test.com",
            display_name="Sig Checkpoint History OK",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_checkpoint_history_ok_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        report_result = export_reconcile_verification_report(session_ids=["cs_sig_checkpoint_history_ok_1"], scope="attempted")
        receipt = create_reconcile_verification_signature_receipt(
            report=dict(report_result.get("report") or {}),
            signature=str(report_result.get("signature", "")),
            signature_type=str(report_result.get("signature_type", "hmac_sha256")),
            actor_email="sig-checkpoint-history-ok-auditor@test.com",
            source="integration_test",
        )
        assert receipt["success"] is True

        artifact_one = export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
        checkpoint_one = create_reconcile_signature_chain_checkpoint(
            label="history_ok_1",
            expected_previous_digest=str(artifact_one.get("digest_sha256", "")),
            require_head=True,
        )
        assert checkpoint_one["success"] is True

        artifact_two = export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)
        checkpoint_two = create_reconcile_signature_chain_checkpoint(
            label="history_ok_2",
            expected_previous_digest=str(artifact_two.get("digest_sha256", "")),
            require_head=True,
        )
        assert checkpoint_two["success"] is True

        history = verify_reconcile_signature_chain_checkpoint_history(limit=50, require_signature_payload=True)
        assert history["success"] is True
        assert str(history.get("status", "")) == "ok"
        assert int(history.get("count", 0)) >= 2
        assert int(history.get("broken", 0)) == 0

    def test_export_reconcile_compliance_status_artifact_chain_and_head(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Diag Compliance Artifact", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-compliance-artifact@test.com",
            display_name="Sig Compliance Artifact",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_compliance_artifact_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-compliance-artifact@test.com",
            display_name="Sig Compliance Artifact",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_compliance_artifact_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        artifact_one = export_reconcile_compliance_status_artifact(chain_limit=50, include_json=True)
        artifact_two = export_reconcile_compliance_status_artifact(chain_limit=50, include_json=False)
        head = get_latest_reconcile_compliance_status_artifact_head()

        assert artifact_one["success"] is True
        assert artifact_two["success"] is True
        assert len(str(artifact_one.get("digest_sha256", ""))) == 64
        assert str(artifact_two.get("previous_digest", "")) == str(artifact_one.get("digest_sha256", ""))
        assert len(str(artifact_two.get("chain_digest", ""))) == 64
        assert head["success"] is True
        assert str(head.get("digest_sha256", "")) == str(artifact_two.get("digest_sha256", ""))

    def test_verify_reconcile_compliance_status_artifact_chain_ok_and_break(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Diag Compliance Chain Verify", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-compliance-chain@test.com",
            display_name="Sig Compliance Chain",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_compliance_chain_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-compliance-chain@test.com",
            display_name="Sig Compliance Chain",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_compliance_chain_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        art_one = export_reconcile_compliance_status_artifact(chain_limit=50, include_json=False)
        art_two = export_reconcile_compliance_status_artifact(chain_limit=50, include_json=False)
        assert art_one["success"] is True
        assert art_two["success"] is True

        verify_ok = verify_reconcile_compliance_status_artifact_chain(limit=50)
        assert verify_ok["success"] is True
        assert str(verify_ok.get("status", "")) == "ok"

        with tdb.get_tournament_connection() as conn:
            row = conn.execute(
                "SELECT metadata_json FROM tournament_events WHERE event_id = ?",
                (int(art_two.get("artifact_event_id", 0)),),
            ).fetchone()
            metadata = json.loads(str(row["metadata_json"] or "{}"))
            metadata["previous_digest"] = "bad_previous"
            conn.execute(
                "UPDATE tournament_events SET metadata_json = ? WHERE event_id = ?",
                (json.dumps(metadata), int(art_two.get("artifact_event_id", 0))),
            )
            conn.commit()

        verify_broken = verify_reconcile_compliance_status_artifact_chain(limit=50)
        assert verify_broken["success"] is True
        assert str(verify_broken.get("status", "")) == "broken"
        assert int(verify_broken.get("broken_links", 0)) >= 1

    def test_prune_reconcile_compliance_status_artifacts_dry_run_and_delete(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Diag Compliance Prune", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-compliance-prune@test.com",
            display_name="Sig Compliance Prune",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_compliance_prune_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-compliance-prune@test.com",
            display_name="Sig Compliance Prune",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_compliance_prune_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")
        artifact = export_reconcile_compliance_status_artifact(chain_limit=50, include_json=False)
        assert artifact["success"] is True

        with tdb.get_tournament_connection() as conn:
            conn.execute(
                "UPDATE tournament_events SET created_at = '2000-01-01 00:00:00' WHERE event_id = ?",
                (int(artifact.get("artifact_event_id", 0)),),
            )
            conn.commit()

        latest_artifact = export_reconcile_compliance_status_artifact(chain_limit=50, include_json=False)
        assert latest_artifact["success"] is True

        dry_run = prune_reconcile_compliance_status_artifacts(max_age_days=30, dry_run=True, keep_latest=1)
        assert dry_run["success"] is True
        assert int(dry_run.get("candidates", 0)) >= 1
        assert int(dry_run.get("deleted", 0)) == 0
        assert int(dry_run.get("keep_latest", 0)) == 1

        execute = prune_reconcile_compliance_status_artifacts(max_age_days=30, dry_run=False, keep_latest=1)
        assert execute["success"] is True
        assert int(execute.get("deleted", 0)) >= 1

    def test_verify_reconcile_compliance_chain_checkpoint_ok_and_history(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Diag Compliance Checkpoint", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-compliance-checkpoint@test.com",
            display_name="Sig Compliance Checkpoint",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_compliance_checkpoint_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-compliance-checkpoint@test.com",
            display_name="Sig Compliance Checkpoint",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_compliance_checkpoint_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        artifact = export_reconcile_compliance_status_artifact(chain_limit=50, include_json=False)
        checkpoint = create_reconcile_compliance_chain_checkpoint(
            label="compliance_verify_ok",
            expected_previous_digest=str(artifact.get("digest_sha256", "")),
            require_head=True,
        )
        assert checkpoint["success"] is True

        latest_checkpoint = get_latest_reconcile_compliance_chain_checkpoint()
        verify = verify_reconcile_compliance_chain_checkpoint(require_current_head=True, require_signature_payload=True)
        history = verify_reconcile_compliance_chain_checkpoint_history(limit=50, require_signature_payload=True)
        assert latest_checkpoint["success"] is True
        assert verify["success"] is True
        assert str(verify.get("status", "")) == "ok"
        assert bool((verify.get("signature_verification") or {}).get("match", False)) is True
        assert history["success"] is True
        assert str(history.get("status", "")) == "ok"

    def test_evaluate_reconcile_compliance_readiness_scores_and_event(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        monkeypatch.setenv(
            "TOURNAMENT_RECONCILE_COMPLIANCE_POLICIES_JSON",
            json.dumps(
                {
                    "integration_test": {
                        "chain_limit": 50,
                        "warning_threshold": 95,
                        "error_threshold": 90,
                        "monitor_transition": True,
                        "transition_cooldown_minutes": 60,
                        "issue_penalty": 40,
                        "warning_penalty": 5,
                        "check_failure_penalty_default": 9,
                        "check_failure_penalties": {
                            "signing_key_ready": 22,
                        },
                    }
                }
            ),
        )
        monkeypatch.setenv("TOURNAMENT_RECONCILE_ALERT_EMAILS", "alerts@test.com")
        tid = create_tournament("Diag Compliance Readiness", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-compliance-readiness@test.com",
            display_name="Sig Compliance Readiness",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_compliance_readiness_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-compliance-readiness@test.com",
            display_name="Sig Compliance Readiness",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_compliance_readiness_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        export_reconcile_compliance_status_artifact(chain_limit=50, include_json=False)
        create_reconcile_compliance_chain_checkpoint(
            label="readiness_checkpoint",
            require_head=True,
        )

        policies = get_reconcile_compliance_readiness_policies()
        assert policies["success"] is True
        assert "integration_test" in dict(policies.get("policies") or {})
        integration_policy = dict((policies.get("policies") or {}).get("integration_test") or {})
        assert int(integration_policy.get("issue_penalty", 0) or 0) == 40
        assert int(integration_policy.get("warning_penalty", 0) or 0) == 5
        assert int(integration_policy.get("transition_cooldown_minutes", 0) or 0) == 60

        snap_one = export_reconcile_compliance_readiness_policy_snapshot(
            policy_name="integration_test",
            include_registry=True,
            persist_event=True,
        )
        snap_two = export_reconcile_compliance_readiness_policy_snapshot(
            policy_name="integration_test",
            include_registry=False,
            persist_event=True,
        )
        snap_head = get_latest_reconcile_compliance_readiness_policy_snapshot_head(policy_name="integration_test")
        snap_chain = verify_reconcile_compliance_readiness_policy_snapshot_chain(limit=50, policy_name="integration_test")
        assert snap_one["success"] is True
        assert snap_two["success"] is True
        assert len(str(snap_one.get("digest_sha256", ""))) == 64
        assert str(snap_two.get("previous_digest", "")) == str(snap_one.get("digest_sha256", ""))
        assert snap_head["success"] is True
        assert str(snap_head.get("digest_sha256", "")) == str(snap_two.get("digest_sha256", ""))
        assert snap_chain["success"] is True
        assert str(snap_chain.get("status", "")) == "ok"

        checkpoint = create_reconcile_compliance_readiness_policy_snapshot_checkpoint(
            policy_name="integration_test",
            label="integration_readiness_snapshot_checkpoint",
            require_head=True,
        )
        checkpoint_head = get_latest_reconcile_compliance_readiness_policy_snapshot_checkpoint(
            policy_name="integration_test",
        )
        checkpoint_verify = verify_reconcile_compliance_readiness_policy_snapshot_checkpoint(
            policy_name="integration_test",
            require_current_head=True,
            require_signature_payload=True,
        )
        checkpoint_history = verify_reconcile_compliance_readiness_policy_snapshot_checkpoint_history(
            limit=50,
            policy_name="integration_test",
            require_signature_payload=True,
        )
        assert checkpoint["success"] is True
        assert int(checkpoint.get("event_id", 0) or 0) > 0
        assert len(str(checkpoint.get("checkpoint_digest", ""))) == 64
        assert checkpoint_head["success"] is True
        assert int(checkpoint_head.get("event_id", 0) or 0) == int(checkpoint.get("event_id", 0) or 0)
        assert str(checkpoint_verify.get("status", "")) == "ok"
        assert str(checkpoint_history.get("status", "")) == "ok"

        readiness_artifact_one = export_reconcile_compliance_readiness_evaluation_artifact(
            policy_name="integration_test",
            chain_limit=50,
            warning_threshold=20,
            error_threshold=10,
            include_json=True,
            include_snapshot=True,
            persist_readiness_event=False,
            auto_chain=True,
            persist_event=True,
        )
        readiness_artifact_two = export_reconcile_compliance_readiness_evaluation_artifact(
            policy_name="integration_test",
            chain_limit=50,
            warning_threshold=20,
            error_threshold=10,
            include_json=False,
            include_snapshot=True,
            persist_readiness_event=False,
            auto_chain=True,
            persist_event=True,
        )
        readiness_artifact_head = get_latest_reconcile_compliance_readiness_evaluation_artifact_head(
            policy_name="integration_test",
        )
        readiness_artifact_chain = verify_reconcile_compliance_readiness_evaluation_artifact_chain(
            limit=50,
            policy_name="integration_test",
        )
        assert readiness_artifact_one["success"] is True
        assert readiness_artifact_two["success"] is True
        assert len(str(readiness_artifact_one.get("digest_sha256", ""))) == 64
        assert len(str(readiness_artifact_two.get("digest_sha256", ""))) == 64
        assert str(readiness_artifact_two.get("previous_digest", "")) == str(readiness_artifact_one.get("digest_sha256", ""))
        assert readiness_artifact_head["success"] is True
        assert str(readiness_artifact_head.get("digest_sha256", "")) == str(readiness_artifact_two.get("digest_sha256", ""))
        assert readiness_artifact_chain["success"] is True
        assert str(readiness_artifact_chain.get("status", "")) == "ok"

        readiness_prune = prune_reconcile_compliance_readiness_policy_snapshots(
            policy_name="integration_test",
            max_age_days=30,
            dry_run=True,
            keep_latest=1,
        )
        assert readiness_prune["success"] is True
        assert int(readiness_prune.get("candidates", 0) or 0) >= 0
        assert int(readiness_prune.get("deleted", 0) or 0) == 0
        assert int(readiness_prune.get("kept", 0) or 0) >= 0

        readiness = evaluate_reconcile_compliance_readiness(
            policy_name="integration_test",
            warning_threshold=20,
            error_threshold=10,
            persist_event=True,
            notify_users=True,
        )
        assert readiness["success"] is True
        assert str((readiness.get("policy") or {}).get("name", "")) == "integration_test"
        assert str(readiness.get("status", "")) in {"ready", "warning", "blocked"}
        assert 0 <= int(readiness.get("score", 0)) <= 100
        assert int(readiness.get("event_id", 0)) > 0
        assert bool((readiness.get("transition") or {}).get("checked", False)) is True
        assert int((readiness.get("policy") or {}).get("transition_cooldown_minutes", 0) or 0) == 60
        assert isinstance((readiness.get("score_breakdown") or {}).get("check_penalty_applied", {}), dict)

        with tdb.get_tournament_connection() as conn:
            latest_checkpoint = conn.execute(
                "SELECT event_id, metadata_json FROM tournament_events WHERE event_type = 'pending.reconcile.compliance_chain_checkpoint' ORDER BY event_id DESC LIMIT 1"
            ).fetchone()
            metadata = json.loads(str(latest_checkpoint["metadata_json"] or "{}"))
            payload = dict(metadata.get("payload") or {})
            original_head_digest = str((payload.get("head") or {}).get("digest_sha256", "") or "")
            payload["head"]["digest_sha256"] = "broken_digest_for_transition_test"
            metadata["payload"] = payload
            conn.execute(
                "UPDATE tournament_events SET metadata_json = ? WHERE event_id = ?",
                (json.dumps(metadata), int(latest_checkpoint["event_id"])),
            )
            conn.commit()

        readiness_changed = evaluate_reconcile_compliance_readiness(
            policy_name="integration_test",
            warning_threshold=20,
            error_threshold=10,
            persist_event=True,
            notify_users=True,
        )
        transition = dict(readiness_changed.get("transition") or {})
        assert transition.get("checked") is True
        assert transition.get("changed") is True
        assert int(transition.get("event_id", 0) or 0) > 0
        assert int(transition.get("notified", 0) or 0) >= 1

        with tdb.get_tournament_connection() as conn:
            latest_checkpoint = conn.execute(
                "SELECT event_id, metadata_json FROM tournament_events WHERE event_type = 'pending.reconcile.compliance_chain_checkpoint' ORDER BY event_id DESC LIMIT 1"
            ).fetchone()
            metadata = json.loads(str(latest_checkpoint["metadata_json"] or "{}"))
            payload = dict(metadata.get("payload") or {})
            payload["head"]["digest_sha256"] = original_head_digest
            metadata["payload"] = payload
            conn.execute(
                "UPDATE tournament_events SET metadata_json = ? WHERE event_id = ?",
                (json.dumps(metadata), int(latest_checkpoint["event_id"])),
            )
            conn.commit()

        readiness_cooldown_suppressed = evaluate_reconcile_compliance_readiness(
            policy_name="integration_test",
            warning_threshold=20,
            error_threshold=10,
            persist_event=True,
            notify_users=True,
        )
        cooldown_transition = dict(readiness_cooldown_suppressed.get("transition") or {})
        assert cooldown_transition.get("checked") is True
        assert cooldown_transition.get("changed") is True
        assert cooldown_transition.get("suppressed_by_cooldown") is True
        assert cooldown_transition.get("cooldown_active") is True
        assert int(cooldown_transition.get("event_id", 0) or 0) == 0

    def test_export_reconcile_compliance_status_envelope_contains_verify_payload(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Diag Compliance Envelope", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="sig-compliance-envelope@test.com",
            display_name="Sig Compliance Envelope",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_compliance_envelope_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="sig-compliance-envelope@test.com",
            display_name="Sig Compliance Envelope",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_sig_compliance_envelope_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        envelope = export_reconcile_compliance_status_envelope(
            chain_limit=50,
            include_json=False,
            auto_chain=True,
            persist_event=True,
            create_checkpoint=True,
            checkpoint_label="integration_envelope",
            require_current_head=False,
            require_signature_payload=True,
        )
        assert envelope["success"] is True
        assert int(envelope.get("envelope", {}).get("envelope_version", 0)) == 1
        verify_payload = dict(envelope.get("verify_payload") or {})
        assert len(str(verify_payload.get("artifact_digest_sha256", ""))) == 64
        assert int(verify_payload.get("checkpoint_event_id", 0)) > 0
        assert len(str(verify_payload.get("checkpoint_digest", ""))) == 64
        assert str(verify_payload.get("verification_status", "")) in {"ok", "stale", "broken", "empty"}

    def test_readiness_evaluation_artifact_prune_checkpoint_envelope(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Readiness Artifact Lifecycle", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="ra-lifecycle@test.com",
            display_name="RA Lifecycle",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_ra_lifecycle_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="ra-lifecycle@test.com",
            display_name="RA Lifecycle",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_ra_lifecycle_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        artifact_one = export_reconcile_compliance_readiness_evaluation_artifact(
            policy_name="default",
            chain_limit=50,
            include_json=False,
            include_snapshot=False,
            auto_chain=True,
            persist_event=True,
        )
        assert artifact_one["success"] is True

        artifact_two = export_reconcile_compliance_readiness_evaluation_artifact(
            policy_name="default",
            chain_limit=50,
            include_json=False,
            include_snapshot=False,
            auto_chain=True,
            persist_event=True,
        )
        assert artifact_two["success"] is True

        # Prune dry run
        prune_dry = prune_reconcile_compliance_readiness_evaluation_artifacts(
            policy_name="default",
            max_age_days=30,
            dry_run=True,
            keep_latest=1,
        )
        assert prune_dry["success"] is True
        assert int(prune_dry.get("deleted", 0) or 0) == 0

        # Checkpoint
        ckpt = create_reconcile_compliance_readiness_evaluation_artifact_checkpoint(
            policy_name="default",
            label="integration_test",
            note="integration test checkpoint",
            require_head=True,
        )
        assert ckpt["success"] is True
        assert int(ckpt.get("event_id", 0)) > 0
        assert len(str(ckpt.get("checkpoint_digest", ""))) == 64

        # Get latest checkpoint
        ckpt_head = get_latest_reconcile_compliance_readiness_evaluation_artifact_checkpoint(
            policy_name="default",
        )
        assert ckpt_head["success"] is True
        assert int(ckpt_head.get("event_id", 0)) == int(ckpt.get("event_id", 0))

        # Verify checkpoint
        verify_ckpt = verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint(
            policy_name="default",
            require_current_head=False,
            require_signature_payload=False,
        )
        assert str(verify_ckpt.get("status", "")) in {"ok", "stale"}

        # Verify checkpoint history
        history = verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint_history(
            limit=50,
            policy_name="default",
            require_signature_payload=False,
        )
        assert history["success"] is True
        assert int(history.get("ok", 0) or 0) >= 1

        # Envelope
        envelope = export_reconcile_compliance_readiness_evaluation_artifact_envelope(
            policy_name="default",
            chain_limit=50,
            include_json=False,
            include_snapshot=False,
            auto_chain=True,
            persist_event=True,
            create_checkpoint=True,
            checkpoint_label="integration_envelope",
            require_current_head=False,
            require_signature_payload=False,
        )
        assert envelope["success"] is True
        vp = dict(envelope.get("verify_payload") or {})
        assert len(str(vp.get("artifact_digest_sha256", ""))) == 64
        assert int(vp.get("checkpoint_event_id", 0)) > 0
        assert len(str(vp.get("checkpoint_digest", ""))) == 64
        assert str(vp.get("verification_status", "")) in {"ok", "stale", "broken", "empty"}

    def test_composite_governance_snapshot_lifecycle(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Composite Governance Lifecycle", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="cg-lifecycle@test.com",
            display_name="CG Lifecycle",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_cg_lifecycle_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="cg-lifecycle@test.com",
            display_name="CG Lifecycle",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_cg_lifecycle_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        export_reconcile_compliance_status_artifact(chain_limit=50, include_json=False, auto_chain=True, persist_event=True)
        export_reconcile_compliance_readiness_policy_snapshot(
            policy_name="default",
            include_registry=False,
            auto_chain=True,
            persist_event=True,
        )
        export_reconcile_compliance_readiness_evaluation_artifact(
            policy_name="default",
            chain_limit=50,
            include_json=False,
            include_snapshot=False,
            auto_chain=True,
            persist_event=True,
        )

        snap_one = export_reconcile_composite_governance_snapshot(
            policy_name="default",
            chain_limit=50,
            include_json=False,
            include_snapshot=False,
            auto_chain=True,
            persist_event=True,
        )
        assert snap_one["success"] is True

        snap_two = export_reconcile_composite_governance_snapshot(
            policy_name="default",
            chain_limit=50,
            include_json=False,
            include_snapshot=False,
            auto_chain=True,
            persist_event=True,
        )
        assert snap_two["success"] is True

        head = get_latest_reconcile_composite_governance_snapshot_head(policy_name="default")
        assert head["success"] is True
        assert len(str(head.get("digest_sha256", ""))) == 64

        chain_ok = verify_reconcile_composite_governance_snapshot_chain(limit=100, policy_name="default")
        assert chain_ok["success"] is True
        assert str(chain_ok.get("status", "")) in {"ok", "broken", "empty"}

        prune_dry = prune_reconcile_composite_governance_snapshots(
            max_age_days=30,
            dry_run=True,
            policy_name="default",
            keep_latest=1,
        )
        assert prune_dry["success"] is True
        assert int(prune_dry.get("deleted", 0) or 0) == 0

        ckpt = create_reconcile_composite_governance_snapshot_checkpoint(
            policy_name="default",
            label="integration_composite",
            note="integration composite snapshot checkpoint",
            require_head=True,
        )
        assert ckpt["success"] is True
        assert int(ckpt.get("event_id", 0) or 0) > 0
        assert len(str(ckpt.get("checkpoint_digest", ""))) == 64

        ckpt_head = get_latest_reconcile_composite_governance_snapshot_checkpoint(policy_name="default")
        assert ckpt_head["success"] is True
        assert int(ckpt_head.get("event_id", 0) or 0) == int(ckpt.get("event_id", 0) or 0)

        verify_ckpt = verify_reconcile_composite_governance_snapshot_checkpoint(
            policy_name="default",
            require_current_head=False,
            require_signature_payload=False,
        )
        assert str(verify_ckpt.get("status", "")) in {"ok", "stale", "broken", "empty"}

        history = verify_reconcile_composite_governance_snapshot_checkpoint_history(
            limit=100,
            policy_name="default",
            require_signature_payload=False,
        )
        assert history["success"] is True
        assert int(history.get("ok", 0) or 0) >= 1

    def test_composite_governance_snapshot_envelope(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Composite Envelope", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="cg-envelope@test.com",
            display_name="CG Envelope",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_cg_envelope_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="cg-envelope@test.com",
            display_name="CG Envelope",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_cg_envelope_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        envelope = export_reconcile_composite_governance_snapshot_envelope(
            policy_name="default",
            chain_limit=50,
            include_json=False,
            include_snapshot=False,
            auto_chain=True,
            persist_event=True,
            create_checkpoint=True,
            checkpoint_label="integration_composite_envelope",
            require_current_head=False,
            require_signature_payload=False,
        )
        assert envelope["success"] is True
        vp = dict(envelope.get("verify_payload") or {})
        assert len(str(vp.get("artifact_digest_sha256", ""))) == 64
        assert int(vp.get("checkpoint_event_id", 0) or 0) > 0
        assert len(str(vp.get("checkpoint_digest", ""))) == 64
        assert str(vp.get("verification_status", "")) in {"ok", "stale", "broken", "empty"}

    def test_governance_attestation_seal_lifecycle_and_diagnostics(self, isolated_db, monkeypatch):
        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")
        tid = create_tournament("Attestation Lifecycle", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="attestation-lifecycle@test.com",
            display_name="Attestation Lifecycle",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_attestation_lifecycle_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="attestation-lifecycle@test.com",
            display_name="Attestation Lifecycle",
            roster=_make_roster(paid=True),
            checkout_session_id="cs_attestation_lifecycle_1",
        )
        assert ok is True
        reconcile_pending_paid_entries(limit=20, max_actions=1, priority="oldest_first")

        seal = export_reconcile_governance_attestation_seal(
            policy_name="default",
            chain_limit=50,
            include_json=False,
            include_snapshot=False,
            auto_chain=True,
            persist_event=True,
        )
        assert seal["success"] is True
        assert len(str(seal.get("digest_sha256", ""))) == 64

        head = get_latest_reconcile_governance_attestation_seal_head(policy_name="default")
        assert head["success"] is True

        chain = verify_reconcile_governance_attestation_seal_chain(limit=100, policy_name="default")
        assert chain["success"] is True
        assert str(chain.get("status", "")) in {"ok", "broken", "empty"}

        prune_dry = prune_reconcile_governance_attestation_seals(
            max_age_days=30,
            dry_run=True,
            policy_name="default",
            keep_latest=1,
        )
        assert prune_dry["success"] is True
        assert int(prune_dry.get("deleted", 0) or 0) == 0

        ckpt = create_reconcile_governance_attestation_seal_checkpoint(
            policy_name="default",
            label="integration_attestation",
            note="integration attestation checkpoint",
            require_head=True,
        )
        assert ckpt["success"] is True
        assert int(ckpt.get("event_id", 0) or 0) > 0
        assert len(str(ckpt.get("checkpoint_digest", ""))) == 64

        ckpt_head = get_latest_reconcile_governance_attestation_seal_checkpoint(policy_name="default")
        assert ckpt_head["success"] is True

        ckpt_verify = verify_reconcile_governance_attestation_seal_checkpoint(
            policy_name="default",
            require_current_head=False,
            require_signature_payload=False,
        )
        assert str(ckpt_verify.get("status", "")) in {"ok", "stale", "broken", "empty"}

        history = verify_reconcile_governance_attestation_seal_checkpoint_history(
            limit=100,
            policy_name="default",
            require_signature_payload=False,
        )
        assert history["success"] is True
        assert int(history.get("ok", 0) or 0) >= 1

        diagnostics = get_reconcile_chain_repair_diagnostics(limit=100, policy_name="default")
        assert diagnostics["success"] is True
        assert "status" in diagnostics
        assert "recommended_actions" in diagnostics

        enforcement = evaluate_reconcile_governance_enforcement(
            action="financial_ops",
            policy_name="default",
            block_on_warning=False,
            require_attestation_seal=False,
        )
        assert enforcement["success"] is True
        assert "blocked" in enforcement
