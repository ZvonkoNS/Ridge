# Forensic Evidence And Biometric Data Standards

Last verified: 2026-10-20
Update when: evidence handling, hashing, custody, reporting, validation, retention, data classes, or the legal assessment change.

This is the canonical rule set for how Ridge treats case material, biometric data and forensic records. Where another file in this pack is less strict, this file wins. Product scope and milestones are defined in `docs/prd.md`; component design in `docs/architecture.md` and `docs/adr/` (both maintained outside this pack).

Status tags used below: **Now** = applies to every change today. **M0-M4** = release blocker from that milestone (milestones defined in `docs/prd.md` section 7, summarised in `Project_Standards_Profile.md` section 2). **Ops gate** = `docs/prd.md` milestone M5 (validation and approval), required before any operational casework use.

## 1. What Ridge is and is not

- Ridge is an image-enhancement aid. It turns photos of fingers into ridge images that a qualified fingerprint examiner can use during Analysis and Comparison (ACE-V) against NAFIS/AFIS results.
- Ridge never identifies a person, never declares a match or non-match, never ranks candidates and never produces a conclusion. Evaluation and Verification are human decisions made outside Ridge.
- Enhancement can remove real detail and can create artefacts (spurious ridge endings, bifurcations or continuity). The current pipeline itself warns that `--min-quality` values below about 0.22 start inventing ridges in blurry areas. Every rule below assumes outputs are processed images, not evidence originals.

### Forbidden claims (Now)

Code, CLI output, GUI text, reports, docs, commit messages and release notes must not:

- Say or imply identification, matching, individualisation, "same source", probability of match, or a quality "pass" that implies suitability for identification.
- Call Ridge, its outputs or its method "validated", "accredited", "certified", "court-approved", "ISO 17025 compliant", "NIST compliant" or similar unless the referenced external process has been completed and the Forensic Quality Manager has approved the wording.
- Present an output image without stating it is a processed image derived from an identified original (by SHA-256).
- Describe NFIQ 2 scores computed on Ridge outputs as standard-conformant quality measurements. ISO/IEC 29794-4:2024 targets contact captures at 500 ppi; scores on photo-derived images are indicative only until the validation study says otherwise.

## 2. Data classes

| Class | Examples | Handling |
| --- | --- | --- |
| E - Evidence and biometric (special category, LED Art. 10) | Original case photos, extracted prints, debug images (contain a crop of the original photo), quality maps, minutiae, exports, volunteer validation images | Never in git, CI, issues, pull requests, screenshots, handoffs, logs, telemetry or AI tools. Encrypted at rest in the case store (M1). Outside the case store only on an OS-encrypted volume (interim control). |
| C - Case-confidential | Case IDs, custody log, job reports, examiner identity, input file names and paths (names can contain personal data), the originals' metadata as text (camera, times, GPS position, serial numbers, owner names: personal data, FR-36) | Stored with the case. Logged only as case-relative IDs and hashes at default log level. |
| I - Internal | Source code, docs, synthetic test data, configuration without secrets | Repository. |
| S - Secrets | Case-store passphrases, data keys, signing private keys, CI tokens | See `environment_configuration_and_secrets.md`. Never logged, never in argv, never in files in the repo. |

Coding agents (including Claude Code) must never be given class E material: no real images, crops, screenshots of outputs or volunteer data in prompts, attachments or tool calls. Debugging uses synthetic data or numeric summaries the examiner has reviewed.

## 3. Evidence immutability (Now)

