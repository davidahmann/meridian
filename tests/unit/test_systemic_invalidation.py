from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from meridian.context import context, ContextItem
from meridian.core import FeatureStore


@pytest.mark.asyncio
async def test_metadata_population() -> None:
    @context(name="meta_ctx")
    async def meta_test() -> list[ContextItem]:
        return [
            ContextItem(content="A", source_id="feat_1"),
            ContextItem(content="B", source_id="feat_2"),
        ]

    ctx = await meta_test()
    assert ctx.meta["freshness_status"] == "guaranteed"
    assert "feat_1" in ctx.meta["source_ids"]
    assert "feat_2" in ctx.meta["source_ids"]


@pytest.mark.asyncio
async def test_invalidation_logic() -> None:
    # 1. Setup Store
    store = FeatureStore(online_store=AsyncMock(), offline_store=MagicMock())

    # 2. Mock Dependency Data in Redis
    # dependency:feat_1 -> { "context:abc:123" }
    store.online_store.smembers.return_value = {b"context:abc:123"}  # type: ignore

    # 3. Call Invalidate
    count = await store.invalidate_contexts_for_feature("feat_1")

    # 4. Verify
    assert count == 1
    # Should delete the specific context key
    store.online_store.delete.assert_any_call(b"context:abc:123")  # type: ignore
    # Should delete the map key
    store.online_store.delete.assert_any_call("dependency:feat_1")  # type: ignore
