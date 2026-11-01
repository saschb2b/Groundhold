"""Sefa Amberwell, the Beekeeper of Thousandwell, as a chibi Builder.

    godot-agent asset blender . art_src/blender/builders/beekeeper.py \\
        --to res://models/builders/beekeeper.glb --seed 1 --review
    godot-agent asset blender . art_src/blender/builders/beekeeper.py \\
        --to res://models/builders/beekeeper_bust.glb --seed 1 --param bust=1

A wiry, sun-browned beekeeper from the red-rock city of stepped cisterns, 2.9 heads tall
and slim like Edda: a long terracotta tunic with an indigo hem and an indigo sash knotted
at her left hip, long cream canvas gloves (beekeeper's mittens) and tall soft boots. Her
hat is an oversized straw sun hat, a low flat crown with an indigo band and a wide brim,
and from the brim hangs her cream veil: round the sides and the back down to her
shoulders like a lampshade, rolled up at the front so her face shows, the roll lying on
the brim. The prop is a bee smoker as tall as her face, held up in her right mitten by
its bellows: a tin canister with a hinged lid and a spout, two wooden bellows boards over
a leather fold, and three puffs of smoke rising from the spout. Two bees hang in the air
by her hat (not in the bust). Dark hair under the hat, honey-amber eyes, a calm smile; left fist on her
hip, weight on her right leg, chin up toward the smoke.

Params: bust=1 (the portrait and icon model: cut through the tunic, the smoker raised
beside her jaw, inside the portrait arch as she turns), check=1 (fail when over budget).
The body plan, face, hat and finishing are the kit's character helpers (chibi, gab).
"""

import math

from mathutils import Matrix, Vector

import chibi
import gab
from chibi import CLOTH, X, Y, Z, lerp, ring, rot, smoothstep

BUST = bool(int(gab.param("bust", 0)))

C = {
    "tunic": "#b4552f", "indigo": "#33417a", "straw": "#d8b062", "veil": "#e8dfc8", "veil_in": "#c6bca4",
    "hair": "#2a1a16", "skin": "#9c6440", "blush": "#c0604c", "iris": "#a86c18", "glove": "#e6dcc2",
    "boot": "#6a4430", "boot_sole": "#3e2a20",
    "tin": "#c4c0b4", "tin_dark": "#84827a", "bellows": "#8a5a36", "leather": "#5a3a2a", "smoke": "#dcd8d0",
    "bee": "#f0b830", "bee_dark": "#2a2018", "wing": "#f6f2e8",
}

SPEC = {
    "H": 0.30, "heads": 2.9, "chin_out": 0.24, "skin": C["skin"], "blush": C["blush"],
    "material": "builder_toon", "palette": "palettes/builders.gpl",
    "face": {
        "eye_v": 0.40, "eye_u": 0.18, "eye_w": 0.22, "eye_h": 0.225,
        "iris_w": 0.155, "iris_h": 0.19, "iris_cover": 0.20, "look": (-0.010, 0.006),
        "lid_cut": 0.16, "lid_w": 0.032, "lid_flick": 0.010,
        "brow_up": 0.088, "brow_len": 0.16, "brow_w": 0.036,
        "brow_tilt": 4.0, "brow_raise": 0.006, "brow_arch": 0.014,
        "nose": (0.070, 0.050, 0.026), "nose_v": 0.29,
        "mouth": "smile", "mouth_v": 0.226, "mouth_w": 0.15,
        "blush": (0.12, 0.06), "blush_u": 0.29, "blush_v": 0.235,
        "iris": C["iris"], "brow": C["hair"],
    },
}

fig = chibi.Figure(SPEC)
H, W, HC, R = fig.H, fig.W, fig.HC, fig.R
# the head tips up a little toward the smoke on her right; planned first, so the veil
# can be built to hang clear of her shoulders in the pose
NECK = Vector((0.0, 0.028, fig.chin + 0.020))
HEAD_TURN = rot(z=-6) @ rot(x=-6)
fig.plan_head(NECK, HEAD_TURN)

# ── 1, 2: head and face ──
head = fig.head()
fig.face()

# ── 3: hair: a dark cap, a fringe parted to her left, two locks framing the face ──


def hairline(a):
    return lerp(lerp(42.0, -18.0, smoothstep(26.0, 74.0, a)), -48.0, smoothstep(100.0, 175.0, a))


