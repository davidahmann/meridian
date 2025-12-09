from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import timedelta, datetime, timezone
from meridian.context import context, Context, ContextItem


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

    # Mock Pipeline
    mock_pipeline = MagicMock()
    mock_pipeline.set.return_value = None
    mock_pipeline.sadd.return_value = None
    mock_pipeline.expire.return_value = None
    # execute is async
    future = AsyncMock(return_value=None)
    mock_pipeline.execute = future

    # IMPORTANT: pipeline() method must be synchronous (MagicMock), not AsyncMock
    mock_store.pipeline = MagicMock(return_value=mock_pipeline)

    # Define Context with Caching
    @context(name="cached_ctx", cache_ttl=timedelta(minutes=1))
    async def expensive_assembly(arg: str) -> str:
        return f"Processed {arg}"

    # Inject backend manually (simulating register_context)
    setattr(expensive_assembly, "_cache_backend", mock_store)

    # 1. First Call (Miss)
    res1 = await expensive_assembly(arg="test")
    assert res1.content == "Processed test"

    # Verify set was called on pipeline
    # The pipeline.set call happens once for context, maybe more for trace (if trace uses pipeline? No trace uses backend.set)
    # Check pipeline.set calls
    # Args: key, value, ex
    assert mock_pipeline.set.called

    # Also verify trace was written? Trace uses backend.set (async)
    # The test doesn't mock trace writing return? AsyncMock returns coroutine.
    # We should await mock_store.set? No, the code awaits it.

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
async def test_context_budget_graceful_degradation() -> None:
    mock_counter = MagicMock()
    mock_counter.count.side_effect = lambda x: len(x)

    @context(name="fail_ctx", max_tokens=5, token_counter=mock_counter)
    async def assemble_fail() -> list[ContextItem]:
        return [
            ContextItem(content="TooLongForBudget", required=True)  # 16 tokens
        ]

    # Graceful degradation: Should NOT raise, but flag budget_exceeded
    result = await assemble_fail()
    assert result.meta["budget_exceeded"] is True
    assert result.content == "TooLongForBudget"


@pytest.mark.asyncio
async def test_context_freshness_sla() -> None:
    mock_store = AsyncMock()
    # Mock pipeline for writes
    mock_pipeline = MagicMock()
    mock_pipeline.set.return_value = None
    mock_pipeline.sadd.return_value = None
    mock_pipeline.expire.return_value = None
    mock_pipeline.execute = AsyncMock(return_value=None)

    # Override pipeline method to be sync
    mock_store.pipeline = MagicMock(return_value=mock_pipeline)

    # Mock set for trace writing (which uses backend.set, async)
    mock_store.set.return_value = None

    # Create an "Old" context
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)
    old_ctx = Context(
        id="old",
        content="Old Content",
        meta={"timestamp": old_time.isoformat(), "name": "fresh_ctx"},
        version="v1",
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
    assert result_lax.content == "Old Content"
    assert result_lax.id == "old"


@pytest.mark.asyncio
async def test_context_budget_priority() -> None:
    # Setup counter: length of content
    mock_counter = MagicMock()
    mock_counter.count.side_effect = lambda x: len(x)

    @context(name="priority_ctx", max_tokens=25, token_counter=mock_counter)
    async def assemble_priority() -> list[ContextItem]:
        return [
            # High Priority (should be kept last if dropping required)
            ContextItem(content="Keep1", priority=10, required=False),  # 5 chars
            # Low Priority (should be dropped first)
            ContextItem(content="Drop1", priority=1, required=False),  # 5 chars
            # Medium Priority (dropped second if needed)
            ContextItem(content="Drop2", priority=5, required=False),  # 5 chars
            # Required (Never dropped)
            ContextItem(content="ReqItem", priority=0, required=True),  # 7 chars
        ]

    # Total chars: 5+5+5+7 = 22. Wait.
    # We want to force a drop.
    # 22 <= 25 budget. Nothing dropped.

    # Let's adjust budget to force partial drop.
    # Budget = 15.
    # Req(7) + Keep1(5) = 12. Safe.
    # Req(7) + Keep1(5) + Drop2(5) = 17 > 15. Drop Drop2?
    # Req(7) + Keep1(5) + Drop1(5) = 17 > 15. Drop Drop1?

    # Priority order ascending (drop first): Drop1 (1), Drop2 (5), Keep1 (10).
    # 1. Drop Drop1. Remaining: Req(7)+Keep1(5)+Drop2(5) = 17. Still > 15.
    # 2. Drop Drop2. Remaining: Req(7)+Keep1(5) = 12. <= 15. Stop.

    # Result should have ReqItem and Keep1.

    await assemble_priority()
    # Wait, budget above needs to be adjusted.
    # If I set max_tokens to 15?
    pass


@pytest.mark.asyncio
async def test_context_budget_priority_execution() -> None:
    # Separate test to execute with correct params
    mock_counter = MagicMock()
    mock_counter.count.side_effect = lambda x: len(x)

    @context(name="priority_ctx_exec", max_tokens=15, token_counter=mock_counter)
    async def assemble_priority_exec() -> list[ContextItem]:
        return [
            ContextItem(content="Keep1", priority=10, required=False),  # 5
            ContextItem(content="Drop1", priority=1, required=False),  # 5
            ContextItem(content="Drop2", priority=5, required=False),  # 5
            ContextItem(content="ReqItem", priority=0, required=True),  # 7
        ]

    ctx = await assemble_priority_exec()

    # Expected: Drop1 and Drop2 are dropped. Keep1 and ReqItem remain.
    assert "ReqItem" in ctx.content
    assert "Keep1" in ctx.content
    assert "Drop1" not in ctx.content
    assert "Drop2" not in ctx.content
    assert ctx.meta["dropped_items"] == 2
