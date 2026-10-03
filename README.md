# 🌙 MoonTales API

> AI-powered children's story generation service — Gemini 2.0 Flash · Imagen 3 · ElevenLabs

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

---

## Overview

MoonTales generates personalised, illustrated, narrated bedtime stories for children aged 3–8. Given a set of story cues (e.g. `"brave girl"`, `"friendly dragon"`, `"enchanted forest"`), the API orchestrates four AI systems in parallel and returns a single unified data contract ready for a React Native app to render.

| Step | AI System | What it produces |
|---|---|---|
| 1 — Write | Gemini 2.0 Flash | Page text + expressive audio script + image prompt |
| 2 — Illustrate | Imagen 3 | One illustration per page (consistent character via fixed seed) |
| 3 — Narrate | ElevenLabs | MP3 narration + character-level word timing (ms) |
| 4 — Store | Google Cloud Storage | Signed URLs returned to the app (1 h expiry) |

Generation is **fully asynchronous**. `POST /api/story` returns a job ID immediately (`202 Accepted`). The React Native app polls `GET /api/story/{id}` until `status` becomes `completed`.

---

## Generation Pipeline

```
POST /api/story
      │
      ▼
[DB] Create Story (status=pending)
      │
      ▼ background task
[Gemini] Generate N pages ──► JSON array: { text, audio_text, image_prompt }
      │
      │  random seed chosen once, shared across all pages
      │
      ├─ page 1 ─┬─ [Imagen 3]    generate_image(prompt, seed)
      │           └─ [ElevenLabs] generate_audio(audio_text)  ◄─ parallel
      ├─ page 2 ─┬─ [Imagen 3]    ...
      │           └─ [ElevenLabs] ...
      └─ page N  ─── ...
      │
      ▼ all complete
[GCS] Upload image + audio per page ◄─ parallel
      │
      ▼
[DB] Update Story: status=completed, pages=[...assembled...]
      │
      ▼
GET /api/story/{id} → full StoryResponse with signed URLs + alignment
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI 0.115+ with uvicorn |
| LLM | Gemini 2.0 Flash (`gemini-2.0-flash`) |
| Image Generation | Imagen 3 (`imagen-3.0-generate-001`) |
| Text-to-Speech | ElevenLabs `/v1/text-to-speech/{id}/with-timestamps` |
| Database | PostgreSQL 15+ via SQLAlchemy 2.x async + asyncpg |
| Migrations | Alembic |
| Storage | Google Cloud Storage (v4 signed URLs) |
| Auth | Firebase Admin SDK (Bearer token verification) |
| Background Jobs | FastAPI `BackgroundTasks` + `asyncio.gather` |

---

## Project Structure

```
moontales-api/
├── app/
│   ├── main.py                    # FastAPI app, lifespan, CORS, /health
│   ├── config.py                  # pydantic-settings (all env vars)
│   ├── database.py                # Async SQLAlchemy engine + session factory
│   ├── models/
│   │   └── story.py               # Story ORM model (UUID PK, JSON cols, soft-delete)
│   ├── schemas/
│   │   └── story.py               # StoryCreateRequest · StoryPage · AlignmentData · StoryResponse
│   ├── api/
│   │   ├── deps.py                # get_current_user Firebase dependency
│   │   └── v1/
│   │       └── story.py           # POST · GET · GET-list · PUT · DELETE
│   ├── services/
│   │   ├── llm_service.py         # Gemini 2.0 Flash — structured JSON story output
│   │   ├── image_service.py       # Imagen 3 — seed-consistent illustrations, 3× retry
│   │   ├── audio_service.py       # ElevenLabs — MP3 + ms alignment conversion
│   │   ├── storage_service.py     # GCS upload + v4 signed URL generation
│   │   └── story_orchestrator.py  # Background pipeline: asyncio.gather per page
│   └── core/
│       └── firebase_auth.py       # Firebase Admin init + token verification
├── alembic/
│   ├── env.py                     # Async Alembic config
│   └── versions/
│       └── 001_create_stories_table.py
├── alembic.ini
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Setup

### Prerequisites

