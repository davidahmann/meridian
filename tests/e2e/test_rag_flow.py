from __future__ import annotations
import pytest
from meridian.core import FeatureStore, entity, feature
from meridian.context import context, ContextItem
from meridian.retrieval import retriever
from meridian.utils.tokens import TokenCounter


# Mock Token Counter for deterministic testing
class MockCounter(TokenCounter):
    def count(self, text: str) -> int:
        return len(text)


@pytest.mark.asyncio
async def test_full_rag_flow() -> None:
    # 1. Setup Store
    store = FeatureStore()

    # 2. Define Entity
    @entity(store)
    class User:
        user_id: str

    # 3. Define Feature
    @feature(entity=User, refresh="1d")
    def user_tier(user_id: str) -> str:
        return "premium" if user_id == "u1" else "free"

    # 4. Define Retriever
    @retriever(name="kb_search")  # type: ignore[untyped-decorator]
    async def search_kb(query: str) -> list[str]:
        return [f"Doc about {query}", "Another Doc"]

    # 5. Define Context
    # We pass 'store' to enable integration (though strictly only needed if features used via store inside)
    # Here we use store.get_feature
    @context(store=store, max_tokens=50, token_counter=MockCounter())
    async def build_rag_prompt(user_id: str, query: str) -> list[ContextItem]:
        # Fetch Feature
        tier = await store.get_feature("user_tier", user_id)

        # Fetch Docs
        docs = await search_kb(query)

        return [
            ContextItem(
                content=f"User is {tier}", priority=0, required=True
            ),  # ~13 chars
            ContextItem(
                content=f"Results: {docs}", priority=1, required=True
            ),  # ~30 chars
            ContextItem(
                content="Extra info that fits", priority=2, required=False
            ),  # ~20 chars
        ]

    # 6. Execute Flow
    # Total chars: 13 + 30 + 20 = 63 > 50.
    # "Extra info that fits" (low priority 2) should be dropped.

    ctx = await build_rag_prompt(user_id="u1", query="meridian")

    # Verification
    assert "User is premium" in ctx.content
    assert "Results: ['Doc about meridian', 'Another Doc']" in ctx.content
    assert "Extra info" not in ctx.content

    assert ctx.meta["dropped_items"] == 1
    assert ctx.meta["status"] == "assembled"
    assert ctx.id is not None

    # Verify Trace existence (if store had online store, trace would be saved, but default store is memory/none)
    # The default FeatureStore() has no Redis configured unless env vars set.
    # So trace saving might be skipped or log warning.
