# Capture guidance: photographing a finger for Ridge

For investigators and examiners who take or receive photographs of fingers. Version 2026-10-24, to be approved by the Forensic Quality Manager. One page to print is at the end.

Ridge enhances the ridge pattern in a photograph so that an examiner can compare it or an AFIS operator can search it. What the camera did not record, Ridge cannot restore: a blurred, glaring or tilted photograph gives a poor print whatever the software does. The photograph is the evidence; Ridge never changes it and records what it was given.

## 1. Before the photograph

- Use the camera's highest resolution and its native lens. Do not use digital zoom; move closer instead.
- Clean the lens.
- If the camera offers RAW (DNG) next to JPEG, keep both. If it offers a "most compatible" JPEG instead of HEIF, choose JPEG.
- Switch off beauty filters, HDR merging, night modes and any "AI enhancement". They invent detail.
- Have a scale reference ready: a ruler with millimetre marks, or an ISO/IEC 7810 ID-1 card (a bank, identity or loyalty card: 85.60 × 53.98 mm).

## 2. Scale reference

Place the ruler or the card **in the same plane as the finger pad**, next to it, not overlapping the ridges, with its whole length or both long edges visible and sharp. Ridge measures the pixels per millimetre from it and records the measurement and its uncertainty in every report.

If no ruler or card is available, photograph the finger anyway. Ridge then estimates the scale from the ridge spacing, says so in the report and in the GUI, and the examiner can decide whether the uncertainty is acceptable or whether a scale sweep is searched. An estimate is worse than a reference, but a missing photograph is worse than an estimate.

Do not write on the finger or the card; do not place the card on top of the finger.

## 3. Position and framing

- The finger pad fills at least a third of the frame; the whole pad is inside the frame with some margin.
- The camera looks straight at the pad: the camera axis perpendicular to the pad's surface, not from above or below. A tilt compresses the ridges on one side.
- Finger upright in the frame (tip up) when possible. Ridge can rotate, but it records any rotation and an upright original is simpler to review.
- One finger per photograph. Several fingers in one frame give small, tilted pads.
- Take at least three frames: one straight on, one with the finger rolled slightly to the left, one to the right. Ridges on the sides of a curved pad are foreshortened; a small roll brings them into view. Keep all frames; do not delete "bad" ones.

## 4. Focus and distance

- Tap or lock the focus on the ridges, not on the background or the card.
- Distance about 10 to 20 cm with a phone; closer if the camera has a macro mode that keeps the whole pad sharp.
- After the shot, zoom into the photograph on the camera's screen: individual ridges must be visible as separate lines across the whole pad. If they are not, retake.
- Hold the camera with both hands or rest it; use the timer or a volume button to avoid shake.

## 5. Lighting

- Even, diffuse light: daylight through a window, a lamp bounced off a white surface, or a diffuser. Avoid a bare flash from the camera: it puts a glare spot on the pad where no ridges can be seen.
- If a flash is the only light, angle the finger so the glare falls off the pad, or hold a sheet of paper over the flash.
- Avoid shadows across the ridges from the hand, the camera or the ruler.
- A plain, matt background behind the finger. Avoid skin-coloured backgrounds; Ridge locates the finger by skin colour.

## 6. After the photograph: handling the original

- Do not crop, rotate, straighten, sharpen, filter, annotate or re-save the photograph. Any edit changes pixels and metadata and Ridge will list what it finds (software tags, missing camera metadata, a re-compressed JPEG) as provenance hints in the report.
- Transfer the original file: by cable, memory card, or a transfer method that keeps the file unchanged. Messaging apps and some e-mail clients recompress and strip metadata; if that is the only way, say so in the capture note.
- Keep the camera's metadata in the file (date, device, settings). Do not strip it before import. Whether reports may show the position data is the laboratory's decision (OQ-16); the import keeps the original as it is in any case.
- Import into Ridge as early as possible; the import records the file's hash and the time, and from then on the original is read-only.

## 7. Record a capture note

For each photograph, note:

| Item | Example |
| --- | --- |
| Case reference and item | [case], item 7 |
| Which finger (hand, finger) and the person's stated identity or "unknown" | right index, unknown |
| Who photographed, when | [name], 2026-10-24 14:32 |
| Device and lens or mode | [phone model], main camera, macro off |
| Scale reference present | ruler, mm marks / ID-1 card / none |
| Light and flash | window light, flash off |
| Frames taken | 3 (straight, left roll, right roll) |
| Anything unusual | wet skin, glove powder, cut, the finger was moved |

The note goes with the item; Ridge's submission record (finger position, source agency) is filled from it by the examiner and labelled as the examiner's statement.

## 8. What to avoid

| Avoid | Because |
| --- | --- |
| Digital zoom, cropping | Fewer pixels per ridge; nothing is gained. |
| Flash straight at the pad | Glare where the ridges are. |
| A tilted camera | Ridges on one side compressed; the scale differs across the pad. |
| Filters, HDR, "enhance" | Invented detail that is not evidence. |
| Sending through messaging apps | Recompression, lost metadata. |
| Editing before import | The import records the edited file as the original. |
| Writing on or near the pad | Hides ridges; confuses the finger mask. |

## 9. What Ridge does with the photograph

Ridge records the file's hash, reads the camera metadata as stored (never verified), lists provenance hints, locates the finger, measures the ridge spacing and the scale from the reference, enhances the ridges, and writes a signed report with every parameter and measurement. It says plainly when no scale reference was given, when an export had to be enlarged to reach a resolution, when a method variant was used, and that nothing in its output is an identification. The examiner reviews the enhanced print against the original with the kept area outlined.

---

## One page to print

**Finger photograph: checklist**

1. Highest resolution, native lens, no zoom, no filters, no HDR. Lens clean.
2. Ruler or ID-1 card in the plane of the pad, beside it, sharp. None available? Photograph anyway.
3. Pad fills a third of the frame; camera straight at the pad; tip up; one finger per frame.
4. Focus locked on the ridges; 10 to 20 cm; both hands or rested; check sharpness by zooming in.
5. Diffuse light, no flash on the pad, no shadows across the ridges, plain matt background.
6. Three frames: straight, slight roll left, slight roll right. Keep all.
7. Do not edit, crop, rotate or re-save. Transfer the original by cable or card. Keep the metadata.
8. Write the capture note: case, finger, who, when, device, reference, light, frames, remarks.

Ridge enhances; it does not identify. The photograph is the evidence.
