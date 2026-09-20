"""Thin, failure-tolerant wrapper around Google Gemini (google-genai SDK).

Every method returns None / raises nothing when the key is missing or a call fails, so callers can fall
back to deterministic logic. The API key is read from GEMINI_API_KEY (env / .env) or set at runtime
from the sidebar (`LLM.set_key`).
"""
from __future__ import annotations

import json
import logging
import re
import threading

from .config import GEMINI_MODEL, env

log = logging.getLogger(__name__)


class LLM:
    def __init__(self) -> None:
        self.key = env("GEMINI_API_KEY") or env("GOOGLE_API_KEY")
        self.model = GEMINI_MODEL
        self.last_error: str | None = None
        self.calls = 0
        self._client = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ setup
    def set_key(self, key: str) -> None:
        self.key = key.strip()
        self._client = None
        self.last_error = None

    @property
    def available(self) -> bool:
        return bool(self.key)

    @property
    def client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.key)
        return self._client

    # ------------------------------------------------------------------ generation
    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.3, json_mode: bool = False,
                 max_tokens: int = 4096) -> str | None:
        if not self.available:
            return None
        try:
            from google.genai import types

            cfg = types.GenerateContentConfig(
                system_instruction=system, temperature=temperature, max_output_tokens=max_tokens,
                response_mime_type="application/json" if json_mode else None,
            )
            with self._lock:
                self.calls += 1
            resp = self.client.models.generate_content(model=self.model, contents=prompt, config=cfg)
            return (resp.text or "").strip()
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"[:300]
            log.warning("Gemini call failed: %s", self.last_error)
            return None

    def generate_json(self, prompt: str, system: str | None = None, temperature: float = 0.1):
        text = self.generate(prompt, system=system, temperature=temperature, json_mode=True)
        return parse_json(text) if text else None

    def transcribe(self, audio: bytes, mime: str = "audio/wav") -> str | None:
        if not self.available:
            return None
        try:
            from google.genai import types

            resp = self.client.models.generate_content(
                model=self.model,
                contents=[types.Part.from_bytes(data=audio, mime_type=mime),
                          "Transcribe this audio exactly. Return only the transcript text."],
            )
            return (resp.text or "").strip()
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"[:300]
            return None

    def test(self) -> tuple[bool, str]:
        out = self.generate("Reply with the single word: ready", temperature=0)
        return (out is not None, out or (self.last_error or "no key"))


def parse_json(text: str):
    """Parse JSON that may be wrapped in markdown fences or surrounded by prose."""
    if not text:
        return None
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"(\{.*\}|\[.*\])", t, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                return None
    return None
