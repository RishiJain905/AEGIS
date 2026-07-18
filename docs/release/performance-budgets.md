# AEGIS release performance budgets

Contract: `aegis.release-performance/v1` (JSON report written by
`tests/performance/release/run_performance.py`). The report records `schemaVersion`,
`runId`, deterministic scenario/seed, `budgets`, `metrics`, `skips`, `errors`, `status`, and
`durationSeconds`. Each metric records `sampleCount`, `p50Ms`, `p95Ms`, `p99Ms`, `budgetMs`,
and `status`. A metric is passing only when all three percentiles are within budget.

The API load defaults to 20 concurrent workers for 30 seconds with a ten-second worker
interval. `AEGIS_PERF_DURATION_SECONDS`, `AEGIS_PERF_CONCURRENCY`,
`AEGIS_PERF_REQUEST_INTERVAL_SECONDS`, `AEGIS_PERF_DB_SAMPLES`, and
`AEGIS_PERF_STREAM_EVENTS` are explicit local-only tuning knobs; changing them is retained
in the command log.

| Metric | p50 | p95 | p99 | Measurement |
| --- | ---: | ---: | ---: | --- |
| `api.load.read` | 300 ms | 500 ms | 750 ms | Scenarios, runs, graph, incidents, and event-range hot reads |
| `api.load.command` | 300 ms | 750 ms | 1,500 ms | Real local `POST /api/v1/realtime/backfill` command |
| `stream.outbox_to_ws` | 250 ms | 750 ms | 1,500 ms | Recorded-at to WebSocket event after PostgreSQL outbox and Redis relay |
| `db.event_range_fetch` | 100 ms | 300 ms | 750 ms | PostgreSQL ordered event range |
| `db.snapshot_load` | 100 ms | 300 ms | 750 ms | Latest graph snapshot lookup |
| `db.incident_list` | 100 ms | 300 ms | 750 ms | Ordered incident list query |
| `graph.2d.target_layout` | 8,000 ms | 8,000 ms | 8,000 ms | Playwright target fixture: 500 nodes / 900 edges; existing worker budget |
| `graph.2d.stress_layout` | 20,000 ms | 20,000 ms | 20,000 ms | Playwright full-view stress transition: 2,500 nodes / 5,000 edges; underlying worker remains at the existing 15,000 ms budget |
| `graph.3d.mount_to_visible` | 8,000 ms | 8,000 ms | 10,000 ms | Playwright Three.js first visible canvas frame |

The 3D metric is capability-aware. A missing WebGL capability records a skip reason and
the detected tier/fallback; it does not convert a measured 3D latency into a pass. When
3D is available, the real mount-to-visible time is retained in `browser-performance.json`.
The current expected baseline is approximately 4–8 seconds and is intentionally visible.

Reports are artifacts, not prose summaries. The release evidence manifest references the
performance report and browser sub-report under the same run directory. No cloud service or
remote model/provider is contacted by this stage.
