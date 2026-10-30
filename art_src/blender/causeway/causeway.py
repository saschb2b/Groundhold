"""The Causeway at low water: props for the hub's backdrop (design 5.1, world.md).

    godot-agent asset blender . art_src/blender/causeway/causeway.py \\
        --to res://models/causeway/road.glb --seed 1 --param piece=road
    (and piece=pole, piece=cairn, piece=wrack, each to its own file)

A raised stone road across the bared Flats, where crews meet and set out. It belongs to no
land, so nothing here is Wickhollow's: no lanterns, gourds or autumn, only weathered
stone, sea timber and weed.

    road    a 2-unit length of the causeway that chains end to end along its length (+Z in
            Godot): sloped sides of dressed blocks, wet and dark below the tide line with a
            fringe of weed, a crowned top of worn flags, a kerb of set stones along both edges
    pole    a leaning timber tide pole with notched depth marks, a rope wrap and weed at its foot
    cairn   a waymark of stacked flat stones, the top one cut with a simple arrow
    wrack   a clump of weed left by the tide on the flats

Front faces -Y, base on the origin (the flats' level), 1 unit = 1 tile.
"""

import math
import os
import sys

from mathutils import Matrix, Vector

import gab

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "builders"))
import figure as fig  # noqa: E402

fig.setup()
rng = gab.rng
PIECE = str(gab.param("piece", "road"))

HEX = {
    "stone": "#6c675f", "stone_light": "#9c958b", "stone_dark": "#4a4642", "wet": "#34322f", "flag": "#736d64",
    "flag_light": "#958e83", "barnacle": "#cfc8b8", "weed": "#3a3519", "weed_light": "#62582a",
    "timber": "#5b4a3a", "timber_light": "#8a7a64", "rope": "#a08a62", "mark": "#2e2a26",
}
TIDE = 0.13  # the tide line on the road's sides
parts = []


def add(obj, fn, pattern="plain", smooth=0.0):
    fig.material(obj)
    if smooth:
        fig.smooth(obj, smooth)
    else:
        gab.flat(obj)
    fig.paint(obj, fn, pattern)
    parts.append(obj)
    return obj


def weathered(base, top, z0, z1, tide=TIDE, grain=0.08):
    """Stone or timber: dark and wet below the tide line, with pale barnacle flecks there."""
    dry = fig.shade(base, top, z0, z1, grain=grain, ground=0.0)

    def colour(co, n):
        c = dry(co, n)
        wet = fig.smoothstep(tide + 0.03, tide - 0.03, co.z + 0.02 * fig.mottle(co, 1.0, 9.0))
        c = c.lerp(fig.col(HEX["wet"]) * fig.mottle(co, 0.1), 0.75 * wet)
        fleck = fig.mottle(co, 1.0, 60.0)
        if wet > 0.5 and fleck > 1.55:
            c = fig.col(HEX["barnacle"])
        return c
    return colour


def _with(colour, fn):
    """A colour function with `fn(co, n, c)` applied on top."""
    return lambda co, n: fn(co, n, colour(co, n))


def _courses(obj):
    """Swaps a loft's UVs so dressed blocks lie in courses along the road, not up its side."""
    layer = obj.data.uv_layers.active
    for loop in layer.data:
        u, v = loop.uv
        loop.uv = (v, u)
    return obj


