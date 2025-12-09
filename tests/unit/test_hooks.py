import pytest
from typing import List, Dict, Any
from meridian.hooks import Hook, HookManager


class TestHook(Hook):
    def __init__(self) -> None:
        self.before_called = False
        self.after_called = False

    async def before_feature_retrieval(
        self, entity_name: str, entity_id: str, features: List[str]
    ) -> None:
        self.before_called = True

    async def after_feature_retrieval(
        self,
        entity_name: str,
        entity_id: str,
        features: List[str],
        result: Dict[str, Any],
    ) -> None:
        self.after_called = True
        result["injected"] = "value"


@pytest.mark.asyncio
async def test_hook_manager_flow() -> None:
    manager = HookManager()
    hook = TestHook()
    manager.register(hook)

    # Test Before
    await manager.trigger_before_retrieval("user", "123", ["f1"])
    assert hook.before_called is True

    # Test After
    result: Dict[str, Any] = {"f1": 1.0}
    await manager.trigger_after_retrieval("user", "123", ["f1"], result)
    assert hook.after_called is True
    assert result["injected"] == "value"


@pytest.mark.asyncio
async def test_hook_error_handling() -> None:
    # Ensure individual hook errors don't crash the manager
    class ErrorHook(Hook):
        async def before_feature_retrieval(self, *args: Any, **kwargs: Any) -> None:
            raise ValueError("Boom")

    manager = HookManager()
    manager.register(ErrorHook())

    # Should not raise
    await manager.trigger_before_retrieval("user", "123", ["f1"])
