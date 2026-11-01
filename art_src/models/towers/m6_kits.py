#!/usr/bin/env python3
"""Writes the mesh recipes of the Bellfounder's and the Beekeeper's eighteen tower forms (M6, contract-m6.md §7).

    python3 art_src/models/towers/m6_kits.py      # from the project root

Each form gets art_src/models/towers/<form>.json (the board's model, models/towers/<form>.glb) and
art_src/models/tower_icons/<form>.json (its command icon's model, models/ui/towers/<form>.glb: the same tower
without its ground, the shaft cut short so the crown fills the button). Then, for every form:

    godot-agent asset mesh . art_src/models/towers/<form>.json --to res://models/towers/<form>.glb --seed 1
    godot-agent asset mesh . art_src/models/tower_icons/<form>.json --to res://models/ui/towers/<form>.glb --seed 1
    godot-agent asset icon . res://models/ui/towers/<form>.glb --to res://art_src/ui/renders/<form>.png \\
        --size 216 --pitch 30 --yaw 35      # pitch 14 for toll_tower and great_toll: the bell shows under the roof
    python3 art_src/ui/icons.py

It also writes the two Builders' emblem props, art_src/models/hand_bell.json and bee_smoker.json (models/ui/<prop>.glb,
rendered to art_src/ui/renders/builder_<id>.png at --pitch 22 --yaw 25 and framed by icons.py as
ui/icons/emblem_<id>.png).

The recipes are this script's output: change the shapes here and run it again, so every branch keeps sharing its
base. Branches reuse their base and change the crown, roof or head (design 3.7); no M6 form turns a head.

    python3 art_src/models/towers/m6_kits.py --check

writes nothing and exits 1 when a recipe on disk is not what this script writes, or when the model's entry in
asset_manifest.json (whose inline recipe `asset regen` builds from) holds another recipe: the script was changed
and not run, a recipe was edited by hand, or a model was not rebuilt after its recipe changed.

Ottilie Brass's towers stand on a turf dike with reeds and a cattail, in Brackwater brick with dark slate and
bronze bells: the Clapper Tower (a timber bell frame on a brick drum, its bell mid-swing over a heavy clapper),
the Toll Tower (a brick bell tower, the bell in an open belfry under a slate spire) and the Chime Post (a post with
a hoop of bronze chimes under a small slate cap). Sefa Amberwell's stand on the stepped red rock of Thousandwell's
cisterns: the Clay Hive (clay pipe hives stacked in a mud wall), the Apiary (a round whitewashed hive house with
rows of bee holes and a clay dome, like a dovecote) and the Hive Hum (a coiled straw hive on a stand, its door
glowing). Colours stay inside palettes/hollow.gpl (models/**: tolerance 26).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOWERS = ROOT / "art_src/models/towers"
ICONS = ROOT / "art_src/models/tower_icons"


def r4(v):
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, (list, tuple)):
        return [r4(x) for x in v]
    if isinstance(v, dict):
        return {k: r4(x) for k, x in v.items()}
    return v


def part(shape, at, color, **kw):
    out = {"shape": shape}
    out.update(kw)
    out["at"] = list(at)
    out["color"] = color
    return out


def cyl(at, r, h, color, rt=None, sides=8, **kw):
    p = {"radius": r, "height": h, "sides": sides}
    if rt is not None:
        p["radius_top"] = rt
    p.update(kw)
    return part("cylinder", at, color, **p)


def cone(at, r, h, color, sides=8, **kw):
    return part("cone", at, color, radius=r, height=h, sides=sides, **kw)


def box(at, size, color, **kw):
    return part("box", at, color, size=list(size), **kw)


def sph(at, r, color, seg=(8, 4), **kw):
    return part("sphere", at, color, radius=r, segments=list(seg), **kw)


def wedge(at, size, color, **kw):
    return part("wedge", at, color, size=list(size), **kw)


def rock(at, r, color, **kw):
    return part("rock", at, color, radius=r, detail=0, **kw)


def grp(parts, at=(0.0, 0.0, 0.0), rotate=None, scale=None):
    g = {"parts": parts, "at": list(at)}
    if rotate is not None:
        g["rotate"] = list(rotate)
    if scale is not None:
        g["scale"] = scale if isinstance(scale, (int, float)) else list(scale)
    return g


def ring_of(n, radius, parts, phase=0.0, at=None):
    g = {"repeat": n, "around": radius, "phase": phase, "parts": parts}
    if at is not None:
        g["at"] = list(at)
    return g


def recipe(note, colors, parts):
    text = json.dumps(parts)
    pal = {k: v for k, v in colors.items() if f'"{k}"' in text}
    return r4({"note": note, "colors": pal, "ground_ao": 0.3, "parts": parts})


# ── Colours: every one a paint of palettes/hollow.gpl ──

BRACK = {
    "turf": "#4f7a32", "turf_lit": "#6a9a3c", "reed": "#a0784a", "reed_pale": "#e6dcc3", "cattail": "#4e3423",
    "brick": "#9a4430", "brick_lit": "#b8563a", "stone": "#8a8580", "stone_pale": "#c9c3b8", "stone_dark": "#5e5a56",
    "slate": "#4a4d55", "slate_dark": "#3a3c42", "slate_roof": "#3a3c42", "slate_roof_lit": "#5e6270",
    "timber": "#4e3423", "wood": "#7a5534", "bronze": "#b07a3a", "bronze_dark": "#7a5426", "gold": "#e0b040",
    "bell_inner": "#2a1d14", "iron": "#3a3c42", "rope": "#e6dcc3", "slit": "#1a1410", "flag_blue": "#2f58a8",
    "flag_white": "#efe6d6", "gull": "#efe6d6",
}

WELL = {
    "rock": "#c4703a", "rock_dark": "#94502a", "plaster": "#e9d6aa", "plaster_shade": "#cbb68a",
    "clay": "#c8642e", "clay_lit": "#d27a3c", "clay_dark": "#8e4420", "straw": "#d0a860", "straw_lit": "#e6c47a",
    "straw_dark": "#9a7444", "honey": "#e0a030", "glow": "#ffb040", "bee": "#e8c04a", "bee_dark": "#1a1410",
    "wing": "#efe6d6", "hole": "#1a1410", "lavender": "#9a6ac0", "stem": "#5a6b2e", "smoke": "#c9c3b8",
    "smoke_lit": "#eef4f8", "wood": "#7a5534", "timber": "#4e3423", "gold": "#e0b040", "cloth": "#2f58a8",
    "cloth_white": "#efe6d6", "water": "#4aa0c8",
}


# ── Shared pieces: the Bellfounder's ──

def dike(icon=False):
    """A low turf dike with basalt at its foot, reed clumps and a cattail: Brackwater's ground."""
    if icon:
        return []
    reeds = []
    for k, (ang, rad) in enumerate(((205.0, 0.36), (325.0, 0.37), (95.0, 0.35))):
        a = math.radians(ang)
        stalks = [cone((0.0, 0.0, 0.0), 0.014, 0.26, "reed", sides=3, rotate=[8.0, 0.0, -4.0]),
                  cone((0.03, 0.0, 0.01), 0.012, 0.21, "reed_pale", sides=3, rotate=[14.0, 0.0, 10.0]),
                  cone((-0.025, 0.0, 0.015), 0.012, 0.19, "turf_lit", sides=3, rotate=[-6.0, 0.0, -14.0])]
        if k != 1:
            stalks.append(cyl((-0.004, 0.17, 0.016), 0.018, 0.06, "cattail", sides=5))
        reeds.append(grp(stalks, at=(rad * math.cos(a), 0.06, -rad * math.sin(a))))
    return [
        cyl((0.0, 0.0, 0.0), 0.47, 0.08, "turf", rt=0.41, sides=10, bevel=0.02, color_top="turf_lit", jitter=0.006),
        ring_of(6, [0.40, 0.43], [rock((0.0, 0.035, 0.0), [0.045, 0.065], ["stone_dark", "stone"], pattern="stone")],
                phase=12.0),
    ] + reeds


