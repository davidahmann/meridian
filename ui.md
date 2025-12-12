# WebUI Production Readiness Plan

## Status: COMPLETED

All phases have been implemented and tested. See summary at end of document.

---

## Executive Summary

The Fabra WebUI currently serves **demo/mock data** by default, which can mislead users about production capabilities. This document outlines the gaps between our README claims and actual implementation, plus a remediation plan with required tests.

---

## Current Architecture

```
Next.js Frontend (port 3001)
        ↓ HTTP
FastAPI ui_server.py (port 8502)
        ↓ load_module()
User's Python Module (e.g., demo_context.py)
        ↓
FeatureStore instance
        ↓
┌─────────────────────────────────────┐
│ Data Stores (per FABRA_ENV)         │
├─────────────────────────────────────┤
│ development: DuckDB + InMemory      │
│ production:  Postgres + Redis       │
└─────────────────────────────────────┘
```

---

## Gap Analysis

### Gap 1: Mock Data in Demo Examples

**Claim**: "Vector search with pgvector"
**Reality**: `demo_context.py` uses keyword matching against `MOCK_DOCS` dictionary

**Location**: `examples/demo_context.py:89-110`, `examples/demo_context.py:113-161`

**Impact**: Users testing the demo don't see real vector search behavior

### Gap 2: InMemoryOnlineStore Data Loss

**Claim**: "Production-ready infrastructure"
**Reality**: Default demo uses `InMemoryOnlineStore` - all data lost on restart

**Location**: `examples/demo_context.py:43-46`

**Impact**: Users may think their features are persisted when they're not

### Gap 3: No Authentication on WebUI Server

**Claim**: N/A (not explicitly claimed, but implied for production)
**Reality**: `ui_server.py` has no auth - anyone can access feature values

**Location**: `src/fabra/ui_server.py` (entire file)

**Impact**: Security vulnerability if exposed publicly

### Gap 4: Hash-Based Deterministic Features

**Claim**: "Real-time feature serving"
**Reality**: Demo features use `hash(user_id)` for deterministic fake values

**Location**: `examples/demo_context.py:59-82`

**Impact**: Demo doesn't demonstrate actual feature computation from data sources

### Gap 5: No "Demo vs Production" Warning

**Claim**: N/A
**Reality**: No visual indicator in UI that data is mock/demo

**Location**: UI frontend + `ui_server.py`

**Impact**: Users can't distinguish demo mode from production mode

### Gap 6: Missing Context Record Display in WebUI

**Claim**: "Immutable Context Records with cryptographic integrity"
**Reality**: WebUI shows context results but not full CRS-001 Context Records

**Location**: `src/fabra/ui_server.py:328-414`

**Impact**: Core CRS-001 value proposition not visible in UI

---

## Remediation Plan

### Phase 1: Transparency & Documentation (Priority: HIGH)

#### Task 1.1: Add Demo Mode Indicator to API Response

Add `is_demo_mode` field to `/api/store` response.

**File**: `src/fabra/ui_server.py`

```python
class StoreInfo(BaseModel):
    # ... existing fields ...
    is_demo_mode: bool  # NEW
    demo_warning: Optional[str] = None  # NEW
```

**Tests Required**:
```python
# tests/test_ui_server.py

def test_store_info_includes_demo_mode_flag():
    """StoreInfo response includes is_demo_mode field."""
    # Load demo_context.py
    # Assert response.is_demo_mode == True
    # Assert response.demo_warning contains "mock data"

def test_store_info_production_mode_false():
    """Production store shows is_demo_mode=False."""
    # Load a module with real Postgres/Redis stores
    # Assert response.is_demo_mode == False
    # Assert response.demo_warning is None
```

#### Task 1.2: Add Production Mode Detection

**File**: `src/fabra/ui_server.py`

```python
def _is_demo_mode(store: FeatureStore) -> bool:
    """Detect if store is using in-memory/demo backends."""
    from fabra.store import InMemoryOnlineStore, DuckDBOfflineStore

    is_inmemory_online = isinstance(store.online_store, InMemoryOnlineStore)
    is_duckdb_offline = isinstance(store.offline_store, DuckDBOfflineStore)

    return is_inmemory_online or is_duckdb_offline
```

**Tests Required**:
```python
# tests/test_ui_server.py

def test_is_demo_mode_inmemory_online():
    """InMemoryOnlineStore is detected as demo mode."""
    store = FeatureStore(online_store=InMemoryOnlineStore())
    assert _is_demo_mode(store) == True

def test_is_demo_mode_redis_online():
    """RedisOnlineStore is NOT demo mode."""
    store = FeatureStore(online_store=RedisOnlineStore(...))
    assert _is_demo_mode(store) == False

def test_is_demo_mode_duckdb_offline():
    """DuckDBOfflineStore is detected as demo mode."""
    store = FeatureStore(offline_store=DuckDBOfflineStore())
    assert _is_demo_mode(store) == True
```

#### Task 1.3: Update Documentation with Demo vs Production Section

**File**: `docs/webui.md` (NEW)

