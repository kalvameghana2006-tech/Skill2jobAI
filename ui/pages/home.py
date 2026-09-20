from __future__ import annotations

from datetime import date

import streamlit as st

from ui import state
from ui.components import esc, goto, jump, section, show, tile

DEMOS = {
    "☕ Java backend fresher": "I'm a third-year B.Tech IT student from Hyderabad. I know Java pretty well and I've built two Spring Boot applications where I created REST APIs and connected them to MySQL. I haven't worked with Docker. I solved 200 LeetCode problems. I'm interested in backend development.",
    "📊 Data analyst aspirant": "Final year B.Sc Statistics student in Chennai. I know SQL and Excel, built a sales dashboard in Power BI and cleaned data with Pandas in Python. I have basic knowledge of statistics from coursework. I haven't used Tableau. Interested in data analytics.",
    "☁️ Cloud & DevOps beginner": "Third year ECE student in Bengaluru. I am comfortable with Linux commands and wrote a few Bash scripts. I deployed a static site on AWS using S3 and EC2 and I know networking basics. I have not used Docker or Kubernetes. Interested in cloud and DevOps.",
}


def render() -> None:
    e = state.eng()
    show("""<div class="hero"><span class="kicker">AI CAREER AGENT · MADE FOR STUDENTS</span>
    <h1>Don't just find jobs.<br><span class="hl">Become</span> <span class="sq">hireable.</span></h1>
    <p class="lead">Tell me what you know – typed, uploaded or spoken. I'll match real roles <b>with evidence</b>, show exactly what's missing,
    rank gaps by career ROI, plan every day of your learning, verify it, and re-match your jobs as you grow.</p></div>""")
    c1, c2 = st.columns([1, 1.2])
    with c1:
        st.button("✍️ Start with my profile", type="primary", on_click=goto, args=("🧑‍🎓 Profile Intake",), key="home_start")
    with c2:
        st.caption("No account, no key needed – the whole app also runs offline.")

    section("Try it in one click", "Pick a persona – the agent pipeline runs live and lands you on your matches.", "⚡")
    cols = st.columns(len(DEMOS))
    for col, (label, txt) in zip(cols, DEMOS.items()):
        with col:
            show(f'<div class="card tight hover"><b>{esc(label)}</b><p class="muted" style="font-size:.95rem">{esc(txt[:150])}…</p></div>')
            if st.button("Run this persona", key=f"demo_{label}"):
                with st.status("Running the agent pipeline…", expanded=True) as stt:
                    out = e.run_pipeline(txt, state.UID, hours=1.5, k=4, start=date.today())
                    for t in out.get("trace", []):
                        st.write(f"**{t['label']}** · {t['ms']} ms — {t['summary']}")
                    stt.update(label="Done! Opening your matches ✔", state="complete")
                st.session_state["last_run"] = out
                st.session_state["intake_text"] = txt
                jump("🎯 Job Matches")

    section("The loop that makes it different", "Most portals stop after 'recommended jobs'. Ours keeps going.", "🔁")
    steps = [("1", "Understand", "Skills + level + evidence from text, resume or voice", "sticky"), ("2", "Match", "Semantic, evidence-weighted, explainable scores", "sticky mint"),
             ("3", "Gap + ROI", "Exact gaps ranked by jobs unlocked per study-day", "sticky pink"), ("4", "Roadmap", "Day-by-day plan with curated resources", "sticky sky"),
             ("5", "Verify", "Quizzes + practical repo checks adapt your plan", "sticky"), ("6", "Re-match", "New roles unlock as your skills are proven", "sticky mint")]
    cols = st.columns(6)
    for col, (n, t, d, cls) in zip(cols, steps):
        with col:
            show(f'<div class="{cls}"><div style="font-size:2rem">{n}. {t}</div><div style="font-size:1rem;font-family:var(--hand);line-height:1.15;margin-top:.3rem">{d}</div></div>')

    section("Under the hood", "", "🛠️")
    n_sk, n_jobs, n_res = len(e.tax.skills), len(e._builtin_jobs), len([1 for d in e.kb.store.docs if d.metadata.get("doc_type") == "resource"])
    cols = st.columns(5)
    for col, (n, l) in zip(cols, [(n_sk, "skills in the graph"), (n_jobs, "curated job postings"), (n_res, "learning resources"), (e.kb.n_chunks, "RAG chunks indexed"), (13, "agent tools")]):
        col.markdown(tile(n, l), unsafe_allow_html=True)
    show("""<div class="card tight" style="margin-top:1rem"><p><b>LLM understands</b> → <b>embeddings discover</b> → <b>evidence validates</b> → <b>rules score</b> → <b>LangGraph orchestrates</b> →
    <b>SQLite remembers</b> → <b>LLM explains</b>. Scores are never guessed by a chatbot – open <i>Trust &amp; Accuracy</i> to see measured results.</p></div>""")
