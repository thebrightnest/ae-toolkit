#!/usr/bin/env node
// E2E harness for the panel PlanDetail view (thp-06).
// Drives the real panel against the live ~/.aet/telemetry archive with
// headless Chrome over the DevTools Protocol. Zero npm dependencies
// (Node >= 22 built-in fetch + WebSocket).
//
// Usage: node scripts/test-panel-plan-detail.mjs
//
// Checks (plan validation steps, docs/plans/thp-06-panel-plan-detail.md):
//  1. selecting the wfd-01 plan shows the spine's completed states and stall point
//  2. the consolidated timeline has rows from >= 2 runs, chronological, with
//     worktree + duration + result populated
//  3. a retried stage (reviewed) appears as repeated rows
//  4. clicking a run chip lands on that run's detail in the Runs lens
//  5. aggregated issues/learnings match an independent archive scan
//  6. zero console errors
//  7. Runs lens regression: run detail still renders
//  8. empty-state: a run_summary-only plan renders the "no rows" pattern

import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const SERVE = path.resolve("src/aet/panel/serve.py");
const TELEMETRY = path.join(os.homedir(), ".aet/telemetry");
const PLAN_NAME = "wfd-01-frontmatter-routing";
const PROJECT = "thebrightnest/ae-toolkit";
const RETRY_RUN = "684c6d9f-4e7e-4ce8-9c0b-40b99a364c10"; // second run (reviewed retry)

const failures = [];
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`  ok   ${name}`);
  } else {
    console.log(`  FAIL ${name}${detail ? " — " + detail : ""}`);
    failures.push(name);
  }
}

/* ---------------- independent archive scan (ground truth) ---------------- */

function scanPlanGroundTruth() {
  const projectDir = path.join(TELEMETRY, PROJECT);
  const rows = [];
  let issues = 0;
  let learnings = 0;
  const runIds = new Set();
  for (const date of fs.readdirSync(projectDir)) {
    const dateDir = path.join(projectDir, date);
    if (!fs.statSync(dateDir).isDirectory()) continue;
    for (const runId of fs.readdirSync(dateDir)) {
      const runDir = path.join(dateDir, runId);
      if (!fs.statSync(runDir).isDirectory()) continue;
      for (const file of fs.readdirSync(runDir)) {
        if (!file.endsWith(".jsonl") || file === "work-history.jsonl") continue;
        for (const line of fs.readFileSync(path.join(runDir, file), "utf8").split("\n")) {
          const t = line.trim();
          if (!t) continue;
          let rec;
          try { rec = JSON.parse(t); } catch { continue; }
          if (!rec || !String(rec.plan_file || "").includes(PLAN_NAME)) continue;
          const time = rec.start_time || rec.timestamp;
          if (rec.type === "stage") {
            rows.push({ kind: "stage", stage: rec.stage, result: rec.result, time, runId });
            runIds.add(runId);
          } else if (rec.type === "test_run") {
            rows.push({ kind: "test", stage: rec.stage, result: rec.result, time, runId });
            runIds.add(runId);
          } else if (rec.type === "environment_issue") {
            issues++;
          } else if (rec.type === "learning_candidate") {
            learnings++;
          }
        }
      }
    }
  }
  rows.sort((a, b) => (a.time || "").localeCompare(b.time || ""));
  return { rows, issues, learnings, runCount: runIds.size };
}

/* ---------------- minimal CDP client ---------------- */

class CDP {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.nextId = 1;
    this.pending = new Map();
    this.consoleErrors = [];
    this.ready = new Promise((resolve, reject) => {
      this.ws.addEventListener("open", resolve, { once: true });
      this.ws.addEventListener("error", reject, { once: true });
    });
    this.ws.addEventListener("message", ev => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
        return;
      }
      if (msg.method === "Runtime.exceptionThrown") {
        const d = msg.params.exceptionDetails;
        this.consoleErrors.push(d.exception?.description || d.text || "exception");
      } else if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") {
        this.consoleErrors.push(msg.params.args.map(a => a.value || a.description || "").join(" "));
      } else if (msg.method === "Log.entryAdded" && msg.params.entry.level === "error") {
        this.consoleErrors.push(msg.params.entry.text);
      }
    });
  }
  send(method, params = {}, sessionId) {
    const id = this.nextId++;
    const payload = { id, method, params };
    if (sessionId) payload.sessionId = sessionId;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify(payload));
    });
  }
  close() { this.ws.close(); }
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

/* ---------------- main ---------------- */

