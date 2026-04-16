import streamlit as st

from tournament import (
    create_tournament_entry_checkout_session,
    evaluate_user_tournament_access,
    get_user_subscription_status,
    get_checkout_session_record,
    get_checkout_session_details,
    get_pending_paid_entry,
    list_open_tournaments,
    list_player_profiles,
    mark_pending_paid_entry_finalized,
    save_pending_paid_entry,
    submit_entry,
    submit_paid_entry_after_checkout,
    upsert_user_subscription_status,
)

st.set_page_config(page_title="Tournament Roster Builder", page_icon="🏗️", layout="wide")
st.title("🏗️ Tournament Roster Builder (Standalone)")
st.caption("Build and submit entries to the isolated tournament subsystem.")

ACTIVE_CAP = 50000
ACTIVE_FLOOR = 40000
ACTIVE_SLOTS = 8
PAID_TOTAL_SLOTS = 9
FREE_TOTAL_SLOTS = 8
MAX_TEAM_PLAYERS = 3


def _validate_roster_ui(roster: list[dict], *, is_paid: bool) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if not roster:
        errors.append("Roster is empty.")
        return False, errors

    expected_slots = PAID_TOTAL_SLOTS if is_paid else FREE_TOTAL_SLOTS
    if len(roster) != expected_slots:
        errors.append(f"Roster must include exactly {expected_slots} players.")

    ids = [str(p.get("player_id", "")) for p in roster]
    if len(ids) != len(set(ids)):
        errors.append("Roster cannot include duplicate players.")

    legends = [p for p in roster if bool(p.get("is_legend", False))]
    active = [p for p in roster if not bool(p.get("is_legend", False))]

    if is_paid and len(legends) != 1:
        errors.append("Paid tournaments require exactly one legend.")
    if is_paid and len(active) != ACTIVE_SLOTS:
        errors.append("Paid tournaments require exactly eight active players.")

    active_salary = sum(int(p.get("salary", 0) or 0) for p in active)
    legend_salary = sum(int(p.get("salary", 0) or 0) for p in legends)

    if is_paid and active_salary > ACTIVE_CAP:
        errors.append(f"Active salary cap exceeded (${ACTIVE_CAP}).")
    if is_paid and active_salary < ACTIVE_FLOOR:
        errors.append(f"Active salary floor not met (${ACTIVE_FLOOR}).")
    if is_paid and legend_salary > 15000:
        errors.append("Legend salary cap exceeded ($15000).")

    team_counts: dict[str, int] = {}
    for p in active:
        team = str(p.get("team", "")).strip().upper()
        if not team:
            continue
        team_counts[team] = team_counts.get(team, 0) + 1
    over_team_limit = [team for team, cnt in team_counts.items() if cnt > MAX_TEAM_PLAYERS]
    if over_team_limit:
        errors.append(f"Too many players from one team (max {MAX_TEAM_PLAYERS}): {', '.join(over_team_limit)}")

    return len(errors) == 0, errors

open_tournaments = list_open_tournaments()
if not open_tournaments:
    st.warning("No open tournaments available. Create one in Tournament Lobby.")
    st.stop()

ids = [t["tournament_id"] for t in open_tournaments]
default_tid = st.session_state.get("tournament_selected_id", ids[0])
if default_tid not in ids:
    default_tid = ids[0]

selected_tid = st.selectbox("Select Tournament", ids, index=ids.index(default_tid), format_func=lambda x: f"#{x}")
st.session_state["tournament_selected_id"] = selected_tid
selected_tournament = [t for t in open_tournaments if t["tournament_id"] == selected_tid][0]

st.write(
    f"Tier: {selected_tournament['court_tier']} | Fee: ${selected_tournament['entry_fee']:.2f} | "
    f"Lock: {selected_tournament['lock_time']}"
)

profiles = list_player_profiles(include_legends=True, limit=220)
if not profiles:
    st.warning("No profiles in tournament DB. Use Bootstrap Player Profiles on Tournament Lobby.")
    st.stop()

is_paid_tournament = float(selected_tournament.get("entry_fee", 0.0) or 0.0) > 0

search = st.text_input("Search Player", value="").strip().lower()
position_filter = st.selectbox("Position Filter", ["ALL", "PG", "SG", "SF", "PF", "C"])
legend_filter = st.selectbox("Pool", ["ALL", "ACTIVE", "LEGENDS"])

filtered_active = []
filtered_legends = []
for p in profiles:
    if search and search not in str(p.get("player_name", "")).lower():
        continue
    if position_filter != "ALL" and str(p.get("position", "")) != position_filter:
        continue
    is_legend = bool(p.get("is_legend", False))
    if legend_filter == "ACTIVE" and is_legend:
        continue
    if legend_filter == "LEGENDS" and not is_legend:
        continue
    if is_legend:
        filtered_legends.append(p)
    else:
        filtered_active.append(p)