def bell(scale=1.0, flare=1.0, color="bronze", band="gold", sides=12):
    """A bronze bell hanging from its crown at the group's origin (y 0), lip down: a flared lip in light
    bronze, sound bow, waist, shoulder and a domed crown. About 0.34 x scale tall, 0.20 x scale across the lip."""
    s = scale
    lip_r = 0.20 * s * flare
    y = -0.34 * s
    bevel = 0.006 * s if sides >= 12 else 0.0   # (a small bell's lip stays sharp: fewer triangles)
    parts = [cyl((0.0, y, 0.0), lip_r, 0.03 * s, band, rt=0.19 * s, sides=sides, bevel=bevel, cap_color="bell_inner",
                 pattern="gold")]
    y += 0.03 * s
    parts.append(cyl((0.0, y, 0.0), 0.19 * s, 0.07 * s, color, rt=0.155 * s, sides=sides, pattern="gold"))
    y += 0.07 * s
    parts.append(cyl((0.0, y, 0.0), 0.155 * s, 0.15 * s, color, rt=0.128 * s, sides=sides, pattern="gold"))
    y += 0.15 * s
    parts.append(cyl((0.0, y, 0.0), 0.128 * s, 0.05 * s, color, rt=0.088 * s, sides=sides, pattern="gold"))
    y += 0.05 * s
    parts.append(sph((0.0, y, 0.0), 0.09 * s, color, seg=(sides, 4), scale=[1.0, 0.42, 1.0], pattern="gold"))
    parts.append(box((0.0, y + 0.02 * s, 0.0), (0.05 * s, 0.05 * s, 0.03 * s), "bronze_dark"))
    return parts


def clapper(drop, r, scale=1.0, seg=(8, 5)):
    """The clapper under a bell's lip: an iron rod and a heavy ball, `drop` below the lip."""
    lip = -0.34 * scale
    return [cyl((0.0, lip - drop, 0.0), 0.013 * scale, drop + 0.06 * scale, "iron", sides=5),
            sph((0.0, lip - drop, 0.0), r, "iron", seg=seg, pattern="metal")]


def brick_drum(h, icon=False):
    y0 = 0.0 if icon else 0.08
    return [
        cyl((0.0, y0, 0.0), 0.36, h, "brick", rt=0.34, sides=8, phase=22.5, bevel=0.02, pattern="bricks"),
        cyl((0.0, y0 + h, 0.0), 0.375, 0.04, "stone", sides=8, phase=22.5, bevel=0.012, pattern="stone"),
        cyl((0.0, y0 + h + 0.035, 0.0), 0.33, 0.012, "wood", sides=8, phase=22.5, pattern="planks"),
    ], y0 + h + 0.045


# ── The Clapper Tower and its branches ──

def clapper_tower(form, icon=False):
    great = form == "great_clapper"
    ringing = form == "ringing_clapper"
    drum_h = 0.30 if great else 0.24
    drum, top = brick_drum(drum_h if not icon else 0.14, icon)
    parts = dike(icon) + drum
    post = 0.12 if great else 0.09
    px = 0.27
    rise = 0.90 if great else 0.80
    beam_y = top + rise
    beam_w = 0.80 if ringing else (0.78 if great else 0.70)
    for sx in (-1, 1):
        parts.append(box((sx * px, top, 0.0), (post, rise, post + 0.02), "timber", bevel=0.012, pattern="planks"))
        parts.append(box((sx * px, top, 0.0), (post + 0.05, 0.06, post + 0.08), "stone", bevel=0.01, pattern="stone"))
        for sz in (-1, 1):   # raking struts from the post's foot to the drum's rim
            parts.append(box((sx * px, top, sz * 0.08), (0.04, 0.32, 0.04), "wood", rotate=[sz * 28.0, 0.0, 0.0],
                             pattern="planks"))
        if great:
            for yb in (0.22, 0.62):
                parts.append(box((sx * px, top + yb * rise, 0.0), (post + 0.016, 0.03, post + 0.036), "iron"))
    parts.append(box((0.0, beam_y, 0.0), (beam_w, 0.10, 0.14), "timber", bevel=0.014, pattern="planks"))
    for sx in (-1, 1):
        parts.append(box((sx * (beam_w / 2 - 0.03), beam_y - 0.006, 0.0), (0.05, 0.112, 0.152), "iron"))
    beam_w = min(beam_w, 0.80)
    parts.append(box((0.0, beam_y - 0.07, 0.0), (0.24, 0.07, 0.15), "wood", bevel=0.01, pattern="planks"))
    s = 1.24 if great else 1.0
    swing = [8.0, 0.0, -14.0]
    bell_parts = bell(s, flare=1.18 if ringing else 1.0) + clapper(0.10 * s, 0.085 if great else 0.068, s)
    if great:
        bell_parts.append(cyl((0.0, -0.20 * s, 0.0), 0.152 * s, 0.022 * s, "gold", rt=0.146 * s, sides=12,
                              pattern="gold"))
    parts.append(grp(bell_parts, at=(0.0, beam_y - 0.07, 0.0), rotate=swing))
    if ringing:   # two small gilded bells hang outside the posts, at the beam's ends
        # On the icon they hang larger, so the branch reads apart from its base at the card's 54 px.
        ss = 0.66 if icon else 0.50
        for sx in (-1, 1):
            small = bell(ss, flare=1.12, color="gold", band="bronze", sides=7) + clapper(0.08 * ss, 0.06 * ss, ss,
                                                                                        seg=(5, 3))
            parts.append(box((sx * 0.35, beam_y - 0.06, 0.0), (0.03, 0.07, 0.03), "iron"))
            parts.append(grp(small, at=(sx * 0.35, beam_y - 0.06, 0.0), rotate=[0.0, 0.0, sx * 8.0]))
    if great:   # a slate gable roof over the beam, gold on its ridge
        parts.append(wedge((0.0, beam_y + 0.10, 0.0), (0.40, 0.20, 0.92), "slate_dark", rotate=[0.0, 90.0, 0.0],
                           pattern="shingles"))
        parts.append(sph((0.0, beam_y + 0.31, 0.0), 0.04, "gold", seg=(6, 4), pattern="gold"))
    else:
        parts.append(sph((0.0, beam_y + 0.12, 0.0), 0.035, "gold", seg=(6, 4), pattern="gold"))
        parts.append(cyl((0.0, beam_y + 0.10, 0.0), 0.012, 0.03, "iron", sides=4))
    return parts


