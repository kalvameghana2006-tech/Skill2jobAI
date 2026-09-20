from __future__ import annotations

import streamlit as st

from core.models import LEVEL_NAMES
from ui import state
from ui.components import chip, empty_state, esc, goto, section, show, bar, jump
from ui.pages.roadmap import KIND_COLOR, KIND_ICON
from core.roadmap import KIND_LABEL

LINK_CHIP = {"direct": ("direct link", "mint"), "search": ("search link", "lemon"), "catalog": ("course catalogue", "sky")}


def _res_card(icon: str, label: str, r: dict | None) -> None:
    if not r:
        return
    lk, col = LINK_CHIP.get(r["link_kind"], ("link", ""))
    show(f'<div class="card tight hover"><div class="row top"><div style="font-size:2rem">{icon}</div><div class="grow"><span class="mono muted">{label}</span><br>'
         f'<a href="{esc(r["url"])}" target="_blank"><b style="font-size:1.25rem">{esc(r["title"])}</b></a><br>'
         f'{chip(r["source"], "ink")}{chip(r["difficulty"], "grape")}{chip(str(r["duration_min"]) + " min", "sky")}{chip(lk, col)}'
         f'<div class="muted" style="font-size:.98rem">{esc(r.get("why_for_you", r["why"]))}</div></div></div></div>')


def _toggle_task(day: dict, i: int) -> None:
    state.eng().mark_task(day, i, st.session_state[f"task_{day['id']}_{i}"])


def _reset_quiz() -> None:
    for k in ("quiz", "quiz_day", "quiz_result"):
        st.session_state.pop(k, None)


