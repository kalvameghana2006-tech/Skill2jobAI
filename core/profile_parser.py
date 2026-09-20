"""Profile Parsing Agent: unstructured text (resume / typed / voice transcript) -> structured profile.

Output per skill = canonical skill + proficiency + evidence + evidence type (not just keywords).
Two engines run together:
  * a deterministic, rule-based extractor (always available, tested in core/evaluation.py)
  * Gemini structured extraction (when an API key is present) – merged, LLM wins on level/evidence type.
"""
from __future__ import annotations

import re

from .llm import LLM
from .profile import add_evidence, detect_interests, finalize, new_profile

NUM_WORDS = {"one": 1, "a": 1, "single": 1, "two": 2, "couple": 2, "three": 3, "four": 4, "five": 5, "six": 6,
             "multiple": 3, "several": 3, "many": 4, "few": 3}

NEG = re.compile(
    r"\b(haven'?t|have not|hasn'?t|don'?t|do not|didn'?t|never|no (?:prior |hands-on |real )?(?:experience|exposure|knowledge)|"
    r"not (?:yet )?(?:familiar|worked|learned|learnt|comfortable|touched)|lack(?:ing)?|yet to (?:learn|use|explore)|"
    r"(?:want|wants|wish|would like|plan|planning|hope|looking|need|trying|aim)(?:s)? to (?:learn|study|pick up|explore|start)|"
    r"interested in learning|unfamiliar|without any|not know|can'?t|cannot|missing)\b", re.I)
CLAUSE_SPLIT = re.compile(
    r"[;]|\bbut\b|\bhowever\b|\bwhile\b|\balthough\b|\bthough\b|\bwhereas\b|"
    r"(?:,\s*)?\band\s+(?=(?:i|i've|i have|also|then|did|completed|took|know|knew|am|can|use|used|have|had|built|developed|worked|learned|learnt|studied|solved|created|done)\b)", re.I)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+|\s*[•▪●◦]\s*")

LEVEL_PATTERNS = [
    (4, re.compile(r"\b(expert|mastery|master(?:ed)?|guru)\b", re.I)),
    (3, re.compile(r"\b(advanced|strong(?:ly)?|proficient|very good|extensive(?:ly)?|experienced|excellent|deep|solid)\b", re.I)),
    (1, re.compile(r"\b(basic|beginner|familiar(?:ity)?|little|some|learning|new to|introductory|exposure|elementary|just started|starting)\b", re.I)),
    (2, re.compile(r"\b(pretty well|good|comfortable|intermediate|hands-on|decent|working knowledge|fairly|well)\b", re.I)),
]
EVIDENCE_PATTERNS = [
    ("internship", re.compile(r"\bintern(?:ship|ed)?\b|\btrainee\b", re.I)),
    ("production", re.compile(r"\b(worked (?:at|as|for)|work experience|professional(?:ly)?|employed|full[- ]time|freelanc\w+|in production|at my (?:company|job|work))\b", re.I)),
    ("major_project", re.compile(r"\b(capstone|final[- ]year project|major project|hackathon)\b", re.I)),
    ("project", re.compile(r"\b(built|build|developed|develop|created|implemented|designed|deployed|made|wrote|projects?|applications?|apps?|websites?|clone|system)\b", re.I)),
    ("github", re.compile(r"github\.com|\bon github\b|open[- ]source|pull requests?", re.I)),
    ("certification", re.compile(r"\bcertif\w+", re.I)),
    ("practice", re.compile(r"\b(solved|leetcode|hackerrank|codechef|codeforces|practi[sc]e[d]?|problems)\b", re.I)),
    ("coursework", re.compile(r"\b(course|coursework|learned|learnt|studied|tutorial|coursera|nptel|udemy|bootcamp|training|taught|semester|subject|syllabus|academic)\b", re.I)),
]
SECTION_RE = re.compile(r"^\s*(?:#+\s*)?(technical skills|skills|projects?|academic projects?|experience|work experience|internships?|education|certifications?|achievements|courses?|coursework|summary|objective|profile)\s*:?\s*$", re.I)
SECTION_DEFAULT = {"skills": "self_declared", "technical skills": "self_declared", "project": "project", "projects": "project",
                   "academic projects": "project", "academic project": "project", "experience": "internship", "work experience": "production",
                   "internship": "internship", "internships": "internship", "certification": "certification",
                   "certifications": "certification", "course": "coursework", "courses": "coursework", "coursework": "coursework",
                   "education": "coursework"}

