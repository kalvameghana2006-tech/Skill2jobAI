from __future__ import annotations

import json

import streamlit as st

from core import evaluation
from core.config import EVAL_DIR, MATCH_WEIGHTS
from ui import state
from ui.components import bar, chip, esc, section, show, tile


def _pct(x: float) -> str:
    return f"{x:.0%}"


def render() -> None:
    e = state.eng()
    section("Trust & accuracy", "Numbers here are measured by running the evaluation – nothing is hand-typed. Gold labels are in data/eval/.", "🧪")
    show('<div class="card tight">20 hand-labelled candidate profiles × 43 postings (≈4,000 requirement judgements), 119 synonym pairs and structured truth for every job description. '
         'Requirement labels come from the <b>true skill levels</b>, so the system – which only reads free text – is graded against ground truth.</div>')
    rep_path = EVAL_DIR / "report.json"
    if st.button("▶ Run the evaluation now", type="primary", key="ev_run"):
        with st.spinner("Scoring extraction, normalization, parsing and matching…"):
            rep = evaluation.run_all(e)
            rep_path.write_text(json.dumps(rep, indent=2), encoding="utf-8")
        st.session_state["eval_rep"] = rep
    rep = st.session_state.get("eval_rep") or (json.loads(rep_path.read_text(encoding="utf-8")) if rep_path.exists() else None)
    if not rep:
        st.info("Press the button to compute the metrics.")
        return
    ex, no, jp, mt = rep["extraction"], rep["normalization"], rep["job_parsing"], rep["matching"]
    show(f'<div class="mono muted">embedder used for this run: {esc(rep["embedder"])}</div>')
    cols = st.columns(4)
    for col, (n, l) in zip(cols, [(_pct(ex["skills"]["f1"]), "skill extraction F1"), (_pct(no["accuracy"]), "normalization accuracy"), (_pct(jp["required"]["f1"]), "required-skill parsing F1"), (_pct(mt["status_accuracy"]), "requirement status accuracy")]):
        col.markdown(tile(n, l), unsafe_allow_html=True)
    st.write("")
    rows = [("Skill extraction – precision / recall", f'{_pct(ex["skills"]["precision"])} / {_pct(ex["skills"]["recall"])}'),
            ("“I haven’t used X” (negation) F1", _pct(ex["negation"]["f1"])),
            ("Proficiency level – exact / within one level", f'{_pct(ex["level_exact"])} / {_pct(ex["level_within_1"])}'),
            ("Job parsing – required F1 / preferred F1 / level accuracy", f'{_pct(jp["required"]["f1"])} / {_pct(jp["preferred"]["f1"])} / {_pct(jp["level_accuracy"])}'),
            ("Gap detection – precision / recall", f'{_pct(mt["gap_detection"]["precision"])} / {_pct(mt["gap_detection"]["recall"])}'),
            ("Suitable-role classification F1 (small positive set)", _pct(mt["suitable_roles"]["f1"])),
            ("Top-3 contains a role from the candidate's target family", _pct(mt["top3_relevance"])),
            ("Status accuracy if the profile were perfectly extracted", _pct(rep["matching_with_gold_profiles"]["status_accuracy"]))]
    for k, v in rows:
        show(f'<div class="req st-partial"><span class="grow">{esc(k)}</span><b>{esc(v)}</b></div>')
    with st.expander("Scoring weights in use (tunable: python -m core.evaluation --tune)"):
        for k, v in MATCH_WEIGHTS.items():
            show(f'<div class="row"><span style="width:130px">{esc(k)}</span><div class="grow">{bar(v * 250, "thin")}</div><span class="mono">{v:.2f}</span></div>')
    with st.expander("Where it still fails (honest error list)"):
        for grp, items in rep["failures"].items():
            if items:
                st.markdown(f"**{grp}**")
                st.code("\n".join(json.dumps(i) for i in items[:12]))
    show('<div class="card tight"><b>Read this honestly:</b> job descriptions here follow a small set of templates and the candidate set is small (20), so treat these as regression numbers, '
         'not a promise about arbitrary resumes. Real-world text is where Gemini parsing and a Sentence-Transformers model help most.</div>')
