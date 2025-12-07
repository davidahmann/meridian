This is the foundational document for Meridian. It moves beyond "feature store" and defines the **Context Infrastructure** category.

-----

# Product Requirements Document (PRD): Meridian Context Platform

**Version:** 1.0 (Master Strategy)
**Status:** Approved for Phase 1 Execution
**Author:** David Ahmann (User) & Gemini (AI Partner)

-----

## 1\. Executive Summary & Vision

**The Thesis:**
We are witnessing a shift in AI architecture similar to the "Data Lakehouse" shift of 2015. Just as Databricks unified Data Warehouses (structured) and Data Lakes (unstructured) into a single platform, **Meridian unifies Feature Stores (structured) and Vector Databases (unstructured) into a single "Context Store."**

**The Problem:**
AI Engineers today are building "Context Pipelines" using glue code (LangChain) to stitch together Redis, Pinecone, and SQL. This approach is:

1.  **Fragile:** No guarantees that data is fresh.
2.  **Unobservable:** You cannot debug why an LLM hallucinated (was it the retrieval? the prompt? the stale data?).
3.  **Ephemeral:** Context is lost immediately after the request. There is no system of record.

**The Solution:**
**Meridian** is the world’s first **Context Infrastructure**. It is an open-source platform that manages the **State of AI**. It handles ingestion, indexing, retrieval, and assembly of context with production guarantees: freshness, lineage, and replayability.

**The "Databricks" Moment:**
We are not building a tool to *connect* things (like LangChain). We are building the infrastructure that *stores and manages* the integrity of the data fed to LLMs.

-----

## 2\. Strategic Differentiation (Why We Win)

Meridian is not just "different" (better features); it is **unique** (solving a different problem).

| Concept | The Status Quo (Competitors) | The Meridian Way (Unique) |
| :--- | :--- | :--- |
| **Category** | Feature Store OR Vector DB | **Context Store** (Unified) |
| **Philosophy** | "We store vectors." | **"We manage Context Integrity."** |
| **Architecture** | Microservices / Kubernetes | **Boring Tech** (Postgres + Redis + Python) |
| **Data Flow** | Read-Only Wrapper (Bring your own data) | **Managed Write Path** (We own the index & freshness) |
| **Debugging** | Trace Logs (What happened?) | **Time-Travel Replay** (Recreate the state exactly) |
| **Context** | Simple String Concatenation | **Dependency Graph & Token Prioritization** |

-----

## 3\. Jobs to Be Done (JTBD)

**Primary Persona:** The AI Product Engineer (Full-stack, Python-native, building RAG/Agents).

1.  **"Stop the Hallucinations":** When the model fails, I need to know *exactly* what context was fed to it, and if that context was stale or truncated.
      * *Feature:* `explain_context()`
2.  **"Pass the Audit":** I need to prove to Compliance that the "Safety Guidelines" document was *definitely* included in the context window for every chat.
      * *Feature:* `required=True` (Priority Token Budgeting)
3.  **"Time Travel":** I need to reproduce a bug from last Tuesday. I need the user's features and the vector search results exactly as they were *then*, not as they are *now*.
      * *Feature:* Point-in-Time Correctness & Replay.
4.  **"Freshness Guarantee":** I need the bot to know about the transaction that happened 1 second ago, not 1 hour ago.
      * *Feature:* Event-Driven Triggers.

-----

## 4\. Architecture & Technology

  * **Language:** Python (98%), Rust (optional for heavy tokenizer lifting later).
  * **Offline Store:** PostgreSQL (with `pgvector`).
  * **Online Store:** Redis (with Streams).
  * **DX:** Decorator-based (`@feature`, `@context`, `@index`).
  * **Deployment:** Single container / `pip install`. No mandatory Kubernetes.

-----

## 5\. Functional Requirements (The Roadmap)

### Phase 1: The Event Wedge (Real-Time Foundation)

*Goal: Enable sub-second freshness for structured features.*

  * **FR-1.1 Event Ingestion:** `POST /ingest` endpoint backed by Redis Streams.
  * **FR-1.2 Trigger Logic:** `@feature(trigger="purchase_event")`. Consumer auto-updates the online store upon event receipt.
  * **FR-1.3 Entity Routing:** Mapping event payloads to specific `entity_ids`.

