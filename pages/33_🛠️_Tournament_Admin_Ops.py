import streamlit as st
import json

from tournament import (
    compute_reconcile_digest,
    create_reconcile_compliance_readiness_policy_snapshot_checkpoint,
    create_reconcile_compliance_chain_checkpoint,
    create_reconcile_signature_chain_checkpoint,
    create_reconcile_verification_signature_receipt,
    create_weekly_schedule,
    evaluate_reconcile_compliance_readiness,
    create_reconcile_compliance_readiness_evaluation_artifact_checkpoint,
    export_reconcile_compliance_readiness_evaluation_artifact,
    export_reconcile_compliance_readiness_evaluation_artifact_envelope,
    export_reconcile_composite_governance_snapshot_envelope,
        create_reconcile_composite_governance_snapshot_checkpoint,
        export_reconcile_composite_governance_snapshot,
        create_reconcile_governance_attestation_seal_checkpoint,
        export_reconcile_governance_attestation_seal,
    export_reconcile_compliance_readiness_policy_snapshot,
    get_reconcile_compliance_readiness_policies,
    get_latest_reconcile_compliance_readiness_evaluation_artifact_checkpoint,
    get_latest_reconcile_compliance_readiness_evaluation_artifact_head,
    get_latest_reconcile_compliance_readiness_policy_snapshot_checkpoint,
    get_latest_reconcile_compliance_readiness_policy_snapshot_head,
        get_latest_reconcile_composite_governance_snapshot_checkpoint,
        get_latest_reconcile_composite_governance_snapshot_head,
        get_latest_reconcile_governance_attestation_seal_checkpoint,
        get_latest_reconcile_governance_attestation_seal_head,
        get_reconcile_chain_repair_diagnostics,
    export_reconcile_compliance_status_envelope,
    export_reconcile_compliance_status_artifact,
    export_reconcile_signature_receipts_artifact,
    export_reconcile_verification_envelope,
    finalize_pending_paid_entry,
    export_reconcile_verification_report,
    get_reconcile_compliance_status,
    get_latest_reconcile_compliance_status_artifact_head,
    get_latest_reconcile_compliance_chain_checkpoint,
    get_latest_reconcile_signature_receipts_artifact_head,
    get_latest_reconcile_summary_event,
    get_reconcile_signing_key_registry_status,
    list_pending_paid_entries,
    list_reconcile_signature_receipts,
    list_tournaments,
    list_due_payout_entries,
    list_season_lp_leaderboard,
    distribute_season_end_rewards,
    qualify_for_championship,
    create_user_connect_onboarding,
    sync_user_connect_status_from_stripe,
    get_user_connect_status,
    evaluate_user_payout_eligibility,
    process_cancelled_tournament_refunds,
    process_resolved_tournament_payouts,
    prune_reconcile_compliance_status_artifacts,
    prune_reconcile_compliance_readiness_evaluation_artifacts,
    prune_reconcile_compliance_readiness_policy_snapshots,
        prune_reconcile_composite_governance_snapshots,
        prune_reconcile_governance_attestation_seals,
    prune_reconcile_signature_receipts,
    reconcile_pending_paid_entries,
    resolve_locked_tournaments,
    run_tournament_jobs,
    verify_reconcile_compliance_chain_checkpoint,
    verify_reconcile_compliance_chain_checkpoint_history,
    verify_reconcile_compliance_readiness_evaluation_artifact_chain,
    verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint,
    verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint_history,
    verify_reconcile_compliance_readiness_policy_snapshot_checkpoint,
    verify_reconcile_compliance_readiness_policy_snapshot_checkpoint_history,
    verify_reconcile_compliance_readiness_policy_snapshot_chain,
        verify_reconcile_composite_governance_snapshot_chain,
        verify_reconcile_composite_governance_snapshot_checkpoint,
        verify_reconcile_composite_governance_snapshot_checkpoint_history,
        verify_reconcile_governance_attestation_seal_chain,
        verify_reconcile_governance_attestation_seal_checkpoint,
        verify_reconcile_governance_attestation_seal_checkpoint_history,
    verify_reconcile_digest,
    verify_reconcile_signature_chain_checkpoint_history,
    verify_reconcile_signature_chain_checkpoint,
    verify_reconcile_compliance_status_artifact_chain,
    verify_reconcile_signature_receipts_artifact_chain,
    verify_reconcile_digest_for_event,
    verify_reconcile_digest_for_latest_event,
    verify_reconcile_verification_report_signature,
    evaluate_reconcile_governance_enforcement,
)
from tournament.events import list_events

st.set_page_config(page_title="Tournament Admin Ops", page_icon="🛠️", layout="wide")
st.title("🛠️ Tournament Admin Ops (Standalone)")
st.caption("Runs scheduler, resolve, refund, and payout jobs against isolated tournament DB.")

c1, c2, c3 = st.columns(3)
with c1:
    if st.button("Create This Week Schedule", use_container_width=True):
        ids = create_weekly_schedule()
        st.success(f"Created {len(ids)} tournaments")
with c2:
    if st.button("Resolve Locked Now", use_container_width=True):
        results = resolve_locked_tournaments()
        st.success(f"Resolve attempts: {len(results)}")
with c3:
    st.info("Use controls below for refunds and payouts")

st.subheader("Jobs Runner")
j1, j2, j3, j4, j5, j6 = st.columns(6)
with j1:
    run_schedule_create = st.checkbox("Create Schedule", value=False)
with j2:
    run_resolve_locked = st.checkbox("Resolve Locked", value=True)
with j3:
    run_refunds = st.checkbox("Refund Cancelled", value=True)
with j4:
    run_payouts = st.checkbox("Payout Resolved", value=True)
with j5:
    run_pending_cleanup = st.checkbox("Cleanup Pending", value=True)
with j6:
    run_pending_reconcile = st.checkbox("Reconcile Pending", value=True)
run_pending_reconcile_dry_run = st.checkbox("Reconcile Dry Run", value=True)
run_signature_receipts_prune = st.checkbox("Prune Signature Receipts", value=False)
run_signature_receipts_prune_dry_run = st.checkbox("Prune Receipts Dry Run", value=True)
run_signature_chain_checkpoint = st.checkbox("Create Chain Checkpoint", value=False)
run_compliance_status_export = st.checkbox("Export Compliance Artifact", value=False)
run_compliance_artifacts_prune = st.checkbox("Prune Compliance Artifacts", value=False)
run_compliance_artifacts_prune_dry_run = st.checkbox("Prune Compliance Dry Run", value=True)
run_compliance_chain_checkpoint = st.checkbox("Create Compliance Chain Checkpoint", value=False)
run_compliance_readiness_policy_snapshot = st.checkbox("Export Readiness Policy Snapshot", value=False)
run_compliance_readiness_policy_snapshot_include_registry = st.checkbox("Snapshot Includes Policy Registry", value=False)
run_compliance_readiness_policy_snapshot_prune = st.checkbox("Prune Readiness Policy Snapshots", value=False)
run_compliance_readiness_policy_snapshot_prune_dry_run = st.checkbox("Readiness Snapshot Prune Dry Run", value=True)
run_compliance_readiness_policy_snapshot_checkpoint = st.checkbox("Create Readiness Snapshot Checkpoint", value=False)
run_compliance_readiness_evaluation_artifact_export = st.checkbox("Export Readiness Evaluation Artifact", value=False)
run_compliance_readiness_evaluation_artifact_include_json = st.checkbox("Readiness Artifact Includes JSON", value=False)
run_compliance_readiness_evaluation_artifact_include_snapshot = st.checkbox("Readiness Artifact Includes Snapshot", value=True)
run_compliance_readiness_evaluation_artifact_prune = st.checkbox("Prune Readiness Evaluation Artifacts", value=False)
run_compliance_readiness_evaluation_artifact_prune_dry_run = st.checkbox("Readiness Artifact Prune Dry Run", value=True)
run_compliance_readiness_evaluation_artifact_checkpoint = st.checkbox("Create Readiness Artifact Checkpoint", value=False)
run_compliance_readiness_evaluation_artifact_envelope = st.checkbox("Export Readiness Artifact Envelope", value=False)
run_composite_governance_snapshot_export = st.checkbox("Export Composite Governance Snapshot", value=False)
run_composite_governance_snapshot_prune = st.checkbox("Prune Composite Governance Snapshots", value=False)
run_composite_governance_snapshot_prune_dry_run = st.checkbox("Composite Snapshot Prune Dry Run", value=True)
run_composite_governance_snapshot_checkpoint = st.checkbox("Create Composite Snapshot Checkpoint", value=False)
run_composite_governance_snapshot_envelope = st.checkbox("Export Composite Snapshot Envelope", value=False)
run_governance_attestation_seal_export = st.checkbox("Export Governance Attestation Seal", value=False)
run_governance_attestation_seal_prune = st.checkbox("Prune Governance Attestation Seals", value=False)
run_governance_attestation_seal_prune_dry_run = st.checkbox("Attestation Seal Prune Dry Run", value=True)
run_governance_attestation_seal_checkpoint = st.checkbox("Create Attestation Seal Checkpoint", value=False)
run_governance_repair_diagnostics = st.checkbox("Run Governance Repair Diagnostics", value=False)
enforce_governance_for_financial_ops = st.checkbox("Enforce Governance For Refund/Payout", value=False)
governance_enforcement_block_on_warning = st.checkbox("Governance Enforcement Blocks On Warning", value=False)
governance_enforcement_require_attestation_seal = st.checkbox("Governance Enforcement Requires Attestation Seal", value=False)
run_compliance_readiness_check = st.checkbox("Evaluate Compliance Readiness", value=False)
run_compliance_readiness_persist_event = st.checkbox("Persist Readiness Event", value=True)
run_compliance_readiness_monitor_transition = st.checkbox("Monitor Readiness Transition", value=False)
run_compliance_readiness_notify_users = st.checkbox("Notify Readiness Transition Users", value=False)

