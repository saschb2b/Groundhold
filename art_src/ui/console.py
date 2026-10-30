#!/usr/bin/env python3
"""Paints the console art in ui/console/ from art_src/ui/console.json.

    python3 art_src/ui/console.py            # from the project root; rewrites ui/console/*

Every piece of the bottom console (two wings with a recessed well each, the arched
crest round the portrait window, the rail that joins them, the resource strip, the
end plate, the banner and the small nine-slices: tooltip, button states, the hover
glow) is a silhouette turned into a height field and lit as weathered bronze over
stone from the top left. The screens outside a match (hub, party, join, Builders,
loading, results) reuse that material: a large panel whose stone tiles both ways, the
jewel to crown one panel per screen, a card frame and its lit state, an arched portrait
plate, a sunk text field and its focus, a progress bar's trough and gilt fill, and an
incised divider. One bronze rim follows the silhouette and meets curves in
round fillets; the wells are cut into the stone and read by their shade; the portrait
window, the focal point, gets the one moulding and the crest above it the one jewel.
With "scale": 2 the PNGs carry twice the texels of the layout (and mipmaps), the
StyleBoxTexture margins are in texels, and layout.json gives the HUD every rectangle
in layout pixels with the scale alongside, so code and art cannot drift.

Seeded and deterministic: the same spec writes the same bytes. The game owns this
painter (only Pillow is needed); it records its outputs in asset_manifest.json with
"tool": "script", so the manifest says how each file was made. A file whose bytes come
out as they were is left alone, and so is its manifest entry (its "updated" stamp too).
"""

from __future__ import annotations

import io
import json
import math
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

GILT = ("#3a2508", "#a77a2c", "#ffe9a8")  # dark, base and light of the banner's gilt rule


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _mix(a, b, t: float):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


# Every key the spec may set, with its default. Sizes are in layout pixels.
CONSOLE = {
    "seed": 7,
    "scale": 1,
    "rail": 28,  # height of the band that joins the pieces
    "shadow": 14,  # room above each piece for its shadow on the world
    "rim": 6,  # width of the bronze rim along every silhouette
    "grooves": [],  # incised lines at these distances inside the rim
    "fillet": 10,  # radius where the arch meets the flats beside it
    "socket": {"wall": 4, "bead": 0, "depth": 5.0},
    "wing": {"size": [240, 140], "slope": [178, 226], "well": [16, 14, 168, 112]},
    "card": {"socket": 54, "gap": [3, 4]},
    "centre": {
        "width": 572,
        "height": 184,
        "crest": {"x": 116, "radius": 86, "base": 80, "rise": [8, 34]},
        # The one jewel: a pointed bronze keystone over the arch holding an amber gem, and
        # two short flanges swept along the arch from its sides.
        "keystone": {"half": 14, "rise": 28, "drop": 10, "gem": 6.5},
        "flanges": {"width": 10, "from": 10, "to": 42, "lift": 5},
        "window": [54, 14, 124, 128],
        "moulding": 10,
        "shoulder": [200, 534, 106],
        "text": [214, 8, 308, 84],
        "incised": 0,
    },
    "strip": {"height": 34, "cap": 44, "period": 64},
    "plate": [460, 200],
    # Behind titles: a soft band the HUD stretches to the title, and a gilt rule (one half,
    # mirrored) with a small diamond under it.
    "banner": {"band": [512, 64], "rule": [128, 4], "gem": 12},
    "button": [96, 40],
    "tooltip": [64, 64],
    "portrait": {"centre": "#2a2620", "edge": "#0e0c0a", "key": "#30291f"},
    "material": {
        "dark": "#1c130c", "mid": "#604428", "worn": "#d6a464", "patina": "#30463c",
        "stone_top": "#3b342c", "stone_base": "#1f1b17", "spec": "#ffdaa0", "hollow": "#0b0908",
        "ember": "#ffb054",
    },
    # The stone: how far down the ramp from stone_top to stone_base runs, and the strength
    # of its value noise at three scales (as a share of the value) plus its pits.
    "stone": {"ramp": 96, "macro": 0.10, "meso": 0.07, "fine": 0.05, "pits": 0.3},
    # Where the rim meets the stone: a light catch on the bronze lip, then a shadow on the
    # stone under it, so the stone sits below the bronze.
    "lip": {"catch": 0.25, "shade": 0.4, "shade_width": 2},
    # The console's shadow on the world: how far it reaches and how dark it starts.
    "cast": {"reach": 5, "dark": 0.45},
    # The screens' pieces. The panel is a nine-slice whose middle tiles: `tile` (width,
    # height) layout pixels of stone that repeat both ways between `margin`s, wider than
    # tall because panels are, the silhouette `inset` from
    # the texture's edge (room for its shadow) with corners of `radius`. Its stone is the
    # console's made quieter for text to sit on (`stone` overrides the console's: smaller
    # clouds, so a tile holds several and its repeat does not show; `macro_cell` and
    # `meso_cell` are their sizes), falling from stone_top under the top rim to
    # `stone_base` over `stone.ramp` pixels, all inside the margin.
    "panel": {"tile": [256, 128], "margin": 32, "inset": 8, "radius": 12, "content": [22, 20, 22, 20],
              "stone_base": "#29241e",
              "stone": {"ramp": 18, "macro": 0.055, "meso": 0.06, "fine": 0.045, "pits": 0.12, "macro_cell": 22,
                        "meso_cell": 9}},
    # The jewel that crowns a panel: its canvas, and the height (from its top) of the line
    # it seats on, the panel's top edge.
    "jewel": {"size": [136, 64], "seat": 40},
    "card_frame": {"size": [96, 96], "radius": 8, "rim": 4, "margin": 16, "content": [14, 12, 14, 12]},
    # An arched window for a portrait on a card: the window, the stone round it, the shadow.
    "portrait_plate": {"window": [112, 120], "border": 18, "moulding": 8, "shadow": 6},
    "field": {"size": [64, 40], "radius": 5, "rim": 3, "margin": 10, "content": [12, 6, 12, 6], "height": 30,
              "code": {"cell": [30, 38], "gap": 5, "dash": 14}},
    "bar": {"trough": [64, 18], "fill": [48, 10], "inset": [4, 4]},
    "divider": [128, 6],
}
_S = 2  # painting scale: twice the output scale, box-filtered down
_LIGHT = (-0.42, -0.78, 0.46)


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def _unit(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


_L = _unit(_LIGHT)
_H = _unit((_L[0], _L[1], _L[2] + 1.0))
_L2 = _unit((_L[0], _L[1]))  # the light's direction across the screen


def _blur(f, w, h, r, passes=3):
    """Separable box blur on a flat float list; three passes approximate a gaussian, edges clamp."""
    if r <= 0:
        return list(f)
    n = 2 * r + 1
    for _ in range(passes):
        out = [0.0] * (w * h)
        for y in range(h):
            row = y * w
            s = f[row] * (r + 1) + sum(f[row + min(k, w - 1)] for k in range(1, r + 1))
            for x in range(w):
                out[row + x] = s / n
                s += f[row + min(x + r + 1, w - 1)] - f[row + max(x - r, 0)]
        f = out
        if h == 1:
            continue
        out = [0.0] * (w * h)
        for x in range(w):
            s = f[x] * (r + 1) + sum(f[min(k, h - 1) * w + x] for k in range(1, r + 1))
            for y in range(h):
                out[y * w + x] = s / n
                s += f[min(y + r + 1, h - 1) * w + x] - f[max(y - r, 0) * w + x]
        f = out
    return f


def _inside(m, w, h):
    """Chamfer distance from each inside pixel to the nearest outside one. The canvas border
    is not an edge: shapes may run off the canvas (the screen edge) without a bevel."""
    inf = 1e9
    d = [0.0 if v < 0.5 else inf for v in m]
    a, b = 1.0, 1.4142
    for y in range(h):
        row = y * w
        for x in range(w):
            i = row + x
            v = d[i]
            if v == 0.0:
                continue
            if x > 0 and d[i - 1] + a < v:
                v = d[i - 1] + a
            if y > 0:
                j = i - w
                if d[j] + a < v:
                    v = d[j] + a
                if x > 0 and d[j - 1] + b < v:
                    v = d[j - 1] + b
                if x < w - 1 and d[j + 1] + b < v:
                    v = d[j + 1] + b
            d[i] = v
    for y in range(h - 1, -1, -1):
        row = y * w
        for x in range(w - 1, -1, -1):
            i = row + x
            v = d[i]
            if v == 0.0:
                continue
            if x < w - 1 and d[i + 1] + a < v:
                v = d[i + 1] + a
            if y < h - 1:
                j = i + w
                if d[j] + a < v:
                    v = d[j] + a
                if x < w - 1 and d[j + 1] + b < v:
                    v = d[j + 1] + b
                if x > 0 and d[j - 1] + b < v:
                    v = d[j - 1] + b
            d[i] = v
    return d


def _px(img):
    return list(img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata())


def _field(img):
    return [v / 255.0 for v in _px(img)]


def _noise(w, h, cell, seed, period_x=None, period_y=None):
    """Smooth value noise in [0, 1] from an upscaled random grid; repeats every period_x
    (and with period_y, down too: a tile that repeats both ways)."""
    rng = random.Random(seed)
    if period_x and period_y:
        gx, gy = max(1, round(period_x / cell)), max(1, round(period_y / cell))
        grid = Image.new("L", (gx, gy))
        grid.putdata([rng.randrange(256) for _ in range(gx * gy)])
        tiled = Image.new("L", (gx * 3, gy * 3))
        for i in range(3):
            for j in range(3):
                tiled.paste(grid, (i * gx, j * gy))
        tile = tiled.resize((period_x * 3, period_y * 3), Image.BICUBIC).crop(
            (period_x, period_y, period_x * 2, period_y * 2))
        img = Image.new("L", (w, h))
        for y in range(0, h, period_y):
            for x in range(0, w, period_x):
                img.paste(tile, (x, y))
    elif period_x:
        gw, gh = max(1, round(period_x / cell)), h // cell + 4
        grid = Image.new("L", (gw, gh))
        grid.putdata([rng.randrange(256) for _ in range(gw * gh)])
        tiled = Image.new("L", (gw * 3, gh))
        for k in range(3):
            tiled.paste(grid, (k * gw, 0))
        big = tiled.resize((period_x * 3, gh * cell), Image.BICUBIC)
        strip = big.crop((period_x, cell, period_x * 2, cell + h))
        img = Image.new("L", (w, h))
        for x in range(0, w, period_x):
            img.paste(strip, (x, 0))
    else:
        gw, gh = w // cell + 4, h // cell + 4
        grid = Image.new("L", (gw, gh))
        grid.putdata([rng.randrange(256) for _ in range(gw * gh)])
        img = grid.resize((gw * cell, gh * cell), Image.BICUBIC).crop((cell, cell, cell + w, cell + h))
    return _field(img)


def _octaves(w, h, seed, period_x=None, base=40, octaves=4, period_y=None):
    total = [0.0] * (w * h)
    amp, norm, cell = 1.0, 0.0, base
    for o in range(octaves):
        n = _noise(w, h, max(2, int(cell)), seed * 31 + o, period_x, period_y)
        for i in range(w * h):
            total[i] += n[i] * amp
        norm += amp
        amp *= 0.5
        cell /= 2
    return [v / norm for v in total]


def _smooth(t):
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return t * t * (3 - 2 * t)


def _normal(f):
    """The field shifted and scaled to mean 0 and standard deviation 1."""
    n = len(f)
    mean = sum(f) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in f) / n) or 1.0
    return [(v - mean) / sd for v in f]


