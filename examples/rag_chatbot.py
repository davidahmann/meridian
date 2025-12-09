import asyncio
from datetime import timedelta
from meridian.core import FeatureStore, entity, feature
from meridian.context import context, Context, ContextItem
from meridian.retrieval import retriever

# Initialize Store
store = FeatureStore()


# --- 1. Define Entities ---
@entity(store)
class User:
    user_id: str


# --- 2. Define Features ---
@feature(entity=User, refresh=timedelta(hours=1))
def user_tier(user_id: str) -> str:
    # Simulate DB lookup
    # In reality: return await db.get_user_tier(user_id)
    return "premium" if hash(user_id) % 2 == 0 else "free"


@feature(entity=User)
def support_history(user_id: str) -> list[str]:
    # Simulate fetching last 3 tickets
    return [
        "Issue #101: Login failure",
        "Issue #98: Billing question",
        "Issue #45: Feature request",
    ]


# --- 3. Define Retrieval ---
@retriever(name="knowledge_base", cache_ttl=timedelta(seconds=300))  # type: ignore[untyped-decorator]
async def search_docs(query: str, top_k: int = 3) -> list[str]:
    # Simulate Semantic Search (pgvector)
    # In reality: return await store.vector_search("docs", query, top_k)
    print(f"    [Retriever] Searching for: '{query}'")
    return [
        "Meridian allows defining token budgets for context.",
        "Use @retriever to define vector search pipelines.",
        "Features can be cached in Redis for low latency.",
    ][:top_k]


# --- 4. Define Context Assembly ---
@context(store, max_tokens=200)  # Small budget to demonstrate dropping
async def chat_context(user_id: str, query: str) -> Context:
    # 1. Fetch personalization features
    # Note: get_online_features returns a dict, we extract values
    features = await store.get_online_features(
        "User", user_id, ["user_tier", "support_history"]
    )
    tier = features.get("user_tier", "free")
    history = features.get("support_history", [])

    # 2. Fetch relevant docs
    docs = await search_docs(query)

    # 3. Assemble Items
    items = [
        # Priority 0: Must have (System Prompt)
        ContextItem(content="You are a helpful assistant.", priority=0, required=True),
        # Priority 1: User Info (Important for tone)
        ContextItem(content=f"User Tier: {tier}", priority=1, required=True),
        # Priority 2: Retrieved Docs (Core content)
        ContextItem(content="Context:\n" + "\n".join(docs), priority=2, required=True),
        # Priority 3: History (Nice to have, drop if budget exceeded)
        ContextItem(
            content="History:\n" + "\n".join(str(h) for h in history),
            priority=3,
            required=False,
        ),
    ]
    # Mypy complains that we return list but signature says Context.
    # The decorator handles the conversion at runtime.
    return items  # type: ignore[return-value]


# --- 5. Main Execution ---
async def main() -> None:
    user_id = "user_123"

    query = "How does context work?"

    print(f"--- Building Context for {user_id} ---")
    ctx = await chat_context(user_id, query)

    print("\n--- Final Assembled Context ---")
    print(ctx.content)
    print("\n--- Metadata ---")
    print(f"Status: {ctx.meta.get('status')}")
    print(f"Dropped Items: {ctx.meta.get('dropped_items')}")


if __name__ == "__main__":
    asyncio.run(main())
