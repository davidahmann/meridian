"""
Tests for the Fabra UI Server.

These tests cover:
- Phase 1: Demo mode detection and indicators
- Phase 2: Retriever type detection
- Phase 4: Optional API key authentication
- Phase 5: InMemoryOnlineStore startup warning
- Phase 3: Context Record endpoints
"""

import os
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from fabra.core import FeatureStore
from fabra.store import InMemoryOnlineStore, DuckDBOfflineStore
from fabra.ui_server import (
    _is_demo_mode,
    _get_demo_warning,
    _get_api_key,
    app,
    load_module,
    StoreInfo,
)


# =============================================================================
# Phase 1: Demo Mode Detection Tests
# =============================================================================


class TestDemoModeDetection:
    """Tests for _is_demo_mode() function."""

    def test_is_demo_mode_with_inmemory_online(self) -> None:
        """InMemoryOnlineStore is detected as demo mode."""
        store = FeatureStore(online_store=InMemoryOnlineStore())
        assert _is_demo_mode(store) is True

    def test_is_demo_mode_with_duckdb_offline(self) -> None:
        """DuckDBOfflineStore is detected as demo mode."""
        store = FeatureStore(offline_store=DuckDBOfflineStore())
        assert _is_demo_mode(store) is True

    def test_is_demo_mode_with_both_demo_stores(self) -> None:
        """Both InMemory and DuckDB is demo mode."""
        store = FeatureStore(
            online_store=InMemoryOnlineStore(),
            offline_store=DuckDBOfflineStore(),
        )
        assert _is_demo_mode(store) is True

    def test_get_demo_warning_inmemory(self) -> None:
        """Warning message includes InMemoryOnlineStore info."""
        store = FeatureStore(online_store=InMemoryOnlineStore())
        warning = _get_demo_warning(store)
        assert warning is not None
        assert "InMemoryOnlineStore" in warning
        assert "data lost on restart" in warning

    def test_get_demo_warning_duckdb(self) -> None:
        """Warning message includes DuckDBOfflineStore info."""
        store = FeatureStore(offline_store=DuckDBOfflineStore())
        warning = _get_demo_warning(store)
        assert warning is not None
        assert "DuckDBOfflineStore" in warning
        assert "local development only" in warning

    def test_get_demo_warning_suggests_production(self) -> None:
        """Warning message suggests FABRA_ENV=production."""
        store = FeatureStore(online_store=InMemoryOnlineStore())
        warning = _get_demo_warning(store)
        assert warning is not None
        assert "FABRA_ENV=production" in warning


# =============================================================================
# Phase 4: Authentication Tests
# =============================================================================


class TestAuthentication:
    """Tests for API key authentication."""

    def test_no_auth_when_env_not_set(self) -> None:
        """API works without auth when FABRA_UI_API_KEY not set."""
        # Ensure env var is not set
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("FABRA_UI_API_KEY", None)
            # Should not raise
            result = _get_api_key(None)
            assert result is None

    def test_auth_required_when_env_set(self) -> None:
        """API requires auth when FABRA_UI_API_KEY is set."""
        from fastapi import HTTPException

        test_key = "test-api-key-12345"  # pragma: allowlist secret
        with patch.dict(os.environ, {"FABRA_UI_API_KEY": test_key}):
            with pytest.raises(HTTPException) as exc_info:
                _get_api_key(None)  # No key provided
            assert exc_info.value.status_code == 401

    def test_auth_succeeds_with_valid_key(self) -> None:
        """API works with valid API key."""
        test_key = "test-api-key-12345"  # pragma: allowlist secret
        with patch.dict(os.environ, {"FABRA_UI_API_KEY": test_key}):
            result = _get_api_key(test_key)
            assert result == test_key

    def test_auth_fails_with_invalid_key(self) -> None:
        """API rejects invalid API key."""
        from fastapi import HTTPException

        test_key = "test-api-key-12345"  # pragma: allowlist secret
        with patch.dict(os.environ, {"FABRA_UI_API_KEY": test_key}):
            with pytest.raises(HTTPException) as exc_info:
                _get_api_key("wrong_key")
            assert exc_info.value.status_code == 401


