import pytest

from fabra.context import EvidencePersistenceError, context


class _FailingOfflineStore:
    async def log_record(self, record):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")

    async def log_context(self, **_kwargs):  # type: ignore[no-untyped-def]
        return None


class _NoRecordOfflineStore:
    async def log_context(self, **_kwargs):  # type: ignore[no-untyped-def]
        return None


class _StubStore:
    def __init__(self, offline_store):  # type: ignore[no-untyped-def]
        self.offline_store = offline_store


@pytest.mark.asyncio
async def test_evidence_required_fails_without_record_persistence(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FABRA_ENV", "production")
    monkeypatch.setenv("FABRA_EVIDENCE_MODE", "required")

    store = _StubStore(_FailingOfflineStore())

    @context(store, name="t")
    async def t(user_id: str) -> str:
        return f"user={user_id}"

    with pytest.raises(EvidencePersistenceError):
        await t(user_id="u1")


@pytest.mark.asyncio
async def test_evidence_best_effort_surfaces_failure_in_meta(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FABRA_ENV", "development")
    monkeypatch.setenv("FABRA_EVIDENCE_MODE", "best_effort")

    store = _StubStore(_FailingOfflineStore())

    @context(store, name="t")
    async def t(user_id: str) -> str:
        return f"user={user_id}"

    ctx = await t(user_id="u1")
    assert ctx.meta["evidence_mode"] == "best_effort"
    assert ctx.meta["evidence_persisted"] is False
    assert "evidence_error" in ctx.meta


@pytest.mark.asyncio
async def test_evidence_required_fails_when_store_does_not_support_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FABRA_ENV", "production")
    monkeypatch.setenv("FABRA_EVIDENCE_MODE", "required")

    store = _StubStore(_NoRecordOfflineStore())

    @context(store, name="t")
    async def t(user_id: str) -> str:
        return f"user={user_id}"

    with pytest.raises(EvidencePersistenceError):
        await t(user_id="u1")
