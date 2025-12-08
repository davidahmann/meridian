import pytest
from unittest.mock import AsyncMock
from meridian.store.postgres import PostgresOfflineStore
from meridian.embeddings import OpenAIEmbedding
from sqlalchemy import text


@pytest.mark.asyncio
async def test_vector_search_e2e() -> None:
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("Testcontainers not installed")

    with PostgresContainer("postgres:15-alpine") as postgres:
        # 1. Setup Postgres with pgvector
        url = postgres.get_connection_url().replace("psycopg2", "asyncpg")
        store = PostgresOfflineStore(url)

        # Ensure pgvector extension
        async with store.engine.begin() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # 2. Setup Mock Embedding to return deterministic vectors
        # "cat" -> [1.0, 0.0, ...]
        # "dog" -> [0.9, 0.1, ...]
        mock_embedder = AsyncMock(spec=OpenAIEmbedding)

        async def fake_embed(texts: list[str], model: str = "") -> list[list[float]]:
            return [[1.0] * 1536 for _ in texts]  # Simple dummy vector

        mock_embedder.embed.side_effect = fake_embed

        # 3. Create Index
        index_name = "e2e_test_index"
        await store.create_index_table(index_name, 1536)

        # 4. Add Documents
        # Call 1: Entity 1
        await store.add_documents(
            index_name=index_name,
            entity_id="id1",
            chunks=["doc1_content"],
            embeddings=[[1.0] * 1536],
            metadatas=[{"text": "doc1_content"}],
        )

        # Call 2: Entity 2
        await store.add_documents(
            index_name=index_name,
            entity_id="id2",
            chunks=["doc2_content"],
            embeddings=[[1.0] * 1536],
            metadatas=[{"text": "doc2_content"}],
        )

        # 5. Search
        # Search with same vector should return doc1 (or doc2, score tie, check logic)
        query_vector = [1.0] * 1536
        results = await store.search(index_name, query_vector, top_k=5)

        assert len(results) >= 1
        # Check that we got results
        texts = [r["metadata"]["text"] for r in results]
        assert "doc1_content" in texts

        await store.engine.dispose()  # type: ignore[no-untyped-call]
