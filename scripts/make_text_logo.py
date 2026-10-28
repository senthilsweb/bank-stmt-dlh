"""Make a plain text logo (two PNGs: dark text and white text, transparent background) for the report and the PDFs.

    python scripts/make_text_logo.py "Your Company" [out_dir]     # default assets/

Writes logo.png (dark text, for the PDF on white) and logo-white.png (for the email header on green). Size 700x155,
the proportion the report code expects.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SIZE = (700, 155)
FONTS = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]


def font(size: int):
    for f in FONTS:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def render(name: str, color: str, path: Path) -> None:
    img = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    size = 110
    while size > 20:
        f = font(size)
        box = draw.textbbox((0, 0), name, font=f)
        if box[2] - box[0] <= SIZE[0] - 40 and box[3] - box[1] <= SIZE[1] - 30:
            break
        size -= 4
    x = (SIZE[0] - (box[2] - box[0])) // 2 - box[0]
    y = (SIZE[1] - (box[3] - box[1])) // 2 - box[1]
    draw.text((x, y), name, font=f, fill=color)
    img.save(path)
    print(path)


def main(name: str, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    render(name, "#0f172a", out / "logo.png")
    render(name, "#ffffff", out / "logo-white.png")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "Your Company", Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "assets"))
