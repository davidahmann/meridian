from __future__ import annotations
import pytest
import pytest_asyncio
from meridian.store.postgres import PostgresOfflineStore
from typing import Dict, Any, AsyncGenerator


@pytest_asyncio.fixture
async def vector_store(
    infrastructure: Dict[str, Any]
) -> AsyncGenerator[PostgresOfflineStore, None]:
    url = infrastructure["postgres_url"]
    store = PostgresOfflineStore(url)
    yield store
    # Cleanup?
    # Tables are dropped when container dies.


@pytest.mark.asyncio
async def test_vector_flow(vector_store: PostgresOfflineStore) -> None:
    index_name = "test_docs"

    # 1. Create Index
    await vector_store.create_index_table(index_name, dimension=3)

    # 2. Add Documents
    # Vectors: [1,0,0], [0,1,0], [0,0,1]
    chunks = ["doc_a", "doc_b", "doc_c"]
    embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    metadatas = [{"tag": "a"}, {"tag": "b"}, {"tag": "c"}]

    await vector_store.add_documents(index_name, "ent1", chunks, embeddings, metadatas)

    # 3. Search
    # Query: [1, 0.1, 0] -> closest to doc_a ([1,0,0])
    query = [1.0, 0.1, 0.0]

    results = await vector_store.search(index_name, query, top_k=2)

    assert len(results) == 2
    assert results[0]["content"] == "doc_a"
    # Metadata now includes default fields. Check subset/existence.
    assert results[0]["metadata"]["tag"] == "a"
    assert "content_hash" in results[0]["metadata"]
    assert "ingestion_timestamp" in results[0]["metadata"]
    assert results[0]["metadata"]["indexer_version"] == "meridian-v1"
    # Score should be high (close to 1 if using cosine sim equivalent, or distance close to 0)
    # Our search returns "1 - distance" as score.
    # embedding <=> query is Cosine DISTANCE.
    # So 1 - distance = Similarity.
    assert results[0]["score"] > 0.9

    # Second result should be doc_b or doc_c?
    # doc_b: [0,1,0]. Cosine sim with [1, 0.1, 0] ~ small.
    # Dist ~ 1.

    # Let's verify result ordering
    assert results[1]["content"] in ["doc_b", "doc_c"]


@pytest.mark.asyncio
async def test_duplicate_handling(vector_store: PostgresOfflineStore) -> None:
    # TODO: Implement dedup logic if required by Story 2.2.3 (Constraint: content_hash unique)
    # "Constraint: content_hash unique per entity_id to prevent duplication."
    pass
