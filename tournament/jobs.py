"""Standalone tournament jobs runner for scheduled automation."""

from __future__ import annotations

from datetime import datetime

from tournament.events import log_event
from tournament.manager import (
    create_reconcile_compliance_readiness_policy_snapshot_checkpoint,
    create_reconcile_compliance_chain_checkpoint,
    create_reconcile_signature_chain_checkpoint,
    create_reconcile_compliance_readiness_evaluation_artifact_checkpoint,
    evaluate_reconcile_compliance_readiness,
    export_reconcile_compliance_readiness_evaluation_artifact,
    export_reconcile_compliance_readiness_evaluation_artifact_envelope,
    expire_stale_pending_paid_entries,
    export_reconcile_compliance_readiness_policy_snapshot,
    export_reconcile_compliance_status_artifact,
    list_tournaments,
    prune_reconcile_compliance_readiness_policy_snapshots,
    prune_reconcile_compliance_readiness_evaluation_artifacts,
    prune_reconcile_compliance_status_artifacts,
    prune_reconcile_signature_receipts,
    reconcile_pending_paid_entries,
    export_reconcile_composite_governance_snapshot,
    export_reconcile_composite_governance_snapshot_envelope,
    prune_reconcile_composite_governance_snapshots,
    create_reconcile_composite_governance_snapshot_checkpoint,
    export_reconcile_governance_attestation_seal,
    prune_reconcile_governance_attestation_seals,
    create_reconcile_governance_attestation_seal_checkpoint,
    get_reconcile_chain_repair_diagnostics,
    evaluate_reconcile_governance_enforcement,
    process_due_payouts,
)
from tournament.payout_runner import (
    process_cancelled_tournament_refunds,
    process_resolved_tournament_payouts,
)
from tournament.scheduler import create_weekly_schedule, resolve_locked_tournaments


