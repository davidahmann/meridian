from __future__ import annotations
import pytest
from meridian.graph import DependencyResolver


def test_parse_dependencies() -> None:
    resolver = DependencyResolver()
    template = "Hello {user.name}, your score is {user.score}."
    deps = resolver.parse_dependencies(template)
    assert deps == {"user.name", "user.score"}


def test_parse_dependencies_empty() -> None:
    resolver = DependencyResolver()
    assert resolver.parse_dependencies("Just text") == set()


@pytest.mark.asyncio
async def test_resolve_template() -> None:
    resolver = DependencyResolver()
    template = "Hello {name}"
    rendered = await resolver.resolve(template, {"name": "Alice"})
    assert rendered == "Hello Alice"


@pytest.mark.asyncio
async def test_execute_dag_with_mock_store() -> None:
    from unittest.mock import MagicMock, AsyncMock

    mock_store = MagicMock()
    # Mock registry feature lookup
    mock_feature = MagicMock()
    mock_feature.entity_name = "User"
    mock_store.registry.features.get.return_value = mock_feature

    # Mock get_online_features to return async result
    mock_store.get_online_features = AsyncMock(
        return_value={"my_feature": "mock_value"}
    )

    resolver = DependencyResolver(store=mock_store)

    template = "Value is {my_feature}"
    result = await resolver.execute_dag(template, "u1")

    assert result == "Value is mock_value"
    mock_store.get_online_features.assert_called()
