# Handoff_34.md

Date/time (ISO 8601 with offset): 2026-10-23T02:20+02:00
Author/agent: Claude Code (claude-opus-5-5), end of the autonomous window granted by the product owner on 2026-10-22 ("do everything one by one. Make it fully production ready. Also do a refactoring run based on the instructions provided in the instructions folder ... do everything yourself")
Project: Ridge
Branch: `m5-release-check-18`, stacked on `m5-refactor-17` (PR #31, Handoff_33)
Base commit: `a0c6525` (tip of `m5-refactor-17`)
Latest commit: see the pull request

## 1. Scope

Requested change: work through the follow-ups listed on 2026-10-22 one by one, run a refactoring pass against the instruction pack, and bring Ridge to "fully production ready".

What "production ready" can mean here. Ridge has two release types (`release_readiness_checklist.md`):

- An **internal engineering build** (not for casework) needs the automated gates, the GUI gate and a few manual checks. This window brought the code to that state (section 10).
- An **operational release** (the Ops gate, PRD M5) also needs a method-validation report, a DPIA, an AI Act assessment, independent owners and a release signed with the laboratory's certificate. None of these can be produced by code. Section 10 lists each one with its owner.

Completed in this window. Each item has its own pull request; they are stacked and none is merged yet (section 2):

| Item | Pull request | Handoff |
| --- | --- | --- |
| The GUI reports a missing processing engine as a broken installation (open since 2026-10-19; Codex thread already resolved) | [ZvonkoNS/Ridge#26](https://github.com/ZvonkoNS/Ridge/pull/26) | Handoff_30 |
| Pillow 13.0.0 (35 advisories against 12.3.0), Vite 8.3.5, certifi and uv in the dev lock; `tools/decoder_evidence.py` (Pillow 12.3.0 vs 13.0.0: 31 of 31 synthetic inputs identical); one malformed TIFF is now refused (fails closed) | [ZvonkoNS/Ridge#29](https://github.com/ZvonkoNS/Ridge/pull/29) | Handoff_31 |
| Every CLI line filtered for control, bidirectional and zero-width characters and line breaks (CWE-150, CVE-2021-42574); shared photo-metadata read; architecture §9.1 corrected and the bomb-warning deviation recorded; stray doc line removed | [ZvonkoNS/Ridge#30](https://github.com/ZvonkoNS/Ridge/pull/30) | Handoff_32 |
| Refactoring run, structure only (pipeline, case jobs, CLI entrypoint, report HTML, Rust sidecar and prompt dispatch, image viewer); goldens identical | [ZvonkoNS/Ridge#31](https://github.com/ZvonkoNS/Ridge/pull/31) | Handoff_33 |
| The frozen-sidecar build now checks that every allow-listed decoder is bundled; release build repeated with the upgraded dependencies; this release-readiness review | this pull request | Handoff_34 |
| Housekeeping: 31 local branches already merged into `main` deleted; 2 stale, clean worktrees removed (`m2-export`, `claude/nostalgic-babbage-40e1ce`) | — | — |

Codex review findings in this window, all fixed, answered with the commit and test, and resolved: two on PR #29 (the evidence tool hashed a relabelled print instead of the stored comparison export; `compare` could pass with two manifests from one environment) and one P1 on PR #30 (a line break in a POSIX file name could forge an output line).

Out of scope: anything needing a person or an organisational decision (section 10); merging (section 2).

## 2. Current repository state

Git status summary: committed on `m5-release-check-18`. `main` is unchanged at `36e264a`.

Not merged, and why: `gh pr merge` was refused by the Claude Code auto-mode permission classifier ("Merge Without Review"), so no pull request was merged and nothing was pushed to `main`. Every pull request in the stack has green CI and resolved review threads (PR #31's Codex review had not arrived when this was written). The owner merges them, with merge commits, in this order:

```bash
gh pr merge 26 --merge
gh pr edit 29 --base main
gh pr merge 29 --merge
gh pr edit 30 --base main
gh pr merge 30 --merge
gh pr edit 31 --base main
gh pr merge 31 --merge
gh pr edit 32 --base main      # this pull request
gh pr merge 32 --merge
```

Merged branches that are still on GitHub: deleting them (`git push origin --delete …`) was also refused by the classifier. They are listed by `git branch -r --merged origin/main`.

CI on the stack (head commits as pushed):

| Pull request | Head | `ci.yml` gates (Linux, py3.12) | Supply chain (pip-audit, SBOM, gitleaks) | `arm64.yml` pixel tests | `gui.yml` |
| --- | --- | --- | --- | --- | --- |
| #26 | `4baf909` | not triggered (GUI-only) | not triggered | not triggered | covered by the run on #31 |
| #29 | `46f513c` | pass | pass | pass | covered by the run on #31 |
| #30 | `efb833e` | pass | pass | not triggered (no pixel code) | covered by the run on #31 |
| #31 | `a0c6525` | pass | pass | pass | run 39874181992 on `m5-refactor-17`: success |

## 3. Standards applicability and evidence

Project standards profile updated: yes (`Last verified` 2026-10-23; the rows added by Handoff_31 and Handoff_32).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Release packaging (architecture §10, release checklist "From M4") | Yes | `python tools/build_sidecar.py` on `5097d54` (clean tree): archive check passes (913 modules, keystore backend, 7 decoder modules), stdio smoke test passes; native decoders present in the bundle (`PIL/_imaging`, `PIL/_webp`, `_pillow_heif`, libheif); `npx tauri build --config src-tauri/tauri.release.conf.json` (section 9) | Code signing: profile §8 |
| Dependency audit | Yes | Handoff_31: pip-audit (both locks), npm audit, cargo audit and deny clean | None |

## 4. Forensic impact

Output pixels changed: no (Handoff_31 to Handoff_33). This pull request changes a build tool and documentation only.

Revalidation decision: the Pillow 13 decoder upgrade still needs the §13 decision (profile §8 row, evidence in Handoff_31).

Data classes touched: none; synthetic data only throughout the window.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `tools/build_sidecar.py` | `check_bundle` also requires the decoder modules |
| `docs/architecture.md` | §10 item 2 describes the new check |
| `Instruction_documentation/Project_Standards_Profile.md` | `Last verified` 2026-10-23 |
| `Instruction_documentation/Handoff/Handoff_34.md` (new) | This handoff |

## 6. Data store, records and formats

None.

## 7. Configuration, keys and CI

None. One on-demand `gui.yml` run was used for the whole stack (minimal Actions use); the full matrix was not run (section 10).

## 8. Security

The new bundle check prevents shipping a frozen build that silently cannot decode an allow-listed format. No other change.

## 9. Tests

```bash
python -m ruff check tools/build_sidecar.py; python -m ruff format --check tools/build_sidecar.py; python -m mypy tools/build_sidecar.py   # clean
python -m pip install --require-hashes --no-deps -r requirements-build.lock
python tools/build_sidecar.py
# frozen archive ok: 913 modules, keystore backend keyring.backends.Windows, 7 decoders
# frozen sidecar ok: Ridge 0.2.0 5097d542f66d5665aa18bd87e4bfffd73cf37550, protocol ridge.sidecar/1   (_build.json: dirty false)
cd gui && npx tauri build --config src-tauri/tauri.release.conf.json
# Finished 2 bundles: Ridge_0.2.0_x64_en-US.msi (82.09 MiB, WiX), Ridge_0.2.0_x64-setup.exe (57.48 MiB, per-user NSIS)
python tools/gate.py docs lint format typecheck
# === all 4 gate(s) passed: docs, lint, format, typecheck   (the code gates ran on the branches below: Handoff_31 to Handoff_33)
```

SHA-256 of the build outputs (engineering build, unsigned, not for casework; kept in the ignored `build/` and `gui/src-tauri/target/` folders, not published):

| File | SHA-256 |
| --- | --- |
| `gui/src-tauri/target/release/bundle/msi/Ridge_0.2.0_x64_en-US.msi` (86078368 bytes) | `5e7cb743b142d5a336217283e77a804bbc9100e339a9b89347f3acc8b0145d45` |
| `gui/src-tauri/target/release/bundle/nsis/Ridge_0.2.0_x64-setup.exe` (60269719 bytes) | `52e629ffc3ae580800ce26ef56843b7a3d4dbf4aa194da529c059a4ce7f067ac` |
| `gui/src-tauri/target/release/ridge-gui.exe` | `9e4d559e901c6581ae50c375fb98b90a931348ba81300415c1cd7ca5f3ec1092` |
| `build/sidecar/ridge-sidecar/ridge-sidecar.exe` (frozen from `5097d54`, clean tree) | `99c296de98059f7e8128bcdec3b74937b395963eec73b30bd54dba0a2fb47444` |

The version is still 0.2.0: no release was cut and nothing was tagged. PyInstaller and the bundlers are not bit-reproducible (architecture §10), so a rebuild gives other hashes.

Not run and why: installing and uninstalling the installers on this workstation (Handoff_26 did this for 0.2.0; it changes the user's system and was not repeated unattended); the full CI matrix; Tauri WebDriver E2E (profile exception).

## 10. Release readiness review

Checked against `Instruction_documentation/release_readiness_checklist.md` for the stack top (this branch), which is what `main` will be after the merges. "Done" means verified in this window or by the handoff named; "Open" items cannot be closed by engineering work alone.

Verdict:

- **Internal engineering build: ready** once the stack is merged, the full CI matrix and `gui.yml` pass on the tagged commit, and the installers are smoke-tested. Every automated gate passes, no known vulnerability is open, docs match behaviour, and the packaging path works with the upgraded dependencies. It stays labelled "not for casework", and the Pillow 13 revalidation decision should be recorded first.
- **Operational release (casework): not ready.** Blocked by the organisational items in the second table. No engineering change can close them.

### Engineering release (internal engineering build, "not for casework")

| Checklist item | Status | Evidence / owner |
| --- | --- | --- |
| `python tools/gate.py all` on the release commit | Done for the stack top | Handoff_33 section 9; rerun on the tagged commit |
| `python tools/gate.py gui` (npm and cargo checks) | Done | Handoff_31, Handoff_33; `gui.yml` run 39874181992 (success) |
| Dependency audit clean (runtime, development, npm, Cargo) | Done | pip-audit on both locks, npm audit 0, cargo audit/deny clean (Handoff_31) |
| Full CI matrix (Windows, Linux, macOS x Python 3.12 to 3.14) on the release commit | Open | Runs on demand or for a `v*` tag (`ci.yml`, full = true); not run in this window to keep Actions use minimal |
| CodeQL, dependency review | Not available | Private repository without code scanning (profile §8); bandit and ruff S run in the gates |
| Golden characterization and determinism on every supported platform | Partly | x86-64 locally (exact), Apple silicon pixel tests on PR #29 and PR #31, Linux 3.12 in CI; Windows/macOS full matrix with the release tag |
| Pixel-changing changes have an ADR and a revalidation decision | Open (one item) | No pixel change in this window. The Pillow 13 decoder upgrade still needs the §13 revalidation decision (profile §8 row; evidence in Handoff_31). Forensic Quality Manager (interim: product owner) |
| Owners named | Done on an interim basis | Profile §1: the product owner holds all five roles (OQ-10) |
| Reproducibility evidence (reference run manifest, lock hash, versions) | With the release | Job reports record versions and platform; produce the manifest when tagging |
| Custody and report verification tests pass | Done | `test` gate |
| Docs match behaviour; handoffs consecutive; profile current | Done | §9.1 corrected (Handoff_32); `docs` gate; profile updated |
| Signed artifacts, `SHA256SUMS`, SBOMs | Open | Unsigned installers built and hashed (section 9); SBOMs generated by the gates; code signing needs the laboratory's certificate (profile §8) |
| Tauri WebDriver E2E | Open (recorded exception) | Profile §8; Vitest flows with mocked IPC and the live Rust-to-sidecar test instead |
| Manual NVDA pass | Open | `docs/screen_reader_test.md`; a person with a screen reader |
| Clean offline install and offline check | Open | Smoke-tested for 0.2.0 on 2026-10-18 (Handoff_26); repeat for the next build |

### Operational release (casework, Ops gate M5)

Not ready. Each item needs a decision or document from outside engineering:

| Item | Owner | Reference |
| --- | --- | --- |
| Method validation report (ISO/IEC 17025 7.2.2) on the consented volunteer set, per CPU architecture | Forensic Quality Manager | forensic standard §13; PRD §12, OQ-6, OQ-15 |
| DPIA (LED Art. 27) | DPO | OQ-2 |
| Legal basis confirmation | DPO / legal | OQ-1 |
| AI Act applicability assessment (NFIQ 2 is a trained model) | Legal | OQ-3 |
| Independent DPO and Forensic Quality Manager | Organisation | profile §1 |
| Photo metadata in reports (GPS, serial numbers, owner names) | DPO | OQ-16 |
| Licence confirmations: pillow-heif bundled LGPL/GPL codecs, PSF-2.0, MPL-2.0 crates, PyInstaller bootloader | Legal | OQ-14, profile §8 |
| Code-signing certificate for the sidecar and installers | Quality/Release Owner | profile §8 |
| AFIS exchange format | Product owner / vendor | OQ-4 |
| Device-secret recovery procedure rehearsed; custody-head countersigning in place | Laboratory | ADR-012, OQ-8 |

## 11. Open risks and known issues

- The stack is unmerged (section 2).
- Revalidation decision for Pillow 13 pending (profile §8).
- PR #31's Codex review had not arrived when this was written; if it reports findings, they need the usual fix, reply and resolve before merging.

## 12. Recommended next work

1. Owner: merge the stack in the order of section 2.
2. Forensic Quality Manager: record the Pillow 13 revalidation decision.
3. Before tagging the next internal build: run the full matrix once (`gh workflow run ci.yml --ref main -f full=true`) and `gui.yml` on the tag, then build, hash and smoke-test the installers (architecture §10).
4. Organisation: the operational-release items in section 10.

## 13. First thing the next agent/developer should read or do

Read Handoff_30 to Handoff_34 in order, then check whether the stack has been merged (`gh pr list`).
