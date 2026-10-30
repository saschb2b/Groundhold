"""Edda Greyplume, the Lookout of Fogholm, as a chibi Builder.

    godot-agent asset blender . art_src/blender/builders/lookout.py \\
        --to res://models/builders/lookout.glb --seed 1 --review
    godot-agent asset blender . art_src/blender/builders/lookout.py \\
        --to res://models/builders/lookout_bust.glb --seed 1 --param bust=1

A composed lookout from the fog cliffs, 2.9 heads tall and slimmer than Tamsin, drawn in a
seabird's colours. A deep fog-white hood, lined in lichen orange, runs from her crown down
into a short feathered capelet, so hood and capelet are one garment and no neck shows. The
capelet lies over her shoulders and back in broad rounded scallops and is open at the
front, its edges rolled in and trimmed lichen, so the ink sea-coat's stand collar meets her
jaw and nothing pale sits under her mouth. The hood's upper corners rise into two broad,
rounded owl tufts, and one grey plume arches back from the left one: the Greyplume. The
ink coat flares as an A over tall tar boots with lichen cuffs and round toes; fog-white
knit mittens. A brass spyglass of three telescoping sections (dark draw tubes, a bright
barrel, a wide lens lip) rests on her right shoulder, pointing up, out and back. Weight on
her right leg, left mitten at her hip, head tipped up toward the open side.

Params: bust=1 (the portrait and icon model: cut through the coat, the spyglass stood up
beside her hood, clear of her face as the portrait turns), check=1 (fail when over budget).
The body plan, face, hood and finishing are the kit's character helpers (chibi, gab).
"""

import math

from mathutils import Matrix, Vector

import chibi
import gab
from chibi import CLOTH, X, lerp, rot, smoothstep

BUST = bool(int(gab.param("bust", 0)))

C = {
    "coat": "#4a4356", "fog": "#e0dbd2", "lichen": "#dc8a2e", "plume": "#8e8a96", "plume_tip": "#5c5866",
    "hair": "#3a2a26", "skin": "#b47a52", "blush": "#c46a5a", "iris": "#7a5414", "tar": "#2c2830",
    "brass": "#d6a23c", "brass_light": "#f2c868", "brass_dark": "#8a5e22", "leather": "#4b3a33", "lens": "#c9d3ea",
}

SPEC = {
    "H": 0.30, "heads": 2.9, "chin_out": 0.24, "skin": C["skin"], "blush": C["blush"],
    "material": "builder_toon", "palette": "palettes/builders.gpl",
    "face": {
        "eye_v": 0.40, "eye_u": 0.18, "eye_w": 0.22, "eye_h": 0.23,
        "iris_w": 0.155, "iris_h": 0.19, "iris_cover": 0.15, "look": (0.0, 0.0),
        "lid_cut": 0.14, "lid_w": 0.030, "lid_flick": 0.008,
        "brow_up": 0.085, "brow_len": 0.16, "brow_w": 0.035,
        "brow_tilt": 3.0, "brow_raise": 0.0, "brow_arch": 0.004,
        "nose": (0.070, 0.050, 0.026), "nose_v": 0.29,
        "mouth": "smirk", "mouth_v": 0.228, "mouth_w": 0.15,
        "blush": (0.12, 0.06), "blush_u": 0.29, "blush_v": 0.23,
        "iris": C["iris"], "brow": C["hair"],
    },
}

fig = chibi.Figure(SPEC)
H, W, HC, R = fig.H, fig.W, fig.HC, fig.R
# the head tips up and turns toward her open side; planned first, so the hood lands on the capelet
fig.plan_head(Vector((0.0, 0.028, fig.chin + 0.020)), rot(z=6) @ rot(x=-10))

# ── 1, 2: head and face ──
head = fig.head()
fig.face()

# ── 3: hair: a cap, a fringe parted to her right, two short locks framing the face ──


def hairline(a):
    return lerp(lerp(40.0, -20.0, smoothstep(26.0, 74.0, a)), -50.0, smoothstep(100.0, 175.0, a))


