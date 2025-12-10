---
title: "AI Compliance Guide: GDPR, SOC2, and Regulated Industries | Fabra"
description: "Build compliant AI applications with Fabra. Full audit trails, context replay, and lineage tracking for GDPR, SOC2, HIPAA, and financial regulations."
keywords: ai compliance, gdpr ai, soc2 ai, hipaa ai, ai audit trail, llm compliance, rag compliance, ai explainability, ai regulations, fintech ai compliance, healthcare ai compliance, ai decision audit
---

# AI Compliance Guide

> **TL;DR:** Fabra provides the audit infrastructure for compliant AI. Full lineage tracking, context replay, and exportable audit trails for GDPR, SOC2, HIPAA, and financial regulations.

## The Compliance Challenge

Regulators and auditors increasingly ask:

- **"What data did your AI use to make this decision?"**
- **"Can you reproduce the exact context from that date?"**
- **"How fresh was the data when the decision was made?"**
- **"Show me the audit trail for this user's interactions."**

Most RAG frameworks and feature stores can't answer these questions. They're read-only wrappers — they query external stores but don't track what was retrieved.

**Fabra owns the write path.** We ingest, index, track freshness, and serve. This enables lineage, replay, and auditability that read-only tools cannot provide.

## Key Compliance Capabilities

### 1. Full Lineage Tracking

Every context assembly automatically records:

| Data Point | Description |
|:---|:---|
| **Context ID** | UUIDv7 (time-sortable, unique) |
| **Timestamp** | When the context was assembled |
| **Features Used** | Which features, their values, and freshness |
| **Retrievers Called** | Which searches, queries, and result counts |
| **Items Included** | What made it into the final prompt |
| **Items Dropped** | What was truncated due to token budget |
| **Freshness Status** | Whether all data met freshness SLAs |

```python
ctx = await build_context(user_id, query)

# Full lineage automatically attached
print(ctx.lineage)
# {
#   "context_id": "01912345-...",
#   "features_used": [...],
#   "retrievers_used": [...],
#   "freshness_status": "guaranteed"
# }
```

### 2. Context Replay

Reproduce any historical context by ID:

```python
# Retrieve exact context from any point in time
historical_ctx = await store.get_context_at("01912345-6789-7abc-def0-123456789abc")

print(historical_ctx.content)   # Exact prompt that was assembled
print(historical_ctx.lineage)   # Complete data provenance
print(historical_ctx.meta)      # Assembly metadata
```

This enables:
- **Incident investigation** — What went wrong?
- **Regulatory response** — Show exactly what the AI knew
- **Model debugging** — Reproduce production behavior locally

### 3. Freshness Guarantees

Track data freshness with configurable SLAs:

```python
from fabra import FeatureStore, feature
from datetime import timedelta

store = FeatureStore()

@feature(entity=User, refresh="5m", max_staleness=timedelta(minutes=10))
def user_risk_score(user_id: str) -> float:
    return calculate_risk(user_id)
```

When data exceeds `max_staleness`:
- **Degraded mode:** Context marked as `freshness_status: "degraded"`
- **Fail-safe mode:** Request fails with clear error (configurable)

### 4. Audit Export

Export context history for compliance review:

```bash
# Export single context
fabra context export 01912345-6789-7abc-def0-123456789abc --format json

# Export time range
fabra context list --start 2024-01-01 --end 2024-01-31 --format json > audit.json

# Export with lineage
fabra context export 01912345-... --include-lineage --format yaml
```

## Compliance Framework Mapping

### GDPR (EU AI Act)

| Requirement | Fabra Capability |
|:---|:---|
| Right to explanation | Context replay shows what data was used |
| Data minimization | Token budgets limit data in prompts |
| Audit trails | Full lineage tracking |
| Data freshness | Freshness SLAs with timestamps |

### SOC 2 Type II

| Control | Fabra Capability |
|:---|:---|
| CC6.1 - Logical access | API authentication, audit logging |
| CC7.2 - System monitoring | Prometheus metrics, JSON logs |
| CC7.3 - Change management | Lineage tracks data changes |
| CC8.1 - Incident response | Context replay for investigation |

### HIPAA (Healthcare)

| Requirement | Fabra Capability |
|:---|:---|
| Audit controls | Full lineage with timestamps |
| Access logs | Every context assembly logged |
| Data integrity | Immutable context log |
| Minimum necessary | Token budgets enforce data limits |

### Financial Services (FFIEC, OCC)

| Requirement | Fabra Capability |
|:---|:---|
| Model risk management | Context replay for validation |
| Audit trail | Complete data provenance |
| Explainability | Lineage shows what informed decisions |
| Data quality | Freshness SLAs ensure current data |

## Implementation Patterns

### Pattern 1: Audit Every Decision

```python
from fabra import FeatureStore, context, ContextItem

store = FeatureStore()

@context(store, name="loan_decision_context", max_tokens=4000)
async def build_loan_context(user_id: str, application_id: str) -> list[ContextItem]:
    # Every feature retrieval is tracked
    credit_score = await store.get_feature("credit_score", user_id)
    income = await store.get_feature("annual_income", user_id)
    debt_ratio = await store.get_feature("debt_to_income", user_id)

    return [
        ContextItem(content=f"Credit Score: {credit_score}", priority=0, required=True),
        ContextItem(content=f"Annual Income: {income}", priority=1, required=True),
        ContextItem(content=f"Debt Ratio: {debt_ratio}", priority=2, required=True),
    ]

# Call context
ctx = await build_loan_context("user123", "app456")

# Store context ID with the decision
decision = make_loan_decision(ctx.content)
save_decision(
    application_id="app456",
    decision=decision,
    context_id=ctx.id,  # Link to full audit trail
)
```