- Originals are opened read-only. Code must not write, rename, re-encode, re-orient, strip metadata from or touch timestamps of an input file.
- EXIF orientation is applied to the in-memory pixel array only, and the applied transform is recorded in the run record.
- Outputs are never written into the directory that holds the input originals. The CLI must refuse an output directory equal to or inside an input directory (planned in `src/ridge/image_io.py`; the legacy script does not check this).
- From M1, evidence is ingested into the case store by copy, the copy's SHA-256 is verified against the source hash before any processing, and processing reads only the verified copy.
- An original whose hash no longer matches its recorded hash is quarantined: processing stops and the event is written to the custody log.
- Outputs are never overwritten silently. Outside the case store, replacing an existing output requires the explicit `--overwrite` flag (`docs/prd.md` FR-11); the replacement is reported and the run record keeps the replaced file's hash. Inside the case store nothing is overwritten (content-addressed, append-only).
- The no-case mode (`docs/prd.md` FR-27) is for synthetic or consented R&D data only and labels its outputs "not for casework".

## 4. Hashing (Now for new code; legacy script exempt until refactor)

- SHA-256 (FIPS 180-4) of the exact input bytes as read, computed before decoding.
- SHA-256 of the exact output bytes as written, computed by re-reading the file after the atomic rename.
- Pixel-content hash for reproducibility: SHA-256 over a canonical byte string of dtype, shape and C-contiguous array bytes. File hashes can change when an encoder or zlib version changes even if pixels are identical; the pixel hash separates these cases.
- Hashes are lowercase hex, labelled with the algorithm (`sha256:<hex>`).
- MD5 and SHA-1 must not be used for integrity. A future algorithm change requires an ADR and a migration that keeps old hashes verifiable.

## 5. Chain-of-custody log (M1)

Authoritative design: `docs/architecture.md` section 8.4 (planned module `src/ridge/custody/`, JSONL file). Minimum rules:

- One append-only log per case. Entries are never edited or deleted; corrections are new entries that reference the corrected entry.
- Each entry contains at least: strictly increasing sequence number, UTC timestamp (ISO 8601 with `Z`), actor (OS account and workstation or examiner ID), action, target IDs and hashes, job ID, result, and the link to the previous entry. Ridge version, commit and parameters are reachable through the job ID and the signed report.
- The link is SHA-256 over the RFC 8785 (JCS) canonical bytes of the previous entry (field `prev` in the architecture). The first entry links to a per-case genesis value recorded in the case metadata.
- The chain head is signed with Ed25519 at least at the end of each job and on verification. A hash chain alone does not detect truncation of the newest entries; signed job reports therefore record the head hash (and entry count), and the head hash is exported to the case file outside Ridge at each report. Timestamps from an offline clock are weak evidence; lab-side countersigning is an open question (`docs/prd.md` OQ-8) and must not introduce runtime network access.
- Logged actions: case created, evidence ingested, hash verified or failed, processing run started and finished, export, report signed, key events (created, rotated, revoked), legal hold set or released, retention action, deletion, verification run, integrity failure.
- Never logged: pixel data, passphrases, keys, full file paths of originals at default level.
- The verification command (`ridge case verify`, `docs/prd.md` FR-24) recomputes the chain and signatures and fails closed on any gap, reorder or mismatch.

## 6. Reproducibility (Now)

Requirement: the same input bytes, same Ridge version, same parameters and same platform produce bit-identical output pixels and file bytes.

- "Same platform" means same OS family and version, CPU architecture and instruction-set level, Python version and the exact hashed dependency set from `requirements.lock`.
- Every run records a manifest: Ridge version and git commit, lock-file SHA-256, Python version, OS, CPU architecture, numpy/OpenCV/Pillow/pillow-heif/libheif versions, OpenCV build-information hash, thread count, every parameter value including defaults, input hashes, output file and pixel hashes, start/end UTC time.
- The pipeline is single-threaded or uses a fixed, recorded thread count. Nondeterministic parallel reductions, unseeded randomness and wall-clock-dependent behaviour are forbidden in `src/ridge/pipeline/`.
- Results from different CPU architectures (x86-64, arm64) are not interchangeable: reproducibility and method validation are per architecture (`docs/prd.md` NFR-3). Runs on different CPUs of the same architecture are compared with documented tolerances (see `coding_standards.md` numerics section); cross-architecture differences are measured and reported per release, never silently accepted.
- Any change that alters output pixels for the golden set is a method change: it needs an ADR, updated golden arrays with review, and a revalidation decision by the Forensic Quality Manager.