Content to include:
- Clear explanation of demo mode vs production mode
- How to switch between modes
- What data is mock vs real
- Warning about InMemoryOnlineStore data loss

**Tests Required**:
```python
# tests/test_docs.py

def test_webui_docs_exist():
    """WebUI documentation exists."""
    assert Path("docs/webui.md").exists()

def test_webui_docs_contains_demo_warning():
    """WebUI docs explain demo vs production mode."""
    content = Path("docs/webui.md").read_text()
    assert "demo mode" in content.lower()
    assert "InMemoryOnlineStore" in content
```

---

### Phase 2: Real Vector Search Example (Priority: HIGH)

#### Task 2.1: Create Production-Ready Example

**File**: `examples/production_context.py` (NEW)

A new example that:
- Uses environment variables for API keys
- Connects to real pgvector (if available) or gracefully degrades
- Shows actual embedding and retrieval
- Documents requirements clearly

**Tests Required**:
```python
# tests/test_examples.py

def test_production_example_loads():
    """production_context.py loads without syntax errors."""
    import examples.production_context

def test_production_example_has_real_retriever():
    """production_context.py uses index= parameter for real vector search."""
    content = Path("examples/production_context.py").read_text()
    assert "@retriever(index=" in content
    assert "MOCK_DOCS" not in content

def test_production_example_env_vars_documented():
    """production_context.py documents required env vars."""
    content = Path("examples/production_context.py").read_text()
    assert "OPENAI_API_KEY" in content or "FABRA_ENV" in content
```

#### Task 2.2: Add Retriever Type Detection

**File**: `src/fabra/ui_server.py`

Enhance retriever info to show if it's mock vs real:

```python
class Retriever(BaseModel):
    name: str
    backend: str
    cache_ttl: str
    is_mock: bool  # NEW - True if no index= parameter
    index_name: Optional[str] = None  # NEW
```

**Tests Required**:
```python
# tests/test_ui_server.py

def test_retriever_info_shows_mock_status():
    """Retriever response shows is_mock=True for mock retrievers."""
    # Load demo_context.py
    # Find demo_docs retriever
    # Assert retriever.is_mock == True

def test_retriever_info_shows_index_name():
    """Retriever response shows index_name for real retrievers."""
    # Load production example
    # Assert retriever.index_name is not None
    # Assert retriever.is_mock == False
```

---

### Phase 3: Context Record Display (Priority: MEDIUM)

#### Task 3.1: Add Full Context Record to API Response

**File**: `src/fabra/ui_server.py`

Expose the full CRS-001 Context Record in the response:

```python
class ContextResult(BaseModel):
    id: str
    items: List[ContextResultItem]
    meta: ContextResultMeta
    lineage: Optional[ContextLineageResponse] = None
    record: Optional[ContextRecordResponse] = None  # NEW - Full CRS-001 record

class ContextRecordResponse(BaseModel):
    context_id: str
    version: str  # "CRS-001"
    integrity: IntegrityResponse
    # ... other CRS-001 fields
```

**Tests Required**:
```python
# tests/test_ui_server.py

def test_context_result_includes_record():
    """Context assembly returns full CRS-001 record."""
    response = await assemble_context("chat_context", {"user_id": "u1", "query": "test"})
    assert response.record is not None
    assert response.record.version == "CRS-001"
    assert response.record.integrity.content_hash.startswith("sha256:")

def test_context_record_has_cryptographic_integrity():
    """Context record includes verifiable integrity fields."""
    response = await assemble_context(...)
    assert response.record.integrity.content_hash is not None
    assert response.record.integrity.lineage_hash is not None
```

#### Task 3.2: Add Context Record Verification Endpoint

**File**: `src/fabra/ui_server.py`

```python
@app.get("/api/context/{context_id}/verify")
async def verify_context(context_id: str) -> VerificationResult:
    """Verify cryptographic integrity of a Context Record."""
    # Retrieve stored record
    # Recompute hashes
    # Compare and return result
```

**Tests Required**:
```python
# tests/test_ui_server.py

def test_verify_context_valid():
    """Verify endpoint confirms valid context record."""
    # Create context
    ctx_id = response.id
    # Verify
    verify_result = await verify_context(ctx_id)
    assert verify_result.is_valid == True

def test_verify_context_detects_tampering():
    """Verify endpoint detects tampered records."""
    # Create context
    # Manually corrupt stored record
    # Verify
    verify_result = await verify_context(ctx_id)
    assert verify_result.is_valid == False
    assert "tampered" in verify_result.error.lower()
```

---

### Phase 4: Authentication (Priority: MEDIUM)

#### Task 4.1: Add Optional API Key Authentication

**File**: `src/fabra/ui_server.py`

```python
from fastapi import Depends, Security
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_api_key(api_key: str = Security(API_KEY_HEADER)) -> Optional[str]:
    expected = os.environ.get("FABRA_UI_API_KEY")
    if expected and api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key
```

