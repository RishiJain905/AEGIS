# Review-phase leads (accumulated during phases 32-33 + visual work)

1. Something in the pytest suite rewrites `scenarios/_fixtures/valid-minimal/package.manifest.yaml` with platform-native (CRLF) line endings on Windows — observed twice after full test runs. Fixture regeneration should be byte-stable (write with newline="\n").
2. Inspector panel showed "Loading after-action report" spinner indefinitely on a RUNNING run (no report exists yet) — check whether that query has a proper empty state vs infinite pending spinner.
3. pytest warnings: UnicodeDecodeError 'charmap' codec (cp1252) during test runs — some file read without encoding="utf-8"; find and fix (silent Windows-only hazard).
4. vitest @aegis/web spams "Not implemented: HTMLCanvasElement.prototype.getContext" errors (jsdom + Sigma) — noisy, mask real failures; consider canvas mock in test setup.
5. Web container image: 23 fixable HIGH transitive Node findings (Trivy) recorded in scan-triage-policy — candidate for base-image/deps bump during fix phase.
6. THREE.Color rgba() misuse produced 1360+ console warnings and the 3D canvas rendered empty — being fixed by codex-visual job; review must confirm no other per-frame string-parsing hot paths remain.
7. Windows-local `pnpm build` (Next standalone) fails with symlink EPERM — pre-existing platform limitation; document in Phase 35 known limitations (CI/Linux unaffected).

# Environment notes (for final report)
- Installed standalone pnpm (PNPM_HOME=%LOCALAPPDATA%\pnpm) + corepack shims dir %LOCALAPPDATA%\corepack-bin; user PATH updated; Node 22.17.0 via `pnpm env use --global`. System Node 24 untouched at C:\Program Files\nodejs but PNPM_HOME\bin now precedes it on user PATH (node resolves 22.17.0 in NEW shells).
- verify gate: scripts/verify.ps1|.sh (final line VERIFY: PASS|FAIL; -Deployment mode added in Phase 33).
- Detached-verify logs: use PowerShell Get-Content (encoding); grep/iconv unreliable on `*>` output.

# Checkpoints
- c92b678 docker fixes; d9270ca baseline; 028f668 Phase 32; 743b98b Phase 33.
- Dev stack containers up (aegis-*); prod-like validation project name: aegis-phase33-verify (torn down).
8. 3D view mount->visible latency ~4-8s (capability detection + scene build); shows only fog meanwhile. Consider a loading shimmer/progress cue in the canvas. Not a defect (fixed the never-renders bug); polish item.
9. scripts/release_validation.py writes evidence JSON with platform newlines (CRLF on Windows) -> perpetual worktree-modified churn under eol=lf. Open with newline='\n' (same class as lead #1).

# From recon-dataflow (verify during review)
10. services/workers/agent_runtime_runner.py main() registers SIGTERM/SIGINT -> sys.exit(0) IMMEDIATELY — no drain of in-flight executor.execute() (outbox relay does graceful stop_event). Worker shutdown defect candidate.
11. Agent task claiming race candidate: _poll_once lists QUEUED tasks then TaskExecutor.execute() no-ops if status != QUEUED, but two worker processes could both read QUEUED before either marks RUNNING (separate UoWs; need row-lock/UPDATE-claim check). Verify single-worker assumption or locking.
12. ReplayService.assert_read_only() is a documented NO-OP (convention only) — replay isolation not mechanically enforced.
13. Outbox relay: per-claim publish in separate sessions (crash mid-batch leaves partial published + claimed rows until claim TTL) — verify claim_ttl reclaim works and no duplicate xadd on reclaim (Redis xadd not idempotent; WS dedup is in-memory per connection only; DB consumer receipts exist but unused by relay). Duplicate-delivery path on relay crash-restart needs review.
14. Recon coverage gaps to spot-check in review: apps/web/lib/realtime/run-reducer.ts body; services/agents/providers/generation.py; reports service body; simulation event_queue.py/world_state.py; incidents rules internals.

# From recon-hygiene (verify during review)
15. apps/api/src/aegis_api/auth/router.py:31 _OIDC_STATE in-memory dict: entries added on /login, popped only on successful /callback; created_at stored but never used for expiry -> unbounded growth via abandoned logins (memory + minor DoS). Needs TTL sweep/cap.
16. new_runtime_id() byte-identical duplicate in 4 packages (replay/reports/scoring/agents ids.py:10) — consolidate to shared location (contracts/persistence util) or accept + document.
17. Dead exports (candidates): packages/ui StatusIcon, RiskIcon, VisuallyHidden, Separator, raw cva variant exports, formatPlatformStatus; packages/graph-domain InMemoryGraphStore, GraphDomainError (external). Confirm + prune or wire.
18. NEXT_PUBLIC_AEGIS_CSRF_COOKIE_NAME declared in .env.example + compose but unread by web production code (cookie name hardcoded) — drift; align code to env or drop var.
19. services/replay has 12x "type: ignore[arg-type]" cluster — check whether typing is genuinely unsound around projectors/snapshot payloads.
20. ~25 noqa: BLE001 broad-excepts, several without justification comments — spot-check the unjustified ones for swallowed errors (esp. approvals/service.py, scoring/service.py, replay/service.py).
21. useEffect cleanup audited only for timer cases; remaining ~16 feature files unaudited for listener/subscription cleanup — cover WebGL/graph components in review.
22. apps/web/features/auth/sign-in-panel.tsx:31-39 — dev-identities fetch failure silently renders EMPTY identity list (catch -> setUsers([])): no error alert, no retry. User-observed 2026-07-18 during API restart window; sign-in appears broken. Fix: error state + retry button (and optionally auto-retry with backoff).
