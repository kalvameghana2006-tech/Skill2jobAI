from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from ui import state
from ui.components import PRIORITY_COLOR, chip, esc, goto, section, show, tile, plot
from ui.theme import GRAPE, INK, MINT, PINK, TANG, style_fig


def _use(skills: list[str]) -> None:
    st.session_state["roadmap_skills"] = skills
    st.session_state["nav"] = "🗺️ Roadmap"


def render() -> None:
    e = state.eng()
    p = state.require_profile()
    section("Career ROI", "Which missing skill is worth learning first? I re-run the real matcher with each skill added – a counterfactual, not an opinion.", "📈")
    k = st.slider("How many skills should the plan include?", 2, 8, 4, key="roi_k")
    sig = (e._sig(p), k)
    cache = st.session_state.get("roi_cache")
    if not cache or cache[0] != sig:
        with st.spinner("🧮 Simulating each skill against your target jobs…"):
            plan = e.roi(p, k=k)
        st.session_state["roi_cache"] = (sig, plan)
    else:
        plan = cache[1]
    rk = plan["ranking"]
    if not rk:
        show('<div class="card mint"><h3>Nothing left to learn for your target roles 🎉</h3><p>Verify your skills and start applying.</p></div>')
        return
    tr = plan["trajectory"]
    cols = st.columns(4)
    for col, (n, l) in zip(cols, [(rk[0]["name"], "learn first"), (f"{rk[0]['effort_days']:g} d", "for the top skill"), (tr[0]["suitable"], "roles you qualify for today"),
                                  (tr[-1]["suitable"], f"after the top-{len(tr) - 1} plan")]):
        col.markdown(tile(n, l), unsafe_allow_html=True)
    left, right = st.columns([1.3, 1])
    with left:
        top = rk[:10]
        fig = go.Figure(go.Bar(y=[x["name"] for x in top][::-1], x=[x["roi"] for x in top][::-1], orientation="h",
                               marker=dict(color=[{"Very High": PINK, "High": TANG, "Medium": "#FFE24A", "Low": GRAPE}[x["priority"]] for x in top][::-1], line=dict(color=INK, width=2.5)),
                               customdata=[[x["jobs_unlocked"], x["effort_days"], x["demand_required"], x["demand_preferred"]] for x in top][::-1],
                               hovertemplate="<b>%{y}</b><br>ROI %{x:.2f}<br>jobs unlocked %{customdata[0]}<br>effort %{customdata[1]} days<br>required in %{customdata[2]} · preferred in %{customdata[3]}<extra></extra>"))
        fig.update_layout(title="ROI = opportunity gained ÷ learning effort", xaxis_title="ROI score")
        plot(style_fig(fig, 420))
    with right:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=[t["after"] for t in tr], y=[t["suitable"] for t in tr], mode="lines+markers", name="roles you qualify for", line=dict(color=TANG, width=4), marker=dict(size=13, line=dict(color=INK, width=2.5))))
        fig2.add_trace(go.Scatter(x=[t["after"] for t in tr], y=[t["avg_top5"] for t in tr], mode="lines+markers", name="avg top-5 score", yaxis="y2", line=dict(color=GRAPE, width=3, dash="dot"), marker=dict(size=10, line=dict(color=INK, width=2))))
        fig2.update_layout(title="If you learn them in this order…", yaxis=dict(title="roles"), yaxis2=dict(overlaying="y", side="right", title="score", range=[0, 100], tickvals=[0, 25, 50, 75, 100], showgrid=False), legend=dict(orientation="h", y=-0.25))
        plot(style_fig(fig2, 420))
    section("The reasoning", "", "💡")
    for i, x in enumerate(rk[:6], 1):
        unl = ", ".join(esc(e.job(j)["title"]) for j in x["unlocked_ids"][:3]) or "none directly – it lifts scores"
        pre = ", ".join(e.tax.name(q) for q in x["effort"]["missing_prereqs"])
        show(f'<div class="card tight hover"><div class="row top"><div style="font-family:var(--display);font-size:2.6rem;line-height:1;width:44px">{i}</div><div class="grow">'
             f'<b style="font-size:1.35rem">{esc(x["name"])}</b> {chip(x["priority"] + " priority", PRIORITY_COLOR[x["priority"]])}{chip("%d jobs unlocked" % x["jobs_unlocked"], "mint")}{chip("~%g days" % x["effort_days"], "sky")}{chip("ROI %.2f" % x["roi"], "grape")}'
             f'<p>{esc(x.get("explanation", ""))}</p><p class="muted">Unlocks: {unl}.{" Prerequisites added: " + esc(pre) + "." if pre else ""}</p></div></div></div>')
    plan_skills = [x["skill_id"] for x in plan["plan"]]
    st.button(f"Build a roadmap for the top {len(plan_skills)} →", type="primary", on_click=_use, args=(plan_skills,), key="roi_go")
