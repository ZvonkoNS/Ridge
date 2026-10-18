// Development smoke test of the built desktop app over WebView2's DevTools protocol (Windows).
// Nothing here ships. It needs a synthetic, empty store and touches no OS keystore entry:
// it opens the first-run passphrase prompt and cancels it.
//
//   cd gui/src-tauri && cargo build --features tauri/custom-protocol
//   set RIDGE_DEV_STORE=<empty folder>  (debug builds only)
//   set WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9333
//   target\debug\ridge-gui.exe
//   node tools/gui_smoke.mjs 9333 <output folder>
//
// It checks the CSP (inline script and remote fetch blocked), that WebView storage stays empty,
// that each window can call only its own commands, that the dialog plugin is closed to the
// WebView, and that the real sidecar answers; it writes cdp_report.json and two screenshots.
import { writeFileSync } from "node:fs";
import { join } from "node:path";

const [port, out] = process.argv.slice(2);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function targets() {
  for (let i = 0; i < 60; i += 1) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/list`);
      const list = await res.json();
      if (list.some((t) => t.type === "page")) return list;
    } catch {}
    await sleep(500);
  }
  throw new Error("no DevTools target");
}

function connect(url) {
  const ws = new WebSocket(url);
  let id = 0;
  const pending = new Map();
  const events = [];
  ws.onmessage = (m) => {
    const msg = JSON.parse(m.data);
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    } else if (msg.method) {
      events.push(msg);
    }
  };
  const ready = new Promise((r) => (ws.onopen = r));
  const send = (method, params = {}) =>
    new Promise((resolve) => {
      id += 1;
      pending.set(id, resolve);
      ws.send(JSON.stringify({ id, method, params }));
    });
  return { ready, send, events, close: () => ws.close() };
}

async function evaluate(page, expression) {
  const r = await page.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  return r.result?.result?.value ?? r.result?.exceptionDetails?.text;
}

async function shot(page, name) {
  const r = await page.send("Page.captureScreenshot", { format: "png" });
  writeFileSync(join(out, name), Buffer.from(r.result.data, "base64"));
}

const report = {};
const list = await targets();
const main = list.find((t) => t.type === "page" && t.url.includes("index.html")) ?? list.find((t) => t.type === "page");
report.mainUrl = main.url;
const page = connect(main.webSocketDebuggerUrl);
await page.ready;
await page.send("Runtime.enable");
await page.send("Log.enable");
await page.send("Page.enable");
await sleep(2500);
report.cspSource = await evaluate(page, "document.querySelector('meta[http-equiv=\"Content-Security-Policy\"]')?.content ?? 'header'");
report.mainText = await evaluate(page, "document.body.innerText.slice(0, 600)");
report.tauriGlobal = await evaluate(page, "typeof window.__TAURI__");
report.inlineScriptBlocked = await evaluate(
  page,
  "new Promise((resolve) => { let fired = false; document.addEventListener('securitypolicyviolation', () => { fired = true; }, { once: true }); const s = document.createElement('script'); s.textContent = 'window.__inline = 1'; document.head.appendChild(s); setTimeout(() => resolve({ ran: window.__inline === 1, violation: fired }), 300); })",
);
report.remoteFetchBlocked = await evaluate(
  page,
  "fetch('https://example.com/').then(() => 'fetched', (e) => 'blocked: ' + e.name)",
);
report.storage = await evaluate(page, "JSON.stringify({ local: localStorage.length, session: sessionStorage.length })");
await shot(page, "app-main.png");

// Open the passphrase prompt for a first-run identity, look at it, then cancel (no keystore write).
await evaluate(page, "[...document.querySelectorAll('button')].find((b) => b.textContent.includes('Create examiner identity'))?.click() ?? 'no button'");
await sleep(2500);
const after = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const promptTarget = after.find((t) => t.type === "page" && t.url.includes("passphrase.html"));
report.promptOpened = Boolean(promptTarget);
if (promptTarget) {
  const prompt = connect(promptTarget.webSocketDebuggerUrl);
  await prompt.ready;
  await prompt.send("Runtime.enable");
  await sleep(1000);
  report.promptText = await evaluate(prompt, "document.body.innerText.slice(0, 400)");
  // The prompt window must not be able to call main-window commands (capability `passphrase`).
  report.promptCallsMainCommand = await evaluate(
    prompt,
    "window.__TAURI_INTERNALS__.invoke('list_items', {}).then(() => 'allowed', (e) => 'denied: ' + String(e))",
  );
  await shot(prompt, "app-prompt.png");
  await evaluate(prompt, "[...document.querySelectorAll('button')].find((b) => b.textContent === 'Cancel')?.click()");
  prompt.close();
  await sleep(1500);
}
// The main window must not be able to call the prompt's commands.
report.mainCallsPromptCommand = await evaluate(
  page,
  "window.__TAURI_INTERNALS__.invoke('passphrase_submit', { request: { passphrase: 'x', confirmation: null } }).then(() => 'allowed', (e) => 'denied: ' + String(e))",
);
report.mainCallsUnknownCommand = await evaluate(
  page,
  "window.__TAURI_INTERNALS__.invoke('plugin:dialog|open', {}).then(() => 'allowed', (e) => 'denied: ' + String(e))",
);
report.mainTextAfterCancel = await evaluate(page, "document.body.innerText.slice(0, 300)");
report.engine = await evaluate(page, "window.__TAURI_INTERNALS__.invoke('app_info', {}).then((v) => JSON.stringify(v), (e) => 'error: ' + JSON.stringify(e))");
report.consoleErrors = page.events
  .filter((e) => (e.method === "Runtime.consoleAPICalled" && e.params.type === "error") || e.method === "Runtime.exceptionThrown" || (e.method === "Log.entryAdded" && e.params.entry.level === "error"))
  .map((e) => JSON.stringify(e.params).slice(0, 300));
page.close();
writeFileSync(join(out, "cdp_report.json"), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
process.exit(0);