# ── The Toll Tower and its branches ──

def toll_tower(form, icon=False):
    great = form == "great_toll"
    sky = form == "sky_toll"
    y0 = 0.0 if icon else 0.08
    body = 0.24 if icon else 0.92
    parts = dike(icon) + [
        box((0.0, y0, 0.0), (0.58, 0.10, 0.58), "stone", bevel=0.02, pattern="stone"),
        box((0.0, y0 + 0.08, 0.0), (0.50, body - 0.08, 0.50), "brick", bevel=0.02, taper=0.94, pattern="bricks"),
    ]
    if not icon:
        parts += [
            box((0.0, y0 + 0.48, 0.0), (0.51, 0.04, 0.51), "stone_pale", pattern="stone"),
            box((0.0, y0 + 0.10, 0.25), (0.15, 0.24, 0.03), "timber", pattern="planks"),
            box((0.0, y0 + 0.34, 0.255), (0.17, 0.035, 0.03), "stone_pale"),
            box((0.0, y0 + 0.60, 0.243), (0.06, 0.14, 0.02), "slit"),
            box((0.243, y0 + 0.60, 0.0), (0.02, 0.14, 0.06), "slit"),
            box((-0.243, y0 + 0.60, 0.0), (0.02, 0.14, 0.06), "slit"),
        ]
    top = y0 + body
    parts.append(box((0.0, top, 0.0), (0.56, 0.05, 0.56), "stone_pale", bevel=0.01, pattern="stone"))
    belfry = 0.44 if great else 0.42
    fy = top + 0.05
    for sx in (-1, 1):
        for sz in (-1, 1):
            parts.append(box((sx * 0.215, fy, sz * 0.215), (0.09, belfry, 0.09), "brick_lit", bevel=0.01,
                             pattern="bricks"))
    lintel = fy + belfry
    parts.append(box((0.0, lintel, 0.0), (0.56, 0.06, 0.56), "stone_pale", bevel=0.01, pattern="stone"))
    parts.append(box((0.0, lintel - 0.05, 0.0), (0.42, 0.05, 0.08), "timber", pattern="planks"))
    if not sky:
        s = 1.12 if great else 0.94
        b = bell(s) + clapper(0.0, 0.04 * s, s)
        if great:
            b.append(cyl((0.0, -0.20 * s, 0.0), 0.152 * s, 0.022 * s, "gold", rt=0.146 * s, sides=12, pattern="gold"))
        parts.append(grp(b, at=(0.0, lintel - 0.05, 0.0)))
    else:   # the belfry stands empty: the bell is lifted into the open, under the sky
        parts.append(box((0.0, fy, 0.0), (0.36, 0.08, 0.36), "timber", pattern="planks"))
    roof_y = lintel + 0.06
    if great:   # a Dutch lantern roof: a slate drum, a bulb, a gold-banded lantern and a gold spike
        for sx in (-1, 1):
            for sz in (-1, 1):
                parts.append(cone((sx * 0.24, roof_y, sz * 0.24), 0.045, 0.14, "gold", sides=4, pattern="gold"))
        parts += [
            cyl((0.0, roof_y, 0.0), 0.26, 0.08, "slate_dark", sides=8, phase=22.5, pattern="shingles"),
            sph((0.0, roof_y + 0.27, 0.0), 0.23, "bronze", seg=(8, 6), scale=[1.0, 1.0, 1.0],
                color_top="gold", pattern="gold"),
            cyl((0.0, roof_y + 0.46, 0.0), 0.08, 0.04, "gold", sides=8, pattern="gold"),
            cyl((0.0, roof_y + 0.50, 0.0), 0.065, 0.08, "slate_dark", sides=8),
            cone((0.0, roof_y + 0.58, 0.0), 0.08, 0.16, "slate_roof", sides=8, pattern="shingles"),
            sph((0.0, roof_y + 0.75, 0.0), 0.03, "gold", seg=(6, 4), pattern="gold"),
        ]
    elif sky:   # a parapet, an iron arch over the roof with the bell hung in the open, sky-blue pennants
        for sx in (-1, 1):
            for sz in (-1, 1):
                parts.append(box((sx * 0.235, roof_y, sz * 0.235), (0.10, 0.10, 0.10), "stone_pale", bevel=0.008,
                                 pattern="stone"))
        arch_h = 0.56
        for sx in (-1, 1):
            parts.append(box((sx * 0.17, roof_y, 0.0), (0.045, arch_h, 0.06), "iron", rotate=[0.0, 0.0, sx * 6.0]))
        parts.append(box((0.0, roof_y + arch_h - 0.02, 0.0), (0.44, 0.06, 0.08), "iron"))
        parts.append(cyl((0.0, roof_y + arch_h + 0.04, 0.0), 0.06, 0.04, "gold", sides=8, pattern="gold"))
        b = bell(0.80) + clapper(0.02, 0.034, 0.80)
        parts.append(grp(b, at=(0.0, roof_y + arch_h - 0.02, 0.0), rotate=[0.0, 0.0, 6.0]))
        # the gull on the arch, wings up
        parts.append(grp([sph((0.0, 0.0, 0.0), 0.035, "gull", seg=(6, 4), scale=[0.8, 0.8, 1.5]),
                          wedge((0.05, 0.01, 0.0), (0.10, 0.05, 0.03), "gull", rotate=[0.0, 0.0, -70.0]),
                          wedge((-0.05, 0.01, 0.0), (0.10, 0.05, 0.03), "gull", rotate=[0.0, 0.0, 70.0]),
                          cone((0.0, 0.0, 0.05), 0.012, 0.035, "gold", sides=3, rotate=[90.0, 0.0, 0.0])],
                         at=(0.0, roof_y + arch_h + 0.12, 0.0), rotate=[0.0, 30.0, 0.0]))
        for sx, sz, col in ((-1, -1, "flag_blue"), (1, 1, "flag_white")):
            parts.append(cyl((sx * 0.25, roof_y + 0.09, sz * 0.25), 0.012, 0.36, "timber", sides=4))
            parts.append(grp([wedge((0.0, 0.0, 0.0), (0.07, 0.24, 0.01), col, rotate=[0.0, 0.0, -98.0],
                                    pattern="cloth")],
                             at=(sx * 0.25, roof_y + 0.43, sz * 0.25), rotate=[0.0, 40.0 if sx < 0 else -140.0, 0.0]))
    else:   # a steep slate spire with flared eaves, a gold ball and a weathercock
        parts += [
            box((0.0, roof_y - 0.01, 0.0), (0.62, 0.035, 0.62), "slate_dark", pattern="shingles"),
            cyl((0.0, roof_y, 0.0), 0.43, 0.62, "slate_roof", rt=0.0, sides=4, phase=45.0,
                color_top="slate_roof_lit", pattern="shingles"),
            cyl((0.0, roof_y + 0.55, 0.0), 0.012, 0.20, "iron", sides=4),
            sph((0.0, roof_y + 0.64, 0.0), 0.035, "gold", seg=(6, 4), pattern="gold"),
            grp([wedge((0.0, 0.0, 0.0), (0.12, 0.08, 0.012), "gold", pattern="gold"),
                 wedge((-0.05, 0.03, 0.0), (0.05, 0.07, 0.012), "gold", rotate=[0.0, 0.0, 40.0])],
                at=(0.0, roof_y + 0.71, 0.0), rotate=[0.0, 30.0, 0.0]),
        ]
    return parts


