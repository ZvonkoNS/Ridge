# Desktop GUI (Tauri v2 + React + TypeScript) Standards

Last verified: 2026-10-16
Update when: the GUI stack, Tauri version, IPC contract, capability files, CSP, packaging or update channel change.

Status: the GUI is not built yet (planned milestone M4, planned folder `gui/`). These rules apply from the first GUI commit. Architecture decisions are recorded as ADRs (table in `docs/architecture.md` section 13, files in `docs/adr/` when created); `docs/architecture.md` section 7.3 already fixes the sidecar transport and packaging (signed PyInstaller one-folder build, newline-delimited JSON-RPC, no ports). Open GUI decisions: isolation pattern, IPC type generation.

## 1. Trust model

| Layer | Trust | Role |
| --- | --- | --- |
| WebView (React UI) | Untrusted. It plays the role this pack gives to "the browser/client". | Display and input only. No security decision, no file system access, no direct process control. |
| Tauri Rust core (`gui/src-tauri/`) | Trusted | Owns windows, native dialogs, the IPC allow-list, sidecar lifecycle, case-scoped handles. |
| Python sidecar (planned `src/ridge/sidecar/`) | Trusted | Runs the Ridge core: case store, custody log, pipeline, reports. Re-validates every request. |

Tauri's own model matches this: WebView code reaches system resources only through the IPC layer, while core and plugin code is fully privileged (source: Tauri v2 security overview, see `references.md`). Every value crossing WebView to Rust and Rust to sidecar is untrusted input for the receiver.

## 2. Process and transport rules

- The GUI talks to the Python core only through the Rust core, which talks to the sidecar over stdio using JSON-RPC 2.0 messages. Rules for those handlers: `edge_function_standards.md`.
- No network sockets, no localhost HTTP server, no named pipes exposed to other users, no WebSocket.
- The Rust core spawns the sidecar itself at startup from the bundled binary. No capability grants `shell:*` (execute, spawn, open) to any WebView.
- The sidecar binary is located by the Rust core from the application bundle only, never from `PATH`, the working directory, configuration or user input.
- Sidecar crashes are surfaced to the examiner; the core restarts the sidecar at most a bounded number of times and never retries a mutating request automatically.

## 3. IPC allow-list

- Only custom Tauri commands defined by Ridge are callable. Restrict registered commands at build time (`AppManifest::commands` in `build.rs`) and grant each one explicitly in `gui/src-tauri/capabilities/` files; one capability file per window.
- Do not enable core plugins the product does not need. Not allowed without an ADR: `fs`, `http`, `shell`, `opener`, `process`, `updater`, `websocket`, `upload`, `sql`, `store`.
- Capability files must not contain a `remote` section. Remote origins never get IPC access.
- Each command handler is thin (about 20-30 lines), deserialises into typed structs with `#[serde(deny_unknown_fields)]`, enforces size limits, validates, maps to exactly one allow-listed sidecar method, and returns a safe typed result or a typed error.
- The WebView never sends file system paths for reading or writing. Files are chosen through a native dialog opened by the Rust core; the WebView receives opaque, case-scoped handles.
- Evidence images are shown through a Rust-served custom URI scheme that resolves opaque handles only (no path segments, no traversal), or as `blob:` data. The built-in `asset:` protocol is not enabled for case data.

## 4. Content Security Policy and content rules

- Tauri applies a CSP only when one is configured; Ridge must configure it. Baseline:
  `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: <ridge-scheme>:; font-src 'self'; connect-src` limited to the IPC origins Tauri v2 requires for the pinned version; `object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`.
- Forbidden: `'unsafe-inline'`, `'unsafe-eval'`, remote origins, CDN scripts or styles, remote fonts (including Google Fonts), analytics, iframes of external content. Bundle every asset.
- Navigation to any URL outside the app is blocked in the Rust core; new windows from the WebView are denied. The offline workstation has no use for external links.
- DevTools are disabled in release builds.
- Evaluate the Tauri isolation pattern for the main window and record the decision as an ADR.

## 5. Updates and distribution

- No updater plugin and no update check over the internet.
- Updates are signed installer packages delivered through the organisation's internal offline channel. Installers are OS code-signed; release artifacts also carry a detached signature and SHA-256 list that the installer procedure verifies before installation (see `release_readiness_checklist.md`).
- Each release ships its SBOM (CycloneDX) for Python, npm and Cargo dependencies.

## 6. Forensic UI rules

