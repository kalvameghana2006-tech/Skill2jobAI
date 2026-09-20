"""LangGraph orchestration.

Workflow 1 (analysis):
  Profile Parser -> Skill Normalizer -> Job Retrieval -> Job Parser -> Matching Engine -> Gap Analyzer -> ROI Engine
  -> Training Recommender -> Roadmap Generator -> Resource Recommender -> Progress Tracker
  (a conditional edge stops early and asks for more detail when no skills could be extracted)

Workflow 2 (learning loop):
  Progress Update -> Skill Verification -> Update Profile -> Re-run Matching

Every node appends to `trace` (name, duration, one-line summary) so the UI can show the agent's reasoning path.
If the `langgraph` package is missing the same nodes run through a tiny sequential runner.
"""
from __future__ import annotations

import time
from datetime import date
from typing import Any, Callable, TypedDict

from . import notifications as notif
from .gap import analyze_gaps, gap_summary
from .profile import finalize
from .profile_parser import parse_profile


class State(TypedDict, total=False):
    uid: str
    text: str
    overrides: dict
    hours: float
    k: int
    start: date
    profile: dict
    info: dict
    normalization: list
    retrieved_jobs: list
    matches: list
    target: dict
    gaps: list
    gap_summary: dict
    roi: dict
    training: list
    roadmap: list
    libraries: dict
    snapshot: dict
    trace: list
    stop: str
    error: str
    event: dict
    verified_level: str


def traced(name: str, label: str):
    """Decorator: times a node and records a trace entry."""
    def deco(fn: Callable[[Any, State], dict]):
        def wrapper(engine, state: State) -> dict:
            t0 = time.perf_counter()
            try:
                upd = fn(engine, state)
            except Exception as exc:  # a node failure must never crash the app
                upd = {"stop": f"{label} failed: {exc}", "error": f"{type(exc).__name__}: {exc}"}
            summary = upd.pop("_summary", upd.get("stop", ""))
            trace = list(state.get("trace", []))
            trace.append({"node": name, "label": label, "ms": round((time.perf_counter() - t0) * 1000), "summary": summary})
            return {**upd, "trace": trace}
        wrapper.__name__ = name
        return wrapper
    return deco


# ---------------------------------------------------------------------------- analysis nodes
@traced("profile_parser", "Profile Parsing Agent")
def n_profile(engine, s: State) -> dict:
    profile, info = parse_profile(s["text"], engine.tax, engine.llm, s.get("overrides"))
    profile["user_id"] = s["uid"]
    profile["hours_per_day"] = s.get("hours", 1.5)
    old = engine.get_profile(s["uid"])
    if old and old.get("target_job_id"):
        profile["target_job_id"] = old["target_job_id"]
    n = len([1 for v in profile["skills"].values() if not v.get("negated") and not v.get("inferred")])
    return {"profile": profile, "info": info, "_summary": f"{n} skills with evidence via {info['engine']}"}


@traced("skill_normalizer", "Skill Normalization")
def n_normalize(engine, s: State) -> dict:
    prof, table = s["profile"], []
    for sid, sk in prof["skills"].items():
        for surf in sk.get("surfaces", []):
            r = engine.tax.normalize(surf)
            table.append({"surface": surf, "canonical": engine.tax.name(sid), "method": r.method, "confidence": r.confidence})
    seen, uniq = set(), []
    for t in table:
        key = (t["surface"].lower(), t["canonical"])
        if key not in seen:
            seen.add(key)
            uniq.append(t)
    real = [v for v in prof["skills"].values() if not v.get("negated")]
    if not real:
        return {"normalization": uniq, "stop": "I couldn't find any skills in that text yet. Try adding what you know and what you've built.",
                "_summary": "no skills found – asking for more detail"}
    engine.save_profile(prof)
    changed = sum(1 for t in uniq if t["surface"].lower() != t["canonical"].lower())
    return {"normalization": uniq, "_summary": f"{len(uniq)} mentions mapped to canonical skills ({changed} synonyms resolved)"}


