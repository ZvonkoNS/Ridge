# Ridge

Extract fingerprints from ordinary digital photos of fingers and save them as clean
white ridges on a black background, as an image-enhancement aid for qualified
fingerprint examiners.

> **Ridge does not identify anyone and draws no conclusions.** Comparison and
> conclusions stay with the examiner. Ridge is **not yet validated or approved for
> casework** (see [docs/prd.md](docs/prd.md) §7, milestone M5).

| Document | Purpose |
| --- | --- |
| [docs/prd.md](docs/prd.md) | Product requirements, milestones, risks, open questions |
| [docs/architecture.md](docs/architecture.md) | Architecture, security design, ADRs |
| [CHANGELOG.md](CHANGELOG.md) | What changed, its forensic impact and known issues (internal builds, not for casework) |
| [docs/verification_guide.md](docs/verification_guide.md) | For reviewers, the DPO and the FQM: checking exported reports, records, packages and keys offline |
| [AGENTS.md](AGENTS.md) and [Instruction_documentation/](Instruction_documentation/README.md) | Engineering rules, standards profile, quality gates, handoffs |

## Install

Python 3.12 or newer. Dependencies are pinned with hashes.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install --require-hashes --no-deps -r requirements.lock    # Windows
.venv/Scripts/python -m pip install --no-deps -e .
```

On Linux and macOS, use `.venv/bin/python`. `requirements.lock` includes `pillow-heif`
for iPhone `.HEIC` photos. For development, also install `requirements-dev.lock`; see
[Development](#development).

## Usage

```bash
ridge photo.jpg                     # -> fingerprints/photo_fingerprint.png
ridge photos/ -o prints/            # every image in a folder
ridge photo.jpg --debug             # also save the intermediate steps
python -m ridge photo.jpg           # same as ridge
python fingerprint_extract.py photo.jpg   # v0 entry point, still supported
```

| Option | What it does |
| --- | --- |
| `-o`, `--outdir DIR` | Output folder (default `./fingerprints`). It is created owner-only on Linux/macOS. |
| `--min-quality Q` | 0–1: how clear the ridges must be to be kept (default 0.25). Lower values keep more of the finger. Much below 0.22 Ridge starts inventing ridges in blurry areas. |
| `--flip` | Swap ridges and valleys, e.g. for scans of ink prints, where ridges are dark. |
| `--period N` | Ridge spacing in pixels, if the automatic measurement is wrong. |
| `--no-crop` | Output at the photo's size instead of cropping to the print. |
| `--debug` | Also save intermediate images. `*_debug_region.jpg` outlines the part of the photo that was used. |
| `--overwrite` | Replace existing outputs. Without it Ridge refuses, so earlier results are never lost silently. |
| `--max-input-mb N` | Largest input file accepted (default 200 MiB). |
| `--max-megapixels N` | Largest image accepted (default 150 MP). |
| `--verbose` | Print tracebacks for internal errors. |

Exit codes: `0` every photo succeeded; `1` at least one photo failed (each failure is
listed on stderr); `2` usage error; `3` internal error (a bug, so please report it with
`--verbose` output).

Accepted formats are JPEG, PNG, TIFF, BMP, WebP and HEIF/HEIC, recognised by content
rather than by file extension. Outputs contain pixels only: no EXIF or GPS data is
copied from the photo.

Library use:

```python
from ridge import extract_fingerprint
from ridge.image_io import load_image

