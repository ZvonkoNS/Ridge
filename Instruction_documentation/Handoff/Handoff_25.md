# Handoff_25.md

Date/time (ISO 8601 with offset): 2026-10-18T19:30+02:00
Author/agent: Claude Code (claude-opus-5-5)
Project: Ridge
Branch: `m5-recovery-11` → `main`
Base commit: `1fbd5b3` (Merge pull request #23, Handoff_24)
Latest commit: see the pull request

## 1. Scope

The product owner's decisions, 2026-10-18:

- **ADR-012:** accepted, Option B.
- **Installer:** build and smoke-test it; "everything turnkey ready". Downloading Tauri's WiX 3.14 and NSIS 3.11 tools was explicitly approved.
- **OQ-8:** yes, a laboratory system countersigns exported custody heads out of band.
- **OQ-9:** one key per examiner; the FQM keeps the key register.
- **OQ-10:** the product owner holds all five owner roles on an interim basis.
- **Screen-reader pass:** the product owner runs it with NVDA from a script.

Completed:

| Area | What |
| --- | --- |
| Device-secret recovery (ADR-012) | `src/ridge/case/recovery.py`, `cli_recovery.py`: `ridge-case recovery export|import|check`. The OS-keystore secret is sealed under a separate recovery passphrase (Argon2id, AES-256-GCM, with key id, fingerprint and time bound into the seal) in `ridge.device-secret-recovery/1`. Export needs the examiner passphrase; the recovery passphrase meets the policy and is not the examiner's. Import never replaces a secret, first proves the secret unlocks the store's identity, and is undone if it cannot be logged |
| Store audit file | `src/ridge/case/store_audit.py`: `store-audit.jsonl`, hash-chained and verified on every read, for store-level actions with no case open |
| GUI recovery | Store-screen card "Device-secret recovery": export (save dialog, new recovery passphrase, examiner passphrase) and restore (file, recovery passphrase checked at once, examiner passphrase). Two Rust prompt-window steps; the first passphrase is held only in the Rust core (zeroised, `Debug` redacted). Sidecar `recovery.export`, `recovery.check`, `recovery.import`. This deviates from the ADR's "no GUI at first", because the installed application ships no command line |
| Workstation check | Says whether a recovery file was exported for the store and whether the store audit chain is intact |
| Installers | The first Windows bundle build, from `main` at `1fbd5b3`: `Ridge_0.2.0_x64_en-US.msi` (82.01 MiB, SHA-256 `d4641e24fe15ea7dfa967dc899cc482a2a46834753e90232919f57cf08dc3f0a`) and `Ridge_0.2.0_x64-setup.exe` (57.37 MiB, SHA-256 `fccff4a6b14f61d42346fca4e8068c0d185a71b98356033aa7950c7fb9defe6f`). Smoke test of the per-user NSIS build: silent install to `%LOCALAPPDATA%\Ridge` (exit 0); the installed engine answered `ridge.version` with commit `1fbd5b3` (build); the app opened its "Ridge" window and started WebView2 and the engine; closing it stopped the engine; silent uninstall (exit 0) removed it. The final installers are rebuilt from `main` after this branch merges |
| Decisions recorded | ADR-012 accepted with its implementation. PRD OQ-8, OQ-9, OQ-10 (interim) and OQ-12 answered. Standards profile owners (interim) and packaging exception updated. Release checklist: installer smoke test, recovery procedure, countersigning, NVDA pass |
| NVDA script | `docs/screen_reader_test.md`: 22 steps over the examiner guide's tasks on a synthetic store, with expected announcements and a record sheet |

Out of scope / not done:

- code signing: needs the laboratory's certificate;
- the NVDA pass itself (product owner);
- Tauri WebDriver E2E;
- macOS and Linux bundles;
- the laboratory procedures for recovery files and countersigning.

## 2. Current repository state

- `main` is at `1fbd5b3`. This branch is ahead of it; see the pull request.
- No new dependencies. Tauri's build tools (WiX, NSIS) live in `%LOCALAPPDATA%\tauri` on this workstation, outside the repository.

## 3. Standards applicability and evidence

Project standards profile updated: owners (interim) and the packaging exception.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Key management (ADR-004, ADR-012), OWASP ASVS V6/V11, CWE-320 | Yes | `tests/test_recovery.py` (17 tests): new-account restore, refusals, tampering, fingerprint mismatch, audit chain, CLI, sidecar; Rust prompt tests; Vitest card tests | GUI added beyond the ADR's "no GUI at first" (recorded in the ADR) |
| ISO/IEC 27037 (records of store-level actions) | Yes | Hash-chained store audit file; tamper tests | None |
| Release (ISO/IEC 12207 configuration, release checklist) | Yes | Installer hashes and smoke test above | Unsigned installers (exception, pending certificate) |
| WCAG 2.2 AA | Yes | `docs/screen_reader_test.md` | Manual pass pending (product owner) |
| Owner roles (profile section 1) | Yes | Interim: product owner holds all five roles | Independent DPO and FQM recommended before casework |

## 4. Forensic impact

- Output pixels changed: no.
- Recorded parameters: unchanged.
- New file formats: `ridge.device-secret-recovery/1` (holds no evidence) and `store-audit.jsonl` (store-level log).
- Data classes: synthetic data only.

## 5. Files changed

- `src/ridge/case/recovery.py`, `store_audit.py`, `cli_recovery.py` (new), `cli.py`, `workstation.py`;
- `src/ridge/sidecar/recovery_methods.py` (new), `handlers.py`;
- `gui/src-tauri/src/commands/recovery.rs` (new), `prompt.rs`, `prompt_calls.rs`, `state.rs`, the allow-lists;
- `gui/src/screens/RecoveryCard.tsx` (new), StoreScreen, IPC types, prompt labels;
- tests;
- `docs/adr/ADR-012-device-secret-recovery.md`, `docs/architecture.md`, `docs/prd.md`, `docs/examiner_guide.md`, `docs/screen_reader_test.md` (new);
- `Instruction_documentation/Project_Standards_Profile.md`, `release_readiness_checklist.md`, README, CHANGELOG.

## 6. Data store, records and formats

- No migration. `store-audit.jsonl` appears in a store after the first recovery export or import; backups copy it.

## 7. Configuration, keys and CI

- No CI change.
- No key material in the repository, argv or environment.

## 8. Security

- The recovery file replaces only the device factor: opening a case still needs the examiner passphrase.
- Open: code signing, ADR-010 review, the laboratory's procedures (recovery custody, countersigning).
- In this session's GUI work, `npx` once fetched unpinned prettier and eslint from the npm registry, because the worktree had no `node_modules`. Nothing was installed into the project. `npm ci` from the lock file was run before any further checks, and the gate uses the locked tools.

## 9. Tests

- Added:
  - Python: `test_recovery.py` (17), plus a workstation recovery finding;
  - Rust: recovery prompt rules and secret redaction;
  - Vitest: recovery card (2).
- Commands: `python tools/gate.py all` on this branch; the result is recorded in the pull request.
- Not run:
  - WebDriver E2E;
  - GUI on Linux and macOS.

## 10. Release readiness

- Internal engineering build; installers build and pass a smoke test.
- Before casework use:
  - code signing;
  - the NVDA pass;
  - method validation (OQ-6, OQ-15);
  - independent DPO and FQM;
  - the laboratory procedures.

## 11. Open risks and known issues

- Interim combined owner roles: the DPO and FQM independence conflict is recorded.
- Unsigned installers trigger Windows SmartScreen warnings.

## 12. Recommended next work

1. Rebuild and smoke-test the installers from `main` after this merge, and record their hashes.
2. Obtain a code-signing certificate and sign the sidecar and the installers.
3. Run the NVDA script and record the results.
4. Write the laboratory procedures for recovery files and countersigned heads.

## 13. First thing the next agent/developer should read or do

Run `python tools/gate.py all`. Read ADR-012, `docs/screen_reader_test.md` and the release checklist.
