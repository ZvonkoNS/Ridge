# Ridge — Architecture

| Field | Value |
| --- | --- |
| Document | `docs/architecture.md` (IEEE 1016-style design description) |
| Version | 0.1 (draft for owner review) |
| Date | 2026-10-16 |
| Status | Draft. §6, §8, §9.1 and §9.3 describe the implementation (M0, M1); §7.3 and the GUI are the target design for M2–M4. |
| Requirements | [`docs/prd.md`](prd.md) (IDs FR-, SEC-, PRIV-, NFR-) |
| Standards | [`Instruction_documentation/Project_Standards_Profile.md`](../Instruction_documentation/Project_Standards_Profile.md) |

Each section is marked **[Implemented]** (in the repository now) or **[Planned]** (design target).

---

## 1. Context

```mermaid
flowchart LR
  subgraph Lab["Forensic lab (offline examiner workstation)"]
    EX([Fingerprint examiner])
    R[Ridge<br/>CLI / library / GUI]
    KS[(OS keystore<br/>DPAPI / Keychain / Secret Service)]
    CS[(Encrypted case store)]
  end
  SRC[[Case photos<br/>from upstream acquisition]] -->|files + upstream hashes| R
  EX -->|operates| R
  R <--> KS
  R <--> CS
  R -->|logged export: matcher-ready images, signed reports| OUT[[Exports for manual comparison]]
  OUT -. examiner compares manually .- AFIS[(NAFIS / AFIS<br/>no connection from Ridge)]
```

Ridge has **no network interface**: no AFIS connection, no updates, no telemetry (SEC-1). The only exchange with the outside world is files: evidence imported by the examiner, and exports and reports written deliberately and logged.

## 2. Architectural drivers

| Driver | Source | Architectural consequence |
| --- | --- | --- |
| Evidence integrity, custody, reproducibility | FR-21–FR-25, G-2, G-3 | Content-addressed evidence, hash-chained custody log, signed reports, pinned toolchain, deterministic pipeline. |
| Special-category biometric data | PRIV-1–3, SEC-3 | Encryption at rest with dual-factor key wrapping; a single controlled export path; minimisation. |
| Offline single-examiner workstation | A-1, A-2, SEC-1 | No server, no sockets; the OS account plus case passphrase is the access control; local files. |
| Cross-platform desktop (Win/Linux/macOS) | NFR-5 | Pure-Python core on wheels; Tauri for the GUI; paths via `pathlib`; CI on three OSes. |
| Existing validated-to-be algorithm | FR-1 | Behaviour-preserving refactor; golden characterization tests guard every change. |
| Maintainability under fast delivery | NFR-6, R-8 | Small typed modules, strict gates, explicit dependency rules between layers. |

## 3. Quality attribute scenarios

| ID | Attribute | Stimulus → response | Measure |
| --- | --- | --- | --- |
| QA-1 | Integrity | Someone edits a byte of an output, report or log entry → `ridge case verify` reports the exact artefact. | 100% of tamper fixtures detected. |
| QA-2 | Reproducibility | A defence expert re-runs a job from its report with the same release on the same OS and CPU architecture → identical output. | Hash-equal output (same OS and architecture). |
| QA-3 | Security | A crafted image (decompression bomb, wrong format, truncated) is imported → rejected before full decode, with bounded memory and a typed error. | No crash; peak memory below the limit plus a constant. |
| QA-4 | Confidentiality | A workstation disk is copied → no biometric plaintext is readable without the keystore entry and the passphrase. | Storage inspection test. |
| QA-5 | Isolation | Compromised GUI JavaScript tries to read arbitrary files or reach the network → blocked by the Tauri capability allow-list and CSP; the sidecar accepts only schema-valid RPCs. | IPC denial tests. |
| QA-6 | Maintainability | A new export format is added → only `export/` and the report schema change. | No pipeline or case-store change. |

## 4. Solution strategy