# ── The Chime Post and its branches ──

def chime(length, r, color="gold", cap="bronze_dark", foot="bronze"):
    """A bright bronze chime tube hanging down from the group's origin, darker toward its foot, a dark ring at
    its top."""
    return [cyl((0.0, 0.0, 0.0), r, length, color, sides=6, rotate=[180.0, 0.0, 0.0], color_top=foot,
                pattern="gold"),
            cyl((0.0, -0.025, 0.0), r * 1.25, 0.02, cap, sides=6, pattern="gold")]


def chime_post(form, icon=False):
    deep = form == "deep_chime"
    long_ = form == "long_chime"
    y0 = 0.0 if icon else 0.08
    parts = dike(icon) + [
        cyl((0.0, y0, 0.0), 0.21, 0.16, "brick", rt=0.19, sides=8, phase=22.5, bevel=0.015, pattern="bricks"),
        cyl((0.0, y0 + 0.16, 0.0), 0.23, 0.035, "stone", sides=8, phase=22.5, bevel=0.01, pattern="stone"),
    ]
    foot = y0 + 0.195
    post_h = (0.62 if icon else 1.18) + (0.10 if deep else 0.0)
    top = foot + post_h
    parts.append(box((0.0, foot, 0.0), (0.11, post_h, 0.11), "timber", bevel=0.012, pattern="planks"))
    for yb in (0.12, 0.55):
        parts.append(box((0.0, foot + yb * post_h, 0.0), (0.125, 0.03, 0.125), "iron"))
    if long_:   # four long arms reaching out, a chime at each end and one under each arm's middle
        arm_y = top - 0.10
        parts.append(box((0.0, arm_y, 0.0), (0.90, 0.05, 0.06), "timber", pattern="planks", bevel=0.008))
        parts.append(box((0.0, arm_y, 0.0), (0.06, 0.05, 0.90), "timber", pattern="planks", bevel=0.008))
        for k in range(4):
            a = math.radians(90.0 * k + 0.0)
            for rad, ln in ((0.42, 0.36), (0.23, 0.26)):
                parts.append(grp(chime(ln, 0.022), at=(rad * math.cos(a), arm_y, -rad * math.sin(a))))
            parts.append(sph((0.44 * math.cos(a), arm_y + 0.025, -0.44 * math.sin(a)), 0.03, "gold", seg=(6, 3),
                             pattern="gold"))
        parts += [
            cone((0.0, top - 0.06, 0.0), 0.15, 0.20, "slate_roof", sides=8, phase=22.5, color_top="slate_roof_lit",
                 pattern="shingles"),
            sph((0.0, top + 0.16, 0.0), 0.032, "gold", seg=(6, 4), pattern="gold"),
        ]
        return parts
    hoop_y = top - 0.12
    hoop_r = 0.31
    spokes = ring_of(4, hoop_r / 2, [box((0.0, 0.0, 0.0), (0.04, 0.04, hoop_r), "timber", pattern="planks")],
                     phase=45.0, at=(0.0, hoop_y, 0.0))
    edge = 2 * hoop_r * math.sin(math.radians(22.5)) + 0.03
    hoop = ring_of(8, hoop_r * math.cos(math.radians(22.5)),
                   [box((0.0, -0.02, 0.0), (edge, 0.04, 0.04), "wood", pattern="planks")], phase=22.5,
                   at=(0.0, hoop_y, 0.0))
    parts += [spokes, hoop]
    if deep:   # a domed bronze cap over six long, heavy chimes in dark bronze, a bell hanging in the middle
        parts += [
            sph((0.0, top - 0.02, 0.0), 0.20, "bronze", seg=(10, 5), scale=[1.0, 0.55, 1.0], color_top="gold",
                pattern="gold"),
            cyl((0.0, top - 0.035, 0.0), 0.21, 0.03, "bronze_dark", sides=10, pattern="gold"),
            sph((0.0, top + 0.12, 0.0), 0.035, "gold", seg=(6, 4), pattern="gold"),
        ]
        lengths = (0.66, 0.54, 0.62, 0.50, 0.70, 0.58)
        for k, ln in enumerate(lengths):
            a = math.radians(30.0 + 60.0 * k)
            parts.append(grp(chime(ln, 0.036, "bronze", "gold", "bronze_dark"), at=(hoop_r * math.cos(a), hoop_y - 0.02,
                                                                  -hoop_r * math.sin(a))))
        return parts
    parts += [
        cone((0.0, top - 0.04, 0.0), 0.19, 0.20, "slate_roof", sides=8, phase=22.5, color_top="slate_roof_lit",
             pattern="shingles"),
        sph((0.0, top + 0.18, 0.0), 0.032, "gold", seg=(6, 4), pattern="gold"),
    ]
    lengths = (0.36, 0.28, 0.42, 0.30, 0.38, 0.26, 0.40, 0.32)
    for k, ln in enumerate(lengths):
        a = math.radians(45.0 * k)
        parts.append(grp(chime(ln, 0.027), at=(hoop_r * math.cos(a), hoop_y - 0.02, -hoop_r * math.sin(a))))
    return parts


# ── Shared pieces: the Beekeeper's ──

def cistern_steps(icon=False):
    """Two steps of red rock, cut like the stepped cisterns of Thousandwell, a little water in a channel."""
    if icon:
        return []
    return [
        box((0.0, 0.0, 0.0), (0.90, 0.07, 0.90), "rock_dark", bevel=0.015, pattern="stone", jitter=0.004),
        box((0.0, 0.07, 0.0), (0.76, 0.07, 0.76), "rock", bevel=0.015, pattern="stone", jitter=0.004),
        box((0.0, 0.062, 0.415), (0.50, 0.012, 0.05), "water"),
    ]


def bee(at, heading=0.0, size=1.0, pitch=0.0):
    """A small round bee: a striped honey body, a dark head and two pale wings, flying along +Z."""
    s = size
    return grp([
        sph((0.0, 0.0, 0.0), 0.034 * s, "bee", seg=(6, 4), scale=[0.85, 0.85, 1.35]),
        cyl((0.0, 0.0, -0.012 * s), 0.031 * s, 0.014 * s, "bee_dark", sides=5, rotate=[90.0, 0.0, 0.0]),
        sph((0.0, 0.004 * s, 0.050 * s), 0.021 * s, "bee_dark", seg=(5, 3)),
        box((0.024 * s, 0.026 * s, -0.004 * s), (0.044 * s, 0.004 * s, 0.032 * s), "wing", rotate=[0.0, 0.0, -24.0]),
        box((-0.024 * s, 0.026 * s, -0.004 * s), (0.044 * s, 0.004 * s, 0.032 * s), "wing", rotate=[0.0, 0.0, 24.0]),
    ], at=at, rotate=[pitch, heading, 0.0])