def run_tournament_jobs(
    *,
    now: datetime | None = None,
    run_schedule_create: bool = False,
    run_resolve_locked: bool = True,
    run_refunds: bool = True,
    run_payouts: bool = True,
    run_due_payouts_only: bool = False,
    payout_sla_hours: int = 24,
    payout_max_tournaments: int = 50,
    run_pending_cleanup: bool = True,
    run_pending_reconcile: bool = True,
    run_pending_reconcile_dry_run: bool = False,
    pending_cleanup_max_age_hours: int = 24,
    pending_reconcile_limit: int = 200,
    pending_reconcile_max_actions: int | None = None,
    pending_reconcile_priority: str = "paid_first_oldest",
    run_signature_receipts_prune: bool = False,
    run_signature_receipts_prune_dry_run: bool = True,
    signature_receipts_prune_max_age_days: int = 30,
    run_signature_chain_checkpoint: bool = False,
    signature_chain_checkpoint_label: str = "jobs",
    run_compliance_status_export: bool = False,
    compliance_status_export_chain_limit: int = 200,
    run_compliance_artifacts_prune: bool = False,
    run_compliance_artifacts_prune_dry_run: bool = True,
    compliance_artifacts_prune_max_age_days: int = 30,
    compliance_artifacts_prune_keep_latest: int | None = None,
    run_compliance_chain_checkpoint: bool = False,
    compliance_chain_checkpoint_label: str = "jobs",
    run_compliance_readiness_policy_snapshot: bool = False,
    compliance_readiness_policy_snapshot_include_registry: bool = False,
    run_compliance_readiness_policy_snapshot_prune: bool = False,
    run_compliance_readiness_policy_snapshot_prune_dry_run: bool = True,
    compliance_readiness_policy_snapshot_prune_max_age_days: int = 30,
    compliance_readiness_policy_snapshot_prune_keep_latest: int | None = None,
    run_compliance_readiness_policy_snapshot_checkpoint: bool = False,
    compliance_readiness_policy_snapshot_checkpoint_label: str = "jobs",
    run_compliance_readiness_evaluation_artifact_export: bool = False,
    compliance_readiness_evaluation_artifact_include_json: bool = False,
    compliance_readiness_evaluation_artifact_include_snapshot: bool = True,
    run_compliance_readiness_evaluation_artifact_prune: bool = False,
    run_compliance_readiness_evaluation_artifact_prune_dry_run: bool = True,
    compliance_readiness_evaluation_artifact_prune_max_age_days: int = 30,
    compliance_readiness_evaluation_artifact_prune_keep_latest: int | None = None,
    run_compliance_readiness_evaluation_artifact_checkpoint: bool = False,
    compliance_readiness_evaluation_artifact_checkpoint_label: str = "jobs",
    run_compliance_readiness_evaluation_artifact_envelope: bool = False,
    compliance_readiness_evaluation_artifact_envelope_checkpoint_label: str = "jobs",
    compliance_readiness_evaluation_artifact_envelope_require_current_head: bool = False,
    compliance_readiness_evaluation_artifact_envelope_include_json: bool = False,
    compliance_readiness_evaluation_artifact_envelope_include_snapshot: bool = True,
    run_composite_governance_snapshot_export: bool = False,
    composite_governance_snapshot_include_json: bool = False,
    composite_governance_snapshot_include_snapshot: bool = False,
    run_composite_governance_snapshot_prune: bool = False,
    run_composite_governance_snapshot_prune_dry_run: bool = True,
    composite_governance_snapshot_prune_max_age_days: int = 30,
    composite_governance_snapshot_prune_keep_latest: int | None = None,
    run_composite_governance_snapshot_checkpoint: bool = False,
    composite_governance_snapshot_checkpoint_label: str = "jobs",
    run_composite_governance_snapshot_envelope: bool = False,
    composite_governance_snapshot_envelope_checkpoint_label: str = "jobs",
    composite_governance_snapshot_envelope_require_current_head: bool = False,
    composite_governance_snapshot_envelope_include_json: bool = False,
    composite_governance_snapshot_envelope_include_snapshot: bool = False,
    run_governance_attestation_seal_export: bool = False,
    governance_attestation_seal_include_json: bool = False,
    governance_attestation_seal_include_snapshot: bool = False,
    run_governance_attestation_seal_prune: bool = False,
    run_governance_attestation_seal_prune_dry_run: bool = True,
    governance_attestation_seal_prune_max_age_days: int = 30,
    governance_attestation_seal_prune_keep_latest: int | None = None,
    run_governance_attestation_seal_checkpoint: bool = False,
    governance_attestation_seal_checkpoint_label: str = "jobs",
    run_governance_repair_diagnostics: bool = False,
    enforce_governance_for_financial_ops: bool = False,
    governance_enforcement_block_on_warning: bool = False,
    governance_enforcement_require_attestation_seal: bool = False,
    run_compliance_readiness_check: bool = False,
    compliance_readiness_policy_name: str = "jobs",
    compliance_readiness_warning_threshold: int = 80,
    compliance_readiness_error_threshold: int = 60,
    compliance_readiness_transition_cooldown_minutes: int = 0,
    run_compliance_readiness_persist_event: bool = True,
    run_compliance_readiness_monitor_transition: bool = False,
    run_compliance_readiness_notify_users: bool = False,
) -> dict:
    """Run standalone tournament operational jobs and return a summary."""
    summary = {
        "scheduled_created": 0,
        "resolved_attempts": 0,
        "refund_runs": 0,
        "refund_total": 0,
        "payout_runs": 0,
        "payout_total": 0,
        "payout_due_entries": 0,
        "payout_due_tournaments_processed": 0,
        "pending_expired": 0,
        "pending_reconciled": 0,
        "pending_reconcile_candidates": 0,
        "pending_reconcile_attempted": 0,
        "pending_reconcile_digest": "",
        "signature_receipts_prune_candidates": 0,
        "signature_receipts_pruned": 0,
        "signature_chain_checkpoint_event_id": 0,
        "signature_chain_checkpoint_digest": "",
        "compliance_status_artifact_event_id": 0,
        "compliance_status_artifact_digest": "",
        "compliance_artifacts_prune_candidates": 0,
        "compliance_artifacts_pruned": 0,
        "compliance_chain_checkpoint_event_id": 0,
        "compliance_chain_checkpoint_digest": "",
        "compliance_readiness_policy_snapshot_event_id": 0,
        "compliance_readiness_policy_snapshot_digest": "",
        "compliance_readiness_policy_snapshot_prune_candidates": 0,
        "compliance_readiness_policy_snapshot_pruned": 0,
        "compliance_readiness_policy_snapshot_checkpoint_event_id": 0,
        "compliance_readiness_policy_snapshot_checkpoint_digest": "",
        "compliance_readiness_evaluation_artifact_event_id": 0,
        "compliance_readiness_evaluation_artifact_digest": "",
        "compliance_readiness_evaluation_artifact_prune_candidates": 0,
        "compliance_readiness_evaluation_artifact_pruned": 0,
        "compliance_readiness_evaluation_artifact_checkpoint_event_id": 0,
        "compliance_readiness_evaluation_artifact_checkpoint_digest": "",
        "compliance_readiness_evaluation_artifact_envelope_artifact_digest": "",
        "compliance_readiness_evaluation_artifact_envelope_digest": "",
        "composite_governance_snapshot_event_id": 0,
        "composite_governance_snapshot_digest": "",
        "composite_governance_snapshot_prune_candidates": 0,
        "composite_governance_snapshot_pruned": 0,
        "composite_governance_snapshot_checkpoint_event_id": 0,
        "composite_governance_snapshot_checkpoint_digest": "",
        "composite_governance_snapshot_envelope_artifact_digest": "",
        "composite_governance_snapshot_envelope_digest": "",
        "governance_attestation_seal_event_id": 0,
        "governance_attestation_seal_digest": "",
        "governance_attestation_seal_prune_candidates": 0,
        "governance_attestation_seal_pruned": 0,
        "governance_attestation_seal_checkpoint_event_id": 0,
        "governance_attestation_seal_checkpoint_digest": "",
        "governance_repair_diagnostics_status": "",
        "governance_repair_diagnostics_issue_count": 0,
        "governance_repair_diagnostics_recommendation_count": 0,
        "governance_enforcement_checked": False,
        "governance_enforcement_blocked": False,
        "governance_enforcement_reason": "",
        "compliance_readiness_status": "",
        "compliance_readiness_score": 0,
        "compliance_readiness_event_id": 0,
        "compliance_readiness_transition_changed": False,
        "compliance_readiness_transition_event_id": 0,
    }

    if run_schedule_create:
        created = create_weekly_schedule(anchor_date=(now.date() if now else None))
        summary["scheduled_created"] = len(created)
        log_event(
            "jobs.schedule_create",
            f"Jobs created {len(created)} scheduled tournaments",
            metadata={"ids": created[:20]},
        )

    if run_resolve_locked:
        resolved = resolve_locked_tournaments(now=now)
        summary["resolved_attempts"] = len(resolved)
        log_event(
            "jobs.resolve_locked",
            f"Jobs resolve attempts: {len(resolved)}",
            metadata={"results": resolved[:20]},
        )

    governance_gate = {
        "checked": False,
        "blocked": False,
        "blocked_reasons": [],
    }
    if bool(enforce_governance_for_financial_ops) and (bool(run_refunds) or bool(run_payouts)):
        governance_gate = evaluate_reconcile_governance_enforcement(
            action="financial_ops",
            policy_name=str(compliance_readiness_policy_name or "jobs"),
            block_on_warning=bool(governance_enforcement_block_on_warning),
            require_attestation_seal=bool(governance_enforcement_require_attestation_seal),
        )
        summary["governance_enforcement_checked"] = True
        summary["governance_enforcement_blocked"] = bool(governance_gate.get("blocked", False))
        reasons = list(governance_gate.get("blocked_reasons") or [])
        summary["governance_enforcement_reason"] = ",".join(str(r) for r in reasons[:5])
        if bool(governance_gate.get("blocked", False)):
            log_event(
                "jobs.governance_blocked",
                "Financial ops blocked by governance enforcement",
                severity="warning",
                metadata={
                    "policy_name": str(compliance_readiness_policy_name or "jobs"),
                    "blocked_reasons": reasons,
                    "block_on_warning": bool(governance_enforcement_block_on_warning),
                    "require_attestation_seal": bool(governance_enforcement_require_attestation_seal),
                },
            )

    run_refunds_effective = bool(run_refunds) and not bool(governance_gate.get("blocked", False))
    run_payouts_effective = bool(run_payouts) and not bool(governance_gate.get("blocked", False))

    if run_refunds_effective:
        cancelled = list_tournaments(status="cancelled")
        for t in cancelled:
            result = process_cancelled_tournament_refunds(int(t["tournament_id"]))
            if result.get("success"):
                summary["refund_runs"] += 1
                summary["refund_total"] += int(result.get("refunded", 0))

    if run_payouts_effective:
        if bool(run_due_payouts_only):
            due_result = process_due_payouts(
                sla_hours=max(1, int(payout_sla_hours)),
                max_tournaments=max(1, int(payout_max_tournaments)),
                now=now,
            )
            if due_result.get("success", False):
                summary["payout_runs"] = int(due_result.get("processed_tournaments", 0) or 0)
                summary["payout_total"] = int(due_result.get("transferred", 0) or 0)
                summary["payout_due_entries"] = int(due_result.get("due_entries", 0) or 0)
                summary["payout_due_tournaments_processed"] = int(due_result.get("processed_tournaments", 0) or 0)
        else:
            resolved_tournaments = list_tournaments(status="resolved")
            for t in resolved_tournaments:
                result = process_resolved_tournament_payouts(int(t["tournament_id"]))
                if result.get("success"):
                    summary["payout_runs"] += 1
                    summary["payout_total"] += int(result.get("transferred", 0))

    if run_pending_cleanup:
        expired = expire_stale_pending_paid_entries(
            max_age_hours=int(pending_cleanup_max_age_hours),
            now=now,
        )
        summary["pending_expired"] = int(expired)

    if run_pending_reconcile:
        reconcile_result = reconcile_pending_paid_entries(
            limit=max(1, int(pending_reconcile_limit)),
            dry_run=bool(run_pending_reconcile_dry_run),
            max_actions=(None if pending_reconcile_max_actions is None else max(1, int(pending_reconcile_max_actions))),
            priority=str(pending_reconcile_priority or "paid_first_oldest"),
        )
        summary["pending_reconciled"] = int(reconcile_result.get("reconciled", 0) or 0)
        summary["pending_reconcile_candidates"] = int(reconcile_result.get("candidates", 0) or 0)
        summary["pending_reconcile_attempted"] = int(reconcile_result.get("attempted", 0) or 0)
        summary["pending_reconcile_digest"] = str(reconcile_result.get("attempted_sessions_sha256", "") or "")

    if run_signature_receipts_prune:
        prune_result = prune_reconcile_signature_receipts(
            max_age_days=max(1, int(signature_receipts_prune_max_age_days)),
            dry_run=bool(run_signature_receipts_prune_dry_run),
            now=now,
        )
        summary["signature_receipts_prune_candidates"] = int(prune_result.get("candidates", 0) or 0)
        summary["signature_receipts_pruned"] = int(prune_result.get("deleted", 0) or 0)

    if run_signature_chain_checkpoint:
        checkpoint = create_reconcile_signature_chain_checkpoint(
            label=str(signature_chain_checkpoint_label or "jobs"),
            note="Scheduled jobs checkpoint",
            require_head=False,
        )
        if checkpoint.get("success", False):
            summary["signature_chain_checkpoint_event_id"] = int(checkpoint.get("event_id", 0) or 0)
            summary["signature_chain_checkpoint_digest"] = str(checkpoint.get("checkpoint_digest", "") or "")

    if run_compliance_status_export:
        compliance_artifact = export_reconcile_compliance_status_artifact(
            chain_limit=max(1, int(compliance_status_export_chain_limit)),
            include_json=False,
            auto_chain=True,
            persist_event=True,
        )
        if compliance_artifact.get("success", False):
            summary["compliance_status_artifact_event_id"] = int(compliance_artifact.get("artifact_event_id", 0) or 0)
            summary["compliance_status_artifact_digest"] = str(compliance_artifact.get("digest_sha256", "") or "")

    if run_compliance_artifacts_prune:
        prune_result = prune_reconcile_compliance_status_artifacts(
            max_age_days=max(1, int(compliance_artifacts_prune_max_age_days)),
            dry_run=bool(run_compliance_artifacts_prune_dry_run),
            keep_latest=(None if compliance_artifacts_prune_keep_latest is None else max(0, int(compliance_artifacts_prune_keep_latest))),
            now=now,
        )
        summary["compliance_artifacts_prune_candidates"] = int(prune_result.get("candidates", 0) or 0)
        summary["compliance_artifacts_pruned"] = int(prune_result.get("deleted", 0) or 0)

    if run_compliance_chain_checkpoint:
        checkpoint = create_reconcile_compliance_chain_checkpoint(
            label=str(compliance_chain_checkpoint_label or "jobs"),
            note="Scheduled jobs compliance checkpoint",
            require_head=False,
        )
        if checkpoint.get("success", False):
            summary["compliance_chain_checkpoint_event_id"] = int(checkpoint.get("event_id", 0) or 0)
            summary["compliance_chain_checkpoint_digest"] = str(checkpoint.get("checkpoint_digest", "") or "")

    if run_compliance_readiness_policy_snapshot:
        snapshot = export_reconcile_compliance_readiness_policy_snapshot(
            policy_name=str(compliance_readiness_policy_name or "jobs"),
            include_registry=bool(compliance_readiness_policy_snapshot_include_registry),
            auto_chain=True,
            persist_event=True,
        )
        if snapshot.get("success", False):
            summary["compliance_readiness_policy_snapshot_event_id"] = int(snapshot.get("snapshot_event_id", 0) or 0)
            summary["compliance_readiness_policy_snapshot_digest"] = str(snapshot.get("digest_sha256", "") or "")

    if run_compliance_readiness_policy_snapshot_prune:
        prune_result = prune_reconcile_compliance_readiness_policy_snapshots(
            max_age_days=max(1, int(compliance_readiness_policy_snapshot_prune_max_age_days)),
            dry_run=bool(run_compliance_readiness_policy_snapshot_prune_dry_run),
            policy_name=str(compliance_readiness_policy_name or "jobs"),
            keep_latest=(None if compliance_readiness_policy_snapshot_prune_keep_latest is None else max(0, int(compliance_readiness_policy_snapshot_prune_keep_latest))),
            now=now,
        )
        summary["compliance_readiness_policy_snapshot_prune_candidates"] = int(prune_result.get("candidates", 0) or 0)
        summary["compliance_readiness_policy_snapshot_pruned"] = int(prune_result.get("deleted", 0) or 0)

    if run_compliance_readiness_policy_snapshot_checkpoint:
        checkpoint = create_reconcile_compliance_readiness_policy_snapshot_checkpoint(
            policy_name=str(compliance_readiness_policy_name or "jobs"),
            label=str(compliance_readiness_policy_snapshot_checkpoint_label or "jobs"),
            note="Scheduled jobs readiness policy snapshot checkpoint",
            require_head=False,
        )
        if checkpoint.get("success", False):
            summary["compliance_readiness_policy_snapshot_checkpoint_event_id"] = int(checkpoint.get("event_id", 0) or 0)
            summary["compliance_readiness_policy_snapshot_checkpoint_digest"] = str(checkpoint.get("checkpoint_digest", "") or "")

    if run_compliance_readiness_evaluation_artifact_export:
        readiness_artifact = export_reconcile_compliance_readiness_evaluation_artifact(
            policy_name=str(compliance_readiness_policy_name or "jobs"),
            chain_limit=max(1, int(compliance_status_export_chain_limit)),
            warning_threshold=max(0, min(100, int(compliance_readiness_warning_threshold))),
            error_threshold=max(0, min(100, int(compliance_readiness_error_threshold))),
            include_json=bool(compliance_readiness_evaluation_artifact_include_json),
            include_snapshot=bool(compliance_readiness_evaluation_artifact_include_snapshot),
            persist_readiness_event=False,
            auto_chain=True,
            persist_event=True,
        )
        if readiness_artifact.get("success", False):
            summary["compliance_readiness_evaluation_artifact_event_id"] = int(readiness_artifact.get("artifact_event_id", 0) or 0)
            summary["compliance_readiness_evaluation_artifact_digest"] = str(readiness_artifact.get("digest_sha256", "") or "")

    if run_compliance_readiness_evaluation_artifact_prune:
        prune_result = prune_reconcile_compliance_readiness_evaluation_artifacts(
            max_age_days=max(1, int(compliance_readiness_evaluation_artifact_prune_max_age_days)),
            dry_run=bool(run_compliance_readiness_evaluation_artifact_prune_dry_run),
            policy_name=str(compliance_readiness_policy_name or "jobs"),
            keep_latest=(None if compliance_readiness_evaluation_artifact_prune_keep_latest is None else max(0, int(compliance_readiness_evaluation_artifact_prune_keep_latest))),
            now=now,
        )
        summary["compliance_readiness_evaluation_artifact_prune_candidates"] = int(prune_result.get("candidates", 0) or 0)
        summary["compliance_readiness_evaluation_artifact_pruned"] = int(prune_result.get("deleted", 0) or 0)

    if run_compliance_readiness_evaluation_artifact_checkpoint:
        checkpoint = create_reconcile_compliance_readiness_evaluation_artifact_checkpoint(
            policy_name=str(compliance_readiness_policy_name or "jobs"),
            label=str(compliance_readiness_evaluation_artifact_checkpoint_label or "jobs"),
            note="Scheduled jobs readiness evaluation artifact checkpoint",
            require_head=False,
        )
        if checkpoint.get("success", False):
            summary["compliance_readiness_evaluation_artifact_checkpoint_event_id"] = int(checkpoint.get("event_id", 0) or 0)
            summary["compliance_readiness_evaluation_artifact_checkpoint_digest"] = str(checkpoint.get("checkpoint_digest", "") or "")

    if run_compliance_readiness_evaluation_artifact_envelope:
        envelope = export_reconcile_compliance_readiness_evaluation_artifact_envelope(
            policy_name=str(compliance_readiness_policy_name or "jobs"),
            chain_limit=max(1, int(compliance_status_export_chain_limit)),
            warning_threshold=max(0, min(100, int(compliance_readiness_warning_threshold))),
            error_threshold=max(0, min(100, int(compliance_readiness_error_threshold))),
            include_json=bool(compliance_readiness_evaluation_artifact_envelope_include_json),
            include_snapshot=bool(compliance_readiness_evaluation_artifact_envelope_include_snapshot),
            persist_readiness_event=False,
            auto_chain=True,
            persist_event=True,
            create_checkpoint=True,
            checkpoint_label=str(compliance_readiness_evaluation_artifact_envelope_checkpoint_label or "jobs"),
            checkpoint_note="Scheduled jobs evaluation artifact envelope checkpoint",
            require_current_head=bool(compliance_readiness_evaluation_artifact_envelope_require_current_head),
            require_signature_payload=False,
        )
        if envelope.get("success", False):
            vp = dict(envelope.get("verify_payload") or {})
            summary["compliance_readiness_evaluation_artifact_envelope_artifact_digest"] = str(vp.get("artifact_digest_sha256", "") or "")
            summary["compliance_readiness_evaluation_artifact_envelope_digest"] = str(envelope.get("envelope_digest_sha256", "") or "")

    if run_composite_governance_snapshot_export:
        composite = export_reconcile_composite_governance_snapshot(
            policy_name=str(compliance_readiness_policy_name or "jobs"),
            chain_limit=max(1, int(compliance_status_export_chain_limit)),
            warning_threshold=max(0, min(100, int(compliance_readiness_warning_threshold))),
            error_threshold=max(0, min(100, int(compliance_readiness_error_threshold))),
            include_json=bool(composite_governance_snapshot_include_json),
            include_snapshot=bool(composite_governance_snapshot_include_snapshot),
            auto_chain=True,
            persist_event=True,
        )
        if composite.get("success", False):
            summary["composite_governance_snapshot_event_id"] = int(composite.get("snapshot_event_id", 0) or 0)
            summary["composite_governance_snapshot_digest"] = str(composite.get("digest_sha256", "") or "")

    if run_composite_governance_snapshot_prune:
        prune_result = prune_reconcile_composite_governance_snapshots(
            max_age_days=max(1, int(composite_governance_snapshot_prune_max_age_days)),
            dry_run=bool(run_composite_governance_snapshot_prune_dry_run),
            policy_name=str(compliance_readiness_policy_name or "jobs"),
            keep_latest=(None if composite_governance_snapshot_prune_keep_latest is None else max(0, int(composite_governance_snapshot_prune_keep_latest))),
            now=now,
        )
        summary["composite_governance_snapshot_prune_candidates"] = int(prune_result.get("candidates", 0) or 0)
        summary["composite_governance_snapshot_pruned"] = int(prune_result.get("deleted", 0) or 0)

    if run_composite_governance_snapshot_checkpoint:
        checkpoint = create_reconcile_composite_governance_snapshot_checkpoint(
            policy_name=str(compliance_readiness_policy_name or "jobs"),
            label=str(composite_governance_snapshot_checkpoint_label or "jobs"),
            note="Scheduled jobs composite governance snapshot checkpoint",
            require_head=False,
        )
        if checkpoint.get("success", False):
            summary["composite_governance_snapshot_checkpoint_event_id"] = int(checkpoint.get("event_id", 0) or 0)
            summary["composite_governance_snapshot_checkpoint_digest"] = str(checkpoint.get("checkpoint_digest", "") or "")

    if run_composite_governance_snapshot_envelope:
        envelope = export_reconcile_composite_governance_snapshot_envelope(
            policy_name=str(compliance_readiness_policy_name or "jobs"),
            chain_limit=max(1, int(compliance_status_export_chain_limit)),
            warning_threshold=max(0, min(100, int(compliance_readiness_warning_threshold))),
            error_threshold=max(0, min(100, int(compliance_readiness_error_threshold))),
            include_json=bool(composite_governance_snapshot_envelope_include_json),
            include_snapshot=bool(composite_governance_snapshot_envelope_include_snapshot),
            auto_chain=True,
            persist_event=True,
            create_checkpoint=True,
            checkpoint_label=str(composite_governance_snapshot_envelope_checkpoint_label or "jobs"),
            checkpoint_note="Scheduled jobs composite governance envelope checkpoint",
            require_current_head=bool(composite_governance_snapshot_envelope_require_current_head),
            require_signature_payload=False,
        )
        if envelope.get("success", False):
            vp = dict(envelope.get("verify_payload") or {})
            summary["composite_governance_snapshot_envelope_artifact_digest"] = str(vp.get("artifact_digest_sha256", "") or "")
            summary["composite_governance_snapshot_envelope_digest"] = str(envelope.get("envelope_digest", "") or "")

    if run_governance_attestation_seal_export:
        seal = export_reconcile_governance_attestation_seal(
            policy_name=str(compliance_readiness_policy_name or "jobs"),
            chain_limit=max(1, int(compliance_status_export_chain_limit)),
            warning_threshold=max(0, min(100, int(compliance_readiness_warning_threshold))),
            error_threshold=max(0, min(100, int(compliance_readiness_error_threshold))),
            include_json=bool(governance_attestation_seal_include_json),
            include_snapshot=bool(governance_attestation_seal_include_snapshot),
            auto_chain=True,
            persist_event=True,
        )
        if seal.get("success", False):
            summary["governance_attestation_seal_event_id"] = int(seal.get("seal_event_id", 0) or 0)
            summary["governance_attestation_seal_digest"] = str(seal.get("digest_sha256", "") or "")

    if run_governance_attestation_seal_prune:
        prune_result = prune_reconcile_governance_attestation_seals(
            max_age_days=max(1, int(governance_attestation_seal_prune_max_age_days)),
            dry_run=bool(run_governance_attestation_seal_prune_dry_run),
            policy_name=str(compliance_readiness_policy_name or "jobs"),
            keep_latest=(None if governance_attestation_seal_prune_keep_latest is None else max(0, int(governance_attestation_seal_prune_keep_latest))),
            now=now,
        )
        summary["governance_attestation_seal_prune_candidates"] = int(prune_result.get("candidates", 0) or 0)
        summary["governance_attestation_seal_pruned"] = int(prune_result.get("deleted", 0) or 0)

    if run_governance_attestation_seal_checkpoint:
        checkpoint = create_reconcile_governance_attestation_seal_checkpoint(
            policy_name=str(compliance_readiness_policy_name or "jobs"),
            label=str(governance_attestation_seal_checkpoint_label or "jobs"),
            note="Scheduled jobs governance attestation seal checkpoint",
            require_head=False,
        )
        if checkpoint.get("success", False):
            summary["governance_attestation_seal_checkpoint_event_id"] = int(checkpoint.get("event_id", 0) or 0)
            summary["governance_attestation_seal_checkpoint_digest"] = str(checkpoint.get("checkpoint_digest", "") or "")

    if run_governance_repair_diagnostics:
        diag = get_reconcile_chain_repair_diagnostics(
            limit=max(1, int(compliance_status_export_chain_limit)),
            policy_name=str(compliance_readiness_policy_name or "jobs"),
        )
        summary["governance_repair_diagnostics_status"] = str(diag.get("status", "") or "")
        summary["governance_repair_diagnostics_issue_count"] = int(diag.get("issue_count", 0) or 0)
        summary["governance_repair_diagnostics_recommendation_count"] = int(diag.get("recommendation_count", 0) or 0)

    if run_compliance_readiness_check:
        readiness = evaluate_reconcile_compliance_readiness(
            chain_limit=max(1, int(compliance_status_export_chain_limit)),
            warning_threshold=max(0, min(100, int(compliance_readiness_warning_threshold))),
            error_threshold=max(0, min(100, int(compliance_readiness_error_threshold))),
            policy_name=str(compliance_readiness_policy_name or "jobs"),
            persist_event=bool(run_compliance_readiness_persist_event),
            monitor_transition=bool(run_compliance_readiness_monitor_transition),
            transition_cooldown_minutes=max(0, min(1440, int(compliance_readiness_transition_cooldown_minutes))),
            notify_users=bool(run_compliance_readiness_notify_users),
        )
        summary["compliance_readiness_status"] = str(readiness.get("status", "") or "")
        summary["compliance_readiness_score"] = int(readiness.get("score", 0) or 0)
        summary["compliance_readiness_event_id"] = int(readiness.get("event_id", 0) or 0)
        transition = dict(readiness.get("transition") or {})
        summary["compliance_readiness_transition_changed"] = bool(transition.get("changed", False))
        summary["compliance_readiness_transition_event_id"] = int(transition.get("event_id", 0) or 0)

    log_event("jobs.completed", "Tournament jobs run completed", metadata=summary)
    return summary