1. **Pure, deterministic core.** The pipeline is a set of pure functions over NumPy arrays: no I/O, no global state, no clock, no randomness.
2. **Hexagonal edges.** All I/O sits at the edges: decoding, encoding, filesystem, keystore, crypto, sidecar RPC. Each edge is a small adapter with strict validation.
3. **Evidence as content-addressed, append-only data.** Originals and derived artefacts are named by SHA-256, and every action is a custody-log entry. Nothing is updated in place.
4. **Trust boundaries made explicit.** Image bytes, RPC messages and the WebView are untrusted. The Python core and the Tauri Rust core are trusted.
5. **Defense in depth for biometrics.** OS full-disk encryption, plus case-store encryption, plus a single logged export path, plus no network.

## 5. Building blocks (container view)

```mermaid
flowchart TB
  subgraph GUI["gui/ — Tauri v2 [Planned M4]"]
    WV["WebView: React + TypeScript<br/>(UNTRUSTED)"]
    RC["Rust core: commands,<br/>capability allow-list (trusted)"]
  end
  subgraph PY["src/ridge — Python core"]
    CLI["cli.py [Implemented]"]
    SC["sidecar/ JSON-RPC over stdio [Implemented M4]"]
    APP["case/jobs.py + export_step.py app services [Implemented M1-M2]"]
    PIPE["pipeline/ pure extraction [Implemented]"]
    IO["image_io.py bounded decode/encode [Implemented]"]
    CASE["case/store.py encrypted store [Implemented M1]"]
    CUST["case/custody.py hash-chained log [Implemented M1]"]
    REP["case/jobs.py signed JSON report [Implemented M1]"]
    EXP["export/ 500 ppi, polarity, mirror [Implemented M2]"]
    QLT["quality/ NFIQ 2 adapter [Implemented M2]"]
    MIN["minutiae/ Zhang-Suen + crossing number [Implemented M3]"]
    KEY["case/keys.py + identity.py [Implemented M1]"]
  end
  WV -- "invoke (allow-listed)" --> RC
  RC -- "spawn + stdio" --> SC
  CLI --> APP
  SC --> APP
  APP --> PIPE
  APP --> IO
  APP --> CASE
  APP --> CUST
  APP --> REP
  APP --> EXP
  APP --> QLT
  CASE --> KEY
  REP --> KEY
```

## 6. Module structure and dependency rules [Implemented for M0 modules]

```text
src/ridge/
  __init__.py          Public API: extract_fingerprint, ExtractionResult, errors, __version__
  __main__.py          python -m ridge
  cli.py               Argument parsing and the per-file loop (thin)
  errors.py            Typed error hierarchy (RidgeError → InputError, ParameterError, OutputError, ExtractionError, …)
  image_io.py          Allow-listed, size-bounded decoding; atomic, no-overwrite encoding
  debug.py             Writing of debug images (intermediate arrays → files)
  pipeline/
    imgutil.py         masked_blur, disk, largest_component, fill_holes, remove_specks
    mask.py            finger_mask (skin colour, Lab a*, Otsu)
    period.py          estimate_period (local FFT)
    gabor.py           gabor_bank, ridge_orientation, oriented_filter
    quality.py         periodicity and print-region selection
    extract.py         extract_fingerprint orchestration → ExtractionResult
fingerprint_extract.py Backward-compatible shim (legacy CLI and legacy function signature)
tests/                 pytest; synthetic data generator; golden characterization arrays
tools/gate.py          Named quality gates (see §12)
```

Dependency rules (enforced by review now; an import-linter contract is planned):

