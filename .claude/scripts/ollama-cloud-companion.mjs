#!/usr/bin/env node
// AEGIS — Ollama cloud delegation companion.
//
// Delegates a single stateless turn to an Ollama-cloud-hosted model by way of
// `ollama launch claude`, which starts a local Anthropic-API-compatible proxy
// (process-scoped env only, no global config is touched) and then execs the
// real `claude` CLI inside that env.
//
// Command shape built here (the `--model` flag appears TWICE on purpose):
//
//   ollama launch claude --model <tag> -y -- \
//     -p --effort <effort> --model "<tag>[1m]" --output-format json "<prompt>"
//
//   * the OUTER `--model` picks which model the local proxy backs.
//   * the INNER `--model` is what the `claude` CLI resolves; the `[1m]` suffix
//     is what selects the 1,000,000-token context window (default is 200,000).
//
// Defaults deliberately mirror the manual workflow this replaces: `--effort max`
// and the `[1m]` context window are ON unless a caller explicitly opts out with
// `--effort <other>` / `--no-1m`.
//
// This proxy is text-only: any image/vision attempt triggers an API 400 that ends
// the run irrecoverably (a fresh dispatch is the only way forward). IMAGE_CAVEAT
// is therefore always appended to the dispatched prompt — see promptForDispatch.
//
// Dependency-free: Node built-ins only. All job logs are written with Node's own
// fs calls (UTF-8 by construction) rather than shell redirection, which avoids
// the PowerShell `*>` UTF-16 logging footgun documented in CLAUDE.md.
//
// Manual smoke test (costs real Ollama cloud usage — never run from CI/tests):
//   node .claude/scripts/ollama-cloud-companion.mjs task --model minimax-m3:cloud "Say hello and nothing else."

import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT_PATH = fileURLToPath(import.meta.url);
const SCRIPT_DIR = path.dirname(SCRIPT_PATH);
export const REPO_ROOT = path.resolve(SCRIPT_DIR, '..', '..');
// .claude/scripts/<this> -> .claude/.ollama-jobs. AEGIS_OLLAMA_JOBS_DIR exists so
// the offline tests can drive real subprocesses into a throwaway directory; it is
// inherited by the detached runner, so both halves of a background job agree.
export const JOBS_DIR = process.env.AEGIS_OLLAMA_JOBS_DIR
  ? path.resolve(process.env.AEGIS_OLLAMA_JOBS_DIR)
  : path.resolve(SCRIPT_DIR, '..', '.ollama-jobs');

export const VALID_EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max'];
export const DEFAULT_EFFORT = 'max';
// A hung background job with no timeout runs forever until someone notices via
// `check` — CLAUDE.md's own anti-stall guidance says every watched job needs a
// stall/kill bound, not just change detection. 10 minutes; pass --timeout-ms 0
// to disable for a task that's known to run long.
export const DEFAULT_TIMEOUT_MS = 600_000;
const OLLAMA_BIN = process.env.OLLAMA_BIN || 'ollama';

// Appended to every dispatched prompt (never stored as the job's displayed
// `prompt` — that field stays the caller's raw text). This proxy has no image
// capability at all; an image attempt returns an API 400 and the run is dead
// with no recovery, so the model must be told up front, every time.
export const IMAGE_CAVEAT =
  'Note: you are running text-only in this session with no image or vision ' +
  'capability whatsoever. Do not attempt to view, generate, edit, or otherwise ' +
  'act on any image content. Doing so will trigger an API 400 error that ends ' +
  'this session with no recovery — only a fresh dispatch can continue.';

const USAGE = `Usage:
  ollama-cloud-companion.mjs task --model <tag> [options] <prompt...>
  ollama-cloud-companion.mjs check [jobId]
  ollama-cloud-companion.mjs cancel <jobId>

task options:
  --model <tag>        Required. Ollama cloud model tag, e.g. minimax-m3:cloud
  --effort <level>     ${VALID_EFFORTS.join(' | ')}   (default: ${DEFAULT_EFFORT})
  --1m / --no-1m       Request the 1,000,000-token context window (default: --1m)
  --wait               Run in the foreground and print the result (default)
  --background         Detach; print the job id immediately, poll with \`check\`
  --raw                Also print the raw JSON result line
  --timeout-ms <n>     Kill the run after n ms (default: ${DEFAULT_TIMEOUT_MS} = 10 min; 0 disables)
`;

