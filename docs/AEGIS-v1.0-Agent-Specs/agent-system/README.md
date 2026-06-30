# Agent System Phases

These specifications are read by coding agents. Execute a phase only after all direct dependencies are approved.

| Phase | Title | Direct dependencies |
|---:|---|---|
| 18 | [Model-Provider Abstraction](18-model-provider-abstraction.md) | 00, 01, 02 |
| 19 | [Agent Runtime](19-agent-runtime.md) | 01, 02, 11, 18 |
| 20 | [WATCHTOWER and TRACE](20-watchtower-and-trace.md) | 13, 15, 17, 19 |
| 21 | [ORACLE](21-oracle.md) | 19, 20 |
| 22 | [BASTION and WARDEN](22-bastion-and-warden.md) | 15, 17, 19, 21 |
| 23 | [SCRIBE](23-scribe.md) | 19, 20, 21, 22 |

Use the root `PHASE-EXECUTION-PROTOCOL.md` for implementation, validation, repair, and handoff rules.
