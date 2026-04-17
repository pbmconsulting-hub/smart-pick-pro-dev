"""Integration tests for tournament.accounts."""

from tournament.accounts import (
    create_email_verification_token,
    get_user_account,
    register_user_account,
    verify_user_email,
)


def test_register_user_account_and_uniqueness(isolated_db):
    ok = register_user_account("alpha@test.com", "Alpha_123")
    assert ok["success"] is True

    conflict = register_user_account("beta@test.com", "Alpha_123")
    assert conflict["success"] is False
    assert "display_name already taken" in conflict["error"]


def test_register_user_account_display_name_validation(isolated_db):
    bad = register_user_account("alpha@test.com", "no")
    assert bad["success"] is False

    good = register_user_account("alpha@test.com", "Valid_Name_7")
    assert good["success"] is True


def test_email_verification_flow(isolated_db):
    register_user_account("verified@test.com", "Verified_01")
    token_result = create_email_verification_token("verified@test.com")
    assert token_result["success"] is True
    token = token_result["token"]

    invalid = verify_user_email("verified@test.com", "wrong-token")
    assert invalid["success"] is False

    verified = verify_user_email("verified@test.com", token)
    assert verified["success"] is True
    account = get_user_account("verified@test.com")
    assert int(account.get("email_verified", 0) or 0) == 1

