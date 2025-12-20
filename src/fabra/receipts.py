from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from fabra.context import generate_context_id, get_environment, get_fabra_version
from fabra.config import get_duckdb_path
from fabra.models import (
    AssemblyDecisions,
    ContextRecord,
    IntegrityMetadata,
    LineageMetadata,
)
from fabra.store.offline import DuckDBOfflineStore
from fabra.utils.integrity import compute_content_hash, compute_record_hash


@dataclass(frozen=True)
class RecordedReceipt:
    context_id: str
    record: ContextRecord


class ReceiptRecorder:
    """
    Persist CRS-001 Context Records as "receipts" from places that don't use @context.

    This is intentionally thin: it stores a durable, verifiable record with
    `content` as "what the model saw" and `inputs` for supplemental metadata.
    """

    def __init__(
        self,
        *,
        offline_store: Optional[Any] = None,
        duckdb_path: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> None:
        if offline_store is not None:
            self._offline_store = offline_store
        else:
            path = duckdb_path or get_duckdb_path()
            _ensure_parent_dir(path)
            self._offline_store = DuckDBOfflineStore(database=path)
        self._environment = environment or get_environment()

    async def record(
        self,
        *,
        context_function: str,
        content: str,
        inputs: Optional[dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        schema_version: str = "1.0.0",
    ) -> RecordedReceipt:
        if not hasattr(self._offline_store, "log_record"):
            raise RuntimeError("offline_store does not support log_record()")

        record = _build_record(
            context_function=context_function,
            content=content,
            inputs=inputs,
            created_at=created_at,
            schema_version=schema_version,
            environment=self._environment,
        )

        await self._offline_store.log_record(record)
        return RecordedReceipt(context_id=record.context_id, record=record)

    def record_sync(
        self,
        *,
        context_function: str,
        content: str,
        inputs: Optional[dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        schema_version: str = "1.0.0",
    ) -> RecordedReceipt:
        if not hasattr(self._offline_store, "log_record"):
            raise RuntimeError("offline_store does not support log_record()")

        record = _build_record(
            context_function=context_function,
            content=content,
            inputs=inputs,
            created_at=created_at,
            schema_version=schema_version,
            environment=self._environment,
        )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._offline_store.log_record(record))
            return RecordedReceipt(context_id=record.context_id, record=record)

        # If we're already inside an event loop (common in async apps/tests),
        # do NOT block waiting for persistence. Schedule it and return the receipt.
        loop.create_task(self._offline_store.log_record(record))
        return RecordedReceipt(context_id=record.context_id, record=record)


def _estimate_tokens(text: str) -> int:
    # Tokenizers vary; this is a conservative, deterministic approximation.
    return max(0, len(text.split()))


def _ensure_parent_dir(file_path: str) -> None:
    if file_path == ":memory:":
        return
    import os

    parent = os.path.dirname(file_path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _build_record(
    *,
    context_function: str,
    content: str,
    inputs: Optional[dict[str, Any]],
    created_at: Optional[datetime],
    schema_version: str,
    environment: str,
) -> ContextRecord:
    now = created_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    context_id = generate_context_id()

    content_hash = compute_content_hash(content)
    temp_integrity = IntegrityMetadata(record_hash="", content_hash=content_hash)

    lineage = LineageMetadata(
        features_used=[],
        retrievers_used=[],
        indexes_used=[],
        code_version=None,
        fabra_version=get_fabra_version(),
        assembly_latency_ms=0.0,
        estimated_cost_usd=0.0,
    )

    record = ContextRecord(
        context_id=context_id,
        created_at=now,
        environment=environment,
        schema_version=schema_version,
        inputs=inputs or {},
        context_function=context_function,
        content=content,
        token_count=_estimate_tokens(content),
        features=[],
        retrieved_items=[],
        assembly=AssemblyDecisions(),
        lineage=lineage,
        integrity=temp_integrity,
    )

    record.integrity.record_hash = compute_record_hash(record)

    # Optional signing (attestation over record_hash)
    try:
        from fabra.utils.signing import (
            get_signature_mode,
            get_signing_key,
            get_signing_key_id,
            sign_record_hash,
        )

        if get_signature_mode() != "off":
            key = get_signing_key()
            if key is not None:
                key_id = get_signing_key_id()
                sig = sign_record_hash(
                    record.integrity.record_hash, key=key, key_id=key_id
                )
                record.integrity.signed_at = sig.signed_at
                record.integrity.signing_key_id = sig.signing_key_id
                record.integrity.signature = sig.signature
    except Exception:
        record.integrity.signed_at = None
        record.integrity.signing_key_id = None
        record.integrity.signature = None
    return record


def _safe_json(value: Any, *, max_chars: int = 50_000) -> str:
    s = json.dumps(value, default=str, ensure_ascii=False)
    if len(s) > max_chars:
        return s[:max_chars] + "…"
    return s
