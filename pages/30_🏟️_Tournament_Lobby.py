import datetime as dt

import streamlit as st

from tournament import (
    create_tournament,
    get_supported_tournament_sports,
    get_user_subscription_status,
    upsert_user_subscription_status,
    get_checkout_session_record,
    get_checkout_session_details,
    get_pending_paid_entry,
    mark_pending_paid_entry_finalized,
    ensure_profile_pool,
    get_tournament_scoreboard,
    initialize_tournament_database,
    list_open_tournaments,
    list_tournaments,
    list_user_entries,
    resolve_tournament,
    submit_paid_entry_after_checkout,
)

st.set_page_config(page_title="Tournament Lobby", page_icon="🏟️", layout="wide")
st.title("🏟️ Tournament Lobby (Standalone)")
st.caption("This page uses only the isolated tournament subsystem.")

initialize_tournament_database()

with st.sidebar:
    st.subheader("Profile Pool")
    if st.button("Bootstrap Player Profiles", use_container_width=True):
        if ensure_profile_pool is None:
            st.warning("Profile bootstrap unavailable in this environment.")
        else:
            result = ensure_profile_pool()
            if result["ok"]:
                st.success(f"Profiles ready: {result['generated_profiles']}")
            else:
                st.warning(f"Only {result['generated_profiles']} profiles generated")

    st.markdown("---")
    st.subheader("Subscription Access")
    sub_email = st.text_input("User Email", value=st.session_state.get("tournament_email", "")).strip().lower()
    existing_sub = get_user_subscription_status(sub_email) if sub_email else {}
    premium_active = st.checkbox("Premium Active", value=bool(existing_sub.get("premium_active", False)))
    legend_active = st.checkbox("Legend Pass Active", value=bool(existing_sub.get("legend_pass_active", False)))
    if st.button("Save Subscription Status", use_container_width=True):
        if not sub_email:
            st.error("Enter a user email first.")
        else:
            saved = upsert_user_subscription_status(
                sub_email,
                premium_active=premium_active,
                legend_pass_active=legend_active,
                source="lobby_sidebar",
            )
            if saved.get("success"):
                st.success("Subscription status saved.")
            else:
                st.error(str(saved.get("error", "Save failed")))

    st.markdown("---")
    st.subheader("Paid Entry Finalization")
    qp = st.query_params
    callback_sid = str(qp.get("session_id", "") or "").strip()
    callback_tid = str(qp.get("tournament_id", "") or "").strip()

    if callback_sid:
        st.caption(f"Session: {callback_sid}")
        pending = get_pending_paid_entry(callback_sid)
        if not pending:
            st.warning("No pending paid entry found for this checkout session.")
        else:
            expected_tid = str(pending.get("tournament_id", ""))
            if callback_tid and callback_tid != expected_tid:
                st.error("Callback tournament mismatch with pending entry.")
            else:
                if st.button("Finalize Paid Entry (From Callback)", use_container_width=True):
                    details = get_checkout_session_details(callback_sid)
                    if not details.get("success"):
                        record = get_checkout_session_record(callback_sid)
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

                    if str(details.get("tournament_id", "")) != expected_tid:
                        st.error("Checkout tournament mismatch.")
                        st.stop()

                    verified_email = str(details.get("customer_email", "")).strip().lower()
                    pending_email = str(pending.get("user_email", "")).strip().lower()
                    if verified_email and pending_email and verified_email != pending_email:
                        st.error("Checkout email does not match pending entry email.")
                        st.stop()

                    payment_ref = str(details.get("payment_intent_id", "") or callback_sid)
                    ok, msg, entry_id = submit_paid_entry_after_checkout(
                        tournament_id=int(pending.get("tournament_id", 0) or 0),
                        user_email=str(pending.get("user_email", "")),
                        display_name=str(pending.get("display_name", "")),
                        roster=list(pending.get("roster", [])),
                        checkout_session_id=payment_ref,
                    )
                    if ok:
                        mark_pending_paid_entry_finalized(callback_sid, payment_ref)
                        st.success(f"Entry #{entry_id} finalized. {msg}")
                    else:
                        st.error(msg)
    else:
        st.caption("Return from Stripe checkout to finalize paid entries here.")

