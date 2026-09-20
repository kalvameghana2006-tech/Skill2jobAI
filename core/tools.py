"""LangChain tools used by the Career Copilot agent.

Every tool is a real Python function: numbers, rankings and verdicts come from the matching / ROI / RAG
code, never from the LLM guessing. Tools are decorated with @tool, fully documented and JSON-serialisable.
"""
from __future__ import annotations

import difflib
from datetime import date

from langchain_core.tools import tool

from .quiz import generate_quiz
from .verify import grade_practical

_CTX: dict = {"engine": None, "uid": "default"}


def bind(engine, uid: str = "default") -> None:
    _CTX["engine"], _CTX["uid"] = engine, uid


def _eng():
    if _CTX["engine"] is None:
        raise RuntimeError("Tools are not bound to an engine")
    return _CTX["engine"]


def _profile():
    p = _eng().get_profile(_CTX["uid"])
    if not p or not p["skills"]:
        raise ValueError("No profile yet – ask the user to add their skills on the Profile page first.")
    return p


def _find_job(query: str):
    e = _eng()
    res = e.matches(_profile())
    if not query:
        return e.target_job(_profile(), res)
    q = query.strip().lower()
    for r in res:
        if r["job_id"].lower() == q:
            return r
    titles = {r["title"].lower(): r for r in res}
    hit = difflib.get_close_matches(q, list(titles), n=1, cutoff=0.4)
    if hit:
        return titles[hit[0]]
    for t, r in titles.items():
        if q in t or t in q:
            return r
    return None


@tool
def extract_skills(text: str) -> dict:
    """Extract the skills a person has from free text, with proficiency level, evidence type and canonical names.
    Use when the user describes what they know or have built. Does NOT save the profile.

    Args:
        text: free text such as "I built two Spring Boot projects with MySQL".
    """
    from .profile_parser import parse_profile

    e = _eng()
    profile, info = parse_profile(text, e.tax, e.llm)
    skills = [{"skill": e.tax.name(s), "level": v["level"], "negated": v.get("negated", False),
               "evidence_type": v["evidence"][0]["type"] if v["evidence"] else None} for s, v in profile["skills"].items()]
    return {"skills": skills, "engine": info["engine"], "summary": f"Found {len(skills)} skills."}


@tool
def normalize_skill(term: str) -> dict:
    """Map any spelling or synonym of a skill to its canonical name (e.g. 'RESTful services' -> 'REST API').

    Args:
        term: the raw skill wording.
    """
    e = _eng()
    r = e.tax.normalize(term)
    return {"input": term, "canonical": e.tax.name(r.skill_id) if r.ok else None, "method": r.method, "confidence": r.confidence}


@tool
def match_jobs(top_k: int = 5, domain: str = "") -> dict:
    """Rank the curated jobs for the user's profile with an explainable score (required/preferred coverage,
    semantic similarity, proficiency, evidence, experience, education).

    Args:
        top_k: how many jobs to return.
        domain: optional filter such as 'Backend', 'Data Analytics', 'Cloud & DevOps'.
    """
    e = _eng()
    res = e.matches(_profile())
    if domain:
        res = [r for r in res if domain.lower() in r["domain"].lower()]
    out = [{"job_id": r["job_id"], "title": r["title"], "company": r["company"], "score": r["score"], "tier": r["tier"],
            "required": f"{r['counts']['required_met']}/{r['counts']['required_total']}", "suitable": r["suitable"]} for r in res[:top_k]]
    return {"jobs": out, "total_suitable": sum(1 for r in e.matches(_profile()) if r["suitable"]), "summary": f"Top {len(out)} jobs computed."}


@tool
def explain_job_match(job: str = "") -> dict:
    """Explain WHY a job matches: satisfied requirements with the evidence behind them, and what is missing.

    Args:
        job: job id (e.g. J03) or title; empty means the user's best match.
    """
    r = _find_job(job)
    if not r:
        return {"error": f"No job called '{job}' found."}
    ex = _eng().explain(r)
    return {"job": r["title"], "score": r["score"], "tier": r["tier"], **ex, "components": r["components"]}


@tool
def analyze_skill_gap(job: str = "") -> dict:
    """List specific skill gaps for a job: status (missing/partial/insufficient evidence), required vs current level,
    jobs affected, estimated learning days, prerequisites and a recommended path.

    Args:
        job: job id or title; empty means the user's best match.
    """
    r = _find_job(job)
    if not r:
        return {"error": f"No job called '{job}' found."}
    gaps = _eng().gaps(_profile(), r["job_id"])
    return {"job": r["title"], "gaps": [{"skill": g["name"], "status": g["status"], "importance": g["importance"], "needs": g["required_level_name"],
                                        "now": g["current_level_name"], "jobs_relevant": f"{g['jobs_relevant']}/{g['jobs_total']}",
                                        "days": g["effort"]["total_days"], "prerequisites": g["prerequisites_missing"],
                                        "path": g["recommended_path"][:5]} for g in gaps]}


