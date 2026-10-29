"""Pine: a tall, narrow, tiered evergreen for Lantern Hollow's forests and high ground.

Build (seeds 1, 2, 3 are the three shipped variants):
    godot-agent asset blender . art_src/blender/pine.py --to res://models/vegetation/tree_pine_1.glb \
        --seed 1 --review --no-import

Read from the game's 56 degree camera first, the turntable second:
- A narrow cone that ends in a lit, pointed spire, taller than the broadleaf trees so pines stand
  out of mixed woods as spires.
- 6-8 tiers of boughs with a flat shoulder that turns down into a skirt. A bough is one large,
  convex foliage_pine card (lit spine, edges rolling down) and one side card tenting over it; a
  short, upswept inner layer fills the gap between tiers near the trunk, the lowest tiers get an
  under card. Few, large cards keep the needle texture big enough to read as clumps.
- Light comes from the normals as much as from the tint: a bough's normals point up on its
  shoulder and out along its hanging rim, so every tier has a lit top and a darker drop. The tint
  runs from a cool, saturated blue-green inside to bright yellow-green tips high on the tree, and
  each tier turns toward a deep teal (not black) in a band below the rim of the tier above, so
  shadows stay coloured under the warm sun, the cool ambient and the warm haze.
- The tint is capped so that card texel x tint x tint_boost x top_light never clips: the tips
  keep their needle detail instead of turning flat chartreuse.
- The spire is a short leader: a closed, three-sided sheath of cards (every face is a front face,
  so none renders dark from behind) above three small whorls.
- The crown starts high enough that the camera sees the trunk base past the lowest tier: a
  reddish-brown trunk on seven rounded root buttresses that dive into the soil, moss or dirt at
  the ground line, bark ridges with dark crevices, and two or three short, tapered dead stubs
  growing out of bark collars.
- Everything inside the crown (dark interior cones, the upper trunk) uses the foliage material
  mapped to one opaque texel, so it sways with the cards instead of sliding behind them.
- COLOR.a of the crown carries a flutter weight, 0 at a bough's root and 1 at its tip (the
  foliage shader does not read the pattern alpha), for a per-vertex flutter term in the shader.

Per seed: a habit (1 classic, 2 tall slender spruce, 3 short and full) with its own height,
width, cone profile, lean, hue and a signature: seed 1 a lopsided crown, short on the side away
from its lean; seed 2 a bluer spruce with a small secondary leader; seed 3 a warmer, leaning tree
with one mid tier dented on one side.

Params:
    height   override the total height in units
    whorls   override the whorl count
    only     preview only: "trunk" keeps just the trunk and stubs below the crown
    flat     preview only: 1 maps every card to one solid texel, to inspect the tints alone
"""

import colorsys
import math

import bpy
from mathutils import Vector

import gab

R = gab.rng
SEED = gab.seed

# ── Palette (palettes/hollow.gpl) ──
BARK = "#5b3a29"
WOOD = "#7a5534"
WOOD_DARK = "#4e3423"
PUMPKIN_DARK = "#a8521e"
STONE_WARM = "#9a948a"
STONE_SHADOW = "#6b665f"
NEEDLE = "#2f5f3e"         # moss at the ground line

# Foliage tints (multiplied by the grey card; not palette-checked).
TINT_DEEP = "#0f3e34"      # cool, dark blue-green deep inside the crown
TINT_MID = "#1c5e48"
TINT_LIGHT = "#5c9a3c"     # lit rims on the upper tiers
TINT_LIGHT_LOW = "#2e7a56" # lit rims low on the tree: a cool forest green, so the camera-facing
                           # skirts of the lower tiers stay blue-green under the warm sun
TINT_TIP = "#a9c95a"       # warm yellow-green tips, high on the tree only
TINT_SHADOW = "#0d3a33"    # what a tier turns toward under the rim of the tier above

# The foliage shader multiplies texel x tint x tint_boost (1.45) x top light (up to 1.25); the
# brightest tip texels are about 0.95. Keeping every tint channel under this cap means no albedo
# ever clamps, so lit tips keep their needles.
TINT_CAP = 1.0 / (0.95 * 1.45 * 1.25)
# One opaque, mid-grey texel on the bough's stem (linear grey about 0.175): interior cones and
# the upper trunk sample only this texel, so they render solid with the swaying foliage shader.
SOLID_UV = (0.502, 0.502)
SOLID_TEXEL = 0.175 * 1.45

BARK_A = (gab.PATTERNS.index("bark") + 0.5) / 16

