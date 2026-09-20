from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from core.models import EVIDENCE_LABEL, LEVEL_NAMES
from core.profile import add_evidence, finalize
from ui import state
from ui.components import chip, esc, evidence_chip, pips, section, show, bar, tile, plot
from ui.theme import INK, TANG, style_fig


def render() -> None:
    e = state.eng()
    p = state.require_profile()
    tax = e.tax
    have = {s: v for s, v in p["skills"].items() if not v.get("negated")}
    gaps = [s for s, v in p["skills"].items() if v.get("negated")]
    section("Your skill profile", "Skill + proficiency + evidence – not just keywords.", "🧠")
    cols = st.columns(4)
    direct = [v for v in have.values() if not v.get("inferred")]
    for col, (n, l) in zip(cols, [(len(direct), "skills with evidence"), (sum(1 for v in have.values() if v.get("verified")), "verified skills"),
                                  (len(gaps), "declared gaps"), (f"{sum(v['confidence'] for v in direct) / max(1, len(direct)):.0%}", "avg. confidence")]):
        col.markdown(tile(n, l), unsafe_allow_html=True)
    ident = " · ".join(x for x in [p.get("degree"), p.get("branch"), f"Year {p['year']}" if p.get("year") else "", p.get("location")] if x)
    if ident or p.get("interests"):
        show(f'<div class="card tight" style="margin-top:1rem"><b>About you:</b> {esc(ident or "details not detected")} '
             + "".join(chip(i, "sky") for i in p.get("interests", [])) + "</div>")

    left, right = st.columns([1.6, 1])
    cats = tax.by_category()
    with right:
        rows = []
        for cat, ids in cats.items():
            lv = [have[i]["level"] for i in ids if i in have]
            if lv:
                rows.append((cat, max(lv)))
        if len(rows) >= 3:
            fig = go.Figure(go.Scatterpolar(r=[r for _, r in rows] + [rows[0][1]], theta=[c for c, _ in rows] + [rows[0][0]], fill="toself",
                                            line=dict(color=INK, width=3), fillcolor="rgba(255,106,43,.45)"))
            fig.update_layout(polar=dict(radialaxis=dict(range=[0, 4], tickvals=[1, 2, 3, 4], gridcolor="rgba(43,26,74,.2)"), bgcolor="rgba(255,253,246,.9)"), showlegend=False)
            show('<div class="card tight"><b>Strength map</b> (highest level per area)</div>')
            plot(style_fig(fig, 360))
        if gaps:
            show('<div class="card pink tight"><b>You said you haven’t used yet</b><br>' + "".join(chip(tax.name(g), "pink") for g in gaps) + "</div>")
    with left:
        for cat, ids in cats.items():
            mine = [i for i in ids if i in have]
            if not mine:
                continue
            show(f'<div style="font-family:var(--marker);font-size:.95rem;letter-spacing:1px;margin:.9rem 0 .2rem">{esc(cat.upper())}</div>')
            for sid in sorted(mine, key=lambda i: -have[i]["level"]):
                v = have[sid]
                ev_types = list(dict.fromkeys(x["type"] for x in v["evidence"]))
                quote = max(v["evidence"], key=lambda x: len(x["text"]))["text"] if v["evidence"] else ""
                badge = (chip("🏅 verified", "mint") if v.get("verified", 0) >= 2 else chip("✅ quiz-verified", "mint") if v.get("verified") == 1 else "") + (chip("inferred", "grape") if v.get("inferred") else "")
                show(f'<div class="card tight hover"><div class="row"><div class="grow"><b style="font-size:1.35rem">{esc(tax.name(sid))}</b> &nbsp;{pips(v["level"])} '
                     f'<span class="muted">{LEVEL_NAMES[v["level"]]}</span> {badge}<br>{"".join(evidence_chip(t) for t in ev_types)}'
                     f'<div class="muted" style="font-size:.95rem;margin-top:.15rem">“{esc(quote[:150])}”</div></div>'
                     f'<div style="width:110px"><div class="mono">confidence {v["confidence"]:.0%}</div>{bar(v["confidence"] * 100, "thin mint")}</div></div></div>')

    section("Correct or add a skill", "The agent can be wrong – you have the final word.", "✏️")
    names = sorted(s["name"] for s in tax.skills.values())
    with st.expander("Add / correct a skill"):
        c1, c2, c3 = st.columns(3)
        nm = c1.selectbox("Skill", names, key="edit_skill")
        lvl = c2.slider("Level", 1, 4, 2, key="edit_level", help="1 Beginner · 2 Intermediate · 3 Advanced · 4 Expert")
        et = c3.selectbox("Evidence", [k for k in EVIDENCE_LABEL if not k.startswith("verified") and k != "inferred"], format_func=lambda k: EVIDENCE_LABEL[k], key="edit_ev")
        note = st.text_input("What shows this? (one line)", key="edit_note", placeholder="e.g. Built an inventory API with Flask")
        if st.button("Save skill", key="edit_save"):
            sid = tax.id_from_name(nm)
            p["skills"].pop(sid, None)
            add_evidence(p, sid, note or "Added manually", et, stated=lvl, source="manual")
            finalize(p, tax)
            e.save_profile(p)
            st.toast(f"{nm} saved")
            st.rerun()
        rm = st.multiselect("Remove skills", [tax.name(s) for s in p["skills"] if not p["skills"][s].get("inferred")], key="edit_rm")
        if rm and st.button("Remove selected", key="edit_rm_btn"):
            for r in rm:
                p["skills"].pop(tax.id_from_name(r), None)
            finalize(p, tax)
            e.save_profile(p)
            st.rerun()
