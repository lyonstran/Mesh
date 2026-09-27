# ElevenLabs text-to-speech reference

Summarized from https://elevenlabs.io/docs/api-reference/text-to-speech/convert, read on 2026-09-27. Only what that page states is recorded here. `backend/app/services/voice.py` implements it (PLAN.md §12).

## Convert text to speech
`POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`

- **Auth:** the `xi-api-key` header (our `ELEVENLABS_API_KEY`). `voice_id` comes from `ELEVENLABS_VOICE_ID`.
- **Body (JSON):**
  - `text` (required): "The text that will get converted into speech."
  - `model_id`: defaults to `eleven_multilingual_v2`, which is our `ELEVENLABS_MODEL_ID`. The list of models is at `GET /v1/models`.
  - `language_code`: ISO 639-1, "used to enforce a language for the model and text normalization." We send it for `en` and `es`.
  - Also available, unused: `voice_settings`, `pronunciation_dictionary_locators`, `seed`, `previous_text`/`next_text`, `previous_request_ids`/`next_request_ids`, `apply_text_normalization`, `apply_language_text_normalization`.
- **Query:** `output_format`, written as `codec_sample_rate_bitrate`. It defaults to `mp3_44100_128`, which is what we use. Options include MP3, Opus, PCM, µ-law/A-law and WAV (`wav_16000` … `wav_48000`).
- **Response:** 200 returns the audio file as binary. 422 is a validation error.

## Not verified yet
- `TODO(HUMAN)`: the team's key and voice. The voice ID must be a multilingual voice from the ElevenLabs voice library. Until both are set, `/api/voice/speak` returns 503 `VOICE_UNAVAILABLE` and the UI hides "Tap to hear".
- Newer models (`eleven_flash_v2_5`, `eleven_turbo_v2_5`, `eleven_v3`) aren't mentioned on this page, so we stay on the documented default.
