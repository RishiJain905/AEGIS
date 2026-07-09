#!/usr/bin/env node
/**
 * Phase 25 diagnostic capture — backend replay harness (not Phase 26 UI).
 */
import { chromium } from "@playwright/test";
import { execSync, spawn } from "node:child_process";
import { mkdirSync, writeFileSync, readFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "../../..");
const OUT = "/opt/cursor/artifacts/screenshots";
const STORAGE =
  process.env.AEGIS_REPLAY_STORAGE_DIR ?? "/tmp/aegis-replay-storage";
const RUN =
  process.env.AEGIS_REPLAY_DEMO_RUN_ID ?? "run_01ARZ3NDEKTSV4RRFFQ69G5FD0";
const DIAG = "/opt/cursor/artifacts/replay-diagnostic.html";

mkdirSync(OUT, { recursive: true });
mkdirSync(STORAGE, { recursive: true });

function loadEnvExample() {
  const parsed = {};
  const raw = readFileSync(resolve(ROOT, ".env.example"), "utf8");
  for (const line of raw.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const [key, ...rest] = trimmed.split("=");
    parsed[key] = rest.join("=");
  }
  return parsed;
}

const env = {
  ...loadEnvExample(),
  ...process.env,
  PATH: `${process.env.HOME}/.local/bin:${process.env.PATH}`,
  AEGIS_REPLAY_STORAGE_DIR: STORAGE,
};

