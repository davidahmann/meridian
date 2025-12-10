---
title: "RAG Compliance for Fintech: What Regulators Want to See"
description: "Building AI for financial services? Here's what CFPB, OCC, and other regulators expect for AI audit trails, explainability, and compliance."
keywords: AI compliance fintech, LLM audit trail banking, CFPB AI requirements, financial services AI compliance, rag audit trail fintech, AI explainability banking, adverse action AI
date: 2025-01-22
---

# RAG Compliance for Fintech: What Regulators Want to See

You built a RAG-powered customer support bot for your fintech app. It's live. Customers love it.

Then Legal sends an email:

> "The CFPB is asking about our AI systems. They want to know how we ensure fair lending practices when AI is involved in customer interactions. Can you provide an audit trail?"

Your stomach drops. You're using LangChain. There is no audit trail.

## The Regulatory Landscape

Financial services AI faces scrutiny from multiple regulators:

| Regulator | Focus Area | Key Requirement |
|:---|:---|:---|
| **CFPB** | Consumer protection | Explain adverse actions |
| **OCC** | Bank operations | Model risk management |
| **FFIEC** | IT examination | Audit trails, data governance |
| **SEC** | Investment advice | Fiduciary duty, disclosures |
| **State AGs** | Consumer protection | Fair lending, discrimination |

The common thread: **you must be able to explain what your AI knew when it made a decision**.

## What Regulators Actually Ask

Based on recent enforcement actions and guidance, here's what examiners want:

### 1. "What data informed this decision?"

If a customer was denied a loan modification and your AI chatbot handled the interaction, regulators want to know:

- What customer data was retrieved?
- What policy documents were consulted?
- What was the exact context assembled for the LLM?

**With LangChain:** Hope your logs are complete enough.

**With Fabra:** Every context assembly gets a UUIDv7 ID with full lineage:

```python
ctx = await customer_support_context(user_id, query)

# Regulators get:
print(ctx.id)       # "01912345-6789-7abc-def0-123456789abc"
print(ctx.lineage)  # Complete data provenance
```

### 2. "Can you reproduce this interaction?"

Six months later, a customer complains. Regulators want to see exactly what the AI knew at that time.

**With most RAG frameworks:** Impossible. The vector index has changed, features have updated.

**With Fabra:** Context replay:

```python
# Reproduce any historical context
historical_ctx = await store.get_context_at("01912345-6789-7abc-def0-123456789abc")
print(historical_ctx.content)  # Exact prompt from 6 months ago
```

### 3. "How fresh was the data?"

Regulatory guidance emphasizes data quality. If your AI used stale customer information, that's a compliance issue.

**With Fabra:** Freshness tracking is automatic:

```python
@context(store, max_tokens=4000, freshness_sla="5m")
async def lending_context(customer_id: str, query: str):
    # Features must be <5 minutes old
    credit_score = await store.get_feature("credit_score", customer_id)
    # ...

ctx = await lending_context(customer_id, query)
print(ctx.lineage.freshness_status)  # "guaranteed" or "degraded"
print(ctx.lineage.stalest_feature_ms)  # 150ms
```

## CFPB Adverse Action Requirements

The Equal Credit Opportunity Act (ECOA) requires lenders to provide "specific reasons" for adverse actions. If AI is involved in credit decisions, you need to trace how.

### The Problem

Your RAG chatbot helps customers understand their loan options. The customer asks about a home equity line. The bot says their application "doesn't meet current criteria."

That's potentially an adverse action. The CFPB wants to know:
1. What criteria were applied?
2. What customer data was considered?
3. Was the decision fair and consistent?

### The Solution: Full Lineage

