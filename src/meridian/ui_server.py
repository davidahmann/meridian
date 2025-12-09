"""FastAPI server for Meridian UI.

This server provides API endpoints for the Next.js frontend to interact
with Meridian's Feature Store and Context Store.
"""

import asyncio
import importlib.util
import inspect
import os
import sys
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from meridian.core import FeatureStore

app = FastAPI(title="Meridian UI API", version="0.1.0")

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8501",
        "http://localhost:8502",
        "http://127.0.0.1:3000",
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
}


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


class ContextResult(BaseModel):
    id: str
    items: List[ContextResultItem]
    meta: ContextResultMeta


# =============================================================================
# Module Loading
# =============================================================================


def load_module(file_path: str) -> None:
    """Load a Python module and extract Meridian objects."""
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

        if hasattr(attr, "_meridian_retriever"):
            retrievers[attr_name] = getattr(attr, "_meridian_retriever")

    if not store:
        raise ValueError("No FeatureStore instance found in the provided file.")

    _state["store"] = store
    _state["contexts"] = contexts
    _state["retrievers"] = retrievers
    _state["file_path"] = file_path


# =============================================================================
# API Endpoints
# =============================================================================


@app.get("/api/store", response_model=StoreInfo)
async def get_store_info() -> StoreInfo:
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

    # Build retrievers list
    retrievers = []
    for r_name, r_obj in _state["retrievers"].items():
        retrievers.append(
            Retriever(
                name=r_name,
                backend=r_obj.backend,
                cache_ttl=str(r_obj.cache_ttl),
            )
        )

    return StoreInfo(
        file_name=os.path.basename(_state["file_path"]),
        entities=entities,
        features=features,
        contexts=contexts,
        retrievers=retrievers,
        online_store_type=store.online_store.__class__.__name__,
    )


@app.get("/api/features/{entity_name}/{entity_id}")
async def get_features(entity_name: str, entity_id: str) -> Dict[str, Any]:
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
async def assemble_context(context_name: str, params: Dict[str, str]) -> ContextResult:
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

        return ContextResult(
            id=result.id,
            items=items,
            meta=meta,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph", response_model=MermaidGraph)
async def get_mermaid_graph() -> MermaidGraph:
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


# =============================================================================
# Server Functions
# =============================================================================


def create_app(file_path: str) -> FastAPI:
    """Create the FastAPI app with the given feature file loaded."""
    load_module(file_path)
    return app


def run_server(file_path: str, port: int = 8502, host: str = "127.0.0.1") -> None:
    """Run the Meridian UI server."""
    import uvicorn

    load_module(file_path)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ui_server.py <path_to_features.py>")
        sys.exit(1)

    run_server(sys.argv[1])
