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
async def test_execute_dag_stub() -> None:
    resolver = DependencyResolver()
    # Should use stub data "mock_value_for_X"
    template = "Value is {my_feature}"
    result = await resolver.execute_dag(template, "u1")
    assert result == "Value is mock_value_for_my_feature"
