from datetime import datetime

from pydantic import BaseModel, Field


# ── Request schemas ────────────────────────────────────────────────────────────

class StoryCreateRequest(BaseModel):
    user_id: str
    user_cues: list[str] = Field(default_factory=list)  # e.g. ["brave girl", "dragon"]
    prompt: str | None = None  # Free-text user idea (e.g. "a shy little hedgehog")
    duration_minutes: int = Field(default=5, ge=1, le=15)
    page_count: int = Field(default=8, ge=1, le=30)
    voice_id: str | None = None  # Optional voice ID (e.g. "en-IN-Neural2-D")


class StoryUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)


# ── Supporting schemas ─────────────────────────────────────────────────────────

class AlignmentData(BaseModel):
    characters: list[str] = Field(default_factory=list)
    character_start_times_ms: list[float] = Field(default_factory=list)
    character_end_times_ms: list[float] = Field(default_factory=list)


class StoryPage(BaseModel):
    page_number: int
    text: str                                    # plain story text
    audio_text: str                              # text with [laughs], [whispers] tags
    image_prompt: str = ""
    ready: bool = False                          # True when image + audio are generated & uploaded
    image_url: str | None = None                 # signed GCS URL (populated when ready)
    audio_url: str | None = None                 # signed GCS URL (populated when ready)
    alignment: AlignmentData | None = None       # character-level timing


# ── Response schemas ───────────────────────────────────────────────────────────

class StoryStatusResponse(BaseModel):
    """Lightweight response returned immediately after POST /api/story."""
    id: str
    status: str


class StoryResponse(BaseModel):
    id: str
    user_id: str
    status: str  # pending | generating | completed | failed
    title: str | None = None
    page_count: int
    pages_ready: int = 0
    pages: list[StoryPage] | None = None
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None

    model_config = {"from_attributes": True}

