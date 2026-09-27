"""Voice (PLAN.md §12): transcription and read-aloud, with the providers faked at the HTTP layer.

tests/fixtures/muse_transcribe.json is a real Muse Voice Transcribe response (2026-09-27), not a hand-written shape.
"""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.services import voice

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "muse_transcribe.json").read_text(encoding="utf-8"))
WAV = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 100


@pytest.fixture
def keys(monkeypatch, tmp_path):
    monkeypatch.setenv("MUSE_API_KEY", "test-muse")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-11")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "voice123")
    monkeypatch.setattr(voice, "TTS_CACHE_DIR", tmp_path)
    get_settings.cache_clear()


def _serve(monkeypatch, handler):
    calls: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    monkeypatch.setattr(voice, "_transport", httpx.MockTransport(record))
    return calls


# --- configuration --------------------------------------------------------------


def test_status_without_keys_hides_both():
    assert voice.status() == {"transcribe": False, "speak": False}


def test_status_with_keys(keys):
    assert voice.status() == {"transcribe": True, "speak": True}


async def test_unconfigured_raises_unavailable():
    with pytest.raises(voice.VoiceUnavailable):
        await voice.transcribe(WAV)
    with pytest.raises(voice.VoiceUnavailable):
        await voice.speak("hello")


def test_status_endpoint_works_without_keys():
    assert TestClient(app).get("/api/voice/status").json() == {"transcribe": False, "speak": False}


def test_voice_endpoints_need_a_session():
    client = TestClient(app)
    assert client.post("/api/voice/speak", json={"text": "hi"}).status_code in (401, 503)
    assert client.post("/api/voice/transcribe", files={"audio": ("a.wav", WAV, "audio/wav")}).status_code in (401, 503)


@pytest.mark.parametrize(
    ("line", "expected"),
    [("ELEVENLABS_API_KEY=               # TODO(HUMAN)", ""), ("ELEVENLABS_API_KEY=abc123", "abc123")],
)
def test_env_placeholder_comments_are_unset(tmp_path, monkeypatch, line, expected):
    monkeypatch.delenv("ELEVENLABS_API_KEY")  # the real environment wins over the file; read only the file here
    env = tmp_path / ".env"
    env.write_text(line + "\n", encoding="utf-8")
    assert Settings(_env_file=env).elevenlabs_api_key == expected


# --- transcription -----------------------------------------------------------------


def test_parse_real_muse_response():
    assert voice.parse_transcript(FIXTURE).startswith("A tree fell across my driveway")


def test_is_wav():
    assert voice.is_wav(WAV)
    assert not voice.is_wav(b"\x1aE\xdf\xa3" + b"\x00" * 100)  # WebM
    assert not voice.is_wav(b"RIFF")


@pytest.mark.parametrize(("language", "bias"), [("es", ["Spanish", "English"]), ("en", ["English"]), ("fr", ["English"]), (None, ["English"])])
def test_language_bias(language, bias):
    assert voice.language_bias(language) == bias


async def test_transcribe_sends_the_documented_request(keys, monkeypatch):
    calls = _serve(monkeypatch, lambda r: httpx.Response(200, json=FIXTURE))
    assert await voice.transcribe(WAV, "es") == FIXTURE["transcript"]
    [req] = calls
    assert req.url.path == "/v1/asr/transcribe"
    assert req.headers["authorization"] == "Bearer test-muse"
    body = req.content.decode("latin-1")
    assert '"audioEncoding": "WAV"' in body and '"languageBias": ["Spanish", "English"]' in body
    assert 'name="audio"' in body and 'name="request"' in body


async def test_transcribe_retries_once_on_5xx(keys, monkeypatch):
    responses = iter([httpx.Response(503), httpx.Response(200, json=FIXTURE)])
    calls = _serve(monkeypatch, lambda r: next(responses))
    assert await voice.transcribe(WAV) == FIXTURE["transcript"]
    assert len(calls) == 2


async def test_transcribe_bad_audio_is_flagged(keys, monkeypatch):
    _serve(monkeypatch, lambda r: httpx.Response(400, json={"error": "unsupported audio"}))
    with pytest.raises(voice.VoiceError) as exc:
        await voice.transcribe(WAV)
    assert exc.value.bad_input


async def test_transcribe_network_failure_is_a_voice_error(keys, monkeypatch):
    def fail(request):
        raise httpx.ConnectError("down")

    _serve(monkeypatch, fail)
    with pytest.raises(voice.VoiceError):
        await voice.transcribe(WAV)


# --- read-aloud -----------------------------------------------------------------------


async def test_speak_calls_elevenlabs_and_caches(keys, monkeypatch):
    calls = _serve(monkeypatch, lambda r: httpx.Response(200, content=b"ID3mp3data"))
    assert await voice.speak("Marcus is helping you", "es") == b"ID3mp3data"
    assert await voice.speak("Marcus is helping you", "es") == b"ID3mp3data"
    assert len(calls) == 1  # second call came from the disk cache
    [req] = calls
    assert req.url.path == "/v1/text-to-speech/voice123"
    assert req.headers["xi-api-key"] == "test-11"
    assert json.loads(req.content) == {"text": "Marcus is helping you", "model_id": "eleven_multilingual_v2", "language_code": "es"}


async def test_speak_failure_is_a_voice_error(keys, monkeypatch):
    _serve(monkeypatch, lambda r: httpx.Response(401, json={"detail": "invalid key"}))
    with pytest.raises(voice.VoiceError):
        await voice.speak("hello")
