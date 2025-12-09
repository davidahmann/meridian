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
from meridian.utils.pricing import estimate_cost
from meridian.models import ContextTrace
from meridian.observability import ContextMetrics
import time

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
    version: str = Field("v1", description="Schema version of this context")

    @property
    def is_fresh(self) -> bool:
        return self.meta.get("freshness_status") == "guaranteed"

    def _repr_html_(self) -> str:
        status_color = "#1e8e3e" if self.is_fresh else "#d93025"
        status_text = "FRESH" if self.is_fresh else "DEGRADED"

        # Format content with some line truncation for display
        content_preview = (
            self.content[:500] + "..." if len(self.content) > 500 else self.content
        )
        content_html = content_preview.replace("\n", "<br>")

        return f"""
        <div style="font-family: -apple-system, sans-serif; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; max-width: 800px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3 style="margin: 0; color: #202124;">Context Assembly</h3>
                <span style="background-color: {status_color}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;">{status_text}</span>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 13px; color: #5f6368; margin-bottom: 15px; background: #f8f9fa; padding: 10px; border-radius: 6px;">
                <div><strong>ID:</strong> <code>{self.id}</code></div>
                <div><strong>Timestamp:</strong> {self.meta.get('timestamp', 'N/A')}</div>
                <div><strong>Dropped Items:</strong> {self.meta.get('dropped_items', 0)}</div>
                <div><strong>Sources:</strong> {len(self.meta.get('source_ids', []))}</div>
            </div>

            <div style="background-color: #f1f3f4; padding: 15px; border-radius: 6px; font-family: monospace; font-size: 12px; line-height: 1.5; color: #333; max-height: 300px; overflow-y: auto;">
                {content_html}
            </div>
        </div>
        """


def context(
    name: Optional[str] = None,
    max_tokens: Optional[int] = None,
    cache_ttl: Optional[timedelta] = timedelta(minutes=5),
    token_counter: Optional[TokenCounter] = None,
    max_staleness: Optional[timedelta] = None,
    version: str = "v1",
    model: str = "gpt-4",
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
            metrics = ContextMetrics(context_name)
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
                            metrics.record_cache_hit()
                            return cached_ctx
                except Exception as e:
                    logger.warning("context_cache_read_error", error=str(e))

            # 1. Generate Identity
            ctx_id = str(uuid6.uuid7())
            logger.info("context_assembly_start", context_id=ctx_id, name=context_name)

            # 2. Execute
            start_time = time.time()
            try:
                with metrics:
                    result = await func(*args, **kwargs)
                counter = token_counter or _default_counter

                final_content = ""
                dropped_items = 0
                source_ids = []
                stale_sources = []
                # Timestamps for sources to determine overall freshness if needed

                # 3. Handle Prioritization if List[ContextItem]
                token_usage = 0  # Initialize for usage in step 4

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

                            # Strategy: Collect optional items, sort by priority (lowest 0 -> drop first), then drop.
                            # We keep indices to remove them from the original list order.
                            candidates = []
                            for idx, item in enumerate(items):
                                if not item.required:
                                    candidates.append((idx, item))

                            # Sort by priority ascending (0..1..2). Low priority dropped first.
                            # Secondary sort by index descending (drop from bottom if priorities equal)
                            candidates.sort(key=lambda x: (x[1].priority, -x[0]))

                            indices_to_drop = set()
                            for idx, item in candidates:
                                if total_tokens <= max_tokens:
                                    break
                                item_tokens = counter.count(item.content)
                                total_tokens -= item_tokens
                                indices_to_drop.add(idx)

                            if total_tokens > max_tokens:
                                # Graceful Degradation: Do not raise, just warn and flag.
                                logger.warning(
                                    "context_budget_overflow",
                                    total=total_tokens,
                                    limit=max_tokens,
                                    msg="Required items exceed budget. Returning partial/overflow context.",
                                )
                                # We continue with what we have (required items)

                            items = [
                                item
                                for i, item in enumerate(items)
                                if i not in indices_to_drop
                            ]
                            dropped_items = len(indices_to_drop)

                        token_usage = total_tokens

                    final_content = "\n".join(i.content for i in items)

                else:
                    final_content = str(result)
                    if max_tokens and counter:
                        current_tokens = counter.count(final_content)
                        if current_tokens > max_tokens:
                            logger.warning(
                                "context_budget_overflow",
                                total=current_tokens,
                                limit=max_tokens,
                                msg="Raw string context exceeds budget.",
                            )
                            # We optionally truncate here?
                            # For raw string, let's just flag it.
                            pass
                        token_usage = current_tokens

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
                        "budget_exceeded": (token_usage > max_tokens)
                        if max_tokens
                        else False,
                    },
                    version=version,
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

                # 6. Observability: Record Trace & Metrics
                # usage is already calculated? If counter set.
                if counter and token_usage == 0:
                    # This happens if max_tokens was None but we want usage?
                    # The default counter is set if max_tokens is set.
                    # If max_tokens is None, counter might be None.
                    # But we allow passing explicit token_counter even if max_tokens None?
                    # Decorator: `_default_counter = OpenAITokenCounter() if max_tokens else None`
                    # So if max_tokens is None and no counter passed, counter is None.
                    pass
                elif not counter and token_counter:
                    # Should not happen
                    pass

                # If we have a counter but didn't run budget logic (e.g. max_tokens None), we should count now?
                # The existing code did "Recalculate tokens for metric if not done"
                # Logic:
                if counter:
                    if token_usage == 0 and len(final_content) > 0:
                        token_usage = counter.count(final_content)
                    metrics.record_tokens(token_usage)

                # Calculate Cost
                cost_usd = estimate_cost(model, token_usage)

                trace = ContextTrace(
                    context_id=ctx_id,
                    latency_ms=(time.time() - start_time) * 1000,
                    token_usage=token_usage,
                    freshness_status=freshness_status,
                    source_ids=source_ids,  # collected in step 3
                    stale_sources=stale_sources,
                    cost_usd=cost_usd,
                    cache_hit=False,
                )

                # Add cost to context meta
                ctx.meta["cost_usd"] = cost_usd

                if backend:
                    try:
                        # Save trace with 24h TTL
                        await backend.set(
                            f"trace:{ctx_id}", trace.model_dump_json(), ex=86400
                        )
                    except Exception as e:
                        logger.warning("context_trace_write_error", error=str(e))

                logger.info(
                    "context_assembly_complete",
                    context_id=ctx_id,
                    length=len(final_content),
                    cost=cost_usd,
                )
                return ctx

            except Exception as e:
                logger.error("context_assembly_failed", context_id=ctx_id, error=str(e))
                raise e

        # Mark it so we can find it in the registry if needed
        wrapper._is_context = True  # type: ignore[attr-defined]
        return wrapper

    return decorator
