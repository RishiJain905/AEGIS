// Offline unit tests for the Ollama cloud companion.
//
// Run with:  node --test .claude/scripts/
//
// These cover ONLY pure logic — argument parsing/defaults, command construction,
// JSON extraction from mixed stdout, and job-id shape. The real `ollama launch`
// call hits a billed external API and is never exercised here; see the manual
// smoke test noted at the top of ollama-cloud-companion.mjs.

import assert from 'node:assert/strict';
import test from 'node:test';

import {
  DEFAULT_EFFORT,
  DEFAULT_TIMEOUT_MS,
  IMAGE_CAVEAT,
  VALID_EFFORTS,
  baseModelTag,
  buildOllamaArgs,
  classifyFailure,
  extractResultJson,
  formatDuration,
  formatJobSummary,
  innerModelTag,
  newJobId,
  parseTaskArgs,
  promptForDispatch,
} from './ollama-cloud-companion.mjs';

// --- fixtures: verbatim stdout shapes observed from real runs -----------------

const WARNING_LINE =
  "⚠ claude.ai connectors are disabled because ANTHROPIC_API_KEY or another auth source is set and takes precedence over your claude.ai login · Unset it to load your organization's connectors";

const SUCCESS_JSON =
  '{"is_error":false,"duration_api_ms":3066,"num_turns":1,"stop_reason":"end_turn","session_id":"96a8fb5c-9074-4133-b41f-be0687213770","total_cost_usd":0.20243,"usage":{"input_tokens":40201,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":57,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[]},"modelUsage":{"minimax-m3:cloud":{"inputTokens":40201,"outputTokens":57,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0.20243,"contextWindow":200000,"maxOutputTokens":32000,"canonicalModel":"minimax-m3:cloud","provider":"firstParty"}},"permission_denials":[],"terminal_reason":"completed","fast_mode_state":"off","fast_mode_disabled_reason":"sdk_opt_in_required","subtype":"success","api_error_status":null,"result":"Hello","ttft_ms":2904,"ttft_stream_ms":2371,"time_to_request_ms":27,"type":"result","duration_ms":3501,"uuid":"7fa5640b-0be7-4260-a448-22a2c7c3ab71"}';

const ERROR_JSON =
  '{"is_error":true,"num_turns":1,"total_cost_usd":0,"usage":{"input_tokens":0,"output_tokens":0},"terminal_reason":"api_error","api_error_status":403,"subtype":"error","result":"Failed to authenticate. API Error: 403 this model requires a subscription, upgrade for access: https://ollama.com/upgrade (ref: abc123)","type":"result","duration_ms":812}';

const SUCCESS_STDOUT = `${WARNING_LINE}\n${SUCCESS_JSON}\n`;
const ERROR_STDOUT = `${WARNING_LINE}\n${ERROR_JSON}\n`;

// --- argument parsing / defaults ---------------------------------------------

test('defaults: effort is max and the 1m context window is ON', () => {
  const opts = parseTaskArgs(['--model', 'minimax-m3:cloud', 'Say hello and nothing else.']);
  assert.equal(opts.effort, 'max');
  assert.equal(DEFAULT_EFFORT, 'max');
  assert.equal(opts.oneMillion, true);
  assert.equal(opts.background, false, 'foreground/--wait is the default');
  assert.equal(opts.raw, false);
  assert.equal(opts.timeoutMs, DEFAULT_TIMEOUT_MS, 'a hung background job must not run forever by default');
  assert.equal(opts.model, 'minimax-m3:cloud');
  assert.equal(opts.prompt, 'Say hello and nothing else.');
});

test('--no-1m opts out of the 1m context window', () => {
  const opts = parseTaskArgs(['--model', 'minimax-m3:cloud', '--no-1m', 'hi']);
  assert.equal(opts.oneMillion, false);
  assert.equal(innerModelTag(opts), 'minimax-m3:cloud');
});

test('--1m is accepted explicitly and is a no-op against the default', () => {
  const opts = parseTaskArgs(['--model', 'minimax-m3:cloud', '--1m', 'hi']);
  assert.equal(opts.oneMillion, true);
  assert.equal(innerModelTag(opts), 'minimax-m3:cloud[1m]');
});

test('last --1m/--no-1m flag wins', () => {
  assert.equal(parseTaskArgs(['--model', 'm', '--no-1m', '--1m', 'hi']).oneMillion, true);
  assert.equal(parseTaskArgs(['--model', 'm', '--1m', '--no-1m', 'hi']).oneMillion, false);
});

test('explicit --effort overrides the max default; every valid level is accepted', () => {
  for (const effort of VALID_EFFORTS) {
    assert.equal(parseTaskArgs(['--model', 'm', '--effort', effort, 'hi']).effort, effort);
  }
});

test('--background / --wait select execution mode, last flag wins', () => {
  assert.equal(parseTaskArgs(['--model', 'm', '--background', 'hi']).background, true);
  assert.equal(parseTaskArgs(['--model', 'm', '--wait', 'hi']).background, false);
  assert.equal(parseTaskArgs(['--model', 'm', '--background', '--wait', 'hi']).background, false);
});

