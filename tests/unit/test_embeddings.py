from __future__ import annotations
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Any
from meridian.embeddings import OpenAIEmbedding
from openai.types import CreateEmbeddingResponse, Embedding


@pytest.mark.asyncio
async def test_openai_embedding_basic() -> None:
    with patch("meridian.embeddings.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        # Mock Response
        mock_resp = MagicMock(spec=CreateEmbeddingResponse)
        mock_embedding = MagicMock(spec=Embedding)
        mock_embedding.embedding = [0.1, 0.2, 0.3]
        mock_resp.data = [mock_embedding]

        mock_client.embeddings.create.return_value = mock_resp

        provider = OpenAIEmbedding(api_key="sk-fake")
        res = await provider.embed_documents(["hello"])

        assert len(res) == 1
        assert res[0] == [0.1, 0.2, 0.3]

        # Verify call args
        mock_client.embeddings.create.assert_called_once()
        args, kwargs = mock_client.embeddings.create.call_args
        assert kwargs["input"] == ["hello"]
        assert kwargs["model"] == "text-embedding-3-small"


@pytest.mark.asyncio
async def test_openai_embedding_batching() -> None:
    with patch("meridian.embeddings.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        # Mock Response for 105 items (batch size 100)
        # Call 1: 100 items
        # Call 2: 5 items

        def side_effect(input: Any, model: str) -> Any:
            count = len(input)
            mock_resp = MagicMock(spec=CreateEmbeddingResponse)
            # define data list
            data = []
            for _ in range(count):
                e = MagicMock(spec=Embedding)
                e.embedding = [0.0] * 1536
                data.append(e)
            mock_resp.data = data
            return mock_resp

        mock_client.embeddings.create.side_effect = side_effect

        provider = OpenAIEmbedding(api_key="sk-fake")
        inputs = ["text"] * 105
        res = await provider.embed_documents(inputs)

        assert len(res) == 105
        assert mock_client.embeddings.create.call_count == 2
