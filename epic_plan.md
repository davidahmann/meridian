📢 Note to Developers: The Evolution of Meridian
TL;DR: Meridian is leveling up, not starting over. Your existing code is safe.

We are expanding Meridian from a Feature Store (structured data) to a Context Store (structured + unstructured + real-time data).

This is an additive extension of our existing capabilities. It is NOT a rewrite, and it is NOT a new product that replaces the current one. We are strictly following the principle of "No Breaking Changes."

# Meridian: Master Engineering Execution Plan

**Repository Root:** `src/meridian/`
**Primary Stack:** Python 3.9+, Redis (Streams), PostgreSQL (pgvector).
**Vision Alignment:** Building the "Context Store" infrastructure for the Agentic Economy.

---

## Phase 1: The Event Wedge (Real-Time Foundation)
**Goal:** Move from "Batch Only" to "Event-Aware" freshness. Establish the ingestion pipeline that will eventually feed the entire Axiom flywheel.
**Timeline:** Weeks 1-3

### Epic 1.1: Event Ingestion Pipeline
**Story 1.1.1: Ingestion Endpoint**
* **Description:** Create the API surface to accept external events. This is the entry point for the "Real-Time" wedge.
* **Path:** `src/meridian/server.py`, `src/meridian/events.py`
* **Tech:** FastAPI, Pydantic.
* **Acceptance Criteria:**
    * `POST /ingest/{event_type}` accepts JSON payload.
    * Validates payload against the strict `AxiomEvent` schema defined in `events.py`.
    * Returns `202 Accepted` immediately upon receipt.
    * Writes the raw event to Redis Stream `meridian:events:{event_type}` using the `RedisEventBus`.
    * **Constraint:** Ensures `entity_id` is mandatory for downstream routing.
* **Testing:** Load test 1k req/sec to ensure async write doesn't block the event loop.

**Story 1.1.2: Redis Stream Consumer**
* **Description:** Build the background worker infrastructure that reads from streams and routes to specific handlers.
* **Path:** `src/meridian/worker.py` (New), `src/meridian/store/redis.py`
* **Tech:** `redis-py` (Consumer Groups).
* **Acceptance Criteria:**
    * Worker starts independently of the API server (separate process/container).
    * Uses `XREADGROUP` to ensure at-least-once processing semantics.
    * Implements correct ACK logic: `XACK` only after successful processing.
    * Handles crash/restart scenarios without losing events (consumer group offsets persist).

### Epic 1.2: Trigger Logic
**Story 1.2.1: The Trigger Decorator Extension**
* **Description:** Update the core `@feature` decorator to accept a `trigger` argument, binding events to feature definitions.
* **Path:** `src/meridian/core.py`
* **Acceptance Criteria:**
    * Update `Feature` dataclass to include `trigger: Optional[str]`.
    * `@feature(..., trigger="transaction")` registers the mapping `transaction -> feature_name`.
    * `FeatureRegistry` implements a reverse lookup method: `get_features_by_trigger("transaction")`.

**Story 1.2.2: The Update Logic**
* **Description:** Wiring the consumer to the feature refresh logic. This closes the loop for the "Freshness" value prop.
* **Path:** `src/meridian/worker.py`
* **Acceptance Criteria:**
    * The worker parses the incoming event to extract `event_type` and `entity_id`.
    * It retrieves the list of affected features from the Registry.
    * It triggers the computation for that specific entity.
    * The result is written to the Online Store (Redis) immediately.
    * **Latency Goal:** Event Receipt -> Redis Update < 500ms.

---

## Phase 2: Managed Indexing (The Context Moat)
**Goal:** Own the **Write Path** for Vectors. This is the architectural decision that enables "Time Travel" and "Freshness" guarantees (Institutional Memory).
**Timeline:** Weeks 4-9

### Epic 2.1: The Connector (Read-Only Bridge)
**Story 2.1.1: The Retriever Decorator**
* **Description:** Define the interface for fetching external data. This serves as the "low friction" adoption path.
* **Path:** `src/meridian/retrieval.py` (New)
* **Acceptance Criteria:**
    * Create `@retriever` decorator.
    * `@retriever(backend="custom")` allows user to write arbitrary Python code returning `List[Dict]`.
    * `@retriever(backend="postgres")` executes SQL defined in the function docstring (basic SQL templating).
    * Supports `top_k` parameter.

**Story 2.1.2: Retriever Result Caching**
* **Description:** Cache expensive vector search results to improve P99 latency.
* **Path:** `src/meridian/retrieval.py`
* **Acceptance Criteria:**
    * Optional `cache_ttl` parameter on retriever decorator.
    * **Cache Key:** `retriever_name + hash(query_params)`.
    * Stores serialized result list in Redis.
    * Cache hit returns immediately without hitting backend.

