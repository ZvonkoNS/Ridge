# Handoff_11.md

Date/time (ISO 8601 with offset): 2026-10-17T11:15+02:00
Author/agent: Claude Code (claude-opus-5-5), autonomous development window
Project: Ridge
Branch: `m5-store-listing` (built on `m5-compare-reproduce`) → PR #10

## 1. Scope

| Part | What |
| --- | --- |
| `ridge.case.listing` / `ridge-case cases` / sidecar `store.cases` | Lists each case of a store with its id, creation time and state: `active`, `locked` (LOCK present), `erasing` (disposal interrupted), `disposed` (a valid `ridge.disposal/1` record for that id) or `invalid`. It reads only files that are already plaintext: folder names, `case.json` and disposal records. A `case.json` or disposal record that does not match its file name or schema is listed as `invalid`, never trusted or hidden. With this, the GUI's open dialog needs no passphrase, and the sidecar has a back end for every FR-50 flow |
| `ridge-case extract --keep-going` | When one photo is refused, the batch continues: input errors (`InputError`), extraction refusals (`ExtractionError`) and per-photo settings (`ParameterError`). Each refusal is logged as a failed job, and the command ends with a summary and exit code 1. Case-store, integrity, key, custody and output errors always stop the batch (PR #10 review) |

## 2. Evidence

`tests/test_case_listing.py` covers:

- every state;
- that nothing encrypted is revealed (a reference string never appears);
- a mismatched or foreign-schema `case.json`;
- damaged disposal records;
- a missing store.

`tests/test_case_cli.py` covers listing, `--keep-going` past an extraction refusal, and stopping on an integrity error. `tests/test_sidecar.py` covers `store.cases`. `listing.py` has 100 % coverage.

## 3. Standards and forensic impact

- **Confidentiality (ASVS V14, LED):** the listing reveals only data already in plaintext on disk. Case references and legal bases stay encrypted.
- **Integrity (ISO/IEC 27037):** damaged records are surfaced as `invalid`, not presented as completed disposals.
- **Custody:** skipped photos are still recorded as failed jobs, so `--keep-going` loses nothing from the log.

## 4. Open items

- CI is still blocked by the GitHub billing problem; see Handoff_10.
- The Tauri shell (FR-50 to FR-53) still needs the owner's decision on the native passphrase prompt.

## 5. First thing to do

Read `src/ridge/case/listing.py`, then the `PHOTO_REFUSALS` comment in `src/ridge/case/cli.py`.
