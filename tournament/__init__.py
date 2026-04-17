"""Standalone tournament subsystem for Smart Pick Pro.

This package is intentionally isolated from legacy tracking flows.
Imports are defensive so the package loads even without the parent app.
"""

# fmt: off
# ---- Pure-Python modules (no parent app dependency) ----
from tournament.database import initialize_tournament_database
from tournament.events import list_events, log_event
from tournament.gate import evaluate_tournament_access
from tournament.legends import LEGEND_PROFILES
from tournament.notifications import list_user_notifications, send_notification
from tournament.payout import compute_scaled_payouts
from tournament.profiles import build_player_profiles
from tournament.scoring import calculate_fantasy_points, score_player_total
from tournament.webhooks import (
    get_checkout_session_record,
    process_stripe_event,
    upsert_checkout_session,
)

# ---- Modules that import from parent app's engine/data layer ----
try:
    from tournament.bootstrap import ensure_profile_pool
except Exception:  # pragma: no cover
    ensure_profile_pool = None  # type: ignore[assignment]

try:
    from tournament.simulation import (
        generate_tournament_seed,
        simulate_player_full_line,
        simulate_tournament_environment,
    )
except Exception:  # pragma: no cover
    generate_tournament_seed = None  # type: ignore[assignment]
    simulate_player_full_line = None  # type: ignore[assignment]
    simulate_tournament_environment = None  # type: ignore[assignment]

# ---- Modules that chain through simulation ----
try:
    from tournament.manager import (
        assess_pending_paid_entry,
        compute_reconcile_digest,
        create_reconcile_compliance_chain_checkpoint,
        evaluate_reconcile_compliance_readiness,
        export_reconcile_compliance_readiness_evaluation_artifact,
        export_reconcile_compliance_readiness_policy_snapshot,
        get_reconcile_compliance_readiness_policies,
        get_reconcile_compliance_status,
        get_latest_reconcile_compliance_readiness_evaluation_artifact_head,
        get_latest_reconcile_compliance_readiness_policy_snapshot_head,
        export_reconcile_compliance_status_envelope,
        export_reconcile_compliance_status_artifact,
        create_reconcile_signature_chain_checkpoint,
        create_reconcile_verification_signature_receipt,
        create_tournament,
        export_reconcile_signature_receipts_artifact,
        get_tournament,
        get_tournament_scoreboard,
        get_user_career_stats,
        get_user_connect_status,
        get_user_subscription_status,
        upsert_user_subscription_status,
        upsert_user_connect_status,
        create_user_connect_onboarding,
        sync_user_connect_status_from_stripe,
        evaluate_user_payout_eligibility,
        list_due_payout_entries,
        process_due_payouts,
        evaluate_user_tournament_access,
        get_supported_tournament_sports,
        get_latest_reconcile_compliance_status_artifact_head,
        get_latest_reconcile_compliance_chain_checkpoint,
        get_latest_reconcile_signature_receipts_artifact_head,
        get_latest_reconcile_signature_chain_checkpoint,
        get_pending_paid_entry,
        get_latest_reconcile_summary_event,
        get_reconcile_signing_key_registry_status,
        finalize_pending_paid_entry,
        list_career_leaderboard,
        list_season_lp_leaderboard,
        distribute_season_end_rewards,
        qualify_for_championship,
        get_user_head_to_head,
        get_user_best_rosters,
        get_user_progression_snapshot,
        list_reconcile_signature_receipts,
        expire_stale_pending_paid_entries,
        export_reconcile_verification_envelope,
        export_reconcile_verification_report,
        list_pending_paid_entries,
        list_open_tournaments,
        list_player_profiles,
        list_tournaments,
        list_user_entries,
        get_tournament_live_snapshot,
        get_staged_reveal_snapshot,
        get_tournament_simulated_scores,
        load_tournament_entries,
        mark_pending_paid_entry_finalized,
        prune_reconcile_compliance_status_artifacts,
        prune_reconcile_compliance_readiness_policy_snapshots,
        prune_reconcile_signature_receipts,
        reconcile_pending_paid_entries,
        resolve_tournament,
        save_pending_paid_entry,
        submit_entry,
        submit_paid_entry_after_checkout,
        verify_reconcile_compliance_chain_checkpoint,
        verify_reconcile_compliance_chain_checkpoint_history,
        create_reconcile_compliance_readiness_policy_snapshot_checkpoint,
        get_latest_reconcile_compliance_readiness_policy_snapshot_checkpoint,
        verify_reconcile_compliance_readiness_policy_snapshot_checkpoint,
        verify_reconcile_compliance_readiness_policy_snapshot_checkpoint_history,
        create_reconcile_compliance_readiness_evaluation_artifact_checkpoint,
        get_latest_reconcile_compliance_readiness_evaluation_artifact_checkpoint,
        verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint,
        verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint_history,
        prune_reconcile_compliance_readiness_evaluation_artifacts,
        export_reconcile_compliance_readiness_evaluation_artifact_envelope,
        verify_reconcile_compliance_readiness_evaluation_artifact_chain,
        export_reconcile_composite_governance_snapshot,
        get_latest_reconcile_composite_governance_snapshot_head,
        verify_reconcile_composite_governance_snapshot_chain,
        prune_reconcile_composite_governance_snapshots,
        create_reconcile_composite_governance_snapshot_checkpoint,
        get_latest_reconcile_composite_governance_snapshot_checkpoint,
        verify_reconcile_composite_governance_snapshot_checkpoint,
        verify_reconcile_composite_governance_snapshot_checkpoint_history,
        export_reconcile_composite_governance_snapshot_envelope,
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
        verify_reconcile_compliance_readiness_policy_snapshot_chain,
        verify_reconcile_compliance_status_artifact_chain,
        verify_reconcile_signature_chain_checkpoint_history,
        verify_reconcile_signature_chain_checkpoint,
        verify_reconcile_digest,
        verify_reconcile_signature_receipts_artifact_chain,
        verify_reconcile_digest_for_event,
        verify_reconcile_digest_for_latest_event,
        verify_reconcile_verification_report_signature,
    )
