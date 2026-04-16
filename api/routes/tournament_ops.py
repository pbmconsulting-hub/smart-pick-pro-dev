"""api/routes/tournament_ops.py - Tournament admin operations endpoints."""

from __future__ import annotations

import os
from utils.logger import get_logger

_logger = get_logger(__name__)

try:
    from fastapi import APIRouter, Header, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/ops/tournament", tags=["tournament-ops"])
    _FASTAPI_AVAILABLE = True
except Exception:
    router = None
    _FASTAPI_AVAILABLE = False


if _FASTAPI_AVAILABLE:
    class FinalizePendingRequest(BaseModel):
        checkout_session_id: str
        payment_reference: str = ""


    class PendingCleanupRequest(BaseModel):
        max_age_hours: int = 24


    class PendingReconcileRequest(BaseModel):
        limit: int = 200
        dry_run: bool = False
        max_actions: int | None = None
        priority: str = "paid_first_oldest"


    class ReconcileDigestVerifyRequest(BaseModel):
        session_ids: list[str] = []
        digest: str
        strict_order: bool = True
        normalize_mode: str = "trim"
        reference_session_ids: list[str] = []


    class ReconcileDigestVerifyEventRequest(BaseModel):
        event_id: int
        session_ids: list[str] = []
        scope: str = "attempted"
        strict_order: bool = True
        normalize_mode: str = "trim"
        reference_session_ids: list[str] = []


    class ReconcileDigestVerifyLatestEventRequest(BaseModel):
        session_ids: list[str] = []
        scope: str = "attempted"
        strict_order: bool = True
        normalize_mode: str = "trim"
        reference_session_ids: list[str] = []


    class ReconcileVerificationReportRequest(BaseModel):
        session_ids: list[str] = []
        scope: str = "attempted"
        strict_order: bool = True
        normalize_mode: str = "trim"
        event_id: int | None = None
        reference_session_ids: list[str] = []


    class ReconcileVerificationReportSignatureVerifyRequest(BaseModel):
        report: dict = {}
        signature: str
        signature_type: str = "sha256"
        key_id: str = ""
        signature_version: int | None = None


    class ReconcileVerificationReportSignatureReceiptRequest(BaseModel):
        report: dict = {}
        signature: str
        signature_type: str = "sha256"
        key_id: str = ""
        signature_version: int | None = None
        actor_email: str = ""
        source: str = "ops_api"


    class ReconcileSignatureReceiptsExportRequest(BaseModel):
        limit: int = 100
        outcome: str = "all"
        include_csv: bool = True
        previous_digest: str = ""
        auto_chain: bool = True
        persist_event: bool = True


    class ReconcileSignatureReceiptsPruneRequest(BaseModel):
        max_age_days: int = 30
        dry_run: bool = True


    class ReconcileComplianceStatusExportRequest(BaseModel):
        chain_limit: int = 200
        include_json: bool = True
        previous_digest: str = ""
        auto_chain: bool = True
        persist_event: bool = True


    class ReconcileComplianceStatusEnvelopeRequest(BaseModel):
        chain_limit: int = 200
        include_json: bool = False
        previous_digest: str = ""
        auto_chain: bool = True
        persist_event: bool = True
        create_checkpoint: bool = True
        checkpoint_label: str = "ops_envelope"
        checkpoint_note: str = ""
        require_current_head: bool = False
        require_signature_payload: bool = True


    class ReconcileComplianceReadinessPolicySnapshotRequest(BaseModel):
        policy_name: str = "default"
        include_registry: bool = False
        previous_digest: str = ""
        auto_chain: bool = True
        persist_event: bool = True


    class ReconcileComplianceReadinessEvaluationArtifactRequest(BaseModel):
        policy_name: str = "default"
        chain_limit: int = 200
        warning_threshold: int | None = None
        error_threshold: int | None = None
        include_json: bool = True
        include_snapshot: bool = True
        persist_readiness_event: bool = False
        previous_digest: str = ""
        auto_chain: bool = True
        persist_event: bool = True


    class ReconcileComplianceReadinessPolicySnapshotPruneRequest(BaseModel):
        policy_name: str = "default"
        max_age_days: int = 30
        dry_run: bool = True
        keep_latest: int | None = None


    class ReconcileComplianceReadinessPolicySnapshotCheckpointRequest(BaseModel):
        policy_name: str = "default"
        label: str = "ops"
        note: str = ""
        expected_previous_digest: str = ""
        require_head: bool = True


    class ReconcileComplianceReadinessEvaluationArtifactPruneRequest(BaseModel):
        policy_name: str = "default"
        max_age_days: int = 30
        dry_run: bool = True
        keep_latest: int | None = None


    class ReconcileComplianceReadinessEvaluationArtifactCheckpointRequest(BaseModel):
        policy_name: str = "default"
        label: str = "ops"
        note: str = ""
        expected_previous_digest: str = ""
        require_head: bool = True


    class ReconcileComplianceReadinessEvaluationArtifactEnvelopeRequest(BaseModel):
        policy_name: str = "default"
        chain_limit: int = 200
        warning_threshold: int | None = None
        error_threshold: int | None = None
        include_json: bool = False
        include_snapshot: bool = True
        persist_readiness_event: bool = False
        previous_digest: str = ""
        auto_chain: bool = True
        persist_event: bool = True
        create_checkpoint: bool = True
        checkpoint_label: str = "ops_envelope"
        checkpoint_note: str = ""
        require_current_head: bool = False
        require_signature_payload: bool = False


    class ReconcileCompositeGovernanceSnapshotRequest(BaseModel):
        policy_name: str = "default"
        chain_limit: int = 200
        warning_threshold: int | None = None
        error_threshold: int | None = None
        include_json: bool = False
        include_snapshot: bool = False
        previous_digest: str = ""
        auto_chain: bool = True
        persist_event: bool = True


    class ReconcileCompositeGovernanceSnapshotPruneRequest(BaseModel):
        policy_name: str = "default"
        max_age_days: int = 30
        dry_run: bool = True
        keep_latest: int | None = None


    class ReconcileCompositeGovernanceSnapshotCheckpointRequest(BaseModel):
        policy_name: str = "default"
        label: str = "ops"
        note: str = ""
        expected_previous_digest: str = ""
        require_head: bool = True


    class ReconcileCompositeGovernanceSnapshotEnvelopeRequest(BaseModel):
        policy_name: str = "default"
        chain_limit: int = 200
        warning_threshold: int | None = None
        error_threshold: int | None = None
        include_json: bool = False
        include_snapshot: bool = False
        previous_digest: str = ""
        auto_chain: bool = True
        persist_event: bool = True
        create_checkpoint: bool = True
        checkpoint_label: str = "ops_envelope"
        checkpoint_note: str = ""
        require_current_head: bool = False
        require_signature_payload: bool = False


    class ReconcileGovernanceAttestationSealRequest(BaseModel):
        policy_name: str = "default"
        chain_limit: int = 200
        warning_threshold: int | None = None
        error_threshold: int | None = None
        include_json: bool = False
        include_snapshot: bool = False
        previous_digest: str = ""
        auto_chain: bool = True
        persist_event: bool = True


    class ReconcileGovernanceAttestationSealPruneRequest(BaseModel):
        policy_name: str = "default"
        max_age_days: int = 30
        dry_run: bool = True
        keep_latest: int | None = None


    class ReconcileGovernanceAttestationSealCheckpointRequest(BaseModel):
        policy_name: str = "default"
        label: str = "ops"
        note: str = ""
        expected_previous_digest: str = ""
        require_head: bool = True


    class ReconcileComplianceArtifactsPruneRequest(BaseModel):
        max_age_days: int = 30
        dry_run: bool = True
        keep_latest: int | None = None


    class ReconcileComplianceChainCheckpointRequest(BaseModel):
        label: str = "ops"
        note: str = ""
        expected_previous_digest: str = ""
        require_head: bool = True


    class ReconcileSignatureChainCheckpointRequest(BaseModel):
        label: str = "ops"
        note: str = ""
        expected_previous_digest: str = ""
        require_head: bool = True


    class SubscriptionStatusUpsertRequest(BaseModel):
        user_email: str
        premium_active: bool = False
        legend_pass_active: bool = False
        premium_expires_at: str = ""
        legend_pass_expires_at: str = ""
        source: str = "ops_api"
        raw_payload: dict = {}


    class TournamentAccessCheckRequest(BaseModel):
        user_email: str
        court_tier: str
        user_age: int
        state_code: str


    class TournamentCreateRequest(BaseModel):
        tournament_name: str
        court_tier: str
        entry_fee: float
        min_entries: int
        max_entries: int
        lock_time: str
        reveal_mode: str = "instant"
        sport: str = "nba"


    class ConnectOnboardingRequest(BaseModel):
        user_email: str
        refresh_path: str = "/"
        return_path: str = "/"


    class PayoutEligibilityRequest(BaseModel):
        user_email: str
        compliance_year: int | None = None
        kyc_threshold_usd: float = 600.0


    class DuePayoutsProcessRequest(BaseModel):
        sla_hours: int = 24
        max_tournaments: int = 50

    class SeasonLeaderboardRequest(BaseModel):
        year: int
        month: int | None = None
        quarter: int | None = None
        limit: int = 100

    class SeasonDistributeRewardsRequest(BaseModel):
        year: int
        month: int
        top_pct: float = 0.10
        bonus_lp: int = 100

    class ChampionshipQualifyRequest(BaseModel):
        season_label: str
        top_n: int = 8
        year: int | None = None
        month: int | None = None
        lock_offset_hours: int = 24
        entry_fee: float = 0.0
        max_entries: int = 32
        sport: str = "nba"


    def _require_admin_key(header_value: str) -> None:
        configured_key = os.environ.get("TOURNAMENT_ADMIN_API_KEY", "").strip()
        if not configured_key:
            raise HTTPException(status_code=503, detail="Tournament admin API key not configured")
        if str(header_value or "").strip() != configured_key:
            raise HTTPException(status_code=401, detail="Unauthorized")


    @router.get("/events")
    async def list_tournament_events_api(
        tournament_id: int | None = None,
        event_type: str = "",
        severity: str = "all",
        limit: int = 200,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """List tournament audit events with optional filters for ops tooling."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import list_events

            parsed_severity = str(severity or "all").strip().lower()
            if parsed_severity in {"", "all"}:
                parsed_severity = ""
            elif parsed_severity not in {"info", "warning", "error"}:
                raise HTTPException(status_code=400, detail="Invalid severity filter")

            rows = list_events(
                tournament_id=(None if tournament_id is None else int(tournament_id)),
                event_type=(str(event_type).strip() or None),
                limit=max(1, min(500, int(limit))),
            )
            if parsed_severity:
                rows = [r for r in rows if str(r.get("severity", "")).strip().lower() == parsed_severity]

            return {
                "ok": True,
                "count": len(rows),
                "filters": {
                    "tournament_id": tournament_id,
                    "event_type": str(event_type or "").strip(),
                    "severity": (parsed_severity or "all"),
                    "limit": max(1, min(500, int(limit))),
                },
                "rows": rows,
            }
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament events API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/{checkout_session_id}")
    async def get_pending_paid_entry_diagnostics_api(
        checkout_session_id: str,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Return diagnostics and recommended action for one pending checkout session."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import assess_pending_paid_entry

            result = assess_pending_paid_entry(str(checkout_session_id or "").strip())
            if result.get("success", False):
                return {"ok": True, "result": result}

            error_message = str(result.get("error", "Pending diagnostics failed"))
            if "not found" in error_message.lower():
                raise HTTPException(status_code=404, detail=error_message)
            raise HTTPException(status_code=400, detail=error_message)
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament pending diagnostics API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending")
    async def list_pending_paid_entries_api(
        status: str = "all",
        limit: int = 100,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """List pending paid entry rows for operational visibility."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import list_pending_paid_entries

            parsed_status = (status or "all").strip().lower()
            if parsed_status in {"", "all"}:
                parsed_status = ""
            elif parsed_status not in {"pending", "finalized", "expired"}:
                raise HTTPException(status_code=400, detail="Invalid status filter")

            rows = list_pending_paid_entries(
                status=(parsed_status or None),
                limit=max(1, min(500, int(limit))),
            )
            return {"ok": True, "count": len(rows), "rows": rows}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament pending list API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/cleanup")
    async def cleanup_pending_paid_entries_api(
        payload: PendingCleanupRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Expire stale pending paid entries and return expired count."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import expire_stale_pending_paid_entries

            expired = expire_stale_pending_paid_entries(max_age_hours=max(1, int(payload.max_age_hours)))
            return {
                "ok": True,
                "result": {
                    "expired": int(expired),
                    "max_age_hours": max(1, int(payload.max_age_hours)),
                },
            }
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament pending cleanup API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile")
    async def reconcile_pending_paid_entries_api(
        payload: PendingReconcileRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Reconcile pending rows when entries are already finalized."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import reconcile_pending_paid_entries

            result = reconcile_pending_paid_entries(
                limit=max(1, min(1000, int(payload.limit))),
                dry_run=bool(payload.dry_run),
                max_actions=(None if payload.max_actions is None else max(1, min(1000, int(payload.max_actions)))),
                priority=str(payload.priority or "paid_first_oldest"),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament pending reconcile API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/verify-digest")
    async def verify_reconcile_digest_api(
        payload: ReconcileDigestVerifyRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify a reconcile digest against a provided checkout-session list."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_digest

            result = verify_reconcile_digest(
                session_ids=list(payload.session_ids or []),
                digest=str(payload.digest or ""),
                strict_order=bool(payload.strict_order),
                normalize_mode=str(payload.normalize_mode or "trim"),
                reference_session_ids=list(payload.reference_session_ids or []),
            )
            if not result.get("success", False):
                raise HTTPException(status_code=400, detail=str(result.get("error", "Digest verify failed")))
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile digest verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/verify-event-digest")
    async def verify_reconcile_event_digest_api(
        payload: ReconcileDigestVerifyEventRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify a session list against digest metadata stored on a reconcile summary event."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_digest_for_event

            result = verify_reconcile_digest_for_event(
                event_id=int(payload.event_id),
                session_ids=list(payload.session_ids or []),
                scope=str(payload.scope or "attempted"),
                strict_order=bool(payload.strict_order),
                normalize_mode=str(payload.normalize_mode or "trim"),
                reference_session_ids=list(payload.reference_session_ids or []),
            )
            if not result.get("success", False):
                message = str(result.get("error", "Digest verify failed"))
                if "not found" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile event digest verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/verify-latest-event-digest")
    async def verify_reconcile_latest_event_digest_api(
        payload: ReconcileDigestVerifyLatestEventRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify a session list against digest metadata from the latest reconcile summary event."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_digest_for_latest_event

            result = verify_reconcile_digest_for_latest_event(
                session_ids=list(payload.session_ids or []),
                scope=str(payload.scope or "attempted"),
                strict_order=bool(payload.strict_order),
                normalize_mode=str(payload.normalize_mode or "trim"),
                reference_session_ids=list(payload.reference_session_ids or []),
            )
            if not result.get("success", False):
                message = str(result.get("error", "Digest verify failed"))
                if "not found" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile latest event digest verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/latest-summary")
    async def latest_reconcile_summary_api(
        scope: str = "attempted",
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Return latest reconcile summary metadata for operator workflows."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import get_latest_reconcile_summary_event

            result = get_latest_reconcile_summary_event(scope=str(scope or "attempted"))
            if not result.get("success", False):
                message = str(result.get("error", "Latest reconcile summary not found"))
                if "not found" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament latest reconcile summary API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/export-verification-report")
    async def export_reconcile_verification_report_api(
        payload: ReconcileVerificationReportRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Build a signed reconcile verification report for event-audit workflows."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import export_reconcile_verification_report

            result = export_reconcile_verification_report(
                session_ids=list(payload.session_ids or []),
                scope=str(payload.scope or "attempted"),
                strict_order=bool(payload.strict_order),
                normalize_mode=str(payload.normalize_mode or "trim"),
                event_id=(None if payload.event_id is None else int(payload.event_id)),
                reference_session_ids=list(payload.reference_session_ids or []),
            )
            if not result.get("success", False):
                message = str((result.get("report") or {}).get("verification", {}).get("error", "Report generation failed"))
                if "not found" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile verification report API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/export-verification-envelope")
    async def export_reconcile_verification_envelope_api(
        payload: ReconcileVerificationReportRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Build a report envelope that includes both signed report output and verify payload."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import export_reconcile_verification_envelope

            result = export_reconcile_verification_envelope(
                session_ids=list(payload.session_ids or []),
                scope=str(payload.scope or "attempted"),
                strict_order=bool(payload.strict_order),
                normalize_mode=str(payload.normalize_mode or "trim"),
                event_id=(None if payload.event_id is None else int(payload.event_id)),
                reference_session_ids=list(payload.reference_session_ids or []),
            )
            if not result.get("success", False):
                message = str(
                    (
                        (result.get("report_result") or {}).get("report", {})
                    ).get("verification", {}).get("error", "Envelope generation failed")
                )
                if "not found" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile verification envelope API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/verify-report-signature")
    async def verify_reconcile_verification_report_signature_api(
        payload: ReconcileVerificationReportSignatureVerifyRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify cryptographic signature for reconcile verification report JSON."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_verification_report_signature

            result = verify_reconcile_verification_report_signature(
                report=dict(payload.report or {}),
                signature=str(payload.signature or ""),
                signature_type=str(payload.signature_type or "sha256"),
                key_id=str(payload.key_id or ""),
                signature_version=(None if payload.signature_version is None else int(payload.signature_version)),
            )
            if not result.get("success", False):
                raise HTTPException(status_code=400, detail=str(result.get("error", "Report signature verify failed")))
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile report signature verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/verify-report-signature/receipt")
    async def verify_reconcile_verification_report_signature_receipt_api(
        payload: ReconcileVerificationReportSignatureReceiptRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify report signature and persist a verification receipt event."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import create_reconcile_verification_signature_receipt

            result = create_reconcile_verification_signature_receipt(
                report=dict(payload.report or {}),
                signature=str(payload.signature or ""),
                signature_type=str(payload.signature_type or "sha256"),
                key_id=str(payload.key_id or ""),
                signature_version=(None if payload.signature_version is None else int(payload.signature_version)),
                actor_email=str(payload.actor_email or ""),
                source=str(payload.source or "ops_api"),
            )
            if not result.get("success", False):
                message = str((result.get("verify") or {}).get("error", "Report signature verify failed"))
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile report signature receipt API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/signature-receipts")
    async def list_reconcile_signature_receipts_api(
        limit: int = 100,
        outcome: str = "all",
        x_tournament_admin_key: str = Header(default=""),
    ):
        """List reconcile signature verification receipts for audit review."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import list_reconcile_signature_receipts

            rows = list_reconcile_signature_receipts(
                limit=max(1, min(500, int(limit))),
                outcome=str(outcome or "all"),
            )
            return {
                "ok": True,
                "count": len(rows),
                "filters": {
                    "limit": max(1, min(500, int(limit))),
                    "outcome": str(outcome or "all"),
                },
                "rows": rows,
            }
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile signature receipts list API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/signing-keys/status")
    async def reconcile_signing_keys_status_api(
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Return safe reconcile signing-key registry status for operations diagnostics."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import get_reconcile_signing_key_registry_status

            result = get_reconcile_signing_key_registry_status()
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile signing keys status API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/signature-receipts/export")
    async def export_reconcile_signature_receipts_api(
        payload: ReconcileSignatureReceiptsExportRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Export signature receipt artifact with deterministic digest and optional CSV payload."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import export_reconcile_signature_receipts_artifact

            result = export_reconcile_signature_receipts_artifact(
                limit=max(1, min(500, int(payload.limit))),
                outcome=str(payload.outcome or "all"),
                include_csv=bool(payload.include_csv),
                previous_digest=str(payload.previous_digest or ""),
                auto_chain=bool(payload.auto_chain),
                persist_event=bool(payload.persist_event),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile signature receipts export API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/signature-receipts/artifact-head")
    async def get_reconcile_signature_receipts_artifact_head_api(
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Return latest signature receipt artifact metadata for chain-aware exports."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import get_latest_reconcile_signature_receipts_artifact_head

            result = get_latest_reconcile_signature_receipts_artifact_head()
            if not result.get("success", False):
                message = str(result.get("error", "Signature receipt artifact not found"))
                if "not found" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile signature receipts artifact head API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/signature-receipts/verify-chain")
    async def verify_reconcile_signature_receipts_artifact_chain_api(
        limit: int = 200,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify linkage integrity across signature receipt artifact export events."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_signature_receipts_artifact_chain

            result = verify_reconcile_signature_receipts_artifact_chain(limit=max(1, min(1000, int(limit))))
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile signature receipts verify chain API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/signature-receipts/verify-checkpoint")
    async def verify_reconcile_signature_chain_checkpoint_api(
        require_current_head: bool = False,
        require_signature_payload: bool = False,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify the latest signature chain checkpoint against stored artifact head metadata."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_signature_chain_checkpoint

            result = verify_reconcile_signature_chain_checkpoint(
                require_current_head=bool(require_current_head),
                require_signature_payload=bool(require_signature_payload),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile signature checkpoint verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/signature-receipts/verify-checkpoint-history")
    async def verify_reconcile_signature_chain_checkpoint_history_api(
        limit: int = 200,
        require_signature_payload: bool = False,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify integrity of recent checkpoint events, including signature checks when possible."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_signature_chain_checkpoint_history

            result = verify_reconcile_signature_chain_checkpoint_history(
                limit=max(1, min(1000, int(limit))),
                require_signature_payload=bool(require_signature_payload),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile signature checkpoint history verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/compliance-status")
    async def get_reconcile_compliance_status_api(
        chain_limit: int = 200,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Return a consolidated compliance snapshot for reconcile signing operations."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import get_reconcile_compliance_status

            result = get_reconcile_compliance_status(chain_limit=max(1, min(1000, int(chain_limit))))
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance status API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/compliance-status/export")
    async def export_reconcile_compliance_status_artifact_api(
        payload: ReconcileComplianceStatusExportRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Export compliance status snapshot artifact with digest and optional chain linkage."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import export_reconcile_compliance_status_artifact

            result = export_reconcile_compliance_status_artifact(
                chain_limit=max(1, min(1000, int(payload.chain_limit))),
                include_json=bool(payload.include_json),
                previous_digest=str(payload.previous_digest or ""),
                auto_chain=bool(payload.auto_chain),
                persist_event=bool(payload.persist_event),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance status export API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/compliance-status/export-envelope")
    async def export_reconcile_compliance_status_envelope_api(
        payload: ReconcileComplianceStatusEnvelopeRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Export compliance artifact + checkpoint verification envelope for external auditors."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import export_reconcile_compliance_status_envelope

            result = export_reconcile_compliance_status_envelope(
                chain_limit=max(1, min(1000, int(payload.chain_limit))),
                include_json=bool(payload.include_json),
                previous_digest=str(payload.previous_digest or ""),
                auto_chain=bool(payload.auto_chain),
                persist_event=bool(payload.persist_event),
                create_checkpoint=bool(payload.create_checkpoint),
                checkpoint_label=str(payload.checkpoint_label or "ops_envelope"),
                checkpoint_note=str(payload.checkpoint_note or ""),
                require_current_head=bool(payload.require_current_head),
                require_signature_payload=bool(payload.require_signature_payload),
            )
            if not result.get("success", False):
                message = "Compliance envelope export failed"
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance status envelope API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/compliance-status/readiness")
    async def evaluate_reconcile_compliance_readiness_api(
        chain_limit: int | None = None,
        warning_threshold: int | None = None,
        error_threshold: int | None = None,
        policy_name: str = "default",
        persist_event: bool = False,
        monitor_transition: bool | None = None,
        transition_cooldown_minutes: int | None = None,
        notify_users: bool = False,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Evaluate policy-based compliance readiness for alerting and automation."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import evaluate_reconcile_compliance_readiness

            result = evaluate_reconcile_compliance_readiness(
                chain_limit=(None if chain_limit is None else max(1, min(1000, int(chain_limit)))),
                warning_threshold=(None if warning_threshold is None else max(0, min(100, int(warning_threshold)))),
                error_threshold=(None if error_threshold is None else max(0, min(100, int(error_threshold)))),
                policy_name=str(policy_name or "default"),
                persist_event=bool(persist_event),
                monitor_transition=(None if monitor_transition is None else bool(monitor_transition)),
                transition_cooldown_minutes=(None if transition_cooldown_minutes is None else max(0, min(1440, int(transition_cooldown_minutes)))),
                notify_users=bool(notify_users),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/compliance-status/readiness-policies")
    async def get_reconcile_compliance_readiness_policies_api(
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Return configured readiness policies and defaults for operators and automations."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import get_reconcile_compliance_readiness_policies

            result = get_reconcile_compliance_readiness_policies()
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness policies API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/compliance-status/readiness-policy-snapshot")
    async def export_reconcile_compliance_readiness_policy_snapshot_api(
        payload: ReconcileComplianceReadinessPolicySnapshotRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Export signed readiness policy snapshot artifact with optional chain linkage."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import export_reconcile_compliance_readiness_policy_snapshot

            result = export_reconcile_compliance_readiness_policy_snapshot(
                policy_name=str(payload.policy_name or "default"),
                include_registry=bool(payload.include_registry),
                previous_digest=str(payload.previous_digest or ""),
                auto_chain=bool(payload.auto_chain),
                persist_event=bool(payload.persist_event),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness policy snapshot export API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/compliance-status/readiness-evaluation-artifact")
    async def export_reconcile_compliance_readiness_evaluation_artifact_api(
        payload: ReconcileComplianceReadinessEvaluationArtifactRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Export readiness evaluation artifact with optional policy snapshot and chain linkage."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import export_reconcile_compliance_readiness_evaluation_artifact

            result = export_reconcile_compliance_readiness_evaluation_artifact(
                policy_name=str(payload.policy_name or "default"),
                chain_limit=max(1, min(1000, int(payload.chain_limit))),
                warning_threshold=(None if payload.warning_threshold is None else max(0, min(100, int(payload.warning_threshold)))),
                error_threshold=(None if payload.error_threshold is None else max(0, min(100, int(payload.error_threshold)))),
                include_json=bool(payload.include_json),
                include_snapshot=bool(payload.include_snapshot),
                persist_readiness_event=bool(payload.persist_readiness_event),
                previous_digest=str(payload.previous_digest or ""),
                auto_chain=bool(payload.auto_chain),
                persist_event=bool(payload.persist_event),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness evaluation artifact export API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/compliance-status/readiness-policy-snapshot-head")
    async def get_reconcile_compliance_readiness_policy_snapshot_head_api(
        policy_name: str = "",
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Return latest readiness policy snapshot artifact metadata."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import get_latest_reconcile_compliance_readiness_policy_snapshot_head

            result = get_latest_reconcile_compliance_readiness_policy_snapshot_head(policy_name=str(policy_name or ""))
            if not result.get("success", False):
                message = str(result.get("error", "Readiness policy snapshot not found"))
                if "not found" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness policy snapshot head API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/compliance-status/readiness-policy-snapshot-verify-chain")
    async def verify_reconcile_compliance_readiness_policy_snapshot_chain_api(
        limit: int = 200,
        policy_name: str = "",
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify chain integrity for readiness policy snapshots."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_compliance_readiness_policy_snapshot_chain

            result = verify_reconcile_compliance_readiness_policy_snapshot_chain(
                limit=max(1, min(1000, int(limit))),
                policy_name=str(policy_name or ""),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness policy snapshot verify chain API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/compliance-status/readiness-evaluation-artifact-head")
    async def get_reconcile_compliance_readiness_evaluation_artifact_head_api(
        policy_name: str = "",
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Return latest readiness evaluation artifact metadata."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import get_latest_reconcile_compliance_readiness_evaluation_artifact_head

            result = get_latest_reconcile_compliance_readiness_evaluation_artifact_head(policy_name=str(policy_name or ""))
            if not result.get("success", False):
                message = str(result.get("error", "Readiness evaluation artifact not found"))
                if "not found" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness evaluation artifact head API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/compliance-status/readiness-evaluation-artifact-verify-chain")
    async def verify_reconcile_compliance_readiness_evaluation_artifact_chain_api(
        limit: int = 200,
        policy_name: str = "",
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify chain integrity for readiness evaluation artifacts."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_compliance_readiness_evaluation_artifact_chain

            result = verify_reconcile_compliance_readiness_evaluation_artifact_chain(
                limit=max(1, min(1000, int(limit))),
                policy_name=str(policy_name or ""),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness evaluation artifact verify chain API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/compliance-status/readiness-evaluation-artifact/prune")
    async def prune_reconcile_compliance_readiness_evaluation_artifacts_api(
        payload: ReconcileComplianceReadinessEvaluationArtifactPruneRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Prune stale readiness evaluation artifact events with dry-run support."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import prune_reconcile_compliance_readiness_evaluation_artifacts

            result = prune_reconcile_compliance_readiness_evaluation_artifacts(
                policy_name=str(payload.policy_name or "default"),
                max_age_days=max(1, int(payload.max_age_days)),
                dry_run=bool(payload.dry_run),
                keep_latest=(None if payload.keep_latest is None else max(0, int(payload.keep_latest))),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness evaluation artifact prune API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/compliance-status/readiness-evaluation-artifact/checkpoint")
    async def create_reconcile_compliance_readiness_evaluation_artifact_checkpoint_api(
        payload: ReconcileComplianceReadinessEvaluationArtifactCheckpointRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Create a readiness evaluation artifact chain checkpoint anchored to latest artifact head."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import create_reconcile_compliance_readiness_evaluation_artifact_checkpoint

            result = create_reconcile_compliance_readiness_evaluation_artifact_checkpoint(
                policy_name=str(payload.policy_name or "default"),
                label=str(payload.label or "ops"),
                note=str(payload.note or ""),
                expected_previous_digest=str(payload.expected_previous_digest or ""),
                require_head=bool(payload.require_head),
            )
            if not result.get("success", False):
                message = str(result.get("error", "Readiness evaluation artifact checkpoint creation failed"))
                if "not found" in message.lower() or "no readiness evaluation artifact head" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness evaluation artifact checkpoint API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/compliance-status/readiness-evaluation-artifact/verify-checkpoint")
    async def verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint_api(
        policy_name: str = "",
        require_current_head: bool = False,
        require_signature_payload: bool = False,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify latest readiness evaluation artifact checkpoint against stored artifact head metadata."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint

            result = verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint(
                policy_name=str(policy_name or ""),
                require_current_head=bool(require_current_head),
                require_signature_payload=bool(require_signature_payload),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness evaluation artifact checkpoint verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/compliance-status/readiness-evaluation-artifact/verify-checkpoint-history")
    async def verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint_history_api(
        limit: int = 200,
        policy_name: str = "",
        require_signature_payload: bool = False,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify integrity of recent readiness evaluation artifact checkpoint events."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint_history

            result = verify_reconcile_compliance_readiness_evaluation_artifact_checkpoint_history(
                limit=max(1, min(1000, int(limit))),
                policy_name=str(policy_name or ""),
                require_signature_payload=bool(require_signature_payload),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness evaluation artifact checkpoint history verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/compliance-status/readiness-evaluation-artifact/export-envelope")
    async def export_reconcile_compliance_readiness_evaluation_artifact_envelope_api(
        payload: ReconcileComplianceReadinessEvaluationArtifactEnvelopeRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Export readiness evaluation artifact + checkpoint verification envelope for external auditors."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import export_reconcile_compliance_readiness_evaluation_artifact_envelope

            result = export_reconcile_compliance_readiness_evaluation_artifact_envelope(
                policy_name=str(payload.policy_name or "default"),
                chain_limit=max(1, int(payload.chain_limit)),
                warning_threshold=payload.warning_threshold,
                error_threshold=payload.error_threshold,
                include_json=bool(payload.include_json),
                include_snapshot=bool(payload.include_snapshot),
                persist_readiness_event=bool(payload.persist_readiness_event),
                previous_digest=str(payload.previous_digest or ""),
                auto_chain=bool(payload.auto_chain),
                persist_event=bool(payload.persist_event),
                create_checkpoint=bool(payload.create_checkpoint),
                checkpoint_label=str(payload.checkpoint_label or "ops_envelope"),
                checkpoint_note=str(payload.checkpoint_note or ""),
                require_current_head=bool(payload.require_current_head),
                require_signature_payload=bool(payload.require_signature_payload),
            )
            if not result.get("success", False):
                message = str(result.get("error", "Readiness evaluation artifact envelope export failed"))
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness evaluation artifact envelope API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/composite-governance-snapshot/export")
    async def export_reconcile_composite_governance_snapshot_api(
        payload: ReconcileCompositeGovernanceSnapshotRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Export a signed composite governance snapshot pinning all audit chain heads."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import export_reconcile_composite_governance_snapshot

            result = export_reconcile_composite_governance_snapshot(
                policy_name=str(payload.policy_name or "default"),
                chain_limit=max(1, int(payload.chain_limit)),
                warning_threshold=payload.warning_threshold,
                error_threshold=payload.error_threshold,
                include_json=bool(payload.include_json),
                include_snapshot=bool(payload.include_snapshot),
                previous_digest=str(payload.previous_digest or ""),
                auto_chain=bool(payload.auto_chain),
                persist_event=bool(payload.persist_event),
            )
            if not result.get("success", False):
                message = str(result.get("error", "Composite governance snapshot export failed"))
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament composite governance snapshot export API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/composite-governance-snapshot/artifact-head")
    async def get_reconcile_composite_governance_snapshot_head_api(
        policy_name: str = "",
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Return latest composite governance snapshot metadata for chain-aware operations."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import get_latest_reconcile_composite_governance_snapshot_head

            result = get_latest_reconcile_composite_governance_snapshot_head(policy_name=str(policy_name or ""))
            if not result.get("success", False):
                message = str(result.get("error", "Composite governance snapshot not found"))
                if "not found" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament composite governance snapshot head API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/composite-governance-snapshot/verify-chain")
    async def verify_reconcile_composite_governance_snapshot_chain_api(
        limit: int = 200,
        policy_name: str = "",
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify chain integrity across composite governance snapshot events."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_composite_governance_snapshot_chain

            result = verify_reconcile_composite_governance_snapshot_chain(
                limit=max(1, min(1000, int(limit))),
                policy_name=str(policy_name or ""),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament composite governance snapshot chain verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/composite-governance-snapshot/prune")
    async def prune_reconcile_composite_governance_snapshots_api(
        payload: ReconcileCompositeGovernanceSnapshotPruneRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Prune stale composite governance snapshot events with dry-run support."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import prune_reconcile_composite_governance_snapshots

            result = prune_reconcile_composite_governance_snapshots(
                policy_name=str(payload.policy_name or "default"),
                max_age_days=max(1, int(payload.max_age_days)),
                dry_run=bool(payload.dry_run),
                keep_latest=(None if payload.keep_latest is None else max(0, int(payload.keep_latest))),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament composite governance snapshot prune API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/composite-governance-snapshot/checkpoint")
    async def create_reconcile_composite_governance_snapshot_checkpoint_api(
        payload: ReconcileCompositeGovernanceSnapshotCheckpointRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Create a signed composite governance snapshot checkpoint anchored to latest snapshot head."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import create_reconcile_composite_governance_snapshot_checkpoint

            result = create_reconcile_composite_governance_snapshot_checkpoint(
                policy_name=str(payload.policy_name or "default"),
                label=str(payload.label or "ops"),
                note=str(payload.note or ""),
                expected_previous_digest=str(payload.expected_previous_digest or ""),
                require_head=bool(payload.require_head),
            )
            if not result.get("success", False):
                message = str(result.get("error", "Composite governance snapshot checkpoint creation failed"))
                if "not found" in message.lower() or "no composite governance snapshot head" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament composite governance snapshot checkpoint API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/composite-governance-snapshot/verify-checkpoint")
    async def verify_reconcile_composite_governance_snapshot_checkpoint_api(
        policy_name: str = "",
        require_current_head: bool = False,
        require_signature_payload: bool = False,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify latest composite governance snapshot checkpoint against current snapshot head."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_composite_governance_snapshot_checkpoint

            result = verify_reconcile_composite_governance_snapshot_checkpoint(
                policy_name=str(policy_name or ""),
                require_current_head=bool(require_current_head),
                require_signature_payload=bool(require_signature_payload),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament composite governance snapshot checkpoint verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/composite-governance-snapshot/verify-checkpoint-history")
    async def verify_reconcile_composite_governance_snapshot_checkpoint_history_api(
        limit: int = 200,
        policy_name: str = "",
        require_signature_payload: bool = False,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify integrity of recent composite governance snapshot checkpoint events."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_composite_governance_snapshot_checkpoint_history

            result = verify_reconcile_composite_governance_snapshot_checkpoint_history(
                limit=max(1, min(1000, int(limit))),
                policy_name=str(policy_name or ""),
                require_signature_payload=bool(require_signature_payload),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament composite governance snapshot checkpoint history verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/composite-governance-snapshot/export-envelope")
    async def export_reconcile_composite_governance_snapshot_envelope_api(
        payload: ReconcileCompositeGovernanceSnapshotEnvelopeRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Export composite governance snapshot plus checkpoint verification envelope for auditors."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import export_reconcile_composite_governance_snapshot_envelope

            result = export_reconcile_composite_governance_snapshot_envelope(
                policy_name=str(payload.policy_name or "default"),
                chain_limit=max(1, int(payload.chain_limit)),
                warning_threshold=payload.warning_threshold,
                error_threshold=payload.error_threshold,
                include_json=bool(payload.include_json),
                include_snapshot=bool(payload.include_snapshot),
                previous_digest=str(payload.previous_digest or ""),
                auto_chain=bool(payload.auto_chain),
                persist_event=bool(payload.persist_event),
                create_checkpoint=bool(payload.create_checkpoint),
                checkpoint_label=str(payload.checkpoint_label or "ops_envelope"),
                checkpoint_note=str(payload.checkpoint_note or ""),
                require_current_head=bool(payload.require_current_head),
                require_signature_payload=bool(payload.require_signature_payload),
            )
            if not result.get("success", False):
                message = str(result.get("error", "Composite governance snapshot envelope export failed"))
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament composite governance snapshot envelope API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/governance-attestation-seal/export")
    async def export_reconcile_governance_attestation_seal_api(
        payload: ReconcileGovernanceAttestationSealRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Export top-level governance attestation seal across current envelope heads."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import export_reconcile_governance_attestation_seal

            result = export_reconcile_governance_attestation_seal(
                policy_name=str(payload.policy_name or "default"),
                chain_limit=max(1, int(payload.chain_limit)),
                warning_threshold=payload.warning_threshold,
                error_threshold=payload.error_threshold,
                include_json=bool(payload.include_json),
                include_snapshot=bool(payload.include_snapshot),
                previous_digest=str(payload.previous_digest or ""),
                auto_chain=bool(payload.auto_chain),
                persist_event=bool(payload.persist_event),
            )
            if not result.get("success", False):
                message = str(result.get("error", "Governance attestation seal export failed"))
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament governance attestation seal export API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/governance-attestation-seal/artifact-head")
    async def get_reconcile_governance_attestation_seal_head_api(
        policy_name: str = "",
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Return latest governance attestation seal head metadata."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import get_latest_reconcile_governance_attestation_seal_head

            result = get_latest_reconcile_governance_attestation_seal_head(policy_name=str(policy_name or ""))
            if not result.get("success", False):
                message = str(result.get("error", "Governance attestation seal head not found"))
                if "not found" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament governance attestation seal head API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/governance-attestation-seal/verify-chain")
    async def verify_reconcile_governance_attestation_seal_chain_api(
        limit: int = 200,
        policy_name: str = "",
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify chain integrity across governance attestation seal events."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_governance_attestation_seal_chain

            result = verify_reconcile_governance_attestation_seal_chain(
                limit=max(1, min(1000, int(limit))),
                policy_name=str(policy_name or ""),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament governance attestation seal chain verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/governance-attestation-seal/prune")
    async def prune_reconcile_governance_attestation_seals_api(
        payload: ReconcileGovernanceAttestationSealPruneRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Prune stale governance attestation seal events with dry-run support."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import prune_reconcile_governance_attestation_seals

            result = prune_reconcile_governance_attestation_seals(
                policy_name=str(payload.policy_name or "default"),
                max_age_days=max(1, int(payload.max_age_days)),
                dry_run=bool(payload.dry_run),
                keep_latest=(None if payload.keep_latest is None else max(0, int(payload.keep_latest))),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament governance attestation seal prune API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/governance-attestation-seal/checkpoint")
    async def create_reconcile_governance_attestation_seal_checkpoint_api(
        payload: ReconcileGovernanceAttestationSealCheckpointRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Create governance attestation seal checkpoint anchored to latest seal head."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import create_reconcile_governance_attestation_seal_checkpoint

            result = create_reconcile_governance_attestation_seal_checkpoint(
                policy_name=str(payload.policy_name or "default"),
                label=str(payload.label or "ops"),
                note=str(payload.note or ""),
                expected_previous_digest=str(payload.expected_previous_digest or ""),
                require_head=bool(payload.require_head),
            )
            if not result.get("success", False):
                message = str(result.get("error", "Governance attestation seal checkpoint creation failed"))
                if "not found" in message.lower() or "no governance attestation seal head" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament governance attestation seal checkpoint API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/governance-attestation-seal/verify-checkpoint")
    async def verify_reconcile_governance_attestation_seal_checkpoint_api(
        policy_name: str = "",
        require_current_head: bool = False,
        require_signature_payload: bool = False,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify latest governance attestation seal checkpoint against current head."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_governance_attestation_seal_checkpoint

            result = verify_reconcile_governance_attestation_seal_checkpoint(
                policy_name=str(policy_name or ""),
                require_current_head=bool(require_current_head),
                require_signature_payload=bool(require_signature_payload),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament governance attestation seal checkpoint verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/governance-attestation-seal/verify-checkpoint-history")
    async def verify_reconcile_governance_attestation_seal_checkpoint_history_api(
        limit: int = 200,
        policy_name: str = "",
        require_signature_payload: bool = False,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify integrity of recent governance attestation seal checkpoint events."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_governance_attestation_seal_checkpoint_history

            result = verify_reconcile_governance_attestation_seal_checkpoint_history(
                limit=max(1, min(1000, int(limit))),
                policy_name=str(policy_name or ""),
                require_signature_payload=bool(require_signature_payload),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament governance attestation seal checkpoint history verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/governance/repair-diagnostics")
    async def get_reconcile_chain_repair_diagnostics_api(
        limit: int = 200,
        policy_name: str = "",
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Return automated chain-repair diagnostics and recommended recovery actions."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import get_reconcile_chain_repair_diagnostics

            result = get_reconcile_chain_repair_diagnostics(
                limit=max(1, min(1000, int(limit))),
                policy_name=str(policy_name or ""),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament governance repair diagnostics API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/governance/enforcement-check")
    async def evaluate_reconcile_governance_enforcement_api(
        action: str = "financial_ops",
        policy_name: str = "default",
        block_on_warning: bool = False,
        require_attestation_seal: bool = False,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Evaluate whether governance status should block a critical operation."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import evaluate_reconcile_governance_enforcement

            result = evaluate_reconcile_governance_enforcement(
                action=str(action or "financial_ops"),
                policy_name=str(policy_name or "default"),
                block_on_warning=bool(block_on_warning),
                require_attestation_seal=bool(require_attestation_seal),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament governance enforcement check API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/compliance-status/readiness-policy-snapshot/prune")
    async def prune_reconcile_compliance_readiness_policy_snapshots_api(
        payload: ReconcileComplianceReadinessPolicySnapshotPruneRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Prune stale readiness policy snapshot events with dry-run support."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import prune_reconcile_compliance_readiness_policy_snapshots

            result = prune_reconcile_compliance_readiness_policy_snapshots(
                policy_name=str(payload.policy_name or "default"),
                max_age_days=max(1, int(payload.max_age_days)),
                dry_run=bool(payload.dry_run),
                keep_latest=(None if payload.keep_latest is None else max(0, int(payload.keep_latest))),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness policy snapshot prune API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/compliance-status/readiness-policy-snapshot/checkpoint")
    async def create_reconcile_compliance_readiness_policy_snapshot_checkpoint_api(
        payload: ReconcileComplianceReadinessPolicySnapshotCheckpointRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Create a readiness policy snapshot chain checkpoint anchored to latest snapshot head."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import create_reconcile_compliance_readiness_policy_snapshot_checkpoint

            result = create_reconcile_compliance_readiness_policy_snapshot_checkpoint(
                policy_name=str(payload.policy_name or "default"),
                label=str(payload.label or "ops"),
                note=str(payload.note or ""),
                expected_previous_digest=str(payload.expected_previous_digest or ""),
                require_head=bool(payload.require_head),
            )
            if not result.get("success", False):
                message = str(result.get("error", "Readiness policy snapshot checkpoint creation failed"))
                if "not found" in message.lower() or "no readiness policy snapshot head" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness policy snapshot checkpoint API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/compliance-status/readiness-policy-snapshot/verify-checkpoint")
    async def verify_reconcile_compliance_readiness_policy_snapshot_checkpoint_api(
        policy_name: str = "",
        require_current_head: bool = False,
        require_signature_payload: bool = False,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify latest readiness policy snapshot checkpoint against stored snapshot head metadata."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_compliance_readiness_policy_snapshot_checkpoint

            result = verify_reconcile_compliance_readiness_policy_snapshot_checkpoint(
                policy_name=str(policy_name or ""),
                require_current_head=bool(require_current_head),
                require_signature_payload=bool(require_signature_payload),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness policy snapshot checkpoint verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/compliance-status/readiness-policy-snapshot/verify-checkpoint-history")
    async def verify_reconcile_compliance_readiness_policy_snapshot_checkpoint_history_api(
        limit: int = 200,
        policy_name: str = "",
        require_signature_payload: bool = False,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify integrity of recent readiness policy snapshot checkpoint events."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_compliance_readiness_policy_snapshot_checkpoint_history

            result = verify_reconcile_compliance_readiness_policy_snapshot_checkpoint_history(
                limit=max(1, min(1000, int(limit))),
                policy_name=str(policy_name or ""),
                require_signature_payload=bool(require_signature_payload),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance readiness policy snapshot checkpoint history verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/compliance-status/artifact-head")
    async def get_reconcile_compliance_status_artifact_head_api(
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Return latest compliance status artifact metadata for chain-aware exports."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import get_latest_reconcile_compliance_status_artifact_head

            result = get_latest_reconcile_compliance_status_artifact_head()
            if not result.get("success", False):
                message = str(result.get("error", "Compliance status artifact not found"))
                if "not found" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance status artifact head API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/compliance-status/verify-chain")
    async def verify_reconcile_compliance_status_artifact_chain_api(
        limit: int = 200,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify linkage integrity across compliance status artifact export events."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_compliance_status_artifact_chain

            result = verify_reconcile_compliance_status_artifact_chain(limit=max(1, min(1000, int(limit))))
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance status verify chain API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/compliance-status/prune")
    async def prune_reconcile_compliance_status_artifacts_api(
        payload: ReconcileComplianceArtifactsPruneRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Prune stale compliance status artifact events with dry-run support."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import prune_reconcile_compliance_status_artifacts

            result = prune_reconcile_compliance_status_artifacts(
                max_age_days=max(1, int(payload.max_age_days)),
                dry_run=bool(payload.dry_run),
                keep_latest=(None if payload.keep_latest is None else max(0, int(payload.keep_latest))),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance status prune API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/compliance-status/checkpoint")
    async def create_reconcile_compliance_chain_checkpoint_api(
        payload: ReconcileComplianceChainCheckpointRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Create a signed compliance artifact chain checkpoint anchored to latest compliance artifact head."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import create_reconcile_compliance_chain_checkpoint

            result = create_reconcile_compliance_chain_checkpoint(
                label=str(payload.label or "ops"),
                note=str(payload.note or ""),
                expected_previous_digest=str(payload.expected_previous_digest or ""),
                require_head=bool(payload.require_head),
            )
            if not result.get("success", False):
                message = str(result.get("error", "Compliance checkpoint creation failed"))
                if "not found" in message.lower() or "no compliance artifact head" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance chain checkpoint API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/compliance-status/verify-checkpoint")
    async def verify_reconcile_compliance_chain_checkpoint_api(
        require_current_head: bool = False,
        require_signature_payload: bool = False,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify latest compliance chain checkpoint against stored compliance artifact head metadata."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_compliance_chain_checkpoint

            result = verify_reconcile_compliance_chain_checkpoint(
                require_current_head=bool(require_current_head),
                require_signature_payload=bool(require_signature_payload),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance checkpoint verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/pending/reconcile/compliance-status/verify-checkpoint-history")
    async def verify_reconcile_compliance_chain_checkpoint_history_api(
        limit: int = 200,
        require_signature_payload: bool = False,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Verify integrity of recent compliance checkpoint events, including signature checks when possible."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import verify_reconcile_compliance_chain_checkpoint_history

            result = verify_reconcile_compliance_chain_checkpoint_history(
                limit=max(1, min(1000, int(limit))),
                require_signature_payload=bool(require_signature_payload),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile compliance checkpoint history verify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/signature-receipts/prune")
    async def prune_reconcile_signature_receipts_api(
        payload: ReconcileSignatureReceiptsPruneRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Prune stale signature receipt events with dry-run support."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import prune_reconcile_signature_receipts

            result = prune_reconcile_signature_receipts(
                max_age_days=max(1, int(payload.max_age_days)),
                dry_run=bool(payload.dry_run),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile signature receipts prune API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/reconcile/signature-receipts/checkpoint")
    async def create_reconcile_signature_chain_checkpoint_api(
        payload: ReconcileSignatureChainCheckpointRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Create a signed chain checkpoint anchored to latest signature receipt artifact head."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import create_reconcile_signature_chain_checkpoint

            result = create_reconcile_signature_chain_checkpoint(
                label=str(payload.label or "ops"),
                note=str(payload.note or ""),
                expected_previous_digest=str(payload.expected_previous_digest or ""),
                require_head=bool(payload.require_head),
            )
            if not result.get("success", False):
                message = str(result.get("error", "Checkpoint creation failed"))
                if "not found" in message.lower() or "no artifact head" in message.lower():
                    raise HTTPException(status_code=404, detail=message)
                raise HTTPException(status_code=400, detail=message)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament reconcile signature chain checkpoint API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/pending/finalize")
    async def finalize_pending_paid_entry_api(
        payload: FinalizePendingRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Finalize one pending paid tournament entry by checkout session id."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import finalize_pending_paid_entry

            result = finalize_pending_paid_entry(
                checkout_session_id=str(payload.checkout_session_id or "").strip(),
                payment_reference=str(payload.payment_reference or "").strip(),
            )
            if result.get("success", False):
                return {"ok": True, "result": result}

            error_message = str(result.get("error", "Pending finalization failed"))
            if "not found" in error_message.lower():
                raise HTTPException(status_code=404, detail=error_message)
            raise HTTPException(status_code=400, detail=error_message)
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament pending finalize API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/sports")
    async def list_tournament_sports_api(
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Return supported tournament sport router handlers."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import get_supported_tournament_sports

            rows = list(get_supported_tournament_sports() or [])
            return {"ok": True, "count": len(rows), "rows": rows}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament sports list API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/subscriptions/status")
    async def upsert_subscription_status_api(
        payload: SubscriptionStatusUpsertRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Upsert one user's subscription status snapshot for access enforcement."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import upsert_user_subscription_status

            result = upsert_user_subscription_status(
                user_email=str(payload.user_email or "").strip().lower(),
                premium_active=bool(payload.premium_active),
                legend_pass_active=bool(payload.legend_pass_active),
                premium_expires_at=str(payload.premium_expires_at or ""),
                legend_pass_expires_at=str(payload.legend_pass_expires_at or ""),
                source=str(payload.source or "ops_api"),
                raw_payload=dict(payload.raw_payload or {}),
            )
            if result.get("success", False):
                return {"ok": True, "result": result}
            raise HTTPException(status_code=400, detail=str(result.get("error", "Subscription upsert failed")))
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament subscription upsert API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/subscriptions/status/{user_email}")
    async def get_subscription_status_api(
        user_email: str,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Fetch one user's persisted subscription status snapshot."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import get_user_subscription_status

            result = get_user_subscription_status(str(user_email or "").strip().lower())
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament subscription get API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/access/check")
    async def tournament_access_check_api(
        payload: TournamentAccessCheckRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Evaluate tournament access using persisted subscription status and gate rules."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import evaluate_user_tournament_access

            result = evaluate_user_tournament_access(
                user_email=str(payload.user_email or "").strip().lower(),
                court_tier=str(payload.court_tier or "").strip(),
                user_age=int(payload.user_age),
                state_code=str(payload.state_code or "").strip().upper(),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament access check API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/tournaments/create")
    async def create_tournament_api(
        payload: TournamentCreateRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Create a tournament with explicit sport routing metadata."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import create_tournament

            tid = create_tournament(
                tournament_name=str(payload.tournament_name or "").strip(),
                court_tier=str(payload.court_tier or "").strip(),
                entry_fee=float(payload.entry_fee),
                min_entries=max(1, int(payload.min_entries)),
                max_entries=max(2, int(payload.max_entries)),
                lock_time=str(payload.lock_time or "").strip(),
                reveal_mode=str(payload.reveal_mode or "instant").strip(),
                sport=str(payload.sport or "nba").strip().lower(),
            )
            return {"ok": True, "result": {"tournament_id": int(tid)}}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament create API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/connect/onboarding")
    async def create_connect_onboarding_api(
        payload: ConnectOnboardingRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Create Stripe Connect onboarding URL for one user."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import create_user_connect_onboarding

            result = create_user_connect_onboarding(
                user_email=str(payload.user_email or "").strip().lower(),
                refresh_path=str(payload.refresh_path or "/"),
                return_path=str(payload.return_path or "/"),
            )
            if result.get("success", False):
                return {"ok": True, "result": result}
            raise HTTPException(status_code=400, detail=str(result.get("error", "Connect onboarding failed")))
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament connect onboarding API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/connect/sync/{user_email}")
    async def sync_connect_status_api(
        user_email: str,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Sync one user's Stripe Connect account status from Stripe."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import sync_user_connect_status_from_stripe

            result = sync_user_connect_status_from_stripe(str(user_email or "").strip().lower())
            if result.get("success", False):
                return {"ok": True, "result": result.get("result", {})}
            raise HTTPException(status_code=400, detail=str(result.get("error", "Connect sync failed")))
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament connect sync API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/connect/status/{user_email}")
    async def get_connect_status_api(
        user_email: str,
        compliance_year: int | None = None,
        kyc_threshold_usd: float = 600.0,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Get persisted Stripe Connect + KYC compliance status for one user."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import get_user_connect_status

            result = get_user_connect_status(
                str(user_email or "").strip().lower(),
                compliance_year=compliance_year,
                kyc_threshold_usd=float(kyc_threshold_usd),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament connect status API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/payouts/eligibility")
    async def payout_eligibility_api(
        payload: PayoutEligibilityRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Evaluate payout eligibility under Connect + KYC rules."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import evaluate_user_payout_eligibility

            result = evaluate_user_payout_eligibility(
                user_email=str(payload.user_email or "").strip().lower(),
                compliance_year=payload.compliance_year,
                kyc_threshold_usd=float(payload.kyc_threshold_usd),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament payout eligibility API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.get("/payouts/due")
    async def list_due_payouts_api(
        sla_hours: int = 24,
        limit: int = 200,
        include_not_due: bool = False,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """List payout entries due under payout SLA window."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import list_due_payout_entries

            rows = list_due_payout_entries(
                sla_hours=max(1, int(sla_hours)),
                limit=max(1, min(1000, int(limit))),
                include_not_due=bool(include_not_due),
            )
            return {"ok": True, "count": len(rows), "rows": rows}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament due payouts list API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")


    @router.post("/payouts/process-due")
    async def process_due_payouts_api(
        payload: DuePayoutsProcessRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Process payouts for tournaments with due payout entries."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import process_due_payouts

            result = process_due_payouts(
                sla_hours=max(1, int(payload.sla_hours)),
                max_tournaments=max(1, int(payload.max_tournaments)),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("tournament process due payouts API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")

    @router.get("/season/leaderboard")
    async def season_leaderboard_api(
        year: int,
        month: int | None = None,
        quarter: int | None = None,
        limit: int = 100,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Return season-scoped LP leaderboard."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import list_season_lp_leaderboard

            rows = list_season_lp_leaderboard(year=year, month=month, quarter=quarter, limit=max(1, int(limit)))
            return {"ok": True, "count": len(rows), "rows": rows}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("season leaderboard API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")

    @router.post("/season/distribute-rewards")
    async def season_distribute_rewards_api(
        payload: SeasonDistributeRewardsRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Distribute season-end bonus LP and badge to top earners."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import distribute_season_end_rewards

            result = distribute_season_end_rewards(
                year=int(payload.year),
                month=int(payload.month),
                top_pct=float(payload.top_pct),
                bonus_lp=int(payload.bonus_lp),
            )
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("season distribute rewards API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")

    @router.post("/championship/qualify")
    async def championship_qualify_api(
        payload: ChampionshipQualifyRequest,
        x_tournament_admin_key: str = Header(default=""),
    ):
        """Create a Championship tournament and qualify top LP earners."""
        try:
            _require_admin_key(x_tournament_admin_key)

            from tournament import qualify_for_championship

            result = qualify_for_championship(
                payload.season_label,
                top_n=max(2, int(payload.top_n)),
                year=payload.year,
                month=payload.month,
                lock_offset_hours=max(1, int(payload.lock_offset_hours)),
                entry_fee=float(payload.entry_fee),
                max_entries=max(2, int(payload.max_entries)),
                sport=str(payload.sport),
            )
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("error", "Qualification failed"))
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            _logger.error("championship qualify API error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Tournament ops failure: {exc}")
