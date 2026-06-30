# Production Readiness Phases

These specifications are read by coding agents. Execute a phase only after all direct dependencies are approved.

| Phase | Title | Direct dependencies |
|---:|---|---|
| 30 | [Authentication and Authorization](30-authentication-and-authorization.md) | 00, 02, 04, 24 |
| 31 | [Observability](31-observability.md) | 00, 02, 11, 12, 14, 18, 19 |
| 32 | [Security Hardening](32-security-hardening.md) | 19, 22, 24, 30, 31 |
| 33 | [Cloud Deployment](33-cloud-deployment.md) | 00, 02, 11, 12, 30, 31, 32 |
| 34 | [Full-System Validation](34-full-system-validation.md) | 00, 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33 |
| 35 | [v1.0 Release Preparation](35-v1-release-preparation.md) | 29, 33, 34 |

Use the root `PHASE-EXECUTION-PROTOCOL.md` for implementation, validation, repair, and handoff rules.