cap = fig.cap(hairline, C["hair"])
locks = []
for k, (a0, a1, w) in enumerate(((-30, -40, 0.20), (-6, -14, 0.22), (20, 14, 0.20))):
    locks += [fig.lock(f"fringe_{k}", [fig.dir(a0 * 0.8, 66), fig.dir(a0 * 0.95, 56), fig.dir(lerp(a0, a1, 0.4), 46),
                             fig.dir(lerp(a0, a1, 0.8), 39), fig.dir(a1, 33.5)],
             [w * W, w * W, w * 0.95 * W, w * 0.6 * W, 0.0], 0.05 * W, C["hair"], lift=1.075)]
for side in (-1, 1):   # short: they end at the cheek, well above the jaw, inside the hood
    locks += [fig.lock(f"side_lock_{side}", [fig.dir(side * 64, 34), fig.dir(side * 69, 20), fig.dir(side * 70, 6),
                                   fig.dir(side * 68, -6), fig.dir(side * 64, -14)],
             [0.15 * W, 0.15 * W, 0.13 * W, 0.09 * W, 0.0], 0.07 * W, C["hair"], lift=1.06)]

# ── 4: the hood: fog white, lined lichen orange, its opening pushed back past her brows and
#       down beside her jaw; at the sides and back it runs on down into the capelet ──
HOOD = 1.25


def opening(a):
    """The face opening's edge: over the brows at the front, down the cheeks, closed below -90."""
    return lerp(lerp(54.0, 12.0, smoothstep(10.0, 62.0, a)), -90.0, smoothstep(62.0, 100.0, a))


def drape(a, u):
    """The back of the hood lies on the capelet in a soft rounded point, not a ball."""
    back = math.exp(-((180.0 - a) / 38.0) ** 2)
    return 0.030 * back * math.sin(math.pi * min(1.0, u * 1.1)), 0.050 * back * u * u


SHOULDER = (0.128, 0.114, 0.488, 0.012)
hood = fig.hood("hood", opening, C["fog"], C["lichen"], HOOD, SHOULDER, segs=32, thick=0.10, drape=drape,
                lats=(78, 62, 47, 33, 20, 7, -5))
TUFT = {}
for side in (-1, 1):   # each tuft: one broad, flat fog-white feather grown out of the hood's upper
    #                    corner, leaning out and curling outward at its rounded tip: an owl's ear tuft
    root = fig.head_point(fig.dir(side * 42, 48), HOOD - 0.17)
    TUFT[side] = root
    axis = Vector((side * math.sin(math.radians(45)), 0.20, math.cos(math.radians(45))))
    tuft = chibi.teardrop(f"tuft_{side}", root, axis, 0.175, 0.142, 0.046, Vector((side, -0.15, 0.0)), taper=0.86,
                          bend=0.22, segs=6, rows=3)
    fig.add(tuft, "hood", C["fog"], head=True)
# the Greyplume: a broad, soft feather from the left tuft, arching up and back over the hood
# (so it shows from the front and the back, and stays inside the portrait arch as she
# turns), widest in the middle, its last quarter darker
base = TUFT[1] + Vector((0.020, 0.030, 0.070))
plume_pts = chibi.catmull([base, base + Vector((0.026, 0.050, 0.032)), base + Vector((0.050, 0.112, 0.028)),
                           base + Vector((0.062, 0.172, -0.004)), base + Vector((0.066, 0.226, -0.052))], 2)
n_p = len(plume_pts)
profile = [0.012, 0.028, 0.040, 0.048, 0.050, 0.046, 0.036, 0.022, 0.0]
plume_n = [Vector((0.55, -0.15, 1.0)).normalized()] * n_p
plume = chibi.tube("plume", plume_pts, [(w, 0.010) if w > 0 else 0.0 for w in profile], sides=6, normals=plume_n)
plume_len = sum((b_ - a_).length for a_, b_ in zip(plume_pts, plume_pts[1:]))


def along(c):
    """How far along the plume (0 root .. 1 tip) a point lies."""
    best = min(range(n_p), key=lambda i: (plume_pts[i] - c).length)
    return sum((b_ - a_).length for a_, b_ in zip(plume_pts[:best], plume_pts[1:best + 1])) / plume_len