cleanup_age_hours = st.slider(
    "Pending Cleanup Max Age (hours)",
    min_value=1,
    max_value=168,
    value=24,
    step=1,
)
reconcile_limit = st.slider(
    "Pending Reconcile Scan Limit",
    min_value=10,
    max_value=1000,
    value=200,
    step=10,
)
reconcile_max_actions = st.slider(
    "Pending Reconcile Max Actions (0 = no cap)",
    min_value=0,
    max_value=1000,
    value=100,
    step=10,
)
reconcile_priority = st.selectbox(
    "Pending Reconcile Priority",
    ["paid_first_oldest", "oldest_first", "newest_first"],
    index=0,
)
signature_receipts_prune_days = st.slider(
    "Signature Receipts Prune Max Age (days)",
    min_value=1,
    max_value=365,
    value=30,
    step=1,
)
compliance_chain_limit = st.slider(
    "Compliance Chain Limit",
    min_value=10,
    max_value=1000,
    value=200,
    step=10,
)
compliance_artifacts_prune_days = st.slider(
    "Compliance Artifacts Prune Max Age (days)",
    min_value=1,
    max_value=365,
    value=30,
    step=1,
)
compliance_artifacts_keep_latest = st.slider(
    "Compliance Artifacts Keep Latest (0 = disabled)",
    min_value=0,
    max_value=100,
    value=0,
    step=1,
)
compliance_readiness_warning_threshold = st.slider(
    "Compliance Readiness Warning Threshold",
    min_value=1,
    max_value=99,
    value=80,
    step=1,
)
compliance_readiness_error_threshold = st.slider(
    "Compliance Readiness Error Threshold",
    min_value=0,
    max_value=98,
    value=60,
    step=1,
)
compliance_readiness_transition_cooldown_minutes = st.slider(
    "Compliance Readiness Transition Cooldown (minutes)",
    min_value=0,
    max_value=1440,
    value=0,
    step=5,
)
compliance_readiness_policy_name = st.text_input("Compliance Readiness Policy Name", value="jobs")
compliance_readiness_snapshot_prune_days = st.slider(
    "Readiness Snapshot Prune Max Age (days)",
    min_value=1,
    max_value=365,
    value=30,
    step=1,
)
compliance_readiness_snapshot_keep_latest = st.slider(
    "Readiness Snapshot Keep Latest (0 = disabled)",
    min_value=0,
    max_value=100,
    value=0,
    step=1,
)
compliance_readiness_artifact_prune_days = st.slider(
    "Readiness Artifact Prune Max Age (days)",
    min_value=1,
    max_value=365,
    value=30,
    step=1,
)
compliance_readiness_artifact_keep_latest = st.slider(
    "Readiness Artifact Keep Latest (0 = disabled)",
    min_value=0,
    max_value=100,
    value=0,
    step=1,
)
composite_governance_snapshot_prune_days = st.slider(
    "Composite Snapshot Prune Max Age (days)",
    min_value=1,
    max_value=365,
    value=30,
    step=1,
)
composite_governance_snapshot_keep_latest = st.slider(
    "Composite Snapshot Keep Latest (0 = disabled)",
    min_value=0,
    max_value=100,
    value=0,
    step=1,
)
governance_attestation_seal_prune_days = st.slider(
    "Attestation Seal Prune Max Age (days)",
    min_value=1,
    max_value=365,
    value=30,
    step=1,
)
governance_attestation_seal_keep_latest = st.slider(
    "Attestation Seal Keep Latest (0 = disabled)",
    min_value=0,
    max_value=100,
    value=0,
    step=1,
)

if st.button("Run Tournament Jobs", type="primary", use_container_width=True):
    summary = run_tournament_jobs(
        run_schedule_create=run_schedule_create,
        run_resolve_locked=run_resolve_locked,
        run_refunds=run_refunds,
        run_payouts=run_payouts,
        run_pending_cleanup=run_pending_cleanup,
        run_pending_reconcile=run_pending_reconcile,
        run_pending_reconcile_dry_run=run_pending_reconcile_dry_run,
        pending_cleanup_max_age_hours=int(cleanup_age_hours),
        pending_reconcile_limit=int(reconcile_limit),
        pending_reconcile_max_actions=(None if int(reconcile_max_actions) <= 0 else int(reconcile_max_actions)),
        pending_reconcile_priority=str(reconcile_priority),
        run_signature_receipts_prune=bool(run_signature_receipts_prune),
        run_signature_receipts_prune_dry_run=bool(run_signature_receipts_prune_dry_run),
        signature_receipts_prune_max_age_days=int(signature_receipts_prune_days),
        run_signature_chain_checkpoint=bool(run_signature_chain_checkpoint),
        signature_chain_checkpoint_label="streamlit_jobs",
        run_compliance_status_export=bool(run_compliance_status_export),
        compliance_status_export_chain_limit=int(compliance_chain_limit),
        run_compliance_artifacts_prune=bool(run_compliance_artifacts_prune),
        run_compliance_artifacts_prune_dry_run=bool(run_compliance_artifacts_prune_dry_run),
        compliance_artifacts_prune_max_age_days=int(compliance_artifacts_prune_days),
        compliance_artifacts_prune_keep_latest=(None if int(compliance_artifacts_keep_latest) <= 0 else int(compliance_artifacts_keep_latest)),
        run_compliance_chain_checkpoint=bool(run_compliance_chain_checkpoint),
        compliance_chain_checkpoint_label="streamlit_compliance_jobs",
        run_compliance_readiness_policy_snapshot=bool(run_compliance_readiness_policy_snapshot),
        compliance_readiness_policy_snapshot_include_registry=bool(run_compliance_readiness_policy_snapshot_include_registry),
        run_compliance_readiness_policy_snapshot_prune=bool(run_compliance_readiness_policy_snapshot_prune),
        run_compliance_readiness_policy_snapshot_prune_dry_run=bool(run_compliance_readiness_policy_snapshot_prune_dry_run),
        compliance_readiness_policy_snapshot_prune_max_age_days=int(compliance_readiness_snapshot_prune_days),
        compliance_readiness_policy_snapshot_prune_keep_latest=(None if int(compliance_readiness_snapshot_keep_latest) <= 0 else int(compliance_readiness_snapshot_keep_latest)),
        run_compliance_readiness_policy_snapshot_checkpoint=bool(run_compliance_readiness_policy_snapshot_checkpoint),
        compliance_readiness_policy_snapshot_checkpoint_label="streamlit_readiness_snapshot_jobs",
        run_compliance_readiness_evaluation_artifact_export=bool(run_compliance_readiness_evaluation_artifact_export),
        compliance_readiness_evaluation_artifact_include_json=bool(run_compliance_readiness_evaluation_artifact_include_json),
        compliance_readiness_evaluation_artifact_include_snapshot=bool(run_compliance_readiness_evaluation_artifact_include_snapshot),
        run_compliance_readiness_evaluation_artifact_prune=bool(run_compliance_readiness_evaluation_artifact_prune),
        run_compliance_readiness_evaluation_artifact_prune_dry_run=bool(run_compliance_readiness_evaluation_artifact_prune_dry_run),
        compliance_readiness_evaluation_artifact_prune_max_age_days=int(compliance_readiness_artifact_prune_days),
        compliance_readiness_evaluation_artifact_prune_keep_latest=(None if int(compliance_readiness_artifact_keep_latest) <= 0 else int(compliance_readiness_artifact_keep_latest)),
        run_compliance_readiness_evaluation_artifact_checkpoint=bool(run_compliance_readiness_evaluation_artifact_checkpoint),
        compliance_readiness_evaluation_artifact_checkpoint_label="streamlit_readiness_artifact_jobs",
        run_compliance_readiness_evaluation_artifact_envelope=bool(run_compliance_readiness_evaluation_artifact_envelope),
        compliance_readiness_evaluation_artifact_envelope_checkpoint_label="streamlit_readiness_artifact_envelope",
        compliance_readiness_evaluation_artifact_envelope_require_current_head=False,
        compliance_readiness_evaluation_artifact_envelope_include_json=bool(run_compliance_readiness_evaluation_artifact_include_json),
        compliance_readiness_evaluation_artifact_envelope_include_snapshot=bool(run_compliance_readiness_evaluation_artifact_include_snapshot),
        run_composite_governance_snapshot_export=bool(run_composite_governance_snapshot_export),
        composite_governance_snapshot_include_json=bool(run_compliance_readiness_evaluation_artifact_include_json),
        composite_governance_snapshot_include_snapshot=bool(run_compliance_readiness_evaluation_artifact_include_snapshot),
        run_composite_governance_snapshot_prune=bool(run_composite_governance_snapshot_prune),
        run_composite_governance_snapshot_prune_dry_run=bool(run_composite_governance_snapshot_prune_dry_run),
        composite_governance_snapshot_prune_max_age_days=int(composite_governance_snapshot_prune_days),
        composite_governance_snapshot_prune_keep_latest=(None if int(composite_governance_snapshot_keep_latest) <= 0 else int(composite_governance_snapshot_keep_latest)),
        run_composite_governance_snapshot_checkpoint=bool(run_composite_governance_snapshot_checkpoint),
        composite_governance_snapshot_checkpoint_label="streamlit_composite_snapshot_jobs",
        run_composite_governance_snapshot_envelope=bool(run_composite_governance_snapshot_envelope),
        composite_governance_snapshot_envelope_checkpoint_label="streamlit_composite_snapshot_envelope",
        composite_governance_snapshot_envelope_require_current_head=False,
        composite_governance_snapshot_envelope_include_json=bool(run_compliance_readiness_evaluation_artifact_include_json),
        composite_governance_snapshot_envelope_include_snapshot=bool(run_compliance_readiness_evaluation_artifact_include_snapshot),
        run_governance_attestation_seal_export=bool(run_governance_attestation_seal_export),
        governance_attestation_seal_include_json=bool(run_compliance_readiness_evaluation_artifact_include_json),
        governance_attestation_seal_include_snapshot=False,
        run_governance_attestation_seal_prune=bool(run_governance_attestation_seal_prune),
        run_governance_attestation_seal_prune_dry_run=bool(run_governance_attestation_seal_prune_dry_run),
        governance_attestation_seal_prune_max_age_days=int(governance_attestation_seal_prune_days),
        governance_attestation_seal_prune_keep_latest=(None if int(governance_attestation_seal_keep_latest) <= 0 else int(governance_attestation_seal_keep_latest)),
        run_governance_attestation_seal_checkpoint=bool(run_governance_attestation_seal_checkpoint),
        governance_attestation_seal_checkpoint_label="streamlit_attestation_seal_jobs",
        run_governance_repair_diagnostics=bool(run_governance_repair_diagnostics),
        enforce_governance_for_financial_ops=bool(enforce_governance_for_financial_ops),
        governance_enforcement_block_on_warning=bool(governance_enforcement_block_on_warning),
        governance_enforcement_require_attestation_seal=bool(governance_enforcement_require_attestation_seal),
        run_compliance_readiness_check=bool(run_compliance_readiness_check),
        compliance_readiness_policy_name=str(compliance_readiness_policy_name or "jobs"),
        compliance_readiness_warning_threshold=int(compliance_readiness_warning_threshold),
        compliance_readiness_error_threshold=int(compliance_readiness_error_threshold),
        compliance_readiness_transition_cooldown_minutes=int(compliance_readiness_transition_cooldown_minutes),
        run_compliance_readiness_persist_event=bool(run_compliance_readiness_persist_event),
        run_compliance_readiness_monitor_transition=bool(run_compliance_readiness_monitor_transition),
        run_compliance_readiness_notify_users=bool(run_compliance_readiness_notify_users),
    )
    st.success("Jobs completed")
    st.json(summary)

