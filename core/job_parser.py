"""Job Parsing Agent: free-text job description -> structured requirements.

Separates REQUIRED from PREFERRED skills, estimates the level each skill is needed at, and extracts the
experience range and accepted degrees – so a job description's words are not all weighted equally.
Rule-based by default (deterministic, evaluated in core/evaluation.py); Gemini can be used for messy JDs.
"""
from __future__ import annotations

import json
import re

from .config import DATA_DIR
from .llm import LLM
from .profile_parser import DEGREES

HEADERS = [
    ("required", re.compile(r"^\W*(must[- ]have|requirements?|what you(?:'|’)?ll need|what you bring|required skills|key skills|qualifications|you should have|essential(?: skills)?)\s*[:\-–]\s*(.*)$", re.I)),
    ("preferred", re.compile(r"^\W*(nice[- ]to[- ]have|good[- ]to[- ]have|bonus(?: points)?|preferred(?: skills)?|plus points|desirable|added advantage)\s*[:\-–]\s*(.*)$", re.I)),
    ("ignore", re.compile(r"^\W*(about the role|about us|about|responsibilities|what you(?:'|’)?ll do|benefits|perks|overview)\s*[.:\-–]\s*(.*)$", re.I)),
]
PREF_CUE = re.compile(r"\b(a plus|is a plus|nice to have|good to have|bonus|preferred|advantage|desirable|nice-to-have)\b", re.I)
REQ_CUE = re.compile(r"\b(you should have|you bring|must have|is required|are required|required|you will need|you(?:'|’)ll need)\b", re.I)
LEVEL_CUES = [
    (3, re.compile(r"\b(strong|deep|advanced|expert\w*|proficien\w+|extensive|in-depth|command of)\b", re.I)),
    (2, re.compile(r"\b(working knowledge|hands-on|practical experience|comfort\w*|experience (?:with|in)|good (?:knowledge|understanding)|solid understanding)\b", re.I)),
    (1, re.compile(r"\b(basic|familiar\w*|exposure|awareness|introductory|elementary)\b", re.I)),
]
BULLET = re.compile(r"^\s*(?:[-*•▪●]|\d+[.)])\s+")


def _level_for(sentence: str, pos: int, default: int, spans: list[tuple[int, int]] = ()) -> int:
    best_pos, best = -1, default
    for lvl, rx in LEVEL_CUES:
        for m in rx.finditer(sentence):
            if any(a <= m.start() < b for a, b in spans):   # cue word is part of a skill name ("Deep Learning")
                continue
            if m.start() < pos and m.start() > best_pos:
                best_pos, best = m.start(), lvl
    return best


def parse_experience(text: str) -> dict:
    m = re.search(r"(\d+)\s*(?:-|–|to)\s*(\d+)\s*\+?\s*years?", text, re.I)
    if m:
        return {"min": int(m.group(1)), "max": int(m.group(2))}
    m = re.search(r"(\d+)\s*\+\s*years?", text, re.I)
    if m:
        return {"min": int(m.group(1)), "max": int(m.group(1)) + 2}
    if re.search(r"\bfreshers?\b|entry[- ]level|no experience", text, re.I):
        return {"min": 0, "max": 1}
    return {"min": 0, "max": 2}


def parse_degrees(text: str) -> list[str]:
    seg = re.search(r"(?:eligibility|education|qualification)s?\s*:\s*(.+)", text, re.I)
    scope = seg.group(1) if seg else text
    found = [name for pat, name in DEGREES if re.search(pat, scope)]
    return found or ["B.Tech", "B.E."]


def parse_rules(text: str, taxonomy) -> dict:
    required: dict[str, int] = {}
    preferred: dict[str, int] = {}
    section: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        content = BULLET.sub("", line)
        for kind, rx in HEADERS:
            m = rx.match(content)
            if m:
                section, content = kind, m.group(2).strip()
                break
        if not content or section == "ignore":
            continue
        for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z])", content):
            if not sent.strip():
                continue
            pref = bool(PREF_CUE.search(sent))
            if pref:
                bucket, default = preferred, 1
            elif section == "required":
                bucket, default = required, 2
            elif section == "preferred":
                bucket, default = preferred, 1
            elif REQ_CUE.search(sent):
                bucket, default = required, 2
            else:
                continue
            mentions = taxonomy.extract(sent)
            spans = [(m.start, m.end) for m in mentions]
            for m in mentions:
                lvl = _level_for(sent, m.start, default, spans)
                if m.skill_id in required and bucket is preferred:
                    continue
                bucket[m.skill_id] = max(bucket.get(m.skill_id, 0), lvl)
                if bucket is required:
                    preferred.pop(m.skill_id, None)
    return {"required": [{"skill": s, "level": l} for s, l in required.items()],
            "preferred": [{"skill": s, "level": l} for s, l in preferred.items()],
            "experience": parse_experience(text), "degrees": parse_degrees(text)}


LLM_PROMPT = """Parse this job description. Return JSON:
{{"required": [{{"skill": str, "level": "basic|intermediate|strong"}}], "preferred": [{{"skill": str, "level": "basic|intermediate|strong"}}],
"experience_min": int, "experience_max": int, "degrees": [str]}}
Required = must-have; preferred = nice-to-have / plus / bonus. Only technical skills. Do not include skills that merely describe the company.

JOB DESCRIPTION:
{text}"""


def parse_llm(text: str, taxonomy, llm: LLM) -> dict | None:
    data = llm.generate_json(LLM_PROMPT.format(text=text[:8000]))
    if not isinstance(data, dict):
        return None
    lv = {"basic": 1, "intermediate": 2, "strong": 3}
    out = {"required": [], "preferred": [], "experience": {"min": int(data.get("experience_min") or 0), "max": int(data.get("experience_max") or 2)},
           "degrees": [str(d) for d in data.get("degrees") or []] or ["B.Tech", "B.E."]}
    for key in ("required", "preferred"):
        seen = set()
        for it in data.get(key) or []:
            r = taxonomy.normalize(str(it.get("skill", "")))
            if r.ok and r.skill_id not in seen:
                seen.add(r.skill_id)
                out[key].append({"skill": r.skill_id, "level": lv.get(str(it.get("level", "")).lower(), 2)})
    return out if out["required"] or out["preferred"] else None


def parse_job_text(text: str, taxonomy, llm: LLM | None = None, use_llm: bool = False) -> dict:
    if use_llm and llm and llm.available:
        res = parse_llm(text, taxonomy, llm)
        if res:
            res["engine"] = "gemini"
            return res
    res = parse_rules(text, taxonomy)
    res["engine"] = "rules"
    return res


def load_jobs(taxonomy, custom: list[dict] | None = None) -> list[dict]:
    """Load the curated postings and run every description through the Job Parsing Agent."""
    raw = json.loads((DATA_DIR / "jobs.json").read_text(encoding="utf-8"))
    jobs = []
    for j in raw + (custom or []):
        parsed = j["parsed"] if "parsed" in j else parse_job_text(j["description"], taxonomy)
        jobs.append({**{k: v for k, v in j.items() if k != "parsed"}, **parsed})
    return jobs
