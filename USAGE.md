# USAGE

How to set up and run the Rabbit Hole backend — one FastAPI deployable that serves
the **reader** API and, when configured, an **admin generation** trigger
([ADR 0015](docs/adr/0015-one-backend-deployable-http-api.md)). For the request
contracts, see [API.md](API.md).

## Prerequisites

- **uv** (Python 3.12+)
- **Docker** (local Postgres via `docker-compose.yml`)

## Environment variables

Copy the template and edit: `cp .env.example .env`.

### Must-have (the reader backend always needs these)

| Variable | What it is |
| --- | --- |
| `DATABASE_URL` | Postgres DSN for the one database. Holds the Content Graph (Pieces / Topics / Connections) and the reader's own tables (users / sessions / paths); both schemas are auto-migrated on boot ([ADR 0018](docs/adr/0018-one-database-logical-separation.md)). |
| `API_IDENTITY_SECRET` | HMAC key that signs anonymous reader tokens. Set per deployment; a leak lets a holder forge reader identities. |

### Optional — enabling the admin generation trigger

The trigger stays **dormant** unless **both** `LLM_PROVIDER` and `API_ADMIN_TOKEN`
are set; the reader path never imports the generation machinery
([ADR 0016](docs/adr/0016-production-llm-adapter-and-bounded-worker-agents.md)).
When you enable it, the `LLM_*` model values below are also required or boot fails.

| Variable | Default | What it is |
| --- | --- | --- |
| `API_ADMIN_TOKEN` | *(unset → trigger off)* | Operator secret checked on the `X-Admin-Token` header. |
| `LLM_PROVIDER` | *(unset → trigger off)* | Provider key, e.g. `deepseek`. |
| `LLM_API_KEY` | — | Provider API key (required when generation is on). |
| `LLM_MODEL_PRECISE` | — | Model id for structural/judging purposes (required when on). |
| `LLM_MODEL_CREATIVE` | — | Model id for prose purposes (required when on). |
| `LLM_TEMPERATURE_PRECISE` | `0.0` | Sampling temperature for the precise tier. |
| `LLM_TEMPERATURE_CREATIVE` | `1.0` | Sampling temperature for the creative tier. |
| `HARNESS_ROOT` | repo root | Where the authored `harness/` specs and run workspaces live. |
| `HARNESS_FAN_OUT` | `4` | Bounded per-Piece concurrency for the pipeline. |

## Setup — from an empty Postgres to a working `/daily`

Both schemas (Content Graph + consumption) are auto-migrated on boot, so the
only manual step is seeding the Topic taxonomy — content data, not schema.

```bash
# 1. Install deps (add the extras only if you'll run generation)
uv sync                          # reader-only
# uv sync --extra llm --extra web  # + generation

# 2. Start Postgres (creates the `rabbithole` database, listens on localhost:5433)
docker compose up -d postgres

# 3. Configure secrets
cp .env.example .env             # then edit the values

# 4. Seed the Topic taxonomy from the design record (one time)
uv run python -c "import os, psycopg; from pathlib import Path; from dotenv import load_dotenv; from content_graph.adapters.migrate import apply_migrations; from content_graph.adapters.postgres import PostgresContentGraphRepository; from content_graph.seed import load_seed_taxonomy; load_dotenv(); conn = psycopg.connect(os.environ['DATABASE_URL']); apply_migrations(conn); print(len(load_seed_taxonomy(PostgresContentGraphRepository(conn), Path('docs/taxonomy.md').read_text())), 'topics')"
```

## Run the backend

```bash
uv run python -m api.main        # serves on http://0.0.0.0:8000
```

Interactive docs are at `http://localhost:8000/docs`.

## Verify

```bash
curl -i http://localhost:8000/daily
```

A fresh reader is minted on first contact: the response carries an
`X-Rabbit-Token` header — store it and send it back as `Authorization: Bearer <token>`
on later calls (see [API.md](API.md)).

> **Note — content is required for a 200.** `/daily` returns `404` until Pieces
> exist **and** a Daily Feature is assigned. Content is produced by a generation
> run: enable the trigger (set `LLM_PROVIDER` + `API_ADMIN_TOKEN` and the `LLM_*`
> models, install the `llm`/`web` extras) and `POST /admin/generation/runs`.

## Enabling generation (summary)

1. `uv sync --extra llm --extra web`
2. Set `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL_PRECISE`, `LLM_MODEL_CREATIVE`,
   and `API_ADMIN_TOKEN` in `.env`.
3. Restart the backend and trigger a run (see [API.md](API.md#admin-generation)).
