"""Tamsin Wick, the Lamplighter of Wickhollow, as a chibi Builder.

    godot-agent asset blender . art_src/blender/builders/lamplighter.py \\
        --to res://models/builders/lamplighter.glb --seed 1 --review
    godot-agent asset blender . art_src/blender/builders/lamplighter.py \\
        --to res://models/builders/lamplighter_bust.glb --seed 1 --param bust=1

A broad, cheerful little lamplighter, 2.6 heads tall and shaped like a pear: a round
cranberry oilskin coat over chunky round-toed boots, a fat mustard scarf high round her
neck with one tail, leather mittens, a big chestnut slouch hat (a low, round crown, the
brim rolled up at the front and drooping at the sides) with a pumpkin band and an autumn
sprig, a copper braid of five round lobes over her right shoulder, and the lamp pole in
her right mitten, its small amber lantern under a dark brass roof. Weight on her left
leg, left fist on her hip, head tipped up toward the lamp.

Params: bust=1 (the portrait and icon model: cut above the hem, the pole leaning back and
its crook reaching forward, so a smaller lantern hangs beside her jaw and stays inside the
portrait arch as she turns), check=1 (fail when over budget), lamp (glass colour).
The body plan, face, hat and finishing are the kit's character helpers (chibi, gab).
"""

import math

from mathutils import Matrix, Vector

import chibi
import gab
from chibi import CLOTH, FWD, X, Y, Z, lerp, ring, rot, smoothstep

BUST = bool(int(gab.param("bust", 0)))

C = {
    "coat": "#b3313f", "mustard": "#e0a030", "felt": "#6e4430", "band": "#e8692a",
    "leaf_rust": "#d0502a", "leaf_gold": "#f0b440", "hair": "#b4481f", "brow": "#7a2c14",
    "skin": "#ebb48e", "blush": "#ef8f84", "iris": "#4a2410", "mitten": "#8b5a3a",
    "boot": "#4a2c22", "boot_band": "#7a5234", "wood": "#7a4a30", "brass": "#d6a23c",
    "brass_light": "#f2c868", "brass_dark": "#8a5e22", "lamp": "#ffa63c",
}

SPEC = {
    "H": 0.32, "heads": 2.6, "chin_out": 0.26, "skin": C["skin"], "blush": C["blush"],
    "material": "builder_toon", "palette": "palettes/builders.gpl",
    "face": {
        "eye_v": 0.40, "eye_u": 0.18, "eye_w": 0.22, "eye_h": 0.235,
        "iris_w": 0.16, "iris_h": 0.20, "iris_cover": 0.17, "look": (0.0, 0.0),
        "lid_cut": 0.12, "lid_w": 0.030, "lid_flick": 0.004,
        "brow_up": 0.085, "brow_len": 0.17, "brow_w": 0.040,
        "brow_tilt": 9.0, "brow_raise": 0.010, "brow_arch": 0.012,
        "nose": (0.075, 0.055, 0.028), "nose_v": 0.29,
        "mouth": "grin", "mouth_v": 0.228, "mouth_w": 0.15, "mouth_depth": 0.065,
        "blush": (0.13, 0.07), "blush_u": 0.29, "blush_v": 0.24,
        "iris": C["iris"], "brow": C["brow"],
    },
}

fig = chibi.Figure(SPEC)
H, W, HC, R = fig.H, fig.W, fig.HC, fig.R

# ── 1, 2: head and face ──
head = fig.head()
fig.face()

# ── 3: hair: a cap, four fringe clumps, two side locks (the braid comes after the pose) ──


def hairline(a):
    """Latitude of the hair's edge, a degrees round from the front."""
    return lerp(lerp(38.0, -24.0, smoothstep(26.0, 74.0, a)), -52.0, smoothstep(100.0, 175.0, a))


cap = fig.cap(hairline, C["hair"])
locks = []
for k, (a0, a1, w) in enumerate(((-32, -40, 0.21), (-4, -8, 0.23), (26, 32, 0.21))):
    locks.append(fig.lock(f"fringe_{k}", [fig.dir(a0 * 0.8, 66), fig.dir(a0 * 0.95, 55), fig.dir(lerp(a0, a1, 0.4), 45),
                                          fig.dir(lerp(a0, a1, 0.8), 38), fig.dir(a1, 32.5)],
                          [w * W, w * W, w * 0.95 * W, w * 0.62 * W, 0.0], 0.05 * W, C["hair"], lift=1.075))
