# Meridian v1.4-v1.5 Implementation Plan

## The Narrative Shift

**Current positioning:** "Radically simpler context store"

**Target positioning:** "The only context store that can answer: what did the AI know when it decided?"

This shift requires four capabilities:
1. **Owning the write path** — ✅ Already have this
2. **Logging context at decision time** — 🔨 v1.4
3. **Replay capability** — 🔨 v1.4
4. **Lineage tracking** — 🔨 v1.4
5. **Freshness SLAs** — 🔨 v1.5

---

## Phase 1: Context Accountability (v1.4)

### Overview

Every `@context` call becomes an auditable event with full replay capability.

```python
# What we're building
@context(store, max_tokens=4000)
async def build_prompt(user_id: str, query: str):
    tier = await store.get_feature("user_tier", user_id)
    docs = await search_docs(query)
    return [
        ContextItem(content=f"User tier: {tier}", priority=0),
        ContextItem(content=str(docs), priority=1),
    ]

# After v1.4, this returns:
ctx = await build_prompt("user_123", "how do I reset my password?")

ctx.id           # "01914a6c-5f3a-7b8c-9d2e-1a2b3c4d5e6f" (UUIDv7)
ctx.content      # Assembled context string
ctx.lineage      # Full audit trail
ctx.meta         # Token usage, freshness, cost

# And this becomes possible:
historical = await store.get_context_at("01914a6c-5f3a-7b8c-9d2e-1a2b3c4d5e6f")
# Returns EXACTLY what the AI knew at decision time
```

---

### 1.1 Context ID Generation (UUIDv7)

**Goal:** Every context assembly gets a unique, time-sortable identifier.

**Why UUIDv7:**
- Time-sortable (first 48 bits are timestamp)
- Database-friendly (better index performance than UUIDv4)
- No coordination required (can generate client-side)
- Already have `uuid6` dependency in pyproject.toml

**Implementation:**

```python
# src/meridian/context.py

import uuid6

class Context(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid6.uuid7()),
        description="Unique UUIDv7 identifier for this context assembly"
    )
    content: str
    meta: Dict[str, Any]
    lineage: Optional["ContextLineage"] = None
    version: str = "v1"
```

**Files to modify:**
- `src/meridian/context.py` — Add ID generation to Context class

**Tests:**
- Unit: Verify UUIDv7 format and uniqueness
- Unit: Verify time-sortability (later contexts have greater IDs)

**Acceptance criteria:**
- [ ] Every `Context` object has a unique `id` field
- [ ] IDs are valid UUIDv7 format
- [ ] IDs are time-sortable

---

### 1.2 Context Lineage Model

**Goal:** Track exactly what data sources fed each context assembly.

**Data model:**

```python
# src/meridian/models.py (new file or extend existing)

from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class FeatureLineage(BaseModel):
    """Record of a feature used in context assembly."""
    feature_name: str
    entity_id: str
    value: Any
    timestamp: datetime  # When this value was computed
    freshness_ms: int    # Age at assembly time
    source: str          # "cache" | "compute" | "fallback"

class RetrieverLineage(BaseModel):
    """Record of a retriever call in context assembly."""
    retriever_name: str
    query: str
    results_count: int
    latency_ms: int
    index_name: Optional[str] = None

class ContextLineage(BaseModel):
    """Full lineage for a context assembly."""
    context_id: str
    timestamp: datetime

    # What was used
    features_used: List[FeatureLineage]
    retrievers_used: List[RetrieverLineage]

    # Assembly metadata
    items_provided: int      # Total items returned by function
    items_included: int      # Items that fit in budget
    items_dropped: int       # Items dropped due to budget

    # Freshness
    freshness_status: str    # "guaranteed" | "degraded" | "unknown"
    stalest_feature_ms: int  # Age of oldest feature used

    # Token economics
    token_usage: int
    max_tokens: int
    estimated_cost_usd: float
```

