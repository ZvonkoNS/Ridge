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
.venv/Scripts/python tools/gate.py all     # docs lint format typecheck test sast deps secrets licenses sbom
```

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
