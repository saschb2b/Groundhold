"""Duskmoth: a winged creep for Wickhollow (the Spindrift form of its wrack).

Build:
    godot-agent asset blender . art_src/blender/duskmoth.py --to res://models/creeps/duskmoth.glb \
        --seed 1 --review --no-import

A large grey-brown moth drawn up through the sunken field gate toward the hollow's lamps. Broad dusty
forewings of silvered brown with two wavy dark crossbands, a pale fringe and a glowing orange eyespot
ringed in dark; rounder hindwings that glow orange at the base under a dark marginal band, the way an
underwing flashes its colour in flight. A furry thorax with a pale collar, a banded abdomen that tapers to
a tuft, a small head with two big glowing orange eyes and feathered antennae swept up and back, and three
pairs of dark legs tucked under the thorax.

The glow is an emissive material (`creep_glow_orange`), never a light: WebGL 2 allows few lights per object
(design 2.4). Every other surface is the painted material with vertex colours from palettes/hollow.gpl.

It hovers: the model hangs from the origin with its lowest point (the dangling legs) at z = 0 in the rest
pose; the game lifts it about a metre over the road (scripts/creep.gd). The looping 10-frame 'walk' is its
flap cycle: a quick downstroke and a slower upstroke, the hindwings a frame behind the forewings and
shallower, the body rising on each downstroke and sinking on the upstroke, the abdomen and the antennae
following late. At 30 fps one flap takes a third of a second at the speed STRIDE (printed at the end, in
game units at the game's 1.5x scale); Game.CREEPS["duskmoth"]["stride"] should be that value, so the flaps
speed up and slow down with the moth (frost slows them too).

Params:
    pose_frame    bake the flap at this frame into the mesh (preview only; no rig in the output)
    glow          emission strength of the eyes and wing marks (default 0.9: brighter bleaches toward
                  cream under the game's tonemap and glow, and the marks should read orange)

Front faces -Y, Z up.
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import gab

rng = gab.rng
POSE_FRAME = gab.param("pose_frame", -1)
GLOW = gab.param("glow", 0.9)
GAME_SCALE = 1.5


# ── Colour (palettes/hollow.gpl) ──

def hx(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t: float) -> tuple:
    t = max(0.0, min(1.0, t))
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def mul(c, k: float) -> tuple:
    return tuple(min(255.0, max(0.0, ch * k)) for ch in c)


def lin(c) -> tuple:
    return tuple(gab._linear(min(255.0, max(0.0, ch)) / 255.0) for ch in c)


def smoothstep(a: float, b: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


DUST = hx("#9a948a")        # stone_warm: the forewings' silvered grey-brown
DUST_SHADE = hx("#6b665f")  # stone_shadow
BAND = hx("#6b4a34")        # hide: the wavy crossbands
BAND_DARK = hx("#4a3324")   # hide_dark
FRINGE = hx("#d8c8a8")      # spike: the pale fringe and the collar
FUR = hx("#7a5534")         # wood: the thorax's fur
FUR_DARK = hx("#4e3423")    # wood_dark
LEG = hx("#3e2a1e")         # leg
ORANGE = hx("#d9772b")      # pumpkin: the hindwings' lit orange around the glow
ORANGE_DEEP = hx("#a8521e") # pumpkin_dark
GLOW_C = hx("#ffb040")      # glow_orange
GLOW_CORE = hx("#ffd860")   # glow_yellow

PATTERN = {name: (i + 0.5) / 16 for i, name in enumerate(gab.PATTERNS)}


# ── Parts: vertex, colour and UV lists turned into mesh objects, each rigid on one bone ──

PARTS = []


class Part:
    def __init__(self, name: str, bone: str, pattern: str = "plain", material: str = "painted",
                 smooth: float | None = 50.0, mottle: float = 0.04):
        self.name, self.bone, self.pattern, self.material = name, bone, pattern, material
        self.smooth, self.mottle = smooth, mottle
        self.verts, self.cols, self.uvs, self.faces = [], [], [], []
        PARTS.append(self)

    def add(self, co, col, uv=None) -> int:
        co = tuple(co)
        self.verts.append(co)
        self.cols.append(tuple(col))
        self.uvs.append(tuple(uv) if uv is not None else (co[0] * 3, co[1] * 3))
        return len(self.verts) - 1

    def face(self, *idx) -> None:
        clean = []
        for i in idx:
            if i not in clean:
                clean.append(i)
        if len(clean) >= 3:
            self.faces.append(tuple(clean))

    def ring_to_ring(self, a: list, b: list, closed: bool = True) -> None:
        if len(a) == 1 or len(b) == 1:
            ring, tip = (b, a[0]) if len(a) == 1 else (a, b[0])
            n = len(ring)
            for k in range(n if closed else n - 1):
                if len(a) == 1:
                    self.face(tip, ring[(k + 1) % n], ring[k])
                else:
                    self.face(ring[k], ring[(k + 1) % n], tip)
            return
        n = len(a)
        for k in range(n if closed else n - 1):
            k1 = (k + 1) % n
            self.face(a[k], a[k1], b[k1], b[k])

    def build(self) -> bpy.types.Object:
        obj = gab.mesh_object(self.name, self.verts, self.faces)
        mesh = obj.data
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(mesh)
        bm.free()
        uv_layer = mesh.uv_layers.new(name="UVMap")
        layer = mesh.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="CORNER")
        mesh.color_attributes.active_color = layer
        alpha = PATTERN[self.pattern] if self.material == "painted" else 1.0
        shade = [1.0 + rng.uniform(-self.mottle, self.mottle) for _ in self.verts]
        for poly in mesh.polygons:
            for li in poly.loop_indices:
                vi = mesh.loops[li].vertex_index
                uv_layer.data[li].uv = self.uvs[vi]
                layer.data[li].color = (*lin(mul(self.cols[vi], shade[vi])), alpha)
        gab.assign(obj, gab.painted() if self.material == "painted" else bpy.data.materials[self.material])
        if self.smooth is None:
            gab.flat(obj)
        else:
            gab.smooth(obj, self.smooth)
        group = obj.vertex_groups.new(name=self.bone)
        group.add(list(range(len(self.verts))), 1.0, "REPLACE")
        return obj


def tube(part: Part, pts, radii, sides: int, col, squash: float = 1.0) -> None:
    """A tapered tube along a polyline; a radius of 0 ends in a point. col(t, facing) gives the colour at
    length fraction t on a side facing `facing` (-1 down .. 1 up)."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    lengths = [0.0]
    for i in range(1, n):
        lengths.append(lengths[-1] + (pts[i] - pts[i - 1]).length)
    total = lengths[-1] or 1.0
    tangents = []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
        tangents.append(t.normalized())
    up = Vector((0.0, 0.0, 1.0))
    normal = up - tangents[0] * up.dot(tangents[0])
    if normal.length < 1e-6:
        normal = tangents[0].orthogonal()
    normal.normalize()
    rings = []
    for i in range(n):
        if i > 0:
            normal = tangents[i - 1].rotation_difference(tangents[i]) @ normal
            normal = (normal - tangents[i] * normal.dot(tangents[i])).normalized()
        binormal = tangents[i].cross(normal)
        r = radii[i]
        t = lengths[i] / total
        if r <= 1e-6:
            rings.append([part.add(pts[i], col(t, tangents[i].z))])
            continue
        ring = []
        for k in range(sides):
            a = math.pi + 2 * math.pi * k / sides
            d = normal * math.cos(a) * squash + binormal * math.sin(a)
            facing = (normal * math.cos(a) + binormal * math.sin(a)).z
            ring.append(part.add(pts[i] + d * r, col(t, facing), ((a - math.pi) * r * 4, lengths[i] * 4)))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        part.ring_to_ring(a, b)
    if len(rings[0]) > 1:
        c = part.add(pts[0] - tangents[0] * radii[0] * 0.4, col(0.0, -1.0))
        part.ring_to_ring([c], rings[0])
    if len(rings[-1]) > 1:
        c = part.add(pts[-1] + tangents[-1] * radii[-1] * 0.4, col(1.0, 0.0))
        part.ring_to_ring(rings[-1], [c])


