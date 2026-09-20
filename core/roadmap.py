"""Roadmap Agent: turns an ordered skill plan into a personalised day-by-day schedule.

Each skill becomes: learn days (modules from the curated learning path) -> project day -> assessment day
(quiz + practical). Skill prerequisites are always scheduled first. Day count scales with the candidate's
daily study time and their current level/transferable experience.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from urllib.parse import quote_plus

from .config import BASELINE_HOURS_PER_DAY
from .curriculum import path_for
from .gap import learning_effort, real_have

KIND_LABEL = {"learn": "Learn", "practice": "Practice", "project": "Mini project", "assessment": "Assessment",
              "revision": "Revision", "retake": "Reassessment"}


def days_for_skill(profile: dict, taxonomy, sid: str, hours_per_day: float) -> int:
    eff = learning_effort(profile, taxonomy, sid)["skill_days"]
    n = math.ceil(eff * BASELINE_HOURS_PER_DAY / max(0.5, hours_per_day))
    n_mods = len(path_for(sid)["modules"]) or 2
    return max(3, 2 + math.ceil(n_mods / 2), min(21, n))


def _topic_video(res: dict | None, skill: str, topic: str) -> dict | None:
    """Turn a creator's general video into a topic-specific search so every day has a fitting video."""
    if not res:
        return None
    creator = res.get("creator") or ""
    q = f"{creator} {skill} {topic}".strip()
    from .resources import live_youtube

    live = live_youtube(q)
    if live:
        return {**res, "title": live[0], "url": live[1], "link_kind": "direct", "duration_min": 40}
    return {**res, "title": f"{creator}: {skill} — {topic}" if creator else f"{skill} — {topic}",
            "url": "https://www.youtube.com/results?search_query=" + quote_plus(q), "link_kind": "search", "duration_min": 40}


