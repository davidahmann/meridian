import pytest
from meridian.context import ContextItem, context
from meridian.utils.tokens import TokenCounter


class MockCounter(TokenCounter):
    def count(self, text: str) -> int:
        return len(text)


@pytest.mark.asyncio
async def test_context_budget_strict() -> None:
    # Budget: 5 chars.
    # Item 1: "123" (3 chars)
    # Item 2: "456" (3 chars)
    # Total: 6 chars.
    # Both required=True -> Should raise Error.

    @context(max_tokens=5, token_counter=MockCounter())
    async def strict_ctx() -> list[ContextItem]:
        return [
            ContextItem(content="123", required=True),
            ContextItem(content="456", required=True),
        ]

    # Must invoke wrapper
    # Graceful: Should not raise, but flag
    result = await strict_ctx()
    assert result.meta["budget_exceeded"] is True
    assert "123" in result.content
    assert "456" in result.content


@pytest.mark.asyncio
async def test_context_budget_drop_optional() -> None:
    # Budget: 5 chars.
    # Item 1: "123" (3) -> Optional
    # Item 2: "456" (3) -> Required
    # Logic tries to drop optional.
    # If Item 1 dropped, Item 2 fits (3 <= 5)? No wait.
    # If Item 1 dropped, remaining is "456" (3). 3 <= 5. Success.

    @context(max_tokens=5, token_counter=MockCounter())
    async def optional_ctx() -> list[ContextItem]:
        return [
            ContextItem(content="123", required=False),  # Should be dropped
            ContextItem(content="456", required=True),
        ]

    res = await optional_ctx()
    assert "456" in res.content
    assert "123" not in res.content
    assert res.meta["dropped_items"] == 1
