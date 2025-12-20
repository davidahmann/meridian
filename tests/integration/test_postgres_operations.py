"""Integration tests for Postgres offline store operations.

Targets: src/fabra/store/postgres.py (60% → 85%+)
Covers: connection, table creation, vector operations, search, records
"""

import pytest
from datetime import datetime, timezone
from fabra.store.postgres import PostgresOfflineStore
from fabra.models import (
    ContextRecord,
    IntegrityMetadata,
    LineageMetadata,
    AssemblyDecisions,
)
from sqlalchemy import text
import sys

sys.path.insert(0, str(__file__).rsplit("/tests/", 1)[0] + "/tests")


@pytest.fixture
async def postgres_store(postgres_url: str):
    """Create a fresh PostgresOfflineStore for each test."""
    store = PostgresOfflineStore(postgres_url)
    # Clean up vector index tables before test
    try:
        async with store.engine.begin() as conn:
            await conn.execute(
                text(
                    """
                DO $$ DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'fabra_index_%') LOOP
                        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                    END LOOP;
                END $$;
            """
                )
            )
    except Exception:
        pass
    yield store
    # No cleanup needed - SQLAlchemy handles connection pooling


@pytest.mark.asyncio
class TestPostgresConnection:
    """Test connection management."""

    async def test_connection_success(
        self, postgres_store: PostgresOfflineStore
    ) -> None:
        """Test successful connection to Postgres."""
        async with postgres_store.engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            row = result.fetchone()
            assert row[0] == 1


@pytest.mark.asyncio
class TestVectorIndexOperations:
    """Test vector index creation and management."""

    async def test_create_index_table(
        self, postgres_store: PostgresOfflineStore
    ) -> None:
        """Test creating a vector index table."""
        await postgres_store.create_index_table("test_index", dimension=1536)

        # Verify table exists
        async with postgres_store.engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = :table_name)"
                ),
                {"table_name": "fabra_index_test_index"},
            )
            exists = result.fetchone()[0]
            assert exists is True

    async def test_add_documents(self, postgres_store: PostgresOfflineStore) -> None:
        """Test adding documents to vector index."""
        await postgres_store.create_index_table("docs", dimension=3)

        await postgres_store.add_documents(
            index_name="docs",
            entity_id="e1",
            chunks=["chunk1", "chunk2"],
            embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            metadatas=[{"page": 1}, {"page": 2}],
        )

        async with postgres_store.engine.connect() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM fabra_index_docs"))
            count = result.fetchone()[0]
            assert count == 2


@pytest.mark.asyncio
class TestVectorSearch:
    """Test vector similarity search functionality."""

    async def test_basic_vector_search(
        self, postgres_store: PostgresOfflineStore
    ) -> None:
        """Test basic vector similarity search."""
        await postgres_store.create_index_table("search_idx", dimension=3)
        await postgres_store.add_documents(
            index_name="search_idx",
            entity_id="e1",
            chunks=["doc1", "doc2", "doc3"],
            embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            metadatas=[{}, {}, {}],
        )

        results = await postgres_store.search(
            index_name="search_idx", query_embedding=[0.9, 0.1, 0.0], top_k=2
        )

        assert len(results) == 2
        assert results[0]["content"] == "doc1"


@pytest.mark.asyncio
class TestRecordStorage:
    """Test context record storage and retrieval."""

    async def test_log_record(self, postgres_store: PostgresOfflineStore) -> None:
        """Test storing a context record."""
        record = ContextRecord(
            context_id="ctx_test_1",
            created_at=datetime.now(timezone.utc),
            environment="test",
            schema_version="1.0.0",
            inputs={"user_id": "u1"},
            context_function="test_ctx",
            content="Test content",
            token_count=5,
            features=[],
            retrieved_items=[],
            assembly=AssemblyDecisions(),
            lineage=LineageMetadata(
                features_used=[],
                retrievers_used=[],
                indexes_used=[],
                fabra_version="1.0.0",
            ),
            integrity=IntegrityMetadata(
                record_hash="sha256:abc", content_hash="sha256:def"
            ),
        )

        await postgres_store.log_record(record)

        # Verify it was stored
        retrieved = await postgres_store.get_record("ctx_test_1")
        assert retrieved is not None
        assert retrieved.context_id == "ctx_test_1"
        assert retrieved.content == "Test content"

        # Lookup by record_hash should work
        by_hash = await postgres_store.get_record_by_hash("sha256:abc")
        assert by_hash is not None
        assert by_hash.context_id == "ctx_test_1"

        # Immutability: re-log same record is idempotent, different hash is rejected
        await postgres_store.log_record(record)
        from fabra.exceptions import ImmutableRecordError

        bad = record.model_copy(deep=True)
        bad.integrity.record_hash = "sha256:zzz"
        with pytest.raises(ImmutableRecordError):
            await postgres_store.log_record(bad)
