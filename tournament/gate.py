"""Standalone tournament access gate checks."""

from __future__ import annotations

from datetime import datetime, timezone


BLOCKED_STATES_DEFAULT = {"WA", "ID", "MT", "HI", "NV"}
AGE_21_STATES = {"MA", "AZ", "IA"}


def _normalize_state(state_code: str) -> str:
    return (state_code or "").strip().upper()


def _required_age_for_state(state_code: str) -> int:
    return 21 if _normalize_state(state_code) in AGE_21_STATES else 18


def evaluate_tournament_access(
    court_tier: str,
    *,
    is_premium: bool,
    has_legend_pass: bool,
    user_age: int,
    state_code: str,
    blocked_states: set[str] | None = None,
    subscription_status: dict | None = None,
    now_utc: datetime | None = None,
) -> dict:
    """Evaluate whether a user can enter a tournament in the isolated system."""
    blocked = blocked_states or BLOCKED_STATES_DEFAULT
    state = _normalize_state(state_code)

    reasons: list[str] = []
    allowed = True

    if state in blocked:
        allowed = False
        reasons.append(f"Blocked in {state}")

    min_age = _required_age_for_state(state)
    if int(user_age) < min_age:
        allowed = False
        reasons.append(f"Must be {min_age}+ in {state or 'your state'}")

    tier = (court_tier or "Open").strip().lower()
    paid_tier = tier in {"pro", "elite", "championship"}

    if paid_tier and not is_premium:
        allowed = False
        reasons.append("Premium required for paid tournaments")

    # If your flow adds mandatory legend slot checks by tier later,
    # this gate already supports it.
    requires_legend_pass = tier in {"championship"}
    if requires_legend_pass and not has_legend_pass:
        allowed = False
        reasons.append("Legend Pass required for Championship")

    # Optional stronger enforcement using live subscription status snapshot.
    if subscription_status:
        now_dt = now_utc or datetime.now(timezone.utc)
        premium_active = bool(subscription_status.get("premium_active", False))
        legend_active = bool(subscription_status.get("legend_pass_active", False))
        premium_exp = str(subscription_status.get("premium_expires_at", "") or "").strip()
        legend_exp = str(subscription_status.get("legend_pass_expires_at", "") or "").strip()

        if premium_exp:
            try:
                premium_active = premium_active and datetime.fromisoformat(premium_exp.replace("Z", "+00:00")) >= now_dt
            except ValueError:
                premium_active = bool(subscription_status.get("premium_active", False))

        if legend_exp:
            try:
                legend_active = legend_active and datetime.fromisoformat(legend_exp.replace("Z", "+00:00")) >= now_dt
            except ValueError:
                legend_active = bool(subscription_status.get("legend_pass_active", False))

        if paid_tier and not premium_active:
            allowed = False
            reasons.append("Premium subscription inactive")

        if requires_legend_pass and not legend_active:
            allowed = False
            reasons.append("Legend Pass subscription inactive")

    return {
        "allowed": allowed,
        "reasons": reasons,
        "min_age": min_age,
        "blocked": state in blocked,
        "requires_premium": paid_tier,
        "requires_legend_pass": requires_legend_pass,
    }
