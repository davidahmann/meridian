"""Integration tests for Fabra Server API endpoints.

Targets: src/fabra/server.py (56% → 80%+)
Covers: API endpoints, error handling, authentication, and store integration.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone
import json

from fabra.server import create_app
from fabra.core import FeatureStore, Feature
from fabra.models import ContextLineage
from fabra.context import Context


@pytest.fixture
def mock_store() -> MagicMock:
    """Create a mock FeatureStore for testing."""
    store = MagicMock(spec=FeatureStore)
    store.online_store = MagicMock()
    store.offline_store = MagicMock()
    store.registry = MagicMock()
    store.hooks = MagicMock()

    # Setup registry with some dummy data
    store.registry.features = {
        "user_age": Feature(
            name="user_age",
            entity_name="user",
            func=lambda x: 25,
            # Feature class defines arguments mostly as optional or specific types
            # name, entity_name, func are required
        )
    }
    store.registry.contexts = {}

    return store


@pytest.fixture
def client(mock_store: MagicMock) -> TestClient:
    """Create a TestClient with the mocked store."""
    app = create_app(mock_store)
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestFeatureEndpoints:
    """Tests for feature retrieval endpoints."""

    def test_get_features_success(
        self, client: TestClient, mock_store: MagicMock
    ) -> None:
        """Test batch feature retrieval for an entity."""
        mock_store.get_online_features = AsyncMock(
            return_value={"user_age": 25, "user_city": "NY"}
        )

        response = client.post(
            "/v1/features",
            json={
                "entity_name": "user",
                "entity_id": "u123",
                "features": ["user_age", "user_city"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_age"] == 25
        assert data["user_city"] == "NY"

    def test_get_features_error(
        self, client: TestClient, mock_store: MagicMock
    ) -> None:
        """Test error handling in feature retrieval."""
        mock_store.get_online_features.side_effect = Exception("Store error")

        response = client.post(
            "/v1/features",
            json={"entity_name": "user", "entity_id": "u123", "features": ["user_age"]},
        )

        assert response.status_code == 500
        assert "Store error" in response.json()["detail"]

    def test_get_single_feature_success(
        self, client: TestClient, mock_store: MagicMock
    ) -> None:
        """Test single feature retrieval endpoint."""
        # Setup specific return for online store
        mock_store.online_store.get_online_features_with_meta = AsyncMock(
            return_value={
                "user_age": {
                    "value": 30,
                    "as_of": datetime.now(timezone.utc).isoformat(),
                }
            }
        )

        response = client.get("/v1/features/user_age", params={"entity_id": "u123"})

        assert response.status_code == 200
        data = response.json()
        assert data["value"] == 30
        assert data["served_from"] == "online"
        assert "freshness_ms" in data

    def test_get_single_feature_not_found(
        self, client: TestClient, mock_store: MagicMock
    ) -> None:
        """Test single feature not found in registry."""
        response = client.get("/v1/features/non_existent", params={"entity_id": "u123"})
        assert response.status_code == 404
        assert "Feature 'non_existent' not found" in response.json()["detail"]


class TestContextEndpoints:
    """Tests for context management endpoints."""

    def test_assemble_context_success(
        self, client: TestClient, mock_store: MagicMock
    ) -> None:
        """Test context assembly via API."""
        # Register a fake context function
        mock_ctx_func = AsyncMock()
        mock_artifact = Context(
            id="ctx_123",
            content="Hello World",
            meta={"model": "gpt-4"},
            lineage=ContextLineage(context_id="ctx_123"),
        )
        mock_ctx_func.return_value = mock_artifact
        mock_store.registry.contexts["chat"] = mock_ctx_func

        response = client.post("/v1/context/chat", json={"user_query": "hello"})

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "ctx_123"
        assert data["content"] == "Hello World"

        # Verify function called with payload
        mock_ctx_func.assert_called_once_with(user_query="hello")

    def test_assemble_context_not_found(self, client: TestClient) -> None:
        """Test assembling unknown context."""
        response = client.post("/v1/context/unknown_ctx", json={})
        assert response.status_code == 404

    def test_get_context_by_id_success(
        self, client: TestClient, mock_store: MagicMock
    ) -> None:
        """Test retrieving historical context."""
        mock_store.get_context_at = AsyncMock(
            return_value=Context(id="ctx_old", content="Old Content", meta={})
        )

        response = client.get("/v1/context/ctx_old")

        assert response.status_code == 200
        assert response.json()["content"] == "Old Content"

    def test_get_context_by_id_missing(
        self, client: TestClient, mock_store: MagicMock
    ) -> None:
        """Test retrieving missing context."""
        mock_store.get_context_at = AsyncMock(return_value=None)

        response = client.get("/v1/context/ctx_missing")
        assert response.status_code == 404

    def test_list_contexts(self, client: TestClient, mock_store: MagicMock) -> None:
        """Test listing contexts with filters."""
        mock_store.list_contexts = AsyncMock(
            return_value=[
                {"context_id": "ctx_1", "created_at": "2024-01-01T00:00:00Z"},
                {"context_id": "ctx_2", "created_at": "2024-01-02T00:00:00Z"},
            ]
        )

        response = client.get(
            "/v1/contexts", params={"limit": 10, "freshness_status": "guaranteed"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        mock_store.list_contexts.assert_called_with(
            start=None, end=None, limit=10, name=None, freshness_status="guaranteed"
        )

    def test_replay_context(self, client: TestClient, mock_store: MagicMock) -> None:
        """Test context replay endpoint."""
        # Mock replay return
        mock_store.replay_context = AsyncMock(
            return_value=Context(
                id="ctx_replayed",
                content="Replayed Content",
                meta={"replayed_from": "ctx_orig"},
            )
        )

        response = client.post(
            "/v1/context/ctx_orig/replay", params={"timestamp": "2023-01-01T00:00:00Z"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Replayed Content"
        mock_store.replay_context.assert_called_once()
        # Verify timestamp parsing
        call_args = mock_store.replay_context.call_args
        assert call_args.args[0] == "ctx_orig"
        assert call_args.kwargs["timestamp"].isoformat() == "2023-01-01T00:00:00+00:00"

    def test_diff_contexts(self, client: TestClient, mock_store: MagicMock) -> None:
        """Test context diff endpoint."""
        # Should mock get_context_at calls
        c1 = Context(id="ctx_1", content="A", meta={})
        c2 = Context(id="ctx_2", content="B", meta={})

        mock_store.get_context_at = AsyncMock(side_effect=[c1, c2])

        # We also need to mock compare_contexts utility since it's imported inside the function
        # But mocking inside function is hard with patching unless we patch 'fabra.server.compare_contexts'
        # Let's rely on actual compare_contexts if possible, but it requires Lineage objects.

        # Adding minimal lineage to avoid errors
        c1.lineage = ContextLineage(context_id="ctx_1")
        c2.lineage = ContextLineage(context_id="ctx_2")

        response = client.get("/v1/context/diff/ctx_1/ctx_2")

        assert response.status_code == 200
        data = response.json()
        assert "feature_diffs" in data
        assert "content_diff" in data

    def test_explain_context(self, client: TestClient, mock_store: MagicMock) -> None:
        """Test explain context trace endpoint."""
        # Setup online store for trace retrieval
        mock_store.online_store.get = AsyncMock(
            return_value=json.dumps(
                {
                    "context_id": "ctx_1",
                    "created_at": "2024-01-01T00:00:00Z",
                    "latency_ms": 100,
                    "token_usage": 50,
                    "freshness_status": "guaranteed",
                    "source_ids": ["f1"],
                }
            )
        )

        response = client.get("/v1/context/ctx_1/explain")
        assert response.status_code == 200
        data = response.json()
        assert data["context_id"] == "ctx_1"
        assert data["token_usage"] == 50

        mock_store.get_context_at = AsyncMock(return_value=None)
        response = client.get("/v1/context/ctx_missing")
        assert response.status_code == 404

    def test_assemble_context_type_error(
        self, client: TestClient, mock_store: MagicMock
    ) -> None:
        """Test assembly with validation error (TypeError)."""
        # Register function expecting args
        mock_ctx_func = AsyncMock()
        mock_ctx_func.side_effect = TypeError("Missing argument 'query'")
        mock_store.registry.contexts["chat"] = mock_ctx_func

        response = client.post(
            "/v1/context/chat",
            json={},  # Empty payload causes TypeError
        )
        assert response.status_code == 400
        assert "Invalid arguments" in response.json()["detail"]

    def test_replay_context_invalid_timestamp(self, client: TestClient) -> None:
        """Test replay with malformed timestamp."""
        response = client.post(
            "/v1/context/ctx_1/replay", params={"timestamp": "invalid-date"}
        )
        assert response.status_code == 400
        assert "Invalid timestamp format" in response.json()["detail"]

    def test_diff_contexts_not_found(
        self, client: TestClient, mock_store: MagicMock
    ) -> None:
        """Test diff with missing context."""
        mock_store.get_context_at = AsyncMock(return_value=None)

        response = client.get("/v1/context/diff/ctx_1/ctx_2")
        assert response.status_code == 404
        assert "Base context ctx_1 not found" in response.json()["detail"]

        # Test missing second context
        mock_store.get_context_at = AsyncMock(
            side_effect=[Context(id="ctx_1", content="A", meta={}), None]
        )

        response = client.get("/v1/context/diff/ctx_1/ctx_2")
        assert response.status_code == 404
        assert "Comparison context ctx_2 not found" in response.json()["detail"]
