"""Ottilie Brass, the Bellfounder of Brackwater, as a chibi Builder.

    godot-agent asset blender . art_src/blender/builders/bellfounder.py \\
        --to res://models/builders/bellfounder.glb --seed 1 --review
    godot-agent asset blender . art_src/blender/builders/bellfounder.py \\
        --to res://models/builders/bellfounder_bust.glb --seed 1 --param bust=1

A stout, sturdy bell-caster from the dike country, 2.55 heads tall and as broad as Tamsin:
a Delft-blue smock to the ankles under a big tan leather apron (a bib on two straps, a dark
belt), a brick-red kerchief knotted high under her chin, scorched dark leather mittens with
tan gauntlet cuffs, and round pale-wood clogs. Her hat is an oversized teal oilskin
sou'wester, the storm hat of the dikes: a low round crown, the brim short and turned up a
little at the front, wide and drooping at the sides and longest at the back, over a
honey-blonde fringe and two locks that flick out below it. The prop is a bronze hand bell
as wide as her head, held up by its turned wooden handle in her right mitten, mid-swing,
its clapper showing under the lip: a tool for ringing, nothing to swing at anyone. Her
hammer stays small: a little mallet on a dark chain at the front of her belt. Weight on
her left leg, left fist on her hip, chin up toward the bell.

Params: bust=1 (the portrait and icon model: cut through the apron's bib, the bell raised
beside her cheek, inside the portrait arch as she turns), check=1 (fail when over budget).
The body plan, face, hat and finishing are the kit's character helpers (chibi, gab).
"""

import math

from mathutils import Matrix, Vector

import chibi
import gab
from chibi import CLOTH, X, Y, Z, lerp, ring, rot, smoothstep

BUST = bool(int(gab.param("bust", 0)))

C = {
    "smock": "#46658c", "hat": "#2b6460", "apron": "#b07e50", "strap": "#7e5434", "kerchief": "#a8443a",
    "hair": "#deae58", "brow": "#9a6a2a", "skin": "#f2c4a0", "blush": "#f09080", "iris": "#3a5878",
    "glove": "#4e3428", "clog": "#e2c088", "clog_sole": "#b08850",
    "bronze": "#c4883a", "bronze_light": "#eebc64", "bronze_dark": "#7c5226", "handle": "#a8703c",
    "iron": "#5c5c66", "chain": "#3e3c44",
}

SPEC = {
    "H": 0.32, "heads": 2.55, "chin_out": 0.26, "skin": C["skin"], "blush": C["blush"],
    "material": "builder_toon", "palette": "palettes/builders.gpl",
    "face": {
        "eye_v": 0.40, "eye_u": 0.18, "eye_w": 0.22, "eye_h": 0.23,
        "iris_w": 0.16, "iris_h": 0.195, "iris_cover": 0.18, "look": (-0.012, 0.004),
        "lid_cut": 0.13, "lid_w": 0.032, "lid_flick": 0.004,
        "brow_up": 0.080, "brow_len": 0.17, "brow_w": 0.046,
        "brow_tilt": 12.0, "brow_raise": -0.004, "brow_arch": 0.006,
        "nose": (0.080, 0.058, 0.030), "nose_v": 0.29,
        "mouth": "smile", "mouth_v": 0.226, "mouth_w": 0.16,
        "blush": (0.14, 0.07), "blush_u": 0.29, "blush_v": 0.235,
        "iris": C["iris"], "brow": C["brow"],
    },
}

fig = chibi.Figure(SPEC)
H, W, HC, R = fig.H, fig.W, fig.HC, fig.R
# the head tips up toward the bell in her right mitten; planned first, so the hat's brim
# and the locks land where the pose puts them
NECK = Vector((0.0, 0.028, fig.chin + 0.020))
fig.plan_head(NECK, rot(z=-8) @ rot(x=-9))

# ── 1, 2: head and face ──
head = fig.head()
fig.face()

# ── 3: hair: a cap, three fringe clumps, two locks that flick out below the brim ──


def hairline(a):
    """Latitude of the hair's edge, a degrees round from the front."""
    return lerp(lerp(40.0, -22.0, smoothstep(26.0, 74.0, a)), -50.0, smoothstep(100.0, 175.0, a))


cap = fig.cap(hairline, C["hair"])
locks = []
for k, (a0, a1, w) in enumerate(((-34, -42, 0.21), (-6, -10, 0.24), (24, 30, 0.21))):
    locks.append(fig.lock(f"fringe_{k}", [fig.dir(a0 * 0.8, 64), fig.dir(a0 * 0.95, 54), fig.dir(lerp(a0, a1, 0.4), 45),
                                          fig.dir(lerp(a0, a1, 0.8), 38.5), fig.dir(a1, 33.5)],
                          [w * W, w * W, w * 0.95 * W, w * 0.6 * W, 0.0], 0.05 * W, C["hair"], lift=1.075))
