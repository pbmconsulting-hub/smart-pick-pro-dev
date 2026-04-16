"""Terms of Service page for tournament subsystem."""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Terms of Service - Smart Pick Pro", page_icon="📄", layout="wide")

st.title("📄 Terms of Service")
st.markdown(
    """
By using Smart Pick Pro tournaments, you agree to:

1. Participate only where legal in your jurisdiction.
2. Provide accurate account, payment, and tax information.
3. Follow one-account-per-user and fair-play requirements.
4. Accept tournament lock times, scoring, payout, and dispute policies.
5. Acknowledge that paid contests may require Stripe Connect onboarding and KYC.

## Contest Rules
- Contest outcomes are simulation-driven and seed-verifiable.
- Entries lock at posted lock time.
- Results and payouts follow published tournament rules.

## Eligibility
- Must be 18+ (21+ in MA, AZ, IA).
- Not available in WA, ID, MT, HI, NV.

## Responsible Play
If you or someone you know has a gambling problem, call **1-800-GAMBLER**.
"""
)

