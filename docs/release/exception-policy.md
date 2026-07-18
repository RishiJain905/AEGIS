# Release exception policy

Exceptions are finding-specific, time-bounded approvals for a known risk; they do not make a
failed test pass. Reuse the Phase 32 exception-record contract in
[`docs/security/scan-triage-policy.md`](../security/scan-triage-policy.md): finding/issue,
exact revision or image digest, observed scanner/test output, owner, justification, impact,
compensating controls, approver, created time, and hard expiry.

An exception may not weaken a test, lower a budget, suppress a security scanner, or cover a
different finding. Maximum duration is 30 calendar days. The release manifest must retain the
record path and the final decision. Expired or missing approval makes the affected B0/B1 gate
fail. Missing optional Firefox/WebKit is recorded as a deterministic skip-with-reason, not an
exception; missing Chromium or Docker is a release failure.
