# Screen-reader test script (NVDA)

A manual check that an examiner who uses a screen reader can do every task in the [examiner guide](examiner_guide.md). It is required before each GUI release (WCAG 2.2 AA, `desktop_gui_tauri_standards.md` section 9). Automated axe checks in the gate cover markup; this script covers what is actually announced.

**Synthetic data only.** Use a new, empty folder as the case store and the synthetic photo below. Never use real finger photos or case data, and never put screenshots of real data in a report.

## Setup

1. Install Ridge from the release installer. Install NVDA from nvaccess.org yourself (it is free) and start it. Use NVDA's default settings, with the NVDA key set to <kbd>Insert</kbd>.
2. Make a synthetic finger photo from a Ridge checkout:

   ```bash
   .venv/Scripts/python -c "import cv2; from tests.synthetic import make_photo; cv2.imwrite('synthetic_finger.png', make_photo('whorl', 480, 360, 9.0))"
   ```

   Keep the file outside the repository; images are never committed.
3. Create an empty folder for the test store, for example `D:\ridge-sr-test`.
4. Copy the [record sheet](#record-sheet) and note the date, the Ridge version (shown at the bottom of the store screen) and the NVDA version.

Use <kbd>Tab</kbd> and <kbd>Shift</kbd>+<kbd>Tab</kbd> to move between controls. In browse mode, <kbd>H</kbd> moves between headings and <kbd>D</kbd> between landmarks. For each step, note what NVDA says and whether you could do it without a mouse.

## Steps

| # | Do | Expect NVDA to announce |
| --- | --- | --- |
| 1 | Start Ridge | Window "Ridge"; heading "Ridge"; the "Case store" heading |
| 2 | <kbd>Tab</kbd> to **Choose case store...** and press <kbd>Enter</kbd>; pick the empty folder in the Windows dialog | The button name; then the Windows folder dialog (NVDA reads it normally) |
| 3 | Find **First run: your examiner identity**; **Create examiner identity...** | A separate "Choose your examiner passphrase" window. Focus starts in "New passphrase"; then "Type it again"; then the "Create identity" button. A mismatch or a short passphrase is announced as an alert |
| 4 | In **New case**, fill "Case reference", "Legal basis" and "Keep until (retention date)"; **Create case...**; enter the passphrase | Each field label; the passphrase window titled "Create case ..."; then the case screen with the case reference |
| 5 | Press <kbd>?</kbd> | Dialog "Keyboard shortcuts", with focus on "Close". <kbd>Tab</kbd> stays in the dialog, and <kbd>Escape</kbd> closes it and returns focus where it was |
| 6 | Press <kbd>Alt</kbd>+<kbd>1</kbd> to <kbd>Alt</kbd>+<kbd>4</kbd> | Each section button (Evidence, Jobs, References, Records) as current page |
| 7 | Evidence: **Import photos...**; choose `synthetic_finger.png` | The Windows file dialog; then the imported photo's name and its short hash in the list |
| 8 | Choose the photo; tab through the settings; **Run job** | Each setting's label and value; the button changes to "Running job..." and the result is announced when done |
| 9 | Tab into an image viewer; use <kbd>+</kbd>, <kbd>-</kbd>, <kbd>0</kbd>, <kbd>1</kbd>, arrow keys | "image viewer" with its title and the key help; the zoom group; changes are reflected without a mouse |
| 10 | Jobs: **Export signed report...**; **Save readable copy...**; **Reproduce job** | Button names; the Windows save dialog; a status or alert message with the outcome |
| 11 | Jobs: a **Copy** button next to a hash | "Copy SHA-256 ..."; after pressing, "... copied" is announced |
| 12 | Records: **Verify now** | The verification result is announced (OK, or the first problem as an alert) |
| 13 | Records: **Place legal hold**, enter a reason, confirm; then **Lift legal hold** | The reason field label; the result |
| 14 | Records: the custody log; press <kbd>/</kbd>, type a few letters of a note, **Search** | The table and its caption; focus moves to "Find"; the found entries |
| 15 | Records: add a note; **Correct...** it | The note field label; the new note and "corrects #N" |
| 16 | **Lock case** | Back on the store screen; the notice that the case was locked |
| 17 | Store screen: **Verify all cases...**; **Show case details...** | The passphrase window; the results list, with any problem announced |
| 18 | **This workstation → Check this workstation** | The status line ("No problems found..." or the problem count) and each finding with its level in words |
| 19 | **Device-secret recovery → Export recovery file...**; save to the test folder; choose a recovery passphrase; enter the examiner passphrase | The save dialog; window "Choose a recovery passphrase" with "New passphrase" and "Type it again"; window "Export the recovery file"; the saved message with key and fingerprint |
| 20 | **Check exported files → Check a file...**; pick the exported report from step 10 | "verified" with the details |
| 21 | **About Ridge** (bottom of the store screen) | Dialog "About Ridge", with focus on "Close"; <kbd>Escape</kbd> closes it |
| 22 | Close Ridge | NVDA returns to the desktop; no Ridge window is left |

## Record sheet

| # | Heard | Works without a mouse? | Problem and severity (blocker / serious / minor) |
| --- | --- | --- | --- |
| 1 | | | |
| ... | | | |

Report each problem with the step number, what was announced, and what should have been announced. A blocker is a task that cannot be done with the keyboard and NVDA alone. Afterwards, delete the test store folder and the synthetic photo.
