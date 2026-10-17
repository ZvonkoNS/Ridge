# Handoff_6.md

Date/time (ISO 8601 with offset): 2026-10-17T09:50+02:00
Author/agent: Claude Code (claude-opus-5-5), autonomous development window
Project: Ridge
Branch: `m3-minutiae` (built on `m2-integration`) → PR into `main` after PR #4

## 1. Scope

**M3 minutiae** (PRD FR-40). Exchange formats (FR-41) remain open (OQ-4).

| Part | What |
| --- | --- |
| `ridge.minutiae.skeleton` | Vectorised Zhang-Suen thinning (bounded iterations); crossing numbers |
| `ridge.minutiae.extract` | Endings (CN 1) and bifurcations (CN 3); directions by tracing each branch about one ridge spacing; quality heuristic from the distance to the print border. Removes, scaled to the ridge spacing: border artefacts, spurs (ending within 0.8 spacings of a bifurcation), broken-ridge ending pairs (< 1 spacing), bridge or hole bifurcation pairs (< 0.6 spacings). Hard bound of 1000 candidates |
| `to_export_space` | Maps minutiae into the mirrored 500 ppi export (coordinates and angles) |
| Case jobs | `ridge-case extract --minutiae` stores a `ridge.minutiae/1` JSON artefact (print space, plus export space when there is an export). The report gets a `minutiae` summary labelled "unvalidated … not used for any matching" |

Conventions:

- Coordinates are print-image pixels, origin top-left.
- Angles are degrees counter-clockwise from +x.
- Endings point away from their ridge; bifurcations point into their fork.

## 2. Evidence

- Synthetic drawings with known minutiae: one ending, one bifurcation, a broken ridge (no minutiae), parallel ridges (no minutiae).
- Directions within 20°; positions within a few pixels.
- Case-job tests: the stored JSON equals the library output for the same photo.
- The full gate run is recorded in the PR.

## 3. Forensic impact

- Off by default. Print and export pixels are unchanged.
- Minutiae are **unvalidated** (new profile exception). The format is Ridge's own JSON, not ISO/IEC 39794-2 or ANSI/NIST-ITL Type-9 (OQ-4).
- Nothing in Ridge matches minutiae against anything.

## 4. Open items

- Benchmark against a reference extractor (e.g. NIST NBIS `mindtct`) on the consented validation set.
- Exchange-format export once OQ-4 is answered.
- Minutiae quality is a heuristic, not ISO/IEC 29794.

## 5. First thing to do

Run `python tools/gate.py all`, then read `src/ridge/minutiae/extract.py`.