def route_after_normalize(s: State) -> str:
    return "end" if s.get("stop") else "job_retrieval"


@traced("job_retrieval", "Job Retrieval (RAG)")
def n_retrieve(engine, s: State) -> dict:
    p = s["profile"]
    names = ", ".join(engine.tax.name(k) for k, v in p["skills"].items() if not v.get("negated"))
    hits = engine.kb.retrieve(f"{names}. Interested in {', '.join(p.get('interests', []))}", k=10, doc_type="job")
    ids = [h.doc.metadata["job_id"] for h in hits]
    return {"retrieved_jobs": ids, "_summary": f"hybrid dense+BM25 retrieval surfaced {len(ids)} candidate postings from {len(engine.jobs)}"}


@traced("job_parser", "Job Parsing Agent")
def n_job_parser(engine, s: State) -> dict:
    req = sum(len(j["required"]) for j in engine.jobs)
    pref = sum(len(j["preferred"]) for j in engine.jobs)
    return {"_summary": f"{len(engine.jobs)} postings parsed → {req} required / {pref} preferred skill requirements"}


@traced("matcher", "Job Matching Engine")
def n_match(engine, s: State) -> dict:
    res = engine.matches(s["profile"])
    target = engine.target_job(s["profile"], res)
    suitable = sum(1 for r in res if r["suitable"])
    return {"matches": res, "target": target, "_summary": f"{suitable} suitable roles; best: {target['title']} at {target['score']:.0f}%"}


@traced("gap_analyzer", "Gap Analysis Agent")
def n_gap(engine, s: State) -> dict:
    gaps = analyze_gaps(s["profile"], s["target"], engine.jobs, engine.tax)
    gs = gap_summary(gaps)
    return {"gaps": gaps, "gap_summary": gs, "_summary": f"{gs['missing']} missing, {gs['partial']} partial, {gs['insufficient']} need evidence"}


@traced("roi_engine", "ROI Engine")
def n_roi(engine, s: State) -> dict:
    plan = engine.roi(s["profile"], k=max(3, s.get("k", 4)))
    top = plan["ranking"][0]["name"] if plan["ranking"] else "–"
    return {"roi": plan, "_summary": f"counterfactual ROI over {plan['pool_size']} target jobs; learn {top} first"}


@traced("training_recommender", "Training Recommendation Agent")
def n_training(engine, s: State) -> dict:
    plan = s["roi"]["plan"][: s.get("k", 4)]
    training = [{"skill_id": x["skill_id"], "name": x["name"], "priority": x["priority"], "effort_days": x["effort_days"],
                 "jobs_unlocked": x["jobs_unlocked"], "reason": x.get("explanation") or ""} for x in plan]
    return {"training": training, "_summary": "chose " + ", ".join(t["name"] for t in training)}


@traced("roadmap_generator", "Roadmap Agent")
def n_roadmap(engine, s: State) -> dict:
    skills = [t["skill_id"] for t in s.get("training", [])]
    if not skills:
        return {"roadmap": [], "_summary": "nothing to learn – you already meet the criteria"}
    days = engine.create_roadmap(s["uid"], skills, s.get("hours", 1.5), s.get("start"))
    n_prereq = len({d["skill_id"] for d in days} - set(skills))
    return {"roadmap": days, "_summary": f"{len(days)}-day plan across {len({d['skill_id'] for d in days})} skills ({n_prereq} prerequisite skills added first)"}


@traced("resource_recommender", "Resource Recommendation Agent")
def n_resources(engine, s: State) -> dict:
    libs = {}
    for t in s.get("training", []):
        lvl = s["profile"]["skills"].get(t["skill_id"], {}).get("level", 0)
        libs[t["skill_id"]] = engine.recommender.bundle(t["skill_id"], lvl)
    n = sum(len(v) for b in libs.values() for v in b.values())
    return {"libraries": libs, "_summary": f"{n} level-matched resources across Coursera, NPTEL, Skill India, YouTube, docs and practice"}


