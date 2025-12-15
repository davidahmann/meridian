#!/usr/bin/env python3
from __future__ import annotations

import os
import secrets
import subprocess  # nosec B404
import sys
from pathlib import Path


def _run_cli(*args: str) -> None:
    cmd = [sys.executable, "-m", "fabra.cli", *args]
    subprocess.run(cmd, check=True)  # nosec B603


def _create_two_receipts(duckdb_path: str) -> tuple[str, str]:
    env = os.environ.copy()
    env["FABRA_DUCKDB_PATH"] = duckdb_path
    code = r"""
import os
from fabra.receipts import ReceiptRecorder

path = os.environ["FABRA_DUCKDB_PATH"]
recorder = ReceiptRecorder(duckdb_path=path)
a = recorder.record_sync(context_function="smoke.local_diff", content="prompt A", inputs={"answer": "a"})
b = recorder.record_sync(context_function="smoke.local_diff", content="prompt B", inputs={"answer": "b"})
print(a.context_id)
print(b.context_id)
"""
    result = subprocess.run(  # nosec B603
        [sys.executable, "-c", code],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    import re

    matches = re.findall(r"(ctx_[0-9a-fA-F-]+)", result.stdout)
    # Preserve order, drop duplicates
    ids: list[str] = []
    for m in matches:
        if m not in ids:
            ids.append(m)
    if len(ids) < 2:
        raise RuntimeError(f"Expected 2 context_ids, got output: {result.stdout}")
    return ids[-2], ids[-1]


def main() -> int:
    duckdb_path = os.getenv(
        "FABRA_SMOKE_DUCKDB_PATH",
        str(Path.cwd() / f".fabra-record-diff-{secrets.token_hex(6)}.duckdb"),
    )
    try:
        a_id, b_id = _create_two_receipts(duckdb_path)

        _run_cli(
            "context",
            "diff",
            a_id,
            b_id,
            "--local",
            "--duckdb-path",
            duckdb_path,
            "--json",
        )
        return 0
    finally:
        try:
            db_path = Path(duckdb_path)
            db_path.unlink(missing_ok=True)
            Path(str(db_path) + ".wal").unlink(missing_ok=True)
            Path(str(db_path) + ".shm").unlink(missing_ok=True)
        except Exception as e:
            print(f"Warning: failed to delete duckdb: {e}")


if __name__ == "__main__":
    raise SystemExit(main())
