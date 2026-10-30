"""
Speech transcription route.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from app.speech.transcription import transcribe_audio, ALLOWED_AUDIO_MIMETYPES, MAX_AUDIO_BYTES

logger = logging.getLogger(__name__)

speech_bp = Blueprint("speech", __name__, url_prefix="/api/speech")

MAX_AUDIO_MB = MAX_AUDIO_BYTES // (1024 * 1024)


@speech_bp.route("/transcribe", methods=["POST"])
def transcribe():
    """
    Accept an audio file and return a transcript.
    The audio is processed and the raw bytes are NOT stored permanently.
    """
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided. Send as multipart/form-data with key 'audio'."}), 400

    audio_file = request.files["audio"]
    filename = audio_file.filename or "recording.webm"

    audio_bytes = audio_file.read()

    if not audio_bytes:
        return jsonify({"error": "Empty audio file."}), 400

    if len(audio_bytes) > MAX_AUDIO_BYTES:
        return jsonify({
            "error": f"Audio file too large. Maximum size is {MAX_AUDIO_MB}MB."
        }), 413

    result = transcribe_audio(audio_bytes, filename=filename)

    if result.get("error"):
        return jsonify({"error": result["error"]}), 503

    return jsonify({
        "transcript": result["transcript"],
        "language": result.get("language", "en"),
    })
