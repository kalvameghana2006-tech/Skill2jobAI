"""Central configuration: paths, environment variables, scoring weights and thresholds."""
from __future__ import annotations

import os
from pathlib import Path

try:  # optional dependency, .env is a convenience only
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
EVAL_DIR = DATA_DIR / "eval"
STORAGE_DIR = ROOT / "storage"
STORAGE_DIR.mkdir(exist_ok=True)
DB_PATH = Path(os.getenv("SKILL2JOB_DB", STORAGE_DIR / "skill2job.db"))
VECTOR_CACHE = STORAGE_DIR / "vectors"

# ---- API keys / model names (all optional: the app has a full offline mode) -------------------
def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()

GEMINI_MODEL = env("GEMINI_MODEL", "gemini-2.5-flash")
EMBEDDING_MODEL = env("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
# Set EMBEDDING_BACKEND=hash to force the built-in offline embedder (no model download).
EMBEDDING_BACKEND = env("EMBEDDING_BACKEND", "auto")

# ---- Match scoring ----------------------------------------------------------------------------
# Final Match = weighted sum of six signals (see core/matcher.py). Weights were tuned on the
# evaluation set with `python -m core.evaluation --tune`; edit here to experiment.
MATCH_WEIGHTS = {
    "required": 0.40,      # required-skill coverage
    "preferred": 0.10,     # preferred-skill coverage
    "semantic": 0.10,      # semantic similarity (skills + profile-vs-job text)
    "proficiency": 0.15,   # level fit on required skills
    "evidence": 0.10,      # strength of the evidence behind the skills
    "experience": 0.08,
    "education": 0.07,
}
SUITABLE_SCORE = 65.0       # score needed to count a job as "suitable"
SUITABLE_REQ_COVERAGE = 0.70  # ... and this share of required skills must be covered
SUITABLE_PROFICIENCY = 0.70   # ... at an adequate level (level-weighted coverage of required skills)
STRONG_SCORE = 80.0

# ---- Verification thresholds --------------------------------------------------------------------
QUIZ_PASS = 0.70
PRACTICAL_PASS = 55.0
REVISION_THRESHOLD = 0.80   # below -> revision day
RETAKE_THRESHOLD = 0.50     # below -> revision + extra practice + reassessment

# Minutes of study that one "effort day" in the taxonomy represents (1.5h/day baseline).
BASELINE_HOURS_PER_DAY = 1.5
