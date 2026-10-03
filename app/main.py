"""
MoonTales API — FastAPI application entry point.
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.story import router as story_router
from app.core.firebase_auth import initialize_firebase

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Startup:
    - Initialise Firebase Admin SDK (once).

    Shutdown:
    - Nothing required currently (SQLAlchemy engine is closed automatically).
    """
    logger.info("🌙 MoonTales API starting up...")
    initialize_firebase()
    logger.info("Firebase Admin SDK ready.")
    yield
    logger.info("🌙 MoonTales API shutting down.")


# ── Application factory ───────────────────────────────────────────────────────

app = FastAPI(
    title="MoonTales API",
    description=(
        "AI-powered children's story generation service. "
        "Combines Gemini 2.0 Flash (story), Imagen 3 (illustrations), "
        "and ElevenLabs (narration) to create personalised bedtime stories."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(story_router)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["health"], summary="Health check")
async def health_check() -> dict:
    """Returns a simple liveness signal and API version."""
    return {"status": "ok", "version": "0.1.0"}
