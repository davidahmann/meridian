# Freshness SLAs

**New in v1.5** | Track and enforce data freshness guarantees for your AI contexts.

## At a Glance

| | |
|:---|:---|
| **Parameter** | `@context(store, freshness_sla="5m")` |
| **Formats** | `500ms`, `30s`, `5m`, `1h`, `1d` |
| **Default Mode** | Degraded (assembly succeeds, flags violations) |
| **Strict Mode** | `freshness_strict=True` (raises `FreshnessSLAError`) |
| **Check Status** | `ctx.is_fresh` or `ctx.meta["freshness_status"]` |
| **Metrics** | `fabra_context_freshness_violations_total` |

---

## Overview

Freshness SLAs let you specify how recent your feature data must be when assembling context. When features exceed the SLA threshold, Fabra provides clear signals through:

- **Degraded mode**: Assembly succeeds but flags stale data
- **Strict mode**: Assembly fails immediately on SLA breach
- **Prometheus metrics**: Real-time monitoring of freshness violations

```python
from fabra.context import context, ContextItem

@context(store, max_tokens=4000, freshness_sla="5m")
async def build_prompt(user_id: str, query: str):
    tier = await store.get_feature("user_tier", user_id)  # Must be <5m old
    docs = await search_docs(query)
    return [
        ContextItem(content=f"User tier: {tier}"),
        ContextItem(content=str(docs)),
    ]
```

---

## Quick Start

### 1. Set a Freshness SLA

Add `freshness_sla` to your `@context` decorator:

```python
@context(store, freshness_sla="5m")  # Features must be < 5 minutes old
async def build_prompt(user_id: str):
    # Your context assembly logic
    pass
```

### 2. Check Freshness Status

Every context includes freshness information:

```python
ctx = await build_prompt("user_123")

# Check overall status
print(ctx.meta["freshness_status"])  # "guaranteed" or "degraded"
print(ctx.is_fresh)  # True if guaranteed

# See specific violations
if ctx.meta["freshness_violations"]:
    for violation in ctx.meta["freshness_violations"]:
        print(f"Feature {violation['feature']} is {violation['age_ms']}ms old")
        print(f"  SLA threshold: {violation['sla_ms']}ms")
```

### 3. Enable Strict Mode (Optional)

For critical contexts where stale data is unacceptable:

```python
from fabra.exceptions import FreshnessSLAError

@context(store, freshness_sla="30s", freshness_strict=True)
async def critical_context(user_id: str):
    # Raises FreshnessSLAError if any feature exceeds SLA
    pass

try:
    ctx = await critical_context("user_123")
except FreshnessSLAError as e:
    print(f"SLA breached: {e.message}")
    for v in e.violations:
        print(f"  - {v['feature']}: {v['age_ms']}ms > {v['sla_ms']}ms")
```

---

## SLA Format

Supported duration formats:

| Format | Example | Duration |
|--------|---------|----------|
| Milliseconds | `500ms` | 500ms |
| Seconds | `30s` | 30 seconds |
| Minutes | `5m` | 5 minutes |
| Hours | `1h` | 1 hour |
| Days | `1d` | 1 day |

Decimals are supported: `1.5h` = 90 minutes

---

## Freshness Status

### Guaranteed

All features used in context assembly are within the SLA threshold.

```python
ctx.meta["freshness_status"]  # "guaranteed"
ctx.is_fresh  # True
ctx.meta["freshness_violations"]  # []
```

### Degraded

One or more features exceeded the SLA threshold. Context assembly still succeeds.

```python
ctx.meta["freshness_status"]  # "degraded"
ctx.is_fresh  # False
ctx.meta["freshness_violations"]  # [{"feature": "user_tier", "age_ms": 360000, ...}]
```

---

## Metrics

Freshness SLAs expose Prometheus metrics for monitoring:

```
# Total contexts by freshness status
fabra_context_freshness_status_total{name="build_prompt", status="guaranteed"} 1542
fabra_context_freshness_status_total{name="build_prompt", status="degraded"} 23

# SLA violations by feature
fabra_context_freshness_violations_total{name="build_prompt", feature="user_tier"} 15
fabra_context_freshness_violations_total{name="build_prompt", feature="purchase_history"} 8

# Age of stalest feature (histogram)
fabra_context_stalest_feature_seconds_bucket{name="build_prompt", le="60"} 1200
fabra_context_stalest_feature_seconds_bucket{name="build_prompt", le="300"} 1550
```

### Grafana Dashboard Example

```promql
# Freshness violation rate (per minute)
rate(fabra_context_freshness_violations_total[5m]) * 60

# Percentage of degraded contexts
sum(rate(fabra_context_freshness_status_total{status="degraded"}[5m])) /
sum(rate(fabra_context_freshness_status_total[5m])) * 100

# 95th percentile stalest feature age
histogram_quantile(0.95, rate(fabra_context_stalest_feature_seconds_bucket[5m]))
```

---

## Best Practices

### 1. Start with Degraded Mode

Begin with `freshness_strict=False` (the default) to understand your baseline freshness before enforcing.