- **Python 3.11+**
- **PostgreSQL** running locally or accessible remotely
- **Google Cloud project** with:
  - Gemini API enabled ([AI Studio](https://aistudio.google.com))
  - Imagen 3 access (may require allowlisting — see [Vertex AI docs](https://cloud.google.com/vertex-ai/generative-ai/docs/image/generate-images))
  - A GCS bucket
  - A service account with the `Storage Object Admin` IAM role
- **Firebase project** — for verifying React Native auth tokens
- **ElevenLabs account** — with a cloned narrator voice (see [Voice Cloning](#cloning-your-elevenlabs-voice))

---

### 1. Clone & install

```bash
git clone <your-repo-url>
cd moontales-api

python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

---

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in all values in `.env`:

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://user:pass@host:5432/moontales` |
| `GOOGLE_AI_API_KEY` | ✅ | Google AI Studio key — used for both Gemini and Imagen |
| `ELEVENLABS_API_KEY` | ✅ | ElevenLabs API key |
| `DEFAULT_VOICE_ID` | ✅ | Your cloned ElevenLabs voice ID |
| `GCS_BUCKET_NAME` | ✅ | GCS bucket that stores story assets |
| `GCS_PROJECT_ID` | ✅ | GCP project ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | ✅ | Full JSON string of your Firebase service account key |
| `APP_ENV` | — | `development` (default) or `production` |
| `DEFAULT_PAGE_COUNT` | — | Default pages per story (default: `5`, max: `20`) |
| `SIGNED_URL_EXPIRY_HOURS` | — | Signed URL lifetime in hours (default: `1`) |

> **Tip:** `FIREBASE_SERVICE_ACCOUNT_JSON` should be the raw JSON on a single line, e.g.:
> ```
> FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"..."}
> ```
> Download it from Firebase Console → Project Settings → Service Accounts → Generate new private key.

---

### 3. GCS bucket setup

Make sure your service account can write to the bucket and generate signed URLs:

```bash
# Create bucket
gsutil mb -l us-central1 gs://your-bucket-name

# Grant service account access
gsutil iam ch serviceAccount:your-sa@project.iam.gserviceaccount.com:objectAdmin gs://your-bucket-name
```

If your React Native app fetches assets directly (not through the API), configure CORS on the bucket:

```json
// cors.json
[{
  "origin": ["*"],
  "method": ["GET"],
  "maxAgeSeconds": 3600
}]
```
```bash
gsutil cors set cors.json gs://your-bucket-name
```

---

### 4. Run database migrations

```bash
alembic upgrade head
```

---

### 5. Start the server

```bash
# Development (auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

| URL | Description |
|---|---|
| `http://localhost:8000/docs` | Swagger UI (interactive) |
| `http://localhost:8000/redoc` | ReDoc reference |
| `http://localhost:8000/health` | Health check |

---

## API Reference

All endpoints except `/health` require a Firebase ID token:

```
Authorization: Bearer <firebase-id-token>
```

---

### `GET /health`

Liveness check — no auth required.

```http
GET /health
```

```json
{ "status": "ok", "version": "0.1.0" }
```

---

### `POST /api/story`

Start a story generation job. Returns immediately — generation runs in the background.

```http
POST /api/story
Authorization: Bearer <token>
Content-Type: application/json
```

**Request body:**

```json
{
  "user_id": "firebase-uid-abc123",
  "user_cues": ["brave girl", "friendly dragon", "enchanted forest"],
  "page_count": 5,
  "voice_id": "your-elevenlabs-voice-id"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `user_id` | string | ✅ | Must match the Firebase token UID |
| `user_cues` | string[] | ✅ | Story themes / characters / settings |
| `page_count` | integer | — | Pages to generate (1–20, default: 5) |
| `voice_id` | string | ✅ | ElevenLabs voice ID for narration |

**Response `202 Accepted`:**

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "pending"
}
```

---

### `GET /api/story/{story_id}`

Fetch a story by ID. Returns the full story once complete.

```http
GET /api/story/3fa85f64-5717-4562-b3fc-2c963f66afa6
Authorization: Bearer <token>
```

**Response while in progress:**

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "user_id": "firebase-uid-abc123",
  "status": "generating",
  "title": null,
  "page_count": 5,
  "pages": null,
  "created_at": "2026-09-29T13:00:00Z",
  "updated_at": "2026-09-29T13:00:05Z",
  "error_message": null
}
```

**Response when `status=completed`:**

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "user_id": "firebase-uid-abc123",
  "status": "completed",
  "title": "Luna and the Friendly Dragon",
  "page_count": 5,
  "pages": [
    {
      "page_number": 1,
      "text": "Once upon a time, brave little Luna lived at the edge of an enchanted forest.",
      "audio_text": "[warmly] Once upon a time, [quietly] brave little Luna lived at the edge of an [excited] enchanted forest.",
      "image_prompt": "CHARACTER DESIGN (keep exactly consistent across all images): Luna, a 6-year-old girl with long curly auburn hair tied in two loose pigtails, bright green eyes, wearing a yellow raincoat with white star buttons and red rubber boots...\nSCENE: Luna stands at the mossy stone edge of a glowing forest, one foot raised mid-step, eyes wide with wonder. Fireflies drift around her.\nSTYLE: Soft watercolor children's book illustration, warm golden lighting, whimsical, safe for children, storybook quality",
      "image_url": "https://storage.googleapis.com/moontales-assets/stories/3fa8.../page_1/image.png?X-Goog-Signature=...",
      "audio_url": "https://storage.googleapis.com/moontales-assets/stories/3fa8.../page_1/audio.mp3?X-Goog-Signature=...",
      "alignment": {
        "characters": ["O", "n", "c", "e", " ", "u", "p", "o", "n", ...],
        "character_start_times_ms": [0.0, 45.0, 92.0, 138.0, ...],
        "character_end_times_ms": [45.0, 92.0, 138.0, 184.0, ...]
      }
    }
  ],
  "created_at": "2026-09-29T13:00:00Z",
  "updated_at": "2026-09-29T13:02:30Z",
  "error_message": null
}
```

**Status values:**

| Status | Meaning |
|---|---|
| `pending` | Job created, not started yet |
| `generating` | Background pipeline running |
| `completed` | All pages generated, assets uploaded |
| `failed` | Pipeline error — see `error_message` |

> **Polling strategy for React Native:** Poll every 3–5 seconds. Typical generation time is 15–45 seconds depending on page count and API latency.

---

### `GET /api/stories`

List all stories for the authenticated user, newest first.

```http
GET /api/stories?user_id=firebase-uid-abc123
Authorization: Bearer <token>
```

| Query param | Required | Description |
|---|---|---|
| `user_id` | — | Must match token UID if provided. Defaults to token UID. |

**Response:** Array of `StoryResponse` objects (same shape as `GET /api/story/{id}`).

---

### `PUT /api/story/{story_id}`

Update a story's title.

```http
PUT /api/story/3fa85f64-5717-4562-b3fc-2c963f66afa6
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{ "title": "Luna and the Friendly Dragon" }
```

**Response:** Updated `StoryResponse`.

---

### `DELETE /api/story/{story_id}`

Soft-delete a story. The record is retained in the database with `deleted_at` set; it won't appear in list or get queries.

```http
DELETE /api/story/3fa85f64-5717-4562-b3fc-2c963f66afa6
Authorization: Bearer <token>
```

**Response:** `204 No Content`

---

## Data Contract Details

### `AlignmentData`

The `alignment` field on each page enables **karaoke-style text highlighting** in the React Native app — highlight each character as the audio plays.

```typescript
interface AlignmentData {
  characters: string[];               // individual characters of the spoken text
  character_start_times_ms: number[]; // when each character starts (ms)
  character_end_times_ms: number[];   // when each character ends (ms)
}
```

All three arrays have the same length. Map `characters` back to words by detecting space characters.

### Signed URLs

`image_url` and `audio_url` are GCS v4 signed URLs valid for **1 hour** by default (configurable via `SIGNED_URL_EXPIRY_HOURS`). Refresh the story object before the URLs expire, or implement a `/api/story/{id}/refresh-urls` endpoint if needed.

### Character Consistency (Imagen 3 Seed)

A single random integer seed is chosen per story at generation time and passed to every `imagen.generate_images(seed=seed)` call. Combined with the locked `CHARACTER DESIGN` block embedded in every `image_prompt`, this enforces visual consistency across all pages.

---

## Cloning Your ElevenLabs Voice

1. Log in to [ElevenLabs](https://elevenlabs.io) → **VoiceLab → Add Voice → Instant Voice Cloning**
2. Upload **1–5 minutes** of clean audio of the narrator's voice (MP3 or WAV)
3. Copy the **Voice ID** from the voice settings page
4. Set it as `DEFAULT_VOICE_ID` in `.env`, or pass it per-request in the `voice_id` field

> **Recording tips:** Quiet room, consistent mic distance, natural storytelling pace, some variation in pitch and tone. Avoid background music or reverb.

### Audio bracket tags

The LLM embeds expressive direction tags in `audio_text` that ElevenLabs interprets as voice emotion cues:

| Tag | Effect |
|---|---|
| `[warmly]` | Warm, gentle narrator tone |
| `[quietly]` | Softer, hushed delivery |
| `[whispers]` | Near-whisper |
| `[excited]` | Energetic, bright |
| `[dramatically]` | Heightened tension |
| `[gasps]` | Audible gasp |
| `[laughs]` | Laughter before the line |
| `[giggles]` | Light giggle |
| `[sighs]` | Contented or wistful sigh |

---

## Error Handling

The API returns standard HTTP error shapes:

```json
{
  "detail": "Story not found."
}
```

| HTTP Status | Cause |
|---|---|
| `401 Unauthorized` | Missing or expired Firebase token |
| `403 Forbidden` | Token UID doesn't match `user_id` in request |
| `404 Not Found` | Story ID doesn't exist or was soft-deleted |
| `422 Unprocessable Entity` | Invalid request body or malformed UUID |
| `202 Accepted` | Story job created (check `status` field for failures) |

If the background pipeline fails, `status` will be `failed` and `error_message` will contain the exception detail.

---

## Development

### Running tests

```bash
pytest
```

### Applying a new migration

```bash
alembic revision --autogenerate -m "add_column_foo"
alembic upgrade head
```

### Resetting the database (dev only)

```bash
alembic downgrade base
alembic upgrade head
```

### Environment variables for local dev

For local development without a real Firebase token, you can temporarily bypass auth by checking `APP_ENV=development` in `app/api/deps.py` and returning a mock user — **never do this in production**.

---

## License

MIT
