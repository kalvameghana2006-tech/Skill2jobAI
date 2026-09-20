"""Speech -> text. Order: Gemini audio transcription (if key) -> free Google Web Speech via SpeechRecognition -> message."""
from __future__ import annotations

import io


def transcribe(audio: bytes, llm=None, mime: str = "audio/wav") -> tuple[str | None, str]:
    """Return (text, engine_or_error)."""
    if llm is not None and llm.available:
        text = llm.transcribe(audio, mime)
        if text:
            return text, "Gemini"
    try:
        import speech_recognition as sr

        rec = sr.Recognizer()
        with sr.AudioFile(io.BytesIO(audio)) as src:
            data = rec.record(src)
        return rec.recognize_google(data), "Google Web Speech"
    except ImportError:
        return None, "Add a Gemini key (or `pip install SpeechRecognition`) to enable voice transcription."
    except Exception as exc:
        return None, f"Couldn't transcribe the audio ({type(exc).__name__}). Try again, or type it instead."