```python
from fabra import FeatureStore, context, ContextItem

store = FeatureStore()

@context(store, name="lending_support_context", max_tokens=4000)
async def build_lending_context(customer_id: str, query: str) -> list[ContextItem]:
    # All feature retrievals are tracked
    credit_score = await store.get_feature("credit_score", customer_id)
    dti_ratio = await store.get_feature("debt_to_income", customer_id)
    account_age = await store.get_feature("account_age_months", customer_id)

    # Policy retrieval is tracked
    policies = await search_lending_policies(query)

    return [
        ContextItem(content=f"Credit Score: {credit_score}", priority=0, required=True),
        ContextItem(content=f"DTI Ratio: {dti_ratio}", priority=1, required=True),
        ContextItem(content=f"Account Age: {account_age} months", priority=2),
        ContextItem(content=f"Relevant Policies:\n{policies}", priority=3),
    ]

# Usage
ctx = await build_lending_context(customer_id, "Can I get a HELOC?")
response = await call_llm(ctx.content)

# Store context ID with the interaction
save_interaction(
    customer_id=customer_id,
    context_id=ctx.id,  # Full audit trail available via this ID
    response=response,
)
```

When regulators ask about this interaction:

```python
# Retrieve complete audit trail
audit_ctx = await store.get_context_at(saved_interaction.context_id)

print(audit_ctx.lineage)
# {
#   "features_used": [
#     {"feature_name": "credit_score", "value": 720, "freshness_ms": 50},
#     {"feature_name": "debt_to_income", "value": 0.35, "freshness_ms": 120},
#     ...
#   ],
#   "retrievers_used": [
#     {"retriever_name": "search_lending_policies", "results_count": 3}
#   ],
#   "freshness_status": "guaranteed"
# }
```

## OCC Model Risk Management

The OCC's SR 11-7 guidance requires banks to:

1. **Validate models** — including AI/ML models
2. **Document assumptions** — what data is used and why
3. **Monitor performance** — track outcomes and drift
4. **Maintain audit trails** — for examiner review

### Implementation Pattern

```python
# Log every AI interaction for model risk management
async def handle_customer_query(customer_id: str, query: str):
    ctx = await build_lending_context(customer_id, query)
    response = await call_llm(ctx.content)

    # Model risk logging
    model_risk_log.info(
        "ai_interaction",
        context_id=ctx.id,
        customer_id=customer_id,
        features_used=[f["feature_name"] for f in ctx.lineage.features_used],
        freshness_status=ctx.lineage.freshness_status,
        token_usage=ctx.meta.token_usage,
    )

    return response
```

## Export for Examination

When examiners arrive, export your audit data:

```bash
# Export all AI interactions for Q4 2024
fabra context list --start 2024-10-01 --end 2024-12-31 --format json > q4_ai_audit.json

# Export specific interaction
fabra context export 01912345-6789-7abc-def0-123456789abc --include-lineage --format json
```

## Compliance Checklist

| Requirement | LangChain | Fabra |
|:---|:---|:---|
| Track what data was retrieved | ❌ Manual logging | ✅ Automatic lineage |
| Replay historical contexts | ❌ Not possible | ✅ `get_context_at(id)` |
| Track data freshness | ❌ Not tracked | ✅ Freshness SLAs |
| Export audit trails | ❌ Build it yourself | ✅ `fabra context export` |
| Unique interaction IDs | ❌ Manual | ✅ UUIDv7 automatic |

## Getting Started

```bash
pip install "fabra-ai[ui]"
```

```python
from fabra import FeatureStore, context, ContextItem

store = FeatureStore()

@context(store, name="fintech_support", max_tokens=4000)
async def build_support_context(customer_id: str, query: str) -> list[ContextItem]:
    # Your implementation
    pass

# Every call is automatically audited
ctx = await build_support_context(customer_id, query)
print(f"Audit ID: {ctx.id}")
```

[Full Compliance Guide →](../compliance-guide.md) | [Context Accountability Docs →](../context-accountability.md)

---

## Also Need ML Features?

Fabra includes a Feature Store for serving ML features — same infrastructure as the Context Store. User risk scores, fraud signals, personalization features.

[Feature Store →](../feature-store-without-kubernetes.md) | [Quickstart →](../quickstart.md)

---

## You Might Also Search For

- "CFPB AI compliance requirements"
- "LLM audit trail for banking"
- "adverse action AI explainability"
- "model risk management AI"
- "RAG compliance financial services"

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "RAG Compliance for Fintech: What Regulators Want to See",
  "description": "Building AI for financial services? Here's what CFPB, OCC, and regulators expect for AI audit trails and compliance.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "datePublished": "2025-01-22",
  "keywords": "fintech AI compliance, CFPB AI, LLM audit trail, rag compliance"
}
</script>
