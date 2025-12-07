import os
import time
import requests
import subprocess  # nosec
import sys
import tempfile

# 1. Define the content for the temporary feature file
FEATURE_FILE_CONTENT = """
from meridian.core import entity, feature, FeatureStore
from datetime import timedelta

# We need a store instance for the decorators to work if not using global context
# effectively. But the CLI `meridian serve` initializes the app.
# The `basic_features.py` example suggests we just define classes.
# Let's follow the `examples/basic_features.py` pattern if I could see it,
# but based on my code reading of `core.py`:
# The decorators @entity and @feature register themselves to a VALID store.
# `meridian serve` likely loads the module.
# Wait, `core.py` decorators require a `store` argument or the entity to have one.
# CLI usage usually implies a global or module-level store that is passed to `create_app`.

store = FeatureStore()

@entity(store=store, id_column="user_id")
class User:
    pass

@feature(entity=User, store=store, refresh="1m")
def user_name_upper(user_id: str) -> str:
    return f"USER_{user_id.upper()}"

@feature(entity=User, store=store, refresh="1m")
def name_length(user_id: str) -> int:
    return len(user_id)
"""


def run_test() -> None:
    print("🚀 Starting Meridian UAT Smoke Test...")

    # 2. Create Temporary File
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(FEATURE_FILE_CONTENT)
        tmp_path = tmp.name

    print(f"📝 Created temporary feature file: {tmp_path}")

    proc = None
    try:
        # 3. Start Meridian Server
        # Assumptions: 'meridian' is in the PATH or accessible via 'python -m meridian'
        cmd = [
            sys.executable,
            "-m",
            "meridian.cli",
            "serve",
            tmp_path,
            "--port",
            "8008",
        ]
        print(f"▶️  Running command: {' '.join(cmd)}")

        # Use a new process group so we can potentialy kill everything later
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # nosec

        # 4. Wait for Health Check
        print("⏳ Waiting for server to become healthy...")
        healthy = False
        for i in range(20):
            try:
                resp = requests.get("http://localhost:8008/health", timeout=1)
                if resp.status_code == 200:
                    healthy = True
                    print("✅ Server is healthy!")
                    break
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(1)  # Wait 1s between retries

        if not healthy:
            print("❌ Server failed to start within 20 seconds.")
            # Print stderr
            stdout, stderr = proc.communicate(timeout=1)
            print(f"Server Stdout:\n{stdout.decode()}")
            print(f"Server Stderr:\n{stderr.decode()}")
            sys.exit(1)

        # 5. Perform Feature Request
        print("📡 sending feature request...")
        payload = {
            "entity_name": "User",
            "entity_id": "alice",
            "features": ["user_name_upper", "name_length"],
        }

        # NOTE: `meridian serve` usually expects API key or dev mode.
        # server.py says if MERIDIAN_API_KEY is unset, it returns "dev-mode" and allows usage.
        resp = requests.post("http://localhost:8008/features", json=payload, timeout=2)

        if resp.status_code != 200:
            print(f"❌ Request failed with status {resp.status_code}")
            print(f"Response: {resp.text}")
            sys.exit(1)

        data = resp.json()
        print(f"📥 Received Data: {data}")

        # 6. Assertions
        expected = {"user_name_upper": "USER_ALICE", "name_length": 5}
        # Note: The response might contain fewer keys if features are missing/errored
        # Based on server.py it returns a dict.

        if data == expected:
            print("✅ Assertions Passed: Response matches expected output.")
        else:
            print(f"❌ Assertions Failed. Expected {expected}, got {data}")
            sys.exit(1)

    except Exception as e:
        print(f"💥 Exception occurred: {e}")
        if proc:
            print(f"Server return code: {proc.poll()}")
            # _, stderr = proc.communicate()
            # print(stderr.decode())

    finally:
        # 7. Cleanup
        print("🧹 Cleaning up...")
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()

        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            print("🗑️  Deleted temporary file.")


if __name__ == "__main__":
    run_test()
