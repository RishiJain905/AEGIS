"""Interactive provider observability harness for Phase 18."""

# ruff: noqa: E501

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["providers-observability"])


@router.get("/providers/observability", response_class=HTMLResponse)
async def providers_observability_page(request: Request) -> HTMLResponse:
    base = str(request.base_url).rstrip("/")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AEGIS Model Provider Observability</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #0b1220; color: #e8eefc; }}
    section {{ margin-bottom: 1.5rem; padding: 1rem 1.25rem; border: 1px solid #2a3a5c; border-radius: 8px; }}
    pre {{ background: #111a2e; padding: 1rem; overflow: auto; border-radius: 6px; max-height: 24rem; }}
    button {{ padding: 0.45rem 0.9rem; cursor: pointer; margin-right: 0.5rem; margin-bottom: 0.5rem; }}
    .note {{ color: #a8b3cf; font-size: 0.95rem; }}
    .ok {{ color: #86efac; }}
    .err {{ color: #fca5a5; }}
    .meta {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem; }}
    .meta div {{ background: #111a2e; padding: 0.75rem; border-radius: 6px; }}
    label {{ display: block; margin-bottom: 0.35rem; color: #a8b3cf; }}
  </style>
</head>
<body>
  <h1>Phase 18 — Model Provider Abstraction</h1>
  <p class="note">Provider-neutral generation harness. This is infrastructure for Phase 19+ agent runtime — not an agent workflow.</p>

  <section>
    <h2>Provider configuration</h2>
    <pre id="config">Loading…</pre>
  </section>

  <section>
    <h2>Mock provider — structured success</h2>
    <button onclick="runMockSuccess()">Run mock structured output</button>
    <pre id="mock-success">No request yet.</pre>
  </section>

  <section>
    <h2>Recorded provider — deterministic replay</h2>
    <button onclick="runRecordedReplay()">Replay recorded fixture</button>
    <pre id="recorded-replay">No replay yet.</pre>
  </section>

  <section>
    <h2>Canonical response metadata</h2>
    <div class="meta" id="metadata">
      <div><label>Provider</label><span id="meta-provider">—</span></div>
      <div><label>Model</label><span id="meta-model">—</span></div>
      <div><label>Latency</label><span id="meta-latency">—</span></div>
      <div><label>Usage</label><span id="meta-usage">—</span></div>
    </div>
    <pre id="metadata-json">No metadata yet.</pre>
  </section>

  <section>
    <h2>Structured output validation</h2>
    <button onclick="runStructuredValid()">Valid structured output</button>
    <button onclick="runStructuredInvalid()">Reject malformed output</button>
    <pre id="structured-output">No structured output test yet.</pre>
  </section>

  <section>
    <h2>Normalized failure behavior</h2>
    <button onclick="runMissingCredentials()">Missing credentials (OpenAI)</button>
    <button onclick="runUnsupportedCapability()">Unsupported capability</button>
    <pre id="failure-output">No failure test yet.</pre>
  </section>

  <section>
    <h2>CI without external inference</h2>
    <p class="note ok">Default provider is <code>mock</code>. Core tests use mock/recorded providers only.</p>
    <pre id="ci-evidence">Run: uv run pytest tests/agents/provider-conformance -q</pre>
  </section>

  <script>
    const baseRequest = {{
      schemaVersion: 1,
      requestId: 'gen_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      modelConfig: {{
        schemaVersion: 1,
        providerId: 'mock',
        modelId: 'mock-v1',
        promptVersion: 'phase18-v1',
        temperature: 0
      }},
      messages: [
        {{ role: 'system', content: 'System prompt' }},
        {{ role: 'user', content: 'Summarize' }}
      ],
      capabilitiesRequired: ['structured_output'],
      structuredOutput: {{
        schemaVersion: 1,
        jsonSchema: {{
          type: 'object',
          properties: {{
            summary: {{ type: 'string' }},
            confidence: {{ type: 'number', minimum: 0, maximum: 1 }}
          }},
          required: ['summary', 'confidence'],
          additionalProperties: false
        }},
        strict: true,
        maxRepairAttempts: 0
      }},
      maxOutputTokens: 1024
    }};

    function updateMetadata(result) {{
      const response = result.response;
      if (!response) return;
      document.getElementById('meta-provider').textContent = response.providerId;
      document.getElementById('meta-model').textContent = response.modelId;
      document.getElementById('meta-latency').textContent = response.latencyMs + ' ms';
      document.getElementById('meta-usage').textContent = JSON.stringify(response.usage);
      document.getElementById('metadata-json').textContent = JSON.stringify(response, null, 2);
    }}

    async function postGenerate(request, providerId, targetId) {{
      const res = await fetch('{base}/api/v1/providers/generate', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          schemaVersion: 1,
          providerId,
          dryRun: false,
          request
        }})
      }});
      const payload = await res.json();
      document.getElementById(targetId).textContent = JSON.stringify(payload, null, 2);
      updateMetadata(payload);
      return payload;
    }}

    async function loadConfig() {{
      const res = await fetch('{base}/api/v1/providers/config');
      document.getElementById('config').textContent = JSON.stringify(await res.json(), null, 2);
    }}

    async function runMockSuccess() {{
      await postGenerate(baseRequest, 'mock', 'mock-success');
    }}

    async function runRecordedReplay() {{
      const recordedRequest = JSON.parse(JSON.stringify(baseRequest));
      recordedRequest.modelConfig.providerId = 'recorded';
      recordedRequest.modelConfig.modelId = 'recorded-v1';
      recordedRequest.providerId = 'recorded';
      await postGenerate(recordedRequest, 'recorded', 'recorded-replay');
    }}

    async function runStructuredValid() {{
      await postGenerate(baseRequest, 'mock', 'structured-output');
    }}

    async function runStructuredInvalid() {{
      const invalidRequest = JSON.parse(JSON.stringify(baseRequest));
      invalidRequest.messages[1].content = 'Return invalid structured output please';
      await postGenerate(invalidRequest, 'mock', 'structured-output');
    }}

    async function runMissingCredentials() {{
      const openaiRequest = JSON.parse(JSON.stringify(baseRequest));
      openaiRequest.modelConfig.providerId = 'openai';
      openaiRequest.providerId = 'openai';
      delete openaiRequest.structuredOutput;
      openaiRequest.capabilitiesRequired = [];
      const payload = await postGenerate(openaiRequest, 'openai', 'failure-output');
      if (payload.error && payload.error.code === 'CREDENTIALS_MISSING') {{
        document.getElementById('failure-output').textContent += '\\n\\nSafe rejection confirmed.';
      }}
    }}

    async function runUnsupportedCapability() {{
      const badRequest = JSON.parse(JSON.stringify(baseRequest));
      badRequest.capabilitiesRequired = ['vision'];
      await postGenerate(badRequest, 'mock', 'failure-output');
    }}

    loadConfig();
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)
