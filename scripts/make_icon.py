#!/usr/bin/env python3
"""The port's own icon - original art, drawn here: nothing from the game.

    python3 scripts/make_icon.py            # games/up/port/icon.ico

A balloon over a sky-coloured field. The engine's Android build takes the
icon from port/icon.ico (the PC build takes it from the same file), so the
app's icon on the phone is this drawing - not the game's.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "games", "up", "port", "icon.ico")

SIZE = 1024
SKY_TOP = (38, 84, 148)
SKY_BOTTOM = (126, 196, 214)
BALLOON = (232, 96, 62)
BALLOON_DARK = (198, 66, 44)
BALLOON_LIGHT = (246, 146, 92)
BASKET = (120, 78, 44)


def gradient() -> Image.Image:
    image = Image.new("RGB", (SIZE, SIZE), SKY_TOP)
    draw = ImageDraw.Draw(image)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        colour = tuple(int(SKY_TOP[i] + (SKY_BOTTOM[i] - SKY_TOP[i]) * t) for i in range(3))
        draw.line([(0, y), (SIZE, y)], fill=colour)
    return image


def balloon(image: Image.Image) -> Image.Image:
    draw = ImageDraw.Draw(image, "RGBA")
    # The balloon: an ellipse with a rounded point at the bottom.
    left, top, right, bottom = 232, 168, 792, 776
    draw.ellipse([left, top, right, bottom], fill=BALLOON)
    # The gores: stripes that follow the balloon's curve, from pole to pole.
    cx, rx = (left + right) / 2, (right - left) / 2
    cy, ry = (top + bottom) / 2, (bottom - top) / 2
    for index, (u0, u1, colour) in enumerate(
            [(-1.0, -0.62, BALLOON_DARK), (-0.62, -0.26, BALLOON_LIGHT),
             (-0.26, 0.26, BALLOON_DARK), (0.26, 0.62, BALLOON_LIGHT),
             (0.62, 1.0, BALLOON_DARK)]):
        left_edge, right_edge = [], []
        for step in range(41):
            y = top + (bottom - top) * step / 40
            span = rx * max(0.0, 1 - ((y - cy) / ry) ** 2) ** 0.5
            left_edge.append((cx + u0 * span, y))
            right_edge.append((cx + u1 * span, y))
        draw.polygon(left_edge + right_edge[::-1], fill=colour)
    # The neck and the ropes.
    draw.polygon([(470, bottom - 40), (554, bottom - 40), (546, 812), (478, 812)], fill=BALLOON_DARK)
    draw.line([(492, 806), (470, 900)], fill=(255, 255, 255, 220), width=14)
    draw.line([(532, 806), (554, 900)], fill=(255, 255, 255, 220), width=14)
    # The basket.
    draw.rounded_rectangle([448, 896, 576, 976], radius=18, fill=BASKET)
    draw.rounded_rectangle([448, 896, 576, 924], radius=14, fill=(146, 98, 56))
    return image


def main() -> int:
    image = balloon(gradient())
    image = image.resize((256, 256), Image.LANCZOS)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    image.save(OUT, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64),
                                         (128, 128), (256, 256)])
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
