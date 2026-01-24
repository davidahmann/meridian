#!/bin/bash
# Verify Release Workflow Locally
# ===============================
# Simulates the steps in .github/workflows/release.yml to ensure success.
#
# Usage:
#   ./scripts/verify_release_workflow.sh
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Simulating Release Workflow ===${NC}"

# Check for uv
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: uv not found. Please install uv using 'pip install uv'${NC}"
    exit 1
fi

# 1. Simulate Tag Verification
echo -e "\n${BLUE}1. Verifying Tag vs Version...${NC}"
# Use grep/sed for portability across python versions (tomllib is 3.11+)
PYPROJECT_VERSION=$(grep -m1 'version = ' pyproject.toml | sed 's/version = "//;s/"//')
EXPECTED_TAG="v${PYPROJECT_VERSION}"
echo -e "Project version: ${PYPROJECT_VERSION}"
echo -e "Expected tag:    ${EXPECTED_TAG}"
echo -e "${GREEN}✓ Version parsing verified${NC}"

# 2. Setup Clean Environment
echo -e "\n${BLUE}2. Setting up clean environment...${NC}"
TMPDIR=$(mktemp -d)
echo -e "Using temp dir: ${TMPDIR}"
# Match .github/workflows/release.yml (Python 3.11)
uv python install 3.11
uv venv --python 3.11 "$TMPDIR/.venv"
source "$TMPDIR/.venv/bin/activate"

echo -e "Installing dependencies..."
# Use the locked dependency set to avoid "latest dependency" drift in verification.
uv sync --active --frozen --extra dev --extra ui

# 3. Run Tests (as per workflow: pytest --ignore=tests/ui)
echo -e "\n${BLUE}3. Running Tests (pytest --ignore=tests/ui)...${NC}"
if uv run --active pytest --ignore=tests/ui; then
    echo -e "${GREEN}✓ Tests passed${NC}"
else
    echo -e "${RED}✗ Tests failed${NC}"
    exit 1
fi

# 4. Build Package
echo -e "\n${BLUE}4. Building Package...${NC}"
uv run --active --with build python -m build --outdir "$TMPDIR/dist"

if [ -f "$TMPDIR/dist/fabra_ai-${PYPROJECT_VERSION}-py3-none-any.whl" ]; then
    echo -e "${GREEN}✓ Wheel created: fabra_ai-${PYPROJECT_VERSION}-py3-none-any.whl${NC}"
else
    echo -e "${RED}✗ Wheel missing${NC}"
    ls -l "$TMPDIR/dist"
    exit 1
fi

if [ -f "$TMPDIR/dist/fabra_ai-${PYPROJECT_VERSION}.tar.gz" ]; then
    echo -e "${GREEN}✓ Source tarball created: fabra_ai-${PYPROJECT_VERSION}.tar.gz${NC}"
else
    echo -e "${RED}✗ Source tarball missing${NC}"
    exit 1
fi

# Cleanup
echo -e "\n${BLUE}5. Cleanup...${NC}"
rm -rf "$TMPDIR"
echo -e "${GREEN}Cleanup complete.${NC}"

echo -e "\n${GREEN}=== RELEASE SIMULATION SUCCESS ===${NC}"
echo -e "Ready for tag: ${EXPECTED_TAG}"
