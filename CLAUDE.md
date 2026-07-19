# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Picking the right models for workflows and subagents

Rankings, higher = better. Cost reflects what I actually pay (OpenAI has really generous limits), not list price. Intelligence is how hard a problem you can handle the model unsupervised. Taste covers UI/UX, code quality, API design, and copy.

### Claude models

| model | cost | intelligence | taste |
|-------|------|--------------|-------|
| sonnet-5 | 5 | 5 | 7 |
| opus-4.8 | 4 | 7 | 8 |
| fable-5 | 2 | 9 | 9 |

### Claude subagent presets (model + effort)

The Agent tool has no per-spawn effort parameter — effort is pinned in the agent definition. Five presets live in `.claude/agents/` (spawn via `subagent_type: "<preset>"`); Fable is spawned plainly with `model: 'fable'` and inherits the session's effort:

| preset | model | effort | use for |
|--------|-------|--------|---------|
| `sonnet-low` | sonnet-5 | low | Trivial mechanical side tasks with zero design decisions: file sweeps, renames, doc/config tweaks, simple test fixes. |
| `sonnet-xhigh` | sonnet-5 | xhigh | Default for **compact** well-specified work: single-file/single-feature implementation, test authoring, user-facing UI/copy at taste 7. Also the budget fallback when usage is tight. |
| `sonnet-max` | sonnet-5 | max | Niche only: debugging with a known repro, or deep-but-mechanical work confined to one file/domain. Not a rung on the escalation ladder — at max effort on multi-file volume it burns more tokens than opus-xhigh finishing in one pass. |
| `opus-xhigh` | opus-4.8 | xhigh | **Default implementer.** Multi-file features, cross-cutting integration, API design, plan/implementation reviews, subtle debugging. First choice once a task spans files/subsystems, regardless of how clear the spec is. |
| `opus-max` | opus-4.8 | max | Heaviest delegation: architectural refactors, root-cause hunts that survived an opus-xhigh attempt, high-risk changes to shared pipelines. Last stop before Fable does it personally. |
| *(fable, no preset)* | fable-5 | inherits session | Open-ended design and judgment calls the orchestrator would otherwise keep; rare — usually the orchestrator IS Fable. |

Routing by complexity — ask three questions: *does the task span more than one file/subsystem?*, *what breaks if it's slightly wrong?*, and *does the task's true complexity sit within this preset's ceiling at its pinned effort?*
- Route by ceiling, not ladder position: estimate the task's true complexity first and assign the preset whose ceiling comfortably covers it. If a task genuinely demands `opus-max` (architectural refactor, gnarly root-cause, high-risk shared-pipeline change) or Fable (open-ended design, novel judgment), start there on the first pass — never assign a first pass to a preset you expect to fail just because the ladder starts lower.
- Spec explicit, scope compact, failure caught by the gate → `sonnet-low`/`sonnet-xhigh`.
- Scope grows to multi-file — even with a crystal-clear spec → `opus-xhigh` directly. Don't ladder through sonnet-max; fewer smart tokens beat more cheap ones (max-effort Sonnet thinking plus extra gate iterations usually out-burns Opus finishing in one pass).
- Ambiguity, judgment, taste ≥ 8, or cross-subsystem blast radius → `opus-xhigh`; add high-risk on top → `opus-max`.
- Escalation is one-way and immediate: the same miss or failure twice on a preset → next tier (sonnet-xhigh → opus-xhigh → opus-max → Fable inline), never a retry at the same tier. sonnet-max sits off-ladder as a special-purpose tool, not an escalation step. Escalation corrects misjudged routing; it is not a substitute for honest first-pass ceiling matching.
- These presets do not replace Codex routing: bulk/mechanical clear-spec diffs still go to a GPT-5.6 Codex model first; the presets cover work needing Claude judgment/taste, reviews, and the Codex-down fallback.
- Presets fix only the floor (model, effort, verify-gate discipline); all task-specific steering — scope, approach, constraints, what a prior attempt got wrong, report format — goes in the spawn `prompt`, which layers on top of the preset's system prompt. Steer there; don't create new agent files for one-off specializations.

### Codex models

