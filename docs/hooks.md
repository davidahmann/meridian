---
title: "Hooks & Extensibility | Fabra"
description: "Extend Fabra with custom hooks for validation, detailed logging, or external integrations. Configure webhooks for event-driven workflows."
keywords: hooks, webhooks, plugins, extensibility, events, validation
---

# Hooks & Extensibility

## At a Glance

| | |
|:---|:---|
| **Base Class** | `fabra.hooks.Hook` |
| **Register** | `FeatureStore(hooks=[YourHook()])` |
| **Events** | `before_feature_retrieval`, `after_feature_retrieval`, `after_ingest` |
| **Built-in** | `WebhookHook(url="...", headers={...})` |

Fabra provides a powerful **Hook System** that allows you to intercept key lifecycle events in the Feature Store. This is useful for:

*   **Validation**: Check feature values before returning them.
*   **Audit Logging**: specific compliance logging requirements.
*   **Webhooks**: Notify external systems (Slack, PagerDuty, CI capabilities) when data is ingested.

## The `Hook` Interface

To create a custom hook, subclass `fabra.hooks.Hook` and valid methods.

```python
from fabra.hooks import Hook
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
from fabra.core import FeatureStore

store = FeatureStore(
    hooks=[
        AuditLogHook(),
        # ... other hooks
    ]
)
```

## Webhooks

Fabra includes a built-in `WebhookHook` to trigger external HTTP endpoints when events occur (e.g., via `fabra events` or the Ingest API).

### Configuration

```python
from fabra.core import FeatureStore
from fabra.hooks import WebhookHook

store = FeatureStore(
    hooks=[
        WebhookHook(
            url="https://api.example.com/webhooks/fabra",
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

## FAQ

**Q: How do I add custom hooks to Fabra?**
A: Subclass `fabra.hooks.Hook` and implement the lifecycle methods (`before_feature_retrieval`, `after_feature_retrieval`, `after_ingest`). Register via `FeatureStore(hooks=[YourHook()])`.

**Q: Can I add validation to feature retrieval?**
A: Yes. Implement `before_feature_retrieval` to validate inputs or `after_feature_retrieval` to validate/transform outputs. Raise exceptions to block invalid data.

**Q: How do I send webhooks when data is ingested?**
A: Use the built-in `WebhookHook`: `WebhookHook(url="https://...", headers={"Authorization": "..."})`. Triggers automatically on ingest API calls.

**Q: What lifecycle events can I hook into?**
A: Three events: `before_feature_retrieval` (before fetch), `after_feature_retrieval` (after fetch with values), `after_ingest` (after data written).

---

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "TechArticle",
  "headline": "Hooks & Extensibility in Fabra",
  "description": "Extend Fabra with custom hooks for validation, detailed logging, or external integrations. Configure webhooks for event-driven workflows.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "keywords": "hooks, webhooks, plugins, extensibility, feature store",
  "articleSection": "Documentation"
}
</script>
