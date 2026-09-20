"""Resource Recommendation Agent: picks resources that suit *this* candidate's level, time budget and goal."""
from __future__ import annotations

from functools import lru_cache

from .config import env
from .models import LEVEL_NAMES

KIND_TYPES = {"watch": ["video"], "read": ["docs", "article"], "practice": ["practice"], "project": ["project"],
              "course": ["course"], "talk": ["talk"]}
DIFF_RANK = {"beginner": 0, "intermediate": 1, "advanced": 2}


def target_difficulty(level: int, kind: str) -> int:
    base = 0 if level <= 1 else 1 if level == 2 else 2
    return min(2, base + (1 if kind in ("project", "talk") and base < 2 else 0))


class ResourceRecommender:
    def __init__(self, kb, taxonomy):
        self.kb, self.tax = kb, taxonomy
        self._by_skill: dict[str, list[dict]] = {}
        for d in kb.store.docs:
            if d.metadata.get("doc_type") == "resource":
                self._by_skill.setdefault(d.metadata["skill_id"], []).append(d.metadata["resource"])

    def all_for(self, skill_id: str) -> list[dict]:
        return self._by_skill.get(skill_id, [])

    def rank(self, skill_id: str, level: int, kind: str | None = None, query: str = "", budget_min: int | None = None) -> list[dict]:
        pool = self.all_for(skill_id)
        if kind:
            pool = [r for r in pool if r["type"] in KIND_TYPES[kind]]
        if not pool:
            return []
        hits = self.kb.resources(f"{self.tax.name(skill_id)} {query}", skill_id, k=len(self._by_skill.get(skill_id, [])) or 8)
        rel = {h.doc.metadata["chunk_id"]: 1 / (i + 1) for i, h in enumerate(hits)}
        tgt = target_difficulty(level, kind or "watch")
        scored = []
        for r in pool:
            s = 1.0 * rel.get(r["id"], 0.0)
            s += 1.0 - 0.45 * abs(DIFF_RANK[r["difficulty"]] - tgt)
            if budget_min:
                s += 0.4 if r["duration_min"] <= budget_min * 1.3 else -0.2
            s += 0.15 if r["link_kind"] == "direct" else 0.0
            scored.append((s, r))
        scored.sort(key=lambda x: -x[0])
        return [self.personalize(r, skill_id, level, budget_min) for _, r in scored]

    def personalize(self, r: dict, skill_id: str, level: int, budget_min: int | None) -> dict:
        lv = LEVEL_NAMES.get(level, "None")
        why = r["why"]
        fit = f" Matched to your current level ({lv if level else 'new to this skill'})"
        if budget_min:
            fit += f" and today's ~{budget_min} minute budget" + ("." if r["duration_min"] <= budget_min * 1.3 else " – split it across sessions.")
        else:
            fit += "."
        return {**r, "why_for_you": why + fit}

    def pick(self, skill_id: str, level: int, kind: str, query: str = "", budget_min: int | None = None, exclude: set[str] | None = None) -> dict | None:
        for r in self.rank(skill_id, level, kind, query, budget_min):
            if not exclude or r["id"] not in exclude:
                return r
        return None

    def bundle(self, skill_id: str, level: int) -> dict[str, list[dict]]:
        """Full library for a skill grouped by source family (Coursera / NPTEL / Skill India / YouTube / docs ...)."""
        out: dict[str, list[dict]] = {}
        for r in self.rank(skill_id, level):
            out.setdefault(r["source"], []).append(r)
        return out


@lru_cache(maxsize=512)
def live_youtube(query: str) -> tuple[str, str] | None:
    """Optional: with YOUTUBE_API_KEY set, replace a search link by the top real video (title, url)."""
    key = env("YOUTUBE_API_KEY")
    if not key:
        return None
    try:
        import requests

        r = requests.get("https://www.googleapis.com/youtube/v3/search", timeout=6, params={
            "part": "snippet", "q": query, "type": "video", "maxResults": 1, "key": key, "videoEmbeddable": "true", "relevanceLanguage": "en"})
        item = r.json()["items"][0]
        return item["snippet"]["title"], "https://www.youtube.com/watch?v=" + item["id"]["videoId"]
    except Exception:
        return None
