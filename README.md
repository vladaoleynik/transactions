# Transactions

Async event processing service for transaction events. Ingests events over HTTP, queues them for background processing, converts amounts to USD, and exposes read APIs for user summaries and transaction history.

**Status:** bootstrapped — infrastructure and project layout are in place; business logic is not implemented yet.

## Stack

| Component | Choice |
|-----------|--------|
| API | FastAPI + Uvicorn |
| Queue | Redis Streams |
| Database | PostgreSQL |
| ORM | SQLModel (sync) |
| FX rates | Frankfurter API |
| Dependencies | [uv](https://docs.astral.sh/uv/) |
| Orchestration | Docker Compose |
| Lint / format | [Ruff](https://docs.astral.sh/ruff/) |
| Type checking | [mypy](https://mypy-lang.org/) |
| Git hooks | [pre-commit](https://pre-commit.com/) |

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

## Quick start

```bash
make setup   # install dependencies, create .env, install pre-commit hooks
make run     # start postgres, redis, api, and worker
```

Verify the API:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

API docs: http://localhost:8000/docs

## Development

After `make setup`, [pre-commit](https://pre-commit.com/) runs automatically on each commit:

- Ruff (lint + format check)
- mypy
- pytest

Run the same checks manually:

```bash
make check        # lint + test (matches CI)
make lint         # ruff + mypy only
make test         # pytest only
make pre-commit   # all pre-commit hooks
```

Fix formatting issues:

```bash
uv run ruff format .
```

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on push and pull requests to `main`/`master`:

1. Ruff check and format check
2. mypy
3. pytest

## Manual commands

```bash
# Install runtime + dev dependencies and git hooks
uv sync --all-groups
uv run pre-commit install

# Run API locally (requires postgres + redis running)
uv run uvicorn app.main:app --reload

# Stop Docker services
docker compose down
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8000 | HTTP API |
| `postgres` | 5432 | Persistent storage |
| `redis` | 6379 | Event queue (Redis Streams) |
| `worker` | — | Background consumer (stub) |

## Configuration

Copy the template and adjust for local development:

```bash
cp .env.template .env
```

Docker Compose sets `DATABASE_URL` and `REDIS_URL` for the `api` and `worker` services. See `.env.template` for all supported variables.

## Project layout

```
app/
  main.py         # FastAPI application
  worker.py       # Stream consumer (stub)
  config.py       # Settings (pydantic-settings)
  database.py     # SQLModel engine + session
  models.py       # Database models (to be implemented)
  queue.py        # Redis Streams client (to be implemented)
  rates.py        # FX conversion (to be implemented)
  processing.py   # Dedup + persist logic (to be implemented)
tests/
.github/workflows/ci.yml
.pre-commit-config.yaml
docker-compose.yml
Dockerfile
Makefile
pyproject.toml
uv.lock
```

## Planned architecture

```
Client → POST /events → API → Redis Stream → Worker → PostgreSQL
Client → GET /users/{id}/summary|transactions → API → PostgreSQL
```

## License

Private / unlicensed.
