from __future__ import annotations
import functools
import structlog
from typing import List, Dict, Any, Optional, Callable, Literal
from pydantic import BaseModel, Field
import uuid6
import hashlib
import json
from datetime import datetime, timezone, timedelta
from contextvars import ContextVar
from meridian.utils.tokens import TokenCounter, OpenAITokenCounter
from meridian.utils.pricing import estimate_cost
from meridian.utils.time import parse_duration_to_ms, InvalidSLAFormatError
from meridian.models import (
    ContextTrace,
    ContextLineage,
    FeatureLineage,
    RetrieverLineage,
)
from meridian.observability import ContextMetrics
from meridian.exceptions import FreshnessSLAError
import time

# Type for freshness status
FreshnessStatus = Literal["guaranteed", "degraded", "unknown"]

logger = structlog.get_logger()


# Assembly Tracking using contextvars
# This allows us to track feature/retriever calls within a @context decorated function
_assembly_tracker: ContextVar[Optional["AssemblyTracker"]] = ContextVar(
    "meridian_assembly_tracker", default=None
)


class AssemblyTracker:
    """
    Tracks feature and retriever usage during context assembly.
    Used internally by the @context decorator to build lineage.
    """

    def __init__(self, context_id: str) -> None:
        self.context_id = context_id
        self.features: List[FeatureLineage] = []
        self.retrievers: List[RetrieverLineage] = []
        self.start_time = datetime.now(timezone.utc)

    def record_feature(
        self,
        feature_name: str,
        entity_id: str,
        value: Any,
        timestamp: datetime,
        source: str,
    ) -> None:
        """Record a feature retrieval during assembly."""
        freshness_ms = int(
            (datetime.now(timezone.utc) - timestamp).total_seconds() * 1000
        )
        self.features.append(
            FeatureLineage(
                feature_name=feature_name,
                entity_id=entity_id,
                value=value,
                timestamp=timestamp,
                freshness_ms=freshness_ms,
                source=source,  # type: ignore
            )
        )

    def record_retriever(
        self,
        retriever_name: str,
        query: str,
        results_count: int,
        latency_ms: float,
        index_name: Optional[str] = None,
    ) -> None:
        """Record a retriever call during assembly."""
        self.retrievers.append(
            RetrieverLineage(
                retriever_name=retriever_name,
                query=query,
                results_count=results_count,
                latency_ms=latency_ms,
                index_name=index_name,
            )
        )

    def get_stalest_feature_ms(self) -> int:
        """Return the age in ms of the oldest feature used."""
        if not self.features:
            return 0
        return max(f.freshness_ms for f in self.features)


def get_current_tracker() -> Optional[AssemblyTracker]:
    """Get the current assembly tracker if within a @context call."""
    return _assembly_tracker.get()


def record_feature_usage(
    feature_name: str,
    entity_id: str,
    value: Any,
    timestamp: Optional[datetime] = None,
    source: str = "compute",
) -> None:
    """
    Record feature usage for lineage tracking.
    Call this from get_feature/get_online_features to track usage.
    """
    tracker = _assembly_tracker.get()
    if tracker:
        tracker.record_feature(
            feature_name=feature_name,
            entity_id=entity_id,
            value=value,
            timestamp=timestamp or datetime.now(timezone.utc),
            source=source,
        )


