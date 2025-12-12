"""
Cryptographic integrity utilities for Context Records.

Provides hashing and verification functions to ensure tamper-evident
Context Records as part of the Inference Context Ledger.
"""

from __future__ import annotations
import hashlib
import json
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from fabra.models import ContextRecord


def compute_content_hash(content: str) -> str:
    """
    Compute SHA256 hash of content string.

    Args:
        content: The text content to hash.

    Returns:
        SHA256 hash as hex string prefixed with 'sha256:'.
    """
    hash_bytes = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{hash_bytes}"


def compute_record_hash(record: "ContextRecord") -> str:
    """
    Compute SHA256 hash of a ContextRecord's canonical JSON representation.

    The hash is computed over all fields EXCEPT the integrity.record_hash field
    itself, ensuring the hash can be verified after storage.

    Args:
        record: The ContextRecord to hash.

    Returns:
        SHA256 hash as hex string prefixed with 'sha256:'.
    """
    # Convert to dict and remove the record_hash field for hashing
    record_dict = record.model_dump(mode="json")

    # Remove the record_hash from integrity (we're computing it)
    if "integrity" in record_dict and "record_hash" in record_dict["integrity"]:
        record_dict["integrity"]["record_hash"] = ""

    # Create canonical JSON (sorted keys, no extra whitespace)
    canonical_json = json.dumps(record_dict, sort_keys=True, separators=(",", ":"))

    hash_bytes = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return f"sha256:{hash_bytes}"


def verify_record_integrity(record: "ContextRecord") -> bool:
    """
    Verify that a ContextRecord's hash matches its contents.

    Args:
        record: The ContextRecord to verify.

    Returns:
        True if the record_hash matches the computed hash, False otherwise.
    """
    expected_hash = compute_record_hash(record)
    return record.integrity.record_hash == expected_hash


def verify_content_integrity(record: "ContextRecord") -> bool:
    """
    Verify that a ContextRecord's content_hash matches its content.

    Args:
        record: The ContextRecord to verify.

    Returns:
        True if the content_hash matches the computed hash, False otherwise.
    """
    expected_hash = compute_content_hash(record.content)
    return record.integrity.content_hash == expected_hash


def compute_hashes_for_record(record_dict: Dict[str, Any]) -> Dict[str, str]:
    """
    Compute both content_hash and record_hash for a record dictionary.

    This is useful when building a ContextRecord before the IntegrityMetadata
    is complete.

    Args:
        record_dict: Dictionary representation of a ContextRecord (without integrity.record_hash).

    Returns:
        Dictionary with 'content_hash' and 'record_hash' keys.
    """
    content = record_dict.get("content", "")
    content_hash = compute_content_hash(content)

    # Ensure record_hash is empty for computation
    if "integrity" in record_dict:
        record_dict["integrity"]["record_hash"] = ""
        record_dict["integrity"]["content_hash"] = content_hash

    canonical_json = json.dumps(record_dict, sort_keys=True, separators=(",", ":"))
    record_hash = f"sha256:{hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()}"

    return {
        "content_hash": content_hash,
        "record_hash": record_hash,
    }
