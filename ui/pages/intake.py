from __future__ import annotations

from datetime import date

import streamlit as st

from core.models import ROLE_FAMILIES
from core.resume import extract_text
from core.voice import transcribe
from ui import state
from ui.components import chip, esc, goto, section, show


def _apply_pending() -> None:
    """Widgets can't be modified after creation, so text from voice/resume is queued and applied first."""
    pend = st.session_state.pop("pending_text", None)
    if pend is not None:
        mode, txt = pend
        cur = st.session_state.get("intake_text", "")
        st.session_state["intake_text"] = txt if mode == "replace" else (cur + "\n" + txt).strip()


def render() -> None:
    e = state.eng()
    _apply_pending()
    section("Tell me about you", "Three ways in – use any mix. The more you describe what you've <b>built</b>, the better the evidence.", "🖊️")
    show('<div class="sticky" style="max-width:640px">“I built two Spring Boot apps with MySQL… I haven’t used Docker.”<br>'
         '<span style="font-size:1.05rem;font-family:var(--hand)">— that sentence gives skill + level + evidence + a declared gap.</span></div>')
    st.write("")
    t_type, t_resume, t_voice = st.tabs(["✍️ Type it", "📄 Resume upload", "🎙️ Speak it"])
    with t_type:
        st.text_area("Your story", key="intake_text", height=200, label_visibility="collapsed",
                     placeholder="I'm a third-year IT student. I know Java and SQL. I've built two Spring Boot projects and I'm interested in backend development…")
    with t_resume:
        up = st.file_uploader("Upload your resume (PDF, DOCX or TXT)", type=["pdf", "docx", "txt", "md"], key="resume_up")
        if up is not None:
            key = f"resume_done_{up.name}_{up.size}"
            if key not in st.session_state:
                with st.spinner("📄 Reading your resume…"):
                    try:
                        txt = extract_text(up.name, up.getvalue())
                    except Exception as exc:
                        txt = ""
                        st.error(f"I couldn't read that file ({type(exc).__name__}). Try a text-based PDF or paste the text instead.")
                if txt.strip():
                    st.session_state[key] = True
                    st.session_state["pending_text"] = ("replace", txt.strip())
                    st.rerun()
                elif not txt and key not in st.session_state:
                    pass
                else:
                    st.warning("That file had no selectable text (scanned image?). Paste the text into the first tab.")
            else:
                st.success(f"Loaded **{esc(up.name)}** into the text box – review it in the first tab, then analyze.")
    with t_voice:
        st.caption("Record a short intro. I transcribe it (Gemini if you added a key, otherwise free Google Web Speech) and you can edit before analyzing.")
        audio = getattr(st, "audio_input", None)
        if audio is None:
            st.info("Upgrade Streamlit (>=1.40) to use the voice recorder.")
        else:
            rec = audio("Record", key="voice_rec")
            if rec is not None:
                vkey = f"voice_done_{hash(rec.getvalue())}"
                if vkey not in st.session_state:
                    with st.spinner("🎙️ Listening carefully…"):
                        txt, eng_name = transcribe(rec.getvalue(), e.llm)
                    if txt:
                        st.session_state[vkey] = True
                        st.session_state["pending_text"] = ("append", txt)
                        st.toast(f"Transcribed with {eng_name}")
                        st.rerun()
                    else:
                        st.warning(eng_name)

    section("A few details", "Optional – I detect these from your text, but you can override them.", "🎛️")
    c1, c2, c3, c4 = st.columns(4)
    degree = c1.selectbox("Degree", ["", "B.Tech", "B.E.", "BCA", "B.Sc", "MCA", "M.Tech", "M.Sc", "Diploma"], key="f_degree")
    branch = c2.selectbox("Branch", ["", "CSE", "IT", "AI&DS", "ECE", "EEE", "Mechanical", "Civil", "Other"], key="f_branch")
    year = c3.selectbox("Year", [0, 1, 2, 3, 4], format_func=lambda x: "auto" if x == 0 else f"Year {x}", key="f_year")
    location = c4.text_input("Preferred city", key="f_loc", placeholder="e.g. Hyderabad")
    interests = st.multiselect("Career interests", ROLE_FAMILIES, key="f_int", placeholder="Pick roles you like (or let me detect)")
    c5, c6, c7 = st.columns(3)
    hours = c5.slider("Study hours per day", 0.5, 4.0, 1.5, 0.5, key="f_hours")
    k = c6.slider("Skills to plan for", 2, 6, 4, key="f_k", help="How many top-ROI skills go into the roadmap")
    start = c7.date_input("Start date", date.today(), key="f_start")

    text = st.session_state.get("intake_text", "")
    go = st.button("✨ Analyze & build my plan", type="primary", key="analyze_btn")
    if go:
        if len(text.split()) < 4:
            st.warning("Add a little more detail first – even two sentences about what you know helps a lot.")
        else:
            overrides = {"degree": degree, "branch": branch if branch != "Other" else "", "year": year, "location": location, "interests": interests or None}
            with st.status("Running the agent pipeline…", expanded=True) as stt:
                out = e.run_pipeline(text, state.UID, {k_: v for k_, v in overrides.items() if v}, hours, k, start)
                for t in out.get("trace", []):
                    st.write(f"**{t['label']}** · {t['ms']} ms — {t['summary']}")
                stt.update(label="Pipeline complete ✔" if not out.get("stop") else "Need a bit more detail", state="complete" if not out.get("stop") else "error")
            st.session_state["last_run"] = out
            st.session_state.pop("roi_cache", None)
            st.session_state.pop("roadmap_skills", None)
            if out.get("stop"):
                st.warning(out["stop"])
            else:
                st.balloons()

    out = st.session_state.get("last_run")
    if out and not out.get("stop"):
        _show_result(out)


