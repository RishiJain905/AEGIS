# Synthetic Training Scenario

Deterministic tutorial scenario for AEGIS Command — the first run a new operator plays.

## Contents

| File | Purpose |
|------|---------|
| `manifest.yaml` | ScenarioManifestV1 — 9 assets, 3 zones, one phishing attack path |
| `golden-seeds.yaml` | Pinned tutorial seed (1000) and horizon |
| `expected-evidence.yaml` | Evidence chain for the single hidden cause |
| `briefing.md` | Welcoming operator tutorial briefing |
| `presentation/overview.md` | Narrative metadata for cinematic phases |
| `presentation/cinematic-hints.json` | Safe presentation hints (no hidden-cause reveals) |

## Design

One deterministic attack path, no branch RNG: a single attack branch (weight 1.0) is
seed-selected and gates the intrusion beats. Every run uses the pinned seed 1000 and a
short 120-step horizon so a tutorial run finishes in a few minutes under the 2s tick
engine.

Attack beats: phishing foothold on the instructor workstation, credential misuse against
the identity provider, lateral movement to the file server, and a staged exfiltration
attempt against the student records database. Hidden conditions use `hidden_until_triggered`
visibility so the scenario plays correctly under fog of war.

## Validate

```bash
uv run aegis-scenario validate scenarios/synthetic-training
uv run aegis-simulator run-persisted --scenario scenarios/synthetic-training --seed 1000 --steps 120
```
