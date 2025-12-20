"""
Optional signing for CRS-001 Context Records.

MVP implementation uses HMAC-SHA256 over the record_hash. This provides a
tamper-evident, offline-verifiable attestation when the signing key is held
by the verifier (symmetric).

Future-friendly: the interface keeps room for asymmetric signatures (e.g. Ed25519)
without changing record structure.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional


SignatureMode = Literal["off", "optional", "required"]


@dataclass(frozen=True)
class SignatureResult:
    signing_key_id: str
    signed_at: datetime
    signature: str


def get_signature_mode() -> SignatureMode:
    configured = os.environ.get("FABRA_SIGNATURE_MODE", "optional").strip().lower()
    if configured in ("off", "disabled", "false", "0"):
        return "off"
    if configured in ("required", "require", "1", "true"):
        return "required"
    return "optional"


def _decode_key(raw: str) -> bytes:
    raw = raw.strip()
    if raw.startswith("base64:"):
        return base64.b64decode(raw[len("base64:") :].strip())
    if raw.startswith("hex:"):
        return bytes.fromhex(raw[len("hex:") :].strip())
    return raw.encode("utf-8")


def get_signing_key() -> Optional[bytes]:
    key = os.environ.get("FABRA_SIGNING_KEY")
    if not key:
        return None
    return _decode_key(key)


def get_signing_key_id() -> str:
    return os.environ.get("FABRA_SIGNING_KEY_ID", "default").strip() or "default"


def sign_record_hash(record_hash: str, *, key: bytes, key_id: str) -> SignatureResult:
    signed_at = datetime.now(timezone.utc)
    msg = f"fabra:crs-001:{record_hash}".encode("utf-8")
    mac = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return SignatureResult(
        signing_key_id=key_id,
        signed_at=signed_at,
        signature=f"hmac-sha256:{mac}",
    )


def verify_record_hash_signature(
    record_hash: str, *, signature: str, key: bytes
) -> bool:
    if not signature.startswith("hmac-sha256:"):
        return False
    expected = sign_record_hash(record_hash, key=key, key_id="ignored").signature
    return hmac.compare_digest(signature, expected)
