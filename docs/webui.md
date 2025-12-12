---
title: "WebUI - Visual Feature Store & Context Explorer | Fabra"
description: "Interactive web interface for exploring Fabra features, contexts, and dependencies. Debug context assembly, inspect lineage, and test retrievers."
keywords: fabra ui, feature store ui, context explorer, rag debugger, feature visualization, context lineage viewer
---

# Fabra WebUI

> **TL;DR:** A visual interface for exploring your Feature Store and Context Store. Launch with `fabra ui your_features.py`.

## Quick Start

```bash
# Install with UI dependencies
pip install "fabra-ai[ui]"

# Launch the UI
fabra ui examples/demo_context.py
```

The UI opens at `http://localhost:3001` with the API server at `http://localhost:8502`.

---

## Demo Mode vs Production Mode

Fabra automatically detects when you're running in **demo mode** (local development) vs **production mode**.

### Demo Mode Indicators

When the API returns `is_demo_mode: true`, it means:

| Indicator | Meaning |
|:----------|:--------|
| `InMemoryOnlineStore` | Feature data is stored in memory — **lost on restart** |
| `DuckDBOfflineStore` | Using embedded DuckDB — local development only |
| Mock retrievers | Retrievers without `index=` parameter use keyword matching, not vector search |

**Example API Response (Demo Mode):**

```json
{
  "file_name": "demo_context.py",
  "online_store_type": "InMemoryOnlineStore",
  "offline_store_type": "DuckDBOfflineStore",
  "is_demo_mode": true,
  "demo_warning": "Demo mode active. InMemoryOnlineStore: data lost on restart; DuckDBOfflineStore: local development only. Set FABRA_ENV=production for persistent storage.",
  "retrievers": [
    {
      "name": "search_docs",
      "backend": "mock",
      "is_mock": true,
      "index_name": null
    }
  ]
}
```

### Production Mode

Switch to production mode by setting:

```bash
export FABRA_ENV=production
```

This uses:
- `PostgresOfflineStore` — persistent storage with pgvector
- `RedisOnlineStore` — fast, persistent feature cache
- Real vector search retrievers with `index=` parameter

**Example API Response (Production Mode):**

```json
{
  "online_store_type": "RedisOnlineStore",
  "offline_store_type": "PostgresOfflineStore",
  "is_demo_mode": false,
  "demo_warning": null,
  "retrievers": [
    {
      "name": "search_docs",
      "backend": "pgvector",
      "is_mock": false,
      "index_name": "knowledge_base"
    }
  ]
}
```

---

## API Authentication

The WebUI API supports optional API key authentication.

### Enabling Authentication

Set the `FABRA_UI_API_KEY` environment variable:

```bash
export FABRA_UI_API_KEY=your-secret-key
fabra ui examples/demo_context.py
```

### Using the API with Authentication

Include the `X-API-Key` header in requests:

```bash
curl -H "X-API-Key: your-secret-key" http://localhost:8502/api/store
```

**Without the key (when enabled):**

```json
{
  "detail": "Invalid or missing API key"
}
```

### When to Enable Authentication

- **Development:** Leave unset for easy testing
- **Shared environments:** Set a key to prevent unauthorized access
- **Production:** Always set when exposing the UI publicly

---

## API Endpoints

### `GET /api/store`

Returns information about the loaded Feature Store.

**Response:**

```json
{
  "file_name": "features.py",
  "entities": [...],
  "features": [...],
  "contexts": [...],
  "retrievers": [...],
  "online_store_type": "InMemoryOnlineStore",
  "offline_store_type": "DuckDBOfflineStore",
  "is_demo_mode": true,
  "demo_warning": "..."
}
```

### `GET /api/features/{entity_name}/{entity_id}`

Fetch feature values for a specific entity.

```bash
curl http://localhost:8502/api/features/User/user_123
```

**Response:**

```json
{
  "user_tier": "premium",
  "user_engagement_score": 72.5,
  "support_priority": "high"
}
```

### `POST /api/context/{context_name}`

Assemble a context with the given parameters.

```bash
curl -X POST http://localhost:8502/api/context/chat_context \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_123", "query": "how do features work?"}'
```

**Response:**

```json
{
  "id": "ctx_018f3a2b-...",
  "items": [...],
  "meta": {
    "token_usage": 150,
    "freshness_status": "guaranteed"
  },
  "lineage": {
    "context_id": "ctx_018f3a2b-...",
    "features_used": [...],
    "retrievers_used": [...]
  }
}
```

### `GET /api/graph`

Generate a Mermaid diagram of the Feature Store.

**Response:**

```json
{
  "code": "graph LR\n    ..."
}
```

---

## Understanding Mock Data

The `examples/demo_context.py` file uses **mock data** for demonstration:

### Mock Features

Features use deterministic hash-based values:

```python
@feature(entity=User)
def user_tier(user_id: str) -> str:
    return "premium" if hash(user_id) % 2 == 0 else "free"
```

This ensures consistent values across restarts without a database.

### Mock Retrievers

The demo retriever uses keyword matching instead of vector search:

```python
MOCK_DOCS = {
    "features": ["Features in Fabra are defined using..."],
    "context": ["Context assembly in Fabra uses..."],
}

@retriever(name="demo_docs", cache_ttl=timedelta(seconds=300))
async def search_docs(query: str, top_k: int = 3) -> List[dict]:
    # Simple keyword matching - not real vector search
    if "feature" in query.lower():
        docs = MOCK_DOCS["features"]
    # ...
```

### Real Vector Search

For production, use the `index=` parameter:

```python
@retriever(index="knowledge_base", top_k=5)
async def search_docs(query: str):
    pass  # Auto-wired to pgvector
```

---

## Startup Warnings

When loading a module with `InMemoryOnlineStore`, you'll see:

```
UserWarning: Using InMemoryOnlineStore - data will be lost on restart.
Set FABRA_ENV=production for persistent storage.
```

This is expected in development. To suppress:

```python
import warnings
warnings.filterwarnings("ignore", message="Using InMemoryOnlineStore")
```

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Next.js UI     │────▶│  FastAPI Server  │────▶│  Your Module    │
│  (port 3001)    │     │  (port 8502)     │     │  (features.py)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │
                                ▼
                        ┌───────────────────────────────────┐
                        │         FeatureStore              │
                        ├───────────────┬───────────────────┤
                        │ Online Store  │  Offline Store    │
                        │ (InMemory/    │  (DuckDB/         │
                        │  Redis)       │   Postgres)       │
                        └───────────────┴───────────────────┘
```

---

## Troubleshooting

### "No store loaded" Error

The module must contain a `FeatureStore` instance:

```python
from fabra.core import FeatureStore
store = FeatureStore()  # Required!
```

### Data Disappears on Restart

You're using `InMemoryOnlineStore`. Either:
1. Accept this for development (it's fine!)
2. Switch to production mode: `FABRA_ENV=production`

### Authentication Failures

Check that `X-API-Key` header matches `FABRA_UI_API_KEY`:

```bash
# Set the key
export FABRA_UI_API_KEY=secret123

# Use the same key in requests
curl -H "X-API-Key: secret123" http://localhost:8502/api/store
```

---

## Next Steps

- [Context Store](context-store.md) — Deep dive into context assembly
- [Quickstart](quickstart.md) — Get started with Fabra
- [Context Accountability](context-accountability.md) — Full lineage tracking