// ---------------------------------------------------------------------------
// pure helpers (unit-tested; no I/O, no network)
// ---------------------------------------------------------------------------

/** Strip a trailing `[1m]` context-window suffix from a model tag. */
export function baseModelTag(tag) {
  return String(tag).replace(/\[1m\]$/, '');
}

/**
 * Parse `task` argv. Returns the normalized options, applying the two defaults
 * the workflow depends on: effort=max and the 1m context window ON.
 * Throws Error with a human-readable message on bad input.
 */
export function parseTaskArgs(argv) {
  const opts = {
    model: null,
    effort: DEFAULT_EFFORT,
    oneMillion: true,
    background: false,
    raw: false,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  };
  const positional = [];

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    switch (arg) {
      case '--model':
      case '--effort':
      case '--timeout-ms': {
        const value = argv[i + 1];
        if (value === undefined || value.startsWith('--')) {
          throw new Error(`${arg} requires a value`);
        }
        i += 1;
        if (arg === '--model') opts.model = value;
        else if (arg === '--effort') opts.effort = value;
        else opts.timeoutMs = Number(value);
        break;
      }
      case '--1m':
        opts.oneMillion = true;
        break;
      case '--no-1m':
        opts.oneMillion = false;
        break;
      case '--background':
        opts.background = true;
        break;
      case '--wait':
        opts.background = false;
        break;
      case '--raw':
        opts.raw = true;
        break;
      case '--':
        positional.push(...argv.slice(i + 1));
        i = argv.length;
        break;
      default:
        if (arg.startsWith('--')) throw new Error(`Unknown flag: ${arg}`);
        positional.push(arg);
    }
  }

  if (!opts.model) {
    throw new Error('--model <tag> is required (e.g. --model minimax-m3:cloud)');
  }
  opts.model = baseModelTag(opts.model);
  if (!VALID_EFFORTS.includes(opts.effort)) {
    throw new Error(`--effort must be one of: ${VALID_EFFORTS.join(', ')} (got "${opts.effort}")`);
  }
  if (!Number.isFinite(opts.timeoutMs) || opts.timeoutMs < 0) {
    throw new Error('--timeout-ms must be a non-negative number');
  }

  opts.prompt = positional.join(' ').trim();
  if (!opts.prompt) throw new Error('A prompt is required as the final argument');
  return opts;
}

/** Model string handed to the inner `claude --model` flag. */
export function innerModelTag(opts) {
  return opts.oneMillion ? `${opts.model}[1m]` : opts.model;
}

/**
 * The text actually sent to the model: the caller's raw prompt plus the fixed
 * no-image-capability caveat. `opts.prompt` itself is never mutated — job
 * metadata and `check` output display the caller's raw text unchanged.
 */
export function promptForDispatch(prompt) {
  return `${prompt}\n\n${IMAGE_CAVEAT}`;
}

/** Full argv for the `ollama` binary. */
export function buildOllamaArgs(opts) {
  return [
    'launch',
    'claude',
    '--model',
    opts.model,
    '-y',
    '--',
    '-p',
    '--effort',
    opts.effort,
    '--model',
    innerModelTag(opts),
    '--output-format',
    'json',
    promptForDispatch(opts.prompt),
  ];
}

/**
 * Classify a finished result's failure so the wrapper can report it instead of
 * silently retrying the same (rate-limited / unauthorized / unpaid) model.
 * Returns null for a non-error result. Mirrors the Codex fallback pattern in
 * CLAUDE.md: detection is the wrapper's job, and it never self-retries.
 */
export function classifyFailure(result) {
  if (!result?.is_error) return null;
  const status = result.api_error_status;
  const text = String(result.result ?? '');
  if (status === 429 || /rate.?limit/i.test(text)) return 'rate_limit';
  if (status === 403 || /subscription|upgrade|quota|credits?/i.test(text)) return 'billing';
  if (status === 401 || /authenticat/i.test(text)) return 'auth';
  return 'error';
}

/**
 * `ollama launch` prints a connectors warning line before the JSON payload, and
 * a hard failure may print no JSON at all. Take the LAST line that starts with
 * `{` and parses; null means "no parseable result" (a hard failure).
 */
export function extractResultJson(stdout) {
  const lines = String(stdout ?? '').split(/\r?\n/);
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const line = lines[i].trim();
    if (!line.startsWith('{')) continue;
    try {
      const parsed = JSON.parse(line);
      if (parsed && typeof parsed === 'object') return parsed;
    } catch {
      // keep scanning older lines
    }
  }
  return null;
}

