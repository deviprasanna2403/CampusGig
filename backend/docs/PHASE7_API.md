# Phase 7 API - Communication and Engagement

Phase 7 adds application-stage communication, interviews, real-time chat, and
notifications. It does not begin Phase 8 or add payments, fraud, analytics, or
frontend work.

## Applications

- `POST/GET /api/v1/applications/student/` submits and lists the authenticated student's applications.
- `GET/PATCH /api/v1/applications/student/{id}/` reads or updates the student's own application.
- `PATCH /api/v1/applications/student/{id}/withdraw/` withdraws an eligible application.
- `GET /api/v1/applications/business/` lists applications for jobs owned by the business; supports `?status=`.
- `GET/PATCH /api/v1/applications/business/{id}/` reads or advances an owned application.

Application stages are `SUBMITTED`, `SHORTLISTED`, `INTERVIEW`, `SELECTED`,
`REJECTED`, and `WITHDRAWN`. Chat and interviews require `SHORTLISTED` or
`INTERVIEW` state.

## Conversations and messages

- `POST/GET /api/v1/communication/conversations/` creates or lists conversations for an application participant.
- `GET /api/v1/communication/conversations/{id}/` retrieves an authorized conversation.
- `POST/GET /api/v1/communication/conversations/{id}/messages/` sends or lists messages.
- `PATCH /api/v1/communication/messages/{id}/read/` marks an authorized message read.

A WebSocket conversation is available at:

`ws://<host>/ws/conversations/{conversation_id}/?token=<JWT access token>`

The WebSocket uses Django Channels groups, authenticates with the same JWT
access token, persists messages, and broadcasts JSON messages to connected
participants. Production should set `CHANNEL_LAYER_BACKEND=channels_redis.core.RedisChannelLayer`
and `REDIS_URL=redis://...`; tests use the in-memory channel layer.

## Interviews

- `POST/GET /api/v1/interviews/` creates or lists interviews for authorized application participants.
- `GET/PATCH /api/v1/interviews/{id}/` retrieves or updates an authorized interview.

Interview times must be timezone-aware, future-dated, and have `ends_at` after
`starts_at`. Scheduling or updating emits in-app notifications to both parties.

## Notifications

- `GET /api/v1/notifications/` lists the authenticated user's notifications.
- `GET /api/v1/notifications/?unread=true` filters unread notifications.
- `PATCH /api/v1/notifications/{id}/read/` marks one notification read.

Events cover application submission, new applications, shortlist/selection/
rejection, interview scheduling/updates, chat messages, job cancellation,
withdrawals, and deadline reminders. Email delivery is optional and controlled
by `PHASE7_EMAIL_NOTIFICATIONS`; Celery tasks process pending email delivery and
idempotent next-day deadline reminders.
