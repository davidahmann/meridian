<div align="center">
  <h1>Meridian</h1>
  <h3>The Context Store for LLMs & ML Features</h3>

  <p>
    <!-- PyPI Version -->
    <a href="https://pypi.org/project/meridian-oss/"><img src="https://img.shields.io/pypi/v/meridian-oss?color=blue&label=pypi" alt="PyPI version" /></a>
    <!-- Build Status -->
    <a href="https://github.com/davidahmann/meridian/actions/workflows/ci.yml"><img src="https://github.com/davidahmann/meridian/actions/workflows/ci.yml/badge.svg" alt="CI Status" /></a>
    <!-- Release Status -->
    <a href="https://github.com/davidahmann/meridian/actions/workflows/release.yml"><img src="https://github.com/davidahmann/meridian/actions/workflows/release.yml/badge.svg" alt="Release Status" /></a>
    <!-- License -->
    <a href="https://github.com/davidahmann/meridian/blob/main/LICENSE"><img src="https://img.shields.io/github/license/davidahmann/meridian?color=green" alt="License" /></a>
    <!-- Python Version -->
    <a href="#"><img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python Version" /></a>
  </p>

  <br />

  <p><b>Define RAG pipelines and ML features in Python. Get production retrieval, vector search, and training data for free.</b></p>
  <p><i>Stop fighting the infrastructure tax. Meridian takes you from "Notebook Prototype" to "Production RAG" in 30 seconds.</i></p>

  <br />

  <p>
    <b>📚 <a href="https://davidahmann.github.io/meridian/">Documentation</a></b> |
    <b>🤖 <a href="https://davidahmann.github.io/meridian/context-store">Context Store</a></b> |
    <b>🛠️ <a href="docs/unit_testing.md">Testing Guide</a></b> |
    <b>🎮 <a href="https://meridianoss.vercel.app">Try in Browser</a></b>
  </p>
</div>

---

### 🚀 Why Meridian?

Most feature stores are built for the 1% of companies (Uber, DoorDash) with platform teams. They require Kubernetes, Spark, and complex microservices.

**Meridian is built for the rest of us.**

| Feature | The "Old Way" | The Meridian Way |
| :--- | :--- | :--- |
| **Config** | 500 lines of YAML | Python Decorators (`@feature`) |
| **Infra** | Kubernetes + Spark | Runs on your Laptop (DuckDB) |
| **Serving** | Complex API Gateway | `meridian serve file.py` (Realtime & Batch) |
| **RAG Context** | LangChain Spaghetti | Declarative `@context` |
| **Philosophy** | "Google Scale" | "Get it Shipped" |

---

### ⚡ The 30-Second Quickstart

**1. Install**
```bash
pip install "meridian-oss[ui]"
```

**2. Define Features & Context (`features.py`)**
```python
from meridian.core import FeatureStore, entity, feature
from meridian.context import context, ContextItem
from meridian.retrieval import retriever
import random

store = FeatureStore()

@entity(store)
class User:
    user_id: str

# 1. THE FEATURE STORE (Structured Data)
@feature(entity=User, refresh="daily", materialize=True)
def user_tier(user_id: str) -> str:
    # Imagine a DB lookup here; we'll simulate it for speed.
    return "premium" if hash(user_id) % 2 == 0 else "free"

# 2. THE CONTEXT STORE (Unstructured Data)
@retriever(index="docs", top_k=3)
async def find_docs(query: str):
    # Magic Wiring: This automatically runs vector search against 'docs' index
    # No manual implementation required!
    pass

# 3. THE UNIFICATION (Context Assembly)
@context(store, max_tokens=4000)
async def build_prompt(user_id: str, query: str):
    # Fetch feature and docs in parallel
    tier = await store.get_feature("user_tier", user_id)
    docs = await find_docs(query)

    return [
        ContextItem(content=f"User is {tier}. Adjust tone accordingly.", priority=0),
        ContextItem(content=str(docs), priority=1)
    ]
```

**3. Use in Your App**
```python
import asyncio
from features import build_prompt

async def main():
    ctx = await build_prompt(user_id="u1", query="How does Meridian help?")
    print(ctx.content)
    # Output: "User is free... \n [{'content':...}]"

    print(ctx.meta)
    # Output: {'timestamp': '...', 'dropped_items': 0, ...}

if __name__ == "__main__":
    asyncio.run(main())
```

