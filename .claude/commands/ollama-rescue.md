---
description: Delegate a self-contained task to an Ollama-cloud-hosted model via the local `ollama launch claude` proxy
argument-hint: "[--background|--wait] [--model <tag>] [--effort <low|medium|high|xhigh|max>] [--1m|--no-1m] <task>"
allowed-tools: Bash(node:*), AskUserQuestion, Agent
---

Invoke the `ollama-rescue` subagent via the `Agent` tool (`subagent_type: "ollama-rescue"`), forwarding the raw user request as the prompt.
The subagent and this command share the name `ollama-rescue`. Reach the subagent only through `Agent` with `subagent_type: "ollama-rescue"`; never call `Skill(ollama-rescue)` from inside this command — that re-enters the command itself and loops. Run this command inline so the `Agent` tool stays in scope.
The final user-visible response must be the companion script's output verbatim.

Raw user request:
$ARGUMENTS

Model selection:

- `--model <tag>` names the Ollama cloud model, e.g. `minimax-m3:cloud` or `deepseek-v4-flash:0731-cloud`.
- If `--model` is absent, do **not** guess a tag — the user works with more than one. Use `AskUserQuestion` exactly once to ask which model to send this to, offering the tags seen in recent jobs (`node .claude/scripts/ollama-cloud-companion.mjs check` lists them) plus an "other" option for a tag typed in. If `AskUserQuestion` is unavailable, stop and ask for a `--model` in one line.
- Pass the chosen tag through as `--model <tag>`.

Execution mode:

- `--background` runs the subagent in the background and forwards `--background`; the response is the job id, and the user polls it with `/ollama-check <jobId>`.
- `--wait`, or neither flag, runs in the foreground and blocks until the model answers.
- `--background` / `--wait` / `--model` / `--effort` / `--1m` / `--no-1m` are runtime controls. Preserve them for the forwarded `task` call; never treat them as part of the natural-language task text.

Defaults (do not override them unprompted):

- The companion always sends `--effort max` and requests the 1,000,000-token context window (`<tag>[1m]` on the inner `--model`). That mirrors the user's manual workflow.
- Only pass `--effort <level>` or `--no-1m` when the user explicitly asked for a different level or the standard 200k window.

Operating rules:

- The subagent is a thin forwarder. It makes one `Bash` call to `node .claude/scripts/ollama-cloud-companion.mjs task ...` and returns that stdout as-is.
- Return that output verbatim — no paraphrase, no summary, no added commentary.
- Do not ask the subagent to inspect files, monitor progress, poll status, cancel jobs, or do follow-up work.
- Each run is a stateless one-shot turn; there is no thread to resume. Give the model everything it needs in the task text.
- If the output reports that `ollama` could not be run, tell the user to check that the Ollama CLI is installed, on PATH, and signed in.
- If the result carries a `[rate_limit]`, `[billing]`, or `[auth]` tag (see CLAUDE.md's Ollama fallback-handling section), do not retry the same or a different Ollama model. Tell the user the Ollama dispatch failed and why, then complete their underlying task via normal Claude preset / Codex routing instead — this path is opt-in, not autonomous, so there's no state to preemptively skip on a later request.
- If the user supplied no task text, ask what the model should work on.
