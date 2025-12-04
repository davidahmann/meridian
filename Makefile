.PHONY: setup install test lint format clean

setup:
	uv venv
	uv pip install -e ".[dev]"
	uv run pre-commit install

install:
	uv pip install -e ".[dev]"

test:
	pytest tests

lint:
	ruff check .
	mypy .

format:
	ruff format .

clean:
	rm -rf build dist .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