@tool
def rank_skills_by_roi(top_k: int = 5) -> dict:
    """Rank the missing skills by career ROI = opportunity gained (jobs unlocked, demand) / learning effort.
    Runs a counterfactual: the skill is added to the profile and jobs are re-matched.

    Args:
        top_k: number of skills to return.
    """
    plan = _eng().roi(_profile(), k=top_k)
    return {"ranking": [{"skill": x["name"], "priority": x["priority"], "jobs_unlocked": x["jobs_unlocked"], "effort_days": x["effort_days"],
                         "roi": x["roi"], "why": x.get("explanation", "")} for x in plan["ranking"][:top_k]],
            "trajectory": plan["trajectory"]}


@tool
def search_learning_resources(skill: str, kind: str = "") -> dict:
    """Find level-matched learning resources for a skill (YouTube, Coursera, NPTEL, Skill India, documentation, practice, projects).

    Args:
        skill: skill name, e.g. 'Docker'.
        kind: optional: watch, read, practice, project or course.
    """
    e = _eng()
    r = e.tax.normalize(skill)
    if not r.ok:
        return {"error": f"Unknown skill '{skill}'."}
    prof = e.get_profile(_CTX["uid"]) or {"skills": {}}
    level = prof["skills"].get(r.skill_id, {}).get("level", 0)
    items = e.recommender.rank(r.skill_id, level, kind or None)[:6]
    return {"skill": e.tax.name(r.skill_id), "your_level": level, "resources": [
        {"title": x["title"], "type": x["type"], "source": x["source"], "difficulty": x["difficulty"], "minutes": x["duration_min"],
         "url": x["url"], "why_for_you": x["why_for_you"]} for x in items]}


@tool
def retrieve_study_notes(question: str) -> dict:
    """Answer a concept question using ONLY the curated study notes (RAG) and return the cited sources.

    Args:
        question: e.g. 'What is a Dockerfile and how does layer caching work?'
    """
    ans = _eng().kb.answer(question)
    return {"answer": ans["answer"], "sources": [s["cite"] for s in ans["sources"]], "grounded": ans["grounded"]}


@tool
def build_learning_roadmap(skills: list[str], hours_per_day: float = 1.5) -> dict:
    """Create and SAVE a personalised day-by-day roadmap for the given skills (prerequisites are added first).

    Args:
        skills: skill names to learn, in priority order.
        hours_per_day: study hours available per day.
    """
    e = _eng()
    ids = [e.tax.normalize(s).skill_id for s in skills if e.tax.normalize(s).ok]
    if not ids:
        return {"error": "None of those skills are in the taxonomy."}
    days = e.create_roadmap(_CTX["uid"], ids, hours_per_day, date.today())
    return {"days": len(days), "first_days": [f"Day {d['seq']}: {d['plan']['title']}" for d in days[:5]]}


@tool
def make_quiz(skill: str, n: int = 3) -> dict:
    """Generate a short quiz (with answers hidden until graded in the app) grounded in the learning path of a skill.

    Args:
        skill: skill name.
        n: number of questions.
    """
    e = _eng()
    r = e.tax.normalize(skill)
    if not r.ok:
        return {"error": f"Unknown skill '{skill}'."}
    qs = generate_quiz(r.skill_id, e.tax, e.kb, e.llm, n)
    return {"skill": e.tax.name(r.skill_id), "questions": [{"q": q["q"], "options": q["options"], "topic": q["topic"]} for q in qs]}


@tool
def verify_github_project(skill: str, repo_url: str, explanation: str = "") -> dict:
    """Verify a practical project: checks a public GitHub repository for the files and keywords expected for the skill.

    Args:
        skill: the skill the project demonstrates.
        repo_url: https://github.com/owner/repo
        explanation: optional short write-up of what was built.
    """
    e = _eng()
    r = e.tax.normalize(skill)
    if not r.ok:
        return {"error": f"Unknown skill '{skill}'."}
    res = grade_practical(r.skill_id, e.tax, e.embedder, e.llm, repo_url, explanation)
    return {"score": res["score"], "passed": res["passed"], "feedback": res["feedback"]}


@tool
def get_todays_task() -> dict:
    """Return today's roadmap task: what to learn, watch, read and practise, with time estimate."""
    d = _eng().current_day(_CTX["uid"])
    if not d:
        return {"message": "No pending roadmap day. Build a roadmap first."}
    p = d["plan"]
    return {"day": d["seq"], "title": p["title"], "kind": d["kind"], "minutes": p.get("est_minutes"), "checklist": p["checklist"],
            "watch": p["watch"]["title"] if p.get("watch") else None}


@tool
def rematch_jobs() -> dict:
    """Re-run job matching after skills changed and report how many roles are now suitable versus the first analysis."""
    e = _eng()
    res = e.matches(_profile())
    snaps = e.db.list_snapshots(_CTX["uid"])
    now = sum(1 for r in res if r["suitable"])
    return {"suitable_now": now, "suitable_at_start": snaps[0]["suitable_count"] if snaps else None, "best": {"title": res[0]["title"], "score": res[0]["score"]}}


ALL_TOOLS = [extract_skills, normalize_skill, match_jobs, explain_job_match, analyze_skill_gap, rank_skills_by_roi,
             search_learning_resources, retrieve_study_notes, build_learning_roadmap, make_quiz, verify_github_project,
             get_todays_task, rematch_jobs]
TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}
