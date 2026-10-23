# Changelog

Ridge is an image-enhancement aid for fingerprint examiners. Every build listed here is an **internal engineering build, not for casework** (`docs/prd.md` milestone M5). Release notes for a release add the commit, the platforms tested and the exceptions (`Instruction_documentation/release_readiness_checklist.md`).

## Unreleased (after the 0.2.0 installers of 2026-10-18)

Forensic impact: **output pixels unchanged.** No default or recorded parameter changed. Job reports gain `measurements.print_area` and `input.metadata`; older reports verify and render as before. The Pillow 13 decoder upgrade below gives identical results on every synthetic input tested; its revalidation decision is pending with the Forensic Quality Manager.

- Pillow 13.0.0 (was 12.3.0) closes the 35 known vulnerabilities `pip-audit` reports against 12.3.0. Pillow decodes every photo, so this is a method-relevant dependency change (forensic standard §13). The new `tools/decoder_evidence.py` compares both versions on 31 synthetic inputs covering every allow-listed format (JPEG baseline, progressive, greyscale and CMYK, EXIF orientations 1 to 8; PNG 8- and 16-bit, palette and alpha; TIFF raw, LZW, Deflate and CMYK; BMP; WebP lossy and lossless; HEIC; metadata samples). Decoded pixels, metadata records, prints and 500 ppi exports are identical, and the golden characterization passes. One malformed-input change: a TIFF whose PhotometricInterpretation tag has too many entries, which Pillow 12 decoded with a warning, is now refused as not a supported image. Bundled codecs: libjpeg-turbo 3.2.0 (was 3.1.4.1), libtiff 4.7.2 (was 4.7.1).
- Vite 8.3.5 (was 8.3.2) closes a high-severity advisory through `launch-editor` and further development-server advisories (`npm audit`: 0). Vite builds and serves the GUI during development only.
- Terminal output (CWE-150, CVE-2021-42574): every line `ridge-case`, `ridge` and `ridge-validate` print, errors included, now shows control, bidirectional and zero-width characters as `<U+XXXX>` (`ridge.terminal`). Before, `ridge-case list` showed bidirectional marks in stored file names and source notes as they were, `ridge-case import` and `import-reference` printed the input path unfiltered, and the R&D `ridge` command printed file names unfiltered, so a crafted name could reorder what the examiner reads or, on Linux and macOS, send escape sequences to the terminal. Line breaks and tabs of multi-line output are kept; a carriage return is shown.
- The GUI start screen asks for a reinstall, not a restart, when the processing engine is missing from the installation (PR #26).
- Release build: `tools/build_sidecar.py` refuses a frozen sidecar that lacks the Pillow plugin of an allow-listed format, `pillow_heif`, `defusedxml.ElementTree`, or the native decoder libraries (Pillow core and WebP, pillow-heif, libheif), or whose engine does not report that it reads HEIF/HEIC; a missing part would otherwise refuse that format only at run time.
- Photo metadata (FR-36): every metadata block Ridge can read from an imported evidence or reference photo is shown under the photos (EXIF with GPS and the thumbnail IFD, XMP with edit histories, IPTC, ICC, PNG text, JPEG segments and MPF, HEIF items), with a summary and a search. A recorded GPS position is shown in decimal degrees with a Google Maps link to copy; Ridge never opens it. Every job report records the metadata (`input.metadata`, schema `ridge.photo-metadata/1`), and the text and HTML reports append every entry. Values are shown as recorded, made display-safe and bounded; embedded thumbnails and MakerNotes are recorded by size and SHA-256 only. Output images still carry no metadata. New sidecar method `metadata.get` and Tauri command `photo_metadata`.
- `ridge-case metadata CASE SHA [--json]` prints one stored evidence or reference image's metadata without running a job. Text output lists every entry with the map link and the note that opening it sends the position to Google; `--json` prints the `ridge.photo-metadata/1` record as ASCII-only JSON, the same record a job report on the photo holds. The read is logged, as the GUI panel's is; outputs and minutiae are refused before anything is read.
- New runtime dependency: `defusedxml` 0.7.1 (PSF-2.0) for XMP without DTDs, entities or external references. The licence gate's allow-list gains PSF-2.0.
- The original photo in the review shows where the print was extracted: a solid outline around the area kept as the print, the print image's frame dashed, the rest dimmed on screen. It can be hidden. The area is recorded in the signed job report (`measurements.print_area`, photo pixels after EXIF orientation), and the job summary and readable reports state it as a "Print area" line.

## Unreleased (0.2.0 line, 2026-10-18)

Forensic impact: **output pixels unchanged.** No default or recorded parameter changed. Reports gained fields (below), and the custody log gained actions. Older reports and logs verify and render as before.

### Records and verification

- Store-wide verification with one passphrase (`ridge-case verify-store`, GUI "Verify all cases"). A case open elsewhere makes the check fail, because it is then incomplete.
- Store overview of references, retention dates and legal holds (`ridge-case overview [--due] [--json]`, GUI "Show case details"). A case summary is available as `ridge-case status [--json]` and in GUI Records.
- Examiner notes on a case, a job or an evidence photo (custody action `examiner.note`). Notes are append-only; corrections keep the original and its scope.
- Disclosure packages (`ridge-case package`, `check-package`): the signed processing record, every signed report, readable copies and a signed manifest, with no images.
- Readable HTML copies of reports and processing records (`report --html`; `check-report --html` and `check-log --html` after offline verification). They are escaped, script-free and not signed.
- Custody heads carry a whole-file signature; `check-head --record` detects truncation after a head.
- Reports record the source commit (`commit`, `commit_source`), stamped by the release build or read from git's files in a development checkout. The engine reports it too, the GUI footer shows it, and the frozen-sidecar build refuses a bundle without the stamp.
- `ridge-case check PATH` and GUI "Check exported files" verify any exported file, package or store backup by its kind.
- Export every item of one role at once (`ridge-case export-all`, GUI "Export all N comparison exports"): one logged export each, with an `EXPORTS.csv` index.
- Report exports, JSON and readable copies, now log the SHA-256 of the bytes written, so a copy in a case file can be matched to its custody entry.
- Store backups (`ridge-case backup`, `check-backup`, GUI "Back up this store"): an encrypted byte copy with a hash manifest. A backup does **not** hold the OS-keystore device secret.
- Workstation check (`ridge-case workstation`, GUI "This workstation"): the build, the OS keystore, the store and its limits of use, with what to fix before casework. Optionally it also checks the key register (CLI and GUI) and the NFIQ 2 tool (`--nfiq2`, asked only its version). It reads only, and it validates nothing.
- `jobs --json` and `notes --json` for laboratory scripts.

### Keys

- Device-secret recovery (ADR-012, accepted): `ridge-case recovery export|import|check` and the store screen's "Device-secret recovery" card. The OS-keystore secret is sealed under a separate recovery passphrase. Import never replaces a secret and first proves the secret opens the store. Both are logged in the new hash-chained store audit file (`store-audit.jsonl`).
- Limits of use can be signed by the Forensic Quality Manager (`ridge-case fqm-key`, `limits --sign`). A store with a signature has it checked before every job, fail closed.
- Laboratory key register (`ridge.key-register/1`): the offline checks take `--register` to name the key's holder and refuse unregistered, wrong-role, expired or revoked keys. The time checked is the signed time.
- Key cards (`ridge-case key-card`, GUI "Register this key with the laboratory") and `register-add`, for getting keys into the register.

### GUI

- Copy buttons for full SHA-256 values and the signing key id. The result is announced to screen readers.
- Custody log search for a hash, a job id or note text (also `ridge-case log --find`); <kbd>/</kbd> moves to the search box.
- "About Ridge", on the store screen and in a case: what Ridge is and is not, where the data lives, and how exported files are checked.
- Custody log view, case summary, note counts per job, job settings comparison (`ridge-case compare-jobs` in the CLI), and a view-only Measure tool on the comparison export.
- Batch import of up to 50 photos. Only a refusal of a photo itself lets the batch continue.
- Keyboard shortcuts (`?`, Alt+1–4), a retention-date reminder, case search, and an idle lock mirrored from the engine.
- Equal-scale reference comparison and scale bars; minutiae overlay (unvalidated, off by default).

### Security

- Strict input validation in the Rust core for every new command. Bidirectional overrides are refused in notes, names and register text.
- Release builds ignore the WebView debugging environment variables.
- Property-based fuzzing of the record formats a reviewer receives.
- A malformed `identity.json` is refused cleanly, and it is read within a 64 KiB bound.
- Bulk-export folders are private, and their file names stay distinct without regard to case.

### Documentation

- Screen-reader test script (`docs/screen_reader_test.md`) for the manual NVDA pass.
- Examiner guide (`docs/examiner_guide.md`): working a case in the desktop application, task by task, and what Ridge never does.

### Known issues

- Windows installers (MSI and per-user NSIS) build and pass a smoke test, but they are not code-signed yet: that needs the laboratory's certificate. Tauri WebDriver E2E is open. The manual NVDA pass is due before release (`docs/screen_reader_test.md`).
- Signing times come from the signer's clock. Revocation dates are fully effective only together with countersigned custody heads; the laboratory will countersign exported heads (OQ-8), and its procedure is still to be written.
- Restoring a store backup on another account or machine needs the examiner's OS-keystore secret; export a recovery file for it (ADR-012).