def ellipsoid(part: Part, center, radii, segs: int, rings: int, col) -> None:
    """A UV ellipsoid with its poles front (-Y) and back (+Y); col(n) gets the unit normal."""
    c = Vector(center)
    rx, ry, rz = radii

    def point(lat, lon):
        n = Vector((math.sin(lat) * math.cos(lon), -math.cos(lat), math.sin(lat) * math.sin(lon)))
        return c + Vector((n.x * rx, n.y * ry, n.z * rz)), n

    fp, fn = point(0.0, 0.0)
    bp, bn = point(math.pi, 0.0)
    front = part.add(fp, col(fn))
    rows = []
    for j in range(1, rings):
        lat = math.pi * j / rings
        row = []
        for k in range(segs):
            lon = -math.pi / 2 + 2 * math.pi * k / segs
            p, nrm = point(lat, lon)
            row.append(part.add(p, col(nrm), (lon * max(rx, rz) * 4, p.y * 4)))
        rows.append(row)
    back = part.add(bp, col(bn))
    part.ring_to_ring([front], rows[0])
    for a, b in zip(rows, rows[1:]):
        part.ring_to_ring(a, b)
    part.ring_to_ring(rows[-1], [back])


# ── The body ──

ZC = 0.11           # the body's axis height in the rest pose (the legs hang below it)
THORAX_Y = -0.05
FORE_ROOT = Vector((0.035, -0.075, ZC + 0.03))
HIND_ROOT = Vector((0.03, -0.03, ZC + 0.02))


