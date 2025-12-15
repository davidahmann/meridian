#!/usr/bin/env bash
#
# CI Parity Runner
# ===============
# Runs a subset of checks in a way that closely matches GitHub Actions:
# - disables rich/ANSI output for stable help assertions
# - uses hermetic DuckDB paths per subprocess
# - explicitly runs the incident-path smoke test (demo/show/diff/verify + restart)
# - runs unit + e2e tests under Python 3.11
# - runs mypy under Python 3.9 (to catch syntax regressions)
#
# Usage:
#   bash scripts/ci_parity.sh
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export NO_COLOR=1
export TERM=dumb

TMPDIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMPDIR" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "== CI parity =="
echo "root:   $ROOT_DIR"
echo "tmp:    $TMPDIR"
echo "no_color: ${NO_COLOR}"
echo "term:     ${TERM}"
echo

PY311="$(uv python find 3.11)"
PY39="$(uv python find 3.9)"

echo "== Python versions =="
echo "py311: $PY311"
echo "py39:  $PY39"
echo

echo "== Unit + E2E (Python 3.11) =="
uv run --isolated -p "$PY311" --extra dev pytest -q tests/unit tests/e2e
echo

echo "== mypy (Python 3.9) =="
uv run --isolated -p "$PY39" --extra dev mypy .
echo

echo "== Quickstart smoke (restart durability) =="
FABRA_SMOKE_DUCKDB_PATH="$TMPDIR/quickstart_smoke.duckdb" uv run --isolated -p "$PY311" --extra dev python scripts/ci/quickstart_smoke.py
echo

echo "== Quickstart smoke (evidence required) =="
FABRA_SMOKE_DUCKDB_PATH="$TMPDIR/quickstart_smoke_required.duckdb" FABRA_EVIDENCE_MODE=required uv run --isolated -p "$PY311" --extra dev python scripts/ci/quickstart_smoke.py
echo

echo "== Record diff (local receipts, no server) =="
FABRA_SMOKE_DUCKDB_PATH="$TMPDIR/record_diff_local.duckdb" uv run --isolated -p "$PY311" --extra dev python scripts/ci/record_diff_local_smoke.py
echo

echo "== GTM validation (source install, Python 3.11 venv) =="
PYTHON_BIN="$PY311" bash scripts/validate_gtm_checks.sh
echo

echo "== 30-second quickstart (PyPI install, Python 3.11 venv) =="
PYTHON_BIN="$PY311" FABRA_INSTALL_MODE=pypi bash scripts/test_30_second_quickstart.sh all
echo

echo "CI parity OK"