```python
# Phase 1: Monitor
@context(store, freshness_sla="5m")
async def build_prompt(...):
    pass

# After validating metrics, Phase 2: Enforce
@context(store, freshness_sla="5m", freshness_strict=True)
async def build_prompt(...):
    pass
```

### 2. Set Appropriate SLAs

Consider your feature refresh patterns:

| Feature Type | Typical SLA |
|--------------|-------------|
| Real-time events | `30s` - `2m` |
| User preferences | `5m` - `15m` |
| Daily aggregates | `1h` - `24h` |
| Historical data | `1d` or more |

### 3. Handle Strict Mode Gracefully

```python
from fabra.exceptions import FreshnessSLAError

async def safe_build_prompt(user_id: str):
    try:
        return await critical_context(user_id)
    except FreshnessSLAError as e:
        # Log the violation
        logger.warning("Freshness SLA breached", violations=e.violations)
        # Fall back to a simpler context or cached response
        return await fallback_context(user_id)
```

### 4. Alert on Violation Trends

Set up alerts when degraded contexts exceed a threshold:

```yaml
# Prometheus alert rule
- alert: HighContextDegradation
  expr: >
    sum(rate(fabra_context_freshness_status_total{status="degraded"}[5m])) /
    sum(rate(fabra_context_freshness_status_total[5m])) > 0.1
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "More than 10% of contexts are degraded"
```

---

## API Reference

### @context Decorator

```python
def context(
    store: FeatureStore = None,
    max_tokens: int = None,
    freshness_sla: str = None,      # New in v1.5
    freshness_strict: bool = False,  # New in v1.5
    cache_ttl: timedelta = timedelta(minutes=5),
    ...
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `freshness_sla` | `str` | `None` | Max age for features (e.g., "5m", "30s") |
| `freshness_strict` | `bool` | `False` | Raise error on SLA breach |

### Context Meta Fields

| Field | Type | Description |
|-------|------|-------------|
| `freshness_status` | `str` | "guaranteed" or "degraded" |
| `freshness_violations` | `list` | List of violation details |
| `freshness_sla_ms` | `int` | SLA threshold in milliseconds |
| `stale_sources` | `list` | Feature names that exceeded SLA |

### FreshnessSLAError

```python
class FreshnessSLAError(FabraError):
    message: str
    violations: List[Dict[str, Any]]
    # Each violation: {"feature": str, "age_ms": int, "sla_ms": int}
```

---

## Troubleshooting

### Features Always Appear Stale

**Cause**: Feature timestamps not being recorded correctly.

**Solution**: Ensure your features record timestamps when computed:

```python
@feature(entity=User, refresh=timedelta(hours=1))
def user_tier(user_id: str) -> str:
    # Timestamp is automatically recorded by @feature decorator
    return compute_tier(user_id)
```

### Strict Mode Fails Too Often

**Cause**: SLA is too aggressive for your feature refresh rate.

**Solution**: Relax the SLA or increase feature refresh frequency:

```python
# Option 1: Relax SLA
@context(store, freshness_sla="15m", freshness_strict=True)

# Option 2: Refresh features more frequently
@feature(entity=User, refresh=timedelta(minutes=5))  # Was timedelta(hours=1)
```

### Missing Metrics

**Cause**: Prometheus endpoint not exposed.

**Solution**: Ensure the metrics endpoint is running:

```bash
fabra serve features.py  # Exposes /metrics endpoint
```

---

## FAQ

**Q: How do I ensure my AI context uses fresh data?**
A: Add `freshness_sla` to your `@context` decorator: `@context(store, freshness_sla="5m")`. Fabra tracks feature ages and reports violations via `ctx.meta["freshness_violations"]`.

**Q: What happens when features are stale?**
A: By default (degraded mode), context assembly succeeds but `freshness_status` becomes "degraded". Use `freshness_strict=True` to raise `FreshnessSLAError` instead.

**Q: How do I monitor freshness SLA violations?**
A: Fabra exposes Prometheus metrics: `fabra_context_freshness_status_total` (guaranteed/degraded counts), `fabra_context_freshness_violations_total` (per-feature violations).

**Q: What SLA format does Fabra support?**
A: Human-readable durations: `500ms`, `30s`, `5m`, `1h`, `1d`. Decimals supported: `1.5h` = 90 minutes.

**Q: Should I use strict mode or degraded mode?**
A: Start with degraded mode to monitor your baseline. Switch to strict mode for critical contexts after validating your feature refresh rates meet the SLA.

**Q: How do I handle strict mode failures?**
A: Catch `FreshnessSLAError` and fall back to a simpler context or cached response. Log violations for debugging.

---

## Related

- [Context Assembly Guide](context-assembly.md)
- [Context Accountability (v1.4)](context-accountability.md)
- [Troubleshooting](troubleshooting.md)

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "TechArticle",
  "headline": "Freshness SLAs: Data Freshness Guarantees for AI Context",
  "description": "Track and enforce data freshness guarantees for your AI contexts. Degraded mode, strict mode, and Prometheus metrics.",
  "author": {"@type": "Organization", "name": "Fabra Team"},
  "keywords": "freshness sla, data freshness, stale data, ai context, feature freshness",
  "articleSection": "Documentation"
}
</script>
