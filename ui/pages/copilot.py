from __future__ import annotations

import streamlit as st

from core.agent import CareerAgent
from ui import state
from ui.components import esc, section, show

SUGGEST = ["Which jobs fit me best?", "What should I learn first and where do I learn it?", "Why is my top match a good fit?", "What am I missing for backend roles?",
           "What is a Dockerfile?", "Build me a study roadmap", "What should I do today?", "Which new jobs did I unlock?"]


def _ask(q: str) -> None:
    st.session_state["chat_pending"] = q


def render() -> None:
    e = state.eng()
    section("Career Copilot", "Ask anything – it calls real tools (match, gap, ROI, RAG, roadmap) and shows every call.", "🤖")
    hist = st.session_state.setdefault("chat", [])
    if not hist:
        show('<div class="sticky sky" style="max-width:560px">Try: “I want backend jobs – what should I learn first and where?” — that chains match → gap → ROI → resources.</div>')
    cols = st.columns(4)
    for i, s in enumerate(SUGGEST):
        cols[i % 4].button(s, key=f"sg_{i}", on_click=_ask, args=(s,))
    for m in hist:
        with st.chat_message(m["role"], avatar="🧑‍🎓" if m["role"] == "user" else "✏️"):
            st.markdown(m["content"])
            if m.get("trace"):
                with st.expander(f"🔧 Tool calls ({len(m['trace'])}) · {m.get('mode', '')}"):
                    for t in m["trace"]:
                        show(f'<div class="req st-partial"><span class="nm">{esc(t["tool"])}</span><span class="mono grow">{esc(str(t["args"])[:120])}</span></div><div class="mono muted" style="margin:0 0 .4rem 1rem">→ {esc(t["result"][:220])}</div>')
    q = st.chat_input("Ask about jobs, gaps, skills, resources, concepts…") or st.session_state.pop("chat_pending", None)
    if q:
        hist.append({"role": "user", "content": q})
        with st.chat_message("user", avatar="🧑‍🎓"):
            st.markdown(q)
        with st.chat_message("assistant", avatar="✏️"):
            with st.spinner("Thinking with tools…"):
                out = CareerAgent(e, state.UID).ask(q, hist[:-1])
            st.markdown(out["answer"])
            with st.expander(f"🔧 Tool calls ({len(out['trace'])}) · {out['mode']}"):
                for t in out["trace"]:
                    show(f'<div class="req st-partial"><span class="nm">{esc(t["tool"])}</span><span class="mono grow">{esc(str(t["args"])[:120])}</span></div><div class="mono muted" style="margin:0 0 .4rem 1rem">→ {esc(t["result"][:220])}</div>')
        hist.append({"role": "assistant", "content": out["answer"], "trace": out["trace"], "mode": out["mode"]})