for side in (-1, 1):   # short bob locks: down past the ear, the tips flicked outward
    locks.append(fig.lock(f"side_lock_{side}", [fig.dir(side * 72, 24), fig.dir(side * 78, 6), fig.dir(side * 82, -12),
                                                fig.dir(side * 86, -28), fig.dir(side * 98, -36)],
                          [0.16 * W, 0.16 * W, 0.15 * W, 0.12 * W, 0.0], 0.07 * W, C["hair"], lift=1.08))

# ── 4: the sou'wester: a low round crown and a brim swept round as one closed section,
#       short and turned up a little at the front, wide and drooping at the sides and
#       longest at the back, all tipped back 8 degrees ──
HAT_BASE = HC + Vector((0.0, 0.016, 0.070))
R_IN = 0.174
TILT = chibi.about(HAT_BASE, rot(x=-8, y=-3))
hat = fig.hat(HAT_BASE, [(0.000, 1.00), (0.050, 1.00), (0.104, 0.955), (0.144, 0.86), (0.168, 0.66), (0.180, 0.0)],
              R_IN, C["hat"], segs=18, tilt=TILT)


def brim_reach(th):
    """The brim's outer radius at th (ring() angles: -90 degrees is the front)."""
    return (0.82 + 0.12 * math.sin(th) + 0.02 * math.cos(th) ** 2) * W * (0.90 if BUST else 1.0)


def brim_lift(th, r_share):
    """Turned up a little at the front, drooping at the sides, down most at the back."""
    front = max(0.0, -math.sin(th))
    back = max(0.0, math.sin(th))
    side = math.cos(th) ** 2
    return (0.040 * front ** 2 - 0.055 * side - 0.135 * back ** 1.2) * r_share ** 1.5


SECTION = [(0.00, 0.006), (0.94, 0.003), (0.97, -0.011)]
M = 32
verts = []
for r_share, z0 in SECTION:
    for k in range(M):
        th = 2 * math.pi * k / M
        rr = lerp(R_IN * 0.99, brim_reach(th), r_share)
        verts.append(HAT_BASE + Vector((math.cos(th) * rr, math.sin(th) * rr * 0.96, z0 + brim_lift(th, r_share))))
faces = []
for i in range(len(SECTION)):
    i1 = (i + 1) % len(SECTION)
    for k in range(M):
        k1 = (k + 1) % M
        faces.append((i * M + k, i * M + k1, i1 * M + k1, i1 * M + k))
brim = chibi.mesh("hat_brim", verts, faces)
chibi.transform(brim, TILT)
fig.add(brim, "hat", C["hat"], smooth=40, head=True)

# hidden faces: the skull under the cap, the hair under the hat


def hidden_skin(co, margin=3.0):
    a, lat = fig.angles(co)
    return lat > hairline(a) + margin or lat < (-74.0 if a < 50.0 else -64.0)


chibi.cull(head, hidden_skin)
for obj in [cap] + locks:
    chibi.cull(obj, lambda co: hat.covers(co, 0.012))

# ── 5: the smock: a Delft-blue bell to the ankles, stout and round ──
HEM = 0.30 * H
SMOCK = [(HEM, 0.206, 0.188, 0.0), (0.170, 0.205, 0.186, 0.0), (0.250, 0.193, 0.173, 0.0),
         (0.330, 0.171, 0.153, 0.0), (0.392, 0.150, 0.134, 0.004), (0.450, 0.098, 0.090, 0.008)]
fig.bell(SMOCK, C["smock"], C["smock"], 0.030, front_rise=0.030, segs=18)
fig.neck(0.056, 0.420, taper=1.2)


