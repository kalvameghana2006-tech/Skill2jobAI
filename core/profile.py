"""Candidate profile helpers: evidence -> proficiency estimation, implied skills, simulation for ROI."""
from __future__ import annotations

import copy

from .models import EVIDENCE_STRENGTH, strongest

PROJECT_TYPES = ("project", "major_project", "github")


def new_profile(user_id: str = "default") -> dict:
    return {"user_id": user_id, "name": "", "degree": "", "branch": "", "year": 0, "location": "", "interests": [],
            "experience_years": 0.0, "hours_per_day": 1.5, "target_role": "", "projects": [], "certifications": [],
            "raw_text": "", "skills": {}}


def estimate_level(evidence: list[dict], stated: int | None = None) -> int:
    """Proficiency 1-4 estimated from *evidence*, nudged (at most one level) by the stated level.

    production/internship -> Advanced;  >=3 projects -> Advanced;  a project -> Intermediate;
    course / certificate / practice / self-declared -> Beginner.  A self-claimed "expert" without evidence
    can therefore only reach Intermediate.
    """
    types = [e.get("type", "self_declared") for e in evidence]
    prod = sum(1 for t in types if t in ("internship", "production"))
    proj = sum(int(e.get("count", 1)) for e in evidence if e.get("type") in PROJECT_TYPES)
    practice = sum(int(e.get("count", 1)) for e in evidence if e.get("type") == "practice")
    if prod:
        base = 3
    elif proj >= 3:
        base = 3
    elif proj >= 1:
        base = 2
    elif practice >= 100:
        base = 2
    else:
        base = 1
    if "verified_practical" in types or "verified_quiz" in types:
        base = max(base, 2)
    if stated:
        level = min(stated, base + 1) if stated > base else max(stated, base - 1)
    else:
        level = base
    return max(1, min(4, level))


def confidence_of(evidence: list[dict]) -> float:
    if not evidence:
        return 0.3
    best = strongest(evidence)
    extra = min(0.12, 0.04 * (len(evidence) - 1))
    return round(min(1.0, 0.35 + 0.65 * best + extra), 2)


def add_evidence(profile: dict, sid: str, text: str, etype: str, stated: int | None = None, count: int = 1,
                 negated: bool = False, source: str = "text", surface: str | None = None) -> None:
    sk = profile["skills"].setdefault(sid, {"skill_id": sid, "level": 1, "stated": None, "evidence": [], "confidence": 0.3,
                                            "verified": 0, "negated": False, "inferred": False, "source": source})
    if surface and surface not in sk.setdefault("surfaces", []):
        sk["surfaces"].append(surface)
    if negated:
        if not sk["evidence"]:
            sk["negated"] = True
            sk["evidence"] = [{"text": text, "type": "self_declared"}]
        return
    if sk.get("negated") or sk.get("inferred"):  # real evidence overrides earlier negation / inference
        sk.update(negated=False, inferred=False, evidence=[])
    if not any(e["text"] == text and e["type"] == etype for e in sk["evidence"]):
        ev = {"text": text, "type": etype}
        if count > 1:
            ev["count"] = count
        sk["evidence"].append(ev)
    if stated:
        sk["stated"] = max(stated, sk.get("stated") or 0)