- The original image is always available side by side with the processed output, and both are labelled with their SHA-256 prefix.
- Processed images always carry the label "Processed image - not an identification" or approved equivalent wording (see forbidden claims in `forensic_evidence_and_biometric_data_standards.md`).
- The viewer states zoom level and interpolation; at magnification above 100 percent it uses nearest-neighbour by default so pixels are shown as computed.
- No colour, contrast or filter change is applied to evidence pixels without a visible indicator. Animations never apply to evidence pixel content.
- All parameters used for an output are visible and match the job report.
- The WebView never stores class E or C data in `localStorage`, `sessionStorage`, IndexedDB, Cache Storage or service workers. In-memory state is cleared when a case is closed.

## 7. TypeScript and React profile

- TypeScript `strict: true`, plus `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noFallthroughCasesInSwitch`. No `any`, no `@ts-ignore` without a linked issue.
- ECMA-262 target set to what the oldest supported WebView supports (WebView2 on Windows 11, WKWebView on macOS, WebKitGTK on Linux); record it in `Project_Standards_Profile.md`.
- ESLint with typescript-eslint strict type-checked rules and React hooks rules; formatter check in CI.
- Forbidden: `eval`, `new Function`, string timers, `dangerouslySetInnerHTML`, rendering untrusted strings as HTML, dynamic `import()` of computed URLs.
- IPC request and response types are generated from or checked against the Rust and JSON-RPC schemas (tooling chosen in an ADR). Client-side validation is for usability only; Rust and the sidecar re-validate.

## 8. Rust profile (Tauri core)

- `#![forbid(unsafe_code)]` in the application crate.
- `cargo clippy -- -D warnings` clean; deny `clippy::unwrap_used` and `clippy::expect_used` outside tests; no panics on untrusted input.
- Bounded reads from the sidecar (maximum message size), per-request timeouts, explicit error mapping to typed IPC errors without internal paths or stack traces.
- `cargo audit` and `cargo deny check` (advisories, licenses, bans, sources) clean; `Cargo.lock` committed.

## 9. Accessibility

- Target WCAG 2.2 level AA (also published as ISO/IEC 40500:2025): keyboard operation of every control including the image viewer, visible focus, contrast, target size, no information by colour alone, text resize, clear error messages.
- Automated checks (for example axe-core in component and E2E tests) plus a manual screen-reader pass (NVDA on Windows, VoiceOver on macOS) for the main case workflow before each GUI release.

## 10. Animation standard

- Motion is the animation library: `npm install motion`, import from `"motion/react"`. `framer-motion` is acceptable for existing code. Install only the published npm package; never install from a git repository or URL.
- Standard patterns: staggered fade and rise when list or panel content scrolls into view; short micro-interactions on interactive elements (hover, press, focus).
- Always respect `prefers-reduced-motion`: wrap the app in `MotionConfig reducedMotion="user"` and use `useReducedMotion` for custom motion.
- Never delay the Largest Contentful Paint: the main viewer and its first image are visible immediately and are not faded in from opacity 0.

## 11. npm supply chain

- `package-lock.json` committed; installs use `npm ci`; exact versions; no git, URL or file dependencies.
- Lifecycle scripts are disabled by default (`ignore-scripts`) and enabled only for reviewed packages.
- `npm audit --audit-level=moderate` clean or documented exception; license allow-list check; CycloneDX SBOM.

## 12. Testing

| Area | Tests |
| --- | --- |
| Unit and component | Vitest and React Testing Library: render, loading, empty and error states; labels; keyboard; reduced-motion behaviour. |
| IPC security | Commands outside the allow-list fail; unknown fields, oversized payloads, wrong types and forged handles are rejected in Rust; WebView cannot reach `fs`, `shell` or `http`. |
| CSP and offline | CSP present in the built app; no request leaves the machine during a full workflow (network monitored in E2E); navigation to external URLs is blocked. |
| Sidecar | Startup, crash and restart, timeout, malformed JSON-RPC response, version mismatch between GUI and sidecar. |
| Forensic UI | Original and processed shown with hashes; label present; parameters match the job report. |
| Accessibility | Automated checks and the manual pass in section 9. |
| E2E | Tauri WebDriver where the platform supports it; mocked-IPC browser tests for UI-only flows. Record platforms not covered. |

## 13. GUI quality gates (when `gui/` exists)

```bash
npm run lint
npm run typecheck
npm run test
npm run build
npm run test:e2e
npm audit --audit-level=moderate
cargo clippy -- -D warnings
cargo audit
cargo deny check
cargo test
```

The Python gates (`python tools/gate.py all`) remain required. Wiring the GUI gates into `tools/gate.py` is proposed; until then they run as separate CI jobs.
