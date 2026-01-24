# Fabra CLI (high-signal subset)

## Demo + local server
- `fabra demo` → prints a working `context_id`
- `fabra serve <file.py>` → starts FastAPI server for your feature/context definitions

## Incident workflow
- `fabra context show <context_id>` → inspect a record (CRS-001 preferred; legacy fallback when needed)
- `fabra context verify <context_id>` → verify CRS-001 hashes
- `fabra context diff <a> <b>` → compare two contexts
- `fabra context diff <a> <b> --local` → diff two CRS-001 receipts locally from DuckDB
- `fabra context export <id> --bundle -o incident_bundle.zip` → export JSON + manifest for tickets/audits

## Diagnostics
- `fabra doctor` → local diagnostics and configuration hints
