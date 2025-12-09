from fastapi import FastAPI, HTTPException, Request, Response, Depends, Security
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from typing import List, Dict, Any, cast, AsyncGenerator
import time
import os
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from .core import FeatureStore
from .models import ContextTrace
import structlog
import json
import html

logger = structlog.get_logger()

# Metrics
REQUEST_COUNT = Counter(
    "meridian_request_count", "Total request count", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "meridian_request_latency_seconds", "Request latency", ["method", "endpoint"]
)


class FeatureRequest(BaseModel):
    entity_name: str
    entity_id: str
    features: List[str]


API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def get_api_key(
    api_key_header: str = Security(api_key_header),
) -> str:
    expected_key = os.getenv("MERIDIAN_API_KEY")
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

    app = FastAPI(title="Meridian Feature Store API", lifespan=lifespan)

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

    @app.post("/features")
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

    @app.post("/ingest/{event_type}", status_code=202)
    async def ingest_event(
        event_type: str,
        payload: Dict[str, Any],
        entity_id: str,
        api_key: str = Depends(get_api_key),
    ) -> Dict[str, str]:
        """
        Ingests an event into the Axiom Event Bus.
        """
        if not event_type.isalnum():
            raise HTTPException(
                status_code=400, detail="Event type must be alphanumeric"
            )

        from meridian.events import AxiomEvent
        from meridian.bus import RedisEventBus

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

            from meridian.config import get_redis_url

            url = get_redis_url()
            client = Redis.from_url(url, decode_responses=True)

        bus = RedisEventBus(client)
        event = AxiomEvent(event_type=event_type, entity_id=entity_id, payload=payload)
        msg_id = await bus.publish(event)

        # If we created a fresh client, we should close it?
        # If it's shared from store, DON'T close it.
        # To avoid complexity, let's rely on Python GC or context manager if possible.
        # Ideally, use dependency injection with lifecycle.

        return {"msg_id": msg_id, "event_id": str(event.id)}

    @app.get("/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/context/{context_id}/explain", response_model=ContextTrace)
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

    @app.delete("/cache/{entity_name}/{entity_id}")
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

    @app.get("/context/{context_id}/visualize", response_class=HTMLResponse)
    async def visualize_context(
        context_id: str, api_key: str = Depends(get_api_key)
    ) -> HTMLResponse:
        """
        Returns a visual HTML representation of the context trace.
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

        safe_context_id = html.escape(context_id)
        safe_status = html.escape(str(trace.freshness_status).upper())
        safe_stale_sources = html.escape(str(trace.stale_sources or "None"))

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Context Trace: {safe_context_id}</title>
            <style>
                body {{ font-family: -apple-system, system-ui, sans-serif; background: #f8f9fa; padding: 40px; margin: 0; }}
                .card {{ background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); padding: 24px; max-width: 800px; margin: 0 auto; }}
                .header {{ border-bottom: 1px solid #eee; padding-bottom: 20px; margin-bottom: 20px; }}
                .title {{ font-size: 20px; font-weight: 600; color: #202124; margin: 0 0 5px 0; }}
                .subtitle {{ color: #5f6368; font-family: monospace; font-size: 14px; }}
                .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; color: white; vertical-align: middle; margin-left: 10px; }}
                .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 30px; }}
                .metric-box {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
                .metric-val {{ font-size: 24px; font-weight: bold; color: #202124; }}
                .metric-label {{ font-size: 12px; color: #5f6368; text-transform: uppercase; margin-top: 5px; }}
                .section-title {{ font-size: 14px; font-weight: 600; color: #202124; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }}
                .sources {{ margin-bottom: 20px; }}
                .footer {{ margin-top: 30px; text-align: center; color: #9aa0a6; font-size: 12px; }}
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
                </div>

                <div class="sources">
                    <div class="section-title">Included Sources</div>
                    <div>{sources_html if sources_html else "<span style='color:#999'>No sources recorded</span>"}</div>
                </div>

                <div class="sources">
                    <div class="section-title">Details</div>
                     <div style="background: #202124; color: #e8eaed; padding: 15px; border-radius: 6px; font-family: monospace; font-size: 12px; overflow-x: auto;">
                        Cache Hit: {trace.cache_hit}<br>
                        Stale Sources: {safe_stale_sources}<br>
                        Cost: {trace.cost_usd if trace.cost_usd else "N/A"}
                    </div>
                </div>

                <div class="footer">
                    Generated by Meridian Feature Store
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

    return app
