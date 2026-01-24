# Comparisons (high-signal positioning)

## Fabra vs “prompt logging”
- Prompt logs are not a verifiable artifact: they’re hard to diff, easy to lose, and usually omit lineage (features/retrieval/freshness decisions).
- Fabra produces a **CRS-001 Context Record** with `context_id` + hashes so you can verify and diff what changed.

## Fabra vs agent frameworks
- Agent frameworks orchestrate calls and tool use.
- Fabra focuses on **evidence**: capturing what the model saw (and why) as a durable record for incident response and audits.

## Fabra vs Feast (feature store)
- Feast is a general-purpose feature store with heavier infra patterns.
- Fabra defaults to a minimal local stack (DuckDB + in-memory) and can scale to Postgres/Redis; it also captures inference-time evidence (Context Records).
