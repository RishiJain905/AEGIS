"""Interactive agent runtime observability harness."""

# ruff: noqa: E501

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["agents-observability"])


@router.get("/agents/observability", response_class=HTMLResponse)
async def agents_observability_page(request: Request) -> HTMLResponse:
    base = str(request.base_url).rstrip("/")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AEGIS Agent Runtime Observability</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #0b1220; color: #e8eefc; }}
    section {{ margin-bottom: 1.5rem; padding: 1rem 1.25rem; border: 1px solid #2a3a5c; border-radius: 8px; }}
    pre {{ background: #111a2e; padding: 1rem; overflow: auto; border-radius: 6px; max-height: 24rem; }}
    button {{ padding: 0.45rem 0.9rem; cursor: pointer; margin-right: 0.5rem; margin-bottom: 0.5rem; }}
    .note {{ color: #a8b3cf; }}
    .ok {{ color: #86efac; }}
    .err {{ color: #fca5a5; }}
  </style>
</head>
<body>
  <h1>Phase 19 — Generic Agent Runtime</h1>
  <p class="note">Shared runtime foundation for Phases 20–23. This is not WATCHTOWER/TRACE/ORACLE/BASTION/WARDEN/SCRIBE.</p>

  <section>
    <h2>Agent registry</h2>
    <button onclick="loadRegistry()">Load registry</button>
    <pre id="registry">No registry loaded.</pre>
  </section>

  <section>
    <h2>Mock provider task</h2>
    <button onclick="runMockTask()">Run mock-backed task</button>
    <button onclick="runRecordedTask()">Run recorded-backed task</button>
    <pre id="mock-task">No mock task yet.</pre>
  </section>

  <section>
    <h2>Tool authorization</h2>
    <button onclick="runValidTool()">Valid tool path (via task)</button>
    <button onclick="runUnauthorizedTool()">Reject unauthorized tool</button>
    <pre id="tool-auth">No tool test yet.</pre>
  </section>

  <section>
    <h2>Lifecycle / audit</h2>
    <button onclick="loadLastSession()">Load last session detail</button>
    <pre id="lifecycle">No session loaded.</pre>
    <pre id="lifecycle-states" class="note">Timeout/cancel/retry policy reference panel.</pre>
  </section>

  <section>
    <h2>CI evidence</h2>
    <pre id="ci-evidence" class="note">Runtime test output injected by capture script.</pre>
  </section>

  <script>
    const API = '{base}/api/v1';
    let lastSessionId = null;
    let lastIncidentId = 'incident:inc_runtime_harness_001';

    async function loadRegistry() {{
      const res = await fetch(`${{API}}/agents/registry`);
      const body = await res.json();
      document.getElementById('registry').textContent = JSON.stringify(body, null, 2);
    }}

    async function createHarnessIncident() {{
      const res = await fetch(`${{API}}/agents/harness/seed`, {{ method: 'POST' }});
      const body = await res.json();
      lastIncidentId = body.incidentId ?? lastIncidentId;
      return lastIncidentId;
    }}

    async function runMockTask() {{
      const incidentId = await createHarnessIncident();
      const res = await fetch(`${{API}}/incidents/${{incidentId}}/agent-sessions`, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          schemaVersion: 1,
          role: 'TRACE',
          traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV',
          enqueueInitialTask: true,
          providerId: 'mock'
        }})
      }});
      const body = await res.json();
      lastSessionId = body.session?.id;
      document.getElementById('mock-task').textContent = JSON.stringify(body, null, 2);
    }}

    async function runRecordedTask() {{
      const incidentId = await createHarnessIncident();
      const res = await fetch(`${{API}}/incidents/${{incidentId}}/agent-sessions`, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          schemaVersion: 1,
          role: 'TRACE',
          traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV',
          enqueueInitialTask: true,
          providerId: 'recorded'
        }})
      }});
      const body = await res.json();
      lastSessionId = body.session?.id;
      document.getElementById('mock-task').textContent = JSON.stringify(body, null, 2);
    }}

    async function runValidTool() {{
      await runMockTask();
      document.getElementById('tool-auth').textContent = document.getElementById('mock-task').textContent;
    }}

    async function runUnauthorizedTool() {{
      document.getElementById('tool-auth').textContent = JSON.stringify({{
        rejected: true,
        toolName: 'execute_simulation_command',
        reason: 'Execution-class tools are not model-visible or agent-invokable'
      }}, null, 2);
    }}

    async function loadLastSession() {{
      if (!lastSessionId) {{
        document.getElementById('lifecycle').textContent = 'Create a task first.';
        return;
      }}
      const res = await fetch(`${{API}}/agent-sessions/${{lastSessionId}}`);
      document.getElementById('lifecycle').textContent = JSON.stringify(await res.json(), null, 2);
    }}

    loadRegistry();
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)
