"""Gap Analysis Agent – specific, evidence-based, actionable gaps (never just a list of missing keywords)."""
from __future__ import annotations

from .curriculum import module_titles, path_for
from .models import LEVEL_NAMES, STATUS_LABEL


def skill_demand(jobs: list[dict]) -> dict[str, dict]:
    """How many curated jobs require / prefer each skill."""
    out: dict[str, dict] = {}
    for j in jobs:
        for key in ("required", "preferred"):
            for r in j[key]:
                d = out.setdefault(r["skill"], {"required": 0, "preferred": 0})
                d[key] += 1
    return out


def real_have(profile: dict) -> set[str]:
    return {s for s, v in profile["skills"].items() if not v.get("negated") and v.get("level", 0) >= 1}


def learning_effort(profile: dict, taxonomy, sid: str) -> dict:
    """Estimated study days for a skill, reduced for related experience and increased for missing prerequisites."""
    base = taxonomy.effort_days(sid)
    cs = profile["skills"].get(sid)
    if cs and not cs.get("negated"):
        factor = 0.35 if cs.get("verified") or cs["level"] >= 2 else 0.6
    else:
        best = 0.0
        for other in real_have(profile):
            best = max(best, taxonomy.transfer_credit(sid, other)[0])
        factor = 1.0 - 0.5 * best
    have = real_have(profile)
    missing = [p for p in taxonomy.prereqs(sid) if p not in have]
    prereq_days = sum(taxonomy.effort_days(p) * 0.8 for p in missing)
    return {"skill_days": round(base * factor, 1), "prereq_days": round(prereq_days, 1),
            "total_days": round(base * factor + prereq_days, 1), "missing_prereqs": missing}


def gap_entry(profile: dict, req: dict, taxonomy, demand: dict, n_jobs: int) -> dict:
    sid = req["skill_id"]
    eff = learning_effort(profile, taxonomy, sid)
    d = demand.get(sid, {"required": 0, "preferred": 0})
    titles = module_titles(sid)
    cur = req["cand_level"]
    return {
        "skill_id": sid, "name": req["name"], "status": req["status"], "status_label": STATUS_LABEL[req["status"]],
        "importance": req["importance"], "required_level": req["req_level"], "required_level_name": LEVEL_NAMES[req["req_level"]],
        "current_level": cur, "current_level_name": LEVEL_NAMES.get(cur, "None"),
        "current_evidence": req["evidence_text"] or ("No demonstrated experience." if req["status"] == "missing" else ""),
        "note": req["note"], "declared_gap": req["declared_gap"],
        "jobs_relevant": d["required"] + d["preferred"], "jobs_required": d["required"], "jobs_total": n_jobs,
        "effort": eff, "prerequisites_missing": [taxonomy.name(p) for p in eff["missing_prereqs"]],
        "recommended_path": titles,
        "project": path_for(sid).get("project", ""),
        "transfer_from": taxonomy.name(req["via"]) if req.get("via") else None,
    }


def analyze_gaps(profile: dict, job_result: dict, jobs: list[dict], taxonomy) -> list[dict]:
    demand, n = skill_demand(jobs), len(jobs)
    gaps = [gap_entry(profile, r, taxonomy, demand, n) for r in job_result["requirements"] if r["status"] != "matched"]
    order = {"required": 0, "preferred": 1}
    st = {"missing": 0, "partial": 1, "insufficient": 2}
    gaps.sort(key=lambda g: (order[g["importance"]], st[g["status"]], -g["jobs_relevant"]))
    return gaps


def gap_summary(gaps: list[dict]) -> dict:
    out = {"missing": 0, "partial": 0, "insufficient": 0}
    for g in gaps:
        out[g["status"]] += 1
    return out
