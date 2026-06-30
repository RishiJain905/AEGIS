# Graph Platform Phases

These specifications are read by coding agents. Execute a phase only after all direct dependencies are approved.

| Phase | Title | Direct dependencies |
|---:|---|---|
| 05 | [Graph Domain Engine](05-graph-domain-engine.md) | 01 |
| 06 | [Sigma.js Operational Graph](06-sigma-operational-graph.md) | 03, 04, 05 |
| 07 | [Graph Performance and Worker Layouts](07-graph-performance-and-worker-layouts.md) | 05, 06 |

Use the root `PHASE-EXECUTION-PROTOCOL.md` for implementation, validation, repair, and handoff rules.
