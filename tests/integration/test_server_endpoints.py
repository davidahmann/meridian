"""Integration tests for Fabra Server API endpoints with focus on Auth and Records.

Supplements tests/integration/test_server_api.py by covering:
- Authentication Middleware
- /v1/record endpoints
- /v1/contexts pagination
- Error handling edge cases
"""

import pytest
import os
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from fabra.server import create_app
from fabra.models import ContextRecord, LineageMetadata, IntegrityMetadata
from datetime import datetime

import json

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def mock_store():
    """Create a mock FeatureStore."""
    store = MagicMock()
    store.online_store = MagicMock()
    store.offline_store = MagicMock()
    # Ensure offline_store has get_record as AsyncMock to pass hasattr check and be awaitable
    store.offline_store.get_record = AsyncMock(return_value=None)
    store.registry = MagicMock()
    store.registry.contexts = {}
    return store


@pytest.fixture
def auth_client(mock_store):
    """Create a TestClient with API Key enforcement enabled."""
    # We enforce API key by setting the env var before app creation
    # fmt: off
    with patch.dict(os.environ, {"FABRA_API_KEY": "test-secret-key"}):  # pragma: allowlist secret
    # fmt: on
        app = create_app(mock_store)
        client = TestClient(app)
        yield client


# -----------------------------------------------------------------------------
# Authentication Tests
# -----------------------------------------------------------------------------


def test_health_no_auth_required(auth_client):
    """Health endpoint should be public."""
    response = auth_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_route_no_key(auth_client):
    """Protected routes should 403/401 without API key."""
    # Try accessing a protected route without headers
    response = auth_client.get("/v1/contexts")
    assert response.status_code == 403
    assert "Could not validate credentials" in response.json()["detail"]


