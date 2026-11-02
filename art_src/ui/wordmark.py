#!/usr/bin/env python3
"""Paints Groundhold's wordmark and emblem in ui/brand/ from art_src/ui/wordmark.json.

    python3 art_src/ui/wordmark.py           # from the project root; rewrites ui/brand/*

The recipe is vector (docs/design/front-end.md §4.7): the letters are the outlines of the
game's own display face (fonts/NotoSerifDisplay-Bold.ttf, OFL), set in capitals with the
spec's tracking, and the emblem is a curve: a holdfast knot, the (p, q) torus knot the spec
names, one band looping over and under itself as a kelp holdfast grips its rock, set in a
stone roundel in the console's bronze. No Tide word reaches the logo, and nothing of
Wickhollow (world.md): no lantern, no gourd.

    wordmark.png   GROUNDHOLD in gilt with a chamfered bevel, a dark outline and a soft shadow
    wordmark_small.png  the same letters for small sizes (the top bar's 28 px): flat gilt brighter
                   at the top, a light top edge, no bevel's shade and no dark outline, which at
                   that size dragged the gilt down to a mid value
    emblem.png     the knot on its roundel (the front end's top bar, the arrival)
    icon.png       the emblem at the window icon's size (project.godot's config/icon)
    mark.png       the emblem at the site's brand-mark size (web/)
    favicon.png    a simpler cut for the browser's tab (32 px) and favicon_16.png (16 px): the (3, 4)
                   knot blurs to a gold ring with a smudge inside that small, so the favicon is a
                   (2, 3) knot, three lobes and a band twice as thick, flat gilt on the dark stone

Seeded and deterministic, as console.py and front.py are; files whose bytes come out as
they were are left alone, their manifest entries too.
"""

from __future__ import annotations

import io
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import console as C  # noqa: E402
import front as F  # noqa: E402

SPEC = {
    "seed": 5,
    "wordmark": {"text": "GROUNDHOLD", "font": "fonts/NotoSerifDisplay-Bold.ttf", "cap": 56, "tracking": 0.11,
                 "bevel": 3.2, "outline": 2.4, "pad": 10, "out_height": 96,
                 "gilt": ["#3c2408", "#9c6f2a", "#e9c56f", "#fff3c6"], "ink": "#170d05",
                 "shadow": {"reach": 4.0, "drop": 3.0, "dark": 0.7},
                 "small": {"out_height": 64, "flat": ["#fff1c4", "#f0cf86", "#d7a952"], "edge": "#fffbe8",
                           "shadow": {"reach": 2.5, "drop": 2.0, "dark": 0.55}}},
    "knot": {"p": 3, "q": 4, "R": 1.0, "r": 0.46, "band": 0.15, "gap": 0.05, "samples": 2400, "fill": 0.74},
    "emblem": {"size": 512, "rim": 22, "stone": ["#4a4238", "#211c17"], "out": [["emblem.png", 128],
                                                                              ["icon.png", 256], ["mark.png", 128]]},
    # the favicon's cut: fewer crossings and a thicker band, so it reads at 16 px
    "favicon": {"knot": {"p": 2, "q": 3, "R": 1.0, "r": 0.5, "band": 0.24, "gap": 0.09, "samples": 1600,
                         "fill": 0.7},
                "size": 128, "stone": ["#3c352c", "#17130f"], "rim": "#b98a3e",
                "gilt": ["#7a5418", "#e9c56f", "#fff3c6"], "out": [["favicon.png", 32], ["favicon_16.png", 16]]},
}


def _gilt_shade(height, cover, w, h, stops, spec_rgb, light=F._LIGHT, half=F._HALF):
    """Lights a height field as polished gilt: the ramp by how the face turns to the light,
    with a broad sheen and a tight glint."""
    out = [(0, 0, 0, 0)] * (w * h)
    for y in range(h):
        for x in range(w):
            i = y * w + x
            a = cover[i]
            if a <= 0.0:
                continue
            hl = height[i - 1] if x > 0 else height[i]
            hr = height[i + 1] if x < w - 1 else height[i]
            hu = height[i - w] if y > 0 else height[i]
            hd = height[i + w] if y < h - 1 else height[i]
            nx, ny = (hl - hr) * 0.5, (hu - hd) * 0.5
            inv = 1.0 / math.sqrt(nx * nx + ny * ny + 1.0)
            nx, ny, nz = nx * inv, ny * inv, inv
            dif = max(0.0, nx * light[0] + ny * light[1] + nz * light[2])
            ndh = max(0.0, nx * half[0] + ny * half[1] + nz * half[2])
            # a vertical gradient too, as engraved gilt reads: brighter at the top of a letter
            t = 0.1 + 0.9 * dif - 0.12 * (y / h)
            c = F._ramp(stops, t)
            c = [c[k] + spec_rgb[k] * (0.22 * ndh ** 10 + 0.55 * ndh ** 80) for k in range(3)]
            out[i] = (int(max(0, min(255, c[0]))), int(max(0, min(255, c[1]))), int(max(0, min(255, c[2]))),
                      int(255 * a))
    img = Image.new("RGBA", (w, h))
    img.putdata(out)
    return img


