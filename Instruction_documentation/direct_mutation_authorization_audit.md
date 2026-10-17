# Write-Path Authorization And Integrity Audit

Last verified: 2026-10-16
The file name is kept for cross-references. For Ridge this audit covers every path that writes evidence, outputs, debug images, directories, the case store, the custody log, reports, keys or exports - from the CLI, the library API, the sidecar RPC and the GUI. Re-run it when a write path is added or changed and before every milestone release.

## Purpose

Ridge must never modify originals, never lose or silently replace an output, and never write class E data where it is not protected. This audit lists each write path, rates it, and decides whether to keep, restrict, move or remove it.

## Standards alignment

- `forensic_evidence_and_biometric_data_standards.md` (immutability, hashing, custody, minimisation).
- OWASP ASVS 5.0.0 V5 (file handling), V8 (authorization), V14 (data protection), V16 (logging).
- OWASP Top 10:2025 A01, A08, A10; CWE-22, CWE-59, CWE-367, CWE-377, CWE-312, CWE-770.
- ISO/IEC 27037 (preservation), LED Art. 25 and 29 (to be confirmed by the DPO/legal).

## Audit inventory - current code (`fingerprint_extract.py`, audited 2026-10-16)

| ID | Write path | Caller | Target | Data class | Operation | Risk | Current protection | Decision | Milestone |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| W1 | `main()`: `outdir.mkdir(parents=True, exist_ok=True)` | CLI | `--outdir` (default `./fingerprints`, relative to the working directory) | I (directory) | create directories | Medium | None. Runs before inputs are validated (directory is created even when no images are found); follows symlinks; no check against input directories; default permissions. | Restrict: create only after inputs validate; refuse inside or equal to an input directory; refuse symlinks; restrictive permissions. | M0 |
| W2 | `main()`: `save_image(outdir / f"{stem}_fingerprint.png", result)` | CLI | Output PNG | E | create or overwrite | High | None. Silent overwrite; inputs with the same stem (`a.jpg`, `a.png`) overwrite each other; non-atomic `tofile` can leave partial files; encoder chosen from the path suffix; unencrypted; no hash; no record of parameters. | Move to `src/ridge/image_io.py` atomic no-overwrite writer with collision detection, output hash and run record (M0); into the case store with custody entry (M1). | M0, M1 |
| W3 | `extract_fingerprint(debug=...)`: `save_image` for `_debug_region.jpg`, `_debug_normalized.png`, `_debug_gabor.png`, `_debug_quality.png` | Library (via CLI `--debug`) | Debug images in the output directory | E (`_debug_region.jpg` is a crop of the original photo with an outline, stored as lossy JPEG) | create or overwrite | High | Off by default. Otherwise as W2, and the I/O happens inside the pipeline function. | Move: pipeline returns intermediates; `src/ridge/debug.py` writes them through `image_io` rules; mark as class E; never in exports. | M0 |
| R1 | `load_image()`: `Image.open(path)` without `formats=`; on any exception falls back to `cv2.imdecode(np.fromfile(path))` | Library | Original (read) | E | read | High (read path, listed because it decides what reaches native decoders) | None: no byte or pixel limit, any Pillow plugin reachable, errors swallowed, second decoder tried. Originals are not written. | Replace with bounded, allow-listed, single-decoder read from hashed bytes. | M0 |
| R2 | `collect_inputs()`: directory scan skips names ending in `_fingerprint` or containing `_debug_` | CLI | Input selection | C | silently skip | Medium | None: an original whose name matches is silently not processed, so evidence can be left out without notice. | Restrict: report every skipped file; prefer separating outputs from inputs (W1 rule) over name-based skipping. | M0 |

Status after M0 (2026-10-16): W2 and W3 now go through `src/ridge/image_io.py` (`publish`: atomic, no-clobber); R1 is replaced by `load_image` (bounded, allow-listed); see the findings below for what remains open.

Library API note: apart from W3, the pipeline functions are pure array transformations. After the refactor, `src/ridge/pipeline/` must contain no file I/O at all.

## Audit inventory - case-store paths (P1-P8 implemented 2026-10-17 in `src/ridge/case/`, Handoff_3)

| ID | Write path | Caller | Target | Data class | Risk | Required protection | Milestone |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | Case create, metadata and key file write | CLI, sidecar | Case directory, metadata, key file | C, S (wrapped keys) | Critical | Atomic write, restrictive permissions, custody genesis | M1 |
| P2 | Evidence ingest (copy into store) | CLI, sidecar | Encrypted blob | E | Critical | Source opened read-only, hash before and after, AEAD, custody entry | M1 |
| P3 | Processing outputs and debug images | CLI, sidecar | Encrypted blobs | E | High | AEAD, output and pixel hashes, run manifest, custody entry | M1 |
| P4 | Custody log append | Core only | Custody log | C | Critical | Append-only, hash chain, signatures, same transaction as the action | M1 |
| P5 | Job report write and sign | Core only | Report | C | Critical | Canonical JSON, Ed25519, custody entry | M1 |
| P6 | Export outside the store | CLI, sidecar (GUI request) | Examiner-chosen location | E | Critical | Explicit action, destination checks, labels, hashes, custody entry | M1/M2 |
| P7 | Legal hold, retention, crypto-erasure | CLI, sidecar | Header, keys, blobs | C, S | Critical | State checks, hold enforcement, retained deletion record | M1 |
| P8 | Key creation, rotation, OS keystore entries | Core only | OS keystore, key file | S | Critical | No plaintext keys on disk, custody key events | M1 |
| P9 | Configuration file write (GUI settings) | GUI via sidecar | User config directory | I | Medium | Schema validation; limits can only be tightened below hard caps | M4 |
| P10 | Logs (stderr, optional log file) | All | Terminal or log file | I/C | Low-Medium | No class E, no secrets, control characters neutralised | M0 |

