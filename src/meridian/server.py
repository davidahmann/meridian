from fastapi import FastAPI, HTTPException, Request, Response, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from typing import List, Dict, Any, cast
import time
import os
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from .core import FeatureStore
import structlog

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

    if api_key_header == expected_key:
        return api_key_header

    raise HTTPException(status_code=403, detail="Could not validate credentials")


def create_app(store: FeatureStore) -> FastAPI:
    app = FastAPI(title="Meridian Feature Store API")

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

    @app.get("/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

    return app
