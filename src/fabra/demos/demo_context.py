"""
Fabra Demo: Context assembly WITHOUT requiring API keys.

Run:
    fabra demo --mode context

Test (while demo is running):
    curl -X POST localhost:8000/v1/context/chat_context \
      -H "Content-Type: application/json" \
      -d '{"user_id":"user_123","query":"how do features work?"}'
"""

from datetime import timedelta
from typing import Any

from fabra.context import ContextItem, context
from fabra.core import FeatureStore, entity, feature
from fabra.retrieval import retriever
from fabra.store import DuckDBOfflineStore, InMemoryOnlineStore

store = FeatureStore(
    offline_store=DuckDBOfflineStore(),
    online_store=InMemoryOnlineStore(),
)


@entity(store)
class User:
    user_id: str


@feature(entity=User, refresh=timedelta(hours=1))
def user_tier(user_id: str) -> str:
    return "premium" if hash(user_id) % 2 == 0 else "free"


@feature(entity=User, refresh=timedelta(minutes=5))
def user_engagement_score(user_id: str) -> float:
    h = abs(hash(user_id + "engagement"))
    return round((h % 10000) / 100, 2)


@feature(entity=User)
def support_priority(user_id: str) -> str:
    tier = user_tier(user_id)
    score = user_engagement_score(user_id)
    if tier == "premium" and score > 50:
        return "high"
    if tier == "premium" or score > 70:
        return "medium"
    return "normal"


MOCK_DOCS = {
    "features": [
        "Features in Fabra are defined using the @feature decorator.",
        "Features can be materialized to an online store or computed on-demand.",
        "The refresh parameter specifies how often a feature should be recomputed.",
    ],
    "context": [
        "Context assembly in Fabra uses the @context decorator to build prompts.",
        "Token budgeting manages prompt length by dropping low-priority items.",
        "Every context assembly gets a unique ID and full lineage tracking.",
    ],
    "retrieval": [
        "Retrievers in Fabra fetch relevant documents for RAG pipelines.",
        "Auto-wiring connects retrievers to vector indexes when configured.",
        "Retriever usage is tracked in lineage (query, results, latency).",
    ],
    "default": [
        "Fabra is a feature store and context store for ML and AI applications.",
        "Use pip install fabra-ai to get started with Fabra.",
        "Try fabra demo to create your first Context Record.",
    ],
}


@retriever(name="demo_docs", cache_ttl=timedelta(seconds=300))  # type: ignore[untyped-decorator]
async def search_docs(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    import time

    start = time.time()
    query_lower = query.lower()

    if "feature" in query_lower:
        docs = MOCK_DOCS["features"]
    elif "context" in query_lower:
        docs = MOCK_DOCS["context"]
    elif "retriev" in query_lower or "rag" in query_lower:
        docs = MOCK_DOCS["retrieval"]
    else:
        docs = MOCK_DOCS["default"]

    results = [
        {
            "content": doc,
            "score": 0.95 - (i * 0.1),
            "source": f"docs/fabra/{query_lower.split()[0] if query_lower else 'intro'}.md",
        }
        for i, doc in enumerate(docs[:top_k])
    ]

    latency_ms = (time.time() - start) * 1000
    from fabra.context import record_retriever_usage

    record_retriever_usage(
        retriever_name="demo_docs",
        query=query,
        results_count=len(results),
        latency_ms=latency_ms,
    )

    return results


@context(
    store,
    name="chat_context",
    max_tokens=500,
    freshness_sla="5m",
)
async def chat_context(user_id: str, query: str) -> list[ContextItem]:
    tier = user_tier(user_id)
    score = user_engagement_score(user_id)
    priority = support_priority(user_id)

    from datetime import datetime, timezone

    from fabra.context import record_feature_usage

    now = datetime.now(timezone.utc)
    record_feature_usage("user_tier", user_id, tier, now, "compute")
    record_feature_usage("user_engagement_score", user_id, score, now, "compute")
    record_feature_usage("support_priority", user_id, priority, now, "compute")

    docs = await search_docs(query, top_k=3)

    return [
        ContextItem(
            content=(
                "You are a helpful AI assistant for Fabra users. "
                "Be concise and accurate."
            ),
            priority=100,
            required=True,
            source_id="system_prompt",
        ),
        ContextItem(
            content=(
                "User Profile:\n"
                f"- Tier: {tier}\n"
                f"- Engagement Score: {score}\n"
                f"- Support Priority: {priority}"
            ),
            priority=90,
            required=False,
            source_id="user_features",
        ),
        ContextItem(
            content="Relevant Documentation:\n"
            + "\n".join(f"- {d['content']}" for d in docs),
            priority=50,
            required=False,
            source_id="retrieved_docs",
        ),
        ContextItem(
            content=f"User Query: {query}",
            priority=100,
            required=True,
            source_id="user_query",
        ),
    ]
