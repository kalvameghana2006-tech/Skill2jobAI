"""Job Matching Agent – evidence-backed, semantic, explainable.

    LLM understands -> normalisation maps -> embeddings find relations -> evidence validates -> rules score

Per requirement we compute a *presence* credit (direct evidence, inferred, or transferable from a related
skill family), a *level fit* and an *evidence strength*. Seven signals are then combined with configurable
weights (core/config.py::MATCH_WEIGHTS). The score is never produced by an LLM and never by raw embedding
similarity alone.
"""
from __future__ import annotations

import numpy as np

from .config import MATCH_WEIGHTS, STRONG_SCORE, SUITABLE_PROFICIENCY, SUITABLE_REQ_COVERAGE, SUITABLE_SCORE
from .models import EVIDENCE_LABEL, LEVEL_NAMES, strongest

CS_BRANCHES = {"CSE", "IT", "AI&DS"}
DEGREE_RANK = {"Diploma": 0, "B.Sc": 1, "BCA": 1, "B.Tech": 2, "B.E.": 2, "MCA": 3, "M.Sc": 3, "M.Tech": 3}


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


class Matcher:
    def __init__(self, taxonomy, embedder, weights: dict | None = None):
        self.tax, self.emb = taxonomy, embedder
        self.weights = dict(weights or MATCH_WEIGHTS)
        self._job_vecs: dict[str, np.ndarray] = {}

    # ------------------------------------------------------------------ requirement coverage
    def cover(self, profile: dict, sid: str, req_level: int) -> dict:
        skills = profile["skills"]
        cs = skills.get(sid)
        res = {"skill_id": sid, "name": self.tax.name(sid), "req_level": req_level, "presence": 0.0, "cand_level": 0, "level_fit": 0.0,
               "evidence": 0.0, "status": "missing", "via": None, "note": "", "evidence_text": "", "evidence_type": None, "declared_gap": False}
        if cs and cs.get("negated"):
            res.update(note="You said you haven't used this yet.", declared_gap=True, evidence_text=cs["evidence"][0]["text"] if cs["evidence"] else "")
            return res
        if cs:
            ev = strongest(cs["evidence"])
            lvl = cs["level"]
            fit = min(1.0, lvl / req_level)
            best = max(cs["evidence"], key=lambda e: strongest([e])) if cs["evidence"] else {"text": "", "type": "self_declared"}
            res.update(presence=0.9 if cs.get("inferred") else 1.0, cand_level=lvl, level_fit=fit, evidence=ev,
                       evidence_text=best["text"], evidence_type=best["type"])
            if fit >= 1.0 and ev >= 0.5:
                res["status"] = "matched"
            elif fit >= 1.0:
                res.update(status="insufficient", note="Listed, but nothing shows you have used it – add a project or take the quiz to verify.")
            else:
                res.update(status="partial", note=f"Needs {LEVEL_NAMES[req_level]}, evidence suggests {LEVEL_NAMES[lvl]}.")
            return res
        # transferable credit from a related skill (curated families, embeddings only for unblocked pairs)
        best_credit, best_src, why = 0.0, None, ""
        for other, ocs in skills.items():
            if ocs.get("negated"):
                continue
            credit, reason = self.tax.transfer_credit(sid, other)
            credit *= 0.6 + 0.4 * strongest(ocs["evidence"])
            if credit > best_credit:
                best_credit, best_src, why = credit, other, reason
        if best_src and best_credit > 0.1:
            ocs = skills[best_src]
            res.update(presence=round(best_credit, 3), cand_level=ocs["level"], level_fit=min(1.0, ocs["level"] / req_level),
                       evidence=strongest(ocs["evidence"]) * 0.7, status="partial", via=best_src,
                       note=f"Transferable from your {self.tax.name(best_src)} ({why}); direct {res['name']} still needs to be shown.")
        return res

    # ------------------------------------------------------------------ text similarity
    def _profile_text(self, profile: dict) -> str:
        names = [self.tax.name(s) for s, v in profile["skills"].items() if not v.get("negated")]
        return ". ".join([", ".join(names), ", ".join(profile.get("interests", [])), " ".join(profile.get("projects", [])[:3])])

    def _job_vec(self, job: dict) -> np.ndarray:
        if job["id"] not in self._job_vecs:
            names = ", ".join(self.tax.name(r["skill"]) for r in job["required"] + job["preferred"])
            self._job_vecs[job["id"]] = self.emb.encode([f"{job['title']}. {job.get('domain', '')}. {names}"])[0]
        return self._job_vecs[job["id"]]

    def _soft(self, profile: dict, sid: str) -> float:
        """Best semantic proximity between a requirement and any real candidate skill (0-1, dampened)."""
        best = 0.0
        for other, cs in profile["skills"].items():
            if cs.get("negated") or other == sid or frozenset((sid, other)) in self.tax.not_related:
                continue
            best = max(best, self.tax.similarity(sid, other))
        scale = 0.6 if self.emb.is_semantic else 0.35
        return scale * clamp((best - 0.25) / 0.5)

    # ------------------------------------------------------------------ fits
    @staticmethod
    def experience_fit(profile: dict, job: dict) -> float:
        eff = profile.get("experience_years", 0.0) + min(0.4, 0.1 * len(profile.get("projects", [])))
        need = job["experience"]["min"]
        return 1.0 if eff >= need else clamp(1 - (need - eff) * 0.4)

    @staticmethod
    def education_fit(profile: dict, job: dict) -> float:
        deg, branch = profile.get("degree", ""), profile.get("branch", "")
        if not deg:
            d = 0.8
        elif deg in job["degrees"]:
            d = 1.0
        else:
            ranks = [DEGREE_RANK.get(x, 2) for x in job["degrees"]]
            mine = DEGREE_RANK.get(deg, 2)
            d = 0.95 if mine >= min(ranks) else 0.7
        b = 0.8 if not branch else (1.0 if branch in CS_BRANCHES else 0.75 if branch in {"ECE", "EEE"} else 0.5)
        return 0.6 * d + 0.4 * b

    # ------------------------------------------------------------------ main entry
    def match(self, profile: dict, job: dict, profile_vec: np.ndarray | None = None) -> dict:
        w = self.weights
        req = [self.cover(profile, r["skill"], r["level"]) for r in job["required"]]
        pref = [self.cover(profile, r["skill"], r["level"]) for r in job["preferred"]]
        for r in req:
            r["importance"] = "required"
        for r in pref:
            r["importance"] = "preferred"

        def mean(xs):
            return sum(xs) / len(xs) if xs else 0.0

        req_cov = mean([r["presence"] for r in req])
        prof_fit = mean([r["presence"] * r["level_fit"] for r in req])
        evid = mean([r["presence"] * r["evidence"] for r in req])
        pref_cov = mean([r["presence"] * (0.5 + 0.5 * r["level_fit"]) for r in pref]) if pref else None

        soft_terms = [(max(r["presence"], self._soft(profile, r["skill_id"])), 1.0) for r in req] + \
                     [(max(r["presence"], self._soft(profile, r["skill_id"])), 0.5) for r in pref]
        tw = sum(x[1] for x in soft_terms) or 1
        soft_cov = sum(v * wt for v, wt in soft_terms) / tw
        pv = profile_vec if profile_vec is not None else self.emb.encode([self._profile_text(profile)])[0]
        text_sim = clamp((float(pv @ self._job_vec(job)) - 0.05) / 0.45)
        semantic = 0.7 * soft_cov + 0.3 * text_sim
        exp_fit, edu_fit = self.experience_fit(profile, job), self.education_fit(profile, job)

        comps = {"required": req_cov, "preferred": pref_cov if pref_cov is not None else req_cov, "semantic": semantic,
                 "proficiency": prof_fit, "evidence": evid, "experience": exp_fit, "education": edu_fit}
        score = 100 * sum(w[k] * comps[k] for k in w)
        met = sum(1 for r in req if r["status"] == "matched")
        pmet = sum(1 for r in pref if r["status"] == "matched")
        suitable = score >= SUITABLE_SCORE and req_cov >= SUITABLE_REQ_COVERAGE and prof_fit >= SUITABLE_PROFICIENCY
        if suitable and score >= STRONG_SCORE and req_cov >= 0.8:
            tier = "Strong match"
        elif suitable:
            tier = "Good match"
        elif score >= SUITABLE_SCORE:
            tier = "Close match"
        elif score >= 45:
            tier = "Stretch"
        else:
            tier = "Not yet"
        loc = profile.get("location", "")
        return {
            "job_id": job["id"], "title": job["title"], "company": job["company"], "city": job.get("city", ""), "mode": job.get("mode", ""),
            "domain": job.get("domain", ""), "salary_lpa": job.get("salary_lpa"), "score": round(score, 1), "tier": tier, "suitable": suitable,
            "components": {k: round(v, 3) for k, v in comps.items()}, "requirements": req + pref,
            "counts": {"required_met": met, "required_total": len(req), "required_partial": sum(1 for r in req if r["status"] in ("partial", "insufficient")),
                       "preferred_met": pmet, "preferred_total": len(pref)},
            "req_coverage": round(req_cov, 3),
            "interest_match": job.get("domain") in profile.get("interests", []),
            "location_ok": (not loc) or job.get("mode") == "Remote" or job.get("city") == loc,
            "evidence_confidence": "High" if evid >= 0.6 else "Medium" if evid >= 0.35 else "Low",
        }

    def match_all(self, profile: dict, jobs: list[dict], profile_vec: np.ndarray | None = None) -> list[dict]:
        pv = profile_vec if profile_vec is not None else self.emb.encode([self._profile_text(profile)])[0]
        results = [self.match(profile, j, pv) for j in jobs]
        for r in results:
            r["rank_score"] = r["score"] + (4 if r["interest_match"] else 0)
        results.sort(key=lambda r: (-r["rank_score"], -r["score"]))
        return results

    def suitable(self, results: list[dict]) -> list[dict]:
        return [r for r in results if r["suitable"]]


