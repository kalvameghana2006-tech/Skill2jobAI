"""Skill2Job AI – Streamlit entry point.   Run:  streamlit run app.py"""
from __future__ import annotations

import traceback

import streamlit as st

st.set_page_config(page_title="Skill2Job AI", page_icon="✏️", layout="wide", initial_sidebar_state="expanded")

from ui.theme import inject_css  # noqa: E402
from ui.components import H, esc, show  # noqa: E402
from ui import state  # noqa: E402
from ui.pages import (home, intake, skills, matches, job_detail, gaps, roi, roadmap, today, resources, progress, copilot,  # noqa: E402
                      notifications, trust)

PAGES = {
    "🏠 Home": home, "🧑‍🎓 Profile Intake": intake, "🧠 Skill Profile": skills, "🎯 Job Matches": matches, "🔍 Job Details": job_detail,
    "🧩 Skill Gaps": gaps, "📈 ROI Analysis": roi, "🗺️ Roadmap": roadmap, "📅 Daily Task": today, "📚 Resources": resources,
    "📊 Progress": progress, "🤖 Career Copilot": copilot, "🔔 Notifications": notifications, "🧪 Trust & Accuracy": trust,
}

inject_css()
if "_goto" in st.session_state:
    st.session_state["nav"] = st.session_state.pop("_goto")
if "nav" not in st.session_state:
    st.session_state["nav"] = "🏠 Home"

# ------------------------------------------------------------------ engine (cached) with friendly loading state
try:
    with st.spinner("✏️ Sharpening pencils… loading skills, jobs and the knowledge base"):
        engine = state.get_engine()
except Exception as exc:  # never show a raw stack trace on start-up
    st.error("Skill2Job couldn't start. Check that you ran `python scripts/build_data.py` and installed requirements.txt.")
    st.code("".join(traceback.format_exception_only(type(exc), exc)))
    st.stop()

# The Gemini key lives in the server environment (.env or Streamlit secrets) – users are never asked for it.
if not engine.llm.available:
    try:
        _k = st.secrets.get("GEMINI_API_KEY", "")
        if _k:
            engine.llm.set_key(_k)
    except Exception:
        pass

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    show('<span class="brand">Skill2Job ✎ AI<small>YOUR EVIDENCE-BACKED CAREER AGENT</small></span>')
    st.radio("Navigate", list(PAGES), key="nav", label_visibility="collapsed")
    st.markdown("---")
    llm = engine.llm
    if st.button("↺ Start over (clear my data)", key="reset_all"):
        engine.reset(state.UID)
        for k in ("last_run", "quiz", "quiz_day", "quiz_result", "roi_cache", "selected_job", "roadmap_skills", "chat"):
            st.session_state.pop(k, None)
        st.session_state["_goto"] = "🏠 Home"
        st.rerun()

# ------------------------------------------------------------------ top bar (notification bell) + page
unread = engine.db.unread_count(state.UID)
badge = f"<b>{unread}</b>" if unread else ""
show(f'<div class="topbar"><span class="chip ink">{"Gemini + tools" if llm.available else "offline smart mode"}</span>'
     f'<span class="bell" title="Notifications">🔔{badge}</span></div>')
try:
    engine.notify_tick(state.UID)
except Exception:
    pass
try:
    PAGES[st.session_state["nav"]].render()
except Exception as exc:
    show('<div class="card pink"><h3>Oops – the pencil snapped ✏️</h3><p>That page hit an unexpected problem. Your data is safe. '
         'Try again, or open another page.</p></div>')
    with st.expander("Technical details"):
        st.code(traceback.format_exc())