fig.add(plume, "hood", lambda c, i: (C["plume_tip"], CLOTH) if along(c) > 0.74 else (C["plume"], CLOTH), head=True)

# hidden faces: the skull under the cap and inside the hood, the hair under the hood
chibi.cull(head, lambda co: fig.angles(co)[1] > min(hairline(fig.angles(co)[0]) + 3.0, opening(fig.angles(co)[0]) + 4.0)
           or fig.angles(co)[1] < -74.0)
for obj in [cap] + locks:
    chibi.cull(obj, lambda co: fig.angles(co)[1] > opening(fig.angles(co)[0]) + 8.0)

# ── 5: the sea-coat: an A-line in ink, flared to 1.07 H at the hem against 0.85 H
#       shoulders, with a stand collar up under her jaw (so no neck shows) ──
HEM = 0.50 * H
COAT = [(HEM, 0.162, 0.146, 0.0), (0.220, 0.145, 0.131, 0.0), (0.300, 0.129, 0.117, 0.0),
        (0.380, 0.117, 0.106, 0.0), (0.440, 0.106, 0.096, 0.004), (0.515, 0.074, 0.068, 0.008),
        (0.552, 0.062, 0.058, 0.010), (0.590, 0.058, 0.054, 0.012)]
fig.bell(COAT, C["coat"], C["coat"], 0.030, waves=3, wave_amp=0.025, front_rise=0.022, segs=20)

# ── 6: the capelet: fog white over her shoulders and back, open at the front so the ink coat
#       shows from the collar down (no white under her chin), its front edges trimmed lichen;
#       the hem is a run of broad rounded feather scallops ──
N_SCALLOP, PER = 6, 4
CAPELET = [  # (z, rx, ry, dy, half width of the front opening, share of the scallop)
    (0.556, 0.074, 0.069, 0.004, 0.050, 0.0), (0.534, 0.100, 0.092, 0.004, 0.054, 0.0),
    (0.506, 0.130, 0.118, 0.006, 0.060, 0.0), (0.472, 0.150, 0.136, 0.008, 0.068, 0.35),
    (0.442, 0.160, 0.146, 0.008, 0.074, 1.0)]
TRIM = 0.016   # the lichen trim's width along each front edge, rolled in toward the coat so the edge reads thick
ts = [0.0, TRIM] + [TRIM + (1 - TRIM) * k / (N_SCALLOP * PER) for k in range(1, N_SCALLOP * PER)] + [1 - TRIM, 1.0]
ROLL = {0.0: 0.80, 1.0: 0.80}
rings_c = []
for z, rx, ry, dy, half, share in CAPELET:
    gap = math.asin(min(1.0, half / ry))      # the opening, as an angle each side of the front
    pts = []
    for t in ts:
        th = -math.pi / 2 + gap + t * (2 * math.pi - 2 * gap)
        phase = (t * N_SCALLOP + 0.5) % 1.0     # half a lobe at each front corner
        sc = math.sqrt(max(0.0, 1.0 - (2.0 * phase - 1.0) ** 2)) * share
        k = (1 + 0.04 * sc) * ROLL.get(t, 1.0)
        pts.append(Vector((rx * k * math.cos(th), dy + ry * k * math.sin(th), z - 0.030 * sc - 0.006 * share)))
    rings_c.append(pts)
capelet = chibi.loft("capelet", rings_c, closed=False)
n_c = len(ts) - 1
fig.add(capelet, "mantle", lambda c, i: (C["lichen"], CLOTH) if i % n_c in (0, n_c - 1) else (C["fog"], CLOTH),
        smooth=70)

# ── 7 to 10: arms and mittens, held clear of the coat so they read against it ──
if BUST:   # the spyglass stands up beside her hood, pointing up and out, clear of her face as she turns
    GRIP, DIR, LENGTHS = Vector((-0.158, -0.064, 0.470)), Vector((-0.36, 0.04, 0.93)), (0.09, 0.12, 0.15)
