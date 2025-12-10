---
title: "Building an Audit Trail for AI Decisions"
description: "How to implement full data provenance and accountability for LLM-powered applications."
keywords: ai audit trail, llm compliance, ai governance, data provenance, ai accountability
date: 2025-01-15
---

# Building an Audit Trail for AI Decisions

**TL;DR:** As AI systems make more consequential decisions, you need to answer "why did the AI say that?" Fabra v1.4's Context Accountability gives you complete data provenance for every AI interaction.

---

## The Accountability Gap

Your AI assistant just:
- Denied a loan application
- Recommended a medical treatment
- Escalated a support ticket to legal

Six months later, someone asks: *"What data did the AI use to make that decision?"*

For most teams, this question is unanswerable. Traditional logging captures inputs and outputs, but not the *context* — the assembled information that actually influenced the AI's response.

This is the accountability gap. And it's becoming a compliance problem.

---

## Why Traditional Logging Falls Short

### The Typical Setup

```python
# What most teams log
logger.info("AI request", user_id=user_id, query=query)
response = await llm.complete(context)
logger.info("AI response", response_id=response.id)
```

You have the request. You have the response. But what was in `context`?

- Which features were pulled?
- What documents were retrieved?
- Were those values fresh or cached?
- What got truncated due to token limits?

**You don't know.** And reconstructing this later is nearly impossible.

### The Compliance Risk

Regulators increasingly want to know:
- What data influenced this AI decision?
- Was that data accurate at decision time?
- Can you prove the AI had (or didn't have) certain information?

Without proper context logging, you're guessing.

---

## Fabra's Approach: Context Lineage

Fabra v1.4 introduces **Context Lineage** — automatic tracking of every piece of data that goes into your AI's context window.

### Full Data Provenance

Every context assembly captures:

```python
{
    "context_id": "01948c9a-2b3e-7d4f-8e5a-1c2d3e4f5a6b",
    "timestamp": "2025-01-15T15:30:00Z",
    "lineage": {
        "features_used": [
            {
                "feature_name": "credit_score",
                "entity_id": "user_456",
                "value": 720,
                "timestamp": "2025-01-15T15:29:55Z",
                "freshness_ms": 5000,
                "source": "compute"  # fresh computation, not cached
            },
            {
                "feature_name": "account_age_days",
                "entity_id": "user_456",
                "value": 365,
                "freshness_ms": 100,
                "source": "cache"
            }
        ],
        "retrievers_used": [
            {
                "retriever_name": "policy_docs",
                "query": "loan eligibility requirements",
                "results_count": 5,
                "latency_ms": 23.5,
                "index_name": "lending_policies"
            }
        ],
        "freshness_status": "guaranteed",
        "token_usage": {
            "total": 3847,
            "budget": 4000
        }
    }
}
```

### Time-Sortable IDs

We use **UUIDv7** for context IDs. These are:
- Globally unique
- Time-sortable (find contexts by time range efficiently)
- URL-safe (easy to pass in headers, logs, etc.)

```bash
# Find all contexts from a specific hour
fabra context list --start 2025-01-15T14:00:00 --end 2025-01-15T15:00:00
```

### Point-in-Time Accuracy

Every feature records when it was fetched and how fresh it was. If a user's credit score changed at 3:01pm and your decision was made at 3:00pm, the lineage proves you used the old value — because that's what existed at decision time.

---

## Implementation Guide

### Step 1: Enable Context Tracking

It's on by default in Fabra v1.4. Just use the `@context` decorator:

```python
from fabra.context import context, ContextItem

@context(store, max_tokens=4000)
async def build_loan_decision_context(user_id: str, application_id: str):
    # All feature fetches are automatically tracked
    credit_score = await store.get_feature("credit_score", user_id)
    income = await store.get_feature("annual_income", user_id)
    debt_ratio = await store.get_feature("debt_to_income", user_id)

    # Retriever calls are also tracked
    policies = await get_lending_policies(application_id)

    return [
        ContextItem(content=f"Credit Score: {credit_score}", priority=0),
        ContextItem(content=f"Annual Income: ${income:,}", priority=0),
        ContextItem(content=f"Debt-to-Income: {debt_ratio}%", priority=0),
        ContextItem(content=policies, priority=1),
    ]
```

### Step 2: Store the Context ID

Include the context ID in your application's audit log:

```python
result = await build_loan_decision_context(user_id, application_id)

# Store this ID with your business record
loan_decision = LoanDecision(
    application_id=application_id,
    decision="approved",
    context_id=result.id,  # Link to full lineage
    timestamp=datetime.now()
)
await save_decision(loan_decision)
```

### Step 3: Query When Needed

Six months later, auditor asks about application #12345:

```python
# Get the context ID from your business record
decision = await get_loan_decision(application_id="12345")

# Retrieve full context lineage
context = await store.get_context_at(decision.context_id)

# Export for audit
print(context.lineage.model_dump_json(indent=2))
```

Or via CLI:

```bash
fabra context export 01948c9a-2b3e-7d4f-8e5a-1c2d3e4f5a6b --format yaml
```

---

## Compliance Scenarios

### Financial Services

**Requirement:** Explain factors in credit decisions
**Solution:** Export feature lineage showing exactly which data points influenced the context

### Healthcare

**Requirement:** Document information available during clinical decision support
**Solution:** Context replay shows what medical records, guidelines, and patient data were assembled

### Legal

**Requirement:** Prove AI didn't have access to privileged information
**Solution:** Lineage shows exactly which retrievers were called and what they returned

### General GDPR/CCPA

**Requirement:** Respond to "what data do you have on me" requests
**Solution:** Query contexts by entity_id to show all features used for a specific user

---

## Best Practices

### 1. Link Context IDs to Business Events

Always store the context_id with your business decision:

```python
audit_record = {
    "event_type": "loan_decision",
    "decision": "approved",
    "context_id": result.id,  # Critical for audit trail
    "timestamp": datetime.now().isoformat()
}
```

### 2. Set Appropriate Retention

Match your retention policy to compliance requirements:

```python
# Production config
CONTEXT_RETENTION_DAYS = 2555  # 7 years for financial services
```

### 3. Test Your Audit Process

Regularly verify you can retrieve and explain old contexts:

```python
def test_context_audit_trail():
    # Create a context
    result = await build_context(user_id, query)

    # Verify we can retrieve it
    retrieved = await store.get_context_at(result.id)

    assert retrieved is not None
    assert retrieved.lineage.features_used
    assert retrieved.content == result.content
```

### 4. Export in Standard Formats

Auditors may need data in specific formats:

```bash
# JSON for programmatic processing
fabra context export <id> --format json > audit.json

# YAML for human review
fabra context export <id> --format yaml > audit.yaml
```

---

## The Bigger Picture

Context Accountability isn't just about compliance — it's about building trustworthy AI systems.

When you can answer "what did the AI know?" definitively:
- Users trust your system more
- Debugging becomes straightforward
- Compliance audits become routine
- Teams iterate faster with confidence

---

## Getting Started

```bash
pip install --upgrade "fabra-ai[ui]"
```

Context Accountability is enabled by default. Your contexts are already being tracked.

[Full Documentation →](../context-accountability.md)

---

*Have questions about AI compliance? [Open a discussion](https://github.com/davidahmann/fabra/discussions) on GitHub.*

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "Building an Audit Trail for AI Decisions",
  "description": "How to implement full data provenance and accountability for LLM-powered applications.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "datePublished": "2025-01-15",
  "keywords": "ai audit trail, llm compliance, ai governance, data provenance, ai accountability"
}
</script>