def body() -> None:
    thorax = Part("thorax", "body", pattern="thatch", smooth=60.0, mottle=0.06)

    def fur(n):
        up = smoothstep(-0.6, 0.9, n.z)
        return mix(mul(FUR_DARK, 0.8), FUR, up)

    ellipsoid(thorax, (0, THORAX_Y, ZC), (0.05, 0.068, 0.052), 9, 6, fur)
    # a pale collar of tufts behind the head, the patagia
    collar = Part("collar", "body", pattern="thatch", smooth=None, mottle=0.08)
    for k in range(9):
        a = math.pi * (0.1 + 0.8 * k / 8)
        base = Vector((math.cos(a) * 0.044, THORAX_Y - 0.045, ZC + math.sin(a) * 0.044 - 0.004))
        tip = base + Vector((math.cos(a) * 0.022, 0.05, math.sin(a) * 0.026))
        side = Vector((math.sin(a), 0.0, -math.cos(a))) * 0.014
        i0 = collar.add(base - side, mul(FRINGE, 0.82))
        i1 = collar.add(base + side, mul(FRINGE, 0.82))
        i2 = collar.add(tip, FRINGE)
        i3 = collar.add(base + Vector((0, 0.01, -0.006)), mul(FRINGE, 0.6))
        collar.face(i0, i1, i2)
        collar.face(i1, i0, i3)
        collar.face(i0, i2, i3)
        collar.face(i1, i3, i2)

    abdomen = Part("abdomen", "abdomen", pattern="thatch", smooth=55.0, mottle=0.05)
    pts = [(0, -0.005, ZC - 0.004), (0, 0.04, ZC - 0.008), (0, 0.09, ZC - 0.014), (0, 0.14, ZC - 0.022),
           (0, 0.18, ZC - 0.03), (0, 0.205, ZC - 0.034), (0, 0.222, ZC - 0.036)]
    radii = [0.04, 0.046, 0.044, 0.036, 0.024, 0.012, 0.0]

    def band(t, facing):
        stripe = 0.5 + 0.5 * math.cos(t * math.pi * 9)
        c = mix(BAND_DARK, mix(FUR, DUST, 0.3), 0.35 + 0.45 * stripe)
        return mul(c, 0.72 + 0.32 * smoothstep(-0.8, 0.9, facing))

    tube(abdomen, pts, radii, 8, band)
    # a little tuft at the tip
    tuft = Part("tuft", "abdomen", pattern="thatch", smooth=None)
    tip = Vector(pts[-2])
    for k in range(4):
        a = 2 * math.pi * k / 4 + 0.4
        d = Vector((math.cos(a) * 0.012, 0.035, math.sin(a) * 0.012))
        i0 = tuft.add(tip + Vector((math.cos(a + 1.2) * 0.008, 0, math.sin(a + 1.2) * 0.008)), FUR)
        i1 = tuft.add(tip + Vector((math.cos(a - 1.2) * 0.008, 0, math.sin(a - 1.2) * 0.008)), FUR)
        i2 = tuft.add(tip + d, FRINGE)
        tuft.face(i0, i1, i2)
        tuft.face(i1, i0, i2)


