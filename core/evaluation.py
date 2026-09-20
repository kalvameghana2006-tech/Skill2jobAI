"""Internal accuracy evaluation. Numbers are ONLY reported by actually running this module.

    python -m core.evaluation            # print the report and save data/eval/report.json
    python -m core.evaluation --tune     # random-search matching weights against the gold labels

Gold data (hand-written):
  data/eval/candidates.json    20 candidate texts with the true skills / levels / declared gaps
  data/eval/normalization.json surface form -> canonical skill pairs
  data/eval/job_gold.json      structured truth (required / preferred / level) behind each job description

Metrics
  * skill extraction   precision / recall / F1 (present skills) + negation ("I haven't used X") accuracy
  * proficiency        exact and within-one-level accuracy on correctly extracted skills
  * normalization      accuracy on synonyms / aliases / misspellings
  * job parsing        required-vs-preferred classification and level accuracy over all postings
  * matching           requirement-level status accuracy over 20 candidates x all postings (has / partial / missing),
                       gap precision / recall, suitable-role F1, and top-3 role relevance
The requirement labels are derived from the hand-written gold skill levels, so the system (which only sees free text)
is graded against ground truth, not against itself.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from .config import EVAL_DIR, MATCH_WEIGHTS, SUITABLE_REQ_COVERAGE, SUITABLE_SCORE
from .matcher import Matcher
from .profile_parser import parse_profile


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3), "tp": tp, "fp": fp, "fn": fn}


def _load(name: str):
    return json.loads((EVAL_DIR / name).read_text(encoding="utf-8"))


def gold_profile(cand: dict, tax) -> dict:
    """Ideal profile built directly from the hand-labelled skills (bypasses text understanding)."""
    skills = {}
    for name, lvl in cand["gold"].items():
        sid = tax.id_from_name(name)
        skills[sid] = {"skill_id": sid, "level": lvl, "evidence": [{"text": "gold", "type": "project"}], "confidence": 0.9, "verified": 0,
                       "negated": False, "inferred": False, "stated": None}
    return {"skills": skills, "interests": [], "experience_years": 0, "projects": [], "degree": "", "branch": "", "location": ""}


def eval_extraction(engine, cands: list[dict]) -> tuple[dict, list[dict]]:
    tax = engine.tax
    tp = fp = fn = 0
    ntp = nfp = nfn = 0
    exact = within1 = n_lvl = 0
    fails: list[dict] = []
    profiles = {}
    for c in cands:
        prof, _ = parse_profile(c["text"], tax, None)
        profiles[c["id"]] = prof
        gold_ids = {tax.id_from_name(n) for n in c["gold"]}
        # implied (inferred) skills are not penalised as false positives unless the gold says otherwise
        pred = {s: v["level"] for s, v in prof["skills"].items() if not v.get("negated") and (not v.get("inferred") or s in gold_ids)}
        pred_neg = {s for s, v in prof["skills"].items() if v.get("negated")}
        gold = {tax.id_from_name(n): l for n, l in c["gold"].items()}
        gold_neg = {tax.id_from_name(n) for n in c["negated"]}
        g, p = set(gold), set(pred)
        tp += len(g & p)
        fp += len(p - g)
        fn += len(g - p)
        ntp += len(gold_neg & pred_neg)
        nfp += len(pred_neg - gold_neg)
        nfn += len(gold_neg - pred_neg)
        for s in g & p:
            n_lvl += 1
            exact += pred[s] == gold[s]
            within1 += abs(pred[s] - gold[s]) <= 1
            if abs(pred[s] - gold[s]) > 1:
                fails.append({"case": c["id"], "kind": "level", "skill": tax.name(s), "gold": gold[s], "pred": pred[s]})
        for s in p - g:
            fails.append({"case": c["id"], "kind": "extra skill", "skill": tax.name(s)})
        for s in g - p:
            fails.append({"case": c["id"], "kind": "missed skill", "skill": tax.name(s)})
    out = {"skills": prf(tp, fp, fn), "negation": prf(ntp, nfp, nfn),
           "level_exact": round(exact / n_lvl, 3) if n_lvl else 0, "level_within_1": round(within1 / n_lvl, 3) if n_lvl else 0, "n_level_pairs": n_lvl}
    engine._eval_profiles = profiles
    return out, fails


def eval_normalization(engine) -> tuple[dict, list[dict]]:
    tax, pairs = engine.tax, _load("normalization.json")
    ok = tot = 0
    fails = []
    for canonical, terms in pairs.items():
        for t in terms:
            tot += 1
            r = tax.normalize(t)
            good = r.ok and tax.name(r.skill_id) == canonical
            ok += good
            if not good:
                fails.append({"term": t, "expected": canonical, "got": tax.name(r.skill_id) if r.ok else None})
    return {"accuracy": round(ok / tot, 3), "n": tot}, fails


def eval_job_parsing(engine) -> tuple[dict, list[dict]]:
    gold = _load("job_gold.json")
    rp = {"required": [0, 0, 0], "preferred": [0, 0, 0]}
    lvl_ok = lvl_n = 0
    fails = []
    for j in engine._builtin_jobs:
        g = gold[j["id"]]
        for key in ("required", "preferred"):
            gs = {x["skill"]: x["level"] for x in g[key]}
            ps = {x["skill"]: x["level"] for x in j[key]}
            rp[key][0] += len(set(gs) & set(ps))
            rp[key][1] += len(set(ps) - set(gs))
            rp[key][2] += len(set(gs) - set(ps))
            for s in set(gs) & set(ps):
                lvl_n += 1
                lvl_ok += gs[s] == ps[s]
            if set(gs) != set(ps):
                fails.append({"job": j["id"], "kind": key, "missing": sorted(set(gs) - set(ps)), "extra": sorted(set(ps) - set(gs))})
        # classification: skills in wrong bucket
    return {"required": prf(*rp["required"]), "preferred": prf(*rp["preferred"]),
            "level_accuracy": round(lvl_ok / lvl_n, 3) if lvl_n else 0, "n_jobs": len(engine._builtin_jobs)}, fails


def gold_status(gold_levels: dict[str, int], sid: str, req: int) -> str:
    lv = gold_levels.get(sid, 0)
    return "has" if lv >= req else "partial" if lv > 0 else "missing"


def pred_status(r: dict) -> str:
    if r["status"] in ("matched", "insufficient"):
        return "has"
    if r["status"] == "partial" and not r.get("via"):
        return "partial"
    return "missing"


def eval_matching(engine, cands: list[dict], weights: dict | None = None, use_text: bool = True) -> tuple[dict, list[dict]]:
    tax = engine.tax
    matcher = Matcher(tax, engine.embedder, weights or MATCH_WEIGHTS)
    profiles = getattr(engine, "_eval_profiles", None) or {}
    conf = {"has": {"has": 0, "partial": 0, "missing": 0}, "partial": {"has": 0, "partial": 0, "missing": 0}, "missing": {"has": 0, "partial": 0, "missing": 0}}
    gap_tp = gap_fp = gap_fn = 0
    suit = [0, 0, 0]
    top3_hit = top3_n = 0
    fails = []
    for c in cands:
        gold_levels = {tax.id_from_name(n): l for n, l in c["gold"].items()}
        prof = profiles.get(c["id"]) if use_text else gold_profile(c, tax)
        if prof is None:
            prof, _ = parse_profile(c["text"], tax, None)
        results = matcher.match_all(prof, engine._builtin_jobs)
        for r in results:
            for q in r["requirements"]:
                if q["importance"] != "required":
                    continue
                g = gold_status(gold_levels, q["skill_id"], q["req_level"])
                p = pred_status(q)
                conf[g][p] += 1
                gap_g, gap_p = g != "has", p != "has"
                gap_tp += gap_g and gap_p
                gap_fp += (not gap_g) and gap_p
                gap_fn += gap_g and not gap_p
            job = engine.job(r["job_id"])
            reqs = job["required"]
            gcov = sum(gold_levels.get(x["skill"], 0) >= x["level"] for x in reqs) / len(reqs) if reqs else 0
            gsuit = gcov >= 0.75
            suit[0] += gsuit and r["suitable"]
            suit[1] += (not gsuit) and r["suitable"]
            suit[2] += gsuit and not r["suitable"]
        if c["target"]:
            top3 = results[:3]
            top3_n += 1
            top3_hit += any(t["domain"] in c["target"] for t in top3)
            if not any(t["domain"] in c["target"] for t in top3):
                fails.append({"case": c["id"], "kind": "ranking", "wanted": c["target"], "top3": [t["title"] for t in top3]})
    total = sum(sum(v.values()) for v in conf.values())
    correct = sum(conf[k][k] for k in conf)
    return {"status_accuracy": round(correct / total, 3), "n_requirement_pairs": total, "confusion": conf,
            "gap_detection": prf(gap_tp, gap_fp, gap_fn), "suitable_roles": prf(*suit),
            "top3_relevance": round(top3_hit / top3_n, 3) if top3_n else 0, "n_ranked_candidates": top3_n}, fails


def run_all(engine) -> dict:
    cands = _load("candidates.json")
    ext, f1 = eval_extraction(engine, cands)
    norm, f2 = eval_normalization(engine)
    jp, f3 = eval_job_parsing(engine)
    mt, f4 = eval_matching(engine, cands)
    oracle, _ = eval_matching(engine, cands, use_text=False)
    report = {"embedder": engine.embedder.name, "n_candidates": len(cands), "n_jobs": len(engine._builtin_jobs), "extraction": ext,
              "normalization": norm, "job_parsing": jp, "matching": mt, "matching_with_gold_profiles": oracle,
              "weights": MATCH_WEIGHTS, "failures": {"extraction": f1[:40], "normalization": f2[:20], "job_parsing": f3[:10], "matching": f4[:10]}}
    return report


def tune_weights(engine, iters: int = 120, seed: int = 7) -> dict:
    """Random search over the weight simplex maximising suitable-role F1 (+ status accuracy) on the gold labels."""
    cands = _load("candidates.json")
    eval_extraction(engine, cands)
    rng = random.Random(seed)
    keys = list(MATCH_WEIGHTS)
    best, best_score = dict(MATCH_WEIGHTS), -1.0
    for i in range(iters + 1):
        w = dict(MATCH_WEIGHTS) if i == 0 else {k: rng.uniform(0.02, 0.5) for k in keys}
        s = sum(w.values())
        w = {k: v / s for k, v in w.items()}
        m, _ = eval_matching(engine, cands, w)
        score = m["suitable_roles"]["f1"] + 0.5 * m["top3_relevance"]
        if score > best_score:
            best, best_score = w, score
    return {"weights": {k: round(v, 3) for k, v in best.items()}, "objective": round(best_score, 3)}


def main() -> None:
    from .engine import Engine

    engine = Engine(db_path=":memory:" if False else Path("/tmp/skill2job_eval.db"))
    if "--tune" in sys.argv:
        print(json.dumps(tune_weights(engine), indent=2))
        return
    rep = run_all(engine)
    (EVAL_DIR / "report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    e, n, j, m = rep["extraction"], rep["normalization"], rep["job_parsing"], rep["matching"]
    print(f"Embedder: {rep['embedder']}")
    print(f"Skill extraction  P={e['skills']['precision']} R={e['skills']['recall']} F1={e['skills']['f1']}   negation F1={e['negation']['f1']}")
    print(f"Proficiency       exact={e['level_exact']} within±1={e['level_within_1']}  (n={e['n_level_pairs']})")
    print(f"Normalization     accuracy={n['accuracy']} (n={n['n']})")
    print(f"Job parsing       required F1={j['required']['f1']} preferred F1={j['preferred']['f1']} level acc={j['level_accuracy']}")
    print(f"Matching          status acc={m['status_accuracy']} gap F1={m['gap_detection']['f1']} suitable F1={m['suitable_roles']['f1']} top-3 relevance={m['top3_relevance']}")
    print("Saved data/eval/report.json")


if __name__ == "__main__":
    main()
