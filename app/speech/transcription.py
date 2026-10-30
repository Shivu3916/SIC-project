"""
Speech services: transcription via Groq Whisper.
Output (TTS) is handled in the browser via SpeechSynthesis API.
This module is designed so a future real-time voice provider can be added
by implementing the same interface.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from config import Config

logger = logging.getLogger(__name__)

# Allowed audio MIME types for upload safety
ALLOWED_AUDIO_MIMETYPES = {
    "audio/webm", "audio/ogg", "audio/wav", "audio/mpeg",
    "audio/mp4", "audio/flac", "audio/x-m4a",
}

# Max audio upload size: 25 MB (Groq Whisper limit)
MAX_AUDIO_BYTES = 25 * 1024 * 1024


def transcribe_audio(audio_bytes: bytes, filename: str = "recording.webm") -> dict:
    """
    Transcribe audio using Groq's Whisper model.

    Parameters
    ----------
    audio_bytes : raw audio bytes
    filename    : hint for MIME detection (extension matters)

    Returns
    -------
    dict with keys: transcript (str), language (str), error (str|None)
    """
    if not Config.GROQ_API_KEY:
        return {"transcript": "", "language": "", "error": "GROQ_API_KEY not configured."}

    if len(audio_bytes) > MAX_AUDIO_BYTES:
        return {
            "transcript": "",
            "language": "",
            "error": f"Audio file too large ({len(audio_bytes)//1024}KB > 25MB limit).",
        }

    if not audio_bytes:
        return {"transcript": "", "language": "", "error": "Empty audio data received."}

    try:
        from groq import Groq

        client = Groq(api_key=Config.GROQ_API_KEY)

        # Write to a temp file — Groq SDK needs a file-like object with a name
        suffix = Path(filename).suffix or ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model=Config.GROQ_WHISPER_MODEL,
                    file=(filename, audio_file),
                    response_format="verbose_json",
                )
            transcript_text = transcription.text.strip()
            language = getattr(transcription, "language", "en") or "en"
            return {"transcript": transcript_text, "language": language, "error": None}

        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    except Exception as exc:
        logger.exception("Whisper transcription failed: %s", exc)
        error_msg = str(exc)
        # Sanitise to avoid leaking internal details
        if "api_key" in error_msg.lower():
            error_msg = "Authentication error – check your GROQ_API_KEY."
        return {"transcript": "", "language": "", "error": error_msg}