### Pattern 2: Compliance-Ready RAG

```python
from fabra import FeatureStore, context, ContextItem
from fabra.retrieval import retriever

store = FeatureStore()

@retriever(index="policies", top_k=5)
async def search_policies(query: str):
    pass

@context(store, name="support_context", max_tokens=4000)
async def build_support_context(user_id: str, query: str) -> list[ContextItem]:
    # All retrievals tracked in lineage
    policies = await search_policies(query)
    tier = await store.get_feature("user_tier", user_id)

    return [
        ContextItem(content=f"User tier: {tier}", priority=0),
        ContextItem(content=f"Relevant policies:\n{policies}", priority=1),
    ]

# Context includes full lineage for audit
ctx = await build_support_context("user123", "refund policy")
response = call_llm(ctx.content)

# Log for compliance
audit_log.info(
    "ai_response",
    context_id=ctx.id,
    user_id="user123",
    freshness_status=ctx.lineage.freshness_status,
)
```

### Pattern 3: Incident Investigation

```python
async def investigate_incident(user_id: str, incident_time: datetime):
    # Find all contexts around the incident
    contexts = await store.list_contexts(
        start=incident_time - timedelta(hours=1),
        end=incident_time + timedelta(hours=1),
    )

    report = []
    for ctx_summary in contexts:
        # Get full context with lineage
        full_ctx = await store.get_context_at(ctx_summary["context_id"])

        report.append({
            "context_id": full_ctx.id,
            "timestamp": full_ctx.lineage.timestamp,
            "features_used": [f["feature_name"] for f in full_ctx.lineage.features_used],
            "stalest_feature_ms": full_ctx.lineage.stalest_feature_ms,
            "freshness_status": full_ctx.lineage.freshness_status,
        })

    return report
```

## Storage and Retention

Context lineage is stored in the `context_log` table:

```sql
-- Query context history directly
SELECT context_id, timestamp, content, lineage
FROM context_log
WHERE timestamp BETWEEN '2024-01-01' AND '2024-01-31'
ORDER BY timestamp DESC;
```

### Retention Policies

Configure retention based on compliance requirements:

| Regulation | Typical Retention | Fabra Config |
|:---|:---|:---|
| GDPR | 6 years | `FABRA_CONTEXT_RETENTION_DAYS=2190` |
| SOC 2 | 1 year | `FABRA_CONTEXT_RETENTION_DAYS=365` |
| HIPAA | 6 years | `FABRA_CONTEXT_RETENTION_DAYS=2190` |
| Financial | 7 years | `FABRA_CONTEXT_RETENTION_DAYS=2555` |

## FAQ

**Q: How do I prove what data my AI used for a specific decision?**
A: Every context gets a UUIDv7 ID. Store this ID with the decision. Use `store.get_context_at(id)` to retrieve the exact content and lineage.

**Q: Can auditors access the audit trail?**
A: Yes. Use `fabra context export` to export contexts as JSON or YAML. The export includes full lineage, timestamps, and data provenance.

**Q: How do I ensure data freshness for compliance?**
A: Configure `max_staleness` on features. Fabra tracks when data was last updated and marks contexts as `degraded` or fails requests when data is stale.

**Q: Does Fabra support data residency requirements?**
A: Yes. Deploy Fabra to any region using Postgres and Redis. Data stays in your infrastructure — no external SaaS dependencies.

**Q: How long is context history retained?**
A: Configurable via `FABRA_CONTEXT_RETENTION_DAYS`. Default is 90 days. Set based on your compliance requirements.

**Q: Can I integrate with existing compliance tools?**
A: Yes. Export contexts as JSON, query the `context_log` table directly, or use the REST API (`GET /v1/contexts`) for integration.

## Next Steps

- [Context Accountability](context-accountability.md) — Deep dive into lineage tracking
- [RAG Audit Trail](rag-audit-trail.md) — Audit trails for RAG applications
- [Freshness SLAs](freshness-sla.md) — Configure data freshness guarantees
- [Quickstart](quickstart.md) — Get started in 30 seconds

---

## Also Need ML Features?

Fabra includes a Feature Store for serving ML features — user personalization, risk scores, recommendations. Same infrastructure, same audit trails.

[Feature Store →](feature-store-without-kubernetes.md) | [Feast vs Fabra →](feast-alternative.md)

---

## You Might Also Search For

- "ai compliance gdpr"
- "llm audit trail soc2"
- "hipaa ai requirements"
- "fintech ai compliance"
- "ai decision explainability"

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "TechArticle",
  "headline": "AI Compliance Guide: GDPR, SOC2, and Regulated Industries",
  "description": "Build compliant AI applications with Fabra. Full audit trails, context replay, and lineage tracking for regulated industries.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "keywords": "ai compliance, gdpr ai, soc2 ai, hipaa ai, ai audit trail, llm compliance",
  "articleSection": "Documentation"
}
</script>