## 7. Signed job reports (M1)

- One JSON report (ECMA-404, RFC 8785 canonical form) per processing job, written to the case store, containing the run manifest, custody log head hash and count, examiner ID, a fixed statement that the output is a processed image and not an identification, and any warnings (finger not found by skin colour, low quality region, parameter overrides).
- Signed with Ed25519 as a detached signature (`docs/architecture.md` section 8.1, `docs/prd.md` FR-23); the public-key ID is recorded with the signature. Reports never contain image data.
- `ridge case verify` also checks each report's signature, key status and referenced hashes.
- The Ridge job report is a technical record supporting the examiner's own report under ISO 21043-5. It is not the forensic report.

## 8. Examiner in the loop (Now)

- The original image is always available next to any output (GUI side by side; CLI by recorded hash and path).
- All parameters that influence the output are visible to the examiner and recorded.
- Ridge must not auto-select, auto-reject or auto-submit material to any external system.
- Examiner sign-off inside Ridge is optional (nice-to-have); if built, it records who reviewed what and when, and it never replaces the laboratory's own ACE-V records.

## 9. Data minimisation (Now)

- Process only what the examiner selects. Output is cropped to the ridge region by default.
- Outputs carry no EXIF, GPS or other metadata from the original. A test must prove this for every output encoder.
- Job reports may record the original's metadata as bounded, display-safe text (FR-36, owner request 2026-10-20). They never hold embedded images: an EXIF thumbnail or other embedded picture is recorded by size and SHA-256 only, and binary blocks such as MakerNotes likewise. Metadata is read from the verified stored copy, never from the source file.
- Ridge never sends metadata anywhere. A map link to a recorded position is shown for the examiner to copy; Ridge does not open it, and the GUI says that opening it discloses the position to the map provider.
- Debug images (`--debug`) contain a crop of the original photo and are class E. They are off by default, written only inside the case or output area, and never part of exports.
- No telemetry, crash reporting, analytics or update checks. Logs are local and minimal.
- No temporary files outside the case store or the chosen output directory; processing is in memory.

## 10. Retention, legal hold and deletion (M1)

- Retention period is set per case by the laboratory's legal basis (to be confirmed by the DPO/legal). Ridge stores the retention date in the case metadata (required at case creation, `docs/prd.md` FR-20).
- Legal hold blocks every deletion path, including retention expiry. Setting and releasing hold are custody events.
- Deletion of a case is crypto-erasure: destroy the wrapped per-case data key, then delete ciphertext. The deletion is recorded in a retained deletion record (case ID, time, actor, hashes, no content).
- Limits that must be documented to examiners, not hidden: on SSDs, flash media, journaling or copy-on-write filesystems, cloud-synced folders and backups, overwriting does not guarantee erasure. Plaintext copies outside the case store (exports, OS thumbnail caches, recycle bin, swap, crash dumps) are outside Ridge's control. Full-disk encryption on the workstation is therefore mandatory.

## 11. Biometrics never in the repository (Now)

- `.gitignore` blocks common image extensions; do not weaken it. New output formats (for example `.npz` exports of real prints, `.json` minutiae, `.wsq`, `.jp2`, `.eft`, `.an2`) must be added to `.gitignore` when introduced.
- Committed binary test data is allowed only under `tests/golden/` and only when generated from synthetic inputs by a script in the repository.
- `python tools/gate.py secrets` (gitleaks) runs in CI; reviewers reject any pull request containing image-like binaries outside `tests/golden/`.
- If real biometric data is ever committed: stop, inform the Security Owner and DPO, treat it as a personal data breach assessment (LED Art. 30/31, to be confirmed by the DPO/legal), purge history, and record the incident.

## 12. Synthetic test data (Now)

