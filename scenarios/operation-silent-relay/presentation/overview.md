# Operation Silent Relay — Narrative Overview

Operation Silent Relay is the flagship AEGIS v1.0 training scenario. It models a fictional logistics organization experiencing one of four seed-selected root causes, with three operator response branches producing distinct consequences.

## Chapters (for cinematic phases)

1. **Baseline operations** — Normal telemetry across eight organizational zones
2. **Early signals** — Overlapping clues and distractors emerge
3. **Escalation** — Cause-specific evidence crosses detection thresholds
4. **Decision point** — Operator selects containment, investigation, or remediation
5. **Consequences** — Asset status and relationship confidence reflect the chosen path

## Root causes

| Cause ID | Label |
|----------|-------|
| `hidden-cause-compromised-credentials` | Stolen service account credentials |
| `hidden-cause-undocumented-maintenance` | Approved but off-window maintenance |
| `hidden-cause-defective-deployment` | Defective container deployment |
| `hidden-cause-internal-misuse` | Privileged internal data misuse |

Hidden cause labels are **not** exposed to operators during active play (deferred to Phase 29 scoring).

## Response branches

| Branch ID | Trade-off |
|-----------|-----------|
| `branch-response-contain` | Fast isolation, higher service impact |
| `branch-response-investigate` | Richer evidence, slower containment |
| `branch-response-remediate` | Fix underlying fault, moderate operational risk |

## Presentation constraints

- Cinematic layers derive from authoritative simulation events only
- Three.js and generated narrative must not invent domain facts
- Chronology follows `(sim_time, priority, tie_breaker)` ordering
