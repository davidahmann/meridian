---
title: "Fabra Changelog: Release Notes and History"
description: "Stay up to date with Fabra releases. See what's new in v1.2.0 with Context Store for LLMs, and v1.1.0 with Hybrid Features and Point-in-Time Correctness."
keywords: fabra changelog, release notes, feature store updates, context store, rag updates, software version history
---

# Changelog

All notable changes to this project will be documented in this file.

## [v2.0.0] - 2025-12-09

### 🎉 Major Release: Rebrand to Fabra

*   **Rebrand:** Project renamed from Meridian to **Fabra** (context infrastructure for AI applications).
    *   Package renamed from `meridian-oss` to `fabra` on PyPI.
    *   CLI command changed from `meridian` to `fabra`.
    *   All imports changed from `from meridian` to `from fabra`.
*   **Breaking Changes:**
    *   Environment variables renamed: `MERIDIAN_*` → `FABRA_*`.
    *   Internal metric names renamed: `meridian_*` → `fabra_*`.
    *   Config file renamed: `meridian.toml` → `fabra.toml`.
*   **Migration:** Users of `meridian-oss` should update imports and environment variables.

---

## [v1.6.0] - 2025-12-09

### 🚀 Major Features: Next.js UI

*   **Next.js UI Migration:** Replaced Streamlit UI with modern Next.js 14 application.
    *   Built with React, TypeScript, and Tailwind CSS.
    *   App Router architecture for optimal performance.
    *   Dark theme with professional design.
*   **FastAPI Backend:** New dedicated UI backend server.
    *   `GET /api/store` - List features, retrievers, and contexts.
    *   `POST /api/features/get` - Retrieve feature values.
    *   `POST /api/context/assemble` - Assemble context with parameters.
*   **Feature Explorer:** Browse and search all registered features.
    *   View feature metadata, types, and dependencies.
    *   Real-time feature value retrieval with entity inputs.
*   **Context Assembly UI:** Interactive context testing.
    *   Parameter input forms with defaults.
    *   Rich result display with token counts and costs.
    *   Raw JSON viewer for debugging.
*   **E2E Testing:** Playwright test suite with 18 comprehensive tests.

### 🔧 Improvements

*   Removed legacy Streamlit UI (`src/fabra/ui.py`).
*   Simplified CLI `fabra ui` command (removed `--legacy` flag).
*   Updated pre-commit config with ESLint for TypeScript/TSX files.
*   Updated `.gitignore` with Next.js and Playwright artifacts.

---

## [v1.5.0] - 2025-12-09

### 🚀 Major Features: Freshness SLAs

*   **Freshness SLA Parameter:** Configure maximum age for features used in context assembly.
    *   `@context(store, freshness_sla="5m")` - Require features to be less than 5 minutes old.
    *   Supports multiple formats: `"30s"`, `"5m"`, `"1h"`, `"1d"`, `"500ms"`.
*   **Degraded Mode:** Graceful handling when features exceed SLA threshold.
    *   Context assembly succeeds but `freshness_status` becomes `"degraded"`.
    *   `freshness_violations` list provides details on stale features.
    *   Structured logging warns when SLA is breached.
*   **Strict Mode:** Optional hard failure on SLA breach.
    *   `@context(store, freshness_sla="30s", freshness_strict=True)` - Raise `FreshnessSLAError` on violation.
    *   Exception includes full violation details for debugging.
*   **Prometheus Metrics:**
    *   `fabra_context_freshness_status_total{status="guaranteed|degraded"}` - Track freshness status.
    *   `fabra_context_freshness_violations_total{feature="..."}` - Track violations by feature.
    *   `fabra_context_stalest_feature_seconds` - Histogram of stalest feature ages.

### 🔧 Improvements

*   Added `src/fabra/utils/time.py` with `parse_duration_to_ms()` and `format_ms_to_human()` utilities.
*   Added `FreshnessSLAError` exception with structured violation data.
*   Context meta now includes `freshness_violations` and `freshness_sla_ms` fields.
*   Added `is_fresh` property to `Context` class for easy checking.

### 📚 Documentation

*   Added [Freshness SLAs](freshness-sla.md) full guide.
*   Added [Freshness SLAs: When Your AI Needs Fresh Data](blog/freshness-guarantees.md) blog post.
*   40 new unit and integration tests for freshness SLA feature.

---

## [v1.4.0] - 2025-12-09

### 🚀 Major Features: Context Accountability

*   **Context Lineage Tracking:** Automatically track exactly what data was used in every context assembly.
    *   `FeatureLineage` records which features were retrieved, their values, timestamps, and freshness.
    *   `RetrieverLineage` records which retrievers were called, queries, result counts, and latencies.
    *   `ContextLineage` provides full assembly statistics including items dropped, token usage, and cost.
