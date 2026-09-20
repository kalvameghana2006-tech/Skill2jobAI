"""Access to per-skill learning paths (modules, terms, practice tasks, project, repo rubric)."""
from __future__ import annotations

import json
from functools import lru_cache

from .config import DATA_DIR


@lru_cache(maxsize=1)
def load_paths() -> dict:
    return json.loads((DATA_DIR / "paths.json").read_text(encoding="utf-8"))


def path_for(skill_id: str) -> dict:
    return load_paths().get(skill_id) or {"modules": [], "project": "", "check_files": [], "check_keywords": []}


def module_titles(skill_id: str) -> list[str]:
    return [m["title"] for m in path_for(skill_id)["modules"]]
