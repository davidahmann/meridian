import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fabra.store.postgres import PostgresOfflineStore


@pytest.fixture
def mock_engine():
    with patch("fabra.store.postgres.create_async_engine") as mock:
        yield mock


def test_postgres_conn_string_normalization(mock_engine):
    """Test that connection strings are normalized to asyncpg."""
    # psycopg2 -> asyncpg
    # fmt: off
    PostgresOfflineStore("postgresql+psycopg2://user:pass@host/db")  # pragma: allowlist secret
    # fmt: on
    # fmt: off
    mock_engine.assert_called_with("postgresql+asyncpg://user:pass@host/db", pool_size=5, max_overflow=10)  # pragma: allowlist secret
    # fmt: on

    # postgresql:// -> asyncpg
    # fmt: off
    PostgresOfflineStore("postgresql://user:pass@host/db")  # pragma: allowlist secret
    # fmt: on
    # fmt: off
    mock_engine.assert_called_with("postgresql+asyncpg://user:pass@host/db", pool_size=5, max_overflow=10)  # pragma: allowlist secret
    # fmt: on


@pytest.mark.asyncio
async def test_postgres_invalid_names(mock_engine):
    """Test regex validation for table/index names."""
    store = PostgresOfflineStore("postgresql+asyncpg://localhost/db")

    # Add documents - invalid index name
    with pytest.raises(ValueError, match="Invalid index name"):
        await store.add_documents("bad name;", "id", [], [])

    # Search - invalid index name
    with pytest.raises(ValueError, match="Invalid index name"):
        await store.search("bad-name", [], 5)


@pytest.mark.asyncio
async def test_postgres_json_serialization_error(mock_engine):
    """Test JSON serialization failure in log_context."""
    store = PostgresOfflineStore("postgresql+asyncpg://localhost/db")

    # Mock engine begin to returning a context manager
    # We expect serialization to fail BEFORE DB call

    class Unserializable:
        pass

    with pytest.raises(TypeError, match="not JSON serializable"):
        await store.log_context(
            "ctx_1",
            "2023-01-01",  # valid (str or datetime)
            "content",
            {"bad": Unserializable()},  # invalid lineage
            {},
        )


@pytest.mark.asyncio
async def test_postgres_execute_sql_returns_empty(mock_engine):
    """Test execute_sql handles empty results gracefully."""
    store = PostgresOfflineStore("postgresql+asyncpg://localhost/db")

    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_result.keys.return_value = ["col1"]
    mock_conn.execute.return_value = mock_result

    store.engine.connect.return_value.__aenter__.return_value = mock_conn

    df = await store.execute_sql("SELECT * FROM table")
    assert df.empty
    assert list(df.columns) == ["col1"]
