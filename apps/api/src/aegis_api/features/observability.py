"""HTML observability page for Phase 14 feature pipeline."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["features"])


@router.get("/features/observability", response_class=HTMLResponse)
async def feature_observability_page(request: Request) -> HTMLResponse:
    base = str(request.base_url).rstrip("/")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AEGIS Feature Pipeline Observability</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem;
      background: #0b1220; color: #e8eefc; }}
    h1, h2 {{ color: #9ec5ff; }}
    section {{ margin-bottom: 2rem; padding: 1rem 1.25rem;
      border: 1px solid #2a3a5c; border-radius: 8px; }}
    pre {{ background: #111a2e; padding: 1rem; overflow: auto; border-radius: 6px;
      max-height: 28rem; }}
    input {{ width: 24rem; padding: 0.4rem; margin-right: 0.5rem; }}
    button {{ padding: 0.45rem 0.9rem; cursor: pointer; }}
    .ok {{ color: #7dffb3; }}
    .bad {{ color: #ff8f8f; }}
    .note {{ color: #a8b3cf; font-size: 0.95rem; }}
  </style>
</head>
<body>
  <h1>AEGIS Phase 14 — Feature Pipeline</h1>
  <p class="note">Features are derived from PostgreSQL domain events only.
    This page demonstrates schema version, feature computation, offline/online parity,
    deterministic checksums, and rejection handling. Detection rules (Phase 15) and
    anomaly models (Phase 16) are intentionally not implemented here.</p>
  <section>
    <h2>Feature schema manifest</h2>
    <pre id="schema">Loading…</pre>
  </section>
  <section>
    <h2>Persisted run feature computation</h2>
    <input id="runId" placeholder="run_…" />
    <button onclick="computeFeatures()">Compute features</button>
    <button onclick="parityCheck()">Offline/online parity</button>
    <button onclick="repeatDeterminism()">Repeat determinism check</button>
    <pre id="compute">No run loaded.</pre>
  </section>
  <section>
    <h2>Parity and determinism</h2>
    <pre id="parity">No parity check yet.</pre>
  </section>
  <section>
    <h2>Invalid / duplicate / hidden-truth demo</h2>
    <p class="note">Use tests or POST /api/v1/features/compute on runs containing
      hidden-condition events — rejections appear in the compute response.</p>
    <pre id="rejections">Run compute to see rejections.</pre>
  </section>
  <script>
    async function loadSchema() {{
      const res = await fetch('{base}/api/v1/features/schema');
      document.getElementById('schema').textContent = JSON.stringify(await res.json(), null, 2);
    }}
    async function computeFeatures() {{
      const runId = document.getElementById('runId').value.trim();
      if (!runId) return;
      const res = await fetch('{base}/api/v1/features/compute', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ schemaVersion: 1, runId, mode: 'full' }}),
      }});
      const data = await res.json();
      const sample = data.vectors && data.vectors.length ? data.vectors[0] : null;
      document.getElementById('compute').textContent = JSON.stringify({{
        vectorCount: data.vectors?.length ?? 0,
        outputChecksum: data.outputChecksum,
        lastProcessedSequence: data.lastProcessedSequence,
        sampleVector: sample,
      }}, null, 2);
      document.getElementById('rejections').textContent = JSON.stringify(
        data.rejections ?? [], null, 2);
    }}
    async function parityCheck() {{
      const runId = document.getElementById('runId').value.trim();
      if (!runId) return;
      const res = await fetch('{base}/api/v1/features/parity-check', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ schemaVersion: 1, runId }}),
      }});
      const data = await res.json();
      const cls = data.matching ? 'ok' : 'bad';
      document.getElementById('parity').innerHTML =
        '<span class="' + cls + '">matching=' + data.matching + '</span>\\n' +
        JSON.stringify(data, null, 2);
    }}
    async function repeatDeterminism() {{
      const runId = document.getElementById('runId').value.trim();
      if (!runId) return;
      const body = JSON.stringify({{ schemaVersion: 1, runId, mode: 'full' }});
      const first = await (await fetch('{base}/api/v1/features/compute', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body,
      }})).json();
      const second = await (await fetch('{base}/api/v1/features/compute', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body,
      }})).json();
      const matching = first.outputChecksum === second.outputChecksum;
      document.getElementById('parity').textContent = JSON.stringify({{
        firstChecksum: first.outputChecksum,
        secondChecksum: second.outputChecksum,
        deterministic: matching,
        vectorCountFirst: first.vectors?.length ?? 0,
        vectorCountSecond: second.vectors?.length ?? 0,
      }}, null, 2);
    }}
    loadSchema();
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)