def finalize(profile: dict, taxonomy) -> dict:
    """Recompute levels / confidence from evidence and add low-confidence implied skills."""
    skills = profile["skills"]
    for sid in [s for s, v in skills.items() if v.get("inferred")]:
        del skills[sid]                                   # will be re-derived
    for sid, sk in skills.items():
        if sk.get("negated"):
            sk.update(level=0, confidence=0.9)
            continue
        ev = sk["evidence"]
        if sk.get("verified", 0) >= 1 and not any(e["type"].startswith("verified") for e in ev):
            ev.append({"text": "Passed the skill-verification quiz", "type": "verified_quiz"})
        sk["level"] = estimate_level(ev, sk.get("stated"))
        sk["confidence"] = confidence_of(ev)
    for sid, sk in list(skills.items()):
        if sk.get("negated") or sk.get("inferred"):
            continue
        best = strongest(sk["evidence"])
        strong = best >= 0.5
        for imp in taxonomy.implied(sid):
            etype = "project" if best >= 0.8 else "inferred"
            note = f"Applied within your {taxonomy.name(sid)} work (which requires {taxonomy.name(imp)})"
            cur = skills.get(imp)
            if cur is None:
                skills[imp] = {"skill_id": imp, "level": min(2, sk["level"]) if strong else 1, "stated": None, "verified": 0,
                               "evidence": [{"text": note, "type": etype}], "confidence": 0.5 if etype == "project" else 0.45,
                               "negated": False, "inferred": True, "source": "implied"}
            elif not cur.get("negated") and not cur.get("inferred") and strongest(cur["evidence"]) < EVIDENCE_STRENGTH[etype]:
                cur["evidence"].append({"text": note, "type": etype})
                cur["level"] = estimate_level(cur["evidence"], cur.get("stated"))
                cur["confidence"] = confidence_of(cur["evidence"])
    return profile


def real_skills(profile: dict) -> dict:
    """Skills the candidate actually has (not negated)."""
    return {k: v for k, v in profile["skills"].items() if not v.get("negated")}


def simulate(profile: dict, additions: dict[str, int]) -> dict:
    """Copy of profile with extra (skill -> level) added as project-grade evidence (used for ROI what-ifs)."""
    p = copy.deepcopy(profile)
    for sid, lvl in additions.items():
        cur = p["skills"].get(sid)
        if cur and not cur.get("negated") and not cur.get("inferred") and cur["level"] >= lvl:
            continue
        p["skills"][sid] = {"skill_id": sid, "level": lvl, "stated": None, "verified": 0, "negated": False, "inferred": False,
                            "evidence": [{"text": "Simulated: completed roadmap", "type": "project"}], "confidence": 0.8, "source": "sim"}
    return p


def mark_verified(profile: dict, sid: str, kind: str, detail: str) -> None:
    """kind: 'quiz' or 'practical' -> raises verified flag and appends verified evidence."""
    sk = profile["skills"].setdefault(sid, {"skill_id": sid, "level": 1, "stated": None, "evidence": [], "confidence": 0.5,
                                            "verified": 0, "negated": False, "inferred": False, "source": "roadmap"})
    sk.update(negated=False, inferred=False)
    et = "verified_practical" if kind == "practical" else "verified_quiz"
    sk["evidence"] = [e for e in sk["evidence"] if e["type"] not in ("inferred",)]
    sk["evidence"].append({"text": detail, "type": et})
    sk["verified"] = max(sk.get("verified", 0), 2 if kind == "practical" else 1)


INTEREST_KEYWORDS = {
    "Backend": ["backend", "back-end", "back end", "server side", "apis", "microservices"],
    "Frontend": ["frontend", "front-end", "front end", "ui development", "web design", "ui/ux"],
    "Full Stack": ["full stack", "fullstack", "full-stack", "web development", "web developer"],
    "Data Analytics": ["data analyst", "data analytics", "analytics", "business intelligence", "dashboards", "bi "],
    "Data Science & ML": ["data science", "data scientist", "machine learning", "ml ", "ai ", "artificial intelligence", "deep learning", "nlp", "genai", "generative ai", "computer vision"],
    "Data Engineering": ["data engineer", "data engineering", "etl", "data pipelines", "big data"],
    "Cloud & DevOps": ["devops", "cloud", "sre", "site reliability", "infrastructure", "kubernetes"],
    "QA & Testing": ["testing", " qa", "quality assurance", "sdet", "automation testing"],
    "Software Engineering": ["software engineer", "software developer", "sde", "product company", "core software"],
    "Mobile": ["android", "ios", "flutter", "mobile app"],
    "Security": ["cyber", "security"],
    "Database": ["database", "dba", "sql developer"],
}


def detect_interests(text: str) -> list[str]:
    t = f" {text.lower()} "
    return [dom for dom, kws in INTEREST_KEYWORDS.items() if any(k in t for k in kws)]
