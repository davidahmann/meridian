import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock, patch
from fabra.ui_server import (
    _get_api_key,
    _is_demo_mode,
    _get_demo_warning,
    _convert_to_record_response,
    ContextResult,
    ContextResultItem,
    ContextResultMeta,
)
from fabra.store import InMemoryOnlineStore, DuckDBOfflineStore


def test_get_api_key_valid():
    """Test API key validation success."""
    with patch("os.environ.get", return_value="secret-key"):
        # Correct key
        assert _get_api_key("secret-key") == "secret-key"


def test_get_api_key_invalid():
    """Test API key validation failure."""
    with patch("os.environ.get", return_value="secret-key"):
        # Wrong key
        with pytest.raises(HTTPException) as exc:
            _get_api_key("wrong-key")
        assert exc.value.status_code == 401


def test_get_api_key_not_required():
    """Test API key validation when not configured."""
    with patch("os.environ.get", return_value=None):
        # No key configured -> acceptable
        assert _get_api_key(None) is None


def test_demo_mode_detection():
    """Test detection of demo/in-memory stores."""
    store = MagicMock()

    # Case 1: In-Memory Online
    store.online_store = InMemoryOnlineStore()
    store.offline_store = MagicMock()
    assert _is_demo_mode(store) is True
    assert "InMemoryOnlineStore" in _get_demo_warning(store)

    # Case 2: DuckDB Offline
    store.online_store = MagicMock()  # Not InMemory
    store.offline_store = DuckDBOfflineStore(database=":memory:")
    assert _is_demo_mode(store) is True
    assert "DuckDBOfflineStore" in _get_demo_warning(store)

    # Case 3: Production (Mocked)
    store.online_store = MagicMock()
    # Mocking standard OfflineStore to simulate Production
    store.offline_store = MagicMock()
    # The _is_demo_mode checks specifically for DuckDBInstance
    # Since MagicMock isn't DuckDBOfflineStore, it returns False for isinstance
    assert _is_demo_mode(store) is False
    assert _get_demo_warning(store) is None


def test_models_serialization():
    """Test Pydantic model instantiation and serialization."""

    # Context Result
    res = ContextResult(
        id="ctx_123",
        items=[
            ContextResultItem(content="A", priority=10),
            ContextResultItem(content="B", priority=5, source="doc_1"),
        ],
        meta=ContextResultMeta(
            token_usage=100, cost_usd=0.002, freshness_status="fresh"
        ),
    )

    dump = res.model_dump()
    assert dump["id"] == "ctx_123"
    assert len(dump["items"]) == 2
    assert dump["meta"]["token_usage"] == 100


def test_convert_to_record_response():
    """Test conversion logic for ContextRecord."""

    # Mock a ContextRecord object (internal)
    mock_record = MagicMock()
    mock_record.context_id = "ctx_123"
    mock_record.schema_version = "1.0"
    mock_record.created_at.isoformat.return_value = "2023-01-01T00:00:00Z"
    mock_record.environment = "dev"
    mock_record.context_function = "test_func"
    mock_record.inputs = {"q": "test"}
    mock_record.content = "Content"
    mock_record.token_count = 50

    # Assembly
    mock_record.assembly.tokens_used = 50
    mock_record.assembly.max_tokens = 100
    mock_record.assembly.items_provided = 2
    mock_record.assembly.items_included = 2
    mock_record.assembly.dropped_items = []
    mock_record.assembly.freshness_status = "fresh"

    # Integrity
    mock_record.integrity.record_hash = "sha256:abc"
    mock_record.integrity.content_hash = "sha256:def"
    mock_record.integrity.previous_context_id = None

    resp = _convert_to_record_response(mock_record)

    assert resp.context_id == "ctx_123"
    assert resp.assembly.tokens_used == 50
    assert resp.integrity.record_hash == "sha256:abc"


@pytest.mark.asyncio
async def test_get_store_info():
    """Test get_store_info API logic."""
    from fabra.ui_server import get_store_info, _state

    # Setup mock state
    mock_store = MagicMock()
    # Setup registry entities/features
    mock_store.registry.entities = {
        "user": MagicMock(id_column="uid", description="User")
    }
    mock_feat = MagicMock(name="f1", materialize=False, refresh=None, ttl=None)
    mock_feat.name = "f1"  # MagicMock name behavior workaround
    mock_store.registry.get_features_for_entity.return_value = [mock_feat]

    # Mock stores for demo check
    mock_store.online_store = InMemoryOnlineStore()
    mock_store.offline_store = MagicMock()

    # Mock context
    mock_ctx = MagicMock()
    mock_ctx.__doc__ = "Test Doc"

    # Mock function signature
    def my_ctx(user_id: str, limit: int = 10):
        pass

    # Mock retriever
    mock_ret = MagicMock(backend="postgres", cache_ttl="1h", index="idx")

    new_state = {
        "store": mock_store,
        "contexts": {"my_ctx": my_ctx},
        "retrievers": {"ret1": mock_ret},
        "file_path": "/path/to/features.py",
    }

    with patch.dict(_state, new_state, clear=True):
        info = await get_store_info(None)

        assert info.file_name == "features.py"
        assert len(info.entities) == 1
        assert info.entities[0].name == "user"

        assert len(info.contexts) == 1
        assert info.contexts[0].name == "my_ctx"
        # Check params
        # user_id: str (required), limit: int (default=10)
        params = info.contexts[0].parameters
        assert len(params) == 2
        assert params[0].name == "user_id"
        assert params[0].required is True
        assert params[1].name == "limit"
        assert params[1].required is False
        assert params[1].default == "10"

        assert len(info.retrievers) == 1
        assert info.retrievers[0].name == "ret1"
        assert info.retrievers[0].is_mock is False

        assert info.is_demo_mode is True


@pytest.mark.asyncio
async def test_assemble_context():
    """Test assemble_context API."""
    from fabra.ui_server import assemble_context, _state

    # Mock async context function
    async def mock_ctx_func(q: str):
        res = MagicMock()
        res.id = "ctx_id"
        res.items = [MagicMock(content="res", priority=1)]
        res.items[0].content = "res"  # Force str
        res.items[0].source = "s1"
        res.meta = {"token_usage": 10, "freshness_status": "fresh"}
        res.lineage = None
        # to_record mock
        res.to_record.return_value = "record"
        return res

    state = {"contexts": {"mock_ctx": mock_ctx_func}, "context_records": {}}

    with patch.dict(_state, state, clear=True):
        res = await assemble_context("mock_ctx", {"q": "hello"}, None)

        assert res.id == "ctx_id"
        assert res.items[0].content == "res"
        assert _state["context_records"]["ctx_id"] == "record"


@pytest.mark.asyncio
async def test_mermaid_graph():
    """Test mermaid graph generation."""
    from fabra.ui_server import get_mermaid_graph, _state

    mock_store = MagicMock()
    mock_store.online_store.__class__.__name__ = "RedisOnlineStore"

    # Entities and Features
    mock_store.registry.entities = {"user": MagicMock()}
    f1 = MagicMock(materialize=True)
    f1.name = "user_f1"
    mock_store.registry.get_features_for_entity.return_value = [f1]

    state = {"store": mock_store}

    with patch.dict(_state, state, clear=True):
        graph = await get_mermaid_graph(None)
        code = graph.code

        assert "graph LR" in code
        assert "RedisOnlineStore" in code
        assert "subgraph user" in code
        assert "(user_f1)" in code
        assert "-. Materialize .->" in code
