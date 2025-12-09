import pytest
from meridian.context import context


@pytest.mark.asyncio
async def test_context_versioning() -> None:
    @context(name="v2_ctx", version="v2")
    async def v2_func() -> str:
        return "v2 content"

    ctx = await v2_func()
    assert ctx.version == "v2"

    @context(name="default_ver_ctx")
    async def ver_func() -> str:
        return "content"

    ctx_def = await ver_func()
    assert ctx_def.version == "v1"
