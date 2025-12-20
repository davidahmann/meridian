---
title: "Integrity & Verification"
description: "How Fabra makes Context Records tamper-evident with content_hash and record_hash, and how to verify records in CI and incidents."
keywords: record hash, content hash, integrity, verification, tamper evident, ai audit trail
---

# Integrity & Verification

Fabra Context Records are designed to be **tamper-evident**.

## Hashes

### `content_hash`
SHA256 of the `content` field (the assembled context string).

### `record_hash`
SHA256 of the canonical JSON of the full CRS-001 Context Record.

For stability, the `record_hash` computation ignores:
- `integrity.record_hash` (self-reference)
- signing fields (`integrity.signature`, `integrity.signed_at`, `integrity.signing_key_id`)

This lets you detect changes to:
- lineage fields
- inputs
- environment metadata
- budgeting decisions

## CLI verification

```bash
fabra context verify <context_id>
```

This verifies:
- `content_hash` matches the content
- `record_hash` matches the full record

If the server does not expose the CRS-001 record endpoint (`/v1/record/<id>`) or the record is missing, `verify` fails (non-zero). That is intentional: you can’t claim a receipt is verifiable if the record is unavailable.

## Evidence modes (no fake receipts)

Fabra can enforce that it never returns a `context_id` unless the CRS-001 record was persisted successfully.

- `FABRA_EVIDENCE_MODE=best_effort` (development default): the request succeeds, but the response metadata indicates whether evidence was persisted.
- `FABRA_EVIDENCE_MODE=required` (production default): if CRS-001 persistence fails, the request fails (no `context_id` returned).

## Optional signing (attestation)

Fabra can optionally sign `record_hash` at write-time, to support offline verification.

- Enable signing by setting `FABRA_SIGNING_KEY`.
  - Supported formats: `hex:<hex>` or `base64:<b64>` (or raw string bytes).
- Control enforcement with `FABRA_SIGNATURE_MODE`:
  - `optional` (default): if a signature is present and a key is available, verify it; otherwise continue
  - `required`: fail verification if signature is missing/invalid or if the key is unavailable
  - `off`: do not sign and do not require signatures

## Incident workflow

- Use `verify` when a ticket involves compliance, chargebacks, audits, or disputes.
- Use `pack` for a copy/paste-friendly ticket attachment:

```bash
fabra context pack <context_id> -o incident.zip
```

- Use `export --bundle` to attach a verifiable artifact outside the running service:

```bash
fabra context export <context_id> --bundle
```

## CI recommendation

Add a clean-environment job that:
- creates 1–2 Context Records
- runs `show`, `diff`, and `verify`
- fails the build if any verification fails