**4. Serve (Optional)**
Expose features via HTTP for non-Python apps:
```bash
meridian serve features.py
# 🚀 Server running on http://localhost:8000
```

**5. Visualize (Optional)**
Launch the UI to explore features and debug context assembly:
```bash
meridian ui features.py
# 🧭 UI running on http://localhost:8501
```

---

### 🛠️ Key Capabilities

Meridian bridges the gap between **AI Engineers** building RAG agents and **ML Engineers** training models.

#### 🤖 For AI Engineers (The Context Store)
*   **Vector Search & RAG:** Built-in `pgvector` support. Index documents and retrieve them semantically with `@retriever`.
*   **Token Budgets:** Automatically assemble prompt contexts (`@context`) that fit within your LLM's context window, prioritizing high-value information.
*   **Semantic Cache:** Cache expensive LLM computations or retrieval results.
*   **[📖 Read the Context Store Guide](https://davidahmann.github.io/meridian/context-store)**

#### 📊 For ML Engineers (The Feature Store)
*   **Point-in-Time Correctness:** Zero data leakage. Uses `ASOF JOIN` (DuckDB) and `LATERAL JOIN` (Postgres) to fetch feature values exactly as they existed at inference time.
*   **Hybrid Logic:** Mix **Python** (for complex Pandas/Numpy transformations) and **SQL** (for heavy database aggregations) in the same pipeline.
*   **Event-Driven:** Trigger feature updates instantly from Redis Streams (`trigger="transaction_event"`).
*   **Extensibility:** Use `Before/After` hooks to customize retrieval or ingest pipelines.
*   **Observability:** Built-in OpenTelemetry tracing and cost estimation per-request.

#### 🚀 One-Command Deploy (New in v1.3.0)

Deploy to any cloud platform with generated configs:

```bash
meridian deploy fly --name my-app      # Fly.io
meridian deploy cloudrun --name my-app # Google Cloud Run
meridian deploy ecs --name my-app      # AWS ECS
meridian deploy railway --name my-app  # Railway
meridian deploy render --name my-app   # Render
```

Use `--dry-run` to preview generated files. [📖 Deployment Guide](https://davidahmann.github.io/meridian/local-to-production)

#### 🐚 Shell Completion
Enable tab completion for Bash, Zsh, Fish, and PowerShell:
```bash
meridian --install-completion
```

---

### 🏗️ Architecture

Meridian scales with you from **Laptop** to **Production**.

```mermaid
graph TD
    subgraph Dev [Tier 1: Local Development]
        A[Laptop] -->|Uses| B(DuckDB)
        A -->|Uses| C(In-Memory Dict)
        style Dev fill:#e1f5fe,stroke:#01579b
    end

    subgraph Prod [Tier 2: Production]
        D[API Pods] -->|Async| E[(Postgres + pgvector)]
        D -->|Async| F[(Redis)]
        style Prod fill:#fff3e0,stroke:#ff6f00
    end

    Switch{MERIDIAN_ENV} -->|development| Dev
    Switch -->|production| Prod
```

---

### 🏭 Production Configuration

Deploy to production by simply setting environment variables. No code changes required.

```bash
# Security
MERIDIAN_API_KEY=change_me_to_something_secure

# Data Stores
MERIDIAN_REDIS_URL=redis://redis-host:6379
MERIDIAN_POSTGRES_URL=postgresql+asyncpg://user:pass@db-host:5432/meridian  # pragma: allowlist secret

# LLM Providers (for RAG)
OPENAI_API_KEY=sk-...
```

---

### 🗺️ Roadmap

* ✅ **Phase 1:** Core API, DuckDB/Postgres support, Redis caching, FastAPI serving, PIT Correctness, Async I/O.
* ✅ **Phase 2 (v1.2.0):** Context Store, RAG infrastructure, pgvector, Event-Driven features, Time Travel.
* ✅ **Phase 3 (v1.3.0):** UI Visualization, Magic Retrievers, and DX Polish.
* 🚧 **Phase 4:** Drift detection, RBAC, and multi-region support.

---

### 🤝 Contributing

We love contributions! This is a community-driven project. Please read our [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

---

<div align="center">
  <p><b>Meridian</b> &copy; 2025</p>
  <p><i>Apache 2.0 License</i></p>
</div>
