# Operation Silent Relay

> Phase 10 flagship scenario — declarative content for AEGIS Command.

## Overview

Operation Silent Relay models **Meridian Logistics Group**, a fictional organization with 38 assets across 8 security zones. Each run selects one of four root causes and one of three response branches deterministically from the scenario seed.

| Property | Value |
|----------|-------|
| Scenario ID | `scenario:operation-silent-relay` |
| Version | `1.0.0` |
| Platform requirement | `0.0.0-phase10` |
| Assets | 38 |
| Zones | 8 |
| Root causes | 4 |
| Response branches | 3 |

## Topology and clusters

### Zones

| Zone ID | Domain |
|---------|--------|
| `business-unit:logistics` | Logistics routing, fleet, shipments |
| `business-unit:communications` | Gateway, messaging, notifications |
| `business-unit:identity` | IdP, SSO, service accounts |
| `business-unit:cloud` | Kubernetes, CI/CD, registry |
| `business-unit:endpoints` | Workstations, tablets, VPN clients |
| `business-unit:data-platform` | Audit, PII, analytics, shipment DB |
| `business-unit:security-ops` | SIEM, EDR, vulnerability scanning |
| `business-unit:ai-ops` | Inference gateway, models, features |

### Key assets

See [`scenarios/operation-silent-relay/manifest.yaml`](../../scenarios/operation-silent-relay/manifest.yaml) for the authoritative asset inventory.

## Root causes

| Hidden condition | Cause | Primary signals |
|------------------|-------|-----------------|
| `hidden-cause-compromised-credentials` | Stolen service account | Auth failures + lateral success |
| `hidden-cause-undocumented-maintenance` | Off-window maintenance | Deployment anomalies + health flap |
| `hidden-cause-defective-deployment` | Bad container release | API 500 spike + failed health |
| `hidden-cause-internal-misuse` | Privileged data exfil | PII query anomaly + outbound network |

Selection: `branch.seed_selector` with `branchGroup: root-cause` at simulation start.

## Response branches

| Branch | Trade-off |
|--------|-----------|
| `branch-response-contain` | Fast isolation, higher service impact |
| `branch-response-investigate` | Better evidence, slower containment |
| `branch-response-remediate` | Fix root fault, moderate risk |

Selection: `branch.seed_selector` with `branchGroup: response-path` at simulation start.

## Golden seeds

Registry: [`scenarios/operation-silent-relay/golden-seeds.yaml`](../../scenarios/operation-silent-relay/golden-seeds.yaml)

| Seed | Root cause | Response |
|------|------------|----------|
| 1000 | credentials | investigate |
| 1006 | maintenance | remediate |
| 1007 | misuse | investigate |
| 1014 | deployment | investigate |
| 1 | misuse | remediate |
| 11 | misuse | contain |

## Evidence

Expected evidence manifest: [`scenarios/operation-silent-relay/expected-evidence.yaml`](../../scenarios/operation-silent-relay/expected-evidence.yaml)

## Scoring

Scoring criteria are defined in the manifest `scoring` section (8 weighted dimensions). Runtime scoring execution is deferred to Phase 29.

## Validation commands

```bash
uv run aegis-scenario validate scenarios/operation-silent-relay
uv run aegis-simulator determinism-check --scenario scenarios/operation-silent-relay --seed 1000 --steps 300
uv run pytest tests/scenarios/operation-silent-relay -q
uv run pytest tests/golden-replays/operation-silent-relay -q
```

## Constraints for later phases

- Do not hard-code Silent Relay semantics in platform code
- Hidden cause labels remain concealed during active play until Phase 29
- Live timeline and WebSocket streaming require Phases 11–13
- Agent investigation tooling requires Phases 19–21