cap = fig.cap(hairline, C["hair"])
locks = []
for k, (a0, a1, w) in enumerate(((-26, -36, 0.22), (2, 10, 0.22), (28, 36, 0.19))):
    locks.append(fig.lock(f"fringe_{k}", [fig.dir(a0 * 0.8, 66), fig.dir(a0 * 0.95, 56), fig.dir(lerp(a0, a1, 0.4), 46),
                                          fig.dir(lerp(a0, a1, 0.8), 39), fig.dir(a1, 33.5)],
                          [w * W, w * W, w * 0.95 * W, w * 0.6 * W, 0.0], 0.05 * W, C["hair"], lift=1.075))
for side in (-1, 1):
    locks.append(fig.lock(f"side_lock_{side}", [fig.dir(side * 66, 30), fig.dir(side * 71, 14), fig.dir(side * 72, -2),
                                                fig.dir(side * 70, -16), fig.dir(side * 64, -26)],
                          [0.15 * W, 0.15 * W, 0.13 * W, 0.09 * W, 0.0], 0.07 * W, C["hair"], lift=1.06))

# ── 4: the straw sun hat: a low flat crown with an indigo band and a wide brim that
#       droops softly all round, tipped back 6 degrees ──
HAT_BASE = HC + Vector((0.0, 0.012, 0.066))
R_IN = 0.166
R_OUT = (0.86 if BUST else 1.0) * W
TILT = chibi.about(HAT_BASE, rot(x=-6, y=2))


def brim_lift(th, r_share):
    front = max(0.0, -math.sin(th))
    return (0.010 * front - 0.030 - 0.012 * math.cos(th) ** 2) * r_share ** 2


hat = fig.hat(HAT_BASE, [(0.000, 1.00), (0.050, 1.00), (0.092, 0.975), (0.112, 0.90), (0.122, 0.62), (0.126, 0.0)],
              R_IN, C["straw"], band=C["indigo"], segs=18, brim=[(0.00, 0.006), (0.94, 0.003), (0.97, -0.010)],
              r_out=R_OUT, brim_lift=brim_lift, brim_segs=32, tilt=TILT)

# ── 5: the veil: hung from under the brim round the sides and back down to her shoulders,
#       its lower edge rising at the front to the brim, so her face shows; a darker inside;
#       the rolled-up front lies on the brim as a fat cream roll ──
to_rest = fig.head_plan.inverted()
N_V = 20
ROWS = [0.0, 0.3, 0.62, 1.0]
SHOULDER_Z = 0.600


def veil_point(th, u, inner=False):
    """The veil at ring angle th (-90 degrees the front) and share u from the brim down."""
    front = smoothstep(0.30, 0.82, -math.sin(th))
    top_r = 0.74 * R_OUT
    p_top = HAT_BASE + Vector((math.cos(th) * top_r, math.sin(th) * top_r * 0.94, brim_lift(th, 0.74) - 0.004))
    p_top = TILT @ p_top
    # where the lower edge hangs in the posed body, brought back to the head's rest frame
    bottom_r = (0.64 + 0.045 * math.cos(7 * th)) * R_OUT
    p_bot_posed = Vector((math.cos(th) * bottom_r, 0.020 + math.sin(th) * bottom_r * 0.94, SHOULDER_Z))
    p_bot = to_rest @ p_bot_posed
    edge = lerp(1.0, 0.06, front)       # how far down the veil hangs at th
    p = p_top.lerp(p_bot, u * edge)
    if inner:
        c = Vector((HC.x, HC.y, p.z))
        p = c + (p - c) * 0.975
    return p


for inner in (False, True):
    rings_v = [[veil_point(2 * math.pi * k / N_V, u, inner) for k in range(N_V)] for u in ROWS]
    veil = chibi.loft("veil_in" if inner else "veil", rings_v)
    if inner:
        for poly in veil.data.polygons:
            poly.flip()
        veil.data.update()
    fig.add(veil, "veil", C["veil_in"] if inner else C["veil"], smooth=70, head=True)
roll_pts = []
for k in range(9):
    th = math.radians(-90.0 - 62.0 + 124.0 * k / 8)
    r_ = 0.80 * R_OUT
    roll_pts.append(TILT @ (HAT_BASE + Vector((math.cos(th) * r_, math.sin(th) * r_ * 0.94,
                                               brim_lift(th, 0.80) + 0.020))))
roll = chibi.tube("veil_roll", roll_pts, [0.0] + [0.020] * 7 + [0.0], sides=6)
fig.add(roll, "veil", C["veil"], head=True)

# hidden faces: the skull under the cap, the hair under the hat


def hidden_skin(co, margin=3.0):
    a, lat = fig.angles(co)
    return lat > hairline(a) + margin or lat < (-74.0 if a < 50.0 else -64.0)


chibi.cull(head, hidden_skin)
for obj in [cap] + locks:
    chibi.cull(obj, lambda co: hat.covers(co, 0.012))