def pipe(at, r=0.115, length=0.56):
    """A clay pipe hive lying along Z: a mud plug at each end, a lip round its mouth and a dark entrance."""
    x, y, z = at
    return [
        cyl((x, y, z - length / 2), r, length, "clay", sides=8, phase=22.5, rotate=[90.0, 0.0, 0.0],
            cap_color="clay_dark", pattern="plain"),
        cyl((x, y, z + length / 2 - 0.035), r * 1.10, 0.04, "clay_lit", sides=8, phase=22.5, rotate=[90.0, 0.0, 0.0],
            cap_color="clay_dark"),
        cyl((x, y - r * 0.18, z + length / 2 + 0.004), r * 0.46, 0.012, "hole", sides=7, rotate=[90.0, 0.0, 0.0]),
    ]


# ── The Clay Hive and its branches ──

def clay_hive(form, icon=False):
    great = form == "great_clay_hive"
    drowsy = form == "drowsy_clay_hive"
    y0 = 0.0 if icon else 0.14
    parts = cistern_steps(icon)
    rows = (4, 3, 2, 1) if great else (3, 2, 1)
    r = 0.100 if great else 0.115
    step = 2.05 * r
    rise = 1.74 * r
    for i, n in enumerate(rows):
        yc = y0 + r + i * rise
        for j in range(n):
            x = (j - (n - 1) / 2) * step
            parts += pipe((x, yc, 0.02), r)
    top = y0 + r + (len(rows) - 1) * rise + r
    width = rows[0] * step
    # the mud wall the pipes are bedded in, behind and under them
    parts.append(box((0.0, y0, -0.25), (width + 0.04, top - y0 - 0.06, 0.08), "plaster_shade", taper=0.55,
                     pattern="stone"))
    parts.append(box((0.0, y0, 0.0), (width + 0.06, 0.035, 0.62), "plaster", bevel=0.01, pattern="stone"))
    if great:   # a whitewashed dome on top, honey running from two mouths
        parts += [
            sph((0.0, top - 0.01, 0.02), 0.14, "plaster", seg=(8, 4), scale=[1.0, 0.75, 1.3], pattern="stone"),
            sph((0.0, top + 0.10, 0.02), 0.03, "gold", seg=(6, 3), pattern="gold"),
            cone((-0.1025, y0 + r - 0.04, 0.30), 0.022, 0.07, "honey", sides=5, rotate=[180.0, 0.0, 0.0]),
            cone((0.205, y0 + r + rise - 0.04, 0.30), 0.02, 0.06, "honey", sides=5, rotate=[180.0, 0.0, 0.0]),
        ]
        bees = [bee((0.30, top - 0.05, 0.36), heading=-40.0), bee((-0.33, top - 0.20, 0.30), heading=60.0, size=0.9),
                bee((0.05, top + 0.18, 0.28), heading=150.0, size=0.9)]
    elif drowsy:   # a clay chimney pot on top, smoking, and lavender at the corners
        parts += [
            cyl((0.0, top - 0.02, 0.02), 0.075, 0.13, "clay_dark", rt=0.06, sides=8, pattern="plain"),
            cyl((0.0, top + 0.11, 0.02), 0.075, 0.03, "clay_lit", sides=8, cap_color="hole"),
            sph((0.02, top + 0.22, 0.02), 0.07, "smoke", seg=(7, 4), color_top="smoke_lit"),
            sph((0.08, top + 0.34, -0.02), 0.085, "smoke", seg=(7, 4), color_top="smoke_lit"),
            sph((0.17, top + 0.47, -0.05), 0.10, "smoke_lit", seg=(7, 4)),
        ]
        if not icon:
            for sx in (-1, 1):
                sprigs = [cyl((0.0, 0.0, 0.0), 0.008, 0.16, "stem", sides=3, rotate=[a, 0.0, b])
                          for a, b in ((6.0, -8.0), (-6.0, 10.0), (10.0, 4.0))]
                sprigs += [cone((dx, 0.13, dz), 0.022, 0.09, "lavender", sides=4)
                           for dx, dz in ((-0.02, 0.01), (0.022, -0.01), (0.012, 0.02))]
                parts.append(grp(sprigs, at=(sx * 0.33, 0.14, 0.31)))
        bees = [bee((0.24, y0 + 0.08, 0.36), heading=-90.0, pitch=10.0, size=0.9)]
    else:
        parts += [
            box((0.0, top - 0.015, 0.0), (0.30, 0.035, 0.40), "rock", bevel=0.01, pattern="stone"),
            cyl((0.06, top + 0.02, 0.06), 0.06, 0.08, "clay_lit", rt=0.045, sides=7),
            sph((0.06, top + 0.10, 0.06), 0.045, "clay", seg=(7, 3), scale=[1.0, 0.6, 1.0]),
        ]
        bees = [bee((0.28, top - 0.10, 0.36), heading=-40.0), bee((-0.30, top - 0.22, 0.32), heading=60.0, size=0.9)]
    return parts + bees


# ── The Apiary and its branches ──

