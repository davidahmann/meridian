"""Playwright test fixtures for Meridian UI testing.

Run with:
    uv run pytest tests/ui/ --headed  # See browser
    uv run pytest tests/ui/           # Headless
"""

import pytest
import subprocess
import time
import socket
import os
import signal
from typing import Generator


def is_port_in_use(port: int) -> bool:
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def wait_for_port(port: int, timeout: int = 30) -> bool:
    """Wait for a port to be available."""
    for _ in range(timeout):
        if is_port_in_use(port):
            return True
        time.sleep(1)
    return False


@pytest.fixture(scope="session")
def ui_server() -> Generator[str, None, None]:
    """Start the Meridian UI server for testing.

    This starts both:
    1. FastAPI backend on port 8502
    2. Next.js frontend on port 8501
    """
    frontend_port = 8501
    api_port = 8502
    base_url = f"http://localhost:{frontend_port}"

    # Check if already running
    if is_port_in_use(frontend_port):
        yield base_url
        return

    # Get paths
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    ui_next_dir = os.path.join(project_root, "src", "meridian", "ui-next")
    features_file = os.path.join(project_root, "examples", "rag_chatbot.py")

    # Start FastAPI backend
    api_process = subprocess.Popen(
        [
            "uv",
            "run",
            "python",
            "-c",
            f"""
import sys
sys.path.insert(0, '{project_root}')
from meridian.ui_server import run_server
run_server('{features_file}', port={api_port}, host='127.0.0.1')
""",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=project_root,
    )

    # Wait for API to start
    if not wait_for_port(api_port, timeout=15):
        api_process.kill()
        raise RuntimeError(f"API server failed to start on port {api_port}")

    # Start Next.js frontend
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev", "--", "-p", str(frontend_port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=ui_next_dir,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
    )

    # Wait for frontend to start
    if not wait_for_port(frontend_port, timeout=30):
        frontend_process.kill()
        api_process.kill()
        raise RuntimeError(f"Next.js server failed to start on port {frontend_port}")

    # Give extra time for Next.js to fully compile
    time.sleep(3)

    yield base_url

    # Cleanup
    try:
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(frontend_process.pid), signal.SIGTERM)
        else:
            frontend_process.terminate()
    except Exception:
        pass

    try:
        api_process.terminate()
        api_process.wait(timeout=5)
    except Exception:
        api_process.kill()


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict) -> dict:
    """Configure browser context for tests."""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }
