"""HTML diagnostic page for Phase 12 WebSocket gateway."""

# ruff: noqa: E501

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["websocket"])


@router.get("/realtime/websocket-demo", response_class=HTMLResponse)
async def websocket_demo_page(request: Request) -> HTMLResponse:
    base = str(request.base_url).rstrip("/")
    ws_scheme = "wss" if request.url.scheme == "https" else "ws"
    ws_host = request.headers.get("host", "localhost:8000")
    ws_path = "/ws/v1/realtime"
    ws_url = f"{ws_scheme}://{ws_host}{ws_path}"
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AEGIS WebSocket Gateway Demo</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #0b1220; color: #e8eefc; }}
    h1, h2 {{ color: #9ec5ff; }}
    section {{ margin-bottom: 1.5rem; padding: 1rem 1.25rem; border: 1px solid #2a3a5c; border-radius: 8px; }}
    input, button {{ margin: 0.25rem 0.5rem 0.25rem 0; padding: 0.4rem 0.6rem; }}
    pre {{ background: #111a2e; padding: 1rem; overflow: auto; border-radius: 6px; max-height: 320px; }}
    .ok {{ color: #7dffb3; }}
    .err {{ color: #ff8f8f; }}
    .note {{ color: #a8b3cf; font-size: 0.95rem; }}
    #status.connected {{ color: #7dffb3; }}
    #status.disconnected {{ color: #ff8f8f; }}
  </style>
</head>
<body>
  <h1>AEGIS Phase 12 — WebSocket Gateway Demo</h1>
  <p class="note">Transport-only diagnostic page. Command-centre live reducers remain Phase 13.
    PostgreSQL is authoritative; reconnect uses <code>lastAppliedSequence</code>.</p>
  <section>
    <h2>Connection</h2>
    <label>WS URL <input id="wsUrl" value="{ws_url}" size="48" /></label><br/>
    <label>Auth token <input id="authToken" value="aegis-dev-token" size="24" /></label><br/>
    <button id="connectBtn">Connect</button>
    <button id="disconnectBtn">Disconnect</button>
    <p>Status: <span id="status" class="disconnected">disconnected</span></p>
    <p>Connection ID: <span id="connectionId">—</span></p>
  </section>
  <section>
    <h2>Subscription</h2>
    <label>Run ID <input id="runId" placeholder="run_…" size="36" /></label>
    <label>Channel <input id="channel" value="events" size="12" /></label>
    <label>Last sequence <input id="lastSeq" value="0" size="6" /></label><br/>
    <button id="subscribeBtn">Subscribe</button>
    <button id="badSubscribeBtn">Subscribe (bad token run)</button>
    <button id="reconnectBtn">Reconnect with cursor</button>
  </section>
  <section>
    <h2>Event log</h2>
    <pre id="log">Waiting…</pre>
  </section>
  <script>
    const API_BASE = '{base}';
    let socket = null;
    let lastAppliedSequence = 0;
    let connectionId = null;

    function log(line, cls) {{
      const el = document.getElementById('log');
      const prefix = cls === 'err' ? '✗ ' : cls === 'ok' ? '✓ ' : '• ';
      el.textContent = prefix + line + '\\n' + el.textContent;
    }}

    function traceId() {{
      const chars = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
      let body = '';
      for (let i = 0; i < 26; i++) body += chars[Math.floor(Math.random() * chars.length)];
      return 'trc_' + body;
    }}

    function frame(messageType, payload) {{
      return JSON.stringify({{
        schemaVersion: 1,
        protocolVersion: 1,
        messageType,
        traceId: traceId(),
        sentAt: new Date().toISOString().replace(/\\.\\d{{3}}Z$/, '.000Z'),
        payload,
      }});
    }}

    function setStatus(connected) {{
      const status = document.getElementById('status');
      status.textContent = connected ? 'connected' : 'disconnected';
      status.className = connected ? 'connected' : 'disconnected';
    }}

    function connect(token) {{
      return new Promise((resolve, reject) => {{
        if (socket) socket.close();
        const url = document.getElementById('wsUrl').value.trim();
        socket = new WebSocket(url);
        socket.onopen = () => {{
          socket.send(frame('hello', {{ protocolVersion: 1, authToken: token }}));
        }};
        socket.onmessage = (event) => {{
          const msg = JSON.parse(event.data);
          if (msg.messageType === 'hello_ack') {{
            connectionId = msg.payload.connectionId;
            document.getElementById('connectionId').textContent = connectionId;
            setStatus(true);
            log('hello_ack principal=' + msg.payload.principalId, 'ok');
            resolve();
            return;
          }}
          if (msg.messageType === 'ping') {{
            socket.send(frame('pong', {{ serverTime: msg.payload.serverTime }}));
            return;
          }}
          if (msg.messageType === 'event') {{
            const seq = msg.payload.envelope.event.sequence;
            lastAppliedSequence = Math.max(lastAppliedSequence, seq);
            log('event seq=' + seq + ' type=' + msg.payload.envelope.event.type, 'ok');
            return;
          }}
          if (msg.messageType === 'subscribed') {{
            log('subscribed mode=' + msg.payload.deliveryMode, 'ok');
            return;
          }}
          if (msg.messageType === 'resync_complete') {{
            lastAppliedSequence = msg.payload.toSequence;
            document.getElementById('lastSeq').value = String(lastAppliedSequence);
            log('resync_complete delivered=' + msg.payload.eventsDelivered, 'ok');
            return;
          }}
          if (msg.messageType === 'snapshot_required') {{
            log('snapshot_required reason=' + msg.payload.reason, 'err');
            return;
          }}
          if (msg.messageType === 'error') {{
            log('error ' + msg.payload.error.code + ': ' + msg.payload.error.message, 'err');
            return;
          }}
          if (msg.messageType === 'warning') {{
            log('warning ' + msg.payload.code + ': ' + msg.payload.message);
            return;
          }}
          log(msg.messageType + ' ' + JSON.stringify(msg.payload));
        }};
        socket.onerror = () => reject(new Error('WebSocket error'));
        socket.onclose = () => {{
          setStatus(false);
          log('connection closed');
        }};
      }});
    }}

    document.getElementById('connectBtn').onclick = async () => {{
      try {{
        await connect(document.getElementById('authToken').value);
      }} catch (e) {{
        log(String(e), 'err');
      }}
    }};

    document.getElementById('disconnectBtn').onclick = () => {{
      if (socket) socket.close();
    }};

    document.getElementById('subscribeBtn').onclick = () => {{
      if (!socket || socket.readyState !== WebSocket.OPEN) {{
        log('Not connected', 'err');
        return;
      }}
      const runId = document.getElementById('runId').value.trim();
      const channel = document.getElementById('channel').value.trim();
      const lastAppliedSequence = Number(document.getElementById('lastSeq').value || 0);
      socket.send(frame('subscribe', {{ runId, channel, lastAppliedSequence }}));
    }};

    document.getElementById('badSubscribeBtn').onclick = async () => {{
      try {{
        await connect('invalid-token');
      }} catch (e) {{
        log('bad auth rejected: ' + String(e), 'err');
      }}
    }};

    document.getElementById('reconnectBtn').onclick = async () => {{
      const token = document.getElementById('authToken').value;
      const runId = document.getElementById('runId').value.trim();
      const channel = document.getElementById('channel').value.trim();
      const cursor = lastAppliedSequence;
      if (socket) socket.close();
      await new Promise((r) => setTimeout(r, 500));
      await connect(token);
      document.getElementById('lastSeq').value = String(cursor);
      socket.send(frame('subscribe', {{ runId, channel, lastAppliedSequence: cursor }}));
      log('reconnected with cursor=' + cursor, 'ok');
    }};

    fetch(API_BASE + '/api/v1/realtime/streaming/status')
      .then((r) => r.json())
      .then((data) => log('streaming status outbox=' + data.outboxUnpublished));
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)
