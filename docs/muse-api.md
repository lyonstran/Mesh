# Muse API reference (Meta Model API)

Summarized from Meta's developer docs on 2026-09-26:
- Overview: https://dev.meta.ai/docs/overview
- Models: https://dev.meta.ai/docs/models
- API reference: https://dev.meta.ai/docs/api-reference

Only facts stated in those pages are recorded here. Anything missing is marked `TODO(HUMAN)`. Don't fill gaps by guessing (PLAN.md §14.1).

## Basics
- **Base URL:** `https://api.meta.ai/v1`
- **Auth:** `Authorization: Bearer $MODEL_API_KEY` (our env var: `MUSE_API_KEY`)
- **Compatibility:** "drop-in compatible with the OpenAI SDK, the Anthropic SDK, and OpenAI-compatible agent CLIs."

## Models
| Model | ID |
|---|---|
| Muse Spark (text, recommended) | `muse-spark-1.3` |
| Muse Spark (older) | `muse-spark-1.2`, `muse-spark-1.1` |
| Muse Spark (contributor tier) | `muse-spark-1.3-contributor`, `muse-spark-1.2-contributor` |
| Muse Voice Transcribe | `muse-voice-transcribe-1.0` |
| Muse Image | `muse-image-1.0` |
| Segment Anything | `sam-3.1` |

Muse Spark context window: 1,048,576 tokens. The docs list "structured output" among Spark's capabilities.

## Endpoints we use
### Chat Completions (OpenAI-compatible)
`POST /v1/chat/completions` with the standard OpenAI messages-array format:

```json
{"model": "muse-spark-1.3", "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}], "temperature": 0.2}
```

The response uses the OpenAI shape: `choices[0].message.content`. This is what `backend/app/ai/muse.py` implements.

Request parameters we use, from the `CreateChatCompletionRequest` schema (https://dev.meta.ai/docs/api-reference/chat-completions/schemas, read 2026-09-27):
- `reasoning_effort`: enum `none | minimal | low | medium | high | xhigh | max`, nullable. "Reasoning intensity level."
- `response_format`: `ResponseFormatText | ResponseFormatJsonSchema | ResponseFormatJsonObject`. "Constrains the format of the model's output."
- `max_completion_tokens`: integer. "Upper bound on the tokens the model may generate for a completion." (Not used yet.)

Observed against the live API (2026-09-27), not stated in the docs:
- `muse-spark-1.3` rejects `reasoning_effort: "none"` with HTTP 400 ("Supported values: [minimal, low, medium, high, x…").
- Spark reasons before answering. The response reports it as `usage.completion_tokens_details.reasoning_tokens`. For a triage call at the default effort, about 875 of 915 output tokens were reasoning, and the call took 10–25 s. At `minimal` it took about 2 s with the same or better labels. `backend/app/ai/muse.py` uses `minimal` plus `{"type": "json_object"}` for structured calls, and still validates the JSON with pydantic (PLAN.md §8).
- The message object has `content`, `refusal` and `role`.

- `TODO(HUMAN)`: the `ResponseFormatJsonSchema` fields (for strict schema output) weren't expanded on the schema page, so we use `json_object` only.

Other text endpoints exist but we don't use them yet: `POST /v1/responses` (Responses API) and `POST /v1/messages` (Anthropic-compatible).

### Embeddings
**There is no embeddings endpoint or embedding model** in the Meta Model API. Mesh computes embeddings locally with fastembed (PLAN.md §0.1).

### Transcription
From "Transcribe a recording" (https://dev.meta.ai/docs/api-reference/voice/transcribe) and the voice schemas page (https://dev.meta.ai/docs/api-reference/voice/schemas), read 2026-09-27:

- **Path:** `POST /v1/asr/transcribe`. The API reference page lives under `/voice/`, but the documented path is `/asr/transcribe`, which resolves the earlier conflict. The live API answered on it (below).
- **Auth:** `Authorization: Bearer $MODEL_API_KEY`.
- **Body:** `multipart/form-data` with two parts:
  - `request`: JSON with these fields:
    - `model` (required): `muse-voice-transcribe-1.0`;
    - `audioEncoding` (required): enum, `WAV` only;
    - `mode`: `PUSH_TO_TALK` (default), `ENDPOINTING` or `DIARIZATION`;
    - `keywords`: string[], "terms to bias recognition toward";
    - `languageBias`: string[], "languages to bias transcription toward, each as a language name";
    - `partialMode`: `CUMULATIVE` (default) or `DELTA`;
    - `emitAudioProgress`: bool, default true.
  - `audio`: the WAV file. The WAV must be "mono integer PCM at 16 kHz or 24 kHz".
- **Limits:** 10 minutes of audio, 32 MB request body.
- **Query:** optional `sessionId`.
- **Response:** the `Accept` header picks `application/json` (buffered), `text/event-stream` or `text/plain`. We use JSON, which is a `TranscribeResponse`:
  - `sessionId`;
  - `transcript`: "final transcript for the whole clip";
  - `audioDurationMs`;
  - `turns[]`.
- **Errors:**
  - 400: unsupported audio, over 10 minutes, or bad multipart;
  - 406: bad `Accept`;
  - 413: body over 32 MB;
  - 429: rate limited;
  - 500: transcription failed or timed out.
- **Not documented:** a language *code* field (only `languageBias` names), or any audio format other than WAV.

Observed against the live API (2026-09-27):
- A 7.1 s, 16 kHz mono WAV sent with `languageBias: ["English"]` and `Accept: application/json` returned 200 in about 3.5 s, and the transcript was word for word.
- `turns` came back empty in `PUSH_TO_TALK` mode.
- The real response is saved as `backend/tests/fixtures/muse_transcribe.json`.
- Browsers record WebM/Opus (Chrome, Android) or MP4/AAC (Safari, iOS), never WAV. So the frontend decodes the recording and re-encodes it as 16 kHz mono 16-bit WAV before uploading (`frontend/src/lib/wav.ts`). No `ffmpeg` is needed on the server.
- Realtime streaming (`/v1/asr/realtime`, `PCM_16KHZ`/`PCM_24KHZ`) exists but is unused.

## Other endpoints listed (unused)
- Files: `POST/GET /v1/files`, `GET/DELETE /v1/files/{file_id}`
- Images: `POST /v1/images`, `POST /v1/images/edit`
- Models: `GET /v1/models`, `GET /v1/models/{model_id}`
- Status: `GET /v1/status`