for side in (-1, 1):
    locks.append(fig.lock(f"side_lock_{side}", [fig.dir(side * 70, 26), fig.dir(side * 74, 8), fig.dir(side * 74, -10),
                                                fig.dir(side * 70, -27), fig.dir(side * 62, -40)],
                          [0.13 * W, 0.13 * W, 0.115 * W, 0.08 * W, 0.0], 0.06 * W, C["hair"], lift=1.06))

# ── 4: the slouch hat: a low, round crown (one smooth surface, so the terminator crossing
#       it stays one clean edge), a pumpkin band, a wide brim rolled up at the front and
#       drooping at the sides, all tipped back 15 degrees; one three-leaf autumn sprig in
#       the band on her left ──
HAT_BASE = HC + Vector((0.0, 0.010, 0.074))
R_IN = 0.170


def brim_lift(th, r_share):
    """Rolled up at the front, drooping at the sides, a little down at the back."""
    front = max(0.0, -math.sin(th))
    back = max(0.0, math.sin(th))
    side = math.cos(th) ** 2
    return (0.052 * front ** 1.6 - 0.024 * side - 0.008 * back) * r_share ** 1.8


hat = fig.hat(HAT_BASE, [(0.000, 1.00), (0.042, 1.00), (0.100, 0.970), (0.138, 0.90), (0.160, 0.72), (0.174, 0.0)],
              R_IN, C["felt"], band=C["band"], segs=20, lean=lambda h: 0.02 * (h / 0.2) ** 2,
              brim=[(0.00, 0.006), (0.94, 0.003), (0.97, -0.010)], r_out=0.78 * W, brim_lift=brim_lift, brim_segs=36,
              tilt=chibi.about(HAT_BASE, rot(x=-15, y=4)))

# the sprig: three broad leaves fanned up and out of the band on her left
for k, (yaw, pitch, length, colour) in enumerate(((22, 50, 0.104, "leaf_rust"), (-4, 68, 0.118, "leaf_gold"),
                                                  (48, 30, 0.090, "leaf_rust"))):
    root = HAT_BASE + Vector((R_IN * 0.96, -0.030 + 0.022 * k, 0.024))
    d = rot(z=yaw) @ rot(y=-pitch) @ X
    d = (d + Vector((0, 0.15, 0))).normalized()
    c = root + d * length * 0.5
    leaf = chibi.blob(f"leaf_{k}", c, (0.011, 0.036, length / 2), segs=6, rows=3,
                      shape=lambda dd: (1.0, 1.0 - 0.6 * abs(dd.z) ** 1.6, 1.0),
                      rot=Matrix((d.cross(Y).normalized(), d.cross(Y).normalized().cross(d), d)).transposed())
    chibi.transform(leaf, hat.tilt)
    fig.add(leaf, "hat", C[colour], head=True)

# hidden faces: the skull under the cap, the hair under the hat


def hidden_skin(co, margin=3.0):
    """Under the hair cap (which tucks in 3 degrees below the hairline), or under the jaw,
    inside the neck (at the sides and back) and the scarf."""
    a, lat = fig.angles(co)
    return lat > hairline(a) + margin or lat < (-74.0 if a < 50.0 else -64.0)


chibi.cull(head, hidden_skin)
for obj in [cap] + locks:
    chibi.cull(obj, lambda co: hat.covers(co, 0.010))

# ── 5: the coat bell: cranberry with a mustard hem band; its top ends inside the scarf ──
HEM = 0.30 * H
fig.bell([(HEM, 0.200, 0.182, 0.0), (0.180, 0.198, 0.178, 0.0), (0.265, 0.184, 0.164, 0.0),
          (0.350, 0.164, 0.146, 0.0), (0.420, 0.148, 0.130, 0.004), (0.480, 0.100, 0.092, 0.008)],
         C["coat"], C["mustard"], 0.032, waves=4, wave_amp=0.035,
         front_rise=0.040, segs=20)
fig.neck(0.056, 0.452, taper=1.2)

# ── 6: the scarf: a fat ring close round the neck, high enough that little neck shows and
#       no coat shows inside it, and one tail down her front ──
sc_c = Vector((0.0, 0.004, 0.493))
sc_rings = [sc_c + Vector((0.100 * math.cos(th), 0.092 * math.sin(th), 0.0)) for th in [2 * math.pi * k / 16 for k in range(16)]]
scarf = chibi.tube("scarf", sc_rings, [(0.036, 0.030)] * 16, sides=6, up=Z, closed=True)
fig.add(scarf, "scarf", C["mustard"])
tail = chibi.tube("scarf_tail", chibi.catmull([Vector((0.046, -0.112, 0.488)), Vector((0.064, -0.152, 0.424)),
                                               Vector((0.072, -0.166, 0.350)), Vector((0.076, -0.174, 0.290))], 2),
                  [(0.030, 0.013)] * 6 + [(0.028, 0.013)], sides=4, up=FWD)