DEGREES = [(r"(?i:\bb\.?\s?tech\b|bachelor of technology)", "B.Tech"), (r"\bB\.\s?E\b|\bBE\b|(?i:bachelor of engineering)", "B.E."),
           (r"(?i:\bbca\b)", "BCA"), (r"(?i:\bb\.?\s?sc\b|bachelor of science)", "B.Sc"), (r"(?i:\bmca\b)", "MCA"),
           (r"(?i:\bm\.?\s?tech\b|master of technology)", "M.Tech"), (r"(?i:\bm\.?\s?sc\b|master of science)", "M.Sc"),
           (r"(?i:\bdiploma\b)", "Diploma")]
BRANCHES = [(r"\bcse\b|computer science", "CSE"), (r"\bit\b(?! skills)|information technology", "IT"), (r"\bece\b|electronics", "ECE"),
            (r"\beee\b|electrical", "EEE"), (r"mechanical", "Mechanical"), (r"civil", "Civil"),
            (r"ai\s?&\s?ds|ai and ds|artificial intelligence and data science|data science branch|aiml|ai\s?&\s?ml", "AI&DS")]
CITIES = {"bengaluru": "Bengaluru", "bangalore": "Bengaluru", "hyderabad": "Hyderabad", "chennai": "Chennai", "pune": "Pune",
          "mumbai": "Mumbai", "delhi": "Delhi", "gurugram": "Gurugram", "gurgaon": "Gurugram", "noida": "Noida", "kolkata": "Kolkata",
          "coimbatore": "Coimbatore", "kochi": "Kochi", "vijayawada": "Vijayawada", "visakhapatnam": "Visakhapatnam", "vizag": "Visakhapatnam",
          "tirupati": "Tirupati", "anantapur": "Anantapur", "proddatur": "Proddatur", "kadapa": "Kadapa", "remote": "Remote"}
YEARS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "final": 4, "last": 4, "pre-final": 3, "prefinal": 3}


def _num(tok: str) -> int:
    tok = tok.lower()
    return int(tok) if tok.isdigit() else NUM_WORDS.get(tok, 1)


def parse_basics(text: str) -> dict:
    low = text.lower()
    out: dict = {}
    for pat, name in DEGREES:
        if re.search(pat, text):
            out["degree"] = name
            break
    for pat, name in BRANCHES:
        if re.search(pat, low):
            out["branch"] = name
            break
    m = re.search(r"\b(first|1st|second|2nd|third|3rd|fourth|4th|final|last|pre-?final)[\s-]*year", low)
    if m:
        out["year"] = YEARS.get(m.group(1).replace("prefinal", "pre-final"), 0)
    for key, city in CITIES.items():
        if re.search(rf"\b{key}\b", low):
            out["location"] = city
            break
    exp = 0.0
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:\+\s*)?(years?|yrs?|months?)\s*(?:of\s*)?(?:work\s*)?(?:experience|exp)", low)
    if m:
        v = float(m.group(1))
        exp = v / 12 if m.group(2).startswith("month") else v
    else:
        m = re.search(r"(\d+)\s*[- ]?months?\s*(?:of\s*)?(?:an?\s*)?intern", low)
        if m:
            exp = int(m.group(1)) / 12
        elif re.search(r"\bintern(?:ship|ed)?\b", low):
            exp = 0.25
    out["experience_years"] = round(exp, 2)
    out["interests"] = detect_interests(text)
    return out


