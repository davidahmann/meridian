---
title: "Hooks & Extensibility | Meridian"
description: "Extend Meridian with custom hooks for validation, detailed logging, or external integrations. Configure webhooks for event-driven workflows."
keywords: hooks, webhooks, plugins, extensibility, events, validation
---

# Hooks & Extensibility

Meridian provides a powerful **Hook System** that allows you to intercept key lifecycle events in the Feature Store. This is useful for:

*   **Validation**: Check feature values before returning them.
*   **Audit Logging**: specific compliance logging requirements.
*   **Webhooks**: Notify external systems (Slack, PagerDuty, CI capabilities) when data is ingested.

## The `Hook` Interface

To create a custom hook, subclass `meridian.hooks.Hook` and valid methods.

```python
from meridian.hooks import Hook
from typing import List, Dict, Any
import structlog

logger = structlog.get_logger()

class AuditLogHook(Hook):
    async def before_feature_retrieval(self, entity_id: str, feature_names: List[str]) -> None:
        logger.info("audit_access", user="system", entity=entity_id, features=feature_names)

    async def after_feature_retrieval(self, entity_id: str, features: Dict[str, Any]) -> None:
        # Inspect values
        for k, v in features.items():
            if v is None:
                logger.warning("null_feature_detected", feature=k, entity=entity_id)

    async def after_ingest(self, event_type: str, entity_id: str, payload: Dict[str, Any]) -> None:
        logger.info("data_ingested", event=event_type, entity=entity_id)
```

### Registering Hooks

Register your hooks when initializing the `FeatureStore`.

```python
from meridian.core import FeatureStore

store = FeatureStore(
    hooks=[
        AuditLogHook(),
        # ... other hooks
    ]
)
```

## Webhooks

Meridian includes a built-in `WebhookHook` to trigger external HTTP endpoints when events occur (e.g., via `meridian events` or the Ingest API).

### Configuration

```python
from meridian.core import FeatureStore
from meridian.hooks import WebhookHook

store = FeatureStore(
    hooks=[
        WebhookHook(
            url="https://api.example.com/webhooks/meridian",
            headers={"Authorization": "Bearer secret-token"}
        )
    ]
)
```

### Triggering Webhooks

Webhooks are triggered automatically when you call the Ingest API:

```python
# Function call
await store.hooks.trigger_after_ingest(
    event_type="document_updated",
    entity_id="doc_123",
    payload={"status": "indexed"}
)
```

Or via HTTP:

```bash
curl -X POST http://localhost:8000/v1/ingest/document_updated \
  -d '{"entity_id": "doc_123", "payload": {"status": "indexed"}}'
```

The external URL will receive a POST request with the event payload.
