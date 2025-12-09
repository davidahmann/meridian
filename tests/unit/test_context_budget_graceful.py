import pytest
from unittest.mock import MagicMock
from meridian.context import context, ContextItem


@pytest.mark.asyncio
async def test_context_budget_graceful() -> None:
    mock_counter = MagicMock()
    mock_counter.count.side_effect = lambda x: len(x)

    # Define context that will overflow budget with required items
    # Budget 5. "Required" is 8 chars.
    @context(name="overflow_ctx", max_tokens=5, token_counter=mock_counter)
    async def overflow_func() -> list[ContextItem]:
        return [
            ContextItem(content="Required", required=True)  # 8 chars > 5
        ]

    # Should NOT raise ContextBudgetError
    ctx = await overflow_func()

    assert ctx.content == "Required"
    assert ctx.meta["budget_exceeded"] is True
    assert ctx.meta["dropped_items"] == 0


@pytest.mark.asyncio
async def test_context_budget_graceful_string() -> None:
    mock_counter = MagicMock()
    mock_counter.count.side_effect = lambda x: len(x)

    @context(name="overflow_str", max_tokens=5, token_counter=mock_counter)
    async def overflow_str_func() -> str:
        return "TooLong"  # 7 chars > 5

    ctx = await overflow_str_func()
    assert ctx.content == "TooLong"
    assert ctx.meta["budget_exceeded"] is True
