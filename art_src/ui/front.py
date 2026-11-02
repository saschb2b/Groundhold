#!/usr/bin/env python3
"""Paints the front end's pieces in ui/front/ from art_src/ui/front.json.

    python3 art_src/ui/front.py              # from the project root; rewrites ui/front/*

The front end (docs/design/front-end.md §4.1) shares the console's materials and never its
architecture: no rail, wing, crest, well or socket here. Its pieces are lighter plates that
float over the full-bleed Causeway: warm stone glass (smoked, with the console's stone in it)
in a bronze rim, with dark gradient scrims behind text, and one call to action in bevelled
bronze, a chamfer catching the light round a polished field, the brightest thing on the
screen (its word is embossed by the game, CallToAction.Lettering). The bronze is the
console's own (its `material` and `stone`, read from art_src/ui/console.json), so the two read
as one family.

    bar            the top bar: smoked glass, darker at the top, a gilt hairline along its foot
    tab_rule       the active tab's underline (a gilt rule fading at both ends), tab_gem its diamond
    cta_*          the call to action: a body of hammered bronze, lit at the top and falling to a
                   deep shade at the foot, inside a 2 px gilt bevel; idle, hover, pressed (the bevel
                   turned in), disabled, counting (the 3-2-1, haloed), stone and stone_hover (the
                   queue's Cancel: the console's stone in a bronze rim). Behind its word the bronze
                   is dark enough for the cream letters to hold 4.5:1 (cta_contrast says)
    plate          a nameplate: warm stone glass in a bronze rim; plate_lit mine (the glass warmer,
                   the rim brighter), plate_empty a bare mark's
    plate_chip     the seat-colour chip down a nameplate's left edge, in grey for the seat's tint
    chip           the mode chip and small plates; chip_hover
    key            a key cap for the hotkeys shown beside actions (J, B, Enter)
    card           a mode card's frame; card_focus
    sheet          a sheet's panel
    toggle_on      a switch's track and knob, on; toggle_off; knob, a slider's knob
    focus          the keyboard focus ring (front-end.md §6.5), drawn round any control
    scrim_top      dark gradients behind text: from the top edge, and scrim_bottom from the foot;
                   scrim_corner, a soft quarter-ellipse out of a frame's corner, for a local scrim
                   behind one cluster (the call to action, the crew-covers line) instead of a band
    mark_<shape>   the seat glyphs carved into the marks' stone (diamond, circle, triangle, square)
    mode_<mode>    the Modes band's emblems in gilt: High Water an arc of the four seat marks, Tide
                   Race two crews over water with a gap between, Undertow two marks face to face
                   with a corked bottle between them
    copy           the copy glyph inside the party's code chip
    gear           the Settings icon in the top bar

Every nine-slice gets a StyleBoxTexture (.tres) beside it, in texels as console.py writes
them (`scale` 2: twice the layout's texels, with mipmaps), drawn through HdStyleBox. Seeded
and deterministic: the same spec writes the same bytes, and a file that comes out as it was
is left alone, its manifest entry too.
"""

from __future__ import annotations

import io
import json
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import console as C  # noqa: E402  (the console's helpers and its bronze)

# Every key the spec may set, with its default. Sizes are in layout pixels.
FRONT = {
    "seed": 11,
    "scale": 2,
    # the light, as the console's: from the top left
    "gilt": {"dark": "#4a2f10", "base": "#b98a3e", "light": "#fbe5a4", "spec": "#fff6dc"},
    # warm stone glass (F0's review: the navy glass read as a screen over the scene, not a piece
    # of it); mine a little warmer and lighter
    # (opaque: F1's review saw the page's words and the stage's reflections through the plates)
    "glass": {"top": "#3a332b", "bottom": "#1b1712", "alpha": 1.0, "sheen": 0.08},
    "glass_lit": {"top": "#4d4131", "bottom": "#231b12", "alpha": 1.0, "sheen": 0.12},
    "shadow": {"reach": 3, "dark": 0.5, "drop": 2},
    # (warm umber smoke, as the plates are: the navy read as another product's bar)
    "bar": {"size": [256, 56], "fade": 96, "top": "#0b0806", "bottom": "#17110b", "alpha": [0.9, 0.66],
            "hairline": 1.5},
    "tab": {"rule": [128, 6], "gem": 12},
    # the call to action: a 2 px gilt bevel round a body of hammered bronze, lit at its top edge
    # and falling to a deep shade at the foot (top, middle, foot), the middle, behind the word,
    # dark enough for the cream letters (F1's review measured 3.9:1 on the old flat amber)
    "cta": {"size": [128, 72], "radius": 10, "rim": 4, "inset": 6, "margin": 26, "bevel": 2.4, "chamfer": 4,
            "hammer": {"cell": 5.0, "depth": 0.075},
            "fields": {
                "idle": ["#c08243", "#663a17", "#381d09"], "hover": ["#cc8f4e", "#6c3f1b", "#40220b"],
                "pressed": ["#5a3112", "#744420", "#9a6230"], "disabled": ["#5f564c", "#4a433b", "#2f2a25"],
                "counting": ["#c98d4c", "#6a3e1a", "#3e210a"]},
            "halo": "#ffd27a"},
    "plate": {"size": [96, 72], "radius": 7, "rim": 2.0, "inset": 4, "margin": 18},
    "chip_bar": {"size": [16, 48], "width": 5, "inset": 3},
    "chip": {"size": [64, 40], "radius": 9, "rim": 1.6, "inset": 3, "margin": 14},
    "key": {"size": [32, 32], "radius": 5, "rim": 1.4, "inset": 2, "margin": 10},
    "card": {"size": [128, 128], "radius": 10, "rim": 3.0, "inset": 6, "margin": 28},
    "sheet": {"size": [192, 160], "radius": 12, "rim": 3.0, "inset": 8, "margin": 40},
    # the switch: off is a lit stone track (no longer a dark knob in a dark track), on is amber
    "toggle": {"size": [48, 28], "knob": 24, "off_track": ["#6b6052", "#3e362d"]},
    "emblem": {"size": 40},
    "focus": {"size": [64, 64], "radius": 10, "width": 2.5, "glow": 4, "color": "#ffe6a0"},
    "scrim": {"size": [8, 256], "color": "#04070b", "top": 0.78, "bottom": 0.8, "corner": [256, 128],
              "corner_strength": 0.82},
    "mark": {"size": 128},
    "gear": {"size": 32},
}
_K = 4  # paint texels per layout pixel: twice the output's, box-filtered down
_LIGHT = C._unit((-0.42, -0.78, 0.46))
_HALF = C._unit((_LIGHT[0], _LIGHT[1], _LIGHT[2] + 1.0))