**Files to create/modify:**
- `src/meridian/models.py` — Add lineage models
- `src/meridian/context.py` — Integrate lineage into Context

**Tests:**
- Unit: Lineage model serialization/deserialization
- Unit: Lineage captures all features used
- Unit: Lineage captures all retrievers used
- Integration: End-to-end lineage through context assembly

**Acceptance criteria:**
- [ ] `ContextLineage` model defined with all fields
- [ ] Lineage correctly tracks feature usage
- [ ] Lineage correctly tracks retriever usage
- [ ] Lineage serializes to JSON for storage

---

### 1.3 Context Logging to Offline Store

**Goal:** Persist full context (not just features) for replay.

**Storage schema:**

```sql
-- DuckDB (development)
CREATE TABLE context_log (
    context_id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    content TEXT NOT NULL,
    lineage JSON NOT NULL,
    meta JSON NOT NULL,
    version VARCHAR DEFAULT 'v1'
);

CREATE INDEX idx_context_log_timestamp ON context_log(timestamp);

-- Postgres (production) - same schema with JSONB
CREATE TABLE context_log (
    context_id VARCHAR(36) PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    content TEXT NOT NULL,
    lineage JSONB NOT NULL,
    meta JSONB NOT NULL,
    version VARCHAR(10) DEFAULT 'v1'
);

CREATE INDEX idx_context_log_timestamp ON context_log(timestamp);
```

**Implementation:**

```python
# src/meridian/context.py

async def _log_context(self, ctx: Context) -> None:
    """Persist context to offline store for replay."""
    await self.store.offline_store.log_context(
        context_id=ctx.id,
        timestamp=ctx.meta["timestamp"],
        content=ctx.content,
        lineage=ctx.lineage.model_dump() if ctx.lineage else {},
        meta=ctx.meta
    )
```

**Files to modify:**
- `src/meridian/store.py` — Add `log_context` method to offline stores
- `src/meridian/context.py` — Call logging after assembly
- `src/meridian/offline/duckdb.py` — Implement DuckDB logging
- `src/meridian/offline/postgres.py` — Implement Postgres logging

**Tests:**
- Unit: Context logged to DuckDB
- Unit: Context logged to Postgres
- Integration: Log survives process restart
- Performance: Logging adds <5ms latency

**Acceptance criteria:**
- [ ] Context logged to DuckDB in development
- [ ] Context logged to Postgres in production
- [ ] Logging is async and non-blocking
- [ ] Logging failure does not fail context assembly (graceful degradation)

---

### 1.4 Context Replay API

**Goal:** Retrieve exact historical context by ID.

**API:**

```python
# Python API
ctx = await store.get_context_at(context_id="01914a6c-...")
# Returns Context object with full content and lineage

# REST API
GET /context/{context_id}
# Returns JSON with content, lineage, meta
```

**Implementation:**

```python
# src/meridian/core.py

class FeatureStore:
    async def get_context_at(self, context_id: str) -> Optional[Context]:
        """Retrieve a historical context by ID.

        Args:
            context_id: The UUIDv7 identifier from a previous context assembly.

        Returns:
            The exact Context object that was assembled, or None if not found.
        """
        row = await self.offline_store.get_context(context_id)
        if row is None:
            return None

        return Context(
            id=row["context_id"],
            content=row["content"],
            lineage=ContextLineage(**row["lineage"]) if row["lineage"] else None,
            meta=row["meta"],
            version=row["version"]
        )
```

**Files to modify:**
- `src/meridian/core.py` — Add `get_context_at` method
- `src/meridian/offline/duckdb.py` — Add `get_context` query
- `src/meridian/offline/postgres.py` — Add `get_context` query
- `src/meridian/api.py` — Add REST endpoint

**Tests:**
- Unit: Retrieve context by ID (DuckDB)
- Unit: Retrieve context by ID (Postgres)
- Unit: Return None for non-existent ID
- Integration: Round-trip (assemble → log → retrieve)
- API: REST endpoint returns correct data