| model | cost | intelligence | taste | effort |
|-------|------|--------------|-------|--------|
| gpt-5.6-luna | 10 | 7 | 7 | max |
| gpt-5.6-terra | 8 | 8 | 7 | max |
| gpt-5.6-sol | 8 | 8 | 8 | high |
| gpt-5.6-sol | 6 | 9 | 8 | max |

How to apply:
- These are defaults, not limits. You have standing permission to override them: if a cheaper model's output doesn't meet the bar, rerun or redo the work with a smarter model without asking. Judge the output, not the price tag. Escalating costs less than shipping mediocre work.
- Cost is a tie-breaker only; when axes conflict for anything that ships, intelligence > taste > cost.
- Bulk/mechanical work (clear-spec implementation, data analysis, migrations): use a GPT-5.6 Codex model; the specific model and effort are defined in the delegation section.
- Anything user-facing (UI, copy, API design) needs taste ≥ 7.
- When the factor comes down to taste and design always utilize Claude models first with codex models only being used a fallback in that specific scenario. 
- Reviews of plans/implementations: fable-5 or opus-4.8, optionally a GPT-5.6 Codex model as an extra independent perspective.
- Never use Haiku.
- Mechanics: GPT-5.6 Codex models are accessed from Claude Code through the Codex plugin. For implementation, debugging, investigation, data analysis, or other delegated work, use `/codex:rescue --model <model> --effort <effort> <task>`. Add `--background` for longer-running work, then use `/codex:status` and `/codex:result` to monitor it and retrieve the result. For reviews, use `/codex:review` or `/codex:adversarial-review`.
- Claude models (sonnet-5, opus-4.8, fable-5) run via the Agent tool — prefer the effort presets above (`subagent_type: "sonnet-xhigh"` etc.) over a bare `model:` parameter, since a bare spawn cannot set effort.

Using GPT-5.6 inside workflows and subagents:
- The Agent/Workflow `model` parameter only accepts Claude models. To delegate work to a GPT-5.6 Codex model, use the Codex plugin's bundled `codex:codex-rescue` subagent rather than creating a custom Claude wrapper. If a wrapper is absolutely required, spawn a Claude wrapper with `model: 'sonnet', effort: 'low'` and instruct it to write a self-contained Codex prompt. Prefer the plugin whenever possible.
- For implementation or investigation, choose the model and effort up front from the task-fit guidance below, then invoke `/codex:rescue --model <model> --effort <effort> --background <self-contained task>`.
- Use `/codex:status` to check progress and `/codex:result` to retrieve the completed response.
- For an independent code review, run `/codex:review --background`.
- For a review focused on challenging design decisions, assumptions, or specific risk areas, run `/codex:adversarial-review --background <focus>`.
- Claude may also delegate naturally by being instructed to ask Codex to complete a task.

