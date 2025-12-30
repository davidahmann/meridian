<div align="center">
  <h1>Fabra</h1>
  <p><strong>Context Records for LLM incidents.</strong></p>
  <p>Capture what the model saw as a durable artifact you can replay, verify, and diff.<br/>record -> replay -> diff</p>

  <p>
    <a href="https://pypi.org/project/fabra-ai/"><img src="https://img.shields.io/pypi/v/fabra-ai?color=blue&label=pypi" alt="PyPI version" /></a>
    <a href="https://github.com/davidahmann/fabra/blob/main/LICENSE"><img src="https://img.shields.io/github/license/davidahmann/fabra?color=green" alt="License" /></a>
    <img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python Version" />
  </p>
</div>

---

## When An LLM Incident Happens

- Support shares a screenshot.
- Engineering tries to reconstruct prompts, retrieval, features, and runtime state.
- Nobody can answer, precisely and repeatably: what did it see, what changed, why did it answer that way?

Fabra's unit of evidence is a `context_id` (UUID or `ctx_<UUID>`). For long-lived tickets and audits, also log the CRS-001 `record_hash` (`sha256:...`) as the durable content address. Paste either into the ticket, then:

```bash
fabra context show <context_id>
fabra context verify <context_id>
fabra context diff <context_id_A> <context_id_B>
```

You can also reference a CRS-001 record by its `record_hash` (e.g. `sha256:...`) for content-addressed lookups:

```bash
fabra context show sha256:<record_hash>
fabra context verify sha256:<record_hash>
```

---

## Quickstart (No Keys, No Docker)

```bash
pip install fabra-ai
fabra demo
```

`fabra demo` starts a local server, makes a test request, and prints a working `context_id` plus the next commands to run.

By default, Context Records are stored durably in DuckDB at `~/.fabra/fabra.duckdb` (override with `FABRA_DUCKDB_PATH`).

## How It Works (One Screen)

- You define features and `@context` functions in a Python file.
- `fabra serve <file.py>` loads that file, starts a FastAPI server, and serves:
  - `GET /v1/features/<name>` for feature values (with `freshness_ms`)
  - `POST /v1/context/<name>` for assembled context + `context_id` (and `record_hash` / `content_hash` when CRS-001 storage is enabled)
- Fabra persists a CRS-001 Context Record (receipt) and exposes it at `GET /v1/record/<record_ref>` where `<record_ref>` is `ctx_...` or `sha256:...`.
- Under incident pressure you run `fabra context show/verify/diff` from the `context_id`.

Details: `docs/how-it-works.md`

For voice/real-time agents, you can also pass call/turn identifiers as `interaction_ref` (stored in `inputs` and returned in API responses) without changing the CRS-001 schema.

### Requirements

- Python `>= 3.9`
- `pip` (or `uv`, optional)
- `curl` (used in quickstart verification commands)
- Optional:
  - Node.js (only for `fabra ui`)
  - Docker (only for Docker-based examples / local production stack)

Help and diagnostics:

```bash
fabra --help
fabra context --help
fabra doctor
```

### Production defaults (no fake receipts)

In `FABRA_ENV=production`, Fabra defaults to `FABRA_EVIDENCE_MODE=required`: if CRS-001 record persistence fails, the request fails (no `context_id` returned).

Already using LangChain or calling OpenAI directly? Add receipts without changing your app architecture:

- `docs/exporters-and-adapters.md` (LangChain-style callbacks, OpenAI wrapper, logs/OTEL)

Events/workers (optional): `docs/events-and-workers.md`

---

## What A Context Record Is

A Context Record is a durable artifact for an AI request: assembled content plus lineage (features, retrieval, freshness decisions), and optional integrity metadata.

### Privacy & Sensitive Data

By default, Fabra persists **raw context content** (the assembled prompt/context string) inside CRS-001 records and the legacy `context_log` table. Treat Context Records like production logs: **do not include secrets** (API keys, tokens, passwords) and be intentional about PII.

If you need lineage/metadata **without** storing raw text, set:

```bash
export FABRA_RECORD_INCLUDE_CONTENT=0
```

This “privacy mode” stores an empty string for `content` in persisted records (and therefore in `GET /v1/context/{context_id}`), while still capturing lineage and integrity hashes for tamper-evidence on the remaining fields.

Create a `context_id` locally using the shipped example:

```bash
fabra serve examples/demo_context.py
```