def _clip(v, limit=2.5):
    return -limit if v < -limit else (limit if v > limit else v)


def _ogee(x, x0, x1, h0, h1):
    return h0 + (h1 - h0) * _smooth((x - x0) / (x1 - x0))


def _fillet(cx, base, radius, line, f, side):
    """Height on the arc of radius f that rounds the inside corner where an arch (a circle of
    `radius` round (cx, base)) meets a flat at height `line`, on side -1 (left) or 1 (right);
    -inf off the arc. Heights are measured up from the bottom edge."""
    dy = line + f - base
    reach = (radius + f) ** 2 - dy * dy
    if f <= 0 or line <= base or reach <= 0:
        return lambda x: -math.inf
    xf = cx + side * math.sqrt(reach)
    xt = cx + (xf - cx) * radius / (radius + f)
    lo, hi = min(xt, xf), max(xt, xf)

    def arc(x):
        if lo <= x <= hi:
            return line + f - math.sqrt(max(0.0, f * f - (x - xf) ** 2))
        return -math.inf
    return arc


def _profile_mask(width, height, top, ext=40):
    """Mask of everything below top(x) (height above the bottom edge, 1x units), antialiased."""
    k = 4 * _S
    img = Image.new("L", (width * k, height * k), 0)
    points, x = [], -ext
    while x <= width + ext:
        points.append((x * k, (height - top(x)) * k))
        x += 0.25
    points += [((width + ext) * k, (height + ext) * k), (-ext * k, (height + ext) * k)]
    ImageDraw.Draw(img).polygon(points, fill=255)
    return img.resize((width * _S, height * _S), Image.BOX)


def _shape_mask(width, height, draw_fn):
    """Mask drawn by draw_fn(draw, k) in 1x units multiplied by k, antialiased."""
    k = 4 * _S
    img = Image.new("L", (width * k, height * k), 0)
    draw_fn(ImageDraw.Draw(img), k)
    return img.resize((width * _S, height * _S), Image.BOX)


def _arch(draw, k, x, bottom, w, h, canvas_h, fill=255):
    """An arch-topped window: straight sides, a half circle of radius w/2 on top."""
    r = w / 2
    top = canvas_h - (bottom + h - r)
    draw.rectangle([x * k, top * k, (x + w) * k, (canvas_h - bottom) * k], fill=fill)
    draw.ellipse([x * k, (top - r) * k, (x + w) * k, (top + r) * k], fill=fill)


def _rrect(draw, k, x, y, w, h, r, fill=255):
    draw.rounded_rectangle([x * k, y * k, (x + w) * k, (y + h) * k], radius=max(0, r) * k, fill=fill)


def _keystone_points(cx, base_y, top_y, half):
    """A pointed keystone, base at base_y and tip at top_y (image y grows down): its sides
    swell to `half` a third of the way up, then sweep in, concave, to a sharp tip."""
    right = []
    n = 72
    for i in range(n + 1):
        u = i / n  # 0 at the base, 1 at the tip
        if u < 0.34:
            w = half * (0.8 + 0.2 * math.sin(u / 0.34 * math.pi / 2))
        else:
            w = half * math.cos((u - 0.34) / 0.66 * math.pi / 2) ** 1.7
        right.append((cx + w, base_y + (top_y - base_y) * u))
    left = [(2 * cx - x, y) for x, y in reversed(right)]
    return right + left


def _flange_points(cx, cy, radius, side, s0, s1, width, lift):
    """A short swept blade along the circle of `radius` round (cx, cy), on side -1 (left)
    or 1 (right): from arc length s0 past the top to s1, `width` thick at its root and
    tapering to a point that lifts `lift` off the circle, so light shows under its tip."""
    outer, inner = [], []
    n = 72
    for i in range(n + 1):
        t = i / n
        a = (s0 + (s1 - s0) * t) / radius  # radians from straight up
        half = width / 2 * (1 - t) ** 0.85
        mid = radius + width / 2 - 1.5 + lift * t ** 1.6
        ux, uy = side * math.sin(a), -math.cos(a)
        outer.append((cx + ux * (mid + half), cy + uy * (mid + half)))
        inner.append((cx + ux * (mid - half), cy + uy * (mid - half)))
    return outer + list(reversed(inner))


def _fuller_points(cx, cy, radius, side, s0, s1, width):
    """The groove down the middle of a flange (as on a blade), a little short of its tip."""
    pts = []
    n = 48
    for i in range(n + 1):
        t = i / n
        a = (s0 + (s1 - s0) * 0.62 * t) / radius
        mid = radius + width / 2 - 1.5
        pts.append((cx + side * math.sin(a) * mid, cy - math.cos(a) * mid))
    return pts


def _polygon(draw, k, pts, fill=255):
    draw.polygon([(x * k, y * k) for x, y in pts], fill=fill)


