"""Engine: wires every component together and owns the stateful learning loop.

    analyze -> match -> gaps -> ROI -> roadmap -> learn -> quiz/practical -> verify -> update profile -> re-match
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timedelta

from . import notifications as notif
from .config import (PRACTICAL_PASS, QUIZ_PASS, REVISION_THRESHOLD, RETAKE_THRESHOLD)
from .curriculum import path_for
from .db import Database
from .embeddings import get_embedder
from .gap import analyze_gaps, gap_summary, real_have, skill_demand
from .job_parser import load_jobs, parse_job_text
from .llm import LLM
from .matcher import Matcher, explain_match
from .profile import finalize, mark_verified
from .profile_parser import parse_profile
from .quiz import generate_quiz, grade_quiz
from .rag.kb import KnowledgeBase
from .resources import ResourceRecommender
from .roadmap import build_roadmap, next_dates, revision_days
from .roi import plan_learning_order, explain_priority
from .taxonomy import Taxonomy
from .verify import grade_practical

log = logging.getLogger(__name__)
DEFAULT_UID = "default"


class Engine:
    def __init__(self, db_path=None, llm: LLM | None = None):
        self.llm = llm or LLM()
        self.embedder = get_embedder()
        self.tax = Taxonomy()
        self.tax.attach_embedder(self.embedder)
        self.db = Database(db_path)
        self._builtin_jobs = load_jobs(self.tax)
        self.reload_jobs()
        self.kb = KnowledgeBase(self.tax, self.embedder, self.jobs, self.llm)
        self.matcher = Matcher(self.tax, self.embedder)
        self.recommender = ResourceRecommender(self.kb, self.tax)
        self._match_cache: dict[str, list[dict]] = {}

    # ------------------------------------------------------------------ jobs
    def reload_jobs(self) -> None:
        self.custom_jobs = self.db.list_custom_jobs()
        self.jobs = self._builtin_jobs + self.custom_jobs
        self.db.seed_static(self.tax, self.jobs)
        self._match_cache = {}

    def add_custom_job(self, title: str, company: str, city: str, mode: str, description: str, domain: str = "Software Engineering",
                       use_llm: bool = False) -> dict:
        parsed = parse_job_text(description, self.tax, self.llm, use_llm)
        jid = f"C{len(self.custom_jobs) + 1:02d}"
        job = {"id": jid, "title": title, "company": company or "Custom", "city": city, "mode": mode, "domain": domain, "salary_lpa": None,
               "description": description, "custom": True, **parsed}
        self.db.add_custom_job(job)
        self.reload_jobs()
        return job

    def job(self, job_id: str) -> dict | None:
        return next((j for j in self.jobs if j["id"] == job_id), None)

    # ------------------------------------------------------------------ profile + matching
    def get_profile(self, uid: str = DEFAULT_UID) -> dict | None:
        return self.db.load_profile(uid)

    def save_profile(self, profile: dict) -> None:
        self.db.save_profile(profile)
        self._match_cache = {}

    def _sig(self, profile: dict) -> str:
        core = {k: profile.get(k) for k in ("degree", "branch", "year", "location", "interests", "experience_years")}
        core["n_proj"] = len(profile.get("projects", []))
        core["skills"] = sorted((s, v["level"], v.get("negated", False), v.get("inferred", False), tuple(e["type"] for e in v["evidence"]))
                                for s, v in profile["skills"].items())
        return hashlib.md5(json.dumps(core, default=str).encode()).hexdigest() + str(len(self.jobs))

    def matches(self, profile: dict) -> list[dict]:
        key = self._sig(profile)
        if key not in self._match_cache:
            self._match_cache[key] = self.matcher.match_all(profile, self.jobs)
        return self._match_cache[key]

    def explain(self, result: dict) -> dict:
        ex = explain_match(result, self.tax)
        if self.llm.available:
            polished = self.llm.generate(
                "Rewrite this job-match explanation for a student in 3 friendly sentences. Use ONLY these facts, add none.\n"
                f"Facts: {json.dumps({k: ex[k] for k in ('headline', 'strengths', 'gaps')})}", temperature=0.4)
            if polished:
                ex["narrative"] = polished
        return ex

    def gaps(self, profile: dict, job_id: str) -> list[dict]:
        res = next(r for r in self.matches(profile) if r["job_id"] == job_id)
        return analyze_gaps(profile, res, self.jobs, self.tax)

    def roi(self, profile: dict, k: int = 5) -> dict:
        plan = plan_learning_order(profile, self.jobs, self.matcher, self.tax, k=k)
        plan["demand_total"] = len(self.jobs)
        for i, it in enumerate(plan["ranking"][:8]):
            it["explanation"] = explain_priority(it, plan["ranking"][i + 1:], len(self.jobs))
        return plan

    def snapshot(self, uid: str, label: str, profile: dict | None = None) -> dict:
        profile = profile or self.get_profile(uid)
        res = self.matches(profile)
        suitable = [r for r in res if r["suitable"]]
        top = res[0] if res else None
        detail = {"suitable_ids": [r["job_id"] for r in suitable], "close_count": sum(1 for r in res if r["score"] >= 65)}
        self.db.add_snapshot(uid, label, top["job_id"] if top else "", top["score"] if top else 0, len(suitable),
                             round(sum(r["score"] for r in res[:5]) / max(1, len(res[:5])), 1), detail)
        return {"suitable": len(suitable), "top": top}

    def target_job(self, profile: dict, results: list[dict] | None = None) -> dict | None:
        results = results or self.matches(profile)
        tid = profile.get("target_job_id")
        return next((r for r in results if r["job_id"] == tid), results[0] if results else None)

    # ------------------------------------------------------------------ full pipeline (LangGraph)
    def run_pipeline(self, text: str, uid: str = DEFAULT_UID, overrides: dict | None = None, hours: float = 1.5, k: int = 4,
                     start: date | None = None, extra_docs: list | None = None) -> dict:
        from .graph import run_pipeline

        return run_pipeline(self, text, uid, overrides or {}, hours, k, start or date.today())

    # ------------------------------------------------------------------ roadmap
    def create_roadmap(self, uid: str, skill_ids: list[str], hours: float, start: date | None = None, skip_weekends: bool = False) -> list[dict]:
        profile = self.get_profile(uid)
        profile["hours_per_day"] = hours
        self.save_profile(profile)
        days = build_roadmap(profile, skill_ids, self.tax, self.recommender, hours, start, skip_weekends)
        self.db.replace_roadmap(uid, days)
        self.db.add_progress(uid, None, "roadmap_created", detail={"skills": skill_ids, "days": len(days)})
        return self.db.get_roadmap(uid)

    def roadmap(self, uid: str = DEFAULT_UID) -> list[dict]:
        return self.db.get_roadmap(uid)

    def current_day(self, uid: str = DEFAULT_UID) -> dict | None:
        return next((d for d in self.roadmap(uid) if d["status"] == "pending"), None)

    def reschedule(self, uid: str = DEFAULT_UID, start: date | None = None) -> int:
        """Shift every pending day forward so that the first one is today (used after missed days)."""
        pend = [d for d in self.roadmap(uid) if d["status"] == "pending"]
        dates = next_dates(start or date.today(), len(pend), False)
        self.db.set_dates(uid, {d["id"]: dt.isoformat() for d, dt in zip(pend, dates)})
        self.db.add_progress(uid, None, "rescheduled", detail={"days": len(pend)})
        return len(pend)

    # ------------------------------------------------------------------ learning loop
    def day_quiz(self, day: dict, seed: int | None = None) -> list[dict]:
        spec = day["plan"].get("quiz") or {"n": 3, "topics": [], "type": "mini"}
        focus = spec["topics"] if spec["type"] == "mini" or day["kind"] == "retake" else None
        return generate_quiz(day["skill_id"], self.tax, self.kb, self.llm, spec["n"], focus, seed)

    def mark_task(self, day: dict, index: int, done: bool) -> dict:
        state = day["task_state"]
        state[str(index)] = done
        self.db.update_day(day["id"], task_state=state)
        return state

    def complete_day(self, uid: str, day: dict, method: str = "self") -> None:
        self.db.update_day(day["id"], status="done")
        self.db.add_progress(uid, day["id"], "day_done", detail={"method": method, "skill": day["skill_id"]})
        fresh = self.roadmap(uid)
        me = next((d for d in fresh if d["id"] == day["id"]), day)
        nxt = next((d for d in fresh if d["status"] == "pending"), None)
        notif.completed(self.db, uid, me, nxt)

    def submit_quiz(self, uid: str, day: dict, quiz: list[dict], answers: dict[str, int]) -> dict:
        """Grade a quiz, record it, and ADAPT the roadmap (continue / revise / retake) - the roadmap is not fixed."""
        g = grade_quiz(quiz, answers)
        spec = day["plan"].get("quiz") or {}
        final = spec.get("type") == "final"
        sid = day["skill_id"]
        name = self.tax.name(sid)
        pct = g["pct"]
        self.db.add_progress(uid, day["id"], "quiz", g["score"], g["total"], {"skill": sid, "type": spec.get("type"), "weak": g["weak_topics"]})
        profile = self.get_profile(uid)
        inserted, decision, message = 0, "continue", ""
        base = date.fromisoformat(day["planned_date"]) + timedelta(days=1)
        if final:
            if pct >= QUIZ_PASS:
                self.db.update_day(day["id"], status="done", quiz_score=pct)
                self.db.add_verification(uid, sid, "quiz", pct * 100, True, {"weak": g["weak_topics"]})
                mark_verified(profile, sid, "quiz", f"Passed the {name} verification quiz ({g['score']}/{g['total']})")
                finalize(profile, self.tax)
                self.save_profile(profile)
                message = f"{name} quiz passed ({g['score']}/{g['total']}). Add the practical task to earn full verification."
                self._after_profile_change(uid, f"{name} quiz-verified", name)
            else:
                self.db.add_verification(uid, sid, "quiz", pct * 100, False, {"weak": g["weak_topics"]})
                self.db.update_day(day["id"], status="retry", quiz_score=pct)
                sev = "retake" if pct < RETAKE_THRESHOLD else "revise_retest"
                extra = revision_days(day, g["weak_topics"], self.tax, self.recommender, profile, sev, base)
                self.db.insert_days_after(uid, day["seq"], extra)
                inserted, decision = len(extra), "retake"
                message = f"Score {g['score']}/{g['total']} – below the 70% bar. I added {inserted} day(s): revision" + \
                          (", extra practice" if sev == "retake" else "") + " and a reassessment."
        else:
            if pct >= REVISION_THRESHOLD:
                self.db.update_day(day["id"], status="done", quiz_score=pct)
                message = f"Great – {g['score']}/{g['total']}. Continuing to the next day."
            else:
                self.db.update_day(day["id"], status="done", quiz_score=pct)
                sev = "retake" if pct < RETAKE_THRESHOLD else "revise"
                extra = revision_days(day, g["weak_topics"], self.tax, self.recommender, profile, sev, base)
                self.db.insert_days_after(uid, day["seq"], extra)
                inserted, decision = len(extra), "revise" if sev == "revise" else "retake"
                message = (f"Score {g['score']}/{g['total']}. I inserted a revision day on: {', '.join(g['weak_topics'])}."
                           if sev == "revise" else
                           f"Score {g['score']}/{g['total']}. I inserted {inserted} days: revision, extra practice and a reassessment before you move on.")
        fresh = self.roadmap(uid)
        me = next((d for d in fresh if d["id"] == day["id"]), day)
        nxt = next((d for d in fresh if d["status"] == "pending"), None)
        notif.completed(self.db, uid, me, nxt, message)
        return {"grade": g, "decision": decision, "inserted": inserted, "message": message, "final": final}

    def submit_practical(self, uid: str, day: dict, repo_url: str, explanation: str, code: str = "") -> dict:
        sid = day["skill_id"]
        name = self.tax.name(sid)
        res = grade_practical(sid, self.tax, self.embedder, self.llm, repo_url, explanation, code)
        self.db.add_verification(uid, sid, "practical", res["score"], res["passed"], res)
        self.db.add_progress(uid, day["id"], "practical", res["score"], 100, {"skill": sid, "passed": res["passed"]})
        if res["passed"]:
            profile = self.get_profile(uid)
            mark_verified(profile, sid, "practical", f"Practical task verified for {name} (score {res['score']:.0f}/100)")
            finalize(profile, self.tax)
            self.save_profile(profile)
            notif.verified(self.db, uid, name, "practically")
            self._after_profile_change(uid, f"{name} verified", name)
            if day["kind"] == "project":
                self.db.update_day(day["id"], status="done")
        return res

    def _after_profile_change(self, uid: str, label: str, skill_name: str) -> dict:
        """Re-run job matching after the profile changed and announce newly unlocked jobs."""
        prev = self.db.list_snapshots(uid)
        before = prev[-1]["suitable_count"] if prev else 0
        snap = self.snapshot(uid, label)
        notif.unlocked(self.db, uid, before, snap["suitable"], skill_name)
        return {"before": before, "after": snap["suitable"], "top": snap["top"]}

    # ------------------------------------------------------------------ analytics
    def skill_progress(self, uid: str = DEFAULT_UID) -> list[dict]:
        rm = self.roadmap(uid)
        profile = self.get_profile(uid) or {"skills": {}}
        out: dict[str, dict] = {}
        for d in rm:
            o = out.setdefault(d["skill_id"], {"skill_id": d["skill_id"], "name": self.tax.name(d["skill_id"]), "done": 0, "total": 0})
            if d["kind"] in ("learn", "practice", "project", "assessment"):
                o["total"] += 1
                o["done"] += d["status"] in ("done", "retry")
        res = []
        for sid, o in out.items():
            ver = profile["skills"].get(sid, {}).get("verified", 0)
            o["pct"] = round(100 * o["done"] / max(1, o["total"]))
            o["verified"] = ver
            if ver >= 2:
                o["pct"] = 100
            elif ver == 1:
                o["pct"] = max(o["pct"], 85) if o["done"] == o["total"] else o["pct"]
            res.append(o)
        return res

    def streak(self, uid: str = DEFAULT_UID) -> int:
        days = {p["created_at"][:10] for p in self.db.list_progress(uid) if p["event"] in ("day_done", "quiz", "practical")}
        n, d = 0, date.today()
        if d.isoformat() not in days:
            d -= timedelta(days=1)
        while d.isoformat() in days:
            n += 1
            d -= timedelta(days=1)
        return n

    def notify_tick(self, uid: str = DEFAULT_UID, force: str | None = None, now: datetime | None = None) -> list[str]:
        return notif.tick(self.db, uid, self.roadmap(uid), now, force)

    def reset(self, uid: str = DEFAULT_UID) -> None:
        self.db.reset_user(uid)
        self._match_cache = {}
