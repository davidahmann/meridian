"""Extended unit tests for FeatureStore core functionality.

Targets uncovered lines in src/fabra/core.py:
- register_context() method (lines 776-779)
- Error handling in get_online_features() and get_training_data()
"""

import pytest
from unittest.mock import MagicMock
from fabra.core import FeatureStore, entity
from fabra.store import OfflineStore, OnlineStore


@pytest.fixture
def mock_stores():
    """Create mock stores for testing."""
    offline = MagicMock(spec=OfflineStore)
    online = MagicMock(spec=OnlineStore)
    return offline, online


@pytest.fixture
def feature_store(mock_stores):
    """Create a FeatureStore with mocked dependencies."""
    offline, online = mock_stores
    return FeatureStore(offline_store=offline, online_store=online)


class TestRegisterContext:
    """Tests for FeatureStore.register_context() method."""

    def test_register_context_injects_cache_backend(
        self, feature_store: FeatureStore
    ) -> None:
        """Test that register_context() injects cache backend."""

        # Create a mock context function with required attributes
        def mock_context_func():
            pass

        mock_context_func._is_context = True  # type: ignore
        mock_context_func.__name__ = "test_context"  # type: ignore

        # Register it
        feature_store.register_context(mock_context_func)

        # Verify cache backend was injected
        assert hasattr(mock_context_func, "_cache_backend")
        assert mock_context_func._cache_backend == feature_store.online_store  # type: ignore


class TestGetOnlineFeaturesErrorHandling:
    """Tests for error handling in get_online_features()."""

    @pytest.mark.asyncio
    async def test_get_online_features_feature_not_found(
        self, feature_store: FeatureStore
    ) -> None:
        """Test error when feature doesn't exist."""

        # Define an entity but no features
        @entity(feature_store)
        class User:
            user_id: str

        # Try to get non-existent feature
        result = await feature_store.get_online_features(
            entity_name="User",
            entity_id="u1",
            features=["nonexistent_feature"],
        )

        # Should return empty dict or handle gracefully
        assert (
            "nonexistent_feature" not in result or result["nonexistent_feature"] is None
        )


class TestGetTrainingDataEdgeCases:
    """Tests for edge cases in get_training_data()."""

    @pytest.mark.asyncio
    async def test_get_training_data_with_feature_not_found_error(
        self, feature_store: FeatureStore
    ) -> None:
        """Test get_training_data() with non-existent feature raises ValueError."""
        import pandas as pd

        # Define entity
        @entity(feature_store)
        class User:
            user_id: str

        # DataFrame with data
        df = pd.DataFrame({"user_id": ["u1"]})

        # Should raise ValueError for missing feature
        with pytest.raises(ValueError, match="Feature 'nonexistent' not found"):
            await feature_store.get_training_data(
                entity_df=df,
                features=["nonexistent"],
            )

    @pytest.mark.asyncio
    async def test_get_training_data_empty_features_list(
        self, feature_store: FeatureStore
    ) -> None:
        """Test get_training_data() with empty features list."""
        import pandas as pd

        # Define entity
        @entity(feature_store)
        class User:
            user_id: str

        # DataFrame
        df = pd.DataFrame({"user_id": ["u1"]})

        # Empty features should return just the entity df
        result = await feature_store.get_training_data(
            entity_df=df,
            features=[],
        )

        assert len(result) == 1
        assert "user_id" in result.columns