# ── 6: the tunic: a slim terracotta bell to mid-shin, an indigo hem band; the sash at the
#       waist, knotted at her left hip, two tails hanging ──
HEM = 0.50 * H
TUNIC = [(HEM, 0.152, 0.138, 0.0), (0.220, 0.142, 0.128, 0.0), (0.300, 0.126, 0.114, 0.0),
         (0.380, 0.114, 0.103, 0.0), (0.440, 0.106, 0.096, 0.004), (0.500, 0.082, 0.076, 0.006),
         (0.548, 0.060, 0.056, 0.008)]
fig.bell(TUNIC, C["tunic"], C["indigo"], 0.034, waves=3, wave_amp=0.022, front_rise=0.024, segs=16)
fig.neck(0.050, 0.500, taper=1.2)
SASH_Z = 0.340
sash_pts = [Vector((0.124 * math.cos(2 * math.pi * k / 14), 0.112 * math.sin(2 * math.pi * k / 14), SASH_Z))
            for k in range(14)]
sash = chibi.tube("sash", sash_pts, [(0.010, 0.022)] * 14, sides=4, up=Z, closed=True)
fig.add(sash, "sash", C["indigo"])
knot_at = Vector((0.104, -0.070, SASH_Z))
knot = chibi.blob("sash_knot", knot_at, (0.024, 0.020, 0.024), segs=7, rows=4)
fig.add(knot, "sash", C["indigo"])
for k, (dx, ang) in enumerate(((0.012, 14.0), (-0.010, -8.0))):
    tail = chibi.teardrop(f"sash_tail_{k}", knot_at + Vector((dx, -0.008, -0.008)),
                          Vector((0.30 + math.sin(math.radians(ang)), -0.30, -1.0)), 0.110, 0.034, 0.010, X,
                          taper=0.4, segs=4, rows=4, cage=False)
    fig.add(tail, "sash", C["indigo"])

# ── 7 to 10: arms and long canvas gloves: the right forearm forward, the smoker's bellows
#            in its fist; the left fist on her hip ──
if BUST:   # the smoker comes up beside her jaw, inside the portrait arch
    GRIP, SS = Vector((-0.150, -0.110, 0.520)), 0.80
else:
    GRIP, SS = Vector((-0.176, -0.116, 0.430)), 1.00
ARMS = {
    -1: [(-0.098, 0.0, 0.500), (-0.196, 0.030, 0.420), GRIP + Vector((0.020, 0.040, -0.006))],
    1: [(0.098, 0.0, 0.500), (0.212, 0.030, 0.404), (0.156, -0.022, 0.338)],
}
for side, pts in ARMS.items():
    fig.arm(side, pts, 0.040, C["tunic"], C["glove"], cuff_len=0.034)
fig.mitten(-1, GRIP, fingers=(-0.2, -1.0, -0.1), back=(0.6, 0.3, 0.6), size=(0.066, 0.058, 0.080),
           colour=C["glove"], curl=0.1)
fig.mitten(1, (0.152, -0.030, 0.328), fingers=(-0.3, -0.5, -1.0), back=(1.0, 0.0, 0.2),
           size=(0.066, 0.056, 0.078), colour=C["glove"])

# ── 11, 12: tall soft boots with round toes; her weight on her right ──
for side in (-1, 1):
    fig.boot(side, (0.062 * side, -0.016 if side < 0 else -0.032, 0.0), 14 * side, 0.150, 0.48 * H, 0.104,
             C["boot"], C["boot"], C["boot_sole"], cuff_h=0.022, sole_h=0.014, toe=0.70, toe_h=0.50, shin=0.36,
             flare=1.20)

# ── 13: the smoker, built round the grip: the bellows (two wooden boards over a leather
#        fold) in her fist, the tin canister outboard of it, the lid's spout bent up and
#        out, and three puffs of smoke rising from it ──
prop = []
CAN = GRIP + Vector((-0.078, 0.004, 0.006)) * SS
CAN_R, CAN_H = 0.054 * SS, 0.150 * SS
can = chibi.tube("smoker_can", [CAN - Z * CAN_H * 0.5, CAN - Z * CAN_H * 0.40, CAN + Z * CAN_H * 0.40,
                                CAN + Z * CAN_H * 0.5],
                 [CAN_R * 0.94, CAN_R, CAN_R, CAN_R * 0.96], sides=10)
prop.append(fig.add(can, "prop", lambda c, i: (C["tin_dark"], CLOTH) if abs(c.z - CAN.z) > CAN_H * 0.40
                    else (C["tin"], CLOTH), smooth=50))
