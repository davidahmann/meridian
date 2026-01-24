# Security & privacy (operational facts)

## Sensitive data guidance
Context Records are like production logs: do not include secrets (API keys, tokens, passwords) and be intentional about PII.

## Content inclusion (privacy mode)
- Default: raw `content` is persisted in CRS-001 records.
- Disable content storage: `FABRA_RECORD_INCLUDE_CONTENT=0`
  - Effect: persisted records store an empty string for `content` while still capturing lineage + integrity hashes for remaining fields.

## Evidence persistence modes
- `FABRA_EVIDENCE_MODE=best_effort`:
  - Context assembly can succeed even if CRS-001 persistence fails.
  - Use when you prefer availability over strict audit guarantees.
- `FABRA_EVIDENCE_MODE=required`:
  - Requests fail if CRS-001 persistence fails (no `context_id` returned).
  - Default in `FABRA_ENV=production`.

## API access
- If `FABRA_API_KEY` is set, Fabra expects `X-API-Key: ...` on requests.
- If no key is configured, the server allows all requests (dev mode).
