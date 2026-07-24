# AEGIS ↔ EW-3 Integration — Design (2026-07-23)

**Status:** future / design-only. **Blocked on EW-3 models being trained and validated** per `D:\Projects\Triad\Upcoming-Project\docs\TRAINING-PLAYBOOK.md`. This spec exists so the seam is designed before the models arrive, not after. No AEGIS code changes are proposed for *now* — the "when" is "once EW-3 clears its Stage-0/Stage-3 gates."

## Context

Two of the owner's systems:

- **AEGIS Command** — a deterministic cyber-defence *simulation platform*: scenarios emit synthetic telemetry, a detection/ML layer raises alerts, LLM agents + a human blue team investigate and contain, everything renders on a live command surface. Has a formal ML contract (deterministic rules → Isolation Forest → gradient-boosted classifier → autoencoder → GNN), versioned feature schemas, model manifests, and a score contract — and a backlog item for "adversarial mode" (an AI-driven attacker).
- **EW-3: Electronic Warfare Triad** — a 3-player adversarial ML system in the **radio-frequency** domain: a Defender (Mamba-3 + KAN) classifies real-vs-spoofed / modulation / drone-model from I/Q waveforms; an Attacker (RF-Diffusion) generates spoofed I/Q; an Evolver (LTC + REINFORCE) adapts attack strategy in a closed self-play loop.

The owner's intuition: these connect, and the models could power AEGIS scenarios — possibly playing against each other.

## Honest overlap assessment (read this before getting excited)

**There is zero data-level overlap.** EW-3 operates on `(batch, 2, 1024)` float32 I/Q waveform tensors (radio physics — carrier, phase, SNR, modulation). AEGIS's ML layer operates on structured event-derived / graph features with a versioned feature schema. An RF spoofing detector cannot detect a simulated credential compromise, and vice versa. Forcing either model sideways into the other's domain produces nothing. So "AEGIS scenarios just use these models as-is" — **no**, not directly.

**The overlap that IS real is at two levels:**

1. **Model-plug overlap** — EW-3's *trained Defender* is a real signal classifier that can slot behind AEGIS's model-manifest + score contract **if the scenario feeds it signal-domain telemetry.** That requires a new *RF scenario domain* in AEGIS, not a reinterpretation of existing scenarios.
2. **Architectural-pattern overlap** — EW-3's Attacker/Defender/Evolver self-play loop (reward-driven strategy adaptation, curriculum, freeze-one-side) is the *same shape* AEGIS's "adversarial mode" backlog needs. The reusable thing is the **pattern**, not the RF-specific weights.

Everything below builds on those two, in order of near-ness.

---

## Path A — RF scenario domain + EW-3 Defender as an AEGIS detection model *(the concrete, near-term one)*

AEGIS is a scenario platform; nothing says scenarios must be network intrusions. A new scenario class — call it **"Operation Broken Signal"** — puts the blue team in an RF-warfare situation (drone incursion + comms jamming against Meridian Logistics' field operations). The player + AI copilot detect and respond exactly as today; the *detection model underneath* is EW-3's trained Defender.

### The seam (the important part)

Introduce a **signal-detection adapter** that mirrors AEGIS's existing `model-provider` pattern (vendor SDKs stay behind adapters; domain code never imports them directly):

- A new adapter package/module (e.g. `packages/rf-detector` or a `services/ml` adapter) that loads an **EW-3 Defender checkpoint** and exposes AEGIS's standard scoring interface. Input: a window of RF telemetry (the scenario's synthetic I/Q or a feature summary of it). Output: an AEGIS **`ScoreV1`** — model version, entity ID, numeric score, threshold/risk band, feature-schema version, explanation, scoring time/source. EW-3's authenticity-head logits map cleanly onto this (real-vs-spoofed → risk band; the model manifest records the EW-3 checkpoint hash + training run).
- The adapter is **behind AEGIS's model-manifest system** — which was *built for exactly this* (model ID + semver, artifact checksum + object key, algorithm, feature-schema version, training run, thresholds, known limitations). An EW-3 Defender is just another manifested model.
- **Determinism and CI stay intact.** AEGIS's non-negotiables: same scenario+seed ⇒ identical event stream; core CI passes with no external model. The adapter must therefore:
  - Have a **deterministic fake** (like the `mock` LLM provider) that returns fixture scores, so CI and golden replays never need the real Defender — same discipline as the copilot's mock provider.
  - Run inference **offline/local** (the Defender is a local checkpoint; no network egress), fitting AEGIS's "no arbitrary network access" rule.
  - Feed the scenario's RF telemetry deterministically from the seeded scenario runtime — the *simulation* is deterministic; the Defender's scoring of it is a pure function of (checkpoint, input), so a pinned checkpoint keeps runs reproducible. Pin the checkpoint hash in the scenario's required-model manifest.

### The RF scenario pack

