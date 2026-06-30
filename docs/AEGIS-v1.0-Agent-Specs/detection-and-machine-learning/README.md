# Detection and Machine Learning Phases

These specifications are read by coding agents. Execute a phase only after all direct dependencies are approved.

| Phase | Title | Direct dependencies |
|---:|---|---|
| 14 | [Feature Pipeline](14-feature-pipeline.md) | 01, 09, 11 |
| 15 | [Rules and Statistical Baselines](15-rules-and-statistical-baselines.md) | 02, 14 |
| 16 | [Anomaly Model](16-anomaly-model.md) | 02, 14, 15 |
| 17 | [Graph Risk Propagation](17-graph-risk-propagation.md) | 05, 14, 15, 16 |

Use the root `PHASE-EXECUTION-PROTOCOL.md` for implementation, validation, repair, and handoff rules.
