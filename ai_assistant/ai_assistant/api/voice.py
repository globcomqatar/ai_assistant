"""
voice.py — Speech-to-Text transcription endpoint for the AI chat page.

Supports: OpenAI Whisper, Google Speech-to-Text v1, Azure Speech REST.
Audio arrives as a base64-encoded WebM/Opus blob recorded by MediaRecorder.
"""

from __future__ import annotations

import base64
import os
import tempfile

import frappe
from frappe import _


@frappe.whitelist()
def transcribe_audio(audio_base64: str, language: str = "en") -> dict:
    """
    Transcribe a base64-encoded audio blob using the configured voice provider.

    Args:
        audio_base64: Base64 string of a WebM/Opus audio blob.
        language:     BCP-47 language code, e.g. "en-US", "ar-SA".

    Returns:
        {"transcript": "<recognised text>"}
    """
    frappe.only_for("All")

    settings = frappe.get_single("AI Settings")
    if not settings.enable_voice_input:
        frappe.throw(_("Voice input is disabled."))

    provider = settings.voice_provider or "Browser (Free)"
    if provider == "Browser (Free)":
        frappe.throw(_("Browser voice provider does not use a backend endpoint."))

    api_key = settings.get_voice_api_key()
    if not api_key:
        frappe.throw(_("Voice API key is not configured in AI Settings."))

    lang = (language or "en").strip()

    try:
        if provider == "OpenAI Whisper":
            return _transcribe_openai(audio_base64, lang, api_key)
        elif provider == "Google Speech-to-Text":
            return _transcribe_google(audio_base64, lang, api_key)
        elif provider == "Azure Speech":
            region = frappe.db.get_single_value("AI Settings", "azure_speech_region") or "eastus"
            return _transcribe_azure(audio_base64, lang, api_key, region)
        else:
            frappe.throw(_("Unknown voice provider: {0}").format(provider))
    except frappe.ValidationError:
        raise
    except Exception as exc:
        frappe.log_error(title="Voice transcription failed", message=str(exc))
        frappe.throw(_("Transcription failed: {0}").format(str(exc)[:200]))


# ── Provider implementations ────────────────────────────────────────────────

def _transcribe_openai(audio_base64: str, language: str, api_key: str) -> dict:
    """OpenAI Whisper-1 via the openai SDK (already a project dependency)."""
    from openai import OpenAI

    audio_bytes = base64.b64decode(audio_base64)
    suffix = ".webm"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        client = OpenAI(api_key=api_key)
        # Pass only the language root (e.g. "en", "ar") — Whisper expects ISO-639-1
        lang_code = language.split("-")[0].lower() if language else None
        with open(tmp_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language=lang_code,
            )
        return {"transcript": result.text or ""}
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _transcribe_google(audio_base64: str, language: str, api_key: str) -> dict:
    """
    Google Speech-to-Text v1 REST API.
    Audio must be WebM/Opus — matches MediaRecorder default in Chrome.
    """
    import requests as _requests

    lang_code = _bcp47(language)
    payload = {
        "config": {
            "encoding": "WEBM_OPUS",
            "languageCode": lang_code,
            "enableAutomaticPunctuation": True,
        },
        "audio": {"content": audio_base64},
    }
    resp = _requests.post(
        f"https://speech.googleapis.com/v1/speech:recognize?key={api_key}",
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results") or []
    transcript = " ".join(
        r["alternatives"][0]["transcript"]
        for r in results
        if r.get("alternatives")
    )
    return {"transcript": transcript}


def _transcribe_azure(
    audio_base64: str, language: str, api_key: str, region: str
) -> dict:
    """
    Azure Cognitive Services Speech REST API (short audio recognition).
    Endpoint accepts raw WebM/Opus bytes.
    """
    import requests as _requests

    lang_code = _bcp47(language)
    audio_bytes = base64.b64decode(audio_base64)
    url = (
        f"https://{region}.stt.speech.microsoft.com"
        "/speech/recognition/conversation/cognitiveservices/v1"
    )
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type": "audio/webm;codecs=opus",
        "Accept": "application/json",
    }
    params = {"language": lang_code, "format": "detailed"}
    resp = _requests.post(
        url, headers=headers, params=params, data=audio_bytes, timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    # Azure returns DisplayText at the top level for conversation recognition
    transcript = data.get("DisplayText") or ""
    if not transcript:
        # Fallback: NBest array
        nbest = data.get("NBest") or []
        if nbest:
            transcript = nbest[0].get("Display") or nbest[0].get("Lexical") or ""
    return {"transcript": transcript}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _bcp47(language: str) -> str:
    """Normalise a language string to a full BCP-47 tag."""
    lang = (language or "en").lower()
    if "-" in lang:
        # already a full tag like "en-us" — uppercase region part
        parts = lang.split("-", 1)
        return f"{parts[0]}-{parts[1].upper()}"
    # bare ISO-639-1 → add default region
    _map = {
        "ar": "ar-SA",
        "en": "en-US",
        "ur": "ur-PK",
        "fr": "fr-FR",
        "de": "de-DE",
        "es": "es-ES",
        "zh": "zh-CN",
        "hi": "hi-IN",
    }
    return _map.get(lang, f"{lang}-{lang.upper()}")
