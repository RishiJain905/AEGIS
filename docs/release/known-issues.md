# Known release issues

These are explicit records, not silent waivers. They remain subject to the blocker and
exception policies.

| Issue | Severity/status | Evidence and disposition |
| --- | --- | --- |
| Web image has 23 HIGH transitive findings | B2 / open triage | The Phase 32 scan-triage record identifies the affected transitive packages. Fix or create a finding-specific approved exception with digest, controls, owner, and expiry; do not suppress the scan. |
| 3D first render is currently approximately 4–8 seconds | B2 baseline / measured each release | `graph.3d.mount_to_visible` records the real first-frame latency and capability fallback. A hard p99 over budget becomes B1; the latency is not hidden behind a generic readiness check. |
| Windows `pnpm build` can fail with symlink `EPERM` | B2 environment issue / open | Retain the exact build output in deployment evidence and use the documented local mitigation/runner environment. A reproducible release build failure remains B1 until fixed. |