def _rgb(value: str):
    return C.hex_to_rgb(value)


def _ramp(stops, t):
    """A colour along evenly spaced stops, t in 0..1."""
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    f = t * (len(stops) - 1)
    i = min(len(stops) - 2, int(f))
    return C._mix(stops[i], stops[i + 1], f - i)


def _luma(c) -> float:
    """WCAG relative luminance of an sRGB colour (0 to 255 a channel)."""
    def lin(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])


def _contrast(a, b) -> float:
    la, lb = _luma(a), _luma(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _mask(w, h, draw_fn):
    """A coverage mask w x h layout pixels at the paint scale, drawn by draw_fn(draw, k)."""
    img = Image.new("L", (w * _K, h * _K), 0)
    draw_fn(ImageDraw.Draw(img), _K)
    return img


def _rr(draw, k, x, y, w, h, r, fill=255):
    draw.rounded_rectangle([x * k, y * k, (x + w) * k - 1, (y + h) * k - 1], radius=r * k, fill=fill)


def _shadow(mask: Image.Image, reach: float, dark: float, drop: float) -> Image.Image:
    """The piece's soft shadow on the scene below it, dropped a little."""
    w, h = mask.size
    shifted = Image.new("L", (w, h), 0)
    shifted.paste(mask, (0, round(drop * _K)))
    soft = shifted.filter(ImageFilter.GaussianBlur(reach * _K)).point(lambda v: int(min(255, v * dark)))
    out = Image.new("RGBA", (w, h), (2, 3, 6, 0))
    out.putalpha(soft)
    return out


class _Front:
    def __init__(self, spec: dict, dest: Path, res_base: str, console_spec: dict):
        self.spec = C._merge(FRONT, spec or {})
        bronze = C._merge(C.CONSOLE, console_spec or {})
        self.bronze = {k: _rgb(v) for k, v in bronze["material"].items()}
        self.dest = dest
        self.res = res_base.rstrip("/") + "/"
        self.seed = int(self.spec["seed"])
        self.scale = int(self.spec["scale"])
        self.g = {k: _rgb(v) for k, v in self.spec["gilt"].items()}
        self.written: list[Path] = []
        self.unchanged: set[Path] = set()

    # output

    def save(self, name: str, img: Image.Image, width: int, height: int) -> None:
        path = self.dest / name
        data = io.BytesIO()
        C._down(img, width * self.scale, height * self.scale).save(data, format="PNG")
        if not C._write(path, data.getvalue()):
            self.unchanged.add(path)
        C._mipmapped(path)
        self.written.append(path)

    def stylebox(self, name: str, margin, content, expand=0, stretch=0) -> None:
        path = self.dest / f"{name}.tres"
        if not C._stylebox(path, self.res + f"{name}.png", margin, content, expand=expand, stretch=stretch,
                           scale=self.scale):
            self.unchanged.add(path)
        self.written.append(path)

    # the materials

    def rim_relief(self, mask: Image.Image, rim: float, metal: str, field=None, field_alpha=None, sheen=0.0,
                   rim_light=1.0, seed=0, noise=0.0):
        """A shape whose edge is a raised metal rim `rim` layout pixels wide (a rounded bead
        catching the light from the top left) round a flat field. `metal` is "gilt" (polished,
        the front's) or "bronze" (the console's, worn). `field(x, y) -> (r, g, b)` colours the
        inside (paint pixels), `field_alpha(x, y)` its opacity; `sheen` lightens the field's top
        edge. Returns RGBA at the paint scale."""
        w, h = mask.size
        m = C._field(mask)
        dist = C._inside(m, w, h)
        band = rim * _K
        height = [0.0] * (w * h)
        for i, d in enumerate(dist):
            if m[i] <= 0.0:
                continue
            if d < band:
                height[i] = 2.2 * _K * math.sin(math.pi * min(1.0, (d + 0.5) / band))
            else:
                height[i] = 0.0
        height = C._blur(height, w, h, max(1, _K // 3), passes=1)
        tone = C._noise(w, h, 3 * _K, self.seed + seed) if noise else None
        if metal == "gilt":
            stops = [self.g["dark"], self.g["base"], self.g["light"]]
            spec_c, gloss = self.g["spec"], 1.0
        else:
            b = self.bronze
            stops = [b["dark"], b["mid"], b["worn"]]
            spec_c, gloss = b["spec"], 0.45
        out = [(0, 0, 0, 0)] * (w * h)
        for y in range(h):
            for x in range(w):
                i = y * w + x
                a = m[i]
                if a <= 0.0:
                    continue
                d = dist[i]
                rimness = 1.0 - C._smooth((d - band) / (0.8 * _K) + 0.5)
                hl = height[i - 1] if x > 0 else height[i]
                hr = height[i + 1] if x < w - 1 else height[i]
                hu = height[i - w] if y > 0 else height[i]
                hd = height[i + w] if y < h - 1 else height[i]
                nx, ny = (hl - hr) * 0.5, (hu - hd) * 0.5
                inv = 1.0 / math.sqrt(nx * nx + ny * ny + 1.0)
                nx, ny, nz = nx * inv, ny * inv, inv
                dif = max(0.0, nx * _LIGHT[0] + ny * _LIGHT[1] + nz * _LIGHT[2])
                ndh = max(0.0, nx * _HALF[0] + ny * _HALF[1] + nz * _HALF[2])
                metal_c = _ramp(stops, (0.15 + 0.95 * dif) * rim_light)
                metal_c = [metal_c[c] + spec_c[c] * gloss * (0.25 * ndh ** 12 + 0.6 * ndh ** 70) for c in range(3)]
                if field is not None and rimness < 1.0:
                    fc = field(x, y)
                    if tone:
                        fc = [v * (1.0 + noise * (tone[i] - 0.5)) for v in fc]
                    if sheen:
                        # the glass catches the sky along its top edge, just inside the rim
                        s = sheen * math.exp(-max(0.0, d - band) / (3.0 * _K)) * max(0.0, -ny * 2 + 0.5 + (1 - y / h))
                        fc = [v + 255 * s * 0.5 for v in fc]
                    fa = field_alpha(x, y) if field_alpha else 1.0
                    # a dark line where the field meets the rim, so the rim stands proud
                    edge = math.exp(-max(0.0, d - band) / (0.9 * _K))
                    fc = [v * (1.0 - 0.55 * edge) for v in fc]
                    fa = min(1.0, fa + 0.5 * edge)
                    col = [metal_c[c] * rimness + fc[c] * (1 - rimness) for c in range(3)]
                    alpha = a * (rimness + fa * (1 - rimness))
                else:
                    col = metal_c
                    alpha = a * rimness if field is None else a
                out[i] = (int(max(0, min(255, col[0]))), int(max(0, min(255, col[1]))),
                          int(max(0, min(255, col[2]))), int(max(0, min(255, alpha * 255))))
        img = Image.new("RGBA", (w, h))
        img.putdata(out)
        return img

    def bevel_relief(self, mask: Image.Image, bevel: float, field, rim_light=1.0, inward=False, seed=0,
                     noise=0.0):
        """A plate of bronze whose edge is a chamfer `bevel` layout pixels wide, sloping up from
        the outline to a flat polished field (`field(x, y) -> (r, g, b)` in paint pixels), with a
        fine gilt bead along the very edge. `inward` turns the chamfer in (pressed: lit from the
        bottom right). Returns RGBA at the paint scale."""
        w, h = mask.size
        m = C._field(mask)
        dist = C._inside(m, w, h)
        band = bevel * _K
        height = [0.0] * (w * h)
        for i, d in enumerate(dist):
            if m[i] > 0.0:
                height[i] = 1.4 * min(d, band)
        height = C._blur(height, w, h, max(1, _K // 2), passes=1)
        tone = C._noise(w, h, 2 * _K, self.seed + seed) if noise else None
        b = self.bronze
        stops = [b["dark"], b["mid"], b["worn"]]
        sign = -1.0 if inward else 1.0
        out = [(0, 0, 0, 0)] * (w * h)
        for y in range(h):
            for x in range(w):
                i = y * w + x
                a = m[i]
                if a <= 0.0:
                    continue
                d = dist[i]
                hl = height[i - 1] if x > 0 else height[i]
                hr = height[i + 1] if x < w - 1 else height[i]
                hu = height[i - w] if y > 0 else height[i]
                hd = height[i + w] if y < h - 1 else height[i]
                nx, ny = sign * (hl - hr) * 0.5, sign * (hu - hd) * 0.5
                inv = 1.0 / math.sqrt(nx * nx + ny * ny + 1.0)
                nx, ny, nz = nx * inv, ny * inv, inv
                dif = max(0.0, nx * _LIGHT[0] + ny * _LIGHT[1] + nz * _LIGHT[2])
                ndh = max(0.0, nx * _HALF[0] + ny * _HALF[1] + nz * _HALF[2])
                chamfer = 1.0 - C._smooth((d - band) / (0.9 * _K) + 0.5)
                metal = _ramp(stops, (0.05 + 1.05 * dif) * rim_light)
                metal = [metal[c] + b["spec"][c] * 0.5 * (0.3 * ndh ** 10 + 0.7 * ndh ** 60) for c in range(3)]
                fc = list(field(x, y))
                if tone:
                    fc = [v * (1.0 + noise * (tone[i] - 0.5)) for v in fc]
                col = [metal[c] * chamfer + fc[c] * (1.0 - chamfer) for c in range(3)]
                # a fine gilt bead along the very edge, and a dark line where the chamfer meets the
                # field, so the field reads as set into the bronze
                bead = math.exp(-d / (0.6 * _K))
                col = [col[c] * (1.0 - 0.6 * bead) + self.g["light"][c] * 0.6 * bead * rim_light for c in range(3)]
                seam = math.exp(-abs(d - band) / (0.5 * _K)) * 0.35
                col = [v * (1.0 - seam) for v in col]
                out[i] = (int(max(0, min(255, col[0]))), int(max(0, min(255, col[1]))),
                          int(max(0, min(255, col[2]))), int(max(0, min(255, a * 255))))
        img = Image.new("RGBA", (w, h))
        img.putdata(out)
        return img

    def glass(self, key="glass"):
        g = self.spec[key]
        top, bottom = _rgb(g["top"]), _rgb(g["bottom"])
        return g, top, bottom

    def framed(self, size, radius, rim, inset, metal="gilt", glass="glass", rim_light=1.0, shadow=True,
               alpha_scale=1.0, seed=0):
        """A plate of glass in a rim, with its shadow: the front's every plate and panel."""
        w, h = size
        mask = _mask(w, h, lambda d, k: _rr(d, k, inset, inset, w - 2 * inset, h - 2 * inset, radius))
        g, top, bottom = self.glass(glass)
        H = h * _K

        def field(x, y):
            return C._mix(top, bottom, C._smooth(y / H))

        def alpha(x, y):
            return g["alpha"] * alpha_scale

        img = self.rim_relief(mask, rim, metal, field, alpha, sheen=g["sheen"], rim_light=rim_light, seed=seed)
        if shadow:
            sh = self.spec["shadow"]
            img = Image.alpha_composite(_shadow(mask, sh["reach"], sh["dark"], sh["drop"]), img)
        return img

    # pieces

    def bar(self):
        sp = self.spec["bar"]
        w, h = sp["size"]
        foot = 8  # room under the bar for its shadow on the scene
        W, H = w * _K, (h + foot) * _K
        top, bottom = _rgb(sp["top"]), _rgb(sp["bottom"])
        a0, a1 = sp["alpha"]
        fade = sp["fade"] * _K
        line = h * _K
        img = Image.new("RGBA", (W, H))
        px = img.load()
        hair = sp["hairline"] * _K
        for y in range(H):
            for x in range(W):
                ends = min(1.0, min(x, W - 1 - x) / fade)
                if y < line:
                    t = y / line
                    c = C._mix(top, bottom, t)
                    a = a0 + (a1 - a0) * t
                    # the gilt hairline along the foot, fading toward the bar's ends
                    e = (line - 1 - y) / hair
                    if e < 1.0:
                        k2 = (1.0 - max(0.0, e)) * (0.35 + 0.65 * C._smooth(ends))
                        gl = _ramp([self.g["base"], self.g["light"]], 0.4 + 0.5 * ends)
                        c = C._mix(c, gl, k2)
                        a = a + (1.0 - a) * k2
                    px[x, y] = (*(int(v) for v in c), int(255 * a))
                else:
                    s = 1.0 - (y - line) / (foot * _K)
                    px[x, y] = (2, 3, 6, int(255 * 0.35 * s * s))
        self.save("bar.png", img, w, h + foot)
        self.stylebox("bar", (sp["fade"], 0, sp["fade"], foot), (24, 0, 24, foot))

    def tab(self):
        sp = self.spec["tab"]
        w, h = sp["rule"]
        W, H = w * _K, h * _K
        img = Image.new("RGBA", (W, H))
        px = img.load()
        for y in range(H):
            for x in range(W):
                u = abs(x - W / 2) / (W / 2)
                v = abs(y - H / 2) / (H / 2)
                core = max(0.0, 1.0 - v * 2.2)
                glow = max(0.0, 1.0 - v) ** 2 * 0.35
                a = (core + glow) * (1.0 - C._smooth((u - 0.55) / 0.45))
                c = _ramp([self.g["base"], self.g["light"], self.g["spec"]], 0.4 + 0.6 * core)
                px[x, y] = (*(int(v2) for v2 in c), int(255 * min(1.0, a)))
        self.save("tab_rule.png", img, w, h)
        g = sp["gem"]
        mask = _mask(g, g, lambda d, k: d.polygon([(g * k / 2, 1 * k), (g * k - 1 * k, g * k / 2),
                                                   (g * k / 2, g * k - 1 * k), (1 * k, g * k / 2)], fill=255))
        gem = self.rim_relief(mask, g * 0.5, "gilt")
        self.save("tab_gem.png", gem, g, g)

    def hammered(self, w, h, cell, seed):
        """A hammered metal's dents: per paint pixel, a small tilt (nx, ny) toward the middle of
        the nearest of a field of seeded dents, `cell` layout pixels apart, so each dent catches
        the light on its far side."""
        rng = random.Random(self.seed * 31 + seed)
        c = cell * _K
        cols, rows = int(w / c) + 2, int(h / c) + 2
        pts = {}
        for j in range(rows):
            for i in range(cols):
                pts[(i, j)] = ((i + rng.uniform(0.15, 0.85)) * c, (j + rng.uniform(0.15, 0.85)) * c,
                               c * rng.uniform(0.55, 0.85))
        out = [(0.0, 0.0)] * (w * h)
        for y in range(h):
            for x in range(w):
                i0, j0 = int(x / c), int(y / c)
                best, bp = 1e9, None
                for dj in (-1, 0, 1):
                    for di in (-1, 0, 1):
                        q = pts.get((i0 + di, j0 + dj))
                        if q is None:
                            continue
                        d = (x - q[0]) ** 2 + (y - q[1]) ** 2
                        if d < best:
                            best, bp = d, q
                dx, dy = x - bp[0], y - bp[1]
                r = bp[2]
                k = max(0.0, 1.0 - math.sqrt(best) / r)
                # (a shallow bowl: the slope points out from the dent's middle)
                out[y * w + x] = (dx / r * k, dy / r * k)
        return out

    def cta(self):
        sp = self.spec["cta"]
        w, h = sp["size"]
        r, rim, inset, margin = sp["radius"], sp["rim"], sp["inset"], sp["margin"]
        mask = _mask(w, h, lambda d, k: _rr(d, k, inset, inset, w - 2 * inset, h - 2 * inset, r))
        H = h * _K
        sh = self.spec["shadow"]
        shadow = _shadow(mask, sh["reach"] + 1, sh["dark"] + 0.1, sh["drop"] + 1)
        W = w * _K
        dents = self.hammered(W, H, sp["hammer"]["cell"], 21)
        depth = sp["hammer"]["depth"]
        m = C._field(mask)
        dist = C._inside(m, W, H)
        gilt_band = sp["bevel"] * _K
        chamfer = sp["chamfer"] * _K
        lo, hi = (inset) * _K, (h - inset) * _K
        self.contrast = {}
        for state, stops in sp["fields"].items():
            stops = [_rgb(v) for v in stops]
            inward = state == "pressed"
            dull = state == "disabled"
            light = 0.8 if dull else (1.12 if state == "hover" else 1.0)
            out = [(0, 0, 0, 0)] * (W * H)
            for y in range(H):
                t = (y - lo) / max(1, hi - lo)
                body = _ramp(stops, C._smooth(min(1.0, max(0.0, t))) * 0.5 + max(0.0, min(1.0, t)) * 0.5)
                if not inward:
                    # a soft lift of light along the top edge, above the word
                    body = [v * (1.0 + 0.16 * math.exp(-((t - 0.1) / 0.09) ** 2)) for v in body]
                for x in range(W):
                    i = y * W + x
                    a = m[i]
                    if a <= 0.0:
                        continue
                    d = dist[i]
                    if d < gilt_band:
                        # the gilt bevel: a rounded bead lit from the top left (turned in, pressed)
                        u = (d + 0.5) / gilt_band
                        slope = math.cos(math.pi * u) * (-1.0 if inward else 1.0)
                        nx, ny = 0.0, 0.0
                        # the outward direction: toward the nearest edge, from the shape's middle
                        cx, cy = x - W / 2, y - H / 2
                        ln = math.sqrt(cx * cx + cy * cy) or 1.0
                        nx, ny = cx / ln * slope * 0.9, cy / ln * slope * 0.9
                        nz = math.sqrt(max(0.05, 1.0 - nx * nx - ny * ny))
                        dif = max(0.0, nx * _LIGHT[0] + ny * _LIGHT[1] + nz * _LIGHT[2])
                        ndh = max(0.0, nx * _HALF[0] + ny * _HALF[1] + nz * _HALF[2])
                        col = _ramp([self.g["dark"], self.g["base"], self.g["light"]], (0.1 + 0.95 * dif) * light)
                        col = [col[c] + self.g["spec"][c] * (0.2 * ndh ** 10 + 0.5 * ndh ** 60) for c in range(3)]
                        if dull:
                            g = sum(col) / 3.0
                            col = [g * 0.8 + v * 0.2 for v in col]
                    else:
                        # the hammered body; a short chamfer of darker bronze under the gilt
                        dx, dy = dents[i]
                        tilt = (dx * _LIGHT[0] + dy * _LIGHT[1]) * (-1.0 if inward else 1.0)
                        col = [v * (1.0 + depth * 2.2 * tilt) for v in body]
                        ch = 1.0 - min(1.0, (d - gilt_band) / chamfer)
                        if ch > 0.0:
                            side = 0.55 if inward else (0.75 + 0.5 * max(0.0, -(y - H / 2) / H))
                            col = [v * (1.0 - 0.35 * ch * (1.0 - side)) for v in col]
                        # a dark seam where the gilt meets the bronze, so the bevel stands proud
                        seam = math.exp(-abs(d - gilt_band) / (0.45 * _K)) * 0.45
                        col = [v * (1.0 - seam) for v in col]
                    out[i] = (int(max(0, min(255, col[0]))), int(max(0, min(255, col[1]))),
                              int(max(0, min(255, col[2]))), int(max(0, min(255, a * 255))))
            img = Image.new("RGBA", (W, H))
            img.putdata(out)
            # the contrast the cream word holds against the bronze behind it (its band, inside the
            # bevel): the brightest body pixel there, as F1's review measured
            band = [out[y * W + x] for y in range(int(H * 0.36), int(H * 0.64)) for x in range(int(W * 0.3), int(W * 0.7))]
            self.contrast[state] = _contrast((0xff, 0xf7, 0xe2), max(band, key=_luma)[:3])
            base = shadow
            if state == "counting":
                halo = mask.filter(ImageFilter.GaussianBlur(3.5 * _K))
                glow = Image.new("RGBA", mask.size, (*_rgb(sp["halo"]), 0))
                glow.putalpha(halo.point(lambda v: int(min(255, v * 1.6))))
                base = Image.alpha_composite(shadow, glow)
            img = Image.alpha_composite(base, img)
            self.save(f"cta_{state}.png", img, w, h)
            self.stylebox(f"cta_{state}", margin, (margin, 10, margin, 12), expand=inset)
        # the queue's Cancel: the console's stone in a bronze rim, the secondary weight
        stone_top, stone_base = self.bronze["stone_top"], self.bronze["stone_base"]
        for state, lift in (("stone", 1.0), ("stone_hover", 1.18)):
            def field(x, y, lift=lift):
                t = y / H
                return [v * lift for v in C._mix(stone_top, stone_base, C._smooth(t))]

            img = self.rim_relief(mask, rim - 1, "bronze", field, None, rim_light=lift, seed=5, noise=0.22)
            img = Image.alpha_composite(shadow, img)
            self.save(f"cta_{state}.png", img, w, h)
            self.stylebox(f"cta_{state}", margin, (margin, 10, margin, 12), expand=inset)

    def plates(self):
        sp = self.spec["plate"]
        size, r, rim, inset, margin = sp["size"], sp["radius"], sp["rim"], sp["inset"], sp["margin"]
        content = (margin - 2, 10, margin - 6, 10)
        self.save("plate.png", self.framed(size, r, rim + 0.4, inset, metal="bronze", rim_light=1.08, seed=7), *size)
        self.stylebox("plate", margin, content, expand=inset)
        self.save("plate_lit.png", self.framed(size, r, rim + 1.0, inset, metal="bronze", glass="glass_lit",
                                               rim_light=1.32, seed=8), *size)
        self.stylebox("plate_lit", margin, content, expand=inset)
        self.save("plate_empty.png", self.framed(size, r, rim - 0.6, inset, metal="bronze", alpha_scale=0.55,
                                                 rim_light=0.9, seed=9), *size)
        self.stylebox("plate_empty", margin, content, expand=inset)
        cb = self.spec["chip_bar"]
        w, h = cb["size"]
        bw, ins = cb["width"], cb["inset"]
        mask = _mask(w, h, lambda d, k: _rr(d, k, (w - bw) / 2, ins, bw, h - 2 * ins, bw / 2))
        chip = self.rim_relief(mask, bw * 0.5, "gilt", None)
        # grey for the seat's tint: the bevel's light and shade, no gilt hue
        grey = Image.new("RGBA", chip.size)
        grey.putdata([(min(255, int((0.3 * p[0] + 0.59 * p[1] + 0.11 * p[2]) * 1.15)),) * 3 + (p[3],)
                      for p in C._px(chip)])
        self.save("plate_chip.png", grey, w, h)
        self.stylebox("plate_chip", (0, 10, 0, 10), 0)

    def chip(self):
        sp = self.spec["chip"]
        size, r, rim, inset, margin = sp["size"], sp["radius"], sp["rim"], sp["inset"], sp["margin"]
        self.save("chip.png", self.framed(size, r, rim + 0.3, inset, metal="bronze", rim_light=1.1, seed=12), *size)
        self.stylebox("chip", margin, (margin, 6, margin, 7), expand=inset)
        self.save("chip_hover.png", self.framed(size, r, rim + 0.6, inset, metal="bronze", glass="glass_lit",
                                                rim_light=1.35, seed=12), *size)
        self.stylebox("chip_hover", margin, (margin, 6, margin, 7), expand=inset)
        kp = self.spec["key"]
        size, r, rim, inset, margin = kp["size"], kp["radius"], kp["rim"], kp["inset"], kp["margin"]
        stone_top, stone_base = self.bronze["stone_top"], self.bronze["stone_base"]
        w, h = size
        mask = _mask(w, h, lambda d, k: _rr(d, k, inset, inset, w - 2 * inset, h - 2 * inset, r))

        def field(x, y):
            return [v * 1.25 for v in C._mix(stone_top, stone_base, y / (h * _K))]

        img = self.rim_relief(mask, rim, "bronze", field, None, rim_light=1.15, seed=13, noise=0.12)
        img = Image.alpha_composite(_shadow(mask, 1.2, 0.6, 1.2), img)
        self.save("key.png", img, w, h)
        self.stylebox("key", margin, (7, 2, 7, 3), expand=inset)

    def card(self):
        sp = self.spec["card"]
        size, r, rim, inset, margin = sp["size"], sp["radius"], sp["rim"], sp["inset"], sp["margin"]
        content = (margin - 4, margin - 6, margin - 4, margin - 6)
        self.save("card.png", self.framed(size, r, rim, inset, metal="bronze", rim_light=1.05, seed=14), *size)
        self.stylebox("card", margin, content, expand=inset)
        img = self.framed(size, r, rim, inset, rim_light=1.15, seed=14, shadow=False)
        mask = _mask(*size, lambda d, k: _rr(d, k, inset, inset, size[0] - 2 * inset, size[1] - 2 * inset, r))
        glow = Image.new("RGBA", img.size, (*self.g["light"], 0))
        glow.putalpha(mask.filter(ImageFilter.GaussianBlur(3 * _K)).point(lambda v: int(v * 0.8)))
        self.save("card_focus.png", Image.alpha_composite(glow, img), *size)
        self.stylebox("card_focus", margin, content, expand=inset)

    def sheet(self):
        sp = self.spec["sheet"]
        size, r, rim, inset, margin = sp["size"], sp["radius"], sp["rim"], sp["inset"], sp["margin"]
        self.save("sheet.png", self.framed(size, r, rim, inset, metal="bronze", alpha_scale=1.1, seed=15), *size)
        self.stylebox("sheet", margin, (margin - 8, margin - 10, margin - 8, margin - 10), expand=inset)

    def toggles(self):
        sp = self.spec["toggle"]
        w, h = sp["size"]
        kn = sp["knob"]
        track = _mask(w, h, lambda d, k: _rr(d, k, 2, 2, w - 4, h - 4, (h - 4) / 2))
        amber = (_rgb("#d99a3a"), _rgb("#8f4f16"))
        stone = tuple(_rgb(v) for v in sp["off_track"])
        for state in ("on", "off"):
            def field(x, y, state=state):
                t = y / (h * _K)
                if state == "on":
                    return C._mix(amber[0], amber[1], t)
                return C._mix(stone[0], stone[1], t)

            img = self.rim_relief(track, 1.4, "gilt", field, lambda x, y: 1.0, seed=16,
                                  rim_light=1.0 if state == "on" else 0.85)
            cx = (w - 2 - kn / 2 - 1) if state == "on" else (2 + kn / 2 + 1)
            knob = _mask(w, h, lambda d, k, cx=cx: d.ellipse([(cx - kn / 2 + 1) * k, (h / 2 - kn / 2 + 1) * k,
                                                              (cx + kn / 2 - 1) * k, (h / 2 + kn / 2 - 1) * k],
                                                             fill=255))
            kimg = self.rim_relief(knob, kn / 2, "gilt")
            img = Image.alpha_composite(img, Image.alpha_composite(_shadow(knob, 1.2, 0.7, 1.0), kimg))
            self.save(f"toggle_{state}.png", img, w, h)
        knob = _mask(kn, kn, lambda d, k: d.ellipse([1 * k, 1 * k, (kn - 1) * k, (kn - 1) * k], fill=255))
        img = Image.alpha_composite(_shadow(knob, 1.2, 0.7, 1.0), self.rim_relief(knob, kn / 2, "gilt"))
        self.save("knob.png", img, kn, kn)

    def focus(self):
        sp = self.spec["focus"]
        w, h = sp["size"]
        r, width, glow = sp["radius"], sp["width"], sp["glow"]
        pad = glow + 1

        def ring(d, k):
            _rr(d, k, pad, pad, w - 2 * pad, h - 2 * pad, r)
            _rr(d, k, pad + width, pad + width, w - 2 * (pad + width), h - 2 * (pad + width), max(1, r - width),
                fill=0)

        mask = _mask(w, h, ring)
        color = _rgb(sp["color"])
        soft = mask.filter(ImageFilter.GaussianBlur(glow * _K * 0.6))
        halo = Image.new("RGBA", mask.size, (*color, 0))
        halo.putalpha(soft.point(lambda v: int(min(255, v * 1.4))))
        line = Image.new("RGBA", mask.size, (*color, 0))
        line.putalpha(mask)
        self.save("focus.png", Image.alpha_composite(halo, line), w, h)
        self.stylebox("focus", pad + r, 0, expand=pad)

    def scrims(self):
        sp = self.spec["scrim"]
        w, h = sp["size"]
        color = _rgb(sp["color"])
        for name, strength, down in (("scrim_top", sp["top"], False), ("scrim_bottom", sp["bottom"], True)):
            img = Image.new("RGBA", (w * _K, h * _K))
            px = img.load()
            H = h * _K
            for y in range(H):
                t = y / (H - 1)
                t = t if down else 1.0 - t
                a = strength * C._smooth(t) ** 0.85
                for x in range(w * _K):
                    px[x, y] = (*color, int(255 * a))
            self.save(f"{name}.png", img, w, h)
        # the corner scrim: densest in the bottom-right corner, fading out along an ellipse, so
        # it sits behind one cluster and leaves the rest of the stage clear (a mirrored copy
        # serves the bottom-left)
        cw, ch = sp.get("corner", [256, 128])
        strength = sp.get("corner_strength", sp["bottom"])
        img = Image.new("RGBA", (cw * _K, ch * _K))
        px = img.load()
        W, H = cw * _K, ch * _K
        for y in range(H):
            for x in range(W):
                dx = (W - 1 - x) / (W - 1)
                dy = (H - 1 - y) / (H - 1)
                r = math.sqrt(dx * dx + dy * dy)
                a = strength * C._smooth(max(0.0, 1.0 - r)) ** 0.9
                px[x, y] = (*color, int(255 * a))
        self.save("scrim_corner.png", img, cw, ch)

    def marks(self):
        """The seat glyphs as carved into a mark's stone: white where the cut is, with a soft
        bevel down into it, for the mark's material to tint (paint in the seat's colour on a
        crew's mark, plain shadow on a bare one)."""
        n = self.spec["mark"]["size"] // self.scale  # layout px: the PNG is `size` texels
        c, r = n / 2, n * 0.36

        shapes = {
            "diamond": lambda d, k: d.polygon([(c * k, (c - r) * k), ((c + r) * k, c * k), (c * k, (c + r) * k),
                                               ((c - r) * k, c * k)], fill=255),
            "circle": lambda d, k: d.ellipse([(c - r * 0.82) * k, (c - r * 0.82) * k, (c + r * 0.82) * k,
                                              (c + r * 0.82) * k], fill=255),
            "triangle": lambda d, k: d.polygon([(c * k, (c - r) * k), ((c + r) * k, (c + r * 0.72) * k),
                                                ((c - r) * k, (c + r * 0.72) * k)], fill=255),
            "square": lambda d, k: d.rectangle([(c - r * 0.72) * k, (c - r * 0.72) * k, (c + r * 0.72) * k,
                                                (c + r * 0.72) * k], fill=255),
        }
        for name, fn in shapes.items():
            mask = _mask(n, n, fn)
            w, h = mask.size
            m = C._field(mask)
            dist = C._inside(m, w, h)
            out = []
            bevel = 2.2 * _K
            for i, v in enumerate(m):
                depth = min(1.0, dist[i] / bevel)
                out.append((int(255 * (0.55 + 0.45 * depth)),) * 3 + (int(255 * v),))
            img = Image.new("RGBA", (w, h))
            img.putdata(out)
            self.save(f"mark_{name}.png", img, n, n)

    def emblems(self):
        """The Modes band's emblems, gilt line work raised from the card: High Water's arc of the
        four seat marks, Tide Race's two crews over water with a gap, Undertow's two marks face to
        face over a corked bottle."""
        n = self.spec["emblem"]["size"]

        def glyph(d, k, shape, cx, cy, r):
            if shape == "diamond":
                d.polygon([(cx * k, (cy - r) * k), ((cx + r) * k, cy * k), (cx * k, (cy + r) * k), ((cx - r) * k, cy * k)],
                          fill=255)
            elif shape == "circle":
                d.ellipse([(cx - r * 0.85) * k, (cy - r * 0.85) * k, (cx + r * 0.85) * k, (cy + r * 0.85) * k], fill=255)
            elif shape == "triangle":
                d.polygon([(cx * k, (cy - r) * k), ((cx + r) * k, (cy + r * 0.75) * k), ((cx - r) * k, (cy + r * 0.75) * k)],
                          fill=255)
            elif shape == "square":
                d.rectangle([(cx - r * 0.75) * k, (cy - r * 0.75) * k, (cx + r * 0.75) * k, (cy + r * 0.75) * k], fill=255)
            elif shape == "right":
                d.polygon([((cx - r) * k, (cy - r) * k), ((cx + r) * k, cy * k), ((cx - r) * k, (cy + r) * k)], fill=255)
            elif shape == "left":
                d.polygon([((cx + r) * k, (cy - r) * k), ((cx - r) * k, cy * k), ((cx + r) * k, (cy + r) * k)], fill=255)

        def wave(d, k, x0, x1, y, amp, width):
            pts = []
            steps = 24
            for s in range(steps + 1):
                x = x0 + (x1 - x0) * s / steps
                pts.append((x * k, (y + amp * math.sin((x - x0) / (x1 - x0) * math.pi * 3)) * k))
            d.line(pts, fill=255, width=max(1, int(width * k)), joint="curve")

        def high_water(d, k):
            # four marks along a shallow arc, the inner two forward (the crew's arc)
            for shape, cx, cy in (("diamond", 7, 22), ("circle", 15.5, 27), ("triangle", 24.5, 27), ("square", 33, 22)):
                glyph(d, k, shape, cx, cy, 4.6)
            wave(d, k, 4, 36, 35.5, 0.9, 1.6)

        def tide_race(d, k):
            # two crews of two, a gap between them, each over its own still water
            for cx in (7.0, 13.5, 26.5, 33.0):
                glyph(d, k, "circle", cx, 17, 3.6)
                d.rectangle([(cx - 2.2) * k, 20.5 * k, (cx + 2.2) * k, 27 * k], fill=255)
            for x0, x1 in ((3, 17.5), (22.5, 37)):
                d.line([(x0 * k, 31 * k), (x1 * k, 31 * k)], fill=255, width=int(1.6 * k))
                d.line([((x0 + 2) * k, 35 * k), ((x1 - 2) * k, 35 * k)], fill=255, width=int(1.2 * k))

        def undertow(d, k):
            # two marks face to face, a corked bottle afloat between them
            glyph(d, k, "right", 8.5, 20, 6.0)
            glyph(d, k, "left", 31.5, 20, 6.0)
            d.rounded_rectangle([17.0 * k, 17 * k, 23.0 * k, 29 * k], radius=2.4 * k, fill=255)
            d.rectangle([18.6 * k, 13.2 * k, 21.4 * k, 16.4 * k], fill=255)
            wave(d, k, 4, 36, 32.5, 1.3, 1.6)

        gold = C._mix(self.g["base"], self.g["light"], 0.35)
        for name, fn in (("high_water", high_water), ("tide_race", tide_race), ("undertow", undertow)):
            mask = _mask(n, n, fn)
            # (solid gilt, its edges lit: at the card's size an outline alone thinned to hairlines)
            relief = self.rim_relief(mask, 1.2, "gilt", lambda x, y: gold, lambda x, y: 1.0)
            img = Image.alpha_composite(_shadow(mask, 0.8, 0.75, 0.8), relief)
            self.save(f"mode_{name}.png", img, n, n)
        # the copy glyph inside the party's chip: two pages, the front one outlined
        c = 20

        def copy(d, k):
            d.rounded_rectangle([3 * k, 2 * k, 13 * k, 14 * k], radius=1.8 * k, outline=255, width=int(1.7 * k))
            d.rounded_rectangle([7 * k, 6 * k, 17 * k, 18 * k], radius=1.8 * k, fill=255)
            d.rounded_rectangle([8.8 * k, 7.8 * k, 15.2 * k, 16.2 * k], radius=1.0 * k, fill=0)

        mask = _mask(c, c, copy)
        relief = self.rim_relief(mask, 0.8, "gilt", lambda x, y: gold, lambda x, y: 1.0)
        img = Image.alpha_composite(_shadow(mask, 0.6, 0.7, 0.6), relief)
        self.save("copy.png", img, c, c)

    def gear(self):
        n = self.spec["gear"]["size"]
        c = n / 2
        teeth, r_out, r_in, hole = 8, n * 0.44, n * 0.33, n * 0.14

        def draw(d, k):
            pts = []
            steps = teeth * 16
            for s in range(steps):
                a = 2 * math.pi * s / steps
                phase = (s % 16) / 16
                rr = r_out if 0.12 < phase < 0.5 else r_in
                pts.append(((c + math.cos(a) * rr) * k, (c + math.sin(a) * rr) * k))
            d.polygon(pts, fill=255)
            d.ellipse([(c - hole) * k, (c - hole) * k, (c + hole) * k, (c + hole) * k], fill=0)

        mask = _mask(n, n, draw)
        img = Image.alpha_composite(_shadow(mask, 0.8, 0.8, 0.8), self.rim_relief(mask, n * 0.12, "gilt"))
        self.save("gear.png", img, n, n)

    def paint(self) -> list[Path]:
        self.dest.mkdir(parents=True, exist_ok=True)
        random.seed(self.seed)
        for piece in (self.bar, self.tab, self.cta, self.plates, self.chip, self.card, self.sheet, self.toggles,
                      self.focus, self.scrims, self.marks, self.emblems, self.gear):
            piece()
        return self.written


def front(spec: dict | None, dest: Path, res_base: str, console_spec: dict | None = None,
          unchanged: set | None = None) -> list[Path]:
    painter = _Front(spec or {}, dest, res_base, console_spec or {})
    written = painter.paint()
    if unchanged is not None:
        unchanged.update(painter.unchanged)
    return written


def main(argv: list[str]) -> int:
    project = Path(__file__).resolve().parents[2]
    spec_rel = argv[0] if argv else "art_src/ui/front.json"
    dest_rel = argv[1] if len(argv) > 1 else "ui/front"
    spec = json.loads((project / spec_rel).read_text())
    console_spec = json.loads((project / "art_src/ui/console.json").read_text())
    unchanged: set[Path] = set()
    written = front(spec, project / dest_rel, f"res://{dest_rel}", console_spec, unchanged)
    script = Path(__file__).resolve().relative_to(project).as_posix()
    C.record(project, [f for f in written if f.suffix in (".png", ".tres")],
             {"tool": "script", "script": script, "spec": spec_rel, "dest": dest_rel,
              "regen": f"python3 {script} {spec_rel} {dest_rel}"}, keep=unchanged)
    for f in written:
        print(f"wrote {f.relative_to(project).as_posix()}")
    return 0


def cta_contrast(spec: dict | None = None) -> dict:
    """The cream word's contrast against the brightest bronze behind it, by state (painted
    afresh, nothing written): the call to action holds 4.5:1 or better."""
    import tempfile
    project = Path(__file__).resolve().parents[2]
    console_spec = json.loads((project / "art_src/ui/console.json").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        painter = _Front(spec or json.loads((project / "art_src/ui/front.json").read_text()), Path(tmp),
                         "res://tmp", console_spec)
        painter.dest.mkdir(parents=True, exist_ok=True)
        painter.cta()
        return dict(painter.contrast)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
