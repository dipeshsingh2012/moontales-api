# 🌙 MoonTales API

> High-performance AI children's bedtime story generation API — Gemini 3.8 Flash · Imagen 3 · GCP Cloud TTS / ElevenLabs · Progressive Streaming

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

---

## Overview

MoonTales creates personalized, illustrated, and narrated bedtime stories designed specifically to help young children (aged 3–8) wind down and drift off to sleep. 

Given a parent's voice recording, text idea, or visual cue tags, the API generates high-quality stories with:
- **Time-Based Duration**: Stories structured by reading time (e.g. 5 minutes ≈ 8 pages, ~80–95 words per page) with gradual calming pacing.
- **Optimized Image Cadence**: 1 illustration every 2nd page (odd pages 1, 3, 5, 7 receive new illustrations; even pages reuse preceding images for visual continuity and 2x generation speed).
- **Progressive Delivery**: Page 1 is ready in ~20–30s so the child can start reading immediately, while subsequent pages stream in the background.
- **Multimodal Spoken Cues**: Microphone voice recordings transcribed directly via Gemini 3.8 Flash into polished story prompts, themes, characters, and visual cue chips.
- **Zero-Expiry Signed URLs**: Dynamic GCS signed URLs generated on-the-fly on every GET request so links never expire.
- **Synchronized Karaoke Alignment**: Word-level character timestamp alignment for real-time text highlight synced with audio narration.

---

## Architecture & Generation Pipeline

```
           Parent Spoken Voice or Text Idea
                         │
                         ▼
        POST /api/cues/transcribe (or /extract)
        [Gemini 3.8 Flash Multimodal]
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
 Polished Prompt & Theme           Visual & Story Cues
        │                                 │
        └────────────────┬────────────────┘
                         ▼
                  POST /api/story
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
[DB] Create Story (status=pending)     Immediate HTTP 202
        │
        ▼ (Background Task)
[LLM] Generate All N Pages Text Upfront (Saved to DB)
        │
        ├─► Odd Page (1, 3, 5, 7)  ──┬─► [Imagen 3]    Generate Illustration 
        │                            └─► [TTS Engine]  GCP TTS / ElevenLabs (Parallel)
        │
        ├─► Even Page (2, 4, 6, 8) ──┬─► Reuse Preceding Odd Page Illustration
        │                            └─► [TTS Engine]  GCP TTS / ElevenLabs (Parallel)
        │
        ▼ (Atomically per page)
[DB] Update Page (ready=true)
        │
        ├─► Page 1 Ready (~20-30s) ──► Client Opens Reader Immediately!
        └─► Remaining Pages Complete in Background (Streamed via Poller)
```

---

## Tech Stack & Providers

| Layer | Primary Provider | Fallback / Alternative |
|---|---|---|
| **API Framework** | FastAPI 0.115+ (Uvicorn async) | — |
| **LLM Story Generation** | Google Gemini 3.8 Flash (`google-genai`) | OpenAI GPT-4o-mini / Groq Llama 3.3 |
| **Voice & Cue Extraction** | Gemini 3.8 Flash (Multimodal Audio) | — |
| **Illustrations** | Imagen 3 (`gemini-2.5-flash-image` / Imagen 3) | DALL-E 3 / Replicate (Flux-Schnell) |
| **Narration (TTS)** | GCP Cloud Text-to-Speech (Journey / Studio voices) | ElevenLabs (`with-timestamps`) |
| **Accents Supported** | Indian English (`en-IN-Wavenet-D`), US English | Cloned custom voices |
| **Database** | PostgreSQL 15+ via SQLAlchemy 2.x async + asyncpg | — |
| **Asset Storage** | Google Cloud Storage (canonical path + fresh v4 signing) | — |
| **Authentication** | Firebase Admin SDK (Bearer token verification) | Optional dev mode bypass |

---

## Key Endpoints

### 1. Spoken Voice & Text Cues (`/api/cues`)

#### `POST /api/cues/transcribe`
Accepts an audio recording file (`multipart/form-data`) from mobile device microphones.
- Transcribes speech and extracts structured story cues with Gemini multimodal.
- **Response**:
```json
{
  "transcription": "A puppy named Bruno goes to Mars and finds sparkly space bones",
  "prompt": "Join Bruno the adventurous puppy as he journeys into the quiet cosmos...",
  "theme": "space",
  "characters": ["Bruno (a playful puppy)", "Twinkling star friends"],
  "cues": ["sparkly space bones", "red planet", "soft cosmic dust", "bedtime lullaby"]
}
```

#### `POST /api/cues/extract`
Accepts `{ "text": "..." }` and returns the same structured cue output for text ideas.

---

### 2. Story Management (`/api/story`)

#### `POST /api/story`
Initiates asynchronous bedtime story generation.
- **Request Body**:
```json
{
  "user_id": "firebase-uid",
  "prompt": "A brave little dragon who loves flowers",
  "theme": "fantasy",
  "duration_minutes": 5,
  "user_cues": ["dragon", "magic garden", "sweet dreams"],
  "voice_id": "en-IN-Wavenet-D"
}
```
- **Response (202 Accepted)**:
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "pending"
}
```

#### `GET /api/story/{id}`
Returns story details. Generates **fresh, unexpired signed URLs** on every call.
- Pages contain `ready: boolean`. When `pages[0].ready === true`, the reader can open!

#### `GET /api/stories`
Returns all stories created by the authenticated user, ordered newest first.

#### `DELETE /api/story/{id}`
Soft-deletes a story from the library.

---

## Local Development & Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Google Cloud credentials JSON with Storage & Cloud TTS permissions
- Google AI Studio API Key (`GOOGLE_AI_API_KEY`)

### 1. Installation
```bash
git clone https://github.com/dipeshsingh2012/moontales-api.git
cd moontales-api

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

### 2. Configure Environment (`.env`)
```bash
cp .env.example .env
```
Key variables:
```ini
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/moontales
GOOGLE_AI_API_KEY=your_gemini_api_key
GCS_BUCKET_NAME=your_gcs_bucket
GCS_PROJECT_ID=your_gcp_project_id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json

TTS_PROVIDER=gcp
GCP_TTS_VOICE_NAME=en-IN-Wavenet-D
GCP_TTS_LANGUAGE_CODE=en-IN

LLM_PROVIDER=gemini
IMAGE_PROVIDER=imagen
```

### 3. Run Migrations & Start Server
```bash
alembic upgrade head

# Run server with live reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Testing

Run unit and integration tests:
```bash
pytest tests/ -v
```

---

## License

MIT License. See [LICENSE](./LICENSE) for details.