# Habits: height, whorls, crown radius, lowest bough tip, lean, cone profile exponent, hue, saturation,
# bough droop (share of the bough length, bottom tier to top tier)
HABITS = [
    ((2.30, 2.42), (7, 7), (0.43, 0.46), (0.58, 0.62), (0.10, 0.16), 1.0, 0.0, 1.0, (0.45, 0.55)),      # classic
    ((2.55, 2.62), (8, 8), (0.42, 0.45), (0.74, 0.78), (0.06, 0.12), 1.2, 0.012, 0.9, (0.45, 0.55)),    # slender
    ((2.05, 2.15), (6, 6), (0.52, 0.55), (0.54, 0.58), (0.14, 0.22), 1.0, -0.015, 1.0, (0.3, 0.4)),    # short, full
]
HABIT = (SEED - 1) % len(HABITS)
habit = HABITS[HABIT]
HEIGHT = gab.param("height", R.uniform(*habit[0]))
WHORLS = gab.param("whorls", R.randint(*habit[1]))
CROWN_R = R.uniform(*habit[2])
LOW_TIP = R.uniform(*habit[3])     # no foliage below this: the camera sees the trunk base
LEAN = R.uniform(*habit[4])
PROFILE = habit[5]
LEAN_DIR = R.uniform(0, 2 * math.pi)
TRUNK_R = R.uniform(0.085, 0.1)
ONLY = gab.param("only", "")
FLAT = gab.param("flat", 0)          # preview only: 1 shows the card tints without the texture
# Bough shape: droop concentrated toward the tip (t ** CURL), so a tier is a flat shoulder that
# turns down into a skirt; boughs per tier, bottom to top. Lengths and droops vary only a little
# inside a tier, so its rim reads.
CURL = 2.6
DROOP_K = habit[8]
BOUGHS = (6.0, 4.5)
BOUGH_LEN = 1.1                      # main card length / crown radius
BOUGH_WIDTH = 1.15                   # main card width / crown radius
MAIN_ROWS = (0.0, 0.45, 0.72, 0.9, 1.0)   # a crisp kink between the shoulder and the skirt
LEADER = 0.34                        # spire above the top whorl
SHADOW_BAND = 0.16                   # how far below a tier's edge its shadow fades out
CROWN_TOP = HEIGHT - LEADER
CROWN_BASE = LOW_TIP + 0.17          # the lowest whorl's roots; its tips droop to LOW_TIP


def lin(c) -> Vector:
    return Vector(gab.rgb(c))


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def cap(c: Vector) -> Vector:
    m = max(c)
    return c * (TINT_CAP / m) if m > TINT_CAP else c


def axis(z: float) -> Vector:
    """The trunk's centre line: leans toward LEAN_DIR, more toward the top."""
    t = max(0.0, z) / HEIGHT
    off = LEAN * t * t
    return Vector((math.cos(LEAN_DIR) * off, math.sin(LEAN_DIR) * off, z))


def crown_radius(z: float) -> float:
    """A cone from the crown base to the very tip of the spire, its profile set by the habit."""
    t = (z - CROWN_BASE) / (HEIGHT - CROWN_BASE)
    return CROWN_R * max(0.0, 1.0 - t) ** PROFILE + 0.05


def frame(up: Vector):
    """Two unit vectors perpendicular to `up`, right-handed with it (e1 x e2 = up)."""
    ref = Vector((1, 0, 0)) if abs(up.x) < 0.9 else Vector((0, 1, 0))
    e1 = (ref - up * ref.dot(up)).normalized()
    return e1, up.cross(e1).normalized()


# ── Mesh accumulation ──

class Builder:
    """Vertices, faces, UVs, per-vertex colours (linear rgb + alpha) and optional per-vertex custom
    normals, turned into one object at the end."""

    def __init__(self):
        self.verts, self.faces, self.uvs, self.cols, self.norms = [], [], [], [], []

    def vert(self, co, color, alpha, normal=None) -> int:
        self.verts.append(Vector(co))
        self.cols.append((*color, alpha))
        self.norms.append(normal)
        return len(self.verts) - 1

    def face(self, idx, uvs):
        self.faces.append(tuple(idx))
        self.uvs.append(list(uvs))

    def tris(self) -> int:
        return sum(len(f) - 2 for f in self.faces)

    def build(self, name, mat, custom_normals=False, smooth_angle=None):
        obj = gab.mesh_object(name, self.verts, self.faces, self.uvs)
        mesh = obj.data
        layer = gab._color_layer(mesh)
        for poly in mesh.polygons:
            for li in poly.loop_indices:
                vi = mesh.loops[li].vertex_index
                c = self.cols[vi]
                layer.data[li].color = (min(1.0, c[0]), min(1.0, c[1]), min(1.0, c[2]), c[3])
        gab.assign(obj, mat)
        if custom_normals:
            for poly in mesh.polygons:
                poly.use_smooth = True
            normals = []
            for li in range(len(mesh.loops)):
                n = self.norms[mesh.loops[li].vertex_index]
                normals.append(tuple(n))
            mesh.normals_split_custom_set(normals)
        elif smooth_angle is not None:
            gab.smooth(obj, smooth_angle)
        mesh.update()
        return obj


# ── Colour ──

def shifted(c: str, hue_k: float = 1.0) -> Vector:
    """A tint moved to this habit's hue and saturation (slender is a cooler, greyer spruce)."""
    c = c.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    r, g, b = colorsys.hsv_to_rgb((h + HUE * hue_k) % 1.0, s * habit[7], v)
    return lin((round(r * 255), round(g * 255), round(b * 255)))


HUE = habit[6] + R.uniform(-0.006, 0.006)
DEEP, MID, LIGHT, LIGHT_LOW, SHADOW = (shifted(c) for c in (TINT_DEEP, TINT_MID, TINT_LIGHT, TINT_LIGHT_LOW,
                                                              TINT_SHADOW))
