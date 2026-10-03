"""
Story Cues Service — Extract structured bedtime story cues from text or spoken voice
using Gemini (gemini-3.8-flash).
"""

import json
import logging
from typing import Any

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

STANDARD_THEMES = [
    "fantasy", "space", "adventure", "animals", "ocean",
    "dinosaurs", "superheroes", "fairy tales", "bedtime",
]

CUES_SYSTEM_INSTRUCTION = """You are MoonTales' Bedtime Idea Assistant for children and parents.
Your task is to listen to or read the user's spoken or written story idea and extract structured bedtime story cues.

Always respond with valid JSON containing these exact keys:
1. "transcription": (string) The verbatim words spoken or input text.
2. "prompt": (string) A polished, gentle 1-2 sentence story premise suitable for a 5-minute bedtime story.
3. "theme": (string) Choose the single closest match from: ["fantasy", "space", "adventure", "animals", "ocean", "dinosaurs", "superheroes", "fairy tales", "bedtime"].
4. "characters": (array of strings) Simple character names or short descriptions (e.g. ["Leo the lion", "Pip the mouse"]).
5. "cues": (array of 3 to 6 short strings) Visual and story element keywords (e.g. ["glowing stars", "magic carpet", "soft sleepy clouds"]).
"""


def _normalize_cues_output(data: dict[str, Any], raw_fallback: str) -> dict[str, Any]:
    transcription = str(data.get("transcription") or raw_fallback).strip()
    prompt = str(data.get("prompt") or transcription).strip()

    raw_theme = str(data.get("theme") or "bedtime").lower()
    theme = "bedtime"
    for st in STANDARD_THEMES:
        if st in raw_theme:
            theme = st
            break

    raw_chars = data.get("characters") or []
    characters: list[str] = []
    if isinstance(raw_chars, list):
        for c in raw_chars:
            if isinstance(c, dict):
                name = c.get("name") or ""
                desc = c.get("description") or ""
                val = f"{name} ({desc})".strip() if desc else name
                if val:
                    characters.append(val)
            elif isinstance(c, str) and c.strip():
                characters.append(c.strip())

    raw_tags = data.get("cues") or []
    cues: list[str] = []
    if isinstance(raw_tags, list):
        for t in raw_tags:
            if isinstance(t, str) and t.strip():
                cues.append(t.strip())

    return {
        "transcription": transcription,
        "prompt": prompt,
        "theme": theme,
        "characters": characters,
        "cues": cues,
    }


def _get_client() -> genai.Client:
    if not settings.GOOGLE_AI_API_KEY:
        raise ValueError("GOOGLE_AI_API_KEY is not configured.")
    return genai.Client(api_key=settings.GOOGLE_AI_API_KEY)


async def extract_text_cues(text: str) -> dict[str, Any]:
    """Extract story cues and structured attributes from raw text."""
    client = _get_client()
    logger.info("Extracting story cues from text: %r", text)

    user_instruction = (
        f"Extract bedtime story cues from this idea: {json.dumps(text)}\n"
        "Return strictly valid JSON with keys: transcription, prompt, theme, characters, cues."
    )

    response = await client.aio.models.generate_content(
        model="gemini-3.8-flash",
        contents=user_instruction,
        config=types.GenerateContentConfig(
            system_instruction=CUES_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.3,
            max_output_tokens=1024,
        ),
    )

    try:
        data = json.loads(response.text or "{}")
    except Exception as exc:
        logger.warning("Failed to parse cues JSON: %s. Raw: %r", exc, response.text)
        data = {}

    return _normalize_cues_output(data, text)


async def transcribe_audio_cues(audio_bytes: bytes, mime_type: str = "audio/m4a") -> dict[str, Any]:
    """Transcribe audio recording and extract structured story cues in one single Gemini multimodal call."""
    client = _get_client()
    logger.info("Transcribing audio cues (%d bytes, mime=%s)", len(audio_bytes), mime_type)

    audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
    user_instruction = (
        "Listen to this audio recording of a child or parent describing their bedtime story idea.\n"
        "1. Transcribe the spoken words accurately.\n"
        "2. Formulate a gentle 1-2 sentence bedtime story prompt.\n"
        "3. Identify the theme, characters, and key story cues.\n"
        "Return strictly valid JSON with keys: transcription, prompt, theme, characters, cues."
    )

    response = await client.aio.models.generate_content(
        model="gemini-3.8-flash",
        contents=[audio_part, user_instruction],
        config=types.GenerateContentConfig(
            system_instruction=CUES_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.3,
            max_output_tokens=1024,
        ),
    )

    try:
        data = json.loads(response.text or "{}")
    except Exception as exc:
        logger.warning("Failed to parse audio cues JSON: %s. Raw: %r", exc, response.text)
        data = {}

    return _normalize_cues_output(data, "Bedtime Story Idea")