| Module | May import | Must not import |
| --- | --- | --- |
| `pipeline/*` | `numpy`, `cv2`, `ridge.errors`, sibling pipeline modules | `image_io`, `cli`, filesystem, `PIL`, clock, randomness, network |
| `image_io` | `PIL`, `numpy`, `cv2` (encode only), `ridge.errors` | `pipeline`, `cli` |
| `debug` | `image_io`, `numpy`, `cv2` | `cli` |
| `cli` | everything above | — (nothing imports `cli`, except `__main__` and the shim) |
| `sidecar/*` [Implemented M4] | `ridge.case`, `ridge.image_io`, `ridge.errors` | sockets or any network module (offline test), `cli` |
| `minutiae/*` [Implemented M3] | `numpy`, `cv2`, `ridge.errors`, `ridge.pipeline.imgutil` | file I/O, `case`, `cli`; no matching of any kind |
| `export/*`, `quality/*` [Implemented M2] | `numpy`, `cv2`, `PIL` (PNG pHYs), `ridge.errors`, `ridge.pipeline` (result type only); `quality` runs one configured external tool (absolute path, argv list, no shell, timeout) | file I/O except the NFIQ 2 temporary copy in a caller-given folder; `case`, `cli` |
| `case/*` [Implemented M1-M2] (`crypto`, `keys`, `identity`, `custody`, `store`, `jobs`, `export_step`, `verify`, `dispose`, `cli`) | `cryptography`, `argon2-cffi`, `keyring`, `rfc8785`, `ridge.errors`, `ridge.image_io`; `jobs` also `ridge.pipeline` | `cli` modules of other packages; nothing outside `case` imports `case.cli` |

Files are kept to about 300 lines or fewer, and functions do one job. Documentation is never imported by runtime code.

## 7. Runtime views

### 7.1 Extraction (M0, current CLI) [Implemented]

```mermaid
sequenceDiagram
  participant U as Examiner
  participant C as cli.py
  participant I as image_io
  participant P as pipeline.extract
  participant D as debug
  U->>C: ridge photo.jpg [-o dir] [options]
  C->>I: load_image(path, limits)
  I-->>C: BGR uint8 array (EXIF-oriented) or InputRejectedError/DecodeError
  C->>P: extract_fingerprint(bgr, params)
  P-->>C: ExtractionResult(image, period, found_finger, debug arrays?)
  opt --debug
    C->>D: write_debug(result, stem, outdir)
  end
  C->>I: save_image(out_path, image, overwrite=False) (atomic)
  C-->>U: one summary line per file; exit 0 / 1 (failures) / 2 (usage) / 3 (internal error)
```

### 7.2 Case job (M1) [Implemented; M2 export steps planned]

1. `ridge case open` unlocks the case DEK: the passphrase goes through Argon2id to produce a KEK, combined with the keystore device secret (§9.2).
2. The job loads the evidence blob by hash, decrypts and verifies it (AES-GCM tag plus SHA-256), then decodes it via `image_io` with limits.
3. The pipeline runs, then the export transforms (polarity, mirror, 500 ppi), then NFIQ 2 (optional).
4. Outputs are encrypted and stored content-addressed. The report is built (§8.3), canonicalised (RFC 8785 JCS) and signed (Ed25519).
5. Custody entries are appended for each step: `job.start`, `evidence.read`, `artefact.write`, `report.sign`, `job.end`. The chain head is signed at `job.end`.
6. Any failure aborts the job, writes a `job.failed` entry with its category, and leaves no partial artefacts (atomic rename).

### 7.3 GUI ↔ sidecar (M4) [Sidecar implemented; Rust core and WebView planned]

Implemented in `src/ridge/sidecar/` (`ridge-sidecar`, protocol `ridge.sidecar/1`):

