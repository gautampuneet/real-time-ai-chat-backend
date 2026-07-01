# Notes

## Architecture

The assignment focuses on authentication, persistence, WebSockets, and Redis fan-out, so I tried to keep the implementation focused on those areas rather than introducing additional abstractions or optional features.
The project follows a simple layered structure:

```
Router
    ↓
Service
    ↓
Repository
    ↓
Database / Redis
```

Routers are responsible for request handling, services contain business logic, and repositories encapsulate database queries.

---

## WebSocket authentication

The WebSocket uses the access token as a query parameter.

```
ws://.../ws/conversations/{conversation_id}?token=<JWT>
```

This keeps local testing simple and works with browsers, Postman, and websocat.

For a production system I would likely use short-lived connection tokens or another authentication mechanism to reduce the chance of tokens appearing in logs.

---

## Redis

Redis is used only for Pub/Sub.

1. After a message is persisted, it is published to Redis. Every application instance subscribes to the relevant conversation channel and broadcasts the event to its locally connected WebSocket clients.
2. Redis is the only broadcast path used by the application. Whether there's one API instance or multiple, messages follow the same flow, which keeps the WebSocket handling consistent.
---

## AI

The AI service is intentionally minimal and returns a mocked response.

The assignment explicitly states that AI is not the focus, so I kept the implementation simple and concentrated on the messaging pipeline.

---

## Conversation model

Conversations are owner-scoped.

A conversation belongs to a single authenticated user, and any number of WebSocket connections for that user can join the conversation (for example, multiple browser tabs or devices).

If shared conversations were required, I would introduce a `conversation_participants` table and switch authorization from ownership checks to participant membership.

---

## What I intentionally skipped

I didn't implement:

- OAuth
- Presence
- Typing indicators
- Streamed AI responses
- Message delivery guarantees
- Rate limiting

I left these out to keep the project focused on the requested messaging flow.

---

## If I had another day

The next things I would work on would be:

- Shared conversations
- Prometheus metrics
- OpenTelemetry tracing
- Better WebSocket observability
- Delivery acknowledgements for improved reliability

---

## Nice-to-have items

I focused on the core functionality requested in the assignment. As a result, a few optional items were left out:

- Message delivery guarantees such as client-generated message IDs and reconnect/redelivery.
- Prometheus metrics and runtime counters.
- OAuth providers (Google/GitHub).
- Automated load testing with Locust or k6.

The Redis Pub/Sub implementation does support running multiple API instances, and the README includes a manual walkthrough for verifying cross-instance message fan-out.

## Self-critique

Looking back, the overall structure is reasonable for the assignment scope.

The area I'd improve next is the duplicated authorization logic around conversations, especially if shared conversations become a requirement.

I also think there is room to make the Redis subscription lifecycle more observable by exposing metrics around active subscriptions and connected WebSocket clients.