def render() -> None:
    e = state.eng()
    p = state.require_profile()
    rm = e.roadmap(state.UID)
    if not rm:
        empty_state("📅", "No roadmap yet", "Generate one first – then this page becomes your daily coach.")
        st.button("Create my roadmap →", type="primary", on_click=goto, args=("🗺️ Roadmap",), key="td_create")
        return
    cur = e.current_day(state.UID)
    opts = {d["id"]: f'Day {d["seq"]} · {d["planned_date"]} · {d["title"][:44]} ({d["status"]})' for d in rm}
    default_id = (cur or rm[-1])["id"]
    pick = st.selectbox("Day", list(opts), index=list(opts).index(default_id), format_func=opts.get, key="td_pick")
    day = next(d for d in rm if d["id"] == pick)
    plan, sid = day["plan"], day["skill_id"]
    name = e.tax.name(sid)
    if st.session_state.get("quiz_day") != day["id"]:
        _reset_quiz()

    section(f"Day {day['seq']}", "", "📅")
    status_chip = {"done": chip("✓ done", "mint"), "retry": chip("needs revision", "pink"), "pending": chip("to do", "lemon")}[day["status"]]
    show(f'<div class="card tang tape"><h3>{esc(plan["title"])}</h3><p>{chip(KIND_ICON[day["kind"]] + " " + KIND_LABEL[day["kind"]], KIND_COLOR[day["kind"]])}{status_chip}'
         f'{chip("~%d min" % plan.get("est_minutes", 60), "sky")}{chip(day["planned_date"], "")}{chip("adaptive day", "pink") if day["inserted"] else ""}</p>'
         f'<p class="muted">{esc(plan.get("why", ""))}{" · Needed for " + esc(plan["needed_for"]) if plan.get("needed_for") else ""}</p></div>')

    # ---- verification ladder
    prof = p["skills"].get(sid, {})
    ver = prof.get("verified", 0)
    quiz_ok = ver >= 1
    show(f'<div class="flow"><b>{esc(name)} verification:</b> <span class="step">{chip("1 Self-completion", "mint" if day["status"] == "done" else "")}</span><span class="arr">→</span>'
         f'<span class="step">{chip("2 AI quiz", "mint" if quiz_ok else "")}</span><span class="arr">→</span><span class="step">{chip("3 Practical task", "mint" if ver >= 2 else "")}</span>'
         f'{chip("🏅 VERIFIED", "mint") if ver >= 2 else ""}</div>')
    st.write("")

    if plan.get("learn"):
        section("Lesson brief", "Key ideas for today, straight from the curated notes.", "🧠")
        show('<div class="card tight">' + "".join(f'<p>• <b>{esc(t.split(": ", 1)[0])}</b> — {esc(t.split(": ", 1)[1])}</p>' for t in plan["learn"]) + "</div>")
        hits = e.kb.notes(" ".join(plan.get("modules", [])) or name, skill_id=sid, k=2)
        if hits:
            with st.expander("📎 Retrieved study-note passages (RAG, with sources)"):
                for h in hits:
                    show(f'<div class="card tight"><span class="chip ink">{esc(h.cite)}</span><div style="white-space:pre-wrap;font-size:1rem">{esc(h.doc.text.split(chr(10), 1)[-1]).replace(chr(10), "<br>")}</div></div>')
    if plan.get("watch") or plan.get("read"):
        section("Learn", "", "🎓")
        _res_card("🎥", "WATCH", plan.get("watch"))
        _res_card("📚" if day["kind"] != "project" else "🛠️", "READ" if day["kind"] != "project" else "PROJECT REFERENCE", plan.get("read"))

    section("Do", "Tick tasks as you go – progress is saved.", "💻")
    state_ = day["task_state"]
    for i, item in enumerate(plan["checklist"]):
        st.checkbox(item, value=bool(state_.get(str(i))), key=f"task_{day['id']}_{i}", on_change=_toggle_task, args=(day, i))
    tasks_done = all(state_.get(str(i)) for i in range(len(plan["checklist"])))

    # ---- quiz
    if plan.get("quiz"):
        spec = plan["quiz"]
        section("Check-in quiz" if spec["type"] == "mini" else "Verification quiz", f"{spec['n']} questions · pass mark 70% · low scores add revision days automatically.", "🧪")
        if day["status"] in ("done", "retry") and day["quiz_score"] is not None and "quiz_result" not in st.session_state:
            show(f'<div class="card {"mint" if day["quiz_score"] >= .7 else "pink"} tight">Last score: <b>{day["quiz_score"]:.0%}</b></div>')
        if "quiz" not in st.session_state:
            if st.button("Start the quiz", key="td_qstart", type="primary"):
                with st.spinner("📝 Writing questions from your learning path…"):
                    st.session_state["quiz"] = e.day_quiz(day)
                    st.session_state["quiz_day"] = day["id"]
                st.rerun()
        elif "quiz_result" not in st.session_state:
            quiz = st.session_state["quiz"]
            with st.form("quiz_form"):
                answers = {}
                for i, q in enumerate(quiz, 1):
                    show(f'<div class="card tight"><b>{i}. {esc(q["q"])}</b> <span class="chip">{esc(q["topic"])}</span></div>')
                    choice = st.radio(f"q{i}", q["options"], index=None, key=f"qa_{q['id']}", label_visibility="collapsed")
                    answers[q["id"]] = q["options"].index(choice) if choice is not None else -1
                submitted = st.form_submit_button("Submit answers")
            if submitted:
                if -1 in answers.values():
                    st.warning("Answer every question first.")
                else:
                    with st.spinner("Grading and adapting your roadmap…"):
                        st.session_state["quiz_result"] = e.submit_quiz(state.UID, day, quiz, answers)
                    st.rerun()
        else:
            res = st.session_state["quiz_result"]
            g = res["grade"]
            cls = "mint" if res["decision"] == "continue" else "pink"
            show(f'<div class="card {cls} pop"><h3>{g["score"]}/{g["total"]} — {g["pct"]:.0%}</h3><p><b>{esc(res["message"])}</b></p></div>')
            if res["inserted"]:
                show(f'<div class="sticky pink">🔧 Roadmap adapted: +{res["inserted"]} day(s) inserted</div>')
            for q, r_ in zip(st.session_state["quiz"], g["per_question"]):
                ok = r_["correct"]
                show(f'<div class="req {"st-matched" if ok else "st-missing"}"><span class="nm">{"✓" if ok else "✗"} {esc(q["q"][:90])}</span></div>'
                     f'<div class="muted" style="margin:-.2rem 0 .4rem 1rem">Answer: <b>{esc(q["options"][q["answer"]])}</b> — {esc(q["explanation"])}</div>')
            c1, c2 = st.columns(2)
            c1.button("Continue →", key="td_qcont", type="primary", on_click=_reset_quiz)
            c2.button("Open roadmap", key="td_qrm", on_click=goto, args=("🗺️ Roadmap",))

    # ---- practical
    if day["kind"] in ("assessment", "retake", "project"):
        section("Practical task", "Ship something small and show it. I check your GitHub repo (files, README keywords) and grade your write-up against a rubric.", "🛠️")
        proj = plan.get("project") or (plan["practice"][0] if plan.get("practice") else "")
        show(f'<div class="card tight"><b>Task:</b> {esc(proj)}<br><span class="muted">Expected files: {esc(", ".join(plan.get("check_files", [])) or "README")} · concepts: {esc(", ".join(plan.get("check_keywords", [])))}</span></div>')
        with st.form("practical_form"):
            repo = st.text_input("Public GitHub repository URL (optional)", placeholder="https://github.com/you/your-project")
            expl = st.text_area("What did you build? How does it work? What would you improve?", height=130)
            code = st.text_area("Paste key code or config (optional)", height=90)
            sub = st.form_submit_button("Submit for verification")
        if sub:
            if not (repo.strip() or expl.strip()):
                st.warning("Add a repository link or a short write-up.")
            else:
                with st.spinner("🔍 Checking your project…"):
                    res = e.submit_practical(state.UID, day, repo, expl, code)
                st.session_state["prac_result"] = (day["id"], res)
                st.rerun()
        pr = st.session_state.get("prac_result")
        if pr and pr[0] == day["id"]:
            res = pr[1]
            show(f'<div class="card {"mint" if res["passed"] else "pink"} pop"><h3>{res["score"]:.0f}/100 — {"verified 🏅" if res["passed"] else "not yet"}</h3>'
                 + "".join(f'<div class="row"><span style="width:150px">{esc(k.replace("_", " "))}</span><div class="grow">{bar(v * 100, "thin")}</div></div>' for k, v in res["parts"].items())
                 + "".join(f"<p>• {esc(f)}</p>" for f in res["feedback"]) + f'<p class="muted mono">graded by: {esc(res["engine"])}</p></div>')
            if res["passed"]:
                st.balloons()

    # ---- self completion
    if day["status"] == "pending" and day["kind"] in ("learn", "practice", "revision", "project"):
        st.write("")
        if st.button("✅ Mark today complete (self-completion)", key="td_done", disabled=not tasks_done, help="Tick every task first. A quiz makes it count more."):
            e.complete_day(state.UID, day)
            st.toast("Day complete!")
            st.rerun()
