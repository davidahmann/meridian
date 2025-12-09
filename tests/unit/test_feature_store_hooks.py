import pytest
from typing import List, Dict, Any
from unittest.mock import MagicMock
from meridian.core import FeatureStore
from meridian.hooks import Hook
from meridian.store import InMemoryOnlineStore


class SpyHook(Hook):
    def __init__(self) -> None:
        self.before_args: Any = None
        self.after_args: Any = None

    async def before_feature_retrieval(
        self, entity_name: str, entity_id: str, features: List[str]
    ) -> None:
        self.before_args = (entity_name, entity_id, features)

    async def after_feature_retrieval(
        self,
        entity_name: str,
        entity_id: str,
        features: List[str],
        result: Dict[str, Any],
    ) -> None:
        self.after_args = (entity_name, entity_id, features, result)
        # Modify result
        result["spy_value"] = 999


@pytest.mark.asyncio
async def test_feature_store_hooks_integration() -> None:
    spy = SpyHook()
    # Mock offline store to avoid errors
    store = FeatureStore(
        offline_store=MagicMock(), online_store=InMemoryOnlineStore(), hooks=[spy]
    )

    # Register a dummy feature
    def dummy_func(id: str) -> int:
        return 42

    # Register entity imperatively
    store.register_entity("User", "user_id")

    store.register_feature("age", "User", dummy_func)

    # Call get_online_features
    # This will use compute path because cache is empty
    result = await store.get_online_features("User", "u1", ["age"])

    # Check Before Hook
    assert spy.before_args == ("User", "u1", ["age"])

    # Check After Hook
    assert spy.after_args is not None
    assert spy.after_args[3]["age"] == 42

    # Check if hook modification persisted in return value
    # The hook modifies the result dict in place
    assert result["spy_value"] == 999
