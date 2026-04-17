"""Integration tests for tournament.referrals."""

from tournament.accounts import get_user_account
from tournament.referrals import (
    apply_first_paid_entry_referral_credit,
    bind_referral_code,
    get_or_create_referral_code,
)


def test_referral_code_stable_per_user(isolated_db):
    a = get_or_create_referral_code("owner@test.com")
    b = get_or_create_referral_code("owner@test.com")
    assert a["success"] is True
    assert b["success"] is True
    assert a["referral_code"] == b["referral_code"]


def test_bind_and_credit_first_paid_entry(isolated_db):
    owner = get_or_create_referral_code("owner@test.com")
    code = owner["referral_code"]
    bind = bind_referral_code("new_user@test.com", code)
    assert bind["success"] is True

    applied = apply_first_paid_entry_referral_credit(
        referred_user_email="new_user@test.com",
        paid_entry_id=101,
    )
    assert applied["success"] is True
    assert applied["applied"] is True
    assert float(applied["credited_amount"]) == 5.0

    owner_account = get_user_account("owner@test.com")
    assert float(owner_account.get("referral_credit_balance", 0.0) or 0.0) == 5.0

    second = apply_first_paid_entry_referral_credit(
        referred_user_email="new_user@test.com",
        paid_entry_id=102,
    )
    assert second["success"] is True
    assert second["applied"] is False


def test_referral_monthly_cap(isolated_db):
    owner = get_or_create_referral_code("cap_owner@test.com")
    code = owner["referral_code"]

    applied_count = 0
    blocked_count = 0
    for idx in range(1, 13):
        referred = f"user{idx}@test.com"
        bind_referral_code(referred, code)
        result = apply_first_paid_entry_referral_credit(
            referred_user_email=referred,
            paid_entry_id=1000 + idx,
        )
        if result.get("applied", False):
            applied_count += 1
        elif result.get("reason") == "monthly_cap_reached":
            blocked_count += 1

    assert applied_count == 10
    assert blocked_count >= 1
    owner_account = get_user_account("cap_owner@test.com")
    assert float(owner_account.get("referral_credit_balance", 0.0) or 0.0) == 50.0