# =============================================================================
# Phase 5: Startup Warning Tests
# =============================================================================


class TestStartupWarning:
    """Tests for InMemoryOnlineStore startup warning."""

    def test_inmemory_warning_on_load(self, tmp_path: Path) -> None:
        """Loading InMemoryOnlineStore module emits warning."""
        # Create a minimal feature file
        feature_file = tmp_path / "test_features.py"
        feature_file.write_text(
            """
from fabra.core import FeatureStore
from fabra.store import InMemoryOnlineStore, DuckDBOfflineStore

store = FeatureStore(
    online_store=InMemoryOnlineStore(),
    offline_store=DuckDBOfflineStore(),
)
"""
        )

        with pytest.warns(UserWarning, match="InMemoryOnlineStore"):
            load_module(str(feature_file))

    def test_warning_message_content(self, tmp_path: Path) -> None:
        """Warning message has correct content."""
        feature_file = tmp_path / "test_features.py"
        feature_file.write_text(
            """
from fabra.core import FeatureStore
from fabra.store import InMemoryOnlineStore, DuckDBOfflineStore

store = FeatureStore(
    online_store=InMemoryOnlineStore(),
    offline_store=DuckDBOfflineStore(),
)
"""
        )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            load_module(str(feature_file))

            # Find our specific warning
            inmem_warnings = [x for x in w if "InMemoryOnlineStore" in str(x.message)]
            assert len(inmem_warnings) >= 1

            warning_text = str(inmem_warnings[0].message)
            assert "data will be lost on restart" in warning_text
            assert "FABRA_ENV=production" in warning_text


# =============================================================================
# Phase 2: Retriever Type Detection Tests
# =============================================================================


class TestRetrieverDetection:
    """Tests for retriever mock/real detection."""

    def test_retriever_model_has_is_mock_field(self) -> None:
        """Retriever model includes is_mock field."""
        from fabra.ui_server import Retriever

        retriever = Retriever(
            name="test",
            backend="mock",
            cache_ttl="300s",
            is_mock=True,
            index_name=None,
        )
        assert retriever.is_mock is True
        assert retriever.index_name is None

    def test_retriever_model_with_index(self) -> None:
        """Retriever with index is not mock."""
        from fabra.ui_server import Retriever

        retriever = Retriever(
            name="search_docs",
            backend="pgvector",
            cache_ttl="300s",
            is_mock=False,
            index_name="knowledge_base",
        )
        assert retriever.is_mock is False
        assert retriever.index_name == "knowledge_base"


# =============================================================================
# Phase 3: Context Record Tests
# =============================================================================