result = extract_fingerprint(load_image(path))  # result.image, result.period, result.found_finger
```

## Casework: the encrypted case store (`ridge-case`)

`ridge` on its own is R&D mode: outputs are plain files, and it says so on every run. For
case material use `ridge-case`. Everything is stored encrypted (AES-256-GCM) under a key
that needs **both** your passphrase **and** your OS account's keystore entry. Every action
is recorded in a hash-chained custody log, and every job produces a signed report.

```bash
ridge-case identity init --store D:/ridge-store          # once: your Ed25519 signing identity
ridge-case init --store D:/ridge-store --reference KT-2026-17 --legal-basis "..." --retention 2031-12-31
ridge-case cases --store D:/ridge-store                  # case ids and states (nothing decrypted)
ridge-case import D:/ridge-store/<case-id> photo1.jpg photo2.heic --source "Exhibit 12, phone A"
ridge-case extract D:/ridge-store/<case-id> --all       # print + 500 ppi comparison export; same options as ridge
ridge-case extract D:/ridge-store/<case-id> --all --keep-going   # a refused photo does not stop the batch (exit 1)
ridge-case extract D:/ridge-store/<case-id> --evidence <sha> --ruler 12 40 812 44 40   # ruler: 2 points 40 mm apart
ridge-case extract D:/ridge-store/<case-id> --evidence <sha> --roi 900 400 700 1100     # one finger of several
ridge-case extract D:/ridge-store/<case-id> --all --nfiq2 "C:/Program Files/NFIQ2/bin/nfiq2.exe"
ridge-case extract D:/ridge-store/<case-id> --all --minutiae   # + automatic minutiae (unvalidated)
ridge-case list D:/ridge-store/<case-id>                # evidence, outputs, jobs
ridge-case import-reference D:/ridge-store/<case-id> candidate.png --source "NAFIS candidate 3"
ridge-case compare D:/ridge-store/<case-id> <export-sha> <reference-sha> --to sheet.png   # equal scale, view only
ridge-case export D:/ridge-store/<case-id> <sha> --to print.png   # the only way plaintext leaves the store (logged)
ridge-case export-all D:/ridge-store/<case-id> --to D:/for-afis   # every comparison export, one logged export each, with EXPORTS.csv
ridge-case verify D:/ridge-store/<case-id>              # hashes, custody chain, report signatures
ridge-case status D:/ridge-store/<case-id>              # one-screen summary: stored items, jobs, notes, last verify
ridge-case verify-store --store D:/ridge-store           # every case of the store, one passphrase
ridge-case overview --store D:/ridge-store              # references, retention dates, legal holds (reads only)
ridge-case overview --store D:/ridge-store --due        # only cases past retention without a hold (retention review)
ridge-case backup --store D:/ridge-store --to E:/backup-2026-10-18   # encrypted byte copy with a hash manifest
ridge-case workstation --store D:/ridge-store          # build, OS keystore, store, limits: what to fix before casework
ridge-case check-backup E:/backup-2026-10-18            # every file against the manifest
ridge-case note D:/ridge-store/<case-id> "text" --job <job-id>   # examiner note in the custody log (--corrects SEQ)
ridge-case notes D:/ridge-store/<case-id>               # every note, with time and examiner
ridge-case package D:/ridge-store/<case-id> --to D:/disclosure/KT-1   # signed records + manifest, no images
ridge-case check-package D:/disclosure/KT-1 --key-id <key-id>          # verify the package offline
ridge-case key-card --store D:/ridge-store --holder "Name" --to card.json   # your public key, self-signed, for the lab
ridge-case register-add --card card.json --register lab-keys.json --to lab-keys-2.json   # lab: new register version
ridge-case register --check lab-keys.json                # the laboratory's key register (holders, roles, validity)
ridge-case check-report report.json --register lab-keys.json   # name the holder; refuse unregistered or revoked keys
ridge-case check-log record.json --html record.html     # verify, then write a readable copy for the DPO
ridge-case check <file-or-package-folder> --register lab-keys.json   # verify any exported Ridge file by its kind
ridge-case log D:/ridge-store/<case-id>                 # decrypted custody log (processing record)
ridge-case jobs D:/ridge-store/<case-id>                # jobs: started, result, signed report or not (--json)
ridge-case report D:/ridge-store/<case-id> <job-id>     # verified report as text (--json for the signed JSON)
ridge-case report D:/ridge-store/<case-id> <job-id> --to report.json   # + report.json.sig (logged)
ridge-case report D:/ridge-store/<case-id> <job-id> --html report.html # readable copy, not signed (logged)
ridge-case compare-jobs D:/ridge-store/<case-id> <job-a> <job-b>      # settings that differ (no ranking)
ridge-case check-report report.json --key-id <key-id>   # anyone can verify an exported report, no store needed
ridge-case reproduce D:/ridge-store/<case-id> <job-id>  # re-run from the report; exit 1 if any output differs
ridge-case log D:/ridge-store/<case-id> --to record.json # signed processing record for the DPO (logged)
ridge-case check-log record.json --key-id <key-id>      # chain, sequence and signed heads, no store needed
ridge-case head D:/ridge-store/<case-id> --to head.json  # signed custody head for the lab to countersign (logged)
ridge-case check-head head.json --record record.json    # a later record still contains that head (no truncation)
ridge-case hold D:/ridge-store/<case-id> --on --reason "..."
ridge-case limits --store D:/ridge-store                 # limits of use from the lab's validation, if configured
ridge-case limits --check limits-of-use.json             # validate a limits file before placing it in a store
ridge-case fqm-key --to fqm-key.json                     # FQM only: create the key that signs limits of use
ridge-case limits --sign limits-of-use.json --key fqm-key.json   # FQM only: writes limits-of-use.json.sig
ridge-case dispose D:/ridge-store/<case-id> --confirm <case-id> --reason retention-expired
```

Each job also stores a **comparison export**: dark ridges on light, mirrored to contact
orientation, resampled to 500 ppi (PNG with resolution metadata). Without `--ruler` the
scale is estimated from the ridge spacing and an assumed 0.47 mm ridge distance (±15 %,
to be validated); the report records the method and uncertainty. With `--nfiq2` an
**indicative** NFIQ 2 score is recorded (NFIQ 2 is defined for contact prints).

**Limits of use.** When the laboratory's validation report defines limits of use, the
Forensic Quality Manager places them in the store as `limits-of-use.json`. Every job report
then records whether the job stayed within them, and the CLI and GUI show any deviation as a
warning. Ridge ships no limits.

Passphrases (at least 15 characters) are only read interactively. There is no recovery
key yet: losing the passphrase or the OS account makes a case unreadable (PRD OQ-12).

## Desktop GUI (`gui/`)

The desktop GUI (Tauri v2, React, TypeScript) runs the same case store as `ridge-case`:

- choose a store, then create your examiner identity on first run, create or unlock a case;
- import evidence photos with a source note;
- review the original and the outputs side by side. Every image carries an exhibit label
  with its SHA-256. Processed images also say they are not an identification and carry a
  millimetre scale bar drawn at the current zoom;
- run jobs with every parameter visible, including a region of interest and two ruler points
  that you click on the photo or type;
- read verified reports, export them and reproduce jobs;
- put a NAFIS/AFIS reference beside an export (view only);
- verify the case, export the processing record, and place or lift a legal hold.

The passphrase is typed in a separate prompt window that only the trusted Rust core talks
to; the main window never sees it.

It talks to Ridge through `ridge-sidecar`, a child process that speaks JSON-RPC 2.0, one
message per line, on stdin/stdout. Neither the sidecar nor the GUI ever opens a network
socket. Methods, schemas and the GUI's security design are in `docs/architecture.md` §7.3.

Development build (Node.js 22, the Rust toolchain pinned in
`gui/src-tauri/rust-toolchain.toml`, and the Python virtualenv above with `pip install -e .`):

```bash
python tools/gui_icons.py
cd gui
npm ci
npm run tauri dev
```

`npm run dev` alone serves a **preview with synthetic data** in a normal browser, for UI
work. It never touches a case store and is compiled out of production builds.

Release packaging: `python tools/build_sidecar.py` (after installing
`requirements-build.lock`) freezes the sidecar, checks it and smoke-tests it. Then
`npx tauri build --config src-tauri/tauri.release.conf.json` bundles it. The installer
build and code signing are not exercised yet (see the standards profile).

## Validation metrics (`ridge-validate`)

For the method validation study (PRD §12), run an open matcher (for example SourceAFIS or
NIST NBIS) over the lab's consented validation set **outside this repository**. Write the
comparison scores to a CSV with `genuine` (1 or 0) and `score` columns, plus an optional
`group` column, then run:

```bash
ridge-validate scores.csv --fmr 0.001 --fmr 0.0001 --ftx-attempts 400 --ftx-failures 12 -o validation.json
```

The report gives FNMR at each target FMR, with Wilson 95 % intervals and a rule-of-30
check. It also gives the DET curve, EER, the failure-to-extract rate, and the same metrics
per group (the bias check).

## How it works

1. **Find the finger** by skin colour (Lab a\* channel plus an Otsu threshold). If skin
   and background don't separate (a grayscale photo or a skin-coloured background), the
   whole photo is searched.
2. **Measure the ridge spacing** from the spectra of small patches. The photo is then
   rescaled so ridges are 12 px apart, which makes every later step independent of
   camera resolution and distance.
3. **Flatten lighting and contrast**, estimate the local ridge direction, and filter with
   an orientation-adaptive Gabor filter bank (Hong, Wan & Jain, 1998). This is done twice.
4. **Keep only real ridges**: areas where the ridge-frequency energy points in one
   direction *and* repeats the way ridges do. This rejects noise, the finger's outline,
   skin creases and background lines.
5. **Binarize** at the photo's resolution and save the ridges as white on black.

Only the parts of the finger where ridges are actually visible are extracted. Blurry
areas are left out rather than invented.

## Tips for good photos

These apply when photos are taken for validation; case photos are what they are.

- One finger per photo, filling a good part of the frame (macro mode helps).
- Tap to focus on the fingertip: the pad is curved, so only part of it is ever perfectly sharp.
- Soft light from the side (a window) beats a direct flash; avoid strong glare.
- A plain background that isn't skin-coloured, and a scale ruler in the frame.

## Development

```bash
.venv/Scripts/python -m pip install --require-hashes --no-deps -r requirements.lock -r requirements-dev.lock
.venv/Scripts/python -m pip install --no-deps --no-build-isolation -e .
.venv/Scripts/python tools/gate.py all     # docs lint format typecheck test sast deps secrets licenses sbom gui
```

The `gui` gate needs Node.js and npm, the Rust toolchain, `cargo-audit`, `cargo-deny` and
`cargo-cyclonedx` (`cargo install cargo-audit cargo-deny cargo-cyclonedx --locked`). It writes
the npm and Cargo SBOMs to `build/`.

The `secrets` gate needs [gitleaks](https://github.com/gitleaks/gitleaks) on PATH, and
`deps` needs network access. Tests use synthetic images only (`tests/synthetic.py`).
`tests/golden/` freezes the v0 results per CPU architecture (x86-64, arm64), and the test
suite also runs v0 from git history to require bit-identical results on every machine.
Regenerate goldens with `tools/make_golden.py` (arm64: the `golden` workflow) only for an
intended, documented change.

To update the locks:

```bash
python -m uv pip compile pyproject.toml --extra heic --universal --python-version 3.12 --generate-hashes -o requirements.lock
python -m uv pip compile requirements-dev.in --universal --python-version 3.12 --generate-hashes -o requirements-dev.lock
```

## Privacy and evidence

Finger photos and extracted prints are special-category biometric data, and potentially
evidence. Never commit them: `.gitignore` blocks image and fingerprint-exchange formats,
and the `docs` gate fails if one is tracked. Never use real case material for
development or testing.