/** job_<YYYYMMDD_HHMMSS>_<4 hex chars>, local time. */
export function newJobId(now = new Date(), rand = () => randomBytes(2).toString('hex')) {
  const p = (n, w = 2) => String(n).padStart(w, '0');
  const stamp =
    `${now.getFullYear()}${p(now.getMonth() + 1)}${p(now.getDate())}` +
    `_${p(now.getHours())}${p(now.getMinutes())}${p(now.getSeconds())}`;
  return `job_${stamp}_${rand()}`;
}

export function formatDuration(ms) {
  if (!Number.isFinite(ms) || ms < 0) return '-';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const rem = Math.round(s % 60);
  if (m < 60) return `${m}m${p2(rem)}s`;
  return `${Math.floor(m / 60)}h${p2(m % 60)}m`;
}
const p2 = (n) => String(n).padStart(2, '0');

const num = (n) => (Number.isFinite(n) ? n.toLocaleString('en-US') : '-');

/** Render a finished (or failed) job's meta as the human-readable summary. */
export function formatJobSummary(meta) {
  const result = meta.result;
  const lines = [];
  lines.push(`Job       ${meta.jobId}  [${meta.status}]`);

  const usage = result?.modelUsage ? Object.entries(result.modelUsage)[0] : null;
  const shownModel = usage ? usage[0] : innerModelTag(meta);
  const ctx = usage?.[1]?.contextWindow;
  lines.push(`Model     ${shownModel}${ctx ? `  (context ${num(ctx)})` : ''}`);
  lines.push(`Effort    ${meta.effort}`);

  const wall = meta.finishedAt
    ? new Date(meta.finishedAt) - new Date(meta.startedAt)
    : Date.now() - new Date(meta.startedAt);
  const api = result?.duration_api_ms;
  lines.push(`Duration  ${formatDuration(wall)}${api ? `  (api ${formatDuration(api)})` : ''}`);

  if (result?.usage) {
    const u = result.usage;
    lines.push(
      `Tokens    in ${num(u.input_tokens)} / out ${num(u.output_tokens)}` +
        `  (cache read ${num(u.cache_read_input_tokens)}, create ${num(u.cache_creation_input_tokens)})`,
    );
  }
  if (Number.isFinite(result?.total_cost_usd)) {
    lines.push(`Cost      $${result.total_cost_usd.toFixed(5)}`);
  }
  if (result?.num_turns !== undefined || result?.stop_reason) {
    lines.push(`Turns     ${result.num_turns ?? '-'}  ·  stop_reason ${result.stop_reason ?? '-'}`);
  }
  if (result?.is_error) {
    const status = result.api_error_status ? ` (HTTP ${result.api_error_status})` : '';
    const cls = classifyFailure(result);
    lines.push(`Error     ${result.terminal_reason ?? 'error'}${status}${cls ? `  [${cls}]` : ''}`);
  }
  if (Number.isFinite(meta.exitCode)) lines.push(`Exit      ${meta.exitCode}`);

  lines.push('');
  lines.push('--- result ---');
  lines.push(result?.result ?? '(no result text)');
  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// job bookkeeping (I/O)
// ---------------------------------------------------------------------------

function jobDir(jobId) {
  return path.join(JOBS_DIR, jobId);
}

function metaPath(jobId) {
  return path.join(jobDir(jobId), 'meta.json');
}

function readMeta(jobId) {
  const file = metaPath(jobId);
  if (!fs.existsSync(file)) return null;
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

function writeMeta(meta) {
  const dir = jobDir(meta.jobId);
  fs.mkdirSync(dir, { recursive: true });
  const tmp = path.join(dir, `meta.json.${process.pid}.tmp`);
  fs.writeFileSync(tmp, `${JSON.stringify(meta, null, 2)}\n`, 'utf8');
  fs.renameSync(tmp, metaPath(meta.jobId));
}

function patchMeta(jobId, patch) {
  const meta = readMeta(jobId);
  if (!meta) return null;
  const next = { ...meta, ...patch };
  writeMeta(next);
  return next;
}

function isAlive(pid) {
  if (!Number.isFinite(pid)) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    return err.code === 'EPERM';
  }
}

// ---------------------------------------------------------------------------
// running a job
// ---------------------------------------------------------------------------

/**
 * Spawn `ollama launch ...` for an existing job dir and wait for it to close.
 * stdout/stderr are kept on SEPARATE pipes so the connectors warning line can
 * never pollute JSON parsing, and both are streamed to their own log file.
 * Resolves with the updated meta.
 */
async function runJob(jobId, { echoStderr = false } = {}) {
  const meta = readMeta(jobId);
  if (!meta) throw new Error(`Unknown job: ${jobId}`);

  const dir = jobDir(jobId);
  const outLog = fs.createWriteStream(path.join(dir, 'stdout.log'), { encoding: 'utf8' });
  const errLog = fs.createWriteStream(path.join(dir, 'stderr.log'), { encoding: 'utf8' });
  let stdout = '';
  let stderr = '';

  const child = spawn(OLLAMA_BIN, meta.ollamaArgs, {
    cwd: REPO_ROOT,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });

  // The runner is the only writer of meta.json once a job is created — the
  // dispatching parent deliberately writes nothing after spawning it, so there is
  // no read-modify-write race that could clobber the pid `cancel` depends on.
  patchMeta(jobId, { pid: child.pid, runnerPid: process.pid, status: 'running' });

  child.stdout.setEncoding('utf8');
  child.stderr.setEncoding('utf8');
  child.stdout.on('data', (chunk) => {
    stdout += chunk;
    outLog.write(chunk);
  });
  child.stderr.on('data', (chunk) => {
    stderr += chunk;
    errLog.write(chunk);
    // stderr carries progress/warnings, so surface it live in the foreground.
    if (echoStderr) process.stderr.write(chunk);
  });

  let timedOut = false;
  const timer =
    meta.timeoutMs > 0
      ? setTimeout(() => {
          timedOut = true;
          killTree(child.pid);
        }, meta.timeoutMs)
      : null;

  const outcome = await new Promise((resolve) => {
    child.on('error', (err) => resolve({ exitCode: null, spawnError: err }));
    child.on('close', (code, signal) => resolve({ exitCode: code, signal }));
  });

  if (timer) clearTimeout(timer);
  await Promise.all([endStream(outLog), endStream(errLog)]);

  const result = extractResultJson(stdout);
  let status = 'done';
  let error = null;

  if (outcome.spawnError) {
    status = 'error';
    error =
      outcome.spawnError.code === 'ENOENT'
        ? `Could not run "${OLLAMA_BIN}" — is the Ollama CLI installed and on PATH? (set OLLAMA_BIN to override)`
        : `Failed to spawn "${OLLAMA_BIN}": ${outcome.spawnError.message}`;
  } else if (timedOut) {
    status = 'error';
    error = `Timed out after ${meta.timeoutMs}ms and was killed.`;
  } else if (!result) {
    status = 'error';
    error =
      'No parseable JSON result on stdout — the run failed before producing a result ' +
      '(ollama not signed in, network down, unknown model tag, or the CLI crashed). ' +
      'Raw streams follow.';
  } else if (result.is_error) {
    status = 'error';
  }

  // `cancel` marks the job before it kills us; never resurrect it as done/error.
  const current = readMeta(jobId);
  if (current?.status === 'cancelled') {
    status = 'cancelled';
    error = current.error ?? error;
  }

  return patchMeta(jobId, {
    status,
    result,
    error,
    exitCode: outcome.exitCode,
    finishedAt: new Date().toISOString(),
    stdoutBytes: Buffer.byteLength(stdout, 'utf8'),
    stderrBytes: Buffer.byteLength(stderr, 'utf8'),
    // only retained when we could not parse a result — that is the diagnostic
    rawStdout: result ? undefined : stdout,
    rawStderr: result ? undefined : stderr,
  });
}

function endStream(stream) {
  return new Promise((resolve) => stream.end(resolve));
}

function killTree(pid) {
  if (!Number.isFinite(pid)) return false;
  try {
    if (process.platform === 'win32') {
      spawn('taskkill', ['/PID', String(pid), '/T', '/F'], {
        stdio: 'ignore',
        windowsHide: true,
      }).unref();
    } else {
      process.kill(-pid, 'SIGKILL');
    }
    return true;
  } catch {
    try {
      process.kill(pid, 'SIGKILL');
      return true;
    } catch {
      return false;
    }
  }
}

function createJob(opts) {
  const jobId = newJobId();
  fs.mkdirSync(jobDir(jobId), { recursive: true });
  const meta = {
    jobId,
    model: opts.model,
    effort: opts.effort,
    oneMillion: opts.oneMillion,
    contextWindow: opts.oneMillion ? '1m' : 'default',
    prompt: opts.prompt,
    startedAt: new Date().toISOString(),
    finishedAt: null,
    status: 'pending',
    background: opts.background,
    timeoutMs: opts.timeoutMs,
    runnerPid: null,
    pid: null,
    bin: OLLAMA_BIN,
    ollamaArgs: buildOllamaArgs(opts),
    // full argv as executed, for debugging
    argv: [OLLAMA_BIN, ...buildOllamaArgs(opts)],
    exitCode: null,
    result: null,
    error: null,
  };
  writeMeta(meta);
  return meta;
}

function printFailure(meta) {
  const out = [formatHeaderForFailure(meta)];
  out.push('');
  out.push('--- stdout (raw) ---');
  out.push(meta.rawStdout?.trimEnd() || '(empty)');
  out.push('--- stderr (raw) ---');
  out.push(meta.rawStderr?.trimEnd() || '(empty)');
  process.stdout.write(`${out.join('\n')}\n`);
}

function formatHeaderForFailure(meta) {
  return [
    `Job       ${meta.jobId}  [${meta.status}]`,
    `Model     ${innerModelTag(meta)}`,
    `Effort    ${meta.effort}`,
    `Exit      ${meta.exitCode ?? '-'}`,
    `Error     ${meta.error ?? 'unknown failure'}`,
  ].join('\n');
}

/** True when the job produced no parseable JSON at all (hard failure). */
function isHardFailure(meta) {
  return meta.status === 'error' && !meta.result;
}

// ---------------------------------------------------------------------------
// subcommands
// ---------------------------------------------------------------------------

async function cmdTask(argv) {
  let opts;
  try {
    opts = parseTaskArgs(argv);
  } catch (err) {
    process.stderr.write(`${err.message}\n\n${USAGE}`);
    return 2;
  }

  const meta = createJob(opts);

  if (opts.background) {
    const child = spawn(process.execPath, [SCRIPT_PATH, '__run-detached', meta.jobId], {
      cwd: REPO_ROOT,
      detached: true,
      stdio: 'ignore',
      windowsHide: true,
    });
    child.unref();
    process.stdout.write(
      `${meta.jobId}\n` +
        `dispatched in background — model ${innerModelTag(opts)}, effort ${opts.effort}. ` +
        `Poll with: node .claude/scripts/ollama-cloud-companion.mjs check ${meta.jobId}\n`,
    );
    return 0;
  }

  const done = await runJob(meta.jobId, { echoStderr: true });

  if (isHardFailure(done)) {
    printFailure(done);
    return done.exitCode ?? 1;
  }
  process.stdout.write(`${formatJobSummary(done)}\n`);
  if (opts.raw && done.result) {
    process.stdout.write(`\n--- raw json ---\n${JSON.stringify(done.result)}\n`);
  }
  return done.exitCode ?? (done.status === 'error' ? 1 : 0);
}

async function cmdRunDetached(argv) {
  const jobId = argv[0];
  if (!jobId) return 2;
  try {
    await runJob(jobId, { echoStderr: false });
  } catch (err) {
    patchMeta(jobId, {
      status: 'error',
      error: String(err?.message ?? err),
      finishedAt: new Date().toISOString(),
    });
  }
  return 0;
}

function listJobs() {
  if (!fs.existsSync(JOBS_DIR)) return [];
  return fs
    .readdirSync(JOBS_DIR, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => readMeta(e.name))
    .filter(Boolean)
    .sort((a, b) => String(b.startedAt).localeCompare(String(a.startedAt)));
}

/** A detached runner needs a moment to boot and claim the job before it counts as dead. */
const STARTUP_GRACE_MS = 30_000;

/**
 * Reconcile a job whose runner process is gone: a crashed or externally killed
 * runner leaves `status: "running"` behind forever otherwise, and per CLAUDE.md a
 * phase that never changes must surface rather than look like progress.
 */
function reconcile(meta) {
  if (meta.status !== 'running' && meta.status !== 'pending') return meta;
  if (isAlive(meta.runnerPid)) return meta;
  // Dispatched but not yet claimed by its detached runner.
  if (!meta.runnerPid && Date.now() - new Date(meta.startedAt) < STARTUP_GRACE_MS) return meta;
  return (
    patchMeta(meta.jobId, {
      status: 'error',
      error:
        'Runner process is no longer alive but the job never recorded a result (crashed or was killed).',
      finishedAt: meta.finishedAt ?? new Date().toISOString(),
    }) ?? meta
  );
}

function cmdCheck(argv) {
  const jobId = argv.find((a) => !a.startsWith('--'));

  if (!jobId) {
    const jobs = listJobs();
    if (jobs.length === 0) {
      process.stdout.write(`No jobs yet. Dispatch one with \`task --model <tag> "<prompt>"\`.\n`);
      return 0;
    }
    const rows = jobs.map((raw) => {
      const meta = reconcile(raw);
      const end = meta.finishedAt ? new Date(meta.finishedAt) : new Date();
      const age = end - new Date(meta.startedAt);
      return [meta.jobId, innerModelTag(meta), meta.status, formatDuration(age)];
    });
    const widths = [0, 1, 2].map((i) => Math.max(...rows.map((r) => r[i].length)));
    for (const r of rows) {
      process.stdout.write(
        `${r[0].padEnd(widths[0])}  ${r[1].padEnd(widths[1])}  ${r[2].padEnd(widths[2])}  ${r[3]}\n`,
      );
    }
    return 0;
  }

  const raw = readMeta(jobId);
  if (!raw) {
    process.stderr.write(`Unknown job: ${jobId}\n`);
    return 1;
  }
  const meta = reconcile(raw);

  if (meta.status === 'running' || meta.status === 'pending') {
    const elapsed = Date.now() - new Date(meta.startedAt);
    process.stdout.write(
      `Job       ${meta.jobId}  [running]\n` +
        `Model     ${innerModelTag(meta)}\n` +
        `Effort    ${meta.effort}\n` +
        `Elapsed   ${formatDuration(elapsed)}\n` +
        `Pid       runner ${meta.runnerPid ?? '-'} / ollama ${meta.pid ?? '-'}\n`,
    );
    return 0;
  }

  if (isHardFailure(meta)) {
    printFailure(meta);
    return 1;
  }
  process.stdout.write(`${formatJobSummary(meta)}\n`);
  return meta.status === 'error' ? 1 : 0;
}

function cmdCancel(argv) {
  const jobId = argv[0];
  if (!jobId) {
    process.stderr.write(`cancel requires a jobId\n`);
    return 2;
  }
  const meta = readMeta(jobId);
  if (!meta) {
    process.stderr.write(`Unknown job: ${jobId}\n`);
    return 1;
  }
  if (meta.status !== 'running' && meta.status !== 'pending') {
    process.stdout.write(`${jobId} is already ${meta.status}; nothing to cancel.\n`);
    return 0;
  }
  // Mark first, then kill: taskkill is asynchronous, so a runner that happens to
  // finish in the gap must still observe the cancellation and not overwrite it.
  patchMeta(jobId, {
    status: 'cancelled',
    finishedAt: new Date().toISOString(),
    error: 'Cancelled by user.',
  });
  // /T takes the runner's descendants (ollama, and the claude CLI it exec'd) with it.
  const killed = [meta.runnerPid, meta.pid].filter(Boolean).map((pid) => killTree(pid));
  process.stdout.write(
    `${jobId} cancelled (killed ${killed.filter(Boolean).length} process tree(s)).\n`,
  );
  return 0;
}

// ---------------------------------------------------------------------------

async function main(argv) {
  const [sub, ...rest] = argv;
  switch (sub) {
    case 'task':
      return cmdTask(rest);
    case '__run-detached':
      return cmdRunDetached(rest);
    case 'check':
      return cmdCheck(rest);
    case 'cancel':
      return cmdCancel(rest);
    case '--help':
    case '-h':
    case undefined:
      process.stdout.write(USAGE);
      return sub === undefined ? 2 : 0;
    default:
      process.stderr.write(`Unknown subcommand: ${sub}\n\n${USAGE}`);
      return 2;
  }
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === SCRIPT_PATH;
if (invokedDirectly) {
  main(process.argv.slice(2))
    .then((code) => {
      process.exitCode = code ?? 0;
    })
    .catch((err) => {
      process.stderr.write(`${err?.stack ?? err}\n`);
      process.exitCode = 1;
    });
}
