"""Draw the desktop GUI icons into gui/src-tauri/icons/ (generated, never committed).

    python tools/gui_icons.py

Image files are kept out of git (the docs gate refuses them, .gitignore ignores them), so the
icons Tauri needs at build time are drawn here from code: concentric arcs above a millimetre
scale, on the GUI's graphite colour. Nothing biometric is drawn.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "gui" / "src-tauri" / "icons"
GRAPHITE, PAPER, INK = (38, 41, 46, 255), (226, 228, 231, 255), (61, 99, 196, 255)
SIZE = 1024


def draw() -> Image.Image:
    """Draw the master icon at 1024 px."""
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    pen.rounded_rectangle((48, 48, SIZE - 48, SIZE - 48), radius=200, fill=GRAPHITE)
    cx, cy = SIZE // 2, 600
    for i, r in enumerate(range(90, 420, 66)):
        pen.arc((cx - r, cy - r, cx + r, cy + r), start=200 - i * 2, end=340 + i * 2, fill=PAPER, width=34)
    left, right, base = 230, SIZE - 230, 820
    pen.rectangle((left, base, right, base + 18), fill=INK)
    for k, x in enumerate(range(left, right + 1, (right - left) // 10)):
        pen.rectangle((x - 7, base - (70 if k % 5 == 0 else 38), x + 7, base), fill=INK)
    return image


def main() -> int:
    """Write every size Tauri's configuration lists."""
    OUT.mkdir(parents=True, exist_ok=True)
    master = draw()
    for name, side in (("32x32.png", 32), ("128x128.png", 128), ("128x128@2x.png", 256), ("icon.png", 512)):
        master.resize((side, side), Image.Resampling.LANCZOS).save(OUT / name)
    master.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    master.save(OUT / "icon.icns")
    print(f"icons written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