def apiary(form, icon=False):
    royal = form == "royal_apiary"
    guard = form == "queens_guard"
    y0 = 0.0 if icon else 0.14
    radius = 0.33 if guard else 0.30
    body = (0.62 if icon else 0.96) + (0.16 if royal else 0.0) - (0.06 if guard else 0.0)
    parts = cistern_steps(icon) + [
        cyl((0.0, y0, 0.0), radius + 0.02, 0.08, "rock", sides=10, bevel=0.015, pattern="stone"),
        cyl((0.0, y0 + 0.08, 0.0), radius, body - 0.08, "plaster", rt=radius - 0.03, sides=10, pattern="stone"),
    ]
    top = y0 + body
    bands = (0.36, 0.66) if not royal else (0.30, 0.54, 0.78)
    holes = [0.47, 0.77] if not royal else [0.40, 0.64, 0.88]
    if icon:
        bands, holes = (0.50,), [0.68]
    for f in bands:
        r_here = radius - 0.03 * f
        parts.append(cyl((0.0, y0 + f * body, 0.0), r_here + 0.012, 0.035, "clay", sides=10, pattern="plain"))
    for k, f in enumerate(holes):
        r_here = radius - 0.03 * f + 0.004
        parts.append(ring_of(8, r_here, [box((0.0, 0.0, 0.0), (0.05, 0.065, 0.02), "hole")],
                             phase=22.5 * (k % 2), at=(0.0, y0 + f * body, 0.0)))
        if k == 0:
            parts.append(ring_of(8, r_here + 0.012, [box((0.0, -0.012, 0.0), (0.08, 0.016, 0.035), "clay_lit")],
                                 phase=22.5 * (k % 2), at=(0.0, y0 + f * body, 0.0)))
    if not icon:   # a cedar door with a honey-gold lintel
        parts += [box((0.0, y0 + 0.08, radius - 0.02), (0.13, 0.20, 0.04), "timber", pattern="planks"),
                  box((0.0, y0 + 0.28, radius - 0.018), (0.17, 0.03, 0.05), "honey")]
    if guard:   # a crenellated guard ring, a clay platform and the queen herself on watch
        parts += [
            cyl((0.0, top, 0.0), radius - 0.01, 0.05, "clay", sides=10, pattern="plain"),
            ring_of(8, radius - 0.03, [box((0.0, 0.0, 0.0), (0.12, 0.11, 0.07), "plaster", bevel=0.01,
                                           pattern="stone")], phase=0.0, at=(0.0, top + 0.05, 0.0)),
            cyl((0.0, top + 0.05, 0.0), radius - 0.08, 0.04, "clay_dark", sides=10),
        ]
        q = 4.4
        parts.append(bee((0.0, top + 0.20, 0.0), heading=0.0, size=q, pitch=-12.0))
        parts.append(grp([cone((dx, 0.0, 0.0), 0.016, 0.05, "gold", sides=4, pattern="gold")
                          for dx in (-0.03, 0.0, 0.03)] +
                         [cyl((0.0, -0.01, 0.0), 0.04, 0.02, "gold", sides=6, pattern="gold")],
                         at=(0.0, top + 0.31, 0.23)))
        bees = [bee((0.32, top - 0.12, 0.30), heading=-60.0)]
    else:
        dome = 0.29 if not royal else 0.28
        dome_col = "gold" if royal else "clay"
        parts += [
            cyl((0.0, top, 0.0), radius - 0.02, 0.04, "clay_dark" if not royal else "honey", sides=10),
            sph((0.0, top + 0.04, 0.0), dome, dome_col, seg=(10, 6), scale=[1.0, 0.72, 1.0],
                color_top="clay_lit" if not royal else "glow", pattern="gold" if royal else "plain"),
            cyl((0.0, top + 0.04 + dome * 0.70, 0.0), 0.065, 0.10, "plaster", sides=8),
            cone((0.0, top + 0.14 + dome * 0.70, 0.0), 0.09, 0.13, "clay" if not royal else "gold", sides=8,
                 pattern="gold" if royal else "plain"),
            sph((0.0, top + 0.29 + dome * 0.70, 0.0), 0.03, "gold", seg=(6, 4), pattern="gold"),
        ]
        if royal:   # a ring of gold points round the dome, and a little crown on the finial
            parts.append(ring_of(10, radius - 0.01, [cone((0.0, 0.0, 0.0), 0.026, 0.10, "gold", sides=4,
                                                          pattern="gold")], phase=0.0, at=(0.0, top + 0.03, 0.0)))
            parts.append(ring_of(5, 0.035, [cone((0.0, 0.0, 0.0), 0.012, 0.05, "gold", sides=3, pattern="gold")],
                                 phase=0.0, at=(0.0, top + 0.33 + dome * 0.70, 0.0)))
        bees = [bee((0.30, top + 0.12, 0.20), heading=-50.0), bee((-0.24, top + 0.30, 0.12), heading=110.0,
                                                                   size=0.9)]
    return parts + bees


# ── The Hive Hum and its branches ──

def straw_hive(at, scale=1.0, honey_bands=(), glow=0.8):
    """A coiled straw hive on its board: five or six coils narrowing to a cap, the door glowing honey."""
    x, y, z = at
    coils = [(0.270, 0.272), (0.268, 0.255), (0.250, 0.225), (0.216, 0.180), (0.170, 0.118)]
    if honey_bands:
        coils = [(0.275, 0.278), (0.276, 0.266), (0.262, 0.240), (0.236, 0.205), (0.198, 0.158), (0.150, 0.100)]
    h = 0.085 * scale
    parts = []
    for k, (r0, r1) in enumerate(coils):
        col = "honey" if k in honey_bands else ("straw" if k % 2 == 0 else "straw_lit")
        parts.append(cyl((x, y + k * h, z), r0 * scale, h, col, rt=r1 * scale, sides=12, bevel=0.024 * scale,
                         pattern="thatch" if k not in honey_bands else "gold"))
    cap_y = y + len(coils) * h
    r_cap = coils[-1][1] * scale
    parts += [
        sph((x, cap_y, z), r_cap, "straw_lit", seg=(10, 4), scale=[1.0, 0.55, 1.0], pattern="thatch"),
        sph((x, cap_y + r_cap * 0.55, z), 0.035 * scale, "gold" if honey_bands else "straw_dark", seg=(6, 3)),
        box((x, y + 0.004, z + coils[0][0] * scale - 0.03 * scale), (0.12 * scale, 0.07 * scale, 0.07 * scale),
            "glow", emit=glow),
    ]
    return parts, cap_y + r_cap * 0.55


def hive_hum(form, icon=False):
    great = form == "great_hum"
    long_ = form == "long_hum"
    y0 = 0.0 if icon else 0.14
    parts = cistern_steps(icon)
    if long_:   # the straw hive raised high on a tall three-legged stand, ribbons from its board
        legs = 1.0 if not icon else 0.55
        parts.append(ring_of(3, 0.16, [box((0.0, 0.0, 0.0), (0.06, legs + 0.04, 0.06), "timber",
                                           rotate=[-9.0, 0.0, 0.0], pattern="planks")], phase=30.0,
                             at=(0.0, y0, 0.0)))
        parts.append(box((0.0, y0, 0.0), (0.07, legs, 0.07), "wood", pattern="planks"))
        parts.append(cyl((0.0, y0 + 0.45 * legs, 0.0), 0.14, 0.03, "wood", sides=6, pattern="planks"))
        board = y0 + legs
        parts.append(cyl((0.0, board, 0.0), 0.25, 0.04, "wood", sides=10, bevel=0.01, pattern="planks"))
        for k, col in enumerate(("cloth", "cloth_white", "cloth")):
            a = math.radians(200.0 + 70.0 * k)
            parts.append(grp([wedge((0.0, 0.0, 0.0), (0.06, 0.30, 0.008), col, rotate=[0.0, 0.0, 180.0],
                                    pattern="cloth")],
                             at=(0.24 * math.cos(a), board + 0.01, -0.24 * math.sin(a)),
                             rotate=[0.0, math.degrees(a) + 90.0, 6.0]))
        sk, sk_top = straw_hive((0.0, board + 0.04, 0.0), 0.78)
        parts += sk
        bees = [bee((0.24, board + 0.20, 0.22), heading=-60.0, size=0.9),
                bee((-0.22, board - 0.10, 0.18), heading=80.0, size=0.85)]
        return parts + bees
    ped = 0.30 if great else 0.26
    if icon:
        ped = 0.10
    parts += [
        cyl((0.0, y0, 0.0), 0.17, ped, "rock", rt=0.14, sides=8, phase=22.5, bevel=0.012, pattern="stone"),
        cyl((0.0, y0 + ped, 0.0), 0.32 if great else 0.30, 0.04, "wood", sides=10, bevel=0.01, pattern="planks"),
    ]
    board = y0 + ped + 0.04
    if great:
        sk, sk_top = straw_hive((0.0, board, 0.0), 1.12, honey_bands=(1, 4), glow=1.2)
        parts += sk
        parts += [cyl((0.27, board, 0.20), 0.05, 0.07, "clay", rt=0.04, sides=7),
                  sph((0.27, board + 0.075, 0.20), 0.04, "honey", seg=(6, 3), scale=[1.0, 0.6, 1.0])]
        bees = [bee((0.30, sk_top - 0.05, 0.18), heading=-50.0), bee((-0.30, sk_top - 0.20, 0.10), heading=70.0),
                bee((0.0, sk_top + 0.10, 0.25), heading=170.0, size=0.9)]
    else:
        sk, sk_top = straw_hive((0.0, board, 0.0), 1.0)
        parts += sk
        bees = [bee((0.28, sk_top - 0.08, 0.16), heading=-50.0), bee((-0.27, sk_top - 0.22, 0.12), heading=70.0)]
    return parts + bees


