# Human Control and Replay Phases

These specifications are read by coding agents. Execute a phase only after all direct dependencies are approved.

| Phase | Title | Direct dependencies |
|---:|---|---|
| 24 | [Approval Workflow](24-approval-workflow.md) | 02, 12, 13, 22 |
| 25 | [Snapshot and Replay Engine](25-snapshot-and-replay-engine.md) | 02, 09, 11 |
| 26 | [Replay Frontend](26-replay-frontend.md) | 04, 06, 12, 13, 25 |

Use the root `PHASE-EXECUTION-PROTOCOL.md` for implementation, validation, repair, and handoff rules.
