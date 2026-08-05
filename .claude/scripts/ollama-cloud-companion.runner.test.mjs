// Offline end-to-end tests for the Ollama cloud companion's subprocess plumbing:
// separate stdout/stderr pipes, UTF-8 log files, the background detach handshake,
// `check`, and `cancel`.
//
// Run with:  node --test .claude/scripts/ollama-cloud-companion.runner.test.mjs
//
// The real `ollama` binary is NEVER invoked. OLLAMA_BIN points at the Node
// executable and fake-ollama.cjs is preloaded via NODE_OPTIONS, so the companion
// spawns a stub that prints canned Ollama/Claude output. Jobs are written to a
// throwaway directory via AEGIS_OLLAMA_JOBS_DIR, not the real .claude/.ollama-jobs.

import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { setTimeout as sleep } from 'node:timers/promises';

import { promptForDispatch } from './ollama-cloud-companion.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const COMPANION = path.join(HERE, 'ollama-cloud-companion.mjs');
// NODE_OPTIONS honours quotes but not backslash escapes, so normalize to forward
// slashes (Node accepts them on Windows) and only quote when the path has spaces.
const FAKE = path.join(HERE, 'fake-ollama.cjs').replace(/\\/g, '/');
const FAKE_ARG = FAKE.includes(' ') ? `"${FAKE}"` : FAKE;

function makeJobsDir() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'aegis-ollama-jobs-'));
  test.after?.(() => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}

/** Run the companion with the fake ollama wired in. */
function run(jobsDir, args, { mode = 'success' } = {}) {
  const res = spawnSync(process.execPath, [COMPANION, ...args], {
    encoding: 'utf8',
    env: {
      ...process.env,
      AEGIS_OLLAMA_JOBS_DIR: jobsDir,
      OLLAMA_BIN: process.execPath,
      NODE_OPTIONS: `${process.env.NODE_OPTIONS ?? ''} --require ${FAKE_ARG}`.trim(),
      FAKE_OLLAMA_MODE: mode,
    },
    windowsHide: true,
  });
  return { stdout: res.stdout ?? '', stderr: res.stderr ?? '', code: res.status };
}

/**
 * The argv the stub actually received. Node rewrites argv[1] to an absolute path
 * before preloads run, so the "launch" subcommand comes back resolved — normalize
 * it back to its basename so the assertion reads as the real command line.
 */
function fakeArgv(stderr) {
  const argv = JSON.parse(stderr.match(/FAKE_ARGV (\[.*\])/)[1]);
  return [path.basename(argv[0]), ...argv.slice(1)];
}

const readMeta = (jobsDir, jobId) =>
  JSON.parse(fs.readFileSync(path.join(jobsDir, jobId, 'meta.json'), 'utf8'));

// -----------------------------------------------------------------------------

test('foreground task: prints the summary, exits 0, records meta and UTF-8 logs', () => {
  const jobs = makeJobsDir();
  const { stdout, stderr, code } = run(jobs, [
    'task',
    '--model',
    'minimax-m3:cloud',
    'Say hello and nothing else.',
  ]);

  assert.equal(code, 0, stdout + stderr);
  assert.match(stdout, /\[done\]/);
  assert.match(stdout, /Model {5}minimax-m3:cloud\[1m\] {2}\(context 1,000,000\)/);
  assert.match(stdout, /Effort {4}max/);
  assert.match(stdout, /--- result ---\nHello\.$/m);
  // the connectors warning must never leak into the summary
  assert.doesNotMatch(stdout, /connectors are disabled/);

  const [jobId] = fs.readdirSync(jobs);
  assert.match(jobId, /^job_\d{8}_\d{6}_[0-9a-f]{4}$/);

  const meta = readMeta(jobs, jobId);
  assert.equal(meta.status, 'done');
  assert.equal(meta.exitCode, 0);
  assert.equal(meta.effort, 'max');
  assert.equal(meta.contextWindow, '1m');
  assert.equal(meta.prompt, 'Say hello and nothing else.');
  assert.equal(meta.result.result, 'Hello.');
  assert.ok(meta.startedAt && meta.finishedAt);
  assert.ok(Number.isFinite(meta.pid) && Number.isFinite(meta.runnerPid));

  // Logs are written by Node's fs, i.e. UTF-8 — not PowerShell's UTF-16.
  const logDir = path.join(jobs, jobId);
  const raw = fs.readFileSync(path.join(logDir, 'stdout.log'));
  assert.notEqual(raw[1], 0x00, 'stdout.log must not be UTF-16');
  assert.match(raw.toString('utf8'), /connectors are disabled/);
  assert.match(fs.readFileSync(path.join(logDir, 'stderr.log'), 'utf8'), /FAKE_ARGV/);
});

