---
description: Show Ollama cloud delegation jobs for this repository, or the full result of one job
argument-hint: "[jobId]"
disable-model-invocation: true
allowed-tools: Bash(node:*)
---

!`node .claude/scripts/ollama-cloud-companion.mjs check $ARGUMENTS`

This is a read-only status poll — do not route it through the `ollama-rescue` subagent.

If the user did not pass a job id:

- The output is one line per job (`jobId  model  status  age`), newest first. Render it as a compact Markdown table and nothing else.

If the user did pass a job id:

- Present the command output as-is. Do not summarize or condense it — the `--- result ---` section is the delegated model's answer and must survive verbatim.
- A `[running]` job is still in flight; suggest re-running `/ollama-check <jobId>` rather than waiting inside this turn.
- A hard failure prints raw stdout/stderr instead of a summary. Pass it through unchanged; that dump is the diagnostic.
- To stop a job that is still running: `node .claude/scripts/ollama-cloud-companion.mjs cancel <jobId>`.
