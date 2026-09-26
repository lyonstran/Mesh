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

- `TODO(HUMAN)`: the pages didn't spell out `response_format`/`json_schema` parameters. Until confirmed, we ask for JSON in the prompt and validate it with pydantic (PLAN.md §8).

Other text endpoints exist but we don't use them yet: `POST /v1/responses` (Responses API) and `POST /v1/messages` (Anthropic-compatible).

### Embeddings
**There is no embeddings endpoint or embedding model** in the Meta Model API. Mesh computes embeddings locally with fastembed (PLAN.md §0.1).

### Transcription (post-MVP)
- `TODO(HUMAN)`: **the docs conflict on the path.** The overview lists `POST /v1/asr/transcribe` (plus realtime `wss://api.meta.ai/v1/asr/realtime`). The API reference lists `POST /v1/voice/transcribe` and `POST /v1/voice/realtime`.
- `TODO(HUMAN)`: the multipart field names, accepted audio formats, and response shape weren't shown. See https://dev.meta.ai/docs/speech-to-text.

## Other endpoints listed (unused)
- Files: `POST/GET /v1/files`, `GET/DELETE /v1/files/{file_id}`
- Images: `POST /v1/images`, `POST /v1/images/edit`
- Models: `GET /v1/models`, `GET /v1/models/{model_id}`
- Status: `GET /v1/status`