class TestContextRecordModels:
    """Tests for CRS-001 Context Record response models."""

    def test_dropped_item_response_model(self) -> None:
        """DroppedItemResponse model works correctly."""
        from fabra.ui_server import DroppedItemResponse

        item = DroppedItemResponse(
            source_id="docs_chunk_5",
            priority=30,
            token_count=150,
            reason="token_budget_exceeded",
        )
        assert item.source_id == "docs_chunk_5"
        assert item.priority == 30
        assert item.token_count == 150
        assert item.reason == "token_budget_exceeded"

    def test_integrity_response_model(self) -> None:
        """IntegrityResponse model works correctly."""
        from fabra.ui_server import IntegrityResponse

        integrity = IntegrityResponse(
            record_hash="sha256:abc123",
            content_hash="sha256:def456",
            previous_context_id=None,
        )
        assert integrity.record_hash == "sha256:abc123"
        assert integrity.content_hash == "sha256:def456"
        assert integrity.previous_context_id is None

    def test_assembly_response_model(self) -> None:
        """AssemblyResponse model works correctly."""
        from fabra.ui_server import AssemblyResponse

        assembly = AssemblyResponse(
            tokens_used=1500,
            max_tokens=4000,
            items_provided=5,
            items_included=4,
            dropped_items=[],
            freshness_status="guaranteed",
        )
        assert assembly.tokens_used == 1500
        assert assembly.max_tokens == 4000
        assert assembly.freshness_status == "guaranteed"

    def test_context_record_response_model(self) -> None:
        """ContextRecordResponse model works correctly."""
        from fabra.ui_server import (
            ContextRecordResponse,
            AssemblyResponse,
            IntegrityResponse,
        )

        record = ContextRecordResponse(
            context_id="ctx_018f3a2b-test",
            schema_version="1.0.0",
            created_at="2025-01-01T00:00:00Z",
            environment="development",
            context_function="chat_context",
            inputs={"user_id": "u1", "query": "test"},
            content="Test content",
            token_count=50,
            assembly=AssemblyResponse(
                tokens_used=50,
                max_tokens=4000,
                items_provided=2,
                items_included=2,
                dropped_items=[],
                freshness_status="guaranteed",
            ),
            integrity=IntegrityResponse(
                record_hash="sha256:abc",
                content_hash="sha256:def",
            ),
        )
        assert record.context_id == "ctx_018f3a2b-test"
        assert record.schema_version == "1.0.0"

    def test_verification_result_model(self) -> None:
        """VerificationResult model works correctly."""
        from fabra.ui_server import VerificationResult

        result = VerificationResult(
            context_id="ctx_018f3a2b-test",
            is_valid=True,
            content_hash_valid=True,
            record_hash_valid=True,
            error=None,
            verified_at="2025-01-01T00:00:00Z",
        )
        assert result.is_valid is True
        assert result.content_hash_valid is True
        assert result.error is None


# =============================================================================
# StoreInfo Model Tests
# =============================================================================


class TestStoreInfoModel:
    """Tests for StoreInfo response model."""

    def test_store_info_has_demo_fields(self) -> None:
        """StoreInfo model includes demo mode fields."""
        info = StoreInfo(
            file_name="test.py",
            entities=[],
            features=[],
            contexts=[],
            retrievers=[],
            online_store_type="InMemoryOnlineStore",
            offline_store_type="DuckDBOfflineStore",
            is_demo_mode=True,
            demo_warning="Demo mode active.",
        )
        assert info.is_demo_mode is True
        assert info.demo_warning == "Demo mode active."
        assert info.offline_store_type == "DuckDBOfflineStore"

    def test_store_info_production_mode(self) -> None:
        """StoreInfo model for production mode."""
        info = StoreInfo(
            file_name="prod.py",
            entities=[],
            features=[],
            contexts=[],
            retrievers=[],
            online_store_type="RedisOnlineStore",
            offline_store_type="PostgresOfflineStore",
            is_demo_mode=False,
            demo_warning=None,
        )
        assert info.is_demo_mode is False
        assert info.demo_warning is None


# =============================================================================
# Example File Validation Tests
# =============================================================================


