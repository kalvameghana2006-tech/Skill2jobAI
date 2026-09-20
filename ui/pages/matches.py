from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from core.models import ROLE_FAMILIES
from ui import state
from ui.components import TIER_COLOR, chip, empty_state, esc, goto, jump, ring, section, show, tile, plot
from ui.theme import INK, MINT, PINK, style_fig, TANG, LEMON


def _select(job_id: str) -> None:
    st.session_state["selected_job"] = job_id
    st.session_state["nav"] = "🔍 Job Details"


def render() -> None:
    e = state.eng()
    p = state.require_profile()
    res = state.results(p)
    suit = [r for r in res if r["suitable"]]
    close = [r for r in res if r["score"] >= 65]
    section("Job matches", "Semantic + evidence-weighted + explainable. Scores come from rules over your evidence – not from a chatbot's guess.", "🎯")
    cols = st.columns(4)
    for col, (n, l) in zip(cols, [(len(suit), "roles you qualify for now"), (len(close), "close matches (≥65%)"), (f"{res[0]['score']:.0f}%", "best match"), (len(res), "jobs analysed")]):
        col.markdown(tile(n, l), unsafe_allow_html=True)

    st.write("")
    f1, f2, f3, f4 = st.columns([1, 1.4, 1, 1])
    min_score = f1.slider("Min score", 0, 90, 40, 5, key="m_min")
    domains = sorted({r["domain"] for r in res})
    dom = f2.multiselect("Role family", domains, key="m_dom", placeholder="all roles")
    mode = f3.selectbox("Work mode", ["Any", "Remote", "Hybrid", "On-site"], key="m_mode")
    sort = f4.selectbox("Sort by", ["Best match", "My interests first", "Salary"], key="m_sort")
    only = st.toggle("Only roles I qualify for", key="m_only")
    view = [r for r in res if r["score"] >= min_score and (not dom or r["domain"] in dom) and (mode == "Any" or r["mode"] == mode) and (not only or r["suitable"])]
    if sort == "Salary":
        view.sort(key=lambda r: -(r["salary_lpa"] or 0))
    elif sort == "Best match":
        view.sort(key=lambda r: -r["score"])
    if not view:
        empty_state("🔭", "Nothing matches those filters", "Lower the minimum score or clear a filter – the roadmap will raise your scores later.")
    else:
        left, right = st.columns([2.1, 1])
        with right:
            top = view[:8]
            fig = go.Figure(go.Bar(x=[r["score"] for r in top][::-1], y=[r["title"][:26] for r in top][::-1], orientation="h",
                                   marker=dict(color=[MINT if r["suitable"] else LEMON if r["score"] >= 65 else PINK for r in top][::-1], line=dict(color=INK, width=2.5)),
                                   text=[f"{r['score']:.0f}%" for r in top][::-1], textposition="inside"))
            fig.update_layout(xaxis=dict(range=[0, 100]), title="Top of your list")
            plot(style_fig(fig, 380))
            show('<div class="card tight"><span class="chip mint">■ qualify now</span><span class="chip lemon">■ close</span><span class="chip pink">■ stretch</span></div>')
        with left:
            for r in view[:14]:
                c = r["counts"]
                missing = [q for q in r["requirements"] if q["status"] in ("missing",) and q["importance"] == "required"][:3]
                partial = [q for q in r["requirements"] if q["status"] in ("partial", "insufficient") and q["importance"] == "required"][:2]
                sal = f' · ₹{r["salary_lpa"]:g} LPA' if r["salary_lpa"] else ""
                show(f'<div class="card hover {"mint" if r["suitable"] else ""}"><div class="row top">{ring(r["score"], "sm")}<div class="grow">'
                     f'<b style="font-size:1.4rem">{esc(r["title"])}</b> {chip(r["tier"], TIER_COLOR[r["tier"]])}{chip("★ your interest", "sky") if r["interest_match"] else ""}<br>'
                     f'<span class="muted">{esc(r["company"])} · {esc(r["city"])} · {esc(r["mode"])}{sal}</span><br>'
                     f'{chip("core %d/%d" % (c["required_met"], c["required_total"]), "mint")}{chip("preferred %d/%d" % (c["preferred_met"], c["preferred_total"]), "sky")}{chip("evidence " + r["evidence_confidence"], "grape")}'
                     + "".join(chip("needs " + q["name"], "pink") for q in missing) + "".join(chip("level: " + q["name"], "lemon") for q in partial) + "</div></div></div>")
                st.button("Why this score? →", key=f"why_{r['job_id']}", on_click=_select, args=(r["job_id"],))
            if len(view) > 14:
                st.caption(f"Showing 14 of {len(view)} – tighten the filters to see others.")

    section("Add your own job description", "Paste any JD – the Job Parsing Agent separates required from preferred skills and levels.", "➕")
    with st.expander("Parse & add a job"):
        c1, c2, c3, c4 = st.columns(4)
        t = c1.text_input("Title", key="cj_t")
        co = c2.text_input("Company", key="cj_c")
        city = c3.text_input("City", key="cj_city")
        md = c4.selectbox("Mode", ["On-site", "Hybrid", "Remote"], key="cj_m")
        dom_pick = st.selectbox("Role family", ROLE_FAMILIES, key="cj_dom")
        desc = st.text_area("Job description", key="cj_d", height=160, placeholder="Must have: strong Java, working knowledge of Spring Boot… Nice to have: Docker…")
        use_llm = st.checkbox("Use Gemini for parsing (better on messy text)", value=e.llm.available, disabled=not e.llm.available, key="cj_llm")
        if st.button("Parse and add", key="cj_go"):
            if len(desc.split()) < 8 or not t:
                st.warning("Add a title and a few lines of description.")
            else:
                with st.spinner("Parsing requirements…"):
                    job = e.add_custom_job(t, co, city, md, desc, dom_pick, use_llm)
                names = lambda xs: ", ".join(f"{e.tax.name(x['skill'])} (L{x['level']})" for x in xs) or "–"
                st.success(f"Added **{job['title']}** (parsed by {job.get('engine')}).")
                show(f'<div class="card tight"><b>Required:</b> {esc(names(job["required"]))}<br><b>Preferred:</b> {esc(names(job["preferred"]))}<br>'
                     f'<b>Experience:</b> {job["experience"]["min"]}–{job["experience"]["max"]} yrs · <b>Degrees:</b> {esc(", ".join(job["degrees"]))}</div>')
                st.session_state.pop("roi_cache", None)
        if e.custom_jobs:
            st.caption("Your custom jobs: " + ", ".join(f"{j['title']} ({j['id']})" for j in e.custom_jobs))
