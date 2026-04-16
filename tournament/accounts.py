"""Tournament user registration + email verification helpers."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

import tournament.database as tournament_db

DISPLAY_NAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def _normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def validate_display_name(display_name: str) -> tuple[bool, str]:
    value = str(display_name or "").strip()
    if not DISPLAY_NAME_RE.fullmatch(value):
        return False, "display_name must be 3-20 characters (letters, numbers, underscore)"
    return True, ""


def _hash_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def register_user_account(user_email: str, display_name: str) -> dict:
    """Register a user account with unique email and display name."""
    tournament_db.initialize_tournament_database()
    email = _normalize_email(user_email)
    if not email:
        return {"success": False, "error": "user_email is required"}

    valid_name, reason = validate_display_name(display_name)
    if not valid_name:
        return {"success": False, "error": reason}

    name = str(display_name).strip()
    with tournament_db.get_tournament_connection() as conn:
        existing_by_name = conn.execute(
            "SELECT user_email FROM user_accounts WHERE LOWER(display_name) = LOWER(?) LIMIT 1",
            (name,),
        ).fetchone()
        if existing_by_name and str(existing_by_name["user_email"] or "").strip().lower() != email:
            return {"success": False, "error": "display_name already taken"}

        conn.execute(
            """
            INSERT INTO user_accounts
                (user_email, display_name, email_verified, updated_at)
            VALUES (?, ?, 0, datetime('now'))
            ON CONFLICT(user_email) DO UPDATE SET
                display_name=excluded.display_name,
                updated_at=datetime('now')
            """,
            (email, name),
        )
        conn.commit()
    return {"success": True, "user_email": email, "display_name": name}


def create_email_verification_token(user_email: str, ttl_hours: int = 48) -> dict:
    """Create and persist an email verification token for a registered user."""
    tournament_db.initialize_tournament_database()
    email = _normalize_email(user_email)
    if not email:
        return {"success": False, "error": "user_email is required"}

    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=max(1, int(ttl_hours)))).isoformat()

    with tournament_db.get_tournament_connection() as conn:
        row = conn.execute(
            "SELECT user_email FROM user_accounts WHERE user_email = ? LIMIT 1",
            (email,),
        ).fetchone()
        if not row:
            return {"success": False, "error": "user account not found"}

        conn.execute(
            """
            UPDATE user_accounts
            SET verification_token_hash = ?,
                verification_expires_at = ?,
                updated_at = datetime('now')
            WHERE user_email = ?
            """,
            (token_hash, expires_at, email),
        )
        conn.commit()

    return {"success": True, "user_email": email, "token": token, "expires_at": expires_at}


def verify_user_email(user_email: str, token: str) -> dict:
    """Verify account email using a previously issued token."""
    tournament_db.initialize_tournament_database()
    email = _normalize_email(user_email)
    if not email:
        return {"success": False, "error": "user_email is required"}

    provided_hash = _hash_token(token)
    now = datetime.now(timezone.utc)
    with tournament_db.get_tournament_connection() as conn:
        row = conn.execute(
            """
            SELECT verification_token_hash, verification_expires_at, email_verified
            FROM user_accounts
            WHERE user_email = ?
            LIMIT 1
            """,
            (email,),
        ).fetchone()
        if not row:
            return {"success": False, "error": "user account not found"}
        if bool(int(row["email_verified"] or 0)):
            return {"success": True, "already_verified": True, "user_email": email}

        expected_hash = str(row["verification_token_hash"] or "")
        if not expected_hash or provided_hash != expected_hash:
            return {"success": False, "error": "invalid verification token"}

        expires_raw = str(row["verification_expires_at"] or "")
        if not expires_raw:
            return {"success": False, "error": "verification token expired"}
        try:
            expires_dt = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
        except ValueError:
            return {"success": False, "error": "verification token expired"}
        if expires_dt < now:
            return {"success": False, "error": "verification token expired"}

        conn.execute(
            """
            UPDATE user_accounts
            SET email_verified = 1,
                verified_at = datetime('now'),
                verification_token_hash = NULL,
                verification_expires_at = NULL,
                updated_at = datetime('now')
            WHERE user_email = ?
            """,
            (email,),
        )
        conn.commit()

    return {"success": True, "user_email": email, "verified": True}


def get_user_account(user_email: str) -> dict:
    """Return user account row for one email."""
    tournament_db.initialize_tournament_database()
    email = _normalize_email(user_email)
    with tournament_db.get_tournament_connection() as conn:
        row = conn.execute(
            """
            SELECT
                user_email,
                display_name,
                email_verified,
                verification_expires_at,
                verified_at,
                referred_by_code,
                referral_credit_balance,
                created_at,
                updated_at
            FROM user_accounts
            WHERE user_email = ?
            LIMIT 1
            """,
            (email,),
        ).fetchone()
    return dict(row) if row else {}
