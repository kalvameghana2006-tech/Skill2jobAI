"""Skill taxonomy / skill graph.

Responsibilities
  * canonical skills, categories, prerequisites, "implies" links and effort estimates
  * alias index -> Skill Normalization  ("RESTful services" -> REST API, "JS" -> JavaScript)
  * mention extraction from free text (regex over aliases with guards for ambiguous words)
  * transfer credit between related skills (families) with an explicit "never related" block-list
  * semantic fallback: nearest-skill lookup through the embedder when no alias matches
"""
from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import numpy as np

from .config import DATA_DIR

# Words that are also ordinary English: only accept them when written with the canonical casing.
CASE_SENSITIVE_ALIASES = {"react": "React", "excel": "Excel", "express": "Express", "node": "Node",
                          "monitoring": "Monitoring"}
# Single letters / very short names: accepted only inside a list of programming languages.
LIST_CONTEXT_ALIASES = {"c": "C", "go": "Go"}
# Never extracted as a bare word (only through longer aliases such as "r programming").
NEVER_BARE = {"r"}
SPRING_GUARD = r"(?!\s+(?:19|20)\d\d|\s+(?:semester|term|break|season|intern))"

_TOKEN_L = r"(?<![A-Za-z0-9+#])"
_TOKEN_R = r"(?![A-Za-z0-9+#])(?!\.[A-Za-z0-9])"


@dataclass
class Mention:
    skill_id: str
    start: int
    end: int
    alias: str


@dataclass
class NormResult:
    skill_id: str | None
    confidence: float
    method: str  # exact | fuzzy | semantic | none

    @property
    def ok(self) -> bool:
        return self.skill_id is not None


