# ADR-014: Opt-in method variants, off by default, recorded in every report

| Field | Value |
| --- | --- |
| Status | **Proposed** 2026-10-24 by engineering during the autonomous window granted by the product owner (Handoff_35 section 1). Decision pending with the Forensic Quality Manager (interim: the product owner) |
| Context | PRD §8.7 (FR-44 to FR-47), §12 (validation), NFR-3 and ADR-009 (per-architecture reproducibility, goldens), forensic standard §6 (method constants) and §13 (revalidation) |

## Problem

The AFIS-readiness assessment of 2026-10-24 found four changes to the extraction method that are likely to raise the usable print area or the matcher's chances, but each changes output pixels:

1. the colour plane the ridge signal is taken from, and a mask for specular highlights (FR-44);
2. rotation of the finger to upright before extraction (FR-45);
3. a local ridge-frequency map with a multi-frequency Gabor bank instead of one global spacing (FR-46);
4. rectification of the finger's curvature and perspective (FR-47).

A pixel-affecting change is a method change: it needs an ADR, new goldens with human review, and a revalidation decision (forensic standard §13), and the goldens must never be updated to make tests pass. None of the four has been measured on a benchmark yet, so none can be the default.

## Decision

Each variant is implemented behind an explicit option (`ridge.pipeline.options.MethodOptions`), **off by default**:

- with every option at its default the pipeline runs exactly the characterised code path; the stored goldens and the live-v0 comparison are unchanged and keep guarding it;
- every job report records the options under `parameters.options` and what they did under `measurements` (for example the plane used, the share of the finger removed as highlights, the rotation applied); `ridge-case reproduce` rebuilds them, and reports from before this ADR reproduce with the defaults;
- the CLI, the sidecar and the Rust core validate the options at each boundary; the GUI groups them under "Method variants (unvalidated, off by default)" and the readable reports carry a "Variants" line that says they are not covered by the validation;
- variants never widen what Ridge claims: they change how the ridge image is computed, not what it means.

Making a variant a default, or recommending it in the limits of use, is a separate decision for the Forensic Quality Manager after the benchmark (PRD §12), recorded as a new ADR with the golden update it entails.

## Consequences

- The pilot and the validation study can compare variants against the baseline on the same photos, because every report says which were on.
- Examiners can use a variant in casework only within the limits of use the FQM states; until then the reports' "unvalidated" wording stands.
- The pipeline gains optional code paths; each has its own tests (success, refusal, determinism) and a default-identity test that proves the baseline is untouched.
- Cross-architecture reproducibility (ADR-009) applies to variants as to the baseline: results are compared per CPU architecture.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| A. Make the variants the new default now | Simplest for examiners | Changes goldens and the method without a benchmark; violates the forensic standard §13 and ADR-009 |
| B. Opt-in variants, recorded, off by default (chosen) | Baseline untouched; measurable; reversible | More code paths to test and explain |
| C. Keep the variants out of Ridge until validated | Smallest code | Nothing to measure in the pilot; the validation study would have to compare hypothetical methods |
