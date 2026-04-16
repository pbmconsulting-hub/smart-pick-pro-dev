"""Integration tests for tournament.jobs orchestration."""

from datetime import date, datetime

from tournament.manager import list_tournaments
from tournament.jobs import run_tournament_jobs


def _mark_cancelled_and_resolved():
    """Prepare one cancelled and one resolved tournament row for job tests."""
    tournaments = list_tournaments()
    if len(tournaments) < 2:
        return None, None

    cancelled_tid = int(tournaments[0]["tournament_id"])
    resolved_tid = int(tournaments[1]["tournament_id"])
    return cancelled_tid, resolved_tid


class TestRunTournamentJobs:
    def test_default_run_returns_summary(self, isolated_db):
        summary = run_tournament_jobs(now=datetime(2099, 6, 3, 10, 0))
        assert isinstance(summary, dict)
        assert set(summary.keys()) == {
            "scheduled_created",
            "resolved_attempts",
            "refund_runs",
            "refund_total",
            "payout_runs",
            "payout_total",
            "payout_due_entries",
            "payout_due_tournaments_processed",
            "pending_expired",
            "pending_reconciled",
            "pending_reconcile_candidates",
            "pending_reconcile_attempted",
            "pending_reconcile_digest",
            "signature_receipts_prune_candidates",
            "signature_receipts_pruned",
            "signature_chain_checkpoint_event_id",
            "signature_chain_checkpoint_digest",
            "compliance_status_artifact_event_id",
            "compliance_status_artifact_digest",
            "compliance_artifacts_prune_candidates",
            "compliance_artifacts_pruned",
            "compliance_chain_checkpoint_event_id",
            "compliance_chain_checkpoint_digest",
            "compliance_readiness_policy_snapshot_event_id",
            "compliance_readiness_policy_snapshot_digest",
            "compliance_readiness_policy_snapshot_prune_candidates",
            "compliance_readiness_policy_snapshot_pruned",
            "compliance_readiness_policy_snapshot_checkpoint_event_id",
            "compliance_readiness_policy_snapshot_checkpoint_digest",
            "compliance_readiness_evaluation_artifact_event_id",
            "compliance_readiness_evaluation_artifact_digest",
            "compliance_readiness_evaluation_artifact_prune_candidates",
            "compliance_readiness_evaluation_artifact_pruned",
            "compliance_readiness_evaluation_artifact_checkpoint_event_id",
            "compliance_readiness_evaluation_artifact_checkpoint_digest",
            "compliance_readiness_evaluation_artifact_envelope_artifact_digest",
            "compliance_readiness_evaluation_artifact_envelope_digest",
            "composite_governance_snapshot_event_id",
            "composite_governance_snapshot_digest",
            "composite_governance_snapshot_prune_candidates",
            "composite_governance_snapshot_pruned",
            "composite_governance_snapshot_checkpoint_event_id",
            "composite_governance_snapshot_checkpoint_digest",
            "composite_governance_snapshot_envelope_artifact_digest",
            "composite_governance_snapshot_envelope_digest",
            "governance_attestation_seal_event_id",
            "governance_attestation_seal_digest",
            "governance_attestation_seal_prune_candidates",
            "governance_attestation_seal_pruned",
            "governance_attestation_seal_checkpoint_event_id",
            "governance_attestation_seal_checkpoint_digest",
            "governance_repair_diagnostics_status",
            "governance_repair_diagnostics_issue_count",
            "governance_repair_diagnostics_recommendation_count",
            "governance_enforcement_checked",
            "governance_enforcement_blocked",
            "governance_enforcement_reason",
            "compliance_readiness_status",
            "compliance_readiness_score",
            "compliance_readiness_event_id",
            "compliance_readiness_transition_changed",
            "compliance_readiness_transition_event_id",
        }

    def test_schedule_creation_creates_nine(self, isolated_db):
        summary = run_tournament_jobs(
            now=datetime(2099, 6, 3, 10, 0),
            run_schedule_create=True,
            run_resolve_locked=False,
            run_refunds=False,
            run_payouts=False,
        )
        assert summary["scheduled_created"] == 9

    def test_resolve_locked_attempts(self, isolated_db):
        run_tournament_jobs(
            now=datetime(2099, 6, 3, 10, 0),
            run_schedule_create=True,
            run_resolve_locked=False,
            run_refunds=False,
            run_payouts=False,
        )
        summary = run_tournament_jobs(
            now=datetime(2099, 6, 7, 21, 0),
            run_schedule_create=False,
            run_resolve_locked=True,
            run_refunds=False,
            run_payouts=False,
        )
        assert summary["resolved_attempts"] == 9

    def test_disable_all_jobs(self, isolated_db):
        summary = run_tournament_jobs(
            now=datetime(2099, 6, 3, 10, 0),
            run_schedule_create=False,
            run_resolve_locked=False,
            run_refunds=False,
            run_payouts=True,
            run_pending_cleanup=False,
            run_pending_reconcile=False,
        )
        assert summary["scheduled_created"] == 0
        assert summary["resolved_attempts"] == 0
        assert summary["refund_runs"] == 0
        assert summary["payout_runs"] == 0
        assert summary["pending_expired"] == 0
        assert summary["pending_reconciled"] == 0
        assert summary["pending_reconcile_candidates"] == 0
        assert summary["pending_reconcile_attempted"] == 0
        assert summary["pending_reconcile_digest"] == ""
        assert summary["signature_receipts_prune_candidates"] == 0
        assert summary["signature_receipts_pruned"] == 0
        assert summary["signature_chain_checkpoint_event_id"] == 0
        assert summary["signature_chain_checkpoint_digest"] == ""
        assert summary["compliance_status_artifact_event_id"] == 0
        assert summary["compliance_status_artifact_digest"] == ""
        assert summary["compliance_artifacts_prune_candidates"] == 0
        assert summary["compliance_artifacts_pruned"] == 0
        assert summary["compliance_chain_checkpoint_event_id"] == 0
        assert summary["compliance_chain_checkpoint_digest"] == ""
        assert summary["compliance_readiness_policy_snapshot_event_id"] == 0
        assert summary["compliance_readiness_policy_snapshot_digest"] == ""
        assert summary["compliance_readiness_policy_snapshot_prune_candidates"] == 0
        assert summary["compliance_readiness_policy_snapshot_pruned"] == 0
        assert summary["compliance_readiness_policy_snapshot_checkpoint_event_id"] == 0
        assert summary["compliance_readiness_policy_snapshot_checkpoint_digest"] == ""
        assert summary["compliance_readiness_evaluation_artifact_event_id"] == 0
        assert summary["compliance_readiness_evaluation_artifact_digest"] == ""
        assert summary["compliance_readiness_evaluation_artifact_prune_candidates"] == 0
        assert summary["compliance_readiness_evaluation_artifact_pruned"] == 0
        assert summary["compliance_readiness_evaluation_artifact_checkpoint_event_id"] == 0
        assert summary["compliance_readiness_evaluation_artifact_checkpoint_digest"] == ""
        assert summary["compliance_readiness_evaluation_artifact_envelope_artifact_digest"] == ""
        assert summary["compliance_readiness_evaluation_artifact_envelope_digest"] == ""
        assert summary["composite_governance_snapshot_event_id"] == 0
        assert summary["composite_governance_snapshot_digest"] == ""
        assert summary["composite_governance_snapshot_prune_candidates"] == 0
        assert summary["composite_governance_snapshot_pruned"] == 0
        assert summary["composite_governance_snapshot_checkpoint_event_id"] == 0
        assert summary["composite_governance_snapshot_checkpoint_digest"] == ""
        assert summary["composite_governance_snapshot_envelope_artifact_digest"] == ""
        assert summary["composite_governance_snapshot_envelope_digest"] == ""
        assert summary["governance_attestation_seal_event_id"] == 0
        assert summary["governance_attestation_seal_digest"] == ""
        assert summary["governance_attestation_seal_prune_candidates"] == 0
        assert summary["governance_attestation_seal_pruned"] == 0
        assert summary["governance_attestation_seal_checkpoint_event_id"] == 0
        assert summary["governance_attestation_seal_checkpoint_digest"] == ""
        assert summary["governance_repair_diagnostics_status"] == ""
        assert summary["governance_repair_diagnostics_issue_count"] == 0
        assert summary["governance_repair_diagnostics_recommendation_count"] == 0
        assert summary["governance_enforcement_checked"] is False
        assert summary["governance_enforcement_blocked"] is False
        assert summary["governance_enforcement_reason"] == ""
        assert summary["compliance_readiness_status"] == ""
        assert summary["compliance_readiness_score"] == 0
        assert summary["compliance_readiness_event_id"] == 0
        assert summary["compliance_readiness_transition_changed"] is False
        assert summary["compliance_readiness_transition_event_id"] == 0

    def test_pending_cleanup_expires_old_rows(self, isolated_db):
        import tournament.database as tdb

        with tdb.get_tournament_connection() as conn:
            conn.execute(
                """
                INSERT INTO pending_paid_entries
                    (checkout_session_id, tournament_id, user_email, display_name, roster_json,
                     status, payment_intent_id, created_at, updated_at)
                VALUES
                    ('cs_old_1', 100, 'old@test.com', 'Old', '[]', 'pending', '', '2099-06-01 00:00:00', '2099-06-01 00:00:00'),
                    ('cs_new_1', 101, 'new@test.com', 'New', '[]', 'pending', '', '2099-06-03 09:30:00', '2099-06-03 09:30:00')
                """
            )
            conn.commit()

        summary = run_tournament_jobs(
            now=datetime(2099, 6, 3, 10, 0),
            run_schedule_create=False,
            run_resolve_locked=False,
            run_refunds=False,
            run_payouts=True,
            run_pending_cleanup=True,
            run_pending_reconcile=False,
            pending_cleanup_max_age_hours=24,
        )
        assert summary["pending_expired"] == 1

        with tdb.get_tournament_connection() as conn:
            old_row = conn.execute(
                "SELECT status FROM pending_paid_entries WHERE checkout_session_id = 'cs_old_1'"
            ).fetchone()
            new_row = conn.execute(
                "SELECT status FROM pending_paid_entries WHERE checkout_session_id = 'cs_new_1'"
            ).fetchone()

        assert old_row["status"] == "expired"
        assert new_row["status"] == "pending"

    def test_pending_reconcile_marks_stale_rows(self, isolated_db):
        import tournament.database as tdb
        from tournament.manager import create_tournament, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("Jobs Reconcile", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="jobs-reconcile@test.com",
            display_name="Jobs Reconcile",
            roster=[
                {"player_id": f"A{i}", "player_name": f"Player {i}", "salary": 5500, "is_legend": False}
                for i in range(8)
            ]
            + [{"player_id": "L001", "player_name": "MJ", "salary": 15000, "is_legend": True}],
            checkout_session_id="cs_jobs_reconcile_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="jobs-reconcile@test.com",
            display_name="Jobs Reconcile",
            roster=[
                {"player_id": f"A{i}", "player_name": f"Player {i}", "salary": 5500, "is_legend": False}
                for i in range(8)
            ]
            + [{"player_id": "L001", "player_name": "MJ", "salary": 15000, "is_legend": True}],
            checkout_session_id="cs_jobs_reconcile_1",
        )
        assert ok is True

        summary = run_tournament_jobs(
            now=datetime(2099, 6, 3, 10, 0),
            run_schedule_create=False,
            run_resolve_locked=False,
            run_refunds=False,
            run_payouts=False,
            run_pending_cleanup=False,
            run_pending_reconcile=True,
            pending_reconcile_limit=20,
        )
        assert summary["pending_reconciled"] == 1
        assert summary["pending_reconcile_candidates"] >= 1
        assert summary["pending_reconcile_attempted"] >= 1
        assert len(str(summary["pending_reconcile_digest"])) == 64

        with tdb.get_tournament_connection() as conn:
            row = conn.execute(
                "SELECT status FROM pending_paid_entries WHERE checkout_session_id = 'cs_jobs_reconcile_1'"
            ).fetchone()
        assert row is not None
        assert row["status"] == "finalized"

    def test_pending_reconcile_dry_run_no_mutation(self, isolated_db):
        import tournament.database as tdb
        from tournament.manager import create_tournament, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("Jobs Reconcile Dry", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="jobs-reconcile-dry@test.com",
            display_name="Jobs Reconcile Dry",
            roster=[
                {"player_id": f"A{i}", "player_name": f"Player {i}", "salary": 5500, "is_legend": False}
                for i in range(8)
            ]
            + [{"player_id": "L001", "player_name": "MJ", "salary": 15000, "is_legend": True}],
            checkout_session_id="cs_jobs_reconcile_dry_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="jobs-reconcile-dry@test.com",
            display_name="Jobs Reconcile Dry",
            roster=[
                {"player_id": f"A{i}", "player_name": f"Player {i}", "salary": 5500, "is_legend": False}
                for i in range(8)
            ]
            + [{"player_id": "L001", "player_name": "MJ", "salary": 15000, "is_legend": True}],
            checkout_session_id="cs_jobs_reconcile_dry_1",
        )
        assert ok is True

        summary = run_tournament_jobs(
            now=datetime(2099, 6, 3, 10, 0),
            run_schedule_create=False,
            run_resolve_locked=False,
            run_refunds=False,
            run_payouts=False,
            run_pending_cleanup=False,
            run_pending_reconcile=True,
            run_pending_reconcile_dry_run=True,
            pending_reconcile_limit=20,
        )
        assert summary["pending_reconcile_candidates"] >= 1
        assert summary["pending_reconciled"] == 0
        assert summary["pending_reconcile_attempted"] >= 1

        with tdb.get_tournament_connection() as conn:
            row = conn.execute(
                "SELECT status FROM pending_paid_entries WHERE checkout_session_id = 'cs_jobs_reconcile_dry_1'"
            ).fetchone()
        assert row is not None
        assert row["status"] == "pending"

    def test_pending_reconcile_max_actions_limits_attempts(self, isolated_db):
        from tournament.manager import create_tournament, save_pending_paid_entry, submit_paid_entry_after_checkout

        tid = create_tournament("Jobs Reconcile Cap", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        for sid in ("cs_jobs_cap_1", "cs_jobs_cap_2"):
            save_pending_paid_entry(
                tournament_id=tid,
                user_email=f"{sid}@test.com",
                display_name=sid,
                roster=[
                    {"player_id": f"A{i}", "player_name": f"Player {i}", "salary": 5500, "is_legend": False}
                    for i in range(8)
                ]
                + [{"player_id": "L001", "player_name": "MJ", "salary": 15000, "is_legend": True}],
                checkout_session_id=sid,
            )
            ok, _, _ = submit_paid_entry_after_checkout(
                tournament_id=tid,
                user_email=f"{sid}@test.com",
                display_name=sid,
                roster=[
                    {"player_id": f"A{i}", "player_name": f"Player {i}", "salary": 5500, "is_legend": False}
                    for i in range(8)
                ]
                + [{"player_id": "L001", "player_name": "MJ", "salary": 15000, "is_legend": True}],
                checkout_session_id=sid,
            )
            assert ok is True

        summary = run_tournament_jobs(
            now=datetime(2099, 6, 3, 10, 0),
            run_schedule_create=False,
            run_resolve_locked=False,
            run_refunds=False,
            run_payouts=False,
            run_pending_cleanup=False,
            run_pending_reconcile=True,
            pending_reconcile_limit=20,
            pending_reconcile_max_actions=1,
            pending_reconcile_priority="oldest_first",
        )
        assert summary["pending_reconcile_candidates"] >= 2
        assert summary["pending_reconcile_attempted"] == 1
        assert summary["pending_reconciled"] == 1

    def test_signature_receipts_prune_and_checkpoint_jobs(self, isolated_db, monkeypatch):
        import tournament.database as tdb
        from tournament.manager import create_reconcile_verification_signature_receipt, create_tournament, export_reconcile_signature_receipts_artifact, export_reconcile_verification_report, save_pending_paid_entry, submit_paid_entry_after_checkout

        monkeypatch.setenv("TOURNAMENT_RECONCILE_REPORT_SIGNING_KEY", "unit-test-key")

        tid = create_tournament("Jobs Signature Lifecycle", "Pro", 20.0, 2, 24, "2099-06-01T20:00:00")
        save_pending_paid_entry(
            tournament_id=tid,
            user_email="jobs-signature@test.com",
            display_name="Jobs Signature",
            roster=[
                {"player_id": f"A{i}", "player_name": f"Player {i}", "salary": 5500, "is_legend": False}
                for i in range(8)
            ]
            + [{"player_id": "L001", "player_name": "MJ", "salary": 15000, "is_legend": True}],
            checkout_session_id="cs_jobs_signature_1",
        )
        ok, _, _ = submit_paid_entry_after_checkout(
            tournament_id=tid,
            user_email="jobs-signature@test.com",
            display_name="Jobs Signature",
            roster=[
                {"player_id": f"A{i}", "player_name": f"Player {i}", "salary": 5500, "is_legend": False}
                for i in range(8)
            ]
            + [{"player_id": "L001", "player_name": "MJ", "salary": 15000, "is_legend": True}],
            checkout_session_id="cs_jobs_signature_1",
        )
        assert ok is True

        run_tournament_jobs(
            now=datetime(2099, 6, 3, 10, 0),
            run_schedule_create=False,
            run_resolve_locked=False,
            run_refunds=False,
            run_payouts=False,
            run_pending_cleanup=False,
            run_pending_reconcile=True,
            pending_reconcile_limit=20,
        )

        report_result = export_reconcile_verification_report(session_ids=["cs_jobs_signature_1"], scope="attempted")
        receipt = create_reconcile_verification_signature_receipt(
            report=dict(report_result.get("report") or {}),
            signature=str(report_result.get("signature", "")),
            signature_type=str(report_result.get("signature_type", "hmac_sha256")),
            actor_email="jobs-auditor@test.com",
            source="jobs_test",
        )
        assert receipt["success"] is True
        export_reconcile_signature_receipts_artifact(limit=50, outcome="all", include_csv=False)

        with tdb.get_tournament_connection() as conn:
            conn.execute(
                "UPDATE tournament_events SET created_at='2000-01-01 00:00:00' WHERE event_id = ?",
                (int(receipt.get("receipt_event_id", 0)),),
            )
            conn.commit()

        summary = run_tournament_jobs(
            now=datetime(2099, 6, 3, 10, 0),
            run_schedule_create=False,
            run_resolve_locked=False,
            run_refunds=False,
            run_payouts=True,
            run_pending_cleanup=False,
            run_pending_reconcile=False,
            run_signature_receipts_prune=True,
            run_signature_receipts_prune_dry_run=False,
            signature_receipts_prune_max_age_days=30,
            run_signature_chain_checkpoint=True,
            signature_chain_checkpoint_label="jobs_test_checkpoint",
            run_compliance_status_export=True,
            compliance_status_export_chain_limit=50,
            run_compliance_artifacts_prune=True,
            run_compliance_artifacts_prune_dry_run=False,
            compliance_artifacts_prune_max_age_days=30,
            compliance_artifacts_prune_keep_latest=1,
            run_compliance_chain_checkpoint=True,
            compliance_chain_checkpoint_label="jobs_test_compliance_checkpoint",
            run_compliance_readiness_policy_snapshot=True,
            compliance_readiness_policy_snapshot_include_registry=True,
            run_compliance_readiness_policy_snapshot_prune=True,
            run_compliance_readiness_policy_snapshot_prune_dry_run=False,
            compliance_readiness_policy_snapshot_prune_max_age_days=30,
            compliance_readiness_policy_snapshot_prune_keep_latest=1,
            run_compliance_readiness_policy_snapshot_checkpoint=True,
            compliance_readiness_policy_snapshot_checkpoint_label="jobs_test_readiness_checkpoint",
            run_compliance_readiness_evaluation_artifact_export=True,
            compliance_readiness_evaluation_artifact_include_json=True,
            compliance_readiness_evaluation_artifact_include_snapshot=True,
            run_compliance_readiness_check=True,
            compliance_readiness_policy_name="jobs",
            compliance_readiness_warning_threshold=80,
            compliance_readiness_error_threshold=60,
            compliance_readiness_transition_cooldown_minutes=0,
            run_compliance_readiness_persist_event=True,
            run_compliance_readiness_monitor_transition=True,
            run_compliance_readiness_notify_users=False,
        )
        assert int(summary["signature_receipts_pruned"]) >= 1
        assert int(summary["signature_chain_checkpoint_event_id"]) > 0
        assert len(str(summary["signature_chain_checkpoint_digest"])) == 64
        assert int(summary["compliance_status_artifact_event_id"]) > 0
        assert len(str(summary["compliance_status_artifact_digest"])) == 64
        assert int(summary["compliance_artifacts_prune_candidates"]) >= 0
        assert int(summary["compliance_artifacts_pruned"]) >= 0
        assert int(summary["compliance_chain_checkpoint_event_id"]) > 0
        assert len(str(summary["compliance_chain_checkpoint_digest"])) == 64
        assert int(summary["compliance_readiness_policy_snapshot_event_id"]) > 0
        assert len(str(summary["compliance_readiness_policy_snapshot_digest"])) == 64
        assert int(summary["compliance_readiness_policy_snapshot_prune_candidates"]) >= 0
        assert int(summary["compliance_readiness_policy_snapshot_pruned"]) >= 0
        assert int(summary["compliance_readiness_policy_snapshot_checkpoint_event_id"]) > 0
        assert len(str(summary["compliance_readiness_policy_snapshot_checkpoint_digest"])) == 64
        assert int(summary["compliance_readiness_evaluation_artifact_event_id"]) > 0
        assert len(str(summary["compliance_readiness_evaluation_artifact_digest"])) == 64
        assert str(summary["compliance_readiness_status"]) in {"ready", "warning", "blocked"}
        assert 0 <= int(summary["compliance_readiness_score"]) <= 100
        assert int(summary["compliance_readiness_event_id"]) > 0
        assert isinstance(summary["compliance_readiness_transition_changed"], bool)
        assert int(summary["compliance_readiness_transition_event_id"]) >= 0

    def test_compliance_readiness_evaluation_artifact_prune_checkpoint_envelope(self, isolated_db):
        summary = run_tournament_jobs(
            now=None,
            run_schedule_create=False,
            run_resolve_locked=False,
            run_refunds=False,
            run_payouts=True,
            run_pending_cleanup=False,
            run_pending_reconcile=False,
            run_compliance_status_export=True,
            compliance_status_export_chain_limit=50,
            run_compliance_readiness_evaluation_artifact_export=True,
            compliance_readiness_evaluation_artifact_include_json=False,
            compliance_readiness_evaluation_artifact_include_snapshot=False,
            run_compliance_readiness_evaluation_artifact_prune=True,
            run_compliance_readiness_evaluation_artifact_prune_dry_run=True,
            compliance_readiness_evaluation_artifact_prune_max_age_days=30,
            compliance_readiness_evaluation_artifact_prune_keep_latest=1,
            run_compliance_readiness_evaluation_artifact_checkpoint=True,
            compliance_readiness_evaluation_artifact_checkpoint_label="jobs_test_ra_checkpoint",
            run_compliance_readiness_evaluation_artifact_envelope=True,
            compliance_readiness_evaluation_artifact_envelope_checkpoint_label="jobs_test_ra_envelope",
            compliance_readiness_evaluation_artifact_envelope_require_current_head=False,
            compliance_readiness_evaluation_artifact_envelope_include_json=False,
            compliance_readiness_evaluation_artifact_envelope_include_snapshot=False,
            compliance_readiness_policy_name="jobs",
            compliance_readiness_warning_threshold=80,
            compliance_readiness_error_threshold=60,
        )
        assert int(summary["compliance_readiness_evaluation_artifact_event_id"]) > 0
        assert len(str(summary["compliance_readiness_evaluation_artifact_digest"])) == 64
        assert int(summary["compliance_readiness_evaluation_artifact_prune_candidates"]) >= 0
        assert int(summary["compliance_readiness_evaluation_artifact_pruned"]) == 0  # dry_run=True
        assert int(summary["compliance_readiness_evaluation_artifact_checkpoint_event_id"]) > 0
        assert len(str(summary["compliance_readiness_evaluation_artifact_checkpoint_digest"])) == 64
        assert len(str(summary["compliance_readiness_evaluation_artifact_envelope_artifact_digest"])) == 64
        assert len(str(summary["compliance_readiness_evaluation_artifact_envelope_digest"])) >= 0

    def test_composite_governance_snapshot_prune_checkpoint(self, isolated_db):
        summary = run_tournament_jobs(
            now=None,
            run_schedule_create=False,
            run_resolve_locked=False,
            run_refunds=False,
            run_payouts=False,
            run_pending_cleanup=False,
            run_pending_reconcile=False,
            run_compliance_status_export=True,
            compliance_status_export_chain_limit=50,
            run_compliance_readiness_policy_snapshot=True,
            compliance_readiness_policy_snapshot_include_registry=False,
            run_compliance_readiness_evaluation_artifact_export=True,
            compliance_readiness_evaluation_artifact_include_json=False,
            compliance_readiness_evaluation_artifact_include_snapshot=False,
            run_composite_governance_snapshot_export=True,
            composite_governance_snapshot_include_json=False,
            composite_governance_snapshot_include_snapshot=False,
            run_composite_governance_snapshot_prune=True,
            run_composite_governance_snapshot_prune_dry_run=True,
            composite_governance_snapshot_prune_max_age_days=30,
            composite_governance_snapshot_prune_keep_latest=1,
            run_composite_governance_snapshot_checkpoint=True,
            composite_governance_snapshot_checkpoint_label="jobs_test_composite_checkpoint",
            run_composite_governance_snapshot_envelope=True,
            composite_governance_snapshot_envelope_checkpoint_label="jobs_test_composite_envelope",
            composite_governance_snapshot_envelope_require_current_head=False,
            composite_governance_snapshot_envelope_include_json=False,
            composite_governance_snapshot_envelope_include_snapshot=False,
            compliance_readiness_policy_name="jobs",
            compliance_readiness_warning_threshold=80,
            compliance_readiness_error_threshold=60,
        )
        assert int(summary["composite_governance_snapshot_event_id"]) > 0
        assert len(str(summary["composite_governance_snapshot_digest"])) == 64
        assert int(summary["composite_governance_snapshot_prune_candidates"]) >= 0
        assert int(summary["composite_governance_snapshot_pruned"]) == 0
        assert int(summary["composite_governance_snapshot_checkpoint_event_id"]) > 0
        assert len(str(summary["composite_governance_snapshot_checkpoint_digest"])) == 64
        assert len(str(summary["composite_governance_snapshot_envelope_artifact_digest"])) == 64
        assert len(str(summary["composite_governance_snapshot_envelope_digest"])) == 64

    def test_governance_attestation_seal_prune_checkpoint_and_diagnostics(self, isolated_db):
        summary = run_tournament_jobs(
            now=None,
            run_schedule_create=False,
            run_resolve_locked=False,
            run_refunds=False,
            run_payouts=True,
            run_pending_cleanup=False,
            run_pending_reconcile=False,
            run_compliance_status_export=True,
            compliance_status_export_chain_limit=50,
            run_compliance_readiness_policy_snapshot=True,
            compliance_readiness_policy_snapshot_include_registry=False,
            run_compliance_readiness_evaluation_artifact_export=True,
            compliance_readiness_evaluation_artifact_include_json=False,
            compliance_readiness_evaluation_artifact_include_snapshot=False,
            run_composite_governance_snapshot_export=True,
            composite_governance_snapshot_include_json=False,
            composite_governance_snapshot_include_snapshot=False,
            run_governance_attestation_seal_export=True,
            governance_attestation_seal_include_json=False,
            governance_attestation_seal_include_snapshot=False,
            run_governance_attestation_seal_prune=True,
            run_governance_attestation_seal_prune_dry_run=True,
            governance_attestation_seal_prune_max_age_days=30,
            governance_attestation_seal_prune_keep_latest=1,
            run_governance_attestation_seal_checkpoint=True,
            governance_attestation_seal_checkpoint_label="jobs_test_attestation_checkpoint",
            run_governance_repair_diagnostics=True,
            enforce_governance_for_financial_ops=True,
            governance_enforcement_block_on_warning=False,
            governance_enforcement_require_attestation_seal=False,
            compliance_readiness_policy_name="jobs",
            compliance_readiness_warning_threshold=80,
            compliance_readiness_error_threshold=60,
        )
        assert int(summary["governance_attestation_seal_event_id"]) > 0
        assert len(str(summary["governance_attestation_seal_digest"])) == 64
        assert int(summary["governance_attestation_seal_prune_candidates"]) >= 0
        assert int(summary["governance_attestation_seal_pruned"]) == 0
        assert int(summary["governance_attestation_seal_checkpoint_event_id"]) > 0
        assert len(str(summary["governance_attestation_seal_checkpoint_digest"])) == 64
        assert str(summary["governance_repair_diagnostics_status"]) in {"ok", "warning", "error"}
        assert int(summary["governance_repair_diagnostics_issue_count"]) >= 0
        assert int(summary["governance_repair_diagnostics_recommendation_count"]) >= 0
        assert summary["governance_enforcement_checked"] is True
