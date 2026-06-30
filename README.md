# Real-Time AI Chat Backend

A small FastAPI backend for authenticated chat conversations with PostgreSQL,
Redis Pub/Sub, and WebSockets.

The AI reply is mocked. The focus of this project is authentication, persistence,
conversation history, WebSocket messaging, and Redis fan-out between app
instances.

## Tech Stack

- Python 3.12
- FastAPI
- SQLAlchemy 2.0 async
- PostgreSQL
- Redis Pub/Sub
- WebSockets
- Pydantic v2
- Alembic
- Docker Compose

## Running the Project

For local overrides, copy the example environment file:

```bash
cp .env.example .env
```

Start PostgreSQL, Redis, and the API:

```bash
docker compose up --build
```

The API container runs Alembic migrations before Uvicorn starts. If migrations
fail, the container exits with the Alembic error.

Before production use, set `JWT_SECRET_KEY` to a strong random value and keep
`DEBUG=false`.

The API runs at:

```text
http://localhost:8000
```

OpenAPI docs are available at:

```text
http://localhost:8000/docs
```

For local development outside Docker, run migrations manually before starting
Uvicorn:

```bash
.venv/bin/python -m alembic upgrade head
```

## Checks

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check app tests migrations
.venv/bin/python -m mypy app
```

## HTTP API

Authentication:

```text
POST /auth/register
POST /auth/login
POST /auth/refresh
GET  /auth/me
```

Conversations:

```text
POST   /conversations
GET    /conversations
PATCH  /conversations/{conversation_id}
DELETE /conversations/{conversation_id}
GET    /conversations/{conversation_id}/messages
```

## WebSocket API

Connect with an access token:

```text
ws://localhost:8000/ws/conversations/{conversation_id}?token=<ACCESS_TOKEN>
```

Send a message:

```json
{
  "type": "message.send",
  "payload": {
    "content": "Hello"
  }
}
```

Ping:

```json
{
  "type": "ping"
}
```

Example message event:

```json
{
  "type": "message.created",
  "payload": {
    "id": "0e9f6c1d-1f55-4fd8-b2b7-909c2c4a91d8",
    "conversation_id": "4fd88cb4-70d5-4c71-8f8a-92db9b5ec651",
    "sender_id": "be24cc4a-6f2a-4d40-a30e-531f4db921e4",
    "role": "user",
    "content": "Hello",
    "created_at": "2026-06-30T10:00:00Z"
  }
}
```

Assistant replies are persisted and published through the same Redis fan-out path.

## Redis Fan-Out

Redis is used only for Pub/Sub. After a message is saved, the outbound WebSocket
frame is published to:

```text
chat:conversation:{conversation_id}
```

Each API instance with local clients for that conversation subscribes to the
channel and broadcasts received frames to its own WebSocket clients.

To test two local app instances, start PostgreSQL and Redis:

```bash
docker compose up -d postgres redis
.venv/bin/python -m alembic upgrade head
```

Then run two API processes in separate terminals:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Connect one WebSocket client to each port with the same conversation and access
token. A message sent through either connection should be received by both.

## Project Structure

```text
app/
├── database/
├── exceptions/
├── models/
├── repositories/
├── routers/
├── schemas/
├── services/
├── websocket/
├── config.py
├── dependencies.py
├── logging_config.py
├── main.py
└── security.py
```

Routers handle HTTP/WebSocket boundaries, services contain business logic, and
repositories contain database queries.

## Assumptions

- Conversations are private and owned by one user.
- Multiple WebSocket clients can connect to the same conversation for that user.
- AI responses are mocked because model integration is outside the assignment scope.
