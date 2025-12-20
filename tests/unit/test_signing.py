from __future__ import annotations

from fabra.utils.signing import sign_record_hash, verify_record_hash_signature


def test_sign_and_verify_record_hash_hmac() -> None:
    key = b"super-secret-key"
    record_hash = "sha256:" + ("a" * 64)

    sig = sign_record_hash(record_hash, key=key, key_id="k1")
    assert sig.signature.startswith("hmac-sha256:")
    assert verify_record_hash_signature(record_hash, signature=sig.signature, key=key)

    assert not verify_record_hash_signature(
        record_hash, signature=sig.signature, key=b"wrong"
    )