st.subheader("Tournament Ops")
all_tournaments = list_tournaments()
if not all_tournaments:
    st.info("No tournaments found.")
else:
    options = [t["tournament_id"] for t in all_tournaments]
    selected_tid = st.selectbox("Tournament", options, format_func=lambda x: f"#{x}")
    selected = [t for t in all_tournaments if t["tournament_id"] == selected_tid][0]
    st.write(f"Status: {selected['status']} | Tier: {selected['court_tier']} | Fee: ${selected['entry_fee']:.2f}")

    a1, a2 = st.columns(2)
    with a1:
        if st.button("Run Refunds", use_container_width=True):
            result = process_cancelled_tournament_refunds(int(selected_tid))
            if result.get("success"):
                st.success(f"Refunds complete. Refunded: {result.get('refunded', 0)}, Failed: {result.get('failed', 0)}")
            else:
                st.error(result.get("error", "Refund run failed"))
    with a2:
        if st.button("Run Payouts", use_container_width=True):
            result = process_resolved_tournament_payouts(int(selected_tid))
            if result.get("success"):
                st.success(f"Payouts complete. Transferred: {result.get('transferred', 0)}, Failed: {result.get('failed', 0)}")
            else:
                st.error(result.get("error", "Payout run failed"))

st.subheader("Pending Paid Entries")
pp1, pp2 = st.columns(2)
with pp1:
    pending_status = st.selectbox("Pending Status", ["all", "pending", "finalized", "expired"], index=0)
with pp2:
    pending_limit = st.slider("Pending Rows", min_value=10, max_value=500, value=100, step=10)

pending_rows = list_pending_paid_entries(
    status=(None if pending_status == "all" else pending_status),
    limit=int(pending_limit),
)
if not pending_rows:
    st.info("No pending paid entries found.")