# ---------------------------------------------------------------------- explanations
def explain_match(result: dict, taxonomy=None) -> dict:
    """Deterministic, evidence-cited explanation (an LLM may polish the wording, never the facts)."""
    req = [r for r in result["requirements"] if r["importance"] == "required"]
    pref = [r for r in result["requirements"] if r["importance"] == "preferred"]
    c = result["counts"]
    strengths, gaps = [], []
    for r in req + pref:
        if r["status"] == "matched":
            label = EVIDENCE_LABEL.get(r["evidence_type"], "evidence")
            strengths.append(f"{r['name']} – {LEVEL_NAMES[r['cand_level']]} level, backed by {label.lower()}" + (f": “{r['evidence_text'][:110]}”" if r["evidence_text"] else ""))
        else:
            tag = "Required" if r["importance"] == "required" else "Preferred"
            gaps.append(f"{r['name']} ({tag.lower()}, needs {LEVEL_NAMES[r['req_level']]}) – " + (r["note"] or "no evidence found in your profile."))
    if c["required_total"]:
        head = f"You satisfy {c['required_met']} of {c['required_total']} core requirements"
        if c["required_partial"]:
            head += f" and partially meet {c['required_partial']} more"
        head += f", plus {c['preferred_met']} of {c['preferred_total']} preferred skills."
    else:
        head = "No explicit requirements were parsed for this job."
    verdict = {"Strong match": "This is a strong fit – start applying while you close the small gaps.",
               "Good match": "You meet the core bar; closing the gaps below will make you stand out.",
               "Close match": "Your overall score is high, but at least one core skill is below the level asked for – see the gaps below.",
               "Stretch": "This is a stretch role today, but the gap list shows a realistic route.",
               "Not yet": "Not a fit yet – other roles are closer. Use the gap analysis to see what would change that."}[result["tier"]]
    return {"headline": head, "verdict": verdict, "strengths": strengths, "gaps": gaps}
