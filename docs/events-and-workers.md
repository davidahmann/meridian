---
title: "Events & Workers"
description: "How Fabra ingests events, publishes to Redis Streams, and runs a worker to update triggered features."
keywords: events, worker, redis streams, triggers, event-driven features
---

# Events & Workers

Fabra supports an event-driven path for keeping **triggered features** up to date:

1. Your app sends an event to Fabra over HTTP.
2. Fabra writes the event to **Redis Streams**.
3. A Fabra worker process consumes the stream and computes triggered features.
4. Results are written to the **online store** (Redis), so `GET /features/...` is fast.

This is intentionally simple. There’s no “proxy SDK” requirement.

## Ingest an event (HTTP)

```bash
curl -fsS -X POST "http://127.0.0.1:8000/v1/ingest/purchase?entity_id=u1" \
  -H "Content-Type: application/json" \
  -d '{"amount": 42, "currency": "USD"}'
```

## Redis Streams used

Fabra publishes each event to:
- `fabra:events:<event_type>` (example: `fabra:events:purchase`)
- `fabra:events:all` (shared stream for simpler worker setups)

## Run the worker

Load the same feature file you use for `fabra serve`:

```bash
fabra worker features.py
```

By default, the worker will discover triggers from your registered features and listen on the corresponding streams.

### Listen to explicit event types

```bash
fabra worker features.py --event-type purchase,refund
```

### Listen to explicit streams (advanced)

```bash
fabra worker features.py --streams fabra:events:purchase,fabra:events:refund
```

### Listen to all events

```bash
fabra worker features.py --listen-all
```

## Triggered feature functions

Triggered features can optionally accept `payload` or `event`:

```python
from fabra.core import FeatureStore

store = FeatureStore()

def purchase_total(user_id: str, payload: dict) -> int:
    return int(payload["amount"])

store.register_feature(
    name="purchase_total",
    entity_name="user",
    func=purchase_total,
    trigger="purchase",
)
```