*   **UUIDv7 Context Identifiers:** Time-sortable unique IDs for efficient querying and debugging.
*   **Context Replay API:** Retrieve any historical context by ID for debugging and compliance.
    *   `store.get_context_at(context_id)` - Get full context with lineage.
    *   `store.list_contexts(start, end, limit)` - List contexts in a time range.
*   **REST API Endpoints:**
    *   `GET /v1/contexts` - List contexts with time filtering.
    *   `GET /v1/context/{id}` - Retrieve full context by ID.
    *   `GET /v1/context/{id}/lineage` - Get just the lineage data.
*   **CLI Commands:**
    *   `fabra context show <id>` - Display context details.
    *   `fabra context list` - List recent contexts.
    *   `fabra context export <id>` - Export context for audit (JSON/YAML).

### 🔧 Improvements

*   `AssemblyTracker` uses contextvars for clean lineage tracking without API changes.
*   Graceful degradation: context logging failures don't fail assembly.
*   Context table auto-created in both DuckDB and Postgres offline stores.

### 📚 Documentation

*   Added [Context Accountability](context-accountability.md) guide.
*   22 new unit tests for lineage models, tracking, and API endpoints.

---

## [v1.2.0] - 2025-12-07

### 🚀 Major Features: Context Store for LLMs

*   **Context Store:** Full RAG infrastructure for LLM applications.
    *   `@retriever` decorator for semantic search with automatic caching.
    *   `@context` decorator for composing context with token budgets.
    *   Priority-based truncation with `ContextItem(priority=N, required=True/False)`.
*   **Vector Search:**
    *   pgvector integration for Postgres with cosine similarity.
    *   Automatic document chunking via tiktoken.
    *   Multiple embedding providers (OpenAI, Cohere).
*   **Event-Driven Architecture:**
    *   `AxiomEvent` model for structured events.
    *   `RedisEventBus` for publishing to Redis Streams.
    *   `AxiomWorker` for consuming events and triggering feature updates.
    *   Trigger-based features with `@feature(trigger="event_name")`.
*   **DAG Resolution:**
    *   Implicit wiring via `{feature_name}` template syntax.
    *   `DependencyResolver` for automatic dependency graph construction.
*   **Observability:**
    *   `ContextTrace` model for debugging context assembly.
    *   `/context/{id}/explain` API endpoint.
    *   `ContextMetrics` for Prometheus integration.
*   **Time Travel:**
    *   `get_historical_features()` for point-in-time queries.
    *   Debug production issues by querying past state.
*   **Diagnostics:**
    *   `fabra doctor` CLI command for environment diagnostics.
    *   Checks Redis, Postgres, and environment variable configuration.

### 🐛 Bug Fixes

*   Fixed timing-safe API key comparison (now uses `secrets.compare_digest`).
*   Fixed Docker container running as root (now uses non-root user).
*   Fixed environment variable mismatch in docker-compose.yml.
*   Added HEALTHCHECK to Dockerfile.

### 📚 Documentation

*   Added [Context Store Overview](context-store.md) page.
*   Added [Retrievers](retrievers.md) page.
*   Added [Context Assembly](context-assembly.md) page.
*   Added [Event-Driven Features](event-driven-features.md) page.
*   Added [RAG Chatbot Use Case](use-cases/rag-chatbot.md).
*   Updated Architecture page with Context Store diagrams.

---

## [v1.1.0] - 2025-12-05

### 🚀 Major Features

*   **Production Stack (`FABRA_ENV=production`)**: full support for running in production with Postgres (Async) and Redis.
*   **Point-in-Time Correctness**:
    *   Development: Uses DuckDB `ASOF JOIN` logic for zero leakage.
    *   Production: Uses Postgres `LATERAL JOIN` logic for zero leakage.
*   **Async Offline Store**: `PostgresOfflineStore` now uses `asyncpg` for high-throughput I/O.
*   **Hybrid Feature Fixes**: Correctly merges Python (on-the-fly) and SQL (batch) features in retrieval.

### 🐛 Bug Fixes

*   Fixed `AttributeError` in `prod_app.py` regarding `timedelta`.
*   Fixed data loss issue in `PostgresOfflineStore` where Python features were dropped during hybrid retrieval.
*   Fixed type casting issues in `RedisOnlineStore`.

### 📚 Documentation

*   Added [Feast Comparison](feast-alternative.md) page.
*   Added [FAQ](faq.md) page.
*   Added Use Case guides:
    *   [Churn Prediction](use-cases/churn-prediction.md) (PIT Focus)
    *   [Real-Time Recommendations](use-cases/real-time-recommendations.md) (Hybrid Focus)
*   Added Architecture Diagram to README.

## [v1.0.2] - 2025-12-04

### Added
*   Initial support for Hybrid Features (Python + SQL).
