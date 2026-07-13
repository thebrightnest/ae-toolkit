#!/usr/bin/env node
// E2E harness for panel live-run visibility (lvp-01).
// Drives the real panel against a fixture telemetry archive (HOME override)
// with headless Chrome over the DevTools Protocol. Zero npm dependencies
// (Node >= 22 built-in fetch + WebSocket), on the test-panel-plan-detail.mjs
// pattern.
//
// Usage: node scripts/test-panel-live-runs.mjs
//
// Checks (plan validation steps, docs/plans/lvp-01-panel-live-run-visibility.md
// and docs/plans/lvp-02-panel-auto-refresh.md):
//  1. an empty current-layout run dir renders a row with a live badge
//  2. a stale no-summary run dir renders incomplete (never success)
//  3. live rows sort first, then last activity descending
//  4. run detail shows the in-progress banner (zero-record + partial variants)
//  5. the Plans lens shows a live dot when a contributing run is live
//  6. a stage record appended mid-session appears in the row within ~6s (lvp-02)
//  7. a stale run whose mtime advances flips incomplete → live (lvp-02)
//  8. no polling while the tab is hidden; immediate tick on resume (lvp-02)
//  9. zero console errors

import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const SERVE = path.resolve("aet-work/panel/serve");
const CDP_PORT = 9223;

const RUN_LIVE_EMPTY = "1a1a1a1a-0000-4000-8000-000000000001";
const RUN_LIVE_PARTIAL = "2b2b2b2b-0000-4000-8000-000000000002";
const RUN_STALE = "3c3c3c3c-0000-4000-8000-000000000003";
const RUN_DONE = "4d4d4d4d-0000-4000-8000-000000000004";
const PLAN_NAME = "lvp-99-demo-plan";

const failures = [];
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`  ok   ${name}`);
  } else {
    console.log(`  FAIL ${name}${detail ? " — " + detail : ""}`);
    failures.push(name);
  }
}

/* ---------------- fixture archive ---------------- */

const stageRec = over =>
  JSON.stringify({
    type: "stage",
    task_id: "lvp-99",
    stage: "implemented",
    result: "success",
    plan_file: `/repo/.worktrees/lvp-99/docs/plans/${PLAN_NAME}.md`,
    start_time: "2026-07-13T10:00:00Z",
    end_time: "2026-07-13T10:01:00Z",
    duration_seconds: 60,
    ...over,
  });