st.subheader("Create Tournament")
with st.form("create_tournament_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        tournament_name = st.text_input("Tournament Name", value="Tonight Open")
        court_tier = st.selectbox("Court Tier", ["Open", "Pro", "Elite", "Championship"], index=0)
    with c2:
        entry_fee = st.number_input("Entry Fee (USD)", min_value=0.0, max_value=500.0, step=5.0, value=0.0)
        min_entries = st.number_input("Minimum Entries", min_value=1, max_value=64, value=8)
    with c3:
        max_entries = st.number_input("Maximum Entries", min_value=2, max_value=128, value=24)
        lock_hours = st.number_input("Hours Until Lock", min_value=1, max_value=168, value=6)

    reveal_mode = st.selectbox("Reveal Mode", ["instant", "staged"], index=0)
    sports = list(get_supported_tournament_sports() or [])
    sport_codes = [str(s.get("sport", "nba")) for s in sports] or ["nba"]
    sport = st.selectbox("Sport", sport_codes, index=0)
    submitted = st.form_submit_button("Create Tournament", use_container_width=True)

if submitted:
    lock_time = (dt.datetime.utcnow() + dt.timedelta(hours=int(lock_hours))).isoformat()
    tid = create_tournament(
        tournament_name=tournament_name,
        court_tier=court_tier,
        entry_fee=float(entry_fee),
        min_entries=int(min_entries),
        max_entries=int(max_entries),
        lock_time=lock_time,
        reveal_mode=reveal_mode,
        sport=sport,
    )
    st.success(f"Tournament created: #{tid}")

tab_open, tab_upcoming, tab_results, tab_my = st.tabs([
    "Open",
    "Upcoming",
    "Results",
    "My Entries",
])

with tab_open:
    st.subheader("Open Tournaments")
    open_tournaments = list_open_tournaments()
    if not open_tournaments:
        st.info("No open tournaments yet.")
    else:
        for t in open_tournaments:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    st.markdown(f"**#{t['tournament_id']} {t['tournament_name']}**")
                    st.write(f"Sport: {str(t.get('sport', 'nba')).upper()} | Tier: {t['court_tier']} | Fee: ${t['entry_fee']:.2f}")
                    st.write(f"Lock: {t['lock_time']} | Status: {t['status']}")
                with c2:
                    if st.button("Set Active", key=f"set_{t['tournament_id']}"):
                        st.session_state["tournament_selected_id"] = int(t["tournament_id"])
                        st.success(f"Active tournament set to #{t['tournament_id']}")
                with c3:
                    if st.button("Resolve Now", key=f"resolve_{t['tournament_id']}"):
                        result = resolve_tournament(int(t["tournament_id"]))
                        if result.get("success"):
                            st.success(f"Resolved #{t['tournament_id']} ({result.get('status')})")
                        else:
                            st.error(result.get("error", "Resolve failed"))

with tab_upcoming:
    st.subheader("Upcoming / Scheduled")
    scheduled = list_tournaments(status="scheduled")
    if not scheduled:
        st.info("No scheduled tournaments.")
    else:
        for t in scheduled:
            with st.container(border=True):
                st.markdown(f"**#{t['tournament_id']} {t['tournament_name']}**")
                st.write(f"Sport: {str(t.get('sport', 'nba')).upper()} | Tier: {t['court_tier']} | Fee: ${t['entry_fee']:.2f}")
                st.write(f"Lock: {t['lock_time']} | Status: {t['status']}")

with tab_results:
    st.subheader("Recent Resolved / Cancelled")
    resolved = list_tournaments(status="resolved")[:10]
    cancelled = list_tournaments(status="cancelled")[:10]

    if not resolved and not cancelled:
        st.info("No completed tournaments yet.")

    for t in resolved:
        with st.expander(f"Resolved #{t['tournament_id']} - {t['tournament_name']}", expanded=False):
            st.write(f"Sport: {str(t.get('sport', 'nba')).upper()} | Tier: {t['court_tier']} | Fee: ${t['entry_fee']:.2f}")
            scoreboard = get_tournament_scoreboard(int(t["tournament_id"]))
            if scoreboard:
                st.dataframe(scoreboard[:10], use_container_width=True)
            else:
                st.caption("No scores found.")

    for t in cancelled:
        with st.container(border=True):
            st.markdown(f"**Cancelled #{t['tournament_id']} {t['tournament_name']}**")
            st.write(f"Sport: {str(t.get('sport', 'nba')).upper()} | Tier: {t['court_tier']} | Fee: ${t['entry_fee']:.2f}")
            st.write(f"Lock: {t['lock_time']}")

with tab_my:
    st.subheader("My Entry History")
    user_email = st.text_input("User Email", value=st.session_state.get("tournament_email", ""))
    st.session_state["tournament_email"] = user_email

    if user_email.strip():
        entries = list_user_entries(user_email.strip(), limit=50)
        if entries:
            st.dataframe(entries, use_container_width=True)
        else:
            st.info("No entries found for this email.")
    else:
        st.caption("Enter an email to view tournament history.")
