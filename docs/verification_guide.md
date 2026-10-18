# Verifying Ridge records

For reviewers, the Data Protection Officer (DPO), the Forensic Quality Manager (FQM) and anyone who receives files exported from Ridge. All checks run offline, without a case store, either from the command line (`ridge-case ...`) or in the GUI (store screen → "Check exported files").

Ridge is an image-enhancement aid. None of these files, and none of these checks, identify anyone or compare fingerprints.

## What you may receive

| File | Made by | Check | What a pass shows |
| --- | --- | --- | --- |
| `report.json` + `report.json.sig` | `ridge-case report --to`, GUI "Export signed report" | `ridge-case check-report report.json` | The report is exactly as the key signed it (RFC 8785 canonical form, Ed25519) |
| `record.json` (processing record) | `ridge-case log --to`, GUI "Export processing record" | `ridge-case check-log record.json` | The custody log is complete up to its last signed head, entries are linked and unchanged, and the record ends with its own signed export |
| `head.json` (custody head) | `ridge-case head --to`, GUI "Export custody head" | `ridge-case check-head head.json [--record later.json]` | The head is signed; with `--record`, a later record still contains it unchanged (nothing was cut off or rewritten after the head) |
| Disclosure package (folder) | `ridge-case package --to`, GUI "Export disclosure package" | `ridge-case check-package FOLDER` | Every file is as signed in the manifest, nothing was added or removed, the record verifies, and each report is the one the custody log signed |
| `limits-of-use.json` + `.sig` | The FQM (`ridge-case limits --sign`) | `ridge-case limits --check FILE` | The limits are well formed and, if signed, signed with the key named |
| `card.json` (key card) | An examiner or the FQM (`ridge-case key-card`, GUI "Register this key") | `ridge-case check card.json` | Whoever made the card held the private key. **Not** who they are |
| `lab-keys.json` (key register) | The laboratory (`ridge-case register-add`) | `ridge-case register --check FILE` | The register is well formed; its SHA-256 identifies the version |

`ridge-case check PATH` (or the GUI card) recognises every kind above by its schema.

## Who signed it

A valid signature shows only *which key* signed. Every file carries its own public key. To know *who* signed, use the laboratory's key register:

```bash
ridge-case check-package FOLDER --register lab-keys.json
```

With `--register` the check names the key's holder. It refuses a key that is not registered, is registered for another role (`examiner` or `fqm`), or was not valid or already revoked on the signing day. Signing times come from the signed files, that is from the signer's own clock. A key used before its revocation could backdate a file; countersigned custody heads (`ridge-case head`, OQ-8) close that gap.

Without a register, compare the key id in the output with the one the laboratory published for the examiner (or pass `--key-id`).

## Readable copies

`--html PATH` on `check-report` and `check-log` writes a readable page **after** the file verified, rendered from the same bytes. Packages contain readable copies of each report and of the processing record. Readable copies:

- are not signed, and say so;
- name the SHA-256 of the signed file they render;
- contain no images and run no scripts;
- show examiner notes (from the custody log) in their own section, marked as not part of the signed report.

The signed JSON files remain the record.

## What no check can show

- That an image is a correct enhancement, or that a print is suitable for comparison. That is the examiner's judgement, within the laboratory's validated limits of use.
- That entries were not removed after the last signed head of a record, unless a countersigned custody head from before the removal exists.
- That the laboratory's key register itself is the right one. Confirm its SHA-256 with whoever keeps it.
