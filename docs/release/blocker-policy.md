# Release blocker policy

Use one severity on every defect record. Severity is decided by impact on a required gate,
not by implementation effort.

| Level | Operational meaning | Release action |
| --- | --- | --- |
| B0 stop-ship | Security boundary bypass, data loss/corruption, nondeterministic authority, or unsafe agent action | Stop release; validation must fail until fixed and re-run |
| B1 blocker | Required Silent Relay cause/branch fails, replay/golden equivalence breaks, auth/approval invariant fails, or hard p99 budget fails | Release fails; fix and attach fresh evidence |
| B2 conditional | Non-required UX defect, optional browser unavailable with a deterministic reason, or warning budget overage below a hard limit | Ship only with owner, mitigation, expiry, and an approved exception where applicable |
| B3 backlog | Cosmetic or bounded follow-up with no release criterion impact | Record and schedule; no release exception needed |

An optional browser skip is a skip record, not a blocker or an exception, when Chromium
passes and the report names the missing executable and environment. Docker/API/worker
unavailability is never an optional skip. A B0/B1 cannot be waived by editing a budget,
weakening a test, or omitting its artifact.