def road():
    length, top_w, base_w, height = 2.0, 1.10, 1.60, 0.30
    half = length / 2
    # the body: a trapezoid, its top crowned, faced with dressed stone
    def side_x(z):
        return base_w / 2 - (base_w - top_w) / 2 * z / height

    # the section, with rows on the sides at the tide line so the wet stone ends in a line
    rows = (TIDE - 0.025, TIDE + 0.02)
    section = [(-base_w / 2, 0.0), (base_w / 2, 0.0)] + [(side_x(z), z) for z in rows] + \
        [(top_w / 2, height), (0.0, height + 0.025), (-top_w / 2, height)] + [(-side_x(z), z) for z in reversed(rows)]
    body = fig.loft("road_body", [[Vector((x, y, z)) for x, z in section]
                                  for y in (-half, -half / 2, 0.0, half / 2, half)], closed=True, cap0=True,
                    cap1=True, uv=1.6)
    # the rings run along +Y with their points counter-clockwise seen from -Y: face them outward
    fig.flip(body)
    _courses(body)
    add(body, weathered(HEX["stone_dark"], HEX["stone"], 0.0, height), "stone")
    # worn flags on the top, a little proud of the body
    flags = []
    count = 7
    for i in range(count):
        y0 = -half + length * i / count + 0.012
        y1 = -half + length * (i + 1) / count - 0.012
        for side, (x0, x1) in enumerate(((-top_w / 2 + 0.16, -0.01), (0.01, top_w / 2 - 0.16))):
            jitter = rng.uniform(-0.004, 0.006)
            stone = fig.box(f"flag_{i}_{side}", ((x0 + x1) / 2, (y0 + y1) / 2, height + 0.012 + jitter),
                            (x1 - x0, y1 - y0, 0.03), bevel=0.012)
            stone.data.transform(Matrix.Translation(Vector(((x0 + x1) / 2, (y0 + y1) / 2, 0))) @
                                 Matrix.Rotation(rng.uniform(-0.02, 0.02), 4, "Z") @
                                 Matrix.Translation(-Vector(((x0 + x1) / 2, (y0 + y1) / 2, 0))))
            flags.append(stone)
    flag_obj = gab.join(flags, "road_flags")
    add(flag_obj, fig.shade(HEX["flag"], HEX["flag_light"], height, height + 0.04, grain=0.14, grain_scale=9.0,
                            ground=0.0))
    # the kerb: set stones along both edges, a whole number per length so segments chain
    kerbs = []
    per = 8
    for side in (-1, 1):
        for i in range(per):
            y = -half + length * (i + 0.5) / per
            w = length / per - 0.03
            h = 0.11 + rng.uniform(-0.012, 0.014)
            k = fig.box(f"kerb_{side}_{i}", (side * (top_w / 2 - 0.075), y, height + h / 2 - 0.02), (0.15, w, h),
                        bevel=0.018)
            k.data.transform(Matrix.Translation(Vector((side * (top_w / 2 - 0.075), y, 0))) @
                             Matrix.Rotation(rng.uniform(-0.04, 0.04), 4, "Z") @
                             Matrix.Translation(-Vector((side * (top_w / 2 - 0.075), y, 0))))
            kerbs.append(k)
    kerb_obj = gab.join(kerbs, "road_kerb")
    add(kerb_obj, fig.shade(HEX["stone"], HEX["stone_light"], height, height + 0.12, grain=0.1, ground=0.0))
    # weed hanging along the tide line on both sides
    weeds = []
    for side in (-1, 1):
        for i in range(14):
            y = -half + length * (i + rng.uniform(0.15, 0.85)) / 14
            x = side * (base_w / 2 - (base_w - top_w) / 2 * (TIDE / height) - 0.005)
            base = Vector((x, y, TIDE + rng.uniform(-0.01, 0.015)))
            # down the slope (which runs 0.83 out for every 1 down) and a little off it
            down = Vector((side * 1.0, rng.uniform(-0.25, 0.25), -1.0)).normalized()
            blade = fig.leaf(f"weed_{side}_{i}", base + Vector((side * 0.012, 0, 0)), down, Vector((side, 0, 0.8)),
                             rng.uniform(0.12, 0.18), rng.uniform(0.05, 0.08), segs=3, fold=0.2, curl=0.012,
                             notch=0.3)
            weeds.append(blade)
    weed_obj = gab.join(weeds, "road_weed")
    add(weed_obj, fig.shade(HEX["weed"], HEX["weed_light"], 0.0, TIDE, grain=0.12, ground=0.0), smooth=40)