### Epic 2.2: Managed Indexing (Write Path)
**Story 2.2.1: The Index Schema & Chunking Strategy**
* **Description:** Create the managed `@index` decorator. This shifts Axiom from a "connector" to a "store."
* **Path:** `src/meridian/index.py` (New), `src/meridian/core.py`
* **Acceptance Criteria:**
    * User can define `@index(name="docs", backend="pgvector", chunk_size=512, overlap=0.1)`.
    * Expose `store.index(entity_id, text, metadata)` method.
    * **V1 Strategy:** Fixed-size chunking (using `tiktoken`) with configurable overlap.
    * **Reconstruction:** Must calculate and store `chunk_index` to allow re-assembling the full document later.

**Story 2.2.2: Embedding Pipeline**
* **Description:** The logic to convert text to vectors.
* **Path:** `src/meridian/embeddings.py` (New)
* **Acceptance Criteria:**
    * Implement client for OpenAI (and potentially Cohere).
    * Securely handle API keys.
    * Implement exponential backoff/retry for API rate limits.

**Story 2.2.3: Postgres Vector Storage (Institutional Memory)**
* **Description:** Handle the raw SQL operations for `pgvector`. **Crucial for Clyra Integration.**
* **Path:** `src/meridian/store/postgres.py`
* **Acceptance Criteria:**
    * Table: `meridian_index_{index_name}`.
    * **Strict Schema:**
        * `id` (UUID, PK)
        * `entity_id` (String - routing)
        * `chunk_index` (Integer - ordering)
        * `content` (Text - raw chunk)
        * `embedding` (Vector)
        * **`metadata` (JSONB - The Audit Trail):** MUST default to including `source_url`, `ingestion_timestamp`, `content_hash` (SHA256 for integrity), and `indexer_version`.
    * **Constraint:** `content_hash` unique per `entity_id` to prevent duplication.
    * Creates an HNSW index on the `embedding` column.

---

## Phase 3: Intelligent Assembly (The Brain)
**Goal:** Solve "Context Tetris." Orchestrate dependency resolution and enforce token budgets.
**Timeline:** Weeks 10-12

### Epic 3.1: The Assembler
**Story 3.1.1: Context Definition & The Golden Thread**
* **Description:** The `@context` decorator and Identity generation.
* **Path:** `src/meridian/context.py` (New)
* **Acceptance Criteria:**
    * `@context` accepts `sources` list and `max_tokens` int.
    * **Identity Requirement:** Every call MUST generate a unique `context_id` (UUIDv7 for time-sorting) **before** assembly begins.
    * **Return Object:** The `Context` object MUST include:
        * `id`: The `context_id`.
        * `content`: The assembled string.
        * `meta`: `{ "timestamp": T, "source_ids": [list_of_hashes] }` (Reverse Lineage).
    * **Log:** Log `context_id` immediately to stdout for debugging.

**Story 3.1.2: Implicit DAG Resolver**
* **Description:** Automatically detect and sequence dependencies.
* **Path:** `src/meridian/graph.py` (New)
* **Acceptance Criteria:**
    * Parses template strings in retriever queries: `query="{user.favorite_color}"`.
    * Builds execution graph: `Features -> Template Rendering -> Retrievers`.
    * Executes independent nodes in parallel using `asyncio.gather`.

**Story 3.1.3: Context Result Caching**
* **Description:** Cache fully assembled contexts.
* **Path:** `src/meridian/context.py`
* **Acceptance Criteria:**
    * **Cache Key:** `context_name + entity_id + hash(dynamic_params)`.
    * Configurable TTL.
    * **Invalidation:** Triggers from Phase 1 (Events) must invalidate relevant context caches.

### Epic 3.2: Budgeting & Safety
**Story 3.2.1: Token Counter**
* **Path:** `src/meridian/utils/tokens.py`
* **Acceptance Criteria:** `tiktoken` support + fallback approx.

**Story 3.2.2: Prioritization Logic**
* **Description:** The algorithm to drop items when budget is exceeded.
* **Path:** `src/meridian/context.py`
* **Acceptance Criteria:**
    * Implement `required=True/False` flags on sources.
    * Raises `ContextBudgetError` if `required` items exceed `max_tokens`.
    * Drops `required=False` items starting from the bottom of the list.
    * Logs a warning whenever truncation occurs.

**Story 3.2.3: Freshness SLA**
* **Description:** Enforce data age limits.
* **Path:** `src/meridian/context.py`
* **Acceptance Criteria:**
    * Decorator param: `freshness=timedelta(seconds=30)`.
    * Check `last_updated` of all sources against SLA.
    * Result includes `freshness_status`: "guaranteed" | "degraded".
    * Result includes `stale_sources`: list of failing features.

