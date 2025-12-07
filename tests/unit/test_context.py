from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import timedelta, datetime, timezone
from meridian.context import context, Context, ContextItem, ContextBudgetError


@pytest.mark.asyncio
async def test_context_decorator_basic() -> None:
    @context(name="test_ctx")
    async def my_assembler(user: str) -> str:
        return f"Hello {user}"

    # Execution
    result = await my_assembler(user="World")

    # Assertions
    assert isinstance(result, Context)
    assert result.content == "Hello World"
    assert result.id is not None
    # Rudimentary check for UUIDv7 (time based, starts roughly same)
    assert len(result.id) == 36
    assert result.meta["name"] == "test_ctx"
    assert "timestamp" in result.meta


@pytest.mark.asyncio
async def test_context_decorator_default_name() -> None:
    @context()
    async def implicit_name() -> str:
        return "implicit"

    result = await implicit_name()
    assert result.meta["name"] == "implicit_name"


@pytest.mark.asyncio
async def test_context_caching() -> None:
    # Mock Backend
    mock_store = AsyncMock()
    mock_store.get.return_value = None  # Cache Miss initially

    # Define Context with Caching
    @context(name="cached_ctx", cache_ttl=timedelta(minutes=1))
    async def expensive_assembly(arg: str) -> str:
        return f"Processed {arg}"

    # Inject backend manually (simulating register_context)
    setattr(expensive_assembly, "_cache_backend", mock_store)

    # 1. First Call (Miss)
    res1 = await expensive_assembly(arg="test")
    assert res1.content == "Processed test"

    # Verify set was called
    mock_store.set.assert_called_once()

    # 2. Setup Cache Hit
    # The stored value is the JSON dump of the context
    mock_store.get.return_value = res1.model_dump_json()

    # 3. Second Call (Hit)
    res2 = await expensive_assembly(arg="test")
    assert res2.content == "Processed test"
    assert res2.id == res1.id  # Should be identical object ID from cache


@pytest.mark.asyncio
async def test_context_budgeting_trimming() -> None:
    # 1. Define items
    mock_counter = MagicMock()
    mock_counter.count.side_effect = lambda x: len(x)

    @context(name="budget_ctx_mocked", max_tokens=10, token_counter=mock_counter)
    async def assemble_items_mocked() -> list[ContextItem]:
        return [
            ContextItem(content="KeepMe", required=True),  # 6 tokens
            ContextItem(content="DropMe", required=False),  # 6 tokens
        ]

    # Total 12. Limit 10. Should drop "DropMe".

    ctx = await assemble_items_mocked()
    assert "KeepMe" in ctx.content
    assert "DropMe" not in ctx.content
    assert ctx.meta["dropped_items"] == 1


@pytest.mark.asyncio
async def test_context_budget_error() -> None:
    mock_counter = MagicMock()
    mock_counter.count.side_effect = lambda x: len(x)

    @context(name="fail_ctx", max_tokens=5, token_counter=mock_counter)
    async def assemble_fail() -> list[ContextItem]:
        return [
            ContextItem(content="TooLongForBudget", required=True)  # 16 tokens
        ]

    with pytest.raises(ContextBudgetError):
        await assemble_fail()


@pytest.mark.asyncio
async def test_context_freshness_sla() -> None:
    mock_store = AsyncMock()

    # Create an "Old" context
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)
    old_ctx = Context(
        id="old",
        content="Old Content",
        meta={"timestamp": old_time.isoformat(), "name": "fresh_ctx"},
    )

    mock_store.get.return_value = old_ctx.model_dump_json()

    # Define context with 1 hour acceptable staleness
    # Since existing item is 2 hours old, it should be stale -> recompute
    @context(
        name="fresh_ctx",
        cache_ttl=timedelta(hours=24),
        max_staleness=timedelta(hours=1),
    )
    async def get_fresh_data() -> str:
        return "New Content"

    setattr(get_fresh_data, "_cache_backend", mock_store)

    # Executing
    result = await get_fresh_data()

    # Should get "New Content" because cache was stale
    assert result.content == "New Content"
    assert result.id != "old"

    # Now verify if it was fresh enough (e.g. 3 hours staleness allowed)
    @context(
        name="fresh_ctx_lax",
        cache_ttl=timedelta(hours=24),
        max_staleness=timedelta(hours=3),
    )
    async def get_lax_data() -> str:
        return "New Content"

    setattr(get_lax_data, "_cache_backend", mock_store)

    # Executing
    result_lax = await get_lax_data()
    # Should get "Old Content" because 2 hours old < 3 hours max staleness
    assert result_lax.content == "Old Content"
    assert result_lax.id == "old"