fig.add(tail, "scarf", C["mustard"])

# ── 7 to 10: arms and mittens ──
if BUST:   # the pole hand comes in; the pole leans back and the crook reaches forward, so a
    #        smaller lantern hangs beside her jaw, inside the portrait arch at every turn
    PX, PY, GRIP, PTOP, LS = -0.225, -0.030, 0.350, 0.655, 0.80
else:
    PX, PY, GRIP, PTOP, LS = -0.268, -0.056, 0.340, 1.330, 1.00
ARMS = {
    -1: [(-0.118, 0.0, 0.440), (-0.200, 0.014, 0.372), (PX + 0.026, PY + 0.010, GRIP + 0.004)],
    1: [(0.118, 0.0, 0.440), (0.236, 0.040, 0.338), (0.196, -0.026, 0.262)],
}
for side, pts in ARMS.items():
    fig.arm(side, pts, 0.044, C["coat"], C["mustard"], cuff_len=0.022)
fig.mitten(-1, (PX + 0.004, PY - 0.004, GRIP), fingers=(0.25, -1.0, 0.0), back=(-1.0, 0.0, 0.2),
           size=(0.072, 0.064, 0.086), colour=C["mitten"], curl=0.1)
fig.mitten(1, (0.190, -0.034, 0.250), fingers=(-0.3, -0.5, -1.0), back=(1.0, 0.0, 0.2),
           size=(0.074, 0.060, 0.082), colour=C["mitten"])

# ── 11, 12: boots with round toes under the hem, toes out, her weight on her left ──
for side in (-1, 1):
    fig.boot(side, (0.078 * side, -0.050 if side < 0 else -0.030, 0.0), 15 * side, 0.118, 0.42 * H, 0.094,
             C["boot"], C["boot_band"], C["boot_band"], cuff_h=0.026, sole_h=0.016, toe=0.66, toe_h=0.50, shin=0.42)

# ── 13: the lamp pole, its brass crook and the lantern, built upright with the crook
#        reaching out to her right ──
pole = chibi.tube("pole", [(PX, PY, 0.0), (PX, PY, 0.040), (PX, PY, PTOP - 0.050), (PX, PY, PTOP)],
                  [0.017, 0.017, 0.016, 0.016], sides=8)
fig.add(pole, "prop", lambda c, i: (C["brass"], CLOTH) if c.z < 0.040 or c.z > PTOP - 0.050 else (C["wood"], CLOTH),
        smooth=50)
REACH = 0.140
crook_pts = chibi.catmull([(PX, PY, PTOP - 0.02), (PX - 0.022, PY, PTOP + 0.078), (PX - REACH + 0.014, PY, PTOP + 0.072),
                           (PX - REACH, PY, PTOP + 0.022)], 2)
crook = chibi.tube("crook", crook_pts, [0.0140] * len(crook_pts), sides=6)
tip = crook_pts[-1]
fig.add(crook, "prop", lambda c, i: (C["brass_light"], CLOTH) if c.z < tip.z + 0.012 and c.x < PX - REACH + 0.03
        else (C["brass"], CLOTH), smooth=50)
LX, LY = PX - REACH, PY
hook = chibi.tube("lamp_hook", [Vector((LX + math.sin(a) * 0.014, LY, PTOP + 0.002 + math.cos(a) * 0.014))
                                for a in [math.radians(v) for v in range(0, 360, 90)]], [0.005] * 4, sides=3,
                  up=Y, closed=True)
fig.add(hook, "prop", C["brass"])
pole_parts = [pole, crook, hook]
lantern = []
GH, GW = 0.124 * LS, 0.060 * LS   # glass height, half width: the lantern is about 0.6 W (0.5 W in the bust)
ROOF_TOP = PTOP - 0.012
EAVE = ROOF_TOP - 0.064 * LS
BASE = EAVE - GH
# a dark brass pyramid roof that reads from above, over amber glass in dark bars
roof = chibi.tube("lamp_roof", [(LX, LY, EAVE - 0.004 * LS), (LX, LY, EAVE + 0.010 * LS), (LX, LY, EAVE + 0.030 * LS),
                                (LX, LY, ROOF_TOP)], [GW * 1.86, GW * 1.80, GW * 1.06, 0.0], sides=4)
