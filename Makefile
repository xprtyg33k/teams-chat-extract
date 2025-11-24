.PHONY: help setup lint format test run-sample clean

help:
	@echo "Available targets:"
	@echo "  setup       - Create virtual environment and install dependencies"
	@echo "  lint        - Run linter (ruff)"
	@echo "  format      - Format code (black)"
	@echo "  test        - Run unit tests with coverage"
	@echo "  run-sample  - Run sample export (requires Azure credentials)"
	@echo "  clean       - Remove virtual environment, cache files, and output files"

setup:
	python -m venv .venv
	.venv/Scripts/pip install --upgrade pip
	.venv/Scripts/pip install -r requirements.txt

lint:
	python -m ruff check teams_chat_export.py tests/

format:
	python -m black teams_chat_export.py tests/

test:
	python -m pytest tests/ -v --cov=teams_chat_export --cov-report=html --cov-report=term

run-sample:
	@echo "Example command (replace with your values):"
	@echo "python teams_chat_export.py --tenant-id YOUR_TENANT_ID --client-id YOUR_CLIENT_ID --since 2025-06-01 --until 2025-11-15 --participants \"User Name\" --format json --output out/sample.json"

clean:
	rm -rf .venv __pycache__ .pytest_cache .coverage htmlcov out output.* .token_cache.bin
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

