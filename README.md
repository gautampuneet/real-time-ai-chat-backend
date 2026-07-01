# Real-Time AI Chat Backend

A backend for a simple real-time chat application built with FastAPI, PostgreSQL,
Redis, and WebSockets.

The project implements authentication, conversation management, persistent chat
history, and Redis-backed message fan-out across multiple application instances.
AI responses are mocked since the focus of the assignment is the backend.

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

## Manual Demo

### 1. Start the project:

```bash
docker compose up --build
```

This starts FastAPI, PostgreSQL, and Redis. The API container runs Alembic
migrations before Uvicorn starts.

In another terminal, verify readiness:

```bash
curl --noproxy '*' http://localhost:8000/health/ready
```

### 2. Register a user

```bash
curl --noproxy '*' -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"strong-password"}'
```

The response contains `access_token` and `refresh_token`.

### 3. Login

```bash
curl --noproxy '*' -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"strong-password"}'
```

Use the returned `access_token` for REST requests and WebSocket connections:

```bash
export ACCESS_TOKEN="<ACCESS_TOKEN>"
```

### 4. Create a conversation

```bash
curl --noproxy '*' -X POST http://localhost:8000/conversations \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Demo conversation"}'
```

Save the returned conversation id:

```bash
export CONVERSATION_ID="<CONVERSATION_ID>"
```

### 5. Open two WebSocket clients

To check Redis fan-out across app instances, stop the single Docker API
container and keep PostgreSQL and Redis running:

```bash
docker compose stop api
docker compose up -d postgres redis
```

Run two API processes in separate terminals:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

```bash
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/chatdb" \
REDIS_URL="redis://localhost:6379/0" \
JWT_SECRET_KEY="local-development-secret-change-me" \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/chatdb" \
REDIS_URL="redis://localhost:6379/0" \
JWT_SECRET_KEY="local-development-secret-change-me" \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Open one WebSocket client against each API process:

```bash
websocat "ws://localhost:8000/ws/conversations/$CONVERSATION_ID?token=$ACCESS_TOKEN"
```

```bash
websocat "ws://localhost:8001/ws/conversations/$CONVERSATION_ID?token=$ACCESS_TOKEN"
```

### 6. Send a message

In either WebSocket client, send:

```json
{
  "type": "message.send",
  "payload": {
    "content": "Hello from the demo"
  }
}
```

### 7. Expected behavior

All connected clients should receive:

- `message.created` event for the persisted user message
- `assistant.message` event for the persisted mock assistant reply

The events are published through Redis, so clients connected to different API
instances receive the same conversation events.

### 8. Verify message history

```bash
curl --noproxy '*' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/conversations/$CONVERSATION_ID/messages?page=1&page_size=20"
```

The response includes the stored user message and mock assistant reply.

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
- AI responses are mocked because integrating an actual model isn't the focus of this assignment.
