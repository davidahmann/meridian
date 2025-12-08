import pytest
from meridian.graph import DependencyResolver
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_dag_missing_feature() -> None:
    store = MagicMock()
    # Mock registry feature lookup fail
    store.registry.features.get.return_value = None

    resolver = DependencyResolver(store)

    # Resolving {missing.feature}
    # Should warn and skip replacement
    res = await resolver.execute_dag("Hello {missing.feature}", "e1")
    assert res == "Hello {missing.feature}"


@pytest.mark.asyncio
async def test_dag_resolution_error() -> None:
    # Ensure retrieval.py logic handles resolver errors gracefully?
    # graph.py DependencyResolver usually returns string.
    # If store.get_online_features raises?
    store = MagicMock()
    feat = MagicMock()
    feat.entity_name = "user"
    store.registry.features.get.return_value = feat

    store.get_online_features.side_effect = Exception("Store Down")

    resolver = DependencyResolver(store)

    # execute_dag calls get_online_features. If it fails, execute_dag logic?
    # graph.py calls:
    # values = await self.store.get_online_features(...)
    # If this raises, execute_dag raises.

    res = await resolver.execute_dag("Hello {user.name}", "u1")
    assert res == "Hello {user.name}"
