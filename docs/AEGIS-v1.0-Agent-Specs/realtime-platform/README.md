# Realtime Platform Phases

These specifications are read by coding agents. Execute a phase only after all direct dependencies are approved.

| Phase | Title | Direct dependencies |
|---:|---|---|
| 11 | [Event Persistence and Streaming](11-event-persistence-and-streaming.md) | 01, 02, 09 |
| 12 | [WebSocket Gateway](12-websocket-gateway.md) | 01, 02, 11 |
| 13 | [Live Command-Centre Integration](13-live-command-centre-integration.md) | 04, 06, 10, 11, 12 |

Use the root `PHASE-EXECUTION-PROTOCOL.md` for implementation, validation, repair, and handoff rules.
