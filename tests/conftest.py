import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("EMBEDDING_BACKEND", "hash")            # deterministic, no model download in CI
os.environ["SKILL2JOB_DB"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ.pop("GEMINI_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


@pytest.fixture(scope="session")
def engine():
    from core.engine import Engine
    return Engine(db_path=Path(tempfile.mkdtemp()) / "engine.db")


@pytest.fixture()
def fresh(engine):
    engine.reset("default")
    return engine
