import pytest
import base64
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.image.factory import get_image_provider
from app.services.image.imagen import ImagenProvider
from app.services.image.dalle import DalleProvider
from app.services.image.replicate_flux import ReplicateImageProvider
from app.services import image_service


def test_get_image_provider_factory():
    assert isinstance(get_image_provider("imagen"), ImagenProvider)
    assert isinstance(get_image_provider("dalle"), DalleProvider)
    assert isinstance(get_image_provider("replicate"), ReplicateImageProvider)

    with pytest.raises(ValueError, match="Unsupported Image provider"):
        get_image_provider("unsupported_diffusion")


@pytest.mark.asyncio
async def test_dalle_provider():
    provider = DalleProvider(api_key="test-key", model_name="dall-e-3")

    fake_bytes = b"fake-png-data"
    b64_str = base64.b64encode(fake_bytes).decode("utf-8")

    mock_client = MagicMock()
    mock_data = MagicMock(b64_json=b64_str)
    mock_response = MagicMock(data=[mock_data])
    mock_client.images.generate = AsyncMock(return_value=mock_response)

    with patch.object(provider, "_get_client", return_value=mock_client):
        result_bytes = await provider.generate_image("A cute dragon in pajamas", seed=42)
        assert result_bytes == fake_bytes


@pytest.mark.asyncio
async def test_replicate_provider():
    provider = ReplicateImageProvider(api_token="test-token", model_name="black-forest-labs/flux-schnell")

    fake_bytes = b"replicate-image-data"
    mock_file_output = MagicMock()
    mock_file_output.read.return_value = fake_bytes

    mock_client = MagicMock()
    mock_client.run.return_value = [mock_file_output]

    with patch.object(provider, "_get_client", return_value=mock_client):
        result_bytes = await provider.generate_image("A starry night sky", seed=123)
        assert result_bytes == fake_bytes


@pytest.mark.asyncio
async def test_image_service_facade():
    mock_provider = MagicMock()
    mock_provider.generate_image = AsyncMock(return_value=b"image_bytes")

    with patch("app.services.image_service.get_image_provider", return_value=mock_provider):
        result = await image_service.generate_image("prompt", seed=10)
        assert result == b"image_bytes"
        mock_provider.generate_image.assert_awaited_once_with(
            image_prompt="prompt", seed=10
        )