active_label_map = {}
for p in filtered_active:
    team = str(p.get("team", "")).strip().upper() or "N/A"
    label = f"{p.get('player_name')} ({p.get('position')}, {team}) - ${int(p.get('salary', 0))}"
    active_label_map[label] = p

legend_label_map = {}
for p in filtered_legends:
    label = f"{p.get('player_name')} ({p.get('position')}) - ${int(p.get('salary', 0))}"
    legend_label_map[label] = p

st.subheader("Roster Construction")

default_active = st.session_state.get("tournament_active_labels", [])
active_selected_labels = st.multiselect(
    f"Active Players (select {ACTIVE_SLOTS})",
    options=list(active_label_map.keys()),
    default=[x for x in default_active if x in active_label_map],
    max_selections=ACTIVE_SLOTS,
)
st.session_state["tournament_active_labels"] = active_selected_labels

legend_selected_label = None
if is_paid_tournament:
    default_legend = st.session_state.get("tournament_legend_label", "")
    legend_options = ["(none)"] + list(legend_label_map.keys())
    if default_legend not in legend_options:
        default_legend = "(none)"
    legend_selected_label = st.selectbox(
        "Legend Slot (required for paid tournaments)",
        options=legend_options,
        index=legend_options.index(default_legend),
    )
    st.session_state["tournament_legend_label"] = legend_selected_label

selected_players = [active_label_map[l] for l in active_selected_labels]
if is_paid_tournament and legend_selected_label and legend_selected_label != "(none)":
    selected_players.append(legend_label_map[legend_selected_label])

active_salary = sum(int(p.get("salary", 0)) for p in selected_players if not bool(p.get("is_legend", False)))
legend_salary = sum(int(p.get("salary", 0)) for p in selected_players if bool(p.get("is_legend", False)))

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Players", len(selected_players))
with c2:
    st.metric("Active Salary", f"${active_salary}")
with c3:
    st.metric("Legend Salary", f"${legend_salary}")

c4, c5 = st.columns(2)
with c4:
    st.metric("Active Cap", f"${ACTIVE_CAP}")
with c5:
    st.metric("Active Floor", f"${ACTIVE_FLOOR}" if is_paid_tournament else "N/A")

valid_roster, roster_errors = _validate_roster_ui(selected_players, is_paid=is_paid_tournament)
if valid_roster:
    st.success("Roster checks passed.")
else:
    for err in roster_errors:
        st.warning(err)