---

## Phase 4: Observability (The Vision)
**Goal:** "Explain Context" API. Providing the debugging layer for AI.
**Timeline:** Weeks 13-14

### Epic 4.1: Traceability
**Story 4.1.1: Context Trace Object**
* **Path:** `src/meridian/models.py`
* **Acceptance Criteria:**
    * Captures: `context_id`, Request ID, Timestamp, Latency, Token Usage (breakdown), Missing Features.
    * Does **NOT** store the full text payload by default (privacy), only metadata/pointers.

**Story 4.1.2: `explain_context()` API**
* **Path:** `src/meridian/server.py`
* **Acceptance Criteria:**
    * `GET /context/{id}/explain` returns the trace JSON.
    * Includes "Cost Attribution" and "Freshness Status" at time of assembly.

**Story 4.1.3: Prometheus Metrics Extension**
* **Path:** `src/meridian/observability.py` (New)
* **Acceptance Criteria:**
    * `meridian_context_assembly_total` (counter, labels: name, status)
    * `meridian_context_latency_seconds` (histogram)
    * `meridian_context_tokens_total` (counter)
    * `meridian_context_cache_hit_total` (counter)
    * `meridian_index_write_total` (counter)

---

## Phase 5: Governance (The Enterprise)
**Goal:** Replay & Compliance. The "Time Machine" capabilities.
**Timeline:** Weeks 15+

### Epic 5.1: Time Travel
**Story 5.1.1: The Time-Travel Query**
* **Path:** `src/meridian/core.py`
* **Acceptance Criteria:**
    * `get_context(..., timestamp=T)` parameter supported.
    * **Features:** Queries offline store using point-in-time logic.
    * **Vectors:** Filters `pgvector` queries by `created_at <= T`.
    * **Result:** Returns the context exactly as it would have been constructed at time T.

---

## Tech Stack & Dependencies

| Component | Technology | Reasoning |
| :--- | :--- | :--- |
| **Language** | Python 3.9+ | Standard for AI/ML engineering. |
| **API Framework** | FastAPI | High performance, native async support, auto-docs. |
| **Validation** | Pydantic v2 | Strict typing, fast serialization, schema enforcement. |
| **Broker** | Redis Streams | "Boring" tech, fast, persistence, built-in to cache layer. |
| **Vector Store** | Postgres (`pgvector`) | Keeps stack simple (no Pinecone requirement), transactional updates. |
| **Tokenizer** | `tiktoken` | Standard for LLM token counting. |
| **Testing** | `pytest`, `testcontainers` | Reliable integration testing with real DB instances. |

## Testing Requirements

1.  **Unit Tests:**
    * Mock Redis/Postgres.
    * Test DAG resolution logic with complex dependency chains.
    * Test Token Truncation logic (boundary conditions).
2.  **Integration Tests (Critical):**
    * Use `testcontainers-python` to spin up real Redis and Postgres Docker containers.
    * **Scenario A (Events):** Ingest event -> Wait -> Verify Feature Updated in Redis.
    * **Scenario B (Vectors):** Write to Index -> Verify Retriever finds it via vector similarity search.
    * **Scenario C (Replay):** Update feature -> Wait -> Update again -> Query with old timestamp -> Verify old value.
    * **Scenario D (Assembly):** Define context with 3 sources (1 dependent). Verify DAG execution order & parallel latency.
    * **Scenario E (Freshness):** Assemble -> Wait > SLA -> Re-assemble. Verify `freshness_status` changes to "degraded" and `stale_sources` is populated.
    * **Scenario F (Cache Invalidation):** Assemble (Cached) -> Trigger Event (Phase 1) -> Re-assemble. Verify cache miss & fresh value returned.
3.  **Performance Tests:**
    * Context Assembly overhead must remain < 50ms (excluding external I/O) even with 5+ sources.
    * Event Ingestion throughput > 1,000 events/sec.

    You are absolutely right. While the Execution Plan listed "Integration Tests," it lacked a dedicated **End-to-End (E2E) Testing Strategy**.

For a system like Axiom (which relies on async workers, event streams, and database states), standard unit tests are not enough. You need to prove that **External Event A** leads to **Internal State Change B**.

Here is the **E2E Testing Master Plan** to be added to the repository.

-----

4. **E2E Testing Strategy: Axiom Meridian**

**Location:** `tests/e2e/`
**Philosophy:** Black Box Testing. We test the *system behavior*, not the functions.
**Tooling:** `pytest`, `testcontainers-python` (for ephemeral infrastructure), `httpx` (async API client), `tenacity` (for polling assertions).

