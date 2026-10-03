"""
Story Cues API router — /api/cues
"""

import logging
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.services.cues_service import extract_text_cues, transcribe_audio_cues

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cues", tags=["cues"])


class ExtractTextCuesRequest(BaseModel):
    text: str


class CuesResponse(BaseModel):
    transcription: str
    prompt: str
    theme: str
    characters: list[str] = []
    cues: list[str] = []


@router.post("/extract", response_model=CuesResponse)
async def extract_cues(request: ExtractTextCuesRequest) -> Any:
    """Extract structured story cues, theme, characters from raw text idea."""
    if not request.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text cannot be empty.",
        )
    try:
        result = await extract_text_cues(request.text.strip())
        return result
    except Exception as exc:
        logger.exception("Failed to extract cues from text: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not extract story cues: {exc}",
        )


@router.post("/transcribe", response_model=CuesResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
) -> Any:
    """
    Transcribe spoken voice recording and extract bedtime story cues
    (prompt, theme, characters, visual cues).
    Supports m4a, mp3, wav, webm, ogg, aac audio formats.
    """
    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded audio file is empty.",
            )

        mime_type = file.content_type or "audio/m4a"
        # Normalize mime type for common mobile audio recordings
        if "m4a" in (file.filename or "") or "mp4" in mime_type or "m4a" in mime_type:
            mime_type = "audio/m4a"
        elif "mp3" in (file.filename or "") or "mpeg" in mime_type:
            mime_type = "audio/mp3"
        elif "wav" in (file.filename or "") or "wav" in mime_type:
            mime_type = "audio/wav"

        logger.info(
            "Received audio upload for transcription: filename=%s, size=%d bytes, mime=%s",
            file.filename,
            len(audio_bytes),
            mime_type,
        )

        result = await transcribe_audio_cues(audio_bytes, mime_type=mime_type)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to transcribe audio cues: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio transcription failed: {exc}",
        )