def pole():
    lean = Matrix.Rotation(math.radians(4), 3, "X") @ Matrix.Rotation(math.radians(-3), 3, "Y")
    zs = [0.02 * k for k in range(67)]  # rings close enough for the notches to show
    pts = [lean @ Vector((0, 0, z)) for z in zs]
    post = fig.tube("pole", pts, [0.055 - 0.007 * z for z in zs], sides=6, uv=1.0)

    def marks(co, n, c):
        # dark notches every 20 cm, a broader one at each metre
        z = co.z
        band = (z + 0.01) % 0.2 < 0.02 or (z + 0.01) % 1.0 < 0.04
        return fig.col(HEX["mark"]) if band and 0.1 < z < 1.25 else c
    add(post, _with(weathered(HEX["timber"], HEX["timber_light"], 0.0, 1.32, tide=0.45, grain=0.12), marks), "bark",
        smooth=50)
    cap = fig.tube("pole_cap", [lean @ Vector((0, 0, 1.30)), lean @ Vector((0, 0, 1.36)),
                                lean @ Vector((0, 0, 1.38))], [0.06, 0.05, 0.0], sides=6)
    add(cap, fig.shade(HEX["timber"], HEX["timber_light"], 1.3, 1.38, ground=0.0))
    for k, z in enumerate((0.78, 0.81, 0.84)):
        wrap = fig.ring_torus(f"rope_{k}", lean @ Vector((0, 0, z)), 0.056, 0.009, axis=lean @ Vector((0, 0, 1)),
                              segs=10, sides=4)
        add(wrap, fig.shade(HEX["rope"], HEX["rope"], ground=0.0), smooth=50)
    for k in range(7):
        a = 2 * math.pi * k / 7 + rng.uniform(-0.3, 0.3)
        base = Vector((math.cos(a) * 0.05, math.sin(a) * 0.05, 0.02))
        blade = fig.leaf(f"pole_weed_{k}", base, Vector((math.cos(a), math.sin(a), 0.25)), Vector((0, 0, 1)),
                         rng.uniform(0.12, 0.2), 0.045, segs=3, fold=0.15, curl=0.02, notch=0.3)
        add(blade, fig.shade(HEX["weed"], HEX["weed_light"], 0.0, 0.05, ground=0.0), smooth=40)


def cairn():
    z = 0.0
    sizes = [(0.42, 0.36, 0.11), (0.34, 0.30, 0.10), (0.27, 0.24, 0.09), (0.21, 0.19, 0.085), (0.16, 0.15, 0.08)]
    for i, (sx, sy, sz) in enumerate(sizes):
        c = Vector((rng.uniform(-0.015, 0.015), rng.uniform(-0.015, 0.015), z + sz / 2))
        rough = rng.uniform(0, 10)
        stone = fig.blob(f"cairn_{i}", c, (sx / 2, sy / 2, sz / 2), segs=9, rows=5,
                         shape=lambda d, rough=rough: (1.0 + 0.08 * math.sin(3 * math.atan2(d.y, d.x) + rough),
                                                       1.0 + 0.08 * math.sin(2 * math.atan2(d.y, d.x) + rough),
                                                       1.0 if abs(d.z) < 0.6 else 0.75),
                         rot=Matrix.Rotation(rng.uniform(0, math.pi), 3, "Z"))
        add(stone, weathered(HEX["stone_dark"], HEX["stone_light"], 0.0, 0.5, tide=0.06), "stone", smooth=35)
        z += sz * 0.92
    # an arrow cut in the top stone, pointing along the road
    arrow = fig.mesh("cairn_mark", [Vector((0.0, -0.05, z + 0.002)), Vector((0.03, -0.01, z + 0.002)),
                                    Vector((0.01, -0.01, z + 0.002)), Vector((0.01, 0.045, z + 0.002)),
                                    Vector((-0.01, 0.045, z + 0.002)), Vector((-0.01, -0.01, z + 0.002)),
                                    Vector((-0.03, -0.01, z + 0.002))], [(0, 6, 5, 4, 3, 2, 1)])
    add(arrow, fig.shade(HEX["mark"], ground=0.0, grain=0.0))


def wrack():
    for k in range(9):
        a = 2 * math.pi * k / 9 + rng.uniform(-0.25, 0.25)
        base = Vector((math.cos(a) * 0.03, math.sin(a) * 0.03, 0.006))
        d = Vector((math.cos(a), math.sin(a), rng.uniform(0.02, 0.12)))
        bend = Matrix.Rotation(rng.uniform(-0.5, 0.5), 3, "Z")
        blade = fig.leaf(f"wrack_{k}", base, bend @ d, Vector((0, 0, 1)), rng.uniform(0.12, 0.3),
                         rng.uniform(0.04, 0.08), segs=4, fold=0.18, curl=-0.012, notch=0.35)
        add(blade, fig.shade(HEX["weed"], HEX["weed_light"], 0.0, 0.04, grain=0.15, ground=0.0), smooth=40)
    for k in range(6):
        c = Vector((rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), 0.012))
        bladder = fig.blob(f"bladder_{k}", c, (0.016, 0.012, 0.012), segs=6, rows=4)
        add(bladder, fig.shade(HEX["weed_light"], ground=0.0), smooth=60)


{"road": road, "pole": pole, "cairn": cairn, "wrack": wrack}[PIECE]()
model = fig.finish(parts, f"causeway_{PIECE}")
fig.report(model, f"causeway {PIECE}")