def _cue_level(clause: str, pos: int, span_len: int, spans: list[tuple[int, int]] = ()) -> int | None:
    """Level cue closest to the mention (preferring cues before it); words inside skill names are ignored."""
    best, best_d = None, 10 ** 6
    for lvl, rx in LEVEL_PATTERNS:
        for m in rx.finditer(clause):
            if any(a <= m.start() < b for a, b in spans):
                continue
            d = pos - m.end() if m.end() <= pos else (m.start() - (pos + span_len)) + 30
            if d < best_d and d <= 60:
                best, best_d = lvl, d
    return best


def _evidence_type(clause: str, default: str | None = None) -> tuple[str, int]:
    etype = default or "self_declared"
    for name, rx in EVIDENCE_PATTERNS:
        if rx.search(clause):
            etype = name if (default is None or _rank(name) >= _rank(default)) else default
            break
    count = 1
    m = re.search(r"\b(\d+|one|two|three|four|five|six|multiple|several|many|couple of|few)\+?\s+(?:\w+\s+){0,3}?(projects?|applications?|apps?|websites?)", clause, re.I)
    if m:
        count = _num(m.group(1).split()[0])
    m = re.search(r"(\d+)\+?\s+(?:\w+\s+)?(?:problems|questions)", clause, re.I)
    if m and etype == "practice":
        count = int(m.group(1))
    return etype, count


def _rank(t: str) -> float:
    from .models import EVIDENCE_STRENGTH
    return EVIDENCE_STRENGTH.get(t, 0.25)


def heuristic_parse(text: str, taxonomy) -> dict:
    """Rule-based extraction: sections, negation, level cues, evidence types."""
    profile = new_profile()
    profile["raw_text"] = text
    section_default: str | None = None
    for raw_line in text.splitlines() or [text]:
        line = raw_line.strip()
        if not line:
            continue
        hm = SECTION_RE.match(line)
        if hm:
            section_default = SECTION_DEFAULT.get(hm.group(1).lower())
            continue
        inline = re.match(r"^(technical skills|skills|tools|technologies|languages|frameworks)\s*[:\-–]\s*(.+)$", line, re.I)
        if inline:
            for m in taxonomy.extract(inline.group(2)):
                add_evidence(profile, m.skill_id, f"Listed under skills: {m.alias}", "self_declared", surface=m.alias)
            continue
        for sent in [s for s in SENT_SPLIT.split(line) if s and len(s.strip()) > 2]:
            sent = sent.strip()
            for clause in CLAUSE_SPLIT.split(sent):
                mentions = taxonomy.extract(clause)
                if not mentions:
                    continue
                neg = NEG.search(clause)
                etype, count = _evidence_type(clause, section_default)
                spans = [(x.start, x.end) for x in mentions]
                for m in mentions:
                    ev_text = sent if len(sent) <= 220 else sent[:217] + "…"
                    if neg and m.start >= neg.start():
                        add_evidence(profile, m.skill_id, ev_text, "self_declared", negated=True, surface=m.alias)
                        continue
                    lvl = _cue_level(clause, m.start, m.end - m.start, spans)
                    if section_default == "self_declared" and etype == "self_declared":
                        pass
                    add_evidence(profile, m.skill_id, ev_text, etype, stated=lvl, count=count, surface=m.alias)
    basics = parse_basics(text)
    for k, v in basics.items():
        if v:
            profile[k] = v
    # projects / certifications sentences (for display and experience-fit)
    for sent in [s.strip() for s in SENT_SPLIT.split(text) if s.strip()]:
        if re.search(r"\b(built|developed|created|implemented|designed)\b", sent, re.I) and taxonomy.extract(sent):
            profile["projects"].append(sent[:200])
        if re.search(r"\bcertif\w+", sent, re.I):
            profile["certifications"].append(sent[:160])
    profile["projects"] = profile["projects"][:8]
    return profile


LLM_SYSTEM = ("You extract structured candidate profiles for a career-guidance system. Be faithful to the text: never invent skills. "
              "Return ONLY JSON.")
