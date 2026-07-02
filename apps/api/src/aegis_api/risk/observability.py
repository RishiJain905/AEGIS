"""Graph risk observability page."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["risk-observability"])


@router.get("/risk/observability", response_class=HTMLResponse)
async def risk_observability() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AEGIS Graph Risk Observability</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; background: #0f172a; color: #e2e8f0; }
    h1 { color: #f8fafc; }
    h2 { color: #94a3b8; margin-top: 2rem; }
    .note { color: #cbd5e1; max-width: 720px; line-height: 1.5; }
    code { background: #1e293b; padding: 0.15rem 0.4rem; border-radius: 4px; }
    table { border-collapse: collapse; margin-top: 1rem; }
    th, td { border: 1px solid #334155; padding: 0.5rem 0.75rem; text-align: left; }
    th { background: #1e293b; }
  </style>
</head>
<body>
  <h1>Phase 17 — Graph Risk Propagation</h1>
  <p class="note">
    Deterministic bounded graph-risk propagation (<code>graph-risk-v1</code>) consumes
    Phase 15 rule alerts and Phase 16 model scores as origin signals, propagates across
    eligible graph relationships with distance and temporal decay, and emits
    <code>risk.score.computed</code> plus <code>risk.projection.updated</code> events.
    This is transparent rule-based propagation — not a GNN or LLM analyst.
  </p>
  <h2>API endpoints</h2>
  <table>
    <tr><th>Method</th><th>Path</th><th>Purpose</th></tr>
    <tr><td>GET</td><td>/api/v1/risk/config</td><td>Default RiskEngineConfig</td></tr>
    <tr><td>POST</td><td>/api/v1/risk/compute</td><td>Run propagation for a run</td></tr>
    <tr><td>GET</td><td>/api/v1/risk/scores/{runId}</td><td>Latest per-asset risk scores</td></tr>
  </table>
  <h2>Operational commands</h2>
  <pre><code>uv run python scripts/run_graph_risk.py --run-id &lt;run_id&gt;
uv run python scripts/evaluate_graph_risk.py --steps 300</code></pre>
</body>
</html>"""
