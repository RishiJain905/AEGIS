// TEST FIXTURE — never used at runtime.
//
// A stand-in for the `ollama` binary, so ollama-cloud-companion.runner.test.mjs can
// exercise real subprocess plumbing (pipes, log files, detach, cancel) without
// touching the billed Ollama cloud API.
//
// It is injected as `NODE_OPTIONS=--require <this file>` with OLLAMA_BIN pointed at
// the Node executable itself: the companion then spawns `node launch claude ...`,
// this preload sees argv[1] === "launch", emits a canned response, and exits before
// Node ever tries to resolve "launch" as a script.
//
// The same NODE_OPTIONS is inherited by the companion's own detached runner process,
// where argv[1] is the companion script instead — hence the argv[1] guard below,
// which makes this a no-op there. (Node resolves argv[1] to an absolute path before
// preloads run, so compare the basename, not the raw argument.)

if (require('node:path').basename(process.argv[1] || '') === 'launch') {
  const mode = process.env.FAKE_OLLAMA_MODE || 'success';
  const warning =
    "⚠ claude.ai connectors are disabled because ANTHROPIC_API_KEY or another auth source is set and takes precedence over your claude.ai login · Unset it to load your organization's connectors";

  // Echo the argv the companion built so tests can assert the exact command shape.
  process.stderr.write(`FAKE_ARGV ${JSON.stringify(process.argv.slice(1))}\n`);

  const responses = {
    success: {
      code: 0,
      json: {
        is_error: false,
        duration_api_ms: 3066,
        num_turns: 1,
        stop_reason: 'end_turn',
        total_cost_usd: 0.20243,
        usage: {
          input_tokens: 40201,
          output_tokens: 57,
          cache_read_input_tokens: 0,
          cache_creation_input_tokens: 0,
        },
        modelUsage: {
          'minimax-m3:cloud[1m]': {
            contextWindow: 1000000,
            canonicalModel: 'minimax-m3:cloud[1m]',
            provider: 'firstParty',
          },
        },
        terminal_reason: 'completed',
        subtype: 'success',
        api_error_status: null,
        result: 'Hello.',
        type: 'result',
        duration_ms: 3501,
      },
    },
    apierror: {
      code: 1,
      json: {
        is_error: true,
        num_turns: 1,
        total_cost_usd: 0,
        usage: { input_tokens: 0, output_tokens: 0 },
        terminal_reason: 'api_error',
        api_error_status: 403,
        subtype: 'error',
        result:
          'Failed to authenticate. API Error: 403 this model requires a subscription, upgrade for access: https://ollama.com/upgrade (ref: test)',
        type: 'result',
        duration_ms: 812,
      },
    },
  };

  if (mode === 'nojson') {
    process.stdout.write(`${warning}\n`);
    process.stderr.write("Error: model 'nope:cloud' not found, try pulling it first\n");
    process.exit(1);
  }

  if (mode === 'hang') {
    process.stdout.write(`${warning}\n`);
    // Block synchronously (no CPU burn, still killable by taskkill /F). An async
    // timer would let Node fall through to resolving "launch" as a real module.
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 120_000);
    process.exit(0);
  } else {
    const { code, json } = responses[mode] || responses.success;
    process.stdout.write(`${warning}\n${JSON.stringify(json)}\n`);
    process.exit(code);
  }
}