else:
    st.dataframe(
        [
            {
                "pending_id": r.get("pending_id"),
                "session": r.get("checkout_session_id"),
                "tournament": r.get("tournament_id"),
                "email": r.get("user_email"),
                "display_name": r.get("display_name"),
                "status": r.get("status"),
                "payment_intent": r.get("payment_intent_id"),
                "created": r.get("created_at"),
                "updated": r.get("updated_at"),
            }
            for r in pending_rows
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Manual Pending Finalization")
    pending_sessions = [str(r.get("checkout_session_id")) for r in pending_rows]
    mf1, mf2 = st.columns(2)
    with mf1:
        selected_session = st.selectbox("Checkout Session", pending_sessions)
    with mf2:
        manual_payment_ref = st.text_input("Payment Reference Override", value="")

    if st.button("Finalize Selected Pending Entry", use_container_width=True):
        result = finalize_pending_paid_entry(
            checkout_session_id=str(selected_session or ""),
            payment_reference=str(manual_payment_ref or ""),
        )
        if result.get("success"):
            st.success(f"Finalized entry #{result.get('entry_id')}. {result.get('message', '')}")
        else:
            st.error(str(result.get("error", "Pending finalization failed")))

    if st.button("Auto-Reconcile Pending", use_container_width=True):
        result = reconcile_pending_paid_entries(
            limit=int(reconcile_limit),
            dry_run=bool(run_pending_reconcile_dry_run),
            max_actions=(None if int(reconcile_max_actions) <= 0 else int(reconcile_max_actions)),
            priority=str(reconcile_priority),
        )
        st.info(
            f"Scanned {result.get('scanned', 0)} pending rows. "
            f"Candidates {result.get('candidates', 0)}. "
            f"Attempted {result.get('attempted', 0)}. "
            f"Reconciled {result.get('reconciled', 0)}. Failed {result.get('failed', 0)}."
        )
        st.caption(f"Reconcile digest: {result.get('attempted_sessions_sha256', '')}")

    st.markdown("### Reconcile Digest Verification")
    digest_input = st.text_input("Digest", value="")
    sessions_input = st.text_area("Session IDs (one per line)", value="")
    reference_sessions_input = st.text_area("Reference Session IDs (optional)", value="")
    strict_digest_order = st.checkbox("Strict Order", value=True)
    normalize_mode = st.selectbox("Normalize Mode", ["trim", "trim_lower"], index=0)

    if st.button("Verify Digest", use_container_width=True):
        session_ids = [
            s.strip()
            for s in str(sessions_input or "").replace(",", "\n").splitlines()
            if s.strip()
        ]
        reference_session_ids = [
            s.strip()
            for s in str(reference_sessions_input or "").replace(",", "\n").splitlines()
            if s.strip()
        ]
        result = verify_reconcile_digest(
            session_ids=session_ids,
            digest=str(digest_input or "").strip(),
            strict_order=bool(strict_digest_order),
            normalize_mode=str(normalize_mode),
            reference_session_ids=(reference_session_ids or None),
        )
        if result.get("success") and result.get("match"):
            st.success("Digest verified successfully")
        elif result.get("success"):
            st.warning("Digest mismatch")
        else:
            st.error(str(result.get("error", "Digest verification failed")))

        st.json(result)
        if session_ids:
            st.caption(
                f"Computed digest preview: "
                f"{compute_reconcile_digest(session_ids=session_ids, strict_order=bool(strict_digest_order), normalize_mode=str(normalize_mode))}"
            )

    st.markdown("### Reconcile Event Digest Verification")
    verify_event_id = st.number_input("Reconcile Summary Event ID", min_value=1, value=1, step=1)
    verify_scope = st.selectbox("Digest Scope", ["attempted", "candidates"], index=0)

    if st.button("Load Latest Reconcile Summary", use_container_width=True):
        latest_summary = get_latest_reconcile_summary_event(scope=str(verify_scope))
        if latest_summary.get("success"):
            st.success("Loaded latest reconcile summary event")
            st.caption(f"Latest event id: {latest_summary.get('event_id', 0)}")
        else:
            st.error(str(latest_summary.get("error", "Latest summary not found")))
        st.json(latest_summary)

    if st.button("Verify Event Digest", use_container_width=True):
        session_ids = [
            s.strip()
            for s in str(sessions_input or "").replace(",", "\n").splitlines()
            if s.strip()
        ]
        reference_session_ids = [
            s.strip()
            for s in str(reference_sessions_input or "").replace(",", "\n").splitlines()
            if s.strip()
        ]
        result = verify_reconcile_digest_for_event(
            event_id=int(verify_event_id),
            session_ids=session_ids,
            scope=str(verify_scope),
            strict_order=bool(strict_digest_order),
            normalize_mode=str(normalize_mode),
            reference_session_ids=(reference_session_ids or None),
        )
        if result.get("success") and result.get("match"):
            st.success("Event digest verified successfully")
        elif result.get("success"):
            st.warning("Event digest mismatch")
        else:
            st.error(str(result.get("error", "Event digest verification failed")))

        st.json(result)

    if st.button("Verify Latest Event Digest", use_container_width=True):
        session_ids = [
            s.strip()
            for s in str(sessions_input or "").replace(",", "\n").splitlines()
            if s.strip()
        ]
        reference_session_ids = [
            s.strip()
            for s in str(reference_sessions_input or "").replace(",", "\n").splitlines()
            if s.strip()
        ]
        result = verify_reconcile_digest_for_latest_event(
            session_ids=session_ids,
            scope=str(verify_scope),
            strict_order=bool(strict_digest_order),
            normalize_mode=str(normalize_mode),
            reference_session_ids=(reference_session_ids or None),
        )
        if result.get("success") and result.get("match"):
            st.success("Latest event digest verified successfully")
        elif result.get("success"):
            st.warning("Latest event digest mismatch")
        else:
            st.error(str(result.get("error", "Latest event digest verification failed")))

        st.json(result)

    st.markdown("### Reconcile Verification Report Export")
    report_event_id = st.number_input("Report Event ID (0 = latest)", min_value=0, value=0, step=1)
    if st.button("Generate Verification Report", use_container_width=True):
        session_ids = [
            s.strip()
            for s in str(sessions_input or "").replace(",", "\n").splitlines()
            if s.strip()
        ]
        reference_session_ids = [
            s.strip()
            for s in str(reference_sessions_input or "").replace(",", "\n").splitlines()
            if s.strip()
        ]
        result = export_reconcile_verification_report(
            session_ids=session_ids,
            scope=str(verify_scope),
            strict_order=bool(strict_digest_order),
            normalize_mode=str(normalize_mode),
            event_id=(None if int(report_event_id) <= 0 else int(report_event_id)),
            reference_session_ids=(reference_session_ids or None),
        )
        if result.get("success") and result.get("match"):
            st.success("Verification report generated")
        elif result.get("success"):
            st.warning("Verification report generated with mismatch")
        else:
            st.error("Verification report generation failed")

        st.json(result)
        st.download_button(
            "Download Verification Report JSON",
            data=json.dumps(result, indent=2),
            file_name="reconcile_verification_report.json",
            mime="application/json",
            use_container_width=True,
        )

    if st.button("Generate Verification Envelope", use_container_width=True):
        session_ids = [
            s.strip()
            for s in str(sessions_input or "").replace(",", "\n").splitlines()
            if s.strip()
        ]
        reference_session_ids = [
            s.strip()
            for s in str(reference_sessions_input or "").replace(",", "\n").splitlines()
            if s.strip()
        ]
        result = export_reconcile_verification_envelope(
            session_ids=session_ids,
            scope=str(verify_scope),
            strict_order=bool(strict_digest_order),
            normalize_mode=str(normalize_mode),
            event_id=(None if int(report_event_id) <= 0 else int(report_event_id)),
            reference_session_ids=(reference_session_ids or None),
        )
        if result.get("success") and result.get("match"):
            st.success("Verification envelope generated")
        elif result.get("success"):
            st.warning("Verification envelope generated with mismatch")
        else:
            st.error("Verification envelope generation failed")

        st.json(result)
        st.download_button(
            "Download Verification Envelope JSON",
            data=json.dumps(result, indent=2),
            file_name="reconcile_verification_envelope.json",
            mime="application/json",
            use_container_width=True,
        )

    st.markdown("### Verification Report Signature Check")
    signature_report_json = st.text_area("Report JSON", value="", height=180)
    signature_value = st.text_input("Signature", value="")
    signature_type = st.selectbox("Signature Type", ["sha256", "hmac_sha256"], index=0)
    signature_key_id = st.text_input("Signature Key ID (optional)", value="")
    signature_version_value = st.number_input("Signature Version (0 = ignore)", min_value=0, value=0, step=1)
    signature_actor_email = st.text_input("Actor Email (for receipt)", value="")

    if st.button("Verify Report Signature", use_container_width=True):
        try:
            parsed_report = json.loads(str(signature_report_json or "{}").strip() or "{}")
        except Exception as exc:
            st.error(f"Invalid report JSON: {exc}")
            parsed_report = None

        if parsed_report is not None:
            result = verify_reconcile_verification_report_signature(
                report=dict(parsed_report or {}),
                signature=str(signature_value or "").strip(),
                signature_type=str(signature_type),
                key_id=str(signature_key_id or "").strip(),
                signature_version=(None if int(signature_version_value) <= 0 else int(signature_version_value)),
            )
            if result.get("success") and result.get("match"):
                st.success("Report signature verified")
            elif result.get("success"):
                st.warning("Report signature mismatch")
            else:
                st.error(str(result.get("error", "Report signature verification failed")))

            st.json(result)

    if st.button("Verify Signature + Record Receipt", use_container_width=True):
        try:
            parsed_report = json.loads(str(signature_report_json or "{}").strip() or "{}")
        except Exception as exc:
            st.error(f"Invalid report JSON: {exc}")
            parsed_report = None

        if parsed_report is not None:
            result = create_reconcile_verification_signature_receipt(
                report=dict(parsed_report or {}),
                signature=str(signature_value or "").strip(),
                signature_type=str(signature_type),
                key_id=str(signature_key_id or "").strip(),
                signature_version=(None if int(signature_version_value) <= 0 else int(signature_version_value)),
                actor_email=str(signature_actor_email or "").strip(),
                source="streamlit_admin_ops",
            )
            if result.get("success") and result.get("match"):
                st.success("Signature receipt created")
            elif result.get("success"):
                st.warning("Receipt created with signature mismatch")
            else:
                st.error(str((result.get("verify") or {}).get("error", "Signature receipt failed")))

            st.json(result)

    st.markdown("### Signature Verification Receipts")
    receipt_outcome = st.selectbox("Receipt Outcome Filter", ["all", "matched", "mismatched", "error"], index=0)
    receipt_limit = st.slider("Receipt Rows", min_value=10, max_value=300, value=50, step=10)
    if st.button("Load Signature Receipts", use_container_width=True):
        rows = list_reconcile_signature_receipts(limit=int(receipt_limit), outcome=str(receipt_outcome))
        if not rows:
            st.info("No signature receipts found")
        else:
            st.dataframe(
                [
                    {
                        "id": r.get("event_id"),
                        "time": r.get("created_at"),
                        "severity": r.get("severity"),
                        "user": r.get("user_email"),
                        "report_event_id": (r.get("metadata") or {}).get("report_event_id"),
                        "signature_type": (r.get("metadata") or {}).get("signature_type"),
                        "key_id": (r.get("metadata") or {}).get("key_id"),
                    }
                    for r in rows
                ],
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("### Signing Key Registry Status")
    if st.button("Load Signing Key Status", use_container_width=True):
        status = get_reconcile_signing_key_registry_status()
        st.json(status)

    st.markdown("### Signature Receipts Export Artifact")
    export_include_csv = st.checkbox("Include CSV payload", value=True)
    export_auto_chain = st.checkbox("Auto Chain from Latest Artifact", value=True)
    export_persist_event = st.checkbox("Persist Artifact Event", value=True)
    export_previous_digest = st.text_input("Previous Digest Override (optional)", value="")

    if st.button("Load Latest Artifact Head", use_container_width=True):
        head = get_latest_reconcile_signature_receipts_artifact_head()
        if head.get("success"):
            st.success("Loaded latest artifact head")
        else:
            st.warning(str(head.get("error", "Artifact head unavailable")))
        st.json(head)

    if st.button("Verify Artifact Chain Integrity", use_container_width=True):
        chain_result = verify_reconcile_signature_receipts_artifact_chain(limit=int(receipt_limit))
        if str(chain_result.get("status", "")).lower() == "ok":
            st.success("Artifact chain integrity verified")
        elif str(chain_result.get("status", "")).lower() == "empty":
            st.info("No artifact chain data available yet")
        else:
            st.warning("Artifact chain integrity issues detected")
        st.json(chain_result)

    checkpoint_require_current = st.checkbox("Require Checkpoint To Match Current Head", value=False)
    checkpoint_require_payload = st.checkbox("Require Checkpoint Signature Payload", value=False)
    if st.button("Verify Latest Chain Checkpoint", use_container_width=True):
        checkpoint_verify = verify_reconcile_signature_chain_checkpoint(
            require_current_head=bool(checkpoint_require_current),
            require_signature_payload=bool(checkpoint_require_payload),
        )
        if str(checkpoint_verify.get("status", "")).lower() == "ok":
            st.success("Latest chain checkpoint verified")
        elif str(checkpoint_verify.get("status", "")).lower() == "empty":
            st.info("No chain checkpoint available yet")
        elif str(checkpoint_verify.get("status", "")).lower() == "stale":
            st.warning("Latest checkpoint is valid but not current")
        else:
            st.error("Latest checkpoint verification failed")
        st.json(checkpoint_verify)

    if st.button("Verify Checkpoint History Integrity", use_container_width=True):
        checkpoint_history = verify_reconcile_signature_chain_checkpoint_history(
            limit=int(receipt_limit),
            require_signature_payload=bool(checkpoint_require_payload),
        )
        if str(checkpoint_history.get("status", "")).lower() == "ok":
            st.success("Checkpoint history integrity verified")
        elif str(checkpoint_history.get("status", "")).lower() == "empty":
            st.info("No checkpoint history available yet")
        else:
            st.error("Checkpoint history integrity issues detected")
        st.json(checkpoint_history)

    if st.button("Load Compliance Status", use_container_width=True):
        compliance = get_reconcile_compliance_status(chain_limit=int(receipt_limit))
        status = str(compliance.get("status", "")).lower()
        if status == "ok":
            st.success("Compliance status is healthy")
        elif status == "warning":
            st.warning("Compliance status has warnings")
        else:
            st.error("Compliance status has blocking issues")
        st.json(compliance)

    readiness_policy_name = st.text_input("Readiness Policy Name", value="streamlit_ops")
    readiness_warning_threshold = st.slider("Readiness Warning Threshold", min_value=1, max_value=99, value=80, step=1)
    readiness_error_threshold = st.slider("Readiness Error Threshold", min_value=0, max_value=98, value=60, step=1)
    readiness_persist_event = st.checkbox("Persist Readiness Evaluation Event", value=True)
    readiness_monitor_transition = st.checkbox("Monitor Status Transition", value=False)
    readiness_transition_cooldown_minutes = st.slider("Readiness Transition Cooldown (minutes)", min_value=0, max_value=1440, value=0, step=5)
    readiness_notify_users = st.checkbox("Notify Users On Transition", value=False)
    if st.button("Load Compliance Readiness Policies", use_container_width=True):
        policies = get_reconcile_compliance_readiness_policies()
        st.json(policies)

    readiness_snapshot_include_registry = st.checkbox("Readiness Snapshot Include Registry", value=False)
    readiness_snapshot_auto_chain = st.checkbox("Readiness Snapshot Auto Chain", value=True)
    readiness_snapshot_persist_event = st.checkbox("Readiness Snapshot Persist Event", value=True)
    readiness_snapshot_previous_digest = st.text_input("Readiness Snapshot Previous Digest Override (optional)", value="")
    readiness_snapshot_prune_dry_run = st.checkbox("Readiness Snapshot Prune Dry Run", value=True)
    readiness_snapshot_prune_days = st.slider("Readiness Snapshot Prune Max Age (days)", min_value=1, max_value=365, value=30, step=1)
    readiness_snapshot_prune_keep_latest = st.slider("Readiness Snapshot Prune Keep Latest (0 = disabled)", min_value=0, max_value=100, value=0, step=1)
    readiness_snapshot_checkpoint_label = st.text_input("Readiness Snapshot Checkpoint Label", value="streamlit_readiness_snapshot")
    readiness_snapshot_checkpoint_note = st.text_input("Readiness Snapshot Checkpoint Note", value="")
    readiness_snapshot_checkpoint_require_head = st.checkbox("Readiness Snapshot Checkpoint Require Head", value=True)
    readiness_snapshot_checkpoint_require_current = st.checkbox("Readiness Snapshot Verify Require Current Head", value=False)
    readiness_snapshot_checkpoint_require_payload = st.checkbox("Readiness Snapshot Verify Require Signature Payload", value=False)
    if st.button("Generate Readiness Policy Snapshot", use_container_width=True):
        readiness_snapshot = export_reconcile_compliance_readiness_policy_snapshot(
            policy_name=str(readiness_policy_name or "streamlit_ops"),
            include_registry=bool(readiness_snapshot_include_registry),
            previous_digest=str(readiness_snapshot_previous_digest or "").strip(),
            auto_chain=bool(readiness_snapshot_auto_chain),
            persist_event=bool(readiness_snapshot_persist_event),
        )
        st.json(readiness_snapshot)
        st.caption(f"Readiness policy snapshot digest: {readiness_snapshot.get('digest_sha256', '')}")
        st.download_button(
            "Download Readiness Policy Snapshot JSON",
            data=json.dumps(readiness_snapshot, indent=2),
            file_name="readiness_policy_snapshot.json",
            mime="application/json",
            use_container_width=True,
        )

    if st.button("Prune Readiness Policy Snapshots", use_container_width=True):
        readiness_prune = prune_reconcile_compliance_readiness_policy_snapshots(
            policy_name=str(readiness_policy_name or "streamlit_ops"),
            max_age_days=int(readiness_snapshot_prune_days),
            dry_run=bool(readiness_snapshot_prune_dry_run),
            keep_latest=(None if int(readiness_snapshot_prune_keep_latest) <= 0 else int(readiness_snapshot_prune_keep_latest)),
        )
        st.json(readiness_prune)

    if st.button("Create Readiness Snapshot Checkpoint", use_container_width=True):
        readiness_checkpoint = create_reconcile_compliance_readiness_policy_snapshot_checkpoint(
            policy_name=str(readiness_policy_name or "streamlit_ops"),
            label=str(readiness_snapshot_checkpoint_label or "streamlit_readiness_snapshot"),
            note=str(readiness_snapshot_checkpoint_note or ""),
            require_head=bool(readiness_snapshot_checkpoint_require_head),
        )
        if readiness_checkpoint.get("success"):
            st.success("Readiness snapshot checkpoint created")
        else:
            st.warning(str(readiness_checkpoint.get("error", "Readiness snapshot checkpoint failed")))
        st.json(readiness_checkpoint)

    if st.button("Load Latest Readiness Snapshot Checkpoint", use_container_width=True):
        readiness_checkpoint_head = get_latest_reconcile_compliance_readiness_policy_snapshot_checkpoint(
            policy_name=str(readiness_policy_name or "").strip(),
        )
        if readiness_checkpoint_head.get("success"):
            st.success("Loaded latest readiness snapshot checkpoint")
        else:
            st.warning(str(readiness_checkpoint_head.get("error", "Readiness snapshot checkpoint unavailable")))
        st.json(readiness_checkpoint_head)

    if st.button("Verify Readiness Snapshot Checkpoint", use_container_width=True):
        readiness_checkpoint_verify = verify_reconcile_compliance_readiness_policy_snapshot_checkpoint(
            policy_name=str(readiness_policy_name or "").strip(),
            require_current_head=bool(readiness_snapshot_checkpoint_require_current),
            require_signature_payload=bool(readiness_snapshot_checkpoint_require_payload),
        )
        if str(readiness_checkpoint_verify.get("status", "")).lower() == "ok":
            st.success("Readiness snapshot checkpoint verified")
        elif str(readiness_checkpoint_verify.get("status", "")).lower() == "empty":
            st.info("No readiness snapshot checkpoint available yet")
        elif str(readiness_checkpoint_verify.get("status", "")).lower() == "stale":
            st.warning("Readiness snapshot checkpoint is valid but stale")
        else:
            st.error("Readiness snapshot checkpoint verification failed")
        st.json(readiness_checkpoint_verify)

    if st.button("Verify Readiness Snapshot Checkpoint History", use_container_width=True):
        readiness_checkpoint_history = verify_reconcile_compliance_readiness_policy_snapshot_checkpoint_history(
            limit=int(receipt_limit),
            policy_name=str(readiness_policy_name or "").strip(),
            require_signature_payload=bool(readiness_snapshot_checkpoint_require_payload),
        )
        if str(readiness_checkpoint_history.get("status", "")).lower() == "ok":
            st.success("Readiness snapshot checkpoint history verified")
        elif str(readiness_checkpoint_history.get("status", "")).lower() == "empty":
            st.info("No readiness snapshot checkpoint history available yet")
        else:
            st.error("Readiness snapshot checkpoint history integrity issues detected")
        st.json(readiness_checkpoint_history)

    if st.button("Load Latest Readiness Policy Snapshot Head", use_container_width=True):
        readiness_head = get_latest_reconcile_compliance_readiness_policy_snapshot_head(
            policy_name=str(readiness_policy_name or "").strip(),
        )
        if readiness_head.get("success"):
            st.success("Loaded latest readiness policy snapshot head")
        else:
            st.warning(str(readiness_head.get("error", "Readiness policy snapshot head unavailable")))
        st.json(readiness_head)

    if st.button("Verify Readiness Policy Snapshot Chain", use_container_width=True):
        readiness_chain = verify_reconcile_compliance_readiness_policy_snapshot_chain(
            limit=int(receipt_limit),
            policy_name=str(readiness_policy_name or "").strip(),
        )
        if str(readiness_chain.get("status", "")).lower() == "ok":
            st.success("Readiness policy snapshot chain verified")
        elif str(readiness_chain.get("status", "")).lower() == "empty":
            st.info("No readiness policy snapshot chain data available yet")
        else:
            st.error("Readiness policy snapshot chain integrity issues detected")
        st.json(readiness_chain)

    if st.button("Evaluate Compliance Readiness", use_container_width=True):
        readiness = evaluate_reconcile_compliance_readiness(
            chain_limit=int(receipt_limit),
            warning_threshold=int(readiness_warning_threshold),
            error_threshold=int(readiness_error_threshold),
            policy_name=str(readiness_policy_name or "streamlit_ops"),
            persist_event=bool(readiness_persist_event),
            monitor_transition=bool(readiness_monitor_transition),
            transition_cooldown_minutes=int(readiness_transition_cooldown_minutes),
            notify_users=bool(readiness_notify_users),
        )
        readiness_status = str(readiness.get("status", "")).lower()
        if readiness_status == "ready":
            st.success("Compliance readiness is ready")
        elif readiness_status == "warning":
            st.warning("Compliance readiness is warning")
        else:
            st.error("Compliance readiness is blocked")
        st.caption(f"Readiness score: {readiness.get('score', 0)}")
        st.json(readiness)

    readiness_artifact_include_json = st.checkbox("Readiness Artifact Include JSON Payload", value=True)
    readiness_artifact_include_snapshot = st.checkbox("Readiness Artifact Include Policy Snapshot", value=True)
    readiness_artifact_auto_chain = st.checkbox("Readiness Artifact Auto Chain", value=True)
    readiness_artifact_persist_event = st.checkbox("Readiness Artifact Persist Event", value=True)
    readiness_artifact_previous_digest = st.text_input("Readiness Artifact Previous Digest Override (optional)", value="")
    readiness_artifact_persist_readiness = st.checkbox("Readiness Artifact Persists Readiness Event", value=False)

    if st.button("Generate Readiness Evaluation Artifact", use_container_width=True):
        readiness_artifact = export_reconcile_compliance_readiness_evaluation_artifact(
            policy_name=str(readiness_policy_name or "streamlit_ops"),
            chain_limit=int(receipt_limit),
            warning_threshold=int(readiness_warning_threshold),
            error_threshold=int(readiness_error_threshold),
            include_json=bool(readiness_artifact_include_json),
            include_snapshot=bool(readiness_artifact_include_snapshot),
            persist_readiness_event=bool(readiness_artifact_persist_readiness),
            previous_digest=str(readiness_artifact_previous_digest or "").strip(),
            auto_chain=bool(readiness_artifact_auto_chain),
            persist_event=bool(readiness_artifact_persist_event),
        )
        st.json(readiness_artifact)
        st.caption(f"Readiness evaluation artifact digest: {readiness_artifact.get('digest_sha256', '')}")
        st.download_button(
            "Download Readiness Evaluation Artifact JSON",
            data=json.dumps(readiness_artifact, indent=2),
            file_name="readiness_evaluation_artifact.json",
            mime="application/json",
            use_container_width=True,
        )

    if st.button("Load Latest Readiness Evaluation Artifact Head", use_container_width=True):
        readiness_artifact_head = get_latest_reconcile_compliance_readiness_evaluation_artifact_head(
            policy_name=str(readiness_policy_name or "").strip(),
        )
        if readiness_artifact_head.get("success"):
            st.success("Loaded latest readiness evaluation artifact head")
        else:
            st.warning(str(readiness_artifact_head.get("error", "Readiness evaluation artifact head unavailable")))
        st.json(readiness_artifact_head)

    if st.button("Verify Readiness Evaluation Artifact Chain", use_container_width=True):
        readiness_artifact_chain = verify_reconcile_compliance_readiness_evaluation_artifact_chain(
            limit=int(receipt_limit),
            policy_name=str(readiness_policy_name or "").strip(),
        )
        if str(readiness_artifact_chain.get("status", "")).lower() == "ok":
            st.success("Readiness evaluation artifact chain verified")
        elif str(readiness_artifact_chain.get("status", "")).lower() == "empty":
            st.info("No readiness evaluation artifact chain data available yet")
        else:
            st.error("Readiness evaluation artifact chain integrity issues detected")
        st.json(readiness_artifact_chain)

    st.markdown("---")
    st.markdown("**Readiness Evaluation Artifact — Prune / Checkpoint / Envelope**")

    readiness_artifact_prune_max_age_days = st.slider(
        "Readiness Artifact Prune Max Age (days)", min_value=1, max_value=365, value=30, step=1,
        key="ra_prune_days",
    )
    readiness_artifact_prune_keep_latest = st.slider(
        "Readiness Artifact Keep Latest (0 = disabled)", min_value=0, max_value=100, value=0, step=1,
        key="ra_keep_latest",
    )
    readiness_artifact_prune_dry_run = st.checkbox("Readiness Artifact Prune Dry Run", value=True, key="ra_prune_dry")
    if st.button("Prune Readiness Evaluation Artifacts", use_container_width=True):
        prune_result = prune_reconcile_compliance_readiness_evaluation_artifacts(
            policy_name=str(readiness_policy_name or "streamlit_ops"),
            max_age_days=int(readiness_artifact_prune_max_age_days),
            dry_run=bool(readiness_artifact_prune_dry_run),
            keep_latest=(None if int(readiness_artifact_prune_keep_latest) <= 0 else int(readiness_artifact_prune_keep_latest)),
        )
        st.json(prune_result)

    readiness_artifact_checkpoint_label = st.text_input(
        "Readiness Artifact Checkpoint Label", value="streamlit_ops", key="ra_ckpt_label",
    )
    if st.button("Create Readiness Evaluation Artifact Checkpoint", use_container_width=True):
        ckpt = create_reconcile_compliance_readiness_evaluation_artifact_checkpoint(
            policy_name=str(readiness_policy_name or "streamlit_ops"),
            label=str(readiness_artifact_checkpoint_label or "streamlit_ops"),
            note="Streamlit manual checkpoint",
            require_head=True,
        )
        if ckpt.get("success"):
            st.success(f"Checkpoint created: event_id={ckpt.get('event_id')} digest={ckpt.get('checkpoint_digest','')[:16]}...")
        else:
            st.error(str(ckpt.get("error", "Checkpoint creation failed")))
        st.json(ckpt)

    if st.button("Load Latest Readiness Artifact Checkpoint", use_container_width=True):
        ckpt_head = get_latest_reconcile_compliance_readiness_evaluation_artifact_checkpoint(
            policy_name=str(readiness_policy_name or "").strip(),
        )
        if ckpt_head.get("success"):
            st.success("Loaded latest readiness evaluation artifact checkpoint")
        else:
            st.warning(str(ckpt_head.get("error", "No checkpoint found")))
        st.json(ckpt_head)

    readiness_artifact_verify_require_current = st.checkbox(
        "Verify Checkpoint: Require Current Head", value=False, key="ra_verify_current",
    )
    if st.button("Verify Readiness Artifact Checkpoint", use_container_width=True):
        verify_ckpt = verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint(
            policy_name=str(readiness_policy_name or "").strip(),
            require_current_head=bool(readiness_artifact_verify_require_current),
            require_signature_payload=False,
        )
        status = str(verify_ckpt.get("status", "")).lower()
        if status == "ok":
            st.success("Readiness evaluation artifact checkpoint verified OK")
        elif status == "empty":
            st.info("No readiness evaluation artifact checkpoint found")
        elif status == "stale":
            st.warning("Readiness evaluation artifact checkpoint is stale (newer artifact exists)")
        else:
            st.error("Readiness evaluation artifact checkpoint verification failed")
        st.json(verify_ckpt)

    if st.button("Verify Readiness Artifact Checkpoint History", use_container_width=True):
        history = verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint_history(
            limit=int(receipt_limit),
            policy_name=str(readiness_policy_name or "").strip(),
            require_signature_payload=False,
        )
        ok_count = history.get("ok", 0)
        broken_count = history.get("broken", 0)
        stale_count = history.get("stale", 0)
        if broken_count > 0:
            st.error(f"Checkpoint history: {ok_count} ok / {broken_count} broken / {stale_count} stale")
        elif stale_count > 0:
            st.warning(f"Checkpoint history: {ok_count} ok / {broken_count} broken / {stale_count} stale")
        else:
            st.success(f"Checkpoint history: {ok_count} ok / {broken_count} broken / {stale_count} stale")
        st.json(history)

    readiness_artifact_envelope_ckpt_label = st.text_input(
        "Readiness Artifact Envelope Checkpoint Label", value="streamlit_ops_envelope", key="ra_env_ckpt_label",
    )
    readiness_artifact_envelope_require_current = st.checkbox(
        "Envelope: Require Current Artifact Head", value=False, key="ra_env_require_current",
    )
    if st.button("Export Readiness Evaluation Artifact Envelope", use_container_width=True):
        envelope = export_reconcile_compliance_readiness_evaluation_artifact_envelope(
            policy_name=str(readiness_policy_name or "streamlit_ops"),
            chain_limit=int(receipt_limit),
            warning_threshold=int(readiness_warning_threshold),
            error_threshold=int(readiness_error_threshold),
            include_json=bool(readiness_artifact_include_json),
            include_snapshot=bool(readiness_artifact_include_snapshot),
            persist_readiness_event=False,
            auto_chain=True,
            persist_event=True,
            create_checkpoint=True,
            checkpoint_label=str(readiness_artifact_envelope_ckpt_label or "streamlit_ops_envelope"),
            checkpoint_note="Streamlit manual envelope export",
            require_current_head=bool(readiness_artifact_envelope_require_current),
            require_signature_payload=False,
        )
        if envelope.get("success"):
            st.success("Readiness evaluation artifact envelope exported")
        else:
            st.error(str(envelope.get("error", "Envelope export failed")))
        st.json(envelope)
        st.download_button(
            "Download Readiness Artifact Envelope JSON",
            data=json.dumps(envelope, indent=2),
            file_name="readiness_evaluation_artifact_envelope.json",
            mime="application/json",
            use_container_width=True,
        )

    st.markdown("---")
    st.markdown("**Composite Governance Snapshot — Export / Chain / Prune / Checkpoint**")

    composite_include_json = st.checkbox("Composite Snapshot Include JSON", value=False, key="cg_include_json")
    composite_include_snapshot = st.checkbox("Composite Snapshot Include Snapshot", value=False, key="cg_include_snapshot")
    composite_auto_chain = st.checkbox("Composite Snapshot Auto Chain", value=True, key="cg_auto_chain")
    composite_persist_event = st.checkbox("Composite Snapshot Persist Event", value=True, key="cg_persist")
    composite_previous_digest = st.text_input("Composite Snapshot Previous Digest Override (optional)", value="", key="cg_prev")

    if st.button("Export Composite Governance Snapshot", use_container_width=True):
        composite_snapshot = export_reconcile_composite_governance_snapshot(
            policy_name=str(readiness_policy_name or "streamlit_ops"),
            chain_limit=int(receipt_limit),
            warning_threshold=int(readiness_warning_threshold),
            error_threshold=int(readiness_error_threshold),
            include_json=bool(composite_include_json),
            include_snapshot=bool(composite_include_snapshot),
            previous_digest=str(composite_previous_digest or "").strip(),
            auto_chain=bool(composite_auto_chain),
            persist_event=bool(composite_persist_event),
        )
        st.json(composite_snapshot)
        st.caption(f"Composite snapshot digest: {composite_snapshot.get('digest_sha256', '')}")

    if st.button("Load Latest Composite Snapshot Head", use_container_width=True):
        composite_head = get_latest_reconcile_composite_governance_snapshot_head(
            policy_name=str(readiness_policy_name or "").strip(),
        )
        if composite_head.get("success"):
            st.success("Loaded latest composite governance snapshot head")
        else:
            st.warning(str(composite_head.get("error", "Composite snapshot head unavailable")))
        st.json(composite_head)

    if st.button("Verify Composite Snapshot Chain", use_container_width=True):
        composite_chain = verify_reconcile_composite_governance_snapshot_chain(
            limit=int(receipt_limit),
            policy_name=str(readiness_policy_name or "").strip(),
        )
        status = str(composite_chain.get("status", "")).lower()
        if status == "ok":
            st.success("Composite governance snapshot chain verified")
        elif status == "empty":
            st.info("No composite governance snapshot chain data available yet")
        else:
            st.error("Composite governance snapshot chain integrity issues detected")
        st.json(composite_chain)

    composite_prune_dry_run = st.checkbox("Composite Snapshot Prune Dry Run", value=True, key="cg_prune_dry")
    composite_prune_days = st.slider("Composite Snapshot Prune Max Age (days)", min_value=1, max_value=365, value=30, step=1, key="cg_prune_days")
    composite_prune_keep_latest = st.slider("Composite Snapshot Keep Latest (0 = disabled)", min_value=0, max_value=100, value=0, step=1, key="cg_keep_latest")
    if st.button("Prune Composite Governance Snapshots", use_container_width=True):
        composite_prune = prune_reconcile_composite_governance_snapshots(
            policy_name=str(readiness_policy_name or "streamlit_ops"),
            max_age_days=int(composite_prune_days),
            dry_run=bool(composite_prune_dry_run),
            keep_latest=(None if int(composite_prune_keep_latest) <= 0 else int(composite_prune_keep_latest)),
        )
        st.json(composite_prune)

    composite_checkpoint_label = st.text_input("Composite Snapshot Checkpoint Label", value="streamlit_composite_snapshot", key="cg_ckpt_label")
    composite_verify_require_current = st.checkbox("Composite Snapshot Verify: Require Current Head", value=False, key="cg_verify_current")
    composite_verify_require_payload = st.checkbox("Composite Snapshot Verify: Require Signature Payload", value=False, key="cg_verify_payload")

    if st.button("Create Composite Snapshot Checkpoint", use_container_width=True):
        composite_ckpt = create_reconcile_composite_governance_snapshot_checkpoint(
            policy_name=str(readiness_policy_name or "streamlit_ops"),
            label=str(composite_checkpoint_label or "streamlit_composite_snapshot"),
            note="Streamlit manual composite governance snapshot checkpoint",
            require_head=True,
        )
        if composite_ckpt.get("success"):
            st.success("Composite snapshot checkpoint created")
        else:
            st.error(str(composite_ckpt.get("error", "Composite snapshot checkpoint failed")))
        st.json(composite_ckpt)

    if st.button("Load Latest Composite Snapshot Checkpoint", use_container_width=True):
        composite_ckpt_head = get_latest_reconcile_composite_governance_snapshot_checkpoint(
            policy_name=str(readiness_policy_name or "").strip(),
        )
        if composite_ckpt_head.get("success"):
            st.success("Loaded latest composite snapshot checkpoint")
        else:
            st.warning(str(composite_ckpt_head.get("error", "No composite snapshot checkpoint found")))
        st.json(composite_ckpt_head)

    if st.button("Verify Composite Snapshot Checkpoint", use_container_width=True):
        composite_ckpt_verify = verify_reconcile_composite_governance_snapshot_checkpoint(
            policy_name=str(readiness_policy_name or "").strip(),
            require_current_head=bool(composite_verify_require_current),
            require_signature_payload=bool(composite_verify_require_payload),
        )
        status = str(composite_ckpt_verify.get("status", "")).lower()
        if status == "ok":
            st.success("Composite snapshot checkpoint verified")
        elif status == "empty":
            st.info("No composite snapshot checkpoint found")
        elif status == "stale":
            st.warning("Composite snapshot checkpoint is stale")
        else:
            st.error("Composite snapshot checkpoint verification failed")
        st.json(composite_ckpt_verify)

    if st.button("Verify Composite Snapshot Checkpoint History", use_container_width=True):
        composite_ckpt_history = verify_reconcile_composite_governance_snapshot_checkpoint_history(
            limit=int(receipt_limit),
            policy_name=str(readiness_policy_name or "").strip(),
            require_signature_payload=bool(composite_verify_require_payload),
        )
        if int(composite_ckpt_history.get("broken", 0) or 0) > 0:
            st.error("Composite snapshot checkpoint history integrity issues detected")
        else:
            st.success("Composite snapshot checkpoint history verified")
        st.json(composite_ckpt_history)

    composite_envelope_checkpoint_label = st.text_input(
        "Composite Envelope Checkpoint Label", value="streamlit_composite_envelope", key="cg_env_ckpt_label",
    )
    if st.button("Export Composite Governance Snapshot Envelope", use_container_width=True):
        composite_envelope = export_reconcile_composite_governance_snapshot_envelope(
            policy_name=str(readiness_policy_name or "streamlit_ops"),
            chain_limit=int(receipt_limit),
            warning_threshold=int(readiness_warning_threshold),
            error_threshold=int(readiness_error_threshold),
            include_json=bool(composite_include_json),
            include_snapshot=bool(composite_include_snapshot),
            auto_chain=True,
            persist_event=True,
            create_checkpoint=True,
            checkpoint_label=str(composite_envelope_checkpoint_label or "streamlit_composite_envelope"),
            checkpoint_note="Streamlit manual composite envelope export",
            require_current_head=bool(composite_verify_require_current),
            require_signature_payload=bool(composite_verify_require_payload),
        )
        if composite_envelope.get("success"):
            st.success("Composite governance snapshot envelope exported")
        else:
            st.error(str(composite_envelope.get("error", "Composite envelope export failed")))
        st.json(composite_envelope)
        st.download_button(
            "Download Composite Snapshot Envelope JSON",
            data=json.dumps(composite_envelope, indent=2),
            file_name="composite_governance_snapshot_envelope.json",
            mime="application/json",
            use_container_width=True,
        )

    st.markdown("---")
    st.markdown("**Governance Attestation Seal — Export / Chain / Prune / Checkpoint / Diagnostics**")

    if st.button("Export Governance Attestation Seal", use_container_width=True):
        seal = export_reconcile_governance_attestation_seal(
            policy_name=str(readiness_policy_name or "streamlit_ops"),
            chain_limit=int(receipt_limit),
            warning_threshold=int(readiness_warning_threshold),
            error_threshold=int(readiness_error_threshold),
            include_json=False,
            include_snapshot=False,
            auto_chain=True,
            persist_event=True,
        )
        st.json(seal)

    if st.button("Load Latest Attestation Seal Head", use_container_width=True):
        seal_head = get_latest_reconcile_governance_attestation_seal_head(
            policy_name=str(readiness_policy_name or "").strip(),
        )
        st.json(seal_head)

    if st.button("Verify Attestation Seal Chain", use_container_width=True):
        seal_chain = verify_reconcile_governance_attestation_seal_chain(
            limit=int(receipt_limit),
            policy_name=str(readiness_policy_name or "").strip(),
        )
        st.json(seal_chain)

    if st.button("Prune Attestation Seals", use_container_width=True):
        seal_prune = prune_reconcile_governance_attestation_seals(
            policy_name=str(readiness_policy_name or "streamlit_ops"),
            max_age_days=int(governance_attestation_seal_prune_days),
            dry_run=bool(run_governance_attestation_seal_prune_dry_run),
            keep_latest=(None if int(governance_attestation_seal_keep_latest) <= 0 else int(governance_attestation_seal_keep_latest)),
        )
        st.json(seal_prune)

    attestation_checkpoint_label = st.text_input("Attestation Seal Checkpoint Label", value="streamlit_attestation_ckpt", key="attest_ckpt_label")
    if st.button("Create Attestation Seal Checkpoint", use_container_width=True):
        seal_ckpt = create_reconcile_governance_attestation_seal_checkpoint(
            policy_name=str(readiness_policy_name or "streamlit_ops"),
            label=str(attestation_checkpoint_label or "streamlit_attestation_ckpt"),
            note="Streamlit manual governance attestation seal checkpoint",
            require_head=True,
        )
        st.json(seal_ckpt)

    if st.button("Load Latest Attestation Seal Checkpoint", use_container_width=True):
        seal_ckpt_head = get_latest_reconcile_governance_attestation_seal_checkpoint(
            policy_name=str(readiness_policy_name or "").strip(),
        )
        st.json(seal_ckpt_head)

    if st.button("Verify Attestation Seal Checkpoint", use_container_width=True):
        seal_ckpt_verify = verify_reconcile_governance_attestation_seal_checkpoint(
            policy_name=str(readiness_policy_name or "").strip(),
            require_current_head=False,
            require_signature_payload=False,
        )
        st.json(seal_ckpt_verify)

    if st.button("Verify Attestation Seal Checkpoint History", use_container_width=True):
        seal_ckpt_history = verify_reconcile_governance_attestation_seal_checkpoint_history(
            limit=int(receipt_limit),
            policy_name=str(readiness_policy_name or "").strip(),
            require_signature_payload=False,
        )
        st.json(seal_ckpt_history)

    if st.button("Run Governance Repair Diagnostics", use_container_width=True):
        diagnostics = get_reconcile_chain_repair_diagnostics(
            limit=int(receipt_limit),
            policy_name=str(readiness_policy_name or "").strip(),
        )
        st.json(diagnostics)

    if st.button("Run Governance Enforcement Check", use_container_width=True):
        enforcement = evaluate_reconcile_governance_enforcement(
            action="financial_ops",
            policy_name=str(readiness_policy_name or "streamlit_ops"),
            block_on_warning=bool(governance_enforcement_block_on_warning),
            require_attestation_seal=bool(governance_enforcement_require_attestation_seal),
        )
        st.json(enforcement)

    compliance_include_json = st.checkbox("Include Compliance Artifact JSON Payload", value=True)
    compliance_auto_chain = st.checkbox("Auto Chain Compliance Artifact", value=True)
    compliance_persist_event = st.checkbox("Persist Compliance Artifact Event", value=True)
    compliance_previous_digest = st.text_input("Compliance Previous Digest Override (optional)", value="")

    if st.button("Load Latest Compliance Artifact Head", use_container_width=True):
        compliance_head = get_latest_reconcile_compliance_status_artifact_head()
        if compliance_head.get("success"):
            st.success("Loaded latest compliance artifact head")
        else:
            st.warning(str(compliance_head.get("error", "Compliance artifact head unavailable")))
        st.json(compliance_head)

    if st.button("Verify Compliance Artifact Chain Integrity", use_container_width=True):
        compliance_chain = verify_reconcile_compliance_status_artifact_chain(limit=int(receipt_limit))
        if str(compliance_chain.get("status", "")).lower() == "ok":
            st.success("Compliance artifact chain integrity verified")
        elif str(compliance_chain.get("status", "")).lower() == "empty":
            st.info("No compliance artifact chain data available yet")
        else:
            st.error("Compliance artifact chain integrity issues detected")
        st.json(compliance_chain)

    if st.button("Generate Compliance Status Artifact", use_container_width=True):
        compliance_artifact = export_reconcile_compliance_status_artifact(
            chain_limit=int(receipt_limit),
            include_json=bool(compliance_include_json),
            previous_digest=str(compliance_previous_digest or "").strip(),
            auto_chain=bool(compliance_auto_chain),
            persist_event=bool(compliance_persist_event),
        )
        st.json(compliance_artifact)
        st.caption(f"Compliance artifact digest: {compliance_artifact.get('digest_sha256', '')}")
        st.caption(f"Compliance artifact chain digest: {compliance_artifact.get('chain_digest', '')}")
        st.download_button(
            "Download Compliance Artifact JSON",
            data=json.dumps(compliance_artifact, indent=2),
            file_name="compliance_status_artifact.json",
            mime="application/json",
            use_container_width=True,
        )

    compliance_envelope_create_checkpoint = st.checkbox("Compliance Envelope Creates Checkpoint", value=True)
    compliance_envelope_require_current = st.checkbox("Compliance Envelope Require Current Head", value=False)
    compliance_envelope_require_payload = st.checkbox("Compliance Envelope Require Signature Payload", value=True)
    compliance_envelope_checkpoint_label = st.text_input("Compliance Envelope Checkpoint Label", value="streamlit_compliance_envelope")
    compliance_envelope_checkpoint_note = st.text_input("Compliance Envelope Checkpoint Note", value="")
    if st.button("Generate Compliance Envelope", use_container_width=True):
        compliance_envelope = export_reconcile_compliance_status_envelope(
            chain_limit=int(receipt_limit),
            include_json=bool(compliance_include_json),
            previous_digest=str(compliance_previous_digest or "").strip(),
            auto_chain=bool(compliance_auto_chain),
            persist_event=bool(compliance_persist_event),
            create_checkpoint=bool(compliance_envelope_create_checkpoint),
            checkpoint_label=str(compliance_envelope_checkpoint_label or "streamlit_compliance_envelope"),
            checkpoint_note=str(compliance_envelope_checkpoint_note or ""),
            require_current_head=bool(compliance_envelope_require_current),
            require_signature_payload=bool(compliance_envelope_require_payload),
        )
        if compliance_envelope.get("success") and compliance_envelope.get("match"):
            st.success("Compliance envelope generated and verified")
        elif compliance_envelope.get("success"):
            st.warning("Compliance envelope generated with warnings")
        else:
            st.error("Compliance envelope generation failed")
        st.json(compliance_envelope)
        st.download_button(
            "Download Compliance Envelope JSON",
            data=json.dumps(compliance_envelope, indent=2),
            file_name="compliance_status_envelope.json",
            mime="application/json",
            use_container_width=True,
        )

    compliance_prune_days = st.slider("Compliance Artifact Prune Max Age (days)", min_value=1, max_value=365, value=30, step=1)
    compliance_prune_dry_run = st.checkbox("Compliance Artifact Prune Dry Run", value=True)
    compliance_prune_keep_latest = st.slider("Compliance Artifact Prune Keep Latest (0 = disabled)", min_value=0, max_value=100, value=0, step=1)
    if st.button("Run Compliance Artifact Prune", use_container_width=True):
        compliance_prune_result = prune_reconcile_compliance_status_artifacts(
            max_age_days=int(compliance_prune_days),
            dry_run=bool(compliance_prune_dry_run),
            keep_latest=(None if int(compliance_prune_keep_latest) <= 0 else int(compliance_prune_keep_latest)),
        )
        if bool(compliance_prune_result.get("dry_run", True)):
            st.info("Compliance artifact prune dry run completed")
        else:
            st.success("Compliance artifact prune completed")
        st.json(compliance_prune_result)

    st.markdown("### Compliance Chain Checkpoint")
    latest_compliance_checkpoint = get_latest_reconcile_compliance_chain_checkpoint()
    if latest_compliance_checkpoint.get("success"):
        st.caption(f"Latest compliance checkpoint event: {latest_compliance_checkpoint.get('event_id', 0)}")
    compliance_checkpoint_label = st.text_input("Compliance Checkpoint Label", value="streamlit_compliance_ops")
    compliance_checkpoint_note = st.text_input("Compliance Checkpoint Note", value="")
    compliance_checkpoint_expected_prev = st.text_input("Compliance Expected Previous Digest (optional)", value="")
    compliance_checkpoint_require_head = st.checkbox("Require Existing Compliance Artifact Head", value=True)
    if st.button("Create Compliance Chain Checkpoint", use_container_width=True):
        compliance_checkpoint = create_reconcile_compliance_chain_checkpoint(
            label=str(compliance_checkpoint_label or "streamlit_compliance_ops"),
            note=str(compliance_checkpoint_note or ""),
            expected_previous_digest=str(compliance_checkpoint_expected_prev or ""),
            require_head=bool(compliance_checkpoint_require_head),
        )
        if compliance_checkpoint.get("success"):
            st.success("Compliance chain checkpoint created")
        else:
            st.error(str(compliance_checkpoint.get("error", "Compliance checkpoint creation failed")))
        st.json(compliance_checkpoint)

    compliance_checkpoint_require_current = st.checkbox("Require Compliance Checkpoint To Match Current Head", value=False)
    compliance_checkpoint_require_payload = st.checkbox("Require Compliance Checkpoint Signature Payload", value=False)
    if st.button("Verify Latest Compliance Chain Checkpoint", use_container_width=True):
        compliance_checkpoint_verify = verify_reconcile_compliance_chain_checkpoint(
            require_current_head=bool(compliance_checkpoint_require_current),
            require_signature_payload=bool(compliance_checkpoint_require_payload),
        )
        if str(compliance_checkpoint_verify.get("status", "")).lower() == "ok":
            st.success("Latest compliance chain checkpoint verified")
        elif str(compliance_checkpoint_verify.get("status", "")).lower() == "empty":
            st.info("No compliance chain checkpoint available yet")
        elif str(compliance_checkpoint_verify.get("status", "")).lower() == "stale":
            st.warning("Latest compliance checkpoint is valid but not current")
        else:
            st.error("Latest compliance checkpoint verification failed")
        st.json(compliance_checkpoint_verify)

    if st.button("Verify Compliance Checkpoint History Integrity", use_container_width=True):
        compliance_checkpoint_history = verify_reconcile_compliance_chain_checkpoint_history(
            limit=int(receipt_limit),
            require_signature_payload=bool(compliance_checkpoint_require_payload),
        )
        if str(compliance_checkpoint_history.get("status", "")).lower() == "ok":
            st.success("Compliance checkpoint history integrity verified")
        elif str(compliance_checkpoint_history.get("status", "")).lower() == "empty":
            st.info("No compliance checkpoint history available yet")
        else:
            st.error("Compliance checkpoint history integrity issues detected")
        st.json(compliance_checkpoint_history)

    if st.button("Generate Receipts Export Artifact", use_container_width=True):
        artifact = export_reconcile_signature_receipts_artifact(
            limit=int(receipt_limit),
            outcome=str(receipt_outcome),
            include_csv=bool(export_include_csv),
            previous_digest=str(export_previous_digest or "").strip(),
            auto_chain=bool(export_auto_chain),
            persist_event=bool(export_persist_event),
        )
        st.json(artifact)
        st.caption(f"Artifact digest: {artifact.get('digest_sha256', '')}")
        st.caption(f"Chain digest: {artifact.get('chain_digest', '')}")
        st.download_button(
            "Download Receipts Artifact JSON",
            data=json.dumps(artifact, indent=2),
            file_name="signature_receipts_artifact.json",
            mime="application/json",
            use_container_width=True,
        )
        csv_payload = str(artifact.get("csv", "") or "")
        if csv_payload:
            st.download_button(
                "Download Receipts Artifact CSV",
                data=csv_payload,
                file_name="signature_receipts_artifact.csv",
                mime="text/csv",
                use_container_width=True,
            )

    st.markdown("### Prune Signature Receipts")
    prune_days = st.slider("Prune Max Age (days)", min_value=1, max_value=365, value=30, step=1)
    prune_dry_run = st.checkbox("Prune Dry Run", value=True)
    if st.button("Run Signature Receipt Prune", use_container_width=True):
        prune_result = prune_reconcile_signature_receipts(
            max_age_days=int(prune_days),
            dry_run=bool(prune_dry_run),
        )
        if bool(prune_result.get("dry_run", True)):
            st.info("Prune dry run completed")
        else:
            st.success("Prune completed")
        st.json(prune_result)

    st.markdown("### Signature Chain Checkpoint")
    checkpoint_label = st.text_input("Checkpoint Label", value="streamlit_admin_ops")
    checkpoint_note = st.text_input("Checkpoint Note", value="")
    checkpoint_expected_prev = st.text_input("Expected Previous Digest (optional)", value="")
    checkpoint_require_head = st.checkbox("Require Existing Artifact Head", value=True)
    if st.button("Create Chain Checkpoint", use_container_width=True):
        checkpoint = create_reconcile_signature_chain_checkpoint(
            label=str(checkpoint_label or "streamlit_admin_ops"),
            note=str(checkpoint_note or ""),
            expected_previous_digest=str(checkpoint_expected_prev or ""),
            require_head=bool(checkpoint_require_head),
        )
        if checkpoint.get("success"):
            st.success("Chain checkpoint created")
        else:
            st.error(str(checkpoint.get("error", "Checkpoint creation failed")))
        st.json(checkpoint)

st.subheader("Phase 2C Ops: Connect + Due Payout SLA")
connect_user = st.text_input("Connect User Email", value="").strip().lower()
cx1, cx2, cx3 = st.columns(3)
with cx1:
    if st.button("Create Connect Onboarding Link", use_container_width=True):
        if not connect_user:
            st.error("Enter a user email first.")
        else:
            onboarding = create_user_connect_onboarding(
                connect_user,
                refresh_path="/ops/tournament/connect/refresh",
                return_path="/ops/tournament/connect/return",
            )
            if onboarding.get("success"):
                st.success("Connect onboarding link created")
            else:
                st.error(str(onboarding.get("error", "Failed to create onboarding link")))
            st.json(onboarding)
with cx2:
    if st.button("Sync Connect Status", use_container_width=True):
        if not connect_user:
            st.error("Enter a user email first.")
        else:
            synced = sync_user_connect_status_from_stripe(connect_user)
            if synced.get("success"):
                st.success("Connect status synced")
            else:
                st.error(str(synced.get("error", "Sync failed")))
            st.json(synced)
with cx3:
    if st.button("Evaluate Payout Eligibility", use_container_width=True):
        if not connect_user:
            st.error("Enter a user email first.")
        else:
            elig = evaluate_user_payout_eligibility(connect_user)
            if elig.get("allowed"):
                st.success("User is payout eligible")
            else:
                st.warning("User is not payout eligible")
            st.json(elig)

if st.button("Get Persisted Connect Snapshot", use_container_width=True):
    if not connect_user:
        st.error("Enter a user email first.")
    else:
        st.json(get_user_connect_status(connect_user))

sla_hours = st.slider("Due Payout SLA Hours", min_value=1, max_value=72, value=24, step=1)
show_not_due = st.checkbox("Include Not-Due Entries", value=False)
if st.button("List Due Payout Entries", use_container_width=True):
    due_rows = list_due_payout_entries(
        sla_hours=int(sla_hours),
        limit=200,
        include_not_due=bool(show_not_due),
    )
    st.write(f"Rows: {len(due_rows)}")
    st.dataframe(due_rows, use_container_width=True, hide_index=True)

st.subheader("Phase 3B/3C Ops: Season LP + Championship Qualification")
season_year = st.number_input("Season Year", min_value=2020, max_value=2100, value=2026, step=1)
season_month = st.number_input("Season Month", min_value=1, max_value=12, value=4, step=1)
season_limit = st.slider("Season Leaderboard Limit", min_value=10, max_value=500, value=100, step=10)
leaderboard_scope = st.selectbox("Season Scope", options=["monthly", "quarterly", "annual"], index=0)

if st.button("Load Season LP Leaderboard", use_container_width=True):
    if leaderboard_scope == "monthly":
        board = list_season_lp_leaderboard(year=int(season_year), month=int(season_month), limit=int(season_limit))
    elif leaderboard_scope == "quarterly":
        quarter = ((int(season_month) - 1) // 3) + 1
        board = list_season_lp_leaderboard(year=int(season_year), quarter=int(quarter), limit=int(season_limit))
    else:
        board = list_season_lp_leaderboard(year=int(season_year), limit=int(season_limit))
    st.write(f"Rows: {len(board)}")
    st.dataframe(board, use_container_width=True, hide_index=True)

rw1, rw2 = st.columns(2)
with rw1:
    top_pct = st.slider("Season Reward Top %", min_value=1, max_value=50, value=10, step=1)
with rw2:
    bonus_lp = st.number_input("Season Reward Bonus LP", min_value=10, max_value=1000, value=100, step=10)

if st.button("Distribute Season-End Rewards", use_container_width=True):
    rewards = distribute_season_end_rewards(
        year=int(season_year),
        month=int(season_month),
        top_pct=float(top_pct) / 100.0,
        bonus_lp=int(bonus_lp),
    )
    if int(rewards.get("awarded_count", 0) or 0) > 0:
        st.success("Season rewards distributed")
    else:
        st.info("No eligible rows found for this season window")
    st.json(rewards)

champ_label = st.text_input("Championship Season Label", value="2026 April Championship")
ch1, ch2, ch3, ch4 = st.columns(4)
with ch1:
    champ_top_n = st.number_input("Champ Top N", min_value=2, max_value=64, value=8, step=1)
with ch2:
    champ_lock_offset = st.number_input("Champ Lock Offset Hours", min_value=1, max_value=168, value=24, step=1)
with ch3:
    champ_entry_fee = st.number_input("Champ Entry Fee", min_value=0.0, max_value=1000.0, value=0.0, step=5.0)
with ch4:
    champ_max_entries = st.number_input("Champ Max Entries", min_value=2, max_value=256, value=32, step=2)
champ_sport = st.selectbox("Championship Sport", options=["nba", "mlb", "nfl"], index=0)

if st.button("Create Championship from Season LP", use_container_width=True):
    championship = qualify_for_championship(
        season_label=str(champ_label or "Championship"),
        top_n=int(champ_top_n),
        year=int(season_year),
        month=int(season_month),
        lock_offset_hours=int(champ_lock_offset),
        entry_fee=float(champ_entry_fee),
        max_entries=int(champ_max_entries),
        sport=str(champ_sport),
    )
    if championship.get("success"):
        st.success(f"Championship created: #{championship.get('tournament_id')}")
    else:
        st.error(str(championship.get("error", "Championship qualification failed")))
    st.json(championship)

st.subheader("Recent Event Log")
show_limit = st.slider("Events", min_value=10, max_value=300, value=80, step=10)
event_tournament_filter = st.text_input("Filter by Tournament ID", value="").strip()
event_type_filter = st.text_input("Filter by Event Type", value="").strip()

parsed_tournament_id = None
if event_tournament_filter:
    try:
        parsed_tournament_id = int(event_tournament_filter)
    except ValueError:
        st.warning("Tournament ID filter must be numeric.")

events = list_events(tournament_id=parsed_tournament_id, limit=show_limit)
if event_type_filter:
    events = [e for e in events if str(e.get("event_type", "")).startswith(event_type_filter)]

if not events:
    st.info("No events yet.")
else:
    st.dataframe(
        [
            {
                "id": e.get("event_id"),
                "time": e.get("created_at"),
                "type": e.get("event_type"),
                "severity": e.get("severity"),
                "tournament": e.get("tournament_id"),
                "entry": e.get("entry_id"),
                "user": e.get("user_email"),
                "message": e.get("message"),
            }
            for e in events
        ],
        use_container_width=True,
        hide_index=True,
    )