test('a model tag already carrying [1m] is normalized, not doubled', () => {
  const opts = parseTaskArgs(['--model', 'minimax-m3:cloud[1m]', 'hi']);
  assert.equal(opts.model, 'minimax-m3:cloud');
  assert.equal(innerModelTag(opts), 'minimax-m3:cloud[1m]');
  assert.equal(baseModelTag('deepseek-v4-flash:0731-cloud'), 'deepseek-v4-flash:0731-cloud');
});

test('multi-word prompts survive as a single joined prompt', () => {
  const opts = parseTaskArgs(['--model', 'm', 'explain', 'the', 'outbox', 'relay']);
  assert.equal(opts.prompt, 'explain the outbox relay');
});

test('`--` sends everything after it to the prompt, flags included', () => {
  const opts = parseTaskArgs(['--model', 'm', '--', '--effort', 'is', 'literal', 'here']);
  assert.equal(opts.effort, 'max');
  assert.equal(opts.prompt, '--effort is literal here');
});

test('rejects missing model, bad effort, unknown flags, and empty prompts', () => {
  assert.throws(() => parseTaskArgs(['hi']), /--model <tag> is required/);
  assert.throws(
    () => parseTaskArgs(['--model', 'm', '--effort', 'ultra', 'hi']),
    /--effort must be one of/,
  );
  assert.throws(() => parseTaskArgs(['--model', 'm', '--turbo', 'hi']), /Unknown flag: --turbo/);
  assert.throws(() => parseTaskArgs(['--model', 'm']), /prompt is required/);
  assert.throws(() => parseTaskArgs(['--model']), /--model requires a value/);
  assert.throws(() => parseTaskArgs(['--model', 'm', '--timeout-ms', '-5', 'hi']), /non-negative/);
});

// --- command construction -----------------------------------------------------

test('builds the verified command shape with --model on both sides', () => {
  const opts = parseTaskArgs(['--model', 'minimax-m3:cloud', 'Say hello and nothing else.']);
  assert.deepEqual(buildOllamaArgs(opts), [
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
    promptForDispatch('Say hello and nothing else.'),
  ]);
});

test('the dispatched prompt always carries the no-image caveat, raw prompt does not', () => {
  const opts = parseTaskArgs(['--model', 'minimax-m3:cloud', 'Say hello and nothing else.']);
  assert.equal(opts.prompt, 'Say hello and nothing else.', 'stored/displayed prompt stays raw');
  const args = buildOllamaArgs(opts);
  assert.equal(args.at(-1), `Say hello and nothing else.\n\n${IMAGE_CAVEAT}`);
  assert.match(IMAGE_CAVEAT, /no image or vision capability/i);
  assert.match(IMAGE_CAVEAT, /API 400/);
});

test('the outer --model never carries [1m]; only the inner one does', () => {
  const args = buildOllamaArgs(parseTaskArgs(['--model', 'minimax-m3:cloud[1m]', 'hi']));
  const modelValues = args.filter((_, i) => args[i - 1] === '--model');
  assert.deepEqual(modelValues, ['minimax-m3:cloud', 'minimax-m3:cloud[1m]']);
});

test('--no-1m leaves both --model values bare', () => {
  const args = buildOllamaArgs(parseTaskArgs(['--model', 'minimax-m3:cloud', '--no-1m', 'hi']));
  const modelValues = args.filter((_, i) => args[i - 1] === '--model');
  assert.deepEqual(modelValues, ['minimax-m3:cloud', 'minimax-m3:cloud']);
});

test('the prompt stays a single argv element (never shell-split)', () => {
  const args = buildOllamaArgs(parseTaskArgs(['--model', 'm', '--', 'say "hi" & then stop']));
  assert.equal(args.at(-1), promptForDispatch('say "hi" & then stop'));
  assert.equal(args.length, 14, 'prompt (with caveat) is still exactly one argv element');
});

// --- JSON extraction from mixed stdout ---------------------------------------

test('extracts the result past the connectors warning line', () => {
  const parsed = extractResultJson(SUCCESS_STDOUT);
  assert.equal(parsed.is_error, false);
  assert.equal(parsed.result, 'Hello');
  assert.equal(parsed.total_cost_usd, 0.20243);
  assert.equal(parsed.modelUsage['minimax-m3:cloud'].contextWindow, 200000);
});

test('a 403 subscription failure is still a parseable application-level result', () => {
  const parsed = extractResultJson(ERROR_STDOUT);
  assert.equal(parsed.is_error, true);
  assert.equal(parsed.api_error_status, 403);
  assert.equal(parsed.terminal_reason, 'api_error');
  assert.match(parsed.result, /requires a subscription/);
});

// --- failure classification (rate limit / billing / auth fallback signal) ----

test('classifyFailure: null for a successful result', () => {
  assert.equal(classifyFailure(JSON.parse(SUCCESS_JSON)), null);
});

test('classifyFailure: 403 + subscription wording classifies as billing', () => {
  assert.equal(classifyFailure(JSON.parse(ERROR_JSON)), 'billing');
});