else:      # it rests on her right shoulder, pointing up, out and back
    GRIP, DIR, LENGTHS = Vector((-0.150, -0.082, 0.458)), Vector((-0.46, 0.40, 0.79)), (0.12, 0.15, 0.19)
DIR.normalize()
ARMS = {
    -1: [(-0.098, 0.0, 0.500), (-0.196, 0.016, 0.412), GRIP + Vector((-0.012, 0.030, -0.022))],
    1: [(0.098, 0.0, 0.500), (0.212, 0.030, 0.404), (0.156, -0.022, 0.338)],
}
for side, pts in ARMS.items():
    fig.arm(side, pts, 0.040, C["coat"], C["coat"], cuff_len=0.020)
fig.mitten(-1, GRIP, fingers=-DIR.cross(X).normalized() + Vector((0.3, -0.2, 0.0)), back=(-1.0, -0.1, -0.2),
           size=(0.066, 0.058, 0.080), colour=C["fog"], curl=0.1)
fig.mitten(1, (0.152, -0.030, 0.328), fingers=(-0.3, -0.5, -1.0), back=(1.0, 0.0, 0.2),
           size=(0.066, 0.056, 0.078), colour=C["fog"])

# ── 11, 12: tall tar boots with lichen cuffs just under the hem and round toes that stick
#            forward; her weight on her right ──
for side in (-1, 1):
    fig.boot(side, (0.064 * side, -0.016 if side < 0 else -0.032, 0.0), 14 * side, 0.152, 0.50 * H, 0.112,
             C["tar"], C["lichen"], C["tar"], cuff_h=0.030, sole_h=0.014, toe=0.72, toe_h=0.52, shin=0.34, flare=1.28)

# ── 13: the spyglass: three telescoping sections, each about 1.4 x the last, the two draw
#        tubes in dark brass under the bright barrel, light lips at the joints, a short
#        leather grip, a wide lip and a glinting lens at the objective ──
d = DIR
side_v = d.cross(X).normalized() if abs(d.x) < 0.9 else d.cross(chibi.Y).normalized()
frame = Matrix((d.cross(side_v).normalized(), side_v, d)).transposed()
eye_end = GRIP - d * (LENGTHS[0] * 0.6)
R_SEC = (0.0125, 0.0175, 0.0250)
LIP = 0.016
at = eye_end
for k, (length, r_) in enumerate(zip(LENGTHS, R_SEC)):
    a_, b_ = at, at + d * length
    flare = 1.36 if k == 2 else 1.22
    pts, radii = [a_, b_ - d * LIP * (1.5 if k == 2 else 1.0), b_ - d * LIP * 0.9, b_], [r_, r_, r_ * flare, r_ * flare]
    tube_ = chibi.tube(f"spyglass_{k}", pts, radii, sides=8)

    def paint(c, i, k=k, a_=a_, length=length):
        t = (c - a_).dot(d)
        if k == 0 and 0.25 * length < t < 0.60 * length:
            return C["leather"], CLOTH
        if t > length - LIP * (1.5 if k == 2 else 1.0) + 0.001:
            return C["brass_light"], CLOTH
        return (C["brass"] if k == 2 else C["brass_dark"]), CLOTH

    fig.add(tube_, "prop", paint, smooth=50)
    at = b_ - d * 0.008
LENS_R = R_SEC[2] * 1.18
lens = chibi.tube("spyglass_lens", [at + d * 0.004, at + d * 0.0095], [LENS_R, LENS_R * 0.55], sides=8)
fig.add(lens, "prop", C["lens"], chibi.UNLIT, smooth=None)
eyecap = chibi.blob("spyglass_eyepiece", eye_end, (0.015, 0.015, 0.010), segs=8, rows=3, rot=frame)
fig.add(eyecap, "prop", C["brass_dark"])

# ── Pose: the head as planned; the body leans onto her right leg ──
fig.pose_head()
LEAN = chibi.about((0, 0, 0), rot(y=-3.0))
fig.pose(fig.everything(but=("boot",)), LEAN)

fig.finish("lookout_bust" if BUST else "lookout", bust_cut=0.40 if BUST else None,
           check=bool(int(gab.param("check", 0))))
