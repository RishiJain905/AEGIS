# v1.0 Release Preparation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prepare AEGIS v1.0 with accurate operator documentation, reproducible release metadata, a deterministic local demo, and evidence-linked release gates.

**Architecture:** Keep the Phase 34 local production-like Compose stack as the only staging stand-in under ADR 0033. Generate a schema-versioned release manifest from Git, Docker inspection, the Alembic head, scenario/model artifacts, and CI SBOM references; keep the demo as a thin standard-library client over existing canonical HTTP routes.

**Tech Stack:** Markdown, JSON Schema, Python 3.12, pytest, Docker Compose, pnpm, uv, existing Phase 34 validation harness.

---

### Task 1: Establish release contract tests

- Add tests for manifest schema/checksum validation and deterministic demo-manifest fields.
- Run the focused tests first and confirm the new behavior fails before adding implementation.

### Task 2: Implement release metadata

- Add the release manifest schema, generator, verifier, generated manifest, demo manifest, and attribution generator.
- Update package and shared workspace versions to `1.0.0`; regenerate the Python lock metadata.

### Task 3: Finalize user/operator documentation

- Replace the root quick start and add clean-machine, operator, troubleshooting, security scope, contribution, and release documents.
- Update provider and scenario-authoring pointers, deployment wording, and known limitation references.

### Task 4: Add and exercise the deterministic demo

- Implement `scripts/demo_v1.py` with seed `42`, local health/auth/run checks, and URL guidance for the existing graph, detection, provider, agent, approval, replay, cinematic, and after-action surfaces.

### Task 5: Verify release readiness

- Generate and validate the manifest, run focused tests, run the demo against the local stack, perform a fresh-clone install/offline walkthrough, and run the repository verifier.
- Keep all changes uncommitted; record exact failures or limitations rather than weakening gates.
