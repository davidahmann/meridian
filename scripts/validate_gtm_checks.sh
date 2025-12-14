#!/usr/bin/env bash
#
# Consolidated GTM validation runner.
#
# What it does:
# - Runs the 30-second quickstart check (PyPI and/or source install)
# - Validates key CLI commands (doctor + context show/diff/export + deploy dry-run)
# - Validates that key example files are serve-able and return expected JSON
#
# Usage:
#   bash scripts/validate_gtm_checks.sh
#
# Env:
#   VALIDATE_INSTALL_MODE=pypi|source|both   (default: both)
#   VALIDATE_UI=0|1                         (default: 0) - UI requires Node/npm
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${VALIDATE_INSTALL_MODE:-source}"
VALIDATE_UI="${VALIDATE_UI:-0}"

echo "== GTM validation =="
echo "root:  ${ROOT_DIR}"
echo "mode:  ${MODE}"
echo "ui:    ${VALIDATE_UI}"
echo

run_quickstart() {
  local install_mode="$1"
  echo "== 30-second quickstart (${install_mode}) =="
  FABRA_INSTALL_MODE="$install_mode" bash "${ROOT_DIR}/scripts/test_30_second_quickstart.sh"
  echo
}

ensure_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: missing required command: ${cmd}" >&2
    exit 1
  fi
}

ensure_cmd python3
ensure_cmd curl

if [[ "$MODE" == "pypi" || "$MODE" == "both" ]]; then
  run_quickstart "pypi"
fi
if [[ "$MODE" == "source" || "$MODE" == "both" ]]; then
  run_quickstart "source"
fi

echo "== CLI + examples validation (source install) =="

TMPDIR="$(mktemp -d)"
VENV_DIR="${TMPDIR}/venv"

cleanup() {
  set +e
  for pid in ${PIDS:-}; do
    kill "$pid" >/dev/null 2>&1 || true
    wait "$pid" >/dev/null 2>&1 || true
  done
  rm -rf "$TMPDIR" >/dev/null 2>&1 || true
}
trap cleanup EXIT

PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m venv "$VENV_DIR"
PY="${VENV_DIR}/bin/python"
PIP="${VENV_DIR}/bin/pip"
FABRA="${VENV_DIR}/bin/fabra"

"$PIP" install -U pip >/dev/null
"$PIP" install -e "$ROOT_DIR" >/dev/null

echo "== CLI help coverage =="
assert_help_contains() {
  local label="$1"
  local pattern="$2"
  shift 2
  local out
  out="$(NO_COLOR=1 TERM=dumb "$@" 2>&1)" || { echo "ERROR: ${label} failed"; echo "$out"; exit 1; }
  local stripped
  stripped="$(printf '%s' "$out" | sed -E $'s/\x1B\\[[0-9;]*[A-Za-z]//g')"
  echo "$stripped" | grep -q -- "$pattern" || {
    echo "ERROR: ${label} missing: ${pattern}"
    echo "$stripped"
    exit 1
  }
}

assert_help_contains "fabra --help" "demo" "$FABRA" --help
assert_help_contains "fabra --help" "context" "$FABRA" --help
assert_help_contains "fabra context --help" "show" "$FABRA" context --help
assert_help_contains "fabra context --help" "export" "$FABRA" context --help
assert_help_contains "fabra context export --help" "--bundle" "$FABRA" context export --help
echo