def record_retriever_usage(
    retriever_name: str,
    query: str,
    results_count: int,
    latency_ms: float,
    index_name: Optional[str] = None,
) -> None:
    """
    Record retriever usage for lineage tracking.
    Call this from retriever execution to track usage.
    """
    tracker = _assembly_tracker.get()
    if tracker:
        tracker.record_retriever(
            retriever_name=retriever_name,
            query=query,
            results_count=results_count,
            latency_ms=latency_ms,
            index_name=index_name,
        )


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
    lineage: Optional[ContextLineage] = Field(
        None, description="Full lineage tracking what data sources were used"
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

        # Token budget bar
        token_usage = self.meta.get("token_usage", 0)
        max_tokens = self.meta.get("max_tokens")
        token_bar_html = ""  # nosec B105 - not a password, HTML content

        if max_tokens and max_tokens > 0:
            usage_pct = min(100, (token_usage / max_tokens) * 100)
            # Color gradient: green (<70%), yellow (70-90%), red (>90%)
            if usage_pct < 70:
                bar_color = "#1e8e3e"  # green
            elif usage_pct < 90:
                bar_color = "#f9ab00"  # yellow
            else:
                bar_color = "#d93025"  # red

            token_bar_html = f"""
            <div style="margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between; font-size: 12px; color: var(--text-color, #5f6368); margin-bottom: 4px;">
                    <span><strong>Token Budget</strong></span>
                    <span>{token_usage:,} / {max_tokens:,} ({usage_pct:.1f}%)</span>
                </div>
                <div style="background-color: var(--secondary-background-color, #e0e0e0); border-radius: 4px; height: 8px; overflow: hidden;">
                    <div style="background: linear-gradient(90deg, {bar_color} 0%, {bar_color} 100%); width: {usage_pct}%; height: 100%; border-radius: 4px; transition: width 0.3s ease;"></div>
                </div>
            </div>
            """

        # Cost display
        cost_usd = self.meta.get("cost_usd", 0)
        cost_html = f"${cost_usd:.6f}" if cost_usd else "N/A"

        return f"""
        <div style="font-family: -apple-system, sans-serif; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; max-width: 800px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); background-color: var(--background-color, white); color: var(--text-color, #333);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3 style="margin: 0; color: var(--text-color, #202124);">Context Assembly</h3>
                <div>
                    <span style="background-color: {status_color}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;">{status_text}</span>
                    {'<span style="background-color: #673ab7; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; margin-left: 5px;">⚡ CACHED</span>' if self.meta.get("is_cached_response") else ''}
                </div>
            </div>

            {token_bar_html}

            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; font-size: 13px; color: var(--text-color, #5f6368); margin-bottom: 15px; background: var(--secondary-background-color, #f8f9fa); padding: 12px; border-radius: 6px;">
                <div><strong>ID:</strong><br><code style="font-size: 11px;">{self.id[:12]}...</code></div>
                <div><strong>Cost:</strong><br>{cost_html}</div>
                <div><strong>Dropped:</strong><br>{self.meta.get('dropped_items', 0)} items</div>
                <div><strong>Sources:</strong><br>{len(self.meta.get('source_ids', []))} refs</div>
            </div>

            <div style="background-color: var(--secondary-background-color, #f1f3f4); padding: 15px; border-radius: 6px; font-family: monospace; font-size: 12px; line-height: 1.5; color: var(--text-color, #333); max-height: 300px; overflow-y: auto; border: 1px solid var(--text-color-20, transparent);">
                {content_html}
            </div>
        </div>
        """


def context(
    store: Optional[Any] = None,  # Accepts FeatureStore
    name: Optional[str] = None,
    max_tokens: Optional[int] = None,
    cache_ttl: Optional[timedelta] = timedelta(minutes=5),
    token_counter: Optional[TokenCounter] = None,
    max_staleness: Optional[timedelta] = None,
    version: str = "v1",
    model: str = "gpt-4",
    freshness_sla: Optional[str] = None,  # e.g., "5m", "1h", "30s"
    freshness_strict: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to define a Context Assembly function.

    Args:
        store: FeatureStore instance (optional, enables caching).
        name: Logical name.
        max_tokens: Hard budget.
        cache_ttl: TTL.
        token_counter: Counter to use (defaults to OpenAI if max_tokens set).
        max_staleness: Max acceptable age of the context.
        freshness_sla: Maximum age for features used in this context.
            If any feature exceeds this age, freshness_status becomes "degraded".
            Format: "30s", "5m", "1h", "1d"
        freshness_strict: If True, raise FreshnessSLAError when SLA is breached.
            Default is False (graceful degradation).
    """
    # Handle case where named args are used but store is passed as name or skipped
    # If store is really a name (str)? No, type hint helps.
    # But python decorators are tricky. @context(max_tokens=100) -> store is None.

    # Parse and validate freshness_sla upfront
    freshness_sla_ms: Optional[int] = None
    if freshness_sla:
        try:
            freshness_sla_ms = parse_duration_to_ms(freshness_sla)
        except InvalidSLAFormatError as e:
            raise InvalidSLAFormatError(f"Invalid freshness_sla format: {e}") from e

    # Default counter if needed
    _default_counter = OpenAITokenCounter() if max_tokens else None

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        context_name = name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Context:
            metrics = ContextMetrics(context_name)

            # Resolve Backend: Use passed store or attached attribute
            backend = getattr(wrapper, "_cache_backend", None)
            if not backend and store and hasattr(store, "online_store"):
                backend = store.online_store
                # Cache it for future calls
                setattr(wrapper, "_cache_backend", backend)

            # 0. Check Cache (implementation omitted for brevity in this view, assuming previous code remains)

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
                            cached_ctx.meta["is_cached_response"] = True
                            logger.info("context_cache_hit", name=context_name)
                            metrics.record_cache_hit()
                            return cached_ctx
                except Exception as e:
                    logger.warning("context_cache_read_error", error=str(e))

            # 1. Generate Identity
            ctx_id = str(uuid6.uuid7())
            logger.info("context_assembly_start", context_id=ctx_id, name=context_name)

            # 1.5 Create Assembly Tracker for lineage collection
            tracker = AssemblyTracker(context_id=ctx_id)
            tracker_token = _assembly_tracker.set(tracker)

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
                freshness_status: FreshnessStatus = "guaranteed"
                freshness_violations: List[Dict[str, Any]] = []

                # Check freshness SLA against tracked features (v1.5)
                if freshness_sla_ms:
                    for feat in tracker.features:
                        if feat.freshness_ms > freshness_sla_ms:
                            freshness_violations.append(
                                {
                                    "feature": feat.feature_name,
                                    "age_ms": feat.freshness_ms,
                                    "sla_ms": freshness_sla_ms,
                                }
                            )
                            # Also add to stale_sources for backwards compat
                            if feat.feature_name not in stale_sources:
                                stale_sources.append(feat.feature_name)

                    if freshness_violations:
                        freshness_status = "degraded"
                        # Record metrics for each violation
                        for v in freshness_violations:
                            metrics.record_freshness_violation(v["feature"])
                        logger.warning(
                            "context_freshness_sla_breached",
                            context_id=ctx_id,
                            violations=freshness_violations,
                        )

                        # Strict mode: raise exception on SLA breach
                        if freshness_strict:
                            raise FreshnessSLAError(
                                f"Freshness SLA breached for {len(freshness_violations)} feature(s)",
                                violations=freshness_violations,
                            )

                # Legacy: also mark degraded if stale_sources were found via max_staleness
                if stale_sources:
                    freshness_status = "degraded"

                # Record freshness metrics (v1.5)
                metrics.record_freshness_status(freshness_status)
                stalest_ms = tracker.get_stalest_feature_ms()
                if stalest_ms > 0:
                    metrics.record_stalest_feature(
                        stalest_ms / 1000.0
                    )  # Convert to seconds

                # 4. Construct Context (lineage will be attached later if offline_store available)
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
                        "freshness_violations": freshness_violations,  # v1.5
                        "freshness_sla_ms": freshness_sla_ms,  # v1.5
                        "stale_sources": stale_sources,
                        "budget_exceeded": (token_usage > max_tokens)
                        if max_tokens
                        else False,
                    },
                    lineage=None,
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

                # Add cost and token info to context meta
                ctx.meta["cost_usd"] = cost_usd
                ctx.meta["token_usage"] = token_usage
                ctx.meta["max_tokens"] = max_tokens

                if backend:
                    try:
                        # Save trace with 24h TTL
                        await backend.set(
                            f"trace:{ctx_id}", trace.model_dump_json(), ex=86400
                        )
                    except Exception as e:
                        logger.warning("context_trace_write_error", error=str(e))

                # 7. Log context to offline store for replay/audit
                # Get offline store from the FeatureStore if available
                offline_store = None
                if store and hasattr(store, "offline_store"):
                    offline_store = store.offline_store

                if offline_store and hasattr(offline_store, "log_context"):
                    try:
                        # Build full lineage using tracker data
                        lineage_data = ContextLineage(
                            context_id=ctx_id,
                            timestamp=datetime.now(timezone.utc),
                            # Include tracked features and retrievers
                            features_used=tracker.features,
                            retrievers_used=tracker.retrievers,
                            # Assembly statistics
                            items_provided=len(result)
                            if isinstance(result, list)
                            else 1,
                            items_included=len(result) - dropped_items
                            if isinstance(result, list)
                            else 1,
                            items_dropped=dropped_items,
                            # Freshness tracking
                            freshness_status=freshness_status,
                            stalest_feature_ms=tracker.get_stalest_feature_ms(),
                            # Token economics
                            token_usage=token_usage,
                            max_tokens=max_tokens,
                            estimated_cost_usd=cost_usd,
                        )

                        # Attach lineage to context
                        ctx.lineage = lineage_data

                        await offline_store.log_context(
                            context_id=ctx_id,
                            timestamp=datetime.fromisoformat(ctx.meta["timestamp"]),
                            content=final_content,
                            lineage=lineage_data.model_dump(),
                            meta=ctx.meta,
                            version=version,
                        )
                    except Exception as e:
                        # Log but don't fail assembly - graceful degradation
                        logger.warning(
                            "context_log_failed", context_id=ctx_id, error=str(e)
                        )

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
            finally:
                # Always reset the tracker token
                _assembly_tracker.reset(tracker_token)

        # Mark it so we can find it in the registry if needed
        wrapper._is_context = True  # type: ignore[attr-defined]
        return wrapper

    return decorator
