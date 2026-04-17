"""Tournament referral system helpers."""

from __future__ import annotations

import secrets
import string
import hashlib
from datetime import datetime, timezone

import tournament.database as tournament_db


def _normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def _new_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(max(6, int(length))))


def _default_display_name(email: str) -> str:
    local = _normalize_email(email).split("@")[0] or "user"
    digest = hashlib.sha256(_normalize_email(email).encode("utf-8")).hexdigest()[:4]
    return f"{local[:15]}{digest}"[:20]


def get_or_create_referral_code(user_email: str) -> dict:
    """Return stable referral code for a user, creating one if absent."""
    tournament_db.initialize_tournament_database()
    email = _normalize_email(user_email)
    if not email:
        return {"success": False, "error": "user_email is required"}

    with tournament_db.get_tournament_connection() as conn:
        existing = conn.execute(
            "SELECT referral_code FROM referral_codes WHERE owner_email = ? LIMIT 1",
            (email,),
        ).fetchone()
        if existing:
            return {"success": True, "owner_email": email, "referral_code": str(existing["referral_code"] or "")}

        for _ in range(10):
            code = _new_code()
            try:
                conn.execute(
                    "INSERT INTO referral_codes (referral_code, owner_email, created_at) VALUES (?, ?, datetime('now'))",
                    (code, email),
                )
                conn.commit()
                return {"success": True, "owner_email": email, "referral_code": code}
            except Exception:
                conn.rollback()
                continue

    return {"success": False, "error": "could not allocate referral code"}


def bind_referral_code(referred_user_email: str, referral_code: str) -> dict:
    """Attach one referral code to a referred user before first paid entry."""
    tournament_db.initialize_tournament_database()
    referred = _normalize_email(referred_user_email)
    code = str(referral_code or "").strip().upper()
    if not referred:
        return {"success": False, "error": "referred_user_email is required"}
    if not code:
        return {"success": False, "error": "referral_code is required"}

    with tournament_db.get_tournament_connection() as conn:
        owner = conn.execute(
            "SELECT owner_email FROM referral_codes WHERE referral_code = ? LIMIT 1",
            (code,),
        ).fetchone()
        if not owner:
            return {"success": False, "error": "invalid referral code"}
        referrer = _normalize_email(str(owner["owner_email"] or ""))
        if referrer == referred:
            return {"success": False, "error": "cannot refer yourself"}

        row = conn.execute(
            "SELECT referral_code, referrer_email FROM referral_relationships WHERE referred_email = ? LIMIT 1",
            (referred,),
        ).fetchone()
        if row:
            return {
                "success": True,
                "already_bound": True,
                "referred_email": referred,
                "referrer_email": str(row["referrer_email"] or ""),
                "referral_code": str(row["referral_code"] or ""),
            }

        conn.execute(
            """
            INSERT INTO referral_relationships
                (referral_code, referrer_email, referred_email, created_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (code, referrer, referred),
        )
        conn.execute(
            """
            INSERT INTO user_accounts (user_email, display_name, referred_by_code, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(user_email) DO UPDATE SET
                referred_by_code = COALESCE(user_accounts.referred_by_code, excluded.referred_by_code),
                updated_at = datetime('now')
            """,
            (referred, _default_display_name(referred), code),
        )
        conn.commit()

    return {"success": True, "referred_email": referred, "referrer_email": referrer, "referral_code": code}


def apply_first_paid_entry_referral_credit(
    *,
    referred_user_email: str,
    paid_entry_id: int,
    credit_amount: float = 5.0,
    monthly_cap: float = 50.0,
) -> dict:
    """Apply referral credit when referred user submits their first paid entry."""
    tournament_db.initialize_tournament_database()
    referred = _normalize_email(referred_user_email)
    if not referred:
        return {"success": False, "error": "referred_user_email is required"}

    with tournament_db.get_tournament_connection() as conn:
        rel = conn.execute(
            """
            SELECT referral_id, referral_code, referrer_email, first_paid_entry_id, credited_amount
            FROM referral_relationships
            WHERE referred_email = ?
            LIMIT 1
            """,
            (referred,),
        ).fetchone()
        if not rel:
            return {"success": True, "applied": False, "reason": "no_referral"}
        if int(rel["first_paid_entry_id"] or 0) > 0:
            return {"success": True, "applied": False, "reason": "already_credited"}

        referrer = _normalize_email(str(rel["referrer_email"] or ""))
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        monthly_total_row = conn.execute(
            """
            SELECT COALESCE(SUM(credited_amount), 0.0) AS total
            FROM referral_relationships
            WHERE referrer_email = ? AND credited_at IS NOT NULL AND credited_at >= ?
            """,
            (referrer, month_start),
        ).fetchone()
        monthly_total = float((monthly_total_row["total"] if monthly_total_row else 0.0) or 0.0)
        remaining = round(max(0.0, float(monthly_cap) - monthly_total), 2)
        if remaining <= 0:
            conn.execute(
                """
                UPDATE referral_relationships
                SET first_paid_entry_id = ?
                WHERE referral_id = ?
                """,
                (int(paid_entry_id), int(rel["referral_id"])),
            )
            conn.commit()
            return {"success": True, "applied": False, "reason": "monthly_cap_reached", "remaining_cap": remaining}

        credited = min(float(credit_amount), remaining)
        conn.execute(
            """
            UPDATE referral_relationships
            SET first_paid_entry_id = ?,
                credited_amount = ?,
                credited_at = datetime('now')
            WHERE referral_id = ?
            """,
            (int(paid_entry_id), credited, int(rel["referral_id"])),
        )
        conn.execute(
            """
            INSERT INTO user_accounts (user_email, display_name, referral_credit_balance, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(user_email) DO UPDATE SET
                referral_credit_balance = user_accounts.referral_credit_balance + excluded.referral_credit_balance,
                updated_at = datetime('now')
            """,
            (referrer, _default_display_name(referrer), credited),
        )
        conn.commit()

    return {
        "success": True,
        "applied": True,
        "referrer_email": referrer,
        "referred_email": referred,
        "credited_amount": credited,
        "entry_id": int(paid_entry_id),
    }
