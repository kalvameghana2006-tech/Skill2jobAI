"""Opportunity / ROI Engine – which missing skill should be learned first, and why.

For every gap skill we run a *counterfactual*: add the skill (and its missing prerequisites) to the profile,
re-run the real matcher over the target job pool and measure

    opportunity = 4 * jobs newly made suitable + 0.12 * total score gain + demand (required 1.0, preferred 0.35)
    ROI         = opportunity / learning effort (days, incl. missing prerequisites)

Skills are then ordered greedily: after "learning" the best one we re-rank, so the plan accounts for overlap.
"""
from __future__ import annotations

from .gap import learning_effort, real_have, skill_demand
from .profile import simulate

TARGET_LEVEL = 2


def _pool(results: list[dict], pool_n: int) -> list[dict]:
    reachable = [r for r in results if r["score"] >= 30]
    return (reachable or results)[:pool_n]


def _candidates(profile: dict, pool_results: list[dict], taxonomy) -> dict[str, dict]:
    cands: dict[str, dict] = {}
    for r in pool_results:
        for req in r["requirements"]:
            if req["status"] == "matched":
                continue
            c = cands.setdefault(req["skill_id"], {"jobs": [], "required": 0, "preferred": 0, "level": TARGET_LEVEL, "status": req["status"]})
            c["jobs"].append(r["job_id"])
            c[req["importance"]] += 1
            c["level"] = max(c["level"], min(3, req["req_level"])) if req["req_level"] >= 3 and req["importance"] == "required" and False else c["level"]
    return cands


def _evaluate(profile, sid, info, pool_jobs, base_by_id, matcher, taxonomy, pv) -> dict:
    eff = learning_effort(profile, taxonomy, sid)
    adds = {sid: TARGET_LEVEL}
    adds.update({p: 1 for p in eff["missing_prereqs"]})
    sim = simulate(profile, adds)
    new = {r["job_id"]: r for r in matcher.match_all(sim, pool_jobs, pv)}
    unlocked, gain = [], 0.0
    for jid, r in new.items():
        old = base_by_id[jid]
        gain += max(0.0, r["score"] - old["score"])
        if r["suitable"] and not old["suitable"]:
            unlocked.append(jid)
    total_days = max(1.0, eff["total_days"])
    # verifying an existing self-declared skill is cheap
    cs = profile["skills"].get(sid)
    if cs and not cs.get("negated") and cs["level"] >= TARGET_LEVEL:
        total_days = max(1.0, total_days * 0.5)
    opportunity = 4 * len(unlocked) + 0.12 * gain + 1.0 * info["required"] + 0.35 * info["preferred"]
    return {"skill_id": sid, "name": taxonomy.name(sid), "jobs_unlocked": len(unlocked), "unlocked_ids": unlocked, "score_gain": round(gain, 1),
            "demand_required": info["required"], "demand_preferred": info["preferred"], "effort_days": round(total_days, 1),
            "effort": eff, "opportunity": round(opportunity, 2), "roi": round(opportunity / total_days, 3), "status": info["status"]}


def _label(ratio: float) -> str:
    return "Very High" if ratio >= 0.6 else "High" if ratio >= 0.35 else "Medium" if ratio >= 0.15 else "Low"


def rank_skills(profile: dict, jobs: list[dict], matcher, taxonomy, pool_n: int = 20, base_results: list[dict] | None = None,
                _pv=None) -> list[dict]:
    base = base_results or matcher.match_all(profile, jobs)
    pool_res = _pool(base, pool_n)
    ids = {r["job_id"] for r in pool_res}
    pool_jobs = [j for j in jobs if j["id"] in ids]
    base_by_id = {r["job_id"]: r for r in pool_res}
    cands = _candidates(profile, pool_res, taxonomy)
    pv = _pv if _pv is not None else matcher.emb.encode([matcher._profile_text(profile)])[0]
    out = [_evaluate(profile, sid, info, pool_jobs, base_by_id, matcher, taxonomy, pv) for sid, info in cands.items()]
    out.sort(key=lambda x: -x["roi"])
    top = out[0]["roi"] if out else 1.0
    for x in out:
        x["priority"] = _label(x["roi"] / top if top else 0)
        x["relative_roi"] = round(x["roi"] / top, 2) if top else 0
    return out


def plan_learning_order(profile: dict, jobs: list[dict], matcher, taxonomy, k: int = 5, pool_n: int = 20) -> dict:
    """Greedy ROI ordering with re-ranking after each simulated skill. Returns ranked list + trajectory."""
    base = matcher.match_all(profile, jobs)
    pv = matcher.emb.encode([matcher._profile_text(profile)])[0]
    pool_res = _pool(base, pool_n)
    pool_ids = {r["job_id"] for r in pool_res}
    first_ranking = rank_skills(profile, jobs, matcher, taxonomy, pool_n, base_results=base, _pv=pv)
    cur, chosen, traj = profile, [], []
    suitable0 = sum(1 for r in base if r["suitable"])
    traj.append({"after": "today", "suitable": suitable0, "avg_top5": round(sum(r["score"] for r in base[:5]) / max(1, len(base[:5])), 1)})
    remaining = first_ranking
    for _ in range(k):
        if not remaining:
            break
        best = remaining[0]
        chosen.append(best)
        eff = learning_effort(cur, taxonomy, best["skill_id"])
        adds = {best["skill_id"]: TARGET_LEVEL, **{p: 1 for p in eff["missing_prereqs"]}}
        cur = simulate(cur, adds)
        res = matcher.match_all(cur, jobs, pv)
        traj.append({"after": best["name"], "suitable": sum(1 for r in res if r["suitable"]),
                     "avg_top5": round(sum(r["score"] for r in res[:5]) / max(1, len(res[:5])), 1)})
        remaining = [x for x in rank_skills(cur, jobs, matcher, taxonomy, pool_n, base_results=res, _pv=pv) if x["skill_id"] not in {c["skill_id"] for c in chosen}]
        # keep pool stable so the plan is coherent
    top = first_ranking[0]["roi"] if first_ranking else 1.0
    return {"ranking": first_ranking, "plan": chosen, "trajectory": traj, "pool_size": len(pool_ids)}


def explain_priority(item: dict, others: list[dict], demand_total: int) -> str:
    """Human-readable ROI reasoning that compares against a lower-ranked alternative."""
    txt = (f"{item['name']} is {item['priority'].lower()} priority: it appears in {item['demand_required']} required and "
           f"{item['demand_preferred']} preferred slots among your target jobs, would make {item['jobs_unlocked']} more job(s) suitable, "
           f"and needs about {item['effort_days']:g} study days.")
    lower = [o for o in others if o["roi"] < item["roi"] and o["effort_days"] > item["effort_days"]]
    if lower:
        o = lower[0]
        txt += (f" It comes before {o['name']} because {o['name']} needs about {o['effort_days']:g} days for "
                f"{o['jobs_unlocked']} unlocked job(s).")
    return txt