class _Brand:
    def __init__(self, spec: dict, project: Path, dest: Path):
        self.spec = C._merge(SPEC, spec or {})
        self.project = project
        self.dest = dest
        self.written: list[Path] = []
        self.unchanged: set[Path] = set()

    def save(self, name: str, img: Image.Image) -> None:
        path = self.dest / name
        data = io.BytesIO()
        img.save(data, format="PNG")
        if not C._write(path, data.getvalue()):
            self.unchanged.add(path)
        C._mipmapped(path)
        self.written.append(path)

    def wordmark(self, small: bool = False):
        sp = self.spec["wordmark"]
        k = 4  # paint texels per output texel's half: painted at 2x the output, box-filtered
        out_h = sp["small"]["out_height"] if small else sp["out_height"]
        cap = sp["cap"] * k * 2 / 2  # the cap height in paint pixels at twice the output's
        font_path = self.project / sp["font"]
        # the font's cap height is about 0.7 of its em
        probe = ImageFont.truetype(str(font_path), 200)
        bb = probe.getbbox("H")
        em = int(round(cap / ((bb[3] - bb[1]) / 200.0)))
        font = ImageFont.truetype(str(font_path), em)
        track = sp["tracking"] * em
        letters = []
        x = 0.0
        for ch in sp["text"]:
            box = font.getbbox(ch)
            letters.append((ch, x - box[0], box))
            x += (box[2] - box[0]) + track
        width = x - track
        pad = sp["pad"] * k
        top_box = font.getbbox("H")
        W = int(width + 2 * pad)
        H = int(out_h * 2 * k / 2)
        H = int(cap + 2 * pad + 0.25 * cap)
        base = pad + cap * 0.08 - top_box[1]
        mask = Image.new("L", (W, H), 0)
        draw = ImageDraw.Draw(mask)
        for ch, lx, _box in letters:
            draw.text((pad + lx, base), ch, font=font, fill=255)
        m = C._field(mask)
        if small:
            face = self._flat_gilt(mask, m, W, H, sp["small"])
            grown = mask
            sh = sp["small"]["shadow"]
        else:
            dist = C._inside(m, W, H)
            bevel = sp["bevel"] * k
            height = [min(d, bevel) if m[i] > 0 else 0.0 for i, d in enumerate(dist)]
            height = C._blur(height, W, H, 1, passes=1)
            stops = [C.hex_to_rgb(c) for c in sp["gilt"]]
            face = _gilt_shade(height, m, W, H, stops, C.hex_to_rgb("#fff8e0"))
            # the outline: the letters grown, in dark bronze ink
            grown = mask.filter(ImageFilter.MaxFilter(int(sp["outline"] * k) * 2 + 1)).filter(ImageFilter.GaussianBlur(1))
            sh = sp["shadow"]
        ink = Image.new("RGBA", (W, H), (*C.hex_to_rgb(sp["ink"]), 0))
        ink.putalpha(grown if not small else Image.new("L", (W, H), 0))
        drop = Image.new("L", (W, H), 0)
        drop.paste(grown, (0, int(sh["drop"] * k)))
        soft = drop.filter(ImageFilter.GaussianBlur(sh["reach"] * k)).point(lambda v: int(v * sh["dark"]))
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        shadow.putalpha(soft)
        img = Image.alpha_composite(Image.alpha_composite(shadow, ink), face)
        bbox = img.getbbox()
        img = img.crop((max(0, bbox[0] - 2 * k), 0, min(W, bbox[2] + 2 * k), H))
        scale = out_h / img.height
        out = img.convert("RGBa").resize((max(1, round(img.width * scale)), out_h), Image.LANCZOS).convert("RGBA")
        self.save("wordmark_small.png" if small else "wordmark.png", out)

    @staticmethod
    def _flat_gilt(mask, cover, W, H, small):
        """The letters in flat gilt for small sizes: a ramp from light at the cap line to the
        base gilt, and a light edge along every top edge (the letters lit from above), no
        bevel's shade inside them."""
        stops = [C.hex_to_rgb(c) for c in small["flat"]]
        edge = C.hex_to_rgb(small["edge"])
        # the top edges: covered here, not covered a few texels above
        lift = 5
        top = [0.0] * (W * H)
        for y in range(H):
            for x in range(W):
                i = y * W + x
                if cover[i] > 0 and (y < lift or cover[i - lift * W] <= 0.0):
                    top[i] = 1.0
        top = C._blur(top, W, H, 1, passes=1)
        rows = [y for y in range(H) if any(cover[y * W + x] > 0 for x in range(0, W, 3))]
        y0, y1 = (rows[0], rows[-1]) if rows else (0, H - 1)
        out = [(0, 0, 0, 0)] * (W * H)
        for y in range(H):
            t = min(1.0, max(0.0, (y - y0) / max(1, y1 - y0)))
            base = F._ramp(stops, t)
            for x in range(W):
                i = y * W + x
                a = cover[i]
                if a <= 0.0:
                    continue
                c = [base[k] + (edge[k] - base[k]) * min(1.0, top[i]) * 0.85 for k in range(3)]
                out[i] = (int(max(0, min(255, c[0]))), int(max(0, min(255, c[1]))), int(max(0, min(255, c[2]))),
                          int(255 * a))
        img = Image.new("RGBA", (W, H))
        img.putdata(out)
        return img

    def knot_layers(self, n, kn=None):
        """The knot drawn into an n x n canvas: (cover, height, gap) lists; the band's centre
        line stamped sample by sample through a z-buffer, so at every crossing the band that
        comes nearer the eye passes over, with a cut either side of it. `kn` another knot's
        spec (the favicon's) in place of the emblem's."""
        kn = kn or self.spec["knot"]
        p, q, R, r = kn["p"], kn["q"], kn["R"], kn["r"]
        span = (R + r) * 1.0
        scale = n * kn["fill"] / 2 / span
        band, gap = kn["band"] * scale, kn["gap"] * scale
        c = n / 2
        N = n * n
        zbuf = [-1e9] * N
        cover = [0.0] * N
        height = [0.0] * N
        cut = [0.0] * N
        eps = r * 0.35
        samples = kn["samples"]
        outer = band + gap
        for s in range(samples):
            phi = 2 * math.pi * s / samples
            rad = R + r * math.cos(q * phi)
            px = c + rad * math.cos(p * phi) * scale
            py = c + rad * math.sin(p * phi) * scale
            z = r * math.sin(q * phi)
            x0, x1 = int(px - outer - 1), int(px + outer + 2)
            y0, y1 = int(py - outer - 1), int(py + outer + 2)
            for y in range(max(0, y0), min(n, y1)):
                dy = y + 0.5 - py
                for x in range(max(0, x0), min(n, x1)):
                    dx = x + 0.5 - px
                    d = math.sqrt(dx * dx + dy * dy)
                    if d > outer:
                        continue
                    i = y * n + x
                    if d <= band:
                        if z > zbuf[i] - eps:
                            if z > zbuf[i]:
                                zbuf[i] = z
                            hv = math.sqrt(max(0.0, 1.0 - (d / band) ** 2))
                            if cut[i] > 0 and z > zbuf[i] - eps:
                                cut[i] = 0.0
                            if hv > height[i] or cover[i] == 0.0:
                                height[i] = max(height[i], hv)
                            cover[i] = min(1.0, max(cover[i], (band - d) + 0.5))
                    elif z > zbuf[i] + eps:
                        zbuf[i] = z
                        cut[i] = 1.0
                        cover[i] = 0.0
                        height[i] = 0.0
        return cover, height, cut

    def emblem(self):
        sp = self.spec["emblem"]
        n = sp["size"]
        k = 2  # painted at twice the largest output
        N = n * k
        front = F._Front({}, self.dest, "res://ui/brand", json.loads(
            (self.project / "art_src/ui/console.json").read_text()))
        # the roundel: the console's stone in a bronze rim (front.py's relief, at its scale)
        saved = F._K
        F._K = k * 4
        try:
            disc = F._mask(n // 4, n // 4, lambda d, kk: d.ellipse([2 * kk, 2 * kk, (n // 4 - 2) * kk,
                                                                     (n // 4 - 2) * kk], fill=255))
            top, bottom = (C.hex_to_rgb(v) for v in sp["stone"])
            H = disc.height

            def field(x, y):
                return C._mix(top, bottom, C._smooth(y / H))

            stone = front.rim_relief(disc, sp["rim"] / 4, "bronze", field, None, rim_light=1.1, seed=21, noise=0.25)
        finally:
            F._K = saved
        stone = stone.resize((N, N), Image.LANCZOS)
        cover, height, cut = self.knot_layers(N)
        gold = [C.hex_to_rgb(c) for c in self.spec["wordmark"]["gilt"]]
        hscaled = [v * 7.0 * k for v in height]
        hscaled = C._blur(hscaled, N, N, 1, passes=1)
        knot = _gilt_shade(hscaled, cover, N, N, gold, C.hex_to_rgb("#fff8e0"))
        # the knot's shadow on the stone, and the cuts where one band passes over another
        cov_img = Image.new("L", (N, N))
        cov_img.putdata([int(255 * v) for v in cover])
        shadow = Image.new("L", (N, N), 0)
        shadow.paste(cov_img, (int(N * 0.006), int(N * 0.012)))
        shadow = shadow.filter(ImageFilter.GaussianBlur(N * 0.008)).point(lambda v: int(v * 0.75))
        dark = Image.new("RGBA", (N, N), (8, 5, 2, 0))
        dark.putalpha(shadow)
        cut_img = Image.new("L", (N, N))
        cut_img.putdata([int(255 * v) for v in cut])
        cuts = Image.new("RGBA", (N, N), (10, 7, 4, 0))
        cuts.putalpha(cut_img.filter(ImageFilter.GaussianBlur(1.2)).point(lambda v: int(v * 0.85)))
        # the roundel's stone shows only inside its rim; the knot sits on it
        img = Image.alpha_composite(Image.alpha_composite(Image.alpha_composite(stone, dark), cuts), knot)
        # nothing outside the roundel's own disc and shadow
        for name, size in sp["out"]:
            out = img.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA")
            self.save(name, out)

    def favicon(self):
        """The favicon's cut: a dark stone disc in a thin gilt ring, the (2, 3) knot on it in
        flat gilt (lit at the top, no bevel's fine shading, which a 16 px tab would only blur),
        the crossings cut dark so the over-and-under still reads."""
        sp = self.spec.get("favicon")
        if not sp:
            return
        n = sp["size"]
        cover, height, cut = self.knot_layers(n, sp["knot"])
        top, bottom = (C.hex_to_rgb(v) for v in sp["stone"])
        rim = C.hex_to_rgb(sp["rim"])
        dark, mid, light = (C.hex_to_rgb(v) for v in sp["gilt"])
        img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        px = img.load()
        c = n / 2
        for y in range(n):
            for x in range(n):
                d = math.hypot(x + 0.5 - c, y + 0.5 - c)
                disc = max(0.0, min(1.0, c - 1 - d))
                if disc <= 0.0:
                    continue
                col = C._mix(top, bottom, C._smooth(y / n))
                ring = max(0.0, 1.0 - abs(d - (c - n * 0.045)) / (n * 0.03))
                col = C._mix(col, rim, ring)
                i = y * n + x
                if cut[i] > 0:
                    col = C._mix(col, (6, 4, 2), cut[i] * 0.9)
                if cover[i] > 0:
                    t = 0.35 + 0.65 * height[i] * (1.0 - 0.55 * (y / n))
                    g = C._mix(dark, mid, min(1.0, t * 1.4)) if t < 0.72 else C._mix(mid, light, (t - 0.72) / 0.28)
                    col = C._mix(col, g, cover[i])
                px[x, y] = (int(col[0]), int(col[1]), int(col[2]), int(255 * disc))
        for name, size in sp["out"]:
            self.save(name, img.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA"))

    def paint(self) -> list[Path]:
        self.dest.mkdir(parents=True, exist_ok=True)
        self.wordmark()
        self.wordmark(small=True)
        self.emblem()
        self.favicon()
        return self.written


def main(argv: list[str]) -> int:
    project = Path(__file__).resolve().parents[2]
    spec_rel = argv[0] if argv else "art_src/ui/wordmark.json"
    dest_rel = argv[1] if len(argv) > 1 else "ui/brand"
    spec = json.loads((project / spec_rel).read_text())
    painter = _Brand(spec, project, project / dest_rel)
    written = painter.paint()
    script = Path(__file__).resolve().relative_to(project).as_posix()
    C.record(project, written, {"tool": "script", "script": script, "spec": spec_rel, "dest": dest_rel,
                                "regen": f"python3 {script} {spec_rel} {dest_rel}"}, keep=painter.unchanged)
    for f in written:
        print(f"wrote {f.relative_to(project).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
