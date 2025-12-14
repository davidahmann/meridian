#!/bin/bash
# Fabra 30-Second Quickstart Validation Script
#
# Run this on a fresh machine/container to validate the quickstart experience.
# This script tests both Feature Store and Context Store demos.
#
# Usage:
#   ./scripts/test_30_second_quickstart.sh           # Run all tests
#   ./scripts/test_30_second_quickstart.sh features  # Only test Feature Store
#   ./scripts/test_30_second_quickstart.sh context   # Only test Context Store
#
# Notes:
# - In the repo, the equivalent served files are:
#     - examples/demo_features.py
#     - examples/demo_context.py
# - For a true "fresh machine" simulation (PyPI install), we use `fabra demo`,
#   which runs packaged demos with the same behavior as those example files.
#
# Requirements:
#   - Python 3.10+
#   - pip

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PORT_FEATURE=8765  # Use non-standard ports to avoid conflicts
PORT_CONTEXT=8766
TIMEOUT=30
STARTUP_TIMEOUT=${FABRA_STARTUP_TIMEOUT:-20}
MODE=${1:-all}  # all, features, or context
INSTALL_MODE=${FABRA_INSTALL_MODE:-pypi} # pypi|source
PYTHON_BIN=${PYTHON_BIN:-python3}

echo -e "${BLUE}=== Fabra 30-Second Quickstart Validation ===${NC}"
echo -e "Mode: ${MODE}"
echo -e "Port (features): ${PORT_FEATURE}"
echo -e "Port (context):  ${PORT_CONTEXT}"
echo -e "Install: ${INSTALL_MODE}"
echo -e "Python: ${PYTHON_BIN}"
echo ""

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    if [ -n "${SERVER_PID:-}" ]; then
        kill $SERVER_PID 2>/dev/null || true
        wait $SERVER_PID 2>/dev/null || true
    fi
    # Kill any remaining fabra processes on our ports
    if command -v lsof >/dev/null 2>&1; then
        lsof -ti:$PORT_FEATURE | xargs kill -9 2>/dev/null || true
        lsof -ti:$PORT_CONTEXT | xargs kill -9 2>/dev/null || true
    fi
}

trap cleanup EXIT

# Create a clean virtual environment (fresh machine simulation)
TMPDIR=$(mktemp -d)
"$PYTHON_BIN" -m venv "$TMPDIR/venv"
VENV_PY="$TMPDIR/venv/bin/python"
VENV_PIP="$TMPDIR/venv/bin/pip"
VENV_FABRA="$TMPDIR/venv/bin/fabra"

echo -e "${YELLOW}Creating clean venv at ${TMPDIR}/venv...${NC}"
"$VENV_PIP" install -U pip >/dev/null

echo -e "${YELLOW}Installing Fabra (${INSTALL_MODE})...${NC}"
if [ "$INSTALL_MODE" = "source" ]; then
    if [ ! -f "pyproject.toml" ]; then
        echo -e "${RED}ERROR: FABRA_INSTALL_MODE=source requires running from the project root${NC}"
        exit 1
    fi
    "$VENV_PIP" install -e . >/dev/null
else
    "$VENV_PIP" install fabra-ai >/dev/null
fi

# Track total time
TOTAL_START=$(date +%s)

# Function to test Feature Store demo
test_features() {
    echo -e "\n${BLUE}--- Testing Feature Store Demo ---${NC}"
    local START=$(date +%s)
    local LOG="${TMPDIR}/demo_features.log"
    local DUCKDB_PATH="${TMPDIR}/demo_features.duckdb"

    # Start server in background
    echo -e "${YELLOW}Starting demo server (features)...${NC}"
    FABRA_DUCKDB_PATH="${DUCKDB_PATH}" "$VENV_FABRA" demo --mode features --port $PORT_FEATURE >"${LOG}" 2>&1 &
    SERVER_PID=$!

    # Wait for server to be ready (poll health endpoint)
    echo -e "${YELLOW}Waiting for server to be ready...${NC}"
    local max_tries=$((STARTUP_TIMEOUT * 2))
    for i in $(seq 1 "$max_tries"); do
        if curl -fsS "http://127.0.0.1:$PORT_FEATURE/health" >/dev/null 2>&1; then
            echo -e "${GREEN}Server is ready!${NC}"
            break
        fi
        if [ "$i" -eq "$max_tries" ]; then
            echo -e "${RED}ERROR: Server failed to start within ${STARTUP_TIMEOUT} seconds${NC}"
            echo -e "${YELLOW}Last demo logs:${NC}"
            tail -n 80 "${LOG}" || true
            kill $SERVER_PID 2>/dev/null || true
            wait $SERVER_PID 2>/dev/null || true
            unset SERVER_PID
            return 1
        fi
        sleep 0.5
    done

    # Test feature endpoint
    echo -e "${YELLOW}Testing feature endpoint...${NC}"
    RESPONSE=$(curl -fsS "http://127.0.0.1:$PORT_FEATURE/features/user_engagement?entity_id=user_123")
    echo -e "Response: ${RESPONSE}"

    # Validate response has value
    if echo "$RESPONSE" | grep -q '"value"'; then
        echo -e "${GREEN}SUCCESS: Got feature value${NC}"
    else
        echo -e "${RED}FAILURE: No feature value returned${NC}"
        return 1
    fi

    # Validate response has freshness_ms
    if echo "$RESPONSE" | grep -q '"freshness_ms"'; then
        echo -e "${GREEN}SUCCESS: Got freshness_ms${NC}"
    else
        echo -e "${YELLOW}WARNING: No freshness_ms in response${NC}"
    fi

    # Stop server
    kill $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true
    unset SERVER_PID

    local END=$(date +%s)
    local DURATION=$((END - START))
    echo -e "${GREEN}Feature Store test completed in ${DURATION} seconds${NC}"

    if [ $DURATION -gt $TIMEOUT ]; then
        echo -e "${YELLOW}WARNING: Test took longer than ${TIMEOUT} seconds${NC}"
    fi

    return 0
}

