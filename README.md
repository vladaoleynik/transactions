# Transactions

Async event processing service for transaction events. Ingests events over HTTP, queues them for background processing, converts amounts to USD, and exposes read APIs for user summaries and transaction history.

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

## Architecture

```
Client → POST /events → API → Redis Stream → Worker → PostgreSQL
Client → GET /users/{id}/summary|transactions → API → PostgreSQL
Client → GET /metrics → API → Redis (processed counter)
```

### Why Redis Streams

We use Redis Streams as a buffer between the HTTP ingest event path and the worker. The API only needs a fast, durable hand-off (`XADD`); FX conversion and PostgreSQL writes happen asynchronously in the worker.
While Celery is a strong choice for general background jobs (scheduled tasks, chains, many task types, multiple queues). Here we have one linear pipeline — accept event → convert FX → persist — and we wanted the queue layer to stay thin:
- **Consumer groups + explicit acks** — `XREADGROUP` / `XACK` give at-least-once delivery with a pending-entry list, so retries do not require a separate retry topic;
- **Operational simplicity** — dead-lettered events go to a sibling stream (`transactions:dlq`); the pending list shows stuck messages via `XPENDING`;

Celery would pay off if we added cron-style jobs, heterogeneous tasks, or complex workflows. For a single ordered event stream with explicit at-least-once handling, Streams keeps the code and ops closer to the data path.

### Trade-off: at-least-once delivery, idempotent writes

The queue is **at-least-once**: a message stays pending until the worker acks it. Transient FX or DB failures trigger retry with backoff; after max retries the event is copied to the DLQ and acked.

We do **not** dedupe in Redis. Duplicate deliveries (retries or client replays) are handled in PostgreSQL with `ON CONFLICT DO NOTHING` on event `id`. That keeps ingest and the queue simple, but it means:

- The worker may run FX conversion more than once for the same event id before the first insert wins.
- Metrics count **processing attempts**, not unique events inserted.

Exactly-once end-to-end would need transactional outbox, idempotent consumer fencing, or a heavier broker — more complexity than this service needs today.

### At ~10× load

If we were building for high load from the start, **Temporal** would be the first choice over Redis Streams plus a hand-rolled worker loop. Temporal models each event as a **durable workflow** with first-class retries, timeouts, and visibility — the kind of reliability we bolt on manually today (backoff, DLQ, pending lists):

- **Durable execution** — workflow state survives worker crashes and deploys; no custom retry counters or “message stays pending until ack” logic in application code.
- **Built-in observability** — workflow history, stuck-run detection, and replay for debugging replace ad-hoc logging and `XPENDING` inspection.
- **Idempotency by design** — workflow ids map naturally to event ids; activities can be retried safely with explicit policies instead of hoping Postgres dedup catches every duplicate FX call.
- **External calls as activities** — Frankfurter FX lookup and DB persist become separate steps with independent retry/timeout rules, which fits this pipeline without writing a mini orchestrator.

That comes with real cost: a Temporal cluster (or cloud), worker SDK integration, and a steeper learning curve than `XADD` / `XREADGROUP`. For the current scope, Redis Streams is the lighter fit; Temporal is what we’d reach for when reliability and scale requirements are known upfront.

**With the current stack**, rough order of changes before a full re-architect:

1. **Scale workers horizontally** — run multiple worker replicas in the same consumer group with distinct `CONSUMER_NAME` values; Redis distributes stream entries across consumers.
2. **Share FX rate cache** — move the in-memory Frankfurter cache to Redis so replicas do not each cold-call the API under new currencies.
3. **Tune batching** — increase worker `read_batch` size and consider parallel processing per batch (today one message is handled at a time in a sync loop).
4. **Postgres** — connection pool sizing.

If load and operational burden outgrow that, migrate the pipeline to Temporal rather than layering more custom queue logic on Redis.

## Project layout

```
app/
  main.py         # FastAPI application (POST /events, read APIs, metrics, health)
  worker.py       # Stream consumer with retry/backoff
  config.py       # Settings (pydantic-settings)
  database.py     # SQLModel engine + session
  models.py       # Transaction table
  schemas.py      # Request/response DTOs
  queue.py        # Redis Streams publish/consume/dead-letter
  rates.py        # FX conversion (Frankfurter API)
  processing.py   # Dedup + persist logic
  queries.py      # Read-side queries
tests/
  test_api.py           # ingest, read APIs, metrics
  test_processing.py    # dedup + currency conversion
  test_worker.py        # retry / dead-letter behaviour
  integration/          # Postgres + Redis (testcontainers)
.github/workflows/ci.yml
.pre-commit-config.yaml
docker-compose.yml
Dockerfile
Makefile
pyproject.toml
uv.lock
```

## License

Private / unlicensed.