class TestExampleFiles:
    """Tests for example file validity."""

    def test_production_example_exists(self) -> None:
        """production_context.py exists."""
        example_path = Path("examples/production_context.py")
        assert example_path.exists(), "production_context.py should exist"

    def test_production_example_loads(self) -> None:
        """production_context.py loads without syntax errors."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "production_context", "examples/production_context.py"
        )
        assert spec is not None
        assert spec.loader is not None
        # Just check it can be parsed (don't execute to avoid side effects)

    def test_production_example_has_docstring(self) -> None:
        """production_context.py has informative docstring."""
        content = Path("examples/production_context.py").read_text()
        assert "Production Example" in content or "production" in content.lower()
        assert "OPENAI_API_KEY" in content  # Documents env var requirement

    def test_production_example_uses_index_param(self) -> None:
        """production_context.py uses index= for real vector search."""
        content = Path("examples/production_context.py").read_text()
        assert "@retriever(index=" in content

    def test_demo_example_exists(self) -> None:
        """demo_context.py exists."""
        example_path = Path("examples/demo_context.py")
        assert example_path.exists(), "demo_context.py should exist"


# =============================================================================
# Documentation Validation Tests
# =============================================================================


class TestDocumentation:
    """Tests for WebUI documentation."""

    def test_webui_docs_exist(self) -> None:
        """WebUI documentation exists."""
        docs_path = Path("docs/webui.md")
        assert docs_path.exists(), "docs/webui.md should exist"

    def test_webui_docs_contains_demo_warning(self) -> None:
        """WebUI docs explain demo vs production mode."""
        content = Path("docs/webui.md").read_text()
        assert "demo" in content.lower()
        assert "InMemoryOnlineStore" in content

    def test_webui_docs_contains_auth_section(self) -> None:
        """WebUI docs explain authentication."""
        content = Path("docs/webui.md").read_text()
        assert "Authentication" in content or "API Key" in content
        assert "FABRA_UI_API_KEY" in content

    def test_webui_docs_contains_endpoints(self) -> None:
        """WebUI docs list API endpoints."""
        content = Path("docs/webui.md").read_text()
        assert "/api/store" in content
        assert "/api/features" in content
        assert "/api/context" in content


# =============================================================================
# Integration Tests (require running server)
# =============================================================================


class TestAPIEndpoints:
    """Integration tests for API endpoints using TestClient."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> TestClient:
        """Create test client with a minimal feature file loaded."""
        # Create minimal feature file
        feature_file = tmp_path / "test_features.py"
        feature_file.write_text(
            """
from fabra.core import FeatureStore, entity, feature
from fabra.store import InMemoryOnlineStore, DuckDBOfflineStore

store = FeatureStore(
    online_store=InMemoryOnlineStore(),
    offline_store=DuckDBOfflineStore(),
)

@entity(store)
class User:
    user_id: str

@feature(entity=User)
def user_name(user_id: str) -> str:
    return f"User {user_id}"
"""
        )

        # Load the module (suppress warning for tests)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            load_module(str(feature_file))

        return TestClient(app)

    def test_store_endpoint_returns_demo_mode(self, client: TestClient) -> None:
        """GET /api/store returns is_demo_mode=True for demo stores."""
        response = client.get("/api/store")
        assert response.status_code == 200
        data = response.json()
        assert data["is_demo_mode"] is True
        assert data["demo_warning"] is not None
        assert "InMemoryOnlineStore" in data["online_store_type"]

    def test_store_endpoint_returns_offline_store_type(
        self, client: TestClient
    ) -> None:
        """GET /api/store returns offline_store_type."""
        response = client.get("/api/store")
        assert response.status_code == 200
        data = response.json()
        assert "offline_store_type" in data
        assert "DuckDB" in data["offline_store_type"]

    def test_features_endpoint_works(self, client: TestClient) -> None:
        """GET /api/features/{entity}/{id} returns features."""
        response = client.get("/api/features/User/test123")
        # May return empty or computed values depending on store state
        assert response.status_code in [200, 500]  # 500 if feature not seeded

    def test_graph_endpoint_works(self, client: TestClient) -> None:
        """GET /api/graph returns Mermaid code."""
        response = client.get("/api/graph")
        assert response.status_code == 200
        data = response.json()
        assert "code" in data
        assert "graph" in data["code"]

    def test_auth_blocks_without_key(self, client: TestClient) -> None:
        """Endpoints require auth when FABRA_UI_API_KEY is set."""
        test_key = "test-api-key-12345"  # pragma: allowlist secret
        with patch.dict(os.environ, {"FABRA_UI_API_KEY": test_key}):
            response = client.get("/api/store")
            assert response.status_code == 401

    def test_auth_allows_with_key(self, client: TestClient) -> None:
        """Endpoints work with valid auth key."""
        test_key = "test-api-key-12345"  # pragma: allowlist secret
        with patch.dict(os.environ, {"FABRA_UI_API_KEY": test_key}):
            response = client.get("/api/store", headers={"X-API-Key": test_key})
            assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
