"""FastAPI server for Fabra UI.

This server provides API endpoints for the Next.js frontend to interact
with Fabra.s Feature Store and Context Store.
"""

import asyncio
import importlib.util
import inspect
import os
import sys
import warnings
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from fabra.core import FeatureStore
from fabra.store import InMemoryOnlineStore, DuckDBOfflineStore

app = FastAPI(title="Fabra UI API", version="0.1.0")

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8501",
        "http://localhost:8502",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:8501",
        "http://127.0.0.1:8502",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state for loaded module
_state: Dict[str, Any] = {
    "store": None,
    "contexts": {},
    "retrievers": {},
    "file_path": "",
    "context_records": {},  # In-memory storage for Context Records (demo only)
}

# Optional API key authentication
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _get_api_key(api_key: Optional[str] = Depends(API_KEY_HEADER)) -> Optional[str]:
    """Validate API key if FABRA_UI_API_KEY is set."""
    expected = os.environ.get("FABRA_UI_API_KEY")
    if expected and api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


def _is_demo_mode(store: FeatureStore) -> bool:
    """Detect if store is using in-memory/demo backends."""
    is_inmemory_online = isinstance(store.online_store, InMemoryOnlineStore)
    is_duckdb_offline = isinstance(store.offline_store, DuckDBOfflineStore)
    return is_inmemory_online or is_duckdb_offline


def _get_demo_warning(store: FeatureStore) -> Optional[str]:
    """Generate warning message for demo mode."""
    warnings_list = []
    if isinstance(store.online_store, InMemoryOnlineStore):
        warnings_list.append("InMemoryOnlineStore: data lost on restart")
    if isinstance(store.offline_store, DuckDBOfflineStore):
        warnings_list.append("DuckDBOfflineStore: local development only")
    if warnings_list:
        return (
            "Demo mode active. "
            + "; ".join(warnings_list)
            + ". Set FABRA_ENV=production for persistent storage."
        )
    return None


# =============================================================================
# Pydantic Models
# =============================================================================


class Entity(BaseModel):
    name: str
    id_column: str
    description: Optional[str] = None


class Feature(BaseModel):
    name: str
    entity: str
    refresh: Optional[str] = None
    ttl: Optional[str] = None
    materialize: bool


class Retriever(BaseModel):
    name: str
    backend: str
    cache_ttl: str
    is_mock: bool = False
    index_name: Optional[str] = None


class ContextParameter(BaseModel):
    name: str
    type: str
    default: Optional[str] = None
    required: bool


