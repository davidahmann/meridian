---
title: "How It Works"
description: "End-to-end architecture: how Fabra turns requests into durable, verifiable Context Records (CRS-001), and how features/events/workers fit together."
keywords: architecture, how it works, context records, crs-001, receipts, replay, diff, verify, events, worker
---

# How It Works

Fabra’s job is to turn an AI request into **evidence** you can use during an incident.

The unit of evidence is a `context_id`. Under incident pressure, the workflow is:

```bash
fabra context show <context_id>
fabra context verify <context_id>
fabra context diff <a> <b>
```

## Components

### 1) Your code (authoring)
You define a `FeatureStore` and register:
- **features** (values served over HTTP)
- **contexts** (assembled “what the model saw”, with lineage and integrity)

Fabra loads your Python file and discovers the `FeatureStore` by importing it.

### 2) Fabra server (FastAPI)
When you run:

```bash
fabra serve <file.py>
```

Fabra starts a FastAPI app that exposes:

**Features**
- `GET /features/{feature_name}?entity_id=...` → `{"value","freshness_ms","served_from"}`
- `POST /v1/features` and `POST /v1/features/batch` for batch reads

**Context assembly**
- `POST /v1/context/{context_name}` → `{"id","content","meta","lineage"}`

**Evidence retrieval**
- `GET /v1/record/{context_id}` → CRS-001 **Context Record** (verifiable receipt)
- `GET /v1/context/{context_id}` → legacy context view (best-effort fallback)

**Replay / diff**
- `POST /v1/context/{context_id}/replay?timestamp=...` (time-travel feature reads when historical data is available)
- `GET /v1/context/diff/{a}/{b}` (legacy context diff endpoint)

### 3) Offline store (durable evidence)
The offline store is where Fabra keeps durable artifacts for replay/audit.

Defaults:
- **Dev**: DuckDB at `~/.fabra/fabra.duckdb` (override with `FABRA_DUCKDB_PATH`)
- **Prod**: Postgres (set `FABRA_ENV=production` and `FABRA_POSTGRES_URL`)

Fabra persists two related artifacts:
- **CRS-001 Context Record**: immutable, verifiable (preferred)
- **Legacy context log**: used for listing/legacy compatibility

### 4) Online store (serving + freshness metadata)
The online store is what the server uses to serve cached feature values quickly.

Defaults:
- **Dev**: in-memory
- **Optional**: Redis (set `FABRA_REDIS_URL`)

Online stores wrap feature values with an internal `as_of` timestamp so Fabra can compute `freshness_ms` at serve-time.

### 5) Events + worker (optional)
For event-driven features:

1. Your app sends an event:
   - `POST /v1/ingest/{event_type}?entity_id=...`
2. Fabra publishes to Redis Streams:
   - `fabra:events:{event_type}`
   - `fabra:events:all` (shared stream)
3. A worker consumes streams and updates triggered features:
   - `fabra worker <file.py>`

See `docs/events-and-workers.md` for exact flags and defaults.

## Receipts: legacy vs CRS-001

### CRS-001 Context Record (preferred)
CRS-001 is the durable, verifiable receipt. It contains:
- `content` (“what the model saw”)
- structured fields (inputs/lineage/decisions)
- `integrity.content_hash` and `integrity.record_hash`

Use:
- `fabra context verify <id>` to verify hashes
- `fabra context export <id> --bundle` to generate a ticket attachment

### Legacy context (fallback)
Legacy contexts are a best-effort view retrieved via `GET /v1/context/{id}`.
They exist for compatibility and debugging, but CRS-001 is the audit-grade artifact.

## Evidence modes (no fake receipts)

Fabra can enforce that it never returns a `context_id` unless a CRS-001 record was persisted successfully:

- `FABRA_EVIDENCE_MODE=best_effort` (development default): request succeeds, `meta.evidence_persisted` indicates whether the receipt was persisted.
- `FABRA_EVIDENCE_MODE=required` (production default): if persistence fails, the request fails (no “fake” receipt).

## Where the “aha” lands

- **Incident response**: paste `context_id` into the ticket; run `show/verify/diff/export`.
- **AI engineers**: add receipts with minimal code (adapters/exporters) and still get verifiable artifacts.
- **ML engineers**: serve features with explicit freshness numbers, and optionally materialize via events/workers.
