.PHONY: help setup install test test-unit test-integration test-perf test-e2e test-ui test-all \
        quickstart-smoke evidence-required-smoke record-diff-smoke worker-smoke \
        fixtures-verify incident-bundle-smoke ci-parity clean-dev-store \
        lint format clean ui serve docker-up docker-down pre-commit build \
        build-ui build-docs build-playground build-docker build-all

help:
	@echo "Available commands:"
	@echo ""
	@echo "Setup & Install:"
	@echo "  make setup          - Create venv and install dependencies"
	@echo "  make install        - Install dependencies only"
	@echo ""
	@echo "Testing:"
	@echo "  make test           - Run unit/integration tests (excludes e2e)"
	@echo "  make test-unit      - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-perf      - Run performance tests"
	@echo "  make test-e2e       - Run end-to-end tests"
	@echo "  make test-ui        - Run Playwright UI tests"
	@echo "  make test-all       - Run all tests including e2e/ui"
	@echo "  make quickstart-smoke - Run incident-path smoke (demo/show/diff/verify)"
	@echo "  make evidence-required-smoke - Run quickstart smoke with FABRA_EVIDENCE_MODE=required"
	@echo "  make record-diff-smoke - Diff two local CRS-001 receipts (no server)"
	@echo "  make worker-smoke   - Run worker trigger-stream integration test (Docker required)"
	@echo "  make fixtures-verify - Verify golden record/diff fixtures"
	@echo "  make ci-parity      - Run CI-parity checks locally"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           - Run linters (ruff, mypy, bandit)"
	@echo "  make format         - Run formatters (ruff)"
	@echo "  make pre-commit     - Run all pre-commit hooks"
	@echo ""
	@echo "Building:"
	@echo "  make build          - Build Python distribution"
	@echo "  make build-ui       - Build Next.js UI"
	@echo "  make build-docs     - Build documentation site"
	@echo "  make build-playground - Build playground"
	@echo "  make build-docker   - Build Docker images"
	@echo "  make build-all      - Build all artifacts"
	@echo ""
	@echo "Running:"
	@echo "  make ui             - Run Fabra UI"
	@echo "  make serve          - Run Fabra Server (TUI)"
	@echo "  make docker-up      - Start local production stack"
	@echo "  make docker-down    - Stop local production stack"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          - Clean build artifacts"
	@echo "  make clean-dev-store - Remove default dev DuckDB file (~/.fabra/fabra.duckdb)"

setup:
	uv venv
	uv pip install -e ".[dev,ui]"
	uv run pre-commit install
	cd src/fabra/ui-next && npm install

install:
	uv pip install -e ".[dev,ui]"

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit -v

test-integration:
	uv run pytest tests/integration -v

test-perf:
	uv run pytest tests/perf -v

test-e2e:
	uv run pytest tests/e2e -m e2e -v

test-ui:
	uv run pytest tests/ui -m e2e -v

test-all:
	uv run pytest tests/ -m "" -v

quickstart-smoke:
	uv run python scripts/ci/quickstart_smoke.py

evidence-required-smoke:
	FABRA_EVIDENCE_MODE=required uv run python scripts/ci/quickstart_smoke.py

record-diff-smoke:
	uv run python scripts/ci/record_diff_local_smoke.py

worker-smoke:
	uv run pytest -q tests/integration/test_worker_streams.py

ci-parity:
	bash scripts/ci_parity.sh

fixtures-verify:
	uv run pytest tests/unit/test_golden_fixtures.py -q

incident-bundle-smoke:
	uv run python scripts/ci/incident_bundle_smoke.py

clean-dev-store:
	rm -f ~/.fabra/fabra.duckdb ~/.fabra/fabra.duckdb.wal ~/.fabra/fabra.duckdb.shm

lint:
	uv run ruff check .
	uv run mypy .
	uv run bandit -c pyproject.toml -r src

format:
	uv run ruff format .

clean:
	rm -rf build dist .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +

ui:
	uv run fabra ui examples/basic_features.py

serve:
	uv run fabra serve examples/basic_features.py

docker-up:
	docker compose up -d

docker-down:
	docker compose down

prod-up:
	docker-compose -f examples/production/docker-compose.prod.yml up --build

prod-down:
	docker-compose -f examples/production/docker-compose.prod.yml down

pre-commit:
	uv run pre-commit run --all-files

build:
	uv build

build-ui:
	cd src/fabra/ui-next && npm run build

build-docs:
	cd docs-site && npm run build

build-playground:
	cd playground && npm run build

build-docker:
	docker build -t fabra:latest .
	docker build -t fabra:quickstart-test -f Dockerfile.quickstart-test .

build-all: build build-ui build-docs build-playground build-docker
	@echo "All builds completed successfully!"