TIP = shifted(TINT_TIP, 1.0 if HUE > 0 else 0.4)    # a warm habit keeps its tips green, not straw


def height_light(h: float) -> float:
    """Darker low on the tree, lit at the top: 0.8 at the crown base, 1.15 at the spire."""
    return 0.8 + 0.35 * h


def needle_tint(t: float, h: float, shade: float) -> Vector:
    """t: 0 at the bough's root, 1 at its tip; h: 0 at the crown base, 1 at the top.
    The bright TIP colour only on the upper tiers."""
    light = lerp(LIGHT_LOW, LIGHT, smoothstep(0.3, 0.75, h))     # cool low, warm high
    if t < 0.7:
        c = lerp(DEEP, MID, smoothstep(0.15, 0.7, t))
    elif t < 0.86:
        c = lerp(MID, light, smoothstep(0.7, 0.86, t))
    else:
        c = lerp(light, TIP, smoothstep(0.86, 1.0, t) * smoothstep(0.25, 0.6, h))
    return c * height_light(h) * shade


def crown_h(z: float) -> float:
    return max(0.0, min(1.0, (z - CROWN_BASE) / (HEIGHT - CROWN_BASE)))


# ── Trunk ──

BARK_U = 0.3      # metres of bark pattern around the trunk: a few broad streaks per ridge


def trunk_radius(z: float) -> float:
    return TRUNK_R * max(0.0, 1.0 - z / CROWN_TOP) ** 0.9 + 0.014