def _show_result(out: dict) -> None:
    prof, res = out["profile"], out["matches"]
    section("What I understood", "", "🔎")
    n_skill = len([1 for v in prof["skills"].values() if not v.get("negated") and not v.get("inferred")])
    neg = [state.eng().tax.name(s) for s, v in prof["skills"].items() if v.get("negated")]
    show(f'<div class="card mint"><p>I found <b>{n_skill} skills</b> with evidence via <b>{esc(out["info"]["engine"])}</b>'
         + (f' and noted you haven\'t used: {" ".join(chip(n, "pink") for n in neg)}' if neg else "") + ".</p></div>")
    if out.get("normalization"):
        with st.expander("How I normalized your words (skill graph)"):
            rows = [f'{chip(t["surface"])} → <b>{esc(t["canonical"])}</b> <span class="muted mono">({t["method"]} {t["confidence"]:.2f})</span>' for t in out["normalization"]]
            show("<br>".join(rows))
    with st.expander(f"Agent trace · orchestrated by {out.get('orchestrator', '')}", expanded=False):
        for t in out["trace"]:
            show(f'<div class="req st-partial"><span class="nm">{esc(t["label"])}</span><span class="grow">{esc(t["summary"])}</span><span class="mono">{t["ms"]} ms</span></div>')
    top = res[0]
    show(f'<div class="card tang"><div class="row"><div>{__import__("ui.components", fromlist=["ring"]).ring(top["score"], "")}</div>'
         f'<div class="grow"><h3>Best match today: {esc(top["title"])}</h3><p>{esc(top["company"])} · {esc(top["city"])} · {esc(top["tier"])}</p></div></div></div>')
    c1, c2, c3 = st.columns(3)
    c1.button("See my skill profile →", on_click=goto, args=("🧠 Skill Profile",), key="i_sk")
    c2.button("See job matches →", on_click=goto, args=("🎯 Job Matches",), key="i_jm", type="primary")
    c3.button("Open my roadmap →", on_click=goto, args=("🗺️ Roadmap",), key="i_rm")
