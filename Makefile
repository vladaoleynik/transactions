.PHONY: setup run

setup:
	uv sync --all-groups
	@test -f .env || cp .env.template .env

run:
	docker compose up --build