except Exception:  # pragma: no cover
    assess_pending_paid_entry = None  # type: ignore[assignment]
    compute_reconcile_digest = None  # type: ignore[assignment]
    create_reconcile_compliance_chain_checkpoint = None  # type: ignore[assignment]
    evaluate_reconcile_compliance_readiness = None  # type: ignore[assignment]
    export_reconcile_compliance_readiness_evaluation_artifact = None  # type: ignore[assignment]
    export_reconcile_compliance_readiness_policy_snapshot = None  # type: ignore[assignment]
    get_reconcile_compliance_readiness_policies = None  # type: ignore[assignment]
    get_reconcile_compliance_status = None  # type: ignore[assignment]
    get_latest_reconcile_compliance_readiness_evaluation_artifact_head = None  # type: ignore[assignment]
    get_latest_reconcile_compliance_readiness_policy_snapshot_head = None  # type: ignore[assignment]
    export_reconcile_compliance_status_envelope = None  # type: ignore[assignment]
    export_reconcile_compliance_status_artifact = None  # type: ignore[assignment]
    create_reconcile_signature_chain_checkpoint = None  # type: ignore[assignment]
    create_reconcile_verification_signature_receipt = None  # type: ignore[assignment]
    create_tournament = None  # type: ignore[assignment]
    export_reconcile_signature_receipts_artifact = None  # type: ignore[assignment]
    get_tournament = None  # type: ignore[assignment]
    get_tournament_scoreboard = None  # type: ignore[assignment]
    get_user_career_stats = None  # type: ignore[assignment]
    get_user_connect_status = None  # type: ignore[assignment]
    get_user_subscription_status = None  # type: ignore[assignment]
    upsert_user_subscription_status = None  # type: ignore[assignment]
    upsert_user_connect_status = None  # type: ignore[assignment]
    create_user_connect_onboarding = None  # type: ignore[assignment]
    sync_user_connect_status_from_stripe = None  # type: ignore[assignment]
    evaluate_user_payout_eligibility = None  # type: ignore[assignment]
    list_due_payout_entries = None  # type: ignore[assignment]
    process_due_payouts = None  # type: ignore[assignment]
    evaluate_user_tournament_access = None  # type: ignore[assignment]
    get_supported_tournament_sports = None  # type: ignore[assignment]
    get_latest_reconcile_compliance_status_artifact_head = None  # type: ignore[assignment]
    get_latest_reconcile_compliance_chain_checkpoint = None  # type: ignore[assignment]
    get_latest_reconcile_signature_receipts_artifact_head = None  # type: ignore[assignment]
    get_latest_reconcile_signature_chain_checkpoint = None  # type: ignore[assignment]
    get_pending_paid_entry = None  # type: ignore[assignment]
    get_latest_reconcile_summary_event = None  # type: ignore[assignment]
    get_reconcile_signing_key_registry_status = None  # type: ignore[assignment]
    finalize_pending_paid_entry = None  # type: ignore[assignment]
    expire_stale_pending_paid_entries = None  # type: ignore[assignment]
    export_reconcile_verification_envelope = None  # type: ignore[assignment]
    export_reconcile_verification_report = None  # type: ignore[assignment]
    list_career_leaderboard = None  # type: ignore[assignment]
    list_season_lp_leaderboard = None  # type: ignore[assignment]
    distribute_season_end_rewards = None  # type: ignore[assignment]
    qualify_for_championship = None  # type: ignore[assignment]
    get_user_head_to_head = None  # type: ignore[assignment]
    get_user_best_rosters = None  # type: ignore[assignment]
    get_user_progression_snapshot = None  # type: ignore[assignment]
    list_reconcile_signature_receipts = None  # type: ignore[assignment]
    list_pending_paid_entries = None  # type: ignore[assignment]
    list_open_tournaments = None  # type: ignore[assignment]
    list_player_profiles = None  # type: ignore[assignment]
    list_tournaments = None  # type: ignore[assignment]
    list_user_entries = None  # type: ignore[assignment]
    get_tournament_live_snapshot = None  # type: ignore[assignment]
    get_staged_reveal_snapshot = None  # type: ignore[assignment]
    get_tournament_simulated_scores = None  # type: ignore[assignment]
    load_tournament_entries = None  # type: ignore[assignment]
    mark_pending_paid_entry_finalized = None  # type: ignore[assignment]
    prune_reconcile_compliance_status_artifacts = None  # type: ignore[assignment]
    prune_reconcile_compliance_readiness_policy_snapshots = None  # type: ignore[assignment]
    prune_reconcile_signature_receipts = None  # type: ignore[assignment]
    reconcile_pending_paid_entries = None  # type: ignore[assignment]
    resolve_tournament = None  # type: ignore[assignment]
    save_pending_paid_entry = None  # type: ignore[assignment]
    submit_entry = None  # type: ignore[assignment]
    submit_paid_entry_after_checkout = None  # type: ignore[assignment]
    verify_reconcile_compliance_chain_checkpoint = None  # type: ignore[assignment]
    verify_reconcile_compliance_chain_checkpoint_history = None  # type: ignore[assignment]
    create_reconcile_compliance_readiness_policy_snapshot_checkpoint = None  # type: ignore[assignment]
    get_latest_reconcile_compliance_readiness_policy_snapshot_checkpoint = None  # type: ignore[assignment]
    verify_reconcile_compliance_readiness_policy_snapshot_checkpoint = None  # type: ignore[assignment]
    verify_reconcile_compliance_readiness_policy_snapshot_checkpoint_history = None  # type: ignore[assignment]
    create_reconcile_compliance_readiness_evaluation_artifact_checkpoint = None  # type: ignore[assignment]
    get_latest_reconcile_compliance_readiness_evaluation_artifact_checkpoint = None  # type: ignore[assignment]
    verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint = None  # type: ignore[assignment]
    verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint_history = None  # type: ignore[assignment]
    prune_reconcile_compliance_readiness_evaluation_artifacts = None  # type: ignore[assignment]
    export_reconcile_compliance_readiness_evaluation_artifact_envelope = None  # type: ignore[assignment]
    verify_reconcile_compliance_readiness_evaluation_artifact_chain = None  # type: ignore[assignment]
    export_reconcile_composite_governance_snapshot = None  # type: ignore[assignment]
    get_latest_reconcile_composite_governance_snapshot_head = None  # type: ignore[assignment]
    verify_reconcile_composite_governance_snapshot_chain = None  # type: ignore[assignment]
    prune_reconcile_composite_governance_snapshots = None  # type: ignore[assignment]
    create_reconcile_composite_governance_snapshot_checkpoint = None  # type: ignore[assignment]
    get_latest_reconcile_composite_governance_snapshot_checkpoint = None  # type: ignore[assignment]
    verify_reconcile_composite_governance_snapshot_checkpoint = None  # type: ignore[assignment]
    verify_reconcile_composite_governance_snapshot_checkpoint_history = None  # type: ignore[assignment]
    export_reconcile_composite_governance_snapshot_envelope = None  # type: ignore[assignment]
    export_reconcile_governance_attestation_seal = None  # type: ignore[assignment]
    get_latest_reconcile_governance_attestation_seal_head = None  # type: ignore[assignment]
    verify_reconcile_governance_attestation_seal_chain = None  # type: ignore[assignment]
    prune_reconcile_governance_attestation_seals = None  # type: ignore[assignment]
    create_reconcile_governance_attestation_seal_checkpoint = None  # type: ignore[assignment]
    get_latest_reconcile_governance_attestation_seal_checkpoint = None  # type: ignore[assignment]
    verify_reconcile_governance_attestation_seal_checkpoint = None  # type: ignore[assignment]
    verify_reconcile_governance_attestation_seal_checkpoint_history = None  # type: ignore[assignment]
    get_reconcile_chain_repair_diagnostics = None  # type: ignore[assignment]
    evaluate_reconcile_governance_enforcement = None  # type: ignore[assignment]
    verify_reconcile_compliance_readiness_policy_snapshot_chain = None  # type: ignore[assignment]
    verify_reconcile_compliance_status_artifact_chain = None  # type: ignore[assignment]
    verify_reconcile_signature_chain_checkpoint_history = None  # type: ignore[assignment]
    verify_reconcile_signature_chain_checkpoint = None  # type: ignore[assignment]
    verify_reconcile_digest = None  # type: ignore[assignment]
    verify_reconcile_signature_receipts_artifact_chain = None  # type: ignore[assignment]
    verify_reconcile_digest_for_event = None  # type: ignore[assignment]
    verify_reconcile_digest_for_latest_event = None  # type: ignore[assignment]
    verify_reconcile_verification_report_signature = None  # type: ignore[assignment]