Understanding which Codex model + effort to use:
- Select the model before spawning based on the task's expected complexity and required capability ceiling. Do not start with Luna and move upward only after failure.
- **Spec clarity is not the discriminator.** Nearly every task here arrives as a detailed spec doc, so "is the spec clear?" separates nothing — a detailed spec tells you *what* to build, it does not make a hard problem easy. Route on the intrinsic difficulty of the work and on how a mistake would surface, not on how well it is written up. A clear spec is what makes Luna *possible*; it is not what makes Sol unnecessary.
- **Luna/max:** Luna at max effort is a genuinely capable tier, not a budget tier — it benchmarks above Sol/low and roughly level with Sol/medium, at a fraction of the cost. It is the right call for the large majority of delegated work: bulk and mechanical changes, migrations, data analysis, routine investigation, test authoring, and implementation where the spec fixes both the *what* and most of the *how*, so the job is mainly faithful translation into code — **including multi-file work**, provided a mistake fails *loudly* (a test or the verify gate catches it). Send the task here unless you can name a trigger below.
- **Sol/high — when a named trigger fires:** For work that stays hard *after* the spec is perfectly clear. Choose Sol/high when at least one holds, and state which one at dispatch: (a) **correctness rests on invariants a passing test won't prove** — concurrency, cache coherency and invalidation, ordering or streaming/tool-call interleaving, retry and idempotency, auth and security boundaries; (b) **the spec settles the *what* but leaves a real design decision open** — schema, API surface, algorithm choice — where the wrong pick becomes lock-in; (c) **it changes a shared pipeline where errors degrade quality silently instead of failing** — retrieval fusion and ranking, prompt assembly, embeddings, scheduler isolation; (d) debugging with no clear repro or working hypothesis; (e) a Luna/max attempt at the same task already missed the bar.
- Do **not** escalate to Sol/high merely because a task feels important, touches several files, is production code, or leaves you unsure — none of those are triggers. Multi-file is a *volume* signal, not a *difficulty* signal, and Luna/max handles volume cheaply. The question is never "is this task big?" but "would a subtly wrong answer here pass the gate and ship?" Guessing low costs one re-dispatch on the rare miss; habitually guessing high costs extra on every task.
- **Exceptional — Terra/max:** Reserve for genuinely hard, long-horizon, tool-heavy coding or analysis where sustained technical execution is the main constraint and design taste is not. Luna and Sol are generally more cost-efficient, so choose Terra/max only when the task specifically benefits from its higher coding-agent ceiling.
- **Exceptional — Sol/max:** Reserve for genuinely hard, high-stakes, or deeply ambiguous work requiring the highest broad reasoning and judgment ceiling, such as novel debugging, consequential architecture, or difficult cross-system changes. Do not use it when Sol/high can confidently cover the task.
- Luna/max is the normal choice; Sol/high is the justified exception. Terra/max and Sol/max are intentional choices for tasks assessed as exceptionally difficult before delegation, not fallback steps in an escalation ladder.

Fallback handling (Codex usage limits / zero credits):
- **Detection is the wrapper's job — every Codex dispatch must be verified, not assumed.** Immediately after dispatching, the wrapper checks the job result for the limit signatures: (a) an explicit "You've hit your usage limit… try again at HH:MM" error; (b) the instant-fail pattern — `task_complete` within seconds of submission with `last_agent_message: null`, usually alongside a `token_count`/`rate_limits` event showing `has_credits: false` or `balance: "0"` (visible in the newest `~/.codex/sessions/**/rollout-*.jsonl`). A dispatch that produced no repo changes and no agent message did NOT run — treat it as a limit failure, never as success.
- **The wrapper never performs the fallback itself.** On detecting a limit failure it must NOT spawn subagents, NOT retry Codex, and NOT wait for the reset. It reports straight back to the orchestrating (main) session with: the failure signature it matched, the quoted reset time if present, and the untouched task spec. Then it stops.
- **The orchestrator owns the reroute.** On receiving that report, the main session spawns the Claude subagent itself using the preset table above (multi-file/cross-cutting → `opus-xhigh`; compact well-specified → `sonnet-xhigh`; architectural/high-risk → `opus-max`), passing the same task spec. This keeps model routing, budget awareness, and gate discipline in one place.
- **While credits are known-exhausted, skip Codex entirely** for subsequent tasks and route directly to Claude presets until a later dispatch (or the quoted reset time passing) proves Codex is back.
- The orchestrator should still babysit every dispatch with a working-tree watcher: zero writes within ~8 minutes of a dispatch means inspect the newest Codex rollout file for the instant-fail signature rather than waiting longer.

When Using Plan mode:
- Inherited / current model the user is using will be the model that is used to create the plan for the task at hand. This will likely be Fable 5 or Opus 4.8
- Once Fable 5 or Opus 4.8 has thought of a plan, spawn a subagent who will use `model: 'sonnet 5'` and the thinking effort will be based on complexity of task. This sonnet 5 model will create a HTML file using the frontend design skill. This HTML file should outline the entire plan and be presented to me (user).
- Instead of the typical MD file that is shown as the plan outline before the user (me) clicks proceed to implement, this HTML file will replace it. Make sure the Artifact HTML created is opened for the user when you are ready to show the plan and HTML file. 
- The objective is to visualize the plan prior to implementation so that its easier to optimize the plan before any code is written. 
- All subagents launched in Plan Mode will use `'model: 'sonnet 5'`. Effort level can be your choice based on complexity of task given to the model. This includes `Explore` Agents. The only Exception is the `plan` Agent who can use the `Model: 'Opus 4.8'` as the plan-agent default when specs are detailed and exploration ran first; `Model: 'Fable 5'` for open-ended or high ambigutiy design.

