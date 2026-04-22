# ============================================================
# FILE: pages/login.py
# PURPOSE: Public landing + auth page — accessible at /login
#          Unauthenticated visitors land here to subscribe or
#          restore their existing premium session.
#          After successful auth → redirects to Smart_Picks_Pro_Home.py
# ============================================================

import streamlit as st

st.set_page_config(
    page_title="Smart Pick Pro — Sign In",
    page_icon="🏀",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Auth: skip the gate if already authenticated ──────────────
import os
_PRODUCTION = os.environ.get("SMARTAI_PRODUCTION", "").lower() in ("true", "1", "yes")

try:
    from utils.auth import (
        is_premium_user,
        handle_checkout_redirect,
        restore_subscription_by_email,
    )
    from utils.stripe_manager import is_stripe_configured, create_checkout_session

    # Process a returning Stripe checkout redirect first
    _newly_subscribed = handle_checkout_redirect()

    if _newly_subscribed or is_premium_user():
        st.switch_page("Smart_Picks_Pro_Home.py")

    _stripe_on = is_stripe_configured()
except Exception:
    # Stripe/auth not configured — skip gate entirely
    st.switch_page("Smart_Picks_Pro_Home.py")
    st.stop()

# ── Inject global theme ───────────────────────────────────────
try:
    from styles.theme import get_global_css
    st.markdown(get_global_css(), unsafe_allow_html=True)
except Exception:
    pass

# ── Page CSS ──────────────────────────────────────────────────
st.markdown(r"""
<style>
/* ── Reset + base ─────────────────────────────────────── */
[data-testid="stAppViewContainer"] {
    background: #060b14 !important;
}
[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
footer { display: none !important; }

/* ── Ambient orbs ─────────────────────────────────────── */
@keyframes orbFloat {
    0%, 100% { transform: translate(0,0) scale(1); }
    40%  { transform: translate(28px,-18px) scale(1.08); }
    70%  { transform: translate(-18px,12px) scale(0.94); }
}
@keyframes orbFloat2 {
    0%, 100% { transform: translate(0,0) scale(1); }
    35%  { transform: translate(-36px,16px) scale(1.12); }
    65%  { transform: translate(16px,-24px) scale(0.92); }
}
.login-orbs {
    position: fixed; top:0; left:0; width:100%; height:100vh;
    pointer-events: none; z-index: 0; overflow: hidden;
}
.login-orb-1 {
    position:absolute; width:480px; height:480px; border-radius:50%;
    background: radial-gradient(circle, #00f0ff 0%, transparent 70%);
    filter: blur(90px); opacity: 0.07;
    top: -120px; right: -60px;
    animation: orbFloat 22s ease-in-out infinite;
}
.login-orb-2 {
    position:absolute; width:380px; height:380px; border-radius:50%;
    background: radial-gradient(circle, #c800ff 0%, transparent 70%);
    filter: blur(90px); opacity: 0.07;
    bottom: 5%; left: -80px;
    animation: orbFloat2 28s ease-in-out infinite;
}
.login-orb-3 {
    position:absolute; width:320px; height:320px; border-radius:50%;
    background: radial-gradient(circle, #FFD700 0%, transparent 70%);
    filter: blur(100px); opacity: 0.04;
    top: 45%; right: 8%;
    animation: orbFloat 35s ease-in-out infinite reverse;
}

/* ── Hero wrapper ─────────────────────────────────────── */
@keyframes fadeUp {
    from { opacity:0; transform:translateY(22px); }
    to   { opacity:1; transform:translateY(0); }
}
@keyframes shimmer {
    0%   { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}
@keyframes pulseCta {
    0%,100% { box-shadow: 0 0 18px rgba(0,240,255,0.25), 0 6px 24px rgba(0,0,0,0.5); }
    50%     { box-shadow: 0 0 36px rgba(0,240,255,0.55), 0 6px 32px rgba(0,0,0,0.5); }
}

.login-hero {
    text-align: center;
    padding: 56px 32px 36px;
    animation: fadeUp 0.7s cubic-bezier(0.22,1,0.36,1) both;
}
.login-logo-badge {
    display: inline-flex; align-items: center; gap: 10px;
    background: rgba(0,240,255,0.07);
    border: 1px solid rgba(0,240,255,0.22);
    border-radius: 50px; padding: 7px 18px;
    font-size: 0.8rem; font-weight: 600;
    color: #00f0ff; letter-spacing: 0.08em;
    margin-bottom: 24px;
    text-transform: uppercase;
}
.login-h1 {
    font-size: clamp(2.0rem, 4.5vw, 3.2rem);
    font-weight: 800;
    line-height: 1.18;
    background: linear-gradient(135deg, #ffffff 0%, #00f0ff 50%, #c800ff 100%);
    background-size: 200% 200%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: shimmer 6s ease infinite;
    margin-bottom: 14px;
}
.login-sub {
    font-size: 1.1rem;
    color: rgba(255,255,255,0.55);
    max-width: 480px;
    margin: 0 auto 36px;
    line-height: 1.6;
}

/* ── Proof strip ──────────────────────────────────────── */
.login-proof {
    display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;
    margin-bottom: 40px;
}
.login-proof-item {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px; padding: 6px 14px;
    font-size: 0.78rem; color: rgba(255,255,255,0.6);
    white-space: nowrap;
}
.login-proof-item strong { color: #00f0ff; }

/* ── Auth card ─────────────────────────────────────────── */
.login-card {
    background: linear-gradient(135deg, rgba(15,23,42,0.75) 0%, rgba(7,10,19,0.90) 100%);
    backdrop-filter: blur(24px) saturate(1.3);
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 20px;
    padding: 36px 36px 28px;
    margin-bottom: 16px;
    animation: fadeUp 0.7s cubic-bezier(0.22,1,0.36,1) 0.1s both;
}
.login-card-title {
    font-size: 1.05rem; font-weight: 700;
    color: #fff; margin-bottom: 4px;
}
.login-card-subtitle {
    font-size: 0.83rem; color: rgba(255,255,255,0.45);
    margin-bottom: 20px;
}
.login-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0,240,255,0.18) 30%,
        rgba(200,0,255,0.14) 70%, transparent);
    border: none; margin: 32px 0 28px;
}
</style>
""", unsafe_allow_html=True)

# ── Ambient orbs ──────────────────────────────────────────────
st.markdown("""
<div class="login-orbs">
  <div class="login-orb-1"></div>
  <div class="login-orb-2"></div>
  <div class="login-orb-3"></div>
</div>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────
st.markdown("""
<div class="login-hero">
  <div class="login-logo-badge">🏀 Smart Pick Pro · NBA Props</div>
  <div class="login-h1">The Sharper Way<br>to Pick NBA Props</div>
  <div class="login-sub">
    AI-powered edge detection, live line movement tracking,
    and SAFE Score™ analysis — built for serious players.
  </div>
  <div class="login-proof">
    <span class="login-proof-item">⚡ <strong>62.4%</strong> Hit Rate</span>
    <span class="login-proof-item">📈 <strong>+18.3%</strong> Avg ROI</span>
    <span class="login-proof-item">🛡️ SAFE Score™ System</span>
    <span class="login-proof-item">🏀 NBA Specialists</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Auth forms ────────────────────────────────────────────────
_tab_new, _tab_returning = st.tabs(["✨ Get Access", "🔑 Sign In"])

# ── NEW USER: Subscribe via Stripe ────────────────────────────
with _tab_new:
    st.markdown("""
    <div class="login-card">
      <div class="login-card-title">Start Your Premium Access</div>
      <div class="login-card-subtitle">
        Enter your email and we'll take you straight to checkout.
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("subscribe_form", clear_on_submit=False):
        _new_email = st.text_input(
            "Email address",
            placeholder="you@example.com",
            label_visibility="collapsed",
        )
        _submitted_new = st.form_submit_button(
            "⚡ Subscribe Now →",
            use_container_width=True,
            type="primary",
        )

    if _submitted_new:
        if _stripe_on:
            with st.spinner("Creating your checkout session…"):
                _result = create_checkout_session(
                    customer_email=_new_email.strip() if _new_email else ""
                )
            _checkout_url = _result.get("checkout_url", "")
            if _checkout_url:
                st.markdown(
                    f'<meta http-equiv="refresh" content="0; url={_checkout_url}">',
                    unsafe_allow_html=True,
                )
                st.info("Redirecting to Stripe checkout…")
            else:
                st.error(
                    _result.get("error", "Could not create checkout session. "
                                "Please try again or contact support.")
                )
        else:
            # Dev / free mode — grant access immediately
            st.switch_page("Smart_Picks_Pro_Home.py")

# ── RETURNING USER: Restore session by email ─────────────────
with _tab_returning:
    st.markdown("""
    <div class="login-card">
      <div class="login-card-title">Already a Member?</div>
      <div class="login-card-subtitle">
        Enter the email you subscribed with to restore your access.
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("signin_form", clear_on_submit=False):
        _signin_email = st.text_input(
            "Subscriber email",
            placeholder="you@example.com",
            label_visibility="collapsed",
        )
        _submitted_signin = st.form_submit_button(
            "🔑 Sign In →",
            use_container_width=True,
            type="primary",
        )

    if _submitted_signin:
        if not _signin_email or not _signin_email.strip():
            st.warning("Please enter your email address.")
        else:
            with st.spinner("Looking up your subscription…"):
                _found = restore_subscription_by_email(_signin_email.strip())
            if _found:
                st.success("✅ Access restored! Taking you in…")
                st.switch_page("Smart_Picks_Pro_Home.py")
            else:
                st.error(
                    "No active subscription found for that email. "
                    "If you just subscribed, it may take a moment — "
                    "or use the **Get Access** tab to subscribe."
                )
