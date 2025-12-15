from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    Response,
    Depends,
    Security,
    APIRouter,
)
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from typing import List, Dict, Any, cast, AsyncGenerator, Optional
import time
import os
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from .core import FeatureStore
from .models import ContextTrace
from .context import EvidencePersistenceError
import structlog
from datetime import datetime, timezone
import json
import html

try:
    from opentelemetry import trace  # type: ignore
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # type: ignore

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None

logger = structlog.get_logger()

# Trace Provider (No-op if not configured by environment)
tracer = trace.get_tracer("fabra") if OTEL_AVAILABLE else None

# Metrics
REQUEST_COUNT = Counter(
    "fabra_request_count", "Total request count", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "fabra_request_latency_seconds", "Request latency", ["method", "endpoint"]
)


class FeatureRequest(BaseModel):
    entity_name: str
    entity_id: str
    features: List[str]


class BatchFeatureRequest(BaseModel):
    name: str  # entity_name
    ids: List[str]
    features: List[str]


API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def get_api_key(
    api_key_header: str = Security(api_key_header),
) -> str:
    expected_key = os.getenv("FABRA_API_KEY")
    # If no key is configured, allow all (dev mode)
    if not expected_key:
        return "dev-mode"

    import secrets

    if api_key_header and secrets.compare_digest(api_key_header, expected_key):
        return api_key_header

    raise HTTPException(status_code=403, detail="Could not validate credentials")