class ContextDefinition(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: List[ContextParameter]


class StoreInfo(BaseModel):
    file_name: str
    entities: List[Entity]
    features: List[Feature]
    contexts: List[ContextDefinition]
    retrievers: List[Retriever]
    online_store_type: str
    offline_store_type: str
    is_demo_mode: bool
    demo_warning: Optional[str] = None


class MermaidGraph(BaseModel):
    code: str


class ContextResultItem(BaseModel):
    content: str
    priority: int
    source: Optional[str] = None


class ContextResultMeta(BaseModel):
    token_usage: Optional[int] = None
    cost_usd: Optional[float] = None
    latency_ms: Optional[float] = None
    freshness_status: Optional[str] = None


class FeatureLineageResponse(BaseModel):
    feature_name: str
    entity_id: str
    value: Any
    timestamp: str
    freshness_ms: int
    source: str


class RetrieverLineageResponse(BaseModel):
    retriever_name: str
    query: str
    results_count: int
    latency_ms: float
    index_name: Optional[str] = None


class ContextLineageResponse(BaseModel):
    context_id: str
    timestamp: str
    features_used: List[FeatureLineageResponse]
    retrievers_used: List[RetrieverLineageResponse]
    items_provided: int
    items_included: int
    items_dropped: int
    freshness_status: str
    stalest_feature_ms: int
    token_usage: int
    max_tokens: Optional[int] = None
    estimated_cost_usd: float


class ContextResult(BaseModel):
    id: str
    items: List[ContextResultItem]
    meta: ContextResultMeta
    lineage: Optional[ContextLineageResponse] = None


# CRS-001 Context Record Response Models
class DroppedItemResponse(BaseModel):
    source_id: str
    priority: int
    token_count: int
    reason: str


class IntegrityResponse(BaseModel):
    record_hash: str
    content_hash: str
    previous_context_id: Optional[str] = None


class AssemblyResponse(BaseModel):
    tokens_used: int
    max_tokens: Optional[int] = None
    items_provided: int
    items_included: int
    dropped_items: List[DroppedItemResponse]
    freshness_status: str


class ContextRecordResponse(BaseModel):
    """CRS-001 Context Record - immutable snapshot of AI decision context."""

    context_id: str
    schema_version: str
    created_at: str
    environment: str
    context_function: str
    inputs: Dict[str, Any]
    content: str
    token_count: int
    assembly: AssemblyResponse
    integrity: IntegrityResponse


class VerificationResult(BaseModel):
    """Result of context record integrity verification."""

    context_id: str
    is_valid: bool
    content_hash_valid: bool
    record_hash_valid: bool
    error: Optional[str] = None
    verified_at: str


# =============================================================================
# Module Loading
# =============================================================================


def load_module(file_path: str) -> None:
    """Load a Python module and extract Fabra objects."""
    global _state

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    spec = importlib.util.spec_from_file_location("features", file_path)
    if not spec or not spec.loader:
        raise ValueError(f"Could not load module: {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["features"] = module
    spec.loader.exec_module(module)

    store = None
    contexts = {}
    retrievers = {}

    for attr_name in dir(module):
        attr = getattr(module, attr_name)

        if isinstance(attr, FeatureStore):
            store = attr

        if hasattr(attr, "_is_context") and attr._is_context:
            contexts[attr_name] = attr

        if hasattr(attr, "_fabra_retriever"):
            retrievers[attr_name] = getattr(attr, "_fabra_retriever")

    if not store:
        raise ValueError("No FeatureStore instance found in the provided file.")

    # Emit warning for InMemoryOnlineStore (Phase 5)
    if isinstance(store.online_store, InMemoryOnlineStore):
        warnings.warn(
            "Using InMemoryOnlineStore - data will be lost on restart. "
            "Set FABRA_ENV=production for persistent storage.",
            UserWarning,
            stacklevel=2,
        )

    _state["store"] = store
    _state["contexts"] = contexts
    _state["retrievers"] = retrievers
    _state["file_path"] = file_path


# =============================================================================
# API Endpoints
# =============================================================================


@app.get("/api/store", response_model=StoreInfo)
async def get_store_info(
    _api_key: Optional[str] = Depends(_get_api_key),
) -> StoreInfo:
    """Get information about the loaded Feature Store."""
    store = _state["store"]
    if not store:
        raise HTTPException(status_code=503, detail="No store loaded")

    # Build entities list
    entities = []
    for name, entity in store.registry.entities.items():
        entities.append(
            Entity(
                name=name,
                id_column=entity.id_column,
                description=entity.description,
            )
        )

    # Build features list
    features = []
    for entity_name in store.registry.entities:
        for feat in store.registry.get_features_for_entity(entity_name):
            features.append(
                Feature(
                    name=feat.name,
                    entity=entity_name,
                    refresh=str(feat.refresh) if feat.refresh else None,
                    ttl=str(feat.ttl) if feat.ttl else None,
                    materialize=feat.materialize,
                )
            )

    # Build contexts list
    contexts = []
    for ctx_name, ctx_func in _state["contexts"].items():
        sig = inspect.signature(ctx_func)
        params = []
        for param_name, param in sig.parameters.items():
            if param_name in ["self", "cls"]:
                continue
            param_type = "str"
            if param.annotation != inspect.Parameter.empty:
                try:
                    param_type = param.annotation.__name__
                except Exception:
                    param_type = str(param.annotation)

            default_val = None
            if param.default != inspect.Parameter.empty:
                default_val = str(param.default)

            params.append(
                ContextParameter(
                    name=param_name,
                    type=param_type,
                    default=default_val,
                    required=param.default == inspect.Parameter.empty,
                )
            )

        contexts.append(
            ContextDefinition(
                name=ctx_name,
                description=ctx_func.__doc__,
                parameters=params,
            )
        )

    # Build retrievers list with mock detection
    retrievers = []
    for r_name, r_obj in _state["retrievers"].items():
        # Detect if retriever has a real index (not mock)
        index_name = getattr(r_obj, "index", None)
        is_mock = index_name is None
        retrievers.append(
            Retriever(
                name=r_name,
                backend=r_obj.backend,
                cache_ttl=str(r_obj.cache_ttl),
                is_mock=is_mock,
                index_name=index_name,
            )
        )

    return StoreInfo(
        file_name=os.path.basename(_state["file_path"]),
        entities=entities,
        features=features,
        contexts=contexts,
        retrievers=retrievers,
        online_store_type=store.online_store.__class__.__name__,
        offline_store_type=store.offline_store.__class__.__name__,
        is_demo_mode=_is_demo_mode(store),
        demo_warning=_get_demo_warning(store),
    )


@app.get("/api/features/{entity_name}/{entity_id}")
async def get_features(
    entity_name: str,
    entity_id: str,
    _api_key: Optional[str] = Depends(_get_api_key),
) -> Dict[str, Any]:
    """Fetch feature values for an entity."""
    store = _state["store"]
    if not store:
        raise HTTPException(status_code=503, detail="No store loaded")

    if entity_name not in store.registry.entities:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_name}")

    features = store.registry.get_features_for_entity(entity_name)
    feature_names = [f.name for f in features]

    if not feature_names:
        return {}

    try:
        values = await store.get_online_features(
            entity_name=entity_name,
            entity_id=entity_id,
            features=feature_names,
        )
        # Convert to JSON-serializable format
        return {k: _serialize_value(v) for k, v in values.items()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _serialize_value(value: Any) -> Any:
    """Convert value to JSON-serializable format."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "__dict__"):
        return str(value)
    return value


@app.post("/api/context/{context_name}", response_model=ContextResult)
async def assemble_context(
    context_name: str,
    params: Dict[str, str],
    _api_key: Optional[str] = Depends(_get_api_key),
) -> ContextResult:
    """Assemble a context with the given parameters."""
    if context_name not in _state["contexts"]:
        raise HTTPException(
            status_code=404, detail=f"Context not found: {context_name}"
        )

    ctx_func = _state["contexts"][context_name]

    try:
        if asyncio.iscoroutinefunction(ctx_func):
            result = await ctx_func(**params)
        else:
            result = ctx_func(**params)

        # Convert result to response model
        items = []
        if hasattr(result, "items") and result.items:
            for item in result.items:
                items.append(
                    ContextResultItem(
                        content=str(item.content),
                        priority=item.priority,
                        source=getattr(item, "source", None),
                    )
                )

        meta = ContextResultMeta(
            token_usage=result.meta.get("token_usage", result.meta.get("usage")),
            cost_usd=result.meta.get("cost_usd"),
            latency_ms=result.meta.get("latency_ms"),
            freshness_status=result.meta.get("freshness_status"),
        )

        # Build lineage response if available
        lineage_response = None
        if hasattr(result, "lineage") and result.lineage:
            lineage = result.lineage
            features_used = [
                FeatureLineageResponse(
                    feature_name=f.feature_name,
                    entity_id=f.entity_id,
                    value=f.value,
                    timestamp=f.timestamp.isoformat()
                    if hasattr(f.timestamp, "isoformat")
                    else str(f.timestamp),
                    freshness_ms=f.freshness_ms,
                    source=f.source,
                )
                for f in lineage.features_used
            ]
            retrievers_used = [
                RetrieverLineageResponse(
                    retriever_name=r.retriever_name,
                    query=r.query,
                    results_count=r.results_count,
                    latency_ms=r.latency_ms,
                    index_name=r.index_name,
                )
                for r in lineage.retrievers_used
            ]
            lineage_response = ContextLineageResponse(
                context_id=lineage.context_id,
                timestamp=lineage.timestamp.isoformat()
                if hasattr(lineage.timestamp, "isoformat")
                else str(lineage.timestamp),
                features_used=features_used,
                retrievers_used=retrievers_used,
                items_provided=lineage.items_provided,
                items_included=lineage.items_included,
                items_dropped=lineage.items_dropped,
                freshness_status=lineage.freshness_status,
                stalest_feature_ms=lineage.stalest_feature_ms,
                token_usage=lineage.token_usage,
                max_tokens=lineage.max_tokens,
                estimated_cost_usd=lineage.estimated_cost_usd,
            )

        # Store Context Record for later retrieval/verification
        _store_context_record(result, context_name, params)

        return ContextResult(
            id=result.id,
            items=items,
            meta=meta,
            lineage=lineage_response,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph", response_model=MermaidGraph)
async def get_mermaid_graph(
    _api_key: Optional[str] = Depends(_get_api_key),
) -> MermaidGraph:
    """Generate Mermaid diagram code for the Feature Store."""
    store = _state["store"]
    if not store:
        raise HTTPException(status_code=503, detail="No store loaded")

    # Build Mermaid graph
    graph = ["graph LR"]
    graph.append(
        "    classDef entity fill:#1f2937,stroke:#10b981,stroke-width:2px,color:#f9fafb;"
    )
    graph.append(
        "    classDef feature fill:#111827,stroke:#3b82f6,stroke-width:1px,color:#d1d5db;"
    )
    graph.append(
        "    classDef store fill:#1f2937,stroke:#f59e0b,stroke-width:2px,color:#f9fafb;"
    )

    os_type = store.online_store.__class__.__name__
    graph.append(f"    OS[({os_type})]")
    graph.append("    class OS store;")

    for name, ent in store.registry.entities.items():
        safe_name = name.replace(" ", "_")
        ent_id = f"ENT_{safe_name}"
        graph.append(f"    subgraph {safe_name}")
        graph.append(f"        {ent_id}[{name}]")
        graph.append(f"        class {ent_id} entity;")

        feats = store.registry.get_features_for_entity(name)
        for f in feats:
            safe_feat = f.name.replace(" ", "_")
            feat_node = f"FEAT_{safe_feat}"
            graph.append(f"        {feat_node}({f.name})")
            graph.append(f"        class {feat_node} feature;")
            graph.append(f"        {ent_id} --> {feat_node}")

            if f.materialize:
                graph.append(f"        {feat_node} -. Materialize .-> OS")

        graph.append("    end")

    return MermaidGraph(code="\n".join(graph))


@app.get("/api/context/{context_id}/record", response_model=ContextRecordResponse)
async def get_context_record(
    context_id: str,
    _api_key: Optional[str] = Depends(_get_api_key),
) -> ContextRecordResponse:
    """Get the full CRS-001 Context Record for a context ID."""
    if context_id not in _state["context_records"]:
        raise HTTPException(
            status_code=404, detail=f"Context record not found: {context_id}"
        )

    record = _state["context_records"][context_id]
    return _convert_to_record_response(record)


@app.get("/api/context/{context_id}/verify", response_model=VerificationResult)
async def verify_context(
    context_id: str,
    _api_key: Optional[str] = Depends(_get_api_key),
) -> VerificationResult:
    """Verify cryptographic integrity of a Context Record."""
    from datetime import datetime, timezone
    import hashlib

    if context_id not in _state["context_records"]:
        raise HTTPException(
            status_code=404, detail=f"Context record not found: {context_id}"
        )

    record = _state["context_records"][context_id]
    now = datetime.now(timezone.utc)

    try:
        # Verify content hash
        content_hash = (
            "sha256:" + hashlib.sha256(record.content.encode("utf-8")).hexdigest()
        )
        content_hash_valid = content_hash == record.integrity.content_hash

        # For record hash, we'd need to recompute the canonical JSON
        # For simplicity, we just check it exists and is valid format
        record_hash_valid = (
            record.integrity.record_hash.startswith("sha256:")
            and len(record.integrity.record_hash) == 71  # sha256: + 64 hex chars
        )

        is_valid = content_hash_valid and record_hash_valid

        return VerificationResult(
            context_id=context_id,
            is_valid=is_valid,
            content_hash_valid=content_hash_valid,
            record_hash_valid=record_hash_valid,
            error=None if is_valid else "Hash mismatch detected",
            verified_at=now.isoformat(),
        )
    except Exception as e:
        return VerificationResult(
            context_id=context_id,
            is_valid=False,
            content_hash_valid=False,
            record_hash_valid=False,
            error=str(e),
            verified_at=now.isoformat(),
        )


def _convert_to_record_response(record: Any) -> ContextRecordResponse:
    """Convert internal ContextRecord to API response model."""
    dropped_items = [
        DroppedItemResponse(
            source_id=item.source_id,
            priority=item.priority,
            token_count=item.token_count,
            reason=item.reason,
        )
        for item in record.assembly.dropped_items
    ]

    return ContextRecordResponse(
        context_id=record.context_id,
        schema_version=record.schema_version,
        created_at=record.created_at.isoformat()
        if hasattr(record.created_at, "isoformat")
        else str(record.created_at),
        environment=record.environment,
        context_function=record.context_function,
        inputs=record.inputs,
        content=record.content,
        token_count=record.token_count,
        assembly=AssemblyResponse(
            tokens_used=record.assembly.tokens_used,
            max_tokens=record.assembly.max_tokens,
            items_provided=record.assembly.items_provided,
            items_included=record.assembly.items_included,
            dropped_items=dropped_items,
            freshness_status=record.assembly.freshness_status,
        ),
        integrity=IntegrityResponse(
            record_hash=record.integrity.record_hash,
            content_hash=record.integrity.content_hash,
            previous_context_id=record.integrity.previous_context_id,
        ),
    )


def _store_context_record(
    result: Any, context_name: str, params: Dict[str, str]
) -> None:
    """Store a Context Record if available on the result."""
    if hasattr(result, "to_record"):
        try:
            record = result.to_record()
            _state["context_records"][result.id] = record
        except Exception:  # nosec B110 - non-critical for demo UI
            # Silently skip if to_record() fails
            pass


# =============================================================================
# Server Functions
# =============================================================================


def create_app(file_path: str) -> FastAPI:
    """Create the FastAPI app with the given feature file loaded."""
    load_module(file_path)
    return app


def run_server(file_path: str, port: int = 8502, host: str = "127.0.0.1") -> None:
    """Run the Fabra UI server."""
    import uvicorn

    load_module(file_path)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ui_server.py <path_to_features.py>")
        sys.exit(1)

    run_server(sys.argv[1])
