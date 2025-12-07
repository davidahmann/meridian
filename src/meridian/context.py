from __future__ import annotations
import functools
import structlog
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field
import uuid6
import hashlib
import json
from datetime import datetime, timezone, timedelta
from meridian.utils.tokens import TokenCounter, OpenAITokenCounter

logger = structlog.get_logger()


class ContextBudgetError(Exception):
    """Raised when context exceeds max_tokens even after dropping optional items."""

    pass


class ContextItem(BaseModel):
    content: str
    required: bool = True
    priority: int = 0  # 0 is lowest (dropped first)
    source_id: Optional[str] = None  # Feature ID or source identifier
    last_updated: Optional[datetime] = None  # When this specific item was last updated


class Context(BaseModel):
    """
    Represents the fully assembled context ready for LLM consumption.
    """

    id: str = Field(
        ..., description="Unique UUIDv7 identifier for this context assembly"
    )
    content: str = Field(..., description="The final assembled text content")
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata including timestamp, source_ids, and freshness_status",
    )

    @property
    def is_fresh(self) -> bool:
        return self.meta.get("freshness_status") == "guaranteed"


def context(
    name: Optional[str] = None,
    max_tokens: Optional[int] = None,
    cache_ttl: Optional[timedelta] = None,
    token_counter: Optional[TokenCounter] = None,
    max_staleness: Optional[timedelta] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to define a Context Assembly function.

    Args:
        name: Logical name.
        max_tokens: Hard budget.
        cache_ttl: TTL.
        token_counter: Counter to use (defaults to OpenAI if max_tokens set).
        max_staleness: Max acceptable age of the context.
    """
    # Default counter if needed
    _default_counter = OpenAITokenCounter() if max_tokens else None

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        context_name = name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Context:
            # 0. Check Cache (implementation omitted for brevity in this view, assuming previous code remains)
            # ... (Existing cache logic) ...

            # (Re-implementing Cache check here to ensure contiguous replacement works)
            backend = getattr(wrapper, "_cache_backend", None)

            if cache_ttl and backend:
                key_str = f"{args}-{kwargs}"
                arg_hash = hashlib.sha256(key_str.encode()).hexdigest()
                cache_key = f"context:{context_name}:{arg_hash}"
                try:
                    cached_bytes = await backend.get(cache_key)
                    if cached_bytes:
                        data = json.loads(cached_bytes)
                        cached_ctx = Context(**data)

                        # CHECK FRESHNESS SLA
                        is_fresh = True
                        if max_staleness:
                            # accessing meta["timestamp"], assuming isoformat
                            ts_str = cached_ctx.meta.get("timestamp")
                            if ts_str:
                                ts = datetime.fromisoformat(ts_str)
                                # Ensure ts is aware if needed, generic comparison
                                age = datetime.now(timezone.utc) - ts
                                if age > max_staleness:
                                    logger.info(
                                        "context_cache_stale",
                                        age=str(age),
                                        limit=str(max_staleness),
                                    )
                                    is_fresh = False

                        if is_fresh:
                            logger.info("context_cache_hit", name=context_name)
                            return cached_ctx
                except Exception as e:
                    logger.warning("context_cache_read_error", error=str(e))

            # 1. Generate Identity
            ctx_id = str(uuid6.uuid7())
            logger.info("context_assembly_start", context_id=ctx_id, name=context_name)

            # 2. Execute
            try:
                result = await func(*args, **kwargs)
                counter = token_counter or _default_counter

                final_content = ""
                dropped_items = 0
                source_ids = []
                stale_sources = []
                # Timestamps for sources to determine overall freshness if needed

                # 3. Handle Prioritization if List[ContextItem]
                if isinstance(result, list) and all(
                    isinstance(x, ContextItem) for x in result
                ):
                    items: List[ContextItem] = result

                    # Collect metadata before potentially dropping
                    for item in items:
                        if item.source_id:
                            source_ids.append(item.source_id)
                        # Check item staleness if item has last_updated
                        if max_staleness and item.last_updated:
                            age = datetime.now(timezone.utc) - item.last_updated
                            if age > max_staleness:
                                stale_sources.append(item.source_id or "unknown")

                    if max_tokens and counter:
                        # ... (existing budgeting logic) ...
                        current_text = "".join(i.content for i in items)
                        total_tokens = counter.count(current_text)

                        if total_tokens > max_tokens:
                            logger.info(
                                "context_budget_exceeded",
                                total=total_tokens,
                                limit=max_tokens,
                            )

                            indices_to_drop = []
                            for idx in range(len(items) - 1, -1, -1):
                                if total_tokens <= max_tokens:
                                    break
                                item = items[idx]
                                if not item.required:
                                    item_tokens = counter.count(item.content)
                                    total_tokens -= item_tokens
                                    indices_to_drop.append(idx)

                            if total_tokens > max_tokens:
                                raise ContextBudgetError(
                                    f"Budget {max_tokens} exceeded ({total_tokens}) with only required items."
                                )

                            items = [
                                item
                                for i, item in enumerate(items)
                                if i not in indices_to_drop
                            ]
                            dropped_items = len(indices_to_drop)

                    final_content = "\n".join(i.content for i in items)

                else:
                    final_content = str(result)
                    if max_tokens and counter:
                        if counter.count(final_content) > max_tokens:
                            raise ContextBudgetError(
                                f"Budget {max_tokens} exceeded on raw string context."
                            )

                # Determine Freshness Status
                # "guaranteed" = newly assembled (we just ran it)
                # OR (cache hit + fresh).
                # Since we are in the re-compute block, this is guaranteed fresh *execution*.
                # BUT if input sources were stale, is it "degraded"?
                # Plan says: "Result includes stale_sources".
                freshness_status = "guaranteed"
                if stale_sources:
                    freshness_status = "degraded"

                # 4. Construct Context
                ctx = Context(
                    id=ctx_id,
                    content=final_content,
                    meta={
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "name": context_name,
                        "status": "assembled",
                        "dropped_items": dropped_items,
                        "source_ids": source_ids,
                        "freshness_status": freshness_status,
                        "stale_sources": stale_sources,
                    },
                )

                # 5. Write to Cache
                if cache_ttl and backend:
                    try:
                        serialized = ctx.model_dump_json()
                        pipeline = backend.pipeline()
                        pipeline.set(
                            cache_key, serialized, ex=int(cache_ttl.total_seconds())
                        )

                        # Store reverse mapping for invalidation: dependency:{source_id} -> cache_key
                        # We use a set.
                        for src_id in source_ids:
                            dep_key = f"dependency:{src_id}"
                            pipeline.sadd(dep_key, cache_key)
                            # Expire dependency key eventually too (e.g. 2x TTL) to prevent leaks?
                            # Or just let it persist? Leaking sets is bad.
                            # Ideally we set TTL, but adding to set doesn't refresh TTL of set.
                            # Best effort for MVP: Set TTL if not exists.
                            pipeline.expire(dep_key, int(cache_ttl.total_seconds()) * 2)

                        await pipeline.execute()

                    except Exception as e:
                        logger.warning("context_cache_write_error", error=str(e))

                logger.info(
                    "context_assembly_complete",
                    context_id=ctx_id,
                    length=len(final_content),
                )
                return ctx

            except Exception as e:
                logger.error("context_assembly_failed", context_id=ctx_id, error=str(e))
                raise e

        # Mark it so we can find it in the registry if needed
        wrapper._is_context = True  # type: ignore[attr-defined]
        return wrapper

    return decorator