chibi.transform(roof, chibi.about((LX, LY, 0), rot(z=45)))
lantern.append(fig.add(roof, "prop", C["brass_dark"], smooth=40))
knob = chibi.blob("lamp_knob", (LX, LY, ROOF_TOP + 0.004), (0.014, 0.014, 0.012), segs=6, rows=3)
lantern.append(fig.add(knob, "prop", C["brass"]))
LAMP = gab.glow("lamp_glow", gab.param("lamp", C["lamp"]), 0.9, base=0.35)   # amber glass, even in sun
glass = chibi.loft("lamp_glass", [ring((LX, LY, BASE), GW * 1.414, GW * 1.414, 4, phase=math.pi / 4),
                                  ring((LX, LY, EAVE), GW * 1.414, GW * 1.414, 4, phase=math.pi / 4)],
                   cap0=True, cap1=True)
lantern.append(fig.add(glass, "prop", C["lamp"], smooth=None, mat=LAMP))
for sx in (-1, 1):
    for sy in (-1, 1):
        post = chibi.tube(f"lamp_post_{sx}{sy}", [(LX + sx * GW, LY + sy * GW, BASE), (LX + sx * GW, LY + sy * GW, EAVE)],
                          [0.012 * LS, 0.012 * LS], sides=4, cap0=False, cap1=False)
        lantern.append(fig.add(post, "prop", C["brass_dark"], smooth=40))
base = chibi.tube("lamp_base", [(LX, LY, BASE - 0.022 * LS), (LX, LY, BASE - 0.008 * LS), (LX, LY, BASE + 0.004 * LS)],
                  [GW * 1.30, GW * 1.66, GW * 1.66], sides=4)
chibi.transform(base, chibi.about((LX, LY, 0), rot(z=45)))
lantern.append(fig.add(base, "prop", C["brass_dark"], smooth=40))
if BUST:   # swing the crook round to reach forward, lean the pole back about the grip; the
    #        lantern still hangs straight down from the hook
    hang = Vector((LX, LY, PTOP + 0.002))
    tilt = chibi.about((PX, PY, GRIP), Matrix.Rotation(math.radians(-20), 3, "X") @ Matrix.Rotation(math.radians(90), 3, "Z"))
    fig.pose(pole_parts, tilt)
    fig.pose(lantern, Matrix.Translation(tilt @ hang - hang))

# ── Pose: the head tips up and toward the lamp; the body leans onto her left leg ──
NECK = Vector((0.0, 0.030, fig.chin + 0.020))
fig.pose(fig.head_group, chibi.about(NECK, rot(z=-7) @ rot(x=-10)))

# the braid, from behind her right ear over her right shoulder: five smooth round lobes,
# smaller toward the end, a mustard tie and a little brush of hair below it
root = fig.head_matrix @ fig.head_point(fig.dir(-112, -14), 1.0)
path = chibi.catmull([root, Vector((-0.172, -0.014, 0.514)), Vector((-0.160, -0.104, 0.452)),
                      Vector((-0.134, -0.154, 0.390)), Vector((-0.118, -0.170, 0.330))], 4)
braid = chibi.lobes("braid", path, [0.038, 0.036, 0.034, 0.031, 0.027], stretch=1.32, segs=8, rows=4)
fig.add(braid, "braid", C["hair"])
end, d_end = path[-1], (path[-1] - path[-2]).normalized()
tie = chibi.tube("braid_tie", [end - d_end * 0.002, end + d_end * 0.014], [0.021, 0.021], sides=6)
fig.add(tie, "braid", C["mustard"])
tuft = chibi.blob("braid_tuft", end + d_end * 0.032, (0.019, 0.017, 0.022), segs=6, rows=3)
fig.add(tuft, "braid", C["hair"])

LEAN = chibi.about((0, 0, 0), rot(y=3.5))
hand = (LEAN @ Vector((PX, PY, GRIP))) - Vector((PX, PY, GRIP))
body = fig.everything(but=("boot", "prop"))
fig.pose(body, LEAN)
fig.pose([o for o, p in fig.parts if p == "prop"], Matrix.Translation((hand.x, 0.0, 0.0)))

fig.finish("lamplighter_bust" if BUST else "lamplighter", bust_cut=0.30 if BUST else None,
           check=bool(int(gab.param("check", 0))))
