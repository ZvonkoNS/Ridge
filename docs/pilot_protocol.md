# Pilot protocol template: Ridge prints searched in an AFIS

Status: template, 2026-10-24. To be completed by the Product Owner, the Forensic Quality Manager (FQM), the Data Protection Officer (DPO) and the AFIS team before any real photograph is processed. Square brackets mark the decisions to fill in.

## 1. Purpose and limits

The pilot measures one thing: when a print that Ridge extracted from a photograph of a finger is searched in the AFIS named in OQ-4, how often does the true mate appear in the candidate list, and at which rank. The measure is the rank-k hit rate with its confidence interval, and the cumulative match characteristic (CMC) curve, as in ISO/IEC 19795-1 for identification systems.

The pilot does not validate Ridge as a method, does not accredit it, does not establish that any search result is an identification, and does not decide casework. Every candidate the AFIS returns is reviewed and concluded by a qualified examiner under the laboratory's existing procedures; the pilot only records where the known mate appeared. A pilot result is a measurement under the pilot's conditions; its use in a validation plan is the FQM's decision (PRD §12, OQ-7).

## 2. Roles

| Role | Holder | Responsibilities |
| --- | --- | --- |
| Product Owner | [name] | Approves the protocol, the arms and the report. |
| Forensic Quality Manager | [name] | Approves the data source and the method; decides whether results feed the validation plan. |
| Data Protection Officer | [name] | Approves the legal basis, the DPIA entry, retention and access for the pilot data (OQ-1, OQ-2, OQ-6). |
| AFIS team contact | [name] | Runs or supervises the searches; exports ranks; confirms the test database or sandbox (questionnaire E4). |
| Examiners | [names] | Capture or select photographs, run Ridge, prepare submissions, review candidates. |
| Engineering | [name] | Provides the software build, the analysis tool and the report template. **Never sees, receives or handles any photograph, print or result that derives from a real person.** Coding agents are bound by the same rule (`AGENTS.md`). |

## 3. Preconditions

1. OQ-4 answered: accepted format, resolution, polarity, record fields and candidate-list access are known (`docs/afis_integration_questionnaire.md`).
2. The data decision of section 4 is taken and recorded by the DPO and the FQM, with the consent form or the case-selection rule attached.
3. A Ridge release build is installed on a workstation of a validated architecture (OQ-15), with `ridge-case verify` passing on an empty case store; the build's version and the workstation's architecture are written into the pilot record.
4. A pilot case store is created for the pilot only, under the retention period the DPO sets; nothing from it enters a casework store.
5. The AFIS side has a sandbox or a way to mark pilot searches (questionnaire E4), so pilot submissions do not enter casework records.

## 4. Data: decision required

Two sources are possible. The choice, the legal basis and the retention are the DPO's and the FQM's; engineering has no say and no access.

| Option | Description | Ground truth | Considerations |
| --- | --- | --- | --- |
| Consented volunteers | Staff or volunteers give photographs of their fingers under the capture guidance (`docs/capture_guidance.md`) and contact-scanner reference prints at 500 ppi, enrolled in the sandbox or in a test database. | The volunteer's own reference print. | Consent form, withdrawal, retention, no link to any casework database; the fingers of staff may already be in exclusion databases. |
| Closed cases | Photographs from closed cases whose outcome is known, searched against the production database in a mode the AFIS marks as a test. | The case's established outcome. | Legal basis for re-processing, DPIA, the risk that a pilot search touches live records; access limited to examiners already entitled to the case. |

Whatever the option: photographs, prints, reports and ranks stay in the laboratory's systems. They never enter this repository, an issue tracker, a chat, a shared drive outside the laboratory, or an agent's context. The pilot record names files by Ridge's identifiers and hashes, never by a person.

## 5. Design

### 5.1 Unit and sample size

The unit is one submission: one photograph, extracted once with one option set, exported at one scale, searched once. One photograph may give several submissions (arms, scales), which are analysed separately.

Sample size guidance, from the Wilson interval at 95 % confidence for a hit rate near 50 % (the widest case):

| Submissions per arm | Half-width of the interval |
| --- | --- |
| 30 | about 17 percentage points |
| 50 | about 13 |
| 100 | about 10 |
| 200 | about 7 |

[Choose the number of fingers, photographs per finger and arms; a first pilot of 50 to 100 submissions in the default arm is enough to see whether the approach is worth a larger study.]

### 5.2 Arms

The default arm is Ridge's characterised pipeline with default options. Every other arm is one change at a time, and the method variants are labelled unvalidated in every report they appear in (ADR-014).

| Arm | Setting | Question answered |
| --- | --- | --- |
| Default | Default options; scale from a ruler or an ID-1 card in the photo | The baseline. |
| No reference | Default options; scale estimated (no object in the photo) | How much a missing scale reference costs. |
| Sweep | Default options; a scale sweep export (FR-39) with [3 or 5] steps, each searched | Whether several scales recover hits lost to scale error. |
| Grayscale | The grayscale export (FR-37) instead of the binary print | Whether the matcher prefers a contact-like grey image. |
| Variant: [channel auto / specular mask / upright / local frequency / rectify] | One ADR-014 variant on, the rest default | Whether the variant raises the hit rate enough to justify a validation study. |

