"""
Fabra Production Example: Real Vector Search with pgvector.

This demonstrates production-ready context assembly with:
- Real pgvector retriever (requires OPENAI_API_KEY for embeddings)
- Environment-aware store configuration
- Proper error handling for missing API keys
- Full lineage tracking

Prerequisites:
    export OPENAI_API_KEY=your-key
    export FABRA_ENV=production  # Optional: uses Postgres+Redis
    # OR run locally with DuckDB (default)

Run:
    fabra serve examples/production_context.py

Test:
    curl -X POST localhost:8000/v1/context/chat_context \
      -H "Content-Type: application/json" \
      -d '{"user_id":"user_123","query":"how do features work?"}'

Note: This example will work in development mode (DuckDB) but the
retriever requires OPENAI_API_KEY to generate embeddings.
"""

import os
from datetime import timedelta
from typing import List

from fabra.core import FeatureStore, entity, feature
from fabra.context import context, ContextItem
from fabra.retrieval import retriever

# =============================================================================
# Environment Configuration
# =============================================================================

# Check for required API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    import warnings

    warnings.warn(
        "OPENAI_API_KEY not set. Vector search will not work. "
        "Set the environment variable to enable embeddings.",
        UserWarning,
    )

# Initialize store - automatically uses appropriate backends based on FABRA_ENV
store = FeatureStore()


# =============================================================================
# Entity and Features
# =============================================================================


@entity(store)
class User:
    """User entity for personalization."""

    user_id: str


@feature(entity=User, refresh=timedelta(hours=1))
def user_tier(user_id: str) -> str:
    """
    User subscription tier.

    In production, this would query your database.
    For this example, we use a simple hash-based value.
    """
    # Replace with actual database query in production:
    # return db.query("SELECT tier FROM users WHERE id = ?", user_id)
    return "premium" if hash(user_id) % 2 == 0 else "free"


@feature(entity=User, refresh=timedelta(minutes=5))
def user_engagement_score(user_id: str) -> float:
    """
    User engagement score (0-100).

    In production, this would be computed from user activity data.
    """
    # Replace with actual computation in production
    h = abs(hash(user_id + "engagement"))
    return round((h % 10000) / 100, 2)


# =============================================================================
# Production Retriever (Real Vector Search)
# =============================================================================


@retriever(index="knowledge_base", top_k=5, cache_ttl=timedelta(minutes=5))
async def search_knowledge_base(query: str) -> List[dict]:
    """
    Search the knowledge base using pgvector.

    This retriever is "magic wired" to the `knowledge_base` index.
    The `index=` parameter connects it to pgvector automatically.

    Prerequisites:
    1. Create the index: fabra index create knowledge_base --dimension 1536
    2. Index documents: fabra index add knowledge_base --file docs.jsonl
    3. Set OPENAI_API_KEY for embeddings

    The function body is not executed - Fabra handles the search.
    """
    pass  # Auto-wired to pgvector


# =============================================================================
# Context Assembly
# =============================================================================


@context(
    store,
    name="chat_context",
    max_tokens=4000,
    freshness_sla="5m",
)
async def chat_context(user_id: str, query: str) -> List[ContextItem]:
    """
    Assemble context for a chat response.

    This demonstrates production-ready context assembly:
    1. User features with freshness tracking
    2. Real vector search (when OPENAI_API_KEY is set)
    3. Priority-based token budgeting
    4. Full lineage for compliance
    """
    # Get user features
    tier = user_tier(user_id)
    score = user_engagement_score(user_id)

    # Record feature usage for lineage
    from fabra.context import record_feature_usage
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    record_feature_usage("user_tier", user_id, tier, now, "compute")
    record_feature_usage("user_engagement_score", user_id, score, now, "compute")

    # Search knowledge base (requires OPENAI_API_KEY)
    docs = []
    if OPENAI_API_KEY:
        try:
            docs = await search_knowledge_base(query)
        except Exception as e:
            # Graceful degradation if vector search fails
            import logging

            logging.warning(f"Vector search failed: {e}. Continuing without docs.")
    else:
        # Fallback message when API key is not set
        docs = [
            {"content": "(Vector search disabled - set OPENAI_API_KEY)", "score": 0}
        ]

    # Build context items with priorities
    items = [
        # System prompt (highest priority, required)
        ContextItem(
            content="You are a helpful AI assistant. Provide accurate, "
            "concise answers based on the provided context.",
            priority=100,
            required=True,
            source_id="system_prompt",
        ),
        # User context (high priority)
        ContextItem(
            content=f"User Profile:\n"
            f"- Tier: {tier}\n"
            f"- Engagement Score: {score}",
            priority=90,
            required=False,
            source_id="user_features",
        ),
        # User query (required)
        ContextItem(
            content=f"User Query: {query}",
            priority=100,
            required=True,
            source_id="user_query",
        ),
    ]

    # Add retrieved documents (medium priority, truncated first if over budget)
    if docs:
        doc_content = "Relevant Documentation:\n" + "\n".join(
            f"- {d.get('content', d)}" for d in docs[:5]
        )
        items.append(
            ContextItem(
                content=doc_content,
                priority=50,
                required=False,
                source_id="retrieved_docs",
            )
        )

    return items


# =============================================================================
# Simpler Context (No Retrieval)
# =============================================================================


@context(store, name="simple_context", max_tokens=500)
async def simple_context(user_id: str) -> List[ContextItem]:
    """
    Simple context with just features (no retrieval).

    Use this when you don't need document retrieval.
    """
    tier = user_tier(user_id)

    from fabra.context import record_feature_usage
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    record_feature_usage("user_tier", user_id, tier, now, "compute")

    return [
        ContextItem(
            content="Provide a brief, helpful response.",
            priority=100,
            required=True,
        ),
        ContextItem(
            content=f"User tier: {tier}",
            priority=90,
            required=True,
        ),
    ]


# =============================================================================
# Main Entry Point
# =============================================================================


if __name__ == "__main__":
    import asyncio

    async def demo() -> None:
        print("=" * 60)
        print("Fabra Production Context Example")
        print("=" * 60)
        print()

        if not OPENAI_API_KEY:
            print("WARNING: OPENAI_API_KEY not set.")
            print("Vector search will be disabled.")
            print("Set the key to enable: export OPENAI_API_KEY=your-key")
            print()

        # Test context assembly
        print("Testing context assembly...")
        ctx = await chat_context("user_123", "how do features work?")

        print(f"Context ID: {ctx.id}")
        print(f"Freshness: {ctx.meta.get('freshness_status')}")
        print(f"Token Usage: {ctx.meta.get('token_usage')}")
        print()

        if ctx.lineage:
            print(f"Features Used: {len(ctx.lineage.features_used)}")
            for f in ctx.lineage.features_used:
                print(f"  - {f.feature_name}: {f.value}")
            print()

        print("Content Preview:")
        print("-" * 40)
        print(ctx.content[:500] + "..." if len(ctx.content) > 500 else ctx.content)
        print()

        print("=" * 60)
        print("Run the server with: fabra serve examples/production_context.py")
        print("=" * 60)

    asyncio.run(demo())