### Phase 2: The Managed Index (The Context Moat)

*Goal: Own the write path for unstructured data to guarantee freshness.*

  * **FR-2.1 Managed Index Definition:**
    ```python
    @index(name="kb", backend="pgvector", embedding="openai/v3")
    class KnowledgeBase: pass
    ```
  * **FR-2.2 The Write API:** `store.index(entity_id, text)`. Meridian handles chunking, embedding, and storage. When we implement store.index(), we aren't just storing text; we are storing provenance (source URL, hash, timestamp) to enable future auditing.
  * **FR-2.3 Read-Only Connector (Phase 2a):** Support for external Pinecone/Qdrant indices (for low-friction adoption), but with explicit "No Freshness Guarantee" warnings.

### Phase 3: Intelligent Assembly (The Brain)

*Goal: Solve "Context Tetris" automatically.*

  * **FR-3.1 The Context Decorator:** generating a context_id is immediate and mandatory. This ID is the "foreign key" that links Meridian to the future Lumyn and Clyra products.
    ```python
    @context(entity=User, max_tokens=4000)
    def chat_ctx(user_id): ...
    ```
  * **FR-3.2 Implicit DAG Resolution:** Automatically detect that Retriever B depends on Feature A (e.g., `{user.preference}`) and execute in the correct order (Sequential vs. Parallel).
  * **FR-3.3 Token Budgeting:** Support `required=True` (never drop) vs. `optional=True` (drop if full).
  * **FR-3.4 Truncation Strategies:** Smart trimming (summarize vs. cut).

### Phase 4: Observability & Replay (The Enterprise Value)

*Goal: The reason large companies pay us.*

  * **FR-4.1 Context Trace:** Store the *metadata* of every assembled context (inputs, versions, latency, cost).
  * **FR-4.2 Explainability API:** `store.explain_context(id)` returns JSON detailing why items were included or dropped.
  * **FR-4.3 Logical Replay:** Ability to reconstruct a context object from a past timestamp using event logs.

-----

## 6\. Non-Functional Requirements (NFRs)

1.  **Latency:**
      * Event-to-Online-Store: \< 500ms.
      * Context Assembly (Cached): \< 10ms.
      * Context Assembly (Computed): Overhead \< 50ms (excluding external embedding latency).
2.  **Scalability:**
      * Support 100M+ keys in Redis.
      * Support 10M+ vectors in Postgres (before recommending external vector DB).
3.  **Reliability:**
      * Circuit Breakers: If OpenAI is down, fallback to cached context or default values. Never crash the app.
4.  **Usability:**
      * "30 Seconds to Value": Must run locally without Docker if needed (using DuckDB/In-Memory).

-----

## 7\. Success Criteria

**Product Metrics:**

  * **Latency:** P99 context assembly under 100ms.
  * **Integrity:** 100% of "Required" tokens are present in valid responses.

**Growth Metrics (The "Databricks" Indicators):**

  * **Adoption:** 1,000+ GitHub Stars in first 3 months of launch.
  * **Category Recognition:** Other tools describe themselves as "Context Stores" or "Context Managers."
  * **Usage:** 5+ production users migrating *away* from custom LangChain glue code to Meridian.

-----

## 8\. Risks & Mitigations

| Risk | Impact | Mitigation |
| :--- | :--- | :--- |
| **"Just use LangChain"** | Developers view us as redundant. | Position on **State** vs. Flow. We store the data; LangChain orchestrates the calls. We are the database, they are the controller. |
| **Vector DB Lock-in** | Users refuse to move data to Postgres. | Phase 2a (Connector Mode). Allow external vectors initially, then upsell "Freshness" which requires migration. |
| **Complexity Creep** | DAG resolution becomes too hard to debug. | Keep the V1 DAG simple (Single-pass dependency only). Provide visualization tools (`meridian ui`) to see the graph. |
| **Cloud Giants** | AWS releases "Context Store." | We win on DX (Local-first, Python-native) and Open Source agnosticism. |

-----

## 9\. Next Steps (Immediate)

1.  **Execute Phase 1:** Implement Redis Streams & Event Triggers.
2.  **Marketing Prep:** Draft the "Manifesto" blog post ("Why Feature Stores are Dead; Long Live Context Stores").
3.  **Design Review:** Finalize the `@index` API syntax for Phase 2.
