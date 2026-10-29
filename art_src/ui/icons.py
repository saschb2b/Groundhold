#!/usr/bin/env python3
"""Frames the command-card icons in ui/icons/ from raw model renders, as art_src/ui/icons.json lists them.

    python3 art_src/ui/icons.py              # from the project root; rewrites the listed ui/icons/*.png

The renders in art_src/ui/renders/ come from `godot-agent asset icon <model> --size 216` (no frame),
twice the icon's size. Each icon becomes a strategy-game command button: the subject cropped to fill
it, saturated, rim-lit from the top left and shadowed, over a glow from its own colour at the centre
to a deep edge, a glassy sheen, an inner shadow and a thin border in the backdrop's own hue (a dark
line and a light catch at the top left), so the subject is the brightest thing on the button. The
bottom `foot` of the height stays clear of the subject and shaded, for the cost drawn there, and the
top-left corner stays clear for the hotkey tab.

Seeded and deterministic; only Pillow is needed. Outputs are recorded in asset_manifest.json.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from console import _mipmapped, _mix, _smooth, hex_to_rgb, record  # noqa: E402


def _subject(icon, n, k, box_w, box_h, rim):
    """The subject cropped to its pixels, scaled to fit box_w x box_h, saturated and rim-lit."""
    bbox = icon.getchannel("A").point(lambda a: 255 if a > 16 else 0).getbbox()
    crop = icon.crop(bbox)
    scale = min(box_w / crop.width, box_h / crop.height)
    sub = crop.resize((max(1, round(crop.width * scale)), max(1, round(crop.height * scale))), Image.LANCZOS)
    alpha = sub.getchannel("A")
    rgb = ImageEnhance.Color(sub.convert("RGB")).enhance(1.25)
    rgb = ImageEnhance.Brightness(ImageEnhance.Contrast(rgb).enhance(1.1)).enhance(1.06)
    sub = rgb.convert("RGBA")
    sub.putalpha(alpha)
    # rim light where the subject faces the top-left light
    shifted = Image.new("L", alpha.size, 0)
    shifted.paste(alpha, (round(1.5 * k), round(1.5 * k)))
    light = Image.new("RGBA", alpha.size, (255, 236, 196, 0))
    light.putalpha(ImageChops.subtract(alpha, shifted).filter(ImageFilter.GaussianBlur(0.4 * k))
                   .point(lambda v: int(min(255, v * rim))))
    sub.alpha_composite(light)
    sub.putalpha(alpha)
    return sub, alpha


def frame(icon: Image.Image, centre: str, edge: str, size: int, foot: float = 0.0, seed: int = 1,
          rim: float = 0.5, corner: float = 0.0, button: int = 54) -> Image.Image:
    n = icon.width
    k = n / size  # painting scale
    line = max(1, round(size / button))  # the border: one pixel of the button
    b = round(line * k)
    rng = random.Random(seed)
    grid = Image.new("L", (6, 6))
    grid.putdata([rng.randrange(256) for _ in range(36)])
    mottle = grid.resize((n, n), Image.BICUBIC).load()
    c, e = hex_to_rgb(centre), hex_to_rgb(edge)
    base = Image.new("RGBA", (n, n))
    px = base.load()
    for y in range(n):
        for x in range(n):
            t = min(1.0, math.hypot((x / n - 0.46) * 1.05, y / n - 0.4) / 0.72) ** 1.25
            col = _mix(c, e, t)
            f = 0.9 + 0.2 * mottle[x, y] / 255.0
            px[x, y] = (*(int(max(0, min(255, v * f))) for v in col), 255)
    # a soft sheen across the top, the glass of the button
    sheen = Image.new("L", (n, n), 0)
    ImageDraw.Draw(sheen).ellipse([-n * 0.2, -n * 0.55, n * 1.2, n * 0.32], fill=255)
    layer = Image.new("RGBA", (n, n), (255, 240, 210, 0))
    layer.putalpha(sheen.filter(ImageFilter.GaussianBlur(8 * k)).point(lambda v: int(v * 0.13)))
    base.alpha_composite(layer)
    # the subject, cropped to fill the button above its foot
    inner = n - 2 * b
    foot_px = round(foot * n)
    top = b + round(3 * k)
    bottom = n - foot_px if foot_px else n - b - round(4 * k)
    if icon.getchannel("A").point(lambda a: 255 if a > 16 else 0).getbbox():
        box_w = int(inner * 0.86)
        box_h = min(box_w, bottom - top)
        # The hotkey tab covers the top-left `corner` button pixels: move the subject right,
        # as far as the border allows, until it keeps out of that square; if that is not
        # enough, shrink it a little and try again (it stays on the foot).
        clear = round(corner * size / button * k)
        for _ in range(40):
            sub, alpha = _subject(icon, n, k, box_w, box_h, rim)
            x = (n - sub.width) // 2
            if foot_px or sub.height > (bottom - top) * 0.8:
                y = bottom - sub.height
            else:
                y = top + (bottom - top - sub.height) // 2 + round(2 * k)
            if not clear:
                break
            room = n - b - round(2 * k) - sub.width
            x = next((s for s in range(x, max(x, room) + 1, max(1, round(k))) if not _overlaps(alpha, s, y, clear)),
                     None)
            if x is not None:
                break
            box_w, box_h = int(box_w * 0.96), int(box_h * 0.96)
        if x is None:
            x = (n - sub.width) // 2
        sa = Image.new("L", (n, n), 0)
        sa.paste(alpha, (x + round(2 * k), y + round(3 * k)))
        shadow = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        shadow.putalpha(sa.filter(ImageFilter.GaussianBlur(2.5 * k)).point(lambda v: int(v * 0.6)))
        base.alpha_composite(shadow)
        base.alpha_composite(sub, (x, y))
    if foot_px:
        # the foot: shade deepening to the bottom edge, under the cost
        reach = round(foot_px * 1.35)
        shade = Image.new("L", (n, n), 0)
        sp = shade.load()
        for yy in range(n - reach, n):
            v = int(255 * 0.55 * _smooth((yy - (n - reach) + 0.5) / reach) ** 0.9)
            for xx in range(n):
                sp[xx, yy] = v
        layer = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        layer.putalpha(shade)
        base.alpha_composite(layer)
    # inner shadow under the border's top and left
    pad = round(20 * k)
    mask = Image.new("L", (n + 2 * pad, n + 2 * pad), 255)
    ImageDraw.Draw(mask).rectangle([pad + b + round(2 * k), pad + b + round(3 * k), pad + n - b + round(2 * k),
                                    pad + n - b + round(3 * k)], fill=0)
    layer = Image.new("RGBA", (n, n), (4, 3, 2, 0))
    layer.putalpha(mask.filter(ImageFilter.GaussianBlur(3 * k)).crop((pad, pad, pad + n, pad + n))
                   .point(lambda v: int(v * 0.75)))
    base.alpha_composite(layer)
    px = base.load()
    # a dark line in the backdrop's own hue, and inside it a light catch at the top and left
    dark = tuple(v * 0.3 for v in e)
    catch = _mix(c, (255, 244, 224), 0.5)
    for y in range(n):
        for x in range(n):
            d = min(x, y, n - 1 - x, n - 1 - y)
            if d < b:
                px[x, y] = (*(int(v) for v in dark), 255)
            elif d < 2 * b and (x < 2 * b or y < 2 * b) and x < n - b and y < n - b:
                old = px[x, y]
                px[x, y] = (*(int(old[i] + (catch[i] - old[i]) * 0.55) for i in range(3)), 255)
    if size != n:
        base = base.convert("RGBa").resize((size, size), Image.BOX).convert("RGBA")
    return base


def _overlaps(alpha, x, y, clear):
    """Whether the subject (its alpha placed at x, y) has pixels in the top-left clear x clear square."""
    w, h = min(alpha.width, clear - x), min(alpha.height, clear - y)
    if w <= 0 or h <= 0:
        return False
    return alpha.crop((0, 0, w, h)).point(lambda a: 255 if a > 40 else 0).getbbox() is not None


def main(argv: list[str]) -> int:
    project = Path(__file__).resolve().parents[2]
    spec_rel = argv[0] if argv else "art_src/ui/icons.json"
    spec = json.loads((project / spec_rel).read_text())
    script = Path(__file__).resolve().relative_to(project).as_posix()
    for name, icon in spec["icons"].items():
        with Image.open(project / icon["render"]) as img:
            render = img.convert("RGBA")
        out = frame(render, icon["centre"], icon["edge"], spec["size"], foot=spec.get("foot", 0.0),
                    seed=icon.get("seed", 1), rim=icon.get("rim", spec.get("rim", 0.5)),
                    corner=spec.get("corner", 0.0), button=spec.get("button", 54))
        path = project / spec["dest"] / f"{name}.png"
        out.save(path)
        _mipmapped(path)
        record(project, [path], {"tool": "script", "script": script, "spec": spec_rel, "source": icon["render"],
                                 "regen": f"python3 {script} {spec_rel}"})
        print(f"wrote {path.relative_to(project).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