# ── The emblems' props (the hub's Builders button) ──

def hand_bell():
    """Ottilie Brass's bronze hand bell, mid-swing (tipped 22 degrees), its turned handle up and its clapper showing
    under the lip, and her small hammer hanging on its chain behind it."""
    body = [
        # lip, sound bow, waist, a gold band round the waist, shoulder and crown, from the mouth up
        cyl((0, 0, 0), 0.30, 0.045, "gold", rt=0.285, sides=16, bevel=0.01, cap_color="bell_inner", pattern="gold"),
        cyl((0, 0.045, 0), 0.285, 0.10, "bronze", rt=0.235, sides=16, pattern="gold"),
        cyl((0, 0.145, 0), 0.235, 0.21, "bronze", rt=0.195, sides=16, pattern="gold"),
        cyl((0, 0.205, 0), 0.226, 0.03, "gold", rt=0.222, sides=16, pattern="gold"),
        cyl((0, 0.355, 0), 0.195, 0.07, "bronze", rt=0.135, sides=16, pattern="gold"),
        sph((0, 0.425, 0), 0.137, "bronze", seg=(16, 5), scale=[1.0, 0.42, 1.0], pattern="gold"),
        # the collar and the turned wooden handle with its knob
        cyl((0, 0.44, 0), 0.075, 0.06, "bronze_dark", sides=10, pattern="gold"),
        cyl((0, 0.50, 0), 0.055, 0.07, "wood", rt=0.045, sides=10, pattern="planks"),
        cyl((0, 0.57, 0), 0.045, 0.16, "wood", rt=0.06, sides=10, pattern="planks"),
        sph((0, 0.76, 0), 0.075, "wood", seg=(10, 5), scale=[1.0, 0.8, 1.0], pattern="planks"),
        # the clapper's rod and ball under the lip
        cyl((0, -0.09, 0), 0.016, 0.14, "iron", sides=6),
        sph((0, -0.09, 0), 0.075, "iron", seg=(10, 5), pattern="metal"),
    ]
    chain = [sph((0, 0.03 * k, 0), 0.022, "iron", seg=(6, 3), scale=[1.0, 1.3, 0.5]) for k in range(6)]
    hammer = grp([cyl((0, 0, 0), 0.02, 0.26, "wood", sides=6, pattern="planks"),
                  box((0, 0.25, 0), (0.15, 0.065, 0.065), "iron", bevel=0.01, pattern="metal")],
                 at=(0.0, 0.18, 0.0), rotate=(0.0, 0.0, 180.0))
    return [grp(body, at=(0.0, 0.12, 0.0), rotate=(8.0, 0.0, -22.0)),
            grp(chain + [hammer], at=(0.3, 0.2, -0.14), rotate=(0.0, 30.0, -8.0), scale=0.8)]


def bee_smoker():
    """Sefa Amberwell's bee smoker: a tin canister with a domed lid and a bent spout, the wooden bellows with their
    leather fold on its side, and three puffs of smoke rising, the whole leaning 8 degrees."""
    canister = [
        cyl((0, 0, 0), 0.20, 0.04, "iron", sides=14, bevel=0.008, pattern="metal"),     # the foot ring
        cyl((0, 0.04, 0), 0.19, 0.40, "tin", sides=14, pattern="metal"),
        cyl((0, 0.20, 0), 0.197, 0.03, "iron", sides=14, pattern="metal"),               # a band
        cyl((0, 0.44, 0), 0.205, 0.035, "iron", sides=14, pattern="metal"),              # the lid's rim
        cyl((0, 0.475, 0), 0.19, 0.07, "tin", rt=0.15, sides=14, pattern="metal"),       # the domed lid
        cyl((0, 0.545, 0), 0.15, 0.07, "tin", rt=0.06, sides=14, pattern="metal"),
    ]
    spout = grp([cyl((0, 0, 0), 0.065, 0.16, "tin", rt=0.035, sides=10, pattern="metal")],
                at=(-0.03, 0.57, 0.0), rotate=(0.0, 0.0, 42.0))
    bellows = grp([
        box((0, 0, 0), (0.035, 0.40, 0.24), "wood", taper=0.75, bevel=0.008, pattern="planks"),
        box((0.13, 0, 0), (0.035, 0.40, 0.24), "wood", taper=0.75, bevel=0.008, pattern="planks",
            rotate=[0.0, 0.0, -10.0]),
        box((0.06, 0.02, 0), (0.10, 0.30, 0.20), "leather", taper=0.5, pattern="planks"),
        cyl((0.06, -0.02, 0), 0.03, 0.06, "iron", sides=6),
    ], at=(0.215, 0.1, 0.0))
    smoke = [
        sph((-0.2, 0.7, 0.0), 0.07, "smoke", seg=(8, 4)),
        sph((-0.28, 0.8, 0.02), 0.09, "smoke", seg=(8, 4), color_top="smoke_lit"),
        sph((-0.34, 0.94, 0.04), 0.11, "smoke_lit", seg=(8, 4)),
    ]
    # Leaned as a whole, about its foot (no offset).
    return [{"parts": canister + [spout, bellows] + smoke, "rotate": [0.0, 0.0, -8.0]}]


EMBLEMS = {
    "hand_bell": (hand_bell, {"bronze": "#b07a3a", "bronze_dark": "#7a5426", "gold": "#e0b040",
                              "bell_inner": "#2a1d14", "wood": "#a0784a", "iron": "#3a3c42"},
                  "Ottilie Brass's bronze hand bell, mid-swing, its turned handle up and its clapper showing under "
                  "the lip, with her small hammer hanging on its chain behind it: a bell-caster's tools, for the "
                  "Bellfounder's emblem (ui/icons/emblem_bellfounder.png) only."),
    "bee_smoker": (bee_smoker, {"tin": "#b3aca2", "iron": "#5e5a56", "wood": "#a0784a", "leather": "#6b4a34",
                                "smoke": "#c9c3b8", "smoke_lit": "#eef4f8"},
                   "Sefa Amberwell's bee smoker: a tin canister with a domed lid and a bent spout, the wooden "
                   "bellows with their leather fold on its side, and three puffs of smoke rising, for the "
                   "Beekeeper's emblem (ui/icons/emblem_beekeeper.png) only."),
}


# ── Notes and output ──

