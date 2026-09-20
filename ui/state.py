"""Shared Streamlit state helpers."""
from __future__ import annotations

import streamlit as st

from core.engine import Engine
from ui.components import empty_state, goto

UID = "default"


@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    return Engine()


def eng() -> Engine:
    return get_engine()


def profile() -> dict | None:
    p = eng().get_profile(UID)
    return p if p and p.get("skills") else None


def require_profile() -> dict:
    p = profile()
    if p:
        return p
    empty_state("🖊️", "No profile yet", "Tell me what you know – type it, upload a resume, or just talk. Then everything else lights up.")
    st.button("Create my profile →", type="primary", on_click=goto, args=("🧑‍🎓 Profile Intake",), key="need_profile_btn")
    st.stop()


def results(p: dict) -> list[dict]:
    return eng().matches(p)