LID = CAN + Z * CAN_H * 0.5
lid = chibi.blob("smoker_lid", LID, (CAN_R * 1.02, CAN_R * 1.02, 0.030 * SS), segs=10, rows=4,
                 shape=lambda d: 1.0 if d.z >= 0 else 0.0001)
prop.append(fig.add(lid, "prop", C["tin_dark"]))
spout_dir = Vector((-0.55, -0.15, 1.0)).normalized()
spout_root = LID + Z * 0.016 * SS + X * -0.010 * SS
spout = chibi.tube("smoker_spout", [spout_root, spout_root + spout_dir * 0.050 * SS],
                   [0.024 * SS, 0.010 * SS], sides=8)
prop.append(fig.add(spout, "prop", C["tin"], smooth=50))
tip = spout_root + spout_dir * 0.050 * SS
for k, (dist, r_) in enumerate(((0.040, 0.024), (0.092, 0.031), (0.152, 0.036))):
    c = tip + spout_dir * dist * SS + Vector((-0.010 * k, 0.0, 0.0)) * SS
    puff = chibi.blob(f"smoke_{k}", c, (r_ * SS, r_ * SS * 0.92, r_ * SS * 0.86), segs=7, rows=4)
    prop.append(fig.add(puff, "prop", C["smoke"]))
BELLOWS = GRIP + Vector((-0.010, -0.002, -0.030)) * SS
for k, (dx, tilt) in enumerate(((-0.017, 3.0), (0.017, -12.0))):
    board = chibi.blob(f"bellows_board_{k}", BELLOWS + Vector((dx, 0.0, 0.0)) * SS,
                       (0.008 * SS, 0.036 * SS, 0.078 * SS), segs=6, rows=4, power=3.0,
                       rot=rot(y=tilt))
    prop.append(fig.add(board, "prop", C["bellows"]))
fold = chibi.blob("bellows_fold", BELLOWS + Vector((0.0, 0.0, -0.006)) * SS, (0.016 * SS, 0.031 * SS, 0.064 * SS),
                  segs=6, rows=4)
prop.append(fig.add(fold, "prop", C["leather"]))
if BUST:   # in the bust, lean the smoker out a little so its smoke rises clear of the brim
    fig.pose(prop, chibi.about(GRIP, rot(y=12.0)))


# ── 14: two bees in the air by her hat ──
def bee(name, at, heading, size):
    """A round bee: a striped body (two dark bands), a dark head, two pale wings."""
    d = Vector(heading).normalized()
    side = d.cross(Z).normalized()
    up = side.cross(d).normalized()
    basis = Matrix((side, up, d)).transposed()
    body = chibi.blob(f"{name}_body", at, (size, size * 0.92, size * 1.35), segs=7, rows=5, rot=basis)

    def stripes(c, i):
        t = (c - Vector(at)).dot(d) / (size * 1.35)
        return (C["bee_dark"], CLOTH) if -0.55 < t < -0.15 or 0.15 < t < 0.45 else (C["bee"], CLOTH)

    parts = [fig.add(body, "bee", stripes)]
    head_ = chibi.blob(f"{name}_head", Vector(at) + d * size * 1.45, (size * 0.62,) * 3, segs=5, rows=3)
    parts.append(fig.add(head_, "bee", C["bee_dark"]))
    for s in (-1, 1):
        wing = chibi.blob(f"{name}_wing_{s}", Vector(at) + up * size * 1.05 + side * s * size * 0.55 - d * size * 0.2,
                          (size * 0.70, size * 0.16, size * 0.95), segs=5, rows=3,
                          rot=basis @ rot(y=s * 28.0, x=-20.0))
        parts.append(fig.add(wing, "bee", C["wing"]))
    return parts


if not BUST:   # (the bust keeps its triangles for the face; the smoke says enough there)
    bee("bee_0", Vector((0.262, -0.080, 0.700)), (-0.6, -1.0, 0.1), 0.019)
    bee("bee_1", Vector((-0.300, -0.030, 0.800)), (0.8, -0.7, -0.2), 0.016)

# ── Pose: the head as planned; the body leans onto her right leg ──
fig.pose_head()
LEAN = chibi.about((0, 0, 0), rot(y=-3.0))
hand = (LEAN @ GRIP) - GRIP
fig.pose(fig.everything(but=("boot", "prop", "bee")), LEAN)
fig.pose([o for o, p in fig.parts if p == "prop"], Matrix.Translation(hand))

fig.finish("beekeeper_bust" if BUST else "beekeeper", bust_cut=0.34 if BUST else None,
           check=bool(int(gab.param("check", 0))))