LLM_PROMPT = """Extract the candidate profile from the text below.
Return JSON: {{"degree": str, "branch": str, "year": int, "location": str, "experience_years": number,
"interests": [str], "projects": [str], "certifications": [str],
"skills": [{{"name": str, "level": "beginner|intermediate|advanced|expert", "evidence": short quote/paraphrase,
"evidence_type": "internship|production|major_project|project|github|certification|coursework|practice|self_declared",
"negated": true if the candidate says they do NOT have / have not used the skill}}]}}
Rules: level reflects the evidence, not just adjectives. A skill only mentioned in a list is self_declared. Expand implied
concrete skills (e.g. 'created REST APIs' -> REST API).

TEXT:
{text}"""
LEVEL_WORDS = {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}


def llm_parse(text: str, taxonomy, llm: LLM) -> tuple[dict | None, list[str]]:
    data = llm.generate_json(LLM_PROMPT.format(text=text[:12000]), system=LLM_SYSTEM)
    if not isinstance(data, dict):
        return None, []
    profile = new_profile()
    unmapped: list[str] = []
    for s in data.get("skills", []) or []:
        res = taxonomy.normalize(str(s.get("name", "")))
        if not res.ok:
            unmapped.append(str(s.get("name", "")))
            continue
        et = s.get("evidence_type") if s.get("evidence_type") in __import__("core.models", fromlist=["x"]).EVIDENCE_STRENGTH else "self_declared"
        add_evidence(profile, res.skill_id, str(s.get("evidence") or "Mentioned in profile")[:220], et,
                     stated=LEVEL_WORDS.get(str(s.get("level", "")).lower()), negated=bool(s.get("negated")), source="llm")
    for k in ("degree", "branch", "location"):
        if data.get(k):
            profile[k] = str(data[k])
    if isinstance(data.get("year"), int):
        profile["year"] = data["year"]
    try:
        profile["experience_years"] = float(data.get("experience_years") or 0)
    except Exception:
        pass
    profile["interests"] = [str(x) for x in (data.get("interests") or [])]
    profile["projects"] = [str(x)[:200] for x in (data.get("projects") or [])][:8]
    profile["certifications"] = [str(x)[:160] for x in (data.get("certifications") or [])][:6]
    return profile, unmapped


def parse_profile(text: str, taxonomy, llm: LLM | None = None, overrides: dict | None = None) -> tuple[dict, dict]:
    """Full Profile Parsing Agent. Returns (profile, info) where info explains which engines ran."""
    info = {"engine": "rules", "unmapped": [], "llm_error": None}
    profile = heuristic_parse(text, taxonomy)
    if llm and llm.available:
        lp, unmapped = llm_parse(text, taxonomy, llm)
        if lp:
            info.update(engine="rules + Gemini", unmapped=unmapped)
            for sid, sk in lp["skills"].items():
                cur = profile["skills"].get(sid)
                if cur is None or cur.get("negated") != sk.get("negated"):
                    profile["skills"][sid] = sk
                else:  # merge: LLM evidence type / level takes precedence, keep rule-based quotes as extra evidence
                    cur["evidence"] = sk["evidence"] + [e for e in cur["evidence"] if e["text"] not in {x["text"] for x in sk["evidence"]}]
                    cur["stated"] = sk.get("stated") or cur.get("stated")
            for k in ("degree", "branch", "location", "year"):
                if lp.get(k) and not profile.get(k):
                    profile[k] = lp[k]
            profile["interests"] = list(dict.fromkeys(profile["interests"] + lp["interests"]))
            profile["projects"] = profile["projects"] or lp["projects"]
            profile["certifications"] = profile["certifications"] or lp["certifications"]
            if lp["experience_years"] and not profile["experience_years"]:
                profile["experience_years"] = lp["experience_years"]
        else:
            info["llm_error"] = llm.last_error or "Gemini returned no usable JSON"
    for k, v in (overrides or {}).items():
        if v not in (None, "", [], 0):
            profile[k] = v
    finalize(profile, taxonomy)
    return profile, info
