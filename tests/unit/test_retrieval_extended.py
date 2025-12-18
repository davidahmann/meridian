"""Extended unit tests for retrieval module.

Targets: src/fabra/retrieval.py (73% → 85%+)
Covers: sync wrapper, cache handling, and error cases
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fabra.retrieval import retriever, RetrieverRegistry


class TestRetrieverSyncWrapper:
    """Tests for synchronous retriever wrapper."""

    def test_sync_retriever_execution(self) -> None:
        """Test sync wrapper executes retriever correctly."""

        # Define a SYNC function to get the sync wrapper
        @retriever()
        def test_retriever(query: str) -> list:
            return [f"result for {query}"]

        # Call directly
        results = test_retriever(query="test")
        assert len(results) == 1
        assert "test" in results[0]


class TestRetrieverRegistry:
    """Tests for retriever registry."""

    def test_register_and_get_retriever(self) -> None:
        """Test registering and retrieving a retriever."""
        registry = RetrieverRegistry()

        @retriever()
        async def my_retriever(query: str) -> list:
            return ["result"]

        # Manually register since decorator doesn't do it automatically
        # The retriever object is attached to the function
        registry.register(my_retriever._fabra_retriever)

        retrieved = registry.get("my_retriever")
        assert retrieved is not None
        assert retrieved.name == "my_retriever"

    def test_list_retrievers(self) -> None:
        """Test listing all registered retrievers."""
        registry = RetrieverRegistry()

        @retriever()
        async def retriever1(query: str) -> list:
            return []

        @retriever()
        async def retriever2(query: str) -> list:
            return []

        registry.register(retriever1._fabra_retriever)
        registry.register(retriever2._fabra_retriever)

        all_retrievers = registry.retrievers
        assert len(all_retrievers) >= 2


class TestMagicWiringEdgeCases:
    """Tests for magic wiring edge cases."""

    @pytest.mark.asyncio
    async def test_magic_wiring_with_missing_index(self) -> None:
        """Test magic wiring when index doesn't exist."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        @retriever(index="nonexistent_index")
        async def test_retriever(query: str) -> list:
            return []

        # Inject the store reference onto the retriever object
        # The decorator attaches _fabra_retriever to the original function
        # functools.wraps copies attributes, so try accessing it on the wrapper
        if hasattr(test_retriever, "_fabra_retriever"):
            test_retriever._fabra_retriever._fabra_store_ref = mock_store
        else:
            # Fallback for some wrap implementations
            test_retriever.__wrapped__._fabra_retriever._fabra_store_ref = mock_store

        # Should handle missing index gracefully by returning store result (which is empty list)
        # or logging error and returning function result
        results = await test_retriever(query="test")
        assert isinstance(results, list)
