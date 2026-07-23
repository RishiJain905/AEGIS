# Synthetic Training Scenario — Operator Briefing

**Classification:** INTERNAL — TRAINING EXERCISE
**Scenario version:** 1.0.0-synthetic-training
**Organization:** Aurora Learning Lab (fictional)

## Welcome to AEGIS Command

This is your first engagement. It is a hand-held tutorial designed to teach you the
rhythm of a blue-team run: watch telemetry, notice the first credible signal, open an
incident, task an AI agent to investigate, approve a containment action, and read the
after-action once the run ends. Nothing here is timed against you — take the space to
learn the controls. Every run of this scenario is identical (it uses a pinned seed), so
you can replay it as many times as you like and see the same story unfold.

## The organization

Aurora Learning Lab is a small online education provider. Its environment is deliberately
compact so the whole picture fits on one screen:

| Zone | Assets |
|------|--------|
| Workforce Endpoints | Instructor and student workstations, email relay, EDR console |
| Identity and Access | Identity provider, SSO gateway |
| Data Services | Learning portal, file server, student records database |

## What is about to happen

A phishing email reaches an instructor workstation. From that foothold the attacker
misuses stolen credentials against the identity provider, moves laterally to the file
server, and stages an attempt to exfiltrate the student records database near the end of
the run. The signals appear in order — you will have time to see each one.

## Your objectives

1. **Detect the compromised workstation** using corroborating endpoint and identity
   telemetry — not a single alert in isolation.
2. **Contain the intrusion before exfiltration completes.**
3. **Preserve the evidence** so the after-action and replay tell the full story.

## Known distractor

- Routine patch-window authentication noise on the SSO gateway. It is benign — do not
  attribute the intrusion to it.

## Constraints

This is a **synthetic defensive simulation**. All activity is confined to the scenario
runtime. No real-world offensive actions are authorized or required.