test('classifyFailure: HTTP 429 classifies as rate_limit even without matching wording', () => {
  const result = { is_error: true, api_error_status: 429, result: 'Too many requests.' };
  assert.equal(classifyFailure(result), 'rate_limit');
});

test('classifyFailure: "rate limit" wording classifies as rate_limit without a 429 status', () => {
  const result = { is_error: true, api_error_status: null, result: 'You have hit a rate limit, try again later.' };
  assert.equal(classifyFailure(result), 'rate_limit');
});

test('classifyFailure: HTTP 401 classifies as auth', () => {
  const result = { is_error: true, api_error_status: 401, result: 'Invalid credentials.' };
  assert.equal(classifyFailure(result), 'auth');
});

test('classifyFailure: unrecognized error shape falls back to generic "error"', () => {
  const result = { is_error: true, api_error_status: 500, result: 'Internal server error.' };
  assert.equal(classifyFailure(result), 'error');
});

test('takes the LAST parseable JSON line when several are present', () => {
  const stdout = `${WARNING_LINE}\n{"type":"noise","result":"first"}\n${SUCCESS_JSON}\n`;
  assert.equal(extractResultJson(stdout).result, 'Hello');
});

test('skips trailing garbage that merely starts with a brace', () => {
  const stdout = `${SUCCESS_STDOUT}{ this is not json\n`;
  assert.equal(extractResultJson(stdout).result, 'Hello');
});

test('tolerates CRLF line endings', () => {
  assert.equal(extractResultJson(`${WARNING_LINE}\r\n${SUCCESS_JSON}\r\n`).result, 'Hello');
});

test('returns null when there is no parseable JSON at all (hard failure)', () => {
  assert.equal(extractResultJson(''), null);
  assert.equal(extractResultJson(undefined), null);
  assert.equal(extractResultJson('ollama: command not found\n'), null);
  assert.equal(extractResultJson(`${WARNING_LINE}\nError: model not found\n`), null);
  assert.equal(extractResultJson('[1,2,3]\n'), null, 'a JSON array is not a result object');
  assert.equal(extractResultJson('"just a string"\n'), null);
});

// --- job id -------------------------------------------------------------------

test('job ids are job_<YYYYMMDD_HHMMSS>_<4 hex>', () => {
  assert.match(newJobId(), /^job_\d{8}_\d{6}_[0-9a-f]{4}$/);
});

test('job id encodes the given local timestamp with zero padding', () => {
  const when = new Date(2026, 7, 4, 9, 5, 3); // 2026-08-04 09:05:03 local
  assert.equal(
    newJobId(when, () => 'a3f1'),
    'job_20260804_090503_a3f1',
  );
});

test('job ids are distinct within the same second', () => {
  const when = new Date(2026, 7, 4, 9, 5, 3);
  const ids = new Set(Array.from({ length: 200 }, () => newJobId(when)));
  assert.ok(ids.size > 190, `expected near-unique ids, got ${ids.size}/200`);
});

// --- summary rendering --------------------------------------------------------

test('formats a successful job summary from the real result shape', () => {
  const meta = {
    jobId: 'job_20260804_090503_a3f1',
    model: 'minimax-m3:cloud',
    oneMillion: true,
    effort: 'max',
    status: 'done',
    exitCode: 0,
    startedAt: '2026-08-04T09:05:03.000Z',
    finishedAt: '2026-08-04T09:05:06.500Z',
    result: JSON.parse(SUCCESS_JSON),
  };
  const out = formatJobSummary(meta);
  assert.match(out, /job_20260804_090503_a3f1 {2}\[done\]/);
  assert.match(out, /Model {5}minimax-m3:cloud {2}\(context 200,000\)/);
  assert.match(out, /Effort {4}max/);
  assert.match(out, /Cost {6}\$0\.20243/);
  assert.match(out, /in 40,201 \/ out 57/);
  assert.match(out, /--- result ---\nHello$/);
});

test('surfaces api_error status in the summary for a billed-but-failed run', () => {
  const meta = {
    jobId: 'job_1',
    model: 'deepseek-v4-flash:0731-cloud',
    oneMillion: true,
    effort: 'max',
    status: 'error',
    exitCode: 1,
    startedAt: '2026-08-04T09:05:03.000Z',
    finishedAt: '2026-08-04T09:05:03.812Z',
    result: JSON.parse(ERROR_JSON),
  };
  const out = formatJobSummary(meta);
  assert.match(out, /\[error\]/);
  assert.match(out, /Error {5}api_error \(HTTP 403\)  \[billing\]/);
  assert.match(out, /requires a subscription/);
  // no modelUsage in this shape — falls back to the requested tag
  assert.match(out, /Model {5}deepseek-v4-flash:0731-cloud\[1m\]/);
});

test('formatDuration renders ms, seconds, and minutes', () => {
  assert.equal(formatDuration(812), '812ms');
  assert.equal(formatDuration(3501), '3.5s');
  assert.equal(formatDuration(95000), '1m35s');
  assert.equal(formatDuration(NaN), '-');
});
