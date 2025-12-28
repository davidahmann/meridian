from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional


def emit_context_id_json(context_id: str, **fields: Any) -> str:
    """
    Emit a single JSON log line containing `context_id`.

    Returns the JSON string (useful for tests or custom sinks).
    """
    payload: dict[str, Any] = {
        "event": "fabra.context_id",
        "context_id": context_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    text = json.dumps(payload, ensure_ascii=False, default=str)
    logging.getLogger("fabra").info(text)
    return text


def emit_context_ref_json(
    context_id: str,
    *,
    record_hash: Optional[str] = None,
    content_hash: Optional[str] = None,
    **fields: Any,
) -> str:
    """
    Emit a single JSON log line containing `context_id` and (optionally) integrity hashes.

    `record_hash` is the durable, content-addressed reference for a CRS-001 record.
    """

    payload: dict[str, Any] = {
        "event": "fabra.context_ref",
        "context_id": context_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    if record_hash is not None:
        payload["record_hash"] = record_hash
    if content_hash is not None:
        payload["content_hash"] = content_hash

    text = json.dumps(payload, ensure_ascii=False, default=str)
    logging.getLogger("fabra").info(text)
    return text


def emit_structured(
    logger: logging.Logger, context_id: str, **fields: Any
) -> dict[str, Any]:
    """
    Emit via standard `logging` using an easy-to-index `extra` payload.
    """
    payload = {"context_id": context_id, **fields}
    logger.info("fabra.context_id", extra={"fabra": payload})
    return payload


def emit_structured_ref(
    logger: logging.Logger,
    context_id: str,
    *,
    record_hash: Optional[str] = None,
    content_hash: Optional[str] = None,
    **fields: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"context_id": context_id, **fields}
    if record_hash is not None:
        payload["record_hash"] = record_hash
    if content_hash is not None:
        payload["content_hash"] = content_hash
    logger.info("fabra.context_ref", extra={"fabra": payload})
    return payload
