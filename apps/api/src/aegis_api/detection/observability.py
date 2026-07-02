"""HTML observability page for Phase 15 detection."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["detection"])


@router.get("/detection/observability", response_class=HTMLResponse)
async def detection_observability_page(request: Request) -> HTMLResponse:
    base = str(request.base_url).rstrip("/")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AEGIS Detection Observability</title>
  <style>
    body {{
      font-family: system-ui, sans-serif; margin: 2rem;
      background: #0b1220; color: #e8eefc;
    }}
    h1, h2 {{ color: #9ec5ff; }}
    section {{
      margin-bottom: 2rem; padding: 1rem 1.25rem;
      border: 1px solid #2a3a5c; border-radius: 8px;
    }}
    pre {{
      background: #111a2e; padding: 1rem; overflow: auto;
      border-radius: 6px; max-height: 28rem;
    }}
    input {{ width: 24rem; padding: 0.4rem; margin-right: 0.5rem; }}
    button {{ padding: 0.45rem 0.9rem; cursor: pointer; }}
    .note {{ color: #a8b3cf; font-size: 0.95rem; }}
    .phase16 {{ border-left: 3px solid #ffb347; padding-left: 0.75rem; }}
  </style>
</head>
<body>
  <h1>AEGIS Phase 15 — Rules and Statistical Baselines</h1>
  <p class="note">Deterministic rules and calibrated statistical baselines consume Phase 14
    feature vectors. Phase 16 Isolation Forest anomaly models are intentionally deferred.</p>
  <section>
    <h2>Rule registry</h2>
    <pre id="rules">Loading…</pre>
  </section>
  <section>
    <h2>Baseline manifest</h2>
    <pre id="baselines">Loading…</pre>
  </section>
  <section>
    <h2>Run detection evaluation</h2>
    <input id="runId" placeholder="run_…" />
    <button onclick="evaluateRun(false)">Evaluate and persist</button>
    <button onclick="evaluateRun(true)">Dry run</button>
    <pre id="evaluation">No evaluation yet.</pre>
  </section>
  <section class="phase16">
    <h2>Phase 16 deferred</h2>
    <p class="note">Isolation Forest learned anomaly detection is not implemented in Phase 15.
      This page shows only transparent rules and statistical baseline deviations.</p>
  </section>
  <script>
    async function loadRules() {{
      const res = await fetch('{base}/api/v1/detection/rules');
      document.getElementById('rules').textContent = JSON.stringify(await res.json(), null, 2);
    }}
    async function loadBaselines() {{
      const res = await fetch('{base}/api/v1/detection/baselines');
      document.getElementById('baselines').textContent = res.ok
        ? JSON.stringify(await res.json(), null, 2)
        : 'Baseline manifest not found — run scripts/calibrate_baselines.py';
    }}
    async function evaluateRun(dryRun) {{
      const runId = document.getElementById('runId').value.trim();
      if (!runId) return;
      const res = await fetch('{base}/api/v1/detection/evaluate', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ schemaVersion: 1, runId, dryRun }}),
      }});
      document.getElementById('evaluation').textContent = JSON.stringify(await res.json(), null, 2);
    }}
    loadRules();
    loadBaselines();
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)
