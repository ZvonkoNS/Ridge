# Ridge

Ridge turns ordinary digital photographs of fingers into clean fingerprint images, as an
image-enhancement aid for qualified fingerprint examiners. It runs entirely offline, keeps case
material in an encrypted case store with a hash-chained custody log, and signs every job report.

> **Ridge does not identify anyone and draws no conclusions.** It enhances ridge detail; the
> comparison and every conclusion stay with the examiner. Current builds are **internal engineering
> builds, not validated or approved for casework** ([docs/prd.md](docs/prd.md) §7, milestone M5).

## Contents

1. [What Ridge does](#what-ridge-does)
2. [Installation](#installation)
3. [The desktop application](#the-desktop-application)
4. [The command line: `ridge`](#the-command-line-ridge)
5. [Casework from the command line: `ridge-case`](#casework-from-the-command-line-ridge-case)
6. [Outputs, reports and records](#outputs-reports-and-records)
7. [Scale, resolution and AFIS submissions](#scale-resolution-and-afis-submissions)
8. [Method variants and research mode](#method-variants-and-research-mode)
9. [Validation metrics: `ridge-validate`](#validation-metrics-ridge-validate)
10. [How the extraction works](#how-the-extraction-works)
11. [Photographing a finger](#photographing-a-finger)
12. [Security and privacy](#security-and-privacy)
13. [Configuration](#configuration)
14. [Development](#development)
15. [Building the desktop application](#building-the-desktop-application)
16. [Troubleshooting](#troubleshooting)
17. [Documentation](#documentation)
18. [Limits, non-claims and licence](#limits-non-claims-and-licence)

## What Ridge does

- **Extracts** the ridge pattern from a photograph of a finger: it finds the finger by skin colour,
  measures the ridge spacing, flattens lighting, filters with an orientation-adaptive Gabor bank
  and keeps only the areas where real ridges are visible. Blurry areas are left out, never invented.
- **Exports** comparison images for examiners and AFIS operators: a binary print, a contact-like
  grayscale export, both at a known resolution when the scale is known, as PNG, TIFF or BMP, and
  optionally a sweep of scales when the scale is uncertain.
- **Records** everything: originals are hashed and never changed, every job writes a signed report
  with every parameter and measurement, every read and write of case material is a line in a
  hash-chained custody log, and examiner notes and annotations live in the same log.
- **Helps at capture time**: a capture check says whether photographing the finger again would help,
  and notices in every report say when no scale reference was in the photo.
- **Stays out of the way of the examiner's judgement**: no matching, no scoring, no counting of
  agreement. Even the examiner's own annotations are stored as statements, not read as a result.

Three interfaces share one engine:

| Interface | For | Where |
| --- | --- | --- |
| Desktop application (Tauri, React) | Examiners working cases | `installers/` or `gui/` |
| `ridge-case` | Examiners, reviewers, the laboratory, scripts | Python package |
| `ridge` | Research and development on plain files, never case material | Python package |

## Installation

### Requirements

| Component | Requirement |
| --- | --- |
| Operating system | Windows 11 (built and smoke-tested), Linux x86-64, macOS on Apple silicon |
| Python (command line, development) | 3.12 or newer; dependencies pinned with hashes |
| Desktop application | The installer; no Python needed, the engine is bundled |
| Network | None. Ridge never opens a socket; only development tooling needs the internet |
| Optional | NIST NFIQ 2 executable for indicative quality scores; a laboratory limits-of-use file; a key register |

### The desktop application from an installer (Windows)

The folder [installers/](installers/) holds the current engineering builds and their SHA-256 values:

- `Ridge_0.2.0_x64-setup.exe`: per-user, no administrator rights, installs into `%LOCALAPPDATA%\Ridge`;
- `Ridge_0.2.0_x64_en-US.msi`: per-machine, needs an administrator.

Check the hash against `installers/SHA256SUMS.txt` before installing. The builds are unsigned, so
Windows warns about an unknown publisher. See [installers/README.md](installers/README.md) for the
details, and [Building the desktop application](#building-the-desktop-application) for macOS and
Linux, whose bundles are built on their own platforms.

### The Python package (command line)

```bash
git clone https://github.com/ZvonkoNS/Ridge.git
cd Ridge
python -m venv .venv
.venv/Scripts/python -m pip install --require-hashes --no-deps -r requirements.lock    # Windows
.venv/Scripts/python -m pip install --no-deps -e .
```

On Linux and macOS use `.venv/bin/python`. `requirements.lock` includes `pillow-heif` for iPhone
`.HEIC` photos. After the install, four commands are on the virtualenv's path: `ridge`,
`ridge-case`, `ridge-validate` and `ridge-sidecar` (the engine the desktop application runs; you
never call it yourself).

Check the installation:

```bash
.venv/Scripts/ridge --help
.venv/Scripts/ridge-case workstation --store D:/ridge-store      # once a store exists: build, keystore, store, limits
```

### Before the first case

Each examiner needs, once per Windows or OS account:

1. A folder for the **case store** (the laboratory's shared location or a private folder).
2. A **signing identity**: `ridge-case identity init --store <store>` or the desktop application's
   first-run screen. The key is sealed under the examiner's passphrase (at least 15 characters) and a
   secret in the account's OS keystore, so both are needed to open a case.
3. A place in the laboratory's **key register**, so that signed reports can be traced to a person:
   `ridge-case key-card` writes a self-signed card for the laboratory to add with `register-add`.
4. Optionally, the laboratory's **limits of use** (`limits-of-use.json`, signed by the Forensic
   Quality Manager) placed in the store, and a **recovery file** of the device secret exported with
   `ridge-case recovery export` and kept sealed by the laboratory.

## The desktop application

The application works a case from start to finish; the [examiner guide](docs/examiner_guide.md)
describes every screen. In short:

1. **Store screen**: choose the store, create the identity on first run, check this workstation,
   create or unlock a case. The passphrase is typed into a separate prompt window owned by the
   trusted Rust core; the main window never sees it.
2. **Evidence**: import up to 50 photos at a time with a source note. Before importing, **Check a
   photo** runs the capture check on a file without touching the store. Each stored photo shows its
   metadata and provenance hints and has its own capture check and notes.
3. **Review**: the original and the outputs side by side. Each image carries an exhibit label with its
   SHA-256 and, for processed images, the statement that it is not an identification. Set the region
   of interest, click two ruler or ID-1 card points for the scale, choose the finger position and
   source agency for the submission record, run the job, and read its summary. **Link views** moves
   both viewers together through the print area. **Mark minutiae** records your own numbered marks
   as a signed annotation set. **Research mode** reveals the unvalidated method variants.
4. **Jobs**: every job's verified report, its outputs, the examiner notes and annotation sets, the
   submission cover sheet, exports of the report, the readable copy, the annotated image, and
   **Reproduce job**.
5. **References**: a NAFIS/AFIS candidate image beside an export, at equal scale, view only.
6. **Records**: verify the case, read the custody log, export the processing record, build a
   disclosure package, place or lift a legal hold.

Keyboard: <kbd>Alt</kbd>+<kbd>1</kbd>–<kbd>4</kbd> switch sections, <kbd>?</kbd> lists shortcuts,
<kbd>+</kbd>/<kbd>-</kbd>/<kbd>0</kbd>/<kbd>1</kbd> zoom the viewers and the arrow keys pan them. The
application meets WCAG 2.2 AA for its controls and respects `prefers-reduced-motion`.

## The command line: `ridge`

`ridge` is R&D mode: it reads image files, writes plain PNG files, and says so on every run. Never
use it on case material; use `ridge-case`.

```bash
ridge photo.jpg                     # -> fingerprints/photo_fingerprint.png
ridge photos/ -o prints/            # every image in a folder
ridge photo.jpg --debug             # also save the intermediate steps
python -m ridge photo.jpg           # same as ridge
python fingerprint_extract.py photo.jpg   # v0 entry point, still supported
```

| Option | What it does |
| --- | --- |
| `-o`, `--outdir DIR` | Output folder (default `./fingerprints`), created owner-only on Linux/macOS. |
| `--min-quality Q` | 0–1: how clear the ridges must be to be kept (default 0.25). Lower values keep more of the finger; much below 0.22 Ridge starts inventing ridges in blurry areas. |
| `--flip` | Swap ridges and valleys, e.g. for scans of ink prints, where ridges are dark. |
| `--period N` | Ridge spacing in pixels, if the automatic measurement is wrong. |
| `--no-crop` | Output at the photo's size instead of cropping to the print. |
| `--debug` | Also save intermediate images; `*_debug_region.jpg` outlines the part of the photo that was used. |
| `--overwrite` | Replace existing outputs. Without it Ridge refuses, so earlier results are never lost silently. |
| `--max-input-mb N` | Largest input file accepted (default 200 MiB). |
| `--max-megapixels N` | Largest image accepted (default 150 MP). |
| `--verbose` | Print tracebacks for internal errors. |

Exit codes: `0` every photo succeeded; `1` at least one photo failed (each failure is listed on
stderr); `2` usage error; `3` internal error (a bug: please report it with `--verbose` output).

Accepted formats are JPEG, PNG, TIFF, BMP, WebP and HEIF/HEIC, recognised by content rather than by
file extension. Outputs contain pixels only: no EXIF or GPS data is copied from the photo.

Library use:

```python
from ridge import extract_fingerprint
from ridge.image_io import load_image

result = extract_fingerprint(load_image(path))  # result.image, result.period, result.found_finger
```

## Casework from the command line: `ridge-case`

Everything in a case store is encrypted (AES-256-GCM) under a key that needs both the examiner's
passphrase and the OS account's keystore entry. Every action is a line in the hash-chained custody
log, and every successful job writes an Ed25519-signed report. Passphrases are read interactively
only; nothing secret is ever an argument, an environment variable or a log line.

### A case from start to finish

```bash
ridge-case identity init --store D:/ridge-store          # once: your Ed25519 signing identity
ridge-case init --store D:/ridge-store --reference KT-2026-17 --legal-basis "..." --retention 2031-12-31
ridge-case cases --store D:/ridge-store                  # case ids and states (nothing decrypted)
ridge-case check-photo IMG_0412.jpg                      # should the finger be photographed again? (read-only, no case)
ridge-case import D:/ridge-store/<case-id> photo1.jpg photo2.heic --source "Exhibit 12, phone A"
ridge-case extract D:/ridge-store/<case-id> --all       # print + comparison exports for every photo
ridge-case list D:/ridge-store/<case-id>                # evidence, outputs, jobs
ridge-case report D:/ridge-store/<case-id> <job-id>     # verified report as text (--json for the signed JSON)
ridge-case export-all D:/ridge-store/<case-id> --to D:/for-afis   # grayscale comparison exports, logged, with EXPORTS.csv
ridge-case verify D:/ridge-store/<case-id>              # hashes, custody chain, report signatures
```

### Extraction jobs

```bash
ridge-case extract D:/ridge-store/<case-id> --all --keep-going   # a refused photo does not stop the batch (exit 1)
ridge-case extract D:/ridge-store/<case-id> --evidence <sha> --ruler 12 40 812 44 40   # ruler: 2 points 40 mm apart
ridge-case extract D:/ridge-store/<case-id> --evidence <sha> --card long 100 200 1600 230   # ISO/IEC 7810 ID-1 card edge
ridge-case extract D:/ridge-store/<case-id> --evidence <sha> --roi 900 400 700 1100     # one finger of several
ridge-case extract D:/ridge-store/<case-id> --all --nfiq2 "C:/Program Files/NFIQ2/bin/nfiq2.exe"
ridge-case extract D:/ridge-store/<case-id> --all --minutiae   # + automatic minutiae (unvalidated)
ridge-case extract D:/ridge-store/<case-id> --evidence <sha> --finger-position 2 --source-agency "Lab A"   # submission record
ridge-case extract D:/ridge-store/<case-id> --evidence <sha> --channel auto --specular-mask --upright --local-frequency --rectify   # opt-in variants, unvalidated (ADR-014)
```

The options of `ridge` (`--min-quality`, `--flip`, `--period`, `--no-crop`) apply as well. Every
`<sha>` may be a unique prefix of eight or more characters.

### Photos: metadata, capture check, references

```bash
ridge-case metadata D:/ridge-store/<case-id> <sha>      # a photo's metadata without a job (--json; the read is logged)
ridge-case check-photo --case D:/ridge-store/<case-id> <sha>   # the capture check on a stored photo (the read is logged)
ridge-case import-reference D:/ridge-store/<case-id> candidate.png --source "NAFIS candidate 3"
ridge-case compare D:/ridge-store/<case-id> <export-sha> <reference-sha> --to sheet.png   # equal scale, view only
```

### Exports

```bash
ridge-case export D:/ridge-store/<case-id> <sha> --to print.png   # the only way plaintext leaves the store (logged)
ridge-case export D:/ridge-store/<case-id> <sha> --to D:/out/finger.bmp   # converted to BMP (.tif for TIFF; .png copies the stored bytes)
ridge-case export-all D:/ridge-store/<case-id> --to D:/for-afis-binary --role export   # the binary comparison exports
ridge-case export-all D:/ridge-store/<case-id> --to D:/for-afis-tiff --format tiff      # grayscale exports as uncompressed TIFF
ridge-case sweep D:/ridge-store/<case-id> <export-sha> --to D:/out/sweep --steps 5   # rescaled copies over the scale uncertainty
ridge-case report D:/ridge-store/<case-id> <job-id> --cover D:/out/cover.html   # AFIS submission cover sheet (not signed; logged)
```

### Notes and annotations

```bash
ridge-case note D:/ridge-store/<case-id> "text" --job <job-id>   # examiner note in the custody log (--corrects SEQ)
ridge-case notes D:/ridge-store/<case-id>               # every note, with time and examiner
ridge-case annotate D:/ridge-store/<case-id> --job <job-id> --image <print-sha> --mark 410,620,ending,core --mark 532,701,bifurcation
ridge-case annotations D:/ridge-store/<case-id> --job <job-id>   # the sets (--json)
ridge-case export-annotated D:/ridge-store/<case-id> <seq> --to charted.png   # the image with the marks drawn (logged)
```

### Reports, records and verification

```bash
ridge-case jobs D:/ridge-store/<case-id>                # jobs: started, result, signed report or not (--json)
ridge-case report D:/ridge-store/<case-id> <job-id> --to report.json   # + report.json.sig (logged)
ridge-case report D:/ridge-store/<case-id> <job-id> --html report.html # readable copy, not signed (logged)
ridge-case compare-jobs D:/ridge-store/<case-id> <job-a> <job-b>      # settings that differ (no ranking)
ridge-case reproduce D:/ridge-store/<case-id> <job-id>  # re-run from the report; exit 1 if any output differs
ridge-case log D:/ridge-store/<case-id>                 # decrypted custody log (processing record)
ridge-case log D:/ridge-store/<case-id> --find <sha>     # only entries containing a hash, a job id or note words
ridge-case log D:/ridge-store/<case-id> --to record.json # signed processing record for the DPO (logged)
ridge-case head D:/ridge-store/<case-id> --to head.json  # signed custody head for the lab to countersign (logged)
ridge-case status D:/ridge-store/<case-id>              # one-screen summary: stored items, jobs, notes, last verify
ridge-case package D:/ridge-store/<case-id> --to D:/disclosure/KT-1   # signed records + manifest, no images
```

Anyone with the public key can verify what leaves the store, with no store and no passphrase:

```bash
ridge-case check-report report.json --key-id <key-id>   # an exported report
ridge-case check-report report.json --register lab-keys.json   # and name the holder; refuse unregistered or revoked keys
ridge-case check-log record.json --key-id <key-id>      # chain, sequence and signed heads
ridge-case check-log record.json --html record.html     # verify, then write a readable copy for the DPO
ridge-case check-head head.json --record record.json    # a later record still contains that head (no truncation)
ridge-case check-package D:/disclosure/KT-1 --key-id <key-id>
ridge-case check <file-package-or-backup-folder> --register lab-keys.json   # any exported Ridge file by its kind
```

### Store, keys and the laboratory

```bash
ridge-case verify-store --store D:/ridge-store           # every case of the store, one passphrase
ridge-case overview --store D:/ridge-store              # references, retention dates, legal holds (reads only)
ridge-case overview --store D:/ridge-store --due        # only cases past retention without a hold (retention review)
ridge-case backup --store D:/ridge-store --to E:/backup-2026-10-18   # encrypted byte copy with a hash manifest
ridge-case check-backup E:/backup-2026-10-18            # every file against the manifest
ridge-case workstation --store D:/ridge-store --register lab-keys.json --nfiq2 "C:/Program Files/NFIQ2/bin/nfiq2.exe"
ridge-case recovery export --store D:/ridge-store --to E:/ridge-recovery.json   # device secret under a recovery passphrase (ADR-012)
ridge-case recovery import E:/ridge-recovery.json --store D:/ridge-store         # on a new account; never replaces a secret
ridge-case key-card --store D:/ridge-store --holder "Name" --to card.json   # your public key, self-signed, for the lab
ridge-case register-add --card card.json --register lab-keys.json --to lab-keys-2.json   # lab: new register version
ridge-case register --check lab-keys.json                # the laboratory's key register (holders, roles, validity)
ridge-case limits --store D:/ridge-store                 # limits of use from the lab's validation, if configured
ridge-case limits --check limits-of-use.json             # validate a limits file before placing it in a store
ridge-case fqm-key --to fqm-key.json                     # FQM only: create the key that signs limits of use
ridge-case limits --sign limits-of-use.json --key fqm-key.json   # FQM only: writes limits-of-use.json.sig
ridge-case hold D:/ridge-store/<case-id> --on --reason "..."
ridge-case dispose D:/ridge-store/<case-id> --confirm <case-id> --reason retention-expired   # crypto-erase
```

## Outputs, reports and records

Every successful job stores, encrypted, under the job's id:

| Role | What it is |
| --- | --- |
| `print` | The extracted print: white ridges on black, at the photo's resolution (or finer for low-resolution photos), cropped to the print unless `--no-crop`. |
| `export` | The binary comparison export: dark ridges on light, mirrored to contact orientation, resampled to 500 ppi when the scale is known, PNG with resolution metadata. |
| `export-gray` | The grayscale comparison export of the same geometry: the filtered ridge signal through a soft contrast curve, zero outside the print's region. It is the default comparison image in the application and in `export-all`. |
| `debug` | With `--debug`: the intermediate images. |
| `minutiae` | With `--minutiae`: automatic minutiae as JSON, labelled unvalidated and never used for matching. |

The **job report** (signed JSON, RFC 8785 canonical form) records the input's hash, metadata and
provenance hints, every parameter including the method variants, the measurements (ridge spacing,
scale and its uncertainty, print area in the photo's pixels, variant measurements), the outputs with
their hashes, the export's scale and transforms, an indicative NFIQ 2 score when configured, the
submission record, the limits-of-use outcome and a disclaimer. `ridge-case report --html` and the
application's "Save readable copy" render it as a page that also lists the examiner notes and
annotation sets of the job from the custody log; the page is not signed, the JSON is.

The **custody log** is one encrypted, hash-chained JSONL file per case. Every import, read, job,
export, note, annotation, verification, hold and disposal is an entry with a sequence number, a time,
the actor and the previous head's hash; `chain.sign` entries sign the head. The processing record and
disclosure package export it in signed form for the DPO or the court.

**Examiner notes** are custody entries; a correction is a new note naming the one it corrects.
**Annotation sets** (FR-55) are custody entries too: numbered marks (ending, bifurcation, other) with
optional labels on one output image, validated against the stored image, with the chain head signed
right after each set; a newer set names the set it replaces. `export-annotated` writes the image with
the marks drawn on it as a logged plaintext PNG. Marks are the examiner's statements: Ridge never counts
them, compares them or reads them as a match.

## Scale, resolution and AFIS submissions

- **Scale reference.** Two points on a ruler with the distance in millimetres (`--ruler`), or two points
  across an edge of an ISO/IEC 7810 ID-1 card, whose length Ridge supplies (`--card long|short`), give a
  measured scale with a recorded uncertainty. Without either, the job still runs: the scale is
  estimated from the ridge spacing with an assumed ridge distance (±15 %), and the report, the command
  output and the application carry a notice asking for a ruler or a card in the plane of the finger
  pad where one can still be added. The laboratory's limits of use may require a reference.
- **Resolution.** Comparison exports are resampled to the target resolution (500 ppi by default). When
  an export had to be enlarged by more than 5 % to reach it, counting the pipeline's own enlargement of a
  low-resolution photo, the report notes it: no detail is gained by enlarging.
- **Formats.** `export` and `export-all` convert to uncompressed TIFF or BMP on request, pixel for pixel,
  with the resolution and no other metadata; the custody log records the format and the written file's
  hash.
- **Scale sweep.** When the scale is estimated, `sweep` writes 3 to 9 rescaled copies spanning the
  uncertainty, each logged, for separate searches.
- **Submission record and cover sheet.** The finger position (ANSI/NIST-ITL codes 0 to 10) and the
  source agency are recorded as the examiner's statements; `report --cover` writes an HTML cover sheet
  for the AFIS operator with the files to attach, their hashes, the scale method and uncertainty, the
  transforms, the indicative NFIQ 2 score and the limits-of-use outcome.
- **Exchange formats.** Which record format (ANSI/NIST-ITL, ISO/IEC 39794-4) and resolution the
  laboratory's AFIS accepts is open: [docs/afis_integration_questionnaire.md](docs/afis_integration_questionnaire.md)
  collects the answers, and [docs/pilot_protocol.md](docs/pilot_protocol.md) is the template for a pilot
  that measures rank-k hit rates.
- **NFIQ 2.** With the NIST NFIQ 2 executable configured, the grayscale export is scored. The score is
  indicative only: NFIQ 2 is defined for 500 ppi contact prints, and a photograph is outside its scope.

## Method variants and research mode

The characterised pipeline is fixed: the same photo, version, parameters, operating system and CPU
architecture give bit-identical output, guarded by golden tests. Five **method variants** exist behind
explicit options, off by default and recorded in every report ([ADR-014](docs/adr/ADR-014-opt-in-method-variants.md)):

| Variant | Option | What it changes |
| --- | --- | --- |
| Colour plane | `--channel green,red,blue,gray,cyan,auto` | Which plane carries the ridge signal; `auto` picks the strongest. |
| Specular mask | `--specular-mask` | Excludes flash highlights from the finger area. |
| Upright rotation | `--upright` | Rotates the finger so that its axis is vertical, tip up. |
| Local ridge frequency | `--local-frequency` | Filters each pixel with a Gabor bank tuned to its own measured ridge spacing. |
| Rectification | `--rectify` | Unrolls the pad's curvature row by row (implies the upright rotation); the scale then holds on the centre line only. |

They are unvalidated: none may be used in casework before the FQM's decision and a validation study. In
the application they are hidden until **Research mode** is switched on in the review panel, and
switching it off resets them (ADR-015). The command line keeps the flags under their unvalidated labels.

## Validation metrics: `ridge-validate`

For the method validation study (PRD §12), run an open matcher (for example SourceAFIS or NIST NBIS)
over the laboratory's consented validation set **outside this repository**, and feed the results to
`ridge-validate`:

```bash
ridge-validate scores.csv --fmr 0.001 --fmr 0.0001 --ftx-attempts 400 --ftx-failures 12 -o validation.json
ridge-validate --ranks ranks.csv --rank 1 --rank 5 --rank 10 --rank 20 -o identification.json   # 1:N searches
ridge-validate scores.csv --ranks ranks.csv -o both.json
```

`scores.csv` has `genuine` (1 or 0) and `score` columns and an optional `group`; the report gives FNMR
at each target FMR with Wilson 95 % intervals, the rule-of-30 check, the DET curve, the EER, the
failure-to-extract rate and the same per group (the bias check). `ranks.csv` has `probe` and `rank`
(empty when the mate was not returned) and an optional `group`; the report gives the rank-k hit rates
with intervals and the CMC curve (ISO/IEC 19795-1). The tool makes no claim beyond the numbers.

## How the extraction works

1. **Find the finger** by skin colour (Lab a\* channel plus an Otsu threshold). If skin and background
   do not separate (a grayscale photo, a skin-coloured background), the whole photo is searched.
2. **Measure the ridge spacing** from the spectra of small patches, then rescale the photo so that
   ridges are 12 px apart; every later step is then independent of camera resolution and distance.
3. **Flatten lighting and contrast**, estimate the local ridge direction, and filter with an
   orientation-adaptive Gabor filter bank (Hong, Wan and Jain, 1998), twice: the second pass takes its
   directions from the cleaner first result.
4. **Keep only real ridges**: areas where the ridge-frequency energy points in one direction and
   repeats one spacing ahead and behind, which rejects noise, the finger's outline, creases and
   background lines; the largest compact such area is the print.
5. **Render**: binarise at the photo's resolution for the print, or pass the filtered signal through a
   soft contrast curve for the grayscale export; mirror and resample for the comparison exports.

The print's location is mapped back to the photo's pixels and drawn on the original in the
application, so the examiner sees where the print came from. The full design is in
[docs/architecture.md](docs/architecture.md).

## Photographing a finger

[docs/capture_guidance.md](docs/capture_guidance.md) is the guidance for investigators, with a
one-page checklist. The short version:

- one finger per photo, filling at least a third of the frame; the camera straight at the pad, tip up;
- a ruler or an ID-1 card in the plane of the pad, beside it; photograph anyway if none is at hand;
- focus on the ridges, 10 to 20 cm away, both hands or rested; check sharpness by zooming in;
- diffuse light, no flash on the pad, no shadows across the ridges, a plain matt background;
- three frames: straight, slight roll left, slight roll right; keep all;
- do not crop, rotate, filter or re-save; transfer the original file unchanged and keep its metadata.

Run the capture check on the file before import: it says whether a retake would help.

## Security and privacy

- **Offline by design.** No component opens a network socket; the application's WebView may not reach
  the file system, the shell or the network, and talks to the engine only through typed, allow-listed
  commands that the Rust core forwards over stdio as JSON-RPC.
- **Encrypted case store.** Per-case AES-256-GCM data keys wrapped by the examiner's Argon2id
  passphrase and the OS keystore secret; keyed file names; every artefact content-addressed and
  hashed; metadata, reports and custody lines encrypted at rest. A device-secret recovery file can be
  exported under a recovery passphrase and kept sealed by the laboratory (ADR-012).
- **Integrity.** Hash-chained custody log, Ed25519-signed reports and record heads, `verify` for a
  case, `verify-store` for a store, and offline checkers for every exported file.
- **Inputs.** Formats are detected by content from an allow-list, sizes and pixel counts are bounded
  before decoding, originals are opened read-only, hashed and decoded from the same bytes, and never
  modified. Outputs are published atomically and never overwrite silently.
- **Data classes.** Finger photos and prints are special-category biometric data and potentially
  evidence. They never enter this repository: `.gitignore` blocks image and fingerprint-exchange
  formats, the `docs` gate fails if one is tracked, and development and tests use synthetic images only.
- **Metadata.** Photo metadata is read as stored and shown as text; nothing is verified or interpreted,
  the map link is copy-only, and the laboratory decides what reports may carry (OQ-16).

## Configuration

Ridge has no configuration file. What can be set:

| Setting | How |
| --- | --- |
| Input limits | `--max-input-mb`, `--max-megapixels` (hard maxima in code) |
| NFIQ 2 | `--nfiq2 <path to nfiq2 executable>`; the application reads the same path from the workstation check |
| Limits of use | `limits-of-use.json` plus `.sig` in the store, signed with the FQM's key (`fqm-key`, `limits --sign`) |
| Key register | A register file passed with `--register` to the checkers and the workstation check |
| Retention | Per case at creation (`--retention`); `overview --due` lists cases past it |
| OpenCV threads | Set once at startup to the documented, determinism-tested count |

Secrets (passphrases, keys) are never read from arguments, files you write, or the environment.

## Development

```bash
.venv/Scripts/python -m pip install --require-hashes --no-deps -r requirements.lock -r requirements-dev.lock
.venv/Scripts/python -m pip install --no-deps --no-build-isolation -e .
.venv/Scripts/python tools/gate.py all     # docs lint format typecheck test sast deps secrets licenses sbom gui
```

The quality gates: `docs` (document consistency and tracked-image check), `lint` and `format` (ruff),
`typecheck` (mypy strict), `test` (pytest with coverage), `sast` (bandit), `deps` (pip-audit),
`secrets` (gitleaks), `licenses`, `sbom` (CycloneDX) and `gui` (the GUI's npm and cargo checks). The
`gui` gate needs Node.js 22, npm, the Rust toolchain pinned in `gui/src-tauri/rust-toolchain.toml`,
`cargo-audit`, `cargo-deny` and `cargo-cyclonedx` (`cargo install cargo-audit cargo-deny cargo-cyclonedx --locked`).
The `secrets` gate needs [gitleaks](https://github.com/gitleaks/gitleaks) on PATH; `deps` needs network
access.

Tests use synthetic images only (`tests/synthetic.py`). `tests/golden/` freezes the characterised
results per CPU architecture (x86-64, arm64), and the suite also runs v0 from git history to require
bit-identical results. Goldens change only with an ADR and human approval; regenerate them with
`tools/make_golden.py` (arm64: the `golden` workflow) for an intended, documented change.

Engineering rules live in [AGENTS.md](AGENTS.md) and
[Instruction_documentation/](Instruction_documentation/README.md): the standards profile, coding and
testing standards, forensic and biometric data rules, execution rules and the handoff workflow. Every
substantial piece of work ends with a handoff in `Instruction_documentation/Handoff/`.

Repository layout:

```text
src/ridge/            Python core: pipeline/ (pure), image_io, export/, case/, metadata/, minutiae/, validation/, sidecar/
gui/                  Desktop application: src/ (React, TypeScript), src-tauri/ (Rust core, capabilities)
tests/                pytest suite, synthetic generators, goldens per architecture
tools/                gate.py, gate_gui.py, build_sidecar.py, make_golden.py, perf_benchmark.py
docs/                 PRD, architecture and ADRs, guides, pilot protocol, questionnaire
installers/           Current Windows engineering builds and their hashes
Instruction_documentation/   Standards pack, profile, handoffs
```

To update the locks:

```bash
python -m uv pip compile pyproject.toml --extra heic --universal --python-version 3.12 --generate-hashes -o requirements.lock
python -m uv pip compile requirements-dev.in --universal --python-version 3.12 --generate-hashes -o requirements-dev.lock
```

## Building the desktop application

Development build (Node.js 22, the pinned Rust toolchain, and the Python virtualenv above with
`pip install -e .`):

```bash
python tools/gui_icons.py
cd gui
npm ci
npm run tauri dev
```

`npm run dev` alone serves a **preview with synthetic data** in a normal browser for UI work; it never
touches a case store and is compiled out of production builds.

Release bundles:

```bash
python -m pip install --require-hashes --no-deps -r requirements-build.lock
python tools/build_sidecar.py          # freezes the engine, checks the bundle, smoke-tests it over stdio
cd gui && npx tauri build --config src-tauri/tauri.release.conf.json   # bundles resources/sidecar/
```

On Windows this writes the MSI and the per-user NSIS installer; on macOS a `.dmg` and on Linux an
`.AppImage`, each on its own platform. The release checklist adds the installer smoke test, SBOMs,
`SHA256SUMS`, a detached signature and OS code signing, which needs the laboratory's certificate.

## Troubleshooting

| Symptom | What it means and what to do |
| --- | --- |
| `no finger located` or the whole photo is searched | Skin colour did not separate from the background (grayscale photo, skin-coloured background). Retake on a plain matt background; the capture check tells you first. |
| `resolution too low` or very few pixels per ridge | The camera was too far away or digital zoom was used. Move closer; the capture check says "coarse". |
| The job keeps too little of the finger | Blur, glare or an out-of-focus pad: Ridge leaves unclear areas out rather than inventing ridges. Lowering `--min-quality` below 0.22 invents ridges; retake instead. |
| "No scale reference was given" | Expected without a ruler or card; the scale is estimated. Add a reference where one can still be added, or submit a scale sweep. |
| A resolution note on the export | The export was enlarged to reach its resolution; no detail was gained. Prefer a closer photo. |
| `case is open elsewhere` | Another process holds the case; close it. After a crash, delete the named `LOCK` file. |
| The passphrase is refused on a new computer | The key also needs the OS account's keystore secret: import the recovery file with `ridge-case recovery import`. |
| `ridge-case workstation` reports a Problem | Fix what it names before casework (keystore, store, limits, register, NFIQ 2 path). |
| Windows warns about an unknown publisher | The engineering builds are unsigned; compare the installer's hash with `installers/SHA256SUMS.txt`. |
| A method variant is not visible in the application | Switch on Research mode in the review panel; variants stay unvalidated. |

## Documentation

| Document | Purpose |
| --- | --- |
| [docs/examiner_guide.md](docs/examiner_guide.md) | For examiners: working a case in the desktop application, task by task |
| [docs/verification_guide.md](docs/verification_guide.md) | For reviewers, the DPO and the FQM: checking exported reports, records, packages and keys offline |
| [docs/capture_guidance.md](docs/capture_guidance.md) | For investigators: photographing a finger so that Ridge has something to work with |
| [docs/pilot_protocol.md](docs/pilot_protocol.md) | Template for a pilot that searches Ridge prints in an AFIS and measures rank-k hit rates |
| [docs/afis_integration_questionnaire.md](docs/afis_integration_questionnaire.md) | Questions for the AFIS team (OQ-4): formats, records, scale, candidate lists, transfer, pilot |
| [docs/prd.md](docs/prd.md) | Product requirements, milestones, risks, open questions |
| [docs/architecture.md](docs/architecture.md) and [docs/adr/](docs/adr/) | Architecture, security design, the sidecar protocol, ADRs |
| [docs/screen_reader_test.md](docs/screen_reader_test.md) | Manual NVDA test script, run before each GUI release |
| [CHANGELOG.md](CHANGELOG.md) | What changed, its forensic impact and known issues |
| [installers/README.md](installers/README.md) | The current builds, their hashes, install and uninstall |
| [AGENTS.md](AGENTS.md), [Instruction_documentation/](Instruction_documentation/README.md) | Engineering rules, standards profile, quality gates, release checklist, handoffs |

## Limits, non-claims and licence

- Ridge is an image-enhancement aid. It does not identify, match, score or validate, and no output of
  Ridge is an identification. Every processed image says so.
- Ridge is not validated for casework. Method validation, the DPIA, the AI Act assessment, named
  owners and code signing are open (PRD §7, §15); the standards profile records the exceptions.
- Results are reproducible on the same operating system and CPU architecture; x86-64 and arm64
  differ by design and are validated separately.
- The indicative NFIQ 2 score, the automatic minutiae and the method variants are unvalidated aids
  for orientation and research.

Licence: proprietary, for the laboratory's internal use (`LicenseRef-Proprietary` in `pyproject.toml`; no
open-source licence is granted). The Python, npm and Cargo dependencies' licences are checked against an
allow-list by the `licenses` gate and listed in the SBOMs the gates write to `build/`.