def test_protected_route_wrong_key(auth_client):
    """Protected routes should 403 with wrong API key."""
    response = auth_client.get("/v1/contexts", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 403


def test_protected_route_valid_key(auth_client, mock_store):
    """Protected routes should 200 with correct API key."""
    mock_store.list_contexts = AsyncMock(return_value=[])

    response = auth_client.get("/v1/contexts", headers={"X-API-Key": "test-secret-key"})
    assert response.status_code == 200


# -----------------------------------------------------------------------------
# Record Endpoints (/v1/record)
# -----------------------------------------------------------------------------


def test_get_record_success(auth_client, mock_store):
    """Test retrieving a ContextRecord by ID."""
    # Create valid ContextRecord
    record = ContextRecord(
        context_id="ctx_123",
        context_function="chat",
        content="Test content",
        integrity=IntegrityMetadata(record_hash="def", content_hash="abc"),
        lineage=LineageMetadata(fabra_version="1.0.0"),
    )

    # Mock store.offline_store.get_record
    mock_store.offline_store.get_record.return_value = record

    response = auth_client.get(
        "/v1/record/ctx_123", headers={"X-API-Key": "test-secret-key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["context_id"] == "ctx_123"
    assert data["integrity"]["content_hash"] == "abc"


def test_get_record_not_found(auth_client, mock_store):
    """Test 404 for missing record."""
    mock_store.offline_store.get_record.return_value = None

    response = auth_client.get(
        "/v1/record/ctx_missing", headers={"X-API-Key": "test-secret-key"}
    )
    assert response.status_code == 404


def test_get_record_by_hash_success(auth_client, mock_store):
    """Test retrieving a ContextRecord by record_hash via the same endpoint."""
    record = ContextRecord(
        context_id="ctx_123",
        context_function="chat",
        content="Test content",
        integrity=IntegrityMetadata(
            record_hash="sha256:abc", content_hash="sha256:def"
        ),
        lineage=LineageMetadata(fabra_version="1.0.0"),
    )

    mock_store.offline_store.get_record_by_hash = AsyncMock(return_value=record)

    response = auth_client.get(
        "/v1/record/sha256:abc", headers={"X-API-Key": "test-secret-key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["context_id"] == "ctx_123"
    assert data["integrity"]["record_hash"] == "sha256:abc"


# -----------------------------------------------------------------------------
# Context Listing & Pagination
# -----------------------------------------------------------------------------


def test_list_contexts_pagination(auth_client, mock_store):
    """Test limit and offset in list contexts."""
    mock_store.list_contexts = AsyncMock(return_value=[])

    auth_client.get(
        "/v1/contexts?limit=5&start=2023-01-01",
        headers={"X-API-Key": "test-secret-key"},
    )

    mock_store.list_contexts.assert_called_with(
        limit=5, start=datetime(2023, 1, 1), end=None, name=None, freshness_status=None
    )


def test_get_batch_features(auth_client, mock_store):
    """Test batch feature retrieval."""
    mock_store.get_online_features = AsyncMock(return_value={"f1": 1})

    response = auth_client.post(
        "/v1/features/batch",
        json={"name": "user", "ids": ["u1", "u2"], "features": ["f1"]},
        headers={"X-API-Key": "test-secret-key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "u1" in data
    assert "u2" in data
    # Logic in server calls get_online_features loop
    assert mock_store.get_online_features.call_count == 2


def test_get_context_lineage(auth_client, mock_store):
    """Test context lineage endpoint."""
    mock_ctx = MagicMock()
    mock_ctx.lineage = LineageMetadata(fabra_version="1.0.0")
    mock_store.get_context_at = AsyncMock(return_value=mock_ctx)

    response = auth_client.get(
        "/v1/context/ctx_lin/lineage", headers={"X-API-Key": "test-secret-key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "lineage" in data
    assert data["lineage"]["fabra_version"] == "1.0.0"


def test_get_context_lineage_not_found(auth_client, mock_store):
    """Test lineage for missing context."""
    mock_store.get_context_at = AsyncMock(return_value=None)

    response = auth_client.get(
        "/v1/context/ctx_missing/lineage", headers={"X-API-Key": "test-secret-key"}
    )
    assert response.status_code == 404


def test_get_batch_features_partial_error(auth_client, mock_store):
    """Test batch feature retrieval with partial failures."""
    # First call succeeds, second fails
    mock_store.get_online_features = AsyncMock(
        side_effect=[{"f1": 1}, Exception("Store Failed")]
    )

    response = auth_client.post(
        "/v1/features/batch",
        json={"name": "user", "ids": ["u1", "u2"], "features": ["f1"]},
        headers={"X-API-Key": "test-secret-key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["u1"] == {"f1": 1}
    assert "error" in data["u2"]
    assert "Store Failed" in data["u2"]["error"]


def test_explain_context_success(auth_client, mock_store):
    """Test explain context endpoint."""
    trace_data = {
        "context_id": "ctx_1",
        "created_at": "2024-01-01T00:00:00Z",
        "latency_ms": 100,
        "token_usage": 50,
        "cost_usd": 0.001,
        "freshness_status": "guaranteed",
        "stale_sources": [],
        "source_ids": ["f1"],
    }

    mock_store.online_store.get = AsyncMock(return_value=json.dumps(trace_data))

    response = auth_client.get(
        "/v1/context/ctx_1/explain", headers={"X-API-Key": "test-secret-key"}
    )

    assert response.status_code == 200
    data = response.json()
    # Pydantic model ContextTrace validates this
    assert data["context_id"] == "ctx_1"
    assert data["token_usage"] == 50


def test_explain_context_not_found(auth_client, mock_store):
    """Test explain context 404."""
    mock_store.online_store.get = AsyncMock(return_value=None)

    response = auth_client.get(
        "/v1/context/ctx_missing/explain", headers={"X-API-Key": "test-secret-key"}
    )
    assert response.status_code == 404
    assert "Context trace not found" in response.json()["detail"]


# -----------------------------------------------------------------------------
# Error Handling
# -----------------------------------------------------------------------------


def test_internal_server_error(auth_client, mock_store):
    """Test 500 handling when store raises unexpected exception."""
    mock_store.list_contexts = AsyncMock(
        side_effect=Exception("Catastrophic DB Failure")
    )

    response = auth_client.get("/v1/contexts", headers={"X-API-Key": "test-secret-key"})

    assert response.status_code == 500
    assert "Catastrophic DB Failure" in response.json()["detail"]


# -----------------------------------------------------------------------------
# Ingestion & Cache Tests
# -----------------------------------------------------------------------------


def test_ingest_event_success(auth_client, mock_store):
    """Test event ingestion."""
    # Setup offline store client for local import fallback or reuse logic
    # The endpoint tries store.online_store.client or .redis
    mock_redis = MagicMock()
    mock_store.online_store.client = mock_redis

    # Mock bus publish (since we can't easily patch local import RedisEventBus, we rely on it working with mock redis)
    # But RedisEventBus likely needs a real-ish redis client or we patch the class.
    # Given local import 'from fabra.bus import RedisEventBus', patching 'fabra.bus.RedisEventBus' helps if we start patch before function.

    with patch("fabra.bus.RedisEventBus") as MockBus:
        mock_bus_instance = MockBus.return_value
        mock_bus_instance.publish = AsyncMock(return_value="msg_123")

        mock_store.hooks.trigger_after_ingest = AsyncMock()

        response = auth_client.post(
            "/v1/ingest/user_login",
            json={"user_id": "u1"},
            params={"entity_id": "u1"},
            headers={"X-API-Key": "test-secret-key"},
        )

        assert response.status_code == 202
        assert response.json()["msg_id"] == "msg_123"
        mock_store.hooks.trigger_after_ingest.assert_called_once()


def test_ingest_event_invalid_type(auth_client):
    """Test validation of event type."""
    response = auth_client.post(
        "/v1/ingest/invalid-type!",
        json={},
        params={"entity_id": "u1"},
        headers={"X-API-Key": "test-secret-key"},
    )
    assert response.status_code == 400
    assert "alphanumeric" in response.json()["detail"]


def test_invalidate_cache(auth_client, mock_store):
    """Test cache invalidation endpoint."""
    mock_store.online_store.delete = AsyncMock()

    response = auth_client.delete(
        "/v1/cache/user/u123", headers={"X-API-Key": "test-secret-key"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "invalidated"
    mock_store.online_store.delete.assert_called_with("user:u123")


# -----------------------------------------------------------------------------
# Visualization Tests
# -----------------------------------------------------------------------------


def test_visualize_context(auth_client, mock_store):
    """Test HTML visualization generation."""
    # It calls explain_context -> store.online_store.get("trace:{id}")
    import json

    trace_data = {
        "context_id": "ctx_viz",
        "created_at": "2024-01-01T00:00:00Z",
        "latency_ms": 100,
        "token_usage": 150,
        "cost_usd": 0.002,
        "freshness_status": "guaranteed",
        "source_ids": ["feature_1", "retriever_doc"],
        "stale_sources": [],
        "cache_hit": False,
        "meta": {},
    }

    mock_store.online_store.get = AsyncMock(return_value=json.dumps(trace_data))

    response = auth_client.get(
        "/v1/context/ctx_viz/visualize", headers={"X-API-Key": "test-secret-key"}
    )

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    content = response.text

    # Check for visual elements
    assert "feature_1" in content
    assert "Mermaid diagram" in content or "mermaid" in content.lower()
    assert "Context Assembly" in content


def test_assemble_context_includes_record_hash_and_content_hash(monkeypatch):
    """
    POST /v1/context/{context_name} should include record_hash/content_hash when
    CRS-001 records are enabled (offline_store present).
    """

    from fabra.context import context
    from fabra.core import FeatureStore
    from fabra.store.offline import DuckDBOfflineStore

    # Ensure dev-mode auth (no API key requirement for this test client)
    monkeypatch.delenv("FABRA_API_KEY", raising=False)

    store = FeatureStore()
    store.offline_store = DuckDBOfflineStore(":memory:")

    @context(store=store, name="hash_ctx")
    async def hash_ctx(user_id: str) -> str:
        return f"hello {user_id}"

    app = create_app(store)
    client = TestClient(app)

    resp = client.post("/v1/context/hash_ctx", json={"user_id": "u1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"].startswith("ctx_")
    assert data["record_hash"].startswith("sha256:")
    assert data["content_hash"].startswith("sha256:")
    assert data["meta"]["record_hash"] == data["record_hash"]
    assert data["meta"]["content_hash"] == data["content_hash"]