Built-in agents:
-Built-in agent types (`Explore`, `general-purpose`) are always spawned with an explicit `model:` — default `model: "sonnet"` — and never on Fable 5. Their definitions otherwise resolve their own model (Explore was observed defaulting to Opus 4.8), and an inheriting built-in in a Fable session would burn Fable tokens on survey work. Built-ins are for cheap search/survey only; anything needing more intelligence routes through the presets above or stays inline with the orchestrator.

### Babysitting delegated work (anti-stall rules)

Two silent stalls cost ~11 hours on 2026-07-16 (a wrapper that never reported a
finished job; a delegate zombied on its own dead verify subprocess behind a
change-only monitor). These rules are mandatory for every delegated job —
Codex or Claude, background or detached:

- **Never trust the messenger.** A wrapper/agent promising to "report when
  done" is not a completion signal. Poll the underlying job state directly
  (runtime status, job log file, working-tree writes) and read results from
  durable artifacts, not from the delegate's mailbox message.
- **Every watcher needs a stall timeout, not just change detection.** Emit on
  phase change AND on X minutes with no change (X = 2× the longest healthy
  phase seen so far; ~15 min default for verify/test phases). A phase that
  never changes must page the orchestrator, because silence is
  indistinguishable from progress.
- **Dual completion signals.** Primary notification plus an independent
  watcher with a hard deadline. When a watcher expires, re-arm it; never
  interpret watcher expiry or quiet as success.
- **Detach long-running work from the harness task system.** Harness
  background tasks can be killed externally; anything expected to run >15 min
  (eval sweeps, benchmarks) launches as a detached OS process writing to a log
  file, with a monitor tailing that file for both success and failure
  signatures.
- **Stalled-but-complete → take over.** If a delegate is stuck but its
  working tree/artifacts look finished, kill it, run the verify gate yourself,
  and hand back from the artifacts. Don't wait for it, and don't re-dispatch
  work that already exists.
- **Time-box phases at dispatch.** State the expected duration in the
  dispatch note (implementation 20 - 30 min (not a minimum nor a hard limit), verify ≤10 min per pass). One
  phase exceeding its box with zero new writes → inspect the job log
  immediately; a dead child process under a live job is the default suspect.
- **Make the watched log actually matchable — the recurring "monitor never
  returns" bug (Windows).** A monitor that greps a detached run's log will
  hang forever if the completion marker never lands in the log in a form the
  grep can see. Two concrete causes hit repeatedly here: (1) PowerShell `*>`
  redirect writes the file as **UTF-16**, so a bash `grep`/Monitor byte-match
  for `PYEXIT=`/`VERIFY:` never matches — the run finished, the watcher didn't
  notice. (2) `2>&1 | Out-File` captures stdout+stderr but **not** PowerShell's
  `Write-Host` (host stream), so `scripts\verify.ps1`'s own final
  `VERIFY: PASS` line and its `=== [stage]` markers never reach the log.
  Rules: **do not rely on the tool's own final line as the sentinel.** Have the
  wrapper script write an explicit sentinel to the file with a known encoding
  and grep for *that* — e.g. a detached `.ps1` that runs the work then
  `"DONE exit=$LASTEXITCODE" | Out-File -FilePath $log -Encoding utf8 -Append`,
  with the Monitor keyed on `DONE exit=`. Prefer `-Encoding utf8` (or write
  from `bash`) over `*>`; if you must read a `*>` log, decode it
  (`Get-Content` in PowerShell, not bash byte-grep). And always give the
  Monitor a stall timeout so a mis-encoded/mis-keyed log surfaces in minutes,
  not never.

### Loops: which primitive to trigger

A loop = repeated work cycles until a stop condition. The deterministic stop condition for all code loops in this repo is the verify gate — `scripts\verify.ps1` / `scripts/verify.sh`, final line `VERIFY: PASS|FAIL` — governed by the project skill `verify-rag-change`. Use that skill before claiming any code change done, in or out of a loop.

