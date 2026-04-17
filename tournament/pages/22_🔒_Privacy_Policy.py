"""Privacy Policy page for tournament subsystem."""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Privacy Policy - Smart Pick Pro", page_icon="🔒", layout="wide")

st.title("🔒 Privacy Policy")
st.markdown(
    """
Smart Pick Pro collects and processes tournament data to operate contests safely and legally.

## Data We Process
- Account data: email and display name
- Contest data: entries, rosters, scores, ranks, payouts
- Compliance data: state eligibility, Stripe payout onboarding status
- Event data: notifications, tournament lifecycle logs

## Why We Process It
- Provide tournament entry, scoring, and payout services
- Enforce eligibility and anti-fraud safeguards
- Meet legal/tax obligations for paid contests

## Sharing
- Payment/payout processing is handled through Stripe and Stripe Connect.
- We do not sell personal information.

## Your Controls
- Request correction of account profile details.
- Request account closure subject to legal retention obligations.
- Contact support for privacy requests.
"""
)

