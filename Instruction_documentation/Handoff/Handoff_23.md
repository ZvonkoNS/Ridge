# Handoff_23.md

Date/time (ISO 8601 with offset): 2026-10-18T12:00+02:00 (autonomous development window, closing)
Author/agent: Claude Code (claude-opus-5-5)
Project: Ridge
Branch: `m4-docs-9` → `main`
Base commit: `ea8daaa` (Merge pull request #21, Handoff_22)
Latest commit: see the pull request

## 1. Scope

Requested change: continue autonomous development (product owner, 2026-10-18), sparing GitHub Actions. PR #21 (Handoff_22) was merged at `ea8daaa`. Before the merge, its one Codex finding (an NFIQ 2 tool that cannot run counted only as a note) was fixed in `e90d9cb` (recorded in Handoff_22 §1), answered and resolved, and both CI and the local gate were green.

Completed work on this branch:

| Area | What |
| --- | --- |
| Examiner guide | `docs/examiner_guide.md` covers working a case in the desktop application, task by task: before the first case, first run, cases, evidence, jobs and review, references, exports, records, notes, store tasks, and what Ridge never does. Each statement was checked against the code and the PRD. Linked from the README and the verification guide |
| Custody log | <kbd>/</kbd> moves to the search box (`aria-keyshortcuts="/"`), unless the examiner is typing or a dialog is open; listed in the shortcut list |
| Development preview | The preview answers `case_status`, so Records shows the case summary instead of an error |
| Types | The GUI's file-check type includes the `backup` kind added in #21 |

Out of scope (unchanged):

- installer build and code signing. The first `tauri build` downloads WiX/NSIS; a follow-up session card describes the dry run and asks before downloading;
- Tauri WebDriver E2E;
- manual screen-reader pass;
- ADR-012 (owner decision).

## 2. Current repository state

- `main` is at `ea8daaa`. This branch is ahead of it; see the pull request.
- No new dependencies or tools.

## 3. Standards applicability and evidence

Project standards profile updated: no new exception.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Examiner-facing wording (AGENTS.md: no identification, matching, validation or certification claims) | Yes | The guide states what Ridge never does and that builds are not for casework | None |
| WCAG 2.2 AA (keyboard) | Yes | `/` shortcut exposed with `aria-keyshortcuts` and in the shortcut list; `custody.test.tsx` checks it does not take a key from a text field | Manual screen-reader pass open |

## 4. Forensic impact

- Output pixels changed: no.
- Recorded parameters: unchanged.
- Examiner-facing wording: the new guide.
- Data classes: synthetic data only.

## 5. Files changed

- `docs/examiner_guide.md` (new), `docs/verification_guide.md`, README, CHANGELOG;
- `gui/src/screens/CustodyLog.tsx`, `gui/src/components/ShortcutsHelp.tsx`, `gui/src/dev/preview.ts`, `gui/src/ipc/types.ts`, `gui/src/test/custody.test.tsx`.

## 6. Data store, records and formats

- No changes.

## 7. Configuration, keys and CI

- No changes.

## 8. Security

- No change to trust boundaries.
- Open: ADR-012 (device-secret recovery), ADR-010 review, unsigned installer.

## 9. Tests

- Added: Vitest for the `/` shortcut, including that it leaves text fields alone.
- Evidence also produced in this window, outside the branch:
  - `tools/perf_benchmark.py` on the development workstation: 12 MP synthetic photo 3.1–7.3 s, 48 MP 6.3–6.8 s, peak traced memory about 390 and 700 MiB. That is within the NFR-1 baseline of 2026-10-17;
  - the frozen sidecar built and smoke-tested from `4ef5a20`.
- Commands: `python tools/gate.py all` on this branch; the result is recorded in the pull request.
- Not run:
  - `tauri build` installers;
  - GUI on Linux and macOS;
  - WebDriver E2E.

## 10. Release readiness

- Internal engineering build.
- Not ready for casework (M5).
- Blockers unchanged.

## 11. Open risks and known issues

- Until ADR-012 is decided, losing an examiner's OS keystore loses that examiner's cases.
- The installer has never been built.

## 12. Recommended next work

1. Decide ADR-012, OQ-8, OQ-9 and OQ-10.
2. Run the release dry run (follow-up session card "Release dry run: build and smoke-test the installer").
3. Manual screen-reader pass (NVDA, VoiceOver) of the store and case screens, using `docs/examiner_guide.md` as the script.

## 13. First thing the next agent/developer should read or do

Run `python tools/gate.py all`. Read `CHANGELOG.md`, `docs/examiner_guide.md` and ADR-012.