| Method | Params (unknown fields refused) | Result |
| --- | --- | --- |
| `ridge.version` | – | Ridge and protocol versions |
| `session.unlock` | `store` (absolute), `case_id` (UUID), `passphrase` | Case reference, retention, hold. **Only the Rust core sends this**, from a native prompt, never from the WebView |
| `identity.create` | `store` (absolute), `passphrase` | Key id and public key of the new examiner identity (first run). **Rust core only**, from a native prompt |
| `case.create` | `store`, `reference`, `legal_basis`, `retention_until` (YYYY-MM-DD), `passphrase` | New case id; the passphrase must unlock the identity. **Rust core only** |
| `session.lock` / `session.status` | – | Locks the case (also done at end of input and after 15 minutes without requests) / unlocked state and idle timeout |
| `case.items` / `case.verify` | – | Stored items / verification result |
| `case.import` | `path` (absolute, from a native file dialog) | Evidence item |
| `job.run` | `evidence`, extraction options, `export`, `mirror`, `ppi`, `ruler`, `minutiae` | Outputs, measurements, export, quality, minutiae summary |
| `preview.get` | `sha256`, `max_side` 16–2048 | Bounded PNG (base64) for display; the read is logged |
| `case.export` | `sha256`, `dest` (absolute), `overwrite` | Logged plaintext export |

Errors use JSON-RPC codes: -32700 parse, -32600 invalid request, -32601 unknown method, -32602 invalid params, -32000 refused by Ridge (safe message), -32603 internal (exception type only).

- The Tauri Rust core spawns the frozen Python sidecar (`ridge-sidecar`, PyInstaller one-folder build, signed) as a child process. There are **no ports**.
- The protocol is JSON-RPC 2.0, one message per line, UTF-8, ECMA-404 JSON. Each message is at most 1 MiB. Images are passed by case-store reference, never inline; previews are bounded base64 PNGs.
- Each method has a strict schema (unknown fields rejected), an explicit allow-list of methods, and per-method size and time limits. The sidecar exits when stdin closes.
- The WebView can only call allow-listed Tauri commands, which forward validated requests to the sidecar. It has no `fs`, `shell` or `http` capabilities.

## 8. Data architecture [Implemented M1]

### 8.1 Case store layout

```text
<store_root>/                       examiner-chosen, on an FDE-protected volume
  identity.json                     examiner Ed25519 public key + sealed private key (§9.3)
  <case_uuid>.disposal.json         kept after disposal: no personal data (§8.2)
  <case_uuid>/
    case.json                       schema, case id, KDF parameters, salt, wrapped DEK (no plaintext keys, no personal data)
    meta.enc                        case reference, legal basis, retention date, legal hold (encrypted)
    evidence/<keyed-name>.enc       original evidence, encrypted; never rewritten
    artefacts/<keyed-name>.enc      derived outputs and debug images
    reports/<job_uuid>.json.enc     signed job report, encrypted (no pixels, but personal data by reference)
    reports/<job_uuid>.json.sig     detached Ed25519 signature over the plaintext canonical report
    custody.jsonl.enc               append-only hash-chained log; each line AES-GCM encrypted
    LOCK                            single-writer lock file
```

Writes are atomic and never replace existing blobs (`image_io.publish`). The custody log is the index of everything stored: listing, verification and export resolve items through it. Evidence and artefacts are identified by the SHA-256 of their **plaintext**, computed before encryption. On disk they are named `HMAC-SHA256(name_key, sha256)` with `name_key` derived from the case DEK, so file names do not reveal whether a known image is in a store, yet duplicates are still detected. Verification needs the case unlocked (OQ-13).

### 8.2 Encryption envelope

