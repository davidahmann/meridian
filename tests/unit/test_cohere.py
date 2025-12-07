from __future__ import annotations
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from meridian.embeddings import CohereEmbedding


@pytest.mark.asyncio
async def test_cohere_embedding_basic() -> None:
    # Patch the global cohere class since it is imported inside the method
    # but refers to the installed package.
    with patch("cohere.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        # Mock Response structure (simplified)
        mock_resp = MagicMock()
        # For embed_documents (search_document)
        mock_resp.embeddings = [[0.1, 0.2, 0.3]]

        mock_client.embed.return_value = mock_resp

        provider = CohereEmbedding(api_key="fake-key")

        # Test 1: Documents
        res_docs = await provider.embed_documents(["doc1"])
        assert len(res_docs) == 1
        assert res_docs[0] == [0.1, 0.2, 0.3]

        # Verify call args for documents
        call_args = mock_client.embed.call_args_list[0]
        _, kwargs = call_args
        assert kwargs["texts"] == ["doc1"]
        assert kwargs["input_type"] == "search_document"

        # Test 2: Query
        # Reset mock return for query if needed (using same generic structure here)
        mock_resp.embeddings = [[0.9, 0.8, 0.7]]
        res_query = await provider.embed_query("query1")
        assert res_query == [0.9, 0.8, 0.7]

        # Verify call args for query
        call_args_query = mock_client.embed.call_args_list[1]
        _, kwargs_query = call_args_query
        assert kwargs_query["texts"] == ["query1"]
        assert kwargs_query["input_type"] == "search_query"