test('the argv actually executed matches the verified ollama launch shape', () => {
  const jobs = makeJobsDir();
  const { stderr } = run(jobs, ['task', '--model', 'minimax-m3:cloud', 'hi']);
  const argv = fakeArgv(stderr);
  assert.deepEqual(argv, [
    'launch',
    'claude',
    '--model',
    'minimax-m3:cloud',
    '-y',
    '--',
    '-p',
    '--effort',
    'max',
    '--model',
    'minimax-m3:cloud[1m]',
    '--output-format',
    'json',
    promptForDispatch('hi'),
  ]);
});

test('an api_error result is surfaced cleanly, not as a crash', () => {
  const jobs = makeJobsDir();
  const { stdout, code } = run(jobs, ['task', '--model', 'deepseek-v4-flash:0731-cloud', 'hi'], {
    mode: 'apierror',
  });
  assert.equal(code, 1);
  assert.match(stdout, /\[error\]/);
  assert.match(stdout, /Error {5}api_error \(HTTP 403\)/);
  assert.match(stdout, /requires a subscription/);
  assert.doesNotMatch(stdout, /--- stdout \(raw\) ---/, 'parseable errors are not raw-dumped');
});

test('no parseable JSON is a hard failure that dumps raw stdout and stderr', () => {
  const jobs = makeJobsDir();
  const { stdout, code } = run(jobs, ['task', '--model', 'nope:cloud', 'hi'], { mode: 'nojson' });
  assert.equal(code, 1);
  assert.match(stdout, /No parseable JSON result on stdout/);
  assert.match(stdout, /--- stdout \(raw\) ---/);
  assert.match(stdout, /connectors are disabled/);
  assert.match(stdout, /--- stderr \(raw\) ---/);
  assert.match(stdout, /model 'nope:cloud' not found/);
});

test('--no-1m reaches the inner --model flag', () => {
  const jobs = makeJobsDir();
  const { stderr } = run(jobs, ['task', '--model', 'minimax-m3:cloud', '--no-1m', 'hi']);
  const argv = fakeArgv(stderr);
  assert.equal(argv.filter((_, i) => argv[i - 1] === '--model').at(-1), 'minimax-m3:cloud');
});

test('background task returns immediately with a job id, then completes detached', async () => {
  const jobs = makeJobsDir();
  const started = Date.now();
  const { stdout, code } = run(jobs, ['task', '--background', '--model', 'minimax-m3:cloud', 'hi']);
  const dispatchMs = Date.now() - started;

  assert.equal(code, 0);
  const jobId = stdout.split(/\r?\n/)[0].trim();
  assert.match(jobId, /^job_\d{8}_\d{6}_[0-9a-f]{4}$/);
  assert.match(stdout, /dispatched in background/);
  assert.ok(dispatchMs < 5000, `dispatch should not block (took ${dispatchMs}ms)`);

  // A poll landing in the startup window must not declare the job dead.
  const early = run(jobs, ['check', jobId]);
  assert.equal(early.code, 0, early.stdout + early.stderr);
  assert.doesNotMatch(early.stdout, /no longer alive/);

  // The detached runner finishes on its own, with no watcher of its own.
  let meta;
  for (let i = 0; i < 100; i += 1) {
    meta = readMeta(jobs, jobId);
    if (meta.status !== 'running' && meta.status !== 'pending') break;
    await sleep(200);
  }
  assert.equal(meta.status, 'done', `job never completed: ${JSON.stringify(meta)}`);
  assert.equal(meta.result.result, 'Hello.');
  assert.notEqual(meta.runnerPid, process.pid, 'runner must be a separate detached process');

  const check = run(jobs, ['check', jobId]);
  assert.equal(check.code, 0);
  assert.match(check.stdout, /\[done\]/);
  assert.match(check.stdout, /--- result ---\nHello\.$/m);
});