## Risk classification

- Critical: can modify or destroy originals, custody records, reports, keys or whole cases; can move class E data outside protection; can create records that look authentic but are not.
- High: writes class E data; can overwrite or lose outputs; runs native decoders on untrusted input; mixes I/O into the pipeline.
- Medium: creates directories or configuration; can silently skip inputs; can expose case-confidential names.
- Low: writes non-sensitive diagnostic information with no effect on evidence.

## Required checks per write path

- Who can trigger it (CLI user, library caller, sidecar method, GUI command), and in which case state?
- Can the caller choose the target path? Is it resolved, contained, symlink-checked and kept out of input directories?
- Can it overwrite? Is publication atomic? What remains after a crash?
- Which data class is written, and is it encrypted or explicitly an export?
- Are hashes computed from the exact bytes written, and is the run record or custody entry written with it?
- Are limits enforced (size, count, disk space) before writing?
- Is the operation idempotent or protected against duplicates?
- Does it leave temporary files, journal residue or metadata copies?

## Decision rules

- Keep only when the path cannot touch originals, cannot overwrite, writes only where intended, and is covered by tests.
- Restrict when the path is needed but lacks containment, overwrite protection, limits or records.
- Move behind the core API (case store, sidecar) when it writes class E data, keys, custody or reports, or needs a transaction.
- Remove when there is no product need or it cannot be made safe.

## Test requirements

For each kept, restricted or moved path:

- Allowed write succeeds and produces the expected hash and record.
- Existing target is never overwritten; colliding names are handled as specified.
- Output directory inside an input directory, symlinked target, path with `..`, reserved Windows names and control characters are refused.
- Crash simulation leaves no partial published file.
- Originals unchanged (bytes and modification time).
- From M1: custody entry present for success and absent for rejected requests; tampering detected.

## Audit findings (current code)

```text
Finding: F-1 Silent overwrite and stem collisions (W2, W3)
Risk level: High
Applicable standards: forensic rules sections 3-4; ASVS V5; CWE-367
Required change: atomic no-overwrite writer, collision detection, output hashes
Tests required: overwrite refusal, collision, crash simulation
Owner: Quality/Release Owner (TBD)
Status: partly closed 2026-10-16 (Handoff_1): atomic no-clobber publish, `--overwrite` explicit, crash simulation and collision (second same-stem input fails loudly) tested in tests/test_image_io.py and tests/test_hardening.py. Open: output hashes (M1).

Finding: F-2 Unbounded, non-allow-listed decoding with swallowed errors (R1)
Risk level: High
Applicable standards: ASVS V5; Top 10 A10; CWE-400, CWE-409, CWE-434, CWE-770, CWE-390
Required change: formats allow-list, byte/pixel/frame limits, single decoder, typed errors
Tests required: hostile-input suite, fuzzing
Owner: Security Owner (TBD)
Status: closed 2026-10-16 (Handoff_1): Pillow `formats=` allow-list, byte/pixel/min-side limits with hard caps, single decoder, typed errors, hostile-input suite in tests/test_image_io.py. Open: property-based fuzzing (hypothesis/atheris), planned with M1.

Finding: F-3 Pipeline performs file I/O for debug images (W3)
Risk level: High
Applicable standards: architecture rules; forensic minimisation
Required change: return intermediates; write via debug.py and image_io
Owner: Quality/Release Owner (TBD)
Status: closed 2026-10-16 (Handoff_1): `ridge.pipeline` performs no I/O; `ExtractionResult.debug` is written by `src/ridge/debug.py` through `image_io.save_image`.

Finding: F-4 Unencrypted class E outputs, no hashes, no custody (W2, W3)
Risk level: High
Applicable standards: forensic rules sections 2, 4, 5; LED Art. 29 (to be confirmed)
Required change: case store, custody log, signed reports
Compensating control: OS full-disk encryption; manual hash recording
Owner: Security Owner (TBD)
Status: closed for casework 2026-10-17 (M1): `ridge-case` encrypts, hashes and logs everything; the plain `ridge` command remains labelled R&D mode (FR-27)

Finding: F-5 Silent skipping of inputs by name pattern (R2), early directory creation (W1)
Risk level: Medium
Required change: report skipped inputs; validate before creating directories
Owner: Quality/Release Owner (TBD)
Status: partly closed 2026-10-16 (Handoff_1): every skipped file (own-output names, symlinks, non-regular files) is reported on stderr; output folder created owner-only on POSIX. Open: the output folder is still created before inputs are validated (v0 order), and an output folder inside or equal to an input folder is not yet refused (W1).
```

## Completion criteria

- Every write path (current and implemented planned paths) is in the inventory.
- High and critical paths are restricted or moved, or accepted as exceptions in `Project_Standards_Profile.md` with compensating controls and expiry.
- Tests exist for each path.
- The release checklist and handoff reference this audit's current state.