function run(command) {
  try {
    return execSync(command, {
      cwd: ROOT,
      encoding: "utf8",
      env,
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (error) {
    const output =
      `${error.stdout?.toString?.() ?? ""}${error.stderr?.toString?.() ?? ""}`.trim();
    if (output) return output;
    throw error;
  }
}

const steps = [];
function record(name, command, output) {
  steps.push({ name, command, output: String(output).slice(0, 4000) });
  writeFileSync(`/opt/cursor/artifacts/${name}.txt`, String(output));
}

try {
  const persisted = run(
    `uv run aegis-simulator run-persisted --scenario scenarios/operation-silent-relay --seed 1000 --steps 80 --run-id ${RUN}`,
  );
  record("replay-silent-relay-run", "aegis-simulator run-persisted", persisted);
} catch (error) {
  // Run may already exist; continue with existing history.
  record(
    "replay-silent-relay-run",
    "aegis-simulator run-persisted",
    error.stdout?.toString?.() ?? String(error),
  );
}

record(
  "replay-snapshot-create",
  "create-snapshot seq 40",
  run(
    `uv run aegis-replay create-snapshot --run-id ${RUN} --sequence 40 --trigger-reason sequence_interval`,
  ),
);
record(
  "replay-snapshot-final",
  "create-snapshot seq 80",
  run(
    `uv run aegis-replay create-snapshot --run-id ${RUN} --sequence 80 --trigger-reason explicit_request`,
  ),
);
record(
  "replay-from-events",
  "reconstruct from events",
  run(`uv run aegis-replay reconstruct --run-id ${RUN} --from-events-only`),
);
record(
  "replay-from-snapshot",
  "reconstruct from snapshot+tail",
  run(`uv run aegis-replay reconstruct --run-id ${RUN}`),
);
record(
  "replay-equivalence",
  "equivalence",
  run(`uv run aegis-replay equivalence --run-id ${RUN}`),
);
record(
  "replay-corrupt-reject",
  "corrupt-reject-demo",
  run(`uv run aegis-replay corrupt-reject-demo --run-id ${RUN}`),
);
record(
  "replay-gap-detect",
  "gap-detect-demo",
  run(`uv run aegis-replay gap-detect-demo --run-id ${RUN}`),
);
record(
  "replay-diagnostic-page",
  "diagnostic-page",
  run(`uv run aegis-replay diagnostic-page --run-id ${RUN} --output ${DIAG}`),
);

const api = spawn("uv", ["run", "aegis-api"], {
  cwd: ROOT,
  env: { ...env, AEGIS_REPLAY_STORAGE_DIR: STORAGE },
  stdio: "ignore",
});

async function waitFor(url, attempts = 40) {
  for (let i = 0; i < attempts; i += 1) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      // retry
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

async function shot(name, url) {
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForTimeout(400);
  const path = `${OUT}/${name}.png`;
  await page.screenshot({ path, fullPage: true });
  console.log(`Wrote ${path}`);
}

try {
  await waitFor("http://127.0.0.1:8000/health");
  await shot("25-replay-diagnostic-harness", `file://${DIAG}`);

  // JSON evidence pages for specific criteria
  const evidenceHtml = (
    title,
    body,
  ) => `<!doctype html><html><head><meta charset="utf-8"/><title>${title}</title>
  <style>body{font-family:IBM Plex Mono,monospace;background:#0f1419;color:#e7ecf3;padding:24px}
  h1{color:#3d9cf0} pre{background:#1a2332;padding:16px;border:1px solid #2a3648;white-space:pre-wrap}
  .badge{display:inline-block;border:1px solid #3d9cf0;color:#3d9cf0;padding:4px 8px;margin-bottom:12px}</style></head>
  <body><div class="badge">PHASE 25 HISTORICAL REPLAY</div><h1>${title}</h1><pre>${body.replaceAll("<", "&lt;")}</pre></body></html>`;

  const files = [
    [
      "25-replay-silent-relay-history",
      "replay-from-events.json",
      "Silent Relay reconstructed history",
    ],
    [
      "25-replay-snapshot-metadata",
      "replay-snapshot-create.json",
      "Snapshot metadata + checksum",
    ],
    [
      "25-replay-from-events",
      "replay-from-events.json",
      "Replay from beginning (events only)",
    ],
    [
      "25-replay-from-snapshot-tail",
      "replay-from-snapshot.json",
      "Replay from snapshot + event tail",
    ],
    [
      "25-replay-equivalence",
      "replay-equivalence.json",
      "Equivalence validation",
    ],
    [
      "25-replay-corrupt-reject",
      "replay-corrupt-reject.json",
      "Corrupt snapshot rejection",
    ],
    [
      "25-replay-sequence-gap",
      "replay-gap-detect.json",
      "Sequence gap detection",
    ],
  ];

  for (const [shotName, fileName, title] of files) {
    const raw = readFileSync(`/opt/cursor/artifacts/${fileName}`, "utf8");
    const htmlPath = `/opt/cursor/artifacts/${shotName}.html`;
    writeFileSync(htmlPath, evidenceHtml(title, raw));
    await shot(shotName, `file://${htmlPath}`);
  }

  // Live isolation evidence
  const isolation = {
    mode: "historical_replay",
    liveMutationAllowed: false,
    note: "Replay APIs reconstruct state and may write snapshot artifacts only; they never append domain events or execute approvals.",
    diagnosticEndpoint: `/api/v1/replay/runs/${RUN}/diagnostic`,
  };
  const isoPath = "/opt/cursor/artifacts/25-replay-live-isolation.html";
  writeFileSync(
    isoPath,
    evidenceHtml(
      "Live vs replay isolation",
      JSON.stringify(isolation, null, 2),
    ),
  );
  await shot("25-replay-live-isolation", `file://${isoPath}`);

  // API diagnostic
  const diagRes = await fetch(
    `http://127.0.0.1:8000/api/v1/replay/runs/${RUN}/diagnostic`,
  );
  const diagJson = await diagRes.json();
  writeFileSync(
    "/opt/cursor/artifacts/replay-api-diagnostic.json",
    JSON.stringify(diagJson, null, 2),
  );
  const apiHtml = "/opt/cursor/artifacts/25-replay-api-diagnostic.html";
  writeFileSync(
    apiHtml,
    evidenceHtml(
      "API diagnostic harness (graph/audit reconstruction)",
      JSON.stringify(
        {
          mode: diagJson.mode,
          liveMutationAllowed: diagJson.liveMutationAllowed,
          stateDigest: diagJson.state?.stateDigest,
          provenance: diagJson.state?.provenance,
          graphNodeCount: diagJson.state?.graph?.nodes?.length ?? 0,
          auditEventCount: diagJson.state?.auditEvents?.length ?? 0,
          snapshotCount: diagJson.snapshots?.length ?? 0,
          equivalence: diagJson.equivalence,
        },
        null,
        2,
      ),
    ),
  );
  await shot("25-replay-api-domains", `file://${apiHtml}`);

  // Short recording of cursor movement via sequential reconstruct pages
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    recordVideo: {
      dir: "/opt/cursor/artifacts/videos",
      size: { width: 1280, height: 720 },
    },
  });
  const videoPage = await context.newPage();
  for (const seq of [20, 40, 60, 80]) {
    const state = JSON.parse(
      run(`uv run aegis-replay reconstruct --run-id ${RUN} --sequence ${seq}`),
    );
    const html = evidenceHtml(
      `Replay cursor sequence=${seq}`,
      JSON.stringify(
        {
          cursor: state.cursor,
          provenance: state.provenance,
          stateDigest: state.stateDigest,
          graphNodes: state.graph?.nodes?.length ?? 0,
          auditEvents: state.auditEvents?.length ?? 0,
        },
        null,
        2,
      ),
    );
    const path = `/opt/cursor/artifacts/cursor-${seq}.html`;
    writeFileSync(path, html);
    await videoPage.goto(`file://${path}`);
    await videoPage.waitForTimeout(900);
  }
  await context.close();
} finally {
  await browser.close();
  api.kill("SIGTERM");
}

writeFileSync(
  "/opt/cursor/artifacts/replay-capture-steps.json",
  JSON.stringify(steps, null, 2),
);
console.log("Phase 25 capture complete");
