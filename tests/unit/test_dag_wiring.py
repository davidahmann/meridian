import pytest
from typing import List, Dict, Any
from meridian.core import FeatureStore, feature, entity
from meridian.retrieval import retriever
from meridian.store import InMemoryOnlineStore

# We need to define classes inside test or setup to avoid module-level errors
# Or define a global store for this test module
store = FeatureStore(online_store=InMemoryOnlineStore())


@entity(store=store)
class User:
    user_id: str


@feature(User, store=store)
def name(user_id: str) -> str:
    return "Alice"


@feature(User, store=store)
def age(user_id: str) -> int:
    return 30


@retriever(backend="custom", name="echo_retriever")  # type: ignore
async def echo_retriever(query: str, entity_id: str) -> List[Dict[str, Any]]:
    return [{"content": f"Echo: {query}"}]


# Register retriever manually to ensure binding
store.register_retriever(echo_retriever)


@pytest.mark.asyncio
async def test_dag_wiring_success() -> None:
    # Seed Online Store
    await store.online_store.set_online_features(
        "User", "u1", {"name": "Alice", "age": 30}
    )

    results = await echo_retriever(query="Hello {name}", entity_id="u1")

    assert len(results) == 1
    assert results[0]["content"] == "Echo: Hello Alice"


@pytest.mark.asyncio
async def test_dag_complex_dependencies() -> None:
    await store.online_store.set_online_features(
        "User", "u2", {"name": "Bob", "age": 99}
    )

    # Multiple deps
    results = await echo_retriever(query="{name} is {age} years old", entity_id="u2")

    assert results[0]["content"] == "Echo: Bob is 99 years old"
