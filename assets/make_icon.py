"""Generate a Card-Sharp icon set (multiple PNG sizes + .icns).

Design: green felt background, white card with black spade + red heart,
and a small "C-S" monogram. Uses Pillow only.

Run:  python assets/make_icon.py
Output: assets/icon.iconset/*.png  and  assets/icon.icns
"""
import os
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).parent
ICONSET = HERE / "icon.iconset"


FELT = (11, 107, 58, 255)
FELT_DARK = (8, 63, 34, 255)
CARD = (247, 242, 231, 255)
BLACK = (17, 17, 17, 255)
RED = (192, 32, 32, 255)


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Rounded felt background
    r = size // 6
    d.rounded_rectangle([(0, 0), (size, size)], radius=r, fill=FELT)
    # Inner ring
    inset = size // 20
    d.rounded_rectangle([(inset, inset), (size - inset, size - inset)],
                        radius=r, outline=FELT_DARK, width=max(1, size // 64))

    # Card (rotated slightly)
    cw = int(size * 0.55)
    ch = int(size * 0.72)
    card_img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card_img)
    cr = max(4, cw // 10)
    cd.rounded_rectangle([(0, 0), (cw, ch)], radius=cr, fill=CARD, outline=BLACK, width=max(1, size // 96))

    # Suit glyphs inside card
    try:
        font_big = ImageFont.truetype("/System/Library/Fonts/Apple Symbols.ttf", int(ch * 0.42))
        font_mid = ImageFont.truetype("/System/Library/Fonts/Apple Symbols.ttf", int(ch * 0.20))
        font_txt = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", int(ch * 0.22))
    except Exception:
        font_big = ImageFont.load_default()
        font_mid = ImageFont.load_default()
        font_txt = ImageFont.load_default()

    # Big spade centered
    cd.text((cw * 0.5, ch * 0.55), "♠", fill=BLACK, font=font_big, anchor="mm")
    # Small red heart top-left
    cd.text((cw * 0.18, ch * 0.18), "♥", fill=RED, font=font_mid, anchor="mm")
    # "A" top-left
    cd.text((cw * 0.18, ch * 0.36), "A", fill=BLACK, font=font_txt, anchor="mm")
    # Bottom-right mirrored
    cd.text((cw * 0.82, ch * 0.82), "♥", fill=RED, font=font_mid, anchor="mm")
    cd.text((cw * 0.82, ch * 0.64), "A", fill=BLACK, font=font_txt, anchor="mm")

    # Rotate card
    card_img = card_img.rotate(-8, resample=Image.BICUBIC, expand=True)
    # Paste centered
    cx = (size - card_img.width) // 2
    cy = (size - card_img.height) // 2
    img.paste(card_img, (cx, cy), card_img)
    return img


def main():
    if ICONSET.exists():
        shutil.rmtree(ICONSET)
    ICONSET.mkdir(parents=True)
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for s in sizes:
        img = draw_icon(s)
        img.save(ICONSET / f"icon_{s}x{s}.png")
        # @2x variants for retina
        if s in (16, 32, 128, 256, 512):
            img2 = draw_icon(s * 2)
            img2.save(ICONSET / f"icon_{s}x{s}@2x.png")

    # Build .icns via iconutil
    icns = HERE / "icon.icns"
    try:
        subprocess.run(["iconutil", "-c", "icns", str(ICONSET), "-o", str(icns)],
                       check=True)
        print(f"Wrote {icns}")
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"iconutil unavailable ({e}); PNGs only.")


if __name__ == "__main__":
    main()