def build_trunk(b: Builder, solid: Builder):
    """The bark-covered trunk below the crown (painted): seven rounded root buttresses, four
    vertices across each (crevice, shoulder, ridge, shoulder) shaped by cos^2, flaring over the
    bottom 0.4 and diving into the soil through a ring just below the ground, moss on one side
    and dirt on the other at the ground line. Above the roots the trunk drops to fourteen sides:
    bark ridges with dark crevices, each ridge its own shade. Inside the crown the trunk
    continues as a dark core in the foliage material, so it sways with the boughs around it."""
    roots, per = 7, 4
    sides = roots * per
    phase = 2 * math.pi * R.random()
    root_amp = [R.uniform(0.35, 0.85) for _ in range(roots)]
    for k in R.sample(range(roots), 2):
        root_amp[k] = R.uniform(0.95, 1.05)          # two strong roots per tree
    plate = [R.uniform(0.72, 1.12) for _ in range(sides // 2)]
    moss_dir = R.uniform(0, 2 * math.pi)
    top = CROWN_BASE + 0.14                           # hidden inside the lowest tier
    zs = [-0.016, 0.0, 0.035, 0.09, 0.17, 0.28, 0.43, 0.62, 0.82, 1.04]
    zs = [z for z in zs if z < top - 0.1] + [top]
    split = next(k for k, z in enumerate(zs) if z >= 0.43)   # from here up: fourteen sides
    bark_low, bark_high = lin(BARK), lerp(lin(WOOD), lin(PUMPKIN_DARK), 0.35)
    moss, dirt = lin(NEEDLE), lin(STONE_SHADOW)
    rings = []
    for k, z in enumerate(zs):
        zz = max(0.0, z)
        c = axis(zz)
        r = trunk_radius(zz)
        flare = math.exp(-zz / 0.2)
        twist = 0.35 * zz
        ring = []
        for s in range(sides):
            if k >= split and s % 2:
                continue
            ri, x = s // per, (s % per) / per - 0.5          # x: -0.5 crevice, 0 ridge
            th = 2 * math.pi * s / sides + phase + twist
            # A full, rounded hump per root (shoulders close to the ridge), deep grooves between.
            lobe = abs(math.cos(math.pi * x)) ** 0.6 * root_amp[ri]
            rr = r * (1.0 + flare * (0.3 + 0.95 * lobe))
            rr *= 1.0 + 0.04 * (plate[s // 2] - 0.9) * (1 - flare) + R.uniform(-0.01, 0.01)
            if x == -0.5:
                rr *= lerp(0.9, 0.97, flare)                  # a groove between the buttresses
            if z < 0.0:
                rr *= 1.08                                    # the roots dive into the soil
            p = c + Vector((math.cos(th) * rr, math.sin(th) * rr, z))
            p.z = z
            col = lerp(bark_low, bark_high, smoothstep(0.05, 0.8, zz)) * plate[s // 2]
            if x == -0.5:
                col = col * 0.55
            elif x != 0.0:
                col = col * 0.82
            col = col * (1.0 + 0.18 * flare * lobe)                   # lit rim on the root lobes
            col = col * (0.66 + 0.34 * smoothstep(0.0, 0.22, zz))      # ground contact
            col = col * lerp(1.0, 0.45, smoothstep(CROWN_BASE - 0.25, top, zz))   # under the crown
            if z < 0.1:
                mossy = smoothstep(-0.2, 0.4, math.cos(th - moss_dir))
                ground = lerp(dirt, moss, mossy) * 0.8
                col = lerp(col, ground, 0.35 if z < 0.05 else 0.15 * mossy)
            ring.append(b.vert(p, col, BARK_A))
        rings.append(ring)

    def uv(s, n, z):
        return (BARK_U * s / n, z * 0.8)

    for k in range(len(rings) - 1):
        lo, hi = rings[k], rings[k + 1]
        z0, z1 = zs[k], zs[k + 1]
        if len(lo) == len(hi):
            n = len(lo)
            for s in range(n):
                s2 = (s + 1) % n
                b.face((lo[s], lo[s2], hi[s2], hi[s]), [uv(s, n, z0), uv(s + 1, n, z0), uv(s + 1, n, z1), uv(s, n, z1)])
        else:
            n = len(hi)                                       # 28 below, 14 above
            for s in range(n):
                s2 = (s + 1) % n
                a, m, e = lo[2 * s], lo[2 * s + 1], lo[(2 * s + 2) % len(lo)]
                b.face((a, m, hi[s]), [uv(2 * s, 2 * n, z0), uv(2 * s + 1, 2 * n, z0), uv(s, n, z1)])
                b.face((m, e, hi[s2], hi[s]), [uv(2 * s + 1, 2 * n, z0), uv(2 * s + 2, 2 * n, z0),
                                                uv(s + 1, n, z1), uv(s, n, z1)])

    # The core inside the crown: six sides, dark reddish brown fading to shadow, starting a little
    # inside the painted trunk's top so the seam never opens when it sways.
    core_sides = 6
    z0, z1 = CROWN_BASE + 0.04, CROWN_TOP - 0.06
    core_zs = [z0 + (z1 - z0) * i / 3 for i in range(4)]
    core = []
    for z in core_zs:
        c = axis(z)
        r = trunk_radius(z) * 0.94
        ring = []
        for s in range(core_sides):
            th = 2 * math.pi * s / core_sides
            n = Vector((math.cos(th), math.sin(th), 0.15)).normalized()
            col = lerp(lin(BARK) * 0.34, SHADOW * 0.5, smoothstep(0.15, 0.6, crown_h(z))) / SOLID_TEXEL
            ring.append(solid.vert(c + Vector((math.cos(th) * r, math.sin(th) * r, 0)), col, 0.0, n))
        core.append(ring)
    apex = solid.vert(axis(z1 + 0.06), SHADOW * 0.5 / SOLID_TEXEL, 0.0, Vector((0, 0, 1)))
    for k in range(len(core) - 1):
        for s in range(core_sides):
            s2 = (s + 1) % core_sides
            solid.face((core[k][s], core[k][s2], core[k + 1][s2], core[k + 1][s]), [SOLID_UV] * 4)
    for s in range(core_sides):
        solid.face((core[-1][s], core[-1][(s + 1) % core_sides], apex), [SOLID_UV] * 3)


def build_stubs(b: Builder):
    """Short, weathered dead branch stubs between the root flare and the lowest tier, pitched down
    and drooping, tapering to a snapped end, each growing out of a bark collar; one carries a broken
    twig. One always points toward +X (yaw 0) so it shows past the crown on a share of the trees."""
    count = 2 + (1 if R.random() < 0.5 else 0)
    yaw0 = math.radians(R.uniform(-60, 60))
    dead_root = lin(WOOD_DARK) * 1.05
    dead_tip = lerp(lin(WOOD_DARK), lin(STONE_WARM), 0.4)
    end_cap = lerp(lin(WOOD), lin(STONE_WARM), 0.5) * 0.8
    for i in range(count):
        z = lerp(0.35, LOW_TIP - 0.05, (i + R.uniform(0.15, 0.85)) / count)
        yaw = yaw0 + i * math.radians(R.uniform(110, 150))
        rise = -math.radians(R.uniform(10, 25))
        length = R.uniform(0.18, 0.28)
        radius = R.uniform(0.03, 0.038)
        d = Vector((math.cos(yaw) * math.cos(rise), math.sin(yaw) * math.cos(rise), math.sin(rise)))
        start = axis(z) - d * 0.02
        bark_at = trunk_radius(z) + 0.02
        tube(b, start, d, bark_at + length, radius, radius * 0.35, 6, dead_root, dead_tip, end_cap,
             droop=R.uniform(0.03, 0.06), segs=3, collar=bark_at)
        if i == 0:
            p = start + d * (bark_at + length * 0.5)
            side = Vector((-d.y, d.x, 0)).normalized() * (1 if R.random() < 0.5 else -1)
            d2 = (d * 0.55 + side * 0.65 + Vector((0, 0, 0.3))).normalized()
            tube(b, p, d2, length * 0.45, radius * 0.45, radius * 0.2, 4, dead_root, dead_tip, end_cap, segs=1)


def tube(b, start, d, length, r0, r1, sides, c0, c1, c_end, droop=0.0, segs=2, collar=None):
    """A tapered branch along `d` ending in a snapped, jagged cap. With `collar` (the distance from
    `start` to the bark) it grows out of a swollen bark collar 1.3x its radius."""
    up = Vector((0, 0, 1))
    side = d.cross(up)
    if side.length < 1e-4:
        side = Vector((1, 0, 0))
    side.normalize()
    upv = side.cross(d).normalized()
    # (distance along the branch, radius, colour) per ring
    if collar is not None:
        out = length - collar
        stations = [(0.0, r0 * 1.3, c0 * 0.8), (collar, r0 * 1.3, c0 * 0.9), (collar + 0.035, r0, c0)]
        stations += [(collar + out * k / segs, lerp(r0, r1, k / segs), lerp(c0, c1, k / segs))
                     for k in range(1, segs + 1)]
        bend0 = collar
    else:
        stations = [(length * k / segs, lerp(r0, r1, k / segs), lerp(c0, c1, k / segs)) for k in range(segs + 1)]
        bend0 = 0.0

    def centre(dist):
        f = max(0.0, (dist - bend0) / max(1e-4, length - bend0))
        return start + d * dist + Vector((0, 0, -droop * f * f))

    rings = []
    for k, (dist, r, col_k) in enumerate(stations):
        c = centre(dist)
        last = k == len(stations) - 1
        ring = []
        for s in range(sides):
            th = 2 * math.pi * s / sides
            off = side * (math.cos(th) * r) + upv * (math.sin(th) * r)
            jag = d * (R.uniform(-0.4, 0.4) * r if last else 0.0)
            col = col_k * (0.74 + 0.16 * max(0.0, math.sin(th)))   # the sun lights the top already
            ring.append(b.vert(c + off + jag, col, BARK_A))
        rings.append(ring)
    circ = 2 * math.pi * r0
    for k in range(len(rings) - 1):
        lo, hi = rings[k], rings[k + 1]
        v0, v1 = stations[k][0], stations[k + 1][0]
        for s in range(sides):
            s2 = (s + 1) % sides
            u0, u1 = circ * s / sides, circ * (s + 1) / sides
            b.face((lo[s], lo[s2], hi[s2], hi[s]), [(v0, u0), (v1, u0), (v1, u1), (v0, u1)])
    # The snapped end: weathered heartwood, slightly sunken.
    tip = b.vert(centre(length * 0.97), c_end, BARK_A)
    last = rings[-1]
    for s in range(sides):
        b.face((last[s], last[(s + 1) % sides], tip), [(0, 0), (0.02, 0), (0.01, 0.02)])


# ── Interior cones ──

def build_skirt(b: Builder, z: float, radius: float, droop: float, phase: float):
    """A dark cone under a tier so packed forests never show daylight through the crown. It
    samples one opaque texel of the card texture, so it sways with the cards."""
    sides = 7
    c = axis(z + 0.03)
    h = crown_h(z)

    def colour(t, hh):
        return cap(lerp(needle_tint(t, hh, 1.0), SHADOW * height_light(hh), 0.5) * 0.5 / SOLID_TEXEL)

    apex = b.vert(c, colour(0.1, h), 0.0, Vector((0, 0, 1)))
    ring = []
    bottom = max(LOW_TIP + 0.02, z - droop)
    for s in range(sides):
        th = phase + 2 * math.pi * s / sides
        rr = radius * (1.0 if s % 2 == 0 else 0.84)
        p = axis(bottom) + Vector((math.cos(th) * rr, math.sin(th) * rr, 0.0))
        n = Vector((math.cos(th), math.sin(th), 0.9)).normalized()
        ring.append(b.vert(p, colour(0.4, crown_h(bottom)), 0.0, n))
    for s in range(sides):
        b.face((apex, ring[s], ring[(s + 1) % sides]), [SOLID_UV] * 3)


# ── Foliage cards ──

def card(b: Builder, root, yaw, pitch, length, width, droop, roll=0.0, cup=-0.12, segs=3, shade=1.0,
         t0=0.0, curl=None, reach=None, under=None, tw=0.0, uv=(0.0, 1.0, 0.0, 1.0), spine=0.8,
         direction=None, side=None, taper=0.0, rows_t=None, tmax=1.0, flutter=1.0, flip=False):
    """A bough card growing from `root` along yaw/pitch (degrees) or an explicit `direction`
    (with `side` across it), drooping by `droop` metres at the tip, rolled about its own length
    by `roll` degrees. Convex for cup < 0: a lit spine with the edges rolling down. `uv` is the
    (u0, u1, v0, v1) part of the texture it shows, u running root to tip; `rows_t` places its
    rows along the length (default: even).

    Tinted dark to bright by distance from the trunk relative to the tier's `reach` (or along
    the card from `t0` when there is none), never past `tmax`, darker on its edges than its spine
    (`spine`), and turned toward the shadow colour where the tier above (`under`: its radius and
    the height its tips hang down to) covers it; the shadow weakens toward the top of the tree
    (`tw`, the tier's height 0..1). Normals point up on the shoulder and out along the hanging
    rim. Alpha carries the flutter weight, 0 at the root to `flutter` at the tip.

    `flip` makes the card's lower face its front face. The foliage material is double sided and
    Godot negates the normal on back faces, so a steeply upswept card seen from outside (its lower
    face) would light as if it faced down: flipped, the outside is the front and lights as set."""
    if direction is None:
        y, p = math.radians(yaw), math.radians(pitch)
        d = Vector((math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)))
        s = Vector((-math.sin(y), math.cos(y), 0.0))
    else:
        d = Vector(direction).normalized()
        s = Vector(side)
        s = (s - d * s.dot(d)).normalized()
    n = d.cross(s).normalized()
    r = math.radians(roll)
    s, n = s * math.cos(r) + n * math.sin(r), n * math.cos(r) - s * math.sin(r)
    root = Vector(root)
    u0, u1, v0, v1 = uv
    curl = CURL if curl is None else curl
    ts = list(rows_t) if rows_t else [i / segs for i in range(segs + 1)]

    def points(droop_now):
        rows = []
        for t in ts:
            c = root + d * (length * t) + Vector((0, 0, -droop_now * t ** curl))
            lift = n * (cup * width * (1 - t * 0.5))
            w = width * (1.0 - taper * t)
            rows.append([c + s * (w * off) + (lift if off else Vector()) for off in (-0.5, 0.0, 0.5)])
        return rows

    # The lowest tier must clear LOW_TIP so the camera sees the trunk base: flatten its droop.
    rows = points(droop)
    for _ in range(4):
        low = min(p.z for row in rows for p in row)
        if low >= LOW_TIP - 0.005 or droop <= 0.0:
            break
        droop = max(0.0, droop - (LOW_TIP - low) - 0.005)
        rows = points(droop)

    shadow = None
    ids = []
    for t, row in zip(ts, rows):
        out = []
        tb = t ** 1.5
        for k, pos in enumerate(row):
            edge = k - 1                       # -1, 0, 1 across the card
            ax = axis(pos.z)
            radial = Vector((pos.x - ax.x, pos.y - ax.y, 0.0))
            rl = radial.length
            radial = radial / rl if rl > 1e-4 else Vector((d.x, d.y, 0)).normalized()
            h = crown_h(pos.z)
            # Shoulder normals point up (sun and top light), the hanging rim's point out.
            local = (n + s * (edge * 0.7)).normalized() if cup < 0 else n
            nn = (radial * lerp(0.35, 0.95, tb) + Vector((0, 0, lerp(0.95, 0.15, tb))) + local * 0.3).normalized()
            tt = t0 + (1 - t0) * t if reach is None else min(1.0, rl / reach)
            col = needle_tint(min(tt, tmax), h, shade)
            if edge:
                col = col * spine
            if under:
                # The tier above (radius ua, tips hanging down to edge_z) shades this one: toward a
                # deep teal just under its edge, opening up toward this tier's own tips further down.
                ua, edge_z = under
                covered = smoothstep(ua * 1.35, ua * 0.95, rl)
                opened = smoothstep(edge_z - 0.02, edge_z - 0.02 - SHADOW_BAND, pos.z)
                kk = covered * (1.0 - opened) * lerp(0.8, 0.35, tw)
                col = lerp(col, SHADOW * height_light(h) * shade, kk)
            out.append(b.vert(pos, cap(col), flutter * t, nn))
        ids.append(out)
    for i in range(len(ts) - 1):
        ua, ub = lerp(u0, u1, ts[i]), lerp(u0, u1, ts[i + 1])
        vm = 0.5 * (v0 + v1)
        a, c_ = ids[i], ids[i + 1]
        if FLAT:
            b.face((a[0], c_[0], c_[1], a[1]), [SOLID_UV] * 4)
            b.face((a[1], c_[1], c_[2], a[2]), [SOLID_UV] * 4)
            continue
        if flip:
            b.face((a[1], c_[1], c_[0], a[0]), [(ua, vm), (ub, vm), (ub, v0), (ua, v0)])
            b.face((a[2], c_[2], c_[1], a[1]), [(ua, v1), (ub, v1), (ub, vm), (ua, vm)])
            continue
        b.face((a[0], c_[0], c_[1], a[1]), [(ua, v0), (ub, v0), (ub, vm), (ua, vm)])
        b.face((a[1], c_[1], c_[2], a[2]), [(ua, vm), (ub, vm), (ub, v1), (ua, v1)])


GAP_YAW = R.uniform(0, 360)


def bough_scale(i: int, yaw_deg: float, n: int) -> float:
    """Per-seed signatures. Seed 1: a lopsided, wind-swept crown, short on the side away from the
    lean. Seed 3: one mid tier dented on one side."""
    if HABIT == 0:
        away = math.degrees(LEAN_DIR) + 180.0
        diff = abs((yaw_deg - away + 180.0) % 360.0 - 180.0)
        return lerp(0.7, 1.0, smoothstep(40.0, 80.0, diff))
    if HABIT == 2 and i == n // 2:
        diff = abs((yaw_deg - GAP_YAW + 180.0) % 360.0 - 180.0)
        return lerp(0.55, 1.0, smoothstep(22.0, 38.0, diff))
    return 1.0


def build_crown(cards: Builder):
    n = WHORLS
    golden = 137.5
    phase = R.uniform(0, 360)
    span = CROWN_TOP - CROWN_BASE
    whorls = []
    for i in range(n):
        t = i / (n - 1)
        z = CROWN_BASE + span * (1 - (1 - t) ** 1.2) + (R.uniform(-0.02, 0.02) if i else 0.0)
        whorls.append((t, z, crown_radius(z) * R.uniform(0.94, 1.06) * (0.8 if i == 0 else 1.0)))
    for i, (t, z, rad) in enumerate(whorls):
        above = None
        if i < n - 1:
            ta, za, ra = whorls[i + 1]
            ra *= BOUGH_LEN
            above = (ra, za + ra * (math.sin(math.radians(lerp(5, 10, ta))) - lerp(0.45, 0.55, ta)))
        nb = round(lerp(BOUGHS[0], BOUGHS[1], t)) + R.choice((-1, 0, 0, 0, 1))
        nb = max(3, min(8, nb))
        whorl_phase = phase + golden * i
        droop_k = 0.3 if i == 0 else lerp(DROOP_K[0], DROOP_K[1], t)
        pitch_base = lerp(5, 10, t)
        shade = R.uniform(0.94, 1.06)
        reach = rad * BOUGH_LEN
        if t < 0.85:
            build_skirt(cards, z - 0.05, rad * lerp(0.5, 0.36, smoothstep(0.4, 0.85, t)), rad * 0.26,
                        math.radians(whorl_phase))
        for j in range(nb):
            yaw = whorl_phase + 360.0 * j / nb + R.uniform(-0.25, 0.25) * 360.0 / nb
            length = reach * (1 + R.uniform(-0.024, 0.015)) * bough_scale(i, yaw, n)
            pitch = pitch_base + R.uniform(-1.2, 1.2)
            droop = length * droop_k * (1 + R.uniform(-0.036, 0.036))
            width = rad * BOUGH_WIDTH * R.uniform(0.95, 1.05) * (0.85 + 0.15 * length / reach)
            ax = axis(z)
            root = ax + Vector((math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0)) * 0.02
            root.z = z + R.uniform(-0.02, 0.02)
            bshade = shade * R.uniform(0.92, 1.06)
            common = dict(reach=reach, under=above, tw=t)
            # Main card: a broad convex fan, lit along its spine, kinked between shoulder and skirt.
            card(cards, root, yaw, pitch, length, width, droop, cup=-0.12, shade=bshade, rows_t=MAIN_ROWS, **common)
            # One side card tents over it, outer edge rolled down, alternating sides along the tier.
            side = -1 if j % 2 else 1
            dy = side * R.uniform(16, 24)
            l2 = length * R.uniform(0.72, 0.86)
            r2 = root + Vector((0, 0, R.uniform(0.01, 0.04)))
            card(cards, r2, yaw + dy, pitch + R.uniform(3, 8), l2, width * 0.8, droop * 0.85,
                 roll=-side * R.uniform(28, 38), cup=-0.06, segs=2, shade=bshade, spine=0.85, **common)
            # High on the tree, a short bough between tiers hides the trunk.
            if t >= 0.7 and i < n - 1 and j % 2 == 0:
                zm = 0.5 * (z + whorls[i + 1][1])
                ym = yaw + 180.0 / nb
                rm = axis(zm) + Vector((math.cos(math.radians(ym)), math.sin(math.radians(ym)), 0)) * 0.02
                lm = crown_radius(zm) * R.uniform(0.8, 0.95)
                card(cards, rm, ym, pitch + 6, lm, lm * 0.9, lm * 0.45, cup=-0.08, segs=2,
                     shade=bshade * 0.95, reach=crown_radius(zm), under=above, tw=t)
            # Low on the tree, a flat under card closes the bottom of the tier.
            if t < 0.45:
                r3 = root + Vector((0, 0, -0.05))
                card(cards, r3, yaw + R.uniform(-12, 12), pitch - 6, length * 0.9, width * 0.95, droop * 1.05,
                     cup=-0.05, segs=2, shade=bshade * 0.82, flutter=0.8, **common)
        # The inner layer: short, upswept cards between the boughs, rooted a little higher, dark
        # (never past MID), filling the gap between tiers near the trunk. The upper tiers sit
        # closer to their own width apart, so they get one between every pair of boughs.
        if i < n - 1:
            ni = max(2, nb // 2) if t < 0.5 else nb
            for j in range(ni):
                yaw = whorl_phase + 360.0 * (j + 0.5) / ni + R.uniform(-8, 8)
                li = reach * lerp(0.55, 0.68, smoothstep(0.4, 0.9, t)) * R.uniform(0.92, 1.08)
                ri = axis(z + 0.04) + Vector((math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0)) * 0.02
                card(cards, ri, yaw, pitch_base + 18 + R.uniform(-3, 3), li, li * 0.95, li * 0.22, cup=-0.1,
                     segs=2, shade=shade * 0.75, t0=0.0, tmax=0.7, under=above, tw=t, flutter=0.6)
    # The spire: one leader, or seed 2's leader with a small secondary leader beside it.
    lead_phase = R.uniform(0, 360)
    if HABIT == 1:
        fork = R.uniform(0, 360)
        build_spire(cards, lead_phase, tilt=4, tilt_yaw=fork + 180, scale=1.0)
        build_spire(cards, lead_phase + 40, tilt=30, tilt_yaw=fork, scale=0.65, ring=False, drop=0.15,
                    whorls=((0.1, 0.12, 34),))
    else:
        build_spire(cards, lead_phase, tilt=math.degrees(LEAN) * 0.6, tilt_yaw=math.degrees(LEAN_DIR), scale=1.0)


def build_spire(cards: Builder, phase: float, tilt: float, tilt_yaw: float, scale: float, ring: bool = True,
                drop: float = 0.0, whorls=((0.05, 0.17, 28), (0.11, 0.14, 38), (0.17, 0.11, 50), (0.23, 0.08, 62))):
    """The top: a ring of small upswept boughs on the top whorl, then small whorls of three up the
    leader, each shorter and steeper than the last, so the crown closes into a cone of real fronds;
    the point is a short, closed three-sided sheath showing the whole fan of the texture's tip.
    Steep cards and the sheath face outward (front faces), so none goes dark from behind."""
    ty, tl = math.radians(tilt_yaw), math.radians(tilt)
    up = Vector((math.sin(tl) * math.cos(ty), math.sin(tl) * math.sin(ty), math.cos(tl)))
    e1, e2 = frame(up)
    base = axis(CROWN_TOP - drop)
    if ring:
        for j in range(5):
            yaw = phase + 72 * j + R.uniform(-12, 12)
            root = base + Vector((0, 0, 0.03 + R.uniform(-0.02, 0.02)))
            card(cards, root, yaw, R.uniform(30, 38), R.uniform(0.17, 0.2), 0.16, 0.05, cup=-0.08, segs=2,
                 shade=1.05, t0=0.45, flutter=0.8)
    for k, (dz, ln, pitch) in enumerate(whorls):
        root = base + up * (dz * scale)
        for j in range(3):
            a = math.radians(phase + 40 + 60 * k + 120 * j + R.uniform(-15, 15))
            p = math.radians(pitch + R.uniform(-4, 4))
            out = e1 * math.cos(a) + e2 * math.sin(a)
            d = out * math.cos(p) + up * math.sin(p)
            sd = e2 * math.cos(a) - e1 * math.sin(a)
            lk = ln * R.uniform(0.9, 1.05) * (0.8 + 0.2 * scale)
            card(cards, root, 0, 0, lk, lk * 0.95, 0.025, cup=-0.08, segs=2, shade=1.1, t0=0.5 + 0.1 * k,
                 direction=d, side=sd, flutter=0.8, flip=pitch > 38)
    # The point: three outward faces around the axis, normals out from the leader plus up.
    sheath_z = whorls[-1][0] * 0.9
    length = (LEADER + 0.05) * scale - sheath_z * scale
    rc = 0.045 * (0.75 + 0.25 * scale)
    taper, segs, faces = 0.6, 3, 3
    start = base + up * (sheath_z * scale)
    u0, u1, v0, v1 = 0.3, 1.0, 0.0, 1.0
    rows = []
    for i in range(segs + 1):
        t = i / segs
        c = start + up * (length * t)
        r = rc * (1.0 - taper * t)
        h = crown_h(c.z)
        row = []
        for k in range(faces):
            a = math.radians(phase) + 2 * math.pi * k / faces
            out = e1 * math.cos(a) + e2 * math.sin(a)
            nrm = (out * 0.6 + up * 0.8).normalized()
            col = cap(needle_tint(lerp(0.75, 1.0, t), max(h, 0.9), 1.08))
            row.append(cards.vert(c + out * r, col, 0.6 + 0.4 * t, nrm))
        rows.append(row)
    for k in range(faces):
        k2 = (k + 1) % faces
        for i in range(segs):
            ua, ub = lerp(u0, u1, i / segs), lerp(u0, u1, (i + 1) / segs)
            quad = (rows[i][k], rows[i][k2], rows[i + 1][k2], rows[i + 1][k])
            cards.face(quad, [SOLID_UV] * 4 if FLAT else [(ua, v0), (ua, v1), (ub, v1), (ub, v0)])


def normalise_height(objs):
    zmax = max((o.matrix_world @ v.co).z for o in objs for v in o.data.vertices)
    k = HEIGHT / zmax
    for o in objs:
        o.scale = (k, k, k)
        gab.apply_transform(o)


def main():
    painted = Builder()
    cards = Builder()
    build_trunk(painted, cards)
    build_stubs(painted)
    build_crown(cards)
    trunk = painted.build("pine_trunk", gab.painted(), smooth_angle=40)
    crown = cards.build("pine_crown", gab.foliage("foliage_pine"), custom_normals=True)
    normalise_height([trunk, crown])
    if ONLY == "trunk":
        # Preview only: the trunk and stubs below the crown, for a close look at the bark.
        bpy.data.objects.remove(crown)
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(trunk.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().z > CROWN_BASE], context="FACES")
        bm.to_mesh(trunk.data)
        bm.free()
    low = min(v.co.z for v in crown.data.vertices) if ONLY != "trunk" else 0.0
    xs = [v.co.x for o in (trunk, crown) if o.name in bpy.data.objects for v in o.data.vertices] if ONLY != "trunk" else [0]
    ys = [v.co.y for o in (trunk, crown) if o.name in bpy.data.objects for v in o.data.vertices] if ONLY != "trunk" else [0]
    w = max(max(xs) - min(xs), max(ys) - min(ys))
    print(f"pine seed {SEED}: height {HEIGHT:.2f}, whorls {WHORLS}, lean {LEAN:.2f}, crown base {CROWN_BASE:.2f}, "
          f"lowest foliage {low:.2f}, width {w:.2f} w/h {w / HEIGHT:.2f}, tris trunk {painted.tris()} "
          f"crown {cards.tris()} total {painted.tris() + cards.tris()}")


main()
