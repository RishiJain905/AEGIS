"""HTML observability page for Phase 16 anomaly model."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["models"])


@router.get("/models/observability", response_class=HTMLResponse)
async def models_observability_page(request: Request) -> HTMLResponse:
    base = str(request.base_url).rstrip("/")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AEGIS Anomaly Model Observability</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem;
      background: #0b1220; color: #e8eefc; }}
    section {{ margin-bottom: 2rem; padding: 1rem 1.25rem;
      border: 1px solid #2a3a5c; border-radius: 8px; }}
    pre {{ background: #111a2e; padding: 1rem; overflow: auto;
      border-radius: 6px; max-height: 28rem; }}
    input {{ width: 24rem; padding: 0.4rem; margin-right: 0.5rem; }}
    button {{ padding: 0.45rem 0.9rem; cursor: pointer; margin-right: 0.5rem; }}
    .note {{ color: #a8b3cf; font-size: 0.95rem; }}
    .phase17 {{ border-left: 3px solid #888; padding-left: 0.75rem; opacity: 0.85; }}
  </style>
</head>
<body>
  <h1>AEGIS Phase 16 — Isolation Forest Anomaly Model</h1>
  <p class="note">Advisory anomaly scores from the approved Isolation Forest model.
    Phase 15 rules and baselines remain active and provide fallback
    when the model is unavailable.</p>
  <section>
    <h2>Model manifest</h2>
    <pre id="manifest">Loading…</pre>
  </section>
  <section>
    <h2>Artifact verification</h2>
    <button onclick="verifyArtifact()">Verify checksum + schema</button>
    <button onclick="verifyCorrupt()">Simulate corrupt artifact</button>
    <pre id="verification">No verification yet.</pre>
  </section>
  <section>
    <h2>Score run</h2>
    <input id="runId" placeholder="run_…" />
    <button onclick="scoreRun(true)">Dry run</button>
    <button onclick="scoreRun(false)">Score and persist</button>
    <pre id="scoring">No scoring yet.</pre>
  </section>
  <section>
    <h2>Phase 15 baseline comparison</h2>
    <pre id="baselines">Loading…</pre>
  </section>
  <section class="phase17">
    <h2>Phase 17 — graph-risk propagation</h2>
    <p class="note">Graph risk propagation is implemented in Phase 17. See
    <a href="/risk/observability">/risk/observability</a> for the dedicated observability page.
    Isolation Forest scores remain tabular per-entity anomalies; graph risk is additive.</p>
  </section>
  <script>
    async function loadManifest() {{
      const res = await fetch('{base}/api/v1/models/manifest');
      document.getElementById('manifest').textContent = res.ok
        ? JSON.stringify(await res.json(), null, 2)
        : 'Manifest not found — run scripts/train_isolation_forest.py';
    }}
    async function verifyArtifact() {{
      const res = await fetch('{base}/api/v1/models/verify-artifact', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          schemaVersion: 1,
          manifestPath: 'models/manifests/isolation-forest-v1/manifest.json',
        }}),
      }});
      const verification = document.getElementById('verification');
      verification.textContent = JSON.stringify(await res.json(), null, 2);
    }}
    async function verifyCorrupt() {{
      const res = await fetch('{base}/api/v1/models/verify-artifact', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          schemaVersion: 1,
          manifestPath: 'models/manifests/isolation-forest-v1/manifest.json',
          artifactPath: 'models/manifests/isolation-forest-v1/manifest.json',
        }}),
      }});
      const verification = document.getElementById('verification');
      verification.textContent = JSON.stringify(await res.json(), null, 2);
    }}
    async function scoreRun(dryRun) {{
      const runId = document.getElementById('runId').value.trim();
      if (!runId) return;
      const res = await fetch('{base}/api/v1/models/score', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ schemaVersion: 1, runId, dryRun }}),
      }});
      document.getElementById('scoring').textContent = JSON.stringify(await res.json(), null, 2);
    }}
    async function loadBaselines() {{
      const res = await fetch('{base}/api/v1/detection/baselines');
      document.getElementById('baselines').textContent = res.ok
        ? JSON.stringify(await res.json(), null, 2)
        : 'Baseline manifest not found';
    }}
    loadManifest();
    loadBaselines();
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)