try:
    from tournament.exports import (
        export_tournament_entries_csv,
        export_tournament_events_csv,
        export_tournament_scores_csv,
    )
except Exception:  # pragma: no cover
    export_tournament_entries_csv = None  # type: ignore[assignment]
    export_tournament_events_csv = None  # type: ignore[assignment]
    export_tournament_scores_csv = None  # type: ignore[assignment]

try:
    from tournament.payout_runner import (
        process_cancelled_tournament_refunds,
        process_resolved_tournament_payouts,
    )
except Exception:  # pragma: no cover
    process_cancelled_tournament_refunds = None  # type: ignore[assignment]
    process_resolved_tournament_payouts = None  # type: ignore[assignment]

try:
    from tournament.scheduler import create_weekly_schedule, resolve_locked_tournaments
except Exception:  # pragma: no cover
    create_weekly_schedule = None  # type: ignore[assignment]
    resolve_locked_tournaments = None  # type: ignore[assignment]

try:
    from tournament.jobs import run_tournament_jobs
except Exception:  # pragma: no cover
    run_tournament_jobs = None  # type: ignore[assignment]

try:
    from tournament.stripe import (
        create_connect_account,
        create_connect_onboarding_link,
        create_tournament_entry_checkout_session,
        create_tournament_refund,
        get_connect_account_status,
        create_winner_payout_transfer,
        get_checkout_session_details,
        create_legend_pass_checkout_session,
        create_premium_checkout_session,
        get_subscription_details,
    )
