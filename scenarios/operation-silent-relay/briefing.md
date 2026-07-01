# Operation Silent Relay — Operator Briefing

**Classification:** INTERNAL — TRAINING EXERCISE  
**Scenario version:** 1.0.0  
**Organization:** Meridian Logistics Group (fictional)

## Situation

Meridian Logistics Group operates a multi-zone digital supply chain spanning logistics routing, customer communications, identity services, cloud deployment pipelines, endpoint fleets, regulated data stores, security operations, and AI-assisted route optimization.

Over the past cycle, baseline telemetry has been stable. However, synthetic monitoring indicates the potential for overlapping incident patterns that may reflect **compromised credentials**, **undocumented maintenance**, **defective deployment**, or **internal misuse**. Signals will not point to a single obvious root cause.

## Your mission

1. Detect the true root cause using corroborating evidence — not a single alert in isolation.
2. Choose a response path that balances containment speed, evidence preservation, and service impact.
3. Avoid false attribution driven by routine patch activity, benign CI traffic, or scheduled analytics jobs.

## Operational zones

| Zone | Function |
|------|----------|
| Logistics Operations | Routing API, fleet coordination, shipment scheduling |
| Communications | Gateway, message bus, notifications |
| Identity and Access | IdP, SSO, service accounts |
| Cloud Platform | Kubernetes, CI/CD, container registry |
| Endpoints | Analyst workstations, field devices, vendor VPN |
| Data Platform | Audit, PII, analytics, shipment records |
| Security Operations | SIEM, EDR, vulnerability management |
| AI Operations | Inference gateway, model registry, feature store |

## Known distractors

- Scheduled patch-window authentication noise on SSO infrastructure
- Benign container registry deployments from CI/CD
- Legitimate analytics batch queries against the warehouse

## Success criteria

- Identify the hidden cause with evidence that contradicts plausible false hypotheses
- Select a proportionate response (contain, investigate, or remediate)
- Minimize unnecessary service disruption

## Constraints

This is a **synthetic defensive simulation**. All activity is confined to the scenario runtime. No real-world offensive actions are authorized or required.
