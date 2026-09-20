from __future__ import annotations

import streamlit as st

from core.gap import gap_summary
from ui import state
from ui.components import chip, empty_state, esc, goto, pips, section, show, status_chip, tile


def _add(sid: str) -> None:
    cur = st.session_state.setdefault("roadmap_skills", [])
    if sid not in cur:
        cur.append(sid)
    st.toast("Added to your roadmap selection")


def render() -> None:
    e = state.eng()
    p = state.require_profile()
    res = state.results(p)
    by_id = {r["job_id"]: r for r in res}
    ids = [r["job_id"] for r in res]
    cur = st.session_state.get("selected_job") or e.target_job(p, res)["job_id"]
    section("Skill gaps", "Not a keyword list – each gap says how far you are, why it matters, and how to close it.", "🧩")
    sel = st.selectbox("Analyze gaps for", ids, index=ids.index(cur) if cur in ids else 0, format_func=lambda i: f"{by_id[i]['title']} — {by_id[i]['company']} ({by_id[i]['score']:.0f}%)", key="gap_pick")
    st.session_state["selected_job"] = sel
    gaps = e.gaps(p, sel)
    r = by_id[sel]
    matched = [q for q in r["requirements"] if q["status"] == "matched"]
    gs = gap_summary(gaps)
    cols = st.columns(4)
    for col, (n, l) in zip(cols, [(len(matched), "🟢 matched"), (gs["partial"], "🟡 partial"), (gs["missing"], "🔴 missing"), (gs["insufficient"], "⚠️ insufficient evidence")]):
        col.markdown(tile(n, l), unsafe_allow_html=True)
    if not gaps:
        show('<div class="card mint pop"><h3>No gaps for this role 🎉</h3><p>You meet every parsed requirement with evidence. Go apply – or verify your skills to make the evidence bulletproof.</p></div>')
        return
    st.write("")
    show('<div class="sub"><i>“Not mentioned” never means “doesn’t know”: skills you listed without proof are flagged <b>insufficient evidence</b>, not missing.</i></div>')
    for g in gaps:
        eff = g["effort"]
        path = "".join(f'<span class="step">{esc(t)}</span><span class="arr">→</span>' for t in g["recommended_path"][:5])
        pre = (f'<p><b>Prerequisites you lack:</b> {"".join(chip(x, "pink") for x in g["prerequisites_missing"])} <span class="muted">(added to the plan first)</span></p>' if g["prerequisites_missing"] else "")
        tr = f'<p class="muted">Transferable from your <b>{esc(g["transfer_from"])}</b> – that shortens the learning time.</p>' if g["transfer_from"] else ""
        cls = {"missing": "pink", "partial": "lemon", "insufficient": "grape"}[g["status"]]
        show(f'<div class="card {cls} hover"><div class="row top"><div class="grow"><h3>{esc(g["name"])} &nbsp;{status_chip(g["status"])}{chip(g["importance"], "ink" if g["importance"] == "required" else "sky")}</h3>'
             f'<p><b>Required level:</b> {esc(g["required_level_name"])} {pips(g["required_level"])} &nbsp; <b>You:</b> {esc(g["current_level_name"])} {pips(g["current_level"], cls="mint")}</p>'
             f'<p><b>Current evidence:</b> <span class="muted">{esc(g["current_evidence"] or "none")}</span>{" — " + esc(g["note"]) if g["note"] and g["status"] != "missing" else ""}</p>'
             f'<p><b>Why it matters:</b> appears in <b>{g["jobs_relevant"]}/{g["jobs_total"]}</b> curated jobs ({g["jobs_required"]} as required).</p>{tr}{pre}'
             f'<p><b>Estimated effort:</b> {eff["total_days"]:g} study days <span class="muted">({eff["skill_days"]:g} for the skill + {eff["prereq_days"]:g} for prerequisites)</span></p>'
             f'<div class="flow"><b>Path:</b> {path}<span class="step">🛠️ {esc(g["project"][:70])}…</span></div></div></div></div>')
        st.button(f"➕ Add {g['name']} to my roadmap", key=f"gapadd_{g['skill_id']}", on_click=_add, args=(g["skill_id"],))
    c1, c2 = st.columns(2)
    c1.button("Rank these by ROI →", on_click=goto, args=("📈 ROI Analysis",), key="gap_roi", type="primary")
    c2.button("Build the roadmap →", on_click=goto, args=("🗺️ Roadmap",), key="gap_rm")
