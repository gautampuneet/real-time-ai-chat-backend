# Notes

## Architecture

I kept the project intentionally small. The assignment focuses on authentication, persistence, WebSockets, and Redis fan-out, so I tried to keep those pieces straightforward instead of introducing additional abstractions.

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

After a message is persisted, it is published to Redis. Every application instance subscribes to the relevant conversation channel and broadcasts the event to its locally connected WebSocket clients.

Using Redis as the common broadcast path means the same flow works whether there is one API instance or several.

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

## Self-critique

Looking back, the overall structure is reasonable for the assignment scope.

The area I'd improve next is the duplicated authorization logic around conversations, especially if shared conversations become a requirement.

I also think there is room to make the Redis subscription lifecycle more observable by exposing metrics around active subscriptions and connected WebSocket clients.