wait_health() {
  local port="$1"
  for _ in $(seq 1 80); do
    if curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

serve_and_assert_feature() {
  local file="$1"
  local port="$2"
  local url="$3"
  echo "serve: ${file} (${port})"
  FABRA_DUCKDB_PATH="${TMPDIR}/serve-${port}.duckdb" "$FABRA" serve "${ROOT_DIR}/${file}" --port "$port" >/dev/null 2>&1 &
  local pid=$!
  PIDS="${PIDS:-} ${pid}"
  wait_health "$port"
  curl -fsS "$url" | "$PY" -c 'import sys,json; j=json.load(sys.stdin); assert "value" in j'
  kill "$pid" >/dev/null 2>&1 || true
  wait "$pid" >/dev/null 2>&1 || true
}

serve_and_assert_context() {
  local file="$1"
  local port="$2"
  echo "serve: ${file} (${port})"
  FABRA_DUCKDB_PATH="${TMPDIR}/serve-${port}.duckdb" "$FABRA" serve "${ROOT_DIR}/${file}" --port "$port" >/dev/null 2>&1 &
  local pid=$!
  PIDS="${PIDS:-} ${pid}"
  wait_health "$port"
  curl -fsS -X POST "http://127.0.0.1:${port}/v1/context/chat_context" \
    -H "Content-Type: application/json" \
    -d '{"user_id":"user_123","query":"test"}' | "$PY" -c 'import sys,json; j=json.load(sys.stdin); assert "id" in j'
  kill "$pid" >/dev/null 2>&1 || true
  wait "$pid" >/dev/null 2>&1 || true
}

# Example validations
serve_and_assert_feature "examples/demo_features.py" 50101 "http://127.0.0.1:50101/features/user_engagement?entity_id=user_123"
serve_and_assert_context "examples/demo_context.py" 50102
serve_and_assert_feature "examples/basic_features.py" 50103 "http://127.0.0.1:50103/features/user_click_count?entity_id=u1"
serve_and_assert_context "examples/rag_chatbot.py" 50104
serve_and_assert_feature "examples/basic_features_no_keys.py" 50105 "http://127.0.0.1:50105/features/user_click_count?entity_id=u1"
serve_and_assert_context "examples/rag_chatbot_no_keys.py" 50106

# CLI validations against a running demo server
PORT_DEMO=50120
echo "demo: context (${PORT_DEMO})"
DEMO_HELP="$("$FABRA" demo --help 2>&1 || true)"
NO_TEST=()
if echo "$DEMO_HELP" | grep -q -- "--no-test"; then
  NO_TEST=(--no-test)
fi

FABRA_DUCKDB_PATH="${TMPDIR}/demo-${PORT_DEMO}.duckdb" "$FABRA" demo --mode context --port "$PORT_DEMO" "${NO_TEST[@]}" >/dev/null 2>&1 &
DEMO_PID=$!
PIDS="${PIDS:-} ${DEMO_PID}"
wait_health "$PORT_DEMO"

CTX1="$(curl -fsS -X POST "http://127.0.0.1:${PORT_DEMO}/v1/context/chat_context" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user_123","query":"test"}' | "$PY" -c 'import sys,json; print(json.load(sys.stdin)["id"])')"
CTX2="$(curl -fsS -X POST "http://127.0.0.1:${PORT_DEMO}/v1/context/chat_context" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user_123","query":"test 2"}' | "$PY" -c 'import sys,json; print(json.load(sys.stdin)["id"])')"

"$FABRA" doctor --host 127.0.0.1 --port "$PORT_DEMO" >/dev/null
"$FABRA" context list --host 127.0.0.1 --port "$PORT_DEMO" --limit 5 >/dev/null
"$FABRA" context show "$CTX1" --host 127.0.0.1 --port "$PORT_DEMO" >/dev/null
"$FABRA" context diff "$CTX1" "$CTX2" --host 127.0.0.1 --port "$PORT_DEMO" --json >/dev/null
"$FABRA" context verify "$CTX1" --host 127.0.0.1 --port "$PORT_DEMO" >/dev/null
"$FABRA" context export "$CTX1" --host 127.0.0.1 --port "$PORT_DEMO" --format json --output "${TMPDIR}/context.json" >/dev/null
"$PY" -c "import json; json.load(open('${TMPDIR}/context.json'))"

# Incident bundle export (CRS-001 record + hashes)
BUNDLE_PATH="${TMPDIR}/incident_bundle.zip"
"$FABRA" context export "$CTX1" --host 127.0.0.1 --port "$PORT_DEMO" --bundle --output "$BUNDLE_PATH" >/dev/null
"$PY" - <<PY
import json
import zipfile
from pathlib import Path

bundle = Path("${BUNDLE_PATH}")
assert bundle.exists(), f"missing bundle: {bundle}"
with zipfile.ZipFile(bundle, "r") as zf:
    names = set(zf.namelist())
    assert "manifest.json" in names, f"bundle missing manifest.json: {sorted(names)}"
    manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    record_id = manifest["id"]
    assert f"{record_id}.json" in names, f"bundle missing {record_id}.json"

    # When exporting CRS-001 records, the bundle should be self-verifiable.
    if manifest.get("exported_kind") == "record":
        assert "verification_error" not in manifest, manifest.get("verification_error")
        assert manifest.get("stored_content_hash") == manifest.get("computed_content_hash")
        assert manifest.get("stored_record_hash") == manifest.get("computed_record_hash")
PY

# Deploy requirements sanity: no hardcoded fabra>=2.2.0 and includes fabra-ai
DEPLOY_OUT="$("$FABRA" deploy fly --dry-run 2>&1 || true)"
echo "$DEPLOY_OUT" | grep -q "fabra-ai>=" || (echo "ERROR: deploy did not output fabra-ai requirement" >&2; exit 1)
echo "$DEPLOY_OUT" | grep -q "fabra>=2.2.0" && (echo "ERROR: deploy still outputs hardcoded fabra>=2.2.0" >&2; exit 1) || true

if [[ "$VALIDATE_UI" == "1" ]]; then
  echo "ui: starting briefly (may install deps)"
  UI_HELP="$("$FABRA" ui --help 2>&1 || true)"
  UI_ARGS=("$FABRA" ui "${ROOT_DIR}/examples/demo_features.py" --port 50130)
  if echo "$UI_HELP" | grep -q -- "--no-browser"; then
    UI_ARGS+=(--no-browser)
  fi
  "${UI_ARGS[@]}" >/dev/null 2>&1 &
  UI_PID=$!
  PIDS="${PIDS:-} ${UI_PID}"
  sleep 5
  kill "$UI_PID" >/dev/null 2>&1 || true
  wait "$UI_PID" >/dev/null 2>&1 || true
fi

kill "$DEMO_PID" >/dev/null 2>&1 || true
wait "$DEMO_PID" >/dev/null 2>&1 || true

echo
echo "GTM validation OK"
