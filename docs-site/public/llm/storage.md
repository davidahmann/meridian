# Storage modes (offline + online)

Fabra uses two stores:
- **Offline store**: durable evidence + replay/audit history.
- **Online store**: serving cache for fast feature reads (and context cache).

## Development defaults
- Offline: DuckDB at `~/.fabra/fabra.duckdb`
  - Override: `FABRA_DUCKDB_PATH=/path/to/file.duckdb` (or `:memory:` for in-memory)
- Online: in-memory
  - Optional Redis: set `FABRA_REDIS_URL=redis://...`

## Production defaults
- Set `FABRA_ENV=production`.
- Evidence mode default becomes `required` (unless `FABRA_EVIDENCE_MODE` overrides it).
- Offline: Postgres via `FABRA_POSTGRES_URL=postgresql://...`
- Online: Redis via `FABRA_REDIS_URL=redis://...`
