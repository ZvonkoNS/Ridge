# Examiner guide

How to work a case in the Ridge desktop application, task by task. For checking files that you receive from someone else, see the [verification guide](verification_guide.md).

> **Ridge is an image-enhancement aid.** It turns photos of fingers into prints for you to examine. It does not identify anyone, does not decide whether prints match and draws no conclusions: the comparison and the conclusions are yours. Current builds are **internal engineering builds, not for casework** ([docs/prd.md](prd.md), milestone M5).

## Before your first case

Your laboratory gives you:

- a folder for the **case store**, where Ridge keeps every case encrypted;
- the **limits of use** from its validation report, signed by the Forensic Quality Manager (FQM), if it has set any;
- a place in its **key register**, so that your signed reports can be traced to you.

On the store screen, **This workstation → Check this workstation** shows whether Ridge is ready on this computer:

- the build;
- the OS keystore;
- the store and its cases;
- the limits of use, and whether they cover this computer's processor type.

Tick the key-register box to also check that your signing key is registered. The check changes nothing; fix every **Problem** before casework.

## First run

1. **Choose case store...** and pick the laboratory's folder, or an empty folder to start a new store.
2. **Create examiner identity...** Ridge opens its own passphrase window; the main window never sees your passphrase. Your signing key is sealed with the passphrase and with a secret in this account's OS keystore, so both are needed to open your cases.
3. Open **Register this key with the laboratory**, enter your name and **Export key card...**. Give the card to the laboratory: it confirms who you are before it adds the key to its register. A card proves only that whoever made it holds the key.

## Cases

- **New case** needs a case reference, the legal basis and a retention date. **Create case...** asks for your passphrase and opens the case.
- **Unlock...** opens a case from the list. **Show case details...** shows every case's reference, retention date and legal hold with one passphrase; cases past their retention date without a hold are marked for the retention review. Ridge never disposes of a case by itself.
- A case locks itself after a period without activity, and **Lock case** locks it at once. Decrypted previews are discarded when it locks.
- Press <kbd>?</kbd> for the keyboard shortcuts: <kbd>Alt</kbd>+<kbd>1</kbd>–<kbd>4</kbd> switch between the sections. **About Ridge** says what Ridge is and is not.

## Evidence

- **Import photos...** takes up to 50 photos at a time: JPEG, PNG, TIFF, BMP, WebP and HEIF/HEIC, recognised by their content and not by their name. Ridge hashes each original, stores it encrypted and never changes it. A photo that cannot be read is refused and the rest of the batch continues.
- An optional source note (exhibit number, device) is kept with the photo and repeated in every report on it.
- Notes on a photo stay with that photo (see [Notes](#notes)).

## Jobs and review

1. Choose a photo and its settings. Use **Region** to process one finger of several. Use **Ruler** (two points on a scale in the photo, with the distance in mm) for a calibrated 500 ppi comparison export. Without a ruler, the scale is estimated from the ridge spacing, and the report says so together with its uncertainty.
2. **Run job.** The original, the region and the result are shown side by side. Zoom with <kbd>+</kbd> and <kbd>-</kbd>; <kbd>0</kbd> fits the image, and the arrow keys move it.
3. **Measure** shows the distance between two points in pixels and, on a scaled export, in millimetres with its uncertainty. It is for orientation and is not recorded.
4. The minutiae overlay is off by default. It is unvalidated, for orientation only, and never used for matching.

Every job is logged, and a failed job is logged with its reason. Only a job that succeeds has a signed report. In **Jobs**:

- **Export signed report...** writes the report with its signature;
- **Save readable copy...** writes an HTML page for the case file. The page is not signed: the JSON report is the record;
- **Reproduce job** runs the job again from its report and compares every output. Results are reproducible on the same operating system and processor type;
- **Compare settings with** lists only the settings that differ between two jobs. It does not rank the outputs.

If the laboratory has set limits of use, each report says whether the job stayed within them, and names any deviation.

## References

**Import reference...** brings in a NAFIS/AFIS candidate image for manual comparison. It is hashed and logged like evidence and never processed. The export and the reference are shown side by side at the same physical scale, and **Export comparison sheet...** saves both at one scale with 10 mm bars. This view is for your comparison only: Ridge never compares or matches prints.

## Exports

Decrypted files leave the case only through the export buttons, and every export is written to the custody log with its destination. An exported image, comparison sheet, signed report or readable copy is logged with its SHA-256. An exported processing record, custody head or package is logged with its case or package. Its own export entry is covered by its signature, so it cannot name its own hash: that signature protects its content instead.

- **Export shown image** saves the image on screen.
- **Export all N comparison exports...** / **processed prints...** write every item of that kind into a new folder, with an `EXPORTS.csv` index of names, hashes, jobs and labels.

## Records

- **Case summary**: what is stored, the jobs, the notes, the retention date and the last verification.
- **Verify the case → Verify now**: re-checks every hash, the custody chain and every signature, and names the first problem.
- **Legal hold**: **Place legal hold** or **Lift legal hold**, with a reason. A case on hold cannot be disposed of.
- **Processing record → Export processing record...**: the signed custody log, for the Data Protection Officer or a reviewer.
- **Custody head for countersigning → Export custody head...**: a signed snapshot that a laboratory system can countersign out of band.
- **Disclosure package → Export disclosure package...**: the processing record and every signed report, with a signed manifest. It contains no images.
- **Custody log**: every entry, newest first. Filter by kind, or search for a hash, a job id or words of a note (<kbd>/</kbd> moves to the search box).

### Notes

Notes on the case, a job or a photo are written to the custody log with your name and the time. They cannot be changed or deleted. **Correct...** adds a new note that names the one it corrects, and the original stays.

## Store tasks

- **Verify all cases...** checks every case with one passphrase and logs each check in its case.
- **Back up this store...** copies the encrypted store into a new folder with a hash manifest. **A backup does not hold the OS-keystore secret** that opening the cases also needs; the laboratory's procedure must cover it (ADR-012).
- **Check exported files** verifies a report, processing record, custody head, key card, key register, limits file, disclosure package or store backup, without the store.

## What Ridge never does

- It never identifies anyone, matches prints or draws a conclusion.
- It never changes an original photo.
- It never sends data anywhere: it works offline.
- Its NFIQ 2 scores, where configured, are indicative only, because photos are outside the scope of NFIQ 2.