# Function to test Context Store demo
test_context() {
    echo -e "\n${BLUE}--- Testing Context Store Demo ---${NC}"
    local START=$(date +%s)
    local LOG="${TMPDIR}/demo_context.log"
    local DUCKDB_PATH="${TMPDIR}/demo_context.duckdb"

    # Start server in background
    echo -e "${YELLOW}Starting demo server (context)...${NC}"
    FABRA_DUCKDB_PATH="${DUCKDB_PATH}" "$VENV_FABRA" demo --mode context --port $PORT_CONTEXT >"${LOG}" 2>&1 &
    SERVER_PID=$!

    # Wait for server to be ready
    echo -e "${YELLOW}Waiting for server to be ready...${NC}"
    local max_tries=$((STARTUP_TIMEOUT * 2))
    for i in $(seq 1 "$max_tries"); do
        if curl -fsS "http://127.0.0.1:$PORT_CONTEXT/health" >/dev/null 2>&1; then
            echo -e "${GREEN}Server is ready!${NC}"
            break
        fi
        if [ "$i" -eq "$max_tries" ]; then
            echo -e "${RED}ERROR: Server failed to start within ${STARTUP_TIMEOUT} seconds${NC}"
            echo -e "${YELLOW}Last demo logs:${NC}"
            tail -n 80 "${LOG}" || true
            kill $SERVER_PID 2>/dev/null || true
            wait $SERVER_PID 2>/dev/null || true
            unset SERVER_PID
            return 1
        fi
        sleep 0.5
    done

    # Test context endpoint
    echo -e "${YELLOW}Testing context endpoint...${NC}"
    RESPONSE=$(curl -fsS -X POST "http://127.0.0.1:$PORT_CONTEXT/v1/context/chat_context" \
        -H "Content-Type: application/json" \
        -d '{"user_id":"user_123","query":"how do features work?"}')

    echo -e "Response (truncated): ${RESPONSE:0:200}..."

    # Validate response has id (context_id)
    if echo "$RESPONSE" | grep -q '"id"'; then
        echo -e "${GREEN}SUCCESS: Got context ID${NC}"
    else
        echo -e "${RED}FAILURE: No context ID returned${NC}"
        return 1
    fi

    # Validate response has content
    if echo "$RESPONSE" | grep -q '"content"'; then
        echo -e "${GREEN}SUCCESS: Got context content${NC}"
    else
        echo -e "${RED}FAILURE: No content returned${NC}"
        return 1
    fi

    # Validate response has meta with freshness_status
    if echo "$RESPONSE" | grep -q '"freshness_status"'; then
        echo -e "${GREEN}SUCCESS: Got freshness_status${NC}"
    else
        echo -e "${YELLOW}WARNING: No freshness_status in response${NC}"
    fi

    # Stop server
    kill $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true
    unset SERVER_PID

    local END=$(date +%s)
    local DURATION=$((END - START))
    echo -e "${GREEN}Context Store test completed in ${DURATION} seconds${NC}"

    if [ $DURATION -gt $TIMEOUT ]; then
        echo -e "${YELLOW}WARNING: Test took longer than ${TIMEOUT} seconds${NC}"
    fi

    return 0
}

# Run tests based on mode
FAILURES=0

if [ "$MODE" = "all" ] || [ "$MODE" = "features" ]; then
    if ! test_features; then
        ((FAILURES++))
    fi
fi

if [ "$MODE" = "all" ] || [ "$MODE" = "context" ]; then
    if ! test_context; then
        ((FAILURES++))
    fi
fi

# Final summary
TOTAL_END=$(date +%s)
TOTAL_DURATION=$((TOTAL_END - TOTAL_START))

echo ""
echo -e "${BLUE}=== Summary ===${NC}"
echo -e "Total time: ${TOTAL_DURATION} seconds"
echo -e "Target: < ${TIMEOUT} seconds"

if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    if [ $TOTAL_DURATION -le $TIMEOUT ]; then
        echo -e "${GREEN}30-second quickstart validated successfully!${NC}"
    else
        echo -e "${YELLOW}Tests passed but took longer than ${TIMEOUT} seconds${NC}"
    fi
    exit 0
else
    echo -e "${RED}${FAILURES} test(s) failed${NC}"
    exit 1
fi
