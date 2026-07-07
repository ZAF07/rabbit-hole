# API

Request contracts for the Rabbit Hole backend. To set up and start it, see
[USAGE.md](USAGE.md). Base URL in local dev: `http://localhost:8000`.
Every response body is JSON; every field uses internal vocabulary only
(no `run_id`, no constellation — [ADR 0006](docs/adr/0006-generation-and-consumption-are-separate.md)).

## Authentication

Two independent gates:

- **Reader** — anonymous, token-based. On the **first** request send **no**
  auth; the server mints a reader and returns the token on the `X-Rabbit-Token`
  **response** header. Store it and send it on every later request as
  `Authorization: Bearer <token>`. A missing or invalid token is treated as a
  new first contact.
- **Admin** — a shared operator secret on the `X-Admin-Token` **request** header.
  Wholly separate from reader identity.

## Reader endpoints

| Method | Path | Body | Success | Notes |
| --- | --- | --- | --- | --- |
| `GET` | `/daily` | — | `200` `DailyFeature` | `404` if no Daily Feature assigned. |
| `GET` | `/notification` | — | `200` `Notification` | `404` if no Daily Feature assigned. |
| `POST` | `/pieces/{piece_id}/read` | — | `200` `Reading` | Guarded entry — `403` if the Piece is not the Daily Feature or already in your trail. |
| `POST` | `/pull` | `Pull` | `200` `Reading` | `404` unknown Connection; `409` if `from_piece_id` is not your current Piece. |
| `POST` | `/backtrack` | — | `200` `Reading` | `409` if there is nowhere to step back to. |
| `GET` | `/journey` | — | `200` `Journey` | `404` if no journey started. |
| `GET` | `/resume` | — | `200` `Resume` | `204` if there is nothing to resume. |
| `POST` | `/close` | — | `204` | Ends the current analytics Session. |
| `GET` | `/knowledge-graph` | — | `200` `KnowledgeGraph` | The reader's own trail. |

### Request bodies

```jsonc
// Pull  (POST /pull)
{ "from_piece_id": "string", "to_piece_id": "string" }
```

### Response shapes

```jsonc
// Topic — embedded wherever topics appear
{ "id": "string", "slug": "string", "title": "string", "parent_ids": ["string"] }

// ConnectionPreview — an onward card
{ "from_piece_id": "string", "to_piece_id": "string", "hook": "string",
  "to_title": "string", "to_topics": [Topic] }

// DailyFeature  (GET /daily)
{ "piece": { "id": "string", "title": "string", "teaser": "string",
             "read_time_min": 0, "topics": [Topic] },
  "connections": [ConnectionPreview] }

// Reading  (POST /pieces/{id}/read, /pull, /backtrack)
{ "piece": { "id": "string", "title": "string", "teaser": "string",
             "read_time_min": 0,
             "blocks": [ { "kind": "string", "payload": { } } ],
             "topics": [Topic] },
  "connections": [ConnectionPreview] }

// Journey  (GET /journey)
{ "current_piece_id": "string | null", "stack": ["string"], "depth": 0 }

// Resume  (GET /resume)
{ "reading": Reading, "stack": ["string"], "session_id": "string" }

// KnowledgeGraph  (GET /knowledge-graph)
{ "nodes": [ { "piece_id": "string", "title": "string", "topics": [Topic] } ],
  "edges": [ { "from_piece_id": "string", "to_piece_id": "string" } ] }

// Notification  (GET /notification)
{ "piece_id": "string", "title": "string", "teaser": "string" }
```

### Reader error statuses

`401` unknown reader · `403` free-roam (unguarded read) · `404` unknown
Connection / no Daily Feature / no journey · `409` conflict (not your current
Piece, or cannot backtrack). Bodies are `{ "detail": "..." }`.

## Admin — generation

Requires the `X-Admin-Token` header; `401` without it. Enabled only when the
generation trigger is configured (see [USAGE.md](USAGE.md)).

| Method | Path | Body | Success |
| --- | --- | --- | --- |
| `POST` | `/admin/generation/runs` | `Trigger` | `202` `RunHandle` |
| `GET` | `/admin/generation/runs/{run_id}` | — | `200` `RunHandle` (`404` if unknown) |

```jsonc
// Trigger  (POST /admin/generation/runs)
{ "brief": "string" }        // the through-line the run plans a constellation from

// RunHandle
{ "run_id": "string", "state": "running | succeeded | failed", "detail": "string" }
```

The trigger dispatches the run off the request path and returns `202`
immediately; poll the run-status endpoint to follow it.

## Examples

```bash
# First contact — capture the minted token from the response header
curl -si http://localhost:8000/daily | grep -i x-rabbit-token

# Read a Piece as an established reader
curl -s -X POST http://localhost:8000/pieces/PIECE_ID/read \
  -H "Authorization: Bearer YOUR_TOKEN"

# Pull a Connection onward
curl -s -X POST http://localhost:8000/pull \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"from_piece_id":"A","to_piece_id":"B"}'

# Trigger a generation run (operator)
curl -s -X POST http://localhost:8000/admin/generation/runs \
  -H "X-Admin-Token: YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"brief":"How glass shaped modern science"}'
```
