"""Voice in and out (PLAN.md §12): Muse Voice Transcribe and ElevenLabs text-to-speech.

Implemented only from docs/muse-api.md and docs/elevenlabs-api.md (CLAUDE.md rule 1). Either side is optional:
with its key unset it raises VoiceUnavailable, the router answers 503 VOICE_UNAVAILABLE and the UI hides the button.
"""

import hashlib
import json
import logging
import os
from pathlib import Path

import httpx

from app.config import get_settings

log = logging.getLogger("mesh.voice")

# A 60 s clip takes a few seconds to transcribe; connecting still fails fast (one retry, CLAUDE.md).
_TIMEOUT = httpx.Timeout(20.0, connect=8.0)
_transport: httpx.AsyncBaseTransport | None = None  # tests swap in httpx.MockTransport

# The browser sends 16 kHz mono 16-bit WAV (32,000 bytes/s), so 60 s is ~1.9 MB. Muse itself allows 10 min / 32 MB.
MAX_AUDIO_BYTES = 3_000_000
MAX_SPEAK_CHARS = 500

# Muse's languageBias takes language names, not codes (docs/muse-api.md).
_LANGUAGE_NAMES = {"en": "English", "es": "Spanish"}

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
TTS_CACHE_DIR = Path(__file__).resolve().parents[2] / "media" / "tts"  # backend/media is gitignored and a volume


class VoiceUnavailable(Exception):
    """The provider's key isn't configured."""


class VoiceError(Exception):
    """The provider was reached but the call failed."""

    def __init__(self, message: str, *, bad_input: bool = False) -> None:
        super().__init__(message)
        self.bad_input = bad_input


def status() -> dict:
    settings = get_settings()
    return {
        "transcribe": bool(settings.muse_api_key),
        "speak": bool(settings.elevenlabs_api_key and settings.elevenlabs_voice_id),
    }


def is_wav(data: bytes) -> bool:
    return len(data) > 44 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"


def language_bias(language: str | None) -> list[str]:
    """Bias toward the speaker's language, and English as the app's other language."""
    names = [_LANGUAGE_NAMES[language]] if language in _LANGUAGE_NAMES else []
    return names if "English" in names else [*names, "English"]


def parse_transcript(payload: dict) -> str:
    return str(payload["transcript"]).strip()


async def _post(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    """POST with one retry on network errors and 5xx. 4xx is returned for the caller to classify."""
    last: Exception | None = None
    for _ in range(2):
        try:
            resp = await client.post(url, **kwargs)
        except httpx.TransportError as e:
            last = e
            continue
        if resp.status_code < 500:
            return resp
        last = VoiceError(f"HTTP {resp.status_code}")
    raise VoiceError(f"{type(last).__name__}: {last}")


async def transcribe(wav: bytes, language: str | None = None) -> str:
    settings = get_settings()
    if not settings.muse_api_key:
        raise VoiceUnavailable("MUSE_API_KEY is not set")
    request = {
        "model": settings.muse_transcribe_model,
        "audioEncoding": "WAV",
        "mode": "PUSH_TO_TALK",
        "languageBias": language_bias(language),
        "emitAudioProgress": False,
    }
    files = {
        "request": (None, json.dumps(request), "application/json"),
        "audio": ("audio.wav", wav, "audio/wav"),
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT, transport=_transport) as client:
        resp = await _post(
            client,
            settings.muse_base_url.rstrip("/") + "/asr/transcribe",
            files=files,
            headers={"Authorization": f"Bearer {settings.muse_api_key}", "Accept": "application/json"},
        )
    if resp.status_code != 200:
        log.warning("Muse transcribe returned %s: %s", resp.status_code, resp.text[:300])
        raise VoiceError(f"Muse transcribe returned {resp.status_code}", bad_input=resp.status_code in (400, 413))
    try:
        return parse_transcript(resp.json())
    except (KeyError, ValueError) as e:
        raise VoiceError(f"Unexpected transcribe response: {e}") from e


def _cache_path(text: str, language: str, voice_id: str, model_id: str) -> Path:
    key = hashlib.sha256(f"{voice_id}\n{model_id}\n{language}\n{text}".encode()).hexdigest()
    return TTS_CACHE_DIR / f"{key}.mp3"


async def speak(text: str, language: str = "en") -> bytes:
    """MP3 audio for `text`. Cached on disk, so repeating a status line costs nothing."""
    settings = get_settings()
    if not (settings.elevenlabs_api_key and settings.elevenlabs_voice_id):
        raise VoiceUnavailable("ELEVENLABS_API_KEY or ELEVENLABS_VOICE_ID is not set")
    text = text.strip()[:MAX_SPEAK_CHARS]
    path = _cache_path(text, language, settings.elevenlabs_voice_id, settings.elevenlabs_model_id)
    if path.exists():
        return path.read_bytes()

    body: dict = {"text": text, "model_id": settings.elevenlabs_model_id}
    if language in _LANGUAGE_NAMES:
        body["language_code"] = language
    async with httpx.AsyncClient(timeout=_TIMEOUT, transport=_transport) as client:
        resp = await _post(
            client,
            ELEVENLABS_URL.format(voice_id=settings.elevenlabs_voice_id),
            params={"output_format": "mp3_44100_128"},
            json=body,
            headers={"xi-api-key": settings.elevenlabs_api_key, "Accept": "audio/mpeg"},
        )
    if resp.status_code != 200:
        log.warning("ElevenLabs returned %s: %s", resp.status_code, resp.text[:300])
        raise VoiceError(f"ElevenLabs returned {resp.status_code}")

    audio = resp.content
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(audio)
        os.replace(tmp, path)  # atomic, so a concurrent reader never sees half a file
    except OSError:
        log.warning("Couldn't cache TTS audio at %s", path, exc_info=True)
    return audio