def head() -> None:
    hd = Part("head", "head", pattern="thatch", smooth=60.0)
    hy = THORAX_Y - 0.085
    ellipsoid(hd, (0, hy, ZC - 0.004), (0.032, 0.03, 0.03), 8, 5,
              lambda n: mix(mul(FUR_DARK, 0.75), FUR, smoothstep(-0.5, 1.0, n.z)))
    eyes = Part("eyes", "head", material="creep_glow_orange", smooth=60.0, mottle=0.0)
    for s in (1, -1):
        ellipsoid(eyes, (s * 0.026, hy - 0.008, ZC + 0.002), (0.017, 0.017, 0.019), 6, 4, lambda n: GLOW_C)
    # feathered antennae, swept up and back, flat like a fern frond
    ant = Part("antennae", "head", pattern="plain", smooth=None, mottle=0.04)
    for s in (1, -1):
        p0 = Vector((s * 0.014, hy - 0.022, ZC + 0.02))
        pts = [p0, p0 + Vector((s * 0.03, -0.03, 0.05)), p0 + Vector((s * 0.07, -0.03, 0.09)),
               p0 + Vector((s * 0.11, 0.0, 0.115)), p0 + Vector((s * 0.135, 0.04, 0.12))]
        tube(ant, pts, [0.004, 0.012, 0.016, 0.011, 0.0], 4,
             lambda t, f: mix(BAND, FRINGE, 0.25 + 0.5 * t), squash=0.22)


def legs() -> None:
    lg = Part("legs", "body", pattern="plain", smooth=None, mottle=0.03)
    for s in (1, -1):
        for k, (y, out, down, back) in enumerate(((-0.08, 0.04, 0.085, -0.02), (-0.055, 0.05, 0.095, 0.02),
                                                  (-0.03, 0.045, 0.1, 0.06))):
            hip = Vector((s * 0.02, THORAX_Y + y + 0.05, ZC - 0.03))
            knee = hip + Vector((s * out, back * 0.4, -down * 0.45))
            foot = knee + Vector((s * out * 0.2, back, -down * 0.55))
            tube(lg, [hip, knee, foot], [0.008, 0.006, 0.002], 4, lambda t, f: mix(LEG, FUR_DARK, 0.3 * (1 - t)))


# ── The wings: closed thin slabs on a fan grid from the root, painted per vertex ──

def wing_grid(outline, rows, thick_root, thick_tip):
    """Fan-grid points for a wing in its own plane (u outward, v back): row j at fraction r_j of the way
    from the root to each outline point. Returns [(r, k, (u, v))] rows and the root."""
    grid = []
    for j in range(1, rows + 1):
        r = j / rows
        grid.append([(r, k, (outline[k][0] * r, outline[k][1] * r)) for k in range(len(outline))])
    return grid


