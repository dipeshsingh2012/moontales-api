import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.llm.factory import get_llm_provider
from app.services.llm.gemini import GeminiLLMProvider
from app.services.llm.openai import OpenAILLMProvider
from app.services.llm.groq import GroqLLMProvider
from app.services.llm.prompts import parse_and_validate_pages, build_user_prompt
from app.services import llm_service


def test_get_llm_provider_factory():
    assert isinstance(get_llm_provider("gemini"), GeminiLLMProvider)
    assert isinstance(get_llm_provider("openai"), OpenAILLMProvider)
    assert isinstance(get_llm_provider("groq"), GroqLLMProvider)

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        get_llm_provider("unsupported_llm")


def test_parse_and_validate_pages_valid():
    raw_json = """[
        {
            "page_number": 1,
            "text": "Once upon a time in a starry sky.",
            "audio_text": "Once upon a time [whispers] in a starry sky.",
            "image_prompt": "CHARACTER DESIGN: Luna... SCENE: ... STYLE: ..."
        }
    ]"""
    pages = parse_and_validate_pages(raw_json, 1)
    assert len(pages) == 1
    assert pages[0]["page_number"] == 1


def test_parse_and_validate_pages_markdown_fence():
    raw = """```json
    [
        {
            "page_number": 1,
            "text": "Page one text.",
            "audio_text": "Page one text.",
            "image_prompt": "Prompt 1"
        }
    ]
    ```"""
    pages = parse_and_validate_pages(raw, 1)
    assert len(pages) == 1
    assert pages[0]["text"] == "Page one text."


def test_parse_and_validate_pages_nested_dict():
    raw = """{
        "pages": [
            {
                "page_number": 1,
                "text": "Nested page text.",
                "audio_text": "Nested page text.",
                "image_prompt": "Prompt nested"
            }
        ]
    }"""
    pages = parse_and_validate_pages(raw, 1)
    assert len(pages) == 1
    assert pages[0]["text"] == "Nested page text."


def test_parse_and_validate_pages_missing_key():
    raw = """[
        {
            "page_number": 1,
            "text": "Missing audio and image"
        }
    ]"""
    with pytest.raises(RuntimeError, match="missing keys"):
        parse_and_validate_pages(raw, 1)


@pytest.mark.asyncio
async def test_openai_llm_provider():
    provider = OpenAILLMProvider(api_key="test-key", model_name="gpt-4o-mini")

    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = """[
        {
            "page_number": 1,
            "text": "Page text",
            "audio_text": "Page text [warmly]",
            "image_prompt": "Prompt"
        }
    ]"""
    mock_response = MagicMock(choices=[mock_choice])
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch.object(provider, "_get_client", return_value=mock_client):
        pages = await provider.generate_story_pages(user_cues=["adventure"], page_count=1)
        assert len(pages) == 1
        assert pages[0]["page_number"] == 1


@pytest.mark.asyncio
async def test_groq_llm_provider():
    provider = GroqLLMProvider(api_key="test-groq-key", model_name="llama-3.3-70b-versatile")

    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = """[
        {
            "page_number": 1,
            "text": "Groq story text",
            "audio_text": "Groq story text [excited]",
            "image_prompt": "Groq prompt"
        }
    ]"""
    mock_response = MagicMock(choices=[mock_choice])
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch.object(provider, "_get_client", return_value=mock_client):
        pages = await provider.generate_story_pages(user_cues=["stars"], page_count=1)
        assert len(pages) == 1
        assert pages[0]["text"] == "Groq story text"


@pytest.mark.asyncio
async def test_llm_service_facade():
    mock_provider = MagicMock()
    mock_provider.generate_story_pages = AsyncMock(return_value=[{"page_number": 1}])

    with patch("app.services.llm_service.get_llm_provider", return_value=mock_provider):
        pages = await llm_service.generate_story_pages(["cue1"], 1)
        assert pages == [{"page_number": 1}]
        mock_provider.generate_story_pages.assert_awaited_once_with(
            user_cues=["cue1"], page_count=1
        )