@traced("progress_tracker", "Progress Tracker")
def n_progress(engine, s: State) -> dict:
    snap = engine.snapshot(s["uid"], "Initial analysis", s["profile"])
    engine.notify_tick(s["uid"])
    return {"snapshot": snap, "_summary": f"baseline saved ({snap['suitable']} suitable roles); notifications scheduled"}


ANALYSIS_NODES = [n_profile, n_normalize, n_retrieve, n_job_parser, n_match, n_gap, n_roi, n_training, n_roadmap, n_resources, n_progress]


# ---------------------------------------------------------------------------- learning-loop nodes
@traced("progress_update", "Progress Update")
def p_update(engine, s: State) -> dict:
    ev = s["event"]
    return {"_summary": f"{ev.get('type', 'event')} recorded for {engine.tax.name(ev['skill_id'])}"}


@traced("skill_verification", "Skill Verification")
def p_verify(engine, s: State) -> dict:
    ev = s["event"]
    level = "practical" if ev.get("practical_passed") else "quiz" if ev.get("quiz_passed") else "self"
    return {"verified_level": level, "_summary": f"verification level reached: {level}"}


@traced("update_profile", "Update Profile")
def p_profile(engine, s: State) -> dict:
    profile = engine.get_profile(s["uid"])
    return {"profile": profile, "_summary": "profile evidence and proficiency refreshed"}


@traced("rematch", "Re-run Matching")
def p_rematch(engine, s: State) -> dict:
    res = engine.matches(s["profile"])
    suitable = sum(1 for r in res if r["suitable"])
    return {"matches": res, "_summary": f"{suitable} suitable roles after update"}


LEARNING_NODES = [p_update, p_verify, p_profile, p_rematch]


# ---------------------------------------------------------------------------- runners
def _sequential(engine, nodes, state: State, guard: Callable[[State], bool] | None = None) -> State:
    for fn in nodes:
        state = {**state, **fn(engine, state)}
        if guard and guard(state):
            break
    return state


def _langgraph(engine, nodes, state: State, conditional: dict[str, Callable] | None = None) -> State:
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(State)
    for fn in nodes:
        g.add_node(fn.__name__, (lambda st, _fn=fn: _fn(engine, st)))
    g.add_edge(START, nodes[0].__name__)
    for a, b in zip(nodes, nodes[1:]):
        cond = (conditional or {}).get(a.__name__)
        if cond:
            g.add_conditional_edges(a.__name__, cond, {"end": END, b.__name__: b.__name__})
        else:
            g.add_edge(a.__name__, b.__name__)
    g.add_edge(nodes[-1].__name__, END)
    return g.compile().invoke(state)


def run_pipeline(engine, text: str, uid: str, overrides: dict, hours: float, k: int, start: date) -> State:
    state: State = {"uid": uid, "text": text, "overrides": overrides, "hours": hours, "k": k, "start": start, "trace": []}
    try:
        out = _langgraph(engine, ANALYSIS_NODES, state, {"skill_normalizer": lambda s: "end" if s.get("stop") else "job_retrieval"})
        out["orchestrator"] = "LangGraph"
    except ImportError:
        out = _sequential(engine, ANALYSIS_NODES, state, guard=lambda s: bool(s.get("stop")))
        out["orchestrator"] = "sequential fallback (install langgraph)"
    return out


def run_learning_loop(engine, uid: str, event: dict) -> State:
    state: State = {"uid": uid, "event": event, "trace": []}  # type: ignore[typeddict-unknown-key]
    try:
        out = _langgraph(engine, LEARNING_NODES, state)
    except ImportError:
        out = _sequential(engine, LEARNING_NODES, state)
    return out
