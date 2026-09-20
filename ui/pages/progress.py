from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from ui import state
from ui.components import bar, chip, empty_state, esc, goto, ring, section, show, tile, plot
from ui.theme import GRAPE, INK, MINT, TANG, style_fig


def render() -> None:
    e = state.eng()
    p = state.require_profile()
    uid = state.UID
    res = state.results(p)
    target = e.target_job(p, res)
    rm = e.roadmap(uid)
    snaps = e.db.list_snapshots(uid)
    section("Progress dashboard", "Are you actually getting hireable? Readiness, plan progress and verified skills in one place.", "📊")
    done = sum(d["status"] in ("done", "retry") for d in rm)
    c1, c2 = st.columns([1, 2])
    with c1:
        show(f'<div class="card tang" style="text-align:center"><span class="mono muted">JOB READINESS</span><br><div style="display:flex;justify-content:center;margin:.4rem 0">{ring(target["score"], "xl")}</div>'
             f'<b>{esc(target["title"])}</b><br><span class="muted">{esc(target["company"])} · {esc(target["tier"])}</span></div>')
    with c2:
        prog = e.skill_progress(uid)
        cols = st.columns(4)
        for col, (n, l) in zip(cols, [(f"{done}/{len(rm)}" if rm else "–", "roadmap days"), (e.streak(uid), "day streak 🔥"),
                                      (sum(1 for s in p["skills"].values() if s.get("verified")), "verified skills"), (sum(1 for r in res if r["suitable"]), "roles unlocked")]):
            col.markdown(tile(n, l), unsafe_allow_html=True)
        st.write("")
        if rm:
            show(f'<div class="row"><b style="width:110px">Roadmap</b><div class="grow">{bar(100 * done / len(rm))}</div><span class="mono">{done}/{len(rm)}</span></div>')
        for sp in prog:
            cls = "mint" if sp["verified"] >= 2 else "grape" if sp["verified"] == 1 else ""
            tag = " 🏅" if sp["verified"] >= 2 else " ✅" if sp["verified"] == 1 else ""
            show(f'<div class="row" style="margin:.25rem 0"><b style="width:110px">{esc(sp["name"])}{tag}</b><div class="grow">{bar(sp["pct"], cls)}</div><span class="mono">{sp["pct"]}%</span></div>')
        if not rm:
            show('<div class="card tight">No roadmap yet – create one to track skill progress here.</div>')

    section("How your matches changed", "Every verified skill triggers a fresh matching run.", "📈")
    if len(snaps) >= 1:
        fig = go.Figure()
        labels = [f'{i}. {s["label"]}' for i, s in enumerate(snaps)]
        fig.add_trace(go.Scatter(x=labels, y=[s["suitable_count"] for s in snaps], mode="lines+markers", name="roles you qualify for", line=dict(color=TANG, width=4), marker=dict(size=14, line=dict(color=INK, width=2.5))))
        fig.add_trace(go.Scatter(x=labels, y=[s["avg_top5"] for s in snaps], mode="lines+markers", name="avg score of top 5", yaxis="y2", line=dict(color=GRAPE, width=3, dash="dot"), marker=dict(size=10, line=dict(color=INK, width=2))))
        fig.update_layout(yaxis=dict(title="suitable roles", rangemode="tozero"), yaxis2=dict(overlaying="y", side="right", range=[0, 100], title="score", tickvals=[0, 25, 50, 75, 100], showgrid=False), legend=dict(orientation="h", y=-0.3))
        plot(style_fig(fig, 340))
    if len(snaps) >= 2:
        first, last = snaps[0], snaps[-1]
        new_ids = [j for j in last["detail"].get("suitable_ids", []) if j not in first["detail"].get("suitable_ids", [])]
        if new_ids:
            show(f'<div class="card mint pop"><h3>🎉 Your updated skills unlocked {len(new_ids)} additional role(s)</h3><p class="muted">They now meet the criteria used by our matching system – this is not a guarantee of employment.</p>'
                 + "".join(chip(e.job(j)["title"], "mint") for j in new_ids if e.job(j)) + "</div>")
    elif snaps:
        show('<div class="card tight">Complete quizzes and practical tasks – each verified skill re-runs matching and this chart grows.</div>')

    section("Verification ledger", "", "🏅")
    ver = e.db.list_verifications(uid)
    if not ver:
        empty_state("🧪", "Nothing verified yet", "Pass an assessment quiz and submit a practical task on the Daily Task page.")
    else:
        for v in reversed(ver[-10:]):
            show(f'<div class="req {"st-matched" if v["passed"] else "st-missing"}"><span class="nm">{esc(e.tax.name(v["skill_id"]))}</span>{chip(v["level"], "ink")}'
                 f'<span class="grow">{v["score"]:.0f}/100 — {"passed" if v["passed"] else "not yet"}</span><span class="mono muted">{esc(v["created_at"][:16])}</span></div>')
    st.button("Open today's task →", on_click=goto, args=("📅 Daily Task",), key="pg_today", type="primary")