class _Relief:
    """A silhouette plus relief, lit as weathered bronze over stone."""

    def __init__(self, width, height, mask, seed, material, period_x=None, band=6.0, grooves=(), look=None,
                 period_y=None):
        self.w, self.h = width * _S, height * _S
        self.width, self.height = width, height
        self.mask_img = mask
        self.mask = _field(mask)
        self.seed = seed
        self.m = material
        self.look = look or {k: CONSOLE[k] for k in ("stone", "lip", "cast")}
        self.period_x = period_x * _S if period_x else None
        self.period_y = period_y * _S if period_y else None  # with period_x: the stone tiles both ways
        self.wells = []  # (field, depth, colour, window, wall)
        self.ornament = [0.0] * (self.w * self.h)
        self.bronze = [0.0] * (self.w * self.h)
        self.gems = []
        self.grooves = list(grooves)
        self.band = float(band)  # width of the bronze rim along the silhouette; stone inside it

    def extend(self, mask_img):
        """Adds a shape to the silhouette (an ornament that breaks its outline)."""
        self.mask_img = ImageChops.lighter(self.mask_img, mask_img)
        self.mask = _field(self.mask_img)

    def add_well(self, mask_img, depth=6.0, color=None, window=False, wall=2.2):
        self.wells.append((_field(mask_img), depth, color or self.m["hollow"], window, wall))

    def add_ornament(self, mask_img, height=2.6, soften=1, bronze=True, bevel=0.0):
        """Raises a shape `height` above the surface. With `bevel` (layout pixels) its edges
        are flat chamfers that wide, which catch the light crisply at any size; without, it
        is a soft swelling."""
        f = _field(mask_img)
        cover = f
        if bevel > 0:
            d = _inside([1.0 if v >= 0.5 else 0.0 for v in f], self.w, self.h)
            bw = bevel * _S
            f = [min(1.0, max(0.0, (di + v - 0.5) / bw)) if v > 0 else 0.0 for di, v in zip(d, f)]
        elif soften:
            f = _blur(f, self.w, self.h, soften, passes=1)
        for i, v in enumerate(f):
            self.ornament[i] += v * height * _S
            if bronze and cover[i] > self.bronze[i]:
                self.bronze[i] = cover[i]

    def add_bronze(self, mask_img):
        for i, v in enumerate(_field(mask_img)):
            if v > self.bronze[i]:
                self.bronze[i] = v

    def add_frame(self, mask_img, width, height=3.0):
        """One rounded bronze moulding `width` wide round the outside of a shape (the
        portrait window): it rises from the opening, crowns half way and falls to the rim."""
        f = _field(mask_img)
        out = _inside([1.0 - v for v in f], self.w, self.h)
        wpx = width * _S
        for i, d in enumerate(out):
            if 0.0 < d < wpx + 2 * _S:
                t = min(1.0, d / wpx)
                self.ornament[i] += height * _S * math.sin(math.pi * t) ** 0.55
                edge = 1.0 - _smooth((d - wpx) / (1.4 * _S) + 0.5)
                if edge > self.bronze[i]:
                    self.bronze[i] = edge

    def add_gem(self, x, y, r):
        self.gems.append((x * _S, y * _S, r * _S))

    def add_socket(self, x, y, w, h, radius=4, wall=4, bead=0, depth=5.0):
        """A well cut into the stone for a widget drawn over it (minimap, command card): its
        walls fall into shade at the top and left and catch the light on the lower lip. A
        bead > 0 rings it in bronze. (x, y, w, h) is the content rectangle in 1x pixels."""
        W, H = self.width, self.height
        self.add_well(_shape_mask(W, H, lambda d, k: _rrect(d, k, x - wall, y - wall, w + 2 * wall, h + 2 * wall,
                                                            radius + wall)), depth=depth, wall=wall)
        if bead <= 0:
            return

        def ring(d, k):
            _rrect(d, k, x - wall - bead, y - wall - bead, w + 2 * (wall + bead), h + 2 * (wall + bead),
                   radius + wall + bead)
            _rrect(d, k, x - wall, y - wall, w + 2 * wall, h + 2 * wall, radius + wall, fill=0)

        self.add_ornament(_shape_mask(W, H, ring), height=1.8)

    def paint(self):
        w, h, n, m = self.w, self.h, self.w * self.h, self.m
        dist = _inside(self.mask, w, h)
        band = self.band * _S
        # The rim is a bead: it rises steeply from the outer edge to a crown a third of the
        # way in (which catches the light and the glint), then falls gently toward the stone,
        # so it reads as cast metal with a highlight, a body and a shaded inner edge.
        crown = 0.36 * band
        fall = 0.27 * band
        rise = 5.4 * _S + fall  # the inner edge ends where the stone's level starts
        height = [0.0] * n
        bronze = [0.0] * n
        for i in range(n):
            d = dist[i]
            if d < crown:
                hv = rise * math.sin(math.pi / 2 * d / crown)
            else:
                hv = rise - fall * _smooth((d - crown) / (band - crown))
            b = 1.0 - _smooth((d - band) / (1.6 * _S) + 0.5)
            # the rim's inner edge: a chamfer down to the stone
            hv -= (1 - b) * 2.6 * _S
            orn = self.ornament[i]
            bronze[i] = max(b, self.bronze[i])
            if bronze[i] < 0.5:
                for g in self.grooves:
                    e = (d - g * _S) / (0.8 * _S)
                    if -3 < e < 3:
                        hv -= 1.2 * _S * math.exp(-e * e)
            height[i] = hv + orn
        well_any = [0.0] * n
        window = [0.0] * n
        well_color = [None] * n
        for wf, depth, color, is_window, wall in self.wells:
            wd = _inside([1.0 if v >= 0.5 else 0.0 for v in wf], w, h)
            for i in range(n):
                if wf[i] > 0.02:
                    t = min(wd[i] / (wall * _S), 1.0)
                    height[i] -= depth * _S * _smooth(t) + depth * _S * 0.25 * wf[i]
                    if wf[i] > well_any[i]:
                        well_any[i] = wf[i]
                        well_color[i] = color
                    if is_window:
                        window[i] = max(window[i], wf[i])
        height = _blur(height, w, h, max(1, _S // 2), passes=2)
        broad = _blur(height, w, h, 3 * _S, passes=2)

        # Which way the silhouette faces, from a blurred mask: runs that face the light are
        # brighter, and the inside corners (more of the piece round them than along a
        # straight edge) gather patina.
        soft = _blur(self.mask, w, h, 4 * _S, passes=2)
        corner_r = 4 * _S
        wide = _blur(self.mask, w, h, corner_r, passes=2)
        line = max(8, int(corner_r * 4))
        step = _blur([0.0] * line + [1.0] * line, 2 * line, 1, corner_r, passes=2)
        ytop = [h] * w
        for x in range(w):
            for y in range(h):
                if self.mask[y * w + x] >= 0.5:
                    ytop[x] = y
                    break

        py = self.period_y
        tone = _octaves(w, h, self.seed, self.period_x, base=36 * _S, period_y=py)
        grain = _noise(w, h, 2 * _S, self.seed + 5, self.period_x, py)
        blotch = _octaves(w, h, self.seed + 9, self.period_x, base=14 * _S, octaves=2, period_y=py)
        streak = _noise(w, h, 22 * _S, self.seed + 17, self.period_x, py)
        # The stone's value noise, each scale normalised so its strength is what the spec says:
        # broad clouds (40-80 px), knots (10-20 px) and a fine grain (2-3 px), plus pits.
        st, lip = self.look["stone"], self.look["lip"]
        macro = _normal(_octaves(w, h, self.seed + 13, self.period_x, base=st.get("macro_cell", 56) * _S, octaves=2,
                                 period_y=py))
        meso = _normal(_octaves(w, h, self.seed + 21, self.period_x, base=st.get("meso_cell", 14) * _S, octaves=2,
                                period_y=py))
        fine = _normal(_noise(w, h, max(2, round(2.5 * _S)), self.seed + 6, self.period_x, py))
        pits = _noise(w, h, max(2, round(1.5 * _S)), self.seed + 23, self.period_x, py)
        flat = 0.36 + 1.1 * _L[2]  # how the light shades a flat face: the stone's colours are what shows

        glow = [0.0] * n  # warm light from an amber gem
        for gx, gy, gr in self.gems:
            for y in range(h):
                for x in range(w):
                    glow[y * w + x] += math.exp(-max(0.0, math.hypot(x - gx, (y - gy) * 1.15) - gr) / (16.0 * _S))

        dark, mid, worn, patina = m["dark"], m["mid"], m["worn"], m["patina"]
        s_top, s_base, spec, ember = m["stone_top"], m["stone_base"], m["spec"], m["ember"]
        rgba = [(0, 0, 0, 0)] * n
        for y in range(h):
            for x in range(w):
                i = y * w + x
                a = self.mask[i]
                if a <= 0.0:
                    continue
                hl = height[i - 1] if x > 0 else height[i]
                hr = height[i + 1] if x < w - 1 else height[i]
                hu = height[i - w] if y > 0 else height[i]
                hd = height[i + w] if y < h - 1 else height[i]
                nx, ny = (hl - hr) * 0.5, (hu - hd) * 0.5
                inv = 1.0 / math.sqrt(nx * nx + ny * ny + 1.0)
                nx, ny, nz = nx * inv, ny * inv, inv
                dif = max(0.0, nx * _L[0] + ny * _L[1] + nz * _L[2])
                ndh = max(0.0, nx * _H[0] + ny * _H[1] + nz * _H[2])
                cav = min(1.0, max(0.0, (broad[i] - height[i]) / (2.0 * _S)))
                vex = min(1.0, max(0.0, (height[i] - broad[i]) / (1.4 * _S)))
                t = tone[i] * 0.75 + grain[i] * 0.25
                b = bronze[i]
                # facing of the silhouette here: 1 toward the light, -1 away from it
                gx = soft[i + 1] - soft[i - 1] if 0 < x < w - 1 else 0.0
                gy = soft[i + w] - soft[i - w] if 0 < y < h - 1 else 0.0
                gm = math.hypot(gx, gy)
                facing = 0.0
                if gm > 1e-5:
                    facing = (-gx * _L2[0] - gy * _L2[1]) / gm * min(1.0, gm * 6 * _S)
                d = dist[i]
                corner = 0.0
                if d < band + 4 * _S:
                    ref = step[min(2 * line - 1, line + max(0, int(d)) - 1)]
                    corner = min(1.0, max(0.0, (wide[i] - ref) * 4.0))
                # bronze: dark, mottled, streaked along its length, patina in the crevices
                # and inside corners, worn bright on the edges
                lit_run = 1.0 + 0.24 * facing
                metal = [(dark[c] + (mid[c] - dark[c]) * (0.3 + 0.7 * t)) * (0.86 + 0.28 * streak[i]) * lit_run
                         for c in range(3)]
                pat = min(1.0, cav * 0.9 + corner * 0.9 + max(0.0, blotch[i] - 0.6) * 1.2)
                metal = [metal[c] + (patina[c] - metal[c]) * pat * 0.55 for c in range(3)]
                wear = vex * (0.6 + 0.4 * grain[i]) * (0.75 + 0.35 * max(0.0, facing))
                metal = [metal[c] + (worn[c] - metal[c]) * min(1.0, wear * 0.8) for c in range(3)]
                # stone: matte and granular, lightest just under the top rim and falling
                # darker toward the base, clouded, knotted and grained, with a few pits
                below = max(0.0, (y - ytop[x]) / _S - self.band)
                ramp = _smooth(below / st["ramp"])
                rock = _mix(s_top, s_base, ramp)
                # the darker the stone, the stronger its texture in proportion, so it still reads
                grow = 1 + 0.6 * ramp
                val = 1 + grow * (st["macro"] * _clip(macro[i]) + st["meso"] * _clip(meso[i])
                                  + st["fine"] * _clip(fine[i]))
                if pits[i] < 0.14:
                    val *= 1 - st["pits"] * _smooth((0.14 - pits[i]) / 0.05)
                elif pits[i] > 0.88:
                    val *= 1 + st["pits"] * 0.4 * _smooth((pits[i] - 0.88) / 0.05)
                rock = [v * val / flat for v in rock]
                base = [rock[c] + (metal[c] - rock[c]) * b for c in range(3)]
                shade = 0.36 + 1.1 * dif
                ao = 1.0 - 0.5 * cav - 0.25 * corner * b
                gloss = b * (0.3 + 0.7 * vex) * (0.7 + 0.5 * max(0.0, facing)) + (1 - b) * 0.04
                # two speculars: a broad warm sheen and a tight bright glint
                col = [base[c] * shade * ao + (worn[c] * 0.3 * ndh ** 9 + spec[c] * ndh ** 60) * gloss
                       for c in range(3)]
                # where the rim meets the stone: a light catch along the bronze lip, then the
                # rim's shadow on the stone just under it, so the stone sits below the bronze
                e = (d - band) / _S
                if -1.5 < e < 0.5:
                    col = [v * (1 + lip["catch"] * (1 - abs(e + 0.5))) for v in col]
                elif 0.5 <= e < 0.5 + lip["shade_width"] + 1.5:
                    s = lip["shade"] * (1 - _smooth((e - 0.5 - lip["shade_width"]) / 1.5)) * (1 - self.bronze[i])
                    col = [v * (1 - s) for v in col]
                if glow[i] > 0.001:
                    facing_z = max(0.15, nz)
                    col = [col[c] + ember[c] * glow[i] * 0.35 * facing_z * (base[c] / 120 + 0.25) for c in range(3)]
                if well_any[i] > 0.02 and window[i] < 0.5:
                    inner = [well_color[i][c] * (0.8 + 0.4 * grain[i]) for c in range(3)]
                    k2 = _smooth((well_any[i] - 0.5) * 4) if well_any[i] < 0.75 else 1.0
                    # the walls keep their lighting, the floor goes dark
                    depth_t = min(1.0, max(0.0, (-height[i] - 2.5 * _S) / (2.5 * _S)))
                    col = [col[c] + (inner[c] - col[c]) * k2 * depth_t for c in range(3)]
                alpha = a * (1 - window[i]) if window[i] > 0.0 else a
                rgba[i] = (int(max(0, min(255, col[0]))), int(max(0, min(255, col[1]))),
                           int(max(0, min(255, col[2]))), int(max(0, min(255, alpha * 255))))
        img = Image.new("RGBA", (w, h))
        img.putdata(rgba)

        if any(wl[3] for wl in self.wells):
            # Inside a transparent window the frame's lip shades the top and left.
            win = Image.new("L", (w, h))
            win.putdata([int(v * 255) for v in window])
            shifted = Image.new("L", (w, h), 255)
            shifted.paste(win.point(lambda v: 255 - v), (2 * _S, 4 * _S))
            soft_win = shifted.filter(ImageFilter.GaussianBlur(5 * _S))
            inner = [int(min(255, s * 0.9) * (wv / 255.0)) for s, wv in zip(_px(soft_win), _px(win))]
            shade = Image.new("RGBA", (w, h), (8, 6, 4, 0))
            shade.putalpha(Image.frombytes("L", (w, h), bytes(inner)))
            img = Image.alpha_composite(shade, img)

        # The console's shadow on the world round the silhouette: dark at the edge and gone
        # about two reaches out, so the console stands above the hollow.
        solid = Image.new("L", (w, h))
        solid.putdata([int(mv * (1 - wv) * 255) for mv, wv in zip(self.mask, window)])
        cast = self.look["cast"]
        sh = solid.filter(ImageFilter.GaussianBlur(cast["reach"] * _S)).point(
            lambda v: int(min(255, v * 2 * cast["dark"])))
        shadow = Image.new("RGBA", (w, h), (6, 4, 2, 0))
        shadow.putalpha(sh)
        img = Image.alpha_composite(shadow, img)
        for gx, gy, gr in self.gems:
            img = _gem(img, gx, gy, gr)
        return img


def _down(img, width, height):
    if img.size == (width, height):
        return img
    return img.convert("RGBa").resize((width, height), Image.BOX).convert("RGBA")


def _gem(img, gx, gy, gr):
    """An amber cabochon in a dark bezel: deep at the bottom, a bright core, a cut glint at
    the top left and warm light bounced along the lower rim. The one hot colour on the
    console, so its halo stays small."""
    w, h = img.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = layer.load()
    ry = 1.25
    bezel = 0.32
    reach = 2.6
    deep, amber, core, hot = (120, 36, 6), (238, 128, 28), (255, 208, 110), (255, 248, 228)
    for y in range(int(gy - gr * ry * reach), int(gy + gr * ry * reach) + 2):
        for x in range(int(gx - gr * reach), int(gx + gr * reach) + 2):
            if not (0 <= x < w and 0 <= y < h):
                continue
            dx, dy = (x + 0.5 - gx) / gr, (y + 0.5 - gy) / (gr * ry)
            d = math.hypot(dx, dy)
            edge_px = (1.0 - d) * gr
            if d <= 1.0 + 0.5 / gr:
                v = (dy + 1) / 2  # 0 at the top, 1 at the bottom
                c = _mix(amber, deep, _smooth(v * 1.3 - 0.15))
                glow = max(0.0, 1 - math.hypot(dx * 1.05, (dy + 0.12) * 1.1) / 0.75) ** 1.2
                c = _mix(c, core, glow * 0.95)
                bounce = _smooth((d - 0.6) / 0.4) * max(0.0, 0.55 * dx + 0.8 * dy)
                c = [min(255, c[k] + (255, 150, 60)[k] * bounce * 0.55) for k in range(3)]
                c = [v2 * (0.7 + 0.3 * _smooth((1 - d) * 4)) for v2 in c]
                # the cut glint: a small bright quad at the top left, a soft one under it
                glint = math.exp(-(((dx + 0.34) / 0.2) ** 2 + ((dy + 0.46) / 0.13) ** 2) ** 2)
                c = _mix(c, hot, min(1.0, glint * 1.2))
                soft = math.exp(-(((dx + 0.15) / 0.35) ** 2 + ((dy + 0.1) / 0.3) ** 2))
                c = [min(255, c[k] + 40 * soft) for k in range(3)]
                px[x, y] = (*(int(v2) for v2 in c), int(255 * max(0.0, min(1.0, edge_px + 0.5))))
            elif d <= 1.0 + bezel:
                t = (d - 1.0) / bezel
                lit = max(0.0, -0.45 * dx - 0.85 * dy) / max(d, 1e-6)
                c = _mix((16, 10, 6), (150, 104, 56), lit * math.sin(math.pi * t) ** 0.7)
                outer = (1.0 + bezel - d) * gr
                px[x, y] = (*(int(v2) for v2 in c), int(255 * max(0.0, min(1.0, outer + 0.5))))
            else:
                a = math.exp(-(d - 1.0 - bezel) * 2.2) * 0.32
                px[x, y] = (255, 168, 70, int(255 * a))
    return Image.alpha_composite(img, layer)


def _write(path: Path, data: bytes) -> bool:
    """Writes `data` to `path` unless it already holds exactly that; True when it changed."""
    if path.exists() and path.read_bytes() == data:
        return False
    path.write_bytes(data)
    return True


def _stylebox(path: Path, res: str, margin, content, expand=0, stretch=2, scale=1) -> bool:
    """A StyleBoxTexture; margins are given in layout pixels and written in texels."""
    m = margin if isinstance(margin, (tuple, list)) else (margin,) * 4
    c = content if isinstance(content, (tuple, list)) else (content,) * 4
    lines = ['[gd_resource type="StyleBoxTexture" load_steps=2 format=3]', "",
             f'[ext_resource type="Texture2D" path="{res}" id="1"]', "", "[resource]", 'texture = ExtResource("1")']
    lines += [f"texture_margin_{s} = {float(v * scale)}" for s, v in zip(("left", "top", "right", "bottom"), m)]
    lines += [f"content_margin_{s} = {float(v * scale)}" for s, v in zip(("left", "top", "right", "bottom"), c)]
    if expand:
        lines += [f"expand_margin_{s} = {float(expand * scale)}" for s in ("left", "top", "right", "bottom")]
    lines += [f"axis_stretch_horizontal = {stretch}", f"axis_stretch_vertical = {stretch}", ""]
    return _write(path, "\n".join(lines).encode())


_MIPMAP_IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[params]

compress/mode=0
mipmaps/generate=true
"""


def _mipmapped(png: Path) -> None:
    """HD art is drawn smaller than its texels, so it gets mipmaps (kept on reimport)."""
    imp = png.with_name(png.name + ".import")
    if not imp.exists():
        imp.write_text(_MIPMAP_IMPORT)
        return
    text = imp.read_text()
    if "mipmaps/generate=false" in text:
        imp.write_text(text.replace("mipmaps/generate=false", "mipmaps/generate=true"))
    elif "mipmaps/generate=" not in text:
        imp.write_text(text.rstrip("\n") + "\nmipmaps/generate=true\n")


class _Console:
    def __init__(self, spec: dict, dest: Path, res_base: str):
        self.spec = _merge(CONSOLE, spec or {})
        self.m = {k: hex_to_rgb(v) for k, v in self.spec["material"].items()}
        self.dest = dest
        self.res = res_base.rstrip("/") + "/"
        self.seed = int(self.spec["seed"])
        self.scale = max(1, int(self.spec["scale"]))
        self.written: list[Path] = []
        self.unchanged: set[Path] = set()  # written files whose bytes came out as they were
        self.layout: dict = {}

    def save(self, name: str, img: Image.Image, width: int, height: int) -> None:
        path = self.dest / name
        data = io.BytesIO()
        _down(img, width * self.scale, height * self.scale).save(data, format="PNG")
        if not _write(path, data.getvalue()):
            self.unchanged.add(path)
        if self.scale > 1:
            _mipmapped(path)
        self.written.append(path)

    def stylebox(self, name: str, margin, content, expand=0, stretch=2) -> None:
        path = self.dest / f"{name}.tres"
        if not _stylebox(path, self.res + f"{name}.png", margin, content, expand=expand, stretch=stretch,
                         scale=self.scale):
            self.unchanged.add(path)
        self.written.append(path)

    def relief(self, width, height, mask, seed_offset, period_x=None):
        return _Relief(width, height, mask, self.seed + seed_offset, self.m, period_x, band=self.spec["rim"],
                       grooves=self.spec["grooves"], look={k: self.spec[k] for k in ("stone", "lip", "cast")})

    def jewel(self, piece, width, height, cx, cy, radius, keystone, flanges):
        """The console's one ornament: a pointed keystone holding an amber gem, standing on
        two short flanges swept along the circle of `radius` round (cx, cy) whose top it
        crowns. Flat chamfered faces, so each catches the light crisply even at 1x. Returns
        the mask to add to the silhouette."""
        ks, fl = keystone, flanges
        apex = cy - radius
        key = _keystone_points(cx, apex + ks["drop"], apex - ks["rise"], ks["half"])
        blades = [_flange_points(cx, cy, radius, side, fl["from"], fl["to"], fl["width"], fl["lift"])
                  for side in (-1, 1)]
        fullers = [_fuller_points(cx, cy, radius, side, fl["from"] + 6, fl["to"], fl["width"]) for side in (-1, 1)]

        def blade_shapes(d, k):
            for b in blades:
                _polygon(d, k, b)
            _polygon(d, k, key, fill=0)

        def grooves(d, k):
            for f in fullers:
                d.line([(x * k, y * k) for x, y in f], fill=255, width=max(1, round(1.2 * k)))

        both = _shape_mask(width, height, lambda d, k: [_polygon(d, k, p) for p in blades + [key]])
        piece.add_ornament(_shape_mask(width, height, blade_shapes), height=2.4, bevel=2.0)
        piece.add_ornament(_shape_mask(width, height, grooves), height=-0.9, soften=1, bronze=False)
        piece.add_ornament(_shape_mask(width, height, lambda d, k: _polygon(d, k, key)), height=3.6, bevel=2.6)
        # the gem sits where the keystone is widest
        piece.add_gem(cx, apex + ks["drop"] - (ks["drop"] + ks["rise"]) * 0.34, ks["gem"])
        return both

    # pieces

    def wing(self, right: bool):
        sp, rail, shadow = self.spec["wing"], self.spec["rail"], self.spec["shadow"]
        width, top_h = sp["size"]
        height = top_h + shadow
        s0, s1 = sp["slope"]

        def top(x):
            x = width - x if right else x
            return top_h if x <= s0 else (rail if x >= s1 else _ogee(x, s0, s1, top_h, rail))

        piece = self.relief(width, height, _profile_mask(width, height, top), 2 if right else 1)
        wx, wb, ww, wh = sp["well"]
        if right:
            wx = width - wx - ww
        wy = height - wb - wh
        so = self.spec["socket"]
        piece.add_socket(wx, wy, ww, wh, wall=so["wall"], bead=so["bead"], depth=so["depth"])
        self.save("wing_right.png" if right else "wing_left.png", piece.paint(), width, height)
        self.layout["card_well" if right else "map_well"] = [wx, wy, ww, wh]
        self.layout["wing"] = [width, height]

    def crest(self):
        sp, rail, shadow = self.spec["centre"], self.spec["rail"], self.spec["shadow"]
        cr = sp["crest"]
        width, height = sp["width"], sp["height"] + shadow
        cx, radius, base = cr["x"], cr["radius"], cr["base"]
        r0, r1 = cr["rise"]
        x0, x1, shoulder = sp["shoulder"]
        start = min(x0, cx)  # the shoulder runs in under the arch, so the two always meet
        springing = base + 2
        f = float(self.spec["fillet"])
        # The left fillet needs the rise to have levelled out where the fillet meets it.
        tangent = cx - math.sqrt(max(0.0, (radius + f) ** 2 - (springing + f - base) ** 2))
        fillets = (_fillet(cx, base, radius, springing, f, -1) if tangent >= r1 else None,
                   _fillet(cx, base, radius, shoulder, f, 1))

        def top(x):
            hv = rail
            if x < cx:
                hv = max(hv, _ogee(x, r0, r1, rail, springing))
            dx = x - cx
            if abs(dx) <= radius:
                hv = max(hv, base + math.sqrt(radius ** 2 - dx * dx))
            if start <= x <= x1 + 30:
                hv = max(hv, shoulder if x <= x1 else _ogee(x, x1, x1 + 30, shoulder, rail))
            for arc in fillets:
                if arc:
                    hv = max(hv, arc(x))
            return hv

        piece = self.relief(width, height, _profile_mask(width, height, top), 3)
        if sp.get("incised"):
            piece.grooves = list(piece.grooves) + [self.spec["rim"] + sp["incised"]]
        wx, wb, ww, wh = sp["window"]
        window = _shape_mask(width, height, lambda d, k: _arch(d, k, wx, wb, ww, wh, height))
        piece.add_well(window, depth=5.0, window=True)
        if sp["moulding"]:
            piece.add_frame(window, sp["moulding"], height=3.2)
        jewel = self.jewel(piece, width, height, cx, height - base, radius, sp["keystone"], sp["flanges"])
        piece.extend(jewel)
        self.save("crest.png", piece.paint(), width, height)
        tx, tb, tw, th = sp["text"]
        wy = height - wb - wh
        pad = 3
        self.layout.update({"centre": [width, height], "window": [wx, wy, ww, wh], "shoulder": shoulder,
                            "backdrop": [wx - pad, wy - pad, ww + 2 * pad, wh + 2 * pad],
                            "text": [tx, height - tb - th, tw, th]})
        self.portrait_bg(ww, wh, pad)

    def rail(self):
        rail, shadow = self.spec["rail"], self.spec["shadow"]
        width, height = 64, rail + shadow
        piece = self.relief(width, height, _profile_mask(width, height, lambda x: rail), 4, period_x=64)
        self.save("rail.png", piece.paint(), width, height)
        self.layout["rail"] = height

    def strip(self):
        """The resource strip hanging from the top edge: a curled cap on the left, then a bar
        whose middle repeats, so a nine-slice can grow it leftwards for big numbers."""
        sp = self.spec["strip"]
        bar, cap, period = sp["height"], sp["cap"], sp["period"]
        width, height = cap + 2 * period, bar + 12
        k = 4 * _S
        img = Image.new("L", (width * k, height * k), 0)
        pts, x = [], -40.0
        while x <= width + 40:
            pts.append((x * k, (bar if x >= cap - 14 else _ogee(x, 4, cap - 14, -2, bar)) * k))
            x += 0.25
        pts += [((width + 40) * k, -40 * k), (-40 * k, -40 * k)]
        ImageDraw.Draw(img).polygon(pts, fill=255)
        piece = self.relief(width, height, img.resize((width * _S, height * _S), Image.BOX), 5, period_x=period)
        self.save("strip.png", piece.paint(), width, height)
        self.stylebox("strip", (cap, 0, 0, 0), (cap, 0, 14, 12), stretch=1)
        self.layout["strip"] = {"height": height, "bar": bar, "cap": cap}

    def plate(self):
        """The end-of-game plate: a slab in the console's material, crowned by its jewel."""
        width, height = self.spec["plate"]
        cx, top = width / 2, 32
        piece = self.relief(width, height, _shape_mask(width, height, lambda d, k: _rrect(
            d, k, 14, top, width - 28, height - top - 14, 10)), 6)
        # Along the top edge the flanges follow a circle so wide it is nearly straight.
        far = 2000
        flanges = dict(self.spec["centre"]["flanges"], to=self.spec["centre"]["flanges"]["to"] + 6)
        piece.extend(self.jewel(piece, width, height, cx, top + far, far, self.spec["centre"]["keystone"], flanges))
        self.save("plate.png", piece.paint(), width, height)
        self.layout["plate"] = {"size": [width, height], "text": [30, 54, width - 60, height - 80]}

    def portrait_bg(self, ww, wh, pad, name="portrait_bg.png"):
        """Behind the portrait model: a dark warm vignette with a soft key light behind the
        model's upper half, so a silhouette of any colour reads against it. Shaped like the
        window and `pad` larger all round, so it can clip the portrait to the arch."""
        sp = self.spec["portrait"]
        centre, edge, key = hex_to_rgb(sp["centre"]), hex_to_rgb(sp["edge"]), hex_to_rgb(sp["key"])
        bw, bh = ww + 2 * pad, wh + 2 * pad
        w, h = bw * _S, bh * _S
        shape = _field(_shape_mask(bw, bh, lambda d, k: _arch(d, k, 0, 0, bw, bh, bh)))
        img = Image.new("RGBA", (w, h))
        px = img.load()
        tone = _noise(w, h, 12 * _S, self.seed + 20)
        for y in range(h):
            for x in range(w):
                u, v = (x + 0.5) / w, (y + 0.5) / h
                d = math.hypot((u - 0.5) * 1.15, (v - 0.48) * 0.95) / 0.62
                c = _mix(centre, edge, _smooth(d))
                light = math.exp(-(((u - 0.5) / 0.32) ** 2 + ((v - 0.34) / 0.24) ** 2))
                t = 0.95 + 0.1 * tone[y * w + x]
                px[x, y] = (*(int(min(255, (c[k] + key[k] * light) * t)) for k in range(3)),
                            int(255 * shape[y * w + x]))
        self.save(name, img, bw, bh)

    def well_shade(self):
        """Inner shadow over the minimap: the socket's top and left lip shade its picture."""
        _, _, ww, wh = self.spec["wing"]["well"]
        w, h = ww * _S, wh * _S
        pad = 20 * _S
        mask = Image.new("L", (w + 2 * pad, h + 2 * pad), 255)
        ImageDraw.Draw(mask).rounded_rectangle([pad + 2 * _S, pad + 4 * _S, pad + w + 2 * _S, pad + h + 4 * _S],
                                               radius=3 * _S, fill=0)
        soft = mask.filter(ImageFilter.GaussianBlur(4 * _S)).crop((pad, pad, pad + w, pad + h))
        img = Image.new("RGBA", (w, h), (6, 4, 3, 0))
        img.putalpha(soft.point(lambda v: int(v * 0.8)))
        self.save("well_shade.png", img, ww, wh)

    def banner(self):
        """Behind titles: a dark band soft at every edge, which the HUD stretches to the
        title's width; and a thin gilt rule, painted as its left half (the HUD mirrors it)
        fading in from the end, with a small diamond for its middle."""
        sp = self.spec["banner"]
        rng = random.Random(self.seed + 31)
        width, height = sp["band"]
        w, h = width * _S, height * _S
        fall = 18 * _S
        data = []
        for y in range(h):
            fy = _smooth(y / fall) * _smooth((h - 1 - y) / fall)
            for x in range(w):
                dx = abs(x + 0.5 - w / 2) / (w / 2)
                fx = max(0.0, 1 - dx ** 2.4) ** 1.5
                # triangular dither of about a level and a half, so the fades do not band
                a = 0.72 * fx * fy * 255 + (rng.random() - rng.random()) * 1.5
                data.append((10, 7, 4, int(max(0, min(255, round(a))))))
        img = Image.new("RGBA", (w, h))
        img.putdata(data)
        self.save("banner.png", img, width, height)

        gold, light = hex_to_rgb(GILT[1]), hex_to_rgb(GILT[2])
        line = tuple(int(gold[c] + (light[c] - gold[c]) * 0.35) for c in range(3))
        rw, rh = sp["rule"]
        w, h = rw * _S, rh * _S
        img = Image.new("RGBA", (w, h))
        px = img.load()
        for y in range(h):
            yy = (y + 0.5) / _S  # layout pixels from the top
            for x in range(w):
                fade = _smooth((x + 0.5) / w / 0.85) ** 1.2
                if 1.0 <= yy < 2.5:  # the gilt line, a pixel and a half
                    px[x, y] = (*line, int(255 * 0.95 * fade))
                elif 2.5 <= yy < 3.5:  # its shadow, so it reads over grass
                    px[x, y] = (12, 8, 4, int(255 * 0.55 * fade))
        self.save("banner_rule.png", img, rw, rh)

        size = sp["gem"]
        n = size * _S
        k = 4
        big = Image.new("RGBA", (n * k, n * k))
        draw = ImageDraw.Draw(big)
        c, r = n * k / 2, n * k / 2 - 0.5 * _S * k
        draw.polygon([(c, c - r), (c + r, c), (c, c + r), (c - r, c)], fill=(12, 8, 4, 255))
        r2 = r - 1.2 * _S * k
        draw.polygon([(c, c - r2), (c + r2, c), (c, c + r2), (c - r2, c)], fill=(*gold, 255))
        draw.polygon([(c, c - r2), (c, c), (c - r2, c)], fill=(*light, 255))
        draw.polygon([(c, c), (c + r2, c), (c, c + r2)], fill=tuple(int(v * 0.62) for v in gold) + (255,))
        self.save("banner_gem.png", big.resize((n, n), Image.BOX), size, size)
        self.layout["banner"] = {"band": [width, height], "rule": [rw, rh], "gem": [size, size]}

    def glow(self):
        """Hover halo for a command: warm light leaking round the icon."""
        size = self.spec["card"]["socket"] + 20
        w = h = size * _S
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        px = img.load()
        inner = 10 * _S
        for y in range(h):
            for x in range(w):
                dx = max(inner - x, 0, x - (w - 1 - inner))
                dy = max(inner - y, 0, y - (h - 1 - inner))
                if dx == 0 and dy == 0:
                    e = min(x - inner, y - inner, w - 1 - inner - x, h - 1 - inner - y) / _S
                    a = 0.55 * math.exp(-e / 2.5)
                else:
                    a = math.exp(-((math.hypot(dx, dy) / _S / 4.2) ** 1.6))
                px[x, y] = (255, 196, 96, int(255 * a))
        self.save("card_glow.png", img, size, size)
        self.stylebox("card_glow", 16, 0, expand=10, stretch=0)

    def plate_9(self, name, size, radius, rim, fill, fill_alpha, margin, content, glow=None, inset=False):
        """Small nine-slices (tooltip, buttons): a bronze bead round a dark fill."""
        width, height = size
        mask = _shape_mask(width, height, lambda d, k: _rrect(d, k, 1, 1, width - 2, height - 2, radius))
        piece = self.relief(width, height, mask, 11)
        piece.band = rim + 1.5
        piece.grooves = []
        img = piece.paint()
        w, h = img.size
        inner = _shape_mask(width, height, lambda d, k: _rrect(d, k, rim, rim, width - 2 * rim, height - 2 * rim,
                                                               max(1, radius - rim)))
        tone = _noise(w, h, 10 * _S, self.seed + 12)
        data = []
        for (r, g, b, a), mv, t in zip(_px(img), _px(inner), tone):
            f = mv / 255.0
            if f <= 0:
                data.append((r, g, b, a))
                continue
            fc = [fill[c] * (0.9 + 0.2 * t) for c in range(3)]
            data.append((int(r + (fc[0] - r) * f), int(g + (fc[1] - g) * f), int(b + (fc[2] - b) * f),
                         int(a + (fill_alpha - a) * f)))
        img.putdata(data)
        if inset:  # pressed: the fill sinks, a shadow under the top rim
            sh = Image.new("L", (w, h), 0)
            sh.paste(inner.point(lambda v: 255 - v), (0, 3 * _S))
            sh = Image.composite(sh.filter(ImageFilter.GaussianBlur(3 * _S)), Image.new("L", (w, h), 0), inner)
            layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            layer.putalpha(sh.point(lambda v: int(v * 0.7)))
            img = Image.alpha_composite(img, layer)
        if glow:
            g = inner.filter(ImageFilter.GaussianBlur(6 * _S))
            layer = Image.new("RGBA", (w, h), (*glow, 0))
            edge = [int(max(0, min(255, (255 - abs(v - 128) * 2) * 0.55))) for v in _px(g)]
            layer.putalpha(Image.frombytes("L", (w, h), bytes(edge)))
            img = Image.alpha_composite(img, layer)
        self.save(f"{name}.png", img, width, height)
        # The fill's noise does not repeat, so the middle stretches rather than tiles.
        self.stylebox(name, margin, content, stretch=0)

    # the screens outside a match

    def panel(self):
        """The screens' large panel (the Builders kit, Join, the loading and results plates):
        a slab in the console's material whose stone tiles both ways, so a nine-slice grows
        it to any size without stretching the grain (whole tiles, a little scaled to fit:
        Godot's tile-fit). Its silhouette sits `inset` inside the texture, which the
        StyleBox's expand margin draws outside the control: the control's rect is the bronze
        edge, and the shadow falls outside it."""
        sp = self.spec["panel"]
        (tx, ty), margin, inset, radius = sp["tile"], sp["margin"], sp["inset"], sp["radius"]
        width, height = 2 * margin + tx, 2 * margin + ty
        mask = _shape_mask(width, height, lambda d, k: _rrect(d, k, inset, inset, width - 2 * inset,
                                                              height - 2 * inset, radius))
        look = {"stone": dict(self.spec["stone"], **sp["stone"]), "lip": self.spec["lip"], "cast": self.spec["cast"]}
        material = dict(self.m, stone_base=hex_to_rgb(sp["stone_base"]))
        piece = _Relief(width, height, mask, self.seed + 40, material, period_x=tx, band=self.spec["rim"],
                        grooves=self.spec["grooves"], look=look, period_y=ty)
        self.save("panel.png", piece.paint(), width, height)
        self.stylebox("panel", margin, sp["content"], expand=inset, stretch=2)
        self.layout["panel"] = {"margin": margin, "expand": inset, "tile": [tx, ty], "content": sp["content"]}

    def panel_jewel(self):
        """The crest's jewel on its own (keystone, amber gem, two swept flanges), to crown the
        one panel a screen is about: drawn with its `seat` on the panel's top edge."""
        sp = self.spec["jewel"]
        width, height = sp["size"]
        seat, cx, far = sp["seat"], width / 2, 2000
        piece = self.relief(width, height, Image.new("L", (width * _S, height * _S), 0), 41)
        flanges = dict(self.spec["centre"]["flanges"], to=self.spec["centre"]["flanges"]["to"] + 6)
        piece.extend(self.jewel(piece, width, height, cx, seat + far, far, self.spec["centre"]["keystone"], flanges))
        self.save("panel_jewel.png", piece.paint(), width, height)
        self.layout["panel_jewel"] = {"size": [width, height], "seat": [cx, seat]}

    def portrait_plate(self):
        """An arched, moulded window cut in a stone slab, for a Builder's portrait on a card
        (loading, Builders): the window is open, so the portrait drawn under the plate shows
        through, and `portrait_plate_bg` goes behind the portrait."""
        sp = self.spec["portrait_plate"]
        ww, wh = sp["window"]
        border, shadow = sp["border"], sp["shadow"]
        width, height = ww + 2 * (border + shadow), wh + 2 * (border + shadow)
        slab = _shape_mask(width, height, lambda d, k: _arch(d, k, shadow, shadow, ww + 2 * border, wh + 2 * border,
                                                             height))
        piece = self.relief(width, height, slab, 42)
        window = _shape_mask(width, height, lambda d, k: _arch(d, k, shadow + border, shadow + border, ww, wh, height))
        piece.add_well(window, depth=5.0, window=True)
        piece.add_frame(window, sp["moulding"], height=3.2)
        self.save("portrait_plate.png", piece.paint(), width, height)
        pad = 3
        wx, wy = shadow + border, height - shadow - border - wh
        self.layout["portrait_plate"] = {"size": [width, height], "window": [wx, wy, ww, wh],
                                         "backdrop": [wx - pad, wy - pad, ww + 2 * pad, wh + 2 * pad]}
        self.portrait_bg(ww, wh, pad, name="portrait_plate_bg.png")

    def bar(self):
        """A progress bar: a sunk trough (a nine-slice) and a gilt fill drawn `inset` inside
        it; the fill stretches, and the HUD may tint it (amber for Slow)."""
        sp = self.spec["bar"]
        tw, th = sp["trough"]
        self.plate_9("bar_trough", (tw, th), th / 2 - 1, 3, (9, 7, 6), 255, (th // 2, th // 2 - 1, th // 2, th // 2 - 1),
                     0, inset=True)
        fw, fh = sp["fill"]
        w, h = fw * _S, fh * _S
        mask = _field(_shape_mask(fw, fh, lambda d, k: _rrect(d, k, 0, 0, fw, fh, fh / 2 - 0.5)))
        dark, base, light = (hex_to_rgb(c) for c in GILT)
        tone = _noise(w, h, 6 * _S, self.seed + 45)
        data = []
        for y in range(h):
            v = (y + 0.5) / h  # 0 at the top: the light catches the top, the base falls dark
            if v < 0.3:
                c = _mix(light, base, _smooth(v / 0.3))
            else:
                c = _mix(base, dark, _smooth((v - 0.3) / 0.7) * 0.8)
            for x in range(w):
                i = y * w + x
                t = 0.92 + 0.16 * tone[i]
                data.append((*(int(max(0, min(255, ch * t))) for ch in c), int(255 * mask[i])))
        img = Image.new("RGBA", (w, h))
        img.putdata(data)
        self.save("bar_fill.png", img, fw, fh)
        self.stylebox("bar_fill", (fh // 2 + 1, 0, fh // 2 + 1, 0), 0, stretch=0)
        self.layout["bar"] = {"height": th, "fill_height": fh, "inset": sp["inset"]}

    def divider(self):
        """An incised line across a panel between its sections: a dark cut with the light
        caught on its lower lip, fading in at both ends."""
        width, height = self.spec["divider"]
        w, h = width * _S, height * _S
        worn = self.m["worn"]
        fade_px = 24 * _S
        img = Image.new("RGBA", (w, h))
        px = img.load()
        for y in range(h):
            yy = (y + 0.5) / _S
            for x in range(w):
                fade = _smooth(min(x + 0.5, w - 0.5 - x) / fade_px)
                if 2.0 <= yy < 3.0:
                    px[x, y] = (12, 8, 4, int(255 * 0.8 * fade))
                elif 3.0 <= yy < 4.0:
                    px[x, y] = (*worn, int(255 * 0.3 * fade))
        self.save("divider.png", img, width, height)
        self.stylebox("divider", (28, 0, 28, 0), 0, stretch=0)
        self.layout["divider"] = {"height": height}

    def screens(self):
        """Every piece the screens outside a match add to the console's."""
        self.panel()
        self.panel_jewel()
        cf = self.spec["card_frame"]
        for name, glow in (("card_frame", None), ("card_frame_lit", (255, 190, 90))):
            self.plate_9(name, cf["size"], cf["radius"], cf["rim"], (24, 19, 15), 255, cf["margin"], cf["content"],
                         glow=glow)
        self.layout["card_frame"] = {"margin": cf["margin"], "content": cf["content"]}
        self.portrait_plate()
        fd = self.spec["field"]
        for name, glow in (("field", None), ("field_focus", (255, 190, 90))):
            self.plate_9(name, fd["size"], fd["radius"], fd["rim"], (11, 9, 8), 255, fd["margin"], fd["content"],
                         glow=glow, inset=True)
        self.layout["field"] = {"height": fd["height"], "content": fd["content"], "code": fd["code"]}
        self.bar()
        self.divider()

    def paint(self) -> list[Path]:
        self.dest.mkdir(parents=True, exist_ok=True)
        self.wing(False)
        self.wing(True)
        self.crest()
        self.rail()
        self.strip()
        self.plate()
        self.well_shade()
        self.banner()
        self.glow()
        self.plate_9("tooltip", self.spec["tooltip"], 5, 3, (14, 11, 9), 238, 12, (12, 9, 12, 10))
        for state, glow, inset in (("normal", None, False), ("hover", (255, 190, 90), False),
                                   ("pressed", None, True)):
            self.plate_9(f"button_{state}", self.spec["button"], 6, 4, (34, 26, 20), 255, 12, (16, 6, 16, 6),
                         glow=glow, inset=inset)
        self.plate_9("button_disabled", self.spec["button"], 6, 4, (22, 19, 17), 255, 12, (16, 6, 16, 6))
        card = self.spec["card"]
        self.layout.update({"socket": [card["socket"], card["socket"]], "gap": card["gap"], "scale": self.scale})
        self.screens()
        layout = self.dest / "layout.json"
        if not _write(layout, (json.dumps(self.layout, indent=2) + "\n").encode()):
            self.unchanged.add(layout)
        self.written.append(layout)
        return self.written


def console(spec: dict | None, dest: Path, res_base: str, unchanged: set | None = None) -> list[Path]:
    """Paints every console piece into the folder `dest` (see CONSOLE for the spec's keys and
    defaults) and returns the files written: PNGs, StyleBoxTextures and layout.json. With
    "scale": 2 the PNGs carry twice the texels of the layout (and mipmaps), the .tres margins
    are in texels, and layout.json stays in layout pixels with its "scale" alongside. A set
    passed as `unchanged` receives the files whose bytes came out as they were."""
    global _S
    scale = max(1, int((spec or {}).get("scale", CONSOLE["scale"])))
    previous, _S = _S, 2 * scale
    try:
        painter = _Console(spec or {}, dest, res_base)
        written = painter.paint()
        if unchanged is not None:
            unchanged.update(painter.unchanged)
        return written
    finally:
        _S = previous


# ── Command line ──

MANIFEST = "asset_manifest.json"
LICENSE = "generated by the game's own script; owned by the project"


def record(project: Path, files: list[Path], entry: dict, keep=()) -> None:
    """Records each written file in asset_manifest.json, as the kit records its own. A file
    in `keep` (its bytes did not change) whose entry already says the same keeps its entry."""
    path = project / MANIFEST
    manifest = json.loads(path.read_text()) if path.exists() else {"version": 1, "assets": {}}
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for f in files:
        key = f.relative_to(project).as_posix()
        old = manifest["assets"].get(key)
        if f in keep and old and all(old.get(k) == v for k, v in {**entry, "license": LICENSE}.items()):
            continue
        manifest["assets"][key] = {**entry, "license": LICENSE, "updated": stamp}
    manifest["assets"] = dict(sorted(manifest["assets"].items()))
    tmp = project / f".{MANIFEST}.tmp{os.getpid()}"
    tmp.write_text(json.dumps(manifest, indent=2) + "\n")
    os.replace(tmp, path)


def main(argv: list[str]) -> int:
    project = Path(__file__).resolve().parents[2]
    spec_rel = argv[0] if argv else "art_src/ui/console.json"
    dest_rel = argv[1] if len(argv) > 1 else "ui/console"
    spec = json.loads((project / spec_rel).read_text())
    unchanged: set[Path] = set()
    written = console(spec, project / dest_rel, f"res://{dest_rel}", unchanged)
    script = Path(__file__).resolve().relative_to(project).as_posix()
    record(project, [f for f in written if f.suffix in (".png", ".tres", ".json")],
           {"tool": "script", "script": script, "spec": spec_rel, "dest": dest_rel,
            "regen": f"python3 {script} {spec_rel} {dest_rel}"}, keep=unchanged)
    for f in written:
        print(f"wrote {f.relative_to(project).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