**Acceptance criteria:**
- [ ] `get_context_at()` returns exact historical context
- [ ] REST endpoint `/context/{id}` works
- [ ] Non-existent IDs return None/404 (not error)
- [ ] Retrieved context matches original exactly

---

### 1.5 Lineage Collection During Assembly

**Goal:** Automatically capture lineage as context is assembled.

**Implementation approach:**

The `@context` decorator needs to intercept feature and retriever calls within the decorated function to build lineage. Options:

**Option A: Explicit tracking context**
```python
@context(store, max_tokens=4000)
async def build_prompt(user_id: str, query: str):
    # Internally, store tracks all get_feature calls
    tier = await store.get_feature("user_tier", user_id)
    docs = await search_docs(query)
    # Lineage automatically populated
```

**Option B: Context variable for tracking**
```python
# Use contextvars to track calls within assembly
_assembly_context: ContextVar[Optional[AssemblyTracker]] = ContextVar(...)

# In get_feature:
if tracker := _assembly_context.get():
    tracker.record_feature(name, entity_id, value, timestamp)
```

**Recommended: Option B** — cleaner, doesn't require API changes.

**Files to modify:**
- `src/meridian/context.py` — Add `AssemblyTracker` and context variable
- `src/meridian/core.py` — Record feature calls when tracker active
- `src/meridian/retrieval.py` — Record retriever calls when tracker active

**Tests:**
- Unit: Tracker captures feature calls
- Unit: Tracker captures retriever calls
- Unit: Tracker handles nested contexts correctly
- Integration: Full lineage captured in real assembly

**Acceptance criteria:**
- [ ] All `get_feature` calls within `@context` are tracked
- [ ] All retriever calls within `@context` are tracked
- [ ] Lineage includes timing information
- [ ] Lineage includes source (cache/compute)

---

### 1.6 API Updates

**New REST endpoints:**

```
GET /context/{context_id}
    Returns historical context by ID

GET /context/{context_id}/lineage
    Returns just the lineage for a context

GET /contexts?start={timestamp}&end={timestamp}&limit={n}
    List contexts in time range (for debugging)
```

**Files to modify:**
- `src/meridian/api.py` — Add new endpoints

**Tests:**
- API: All endpoints return correct data
- API: Pagination works for list endpoint
- API: Invalid IDs return 404

**Acceptance criteria:**
- [ ] All REST endpoints implemented
- [ ] OpenAPI spec updated
- [ ] Endpoints handle errors gracefully

---

### 1.7 CLI Updates

**New commands:**

```bash
# Inspect a context
meridian context show <context_id>

# List recent contexts
meridian context list --limit 10

# Export context for audit
meridian context export <context_id> --format json
```

**Files to modify:**
- `src/meridian/cli.py` — Add context subcommands

**Tests:**
- CLI: Commands execute without error
- CLI: Output formats correctly

**Acceptance criteria:**
- [ ] `meridian context show` works
- [ ] `meridian context list` works
- [ ] `meridian context export` works

---

### 1.8 Testing Strategy for v1.4

**Unit tests:**
- `tests/test_context_id.py` — UUIDv7 generation
- `tests/test_lineage.py` — Lineage model and collection
- `tests/test_context_logging.py` — Offline store logging
- `tests/test_context_replay.py` — Replay API

**Integration tests:**
- `tests/integration/test_context_accountability.py`
  - Full round-trip: define features → assemble context → log → replay
  - Verify lineage accuracy
  - Verify content matches exactly

**End-to-end tests:**
- `tests/e2e/test_context_api.py`
  - REST API for context retrieval
  - CLI commands

**Performance tests:**
- `tests/performance/test_context_overhead.py`
  - Measure latency impact of logging
  - Target: <5ms overhead

**Acceptance criteria:**
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] All e2e tests pass
- [ ] Performance overhead <5ms
- [ ] Code coverage >80%

---