Route by task size; never a bigger loop than the task needs:

- **Short** (one file / obvious fix, ~≤3 turns): plain turn-based work. No /goal, no subagents, no background jobs. Run the gate once before reporting done; read only the verdict + failures.
- **Medium** (multi-file feature/bugfix with a checkable done-state): best run as `/goal <task>. Done when scripts\verify.ps1 prints VERIFY: PASS. Stop after 4 tries.` Iterate on the scoped gate (`-TestPath tests\test_x.py`) while fixing; the full gate is the exit check. Bulk/mechanical diffs → gpt-5.6 via `/codex:rescue` (table above); close with `/codex:review --background` for a fresh-context review. If a medium task arrives as a plain prompt, still enforce the gate, and put the ready-to-paste /goal one-liner in the final summary so the next run can be hands-off.
- **Long** (multi-phase, hours, or waiting on external systems): plan mode first (rules above), then each phase runs as its own medium /goal loop with its own PASS exit — never one giant loop. Watching external state (CI, PR reviews) → `/loop` with the interval matched to how fast the target changes (~4m for active CI; ≥20m for idle watching — avoid ~5m, it's the worst cache breakpoint), or interval-free `/loop` so Claude self-paces. Recurring repo upkeep (ingestion/scheduler health) → `/schedule` routine, not a live session.
- **Every size**: deterministic steps go in scripts, not reasoning; the same failure surviving two fix attempts means stop patching — change approach or escalate the model; pilot one slice before any fan-out; audit burn with `/usage` and `/goal` (no args).

## What this is

AEGIS Command — an interactive cyber-defence simulation and defensive-agent evaluation platform. A deterministic simulation emits synthetic telemetry for a fictional org, detection/ML layers raise alerts and incidents, LLM agents investigate through an allowlisted tool registry, humans approve state changes, and everything renders as a replayable Sigma.js operational graph. First scenario: **Operation Silent Relay**.

**`docs/architecture.md` is the binding implementation contract.** Read it before making structural changes. If a request conflicts with it, stop and propose an ADR (in `docs/AEGIS-v1.0-Agent-Specs/adrs/`) instead of silently diverging. Phase specs live in `docs/AEGIS-v1.0-Agent-Specs/`; per-subsystem docs (database, websocket protocol, replay engine, policy, etc.) live in `docs/`.

## Toolchain and setup

Hybrid monorepo: pnpm 11.9.0 + Turbo for TypeScript (Node 22), uv for Python 3.12. **pnpm only — never npm/npx/yarn.** All Python commands go through `uv run`.

```bash
./scripts/bootstrap.sh          # copies .env.example → .env, pnpm install, uv sync, validates env
docker compose up -d postgres redis minio   # local infra for integration tests / migrations
uv run alembic upgrade head     # apply DB migrations
```

Note: `bootstrap.sh` and several package scripts are bash; on this Windows machine run them via the Bash tool / Git Bash, not PowerShell.

## Commands

TypeScript (from repo root):

```bash
pnpm lint            # ESLint + dependency-cruiser boundary checks
pnpm typecheck       # tsc strict, via turbo
pnpm test            # workspace vitest suites, via turbo
pnpm format:check    # prettier (use `pnpm format` to fix)
pnpm build           # production builds
pnpm --filter @aegis/web test              # single workspace package
pnpm --filter @aegis/web exec vitest run path/to/file.test.tsx   # single test file
pnpm test:e2e        # Playwright (apps/web)
pnpm --filter @aegis/web storybook         # component dev, port 6006
```

Python:

```bash
uv run ruff check .
pnpm typecheck:py                # mypy over all aegis_* packages (strict mode)
uv run pytest -q                 # all Python tests (unit + contract run without infra)
uv run pytest tests/unit/some_test.py -q                 # single file
uv run pytest tests/unit/some_test.py::test_name -q      # single test
uv run pytest tests/integration -q    # requires postgres + redis running
uv run lint-imports              # import-linter boundary contracts
```

Cross-cutting:

```bash
pnpm check-contracts             # Python↔TS contract compatibility gate
uv run python scripts/generate_contract_schemas.py   # regenerate JSON Schemas after contract edits
```

Dev servers: `pnpm --filter @aegis/web dev` (Next.js, port 3000); API entry point is `aegis-api` (`uv run aegis-api`). Workers: `uv run aegis-worker --mode outbox-relay`. Simulator: `uv run aegis-simulator run-persisted --scenario <path> --seed <n> --steps <n>`.

## Architecture

Modular monolith deployed as multiple processes (web, API, workers, simulator) — do not split into network microservices.

Layering (enforced in CI by dependency-cruiser for TS and import-linter for Python — violations fail the build):

- `packages/*` — shared domain/infra libraries. Must not import apps or services. Key ones: `contracts-python` + `contracts-ts` (the **only** place domain contracts live — Pydantic and Zod, kept compatible via `pnpm check-contracts`), `persistence`, `event-streaming`, `scenario-sdk`, `simulation-domain`, `graph-domain` (both TS and Python variants), `graph-risk`, `model-provider` (provider-neutral LLM adapter), `policy`, `observability`, `realtime-client`, `ui`.
- `services/*` — Python application services: `simulation`, `incidents`, `agents`, `ml`, `workers`, `replay`, `reports`, `scoring`. May depend on packages, never on apps.
- `apps/api` — FastAPI, thin route handlers under `/api/v1` delegating to services. `apps/web` — Next.js 15 / React 19 command centre (TanStack Query for server state, Zustand for ephemeral UI state only, Sigma.js + Graphology for the graph, ForceAtlas2 in a Web Worker, Three.js/R3F only for the derived cinematic view).
- `scenarios/*` — declarative scenario definitions using the scenario SDK only; no arbitrary scenario code, complex behavior uses allowlisted plugins.

Core data flow: command handlers write state changes + domain events + outbox rows in one PostgreSQL transaction → outbox relay worker publishes to Redis Streams → WebSocket gateway delivers sequence-numbered deltas → frontend reducer applies them, detecting gaps and refetching snapshots on reconnect. PostgreSQL is the sole source of truth; Redis and browser state are projections. Events are append-only with a unique monotonic `(run_id, sequence)`; replay reconstructs historical state from snapshots + events.

Agent runtime: six roles (WATCHTOWER, TRACE, ORACLE, BASTION, WARDEN, SCRIBE) share one runtime with schema-constrained outputs, persisted tool calls, and evidence-ID grounding. State-changing agent actions are **proposals** — policy validation (Class 0–3) plus human approval gate execution; execution tools are never exposed to the model. Harness scripts for exercising agents locally live in `scripts/run_*_harness.py`.

## Non-negotiable rules (from the architecture contract)

- Simulation is deterministic: same scenario version + seed + config ⇒ identical normalized event sequence. Golden replay tests hash the event stream; intentional changes require updating the golden artifact with an explanation. No random global state in simulation code.
- Never redefine event or API shapes outside the shared contracts packages; event payloads are schema-versioned and never silently changed.
- IDs are stable, namespaced strings (`asset:...`, `incident:inc_...`); never use display labels as identity.
- Business logic lives in services, not route handlers; never return raw ORM objects; never write to domain tables directly from routes.
- Vendor SDKs stay behind adapters (`model-provider` etc.); domain code must not import them.
- Core CI must pass without an external LLM — agent workflow tests use deterministic provider fakes.
- Reduced-motion support and accessibility are mandatory in the frontend (a11y tests use vitest-axe / Storybook a11y).
- No Neo4j, Kafka, Kubernetes, or feature store without an ADR. No offensive cyber functionality — all activity is synthetic and scenario-confined.

## Testing layout

`tests/` at the root holds cross-cutting Python suites: `unit/`, `contract/` (schema/boundary contracts), `integration/` (needs real PostgreSQL + Redis), `golden-replays/`, plus per-domain suites (`agents/`, `ml/`, `policy/`, `replay/`, `scoring/`, `security/`, `a11y/`, ...). TS unit tests live next to code in `apps/web` and `packages/*` (vitest); e2e is Playwright in `apps/web`. mypy is strict everywhere except `tests.*`.