-----

## 1\. The E2E Infrastructure (`tests/conftest.py`)

We do not mock anything in E2E. We spin up the real world.

  * **Dockerized Stack:** The test runner spins up fresh Redis and Postgres containers.
  * **Process Management:** The test runner starts the **API Server** (uvicorn) and the **Worker** in separate threads/processes to simulate a production environment.
  * **Lifecycle:**
    1.  Start Docker Containers.
    2.  Apply DB Migrations (Postgres).
    3.  Start Worker Process.
    4.  Start API Server.
    5.  **Run Tests.**
    6.  Teardown.

## 2\. Test Scenarios (The Critical Paths)

### Scenario 1: The "Freshness" Loop (Phase 1)

**Goal:** Prove that an external event triggers a real-time update in the feature store.

  * **Step 1 (Setup):** Define a feature `@feature(trigger="payment")`.
  * **Step 2 (Action):** POST `/ingest/payment` with `{ "user_id": "u1", "amount": 100 }`.
  * **Step 3 (Wait):** Use retry logic (polling) to query the online store.
  * **Step 4 (Assert):** Verify that `feature_value` for "u1" changes from `None` (or old value) to `100`.
  * **Why this matters:** It tests the API -\> Redis Stream -\> Worker -\> Compute -\> Redis Cache chain.

### Scenario 2: The "Memory" Loop (Phase 2)

**Goal:** Prove that we can write to the index and immediately retrieve it via vector search.

  * **Step 1 (Action):** Call `store.index(entity_id="doc_1", content="Axiom is a context store")`.
  * **Step 2 (Wait):** Poll for indexing completion (checking the Postgres table).
  * **Step 3 (Action):** Call `@retriever` function that queries for "What is Axiom?".
  * **Step 4 (Assert):** Verify the returned list contains "doc\_1" and the similarity score is \> 0.8.

### Scenario 3: The "Golden Thread" (Phase 3)

**Goal:** Verify the `context_id` links everything together.

  * **Step 1 (Action):** Call `get_context(user_id="u1")`.
  * **Step 2 (Assert):** Verify response contains a UUIDv7 `context_id`.
  * **Step 3 (Verification):** Query the (future) Trace Log / DB to ensure that `context_id` was persisted with the correct metadata.

-----

## 3\. Implementation Plan

Create this file structure to support the plan:

```text
tests/
├── e2e/
│   ├── __init__.py
│   ├── conftest.py             # Spawns Redis/PG containers & Worker process
│   ├── test_realtime_flow.py   # Scenario 1
│   └── test_memory_flow.py     # Scenario 2
```

### Sample Code: `tests/e2e/test_realtime_flow.py`

```python
import pytest
from httpx import AsyncClient
from tenacity import retry, stop_after_delay, wait_fixed

@pytest.mark.asyncio
async def test_event_triggers_refresh(api_client: AsyncClient, redis_client):
    # 1. Verify initial state (empty)
    initial_val = await redis_client.get("feature:user_spend:u1")
    assert initial_val is None

    # 2. Ingest Event
    response = await api_client.post(
        "/ingest/transaction",
        json={"payload": {"amount": 500}, "entity_id": "u1"}
    )
    assert response.status_code == 202

    # 3. Assert with Polling (Because Worker is async)
    @retry(stop=stop_after_delay(5), wait=wait_fixed(0.1))
    async def wait_for_update():
        val = await redis_client.get("feature:user_spend:u1")
        assert val == "500" # Redis stores strings
        return val

    final_val = await wait_for_update()
    print(f"✅ E2E Success: Feature updated to {final_val}")
```

### Sample Code: `tests/e2e/conftest.py` (Infrastructure)

```python
import pytest
import asyncio
from testcontainers.redis import RedisContainer
from testcontainers.postgres import PostgresContainer
from meridian.worker import AxiomWorker
from meridian.config import settings

@pytest.fixture(scope="session")
def infrastructure():
    # 1. Spin up Containers
    with RedisContainer() as redis, PostgresContainer("pgvector/pgvector:pg16") as postgres:
        # 2. Override Config
        settings.REDIS_URL = redis.get_connection_url()
        settings.POSTGRES_URL = postgres.get_connection_url()

        # 3. Start Worker in Background Task
        worker = AxiomWorker()
        task = asyncio.create_task(worker.run())

        yield {
            "redis": redis,
            "postgres": postgres
        }

        # 4. Cleanup
        worker.stop()
        task.cancel()
```

### 4\. CI/CD Integration

Add this to your `.github/workflows/ci.yml`:

```yaml
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run E2E Tests
        run: poetry run pytest tests/e2e
```