### 1.9 Documentation for v1.4

**New docs:**

1. `docs/context-accountability.md` — Full guide to context replay and lineage
2. `docs/api-reference.md` — Update with new endpoints
3. `docs/changelog.md` — v1.4 release notes

**Blog posts:**

1. `docs/blog/context-replay.md` — "What Did Your AI Know? Introducing Context Replay"
   - Why context replay matters for AI accountability
   - How to use `get_context_at()`
   - Compliance and audit use cases

2. `docs/blog/ai-audit-trail.md` — "Building an Audit Trail for AI Decisions"
   - Regulatory landscape (OCC, SEC, FDA)
   - How lineage enables compliance
   - Meridian's approach

**README updates:**
- Add "Context Accountability" to key capabilities
- Update code example to show lineage

**Acceptance criteria:**
- [ ] All new docs written
- [ ] Blog posts published
- [ ] README updated
- [ ] Changelog updated

---

### 1.10 v1.4 Release Checklist

- [ ] All code complete
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Blog posts ready
- [ ] Version bumped to 1.4.0 in:
  - [ ] `pyproject.toml`
  - [ ] `src/meridian/__init__.py`
  - [ ] `tests/test_version.py`
- [ ] Changelog updated
- [ ] Git tag v1.4.0 created
- [ ] PyPI release published
- [ ] Announcement prepared

---

## Phase 2: Freshness SLAs (v1.5)

### Overview

Add freshness guarantees to context assembly with clear degradation modes.

```python
@context(store, max_tokens=4000, freshness_sla="5m")
async def build_prompt(user_id: str, query: str):
    tier = await store.get_feature("user_tier", user_id)  # Must be <5m old
    docs = await search_docs(query)
    return [...]

# If any feature exceeds SLA:
ctx = await build_prompt("user_123", "query")
ctx.meta["freshness_status"]  # "degraded"
ctx.meta["freshness_violations"]  # [{"feature": "user_tier", "age_ms": 360000, "sla_ms": 300000}]
```

---

### 2.1 Freshness SLA Parameter

**Goal:** Add `freshness_sla` parameter to `@context` decorator.

**Implementation:**

```python
# src/meridian/context.py

def context(
    store: "FeatureStore",
    max_tokens: int = 4000,
    freshness_sla: Optional[str] = None,  # e.g., "5m", "1h", "30s"
    cache_ttl: Optional[str] = None,
):
    """
    Args:
        freshness_sla: Maximum age for features used in this context.
            If any feature exceeds this age, freshness_status becomes "degraded".
            Format: "30s", "5m", "1h", "1d"
    """
```

**Files to modify:**
- `src/meridian/context.py` — Add parameter and parsing
- `src/meridian/utils/time.py` — Add SLA parsing utilities

**Tests:**
- Unit: SLA parsing ("5m" → 300000ms)
- Unit: SLA validation (reject invalid formats)

**Acceptance criteria:**
- [ ] `freshness_sla` parameter accepted
- [ ] Various formats supported (s, m, h, d)
- [ ] Invalid formats raise clear errors

---

### 2.2 Freshness Checking

**Goal:** Check feature freshness against SLA during assembly.

**Implementation:**

```python
# During assembly, for each feature:
feature_age_ms = (now - feature_timestamp).total_seconds() * 1000
if freshness_sla_ms and feature_age_ms > freshness_sla_ms:
    violations.append({
        "feature": feature_name,
        "age_ms": feature_age_ms,
        "sla_ms": freshness_sla_ms
    })
```

**Files to modify:**
- `src/meridian/context.py` — Add freshness checking to assembly

**Tests:**
- Unit: Fresh features pass
- Unit: Stale features recorded as violations
- Integration: Freshness checked for all features

**Acceptance criteria:**
- [ ] Freshness checked for all features
- [ ] Violations recorded with details
- [ ] Check adds minimal latency

---

### 2.3 Degraded Mode Handling

