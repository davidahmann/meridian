"""Integration tests for embedding providers.

Targets: src/fabra/embeddings.py (64% → 85%+)
Covers: OpenAI and Cohere embedding with retries and error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fabra.embeddings import OpenAIEmbedding, CohereEmbedding


@pytest.mark.asyncio
class TestOpenAIEmbedding:
    """Tests for OpenAI embedding provider."""

    async def test_embed_documents_success(self) -> None:
        """Test successful document embedding."""
        with patch("fabra.embeddings.AsyncOpenAI") as mock_client_class:
            # Mock the embeddings API
            mock_client = MagicMock()
            mock_client.embeddings.create = AsyncMock(
                return_value=MagicMock(
                    data=[
                        MagicMock(embedding=[0.1] * 1536),
                        MagicMock(embedding=[0.2] * 1536),
                    ]
                )
            )
            mock_client_class.return_value = mock_client

            embedder = OpenAIEmbedding(api_key="test_key")
            results = await embedder.embed_documents(["text1", "text2"])

            assert len(results) == 2
            assert len(results[0]) == 1536

    async def test_embed_query_success(self) -> None:
        """Test successful query embedding."""
        with patch("fabra.embeddings.AsyncOpenAI") as mock_client_class:
            mock_client = MagicMock()
            mock_client.embeddings.create = AsyncMock(
                return_value=MagicMock(data=[MagicMock(embedding=[0.5] * 1536)])
            )
            mock_client_class.return_value = mock_client

            embedder = OpenAIEmbedding(api_key="test_key")
            result = await embedder.embed_query("test query")

            assert len(result) == 1536
            assert result[0] == 0.5

    async def test_retry_on_rate_limit(self) -> None:
        """Test retry logic on rate limit errors."""
        with patch("fabra.embeddings.AsyncOpenAI") as mock_client_class:
            mock_client = MagicMock()

            # Setup side effects for the create method
            # First call raises RateLimitError, second returns success
            from openai import RateLimitError

            error = RateLimitError(
                "Rate limit exceeded", response=MagicMock(), body=None
            )

            mock_client.embeddings.create = AsyncMock(
                side_effect=[error, MagicMock(data=[MagicMock(embedding=[0.1] * 1536)])]
            )
            mock_client_class.return_value = mock_client

            embedder = OpenAIEmbedding(api_key="test_key")

            # Patch asyncio.sleep to avoid actual waiting
            with patch("fabra.embeddings.asyncio.sleep", new_callable=AsyncMock):
                results = await embedder.embed_documents(["text"])
                assert len(results) == 1
                # Verify it was called twice
                assert mock_client.embeddings.create.call_count == 2


@pytest.mark.asyncio
class TestCohereEmbedding:
    """Tests for Cohere embedding provider."""

    async def test_embed_documents_success(self) -> None:
        """Test successful document embedding with Cohere."""
        # Mock cohere module since it's imported dynamically
        with patch.dict("sys.modules", {"cohere": MagicMock()}):
            import cohere

            # Setup the AsyncClient mock
            mock_client = MagicMock()
            mock_client.embed = AsyncMock(
                return_value=MagicMock(embeddings=[[0.1] * 1024, [0.2] * 1024])
            )
            cohere.AsyncClient.return_value = mock_client

            embedder = CohereEmbedding(api_key="test_key")
            # Inject the mock client directly to be sure
            embedder.client = mock_client

            results = await embedder.embed_documents(["text1", "text2"])

            assert len(results) == 2
            assert len(results[0]) == 1024

    async def test_embed_query_success(self) -> None:
        """Test successful query embedding with Cohere."""
        with patch.dict("sys.modules", {"cohere": MagicMock()}):
            import cohere

            mock_client = MagicMock()
            mock_client.embed = AsyncMock(
                return_value=MagicMock(embeddings=[[0.5] * 1024])
            )
            cohere.AsyncClient.return_value = mock_client

            embedder = CohereEmbedding(api_key="test_key")
            embedder.client = mock_client

            result = await embedder.embed_query("test query")

            assert len(result) == 1024
