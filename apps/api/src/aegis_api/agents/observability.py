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
  <h1>Phase 19–22 — Agent Runtime, Investigation &amp; Proposals</h1>
  <p class="note">Shared runtime foundation (Phase 19), WATCHTOWER/TRACE investigation (Phase 20), ORACLE hypothesis generation (Phase 21), and BASTION/WARDEN proposal policy (Phase 22).</p>

  <section>
    <h2>Phase 22 — BASTION / WARDEN</h2>
    <button onclick="triggerBastion()">Trigger BASTION for harness run</button>
    <button onclick="triggerWarden()">Trigger WARDEN re-evaluation</button>
    <button onclick="loadProposalArtifacts()">Show proposal &amp; policy artifacts</button>
    <button onclick="showBlockedProposal()">Show blocked/malformed proposal</button>
    <pre id="bastion-warden">No BASTION/WARDEN activity yet.</pre>
  </section>

  <section>
    <h2>Phase 21 — ORACLE</h2>
    <button onclick="triggerOracle()">Trigger ORACLE for harness run</button>
    <button onclick="loadOracleHypotheses()">Show hypothesis artifacts</button>
    <button onclick="showInvalidOracleOutput()">Show invalid ORACLE output rejection</button>
    <pre id="oracle-observability">No ORACLE activity yet.</pre>
  </section>

  <section>
    <h2>Phase 20 — WATCHTOWER / TRACE</h2>
    <button onclick="triggerWatchtower()">Trigger WATCHTOWER for harness run</button>
    <button onclick="loadInvestigationDetail()">Show investigation detail</button>
    <button onclick="loadTraceSession()">Load TRACE session detail</button>
    <pre id="watchtower-trace">No WATCHTOWER/TRACE activity yet.</pre>
  </section>

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
    let lastRunId = null;
    let lastTraceSessionId = null;
    let lastOracleSessionId = null;
    let lastBastionSessionId = null;
    let lastProposalId = null;

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

    async function resolveHarnessRunId() {{
      if (lastRunId) {{
        return lastRunId;
      }}
      const incidentId = await createHarnessIncident();
      const incidentRes = await fetch(`${{API}}/incidents/${{incidentId}}`);
      const incident = await incidentRes.json();
      lastRunId = incident.runId;
      return lastRunId;
    }}

    async function triggerWatchtower() {{
      const runId = await resolveHarnessRunId();
      const res = await fetch(`${{API}}/runs/${{runId}}/investigation/trigger-watchtower`, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          schemaVersion: 1,
          runId,
          alertIds: [],
          traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV',
          providerId: 'mock',
          idempotencyKey: `watchtower-${{Date.now()}}`
        }})
      }});
      const body = await res.json();
      lastIncidentId = body.incidentId ?? lastIncidentId;
      lastTraceSessionId = body.traceSessionId ?? null;
      lastSessionId = body.watchtowerSessionId ?? lastSessionId;
      document.getElementById('watchtower-trace').textContent = JSON.stringify(body, null, 2);
    }}

    async function loadInvestigationDetail() {{
      if (!lastIncidentId) {{
        document.getElementById('watchtower-trace').textContent = 'Trigger WATCHTOWER or seed harness first.';
        return;
      }}
      const res = await fetch(`${{API}}/incidents/${{lastIncidentId}}/investigation`);
      document.getElementById('watchtower-trace').textContent = JSON.stringify(await res.json(), null, 2);
    }}

    async function loadTraceSession() {{
      if (!lastTraceSessionId) {{
        document.getElementById('watchtower-trace').textContent = 'Trigger WATCHTOWER first to create TRACE session.';
        return;
      }}
      const res = await fetch(`${{API}}/agent-sessions/${{lastTraceSessionId}}`);
      document.getElementById('watchtower-trace').textContent = JSON.stringify(await res.json(), null, 2);
    }}

    async function triggerOracle() {{
      const runId = await resolveHarnessRunId();
      if (!lastIncidentId) {{
        await createHarnessIncident();
      }}
      if (!lastTraceSessionId) {{
        await triggerWatchtower();
      }}
      const res = await fetch(`${{API}}/runs/${{runId}}/investigation/trigger-oracle`, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          schemaVersion: 1,
          runId,
          incidentId: lastIncidentId,
          traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV',
          providerId: 'mock',
          idempotencyKey: `oracle-${{Date.now()}}`
        }})
      }});
      const body = await res.json();
      lastOracleSessionId = body.oracleSessionId ?? lastOracleSessionId;
      document.getElementById('oracle-observability').textContent = JSON.stringify(body, null, 2);
    }}

    async function loadOracleHypotheses() {{
      if (!lastIncidentId) {{
        document.getElementById('oracle-observability').textContent = 'Trigger ORACLE or seed harness first.';
        return;
      }}
      const res = await fetch(`${{API}}/incidents/${{lastIncidentId}}/investigation`);
      const detail = await res.json();
      document.getElementById('oracle-observability').textContent = JSON.stringify({{
        hypotheses: detail.hypotheses ?? [],
        hypothesisRevisions: detail.hypothesisRevisions ?? [],
        hypothesisComparisons: detail.hypothesisComparisons ?? [],
        verificationRequests: detail.verificationRequests ?? []
      }}, null, 2);
    }}

    function showInvalidOracleOutput() {{
      document.getElementById('oracle-observability').textContent = JSON.stringify({{
        rejected: true,
        role: 'ORACLE',
        promptVersion: 'phase21-oracle-v1',
        reason: 'Structured output validation failed: hypotheses array must contain at least 2 entries',
        safeFailure: true
      }}, null, 2);
    }}

    async function triggerBastion() {{
      const runId = await resolveHarnessRunId();
      if (!lastIncidentId) {{
        await createHarnessIncident();
      }}
      if (!lastTraceSessionId) {{
        await triggerWatchtower();
      }}
      if (!lastOracleSessionId) {{
        await triggerOracle();
      }}
      const res = await fetch(`${{API}}/runs/${{runId}}/investigation/trigger-bastion`, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          schemaVersion: 1,
          runId,
          incidentId: lastIncidentId,
          traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV',
          providerId: 'mock',
          idempotencyKey: `bastion-${{Date.now()}}`
        }})
      }});
      const body = await res.json();
      lastBastionSessionId = body.bastionSessionId ?? lastBastionSessionId;
      lastSessionId = lastBastionSessionId ?? lastSessionId;
      document.getElementById('bastion-warden').textContent = JSON.stringify(body, null, 2);
    }}

    async function triggerWarden() {{
      const runId = await resolveHarnessRunId();
      if (!lastProposalId) {{
        await loadProposalArtifacts();
      }}
      const res = await fetch(`${{API}}/runs/${{runId}}/investigation/trigger-warden`, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          schemaVersion: 1,
          runId,
          incidentId: lastIncidentId,
          proposalId: lastProposalId,
          traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV',
          providerId: 'mock',
          idempotencyKey: `warden-${{Date.now()}}`
        }})
      }});
      document.getElementById('bastion-warden').textContent = JSON.stringify(await res.json(), null, 2);
    }}

    async function loadProposalArtifacts() {{
      if (!lastIncidentId) {{
        document.getElementById('bastion-warden').textContent = 'Trigger BASTION or seed harness first.';
        return;
      }}
      const res = await fetch(`${{API}}/incidents/${{lastIncidentId}}/investigation`);
      const detail = await res.json();
      lastProposalId = detail.proposals?.[0]?.id ?? lastProposalId;
      document.getElementById('bastion-warden').textContent = JSON.stringify({{
        proposals: detail.proposals ?? [],
        proposalRevisions: detail.proposalRevisions ?? [],
        policyDecisions: detail.policyDecisions ?? []
      }}, null, 2);
    }}

    function showBlockedProposal() {{
      document.getElementById('bastion-warden').textContent = JSON.stringify({{
        rejected: true,
        role: 'WARDEN',
        promptVersion: 'phase22-warden-v1',
        outcome: 'block',
        reasonCodes: ['blocked_malformed_command', 'blocked_stale_revision'],
        note: 'Deterministic policy blocks malformed or stale proposals before execution'
      }}, null, 2);
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
