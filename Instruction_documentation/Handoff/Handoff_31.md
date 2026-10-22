# Handoff_31.md

Date/time (ISO 8601 with offset): 2026-10-23T01:00+02:00
Author/agent: Claude Code (claude-opus-5-5), autonomous window granted by the product owner on 2026-10-22 ("do everything one by one ... do everything yourself")
Project: Ridge
Branch: `m5-deps-15`, stacked on `m5-missing-engine-13` (PR #26, Handoff_30)
Base commit: `4baf909` (tip of `m5-missing-engine-13`)
Latest commit: see the pull request

## 1. Scope

Requested change: close the dependency advisories that Handoff_29 left open (section 12, item 1) and that the standards profile recorded as an exception on 2026-10-22 ("Close with the Pillow 13.0.0 / Vite 8.3.5 update before the next release").

Completed work:

- `requirements.lock`: Pillow 12.3.0 -> 13.0.0, regenerated with the documented command plus `--upgrade-package pillow` (`uv pip compile pyproject.toml --extra heic --universal --python-version 3.12 --generate-hashes -o requirements.lock`). Only the Pillow pin and its hashes changed. `requirements-dev.lock` and `requirements-build.lock` were recompiled and did not change. `pillow-heif` 1.8.1 requires `pillow>=11.1.0` and is unchanged.
- On 2026-10-22, `pip-audit` reported **35** known vulnerabilities in `pillow 12.3.0`. Handoff_29 had recorded 8 the day before. The fix version is 13.0.0 for all of them.
- `gui/package.json` / `gui/package-lock.json`: Vite 8.3.2 -> 8.3.5 (exact pin, as before). One package changed; `npm audit --audit-level=moderate` went from 1 high-severity entry (`launch-editor`, GHSA-698v-4r3x-3vcv, GHSA-r825-w8mm-5pxw, GHSA-587h-7wmj-h5pm, plus the Vite dev-server advisories GHSA-9jrq-w75r-8gcw, GHSA-rq7h-c2jc-7f22, GHSA-vfpm-58rq-9qcg) to 0.
- `requirements-dev.lock`: certifi 2026.7.22 -> 2026.10.19 and uv 0.13.1 -> 0.13.5, for two advisories the `deps` gate found during this work (PYSEC-2026-4320, PYSEC-2026-4321). Development tools only; nothing shipped changes.
- New `tools/decoder_evidence.py` (220 lines): evidence for decoder upgrades, which forensic standard §13 requires and the stored goldens cannot give (they decode PNG only). `make-inputs` writes 31 synthetic files once; `run` records, in the environment under test, the SHA-256 of each file's decoded BGR pixels (`ridge.image_io.decode_image`), metadata record (`ridge.metadata.read_metadata`), extracted print and the comparison export PNG a job with default settings stores (`ridge.case.export_step.photo_scale`, `make_comparison_export`, `encode_png`: ridge-period scale, dark ridges, mirrored, 500 ppi); `compare` lists every difference and exits 1 if there is one, and 2 if the two manifests come from the same versions of the image libraries (Pillow, pillow-heif, libheif, NumPy, OpenCV, bundled codecs), so a run that compared nothing cannot pass as evidence. Both refinements came from the Codex review of PR #29.
- `tests/test_fuzz.py::test_decoder_warnings_are_logged_not_raised` adapted to a real Pillow 13 behaviour change (section 4).
- Documentation: CHANGELOG, `docs/architecture.md` §9.4 (the evidence tool), `Project_Standards_Profile.md` §8 (exception closed; new revalidation row).

Out of scope: the terminal-output hardening and the refactoring run (their own stacked pull requests, Handoff_32 and Handoff_33).

## 2. Current repository state

Git status summary: committed on `m5-deps-15` (`3ab1af6`, `8fdace7`, then this handoff).

Recent commits: `8fdace7` Upgrade certifi and uv in the development lock; `3ab1af6` Upgrade Pillow to 13.0.0 and Vite to 8.3.5; add decoder evidence for the upgrade; `4baf909` Handoff_30 (PR #26).

## 3. Standards applicability and evidence

Project standards profile updated: yes. The row "`deps` and `gui` gates green before merge" is closed. A new row records the pending revalidation decision for the Pillow 13 decoder change (Forensic Quality Manager, interim: product owner).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Dependency vulnerabilities (`deps` gate, npm audit; release blocker "unaddressed vulnerability rated moderate or higher in a runtime dependency") | Yes | `python tools/gate.py deps`: no known vulnerabilities; `npm audit --audit-level=moderate`: 0 | Closed |
| Forensic standard §13: revalidation after a Pillow version change unless results cannot change | Yes | Decoder evidence (below): 31 of 31 inputs identical; golden characterization (live v0 bit-identical, stored x86-64 goldens exact) passes | Decision pending (profile §8) |
| Hash-pinned locks, `--require-hashes` (coding standard, supply chain) | Yes | Lock regenerated with uv and hashes; installed with `pip install --require-hashes --no-deps -r requirements.lock -r requirements-dev.lock`; `pip check` clean | None |
| Hostile-input tests for decoders | Yes | `tests/test_fuzz.py`, `tests/test_image_io.py`, `tests/test_hardening.py`, `tests/test_metadata_hostile.py` pass on Pillow 13 | None |
| Licences of the new version | Yes | `licenses` gate (section 9) | None |

Decoder evidence (Windows 11 x86-64, Python 3.13.5; Pillow 12.3.0 in a scratch virtualenv built from `main`'s `requirements.lock` with `--require-hashes`, Pillow 13.0.0 in the project virtualenv; the inputs were written once):

```bash
python tools/decoder_evidence.py make-inputs <scratch>/inputs            # wrote 31 synthetic inputs
<pillow-12 venv>/python -I tools/decoder_evidence.py run <scratch>/inputs -o pillow-12.3.0.json
python tools/decoder_evidence.py run <scratch>/inputs -o pillow-13.0.0.json
python tools/decoder_evidence.py compare pillow-12.3.0.json pillow-13.0.0.json
# environment codecs: libjpeg_turbo 3.1.4.1 -> 3.2.0, libtiff 4.7.1 -> 4.7.2 (jpg 8.0, littlecms2 2.19, webp 1.6.0, zlib 1.3.1.zlib-ng unchanged)
# environment pillow: 12.3.0 -> 13.0.0
# 31 of 31 inputs give identical results   (exit 0)
python tools/decoder_evidence.py compare pillow-13.0.0.json pillow-13.0.0.json
# no change in pillow, pillow_heif, libheif, numpy, opencv, codecs: the manifests do not compare two versions   (exit 2)
```

The runs above were repeated after the review fix that hashes the production comparison export: still 31 of 31 identical; 29 inputs produce an export.

The 31 inputs: JPEG at quality 95 with 4:4:4 subsampling, at quality 85 with 4:2:0, progressive, greyscale and CMYK; JPEG with EXIF orientations 1 to 8; PNG RGB, RGBA, greyscale, palette, 16-bit grey and 16-bit RGB; TIFF raw, LZW, Deflate and CMYK PackBits; BMP RGB and palette; WebP lossy and lossless; HEIC (libheif 1.23.6); and three metadata samples from `tests/metadata_samples.py`. All 31 decode. 29 produce a print and an export; the two 48 x 64 metadata samples are refused as too small in both versions (`ImageTooSmallError`). The manifests are in `build/evidence/` on the development workstation (not committed: `build/` is ignored); `make-inputs` and `run` reproduce them.

Exceptions, deviations or evidence gaps:

- The evidence covers synthetic inputs. Real phone photos may use encoder features the synthetic set does not (for example arithmetic-coded JPEG, 12-bit JPEG, unusual TIFF photometrics). The validation study, not this tool, covers real photos.
- Apple silicon: the arm64 pixel tests run on the pull request (`arm64.yml` triggers on `requirements.lock`); the decoder evidence ran on x86-64 only.

Steps outside coding work: the revalidation decision (profile §8 row) for the Forensic Quality Manager.

## 4. Forensic impact

Output pixels changed: no, on every synthetic input tested (section 3), and the golden characterization passes. `tests/golden/` untouched.

Behaviour change on malformed input: Pillow 13 refuses a TIFF whose PhotometricInterpretation tag has too many entries (the byte-62 mutation from the earlier fuzzer finding). Pillow 12.3.0 decoded it with "Metadata Warning, tag 262 had too many entries"; Pillow 13.0.0 raises `UnidentifiedImageError`, which Ridge reports as `InputRejectedError` ("not a supported image"). Ridge now fails closed on that input. The regression test now checks this refusal and still proves that a decoder warning is logged, not raised, using a RowsPerStrip tag with too many entries (byte 98), which both versions decode with a warning.

Defaults or recorded parameters changed: no. Job reports record `ridge.dependencies.pillow`, which reads 13.0.0 for new jobs, as intended.

Revalidation decision required / recorded: required by §13; recorded as pending in the profile with this evidence.

Examiner-facing wording changed: none.

Data classes touched and how class E data stayed out of repository and agent session: synthetic images only, generated in memory or in the session scratchpad (`tests/synthetic.py`, `tests/metadata_samples.py`). No real photo was opened.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `requirements.lock` | Pillow 13.0.0 with hashes |
| `requirements-dev.lock` | certifi 2026.10.19, uv 0.13.5 |
| `gui/package.json`, `gui/package-lock.json` | Vite 8.3.5 |
| `tools/decoder_evidence.py` (new) | Decoder-upgrade evidence (forensic standard §13) |
| `tests/test_decoder_evidence.py` (new) | The export hash equals the export a default job stores; `compare` refuses same-version manifests and reports differences |
| `tests/test_fuzz.py` | Decoder-warning regression adapted to Pillow 13; checks the new refusal |
| `CHANGELOG.md` | Unreleased entries for both upgrades |
| `docs/architecture.md` | §9.4: decoder-upgrade evidence |
| `Instruction_documentation/Project_Standards_Profile.md` | §8: exception closed; revalidation row |
| `Instruction_documentation/Handoff/Handoff_31.md` (new) | This handoff |

## 6. Data store, records and formats

None. No case-store, custody, report or export format change.

## 7. Configuration, keys and CI

No configuration, keys or workflow changes. CI on the pull request: `ci.yml` (Linux gates and the supply-chain job, which runs `pip-audit` and now passes) and `arm64.yml` (pixel tests on Apple silicon, triggered by `requirements.lock`).

## 8. Security

Closes 35 Pillow advisories (the image decoder is the main attack surface for evidence files) and the Vite development-server advisories. No change to limits, the allow-list or the decode path; the one behaviour change refuses more malformed input (section 4).

## 9. Tests

Commands run (Windows 11 x86-64, Python 3.13.5, Node 22):

```bash
python tools/gate.py test        # Pillow 13 before the test fix: 1 failed (test_decoder_warnings_are_logged_not_raised), 866 passed, 3 skipped
python -m pytest tests/test_fuzz.py -q        # after the fix: 5 passed
npm audit --audit-level=moderate              # gui/: found 0 vulnerabilities
python tools/gate.py all                      # on 3ab1af6: see below
```

`python tools/gate.py all` on `3ab1af6`, gate by gate:

| Gate | Result |
| --- | --- |
| docs | passed |
| lint | passed (ruff: all checks passed) |
| format | passed (228 files already formatted) |
| typecheck | passed (mypy: no issues found in 167 source files) |
| test | passed: 867 passed, 3 skipped (POSIX permission bits on Windows) in 556 s; branch coverage above the 90 % threshold; includes the live v0 comparison and the stored x86-64 goldens |
| sast | passed (bandit) |
| deps | **failed** on `requirements-dev.lock`: `certifi 2026.7.22` (PYSEC-2026-4320, fix 2026.10.19) and `uv 0.13.1` (PYSEC-2026-4321, fix 0.13.4); `requirements.lock` (runtime): no known vulnerabilities |

Fixed in `8fdace7` (development lock only: certifi 2026.10.19, uv 0.13.5; recompiled with `--upgrade-package certifi --upgrade-package uv`; `requirements-build.lock` recompiled and unchanged). Then, on `8fdace7`:

```bash
python tools/gate.py deps                              # passed: no known vulnerabilities in either lock
python tools/gate.py secrets licenses sbom gui         # all 4 gate(s) passed
```

`gui` covered: `npm ci`, ESLint, `tsc`, Prettier, Vitest (28 files, 108 tests passed, including PR #26's new test), `vite build`, `npm audit --audit-level=moderate` (0 vulnerabilities), npm licences and SBOM, `cargo fmt --check`, `cargo clippy --all-targets -D warnings`, `cargo test` (36 passed, including the live Rust-to-sidecar test), `cargo audit --deny warnings`, `cargo deny check`, Cargo SBOM. The `test` gate was not repeated on `8fdace7`: it changes only development tools (pytest and the others are unchanged).

Tests not run and why: Tauri WebDriver E2E (profile exception, not implemented); the installed application (no GUI behaviour change beyond the Vite build tool); the full CI matrix (on demand and for releases).

## 10. Release readiness

Release type: internal engineering build. With this change `deps` and the npm audit pass again on this branch, and on `main` once it merges. Remaining release blockers are organisational (profile §8: named owners, DPIA, method validation, code-signing certificate, the revalidation decision above).

Rollback: revert the commit (restores Pillow 12.3.0 and Vite 8.3.2 with their advisories).

## 11. Open risks and known issues

- Revalidation decision for Pillow 13 pending (profile §8).
- The evidence tool compares hashes only. When a future upgrade does change pixels, it shows which inputs differ but not how much; the stored-golden tolerances and `tools/compare_goldens.py` are the tools for that.

## 12. Recommended next work

1. Forensic Quality Manager: record the revalidation decision for Pillow 13.0.0 from this evidence.
2. Use `tools/decoder_evidence.py` for every future Pillow, pillow-heif, NumPy or OpenCV upgrade, and attach the comparison to the handoff.

## 13. First thing the next agent/developer should read or do

Read this handoff and the profile §8 revalidation row; then Handoff_32 (terminal output) and Handoff_33 (refactoring), which are stacked on this branch.
