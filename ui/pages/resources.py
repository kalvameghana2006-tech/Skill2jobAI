from __future__ import annotations

import streamlit as st

from core.models import LEVEL_NAMES
from ui import state
from ui.components import chip, empty_state, esc, section, show
from ui.pages.today import LINK_CHIP

TYPE_ICON = {"video": "🎥", "course": "🎓", "docs": "📚", "article": "📰", "practice": "💻", "project": "🛠️", "talk": "🎤"}


def render() -> None:
    e = state.eng()
    p = state.profile() or {"skills": {}}
    section("Resource library", "Curated by skill and matched to your level – with the reason each one suits you.", "📚")
    names = {sid: s["name"] for sid, s in e.tax.skills.items()}
    plan_cache = st.session_state.get("roi_cache")
    suggested = [x["skill_id"] for x in plan_cache[1]["plan"]] if plan_cache else []
    order = suggested + [s for s in names if s not in suggested]
    c1, c2, c3 = st.columns([1.4, 1, 1])
    sid = c1.selectbox("Skill", order, format_func=lambda s: ("★ " if s in suggested else "") + names[s], key="res_skill")
    kinds = ["all", "video", "course", "docs", "article", "practice", "project", "talk"]
    kind = c2.selectbox("Type", kinds, key="res_kind")
    srcs = ["all"] + sorted({r["source"] for r in e.recommender.all_for(sid)})
    src = c3.selectbox("Source", srcs, key="res_src")
    level = p["skills"].get(sid, {}).get("level", 0)
    items = e.recommender.rank(sid, level, None if kind == "all" else kind)
    items = [r for r in items if src == "all" or r["source"] == src]
    show(f'<div class="card tight">Your level in <b>{esc(names[sid])}</b>: <b>{LEVEL_NAMES.get(level, "None")}</b> – results are ordered for that level.</div>')
    if not items:
        empty_state("🔎", "No resources for that filter", "Try “all” types or sources.")
    for r in items:
        lk, col = LINK_CHIP.get(r["link_kind"], ("link", ""))
        show(f'<div class="card tight hover"><div class="row top"><div style="font-size:2rem">{TYPE_ICON.get(r["type"], "•")}</div><div class="grow">'
             f'<a href="{esc(r["url"])}" target="_blank"><b style="font-size:1.25rem">{esc(r["title"])}</b></a><br>{chip(r["source"], "ink")}{chip(r["difficulty"], "grape")}'
             f'{chip(str(r["duration_min"]) + " min", "sky")}{chip(lk, col)}<div class="muted" style="font-size:.98rem">{esc(r["why_for_you"])}</div></div></div></div>')
    st.caption("Links marked **search link** open a YouTube/Coursera/GitHub search for the named creator or topic; **course catalogue** opens the NPTEL / Skill India portal. "
               "Swap in exact URLs in data_src or data/resources.json (see README).")

    section("Ask the study notes", "Answers come only from retrieved notes – with sources you can trace.", "💬")
    q = st.text_input("Ask a concept question", key="kb_q", placeholder="e.g. What's the difference between an image and a container?")
    if q:
        with st.spinner("Searching the notes…"):
            ans = e.kb.answer(q)
        show(f'<div class="card mint"><div style="white-space:pre-wrap">{esc(ans["answer"]).replace(chr(10), "<br>")}</div></div>')
        for s in ans["sources"]:
            with st.expander(f"[{s['n']}] {s['cite']}"):
                st.text(s["text"])
    with st.expander("➕ Add your own notes to the knowledge base (PDF / MD / TXT)"):
        up = st.file_uploader("Upload notes", type=["pdf", "md", "txt"], key="kb_up", accept_multiple_files=True)
        if up and st.button("Index my notes", key="kb_idx"):
            n = 0
            for f in up:
                n += e.kb.add_user_document(f.name, f.getvalue())
            st.success(f"Indexed {n} new chunks – they now appear in answers.")