FORMS = {
    "clapper_tower": (clapper_tower, BRACK,
                      "The Bellfounder's Clapper Tower (Q): a timber bell frame on a brick drum over a turf dike, its "
                      "bronze bell mid-swing over a heavy iron clapper. The strike is instant; the view shows a clap."),
    "great_clapper": (clapper_tower, BRACK,
                      "Great Clapper (Clapper Tower, branch A): the frame heavier and taller, iron-banded posts, a "
                      "slate gable over the beam, a bigger bell with a gold band and a heavier clapper."),
    "ringing_clapper": (clapper_tower, BRACK,
                        "Ringing Clapper (Clapper Tower, branch B): the beam runs out past the posts and two small "
                        "bells hang at its ends beside the flared main bell: a strike that rings through a crowd."),
    "toll_tower": (toll_tower, BRACK,
                   "The Bellfounder's Toll Tower (W): a square Brackwater brick tower on a stone plinth, a big bell in "
                   "its open belfry under a steep slate spire with a gold ball and weathercock."),
    "great_toll": (toll_tower, BRACK,
                   "Great Toll (Toll Tower, branch A): a taller belfry with a bigger gold-banded bell, gold pinnacles "
                   "at its corners and a Dutch lantern roof: a slate drum, a gilded bronze bulb and a slate spike."),
    "sky_toll": (toll_tower, BRACK,
                 "Sky Toll (Toll Tower, branch B): no spire; the belfry stands empty and the bell hangs in an iron "
                 "arch over a parapet, open to the sky, a gull on the arch and pennants at two corners."),
    "chime_post": (chime_post, BRACK,
                   "The Bellfounder's Chime Post (E): a timber post on a brick footing, an octagonal hoop on four "
                   "spokes near its top under a small slate cap, eight bright bronze chimes of different lengths "
                   "hanging from the hoop."),
    "deep_chime": (chime_post, BRACK,
                   "Deep Chime (Chime Post, branch A): a domed bronze cap, and six long, heavy chimes in dark bronze "
                   "hanging from the hoop."),
    "long_chime": (chime_post, BRACK,
                   "Long Chime (Chime Post, branch B): four long arms cross the post's top, chimes at their ends and "
                   "middles, reaching farther; a small slate cap."),
    "clay_hive": (clay_hive, WELL,
                  "The Beekeeper's Clay Hive (Q): Thousandwell's clay pipe hives stacked three, two, one in a mud wall "
                  "on stepped red rock, each mouth with a lip and a dark entrance; bees about it."),
    "great_clay_hive": (clay_hive, WELL,
                        "Great Clay Hive (Clay Hive, branch A): a bigger stack, four, three, two, one, a whitewashed "
                        "dome on top and honey running from two mouths."),
    "drowsy_clay_hive": (clay_hive, WELL,
                         "Drowsy Clay Hive (Clay Hive, branch B): the stack with a smoking clay chimney pot on top and "
                         "lavender at the corners: the smoke slows what it stings."),
    "apiary": (apiary, WELL,
               "The Beekeeper's Apiary (W): a round whitewashed hive house like a dovecote, two rings of bee holes "
               "with clay ledges, clay bands, a clay dome and a turret; its bees are models/projectiles/bee.glb."),
    "royal_apiary": (apiary, WELL,
                     "Royal Apiary (Apiary, branch A): taller, three rings of holes, the dome gilded, a ring of gold "
                     "points round it and a little crown on the finial."),
    "queens_guard": (apiary, WELL,
                     "Queen's Guard (Apiary, branch B): broader and lower, a crenellated guard ring for a dome and the "
                     "queen bee herself on watch on the platform, crowned."),
    "hive_hum": (hive_hum, WELL,
                 "The Beekeeper's Hive Hum (E): a coiled straw hive on a board over a red-rock pedestal, its door "
                 "glowing honey; bees about it."),
    "great_hum": (hive_hum, WELL,
                  "Great Hum (Hive Hum, branch A): a bigger six-coil straw hive with two honey bands, a gold knob, a "
                  "brighter door and a honey pot beside it."),
    "long_hum": (hive_hum, WELL,
                 "Long Hum (Hive Hum, branch B): a smaller straw hive raised high on a tall three-legged stand, "
                 "ribbons hanging from its board: the hum carries farther."),
}


def dump(rec: dict) -> str:
    """A recipe laid out as the others in art_src/models/towers/ are: its keys one to a line, a part to a line."""
    lines = ["{"]
    lines += [f'  "{k}": {json.dumps(v)},' for k, v in rec.items() if k != "parts"]
    lines.append('  "parts": [')
    parts = rec["parts"]
    lines += ["    " + json.dumps(p) + ("," if i < len(parts) - 1 else "") for i, p in enumerate(parts)]
    lines += ["  ]", "}"]
    return "\n".join(lines) + "\n"


def dump_nested(rec: dict) -> str:
    """A prop's recipe, whose parts are a few groups: as `dump`, but a group's own parts one to a line under it."""
    def lay(p: dict, pad: str) -> str:
        if "parts" not in p or next(iter(p)) != "parts":
            return pad + json.dumps(p)
        inner = ",\n".join(lay(q, pad + "  ") for q in p["parts"])
        rest = json.dumps({k: v for k, v in p.items() if k != "parts"})[1:-1]
        return f'{pad}{{"parts": [\n{inner}\n{pad}]' + (f", {rest}}}" if rest else "}")

    lines = ["{"]
    lines += [f'  "{k}": {json.dumps(v)},' for k, v in rec.items() if k != "parts"]
    lines.append('  "parts": [')
    lines.append(",\n".join(lay(p, "    ") for p in rec["parts"]))
    lines += ["  ]", "}"]
    return "\n".join(lines) + "\n"


def outputs() -> list[tuple[str, str, str]]:
    """Every file this script writes: (recipe path, the model built from it, the recipe's text)."""
    out = []
    for form, (build, colors, note) in FORMS.items():
        out.append((f"art_src/models/towers/{form}.json", f"models/towers/{form}.glb",
                    dump(recipe(note, colors, build(form)))))
        icon = recipe(f"{form} for its command icon only: the ground left off, the shaft cut short.", colors,
                      build(form, icon=True))
        icon["origin"] = "bottom-center"
        out.append((f"art_src/models/tower_icons/{form}.json", f"models/ui/towers/{form}.glb", dump(icon)))
    for prop, (build, colors, note) in EMBLEMS.items():
        rec = r4({"note": note, "colors": colors, "origin": "bottom-center", "parts": build()})
        out.append((f"art_src/models/{prop}.json", f"models/ui/{prop}.glb", dump_nested(rec)))
    return out


def check() -> int:
    """Exit 1, writing nothing, when a recipe on disk or a model's manifest entry is not this script's output."""
    assets = json.loads((ROOT / "asset_manifest.json").read_text())["assets"]
    stale, unbuilt = [], []
    for rel, model, text in outputs():
        path = ROOT / rel
        if not path.exists() or path.read_text() != text:
            stale.append(rel)
        entry = assets.get(model, {})
        if entry.get("source") != rel or entry.get("recipe") != json.loads(text):
            unbuilt.append(model)
    if stale or unbuilt:
        print("not this script's output: %s" % (", ".join(stale) or "-"))
        print("not built from it (asset_manifest.json): %s" % (", ".join(unbuilt) or "-"))
        return 1
    print("the M6 recipes and their models are current (%d recipes)" % len(outputs()))
    return 0


def main(argv: list[str]) -> int:
    if "--check" in argv:
        return check()
    for rel, _model, text in outputs():
        (ROOT / rel).write_text(text)
        print(f"wrote {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
