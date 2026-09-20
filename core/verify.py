"""Practical skill verification: real repository checks + rubric grading of a written explanation.

Level 1 – self completion (checklist)     Level 2 – quiz (core/quiz.py)     Level 3 – practical (this module)

Practical evidence is scored from
  * GitHub repository signals via the public GitHub API (files present, README keywords)  [tool logic, no LLM guessing]
  * keyword coverage + semantic similarity of the written explanation against the project rubric
  * an optional Gemini rubric grade (blended 50/50 with the rule-based score)
"""
from __future__ import annotations

import base64
import re

import numpy as np

from .config import PRACTICAL_PASS
from .curriculum import path_for
from .llm import LLM

GH_RE = re.compile(r"github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:/|$|\?|#)", re.I)


def parse_github_url(url: str) -> tuple[str, str] | None:
    m = GH_RE.search(url or "")
    return (m.group(1), m.group(2)) if m else None


def fetch_repo_signals(url: str, timeout: float = 8.0) -> dict:
    """Return {'ok', 'files', 'readme', 'languages', 'error'} from the GitHub REST API (no token needed for public repos)."""
    parsed = parse_github_url(url)
    if not parsed:
        return {"ok": False, "error": "That doesn't look like a github.com/owner/repo link."}
    owner, repo = parsed
    try:
        import requests

        from .config import env

        base = f"https://api.github.com/repos/{owner}/{repo}"
        hdr = {"Accept": "application/vnd.github+json"}
        if env("GITHUB_TOKEN"):                      # optional: raises the API rate limit / allows private repos you own
            hdr["Authorization"] = f"Bearer {env('GITHUB_TOKEN')}"
        r = requests.get(base, timeout=timeout, headers=hdr)
        if r.status_code == 404:
            return {"ok": False, "error": "Repository not found (is it public?)."}
        r.raise_for_status()
        meta = r.json()
        branch = meta.get("default_branch", "main")
        tree = requests.get(f"{base}/git/trees/{branch}?recursive=1", timeout=timeout, headers=hdr).json()
        files = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"][:500]
        readme = ""
        rr = requests.get(f"{base}/readme", timeout=timeout, headers=hdr)
        if rr.ok:
            readme = base64.b64decode(rr.json().get("content", "")).decode("utf-8", errors="ignore")
        langs = list(requests.get(f"{base}/languages", timeout=timeout, headers=hdr).json().keys())
        return {"ok": True, "files": files, "readme": readme, "languages": langs, "description": meta.get("description") or "",
                "pushed_at": meta.get("pushed_at"), "error": None}
    except Exception as exc:  # offline, rate-limited, blocked ...
        return {"ok": False, "error": f"Could not reach GitHub ({type(exc).__name__}). Your write-up was graded instead."}


def keyword_coverage(text: str, keywords: list[str]) -> tuple[float, list[str], list[str]]:
    low = text.lower()
    hit = [k for k in keywords if k.lower() in low]
    miss = [k for k in keywords if k.lower() not in low]
    return (len(hit) / len(keywords) if keywords else 1.0), hit, miss


def grade_practical(skill_id: str, taxonomy, embedder, llm: LLM | None, repo_url: str = "", explanation: str = "", code: str = "") -> dict:
    rubric = path_for(skill_id)
    keywords = rubric.get("check_keywords", [])
    check_files = rubric.get("check_files", [])
    text = f"{explanation}\n{code}"
    words = len(explanation.split())
    feedback: list[str] = []
    parts: dict[str, float] = {}

    repo = fetch_repo_signals(repo_url) if repo_url.strip() else None
    repo_text = ""
    if repo and repo["ok"]:
        names = [f.split("/")[-1].lower() for f in repo["files"]]
        found = [f for f in check_files if f.lower() in names or any(f.lower() == p.lower() for p in repo["files"])]
        parts["repo_files"] = len(found) / len(check_files) if check_files else 1.0
        repo_text = repo["readme"] + " " + " ".join(repo["files"])
        feedback.append(f"Repository reachable: found {len(found)}/{len(check_files)} expected files ({', '.join(found) or 'none'}).")
        missing = [f for f in check_files if f not in found]
        if missing:
            feedback.append(f"Missing: {', '.join(missing)}.")
        if not repo["readme"].strip():
            feedback.append("Add a README that explains how to run the project.")
    elif repo:
        feedback.append(repo["error"])

    kcov, hit, miss = keyword_coverage(text + " " + repo_text, keywords)
    parts["keywords"] = kcov
    if miss:
        feedback.append(f"Not yet mentioned or visible: {', '.join(miss)}.")
    ref = f"{rubric.get('project', '')} {' '.join(keywords)}"
    if text.strip():
        v = embedder.encode([text[:3000], ref])
        parts["semantic"] = float(np.clip((float(v[0] @ v[1]) - 0.05) / 0.45, 0, 1))
    else:
        parts["semantic"] = 0.0
    parts["explanation_depth"] = min(1.0, words / 60) if explanation.strip() else 0.0
    if explanation.strip() and words < 40:
        feedback.append("Write at least ~40 words on what you built, how it works and what you would improve.")

    if "repo_files" in parts:
        rule = 0.40 * parts["repo_files"] + 0.30 * parts["keywords"] + 0.15 * parts["semantic"] + 0.15 * parts["explanation_depth"]
    else:
        rule = 0.45 * parts["keywords"] + 0.25 * parts["semantic"] + 0.30 * parts["explanation_depth"]
    score = 100 * rule
    engine = "rules"
    if llm and llm.available and (explanation.strip() or code.strip()):
        data = llm.generate_json(
            f"Grade a student's practical submission for {taxonomy.name(skill_id)}.\nTask: {rubric.get('project', '')}\n"
            f"Rubric keywords: {', '.join(keywords)}\nWrite-up:\n{explanation[:2500]}\nCode:\n{code[:2500]}\n"
            'Return JSON {"score": 0-100, "feedback": "2 short sentences with one concrete improvement"}',
            system="You are a fair, strict technical reviewer. Only credit what is shown.")
        if isinstance(data, dict) and isinstance(data.get("score"), (int, float)):
            score = 0.5 * score + 0.5 * float(data["score"])
            feedback.append(str(data.get("feedback", ""))[:400])
            engine = "rules + Gemini"
    score = round(max(0.0, min(100.0, score)), 1)
    return {"score": score, "passed": score >= PRACTICAL_PASS, "parts": {k: round(v, 2) for k, v in parts.items()}, "feedback": [f for f in feedback if f],
            "repo": {k: repo[k] for k in ("ok", "error")} if repo else None, "engine": engine}
