from __future__ import annotations

from datetime import date

import streamlit as st

from core.roadmap import KIND_LABEL
from ui import state
from ui.components import chip, empty_state, esc, goto, section, show, tile, bar

KIND_COLOR = {"learn": "sky", "practice": "sky", "project": "tang", "assessment": "grape", "revision": "pink", "retake": "pink"}
KIND_ICON = {"learn": "📖", "practice": "💻", "project": "🛠️", "assessment": "🧪", "revision": "🔁", "retake": "🔄"}


def _reschedule() -> None:
    n = state.eng().reschedule(state.UID)
    st.toast(f"Shifted {n} pending days so the plan starts today")


def render() -> None:
    e = state.eng()
    p = state.require_profile()
    section("Your roadmap", "Prerequisites first, then learn → project → assessment. The plan re-shapes itself from your quiz results.", "🗺️")
    names = {sid: s["name"] for sid, s in e.tax.skills.items()}
    default = st.session_state.get("roadmap_skills")
    if not default:
        sig = e._sig(p)
        cache = st.session_state.get("roi_cache")
        plan = cache[1] if cache and cache[0][0] == sig else e.roi(p, k=4)
        default = [x["skill_id"] for x in plan["plan"][:4]]
    c1, c2, c3, c4 = st.columns([2.2, 1, 1, 1])
    chosen = c1.multiselect("Skills to learn (in priority order)", list(names), default=[d for d in default if d in names], format_func=names.get, key="rm_pick")
    hours = c2.slider("Hours / day", 0.5, 4.0, float(p.get("hours_per_day", 1.5)), 0.5, key="rm_hours")
    start = c3.date_input("Start", date.today(), key="rm_start")
    weekends = c4.toggle("Skip weekends", key="rm_wknd")
    st.session_state["roadmap_skills"] = chosen
    if st.button("🗺️ Generate roadmap" if not e.roadmap(state.UID) else "🗺️ Regenerate (replaces current plan)", type="primary", key="rm_gen", disabled=not chosen):
        with st.spinner("✏️ Drawing your day-by-day plan…"):
            e.create_roadmap(state.UID, chosen, hours, start, weekends)
        st.toast("Roadmap ready!")
        st.rerun()

    rm = e.roadmap(state.UID)
    if not rm:
        empty_state("🧭", "No roadmap yet", "Pick skills above (the ROI page suggests the best ones) and press Generate.")
        return
    done = sum(d["status"] in ("done", "retry") for d in rm)
    ins = sum(d["inserted"] for d in rm)
    cur = e.current_day(state.UID)
    cols = st.columns(4)
    for col, (n, l) in zip(cols, [(len(rm), "days planned"), (f"{done}/{len(rm)}", "days completed"), (ins, "days added by adaptation"), (date.fromisoformat(rm[-1]["planned_date"]).strftime("%d %b"), "expected finish")]):
        col.markdown(tile(n, l), unsafe_allow_html=True)
    st.write("")
    show(bar(100 * done / len(rm)))
    b1, b2, b3 = st.columns(3)
    b1.button("📅 Open today's task", on_click=goto, args=("📅 Daily Task",), key="rm_today", type="primary")
    b2.button("⏭ Reschedule from today", on_click=_reschedule, key="rm_resched", help="Missed a few days? Shift everything pending so it starts today.")
    b3.button("📈 Back to ROI", on_click=goto, args=("📈 ROI Analysis",), key="rm_roi")

    by_skill: dict[str, list[dict]] = {}
    for d in rm:
        by_skill.setdefault(d["skill_id"], []).append(d)
    seen = []
    for d in rm:
        if d["skill_id"] not in seen:
            seen.append(d["skill_id"])
    for sid in seen:
        days = by_skill[sid]
        nd = sum(x["status"] in ("done", "retry") for x in days)
        pre = days[0]["plan"].get("needed_for")
        with st.expander(f"{names[sid]} — {nd}/{len(days)} days" + (f"  ·  prerequisite for {pre}" if pre else ""), expanded=cur is not None and cur["skill_id"] == sid):
            html = '<div class="tl">'
            for d in days:
                cls = "done" if d["status"] == "done" else "retry" if d["status"] == "retry" else "now" if cur and d["id"] == cur["id"] else ""
                if d["inserted"]:
                    cls += " inserted"
                score = f' · quiz {d["quiz_score"]:.0%}' if d["quiz_score"] is not None else ""
                html += (f'<div class="day {cls}"><b>Day {d["seq"]}</b> <span class="mono muted">{d["planned_date"]}</span> '
                         f'{chip(KIND_ICON[d["kind"]] + " " + KIND_LABEL[d["kind"]], KIND_COLOR[d["kind"]])}{chip("adaptive", "pink") if d["inserted"] else ""}'
                         f'<br>{esc(d["title"])} <span class="muted">· {d["plan"].get("est_minutes", 60)} min{score}</span></div>')
            show(html + "</div>")
