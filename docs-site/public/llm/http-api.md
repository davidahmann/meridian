# Fabra HTTP API (high-signal subset)

Base URL (local dev): `http://127.0.0.1:8000`

## Features
- `GET /v1/features/{feature_name}?entity_id=...` → `{"value","freshness_ms","served_from"}`
- `POST /v1/features` → fetch multiple features for one entity
- `POST /v1/features/batch` → fetch features for many entity IDs

## Context assembly
- `POST /v1/context/{context_name}` → assembled context with `id` (context_id), `content`, `meta`, `lineage`

## Evidence retrieval (CRS-001)
- `GET /v1/record/{record_ref}` where `{record_ref}` is:
  - `ctx_<uuid7>` (or UUID without `ctx_` prefix in some clients)
  - `sha256:<record_hash>` for content-addressed lookup

## Replay (when historical data is available)
- `POST /v1/context/{context_id}/replay?timestamp=...` → re-executes context using time-travel reads
