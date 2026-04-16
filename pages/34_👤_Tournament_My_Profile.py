import streamlit as st

from tournament import (
    get_user_career_stats,
    list_career_leaderboard,
    list_user_entries,
    list_user_notifications,
)

st.set_page_config(page_title="Tournament My Profile", page_icon="👤", layout="wide")
st.title("👤 Tournament My Profile (Standalone)")
st.caption("Personal tournament history sourced only from the isolated subsystem.")

email = st.text_input("Email", value=st.session_state.get("tournament_email", ""))
if not email:
    st.info("Enter your tournament email to view profile and history.")
    st.stop()

st.session_state["tournament_email"] = email

career = get_user_career_stats(email)
leaderboard = list_career_leaderboard(limit=200)
my_rank = None
for row in leaderboard:
    if str(row.get("user_email", "")).strip().lower() == email.strip().lower():
        my_rank = int(row.get("rank", 0))
        break

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.metric("Entries", int(career.get("lifetime_entries", 0)))
with c2:
    st.metric("Wins", int(career.get("lifetime_wins", 0)))
with c3:
    st.metric("Top 5", int(career.get("lifetime_top5", 0)))
with c4:
    st.metric("Lifetime LP", int(career.get("lifetime_lp", 0)))
with c5:
    st.metric("Earnings", f"${float(career.get('lifetime_earnings', 0.0)):.2f}")
with c6:
    st.metric("Leaderboard Rank", f"#{my_rank}" if my_rank else "Unranked")

st.subheader("Season Leaderboard")
if not leaderboard:
    st.info("No leaderboard data yet.")
else:
    st.dataframe(
        [
            {
                "rank": row.get("rank"),
                "user": row.get("display_name") or row.get("user_email"),
                "lp": row.get("lifetime_lp"),
                "wins": row.get("lifetime_wins"),
                "top5": row.get("lifetime_top5"),
                "earnings": row.get("lifetime_earnings"),
                "level": row.get("career_level"),
            }
            for row in leaderboard[:25]
        ],
        use_container_width=True,
        hide_index=True,
    )

st.subheader("Entry History")
entries = list_user_entries(email, limit=200)
if not entries:
    st.info("No entries found.")
else:
    st.dataframe(
        [
            {
                "time": row.get("created_at"),
                "tournament": row.get("tournament_name"),
                "tier": row.get("court_tier"),
                "status": row.get("status"),
                "score": row.get("total_score"),
                "rank": row.get("rank"),
                "lp": row.get("lp_awarded"),
                "payout": row.get("payout_amount"),
            }
            for row in entries
        ],
        use_container_width=True,
        hide_index=True,
    )

st.subheader("Notifications")
notes = list_user_notifications(email, limit=100)
if not notes:
    st.info("No notifications yet.")
else:
    st.dataframe(
        [
            {
                "time": n.get("created_at"),
                "type": n.get("event_type"),
                "message": n.get("message"),
                "tournament": n.get("tournament_id"),
            }
            for n in notes
        ],
        use_container_width=True,
        hide_index=True,
    )
