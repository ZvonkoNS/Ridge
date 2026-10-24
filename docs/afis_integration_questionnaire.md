# Questions for the AFIS team (OQ-4)

Status: draft for the Product Owner to send, 2026-10-24. Answers belong in `docs/prd.md` (OQ-4, FR-32, FR-38, FR-41) and in the pilot protocol (`docs/pilot_protocol.md`).

Ridge turns a photograph of a finger into an enhanced, contact-like print image for a fingerprint examiner. It does not identify anyone, does not match, and does not decide anything. Whether such an image can be searched in your AFIS or NAFIS, in what form, and how the result is handled is your decision. These questions are what Ridge's engineering needs to know to produce files your workflow accepts and to run a pilot that measures how often the right candidate appears in a search result. Please answer what you can; "not applicable" and "unknown" are useful answers.

How to answer: one answer per question, with the name and role of the person answering and the date. Where a question asks for a document (a specification, an import manual, a sample record), a reference or an excerpt is enough.

## A. System and workflow

| # | Question | Why it matters | Answer |
| --- | --- | --- | --- |
| A1 | Which AFIS/NAFIS product and version is in use (vendor, system name, release)? | Import rules, record formats and candidate-list behaviour are vendor-specific. | |
| A2 | Which ANSI/NIST-ITL edition does the system read: 1-2011 Update 2015, 1-2025 (NIST SP 500-290e4), or another? Does it also read ISO/IEC 39794-4 or 19794-4 finger images? | Decides whether Ridge writes Type-14/Type-13 records or plain images (FR-41). | |
| A3 | Who submits a search: the examiner, an AFIS operator, or an automated gateway? Who sees the candidate list? | Decides whom the submission cover sheet (FR-38) is for and how ranks can be recorded in a pilot. | |
| A4 | Which workflows would a Ridge image go into: latent search (unknown print against the database), tenprint verification (known subject), manual comparison only, or several? | Latent and tenprint workflows have different quality gates and record types. | |
| A5 | For which case types could a photographed finger be searched at all, and under which legal basis (link to OQ-1)? | Scope of the pilot and of casework use. | |

## B. Accepted image inputs

| # | Question | Why it matters | Answer |
| --- | --- | --- | --- |
| B1 | Which image file formats does the import accept: PNG, TIFF (uncompressed), BMP, JPEG, JPEG 2000, WSQ? Any that are refused? | Ridge exports PNG by default and can convert to uncompressed TIFF or BMP (FR-32); WSQ or JPEG 2000 would be new work. | |
| B2 | Which resolution is required: exactly 500 ppi, exactly 1000 ppi, a range, or "as recorded in the file"? How is the resolution read: from the file header, a record field, or typed by the operator? | Ridge writes the resolution into the file and the report; a tolerance tells whether an exact resample is needed. | |
| B3 | Is 8-bit grayscale required, and must ridges be dark on a light background (as a contact print) or light on dark? | Ridge exports both polarities; the default comparison export is contact-like (dark ridges). | |
| B4 | Are there limits on image size in pixels or bytes, or required margins around the print? | Ridge crops to the print area; margins can be added. | |
| B5 | Must the print be upright (tip up) and the correct way round (not mirrored)? Does the system accept rotated or mirrored input? | Ridge's comparison export is mirrored to look like a contact print; an upright variant exists but is unvalidated. | |
| B6 | Does the system accept a partial print (part of the pad), and is there a minimum area or minutiae count? | Photographs rarely show the whole pad. | |

## C. Records and metadata

