# Ridge

Extract fingerprints from ordinary phone photos of fingers and save them as clean
white ridges on a black background.

## Install

```bash
pip install -r requirements.txt
pip install pillow-heif        # optional: read iPhone .HEIC photos
```

## Usage

```bash
python fingerprint_extract.py photo.jpg             # -> fingerprints/photo_fingerprint.png
python fingerprint_extract.py photos/ -o prints/    # every image in a folder
python fingerprint_extract.py photo.jpg --debug     # also save the intermediate steps
```

| Option | What it does |
| --- | --- |
| `-o`, `--outdir DIR` | Output folder (default `./fingerprints`). |
| `--min-quality Q` | 0–1: how clear the ridges must be to be kept (default 0.25). Lower keeps more of the finger; much below 0.22 it starts inventing ridges in blurry areas. |
| `--flip` | Swap ridges and valleys, e.g. for scans of ink prints, where ridges are dark. |
| `--period N` | Ridge spacing in pixels, if the automatic measurement is wrong. |
| `--no-crop` | Output at the photo's size instead of cropped to the print. |
| `--debug` | Also save intermediate images; `*_debug_region.jpg` outlines the part of the photo that was used. |

## How it works

1. **Find the finger** by skin colour (Lab a\* channel + Otsu threshold). If skin and
   background don't separate (grayscale photo, skin-coloured background), the whole
   photo is searched.
2. **Measure the ridge spacing** from the spectra of small patches and rescale the photo
   so ridges are 12 px apart, which makes every later step independent of camera
   resolution and distance.
3. **Flatten lighting and contrast**, estimate the local ridge direction and filter with
   an orientation-adaptive Gabor filter bank (Hong, Wan & Jain, 1998), twice.
4. **Keep only real ridges**: areas where the ridge-frequency energy points in one
   direction *and* repeats like ridges do. This rejects noise, the finger's outline, skin
   creases and background lines.
5. **Binarize** at the photo's resolution and save the ridges as white on black.

Only the parts of the finger where ridges are actually visible are extracted; blurry
areas are left out rather than invented.

## Tips for good photos

- One finger per photo, filling a good part of the frame (macro mode helps).
- Tap to focus on the fingertip: the pad is curved, so only part of it is ever perfectly sharp.
- Soft light from the side (a window) beats a direct flash; avoid strong glare.
- A plain background that isn't skin-coloured.

## Privacy

Fingerprints are permanent biometric data: think twice before sharing photos or
extracted prints. The `.gitignore` keeps images out of this repository so they aren't
committed by accident.
