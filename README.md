# Transactions

Async event processing service for transaction events. Ingests events over HTTP, queues them for background processing, converts amounts to USD, and exposes read APIs for user summaries and transaction history.

**Status:** ingest and processing pipeline implemented; read APIs and metrics are not implemented yet.

## Stack

| Component | Choice |
|-----------|--------|
| API | FastAPI (`fastapi dev`) |
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
make test         # pytest (in-memory SQLite via test fixtures; no Docker required)
make pre-commit   # all pre-commit hooks
```

Processing tests use in-memory SQLite. `conftest.py` patches `persist_transaction` with a test-only SQLite implementation (`tests/db.py`); production code remains PostgreSQL-only.

Fix formatting issues:

```bash
uv run ruff format .
```

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on push and pull requests to `main`, `develop`, and all other branches:

1. Ruff check and format check
2. mypy
3. pytest

## Manual commands

```bash
# Install runtime + dev dependencies and git hooks
uv sync --all-groups
uv run pre-commit install

# Run API locally (requires postgres + redis running)
uv run fastapi dev app/main.py

# Stop Docker services
docker compose down
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8000 | HTTP API |
| `postgres` | 5432 | Persistent storage |
| `redis` | 6379 | Event queue (Redis Streams) |
| `worker` | — | Stream consumer: FX conversion, dedup, persist |

## Configuration

Copy the template and adjust for local development:

```bash
cp .env.template .env
```

Docker Compose sets `DATABASE_URL` and `REDIS_URL` for the `api` and `worker` services. See `.env.template` for all supported variables.

## Project layout

```
app/
  main.py         # FastAPI application (POST /events)
  worker.py       # Stream consumer with retry/backoff
  config.py       # Settings (pydantic-settings)
  database.py     # SQLModel engine + session
  models.py       # TransactionEvent + Transaction table
  queue.py        # Redis Streams publish/consume/dead-letter
  rates.py        # FX conversion (Frankfurter API)
  processing.py   # Dedup + persist logic
tests/
  test_processing.py  # dedup + currency conversion
  test_worker.py      # retry / dead-letter behaviour
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
