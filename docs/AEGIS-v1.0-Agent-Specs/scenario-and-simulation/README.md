# Scenario and Simulation Phases

These specifications are read by coding agents. Execute a phase only after all direct dependencies are approved.

| Phase | Title | Direct dependencies |
|---:|---|---|
| 08 | [Scenario SDK](08-scenario-sdk.md) | 00, 01 |
| 09 | [Deterministic Simulation Core](09-deterministic-simulation-core.md) | 01, 02, 08 |
| 10 | [Operation Silent Relay Content](10-operation-silent-relay.md) | 05, 08, 09 |

Use the root `PHASE-EXECUTION-PROTOCOL.md` for implementation, validation, repair, and handoff rules.