def wing(name: str, bone: str, root: Vector, outline, colour, rows: int = 4, dihedral: float = 8.0,
         sweep: float = 0.0, side: int = 1, thick=(0.012, 0.004)):
    """One wing as a closed slab. outline: (u, v) points from the leading edge's apex round the margin to the
    inner margin. colour(r, kf, u, v) paints it; kf is the fraction along the outline."""
    part = Part(name, bone, pattern="cloth", smooth=None, mottle=0.035)
    rot = Matrix.Rotation(math.radians(side * dihedral), 3, "Y") @ Matrix.Rotation(math.radians(side * sweep), 3, "Z")

    def place(u, v, dz):
        return root + rot @ Vector((side * u, v, dz))

    k_n = len(outline)
    grid = wing_grid(outline, rows, *thick)
    top_root = part.add(place(0, 0, thick[0] / 2), colour(0.0, 0.0, 0.0, 0.0))
    bot_root = part.add(place(0, 0, -thick[0] / 2), mul(colour(0.0, 0.0, 0.0, 0.0), 0.8))
    tops, bots = [], []
    for row in grid:
        trow, brow = [], []
        for r, k, (u, v) in row:
            t = thick[0] + (thick[1] - thick[0]) * r
            c = colour(r, k / (k_n - 1), u, v)
            trow.append(part.add(place(u, v, t / 2), c, (u * 4, v * 4)))
            brow.append(part.add(place(u, v, -t / 2), mul(c, 0.82), (u * 4, v * 4)))
        tops.append(trow)
        bots.append(brow)
    for rows_, rootv in ((tops, top_root), (bots, bot_root)):
        part.ring_to_ring([rootv], rows_[0], closed=False)
        for a, b in zip(rows_, rows_[1:]):
            part.ring_to_ring(a, b, closed=False)
    # the margin, the leading edge and the inner edge close the slab
    part.ring_to_ring(tops[-1], bots[-1], closed=False)
    lead_t = [top_root] + [r[0] for r in tops]
    lead_b = [bot_root] + [r[0] for r in bots]
    inner_t = [top_root] + [r[-1] for r in tops]
    inner_b = [bot_root] + [r[-1] for r in bots]
    for a, b in ((lead_t, lead_b), (inner_t, inner_b)):
        for i in range(len(a) - 1):
            part.face(a[i], a[i + 1], b[i + 1], b[i])
    return place


def wavy(x, base, amp, freq, phase=0.0):
    return base + amp * math.sin(x * freq * math.pi + phase)


def fore_colour(r, kf, u, v):
    c = mix(DUST_SHADE, mix(DUST, BAND, 0.3), smoothstep(0.0, 0.35, r))
    b1 = abs(r - wavy(kf, 0.42, 0.05, 3.0))
    b2 = abs(r - wavy(kf, 0.78, 0.04, 4.0, 1.0))
    c = mix(c, BAND, smoothstep(0.08, 0.02, b1))
    c = mix(c, BAND_DARK, smoothstep(0.07, 0.02, b2))
    c = mix(c, FRINGE, smoothstep(0.93, 1.0, r) * 0.8)
    return c


def hind_colour(r, kf, u, v):
    c = mix(ORANGE_DEEP, ORANGE, smoothstep(0.1, 0.5, r))
    c = mix(c, BAND_DARK, smoothstep(0.62, 0.74, r))
    c = mix(c, FRINGE, smoothstep(0.92, 1.0, r) * 0.7)
    return c


# forewing: a broad blade, apex forward-out; hindwing: rounder, behind it
FORE = [(0.29, -0.045), (0.275, -0.005), (0.24, 0.045), (0.19, 0.09), (0.12, 0.115), (0.06, 0.11), (0.02, 0.08)]
HIND = [(0.16, 0.03), (0.17, 0.07), (0.15, 0.115), (0.11, 0.15), (0.06, 0.155), (0.02, 0.11)]


def glow_decal(name, bone, place, centre, radii, z, segs=10, ring=None):
    """A flat glowing disc (or ring) on a wing, both faces, just off the surface."""
    part = Part(name, bone, material="creep_glow_orange", smooth=None, mottle=0.0)
    cu, cv = centre
    for dz in (z, -z):
        c = part.add(place(cu, cv, dz), GLOW_CORE)
        rim = [part.add(place(cu + radii[0] * math.cos(2 * math.pi * k / segs),
                              cv + radii[1] * math.sin(2 * math.pi * k / segs), dz), GLOW_C) for k in range(segs)]
        if dz > 0:
            part.ring_to_ring([c], rim)
        else:
            part.ring_to_ring(rim, [c])