def create_app(store: FeatureStore) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Startup
        logger.info("server_startup")
        yield
        # Shutdown
        logger.info("server_shutdown")
        if hasattr(store.offline_store, "engine"):
            await store.offline_store.engine.dispose()
        if hasattr(store.online_store, "client"):
            await store.online_store.client.aclose()
        elif hasattr(store.online_store, "redis"):
            await store.online_store.redis.aclose()

    app = FastAPI(title="Fabra Feature Store API", lifespan=lifespan)

    if OTEL_AVAILABLE:
        # Instrument FastAPI automatically
        # This adds spans for every request
        FastAPIInstrumentor.instrument_app(app)

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next: Any) -> Response:
        start_time = time.time()
        response = cast(Response, await call_next(request))
        process_time = time.time() - start_time

        REQUEST_LATENCY.labels(
            method=request.method, endpoint=request.url.path
        ).observe(process_time)

        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code,
        ).inc()

        # Audit Log for Modifications
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            # Extract user_id from API key (simplified)
            # In real world, we'd decode JWT or look up key owner.
            # Here we just use the hash prefix or 'dev' if public.
            api_key = request.headers.get("X-API-Key", "public")
            user_id = "dev_user" if api_key == "public" else f"key_{hash(api_key)}"

            logger.info(
                "audit_log",
                audit=True,
                user_id=user_id,
                method=request.method,
                path=request.url.path,
                status=response.status_code,
            )

        return response

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # V1 Router
    v1_router = APIRouter(prefix="/v1")

    @v1_router.post("/features/batch")
    async def get_batch_features(
        request: BatchFeatureRequest, api_key: str = Depends(get_api_key)
    ) -> Dict[str, Any]:
        """
        Batch retrieve features for multiple entities.
        """
        results = {}
        for entity_id in request.ids:
            try:
                # Reuse existing logic (sequentially for MVP, parallelize later)
                # In a real impl, we'd add store.get_online_features_batch
                feats = await store.get_online_features(
                    entity_name=request.name,
                    entity_id=entity_id,
                    features=request.features,
                )
                results[entity_id] = feats
            except Exception as e:
                logger.error("batch_feature_error", entity_id=entity_id, error=str(e))
                results[entity_id] = {"error": str(e)}
        return results

    @v1_router.post("/features")
    async def get_features(
        request: FeatureRequest, api_key: str = Depends(get_api_key)
    ) -> Dict[str, Any]:
        """
        Retrieves online features for a specific entity.
        """
        try:
            features = await store.get_online_features(
                entity_name=request.entity_name,
                entity_id=request.entity_id,
                features=request.features,
            )
            return features
        except Exception as e:
            logger.error("Error retrieving features", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/features/{feature_name}")
    async def get_single_feature(
        feature_name: str,
        entity_id: str,
        api_key: str = Depends(get_api_key),
    ) -> Dict[str, Any]:
        """
        Simple GET endpoint to retrieve a single feature value.

        Returns {"value": ..., "freshness_ms": 0, "served_from": "online"}
        """
        try:
            # Find the entity for this feature
            feature_def = store.registry.features.get(feature_name)
            if not feature_def:
                raise HTTPException(
                    status_code=404, detail=f"Feature '{feature_name}' not found"
                )

            entity_name = feature_def.entity_name

            # Fetch from online store (prefer metadata path) so we can compute freshness.
            raw_meta = None
            if hasattr(store.online_store, "get_online_features_with_meta"):
                try:
                    raw_meta = await store.online_store.get_online_features_with_meta(
                        entity_name=entity_name,
                        entity_id=entity_id,
                        feature_names=[feature_name],
                    )
                except NotImplementedError:
                    raw_meta = None

            freshness_ms = 0
            served_from = "online"

            if raw_meta is not None:
                if feature_name not in raw_meta:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Feature '{feature_name}' not found for entity '{entity_id}'",
                    )
                val = raw_meta[feature_name]
                as_of_raw = val.get("as_of") if isinstance(val, dict) else None
                if isinstance(as_of_raw, str):
                    try:
                        as_of_dt = datetime.fromisoformat(
                            as_of_raw.replace("Z", "+00:00")
                        )
                        freshness_ms = int(
                            (datetime.now(timezone.utc) - as_of_dt).total_seconds()
                            * 1000
                        )
                    except Exception:
                        freshness_ms = 0
                value = val.get("value") if isinstance(val, dict) else val
            else:
                raw = await store.online_store.get_online_features(
                    entity_name=entity_name,
                    entity_id=entity_id,
                    feature_names=[feature_name],
                )
                if feature_name not in raw:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Feature '{feature_name}' not found for entity '{entity_id}'",
                    )
                value = raw[feature_name]

            return {
                "value": value,
                "freshness_ms": freshness_ms,
                "served_from": served_from,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error("get_single_feature_error", feature=feature_name, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @v1_router.post("/ingest/{event_type}", status_code=202)
    async def ingest_event(
        event_type: str,
        payload: Dict[str, Any],
        entity_id: str,
        api_key: str = Depends(get_api_key),
    ) -> Dict[str, str]:
        """
        Ingests an event into the Axiom Event Bus.
        """
        if not event_type.replace("_", "").isalnum():
            raise HTTPException(
                status_code=400,
                detail="Event type must be alphanumeric (underscores allowed)",
            )

        from fabra.events import AxiomEvent
        from fabra.bus import RedisEventBus

        # We need a Redis connection. Since store has online_store (Redis),
        # we can try to reuse it or create a temporary one.
        # Ideally, we inject RedisEventBus.
        # For this MVP, we will try to reuse store.online_store if it is Redis.
        # Otherwise, we create a fresh Redis connection using config logic
        # (simulated by instantiating RedisEventBus with new connection or getting it from store).

        # Check if store.online_store has a client
        client = None
        if hasattr(store.online_store, "client"):
            client = store.online_store.client
        elif hasattr(store.online_store, "redis"):
            client = store.online_store.redis

        if not client:
            # Fallback: create fresh client
            from redis.asyncio import Redis

            from fabra.config import get_redis_url

            url = get_redis_url()
            client = Redis.from_url(url, decode_responses=True)

        bus = RedisEventBus(client)
        event = AxiomEvent(event_type=event_type, entity_id=entity_id, payload=payload)
        msg_id = await bus.publish(event)

        # If we created a fresh client, we should close it?
        # If it's shared from store, DON'T close it.
        # To avoid complexity, let's rely on Python GC or context manager if possible.
        # Ideally, use dependency injection with lifecycle.

        # Trigger Hooks
        await store.hooks.trigger_after_ingest(
            event_type=event_type, entity_id=entity_id, payload=payload
        )

        return {"msg_id": msg_id, "event_id": str(event.id)}

    @app.get("/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

    @v1_router.get("/contexts")
    async def list_contexts(
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 100,
        name: Optional[str] = None,
        freshness_status: Optional[str] = None,
        api_key: str = Depends(get_api_key),
    ) -> List[Dict[str, Any]]:
        """
        List contexts in a time range for debugging/audit.

        Query params:
            - start: ISO format timestamp (optional)
            - end: ISO format timestamp (optional)
            - limit: max results (default 100)
            - name: filter by context name (optional)
            - freshness_status: filter by status - "guaranteed" or "degraded" (optional)

        Examples:
            GET /v1/contexts?limit=10
            GET /v1/contexts?name=chat_context&freshness_status=degraded
            GET /v1/contexts?start=2024-01-01T00:00:00Z&end=2024-01-02T00:00:00Z
        """
        start_dt = datetime.fromisoformat(start) if start else None
        end_dt = datetime.fromisoformat(end) if end else None

        # Validate freshness_status if provided
        if freshness_status and freshness_status not in ("guaranteed", "degraded"):
            raise HTTPException(
                status_code=400,
                detail="freshness_status must be 'guaranteed' or 'degraded'",
            )

        try:
            contexts = await store.list_contexts(
                start=start_dt,
                end=end_dt,
                limit=limit,
                name=name,
                freshness_status=freshness_status,
            )
            return contexts
        except Exception as e:
            logger.error("list_contexts_failed", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @v1_router.post("/context/{context_name}")
    async def assemble_context(
        context_name: str,
        payload: Dict[str, Any],
        api_key: str = Depends(get_api_key),
    ) -> Dict[str, Any]:
        """
        Assemble a new context by calling the registered context function.

        The payload should contain the arguments expected by the context function.
        For example, if the context function is:
            @context(store, name="chat_context")
            async def chat_context(user_id: str, query: str): ...

        Then the payload should be:
            {"user_id": "user_123", "query": "how do features work?"}

        Returns the assembled context with id, content, meta, and lineage.
        """
        # Find the context function
        if context_name not in store.registry.contexts:
            raise HTTPException(
                status_code=404, detail=f"Context '{context_name}' not found"
            )

        context_func = store.registry.contexts[context_name]

        try:
            # Call the context function with the provided arguments
            ctx = await context_func(**payload)

            # The context decorator returns an AssembledContext
            result: Dict[str, Any] = {
                "id": ctx.id,
                "content": ctx.content,
                "meta": ctx.meta,
            }

            if ctx.lineage:
                result["lineage"] = ctx.lineage.model_dump()

            return result

        except TypeError as e:
            # Missing or invalid arguments
            logger.error(
                "assemble_context_type_error",
                context_name=context_name,
                error=str(e),
            )
            raise HTTPException(
                status_code=400,
                detail=f"Invalid arguments for context '{context_name}': {e}",
            )
        except EvidencePersistenceError as e:
            logger.error(
                "assemble_context_evidence_persist_failed",
                context_name=context_name,
                context_id=e.context_id,
                error=str(e),
            )
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.error(
                "assemble_context_failed",
                context_name=context_name,
                error=str(e),
            )
            raise HTTPException(status_code=500, detail=str(e))

    @v1_router.get("/context/{context_id}")
    async def get_context_by_id(
        context_id: str, api_key: str = Depends(get_api_key)
    ) -> Dict[str, Any]:
        """
        Retrieve a historical context by ID for replay/audit.
        Returns the full context including content and lineage.
        """
        try:
            ctx = await store.get_context_at(context_id)
            if not ctx:
                raise HTTPException(status_code=404, detail="Context not found")

            # Return serialized context
            return {
                "context_id": ctx.id,
                "content": ctx.content,
                "lineage": ctx.lineage.model_dump() if ctx.lineage else None,
                "meta": ctx.meta,
                "version": ctx.version,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error("get_context_failed", context_id=context_id, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @v1_router.get("/record/{context_id}")
    async def get_record_by_id(
        context_id: str, api_key: str = Depends(get_api_key)
    ) -> Dict[str, Any]:
        """
        Retrieve an immutable CRS-001 ContextRecord by ID for audit/verification.
        """
        if not hasattr(store.offline_store, "get_record"):
            raise HTTPException(
                status_code=501,
                detail="Offline store does not support Context Records",
            )

        record_id = context_id if context_id.startswith("ctx_") else f"ctx_{context_id}"

        try:
            record = await store.offline_store.get_record(record_id)
            if not record:
                raise HTTPException(status_code=404, detail="Record not found")
            return record.model_dump(mode="json")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("get_record_failed", context_id=record_id, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @v1_router.get("/context/{context_id}/lineage")
    async def get_context_lineage(
        context_id: str, api_key: str = Depends(get_api_key)
    ) -> Dict[str, Any]:
        """
        Retrieve just the lineage for a context.
        Shows what data sources were used in the context assembly.
        """
        try:
            ctx = await store.get_context_at(context_id)
            if not ctx:
                raise HTTPException(status_code=404, detail="Context not found")

            if not ctx.lineage:
                return {"context_id": context_id, "lineage": None}

            return {
                "context_id": context_id,
                "lineage": ctx.lineage.model_dump(),
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error("get_lineage_failed", context_id=context_id, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @v1_router.get("/context/{context_id}/explain", response_model=ContextTrace)
    async def explain_context(
        context_id: str, api_key: str = Depends(get_api_key)
    ) -> ContextTrace:
        """
        Retrieve the execution trace for a specific context ID.
        """
        if not store.online_store:
            raise HTTPException(status_code=501, detail="Online store not configured")

        try:
            # Fetch trace from cache
            trace_key = f"trace:{context_id}"
            raw_trace = await store.online_store.get(trace_key)

            if not raw_trace:
                raise HTTPException(status_code=404, detail="Context trace not found")

            # Parse
            if isinstance(raw_trace, (bytes, str)):
                data = json.loads(raw_trace)
            else:
                data = raw_trace

            return ContextTrace(**data)

        except HTTPException:
            raise
        except Exception as e:
            logger.error("explain_context_failed", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @v1_router.post("/context/{context_id}/replay")
    async def replay_context(
        context_id: str,
        timestamp: Optional[str] = None,
        api_key: str = Depends(get_api_key),
    ) -> Dict[str, Any]:
        """
        Replay a historical context assembly.

        If timestamp is provided, re-executes the context function with
        feature values as they existed at that point in time.

        Args:
            context_id: The UUIDv7 identifier from a previous context assembly.
            timestamp: Optional ISO timestamp for time-travel replay.

        Returns:
            The replayed context with content, lineage, and meta.
        """
        try:
            # Parse timestamp if provided
            replay_ts = None
            if timestamp:
                replay_ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

            ctx = await store.replay_context(context_id, timestamp=replay_ts)
            if not ctx:
                raise HTTPException(status_code=404, detail="Context not found")

            # Return serialized context
            result: Dict[str, Any] = {
                "id": ctx.id,
                "content": ctx.content,
                "meta": ctx.meta,
                "version": getattr(ctx, "version", "v1"),
            }

            if ctx.lineage:
                result["lineage"] = ctx.lineage.model_dump()

            return result

        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid timestamp format: {e}"
            )
        except EvidencePersistenceError as e:
            logger.error(
                "replay_context_evidence_persist_failed",
                context_id=e.context_id,
                error=str(e),
            )
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.error("replay_context_failed", context_id=context_id, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @v1_router.get("/context/diff/{base_id}/{comparison_id}")
    async def diff_contexts(
        base_id: str,
        comparison_id: str,
        api_key: str = Depends(get_api_key),
    ) -> Dict[str, Any]:
        """
        Compare two context assemblies and return detailed diff.

        Shows what features, retrievers, and content changed between two contexts.

        Args:
            base_id: The UUIDv7 identifier of the base (older) context.
            comparison_id: The UUIDv7 identifier of the comparison (newer) context.

        Returns:
            ContextDiff with all changes between the two contexts.
        """
        from fabra.utils.compare import compare_contexts
        from fabra.models import ContextLineage

        try:
            # Fetch both contexts
            base_ctx = await store.get_context_at(base_id)
            if not base_ctx:
                raise HTTPException(
                    status_code=404, detail=f"Base context {base_id} not found"
                )

            comp_ctx = await store.get_context_at(comparison_id)
            if not comp_ctx:
                raise HTTPException(
                    status_code=404,
                    detail=f"Comparison context {comparison_id} not found",
                )

            # Build lineage objects (with fallbacks for contexts without lineage)
            base_lineage = base_ctx.lineage or ContextLineage(
                context_id=base_id,
                token_usage=base_ctx.meta.get("token_usage", 0),
                estimated_cost_usd=base_ctx.meta.get("cost_usd", 0.0),
                freshness_status=base_ctx.meta.get("freshness_status", "unknown"),
            )

            comp_lineage = comp_ctx.lineage or ContextLineage(
                context_id=comparison_id,
                token_usage=comp_ctx.meta.get("token_usage", 0),
                estimated_cost_usd=comp_ctx.meta.get("cost_usd", 0.0),
                freshness_status=comp_ctx.meta.get("freshness_status", "unknown"),
            )

            # Compute diff
            diff = compare_contexts(
                base_lineage,
                comp_lineage,
                base_content=base_ctx.content,
                comparison_content=comp_ctx.content,
            )

            return diff.model_dump()

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "diff_contexts_failed",
                base_id=base_id,
                comparison_id=comparison_id,
                error=str(e),
            )
            raise HTTPException(status_code=500, detail=str(e))

    @v1_router.delete("/cache/{entity_name}/{entity_id}")
    async def invalidate_cache(
        entity_name: str, entity_id: str, api_key: str = Depends(get_api_key)
    ) -> Dict[str, str]:
        """
        Manually invalidate cache for a specific entity.
        Warning: This might restart the cold start penalty for this entity.
        """
        if not store.online_store:
            raise HTTPException(status_code=501, detail="Online store not configured")

        try:
            # Identify keys?
            # RedisOnlineStore uses f"entity:{entity_name}:{entity_id}" usually.
            # We should probably expose a delete method on FeatureStore/OnlineStore.
            # But assuming RedisOnlineStore structure for MVP:
            # We can't easily know all keys if they are hashed or individual features.
            # Assuming RedisOnlineStore has a delete_entity method or similar
            # OR we iterate known features.

            # Best effort MVP:
            # Ideally: await store.online_store.delete_entity(entity_name, entity_id)
            # But store interface is generic.

            # If we look at RedisOnlineStore implementation (not visible here but inferred),
            # set_online_features uses hset with key f"{entity_name}:{entity_id}".
            key = f"{entity_name}:{entity_id}"

            if hasattr(store.online_store, "delete"):
                await store.online_store.delete(key)
            elif hasattr(store.online_store, "redis"):
                await store.online_store.redis.delete(key)
            elif hasattr(store.online_store, "client"):
                await store.online_store.client.delete(key)

            return {"status": "invalidated", "key": key}

        except Exception as e:
            logger.error("cache_invalidation_failed", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @v1_router.get("/context/{context_id}/visualize", response_class=HTMLResponse)
    async def visualize_context(
        context_id: str, api_key: str = Depends(get_api_key)
    ) -> HTMLResponse:
        """
        Returns a visual HTML representation of the context trace with Mermaid diagram.
        """
        # Reuse logic from explain_context to get data
        trace = await explain_context(context_id, api_key)

        # Determine status color
        fresh_color = "#1e8e3e" if trace.freshness_status == "guaranteed" else "#d93025"

        # Build Source Pills
        sources_html = ""
        for src in trace.source_ids:
            safe_src = html.escape(str(src))
            is_stale = src in (trace.stale_sources or [])
            bg = "#fce8e6" if is_stale else "#e6f4ea"
            color = "#c5221f" if is_stale else "#137333"
            icon = "⚠️" if is_stale else "✅"
            sources_html += f'<span style="background: {bg}; color: {color}; padding: 4px 8px; border-radius: 12px; font-size: 12px; margin-right: 5px; display: inline-block;">{icon} {safe_src}</span>'

        # Build Mermaid diagram for lineage visualization
        mermaid_nodes = []
        mermaid_edges = []

        # Categorize sources
        features = []
        retrievers = []
        other_sources = []

        for src in trace.source_ids:
            # HTML escape to prevent XSS, then escape quotes for Mermaid syntax
            safe_src = html.escape(str(src)).replace('"', "'")
            # Classify source types based on naming conventions
            if (
                "retriev" in safe_src.lower()
                or "search" in safe_src.lower()
                or "docs" in safe_src.lower()
            ):
                retrievers.append(safe_src)
            elif "_" in safe_src and not safe_src.startswith(("system", "user_query")):
                features.append(safe_src)
            else:
                other_sources.append(safe_src)

        # Add feature nodes
        for i, feat in enumerate(features):
            node_id = f"F{i}"
            is_stale = feat in (trace.stale_sources or [])
            style = ":::stale" if is_stale else ":::fresh"
            mermaid_nodes.append(f'    {node_id}["{feat}"]{style}')
            mermaid_edges.append(f"    {node_id} --> CTX")

        # Add retriever nodes
        for i, ret in enumerate(retrievers):
            node_id = f"R{i}"
            is_stale = ret in (trace.stale_sources or [])
            style = ":::stale" if is_stale else ":::retriever"
            mermaid_nodes.append(f'    {node_id}["{ret}"]{style}')
            mermaid_edges.append(f"    {node_id} --> CTX")

        # Add other source nodes
        for i, src in enumerate(other_sources):
            node_id = f"S{i}"
            is_stale = src in (trace.stale_sources or [])
            style = ":::stale" if is_stale else ":::source"
            mermaid_nodes.append(f'    {node_id}["{src}"]{style}')
            mermaid_edges.append(f"    {node_id} --> CTX")

        # Add context assembly node and output
        mermaid_nodes.append('    CTX[["Context Assembly"]]:::assembly')
        mermaid_nodes.append(
            f'    OUT[("Final Prompt\\n{trace.token_usage} tokens")]:::output'
        )
        mermaid_edges.append("    CTX --> OUT")

        mermaid_diagram = (
            "graph LR\\n"
            + "\\n".join(mermaid_nodes)
            + "\\n"
            + "\\n".join(mermaid_edges)
        )

        safe_context_id = html.escape(context_id)
        safe_status = html.escape(str(trace.freshness_status).upper())
        safe_stale_sources = html.escape(str(trace.stale_sources or "None"))

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Context Trace: {safe_context_id}</title>
            <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
            <style>
                body {{ font-family: -apple-system, system-ui, sans-serif; background: #f8f9fa; padding: 40px; margin: 0; }}
                .card {{ background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); padding: 24px; max-width: 900px; margin: 0 auto; }}
                .header {{ border-bottom: 1px solid #eee; padding-bottom: 20px; margin-bottom: 20px; }}
                .title {{ font-size: 20px; font-weight: 600; color: #202124; margin: 0 0 5px 0; }}
                .subtitle {{ color: #5f6368; font-family: monospace; font-size: 14px; }}
                .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; color: white; vertical-align: middle; margin-left: 10px; }}
                .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; }}
                .metric-box {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
                .metric-val {{ font-size: 24px; font-weight: bold; color: #202124; }}
                .metric-label {{ font-size: 12px; color: #5f6368; text-transform: uppercase; margin-top: 5px; }}
                .section-title {{ font-size: 14px; font-weight: 600; color: #202124; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }}
                .sources {{ margin-bottom: 20px; }}
                .diagram {{ margin: 30px 0; padding: 20px; background: #fafafa; border-radius: 8px; text-align: center; }}
                .footer {{ margin-top: 30px; text-align: center; color: #9aa0a6; font-size: 12px; }}
                .legend {{ display: flex; gap: 20px; justify-content: center; margin-top: 15px; font-size: 12px; color: #5f6368; }}
                .legend-item {{ display: flex; align-items: center; gap: 5px; }}
                .legend-color {{ width: 12px; height: 12px; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="header">
                    <div>
                        <span class="title">Context Assembly Trace</span>
                        <span class="badge" style="background-color: {fresh_color}">{safe_status}</span>
                    </div>
                    <div class="subtitle">{safe_context_id}</div>
                </div>

                <div class="metrics">
                    <div class="metric-box">
                        <div class="metric-val">{int(trace.latency_ms)}ms</div>
                        <div class="metric-label">Latency</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-val">{trace.token_usage}</div>
                        <div class="metric-label">Tokens</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-val">{len(trace.source_ids)}</div>
                        <div class="metric-label">Sources</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-val">{"Yes" if trace.cache_hit else "No"}</div>
                        <div class="metric-label">Cache Hit</div>
                    </div>
                </div>

                <div class="diagram">
                    <div class="section-title">Data Lineage Flow</div>
                    <div class="mermaid">
                    {mermaid_diagram}
                    </div>
                    <div class="legend">
                        <div class="legend-item"><div class="legend-color" style="background: #e6f4ea;"></div> Feature</div>
                        <div class="legend-item"><div class="legend-color" style="background: #e3f2fd;"></div> Retriever</div>
                        <div class="legend-item"><div class="legend-color" style="background: #fff3e0;"></div> Source</div>
                        <div class="legend-item"><div class="legend-color" style="background: #fce8e6;"></div> Stale</div>
                    </div>
                </div>

                <div class="sources">
                    <div class="section-title">Included Sources</div>
                    <div>{sources_html if sources_html else "<span style='color:#999'>No sources recorded</span>"}</div>
                </div>

                <div class="sources">
                    <div class="section-title">Details</div>
                     <div style="background: #202124; color: #e8eaed; padding: 15px; border-radius: 6px; font-family: monospace; font-size: 12px; overflow-x: auto;">
                        Created: {trace.created_at.isoformat() if trace.created_at else "N/A"}<br>
                        Stale Sources: {safe_stale_sources}<br>
                        Missing Features: {html.escape(str(trace.missing_features or "None"))}<br>
                        Cost: {trace.cost_usd if trace.cost_usd else "N/A"}
                    </div>
                </div>

                <div class="footer">
                    Generated by Fabra Feature Store
                </div>
            </div>
            <script>
                mermaid.initialize({{
                    startOnLoad: true,
                    theme: 'neutral',
                    themeVariables: {{
                        primaryColor: '#e6f4ea',
                        primaryBorderColor: '#137333',
                        lineColor: '#5f6368',
                        secondaryColor: '#e3f2fd',
                        tertiaryColor: '#fff3e0'
                    }},
                    flowchart: {{
                        useMaxWidth: true,
                        htmlLabels: true,
                        curve: 'basis'
                    }}
                }});
            </script>
            <style>
                .mermaid .fresh > rect {{ fill: #e6f4ea !important; stroke: #137333 !important; }}
                .mermaid .stale > rect {{ fill: #fce8e6 !important; stroke: #c5221f !important; }}
                .mermaid .retriever > rect {{ fill: #e3f2fd !important; stroke: #1976d2 !important; }}
                .mermaid .source > rect {{ fill: #fff3e0 !important; stroke: #f57c00 !important; }}
                .mermaid .assembly > rect {{ fill: #f3e5f5 !important; stroke: #7b1fa2 !important; }}
                .mermaid .output > rect, .mermaid .output > circle {{ fill: #e8f5e9 !important; stroke: #2e7d32 !important; }}
            </style>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

    app.include_router(v1_router)

    return app
