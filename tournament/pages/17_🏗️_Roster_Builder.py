"""Tournament roster builder page.

This page delegates to the active standalone roster builder implementation in
the root pages directory so both entry points stay in sync.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st


def _load_shared_page() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    candidates = sorted(repo_root.glob("pages/31_*Tournament_Roster_Builder.py"))
    if not candidates:
        raise FileNotFoundError("Shared roster builder page not found.")
    return candidates[0]


try:
    shared_page = _load_shared_page()
    exec(shared_page.read_text(encoding="utf-8"), {})
except Exception as exc:
    st.error(f"Unable to load roster builder: {exc}")
