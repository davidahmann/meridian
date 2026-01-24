# Fabra quickstart (concise)

## Install
```bash
pip install fabra-ai
```

## Run demo
```bash
fabra demo
```

This starts a local server, makes a test request, and prints a `context_id` (`ctx_<uuid7>`).

## Inspect / verify / diff
```bash
fabra context show <context_id>
fabra context verify <context_id>
fabra context diff <context_id_A> <context_id_B>
```

## Where records are stored (default)
- DuckDB file: `~/.fabra/fabra.duckdb` (override with `FABRA_DUCKDB_PATH`)
