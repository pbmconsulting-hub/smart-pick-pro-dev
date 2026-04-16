from tournament.jobs import run_tournament_jobs


def test_run_tournament_jobs_summary(monkeypatch):
    monkeypatch.setattr("tournament.jobs.create_weekly_schedule", lambda anchor_date=None: [1, 2, 3])
    monkeypatch.setattr("tournament.jobs.resolve_locked_tournaments", lambda now=None: [{"success": True}])
    monkeypatch.setattr("tournament.jobs.list_tournaments", lambda status=None: [{"tournament_id": 5}] if status in {"cancelled", "resolved"} else [])
    monkeypatch.setattr("tournament.jobs.process_cancelled_tournament_refunds", lambda tid: {"success": True, "refunded": 2})
    monkeypatch.setattr("tournament.jobs.process_resolved_tournament_payouts", lambda tid: {"success": True, "transferred": 1})
    monkeypatch.setattr("tournament.jobs.log_event", lambda *args, **kwargs: 1)

    summary = run_tournament_jobs(
        run_schedule_create=True,
        run_resolve_locked=True,
        run_refunds=True,
        run_payouts=True,
    )

    assert summary["scheduled_created"] == 3
    assert summary["resolved_attempts"] == 1
    assert summary["refund_total"] == 2
    assert summary["payout_total"] == 1


def test_run_tournament_jobs_due_payout_mode(monkeypatch):
    monkeypatch.setattr("tournament.jobs.create_weekly_schedule", lambda anchor_date=None: [])
    monkeypatch.setattr("tournament.jobs.resolve_locked_tournaments", lambda now=None: [])
    monkeypatch.setattr("tournament.jobs.list_tournaments", lambda status=None: [])
    monkeypatch.setattr("tournament.jobs.process_cancelled_tournament_refunds", lambda tid: {"success": True, "refunded": 0})
    monkeypatch.setattr(
        "tournament.jobs.process_due_payouts",
        lambda sla_hours=24, max_tournaments=50, now=None: {
            "success": True,
            "due_entries": 3,
            "processed_tournaments": 2,
            "transferred": 2,
            "failed": 1,
        },
    )
    monkeypatch.setattr("tournament.jobs.log_event", lambda *args, **kwargs: 1)

    summary = run_tournament_jobs(
        run_schedule_create=False,
        run_resolve_locked=False,
        run_refunds=False,
        run_payouts=True,
        run_due_payouts_only=True,
        payout_sla_hours=24,
        payout_max_tournaments=10,
    )

    assert summary["payout_total"] == 2
    assert summary["payout_runs"] == 2
    assert summary["payout_due_entries"] == 3
