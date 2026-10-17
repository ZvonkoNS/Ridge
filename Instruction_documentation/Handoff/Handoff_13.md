# Handoff_13.md

Date/time (ISO 8601 with offset): 2026-10-17T12:18+02:00
Author/agent: Claude Code (claude-opus-5-5), end of the autonomous development window (2026-10-17, about 08:35–12:35+02:00)
Project: Ridge
Branch: `handoff-13` → `main`
Base commit: `afa38d6` (Merge pull request #11)
Latest commit: this handoff

## 1. Scope

Requested change: the closing status of the autonomous window. **This replaces the state described in Handoff_12 §3–§5.** That handoff was written while GitHub Actions was blocked and nothing had been merged.

Completed work:

- GitHub Actions started running again at about 11:59+02:00; the billing or spending-limit block was lifted.
- The blocked CI runs were re-run on every branch of the stack.
- One arm64-only test bug was found and fixed. `test_a_changed_result_is_a_logged_mismatch` simulated "another platform" with the machine name `arm64`, which is the real machine on macOS arm64 runners. It now uses a name no runner has (`2c8d194`).
- All seven stacked PRs merged into `main` in order with merge commits, each with a green CI matrix (3 OS × Python 3.12–3.14, 13 checks) and no open review thread:

| PR | Content | Merge commit |
| --- | --- | --- |
| #5 | M3 minutiae (unvalidated, opt-in) | `6f6cc58` |
| #6 | M4 GUI sidecar, idle lock, identity and case creation | `94462fb` |
| #7 | `ridge-validate` metrics, NFR-1 baseline | `fa5b2ca` |
| #8 | FR-28 verified reports, PRIV-3 signed processing record, logged-or-nothing exports | `33045dd` |
| #9 | FR-52 reference images and comparison sheets, FR-34/NFR-3 `reproduce` | `8f03d58` |
| #10 | `cases` / `store.cases`, `extract --keep-going` | `f3f6fd0` |
| #11 | proposed FR-35 ROI, FR-21 source notes, CLI split | `afa38d6` |

Out of scope: no code change in this handoff.

## 2. Current repository state

- Git status summary: `main` at `afa38d6` plus this handoff.
- The local checkout in the project folder is still on the older `hardening-followups` branch. Switch it to `main` and pull before the next task.
- Temporary worktrees in the session scratchpad can be removed (`git worktree prune` after deleting them).

## 3. Standards applicability and evidence

Project standards profile updated: not needed (no new exception).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Testing and quality gates (pack) | Yes | Local `python tools/gate.py`: all 10 gates on every branch, 522 tests at the top of the stack. CI matrix green for every merged PR | None |
| NFR-3 per-architecture reproducibility | Yes | macOS arm64 CI is green after the test fix; the bug was in the test, not the pipeline | None |
| Codex review process | Yes | Every review thread on #5–#11 was fixed or answered, then resolved | None |

## 4. Forensic impact

None beyond what Handoff_8 to Handoff_12 describe. The test fix changes no product behaviour.

## 5. Open items (unchanged from Handoff_12 except CI)

- **FR-35** (ROI) is marked "proposed" in the PRD; product-owner confirmation is needed.
- **GUI (FR-50 to FR-53):** every flow has a sidecar method. The Tauri shell needs an owner decision on the native passphrase prompt per OS.
- OQ-4 (exchange format, FR-41), OQ-10 (owner names), OQ-11 (reference workstation for NFR-1) and OQ-15 (casework architectures) remain open.

## 6. First thing to do

Pull `main`, run `python tools/gate.py all`, then decide FR-35 and the GUI passphrase prompt.