def smock_radius(z, th):
    """Where the smock's surface lies at height z and angle th, for the apron to follow."""
    for (z0, rx0, ry0, dy0), (z1, rx1, ry1, dy1) in zip(SMOCK, SMOCK[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            rx, ry, dy = lerp(rx0, rx1, t), lerp(ry0, ry1, t), lerp(dy0, dy1, t)
            x, y = chibi.superellipse(th, 2.15)
            return Vector((x * rx, dy + y * ry, z))
    raise ValueError(z)


# ── 6: the leather apron: a skirt and bib that follow the smock's front a little proud of
#       it, the edges rolled in toward it, two straps over the shoulders and a dark belt ──
APRON = [  # (z, half angle of the front it covers, degrees)
    (0.118, 74.0), (0.180, 72.0), (0.250, 66.0), (0.300, 58.0), (0.340, 46.0), (0.372, 40.0), (0.398, 38.0)]
N_A = 12
rings_a = []
for z, half in APRON:
    pts = []
    for j in range(N_A + 1):
        t = j / N_A
        th = math.radians(-90.0 - half + 2 * half * t)
        p = smock_radius(z, th)
        k = 1.045 if 0 < j < N_A else 1.0   # the edges tuck into the smock
        lift = 0.008 * max(0.0, -math.sin(th)) ** 2   # stands off the rising front hem
        pts.append(Vector((p.x * k, p.y * k, p.z + lift)))
    rings_a.append(pts)
apron = chibi.loft("apron", rings_a, closed=False)
fig.add(apron, "apron", C["apron"], smooth=70)
BELT_Z = 0.300
belt_pts = [smock_radius(BELT_Z, 2 * math.pi * k / 16) for k in range(16)]
belt_pts = [Vector((p.x * 1.07, p.y * 1.07, p.z)) for p in belt_pts]
belt = chibi.tube("belt", belt_pts, [(0.007, 0.018)] * 16, sides=4, up=Z, closed=True)
fig.add(belt, "apron", C["strap"])
for side in (-1, 1):   # the straps: from the bib's top corners over the shoulders to the belt behind
    top = rings_a[-1][0 if side < 0 else -1]
    strap_pts = chibi.catmull([top + Vector((0.0, 0.0, -0.004)), Vector((side * 0.100, -0.084, 0.430)),
                               Vector((side * 0.112, 0.004, 0.446)), Vector((side * 0.100, 0.096, 0.410)),
                               Vector((side * 0.096, 0.150, 0.330))], 1)
    out = [Vector((p.x, p.y, 0.0)).normalized() for p in strap_pts]
    strap = chibi.tube(f"strap_{side}", strap_pts, [(0.014, 0.005)] * len(strap_pts), sides=4, normals=out)
    fig.add(strap, "apron", C["strap"])

# ── 7: the kerchief: a fat brick-red ring knotted at the front, high under her chin ──
kc = Vector((0.0, 0.004, 0.458))
k_rings = [kc + Vector((0.098 * math.cos(2 * math.pi * k / 14), 0.090 * math.sin(2 * math.pi * k / 14), 0.0))
           for k in range(14)]
kerchief = chibi.tube("kerchief", k_rings, [(0.032, 0.026)] * 14, sides=6, up=Z, closed=True)
fig.add(kerchief, "kerchief", C["kerchief"])
knot = chibi.blob("kerchief_knot", (0.020, -0.112, 0.446), (0.030, 0.022, 0.026), segs=7, rows=4)
fig.add(knot, "kerchief", C["kerchief"])
for k, (dx, ang) in enumerate(((0.030, 20.0), (0.004, -14.0))):
    tail = chibi.teardrop(f"kerchief_tail_{k}", Vector((0.020 + dx * 0.4, -0.114, 0.440)),
                          Vector((math.sin(math.radians(ang)), -0.25, -1.0)), 0.070, 0.036, 0.012, X, taper=0.5,
                          segs=5, rows=4, cage=False)
    fig.add(tail, "kerchief", C["kerchief"])

# ── 8 to 10: arms and mittens: the right one up and out, the bell's handle in its fist;
#            the left fist on her hip ──
if BUST:   # the bell comes in beside her cheek, lower and closer, inside the portrait arch
    GRIP, BELL_TILT, BS = Vector((-0.178, -0.080, 0.574)), rot(y=6.0, x=6.0), 0.76
else:
    GRIP, BELL_TILT, BS = Vector((-0.300, -0.052, 0.560)), rot(y=16.0, x=4.0), 1.00
ARMS = {
    -1: [(-0.116, 0.0, 0.414), (-0.236, 0.024, 0.430), GRIP + Vector((0.010, 0.024, -0.034))],
    1: [(0.116, 0.0, 0.412), (0.246, 0.040, 0.312), (0.208, -0.028, 0.236)],
}
for side, pts in ARMS.items():
    fig.arm(side, pts, 0.046, C["smock"], C["apron"], cuff_len=0.026)
fig.mitten(-1, GRIP, fingers=(0.30, -1.0, 0.0), back=(-1.0, 0.0, 0.2), size=(0.074, 0.066, 0.084),
           colour=C["glove"], curl=0.1)
fig.mitten(1, (0.204, -0.036, 0.226), fingers=(-0.3, -0.5, -1.0), back=(1.0, 0.0, 0.2),
           size=(0.076, 0.062, 0.084), colour=C["glove"])

# ── 11, 12: round clogs of pale wood under the hem, toes out, her weight on her left ──
for side in (-1, 1):
    fig.boot(side, (0.080 * side, -0.044 if side < 0 else -0.030, 0.0), 16 * side, 0.104, 0.46 * H, 0.100,
             C["clog"], C["clog"], C["clog_sole"], cuff_h=0.014, sole_h=0.018, toe=0.68, toe_h=0.56, shin=0.44,
             flare=1.10)

# ── 13: the hand bell, built upright round the grip and then tipped mid-swing: a turned
#        wooden handle with a knob, a bronze collar, the bell lofted from crown to a flared
#        lip (dark inside), a light sound bow, and the clapper's ball under the lip ──
bell_parts = []
HANDLE = 0.100 * BS
TOP = GRIP + Vector((0.0, 0.0, 0.050 * BS))
handle = chibi.tube("bell_handle", [TOP, TOP - Z * HANDLE * 0.5, TOP - Z * HANDLE],
                    [0.017 * BS, 0.016 * BS, 0.019 * BS], sides=8)
bell_parts.append(fig.add(handle, "prop", C["handle"], smooth=50))
knob = chibi.blob("bell_knob", TOP + Z * 0.010 * BS, (0.024 * BS, 0.024 * BS, 0.018 * BS), segs=8, rows=4)
bell_parts.append(fig.add(knob, "prop", C["handle"]))
CROWN = TOP - Z * HANDLE
collar = chibi.tube("bell_collar", [CROWN + Z * 0.008 * BS, CROWN - Z * 0.010 * BS],
                    [0.026 * BS, 0.030 * BS], sides=8)
bell_parts.append(fig.add(collar, "prop", C["bronze_dark"], smooth=50))
PROFILE = [  # (depth below the crown, radius), lip last: about 0.7 W across at the lip
    (0.000, 0.000), (0.004, 0.040), (0.016, 0.062), (0.040, 0.074), (0.080, 0.080), (0.120, 0.090),
    (0.150, 0.104), (0.170, 0.118), (0.182, 0.126), (0.190, 0.124)]
rings_b = [ring(CROWN - Z * (d * BS), max(r * BS, 0.0005), max(r * BS, 0.0005), 12) for d, r in PROFILE]
body = chibi.loft("bell_body", rings_b[1:], cap0=False, cap1=True)
LIP_Z = CROWN.z - 0.190 * BS


def bell_paint(c, i):
    if c.z < LIP_Z + 0.0006:
        return C["bronze_dark"], CLOTH          # the mouth: dark inside
    if c.z < CROWN.z - 0.150 * BS:
        return C["bronze_light"], CLOTH         # the sound bow catches the light
    return C["bronze"], CLOTH


bell_parts.append(fig.add(body, "prop", bell_paint, smooth=60))
dome = chibi.blob("bell_dome", CROWN - Z * 0.010 * BS, (0.058 * BS, 0.058 * BS, 0.026 * BS), segs=12, rows=4)
bell_parts.append(fig.add(dome, "prop", C["bronze"]))
clapper = chibi.blob("bell_clapper", Vector((CROWN.x, CROWN.y, LIP_Z - 0.006 * BS)),
                     (0.030 * BS, 0.030 * BS, 0.030 * BS), segs=6, rows=3)
bell_parts.append(fig.add(clapper, "prop", C["iron"]))
fig.pose(bell_parts, chibi.about(GRIP, BELL_TILT))

# ── 14: the little hammer on its chain, hanging from the front of her belt ──
if not BUST:
    hook = smock_radius(BELT_Z, math.radians(-118.0))
    hook = Vector((hook.x * 1.10, hook.y * 1.10, BELT_Z - 0.010))
    chain_path = [hook, hook + Vector((-0.004, -0.010, -0.036)), hook + Vector((-0.006, -0.018, -0.074))]
    chain = chibi.lobes("hammer_chain", chain_path, [0.0080] * 3, stretch=1.20, segs=6, rows=3)
    fig.add(chain, "hammer", C["chain"])
    head_c = chain_path[-1] + Vector((0.0, -0.006, -0.012))
    shaft = chibi.tube("hammer_shaft", [head_c, head_c + Vector((0.004, -0.004, -0.062))], [0.0085, 0.0075], sides=6)
    fig.add(shaft, "hammer", C["handle"], smooth=50)
    hammer = chibi.blob("hammer_head", head_c, (0.026, 0.013, 0.013), segs=8, rows=4, power=3.0)
    fig.add(hammer, "hammer", C["iron"])

# ── Pose: the head as planned; the body leans onto her left leg ──
fig.pose_head()
LEAN = chibi.about((0, 0, 0), rot(y=3.0))
hand = (LEAN @ GRIP) - GRIP
fig.pose(fig.everything(but=("boot", "prop")), LEAN)
fig.pose([o for o, p in fig.parts if p == "prop"], Matrix.Translation(hand))

fig.finish("bellfounder_bust" if BUST else "bellfounder", bust_cut=0.30 if BUST else None,
           check=bool(int(gab.param("check", 0))))
