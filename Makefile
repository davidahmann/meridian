.PHONY: help setup install test lint format clean ui serve docker-up docker-down pre-commit

help:
	@echo "Available commands:"
	@echo "  make setup       - Create venv and install dependencies"
	@echo "  make install     - Install dependencies only"
	@echo "  make test        - Run tests"
	@echo "  make lint        - Run linters (ruff, mypy)"
	@echo "  make format      - Run formatters (ruff)"
	@echo "  make clean       - Clean build artifacts"
	@echo "  make ui          - Run Meridian UI"
	@echo "  make serve       - Run Meridian Server (TUI)"
	@echo "  make docker-up   - Start local production stack"
	@echo "  make docker-down - Stop local production stack"
	@echo "  make pre-commit  - Run all pre-commit hooks"
	@echo "  make build       - Build python distribution"

setup:
	uv venv
	uv pip install -e ".[dev,ui]"
	uv run pre-commit install
	cd src/meridian/ui-next && npm install

install:
	uv pip install -e ".[dev,ui]"

test:
	uv run pytest

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
	uv run meridian ui examples/basic_features.py

serve:
	uv run meridian serve examples/basic_features.py

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