function buildFixture() {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "panel-live-home-"));
  const root = path.join(home, ".aet", "telemetry");
  const now = Date.now() / 1000;
  const mk = (rel, files, mtime) => {
    const dir = path.join(root, rel);
    fs.mkdirSync(dir, { recursive: true });
    for (const [name, content] of Object.entries(files || {})) {
      const p = path.join(dir, name);
      fs.writeFileSync(p, content);
      fs.utimesSync(p, mtime, mtime);
    }
    fs.utimesSync(dir, mtime, mtime);
  };
  // Empty dir, fresh: a just-started run — must render live.
  mk(`proj/2026-07-13/${RUN_LIVE_EMPTY}`, {}, now - 60);
  // Partial JSONL, fresh: mid-pipeline run contributing to a plan — live.
  mk(`proj/2026-07-13/${RUN_LIVE_PARTIAL}`, {
    "task.jsonl": stageRec({ stage: "plan-approved" }) + "\n" + stageRec({}) + "\n",
  }, now - 30);
  // Partial JSONL, 2h stale: crashed/abandoned run — incomplete, never success.
  mk(`proj/2026-07-10/${RUN_STALE}`, {
    "task.jsonl": stageRec({ plan_file: null }) + "\n",
  }, now - 7200);
  // Completed run: keeps the existing outcome logic — success.
  mk(`proj/2026-07-09/${RUN_DONE}`, {
    "task.jsonl": stageRec({ plan_file: null }) + "\n",
    "last-run.json": JSON.stringify({
      run_id: RUN_DONE,
      outcome: "success",
      tasks_succeeded: 1,
      tasks_spawned: 1,
      start_time: "2026-07-09T10:00:00Z",
      end_time: "2026-07-09T10:05:00Z",
    }),
  }, now - 120);
  return { home, root };
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
  const { home, root } = buildFixture();
  console.log(`fixture archive: ${path.join(home, ".aet", "telemetry")}`);

  // 1. panel server against the fixture archive (HOME override), random port
  // -u: the launcher prints its URL on stdout, which is block-buffered when piped
  const serve = spawn("python3", ["-u", SERVE, "--no-open"], {
    stdio: ["ignore", "pipe", "inherit"],
    env: { ...process.env, HOME: home },
  });
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
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "panel-live-e2e-"));
  const chrome = spawn(CHROME, [
    "--headless=new", "--disable-gpu", "--no-first-run", "--disable-extensions",
    `--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${profile}`, "about:blank",
  ], { stdio: "ignore" });

  let cdp, sessionId;
  try {
    // 3. attach
    let wsUrl;
    for (let i = 0; i < 50; i++) {
      try {
        const r = await fetch(`http://127.0.0.1:${CDP_PORT}/json/version`);
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

    // 4. load panel (opens on the Plans lens), switch to the Runs lens
    await cdp.send("Page.navigate", { url: panelUrl }, sessionId);
    await waitFor(`document.body.textContent.includes("${PLAN_NAME}")`, "fixture plan row loaded");
    await ev(`(() => { const b = [...document.querySelectorAll("button")].find(b => b.textContent.trim() === "Runs"); b.click(); })()`);
    await waitFor(`document.body.textContent.includes("${RUN_DONE.slice(0, 8)}")`, "runs lens rows");

    const rowExpr = runId => `(() => {
      const tr = [...document.querySelectorAll("tbody tr")].find(t => t.textContent.includes("${runId.slice(0, 8)}"));
      return tr ? { text: tr.textContent, hasDot: !!tr.querySelector(".live-dot") } : null;
    })()`;

    console.log("\nRuns lens: live badge for a just-started (empty) run dir");
    const emptyRow = await ev(rowExpr(RUN_LIVE_EMPTY));
    check("empty-dir run row renders", !!emptyRow);
    check("empty-dir run row has live badge + pulsing dot",
      !!emptyRow && emptyRow.text.includes("live") && emptyRow.hasDot,
      emptyRow ? JSON.stringify(emptyRow) : "row missing");

    console.log("\nRuns lens: stale no-summary run is honest (incomplete, never success)");
    const staleRow = await ev(rowExpr(RUN_STALE));
    check("stale no-summary run renders incomplete badge",
      !!staleRow && staleRow.text.includes("incomplete") && !staleRow.text.includes("success"),
      staleRow ? JSON.stringify(staleRow) : "row missing");

    console.log("\nRuns lens: live first, then last activity descending");
    const order = await ev(`(() => {
      const grid = [...document.querySelectorAll("div.grid")].find(g => g.children[0] && g.children[0].querySelector("tbody"));
      const left = grid ? grid.children[0] : null;
      return left ? [...left.querySelectorAll("tbody tr")].map(t => t.querySelector("td:nth-child(3)")?.textContent.trim()) : [];
    })()`);
    const expectedOrder = [RUN_LIVE_PARTIAL, RUN_LIVE_EMPTY, RUN_DONE, RUN_STALE].map(id => id.slice(0, 8) + "…");
    check("sort order: live first, then lastActivity desc",
      JSON.stringify(order) === JSON.stringify(expectedOrder), JSON.stringify(order));

    console.log("\nRun detail: in-progress banner");
    await ev(`(() => { const tr = [...document.querySelectorAll("tbody tr")].find(t => t.textContent.includes("${RUN_LIVE_EMPTY.slice(0, 8)}")); tr.click(); })()`);
    await waitFor(`!!document.querySelector('[data-testid="run-progress-banner"]')`, "banner for empty run");
    check("zero-record run banner: waiting for first stage record", await ev(`(() => {
      const el = document.querySelector('[data-testid="run-progress-banner"]');
      return el && el.textContent.includes("Waiting for first stage record");
    })()`));
    await ev(`(() => { const tr = [...document.querySelectorAll("tbody tr")].find(t => t.textContent.includes("${RUN_LIVE_PARTIAL.slice(0, 8)}")); tr.click(); })()`);
    await waitFor(`document.querySelector('[data-testid="run-progress-banner"]')?.textContent.includes("In progress")`, "banner for partial run");
    check("partial run banner: record count + relative activity", await ev(`(() => {
      const el = document.querySelector('[data-testid="run-progress-banner"]');
      const t = el ? el.textContent : "";
      return t.includes("In progress — 2 stage records") && /last activity (just now|\d+m ago)/.test(t);
    })()`));
    await ev(`(() => { const tr = [...document.querySelectorAll("tbody tr")].find(t => t.textContent.includes("${RUN_DONE.slice(0, 8)}")); tr.click(); })()`);
    await waitFor(`document.body.textContent.includes("Wall clock")`, "completed run detail");
    check("completed run shows no banner", await ev(`!document.querySelector('[data-testid="run-progress-banner"]')`));

    console.log("\nPlans lens: live dot when a contributing run is live");
    await ev(`(() => { const b = [...document.querySelectorAll("button")].find(b => b.textContent.trim() === "Plans"); b.click(); })()`);
    await waitFor(`document.body.textContent.includes("${PLAN_NAME}")`, "plans lens");
    check("plan row with a live contributing run shows the live dot", await ev(`(() => {
      const tr = [...document.querySelectorAll("tbody tr")].find(t => t.textContent.includes("${PLAN_NAME}"));
      return !!tr && !!tr.querySelector('[data-testid="plan-live-dot"]');
    })()`));

    console.log("\nAuto-refresh: mid-session append appears without manual refresh (lvp-02)");
    await ev(`(() => { const b = [...document.querySelectorAll("button")].find(b => b.textContent.trim() === "Runs"); b.click(); })()`);
    await waitFor(`document.body.textContent.includes("${RUN_DONE.slice(0, 8)}")`, "runs lens rows (auto-refresh)");
    const stagesCell = runId => `(() => {
      const tr = [...document.querySelectorAll("tbody tr")].find(t => t.textContent.includes("${runId.slice(0, 8)}"));
      return tr ? tr.querySelector("td:nth-child(5)")?.textContent.trim() : null;
    })()`;
    check("partial run starts with 2 stage records", await ev(`(${stagesCell(RUN_LIVE_PARTIAL)}) === "2"`));
    fs.appendFileSync(path.join(root, "proj/2026-07-13", RUN_LIVE_PARTIAL, "task.jsonl"),
      stageRec({ stage: "qa-complete" }) + "\n");
    let gainedWithin6s = false;
    try {
      await waitFor(`(${stagesCell(RUN_LIVE_PARTIAL)}) === "3"`, "row gains appended record", 7000);
      gainedWithin6s = true;
    } catch {}
    check("appended stage record appears in the row within ~6s (no manual refresh)", gainedWithin6s);

    console.log("\nPoll-diff liveness: stale run flips incomplete → live on mtime advance");
    const staleBefore = await ev(rowExpr(RUN_STALE));
    check("stale run starts incomplete", !!staleBefore && staleBefore.text.includes("incomplete"));
    // Append a record, then age its mtime to 45 min ago: the dir's mtime
    // advances vs the last poll (2h → 45m) but stays outside the 30-minute
    // freshness window, so only poll-diff liveness can recover "live".
    const staleJsonl = path.join(root, "proj/2026-07-10", RUN_STALE, "task.jsonl");
    fs.appendFileSync(staleJsonl, stageRec({ plan_file: null, stage: "qa-complete" }) + "\n");
    const aged = Date.now() / 1000 - 2700;
    fs.utimesSync(staleJsonl, aged, aged);
    let flippedToLive = false;
    try {
      await waitFor(`(() => {
        const tr = [...document.querySelectorAll("tbody tr")].find(t => t.textContent.includes("${RUN_STALE.slice(0, 8)}"));
        return !!tr && tr.textContent.includes("live") && !tr.textContent.includes("incomplete");
      })()`, "stale run flips to live", 7000);
      flippedToLive = true;
    } catch {}
    check("mtime advance past the freshness window flips incomplete → live", flippedToLive);

    console.log("\nVisibility gating: no polling while hidden, immediate tick on resume");
    // CDP focus emulation does not drive document.visibilityState in
    // headless=new (Chrome 150), so override the property directly — the
    // plan's sanctioned "visibility override" — and dispatch the event our
    // listener reacts to.
    const setVisibility = state => ev(`(() => {
      window.__vis = "${state}";
      if (!document.__visOverridden) {
        Object.defineProperty(document, "visibilityState", { get: () => window.__vis, configurable: true });
        document.__visOverridden = true;
      }
      document.dispatchEvent(new Event("visibilitychange"));
      return document.visibilityState;
    })()`);
    await setVisibility("hidden");
    check("tab reports hidden", await ev(`document.visibilityState`) === "hidden");
    fs.appendFileSync(path.join(root, "proj/2026-07-13", RUN_LIVE_PARTIAL, "task.jsonl"),
      stageRec({ stage: "reviewed" }) + "\n");
    await sleep(8000); // > one poll interval: ungated polling would pick it up
    check("no polling while hidden (appended record not picked up)",
      await ev(`(${stagesCell(RUN_LIVE_PARTIAL)}) === "3"`));
    await setVisibility("visible");
    let resumedImmediately = false;
    try {
      await waitFor(`(${stagesCell(RUN_LIVE_PARTIAL)}) === "4"`, "immediate tick on resume", 3000);
      resumedImmediately = true;
    } catch {}
    check("resume triggers an immediate tick (record appears ≤ ~3s)", resumedImmediately);
    await ev(`delete document.visibilityState`).catch(() => {});

    console.log("\nConsole");
    check("zero console errors", cdp.consoleErrors.length === 0,
      cdp.consoleErrors.slice(0, 5).join(" | "));
  } finally {
    if (cdp) cdp.close();
    chrome.kill("SIGKILL");
    serve.kill();
    // Let Chrome exit before sweeping its profile, or rmdir hits ENOTEMPTY
    // on cache files it is still flushing.
    await Promise.race([new Promise(r => chrome.once("exit", r)), sleep(3000)]);
    fs.rmSync(profile, { recursive: true, force: true, maxRetries: 3, retryDelay: 200 });
    fs.rmSync(home, { recursive: true, force: true, maxRetries: 3, retryDelay: 200 });
  }

  console.log("");
  if (failures.length) {
    console.log(`FAILED: ${failures.length} check(s)`);
    process.exit(1);
  }
  console.log("ALL CHECKS PASSED");
}

main().catch(e => { console.error(e.message); process.exit(1); });
