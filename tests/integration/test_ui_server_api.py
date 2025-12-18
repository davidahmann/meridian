"""Integration tests for Fabra UI Server API."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
from fabra.ui_server import app, _state
from fabra.core import FeatureStore, Feature, Entity, FeatureRegistry
from fabra.store.online import InMemoryOnlineStore
from fabra.store.offline import DuckDBOfflineStore

client = TestClient(app)


@pytest.fixture
def mock_store() -> MagicMock:
    store = MagicMock(spec=FeatureStore)
    store.online_store = MagicMock(spec=InMemoryOnlineStore)
    store.offline_store = MagicMock(spec=DuckDBOfflineStore)

    # Registry
    store.registry = MagicMock(spec=FeatureRegistry)
    store.registry.entities = {
        "user": Entity(name="user", id_column="user_id", description="A user")
    }

    feat = Feature(
        name="user_clicks",
        entity_name="user",
        func=lambda x: x,
        materialize=True,
        refresh=None,
        ttl=None,
    )
    store.registry.features = {"user_clicks": feat}
    store.registry.get_features_for_entity.return_value = [feat]

    # Mock online store fetch
    store.get_online_features = AsyncMock(return_value={"user_clicks": 42})

    return store


@pytest.fixture(autouse=True)
def setup_state(mock_store: MagicMock) -> None:
    """Inject mock store into global state."""
    _state["store"] = mock_store

    # Mock context function
    async def mock_context(user_id: str) -> MagicMock:
        ctx = MagicMock()
        ctx.id = "ctx_123"
        ctx.content = "Context content"
        ctx.meta = {
            "token_usage": 10,
            "cost_usd": 0.01,
            "latency_ms": 100,
            "freshness_status": "fresh",
        }
        ctx.items = []
        ctx.lineage = None
        # Support to_record
        ctx.to_record = MagicMock(return_value=None)
        return ctx

    _state["contexts"] = {"test_context": mock_context}
    _state["retrievers"] = {}
    _state["file_path"] = "features.py"
    _state["context_records"] = {}


def test_get_store_info() -> None:
    """Test /api/store endpoint."""
    response = client.get("/api/store")
    assert response.status_code == 200
    data = response.json()
    assert data["file_name"] == "features.py"
    assert len(data["entities"]) == 1
    assert data["entities"][0]["name"] == "user"
    assert len(data["features"]) == 1
    assert data["features"][0]["name"] == "user_clicks"
    assert len(data["contexts"]) == 1


def test_get_features() -> None:
    """Test /api/features endpoint."""
    # Assuming user_clicks is materialized
    response = client.get("/api/features/user/u1")
    assert response.status_code == 200
    data = response.json()
    assert data == {"user_clicks": 42}


def test_assemble_context() -> None:
    """Test /api/context/{name} endpoint."""
    response = client.post(
        "/api/context/test_context",
        params={"context_name": "test_context"},  # params are passing in query or body?
        # The endpoint signature:
        # async def assemble_context(context_name: str, params: Dict[str, str], ...)
        # It expects params in BODY as JSON probably? Or query?
        # definition: params: Dict[str, str]
        # FastApi default for Dict is body.
        json={"user_id": "u1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "ctx_123"
    assert data["meta"]["token_usage"] == 10


def test_graph() -> None:
    """Test /api/graph endpoint."""
    response = client.get("/api/graph")
    assert response.status_code == 200
    data = response.json()
    assert "graph LR" in data["code"]
    assert "user_clicks" in data["code"]


def test_verify_context_404() -> None:
    """Test /api/context/{id}/verify 404."""
    response = client.get("/api/context/missing_id/verify")
    assert response.status_code == 404