[Keep the arms few; each arm multiplies the searches.]

### 5.3 Capture conditions

Photographs are taken under `docs/capture_guidance.md`. Record for each photograph the condition code: [A] guidance followed with a scale reference, [B] guidance followed without a reference, [C] guidance not followed (as received). Conditions are a grouping column in the analysis.

## 6. Procedure

For each photograph:

1. Import into the pilot case store (`ridge-case import`); the custody log records the file's hash and its provenance hints.
2. Run the extraction for each arm (`ridge-case extract` with the arm's options, finger position and source agency as stated by the examiner); every job writes a signed report.
3. Export the comparison image in the format and at the resolution OQ-4 names (`ridge-case export` or `export-all --format`); for the sweep arm, `ridge-case sweep`. Record the exported file's SHA-256 as the custody log has it.
4. Write the submission cover sheet (`ridge-case report --cover`) and hand the files to the AFIS operator in the agreed way (questionnaire F1).
5. The AFIS operator searches in the pilot mode and returns, for each submission, the rank of the true mate in the candidate list, or "not returned" when it is absent, and the candidate-list length. Scores are optional.
6. The examiner who records ranks does not change extraction parameters afterwards; re-runs are new submissions with their own job identifiers.
7. Record one line per submission in the ranks file (section 7).

Failures to extract (Ridge refuses the photograph or finds no ridge pattern) are recorded as such; they count in the failure-to-extract rate, not in the hit rates.

## 7. Recording

The ranks file is a CSV with one row per submission. The validation tool needs the columns `probe` and `rank`, groups by the optional column `group`, and ignores every other column, which is there for the pilot's own record:

```text
probe,rank,group,photo_sha256,job_id,scale_method,export_sha256,list_length
P-001,1,default/A,<sha256>,<job id>,ruler,<sha256>,20
P-002,,default/B,<sha256>,<job id>,none,<sha256>,20
```

`rank` is a positive whole number (1 to 1000); an **empty** rank means the mate was not returned. `group` carries the breakdown the analysis needs, for example `arm/condition`, in one column; a row must have exactly the header's fields. The file carries identifiers and hashes only; the mapping from identifiers to persons stays with the FQM.

Ridge's validation tool reads this file and computes the hit rates and the CMC curve:

```bash
ridge-validate --ranks ranks.csv --rank 1 --rank 5 --rank 10 --rank 20 -o pilot.json
```

It prints, for all rows and per `group`, the number of submissions, the rank-k hit rate for each k with its 95 % Wilson interval, the share not returned, and the CMC curve up to the list length (PRD FR-43). It makes no claim beyond those numbers.

## 8. Analysis and acceptance

- Report rank-1, rank-5, rank-10 and rank-20 hit rates with intervals per arm and per condition, the failure-to-extract rate, and the CMC curves on one chart.
- Compare arms against the default arm by their intervals; with the sample sizes above, only large differences are meaningful. Do not pick the best arm after the fact and report it alone.
- Provisional targets are those of PRD §12 (to be confirmed, OQ-7). Meeting or missing them is a result, not a validation; the FQM decides what follows (a validation study per architecture, a change of defaults by ADR, or stopping).
- Any defect, refusal or unexpected output seen during the pilot is reported to engineering **without the image**: job identifier, report excerpt with hashes, the error text.

## 9. Report template

| Section | Content |
| --- | --- |
| Setup | Ridge version and build hash, workstation architecture, AFIS product and edition, pilot mode, dates, roles. |
| Data | Source option, number of fingers and photographs, condition codes, consent or selection rule reference, retention. |
| Results | The table from `ridge-validate`, the CMC chart, failure-to-extract counts, per arm and condition. |
| Observations | Capture problems, scale references missing, refusals, operator remarks. |
| Decision | FQM and Product Owner: next step and owner. |
| Statement | "These results are measurements under the pilot's conditions. They are not a validation of the method and no search result in this pilot is an identification." |

## 10. Risks

| Risk | Mitigation |
| --- | --- |
| Pilot submissions enter casework records or the production audit trail. | Sandbox or marked pilot mode (questionnaire E4); a pilot-only case store; the AFIS contact confirms before the first search. |
| Ranks are influenced by knowing the answer. | The operator who searches does not choose parameters; re-runs are new submissions; the ranks file is frozen before analysis. |
| Real data reaches engineering or an agent. | Section 2's rule; defect reports carry identifiers and hashes only; the repository's `.gitignore` and the agent instructions forbid images. |
| The pilot is read as a validation. | The statement in section 9 appears in every version of the report. |

## 11. Sign-off

| Role | Name | Date | Signature |
| --- | --- | --- | --- |
| Product Owner | | | |
| Forensic Quality Manager | | | |
| Data Protection Officer | | | |
| AFIS team contact | | | |