**Tests Required**:
```python
# tests/test_ui_server.py

def test_no_auth_when_env_not_set():
    """API works without auth when FABRA_UI_API_KEY not set."""
    # Unset env var
    response = client.get("/api/store")
    assert response.status_code == 200

def test_auth_required_when_env_set():
    """API requires auth when FABRA_UI_API_KEY is set."""
    os.environ["FABRA_UI_API_KEY"] = "test-key"  # pragma: allowlist secret
    response = client.get("/api/store")
    assert response.status_code == 401

def test_auth_succeeds_with_valid_key():
    """API works with valid API key."""
    os.environ["FABRA_UI_API_KEY"] = "test-key"  # pragma: allowlist secret
    response = client.get("/api/store", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200

def test_auth_fails_with_invalid_key():
    """API rejects invalid API key."""
    os.environ["FABRA_UI_API_KEY"] = "test-key"  # pragma: allowlist secret
    response = client.get("/api/store", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401
```

---

### Phase 5: Data Persistence Warning (Priority: LOW)

#### Task 5.1: Add Startup Warning for InMemoryOnlineStore

**File**: `src/fabra/ui_server.py`

```python
def load_module(file_path: str) -> None:
    # ... existing code ...

    if isinstance(store.online_store, InMemoryOnlineStore):
        import warnings
        warnings.warn(
            "Using InMemoryOnlineStore - data will be lost on restart. "
            "Set FABRA_ENV=production for persistent storage.",
            UserWarning
        )
```

**Tests Required**:
```python
# tests/test_ui_server.py

def test_inmemory_warning_on_load():
    """Loading InMemoryOnlineStore module emits warning."""
    with pytest.warns(UserWarning, match="InMemoryOnlineStore"):
        load_module("examples/demo_context.py")

def test_no_warning_for_persistent_store():
    """Loading persistent store module does not emit warning."""
    with warnings.catch_warnings(record=True) as w:
        load_module("examples/production_context.py")
        # Filter for our specific warning
        inmem_warnings = [x for x in w if "InMemoryOnlineStore" in str(x.message)]
        assert len(inmem_warnings) == 0
```

---

## Test File Structure

```
tests/
├── test_ui_server.py          # All ui_server.py tests
│   ├── test_store_info_*      # Phase 1 tests
│   ├── test_is_demo_mode_*    # Phase 1 tests
│   ├── test_retriever_*       # Phase 2 tests
│   ├── test_context_*         # Phase 3 tests
│   ├── test_auth_*            # Phase 4 tests
│   └── test_inmemory_*        # Phase 5 tests
├── test_examples.py           # Example file validation
│   ├── test_production_example_*
│   └── test_demo_example_*
└── test_docs.py               # Documentation validation
    └── test_webui_docs_*
```

---

## Implementation Order

| Phase | Priority | Effort | Dependencies |
|-------|----------|--------|--------------|
| Phase 1: Transparency | HIGH | 2-3 hours | None |
| Phase 2: Real Vector Example | HIGH | 3-4 hours | Phase 1 |
| Phase 3: Context Records | MEDIUM | 4-5 hours | CRS-001 (done) |
| Phase 4: Authentication | MEDIUM | 2-3 hours | None |
| Phase 5: Persistence Warning | LOW | 1 hour | None |

**Recommended Order**: 1 → 5 → 2 → 4 → 3

---

## Success Criteria

- [x] All tests pass (`uv run pytest tests/test_ui_server.py -v`) - **36 tests passing**
- [x] Demo mode clearly indicated in UI - **`is_demo_mode` and `demo_warning` in API response**
- [x] Production example with real vector search exists - **`examples/production_context.py`**
- [x] Context Records visible in API response - **`/api/context/{id}/record` endpoint**
- [x] Optional authentication available - **`FABRA_UI_API_KEY` env var + `X-API-Key` header**
- [x] Startup warning for InMemoryOnlineStore - **UserWarning on module load**
- [x] Documentation updated with demo vs production guidance - **`docs/webui.md`**

---

## Implementation Summary

All phases completed on 2025-12-12. Documentation updated on 2025-12-12:

### Files Created
- `tests/test_ui_server.py` - 36 comprehensive tests
- `examples/production_context.py` - Production-ready example with real pgvector
- `docs/webui.md` - WebUI documentation with demo vs production guide

### Files Updated (Documentation)

- `docs/index.md` - Added WebUI link to "Tools" section and linked "Visual UI" reference

### Files Modified
- `src/fabra/ui_server.py`:
  - Added `_is_demo_mode()` and `_get_demo_warning()` functions
  - Added `_get_api_key()` for optional authentication
  - Updated `StoreInfo` model with `is_demo_mode`, `demo_warning`, `offline_store_type`
  - Updated `Retriever` model with `is_mock`, `index_name`
  - Added `ContextRecordResponse`, `VerificationResult` models
  - Added `/api/context/{id}/record` endpoint
  - Added `/api/context/{id}/verify` endpoint
  - Added startup warning for InMemoryOnlineStore

### Test Results
```
373 passed, 1 skipped, 18 deselected, 6 warnings in 15.62s
```

---

## Notes

- This plan focuses on **transparency** first - users should always know when they're seeing demo data
- The core CRS-001 infrastructure is production-ready; these are UI/demo polish items
- Authentication should remain optional to not break existing integrations
- All changes maintain backwards compatibility
