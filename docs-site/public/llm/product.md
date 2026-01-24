# Fabra (product context)

## One-line
Fabra turns an AI request into **evidence**: a durable, verifiable **Context Record (CRS-001)** you can replay, diff, and verify during incidents.

## What Fabra is
- A Python-first **Context Record** system (“what the model saw”) with lineage and integrity.
- A feature/context serving layer (FastAPI) to serve features and assembled context over HTTP.

## What Fabra is not
- Not an agent framework.
- Not a monitoring dashboard.
- Not a no-code prompt builder.

## Core entities (canonical names)
- **Context Record**: immutable record of assembled context + lineage + integrity metadata.
- **CRS-001**: the Context Record schema/version used for receipts.
- **context_id**: identifier like `ctx_<uuid7>` returned for each recorded context.
- **record_hash**: `sha256:...` content-address for a CRS-001 record (durable reference).
- **content_hash**: `sha256:...` hash of the raw `content` field (when content is included).

## Defaults (development)
- Offline store: DuckDB at `~/.fabra/fabra.duckdb` (override with `FABRA_DUCKDB_PATH`).
- Online store: in-memory (or Redis if `FABRA_REDIS_URL` is set).
- Evidence mode: `best_effort` (in prod: `required` unless overridden).

## Evidence modes
- `FABRA_EVIDENCE_MODE=best_effort`: request succeeds even if persistence fails; response indicates whether evidence persisted.
- `FABRA_EVIDENCE_MODE=required`: request fails if CRS-001 persistence fails (no “fake receipts”).

## Privacy mode
- `FABRA_RECORD_INCLUDE_CONTENT=0` stores an empty string for `content` while still persisting lineage and integrity for the remaining fields.