| # | Question | Why it matters | Answer |
| --- | --- | --- | --- |
| C1 | Which record fields are mandatory for a submission (for example finger position code, impression type, source agency ORI, capture date, capture device)? Please attach a sample record or the import manual's field list. | Ridge records the finger position and the source agency as the examiner's statements (FR-38); other fields would be added. | |
| C2 | Which impression type code should be used for "photograph of a finger, processed"? Is such an impression type allowed in a search at all? | ANSI/NIST-ITL has codes for live-scan and latent impressions; a photographed finger fits none exactly. | |
| C3 | Can a quality score accompany the image (for example NFIQ 2 in a Type-14 field), and is it used as a gate? | Ridge reports an indicative NFIQ 2 score, labelled as not a validation. | |
| C4 | Is a free-text or comment field available for the submission, for example to carry the Ridge job identifier and the report's hash? | Links the AFIS log to Ridge's signed report. | |
| C5 | Which transaction types (TOT) would be used, and do they differ for a pilot? | Needed for any record writer. | |

## D. Scale and uncertainty

| # | Question | Why it matters | Answer |
| --- | --- | --- | --- |
| D1 | How does the system treat an image whose true scale is uncertain? Is there a field for scale uncertainty, or is the resolution taken as exact? | Ridge's scale comes from a ruler or an ID-1 card in the photo, with a recorded uncertainty; without a reference it is an estimate (FR-31). | |
| D2 | May an operator submit the same print at several scales (Ridge can write a scale sweep, FR-39), and how would that be logged and de-duplicated? | A sweep raises the chance of a hit when the scale is uncertain, at the cost of several searches. | |
| D3 | Is there a preferred way to mark an image as "scale estimated, no reference" so that a hit is reviewed with that in mind? | Keeps the examiner's review honest about the input. | |

## E. Search output, for the pilot

| # | Question | Why it matters | Answer |
| --- | --- | --- | --- |
| E1 | How long is a candidate list, and can its length be set for a pilot? | The rank at which the true mate appears is the pilot's measure (rank-k hit rate). | |
| E2 | Can the rank of a given candidate be exported or read off, and are matcher scores visible? | Ranks are needed; scores are optional. | |
| E3 | Does the system log the submitted file's hash, or can the submitted file be retrieved later to compare against Ridge's recorded SHA-256? | Lets the pilot show that the searched file is the exported file. | |
| E4 | Is a pilot search distinguishable from casework in the AFIS logs, and is a test database or a sandbox available? | Avoids pilot submissions entering casework records. | |

## F. Transfer, security and custody

| # | Question | Why it matters | Answer |
| --- | --- | --- | --- |
| F1 | How do files reach the AFIS: removable media, a network share, a gateway application? Which encryption or signing is required on the way? | Ridge runs offline; exports are files with recorded hashes. | |
| F2 | Are there file naming conventions or folder structures the import expects? | Ridge names exports by case, evidence and job identifiers. | |
| F3 | Can the submission cover sheet (an HTML page with the files' hashes, scale method and uncertainty, transforms and the indicative quality score) be stored with the submission, or must its content go into record fields? | Decides the form of FR-38's cover sheet in your workflow. | |
| F4 | Who keeps the record of what was submitted, when and by whom, and for how long? | Custody across the boundary between Ridge and the AFIS. | |

## G. Pilot and sign-off

| # | Question | Why it matters | Answer |
| --- | --- | --- | --- |
| G1 | Is the AFIS team willing to take part in a pilot of about 50 to 200 searches with known ground truth (volunteers with reference prints, or closed cases), under the protocol in `docs/pilot_protocol.md`? | Without ranks from real searches no claim about usefulness can be made. | |
| G2 | Who on the AFIS side is the contact for the pilot, and who approves the protocol? | Roles in the protocol. | |
| G3 | Any constraints we have not asked about (throughput, time windows, costs per search, audit requirements)? | | |

## What Ridge will do with the answers

- Record the accepted format, resolution and polarity as the export defaults (FR-32) and, if a record format is required, plan the record writer (FR-41) as an ADR with its own tests.
- Fill the submission record (FR-38) with the fields you name, each labelled as a statement by the examiner or as read from the file, never as verified.
- Write the pilot protocol's data and analysis sections against your candidate-list and logging answers.

Nothing in Ridge's output is an identification, a match or a validation; a search hit is a candidate for the examiner's comparison, and a pilot result is a measurement under the pilot's conditions, not a validation of the method.
