# Handoff_16.md

Date/time (ISO 8601 with offset): 2026-10-18T05:20+02:00 (autonomous development window, continued)
Author/agent: Claude Code (claude-opus-5-5)
Project: Ridge
Branch: `m4-gui-2` → `main`
Base commit: `048d4fb` (Merge pull request #14, Handoff_15)
Latest commit: see the pull request

## 1. Scope

Requested change: continue autonomous development (product owner, 2026-10-18), sparing GitHub Actions. PR #14 (Handoff_15) was merged at `048d4fb` after both Codex threads were fixed and resolved and CI was green.

Completed work on this branch:

| Area | What |
| --- | --- |
| Idle lock in the GUI | The GUI mirrors the sidecar's idle clock (15 min) from the engine calls it makes. It warns in the last minute ("Keep the case open") and locks the case itself on time instead of waiting for the next request to fail |
| Engine check and versions | The GUI asks the engine for its version at start. A missing or mismatched sidecar is reported on the store screen before any work; both screens show "Ridge x (GUI y, protocol)" |
| Equal-scale comparison (FR-52) | `preview.get` returns the resolution an image file declares when it is plausible (250–2000 ppi); 72/96 ppi defaults come back as null. The References section shows scale bars from declared or typed resolutions, and "Equal scale" links the zoom of both viewers so a millimetre is equally long on screen. Nothing is aligned or matched |
| Batch jobs | "Run on all N photos" runs the current settings as one job per evidence photo. Region and ruler are left out, because they belong to one photo. Progress and a summary naming refused photos are shown; a locked case stops the batch |
| Custody heads (OQ-8, R-5) | `ridge-case head --to`, sidecar `head.export` and GUI Records: a small signed `ridge.custody-head/1` file for the laboratory to countersign. It carries two signatures: the log's chain signature and one over the whole file. `ridge-case check-head head.json --record record.json` proves a later processing record still contains that head. A log truncated after the head and continued fails, although its chain is internally consistent |
| Sidecar packaging | `requirements-build.lock` (PyInstaller 6.22.3, hash-pinned, never installed by development or PR CI) and `tools/build_sidecar.py`. The script freezes the sidecar (one folder, about 210 MB on Windows), checks the frozen archive for the platform's keystore backend, and smoke-tests it over stdio. `gui/src-tauri/tauri.release.conf.json` bundles it as `resources/sidecar/` |
| Release smoke | A release build with the frozen sidecar beside it answered `app_info` through the release lookup path. **The same test found that release builds honoured `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS`**, which allowed a DevTools port. This was fixed in PR #14 (`60f05c1`) and verified: the port stays closed |
| SBOMs | The GUI gate writes CycloneDX SBOMs of the npm runtime packages (`cyclonedx-npm`) and the Rust core (`cargo-cyclonedx`) to `build/`; `gui.yml` uploads them |
| Accessibility | Forced-colors (Windows high contrast) styles keep borders, focus and selection visible; evidence keeps its colours |
| Hygiene | `.gitattributes` (`eol=lf`): `core.autocrlf` rewrote files to CRLF on branch switches, which failed the Prettier check |

Out of scope:

- the installer build (`tauri build`, which downloads WiX/NSIS);
- code signing;
- Tauri WebDriver E2E;
- manual screen-reader pass.

## 2. Current repository state

- `main` is at `048d4fb` (PR #14 merged). This branch is ahead of it; see the pull request.
- Workstation tool additions:
  - `cargo-cyclonedx` 0.5.9 in `~/.cargo/bin`;
  - PyInstaller 6.22.3 and its hooks in the project virtualenv, from `requirements-build.lock`;
  - npm dev dependency `@cyclonedx/cyclonedx-npm` 6.0.1.

## 3. Standards applicability and evidence

Project standards profile updated: yes. Section 6 records the SBOM sources. Section 8 has the packaging row updated (frozen sidecar built and checked, installer and signing open) and a new row for the PyInstaller bootloader licence.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| `desktop_gui_tauri_standards.md` §2 (sidecar from the bundle only), §8 | Yes | Release build plus frozen sidecar smoke run; `build_sidecar.py` archive and stdio checks | Installer build not exercised |
| §5, §11 (SBOM for npm and Cargo) | Yes | `build/sbom-npm.cdx.json` (CycloneDX 1.6), `build/sbom-cargo.cdx.json` (CycloneDX 1.5) from the gate | None |
| ISO/IEC 27037/27042 and R-5 (custody integrity) | Yes | Custody-head export and check; tests for tampering of every field, the truncate-and-continue forgery and an older record | Lab countersigning process open (OQ-8) |
| WCAG 2.2 AA (FR-53) | Yes | axe checks on the records, references and batch views; forced-colors styles | Manual screen-reader pass open |
| Security (SEC-8, threat model) | Yes | Release-build DevTools finding fixed and verified (PR #14) | None |

## 4. Forensic impact

- Output pixels changed: no.
- Recorded parameters: unchanged.
- New records:
  - custody entries `head.export`;
  - the custody-head file (no images, no personal data);
  - `preview.get` gains `ppi`, which is display only.
- Examiner-facing wording:
  - equal-scale comparison says "View only. Ridge does not align, match or score";
  - scale bars name the source of the scale (resolution in the file / typed by the examiner);
  - custody-head texts describe what is checked, not more.
- Data classes: synthetic data only. The frozen sidecar was smoke-tested on an empty temporary store; no keystore entry was created.

## 5. Files changed

See the pull request. Main areas:

- `gui/src` (idle, versions, references, batch, records, minutiae and limits from PR #14 follow-ups);
- `gui/src-tauri` (`export_head`, release config);
- `src/ridge/case/custody_head.py`, `cli_records.py`, `src/ridge/sidecar/`;
- `tools/build_sidecar.py`, `tools/gate_gui.py`, `requirements-build.*`, `.gitattributes`, `.github/workflows/gui.yml`;
- docs.

## 6. Data store, records and formats

- New file format `ridge.custody-head/1` (architecture §8.4) and custody action `head.export`.
- No migration needed.
- Write paths: `head.export` writes to an examiner-chosen path (P6-like: native dialog in the GUI, `--to` in the CLI, never overwriting without `--overwrite`).

## 7. Configuration, keys and CI

- No new configuration keys.
- `gui.yml` (on demand and `v*` tags only): installs `cargo-cyclonedx` and uploads the SBOM artifact. Still no GUI workflow runs on pull requests.
- `.gitattributes` added.

## 8. Security

- The release-build WebView debugging finding is fixed (see Handoff_15 §8).
- Custody heads give the laboratory an out-of-band anchor against truncation (R-5).
- Open: ADR-010 review; the limits-of-use file is unsigned; the installer is not code-signed.

## 9. Tests

- Added:
  - Python: `tests/test_custody_head.py` (5), a declared-resolution test in `tests/test_sidecar_gui_methods.py`;
  - Vitest: idle (2), references (3), batch (2), records (1), App engine check (1).
- Commands: `python tools/gate.py all` on this branch; the result is recorded in the pull request.
- Not run:
  - `tauri build` installers (it downloads WiX/NSIS);
  - GUI on Linux and macOS (`gui.yml` on demand);
  - WebDriver E2E.

## 10. Release readiness

- Internal engineering build.
- Not ready for casework (M5).
- GUI release blockers: installer build and code signing, WebDriver E2E, screen-reader pass, ADR-010 review, owner names.

## 11. Open risks and known issues

- The frozen sidecar is not bit-reproducible (PyInstaller timestamps); record per-file hashes per release.
- `PYTHON_KEYRING_BACKEND` and the WebView variables are scrubbed. Other OS-level injection vectors (DLL search order for the frozen sidecar) belong to the code-signing and installation review.

## 12. Recommended next work

1. Run `npx tauri build --config src-tauri/tauri.release.conf.json` on a build machine, then sign the installer and the frozen sidecar.
2. Tauri WebDriver E2E on Windows (`msedgedriver` + `tauri-driver`), driving `RIDGE_DEV_STORE` debug builds with synthetic stores.
3. Signed limits-of-use files (FQM key registered out of band).

## 13. First thing the next agent/developer should read or do

Run `python tools/gate.py all`; the GUI gate now also needs `cargo-cyclonedx`. For a release dry run:

```bash
python -m pip install --require-hashes --no-deps -r requirements-build.lock
python tools/build_sidecar.py
```