except Exception:  # pragma: no cover
    create_connect_account = None  # type: ignore[assignment]
    create_connect_onboarding_link = None  # type: ignore[assignment]
    create_tournament_entry_checkout_session = None  # type: ignore[assignment]
    create_tournament_refund = None  # type: ignore[assignment]
    get_connect_account_status = None  # type: ignore[assignment]
    create_winner_payout_transfer = None  # type: ignore[assignment]
    get_checkout_session_details = None  # type: ignore[assignment]
    create_legend_pass_checkout_session = None  # type: ignore[assignment]
    create_premium_checkout_session = None  # type: ignore[assignment]
    get_subscription_details = None  # type: ignore[assignment]
# fmt: on

__all__ = [
    "LEGEND_PROFILES",
    "build_player_profiles",
    "calculate_fantasy_points",
    "assess_pending_paid_entry",
    "compute_reconcile_digest",
    "create_reconcile_compliance_chain_checkpoint",
    "evaluate_reconcile_compliance_readiness",
    "export_reconcile_compliance_readiness_evaluation_artifact",
    "export_reconcile_compliance_readiness_policy_snapshot",
    "get_reconcile_compliance_readiness_policies",
    "get_reconcile_compliance_status",
    "get_latest_reconcile_compliance_readiness_evaluation_artifact_head",
    "get_latest_reconcile_compliance_readiness_policy_snapshot_head",
    "export_reconcile_compliance_status_envelope",
    "export_reconcile_compliance_status_artifact",
    "create_reconcile_signature_chain_checkpoint",
    "create_reconcile_verification_signature_receipt",
    "compute_scaled_payouts",
    "create_tournament",
    "create_connect_account",
    "create_connect_onboarding_link",
    "get_connect_account_status",
    "create_user_connect_onboarding",
    "export_reconcile_signature_receipts_artifact",
    "create_tournament_entry_checkout_session",
    "create_tournament_refund",
    "create_winner_payout_transfer",
    "get_checkout_session_details",
    "create_legend_pass_checkout_session",
    "create_premium_checkout_session",
    "get_subscription_details",
    "create_weekly_schedule",
    "ensure_profile_pool",
    "evaluate_tournament_access",
    "export_tournament_entries_csv",
    "export_tournament_events_csv",
    "export_tournament_scores_csv",
    "generate_tournament_seed",
    "get_checkout_session_record",
    "get_pending_paid_entry",
    "get_latest_reconcile_summary_event",
    "get_reconcile_signing_key_registry_status",
    "finalize_pending_paid_entry",
    "expire_stale_pending_paid_entries",
    "export_reconcile_verification_envelope",
    "export_reconcile_verification_report",
    "get_tournament",
    "get_tournament_scoreboard",
    "get_user_career_stats",
    "get_user_connect_status",
    "get_user_subscription_status",
    "upsert_user_connect_status",
    "upsert_user_subscription_status",
    "sync_user_connect_status_from_stripe",
    "evaluate_user_payout_eligibility",
    "list_due_payout_entries",
    "process_due_payouts",
    "evaluate_user_tournament_access",
    "get_supported_tournament_sports",
    "get_latest_reconcile_compliance_status_artifact_head",
    "get_latest_reconcile_compliance_chain_checkpoint",
    "get_latest_reconcile_signature_receipts_artifact_head",
    "get_latest_reconcile_signature_chain_checkpoint",
    "list_career_leaderboard",
    "list_season_lp_leaderboard",
    "distribute_season_end_rewards",
    "qualify_for_championship",
    "get_user_head_to_head",
    "get_user_best_rosters",
    "get_user_progression_snapshot",
    "list_reconcile_signature_receipts",
    "list_pending_paid_entries",
    "initialize_tournament_database",
    "list_events",
    "list_open_tournaments",
    "list_player_profiles",
    "list_user_notifications",
    "list_user_entries",
    "get_tournament_live_snapshot",
    "get_staged_reveal_snapshot",
    "get_tournament_simulated_scores",
    "list_tournaments",
    "log_event",
    "load_tournament_entries",
    "mark_pending_paid_entry_finalized",
    "prune_reconcile_compliance_status_artifacts",
    "prune_reconcile_compliance_readiness_policy_snapshots",
    "prune_reconcile_signature_receipts",
    "reconcile_pending_paid_entries",
    "process_cancelled_tournament_refunds",
    "process_stripe_event",
    "process_resolved_tournament_payouts",
    "resolve_locked_tournaments",
    "resolve_tournament",
    "run_tournament_jobs",
    "save_pending_paid_entry",
    "score_player_total",
    "send_notification",
    "simulate_player_full_line",
    "simulate_tournament_environment",
    "submit_entry",
    "submit_paid_entry_after_checkout",
    "verify_reconcile_compliance_chain_checkpoint",
    "verify_reconcile_compliance_chain_checkpoint_history",
    "create_reconcile_compliance_readiness_policy_snapshot_checkpoint",
    "get_latest_reconcile_compliance_readiness_policy_snapshot_checkpoint",
    "verify_reconcile_compliance_readiness_policy_snapshot_checkpoint",
    "verify_reconcile_compliance_readiness_policy_snapshot_checkpoint_history",
    "create_reconcile_compliance_readiness_evaluation_artifact_checkpoint",
    "get_latest_reconcile_compliance_readiness_evaluation_artifact_checkpoint",
    "verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint",
    "verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint_history",
    "prune_reconcile_compliance_readiness_evaluation_artifacts",
    "export_reconcile_compliance_readiness_evaluation_artifact_envelope",
    "verify_reconcile_compliance_readiness_evaluation_artifact_chain",
    "verify_reconcile_compliance_readiness_policy_snapshot_chain",
    "verify_reconcile_compliance_status_artifact_chain",
    "verify_reconcile_signature_chain_checkpoint_history",
    "upsert_checkout_session",
    "verify_reconcile_signature_chain_checkpoint",
    "verify_reconcile_digest",
    "verify_reconcile_signature_receipts_artifact_chain",
    "verify_reconcile_digest_for_event",
    "verify_reconcile_digest_for_latest_event",
    "verify_reconcile_verification_report_signature",
    "export_reconcile_composite_governance_snapshot",
    "get_latest_reconcile_composite_governance_snapshot_head",
    "verify_reconcile_composite_governance_snapshot_chain",
    "prune_reconcile_composite_governance_snapshots",
    "create_reconcile_composite_governance_snapshot_checkpoint",
    "get_latest_reconcile_composite_governance_snapshot_checkpoint",
    "verify_reconcile_composite_governance_snapshot_checkpoint",
    "verify_reconcile_composite_governance_snapshot_checkpoint_history",
    "export_reconcile_composite_governance_snapshot_envelope",
    "export_reconcile_governance_attestation_seal",
    "get_latest_reconcile_governance_attestation_seal_head",
    "verify_reconcile_governance_attestation_seal_chain",
    "prune_reconcile_governance_attestation_seals",
    "create_reconcile_governance_attestation_seal_checkpoint",
    "get_latest_reconcile_governance_attestation_seal_checkpoint",
    "verify_reconcile_governance_attestation_seal_checkpoint",
    "verify_reconcile_governance_attestation_seal_checkpoint_history",
    "get_reconcile_chain_repair_diagnostics",
    "evaluate_reconcile_governance_enforcement",
]