| Item | Choice |
| --- | --- |
| Cipher | AES-256-GCM (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`), 96-bit random nonce per file, single-shot (files are bounded by FR-9). |
| Associated data | `ridge-blob-v1 \| case_id \| role \| plaintext sha256` for blobs, `ridge-custody-v1 \| case_id \| seq` per custody line, `ridge-dek-v1 \| case_id` for the wrapped key. A blob cannot be swapped between cases, roles or positions. |
| Format | `magic "RDG1" \| version \| nonce \| ciphertext+tag`. |
| DEK | 256-bit from `secrets.token_bytes`, one per case. |
| KEK | `HKDF-SHA256(Argon2id(passphrase, salt; t=3, m=256 MiB, p=4) ‖ device_secret, info="ridge-kek-v1\|<purpose>")`, purpose = `case\|<case_id>` or `identity`. Stored parameters are unauthenticated, so they are bounded both ways (t 3-10, m 64 MiB-1 GiB, p 1-16) before Argon2 runs. One examiner passphrase unlocks the identity and all of that examiner's cases (`init` checks this). |
| Sub-keys | HKDF from the DEK: `ridge-data-v1` (blobs, metadata, reports), `ridge-names-v1` (keyed file names), `ridge-custody-v1` (custody lines). |
| Device secret | 256-bit random, one per OS account, stored in the OS keystore via `keyring` (Windows Credential Locker / Keychain / Secret Service). |
| Recovery | **Not implemented**: without the passphrase and the OS account a case is unrecoverable. An optional sealed recovery key waits for the Security Owner's decision (OQ-12). |
| Disposal | `ridge-case dispose`: refused under legal hold or before the retention date (unless `--before-retention`); needs the case id typed back and a reason code from a fixed list. Order: (1) `case.json` becomes an `erasing` stub without the wrapped DEK (crypto-erasure), (2) the `<case_id>.disposal.json` record is published, (3) the folder is deleted; re-running finishes an interrupted disposal. The record holds the examiner's key id and the reason code, no names or free text. The device secret is shared by all cases of the account and is not deleted. |

There is no custom cryptography: only library AEAD, KDF and signature primitives, with parameters recorded in `case.json` and `identity.json`.

### 8.3 Job report (JSON, ECMA-404) — schema outline

```json
{
  "schema": "ridge.job-report/1",
  "job_id": "uuid",
  "case_id": "uuid",
  "case_reference": "string",
  "created_utc": "2026-10-16T19:12:00Z",
  "ridge": {"version": "0.2.0", "python": "3.13.5", "platform": "Windows-11-…", "machine": "AMD64",
            "dependencies": {"numpy": "…", "opencv": "…", "pillow": "…", "cryptography": "…"}},
  "input": {"sha256": "…", "label": "IMG_0042.HEIC", "format": "HEIF", "size_px": [4032, 3024]},
  "parameters": {"period": null, "min_quality": 0.25, "flip": false, "crop": true, "debug": false,
                 "export": {"enabled": true, "mirror": true, "target_ppi": 500, "ruler": [12, 40, 812, 44, 40]}},
  "measurements": {"ridge_period_px": 17.9, "found_finger": true, "output_scale": 1.0},
  "export": {"produced": true, "sha256": "…", "ppi": 500, "factor": 0.98,
             "transforms": ["polarity:dark-ridges", "mirror:horizontal", "scale:500ppi:ruler"],
             "scale": {"method": "ruler", "px_per_mm": 20.0, "uncertainty_pct": 0.25}},
  "quality": {"nfiq2": {"computed": true, "score": 54, "version": "…", "label": "indicative only: …"}},
  "outputs": [{"role": "print|debug|export", "label": "…", "sha256": "…", "size": 12345}],
  "custody_head": "head of the custody chain when the report was built",
  "signer": {"key_id": "…", "public_key": "base64 Ed25519"},
  "disclaimer": "Image enhancement only. Ridge does not identify anyone and draws no conclusions."
}
```

All timestamps are ISO 8601 UTC with a `Z` suffix. The report is canonicalised with RFC 8785 before signing. Without a ruler the scale is `ridge-period` (assumed 0.47 mm ridge distance, ±15 %, both to be validated, `assumed_ridge_period_mm` recorded). An impossible scale gives `"export": {"produced": false, "reason": …}` without failing the job; `--no-export` gives `null`. NFIQ 2 that is not configured or fails gives `{"computed": false, "reason": …}`.

### 8.4 Custody log entry

```json
{"seq": 42, "prev": "sha256(prev entry canonical bytes)", "ts_utc": "2026-10-16T19:12:03Z",
 "actor": "os-user@workstation-id", "action": "artefact.write",
 "target": {"sha256": "…", "role": "export"}, "job_id": "uuid", "result": "ok"}
```

`seq` is strictly increasing and `prev` links the chain. The chain head is signed at the end of each job and on `verify`. Clock trust is limited offline, so out-of-band countersigning or timestamping by a lab system is an open item (OQ-8, R-5); Ridge never contacts a timestamp server itself.

## 9. Security architecture

### 9.1 Input handling [Implemented M0]

| Control | Implementation | Requirement / weakness |
| --- | --- | --- |
| Format allow-list by content | `PIL.Image.open(fp, formats=ALLOWED)`. Exotic plugins (EPS/Ghostscript, PSD, …) are never reached; the extension is ignored. | FR-8; CWE-434, CWE-20 |
| Bounded reading | Open with `O_NONBLOCK` (no hang on FIFOs); `fstat` regular-file and size check; capped read of at most `max_bytes + 1`; decode from memory; hard caps that configuration cannot exceed; minimum side 32 px. | FR-9; CWE-400, CWE-770 |
| Decompression-bomb guard | Header dimensions checked against `max_pixels` before `load()`; `Image.MAX_IMAGE_PIXELS` set to the limit; Pillow bomb warnings escalated to errors. | FR-9; CWE-409 |
| Single decoder, explicit errors | No fallback to a second decoder; truncated or corrupt input raises `DecodeError`. | FR-10; CWE-390, CWE-755 |
| Metadata stripping | Outputs are encoded from pixel arrays only; EXIF orientation is applied, then discarded. | FR-12 |
| Safe output writing | Private temporary file in the target folder and `fsync`, then publish with `os.link`, which fails atomically if the target exists (no check-then-write race). File systems without hard links fall back to exclusive create (`open("xb")`). `os.replace` only with `--overwrite`; temporary files always removed; POSIX modes `0o700` (dirs) and `0o600` (files). | FR-11; CWE-367, CWE-732 |
| Directory traversal | Folder mode lists regular files only and skips symlinks, reporting every skipped file; output names derive from `Path.stem` (no separators). | CWE-22, CWE-59 |
| Pipeline memory bounds | Library arguments validated (`ParameterError`); finger regions under ~75 px refused; the period-measurement rescale capped at 16 MP; work areas above 40 MP refused (`WorkAreaTooLargeError`). v0 could try to allocate many GiB for a thin skin blob. | FR-13; CWE-789, CWE-400 |
| Headless OpenCV | `opencv-python-headless`: no GUI/highgui backends in the dependency tree. | Attack-surface reduction |

### 9.2 Trust boundaries and threat model (STRIDE)

```mermaid
flowchart LR
  subgraph U["Untrusted"]
    IMG[Image bytes]
    WV[WebView JS]
    CFG[Config files / CLI args / env]
    RPC[RPC messages]
  end
  subgraph T["Trusted"]
    RUST[Tauri Rust core]
    CORE[Python core]
    KS[(OS keystore)]
  end
  IMG -->|TB1 decode limits + allow-list| CORE
  WV -->|TB2 capability allow-list| RUST
  RUST -->|TB3 schema-validated JSON-RPC| CORE
  CFG -->|TB4 typed validation| CORE
  CORE <-->|TB5 OS-protected| KS
```

| Threat (STRIDE) | Example | Mitigation | Verification |
| --- | --- | --- | --- |
| Spoofing | Another OS user opens the case store | Keys need both the OS-keystore secret (per OS user) and the passphrase | Key tests; access test with another user (manual) |
| Tampering | Edited output, report or log | Content addressing, AES-GCM tags, hash chain, Ed25519 signatures, `verify` | Tamper fixtures (QA-1) |
| Repudiation | "That job was never run like that" | Custody log with actor, parameters, versions; signed reports | Report schema tests |
| Information disclosure | Plaintext biometrics on disk, in logs or temp files | Encryption at rest, single export path, no temp plaintext, log redaction, metadata stripping | Storage inspection, log tests |
| Denial of service | Decompression bomb, huge RPC payloads | Size and pixel limits, RPC size and time limits | Hostile-input tests (QA-3) |
| Elevation of privilege | WebView XSS calling file/shell APIs; malicious decoder plugin | No `fs`/`shell`/`http` capabilities, strict CSP, decoder allow-list, headless OpenCV | IPC denial tests; config review |

The full ASVS 5.0 L3 mapping (applicable chapters only, with N/A rationale for server-only chapters) is kept in the standards profile.

### 9.3 Key and signing management [Implemented M1]

- The signing key is Ed25519, one per store (`ridge-case identity init`), i.e. per examiner workstation until OQ-9 decides otherwise. The private key is sealed under an identity KEK (passphrase + device secret, purpose `identity`); `ridge-case identity show` prints the key id and public key for the lab registry. Reports and custody heads are verified against the store's identity key.
- Rotation: new reports use the new key, and old reports remain verifiable with registered old public keys.
- Passphrase policy follows the NIST SP 800-63B approach: at least 15 characters, checked against a breached-password list where available offline, with no composition rules. Argon2id parameters are recorded per case.

### 9.4 Supply chain

- Dependencies are pinned with hashes (`requirements.lock`, `requirements-dev.lock`, pip-tools). Installs use `--require-hashes`.
- Runtime dependencies are minimal: `numpy`, `opencv-python-headless` and `pillow` (plus `pillow-heif` as an extra). M1 adds `cryptography`, `argon2-cffi` and `keyring`.
- CI runs `pip-audit`, a licence allow-list, a CycloneDX SBOM, CodeQL, gitleaks, dependency review and OpenSSF Scorecard. Actions are pinned by commit SHA.
- Releases (M5) are built only from signed tags, produce signed artifacts, and are installed offline after signature verification.

## 10. Deployment view

| Release | Artifact | Install |
| --- | --- | --- |
| M0–M3 | Python wheel + hashed lock file | Offline: `pip install --no-index --require-hashes -r requirements.lock` from a vetted wheelhouse, then `pip install --no-deps ridge-*.whl`. |
| M4+ | Tauri bundle (MSI / DMG / AppImage) with the signed PyInstaller sidecar | Signed installer; Tauri updater disabled (offline only). |

The reference workstation is to be specified (OQ-11).

## 11. Cross-cutting concepts

- **Errors:** `RidgeError` subclasses with safe, actionable messages. The CLI exits 0 (all ok), 1 (some inputs failed), 2 (usage/config error) or 3 (internal error: a bug, reported per file while the batch continues). Stack traces appear only with `--verbose` and never contain biometric data.
- **Logging:** stdlib `logging`, structured key=value, ISO 8601 UTC timestamps. Logs record hashes, IDs and categories only, never pixel data, passphrases or keys (SEC-5).
- **Configuration:** CLI flags first, then a `RIDGE_*` environment variable or config file (validated, typed). Defaults are safe. Unknown keys are rejected.
- **Numerics:** the float32 pipeline follows IEEE 754 with no nondeterministic parallel reductions. Reproducibility and method validation are per (release, OS, CPU architecture) (NFR-3, ADR-009). Behaviour preservation is proven on every platform by running v0 from git history next to the package and requiring bit-identical results. Stored goldens exist per architecture family (`tests/golden/v0-x86_64.*`, `v0-arm64.*`). On the reference machine they must match exactly; on other CPUs of the same architecture, ≥ 99.9% of output pixels must agree, the ridge spacing to 1e-6 relative and debug images to within 1 grey level on average. Results are not compared across architectures for equality. Instead, the committed golden sets must stay inside a cross-architecture envelope (`tests/cross_arch.py`): same outcomes and finger detection, ridge spacing within 1%, output size within 2 px, ≥ 99.8% of output pixels agreeing where the sizes match. The envelope is the difference measured on 2026-10-17 plus a small margin; widening it needs Forensic Quality Manager approval. `python tools/compare_goldens.py` prints the table for the release handoff.
- **Text and paths:** Unicode paths everywhere (`pathlib`, `np.fromfile`/`tofile` for OpenCV I/O); UTF-8 JSON.
- **Time:** UTC everywhere, ISO 8601 with `Z`. No local time in records.

## 12. Verification architecture

| Gate | Command | Applies |
| --- | --- | --- |
| docs | `python tools/gate.py docs` | Required documents exist; AGENTS.md reading order resolves; handoffs consecutive; no runtime import of docs |
| lint / format | `python tools/gate.py lint` / `format` | ruff (incl. bandit "S", bugbear "B" and others) |
| typecheck | `python tools/gate.py typecheck` | mypy `--strict` on `src/` and `tests/` |
| test | `python tools/gate.py test` | pytest with branch coverage ≥ 90% on `ridge` |
| sast | `python tools/gate.py sast` | bandit on `src/` |
| deps | `python tools/gate.py deps` | pip-audit on the hashed lock |
| secrets | `python tools/gate.py secrets` | gitleaks |
| licenses | `python tools/gate.py licenses` | pip-licenses allow-list |
| sbom | `python tools/gate.py sbom` | CycloneDX JSON |
| all | `python tools/gate.py all` | All of the above, fails on first error |

Test layers: characterization (live v0 run, bit-identical on every platform; per-architecture golden arrays), unit (pipeline helpers, I/O limits), hostile input (bombs, truncation, wrong formats, symlinks), CLI behaviour, offline guarantee (socket blocking), and, from M1, crypto, custody and tamper tests. From M2: report schema and determinism. From M4: GUI unit/E2E and IPC denial. Validation benchmarks run outside CI on the consented dataset (PRD §12).

## 13. Architecture decision records

| ADR | Decision | Status | Rationale (short) |
| --- | --- | --- | --- |
| ADR-001 | Offline-only: no network code in any component | Accepted | Biometric data, evidential use, workstation threat model (SEC-1). |
| ADR-002 | Python core; Tauri v2 + React + TypeScript GUI talking to a Python sidecar over stdio JSON-RPC | Accepted | Keeps the existing algorithm; rich UI; no listening sockets; WebView isolated. |
| ADR-003 | Pillow as the sole decoder with a format allow-list; headless OpenCV for processing only | Accepted | Removes decoder fallback and the exotic-plugin attack surface. |
| ADR-004 | Per-case AES-256-GCM DEK wrapped by keystore secret + Argon2id passphrase (HKDF-combined) | Accepted (implemented M1; Security Owner review pending) | Two factors, portable libraries, crypto-erase on disposal. Needs Security Owner approval. |
| ADR-005 | Content-addressed artefacts, hash-chained JSONL custody log, Ed25519-signed RFC 8785 reports | Accepted (implemented M1; Security Owner review pending) | Tamper evidence verifiable with standard tools. |
| ADR-006 | Hash-pinned locks, reproducible builds, release signing | Accepted | Reproducibility and supply-chain integrity. |
| ADR-007 | `src/` layout, pure pipeline, I/O at the edges, ≤ 300-line modules | Accepted | Testability and reviewability; pack modularity rules. |
| ADR-008 | Case store on the filesystem (files + JSONL) rather than SQLite, with keyed (HMAC) file names and all metadata, reports and custody lines encrypted | Accepted (implemented M1; Security Owner review pending) | Fewer moving parts; no plaintext personal data or image hashes on disk. Revisit if querying needs grow. |
| ADR-009 | Reproducibility and validation are per CPU architecture; behaviour preservation is proven against a live v0 run; goldens are stored per architecture (arm64 generated on a CI Apple silicon runner by the `golden` workflow) | Accepted | x86-64 and arm64 SIMD floating point legitimately differ (R-7, observed 2026-10-17); equality would always fail, so a measured cross-architecture envelope guards against further drift instead. |

ADRs move to individual files under `docs/adr/` when they need more than a table row.
