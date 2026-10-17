# Handoff_4.md

Date/time (ISO 8601 with offset): 2026-10-17T09:20+02:00
Author/agent: Claude Code (claude-opus-5-5), autonomous development window
Project: Ridge
Branch: `hardening-followups` (stacked on `m1-case-store`) → PR into `main` after M1 merges
Base commit: `c025ead`

## 1. Scope

Close the open items Handoff_1 and Handoff_3 listed as missing tests or controls:

- **W1 output-folder containment.** `ridge` validates inputs before it creates the output folder. It refuses an output folder that is equal to or inside an input folder, or equal to the folder of an input file, so folders of original evidence are never written to. Write-path audit finding F-5 is closed.
- **Property-based fuzzing** (`tests/test_fuzz.py`, hypothesis):
  - random bytes and mutated or truncated PNG, JPEG, TIFF, BMP and WebP files into `decode_image`;
  - random base64 and raw lines into the custody-log parser.
- **Fuzzer findings fixed:**
  1. Malformed TIFF metadata made Pillow emit `UserWarning`s that escaped the decoder. They become exceptions under `-W error` and otherwise print uncontrolled output. Decoder warnings are now captured during decoding and reported through `logging` (`ridge.image_io`). Regression test `test_decoder_warnings_are_logged_not_raised`.
  2. A custody line that is not valid base64, UTF-8 or JSON raised a generic `ValueError`. It now raises `IntegrityError` like any other tampering.
- `.hypothesis/` is ignored by git.

## 2. Evidence

```bash
python tools/gate.py all   # Windows x86-64: all 10 gates passed; 186 passed, 2 skipped; coverage 96.17%
```

CWE: CWE-20, CWE-754 (decoder warnings, custody parsing), CWE-73/CWE-22-adjacent (W1: writing into evidence folders).

## 3. Forensic impact

- Output pixels are unchanged.
- Behaviour change: `ridge photos/ -o photos` (outputs into the input folder) is now a usage error (exit 2). It was allowed in v0.

## 4. Open items

- Longer fuzzing campaigns (atheris, nightly) are not set up; the hypothesis budget is 150 examples per property in CI.
- The custody-log tail-truncation limit remains (R-5, OQ-8).

## 5. First thing to do

Run `python tools/gate.py all`.
