"""HTML observability page for Phase 11 event streaming (HTTP only)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["realtime"])


@router.get("/realtime/observability", response_class=HTMLResponse)
async def observability_page(request: Request) -> HTMLResponse:
    base = str(request.base_url).rstrip("/")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AEGIS Event Streaming Observability</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem;
      background: #0b1220; color: #e8eefc; }}
    h1, h2 {{ color: #9ec5ff; }}
    section {{ margin-bottom: 2rem; padding: 1rem 1.25rem;
      border: 1px solid #2a3a5c; border-radius: 8px; }}
    pre {{ background: #111a2e; padding: 1rem; overflow: auto; border-radius: 6px; }}
    a {{ color: #7ec8ff; }}
    .note {{ color: #a8b3cf; font-size: 0.95rem; }}
  </style>
</head>
<body>
  <h1>AEGIS Phase 11 — Event Streaming Observability</h1>
  <p class="note">PostgreSQL is authoritative. Redis Streams provides at-least-once
    delivery. WebSocket live updates are deferred to Phase 12–13.</p>
  <section>
    <h2>Streaming status</h2>
    <pre id="status">Loading…</pre>
  </section>
  <section>
    <h2>Run events (PostgreSQL)</h2>
    <p>Enter a run ID from a persisted simulation:</p>
    <input id="runId" placeholder="run_…" style="width: 24rem; padding: 0.4rem;" />
    <button onclick="loadEvents()">Load events</button>
    <pre id="events">No run loaded.</pre>
  </section>
  <script>
    async function loadStatus() {{
      const res = await fetch('{base}/api/v1/realtime/streaming/status');
      document.getElementById('status').textContent = JSON.stringify(await res.json(), null, 2);
    }}
    async function loadEvents() {{
      const runId = document.getElementById('runId').value.trim();
      if (!runId) return;
      const url = '{base}/api/v1/realtime/runs/' + encodeURIComponent(runId) + '/events?limit=50';
      const res = await fetch(url);
      document.getElementById('events').textContent = JSON.stringify(await res.json(), null, 2);
    }}
    loadStatus();
    setInterval(loadStatus, 5000);
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)
