from __future__ import annotations

import re

import plotly.graph_objects as go
import streamlit as st

from core.models import EVIDENCE_LABEL, LEVEL_NAMES
from ui import state
from ui.components import TIER_COLOR, chip, empty_state, esc, evidence_chip, goto, pips, ring, section, show, status_chip, plot
from ui.theme import INK, TANG, style_fig

COMP_LABEL = {"required": "Core skills", "preferred": "Preferred", "semantic": "Semantic fit", "proficiency": "Level fit", "evidence": "Evidence", "experience": "Experience", "education": "Education"}


def _set_target(job_id: str) -> None:
    e = state.eng()
    p = e.get_profile(state.UID)
    p["target_job_id"] = job_id
    e.save_profile(p)
    st.session_state["roi_cache"] = None
    st.toast("Target role set – readiness on the dashboard now tracks it")


def render() -> None:
    e = state.eng()
    p = state.require_profile()
    res = state.results(p)
    by_id = {r["job_id"]: r for r in res}
    ids = [r["job_id"] for r in res]
    cur = st.session_state.get("selected_job") or e.target_job(p, res)["job_id"]
    section("Why this job?", "Every point of the score is traceable to evidence in your profile.", "🔍")
    sel = st.selectbox("Job", ids, index=ids.index(cur) if cur in ids else 0, format_func=lambda i: f"{by_id[i]['title']} — {by_id[i]['company']} ({by_id[i]['score']:.0f}%)", key="jd_pick")
    st.session_state["selected_job"] = sel
    r = by_id[sel]
    ex = e.explain(r)
    c = r["counts"]
    show(f'<div class="card {"mint" if r["suitable"] else "tang"} tape"><div class="row">{ring(r["score"], "xl")}<div class="grow">'
         f'<h3>{esc(r["title"])}</h3><p class="muted">{esc(r["company"])} · {esc(r["city"])} · {esc(r["mode"])} · {esc(r["domain"])}</p>'
         f'{chip(r["tier"], TIER_COLOR[r["tier"]])}{chip("core skills %d/%d" % (c["required_met"], c["required_total"]), "mint")}{chip("preferred %d/%d" % (c["preferred_met"], c["preferred_total"]), "sky")}'
         f'{chip("evidence: " + r["evidence_confidence"], "grape")}'
         f'<p style="font-size:1.25rem;margin-top:.5rem"><b>{esc(ex["headline"])}</b> {esc(ex["verdict"])}</p></div></div></div>')
    if ex.get("narrative"):
        show(f'<div class="sticky mint" style="font-size:1.25rem;font-family:var(--hand)">✨ Gemini: {esc(ex["narrative"])}</div>')

    left, right = st.columns([1.5, 1])
    with right:
        comps = r["components"]
        theta = [COMP_LABEL[k] for k in comps]
        fig = go.Figure(go.Scatterpolar(r=[comps[k] * 100 for k in comps] + [comps["required"] * 100], theta=theta + [theta[0]], fill="toself", line=dict(color=INK, width=3), fillcolor="rgba(122,77,255,.4)"))
        fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100], gridcolor="rgba(43,26,74,.2)"), bgcolor="rgba(255,253,246,.9)"), showlegend=False)
        show('<div class="card tight"><b>Score anatomy</b> – six signals, weighted</div>')
        plot(style_fig(fig, 340))
        w = e.matcher.weights
        show('<div class="card tight mono">' + "<br>".join(f'{COMP_LABEL[k]:<13} {comps[k] * 100:5.0f}%  × weight {w[k]:.2f}' for k in comps) + "</div>")
    with left:
        for imp, title in (("required", "Core requirements"), ("preferred", "Nice to have")):
            rows = [q for q in r["requirements"] if q["importance"] == imp]
            if not rows:
                continue
            show(f'<div style="font-family:var(--marker);letter-spacing:1px;margin:.6rem 0 .1rem">{title.upper()}</div>')
            for q in rows:
                ev = (evidence_chip(q["evidence_type"]) + f'<span class="muted" style="font-size:.95rem"> “{esc(q["evidence_text"][:100])}”</span>') if q["evidence_type"] else ""
                show(f'<div class="req st-{q["status"]}"><span class="nm">{esc(q["name"])}</span><span>{status_chip(q["status"])}</span>'
                     f'<span class="mono">needs {LEVEL_NAMES[q["req_level"]]} {pips(q["req_level"])}</span><span class="mono">you {pips(q["cand_level"], cls="mint")}</span></div>'
                     f'<div style="margin:-.15rem 0 .3rem 1rem">{ev}{"<span class=muted> — " + esc(q["note"]) + "</span>" if q["note"] else ""}</div>')
    if ex["strengths"]:
        with st.expander("Evidence behind each strength", expanded=False):
            show("<br>".join(f"✓ {esc(s)}" for s in ex["strengths"]))
    job = e.job(sel)
    with st.expander("Original job description (as parsed)"):
        txt = esc(job["description"])
        for m in sorted({m.alias for m in e.tax.extract(job["description"])}, key=len, reverse=True):
            txt = re.sub(rf"(?i)(?<![\w>])({re.escape(esc(m))})(?![\w<])", r'<mark style="background:#FFE24A;border-radius:4px;padding:0 3px">\1</mark>', txt)
        show(f'<div class="card tight" style="white-space:pre-wrap;line-height:1.35">{txt}</div>'.replace("\n", "<br>"))
        st.caption(f"Parsed → required {len(job['required'])} · preferred {len(job['preferred'])} · experience {job['experience']['min']}–{job['experience']['max']} yrs · {', '.join(job['degrees'])}")
    c1, c2, c3 = st.columns(3)
    c1.button("Analyze the gaps →", on_click=goto, args=("🧩 Skill Gaps",), key="jd_gaps", type="primary")
    c2.button("★ Make this my target role", on_click=_set_target, args=(sel,), key="jd_target")
    c3.button("← All matches", on_click=goto, args=("🎯 Job Matches",), key="jd_back")
