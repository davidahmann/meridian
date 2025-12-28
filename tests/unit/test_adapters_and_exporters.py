from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import pytest

from fabra.adapters.langchain import FabraLangChainCallbackHandler
from fabra.adapters.openai import wrap_openai_call
from fabra.exporters.logging import (
    emit_context_id_json,
    emit_context_ref_json,
    emit_structured,
)
from fabra.receipts import ReceiptRecorder
from fabra.store.offline import DuckDBOfflineStore
from fabra.utils.integrity import verify_content_integrity, verify_record_integrity


@pytest.mark.asyncio
async def test_receipt_recorder_persists_verifiable_record(tmp_path: Path) -> None:
    db_path = tmp_path / "receipts.duckdb"
    store = DuckDBOfflineStore(database=str(db_path))
    recorder = ReceiptRecorder(offline_store=store, environment="test")

    receipt = await recorder.record(
        context_function="unit.test",
        content="hello world",
        inputs={"k": "v"},
    )

    record = await store.get_record(receipt.context_id)
    assert record is not None
    assert record.context_id == receipt.context_id
    assert record.environment == "test"
    assert verify_content_integrity(record)
    assert verify_record_integrity(record)
    assert record.inputs.get("k") == "v"


@pytest.mark.asyncio
async def test_langchain_callback_creates_receipt_and_emits(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db_path = tmp_path / "langchain.duckdb"
    store = DuckDBOfflineStore(database=str(db_path))
    recorder = ReceiptRecorder(offline_store=store, environment="test")
    handler = FabraLangChainCallbackHandler(
        recorder=recorder, emit_logs=True, emit_otel=False
    )

    class _Gen:
        def __init__(self, text: str) -> None:
            self.text = text

    class _Resp:
        def __init__(self) -> None:
            self.generations = [[_Gen("ok")]]

    run_id = "run_123"
    with caplog.at_level(logging.INFO, logger="fabra"):
        handler.on_llm_start({"name": "test"}, ["prompt a"], run_id=run_id)
        handler.on_llm_end(_Resp(), run_id=run_id)

    ctx_id = handler.get_context_id(run_id)
    assert isinstance(ctx_id, str) and ctx_id.startswith("ctx_")

    # A JSON line should have been emitted to the "fabra" logger.
    assert any("fabra.context_id" in rec.message for rec in caplog.records)

    record = await _wait_for_record(store, ctx_id)
    assert record is not None
    assert verify_record_integrity(record)


@pytest.mark.asyncio
async def test_openai_wrapper_records_receipt(tmp_path: Path) -> None:
    db_path = tmp_path / "openai.duckdb"
    store = DuckDBOfflineStore(database=str(db_path))
    recorder = ReceiptRecorder(offline_store=store, environment="test")

    def fake_openai_call(*_args: object, **_kwargs: object) -> dict:
        return {"output_text": "hello"}

    wrapped = wrap_openai_call(
        fake_openai_call,
        recorder=recorder,
        context_function="openai.responses.create",
        emit_logs=False,
        emit_otel=False,
        return_context_id=True,
    )

    result, ctx_id = wrapped(input="hi", model="gpt-test")
    assert result["output_text"] == "hello"
    assert ctx_id.startswith("ctx_")

    record = await _wait_for_record(store, ctx_id)
    assert record is not None
    assert verify_record_integrity(record)
    assert "model" in json.dumps(record.inputs)


def test_logging_exporters_emit_json_and_structured(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="fabra"):
        text = emit_context_id_json("ctx_test", source="unit")
    payload = json.loads(text)
    assert payload["context_id"] == "ctx_test"
    assert payload["source"] == "unit"

    with caplog.at_level(logging.INFO, logger="fabra"):
        text_ref = emit_context_ref_json(
            "ctx_test",
            record_hash="sha256:" + ("a" * 64),
            content_hash="sha256:" + ("b" * 64),
            source="unit",
        )
    payload_ref = json.loads(text_ref)
    assert payload_ref["event"] == "fabra.context_ref"
    assert payload_ref["context_id"] == "ctx_test"
    assert payload_ref["record_hash"].startswith("sha256:")
    assert payload_ref["content_hash"].startswith("sha256:")

    logger = logging.getLogger("fabra.test")
    out = emit_structured(logger, "ctx_test2", source="unit")
    assert out["context_id"] == "ctx_test2"


async def _wait_for_record(
    store: DuckDBOfflineStore,
    context_id: str,
    *,
    timeout_s: float = 2.0,
) -> object:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        record = await store.get_record(context_id)
        if record is not None:
            return record
        await asyncio_sleep(0.01)
    raise AssertionError(f"Timed out waiting for record: {context_id}")


async def asyncio_sleep(seconds: float) -> None:
    # Avoid importing asyncio at module import time if not needed by all tests.
    import asyncio

    await asyncio.sleep(seconds)
