from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.deps import require_onboarded
from app.errors import APIError
from app.services import voice

router = APIRouter(prefix="/api/voice")


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=voice.MAX_SPEAK_CHARS)
    language: str = Field("en", min_length=2, max_length=10)


@router.get("/status")
async def voice_status() -> dict:
    """Which voice features are configured, so the UI can hide the ones that aren't."""
    return voice.status()


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), user: dict = Depends(require_onboarded)) -> dict:
    """16 kHz mono WAV from the browser → text the requester can edit before previewing (PLAN.md §12)."""
    data = await audio.read(voice.MAX_AUDIO_BYTES + 1)
    if len(data) > voice.MAX_AUDIO_BYTES:
        raise APIError(413, "AUDIO_TOO_LONG", "Recordings can be up to about a minute")
    if not voice.is_wav(data):
        raise APIError(400, "BAD_AUDIO", "Audio must be a WAV recording")
    try:
        text = await voice.transcribe(data, user.get("language"))
    except voice.VoiceUnavailable:
        raise APIError(503, "VOICE_UNAVAILABLE", "Voice input isn't available right now. Type your request instead.") from None
    except voice.VoiceError as e:
        if e.bad_input:
            raise APIError(400, "BAD_AUDIO", "We couldn't read that recording. Try again or type instead.") from None
        raise APIError(502, "VOICE_FAILED", "Voice input didn't work this time. Try again or type instead.") from None
    return {"text": text}


@router.post("/speak")
async def speak(body: SpeakIn, _: dict = Depends(require_onboarded)) -> Response:
    try:
        audio = await voice.speak(body.text, body.language)
    except voice.VoiceUnavailable:
        raise APIError(503, "VOICE_UNAVAILABLE", "Read-aloud isn't available right now") from None
    except voice.VoiceError:
        raise APIError(502, "VOICE_FAILED", "Read-aloud didn't work this time") from None
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=86400"})
