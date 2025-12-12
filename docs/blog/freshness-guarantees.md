# Freshness SLAs: When Your AI Needs Fresh Data

*Building confidence that your AI's decisions are based on current information*

---

You've deployed your AI assistant. It's making decisions about user upgrades, product recommendations, support routing. But there's a nagging question: **How fresh is the data it's using?**

That user who just upgraded to premium? Is your AI still treating them as a free user because the feature cache hasn't refreshed? That product that went out of stock 10 minutes ago? Is your AI still recommending it?

**Stale data leads to wrong decisions.** And wrong decisions erode user trust.

---

## The Problem: Silent Staleness

Most AI systems have a dirty secret: they don't know how old their data is. Features flow in from various sources—caches, databases, computed values—and get stitched together into context. But nobody tracks the timestamps.

When something goes wrong, you're left debugging:
- "When was this user's tier last computed?"
- "Was the recommendation model using yesterday's inventory?"
- "How old was the context when the AI made this decision?"

Traditional observability doesn't help. You can see latency, error rates, token counts. But **data freshness is invisible**.

---

## Introducing Freshness SLAs

Fabra v1.5 brings explicit freshness guarantees to your AI contexts. You declare how fresh your data needs to be, and Fabra enforces it.

```python
from fabra.context import context, ContextItem

@context(store, max_tokens=4000, freshness_sla="5m")
async def build_prompt(user_id: str, query: str):
    tier = await store.get_feature("user_tier", user_id)
    recent_orders = await store.get_feature("recent_orders", user_id)
    return [
        ContextItem(content=f"User tier: {tier}"),
        ContextItem(content=f"Recent orders: {recent_orders}"),
    ]
```

That `freshness_sla="5m"` declaration means: **every feature used in this context must be less than 5 minutes old.**

---

## Graceful Degradation

What happens when a feature is stale? By default, Fabra uses **graceful degradation**:

1. **Assembly succeeds** — Your AI still gets context
2. **Status is "degraded"** — Freshness breach is recorded
3. **Violations are listed** — You know exactly which features are stale
4. **Metrics fire** — Your monitoring catches it

```python
ctx = await build_prompt("user_123", "Should I upgrade?")

if not ctx.is_fresh:
    print(f"Warning: Context is degraded")
    for v in ctx.meta["freshness_violations"]:
        print(f"  {v['feature']} is {v['age_ms']}ms old (limit: {v['sla_ms']}ms)")
```

This approach lets you **monitor before enforcing**. Deploy freshness SLAs in observation mode, understand your baseline, then decide whether to enforce strictly.

---

## Strict Mode: Fail Fast

For critical contexts where stale data is unacceptable, enable strict mode:

```python
from fabra.exceptions import FreshnessSLAError

@context(store, freshness_sla="30s", freshness_strict=True)
async def financial_context(user_id: str):
    balance = await store.get_feature("account_balance", user_id)
    return [ContextItem(content=f"Balance: ${balance}")]

try:
    ctx = await financial_context("user_123")
except FreshnessSLAError as e:
    # Handle the breach: retry, use fallback, or fail the request
    logger.error("Freshness SLA breached", violations=e.violations)
    raise
```

Strict mode is perfect for:
- Financial decisions (account balances, credit limits)
- Safety-critical contexts (medical, legal)
- Real-time personalization (live pricing, inventory)

---

## Observability Built In

Freshness SLAs automatically expose Prometheus metrics:

```
# How many contexts are fresh vs degraded?
fabra_context_freshness_status_total{status="guaranteed"} 15420
fabra_context_freshness_status_total{status="degraded"} 234

# Which features are causing violations?
fabra_context_freshness_violations_total{feature="user_tier"} 89
fabra_context_freshness_violations_total{feature="inventory"} 145

# How stale are we getting?
fabra_context_stalest_feature_seconds_bucket{le="60"} 14500
fabra_context_stalest_feature_seconds_bucket{le="300"} 15600
```

Build dashboards. Set alerts. **Know when your AI is operating on stale data.**

---

## The Freshness Pyramid

Not all features need the same freshness guarantees. Think in tiers:

| Tier | Examples | Typical SLA |
|------|----------|-------------|
| **Real-time** | Inventory, pricing, live events | 30s - 2m |
| **Near-real-time** | User preferences, recent activity | 5m - 15m |
| **Hourly** | Aggregates, summaries | 1h |
| **Daily** | Historical analysis, batch features | 24h |

You can set different SLAs for different contexts:

```python
@context(store, freshness_sla="1m")  # Critical: real-time inventory
async def checkout_context(user_id: str):
    pass

@context(store, freshness_sla="1h")  # Less critical: recommendations
async def recommendation_context(user_id: str):
    pass
```

---

## Getting Started

1. **Add SLAs to your critical contexts**:
   ```python
   @context(store, freshness_sla="5m")
   ```

2. **Monitor the metrics**:
   ```bash
   curl localhost:8000/metrics | grep freshness
   ```

3. **Review violations**:
   ```python
   if ctx.meta["freshness_violations"]:
       log_freshness_breach(ctx)
   ```

4. **Optionally enable strict mode**:
   ```python
   @context(store, freshness_sla="30s", freshness_strict=True)
   ```

---

## What's Next

Freshness SLAs are the foundation for **trustworthy AI**. When you can prove your AI had fresh data, you can:

- **Debug confidently**: Know exactly what the AI knew when it decided
- **Audit reliably**: Show regulators the data was current
- **Alert proactively**: Catch staleness before it causes problems

Combined with [Context Accountability](../context-accountability.md) from v1.4, you now have complete visibility into your AI's decision-making context.

**Upgrade to v1.5 today:**

```bash
pip install --upgrade fabra-ai
```

---

*Questions? Issues? [Open a GitHub issue](https://github.com/davidahmann/fabra/issues) or check the [full documentation](https://davidahmann.github.io/fabra/freshness-sla).*

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "Freshness SLAs: When Your AI Needs Fresh Data",
  "description": "Building confidence that your AI's decisions are based on current information. Explicit freshness guarantees for AI context.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "datePublished": "2025-01-16",
  "keywords": "data freshness, ai freshness sla, stale data, context freshness, llm data quality"
}
</script>