In another terminal:

```bash
curl -fsS -X POST http://127.0.0.1:8000/v1/context/chat_context \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u1","query":"test"}'
```

Core workflow (from a `context_id`):

```bash
fabra context show <context_id>
fabra context verify <context_id>
fabra context diff <context_id_A> <context_id_B>
fabra context export <context_id> --bundle -o incident_bundle.zip
```

`incident_bundle.zip` includes the exported record (`<context_id>.json`) plus `manifest.json` with stored vs computed hashes.

### Drop-In Receipts (No Keys)

If you already build prompts but don’t use `@context` yet, emit a verifiable receipt:

```python
from fabra.receipts import ReceiptRecorder
from fabra.exporters.logging import emit_context_ref_json

prompt = "system: ...\nuser: ..."
recorder = ReceiptRecorder()
receipt = recorder.record_sync(
    context_function="my_llm_call",
    content=prompt,
    inputs={"model": "gpt-4.1-mini"},
)
emit_context_ref_json(
    receipt.context_id,
    record_hash=receipt.integrity.record_hash,
    content_hash=receipt.integrity.content_hash,
    source="my-service",
    ticket="INC-1234",
)
```

---

## Two Entry Points

<table>
<tr>
<td width="50%" valign="top">

### ML Engineers (Features)

Define features in Python and serve them over HTTP.

```python
from fabra import FeatureStore, entity, feature
from datetime import timedelta

store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User, refresh=timedelta(hours=1))
def purchase_count(user_id: str) -> int:
    # Replace with a real DB call
    return 47
```

```bash
fabra serve features.py   # or: fabra serve examples/demo_features.py
curl localhost:8000/v1/features/purchase_count?entity_id=u123
# {"value": 47, "freshness_ms": 0, "served_from": "online"}
```

</td>
<td width="50%" valign="top">

### AI Engineers (Context)

Assemble prompts with features + retrieval, with lineage and budgets.

```python
from fabra import FeatureStore
from fabra.context import context, ContextItem

store = FeatureStore()

@context(store, max_tokens=4000, freshness_sla="5m")
async def build_prompt(user_id: str, query: str) -> list[ContextItem]:
    # Replace with your feature calls and retriever / RAG call
    tier = "premium"
    docs = "..."
    return [
        ContextItem(content=f"User tier: {tier}", priority=1),
        ContextItem(content=docs, priority=2),
    ]

ctx = await build_prompt("user_123", "question")
print(ctx.id)
print(ctx.lineage)
```

</td>
</tr>
</table>

---

## CLI (Most Used)

```bash
fabra demo                          # start demo + print a context_id
fabra context show <id>             # inspect a record (or best-effort legacy view)
fabra context verify <id>           # verify CRS-001 hashes (fails if unavailable)
fabra context diff <a> <b>          # compare two contexts
fabra context diff <a> <b> --local  # diff two CRS-001 receipts from DuckDB (no server required)
fabra context pack <id> -o incident.zip                # zip: context.json + summary.md
fabra context pack <id> --baseline <id0> -o incident.zip  # adds diff.patch (content unified diff)
fabra context export <id>           # export json/yaml
fabra context export <id> --bundle  # zip bundle for incident/audit
fabra doctor                        # local diagnostics
fabra serve <file.py>               # run server for examples/your code
fabra deploy fly|cloudrun|ecs        # generate deployment config
fabra ui <file.py>                  # local UI (requires Node.js)
```

Note: `fabra ui` requires Node.js. If you’re running from source, install UI deps with `cd src/fabra/ui-next && npm install`.

---

## What Fabra Is / Isn’t

Fabra is Python-first infrastructure for inference-time evidence (Context Records) and for serving features and context over HTTP. Define features and context in code (not YAML), run locally with DuckDB, and scale to Postgres/Redis in production. No Kubernetes or Kafka is required to adopt Fabra.

Fabra is not:
- an agent framework
- a monitoring dashboard
- a no-code builder

See `docs/quickstart.md`, `docs/context-record-spec.md`, and `docs/comparisons.md` for details.

---

<p align="center">
  <a href="https://fabraoss.vercel.app"><strong>Try in Browser</strong></a> ·
  <a href="https://davidahmann.github.io/fabra/docs/quickstart"><strong>Quickstart</strong></a> ·
  <a href="https://davidahmann.github.io/fabra/docs/"><strong>Docs</strong></a>
</p>