**Goal:** Clear indication when SLA is breached.

**Behavior:**
- Assembly still succeeds (don't fail the request)
- `freshness_status` = "degraded"
- `freshness_violations` lists all breaches
- Log warning for observability

**Implementation:**

```python
# src/meridian/context.py

if violations:
    ctx.meta["freshness_status"] = "degraded"
    ctx.meta["freshness_violations"] = violations
    logger.warning(
        "Context freshness SLA breached",
        context_id=ctx.id,
        violations=violations
    )
else:
    ctx.meta["freshness_status"] = "guaranteed"
```

**Files to modify:**
- `src/meridian/context.py` — Add degraded mode logic

**Tests:**
- Unit: Status is "guaranteed" when all fresh
- Unit: Status is "degraded" when any stale
- Unit: Violations list populated correctly
- Integration: Degraded contexts still usable

**Acceptance criteria:**
- [ ] Degraded mode does not fail assembly
- [ ] Status clearly indicates freshness
- [ ] Violations provide actionable detail

---

### 2.4 Freshness Metrics

**Goal:** Expose freshness metrics for monitoring.

**Metrics:**

```python
# Prometheus metrics
meridian_context_freshness_status_total{status="guaranteed|degraded"}
meridian_context_freshness_violations_total{feature="feature_name"}
meridian_context_stalest_feature_seconds{context_function="build_prompt"}
```

**Files to modify:**
- `src/meridian/observability.py` — Add freshness metrics
- `src/meridian/context.py` — Record metrics during assembly

**Tests:**
- Unit: Metrics increment correctly
- Integration: Metrics visible at /metrics endpoint

**Acceptance criteria:**
- [ ] Freshness metrics exposed
- [ ] Metrics labeled appropriately
- [ ] Grafana dashboard examples provided

---

### 2.5 Strict Mode (Optional)

**Goal:** Option to fail assembly if SLA breached.

```python
@context(store, max_tokens=4000, freshness_sla="5m", freshness_strict=True)
async def critical_context(...):
    # Raises FreshnessSLAError if any feature exceeds SLA
```

**Implementation:**

```python
if violations and freshness_strict:
    raise FreshnessSLAError(
        f"Freshness SLA breached for {len(violations)} features",
        violations=violations
    )
```

**Files to modify:**
- `src/meridian/context.py` — Add strict mode parameter
- `src/meridian/exceptions.py` — Add FreshnessSLAError

**Tests:**
- Unit: Strict mode raises on violation
- Unit: Non-strict mode continues on violation

**Acceptance criteria:**
- [ ] `freshness_strict` parameter works
- [ ] Clear exception with violation details
- [ ] Default is non-strict (graceful degradation)

---

### 2.6 Testing Strategy for v1.5

**Unit tests:**
- `tests/test_freshness_sla.py` — SLA parsing and checking
- `tests/test_freshness_degraded.py` — Degraded mode behavior
- `tests/test_freshness_metrics.py` — Metric recording
- `tests/test_freshness_strict.py` — Strict mode

**Integration tests:**
- `tests/integration/test_freshness_e2e.py`
  - End-to-end with stale features
  - Verify degraded mode propagates

**Performance tests:**
- `tests/performance/test_freshness_overhead.py`
  - Measure latency impact of freshness checking
  - Target: <1ms overhead

**Acceptance criteria:**
- [ ] All tests pass
- [ ] Performance overhead <1ms
- [ ] Code coverage >80%

---

### 2.7 Documentation for v1.5

**New docs:**

1. `docs/freshness-sla.md` — Full guide to freshness guarantees
2. Update `docs/context-assembly.md` — Add freshness section
3. Update `docs/observability.md` — Add freshness metrics

**Blog posts:**

1. `docs/blog/freshness-guarantees.md` — "Freshness SLAs: When Your AI Needs Fresh Data"
   - Why freshness matters
   - How to configure SLAs
   - Monitoring degraded contexts

**Acceptance criteria:**
- [ ] All docs updated
- [ ] Blog post published
- [ ] Examples include freshness_sla usage

---

### 2.8 v1.5 Release Checklist

- [ ] All code complete
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Blog posts ready
- [ ] Version bumped to 1.5.0
- [ ] Changelog updated
- [ ] Git tag v1.5.0 created
- [ ] PyPI release published
- [ ] Announcement prepared

---

## Implementation Timeline

### v1.4 (Context Accountability)

| Week | Focus | Deliverables |
|------|-------|--------------|
| 1 | Foundation | Context ID, Lineage model, Storage schema |
| 2 | Logging | Context logging to DuckDB and Postgres |
| 3 | Replay | `get_context_at()` API, REST endpoints |
| 4 | Lineage Collection | Assembly tracking, full lineage capture |
| 5 | Polish | CLI, documentation, blog posts |
| 6 | Release | Testing, release prep, publish |

### v1.5 (Freshness SLAs)

| Week | Focus | Deliverables |
|------|-------|--------------|
| 1 | SLA Parameter | Parsing, validation, integration |
| 2 | Checking | Freshness checking, degraded mode |
| 3 | Observability | Metrics, strict mode |
| 4 | Release | Testing, docs, publish |

---

## Success Metrics

### v1.4

- [ ] 100% of context assemblies have lineage
- [ ] Context replay works for 100% of logged contexts
- [ ] <5ms latency overhead for logging
- [ ] 3+ enterprises interested in accountability features

### v1.5

- [ ] Freshness SLAs configurable on all contexts
- [ ] Degraded mode clearly visible in observability
- [ ] <1ms latency overhead for freshness checking
- [ ] At least 1 customer using freshness SLAs in production

---

## Migration Notes

### v1.3 → v1.4

- **Breaking changes:** None
- **New tables:** `context_log` (auto-created on first use)
- **API additions:** `/context/{id}`, `/contexts`
- **Deprecations:** None

### v1.4 → v1.5

- **Breaking changes:** None
- **New parameters:** `freshness_sla`, `freshness_strict`
- **New metrics:** `meridian_context_freshness_*`
- **Deprecations:** None

---

## Open Questions

1. **Retention policy:** How long to keep context logs? Configurable? Default 90 days?
2. **Compression:** Compress content in storage for large contexts?
3. **Sampling:** Option to log only a percentage of contexts for high-volume deployments?
4. **Privacy:** Redaction options for sensitive content in lineage?

---

## Appendix: File Changes Summary

### v1.4 New Files
- `src/meridian/models.py` (or extend existing)
- `tests/test_context_id.py`
- `tests/test_lineage.py`
- `tests/test_context_logging.py`
- `tests/test_context_replay.py`
- `tests/integration/test_context_accountability.py`
- `tests/e2e/test_context_api.py`
- `tests/performance/test_context_overhead.py`
- `docs/context-accountability.md`
- `docs/blog/context-replay.md`
- `docs/blog/ai-audit-trail.md`

### v1.4 Modified Files
- `src/meridian/context.py`
- `src/meridian/core.py`
- `src/meridian/retrieval.py`
- `src/meridian/store.py`
- `src/meridian/api.py`
- `src/meridian/cli.py`
- `docs/index.md`
- `docs/changelog.md`
- `README.md`

### v1.5 New Files
- `tests/test_freshness_sla.py`
- `tests/test_freshness_degraded.py`
- `tests/test_freshness_metrics.py`
- `tests/test_freshness_strict.py`
- `tests/integration/test_freshness_e2e.py`
- `tests/performance/test_freshness_overhead.py`
- `docs/freshness-sla.md`
- `docs/blog/freshness-guarantees.md`

### v1.5 Modified Files
- `src/meridian/context.py`
- `src/meridian/observability.py`
- `src/meridian/exceptions.py`
- `docs/context-assembly.md`
- `docs/observability.md`
- `docs/changelog.md`