def wings() -> dict:
    places = {}
    for s, side in ((1, "L"), (-1, "R")):
        fp = wing(f"fore_{side}", f"fore_{side}", FORE_ROOT * Vector((s, 1, 1)), FORE, fore_colour, rows=5,
                  dihedral=10.0, sweep=-4.0, side=s, thick=(0.014, 0.004))
        hp = wing(f"hind_{side}", f"hind_{side}", HIND_ROOT * Vector((s, 1, 1)), HIND, hind_colour, rows=4,
                  dihedral=6.0, sweep=12.0, side=s, thick=(0.01, 0.004))
        places[side] = (fp, hp)
        # the forewing's eyespot: a dark ring and a glowing heart; the hindwing's glowing base
        dark = Part(f"spot_ring_{side}", f"fore_{side}", pattern="plain", smooth=None, mottle=0.0)
        cu, cv = 0.18, 0.04
        for dz in (0.0055, -0.0055):
            c = dark.add(fp(cu, cv, dz), BAND_DARK)
            rim = [dark.add(fp(cu + 0.042 * math.cos(2 * math.pi * k / 10), cv + 0.034 * math.sin(2 * math.pi * k / 10),
                               dz), BAND_DARK) for k in range(10)]
            if dz > 0:
                dark.ring_to_ring([c], rim)
            else:
                dark.ring_to_ring(rim, [c])
        glow_decal(f"spot_{side}", f"fore_{side}", fp, (cu, cv), (0.027, 0.022), 0.0075)
        glow_decal(f"hindglow_{side}", f"hind_{side}", hp, (0.06, 0.07), (0.032, 0.04), 0.0065, segs=8)
    return places


# ── Build ──

GLOW_MAT = gab.glow("creep_glow_orange", "#ffb040", GLOW)
GLOW_MAT.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*lin(mul(GLOW_C, 0.45)), 1.0)

body()
head()
legs()
wings()

objects = [p.build() for p in PARTS]
moth = gab.join(objects, "duskmoth")
moth.data.name = "duskmoth"

# stand the lowest point (the dangling feet) on z = 0 and centre the footprint
xs = [v.co.x for v in moth.data.vertices]
ys = [v.co.y for v in moth.data.vertices]
zs = [v.co.z for v in moth.data.vertices]
SHIFT = Vector((-(min(xs) + max(xs)) / 2, -(min(ys) + max(ys)) / 2, -min(zs)))
for v in moth.data.vertices:
    v.co += SHIFT


def at(p) -> Vector:
    return Vector(p) + SHIFT


# ── Rig ──

bones = [
    ("root", at((0, 0, 0)), at((0, 0, 0.05)), None),
    ("body", at((0, 0.0, ZC)), at((0, THORAX_Y - 0.06, ZC)), "root"),
    ("head", at((0, THORAX_Y - 0.06, ZC)), at((0, THORAX_Y - 0.11, ZC)), "body"),
    ("abdomen", at((0, -0.005, ZC - 0.004)), at((0, 0.2, ZC - 0.034)), "body"),
]
for s, side in ((1, "L"), (-1, "R")):
    fr = FORE_ROOT * Vector((s, 1, 1))
    hr = HIND_ROOT * Vector((s, 1, 1))
    bones.append((f"fore_{side}", at(fr), at(fr + Vector((s * 0.2, 0.0, 0.0))), "body"))
    bones.append((f"hind_{side}", at(hr), at(hr + Vector((s * 0.14, 0.04, 0.0))), "body"))
arm = gab.armature("duskmoth_rig", bones)
modifier = moth.modifiers.new("Armature", "ARMATURE")
modifier.object = arm
moth.parent = arm

# ── The flap cycle ('walk'): 10 frames at 30 fps ──

FRAMES = 10
FPS = bpy.context.scene.render.fps
UP_DEG, DOWN_DEG = 52.0, -38.0      # forewing elevation at the top and bottom of the stroke
DOWN_SHARE = 0.42                   # the downstroke takes this share of the cycle; the upstroke the rest


def stroke(p: float) -> float:
    """Wing elevation (degrees) at cycle phase p: top at 0, a quick downstroke to the bottom, a slower
    upstroke back, eased at both turns."""
    p %= 1.0
    if p < DOWN_SHARE:
        u = p / DOWN_SHARE
        return UP_DEG + (DOWN_DEG - UP_DEG) * (0.5 - 0.5 * math.cos(math.pi * u))
    u = (p - DOWN_SHARE) / (1 - DOWN_SHARE)
    return DOWN_DEG + (UP_DEG - DOWN_DEG) * (0.5 - 0.5 * math.cos(math.pi * u))