test('check with no job id lists jobs newest-first', () => {
  const jobs = makeJobsDir();
  assert.match(run(jobs, ['check']).stdout, /No jobs yet/);

  run(jobs, ['task', '--model', 'minimax-m3:cloud', 'first']);
  run(jobs, ['task', '--model', 'deepseek-v4-flash:0731-cloud', 'second'], { mode: 'apierror' });

  const { stdout, code } = run(jobs, ['check']);
  assert.equal(code, 0);
  const rows = stdout.trim().split(/\r?\n/);
  assert.equal(rows.length, 2);
  assert.match(rows[0], /^job_\S+\s+deepseek-v4-flash:0731-cloud\[1m\]\s+error\s/);
  assert.match(rows[1], /^job_\S+\s+minimax-m3:cloud\[1m\]\s+done\s/);
});

test('check reports an unknown job id without throwing', () => {
  const jobs = makeJobsDir();
  const { stderr, code } = run(jobs, ['check', 'job_20260101_000000_dead']);
  assert.equal(code, 1);
  assert.match(stderr, /Unknown job/);
});

test('cancel kills a running background job and pins its status', async () => {
  const jobs = makeJobsDir();
  const dispatch = run(jobs, ['task', '--background', '--model', 'minimax-m3:cloud', 'hi'], {
    mode: 'hang',
  });
  const jobId = dispatch.stdout.split(/\r?\n/)[0].trim();

  // wait for the detached runner to record the ollama child pid
  let meta;
  for (let i = 0; i < 50; i += 1) {
    meta = readMeta(jobs, jobId);
    if (meta.pid) break;
    await sleep(100);
  }
  assert.ok(meta.pid, 'runner never recorded the ollama pid');
  assert.equal(run(jobs, ['check', jobId]).stdout.includes('[running]'), true);

  const cancelled = run(jobs, ['cancel', jobId]);
  assert.equal(cancelled.code, 0);
  assert.match(cancelled.stdout, /cancelled/);
  assert.equal(readMeta(jobs, jobId).status, 'cancelled');

  // the runner must not resurrect the job as done/error after the kill lands
  await sleep(1500);
  assert.equal(readMeta(jobs, jobId).status, 'cancelled');
  assert.match(run(jobs, ['check', jobId]).stdout, /\[cancelled\]/);

  const second = run(jobs, ['cancel', jobId]);
  assert.match(second.stdout, /already cancelled/);
});

test('--timeout-ms kills a run that never returns', () => {
  const jobs = makeJobsDir();
  const { stdout, code } = run(
    jobs,
    ['task', '--model', 'minimax-m3:cloud', '--timeout-ms', '1500', 'hi'],
    { mode: 'hang' },
  );
  assert.notEqual(code, 0);
  assert.match(stdout, /Timed out after 1500ms/);
});

test('bad usage exits 2 with the usage block and creates no job', () => {
  const jobs = makeJobsDir();
  const { stderr, code } = run(jobs, ['task', 'hello with no model']);
  assert.equal(code, 2);
  assert.match(stderr, /--model <tag> is required/);
  assert.match(stderr, /Usage:/);
  assert.equal(fs.readdirSync(jobs).length, 0);
});