with st.expander("Selected Roster", expanded=True):
    if selected_players:
        st.dataframe(
            [
                {
                    "player_id": p.get("player_id"),
                    "name": p.get("player_name"),
                    "pos": p.get("position"),
                    "legend": bool(p.get("is_legend", False)),
                    "salary": int(p.get("salary", 0)),
                    "ovr": int(p.get("overall_rating", 0)),
                }
                for p in selected_players
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No players selected.")

st.subheader("Submit Entry")
email = st.text_input("Email", value=st.session_state.get("tournament_email", ""))
display_name = st.text_input("Display Name", value=st.session_state.get("tournament_display_name", ""))

st.markdown("### Access Profile")
access_col1, access_col2, access_col3, access_col4 = st.columns(4)
existing_sub = get_user_subscription_status(email.strip().lower()) if email.strip() else {}
with access_col1:
    access_state = st.text_input("State", value=st.session_state.get("tournament_access_state", "CA")).strip().upper()
    st.session_state["tournament_access_state"] = access_state
with access_col2:
    access_age = st.number_input("Age", min_value=13, max_value=120, value=int(st.session_state.get("tournament_access_age", 25)))
    st.session_state["tournament_access_age"] = int(access_age)
with access_col3:
    premium_toggle = st.checkbox("Premium Active", value=bool(existing_sub.get("premium_active", False)))
with access_col4:
    legend_toggle = st.checkbox("Legend Pass Active", value=bool(existing_sub.get("legend_pass_active", False)))

if st.button("Save Access Profile", use_container_width=False):
    if not email.strip():
        st.error("Enter an email before saving access profile.")
    else:
        save_result = upsert_user_subscription_status(
            email.strip().lower(),
            premium_active=bool(premium_toggle),
            legend_pass_active=bool(legend_toggle),
            source="roster_builder",
        )
        if save_result.get("success"):
            st.success("Access profile saved.")
        else:
            st.error(str(save_result.get("error", "Could not save access profile")))


def _enforce_access_for_entry() -> tuple[bool, str]:
    if not email.strip():
        return False, "Email is required to evaluate access"

    upsert_user_subscription_status(
        email.strip().lower(),
        premium_active=bool(premium_toggle),
        legend_pass_active=bool(legend_toggle),
        source="roster_builder_runtime",
    )
    access = evaluate_user_tournament_access(
        user_email=email.strip().lower(),
        court_tier=str(selected_tournament.get("court_tier", "Open")),
        user_age=int(access_age),
        state_code=str(access_state),
    )
    if access.get("allowed", False):
        return True, ""
    reasons = list(access.get("reasons") or [])
    return False, "; ".join(str(r) for r in reasons) or "Access denied"

query_params = st.query_params
checkout_session_id = str(query_params.get("session_id", "") or "").strip()
checkout_tid = str(query_params.get("tournament_id", "") or "").strip()
checkout_cancelled = str(query_params.get("cancelled", "") or "").strip().lower() in {"1", "true", "yes"}

if is_paid_tournament:
    st.caption("Paid tournaments require successful Stripe checkout before finalizing entry.")
    if checkout_cancelled:
        st.warning("Checkout was cancelled. You can retry anytime.")
    if checkout_session_id:
        st.info(f"Checkout session detected: {checkout_session_id}")

    proceed_checkout_clicked = st.button("Proceed to Stripe Checkout", type="primary", use_container_width=True)
    if proceed_checkout_clicked:
        st.session_state["tournament_email"] = email
        st.session_state["tournament_display_name"] = display_name

        if not valid_roster:
            st.error("Fix roster validation errors before checkout.")
        elif not email.strip():
            st.error("Email is required for checkout.")
        else:
            allowed, access_error = _enforce_access_for_entry()
            if not allowed:
                st.error(f"Entry blocked by access policy: {access_error}")
                st.stop()
            checkout = create_tournament_entry_checkout_session(
                tournament_id=int(selected_tid),
                fee_usd=float(selected_tournament.get("entry_fee", 0.0) or 0.0),
                customer_email=email.strip().lower(),
                success_path="/",
                cancel_path="/",
            )
            if checkout.get("success"):
                saved = save_pending_paid_entry(
                    tournament_id=int(selected_tid),
                    user_email=email.strip().lower(),
                    display_name=display_name.strip(),
                    roster=selected_players,
                    checkout_session_id=str(checkout.get("session_id", "")),
                )
                if not saved:
                    st.error("Could not persist pending paid entry. Please try again.")
                else:
                    st.link_button("Open Stripe Checkout", url=str(checkout.get("url", "")), use_container_width=True)
                    st.caption("After payment, return to this page and finalize your entry.")
            else:
                st.error(str(checkout.get("error", "Stripe checkout failed")))

    pending = get_pending_paid_entry(checkout_session_id) if checkout_session_id else None
    pending = pending or {}
    pending_tid = int(pending.get("tournament_id", 0) or 0)
    callback_matches = bool(
        checkout_session_id
        and pending_tid > 0
        and (not checkout_tid or str(pending_tid) == checkout_tid)
    )
    if callback_matches:
        if st.button("Finalize Paid Entry", use_container_width=True):
            details = get_checkout_session_details(checkout_session_id)
            if not details.get("success"):
                record = get_checkout_session_record(checkout_session_id)
                if not record:
                    st.error(str(details.get("error", "Unable to verify checkout session")))
                    st.stop()
                details = {
                    "success": True,
                    "paid": str(record.get("payment_status", "")).lower() == "paid",
                    "tournament_id": str(record.get("tournament_id", "") or ""),
                    "customer_email": str(record.get("user_email", "") or ""),
                    "payment_intent_id": str(record.get("payment_intent_id", "") or ""),
                }

            if not bool(details.get("paid", False)):
                st.error("Checkout is not marked as paid yet.")
                st.stop()

            if str(details.get("tournament_id", "")) != str(pending_tid):
                st.error("Checkout tournament mismatch.")
                st.stop()

            verified_email = str(details.get("customer_email", "")).strip().lower()
            pending_email = str(pending.get("user_email", "")).strip().lower()
            if verified_email and pending_email and verified_email != pending_email:
                st.error("Checkout email does not match pending entry email.")
                st.stop()

            payment_ref = str(details.get("payment_intent_id", "") or checkout_session_id)
            ok, msg, entry_id = submit_paid_entry_after_checkout(
                tournament_id=int(pending["tournament_id"]),
                user_email=str(pending.get("user_email", "")),
                display_name=str(pending.get("display_name", "")),
                roster=list(pending.get("roster", [])),
                checkout_session_id=payment_ref,
            )
            if ok:
                st.success(f"Entry #{entry_id} finalized. {msg}")
                mark_pending_paid_entry_finalized(checkout_session_id, payment_ref)
            else:
                st.error(msg)
else:
    if st.button("Submit Entry", type="primary", use_container_width=True):
        st.session_state["tournament_email"] = email
        st.session_state["tournament_display_name"] = display_name

        if not valid_roster:
            st.error("Fix roster validation errors before submitting.")
        elif not email.strip():
            st.error("Email is required to submit.")
        else:
            allowed, access_error = _enforce_access_for_entry()
            if not allowed:
                st.error(f"Entry blocked by access policy: {access_error}")
                st.stop()
            ok, msg, entry_id = submit_entry(
                tournament_id=int(selected_tid),
                user_email=email,
                display_name=display_name,
                roster=selected_players,
            )
            if ok:
                st.success(f"Entry #{entry_id} submitted. {msg}")
            else:
                st.error(msg)