async function main() {
  const truth = scanPlanGroundTruth();
  console.log(`ground truth: ${truth.rows.length} timeline rows across ${truth.runCount} runs, ` +
    `${truth.issues} issue(s), ${truth.learnings} learning(s)`);
  if (truth.rows.length < 3 || truth.runCount < 2) {
    throw new Error("archive no longer holds the multi-run wfd-01 fixture; cannot verify thp-06");
  }

  // 1. panel server (random port, printed on stdout)
  // -u: the launcher prints its URL on stdout, which is block-buffered when piped
  const serve = spawn("python3", ["-u", SERVE, "--no-open"], { stdio: ["ignore", "pipe", "inherit"] });
  const panelUrl = await new Promise((resolve, reject) => {
    let buf = "";
    serve.stdout.on("data", d => {
      buf += d;
      const m = buf.match(/AET telemetry panel: (http:\/\/\S+)/);
      if (m) resolve(m[1]);
    });
    serve.on("exit", c => reject(new Error(`serve exited (${c})`)));
    setTimeout(() => reject(new Error("serve did not print a URL")), 15000);
  });

  // 2. headless Chrome
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "panel-e2e-"));
  const chrome = spawn(CHROME, [
    "--headless=new", "--disable-gpu", "--no-first-run", "--disable-extensions",
    "--remote-debugging-port=9222", `--user-data-dir=${profile}`, "about:blank",
  ], { stdio: "ignore" });

  let cdp, sessionId;
  try {
    // 3. attach
    let wsUrl;
    for (let i = 0; i < 50; i++) {
      try {
        const r = await fetch("http://127.0.0.1:9222/json/version");
        wsUrl = (await r.json()).webSocketDebuggerUrl;
        break;
      } catch { await sleep(200); }
    }
    if (!wsUrl) throw new Error("chrome devtools endpoint never came up");
    cdp = new CDP(wsUrl);
    await cdp.ready;
    const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
    ({ sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true }));
    await cdp.send("Runtime.enable", {}, sessionId);
    await cdp.send("Log.enable", {}, sessionId);
    await cdp.send("Page.enable", {}, sessionId);

    const ev = async expression => {
      const r = await cdp.send("Runtime.evaluate",
        { expression, returnByValue: true, awaitPromise: true }, sessionId);
      if (r.exceptionDetails) {
        throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
      }
      return r.result.value;
    };
    const waitFor = async (expression, label, timeout = 60000) => {
      const start = Date.now();
      for (;;) {
        const v = await ev(expression).catch(() => null);
        if (v) return v;
        if (Date.now() - start > timeout) throw new Error(`timeout waiting for: ${label}`);
        await sleep(500);
      }
    };

    // 4. load panel, wait for the wfd-01 plan row (project column included in row text)
    await cdp.send("Page.navigate", { url: panelUrl }, sessionId);
    const rowExpr = planProject =>
      `(() => { const tr = [...document.querySelectorAll("tbody tr")].find(t => ` +
      `t.textContent.includes("${PLAN_NAME}") && t.textContent.includes("${planProject}")); ` +
      `return tr ? true : false; })()`;
    await waitFor(rowExpr(PROJECT), "wfd-01 plan row in thebrightnest/ae-toolkit");

    console.log("\nPlanDetail: header + spine");
    await ev(`(() => { const tr = [...document.querySelectorAll("tbody tr")].find(t => ` +
      `t.textContent.includes("${PLAN_NAME}") && t.textContent.includes("${PROJECT}")); tr.click(); })()`);
    await waitFor(`!!document.querySelector('[data-testid="plan-detail"]')`, "plan detail");

    check("header shows plan name and project", await ev(`(() => {
      const el = document.querySelector('[data-testid="plan-detail"]');
      return el.textContent.includes("${PLAN_NAME}") && el.textContent.includes("${PROJECT}");
    })()`));
    check(`header shows ${truth.runCount} contributing runs`, await ev(`(() => {
      const el = document.querySelector('[data-testid="plan-detail-runs"]');
      return el && el.textContent.trim() === "${truth.runCount}";
    })()`));

    const spine = await ev(`(() => {
      const out = {};
      for (const el of document.querySelectorAll('[data-testid^="spine-state-"]')) {
        out[el.dataset.testid.replace("spine-state-", "")] = el.dataset.state;
      }
      return out;
    })()`);
    for (const s of ["plan-approved", "implemented", "qa-complete", "reviewed"]) {
      check(`spine: ${s} done`, spine[s] === "done", `got ${spine[s]}`);
    }
    for (const s of ["secure", "synced"]) {
      check(`spine: ${s} pending (stall point)`, spine[s] === "pending", `got ${spine[s]}`);
    }

    console.log("\nConsolidated timeline");
    const timeline = await ev(`(() => [...document.querySelectorAll('[data-testid="timeline-row"]')].map(tr => ({
      kind: tr.dataset.kind, run: tr.dataset.run, time: tr.dataset.time, result: tr.dataset.result,
      stage: tr.querySelector('[data-testid="timeline-stage"]')?.textContent.trim(),
      worktree: tr.querySelector('[data-testid="timeline-worktree"]')?.textContent.trim(),
      duration: tr.querySelector('[data-testid="timeline-duration"]')?.textContent.trim(),
    })))()`);
    check(`timeline row count = ${truth.rows.length} (independent scan)`, timeline.length === truth.rows.length,
      `got ${timeline.length}`);
    check("timeline spans >= 2 distinct runs", new Set(timeline.map(r => r.run)).size >= 2);
    check("timeline chronological (start_time asc)",
      timeline.every((r, i) => i === 0 || timeline[i - 1].time <= r.time));
    check("worktree/duration/result populated on every row",
      timeline.every(r => r.worktree && r.worktree !== "—" && r.duration && r.duration !== "—" && r.result));
    check("rows match ground-truth kind/stage/result sequence",
      JSON.stringify(timeline.map(r => [r.kind, r.stage, r.result])) ===
      JSON.stringify(truth.rows.map(r => [r.kind, r.stage, r.result])),
      `panel: ${JSON.stringify(timeline.map(r => [r.kind, r.stage, r.result]))}`);
    const reviewedRows = timeline.filter(r => r.stage === "reviewed" && r.kind === "stage");
    check("retried stage (reviewed) appears as repeated rows",
      reviewedRows.length >= 2 && new Set(reviewedRows.map(r => r.result)).size === 2,
      `got ${JSON.stringify(reviewedRows.map(r => r.result))}`);

    console.log("\nAggregates");
    const issueRows = await ev(`document.querySelectorAll('[data-testid="issues-table"] tbody tr').length`);
    const learningRows = await ev(`document.querySelectorAll('[data-testid="learnings-table"] tbody tr').length`);
    check(`aggregated environment issues = ${truth.issues}`, issueRows === truth.issues, `got ${issueRows}`);
    check(`aggregated learning candidates = ${truth.learnings}`, learningRows === truth.learnings, `got ${learningRows}`);

    console.log("\nRun chips → cross-lens navigation");
    const chips = await ev(`[...document.querySelectorAll('[data-testid="run-chip"]')].map(c => c.dataset.runDir)`);
    check(`run chip count = ${truth.runCount}`, chips.length === truth.runCount, `got ${JSON.stringify(chips)}`);
    check("retry run has a chip", chips.some(d => d.includes(RETRY_RUN)));
    await ev(`[...document.querySelectorAll('[data-testid="run-chip"]')].find(c => c.dataset.runDir.includes("${RETRY_RUN}")).click()`);
    await waitFor(`document.body.textContent.includes("${RETRY_RUN}")`, "run detail for retry run");
    check("chip click lands in Runs lens", await ev(`(() => {
      const tabs = [...document.querySelectorAll("button")].find(b => b.textContent.trim() === "Runs");
      return tabs && tabs.className.includes("bg-primary");
    })()`));
    check("Runs lens regression: run detail renders stages", await ev(`(() => {
      const el = document.querySelector('[data-testid="run-detail"]');
      return el && el.textContent.includes("Stages") && el.textContent.includes("reviewed");
    })()`));

    console.log("\nEmpty state (run_summary-only plan)");
    await ev(`(() => { const b = [...document.querySelectorAll("button")].find(b => b.textContent.trim() === "Plans"); b.click(); })()`);
    let emptyStateRow = false;
    try {
      await waitFor(rowExpr("T/tmp"), "run_summary-only wfd-01 plan row", 5000);
      emptyStateRow = true;
    } catch {
      console.log("  skip empty-state check: T/tmp run_summary-only fixture not present in live archive");
    }
    if (emptyStateRow) {
      await ev(`(() => { const tr = [...document.querySelectorAll("tbody tr")].find(t => ` +
        `t.textContent.includes("${PLAN_NAME}") && t.textContent.includes("T/tmp")); tr.click(); })()`);
      await waitFor(`!!document.querySelector('[data-testid="plan-detail"]')`, "plan detail (empty)");
      check("zero-row timeline renders the no-rows pattern", await ev(`(() => {
        const el = document.querySelector('[data-testid="timeline-empty"]');
        return el && el.textContent.includes("No stage sessions or test runs recorded for this plan");
      })()`));
    }

    console.log("\nConsole");
    check("zero console errors", cdp.consoleErrors.length === 0,
      cdp.consoleErrors.slice(0, 5).join(" | "));
  } finally {
    if (cdp) cdp.close();
    chrome.kill("SIGKILL");
    serve.kill();
    fs.rmSync(profile, { recursive: true, force: true });
  }

  console.log("");
  if (failures.length) {
    console.log(`FAILED: ${failures.length} check(s)`);
    process.exit(1);
  }
  console.log("ALL CHECKS PASSED");
}

main().catch(e => { console.error(e.message); process.exit(1); });