def _slots(n_modules: int, learn_days: int) -> list[list[int]]:
    """Distribute module indices over learn days (modules may share a day, or span several days)."""
    slots = []
    for s in range(learn_days):
        lo, hi = s * n_modules // learn_days, (s + 1) * n_modules // learn_days
        idx = list(range(lo, hi)) or [min(n_modules - 1, s * n_modules // learn_days)]
        slots.append(idx)
    return slots


def next_dates(start: date, n: int, skip_weekends: bool) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if not (skip_weekends and d.weekday() >= 5):
            out.append(d)
        d += timedelta(days=1)
    return out


def build_days_for_skill(profile: dict, taxonomy, recommender, sid: str, hours_per_day: float, needed_for: str | None = None) -> list[dict]:
    name = taxonomy.name(sid)
    path = path_for(sid)
    mods = path["modules"] or [{"title": f"{name} fundamentals", "terms": [], "practice": f"Build a tiny {name} example"}]
    level = profile["skills"].get(sid, {}).get("level", 0) if not profile["skills"].get(sid, {}).get("negated") else 0
    n_days = days_for_skill(profile, taxonomy, sid, hours_per_day)
    minutes = int(hours_per_day * 60)
    used: set[str] = set()
    days: list[dict] = []
    learn_days = n_days - 2 if n_days >= 4 else 1
    slots = _slots(len(mods), learn_days)
    prev_first = None
    for s, idx in enumerate(slots):
        ms = [mods[i] for i in idx]
        repeat = idx[0] == prev_first
        prev_first = idx[0]
        topic = " + ".join(m["title"] for m in ms)
        terms = [t for m in ms for t in m["terms"]]
        watch = _topic_video(recommender.pick(sid, level, "watch", topic, int(minutes * 0.5), used) or
                             recommender.pick(sid, level, "watch", topic, int(minutes * 0.5)), name, topic)
        read = recommender.pick(sid, level, "read", topic, int(minutes * 0.3))
        if read:
            read = {**read, "title": f"{read['title']} — focus: {ms[0]['title']}"}
        if watch:
            used.add(watch["id"])
        kind = "practice" if repeat else "learn"
        practice = [m["practice"] for m in ms]
        checklist = ([f"Watch: {watch['title']}"] if watch else []) + ([f"Read: {read['title']}"] if read else []) + \
                    [f"Practice: {p}" for p in practice] + ["Take the 3-question check-in"]
        days.append({"skill_id": sid, "skill": name, "kind": kind, "title": f"{name} — {topic}" if not repeat else f"{name} — practise: {topic}",
                     "modules": [m["title"] for m in ms], "learn": [f"{t['term']}: {t['definition']}" for t in terms],
                     "watch": watch, "read": read, "practice": practice, "checklist": checklist,
                     "quiz": {"n": 3, "topics": [m["title"] for m in ms], "type": "mini"},
                     "est_minutes": minutes, "needed_for": needed_for,
                     "why": f"Builds {name} step by step from {'scratch' if not level else 'your current level'}."})
    if n_days >= 3:
        proj = recommender.pick(sid, max(level, 2), "project", path.get("project", ""), minutes, used)
        days.append({"skill_id": sid, "skill": name, "kind": "project", "title": f"{name} — mini project",
                     "modules": [], "learn": [], "watch": None, "read": proj, "practice": [path.get("project") or f"Build a small {name} project"],
                     "checklist": [f"Build: {path.get('project') or f'a small {name} project'}", "Push it to a public GitHub repository with a README"],
                     "quiz": None, "est_minutes": int(minutes * 1.3), "needed_for": needed_for,
                     "project": path.get("project", ""), "check_files": path.get("check_files", []), "check_keywords": path.get("check_keywords", []),
                     "why": "A portfolio-ready project is also the practical proof for verification."})
    all_topics = [m["title"] for m in mods]
    days.append({"skill_id": sid, "skill": name, "kind": "assessment", "title": f"{name} — assessment & verification",
                 "modules": [], "learn": [], "watch": None, "read": None, "practice": [],
                 "checklist": ["Take the 5-question quiz (need 70%)", "Submit your practical task (repo link or write-up)"],
                 "quiz": {"n": 5, "topics": all_topics, "type": "final"}, "est_minutes": min(minutes, 75), "needed_for": needed_for,
                 "project": path.get("project", ""), "check_files": path.get("check_files", []), "check_keywords": path.get("check_keywords", []),
                 "why": "Verification: quiz + practical evidence turn 'I studied it' into 'I can show it'."})
    return days


def build_roadmap(profile: dict, skill_ids: list[str], taxonomy, recommender, hours_per_day: float = 1.5,
                  start: date | None = None, skip_weekends: bool = False) -> list[dict]:
    start = start or date.today()
    ordered = taxonomy.order_with_prereqs(skill_ids, have={s for s in real_have(profile) if profile["skills"][s]["level"] >= 2})
    days: list[dict] = []
    for item in ordered:
        days += build_days_for_skill(profile, taxonomy, recommender, item["skill"], hours_per_day,
                                     needed_for=taxonomy.name(item["needed_for"]) if item["needed_for"] else None)
    dates = next_dates(start, len(days), skip_weekends)
    for n, (d, dt) in enumerate(zip(days, dates), 1):
        d["planned_date"] = dt.isoformat()
        d["seq"] = n
    return days


def revision_days(day_row: dict, weak_topics: list[str], taxonomy, recommender, profile: dict, severity: str, base_date: date) -> list[dict]:
    """Extra days inserted after a weak assessment: revision (+ extra practice) and reassessment."""
    sid = day_row["skill_id"]
    name = taxonomy.name(sid)
    level = profile["skills"].get(sid, {}).get("level", 1)
    topics = weak_topics or day_row["plan"].get("modules") or [m["title"] for m in path_for(sid)["modules"]][:2]
    path = path_for(sid)
    minutes = day_row["plan"].get("est_minutes", 90)
    out = []
    watch = recommender.pick(sid, max(1, level - 1), "watch", " ".join(topics), int(minutes * 0.5))
    read = recommender.pick(sid, level, "read", " ".join(topics), int(minutes * 0.3))
    prac = [m["practice"] for m in path["modules"] if m["title"] in topics] or [f"Re-do the exercises for {topics[0]}"]
    terms = [f"{t['term']}: {t['definition']}" for m in path["modules"] if m["title"] in topics for t in m["terms"]]
    out.append({"skill_id": sid, "skill": name, "kind": "revision", "title": f"{name} — revision: {', '.join(topics[:2])}",
                "modules": topics, "learn": terms, "watch": watch, "read": read, "practice": prac,
                "checklist": ["Re-read the weak topics", *[f"Practice: {p}" for p in prac], "Take the 3-question check-in"],
                "quiz": {"n": 3, "topics": topics, "type": "mini"}, "est_minutes": minutes, "needed_for": None,
                "why": f"Your last quiz showed gaps in: {', '.join(topics)}."})
    if severity == "revise":
        dates = next_dates(base_date, len(out), False)
        for d, dt in zip(out, dates):
            d["planned_date"] = dt.isoformat()
        return out
    if severity == "retake":
        out.append({"skill_id": sid, "skill": name, "kind": "practice", "title": f"{name} — extra practice",
                    "modules": topics, "learn": [], "watch": None, "read": None, "practice": prac + [f"Explain each of these topics aloud in your own words: {', '.join(topics)}"],
                    "checklist": [f"Practice: {p}" for p in prac], "quiz": {"n": 3, "topics": topics, "type": "mini"}, "est_minutes": minutes,
                    "needed_for": None, "why": "A score under 50% means the ideas need more hands-on repetition before re-testing."})
    out.append({"skill_id": sid, "skill": name, "kind": "retake", "title": f"{name} — reassessment",
                "modules": [], "learn": [], "watch": None, "read": None, "practice": [],
                "checklist": ["Retake the quiz on your weak topics (need 70%)"],
                "quiz": {"n": 5, "topics": topics, "type": "final"}, "est_minutes": 45, "needed_for": None,
                "project": path.get("project", ""), "check_files": path.get("check_files", []), "check_keywords": path.get("check_keywords", []),
                "why": "Reassessment before moving on – the roadmap only advances when you can show the skill."})
    dates = next_dates(base_date, len(out), False)
    for d, dt in zip(out, dates):
        d["planned_date"] = dt.isoformat()
    return out
