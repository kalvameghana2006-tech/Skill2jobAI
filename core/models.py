"""Shared constants and small helpers used across the pipeline."""
from __future__ import annotations

from typing import Iterable

LEVEL_NAMES = {0: "None", 1: "Beginner", 2: "Intermediate", 3: "Advanced", 4: "Expert"}
LEVEL_FROM_CODE = {"b": 1, "m": 2, "s": 3}
CODE_FROM_LEVEL = {1: "b", 2: "m", 3: "s"}

# Why do we believe the candidate has a skill?  -> how strong is that evidence (0-1)
EVIDENCE_STRENGTH = {
    "production": 1.0,
    "internship": 1.0,
    "verified_practical": 1.0,
    "major_project": 0.85,
    "project": 0.8,
    "github": 0.8,
    "verified_quiz": 0.7,
    "certification": 0.55,
    "coursework": 0.5,
    "practice": 0.5,
    "inferred": 0.4,
    "self_declared": 0.25,
}
EVIDENCE_LABEL = {
    "production": "Production work",
    "internship": "Internship",
    "verified_practical": "Verified practical task",
    "major_project": "Major project",
    "project": "Project",
    "github": "GitHub work",
    "verified_quiz": "Quiz-verified",
    "certification": "Certification",
    "coursework": "Course / coursework",
    "practice": "Practice problems",
    "inferred": "Inferred from related skill",
    "self_declared": "Self-declared",
}

STATUS_LABEL = {
    "matched": "Matched",
    "partial": "Partial",
    "missing": "Missing",
    "insufficient": "Insufficient evidence",
}

ROLE_FAMILIES = [
    "Backend", "Frontend", "Full Stack", "Data Analytics", "Data Science & ML", "Data Engineering",
    "Cloud & DevOps", "QA & Testing", "Software Engineering", "Mobile", "Security", "Database",
]


def strongest(evidence: Iterable[dict]) -> float:
    """Highest evidence strength in a list of {type, text} evidence records."""
    best = 0.0
    for e in evidence or []:
        best = max(best, EVIDENCE_STRENGTH.get(e.get("type", "self_declared"), 0.25))
    return best


def level_name(level: float) -> str:
    return LEVEL_NAMES.get(int(round(level)), "None")


def slugify(name: str) -> str:
    s = name.lower().replace("c++", "cpp").replace("c#", "csharp")
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif ch in " /-&.":
            out.append("_" if ch != "." else "")
    slug = "".join(out)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")