- Repository and CI use synthetic data only: generated ridge patterns (oriented sinusoids with controlled period, orientation field, cores/deltas where needed), skin-like and non-skin backgrounds, blur, noise, lighting gradients, and malformed or hostile files.
- Generators are deterministic (fixed seeds) and live in `tests/`. Synthetic data must not be traced from, fitted to or derived from real prints.
- The organisation's consented volunteer set (phone photos plus contact scans) is stored outside the repository on access-controlled, encrypted storage, never in CI, and is used only by the validation procedure.

## 13. Method validation (Ops gate)

Ridge may not be used in casework before a validation report is approved. Requirements derive from ISO/IEC 17025:2017 clause 7.2.2 (validation of methods), 7.6 (measurement uncertainty), 7.11 (control of data and information management, including validation of software) and ISO/IEC 27041 (suitability of investigative methods).

| Element | Minimum content |
| --- | --- |
| Validation plan | Intended use, input conditions in scope, performance requirements and acceptance criteria fixed before testing, approved by the Forensic Quality Manager. |
| Dataset | Consented volunteer set; phone photos and contact-scanner references of the same fingers; documented capture protocol; DPIA covers it. Report the composition (skin tone, age band, finger, device) without identities. |
| Matcher benchmark | Open matcher (SourceAFIS or NIST NBIS mindtct/Bozorth3), genuine and impostor comparisons against contact references, FNMR at a fixed FMR chosen in the plan, with confidence intervals; reporting per ISO/IEC 19795-1. |
| Quality | NFIQ 2 score distributions on Ridge outputs and on references; thresholds set from data, labelled indicative (see section 1). |
| Failure modes | Failure-to-process rate, finger-not-found rate, artefact review by examiners on a sample. |
| Differential performance | Results by skin tone and age band; the Lab a* skin mask may behave differently across skin tones. |
| Reproducibility | Repeat runs and cross-platform runs per section 6. |
| Uncertainty | Confidence intervals for FNMR and quality statistics; stated limits of applicability. |
| Decision | Validation report with results, limits, residual risks; approval by the Forensic Quality Manager. |

Revalidation is required when pipeline numerics, default parameters, decoders, numpy/OpenCV/Pillow/pillow-heif versions or supported platforms change, unless the Forensic Quality Manager documents why the change cannot affect results (evidence: unchanged golden and benchmark results).

## 14. Domain caveats that design must address

- Mirror orientation: a photo shows the finger as seen; contact impressions are mirror images. Matcher-ready exports (planned `src/ridge/export/`) must apply and record the horizontal flip and polarity (dark ridges on light background for most matchers).
- Physical scale: photos have no calibrated resolution. A 500 ppi export from the measured ridge period is an assumption, not a measurement. Use a scale reference in the photo where available, record the method, and cover scale error in validation.
- Image authenticity: Ridge does not assess whether a photo is manipulated or synthetic. Provenance is assessed by the laboratory under ISO/IEC 27037/27042. Ridge records input hashes and leaves metadata untouched. It shows and records the metadata as stored, with a notice that it is not verified and does not by itself establish where, when or with what a photo was taken; it never interprets or scores it.

## 15. Evidence of conformance with this file

| Rule area | Evidence |
| --- | --- |
| Immutability and hashing | Tests: input file bytes and mtime unchanged after a run; output-inside-input refused; hashes in run record match re-read files. |
| Custody log | Tests: chain verifies; tampered, reordered, truncated and re-signed logs fail verification. |
| Reproducibility | Determinism test (same process, separate processes); golden characterization tests. |
| Reports | Signature verification tests, including wrong key and modified field. |
| Minimisation | Tests: outputs carry no metadata (`tests/test_metadata_reports.py` checks a GPS-tagged input); no temp files created outside the target directory; embedded thumbnails recorded by hash only. |
| Repository hygiene | `python tools/gate.py secrets` and review checklist. |
| Validation | Approved validation report referenced in `Project_Standards_Profile.md`. |
