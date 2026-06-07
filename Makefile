.PHONY: setup run check lint test pre-commit

setup:
	uv sync --all-groups
	@test -f .env || cp .env.template .env
	uv run pre-commit install

run:
	docker compose up --build

check: lint test

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy app tests

test:
	uv run pytest

pre-commit:
	uv run pre-commit run --all-files