def clean_term(term: str) -> str:
    t = term.strip().lower()
    t = re.sub(r"[\u2018\u2019`]", "'", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip(" .,:;()[]{}\"'")


class Taxonomy:
    def __init__(self, path: Path | str | None = None):
        path = Path(path) if path else DATA_DIR / "taxonomy.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.skills: dict[str, dict] = raw["skills"]
        self.families: list[dict] = raw.get("families", [])
        self.not_related = {frozenset(p) for p in raw.get("not_related", [])}
        self._build_alias_index()
        self.embedder = None
        self._emb: np.ndarray | None = None
        self._ids: list[str] = list(self.skills)
        self._pos = {sid: i for i, sid in enumerate(self._ids)}
        self._sim: np.ndarray | None = None
        self._tc_cache: dict[tuple[str, str], tuple[float, str]] = {}

    # ------------------------------------------------------------------ basic accessors
    def get(self, sid: str) -> dict:
        return self.skills[sid]

    def name(self, sid: str) -> str:
        return self.skills[sid]["name"] if sid in self.skills else sid

    def __contains__(self, sid: str) -> bool:
        return sid in self.skills

    def by_category(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for sid, s in self.skills.items():
            out.setdefault(s["category"], []).append(sid)
        return out

    def id_from_name(self, name: str) -> str | None:
        return self._name_index.get(clean_term(name))

    # ------------------------------------------------------------------ alias index
    def _build_alias_index(self) -> None:
        self._exact: dict[str, str] = {}      # every alias (incl. normalise-only) -> id
        self._name_index: dict[str, str] = {}
        self._patterns: list[tuple[str, str]] = []   # (alias, sid) extractable
        for sid, s in self.skills.items():
            self._name_index[clean_term(s["name"])] = sid
            self._exact[clean_term(s["name"])] = sid
            extractable = {clean_term(s["name"])} | {clean_term(a) for a in s.get("aliases", [])}
            for a in s.get("norm_aliases", []):
                self._exact[clean_term(a)] = sid
            for a in extractable:
                if a and a not in NEVER_BARE:
                    self._patterns.append((a, sid))
                    self._exact.setdefault(a, sid)
        for a in CASE_SENSITIVE_ALIASES:      # e.g. "Express" / "Node" are normalise-only but extractable when capitalised
            if a in self._exact and not any(x == a for x, _ in self._patterns):
                self._patterns.append((a, self._exact[a]))
        # de-duplicate alias -> keep first (taxonomy order), longest first for matching
        seen: dict[str, str] = {}
        for a, sid in self._patterns:
            seen.setdefault(a, sid)
        items = sorted(seen.items(), key=lambda kv: -len(kv[0]))
        ci_parts, cs_parts, ctx_parts = [], [], []
        self._alias_sid: dict[str, str] = {}
        for a, sid in items:
            self._alias_sid[a.lower()] = sid
            esc = re.escape(a).replace(r"\ ", r"\s+")
            if a == "spring":
                esc += SPRING_GUARD
            if a in CASE_SENSITIVE_ALIASES:
                cs_parts.append(re.escape(CASE_SENSITIVE_ALIASES[a]))
            elif a in LIST_CONTEXT_ALIASES:
                ctx_parts.append(re.escape(LIST_CONTEXT_ALIASES[a]))
            else:
                ci_parts.append(esc)
        self._re_ci = re.compile(_TOKEN_L + "(" + "|".join(ci_parts) + ")" + _TOKEN_R, re.I)
        self._re_cs = re.compile(_TOKEN_L + "(" + "|".join(cs_parts) + ")" + _TOKEN_R) if cs_parts else None
        self._re_ctx = re.compile(_TOKEN_L + "(" + "|".join(ctx_parts) + ")" + _TOKEN_R) if ctx_parts else None
        self._exact_keys = list(self._exact)

    # ------------------------------------------------------------------ extraction
    def extract(self, text: str) -> list[Mention]:
        """Find skill mentions in free text. Longest match wins; overlapping matches are dropped."""
        found: list[Mention] = []
        for m in self._re_ci.finditer(text):
            alias = clean_term(re.sub(r"\s+", " ", m.group(1)))
            sid = self._alias_sid.get(alias)
            if sid:
                found.append(Mention(sid, m.start(1), m.end(1), alias))
        if self._re_cs:
            for m in self._re_cs.finditer(text):
                sid = self._alias_sid.get(m.group(1).lower())
                if sid:
                    found.append(Mention(sid, m.start(1), m.end(1), m.group(1)))
        if self._re_ctx:
            langs = [f for f in found if self.skills[f.skill_id]["category"] == "Programming"]
            for m in self._re_ctx.finditer(text):
                sid = self._alias_sid.get(m.group(1).lower())
                near = [f for f in langs if abs(f.start - m.start(1)) < 40]
                before = text[max(0, m.start(1) - 14):m.start(1)].lower()
                after = text[m.end(1):m.end(1) + 8]
                prep = bool(re.search(r"(?:\bwith|\bin|\busing|\bof|\bknow|\band|,|/)\s+$", before)) and \
                    not re.match(r"\s+(?:to|on|for|the|a|an|through|ahead|back|away|out|over|live|figure)\b", after) and True
                if sid and (near or prep):
                    found.append(Mention(sid, m.start(1), m.end(1), m.group(1)))
        found.sort(key=lambda f: (f.start, -(f.end - f.start)))
        out: list[Mention] = []
        last_end = -1
        for f in found:
            if f.start >= last_end:
                out.append(f)
                last_end = f.end
        return out

    # ------------------------------------------------------------------ normalisation
    def attach_embedder(self, embedder) -> None:
        self.embedder = embedder
        self._tc_cache = {}
        texts = [self.descriptor(sid) for sid in self._ids]
        self._emb = embedder.encode(texts)
        self._sim = self._emb @ self._emb.T

    def descriptor(self, sid: str) -> str:
        s = self.skills[sid]
        return f"{s['name']}. {s['category']}. {s['description']}. Also called: {', '.join(s.get('aliases', [])[:6])}"

    def normalize(self, term: str, allow_semantic: bool = True) -> NormResult:
        """Map any surface form to a canonical skill: exact alias -> fuzzy -> embedding nearest neighbour."""
        t = clean_term(term)
        if not t:
            return NormResult(None, 0.0, "none")
        if t in self._exact:
            return NormResult(self._exact[t], 1.0, "exact")
        compact = re.sub(r"[\s\-_.]", "", t)
        for key, sid in self._exact.items():
            if re.sub(r"[\s\-_.]", "", key) == compact:
                return NormResult(sid, 0.98, "exact")
        ms = self.extract(term)
        if len(ms) == 1 and (ms[0].end - ms[0].start) >= 0.6 * len(term.strip()):
            return NormResult(ms[0].skill_id, 0.95, "exact")
        if len(t) >= 4:
            close = difflib.get_close_matches(t, self._exact_keys, n=1, cutoff=0.88)
            if close:
                ratio = difflib.SequenceMatcher(None, t, close[0]).ratio()
                return NormResult(self._exact[close[0]], round(ratio, 3), "fuzzy")
        if allow_semantic and self.embedder is not None and self._emb is not None:
            v = self.embedder.encode([f"{term}"])[0]
            sims = self._emb @ v
            i = int(np.argmax(sims))
            thr = 0.62 if self.embedder.is_semantic else 0.80
            if sims[i] >= thr:
                return NormResult(self._ids[i], float(round(sims[i], 3)), "semantic")
        return NormResult(None, 0.0, "none")

    # ------------------------------------------------------------------ graph helpers
    def prereqs(self, sid: str, transitive: bool = True) -> list[str]:
        """Prerequisites in learning order (deepest first)."""
        out: list[str] = []

        def visit(x: str, seen: set[str]) -> None:
            for p in self.skills[x].get("prereqs", []):
                if p in seen:
                    continue
                seen.add(p)
                if transitive:
                    visit(p, seen)
                if p not in out:
                    out.append(p)

        visit(sid, {sid})
        return out

    def implied(self, sid: str) -> list[str]:
        return list(self.skills[sid].get("implies", []))

    def dependents(self, sid: str) -> list[str]:
        return [k for k, s in self.skills.items() if sid in s.get("prereqs", [])]

    def order_with_prereqs(self, targets: Iterable[str], have: Iterable[str] = ()) -> list[dict]:
        """Order target skills so that every prerequisite is learned first.

        Returns [{"skill": id, "is_prereq": bool, "needed_for": id|None}] – prerequisites the
        candidate already has are skipped.
        """
        have = set(have)
        targets = list(dict.fromkeys(targets))
        out: list[dict] = []
        placed: set[str] = set()

        def add(sid: str, needed_for: str | None) -> None:
            if sid in placed or sid in have:
                return
            for p in self.skills[sid].get("prereqs", []):
                add(p, sid)
            placed.add(sid)
            out.append({"skill": sid, "is_prereq": sid not in targets, "needed_for": needed_for})

        for t in targets:
            add(t, None)
        return out

    def effort_days(self, sid: str) -> float:
        return float(self.skills[sid].get("effort_days", 6))

    # ------------------------------------------------------------------ similarity / transfer
    def similarity(self, a: str, b: str) -> float:
        if a == b:
            return 1.0
        if self._sim is None:
            return 0.0
        return float(self._sim[self._pos[a], self._pos[b]])

    def transfer_credit(self, target: str, source: str) -> tuple[float, str]:
        """How much of *target* is plausibly covered by real *source* experience?

        Curated skill families give a fixed credit. Embedding similarity may add credit only for
        pairs the curators have not blocked (e.g. Java vs JavaScript look alike but are unrelated).
        """
        key = (target, source)
        if key in self._tc_cache:
            return self._tc_cache[key]
        self._tc_cache[key] = self._transfer_credit(target, source)
        return self._tc_cache[key]

    def _transfer_credit(self, target: str, source: str) -> tuple[float, str]:
        if target == source:
            return 1.0, "same skill"
        if frozenset((target, source)) in self.not_related:
            return 0.0, "blocked"
        best, why = 0.0, ""
        for fam in self.families:
            m = fam["members"]
            if target in m and source in m and fam["credit"] > best:
                best, why = fam["credit"], fam["name"]
        if best == 0.0 and self.embedder is not None and self.embedder.is_semantic:
            sim = self.similarity(target, source)
            if sim >= 0.62:
                best, why = round(min(0.4, 0.2 + (sim - 0.62)), 2), f"semantic similarity {sim:.2f}"
        return best, why


@lru_cache(maxsize=1)
def load_taxonomy() -> Taxonomy:
    return Taxonomy()
