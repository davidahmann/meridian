#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import signal
import secrets
import subprocess  # nosec B404
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ContextRun:
    context_id: str
    raw: dict


def _append_summary(line: str) -> None:
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _wait_for_health(port: int, timeout_s: float = 30.0) -> None:
    url = f"http://127.0.0.1:{port}/health"
    start = time.time()
    while True:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:  # nosec B310
                if resp.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            pass
        if time.time() - start > timeout_s:
            raise RuntimeError(f"Timed out waiting for health endpoint: {url}")
        time.sleep(0.25)


def _post_context(port: int, user_id: str, query: str) -> ContextRun:
    url = f"http://127.0.0.1:{port}/v1/context/chat_context"
    payload = json.dumps({"user_id": user_id, "query": query}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_error: Exception | None = None
    for _ in range(10):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                data = json.loads(resp.read().decode("utf-8"))
            break
        except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
            last_error = e
            time.sleep(0.5)
    else:
        raise RuntimeError(
            f"Context POST failed after retries: {last_error}"
        ) from last_error
    context_id = data.get("id")
    if not isinstance(context_id, str) or not context_id:
        raise RuntimeError(f"Missing context id in response: {data}")
    return ContextRun(context_id=context_id, raw=data)


def _run_cli(*args: str) -> None:
    cmd = [sys.executable, "-m", "fabra.cli", *args]
    subprocess.run(cmd, check=True)  # nosec B603


def _terminate_demo(proc: subprocess.Popen[str], timeout_s: float = 10.0) -> None:
    if proc.poll() is not None:
        return

    if os.name == "nt":
        proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
    else:
        proc.send_signal(signal.SIGINT)

    start = time.time()
    while proc.poll() is None and time.time() - start < timeout_s:
        time.sleep(0.1)

    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> int:
    default_port = 12000 + secrets.randbelow(40001)
    port = int(os.getenv("FABRA_SMOKE_PORT", str(default_port)))
    duckdb_path = os.getenv(
        "FABRA_SMOKE_DUCKDB_PATH", str(Path.cwd() / f".fabra-smoke-{port}.duckdb")
    )

    started_at = time.time()
    _append_summary("## Quickstart Smoke Test")
    _append_summary(f"- Port: `{port}`")
    _append_summary(f"- DuckDB: `{duckdb_path}`")

    demo_cmd = [
        sys.executable,
        "-m",
        "fabra.cli",
        "demo",
        "--mode",
        "context",
        "--no-test",
        "--port",
        str(port),
    ]

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["FABRA_DUCKDB_PATH"] = duckdb_path
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(  # nosec B603
            demo_cmd,
            env=env,
            creationflags=creationflags,
        )

        _wait_for_health(port)

        first = _post_context(port, user_id="user_123", query="how do features work?")
        first_elapsed_s = time.time() - started_at
        _append_summary(f"- First Context Record: `{first.context_id}`")
        _append_summary(f"- Time to first Context Record: `{first_elapsed_s:.2f}s`")
        print(f"First context_id: {first.context_id}")

        # Required CLI calls
        _run_cli(
            "context",
            "show",
            first.context_id,
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        )
        _run_cli(
            "context",
            "verify",
            first.context_id,
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        )

        second = _post_context(
            port,
            user_id="user_123",
            query="tell me about retrieval and token budgets",
        )
        print(f"Second context_id: {second.context_id}")

        _run_cli(
            "context",
            "diff",
            first.context_id,
            second.context_id,
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--json",
        )

        # Persistence check: restart server and ensure the record is still retrievable.
        _append_summary("- Restarting server to validate durability")
        _terminate_demo(proc)
        proc = None

        proc = subprocess.Popen(  # nosec B603
            demo_cmd,
            env=env,
            creationflags=creationflags,
        )
        _wait_for_health(port)

        _run_cli(
            "context",
            "show",
            first.context_id,
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        )
        _run_cli(
            "context",
            "verify",
            first.context_id,
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        )

        return 0
    finally:
        if proc is not None:
            _terminate_demo(proc)
        try:
            db_path = Path(duckdb_path)
            db_path.unlink(missing_ok=True)
            Path(str(db_path) + ".wal").unlink(missing_ok=True)
            Path(str(db_path) + ".shm").unlink(missing_ok=True)
        except Exception as e:
            print(f"Warning: failed to delete duckdb: {e}")


if __name__ == "__main__":
    raise SystemExit(main())
