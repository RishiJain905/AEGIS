# Synthetic Training Scenario — Narrative Overview

The Synthetic Training Scenario is the deterministic tutorial that a new AEGIS operator
plays first. It models a single phishing-driven intrusion at Aurora Learning Lab, a small
fictional online education provider, using a pinned seed and a short horizon so the whole
story plays out legibly in a few minutes.

## Chapters (for cinematic phases)

1. **Baseline operations** — Normal telemetry across three organizational zones
2. **First signal** — A suspicious process burst appears on the instructor workstation
3. **Escalation** — Credential misuse against the identity provider and lateral movement
   to the file server
4. **Decision point** — Operator opens an incident, tasks an agent, and prepares containment
5. **Consequences** — Asset status reflects containment before the staged exfiltration completes

## Hidden causes

| Cause ID | Label |
|----------|-------|
| `hidden-cause-phishing-compromise` | Phishing-compromised workstation and credential misuse |
| `hidden-cause-data-exfiltration` | Staged exfiltration of student records |

Hidden cause labels are **not** exposed to operators during active play.

## Presentation constraints

- Cinematic layers derive from authoritative simulation events only
- Chronology follows `(sim_time, priority, tie_breaker)` ordering
- Safe presentation hints live in `presentation/cinematic-hints.json`
- Hints must set `revealsHiddenCause: false` and omit `hiddenCauseId`