A new scenario package (`scenarios/operation-broken-signal/`) using the scenario SDK: RF assets/zones (ground stations, drones, comms relays, jammers), an RF telemetry generator plugin that emits signal windows (drawing on EW-3's synthetic I/Q generator or a distilled feature form), hidden-condition-gated attacker beats (jamming/spoofing onset) — so **fog of war works unchanged**: a spoofed signal stays undisclosed until the EW-3 Defender scores it as spoofed (that detection is the reveal). All the existing machinery — copilot tasking, containment proposals, approval gate, adversary dossier, ghost branch, after-action — works on top with no changes, because it operates on AEGIS's event/alert/incident abstractions, not on the RF specifics.

### Why this is genuinely novel

No existing product lets a human + AI blue team defend an RF-warfare scenario with fog of war, a tasked copilot, and a real trained signal-classifier as the detection layer, plus counterfactual "what if I'd jammed back 30s earlier" replay. That's a scenario class AEGIS uniquely enables.

---

## Path B — EW-3 Evolver pattern → AEGIS adversarial mode *(the deeper, later one)*

AEGIS's attacker is scripted-but-branching (deterministic, protects golden replays and scoring). The backlog "adversarial mode" wants an **AI-driven attacker that adapts to how well the blue team + copilot are detecting it.** EW-3's Evolver is precisely that pattern: a 10-dim state (defender accuracy, confusion, attack-success history, curriculum phase) → attack-parameter action, trained by REINFORCE against a defender's performance. The **math is domain-agnostic**; only the state inputs and the generative target are RF-specific.

To reuse it in AEGIS: replace the state vector's inputs (RF defender metrics) with cyber-defence signals (detection coverage, dwell time, containment latency, which assets the blue team has disclosed), and replace the "generate spoofed I/Q" action with "select the next attack beat / lateral-movement target." The Evolver *algorithm* (LTC policy + curriculum + REINFORCE) transfers; the weights do not.

**Hard constraint:** an LLM/RL-driven attacker breaks determinism, so adversarial mode must be a **distinct scenario type**, quarantined from the deterministic scenarios that golden replays and scoring depend on (exactly as the AEGIS backlog already notes). Runs in adversarial mode carry a flag; golden-replay tests never touch them.

---

## Architecture stance: two repos, one seam — NOT a merge

Do **not** merge EW-3 into AEGIS. They have different toolchains (EW-3: PyTorch/ROCm/WSL research code, notebook-driven; AEGIS: the pnpm+uv modular monolith with strict layering and CI gates), different determinism models, and different lifecycles. The right structure:

- **EW-3 stays a standalone repo** that produces **versioned, checksummed model artifacts** (Defender checkpoints, later Evolver policies) — its output contract is "a manifested model file," nothing more.
- **AEGIS consumes those artifacts through the adapter seam** (Path A) and the pattern (Path B). The only coupling is the manifest: checkpoint hash, input/output schema, feature-schema version, known limitations. That is a clean, versionable interface across two independently-evolving systems.

This keeps AEGIS's "vendor SDKs behind adapters," "no external model in core CI," and determinism guarantees intact, while letting a real trained EW-3 model light up a real scenario.

---

## Preconditions / gates (why this is blocked today)

Per the EW-3 training playbook, none of this should start until:

1. **EW-3 Defender clears its Stage-0 gate** — a genuinely working classifier (not the current ~39% modulation plateau). A near-random detector behind an AEGIS scenario would produce meaningless alerts and destroy the experience. The authenticity head (real-vs-spoofed) is the one Path A leans on — it must be solid.
2. **A stable, checksummed Defender checkpoint exists** — currently the tracked checkpoints are only diagnostic probes; the real ones aren't even on disk. Path A's manifest needs a durable, hashed artifact.
3. (For Path B) **The Arena loop trains stably** through its Stage-3 gate — otherwise there's no validated Evolver pattern to port.

## Risks / open questions

- **Feature interface for Path A:** does AEGIS feed the Defender raw synthetic I/Q, or a distilled feature summary the scenario generates? Raw I/Q is truer to EW-3 but heavier; a feature form is lighter and fits AEGIS's feature-schema versioning better. Decide when the Defender's real input contract is stable.
- **Inference latency/determinism:** a local Defender forward per telemetry window must be fast enough for the tick engine and deterministic per checkpoint. Batch scoring per tick, pin the checkpoint, mock in CI.
- **Scope creep:** Path A is a bounded, high-value first step (one scenario + one adapter). Path B is a research effort (porting an RL loop). Do Path A first, in full, before touching Path B.

## Recommendation

When EW-3's Defender is trained: build **Path A only** first — the RF scenario pack + the manifested Defender adapter with a deterministic CI fake — as a self-contained AEGIS feature. It exercises the whole seam end to end and delivers a genuinely new scenario class. Treat Path B (adversarial mode via the Evolver pattern) as a separate, later initiative with its own spec, gated on both EW-3's Arena stability and AEGIS's adversarial-mode groundwork.
