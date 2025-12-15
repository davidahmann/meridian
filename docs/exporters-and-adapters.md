---
title: "Exporters & Adapters"
description: "Meet engineers where incidents live: thin adapters for frameworks (LangChain/OpenAI) and exporters into logs/OTEL/tickets."
keywords: adapters, exporters, langchain, openai, observability, opentelemetry, incident response
---

# Exporters & Adapters

You don’t need the world to understand Fabra today.
You need a handful of engineers to say: “that saved me.”

In practice, adoption happens through existing channels:
- frameworks (LangChain / LlamaIndex / OpenAI SDK)
- observability (logs / OTEL / traces)

Fabra now ships thin, dependency-light building blocks for this:
- `fabra.receipts.ReceiptRecorder` (persist a verifiable CRS-001 receipt anywhere)
- `fabra.adapters.langchain.FabraLangChainCallbackHandler` (LangChain-style callbacks)
- `fabra.adapters.openai.wrap_openai_call` (wrap OpenAI call sites)
- `fabra.exporters.logging.emit_context_id_json` (single-line JSON logs)
- `fabra.exporters.otel.attach_context_id_to_current_span` (OTEL span attributes, optional)

## Exporters (evidence to where incidents live)

### Ticket attachment
Use a verifiable bundle:

```bash
fabra context export <context_id> --bundle
```

### Structured logs
Emit JSON exports to your logging pipeline (S3/GCS/Loki/ELK) so support can retrieve evidence by `context_id`.

```python
from fabra.exporters.logging import emit_context_id_json

emit_context_id_json("ctx_...", source="my-service", ticket="INC-1234")
```

### OpenTelemetry (OTEL)
Attach `context_id` to the current span if OTEL is installed/configured:

```python
from fabra.exporters.otel import attach_context_id_to_current_span

attach_context_id_to_current_span("ctx_...", attributes={"fabra.ticket": "INC-1234"})
```

## Adapters (capture a Context Record without rip-and-replace)

### Framework callback pattern (LangChain/LlamaIndex)
Wrap the app’s request lifecycle:
- create a Context Record
- propagate `context_id` into logs/traces
- return the `context_id` to callers (so it lands in tickets)

Minimal example (LangChain-style callbacks):

```python
from fabra.receipts import ReceiptRecorder
from fabra.adapters.langchain import FabraLangChainCallbackHandler

recorder = ReceiptRecorder()  # durable by default in dev (~/.fabra/fabra.duckdb)
handler = FabraLangChainCallbackHandler(recorder=recorder)

# Pass `handler` where your framework expects callbacks/handlers.
# Example (varies by LangChain version):
# llm = ChatOpenAI(..., callbacks=[handler])
```

### OpenAI wrapper pattern
If you call the OpenAI API directly, wrap the call site so each request produces:
- a durable record artifact (content + lineage)
- a `context_id` emitted to logs/OTEL

Minimal example:

```python
from fabra.receipts import ReceiptRecorder
from fabra.adapters.openai import wrap_openai_call

recorder = ReceiptRecorder()

# Example call site (works with any callable; this is SDK-agnostic)
wrapped = wrap_openai_call(
    func=openai_call,  # e.g. client.responses.create
    recorder=recorder,
    context_function="openai.responses.create",
    return_context_id=True,
)

result, context_id = wrapped(input="hi", model="gpt-4.1-mini")
print("receipt:", context_id)
```

## Design goal

Adopters should be able to add Fabra in a day:
- no rewrite
- no data migration day 1
- immediate “receipt” + `show/diff/verify`

## Diffing receipts (CRS-001)

Receipts created by adapters (or `ReceiptRecorder`) are **CRS-001 Context Records**.

You can diff them two ways:

### Record-first diff (server)
If your Fabra server exposes `/v1/record/<id>`, `fabra context diff` will diff CRS-001 records by default:

```bash
fabra context diff <context_id_A> <context_id_B>
```

### Local diff (no server required)
If you’re emitting receipts directly to DuckDB (the default), diff locally:

```bash
fabra context diff <context_id_A> <context_id_B> --local
```

## What these receipts are (and aren’t)

- These adapters produce a durable, verifiable **CRS-001 Context Record** where `content` is the best-effort “what the model saw” (prompt/messages serialized).
- For full lineage (features/retrievers/token-budget decisions) and time-travel replay, use Fabra’s native `@context` + `@retriever` path.
