# ruff: noqa: E501
#!/usr/bin/env python3
"""Generate Phase 31 observability visual evidence pages and capture screenshots."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "handoffs" / "evidence" / "phase-31"
EVIDENCE.mkdir(parents=True, exist_ok=True)
HTML = EVIDENCE / "ops-dashboard.html"

API = "http://127.0.0.1:8000"


def fetch(path: str, cookies: dict[str, str] | None = None) -> tuple[int, object]:
    try:
        response = httpx.get(f"{API}{path}", cookies=cookies or {}, timeout=5.0)
        try:
            return response.status_code, response.json()
        except Exception:
            return response.status_code, response.text
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": str(exc)}


def main() -> None:
    health_code, health = fetch("/health")
    live_code, live = fetch("/live")
    ready_code, ready = fetch("/ready")
    diag_unauth_code, diag_unauth = fetch("/diagnostics")

    # Admin login for protected views
    client = httpx.Client(base_url=API, timeout=10.0)
    login = client.post("/api/v1/auth/dev/login", json={"userId": "user:admin-alpha"})
    cookies = dict(login.cookies)
    diag_code, diag = 0, {}
    metrics_code, metrics_text = 0, ""
    if login.status_code == 200:
        diag_resp = client.get("/diagnostics", cookies=cookies)
        content_type = diag_resp.headers.get("content-type", "")
        diag_code = diag_resp.status_code
        diag = diag_resp.json() if content_type.startswith("application/json") else diag_resp.text
        metrics_resp = client.get("/metrics", cookies=cookies)
        metrics_code, metrics_text = metrics_resp.status_code, metrics_resp.text

    # Viewer denied
    viewer = httpx.Client(base_url=API, timeout=10.0)
    vlogin = viewer.post("/api/v1/auth/dev/login", json={"userId": "user:viewer-alpha"})
    denied_code = 0
    if vlogin.status_code == 200:
        denied = viewer.get("/diagnostics", cookies=dict(viewer.cookies))
        denied_code = denied.status_code

    # Controlled Redis failure → readiness not_ready, then recovery
    readiness_failure = None
    readiness_recovery = None
    try:
        subprocess.run(["sudo", "redis-cli", "shutdown"], check=False, capture_output=True)
        time.sleep(0.8)
        readiness_failure = fetch("/ready")
        subprocess.run(["sudo", "redis-server", "--daemonize", "yes"], check=False, capture_output=True)
        time.sleep(1.0)
        readiness_recovery = fetch("/ready")
    except Exception as exc:  # noqa: BLE001
        readiness_failure = (0, {"error": str(exc)})
        subprocess.run(["sudo", "redis-server", "--daemonize", "yes"], check=False, capture_output=True)

    # Correlation round-trip
    corr = httpx.get(
        f"{API}/health",
        headers={
            "X-Request-Id": "req_PHASE31EVIDENCE000000001",
            "X-Correlation-Id": "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "traceparent": "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01",
        },
        timeout=5.0,
    )

    # Redaction demo (no secrets in output)
    from aegis_observability.redaction import REDACTED, redact_headers, redact_mapping

    redacted = redact_mapping(
        {
            "password": "should-not-appear",
            "authorization": "Bearer secret-token",
            "cookie": "aegis_session=secret",
            "safeField": "ok",
        }
    )
    redacted_headers = redact_headers(
        {"Authorization": "Bearer abc", "X-Request-Id": "req_1"}
    )

    dashboard = {
        "title": "AEGIS Phase 31 Local Operations Evidence",
        "note": "Telemetry is non-authoritative. Docker compose overlay unavailable in this environment; evidence from local API + contract dashboards.",
        "health": {"statusCode": health_code, "body": health},
        "live": {"statusCode": live_code, "body": live},
        "ready": {"statusCode": ready_code, "body": ready},
        "diagnosticsUnauth": {"statusCode": diag_unauth_code, "body": diag_unauth},
        "diagnosticsAdmin": {"statusCode": diag_code, "body": diag},
        "metricsAdmin": {"statusCode": metrics_code, "body": metrics_text},
        "diagnosticsViewerDenied": {"statusCode": denied_code},
        "readinessFailure": {
            "statusCode": readiness_failure[0] if readiness_failure else None,
            "body": readiness_failure[1] if readiness_failure else None,
        },
        "readinessRecovery": {
            "statusCode": readiness_recovery[0] if readiness_recovery else None,
            "body": readiness_recovery[1] if readiness_recovery else None,
        },
        "correlation": {
            "requestId": corr.headers.get("x-request-id"),
            "correlationId": corr.headers.get("x-correlation-id"),
            "traceparent": corr.headers.get("traceparent"),
        },
        "redaction": {"mapping": redacted, "headers": redacted_headers, "token": REDACTED},
        "panels": [
            {"name": "Service health / liveness", "question": "Is the API process alive?"},
            {"name": "Readiness + dependencies", "question": "Can the API safely receive traffic?"},
            {"name": "Protected diagnostics", "question": "Do admin-only ops endpoints enforce authz?"},
            {"name": "Correlation headers", "question": "Do requests preserve correlation context?"},
            {"name": "Redaction", "question": "Are secrets absent from telemetry payloads?"},
        ],
    }
    (EVIDENCE / "ops-snapshot.json").write_text(json.dumps(dashboard, indent=2) + "\n")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>AEGIS Phase 31 Observability Evidence</title>
  <style>
    :root {{ --bg:#0f1c24; --panel:#17303b; --ink:#e8f1f4; --accent:#3db8a0; --warn:#d9a441; --bad:#d46565; }}
    body {{ margin:0; font-family: "IBM Plex Sans", "Segoe UI", sans-serif; background: linear-gradient(160deg,#0f1c24,#1a3340 50%,#102028); color:var(--ink); }}
    header {{ padding:28px 36px 8px; }}
    h1 {{ margin:0; font-size:28px; letter-spacing:0.02em; }}
    .sub {{ opacity:0.8; margin-top:6px; max-width: dual; max-width: 720px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px; padding:20px 36px 40px; }}
    .card {{ background:rgba(23,48,59,0.92); border:1px solid rgba(61,184,160,0.25); border-radius:10px; padding:16px 18px; }}
    .card h2 {{ margin:0 0 10px; font-size:15px; color:var(--accent); text-transform:uppercase; letter-spacing:0.08em; }}
    pre {{ white-space:pre-wrap; word-break:break-word; font-size:12px; line-height:1.4; background:#0b151b; padding:10px; border-radius:6px; }}
    .ok {{ color:var(--accent); font-weight:600; }}
    .bad {{ color:var(--bad); font-weight:600; }}
    .warn {{ color:var(--warn); font-weight:600; }}
    .brand {{ font-size:13px; letter-spacing:0.18em; text-transform:uppercase; color:var(--accent); }}
  </style>
</head>
<body>
  <header>
    <div class="brand">AEGIS Command</div>
    <h1>Phase 31 Observability Evidence</h1>
    <p class="sub">Operational telemetry dashboard snapshot. Domain audit records and authoritative events remain in PostgreSQL — this view is diagnostic only.</p>
  </header>
  <div class="grid">
    <section class="card" id="health">
      <h2>Liveness /health + /live</h2>
      <div class="{'ok' if health_code==200 else 'bad'}">HTTP {health_code}</div>
      <pre>{json.dumps(health, indent=2)}</pre>
      <div class="{'ok' if live_code==200 else 'bad'}">/live HTTP {live_code}</div>
      <pre>{json.dumps(live, indent=2)}</pre>
    </section>
    <section class="card" id="ready">
      <h2>Readiness /ready</h2>
      <div class="{'ok' if ready_code==200 else 'warn'}">HTTP {ready_code}</div>
      <pre>{json.dumps(ready, indent=2)}</pre>
    </section>
    <section class="card" id="authz">
      <h2>Protected ops authz</h2>
      <p>Unauth /diagnostics: <span class="{'ok' if diag_unauth_code in (401,403) else 'bad'}">{diag_unauth_code}</span></p>
      <p>Viewer /diagnostics: <span class="{'ok' if denied_code in (401,403) else 'bad'}">{denied_code}</span></p>
      <p>Admin /diagnostics: <span class="{'ok' if diag_code in (200,503) else 'bad'}">{diag_code}</span></p>
      <p>Admin /metrics: <span class="{'ok' if metrics_code==200 else 'bad'}">{metrics_code}</span></p>
    </section>
    <section class="card" id="failure-recovery">
      <h2>Dependency failure + recovery</h2>
      <p>Redis stopped → /ready</p>
      <pre>{json.dumps(dashboard.get('readinessFailure'), indent=2)}</pre>
      <p>Redis restarted → /ready</p>
      <pre>{json.dumps(dashboard.get('readinessRecovery'), indent=2)}</pre>
    </section>
    <section class="card" id="correlation">
      <h2>Correlation context</h2>
      <pre>{json.dumps(dashboard['correlation'], indent=2)}</pre>
    </section>
    <section class="card" id="diagnostics">
      <h2>Admin diagnostics</h2>
      <pre>{json.dumps(diag, indent=2) if isinstance(diag, dict) else str(diag)[:2000]}</pre>
    </section>
    <section class="card" id="metrics">
      <h2>Admin metrics snapshot</h2>
      <pre>{metrics_text[:2000] if metrics_text else '(empty)'}</pre>
    </section>
    <section class="card" id="redaction">
      <h2>Redaction evidence</h2>
      <pre>{json.dumps({'mapping': redacted, 'headers': redacted_headers}, indent=2)}</pre>
    </section>
    <section class="card" id="grafana-note">
      <h2>Dashboard inventory (provisioned)</h2>
      <pre>{json.dumps(dashboard['panels'], indent=2)}</pre>
      <p class="warn">Compose Grafana/Tempo blocked by host Docker overlayfs; panel definitions live in infra/observability/grafana/dashboards/aegis-operations.json.</p>
    </section>
  </div>
</body>
</html>
"""
    HTML.write_text(html)
    print(f"Wrote {HTML}")
    print(f"health={health_code} ready={ready_code} diag_admin={diag_code} denied={denied_code}")


if __name__ == "__main__":
    # Wait briefly for API
    for _ in range(30):
        try:
            if httpx.get(f"{API}/health", timeout=1.0).status_code == 200:
                break
        except Exception:
            time.sleep(0.5)
    main()