action = bpy.data.actions.new("walk")
arm.animation_data_create()
arm.animation_data.action = action
pose = arm.pose.bones
_last = {}


def key(pb, frame: int, rot: Matrix, loc=None) -> None:
    rest = pb.bone.matrix_local.to_3x3()
    q = (rest.inverted() @ rot @ rest).to_quaternion()
    if pb.name in _last:
        q.make_compatible(_last[pb.name])
    _last[pb.name] = q.copy()
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = q
    pb.keyframe_insert("rotation_quaternion", frame=frame)
    if loc is not None:
        pb.location = rest.inverted() @ Vector(loc)
        pb.keyframe_insert("location", frame=frame)


REST_FORE = 10.0   # the wings' modelled dihedral, which the stroke replaces
REST_HIND = 6.0
for frame in range(FRAMES + 1):
    ph = frame / FRAMES
    fore = stroke(ph) - REST_FORE
    hind = 0.8 * stroke(ph - 0.1) - REST_HIND
    # the body rises through the downstroke and sinks through the upstroke; it pitches nose-up a little
    # as the wings come down
    lift = 0.018 * math.sin(2 * math.pi * (ph - 0.12))
    pitch = math.radians(5.0) * math.sin(2 * math.pi * (ph - 0.2))
    key(pose["root"], frame, Matrix.Identity(3))
    key(pose["body"], frame, Matrix.Rotation(pitch, 3, "X"), (0.0, 0.0, lift))
    key(pose["head"], frame, Matrix.Rotation(-0.6 * pitch, 3, "X"))
    key(pose["abdomen"], frame, Matrix.Rotation(math.radians(7.0) * math.sin(2 * math.pi * (ph - 0.35)), 3, "X"))
    for s, side in ((1, "L"), (-1, "R")):
        # elevation about the body's long axis; the forewing also twists its leading edge down on the
        # downstroke
        twist = math.radians(8.0) * math.cos(2 * math.pi * ph)
        key(pose[f"fore_{side}"], frame,
            Matrix.Rotation(math.radians(-s * fore), 3, "Y") @ Matrix.Rotation(twist, 3, "X"))
        key(pose[f"hind_{side}"], frame, Matrix.Rotation(math.radians(-s * hind), 3, "Y"))

track = arm.animation_data.nla_tracks.new()
track.name = "walk"
track.strips.new("walk", 0, action)
arm.animation_data.action = None
for pb in pose:
    pb.rotation_quaternion = (1, 0, 0, 0)
    pb.location = (0, 0, 0)
bpy.context.scene.frame_start = 0
bpy.context.scene.frame_end = FRAMES

# A flier's feet never touch the road, so any speed would do; the cycle is made for the Duskmoth's design
# speed (1.5 tiles a second in game, design 2.4), at which it plays as authored: three flaps a second.
STRIDE = 1.5

if POSE_FRAME >= 0:
    arm.animation_data.action = action
    for t in list(arm.animation_data.nla_tracks):
        arm.animation_data.nla_tracks.remove(t)
    if hasattr(arm.animation_data, "action_slot") and action.slots:
        arm.animation_data.action_slot = action.slots[0]
    bpy.context.scene.frame_set(POSE_FRAME)
    gab.select_only(moth)
    bpy.ops.object.modifier_apply(modifier="Armature")
    moth.parent = None
    bpy.data.objects.remove(arm)
    bpy.data.actions.remove(action)

xs = [v.co.x for v in moth.data.vertices]
ys = [v.co.y for v in moth.data.vertices]
zs = [v.co.z for v in moth.data.vertices]
print(f"duskmoth: {gab.triangles(moth)} triangles; span {max(xs) - min(xs):.3f} x long {max(ys) - min(ys):.3f} x "
      f"tall {max(zs) - min(zs):.3f} (lowest z {min(zs):.4f}); flap {FRAMES} frames at {FPS} fps "
      f"({FPS / FRAMES:.1f} flaps/s); stride {STRIDE:.3f} game units/s at the game's {GAME_SCALE}x scale")
