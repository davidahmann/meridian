import pytest
from unittest.mock import MagicMock
from meridian.context import context


@pytest.mark.asyncio
async def test_context_pricing() -> None:
    # Mock token counter to return known amount
    mock_counter = MagicMock()
    mock_counter.count.return_value = 1000

    # Use gpt-4o (2.50 per 1M input)
    @context(name="price_ctx_gpt4o", token_counter=mock_counter, model="gpt-4o")
    async def gpt4o_func() -> str:
        return "some content"

    ctx = await gpt4o_func()
    # 1000 tokens * 2.50 / 1,000,000 = 0.0025
    assert ctx.meta["cost_usd"] == 0.0025

    # Use default pricing (5.00 input)
    @context(
        name="price_ctx_default", token_counter=mock_counter, model="unknown-model"
    )
    async def default_func() -> str:
        return "content"

    ctx2 = await default_func()
    # 1000 tokens * 5.00 / 1,000,000 = 0.005
    assert ctx2.meta["cost_usd"] == 0.005
