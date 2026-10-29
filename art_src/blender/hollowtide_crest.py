"""The Hollowtide Crest: the final boss of Wickhollow.

A crowned pumpkin lord, built to read from the strategy camera as a broad, regal
triangle rather than a pumpkin with a hat:
- a ribbed pumpkin head with a carved, glowing face, tipped back 20 degrees so the face
  looks up at the 56-degree camera, under an imperial crown: a gold band of four tall
  gem-tipped points and four short ones flaring out past the head, a purple velvet
  cap inside it, and two crossing gold arches meeting at the stem, which rises
  through them into a spiral hook;
- a high crimson collar swept up into two peaks behind the ears, ribbed, with a gold
  edge and a second gold trim;
- gourd-shell pauldrons (dark violet, ribbed, gold-rimmed, two bone thorns each) over
  a two-layered fur mantle of spiky tufts;
- a long tattered cloak with deep lit folds, a gold hem band and a gold crown sigil;
- a chest of woven vines glowing from inside, vine arms with chunky forearms and gold
  bracers (the right hand carries a crook sceptre with a caged violet lantern, the
  left is an open bone-white claw), and long gnarled root legs with bark ridges, a
  contrasting root strand and moss.

Rigged with 26 bones and a looping 30-frame 'walk': a heavy stride with long double
support, a drop on each footfall, hips and shoulders swaying over the standing leg, a
head that nods late, a stem and a mantle (with the pauldrons and collar) that dip and
settle a frame after each footfall, a cloak rippling in two rows of bones, and a
sceptre and lantern held steady in world space (their parents' rotations are
cancelled every frame).

Blender Z-up, front faces -Y, pivot between the feet. Build:
  godot-agent asset blender . art_src/blender/hollowtide_crest.py \
      --to res://models/creeps/hollowtide_crest.glb --seed 1 --review --no-import

Params:
  leaves=1   add two modelled pumpkin leaves on the stem (off by default: they read as
             pale noise inside the crown from the game camera)
  core=0.6   emission strength of the lantern's violet core
  pose=N     bake walk frame N into the mesh and drop the rig (review sheets only)
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import tessellate_polygon

import gab

rng = gab.rng
TAU = math.tau

# Project palette (palettes/hollow.gpl).
PAL = {
    "pumpkin": "#d9772b", "pumpkin_dark": "#a8521e", "pumpkin_deep": "#b5541f",
    "glow_orange": "#ffb040", "glow_yellow": "#ffd860", "glow_pale": "#ffef7a",
    "stem": "#5a6b2e", "leaf_deep": "#3f7a2e", "needle_deep": "#1d4528", "needle": "#2f5f3e",
    "leaf_green": "#5a8a3a", "leaf_bright": "#7fb444", "leaf_tip": "#c3e070",
    "bark": "#5b3a29", "leg": "#3e2a1e", "wood_dark": "#4e3423", "wood": "#7a5534",
    "hide": "#6b4a34", "hide_dark": "#4a3324", "spike": "#d8c8a8",
    "gold": "#e0b040", "bronze": "#b07a3a", "autumn_tip": "#f6d070",
    "shell": "#4a2f5a", "shell_light": "#6e4a82", "shell_dark": "#2a1e24",
    "cap": "#b8432f", "iron": "#4a4d55", "iron_dark": "#3a3c42", "iron_light": "#7a7e88",
    "glow_purple": "#b070ff", "rune": "#d0a0ff",
}


def col(name, k=1.0):
    c = gab.rgb(PAL.get(name, name))
    return (c[0] * k, c[1] * k, c[2] * k)


def lerp3(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


# ══ Proportions ══
# Round 2 re-proportions the Crest for the 56-degree camera: a smaller head sunk between
# broad pauldrons, the body 5 cm higher on longer legs.
UP = 0.05
HX, HY, HZ = 0.0, -0.025, 0.625     # pumpkin head centre
HR, HH = 0.23, 0.17                 # radius, half height
FS = 1.05                           # the carved face, scaled with the head
# The head, stem and crown tip back 20 degrees about the neck so the carved face turns
# up toward the 56-degree strategy camera (the tilted-head trick); the crown leans 4
# degrees forward on the head, so it ends up 16 degrees back.
NECK = Vector((HX, HY, HZ - HH))
HEAD_TILT = Matrix.Translation(NECK) @ Matrix.Rotation(math.radians(-20), 4, "X") @ Matrix.Translation(-NECK)
LOBES = 8
TY = 0.03                           # torso centre (y)
TORSO = [(0.255, 0.085), (0.28, 0.135), (0.33, 0.165), (0.39, 0.178), (0.46, 0.2), (0.52, 0.215), (0.57, 0.17)]
TSY = 0.8
ARM_R = [(-0.235, 0.035, 0.505), (-0.315, 0.045, 0.46), (-0.37, 0.025, 0.395), (-0.395, -0.05, 0.355),
         (-0.41, -0.115, 0.34)]
ARM_L = [(0.235, 0.035, 0.505), (0.315, 0.045, 0.46), (0.365, 0.02, 0.4), (0.385, -0.06, 0.38),
         (0.39, -0.13, 0.375)]
STAFF_AXIS = Vector((-0.428, -0.148, 0.0))
GRIP = 0.34
# Legs: hip, knee, ankle, foot base (left; the right mirrors x)
LEG = [Vector((0.115, 0.03, 0.37)), Vector((0.155, -0.045, 0.21)), Vector((0.16, -0.01, 0.075)),
       Vector((0.16, -0.015, 0.042))]
HOOK = Vector((-0.548, -0.158, 0.87))
# Crown frame: its base ring sits on the head, tilted a little back and to one side.
CROWN_Z = HZ + HH - 0.052
CROWN_M = (Matrix.Translation((HX + 0.004, HY + 0.01, CROWN_Z)) @ Matrix.Rotation(math.radians(-7), 4, "Y")
           @ Matrix.Rotation(math.radians(4), 4, "X"))
CR0, CR1, CZT = 0.155, 0.168, 0.05
FACE_LIGHT = HEAD_TILT @ Vector((0.0, HY - HR - 0.02, HZ - 0.045))


def mirror(v, sign):
    return Vector((v.x * sign, v.y, v.z))


def torso_r(z):
    if z <= TORSO[0][0]:
        return TORSO[0][1]
    for (z0, r0), (z1, r1) in zip(TORSO, TORSO[1:]):
        if z <= z1:
            return lerp(r0, r1, (z - z0) / (z1 - z0))
    return TORSO[-1][1]


def face_spill(c, co, strength=0.35):
    """Warm light from the carved face, painted onto what sits just below and in
    front of it, so the glow reads on the chest and fur in a dark hollow."""
    d = (co - FACE_LIGHT).length
    front = smoothstep(0.05, -0.2, co.y)
    t = strength * smoothstep(0.3, 0.06, d) * front
    return lerp3(c, col("glow_orange", 0.9), t)


# ── Materials ──

PAINTED = gab.painted()
FACE = gab.glow("creep_face_crest", "#ffef7a", 2.4)
# Blue clips first under filmic tonemapping and the hue slides to lilac, so the core
# glows at a strength that keeps the violet (measured in Godot: 1.6 renders as
# (225, 160, 255), 0.6 as about (185, 120, 245), close to glow_purple itself).
CORE = gab.glow("creep_lantern_crest", "#b070ff", gab.param("core", 0.6))
WALL_TMP = gab.material("cutwall_tmp")


# ── Mesh helpers ──

def build(name, verts, faces, uvs=None):
    return gab.mesh_object(name, verts, faces, uvs)


def fix_normals(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return obj


def set_uvs(obj, fn):
    mesh = obj.data
    layer = mesh.uv_layers.get("UVMap") or mesh.uv_layers.new(name="UVMap")
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            layer.data[li].uv = fn(mesh.vertices[mesh.loops[li].vertex_index].co)
    return obj


def jitter(center, amount):
    """Per-face brightness variation hashed from the face position and the seed, so
    it does not depend on face order (the boolean's output order is not stable)."""
    h = math.sin(center.x * 127.1 + center.y * 311.7 + center.z * 74.7 + gab.seed * 13.37) * 43758.5453
    return 1.0 + amount * (2 * (h - math.floor(h)) - 1)


def paint(obj, fn, pattern="plain", facet=0.05, ao=0.3, ao_h=0.2, faces=None, index=False):
    """Vertex colours from fn(co, normal) -> linear rgb (fn(co, normal, vertex index)
    with `index`), with per-face brightness jitter and ground darkening; the alpha
    channel selects the painted pattern."""
    mesh = obj.data
    layer = gab._color_layer(mesh)
    alpha = (gab.PATTERNS.index(pattern) + 0.5) / 16
    chosen = set(faces) if faces is not None else None
    for poly in mesh.polygons:
        if chosen is not None and poly.index not in chosen:
            continue
        shade = jitter(poly.center, facet)
        n = poly.normal
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index
            co = mesh.vertices[vi].co
            c = fn(co, n, vi) if index else fn(co, n)
            dark = 1.0 - ao * max(0.0, 1.0 - co.z / ao_h) if ao_h > 0 else 1.0
            layer.data[li].color = (*(max(0.0, min(1.0, ch * shade * dark)) for ch in c), alpha)
    return obj


def flat_color(name, k=1.0):
    c = col(name, k)
    return lambda co, n: c


def frames(pts, up=None):
    n = len(pts)
    tans = []
    for i in range(n):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        tans.append((b - a).normalized())
    ref = Vector(up) if up is not None else (Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((0, -1, 0)))
    nrm = (ref - tans[0] * ref.dot(tans[0])).normalized()
    out = []
    for t in tans:
        nrm = (nrm - t * nrm.dot(t)).normalized()
        out.append((t, nrm, t.cross(nrm)))
    return out


def arclen(pts):
    d = [0.0]
    for i in range(1, len(pts)):
        d.append(d[-1] + (pts[i] - pts[i - 1]).length)
    return d


def spline(ctrl, per=4):
    """Catmull-Rom through the control points, `per` samples per span."""
    p = [Vector(c) for c in ctrl]
    out = []
    for i in range(len(p) - 1):
        p0 = p[i - 1] if i > 0 else p[i] * 2 - p[i + 1]
        p1, p2 = p[i], p[i + 1]
        p3 = p[i + 2] if i + 2 < len(p) else p[i + 1] * 2 - p[i]
        for s in range(per):
            t = s / per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(p[-1])
    return out


def tube(name, pts, radius, sides=6, caps=("flat", "point"), noise=0.0, twist=0.0, up=None,
         squash=1.0, closed=False, wobble=0.0, ridges=0.0):
    """A tube swept along pts; radius is a number, a list, or fn(s) of arc fraction s.
    `ridges` pushes even vertices of each ring out and odd ones in (bark ridges that
    follow the twist). Vertex k of ring i has index i * sides + k. UVs in metres: u
    around, v along, so bark streaks run down limbs."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    dist = arclen(pts)
    total = dist[-1] or 1.0
    if callable(radius):
        radii = [radius(d / total) for d in dist]
    elif isinstance(radius, (list, tuple)):
        radii = list(radius)
    else:
        radii = [radius] * n
    fr = frames(pts, up)
    verts, faces, uvs = [], [], []
    for i in range(n):
        t, nrm, bi = fr[i]
        r = radii[i]
        shift = Vector((rng.uniform(-wobble, wobble), rng.uniform(-wobble, wobble), 0)) if wobble else Vector()
        for k in range(sides):
            a = TAU * k / sides + twist * i
            rr = r * (1 + rng.uniform(-noise, noise)) if noise else r
            if ridges:
                rr *= 1 + ridges if k % 2 == 0 else 1 - 0.6 * ridges
            verts.append(pts[i] + shift + (nrm * math.cos(a) + bi * math.sin(a) * squash) * rr)
    spans = n if closed else n - 1
    for i in range(spans):
        j = (i + 1) % n
        circ = TAU * (radii[i] + radii[j]) / 2
        v0, v1 = dist[i], dist[i] + (pts[j] - pts[i]).length
        for k in range(sides):
            a0, a1 = i * sides + k, i * sides + (k + 1) % sides
            b0, b1 = j * sides + k, j * sides + (k + 1) % sides
            faces.append((a0, a1, b1, b0))
            u0, u1 = circ * k / sides, circ * (k + 1) / sides
            uvs.append([(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
    if not closed:
        for i, mode, rev in ((0, caps[0], True), (n - 1, caps[1], False)):
            ring = list(range(i * sides, i * sides + sides))
            if mode == "flat":
                faces.append(tuple(ring[::-1] if rev else ring))
                uvs.append([(0.03 * math.cos(TAU * k / sides), 0.03 * math.sin(TAU * k / sides))
                            for k in (range(sides - 1, -1, -1) if rev else range(sides))])
            elif mode == "point":
                tip = pts[i] + fr[i][0] * (radii[i] * 1.3) * (-1 if rev else 1)
                verts.append(tip)
                ti = len(verts) - 1
                for k in range(sides):
                    a0, a1 = ring[k], ring[(k + 1) % sides]
                    faces.append((a1, a0, ti) if rev else (a0, a1, ti))
                    uvs.append([(0, 0), (0.02, 0), (0.01, 0.02)])
    return build(name, verts, faces, uvs)


def lathe(name, rings, sides, center=(0.0, 0.0), sy=1.0, bottom=None, top=None, rfn=None, phase=0.0):
    """A surface of revolution about Z: rings [(z, r)] bottom to top, closed by pole
    vertices at z=bottom / z=top when given; rfn(theta, z) scales the radius."""
    cx, cy = center
    verts, faces, uvs = [], [], []
    for z, r in rings:
        for k in range(sides):
            th = TAU * k / sides + phase
            rr = r * (rfn(th, z) if rfn else 1.0)
            verts.append((cx + rr * math.sin(th), cy - rr * math.cos(th) * sy, z))
    nr = len(rings)
    for i in range(nr - 1):
        for k in range(sides):
            a0, a1 = i * sides + k, i * sides + (k + 1) % sides
            faces.append((a0, a1, a1 + sides, a0 + sides))
            r0 = rings[i][1]
            uvs.append([(TAU * r0 * k / sides, rings[i][0]), (TAU * r0 * (k + 1) / sides, rings[i][0]),
                        (TAU * r0 * (k + 1) / sides, rings[i + 1][0]), (TAU * r0 * k / sides, rings[i + 1][0])])
    if bottom is not None:
        verts.append((cx, cy, bottom))
        p = len(verts) - 1
        for k in range(sides):
            faces.append((p, (k + 1) % sides, k))
            uvs.append([(0, 0), (0.02, 0.02), (0, 0.02)])
    if top is not None:
        verts.append((cx, cy, top))
        p = len(verts) - 1
        base = (nr - 1) * sides
        for k in range(sides):
            faces.append((base + k, base + (k + 1) % sides, p))
            uvs.append([(0, 0), (0.02, 0), (0.01, 0.02)])
    obj = build(name, verts, faces, uvs)
    if bottom is not None and top is not None:
        fix_normals(obj)
    return obj


def blob(name, center, radii, u=8, v=5, noise=0.0):
    """A lumpy ellipsoid: u segments around, v bands from pole to pole. Built by hand
    rather than with bmesh's uv sphere, whose face order changes from run to run."""
    cx, cy, cz = center
    pts = [(0.0, 0.0, -1.0)]
    for i in range(1, v):
        phi = math.pi * i / v
        pts += [(math.sin(phi) * math.cos(TAU * k / u), math.sin(phi) * math.sin(TAU * k / u), -math.cos(phi))
                for k in range(u)]
    pts.append((0.0, 0.0, 1.0))
    verts = []
    for x, y, z in pts:
        k = 1 + rng.uniform(-noise, noise) if noise else 1.0
        verts.append((cx + x * radii[0] * k, cy + y * radii[1] * k, cz + z * radii[2] * k))
    top = len(pts) - 1
    faces = [(0, 1 + (k + 1) % u, 1 + k) for k in range(u)]
    for i in range(v - 2):
        a, b = 1 + i * u, 1 + (i + 1) * u
        faces += [(a + k, a + (k + 1) % u, b + (k + 1) % u, b + k) for k in range(u)]
    last = 1 + (v - 2) * u
    faces += [(last + k, last + (k + 1) % u, top) for k in range(u)]
    obj = build(name, verts, faces)
    fix_normals(obj)
    gab.uv_box(obj)
    return obj


def gem(name, center, r, h, sides=4, phase=0.0):
    """A cut gem: a bipyramid, taller below than above."""
    cx, cy, cz = center
    verts = [(cx + r * math.sin(TAU * k / sides + phase), cy - r * math.cos(TAU * k / sides + phase), cz)
             for k in range(sides)]
    verts += [(cx, cy, cz + h * 0.45), (cx, cy, cz - h * 0.55)]
    faces = []
    for k in range(sides):
        faces.append((k, (k + 1) % sides, sides))
        faces.append(((k + 1) % sides, k, sides + 1))
    obj = build(name, verts, faces)
    fix_normals(obj)
    gab.uv_box(obj)
    return obj


def sheet(name, grid, thick, outward):
    """A double-sided cloth sheet from a grid of outer points (rows top to bottom):
    outer and inner skins plus rims. Returns (obj, tags) with tags[face] =
    ('out'|'in'|'rim', row, col)."""
    rows, cols = len(grid), len(grid[0])
    P = [[Vector(p) for p in row] for row in grid]

    def normal(i, j):
        a = P[i][min(j + 1, cols - 1)] - P[i][max(j - 1, 0)]
        b = P[min(i + 1, rows - 1)][j] - P[max(i - 1, 0)][j]
        nv = a.cross(b)
        if nv.length < 1e-9:
            nv = outward(P[i][j])
        nv.normalize()
        return nv if nv.dot(outward(P[i][j])) >= 0 else -nv

    verts = [P[i][j] for i in range(rows) for j in range(cols)]
    verts += [P[i][j] - normal(i, j) * thick for i in range(rows) for j in range(cols)]
    off = rows * cols

    def idx(i, j, s=0):
        return s * off + i * cols + j

    faces, tags, wants = [], [], []
    for i in range(rows - 1):
        for j in range(cols - 1):
            faces.append((idx(i, j), idx(i, j + 1), idx(i + 1, j + 1), idx(i + 1, j)))
            tags.append(("out", i, j))
            wants.append(outward((P[i][j] + P[i + 1][j + 1]) / 2))
    for i in range(rows - 1):
        for j in range(cols - 1):
            faces.append((idx(i, j, 1), idx(i + 1, j, 1), idx(i + 1, j + 1, 1), idx(i, j + 1, 1)))
            tags.append(("in", i, j))
            wants.append(-outward((P[i][j] + P[i + 1][j + 1]) / 2))
    for j in range(cols - 1):
        for i, other in ((0, 1), (rows - 1, rows - 2)):
            faces.append((idx(i, j), idx(i, j, 1), idx(i, j + 1, 1), idx(i, j + 1)))
            tags.append(("rim", i, j))
            wants.append(P[i][j] - P[other][j])
    for i in range(rows - 1):
        for j, other in ((0, 1), (cols - 1, cols - 2)):
            faces.append((idx(i, j), idx(i + 1, j), idx(i + 1, j, 1), idx(i, j, 1)))
            tags.append(("rim", i, j))
            wants.append(P[i][j] - P[i][other])
    obj = build(name, verts, faces)
    # Orient every face away from the cloth: outer skin outward, inner skin inward,
    # rims away from the sheet.
    mesh = obj.data
    for poly, want in zip(mesh.polygons, wants):
        if poly.normal.dot(want) < 0:
            poly.flip()
    mesh.update()
    return obj, tags


def faces_where(tags, pred):
    return [k for k, t in enumerate(tags) if pred(t)]


def drop_faces(obj, indices):
    """Deletes faces nobody sees (inner skins against the body), keeping the rest's
    colours and UVs."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in sorted(set(indices))], context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return obj


def transform(objs, m):
    for o in objs:
        o.data.transform(m)
        o.data.update()


# ── Rig weights ──

def bind(obj, fn):
    """Vertex groups from fn(co) -> {bone: weight}."""
    groups = {}
    for v in obj.data.vertices:
        w = fn(v.co)
        total = sum(w.values()) or 1.0
        for bone, x in w.items():
            if x / total <= 1e-3:
                continue
            g = groups.get(bone)
            if g is None:
                g = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
                groups[bone] = g
            g.add([v.index], x / total, "REPLACE")
    return obj


def rigid(bone):
    return lambda co: {bone: 1.0}


def chain(segs, blend=0.035):
    """Weights along a bone chain [(bone, a, b)], blended across each joint."""
    segs = [(nm, Vector(a), Vector(b)) for nm, a, b in segs]
    lens = [(b - a).length for _, a, b in segs]
    joints = []
    acc = 0.0
    for ln in lens[:-1]:
        acc += ln
        joints.append(acc)

    def fn(co):
        best, acc2 = None, 0.0
        for i, (_, a, b) in enumerate(segs):
            ab = b - a
            t = max(0.0, min(1.0, (co - a).dot(ab) / ab.length_squared))
            d = (a + ab * t - co).length
            s = acc2 + t * lens[i]
            if best is None or d < best[0] - 1e-6:
                best = (d, s)
            acc2 += lens[i]
        s = best[1]
        ts = [smoothstep(j - blend, j + blend, s) for j in joints]
        w = {}
        for i, (nm, _, _) in enumerate(segs):
            x = 1.0
            if i > 0:
                x *= ts[i - 1]
            if i < len(segs) - 1:
                x *= 1 - ts[i]
            w[nm] = w.get(nm, 0.0) + x
        return w
    return fn


PARTS = []
LEAVES = gab.param("leaves", 0)


def part(obj, mat, weights, smooth=None):
    gab.assign(obj, mat) if mat is not None else None
    if smooth is not None:
        gab.smooth(obj, smooth)
    else:
        gab.flat(obj)
    bind(obj, weights)
    PARTS.append(obj)
    return obj


# ══ Head ══

def lobe_factor(theta, amp, depth=0.1):
    f = LOBES * theta / TAU
    l = abs(math.cos(math.pi * f))
    li = int(math.floor(f + 0.5)) % LOBES
    return 1 - depth + depth * amp[li] * l ** 0.5


def make_head():
    # Ten rings from pole to pole, less the lowest (inside the mantle) and the highest
    # (under the crown's velvet cap).
    per = 4
    ring_t = [(i + 1) / 11 for i in range(1, 9)]
    rings = len(ring_t)
    seg = LOBES * per
    amp = [rng.uniform(0.75, 1.25) for _ in range(LOBES)]
    amp[0] = 1.1
    verts, faces, uvs = [], [], []
    for t in ring_t:
        phi = math.pi * t
        rho = HR * math.sin(phi) ** 0.7
        z = HZ - HH * math.cos(phi) - 0.07 * math.exp(-((1 - t) / 0.12) ** 2) + 0.028 * math.exp(-(t / 0.15) ** 2)
        for k in range(seg):
            th = TAU * k / seg
            r = rho * lobe_factor(th, amp)
            verts.append((HX + r * math.sin(th), HY - r * math.cos(th), z))
    for i in range(rings - 1):
        for k in range(seg):
            a0, a1 = i * seg + k, i * seg + (k + 1) % seg
            faces.append((a0, a1, a1 + seg, a0 + seg))
            z0, z1 = verts[a0][2], verts[a0 + seg][2]
            uvs.append([(HR * TAU * k / seg, z0), (HR * TAU * (k + 1) / seg, z0),
                        (HR * TAU * (k + 1) / seg, z1), (HR * TAU * k / seg, z1)])
    verts.append((HX, HY, HZ - HH + 0.028))
    bot = len(verts) - 1
    verts.append((HX, HY, HZ + HH - 0.07))
    top = len(verts) - 1
    last = (rings - 1) * seg
    for k in range(seg):
        faces.append((bot, (k + 1) % seg, k))
        uvs.append([(0, 0), (0.02, 0.02), (0, 0.02)])
        faces.append((last + k, last + (k + 1) % seg, top))
        uvs.append([(0, 0), (0.02, 0), (0.01, 0.02)])
    head = build("head", verts, faces, uvs)
    fix_normals(head)
    return head, amp


def face_shapes():
    """The carved face in (x, z) about the head centre, as seen from the front."""
    shapes = []
    for s in (1, -1):
        eye = [(0.04, 0.045), (0.085, 0.072), (0.125, 0.098), (0.158, 0.112), (0.152, 0.07),
               (0.135, 0.04), (0.105, 0.022), (0.07, 0.02), (0.045, 0.028)]
        eye = [(x * s, z) for x, z in eye]
        shapes.append(eye if s > 0 else eye[::-1])
    # Nose: a small notch pointing up.
    shapes.append([(-0.024, -0.03), (0.024, -0.03), (0.0, 0.006)])
    # Mouth: a wide crescent grin with jagged teeth.
    w = 0.175

    def zu(x):
        return -0.06 + 0.05 * (x / w) ** 2

    def zl(x):
        return -0.16 + 0.12 * (x / w) ** 2
    upper_teeth = [(-0.105, 0.022, 0.04), (-0.035, 0.02, 0.033), (0.04, 0.022, 0.042), (0.11, 0.02, 0.033)]
    lower_teeth = [(-0.07, 0.022, 0.044), (0.005, 0.024, 0.053), (0.08, 0.022, 0.04)]
    up = []
    xs = [-w + i * 0.025 for i in range(int(2 * w / 0.025) + 1)]
    for x in xs:
        tooth = next((t for t in upper_teeth if abs(x - t[0]) < t[1]), None)
        if tooth is None:
            up.append((x, zu(x)))
    for xt, hw, ln in upper_teeth:
        up.append((xt - hw, zu(xt - hw)))
        up.append((xt + rng.uniform(-0.004, 0.004), zu(xt) - ln * rng.uniform(0.85, 1.1)))
        up.append((xt + hw, zu(xt + hw)))
    up.sort(key=lambda p: p[0])
    lo = []
    for x in xs[1:-1]:
        tooth = next((t for t in lower_teeth if abs(x - t[0]) < t[1]), None)
        if tooth is None:
            lo.append((x, zl(x)))
    for xt, hw, ln in lower_teeth:
        lo.append((xt - hw, zl(xt - hw)))
        lo.append((xt + rng.uniform(-0.004, 0.004), zl(xt) + ln * rng.uniform(0.85, 1.1)))
        lo.append((xt + hw, zl(xt + hw)))
    lo.sort(key=lambda p: -p[0])
    shapes.append(up + lo)
    # The nose and grin sit a little higher than drawn, nearer the head's equator, so
    # the strategy camera sees the teeth rather than the underside of the head.
    lifts = [0.0, 0.0, 0.009, 0.02]
    return [[(x * FS, z * FS + dz) for x, z in s] for s, dz in zip(shapes, lifts)]


def make_cutter(shape, bvh, depth=0.042, lift=0.032):
    """A prism along rays from the head centre: from outside the rind to `depth`
    below it. Back cap = glow (material 1), sides = cut flesh (material 0)."""
    center = Vector((HX, HY + 0.02, HZ))
    tris = tessellate_polygon([[Vector((x, z, 0)) for x, z in shape]])
    n = len(shape)
    verts = []
    surf = []
    for x, z in shape:
        hit = bvh.ray_cast(Vector((x, HY - 1.0, HZ + z + lift)), Vector((0, 1, 0)))
        surf.append(hit[0] if hit[0] is not None else Vector((x, HY - HR, HZ + z + lift)))
    for s in surf:
        d = (s - center).normalized()
        verts.append(s - d * depth)
    for s in surf:
        d = (s - center).normalized()
        verts.append(s + d * 0.08)
    faces, mats = [], []
    for tri in tris:
        faces.append(tuple(tri))
        mats.append(1)
        faces.append(tuple(n + i for i in reversed(tri)))
        mats.append(0)
    for i in range(n):
        a, b = i, (i + 1) % n
        faces.append((a, b, b + n, a + n))
        mats.append(0)
    cut = build("cutter", verts, faces)
    cut.data.materials.append(WALL_TMP)
    cut.data.materials.append(FACE)
    for poly, m in zip(cut.data.polygons, mats):
        poly.material_index = m
    fix_normals(cut)
    return cut


def position_key(co):
    """A sortable number from a position, quantised to 0.1 mm (z, then y, then x)."""
    q = [round((c + 1.0) * 1e4) for c in (co.z, co.y, co.x)]
    return float(q[0] * 400000000 + q[1] * 20000 + q[2])


def canonical_order(obj):
    """The exact boolean is threaded and orders its output differently from run to
    run. Triangulate and rebuild the mesh with vertices and triangles sorted by
    position, each triangle starting at its lowest vertex, so the export is
    byte-for-byte repeatable."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    dupes = len(bm.verts) - len({position_key(v.co) for v in bm.verts})
    if dupes:
        print(f"godot-agent: {dupes} vertices share a position after the carve")
    bm.verts.sort(key=lambda v: position_key(v.co))
    bm.verts.index_update()
    uv = bm.loops.layers.uv.active
    tris = []
    for f in bm.faces:
        loops = list(f.loops)
        k = min(range(len(loops)), key=lambda i: loops[i].vert.index)
        loops = loops[k:] + loops[:k]
        tris.append((position_key(f.calc_center_median()) * 4 + f.material_index, [lp.vert.index for lp in loops],
                     [tuple(lp[uv].uv) for lp in loops], f.material_index))
    tris.sort(key=lambda t: (t[0], t[1]))
    verts = [v.co.copy() for v in bm.verts]
    bm.free()
    mats = list(obj.data.materials)
    mesh = bpy.data.meshes.new(obj.data.name)
    mesh.from_pydata(verts, [], [t[1] for t in tris])
    layer = mesh.uv_layers.new(name="UVMap")
    for poly, t in zip(mesh.polygons, tris):
        poly.material_index = t[3]
        for li, c in zip(poly.loop_indices, t[2]):
            layer.data[li].uv = c
    for m in mats:
        mesh.materials.append(m)
    mesh.update()
    old = obj.data
    obj.data = mesh
    bpy.data.meshes.remove(old)


def head_parts():
    first = len(PARTS)
    head, amp = make_head()
    head.data.materials.append(PAINTED)
    bvh = BVHTree.FromPolygons([v.co.copy() for v in head.data.vertices],
                               [p.vertices[:] for p in head.data.polygons])
    cutters = [make_cutter(s, bvh) for s in face_shapes()]
    cutter = gab.join(cutters, "cutter")
    mod = head.modifiers.new("carve", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    mod.material_mode = "TRANSFER"
    gab.apply_modifiers(head)
    bpy.data.objects.remove(cutter)
    canonical_order(head)
    names = [m.name for m in head.data.materials]
    i_wall, i_glow = names.index("cutwall_tmp"), names.index("creep_face_crest")
    i_paint = names.index("painted")
    walls = [p.index for p in head.data.polygons if p.material_index == i_wall]
    glows = [p.index for p in head.data.polygons if p.material_index == i_glow]
    skin = [p.index for p in head.data.polygons if p.material_index not in (i_wall, i_glow)]

    def skin_color(co, n):
        h = (co.z - (HZ - HH)) / (2 * HH)
        th = math.atan2(co.x - HX, -(co.y - HY))
        f = LOBES * th / TAU
        l = abs(math.cos(math.pi * f))
        c = lerp3(col("pumpkin_dark", 0.5), col("pumpkin_deep"), smoothstep(0.0, 0.55, h))
        c = lerp3(c, col("pumpkin", 1.08), smoothstep(0.45, 0.95, h) * 0.85)
        # Sheen on the upper lobes, dark grooves between them.
        c = lerp3(c, col("glow_orange", 0.95), smoothstep(0.55, 1.0, l) * smoothstep(0.5, 0.85, h) * 0.3)
        k = 0.55 + 0.45 * l ** 0.7
        # Warm light spilling from the carved face onto the rind around it.
        front = max(0.0, -(co.y - HY) / HR)
        spill = smoothstep(0.75, 0.98, front) * smoothstep(0.42, 0.62, h) * 0.18
        return lerp3(tuple(ch * k for ch in c), col("glow_orange"), spill)

    def wall_color(co, n):
        d = bvh.find_nearest(co)[3] or 0.0
        return lerp3(col("glow_orange", 0.85), col("glow_pale"), smoothstep(0.0, 0.04, d))

    paint(head, skin_color, gab.param("rind", "thatch"), facet=0.03, ao=0.0, faces=skin)
    paint(head, wall_color, "plain", facet=0.02, ao=0.0, faces=walls)
    paint(head, flat_color("glow_pale"), "plain", facet=0.0, ao=0.0, faces=glows)
    for i in walls:
        head.data.polygons[i].material_index = i_paint
    gab.smooth(head, 40)
    gab.select_only(head)
    bpy.ops.object.material_slot_remove_unused()
    bind(head, rigid("head"))
    PARTS.append(head)

    stem()
    if LEAVES:
        for th, roll in ((math.radians(155), -0.3), (math.radians(205), 0.3)):
            pumpkin_leaf(th, roll)
    crown()
    # Tip everything on the head back about the neck, face up toward the camera.
    transform(PARTS[first:], HEAD_TILT)


STEM_PTS = []


def stem():
    """A thick stalk rising through the crown's velvet cap and arches, curling into a
    spiral hook: the Crest's silhouette hook, tallest point of the model."""
    top = HZ + HH - 0.07
    d = Vector((0.8, 0.6, 0.0)).normalized()

    def at(a, z):
        return Vector((HX + d.x * a, HY + d.y * a, z))
    pts = [at(0.0, top - 0.012), at(0.004, top + 0.07), at(0.011, top + 0.145), at(0.022, top + 0.215)]
    cx, cz = 0.07, top + 0.232
    for i in range(1, 8):
        t = i / 7
        ang = math.pi - t * 1.42 * math.pi           # over the top and down the far side
        r = lerp(0.047, 0.029, t)
        pts.append(at(cx + r * math.cos(ang), cz + r * math.sin(ang)))
    dist = arclen(pts)
    # The stem above the crown's hub sways on its own bone (head at the hub, tail at
    # the top of the hook); below the hub the head holds it, so the arches stay put.
    hub_z = CROWN_Z + 0.16
    s_hub = next(dist[i] + (hub_z - pts[i].z) / (pts[i + 1].z - pts[i].z) * (dist[i + 1] - dist[i])
                 for i in range(len(pts) - 1) if pts[i + 1].z >= hub_z > pts[i].z) / dist[-1]
    STEM_PTS[:] = [HEAD_TILT @ at(0.012, hub_z), HEAD_TILT @ max(pts, key=lambda q: q.z)]

    def stem_w(co):
        i = min(range(len(pts)), key=lambda j: (pts[j] - co).length_squared)
        w = smoothstep(s_hub, s_hub + 0.22, dist[i] / dist[-1])
        return {"head": 1 - w, "stem": w}
    obj = tube("stem", pts, lambda s: lerp(0.045, 0.017, s ** 0.85), sides=7, caps=("flat", "point"), twist=0.3,
               noise=0.05)

    def stem_col(co, n):
        i = min(range(len(pts)), key=lambda j: (pts[j] - co).length_squared)
        s = dist[i] / dist[-1]
        c = lerp3(col("needle_deep", 0.8), col("stem", 1.0), smoothstep(0.2, 0.6, s))
        return lerp3(c, col("leaf_green", 0.9), smoothstep(0.7, 1.0, s) * 0.6)
    paint(obj, stem_col, "bark", ao=0.0, facet=0.04)
    part(obj, PAINTED, stem_w, smooth=60)


LEAF_SPOKES = [(0.0, 1.0, "tip"), (0.27, 0.8, "mid"), (0.52, 0.5, "sinus"), (0.78, 0.74, "mid"), (1.0, 0.88, "tip"),
               (1.47, 0.46, "sinus"), (1.9, 0.64, "tip"), (2.45, 0.3, "end")]


def pumpkin_leaf(th, roll, length=0.19, half=0.085):
    """A five-lobed pumpkin leaf, pleated along its veins, arching from the stem over
    the crown's low back rim at crown angle th and drooping down outside. Built in
    the crown's frame (before its tilt), so it follows the crown."""
    dh = Vector((math.sin(th), -math.cos(th), 0.0))
    side = Vector((math.cos(th), math.sin(th), 0.0))
    up = Vector((0, 0, 1))
    ctrl = [dh * r + up * z for r, z in ((0.118, 0.074), (0.158, 0.09), (0.19, 0.074), (0.215, 0.036),
                                           (0.236, -0.012), (0.25, -0.065), (0.256, -0.11))]
    path = spline(ctrl, per=3)
    dist = arclen(path)

    def along(x):
        """Point and tangent at arc length x from the attachment (extrapolated back)."""
        if x <= 0:
            t = (path[1] - path[0]).normalized()
            return path[0] + t * x, t
        for i in range(1, len(path)):
            if dist[i] >= x or i == len(path) - 1:
                f = (x - dist[i - 1]) / max(1e-9, dist[i] - dist[i - 1])
                t = (path[i] - path[i - 1]).normalized()
                return path[i - 1].lerp(path[i], min(f, 1.5)), t

    spokes = [(-a, r, k) for a, r, k in reversed(LEAF_SPOKES[1:])] + LEAF_SPOKES
    ns = len(spokes)
    verts, info, faces, wants = [], [], [], []
    for skin, lift in ((0, 0.0), (1, -0.004)):           # top skin, then the underside
        base = len(verts)
        for q, (a, rf, kind) in [(0.0, (0.0, 0.0, "c"))] + [(q, sp) for q in (0.5, 1.0) for sp in spokes]:
            lx = q * rf * length * math.cos(a)
            ly = q * rf * half * math.sin(a)
            p, t = along(lx)
            nrm = t.cross(side)
            if nrm.z < 0:
                nrm = -nrm
            fold = {"tip": 0.007, "sinus": -0.005}.get(kind, 0.0) * q
            h = fold + 0.9 * ly * ly + roll * ly + lift
            verts.append(p + side * ly + nrm * h)
            info.append((skin, kind, q, nrm, (lx, ly)))
            if q == 0.0:
                center_i = len(verts) - 1
        for sgm in range(ns - 1):
            i0, i1 = base + 1 + sgm, base + 2 + sgm
            o0, o1 = i0 + ns, i1 + ns
            for f in ((center_i, i0, i1), (i0, o0, o1, i1)):
                faces.append(f)
                n_avg = sum((info[v][3] for v in f), Vector())
                wants.append(n_avg if skin == 0 else -n_avg)
    uvs = [[(info[v][4][0] * 1.5, info[v][4][1] * 1.5) for v in f] for f in faces]
    leaf = build("pumpkin_leaf", verts, faces, uvs)
    for poly, want in zip(leaf.data.polygons, wants):
        if poly.normal.dot(want) < 0:
            poly.flip()
    leaf.data.update()
    # Petiole from the stem to the leaf.
    pet = tube("petiole", [dh * 0.012 + up * 0.03, dh * 0.06 + up * 0.08, ctrl[0] + up * 0.002],
               lambda s: lerp(0.012, 0.007, s), sides=4, caps=("flat", "flat"))
    paint(pet, lambda co, n: lerp3(col("needle_deep", 0.9), col("stem", 1.1), 0.5), "bark", ao=0.0)
    transform([leaf, pet], CROWN_M)
    placed = [CROWN_M @ v for v in verts]

    def leaf_col(co, n):
        i = min(range(len(placed)), key=lambda j: (placed[j] - co).length_squared)
        skin, kind, q = info[i][:3]
        if skin == 1:
            return lerp3(col("needle", 0.7), col("leaf_deep", 0.75), q)
        c = lerp3(col("leaf_deep", 0.7), col("leaf_green", 0.92), smoothstep(0.0, 0.7, q))
        c = lerp3(c, col("leaf_bright", 0.95), smoothstep(0.6, 1.0, q) * 0.45)
        if kind == "tip":
            c = lerp3(c, col("leaf_tip"), 0.25 + 0.2 * q)     # the pale vein down each lobe
        elif kind == "sinus":
            c = tuple(ch * 0.7 for ch in c)
        elif kind == "c":
            c = lerp3(c, col("leaf_tip", 0.9), 0.5)
        return c
    paint(leaf, leaf_col, "plain", facet=0.03, ao=0.0)
    part(leaf, PAINTED, rigid("head"), smooth=38)
    part(pet, PAINTED, rigid("head"), smooth=60)


ARCH_H = [(0.163, -0.012), (0.153, 0.024), (0.124, 0.06), (0.071, 0.085), (0.0, 0.095)]


def crown():
    """An imperial crown: eight point positions around a gold band (four tall gem-
    tipped points front, back and sides, four short knobbed ones between), flaring
    out so their tips break past the head from above; a purple velvet cap fills the
    band, and two gold arches cross over it from the tall points to a hub round the
    stem. From the strategy camera it reads as a gold cross in a gold ring."""
    n_pts, per = 8, 4
    seg = n_pts * per
    tall, short = 0.16, 0.09
    rows = [[], [], []]
    tips = []
    for k in range(seg + 1):
        kk = k % seg
        th = TAU * (kk - 2) / seg
        ph = kk % per
        pt = kk // per
        hp = tall if pt % 2 == 0 else short
        lift = {0: 0.004, 1: 0.15 * hp, 2: hp, 3: 0.15 * hp}[ph]
        rt = CR1 + 0.075 * lift / tall
        rows[0].append(Vector((CR0 * math.sin(th), -CR0 * math.cos(th), 0.0)))
        rows[1].append(Vector((CR1 * math.sin(th), -CR1 * math.cos(th), CZT)))
        rows[2].append(Vector((rt * math.sin(th), -rt * math.cos(th), CZT + lift)))
        if ph == 2 and k < seg:
            tips.append((rows[2][-1].copy(), pt % 2 == 0, th))

    def outward(p):
        return Vector((p.x, p.y, 0)).normalized()
    band, tags = sheet("crown", [rows[2], rows[1], rows[0]], 0.014, outward)
    ring = [Vector(((CR0 + 0.004) * math.sin(TAU * k / 12), -(CR0 + 0.004) * math.cos(TAU * k / 12), 0.004))
            for k in range(12)]
    gold_parts = [band, tube("crown_rim", ring, 0.013, sides=3, closed=True, up=(0, 0, 1))]
    gems = []
    for p, is_tall, th in tips:
        if is_tall:
            if abs(th) > 0.1:                  # the front point carries the big stone below instead
                gems.append(gem("crown_gem", p + Vector((0, 0, 0.024)), 0.026, 0.066, sides=4, phase=th))
            else:
                gold_parts.append(gem("crown_knob", p + Vector((0, 0, 0.014)), 0.017, 0.04, sides=4, phase=th))
        else:
            gold_parts.append(gem("crown_knob", p + Vector((0, 0, 0.012)), 0.016, 0.036, sides=4, phase=th))
    # The big front stone in a gold setting at the foot of the front point.
    front = Vector((0, -(CR1 + 0.012), 0.034))
    gold_parts.append(blob("crown_setting", front + Vector((0, 0.004, 0)), (0.036, 0.012, 0.04), u=6, v=4))
    stone = gem("crown_stone", (0, 0, 0), 0.028, 0.07, sides=6)
    stone.rotation_euler = (math.radians(90), 0, 0)
    stone.location = front + Vector((0, -0.01, 0.0))
    gab.apply_transform(stone)
    gems.append(stone)

    # Velvet cap, puffing up between the arches.
    def puff(th, z):
        return 1 + 0.08 * math.sin(2 * th) ** 2 * smoothstep(0.0, CZT, z)
    cap = lathe("crown_cap", [(0.004, CR0 - 0.006), (CZT + 0.012, CR1 - 0.024), (CZT + 0.062, 0.102)], 8,
                top=CZT + 0.084, rfn=puff)
    # Two crossing arches from the tall points' feet over the cap to a hub at the stem.
    arches = []
    for th in (0.0, math.pi / 2):
        dh = Vector((math.sin(th), -math.cos(th), 0.0))
        pts = [dh * r + Vector((0, 0, CZT + z)) for r, z in ARCH_H]
        pts += [-dh * r + Vector((0, 0, CZT + z)) for r, z in reversed(ARCH_H[:-1])]
        side = Vector((math.cos(th), math.sin(th), 0.0))
        arches.append(tube("crown_arch", pts, lambda s: 0.02 - 0.004 * math.sin(math.pi * s), sides=4,
                           caps=("flat", "flat"), up=tuple(side), squash=0.42))
    hz = CZT + 0.104
    hub = lathe("crown_hub", [(hz - 0.016, 0.03), (hz, 0.044), (hz + 0.014, 0.032)], 6, phase=math.pi / 6)
    gold_parts += arches + [hub]
    transform(gold_parts + gems + [cap], CROWN_M)

    def gold(co, n):
        h = smoothstep(CROWN_Z - 0.01, CROWN_Z + 0.19, co.z)
        return lerp3(col("gold", 0.68), col("gold", 1.15), h)
    paint(band, gold, "gold", facet=0.04, ao=0.0, faces=faces_where(tags, lambda t: t[0] != "in"))
    paint(band, lambda co, n: lerp3(col("gold", 0.6), col("gold", 0.92), smoothstep(CROWN_Z, CROWN_Z + 0.17, co.z)),
          "gold", facet=0.03, ao=0.0, faces=faces_where(tags, lambda t: t[0] == "in"))
    for o in gold_parts[1:]:
        paint(o, gold, "gold", facet=0.05, ao=0.0)
        gab.uv_box(o)
    for o in arches + [hub]:
        paint(o, lambda co, n: lerp3(col("gold", 0.62), col("gold", 1.12), 0.35 + 0.65 * max(0.0, n.z)), "gold",
              facet=0.03, ao=0.0)
    gab.uv_box(band)
    gab.uv_box(cap)

    n_cap = len(cap.data.vertices) - 1           # the last vertex is the top pole
    cap_pts = {tuple(round(c, 5) for c in v.co): (i % 8 if i < n_cap else -1) for i, v in enumerate(cap.data.vertices)}

    def velvet(co, n):
        # Four cushions between the arches: lit where they puff up, dark in the
        # creases the arches press into the velvet.
        h = smoothstep(CROWN_Z + 0.03, CROWN_Z + CZT + 0.09, co.z)
        c = lerp3(col("shell_dark", 0.8), col("shell", 1.05), h)
        c = lerp3(c, col("shell_light", 1.15), smoothstep(0.5, 0.95, n.z) * h * 0.45)
        k = cap_pts.get(tuple(round(x, 5) for x in co), -1)
        cushion = 0.95 if k < 0 else (1.12 if k % 2 == 1 else 0.62)
        return tuple(ch * cushion for ch in c)
    paint(cap, velvet, "cloth", facet=0.04, ao=0.0)
    for g in gems:
        paint(g, lambda co, n: col("glow_purple", 0.3), "plain", facet=0.0, ao=0.0)
    for o in gold_parts:
        part(o, PAINTED, rigid("head"), smooth=35)
    part(cap, PAINTED, rigid("head"), smooth=50)
    for g in gems:
        part(g, CORE, rigid("head"))


# ══ Body ══

def body_w(co):
    return {"pelvis": 1 - smoothstep(0.36, 0.45, co.z), "spine": smoothstep(0.36, 0.45, co.z)}


def body_parts():
    # Torso of woven vines, lit from inside along a seam down the front.
    torso = lathe("torso", TORSO, 8, center=(0, TY), sy=TSY, bottom=0.24, top=0.59,
                  rfn=lambda th, z: 1 + 0.04 * math.sin(5 * th + z * 30))

    def torso_col(co, n):
        c = lerp3(col("needle_deep", 0.7), col("stem", 0.9), smoothstep(0.25, 0.5, co.z))
        front = max(0.0, -(co.y - TY) / (torso_r(co.z) * TSY + 1e-6))
        seam = smoothstep(0.8, 1.0, front) * smoothstep(0.28, 0.36, co.z) * smoothstep(0.58, 0.5, co.z)
        return lerp3(c, col("glow_orange", 0.95), 0.75 * seam)
    paint(torso, torso_col, "bark", ao=0.2, ao_h=0.3)
    part(torso, PAINTED, body_w, smooth=60)

    # Two vines wrapping the chest, crossing in front.
    def wrap(th, z, lift=0.016):
        r = torso_r(z) + lift
        return Vector((r * math.sin(th), TY - r * math.cos(th) * TSY, z))
    paths = []
    for th0, sweep, z0, z1 in ((-1.95, 3.0, 0.345, 0.53), (1.95, -3.0, 0.345, 0.53)):
        paths.append([wrap(th0 + sweep * j / 7, lerp(z0, z1, j / 7)) for j in range(8)])
    for pts in paths:
        v = tube("chest_vine", pts, lambda s: 0.03 * (1 - 0.4 * abs(s - 0.5) * 2), sides=5, caps=("point", "point"),
                 noise=0.08)
        paint(v, lambda co, n: face_spill(lerp3(col("leaf_deep", 0.6), col("leaf_green", 1.0),
                                                smoothstep(0.3, 0.5, co.z)), co, 0.45),
              "bark", ao=0.15, ao_h=0.3)
        part(v, PAINTED, body_w, smooth=60)

    # Belt with a gold buckle.
    zb = 0.34
    rb = torso_r(zb) + 0.012
    ring = [Vector((rb * math.sin(TAU * k / 12), TY - rb * TSY * math.cos(TAU * k / 12), zb)) for k in range(12)]
    belt = tube("belt", ring, 0.028, sides=4, closed=True, up=(0, 0, 1), squash=0.45)
    paint(belt, lambda co, n: lerp3(col("hide_dark", 0.8), col("hide"), 0.5 + 0.5 * n.z), "planks", ao=0.0)
    part(belt, PAINTED, rigid("pelvis"), smooth=None)
    bfront = Vector((0, TY - rb * TSY - 0.012, zb))
    buckle = blob("buckle", bfront, (0.04, 0.014, 0.034), u=6, v=4)
    paint(buckle, lambda co, n: lerp3(col("bronze"), col("gold", 1.1), smoothstep(zb - 0.03, zb + 0.03, co.z)), "gold",
          ao=0.0)
    part(buckle, PAINTED, rigid("pelvis"), smooth=None)
    bgem = gem("buckle_gem", (0, 0, 0), 0.016, 0.038, sides=4, phase=math.pi / 4)
    bgem.rotation_euler = (math.radians(90), 0, 0)
    bgem.location = bfront + Vector((0, -0.016, 0))
    gab.apply_transform(bgem)
    paint(bgem, lambda co, n: col("glow_purple", 0.8), "crystal", facet=0.15, ao=0.0)
    part(bgem, PAINTED, rigid("pelvis"))

    # Tabard: a dagged panel hanging from the belt in front of the thighs.
    cols = 7
    hem = [0.15, 0.125, 0.165, 0.11, 0.16, 0.13, 0.155]
    grid = []
    for i in range(5):
        row = []
        for j in range(cols):
            u = j / (cols - 1)
            x = lerp(-0.078, 0.078, u)
            z = lerp(zb - 0.005, hem[j], i / 4)
            bulge = 0.012 * math.sin(math.pi * u)
            y = TY - (torso_r(max(z, 0.26)) * TSY) - 0.035 - bulge - 0.045 * (i / 4) ** 1.5
            row.append((x * (1 + 0.12 * i / 4), y, z))
        grid.append(row)
    tab, ttags = sheet("tabard", grid, 0.01, lambda p: Vector((0, -1, 0)))
    set_uvs(tab, lambda co: (co.x, co.z))
    paint(tab, lambda co, n: lerp3(col("shell_dark"), col("shell"), smoothstep(0.12, 0.32, co.z)), "cloth", ao=0.15,
          faces=faces_where(ttags, lambda t: t[0] != "in" and 0 < t[2] < cols - 2))
    paint(tab, lambda co, n: lerp3(col("bronze", 0.8), col("gold"), smoothstep(0.12, 0.32, co.z)), "gold", ao=0.1,
          faces=faces_where(ttags, lambda t: t[0] != "in" and t[2] in (0, cols - 2)))
    paint(tab, lambda co, n: col("cap", 0.4), "cloth", ao=0.0, faces=faces_where(ttags, lambda t: t[0] == "in"))
    part(tab, PAINTED, lambda co: {"pelvis": smoothstep(0.25, 0.33, co.z), "tabard": 1 - smoothstep(0.25, 0.33, co.z)},
         smooth=50)


# ── Cloak: rigged in two rows of three bones, so the hem ripples ──

CLOAK_TOP = 0.525
CLOAK_BAND = 0.215          # gold hem band from here up 3 cm; tattered dags below
SIGIL_Z = 0.31


def cloak_w(co):
    up = smoothstep(0.5, 0.37, co.z)
    low = smoothstep(0.32, 0.17, co.z)
    wl = smoothstep(0.03, 0.2, co.x)
    wr = smoothstep(-0.03, -0.2, co.x)
    w = {"spine": 1 - up}
    for nm, s in (("L", wl), ("M", 1 - wl - wr), ("R", wr)):
        w["cloak_" + nm] = up * (1 - low) * s
        w["cloak_" + nm + "2"] = up * low * s
    return w


def cloak_parts():
    th_a, th_b = math.radians(100), math.radians(260)
    ncol = 21
    hems = []
    for j in range(ncol):
        hems.append(rng.uniform(0.035, 0.06) if j % 2 == 0 else rng.uniform(0.09, 0.14))
    for j in rng.sample(range(3, ncol - 3), 2):
        hems[j] = rng.uniform(0.15, 0.18)
    hems[0] = hems[-1] = 0.08
    rows_z = [CLOAK_TOP, 0.445, 0.37, 0.3, CLOAK_BAND + 0.03, CLOAK_BAND, None]

    def panel(th, z):
        """1 where the sigil sits (centre back), so the folds flatten under it."""
        return math.exp(-((th - math.pi) / 0.3) ** 2) * math.exp(-((z - SIGIL_Z) / 0.065) ** 2)

    def fold(th, vv, z):
        return 0.08 * vv ** 0.9 * math.sin(9 * th + 0.8) * (1 - 0.85 * panel(th, z))

    grid = []
    for zr in rows_z:
        row = []
        for j in range(ncol):
            th = lerp(th_a, th_b, j / (ncol - 1))
            z = zr if zr is not None else hems[j]
            vv = (CLOAK_TOP - z) / (CLOAK_TOP - 0.04)
            rx = lerp(0.235, 0.375, vv ** 0.8) + fold(th, vv, z)
            ry = lerp(0.17, 0.385, vv ** 0.8) + fold(th, vv, z)
            row.append((rx * math.sin(th), TY - ry * math.cos(th) + 0.03 * vv * vv, z))
        grid.append(row)

    def outward(p):
        return Vector((p.x, p.y - TY, 0)).normalized()
    cloak, tags = sheet("cloak", grid, 0.012, outward)
    set_uvs(cloak, lambda co: (math.atan2(-co.x, co.y - TY) * 0.32, co.z))

    def outer(co, n):
        th = math.atan2(co.x, -(co.y - TY)) % TAU
        vv = max(0.0, (CLOAK_TOP - co.z) / (CLOAK_TOP - 0.04))
        c = lerp3(col("shell_dark", 0.9), col("shell"), smoothstep(0.02, 0.4, co.z))
        c = lerp3(c, col("shell_light"), smoothstep(0.32, 0.5, co.z) * 0.6)
        # Folds: ridges lit toward the light violet, valleys dark.
        ridge = 0.5 + 0.5 * math.sin(9 * th + 0.8 + 0.35)
        reach = min(1.0, vv * 4.0)
        flat_ = panel(th, co.z)
        c = lerp3(c, col("shell_light", 1.15), 0.55 * ridge * reach * (1 - flat_))
        k = lerp(0.95, 0.42 + 0.68 * ridge, reach)
        k = lerp(k, 0.92, flat_)
        return tuple(ch * k for ch in c)
    edge = (0, ncol - 2)
    paint(cloak, outer, "cloth", ao=0.25, ao_h=0.18,
          faces=faces_where(tags, lambda t: t[0] == "out" and t[1] != 4 and t[2] not in edge))
    paint(cloak, lambda co, n: lerp3(col("bronze", 0.75), col("gold", 1.05), smoothstep(0.05, 0.45, co.z)), "gold",
          ao=0.12, faces=faces_where(tags, lambda t: t[0] == "out" and (t[2] in edge or t[1] == 4)))
    paint(cloak, lambda co, n: lerp3(col("cap", 0.3), col("cap", 0.6), smoothstep(0.05, 0.45, co.z)), "cloth", ao=0.2,
          faces=faces_where(tags, lambda t: t[0] == "in"))
    paint(cloak, lambda co, n: col("shell_dark", 0.8), "cloth", ao=0.0, faces=faces_where(tags, lambda t: t[0] == "rim"))
    part(cloak, PAINTED, cloak_w, smooth=60)

    # A gold crown sigil on the flat panel at the back: a band and three points.
    bvh = BVHTree.FromPolygons([v.co.copy() for v in cloak.data.vertices], [p.vertices[:] for p in cloak.data.polygons])
    # Long edges are split so every vertex lands on the curved cloth.
    xs = [-0.072, -0.036, 0.0, 0.036, 0.072]
    shapes = [[(x, -0.058) for x in xs] + [(x, -0.026) for x in reversed(xs)],
              [(-0.074, -0.017), (-0.037, -0.017), (0.0, -0.017), (0.037, -0.017), (0.074, -0.017), (0.092, 0.052),
               (0.042, 0.004), (0.0, 0.07), (-0.042, 0.004), (-0.092, 0.052)]]
    jewels = [(-0.092, 0.052), (0.0, 0.07), (0.092, 0.052)]
    sig_parts = []
    for shape in shapes:
        pts = []
        for x, z in shape:
            hit = bvh.ray_cast(Vector((x, 1.5, SIGIL_Z + z)), Vector((0, -1, 0)))
            pts.append(hit[0] + Vector((0, 0.008, 0)) if hit[0] is not None else Vector((x, 0.4, SIGIL_Z + z)))
        tris = tessellate_polygon([[Vector((x, z, 0)) for x, z in shape]])
        s = build("sigil", pts, [tuple(t) for t in tris])
        for poly in s.data.polygons:
            if poly.normal.y < 0:
                poly.flip()
        s.data.update()
        sig_parts.append(s)
    for x, z in jewels:
        hit = bvh.ray_cast(Vector((x, 1.5, SIGIL_Z + z)), Vector((0, -1, 0)))
        p = hit[0] if hit[0] is not None else Vector((x, 0.4, SIGIL_Z + z))
        sig_parts.append(blob("sigil", p + Vector((0, 0.008, 0.008)), (0.014, 0.008, 0.014), u=5, v=3))
    for s in sig_parts:
        gab.uv_box(s)
        paint(s, lambda co, n: lerp3(col("gold", 0.8), col("gold", 1.2), smoothstep(SIGIL_Z - 0.05, SIGIL_Z + 0.07,
                                                                                      co.z)), "gold", ao=0.0)
        part(s, PAINTED, cloak_w, smooth=45)


def collar():
    """A high collar swept up into two peaks behind the ears and dipping between them,
    so the crown and stem sit in the notch: ribbed like a fan (raised ribs lit,
    grooves dark), with a gold edge and a second gold trim, crimson only on its upper
    third and dark toward the mantle."""
    th_a, th_b = math.radians(125), math.radians(235)
    ncol = 13
    zbase = 0.515
    half = (ncol - 1) // 2
    prof = [0.6, 0.665, 0.79, 0.695, 0.672, 0.664, 0.66]         # top edge, shoulder to centre
    reach = [0.33, 0.385, 0.46, 0.385, 0.368, 0.358, 0.355]       # radius at the edge
    edge = [prof[min(j, ncol - 1 - j)] for j in range(ncol)]
    drops = [0.0, 0.016, 0.03, 0.044, None]                       # below the edge; None = base

    def wfrac(j, z):
        return max(0.0, min(1.0, (edge[j] - z) / (edge[j] - zbase)))
    grid = []
    for d in drops:
        row = []
        for j in range(ncol):
            u = j / (ncol - 1)
            th = lerp(th_a, th_b, u)
            z = edge[j] - d if d is not None else zbase
            w = wfrac(j, z)
            rib = 0.018 if j % 2 == 0 else -0.006
            r = lerp(reach[min(j, ncol - 1 - j)], 0.25, w ** 0.85) + rib * (1 - w)
            row.append((r * math.sin(th), -r * math.cos(th) + 0.035 * (1 - w), z))
        grid.append(row)
    obj, tags = sheet("collar", grid, 0.012, lambda p: Vector((p.x, p.y, 0)).normalized())
    set_uvs(obj, lambda co: (math.atan2(-co.x, co.y) * 0.3, co.z))
    nv = len(grid) * ncol

    def column(vi):
        return (vi % nv) % ncol

    def rib(vi):
        return 1.0 if column(vi) % 2 == 0 else 0.0

    def outer(co, n, vi):
        j = column(vi)
        w = wfrac(j, co.z)
        c = lerp3(col("shell_dark", 0.8), col("cap", 0.56), smoothstep(0.7, 0.15, w))
        return tuple(ch * (0.55 + 0.6 * rib(vi)) for ch in c)

    def inner(co, n, vi):
        j = column(vi)
        w = wfrac(j, co.z)
        c = lerp3(col("shell_dark", 0.7), col("cap", 0.36), smoothstep(0.75, 0.1, w))
        return tuple(ch * (0.55 + 0.6 * rib(vi)) for ch in c)

    def gold(co, n, vi):
        c = lerp3(col("gold", 0.72), col("gold", 1.12), smoothstep(0.6, 0.8, co.z))
        return tuple(ch * (0.85 + 0.2 * rib(vi)) for ch in c)
    trim = lambda t: t[1] in (0, 2) and not (t[0] == "rim" and t[1] == len(drops) - 1)
    paint(obj, outer, "cloth", ao=0.0, index=True, faces=faces_where(tags, lambda t: t[0] == "out" and not trim(t)))
    paint(obj, inner, "cloth", ao=0.0, index=True,
          faces=faces_where(tags, lambda t: t[0] in ("in", "rim") and not trim(t)))
    paint(obj, gold, "gold", ao=0.0, index=True, faces=faces_where(tags, trim))
    # The bottom rim sits inside the fur mantle.
    drop_faces(obj, faces_where(tags, lambda t: t[0] == "rim" and t[1] == len(drops) - 1 and 0 < t[2] < ncol - 1))
    part(obj, PAINTED, rigid("mantle"), smooth=50)


MANTLE_TOP = 0.585


def fur_layer(name, ncol, z_top, rows_v, drop, gap, clump, offset, out):
    """One row of fur: a cone of clumped tufts round the shoulders and back, open at
    the chest; even columns hang down as long spiky tufts, odd ones are the valleys
    between them. Single-skinned (its inside faces the body or the layer below),
    except at the chest opening. `offset` shifts the columns by a fraction of one."""
    th_a, th_b = math.radians(30), math.radians(330)
    step = (th_b - th_a) / (ncol - 1 + offset * 2 if offset else ncol - 1)
    ths = [th_a + step * (j + offset) for j in range(ncol)]
    hem = []
    for j, th in enumerate(ths):
        base = 0.452 + 0.01 * math.cos(th) + gap
        # Shorter tufts over the arms.
        arm = 1 - 0.45 * math.exp(-((abs(th - math.pi) - math.radians(90)) / math.radians(28)) ** 2)
        hem.append(base - (rng.uniform(*drop) * arm if j % 2 == 0 else rng.uniform(0.0, 0.01)))
    grid = []
    for v in rows_v:
        row = []
        for j, th in enumerate(ths):
            z = lerp(z_top, hem[j], v)
            vv = (MANTLE_TOP - z) / (MANTLE_TOP - 0.44)
            ease = 1 - (1 - max(0.0, min(vv, 1.0))) ** 2
            cl = (clump[0] if j % 2 == 0 else clump[1]) * v
            rx = lerp(0.17, 0.33, ease) + cl + out
            ry = lerp(0.15, 0.29, ease) + cl + out
            row.append((rx * math.sin(th), TY - ry * math.cos(th), z))
        grid.append(row)
    obj, tags = sheet(name, grid, 0.02, lambda p: Vector((p.x, p.y - TY, 0.35)).normalized())
    # Coarse UVs, so the thatch pattern's streaks are broad enough to read as strands
    # of fur from the strategy camera.
    set_uvs(obj, lambda co: (math.atan2(-co.x, co.y - TY) * 0.12, co.z * 0.6))
    tip_z = min(hem)
    nv = len(grid) * ncol

    def fur(co, n, vi):
        j = (vi % nv) % ncol
        i = (vi % nv) // ncol
        tuft = 1.0 if j % 2 == 0 else 0.0
        v = rows_v[i]
        reach = (z_top - co.z) / (z_top - tip_z)
        c = lerp3(col("hide_dark", 0.45), col("hide", lerp(0.9, 1.1, tuft)), smoothstep(0.0, 0.6, v))
        c = lerp3(c, col("autumn_tip", 0.85), smoothstep(0.9, 1.0, reach) * 0.35 * tuft)
        c = tuple(ch * (0.5 + 0.6 * tuft) for ch in c)
        return face_spill(c, co, 0.3)
    paint(obj, fur, "thatch", ao=0.0, facet=0.06, index=True, faces=faces_where(tags, lambda t: t[0] == "out"))
    paint(obj, lambda co, n: col("hide_dark", 0.5), "thatch", ao=0.0, faces=faces_where(tags, lambda t: t[0] == "in"))
    paint(obj, lambda co, n: col("hide", 0.75), "thatch", ao=0.0, faces=faces_where(tags, lambda t: t[0] == "rim"))
    drop_faces(obj, faces_where(tags, lambda t: (t[0] == "in" and 1 < t[2] < ncol - 3)
                                or (t[0] == "rim" and t[1] == 0 and t[2] < ncol - 1)))
    part(obj, PAINTED, rigid("mantle"), smooth=55)


def fur_mantle():
    """A thick fur mantle in two staggered rows of spiky tufts: a long lower row and
    a shorter upper row whose tufts fall over the lower row's valleys."""
    fur_layer("mantle", 21, MANTLE_TOP, [0.0, 0.45, 0.8, 1.0], (0.07, 0.09), 0.0, (0.04, -0.015), 0.0, 0.0)
    fur_layer("mantle_top", 19, MANTLE_TOP + 0.006, [0.0, 0.55, 1.0], (0.05, 0.065), 0.055, (0.03, -0.01), 1.0,
              0.02)


def pauldron(sign):
    """A gourd-shell pauldron: a ribbed dome of dark violet rind standing out past
    the head, rimmed in gold, with two bone thorns."""
    c = Vector((0.285 * sign, 0.02, 0.54))
    axis = Vector((0.42 * sign, 0.0, 0.91)).normalized()
    fwd = Vector((0.0, -1.0, 0.0))
    fwd = (fwd - axis * fwd.dot(axis)).normalized()
    out = axis.cross(fwd) * sign
    n = 12
    H, RF, RO = 0.088, 0.122, 0.102
    polar = [0.45, 0.9, 1.3, 1.7]

    def lobe(th):
        return 1 - 0.1 * (1 - abs(math.cos(3 * th)))

    def surf(th, a, grow=1.0):
        lat = (fwd * RF * math.cos(th) + out * RO * math.sin(th)) * math.sin(a)
        return c + (axis * H * math.cos(a) + lat) * lobe(th) * grow
    verts, uvs_v = [], []
    for a in polar:
        for k in range(n):
            th = TAU * k / n
            verts.append(surf(th, a))
            uvs_v.append((th * 0.1, a * 0.08))
    verts.append(c + axis * H)
    uvs_v.append((0.0, 0.0))
    top = len(verts) - 1
    verts.append(c - axis * 0.03)
    uvs_v.append((0.0, 0.2))
    bot = len(verts) - 1
    faces = [(top, k, (k + 1) % n) for k in range(n)]
    for i in range(len(polar) - 1):
        a, b = i * n, (i + 1) * n
        faces += [(a + k, b + k, b + (k + 1) % n, a + (k + 1) % n) for k in range(n)]
    last = (len(polar) - 1) * n
    faces += [(last + k, bot, last + (k + 1) % n) for k in range(n)]
    uvs = [[uvs_v[v] for v in f] for f in faces]
    dome = build("pauldron", verts, faces, uvs)
    fix_normals(dome)

    def rind(co, nrm):
        d = co - c
        hgt = d.dot(axis) / H
        th = math.atan2(d.dot(out) / RO, d.dot(fwd) / RF)
        crest = abs(math.cos(3 * th))
        k = 0.6 + 0.48 * crest ** 0.7
        col_ = lerp3(col("shell_dark", 1.1), col("shell", 1.15), smoothstep(-0.1, 0.45, hgt))
        col_ = lerp3(col_, col("shell_light", 1.2), smoothstep(0.45, 1.0, hgt) * 0.75)
        return tuple(ch * k for ch in col_)
    paint(dome, rind, "thatch", ao=0.0, facet=0.04)
    part(dome, PAINTED, rigid("mantle"), smooth=50)
    rim = tube("pauldron_rim", [surf(TAU * k / n, polar[-1], 1.035) for k in range(n)], 0.017, sides=3, closed=True,
               up=tuple(axis))
    paint(rim, lambda co, nrm: lerp3(col("bronze", 0.85), col("gold", 1.15), 0.4 + 0.6 * max(0.0, nrm.z)), "gold",
          ao=0.0)
    part(rim, PAINTED, rigid("mantle"), smooth=50)
    for th, a, ln in ((1.05, 0.62, 0.072), (2.25, 0.66, 0.06)):
        base = surf(th, a, 0.96)
        radial = (fwd * math.cos(th) + out * math.sin(th)).normalized()
        d = (axis * 0.8 + radial * 0.6).normalized()
        bend = (d + fwd * -0.25 * math.cos(th)).normalized()
        pts = [base, base + d * ln * 0.5, base + d * ln * 0.55 + bend * ln * 0.45]
        th_ = tube("pauldron_thorn", pts, [0.017, 0.01, 0.003], sides=3, caps=("flat", "point"))
        paint(th_, lambda co, nrm, b=base: lerp3(col("hide_dark", 0.8), col("spike", 1.05),
                                                 smoothstep(0.005, 0.05, (co - b).length)), "plain", ao=0.0)
        part(th_, PAINTED, rigid("mantle"), smooth=40)


# ══ Arms ══

def arm_bones(sign):
    pts = [Vector(p) for p in (ARM_L if sign > 0 else ARM_R)]
    return pts[0], pts[2], pts[4]


def vine_arm(sign):
    side = "L" if sign > 0 else "R"
    ctrl = ARM_L if sign > 0 else ARM_R
    pts = spline(ctrl, per=2)
    S, E, W = arm_bones(sign)
    if sign > 0:
        tip = W + Vector((0.01, -0.09, -0.01))
    else:
        tip = Vector((STAFF_AXIS.x, STAFF_AXIS.y, GRIP))
    weights = chain([(f"arm_{side}", S, E), (f"forearm_{side}", E, W), (f"hand_{side}", W, tip)], blend=0.04)
    vine_col = lambda co, n: lerp3(col("needle_deep", 0.75), col("leaf_green"), smoothstep(0.3, 0.5, co.z) * 0.7 + 0.15)

    def arm_r(s):
        """Tapering to the elbow, then a chunky forearm bulge before the wrist."""
        return lerp(0.05, 0.04, smoothstep(0.0, 0.5, s)) + 0.017 * math.exp(-((s - 0.74) / 0.12) ** 2)
    main = tube(f"arm_{side}", pts, arm_r, sides=6, caps=("flat", "flat"), noise=0.07)
    paint(main, vine_col, "bark", ao=0.0)
    part(main, PAINTED, weights, smooth=60)
    fr = frames(pts)
    dist = arclen(pts)
    for ph in (0.0, math.pi):
        hp = []
        for i, p in enumerate(pts):
            s = dist[i] / dist[-1]
            a = ph + TAU * 1.3 * s * sign
            t, nv, bv = fr[i]
            hp.append(p + (nv * math.cos(a) + bv * math.sin(a)) * (arm_r(s) + 0.004))
        strand = tube(f"arm_strand_{side}", hp, lambda s: lerp(0.022, 0.015, s), sides=4, caps=("flat", "point"))
        paint(strand, lambda co, n: lerp3(col("leaf_deep", 0.55), col("leaf_bright", 0.9), smoothstep(0.3, 0.5, co.z)),
              "bark", ao=0.0)
        part(strand, PAINTED, weights, smooth=60)
    # A knot of vine where the arm leaves the pauldron.
    boss = blob(f"arm_boss_{side}", tuple(pts[2] + Vector((0.004 * sign, 0.0, 0.006))), (0.058, 0.056, 0.05),
                u=6, v=4, noise=0.14)
    paint(boss, lambda co, n: lerp3(col("needle_deep", 0.8), col("leaf_green", 0.95), 0.35 + 0.5 * max(0.0, n.z)),
          "bark", ao=0.0)
    part(boss, PAINTED, weights, smooth=55)
    # Thorns along the vine, pointing out and back.
    for k in range(3):
        i = 2 + int((k + rng.uniform(0.2, 0.8)) * (len(pts) - 4) / 3)
        t, nv, bv = fr[i]
        a = rng.uniform(0, TAU)
        d = (nv * math.cos(a) + bv * math.sin(a))
        if d.z < -0.3:
            d = -d
        base = pts[i] + d * (arm_r(dist[i] / dist[-1]) - 0.004)
        tipp = base + (d * 0.9 + t * 0.5).normalized() * rng.uniform(0.032, 0.048)
        th = tube("thorn", [base, (base + tipp) / 2, tipp], [0.013, 0.007, 0.002], sides=3, caps=("flat", "point"))
        paint(th, lambda co, n, b=base: lerp3(col("leaf_deep", 0.6), col("spike"), smoothstep(0.0, 0.035, (co - b).length)),
              "plain", ao=0.0)
        part(th, PAINTED, weights)
    # A gold bracer round the wrist.
    ring_s = (0.8, 0.865, 0.93)

    def at_s(f):
        x = f * dist[-1]
        for i in range(1, len(pts)):
            if dist[i] >= x:
                return pts[i - 1].lerp(pts[i], (x - dist[i - 1]) / (dist[i] - dist[i - 1]))
        return pts[-1]
    bracer = tube(f"bracer_{side}", [at_s(f) for f in ring_s],
                  [arm_r(f) + d for f, d in zip(ring_s, (0.007, 0.014, 0.008))], sides=6, caps=("none", "none"))
    gab.uv_box(bracer)
    paint(bracer, lambda co, n: lerp3(col("bronze", 0.7), col("gold", 0.95), 0.3 + 0.65 * max(0.0, n.z)), "gold",
          ao=0.0)
    part(bracer, PAINTED, rigid(f"forearm_{side}"), smooth=40)
    return pts


def right_hand():
    first = len(PARTS)
    weights = rigid("hand_R")
    palm_c = Vector((STAFF_AXIS.x + 0.026, STAFF_AXIS.y + 0.024, GRIP))
    palm = blob("palm_R", palm_c, (0.034, 0.033, 0.04), u=6, v=4, noise=0.08)
    hand_col = lambda co, n: lerp3(col("needle_deep", 0.8), col("leaf_green", 0.9), smoothstep(GRIP - 0.05, GRIP + 0.05, co.z))
    paint(palm, hand_col, "bark", ao=0.0)
    part(palm, PAINTED, weights, smooth=70)
    a0 = math.atan2(palm_c.y - STAFF_AXIS.y, palm_c.x - STAFF_AXIS.x)
    for k, z in enumerate((GRIP - 0.028, GRIP - 0.003, GRIP + 0.022)):
        pts = []
        for i in range(4):
            a = a0 - 0.2 - 4.4 * i / 3
            rr = 0.035 - 0.004 * i / 3
            pts.append(Vector((STAFF_AXIS.x + rr * math.cos(a), STAFF_AXIS.y + rr * math.sin(a), z - 0.006 * i / 3)))
        f = tube("finger_R", pts, lambda s: lerp(0.014, 0.006, s), sides=4, caps=("flat", "point"))
        paint(f, hand_col, "bark", ao=0.0)
        part(f, PAINTED, weights, smooth=60)
    thumb = tube("thumb_R", spline([palm_c + Vector((0.0, -0.01, 0.022)), Vector((STAFF_AXIS.x + 0.01, STAFF_AXIS.y - 0.032, GRIP + 0.046)),
                                    Vector((STAFF_AXIS.x - 0.02, STAFF_AXIS.y - 0.032, GRIP + 0.04))], per=2),
                 lambda s: lerp(0.014, 0.006, s), sides=5, caps=("flat", "point"))
    paint(thumb, hand_col, "bark", ao=0.0)
    part(thumb, PAINTED, weights, smooth=60)
    # The hand is modelled at 1:1 round the staff, then scaled up to read on it.
    grip = Vector((STAFF_AXIS.x, STAFF_AXIS.y, GRIP))
    transform(PARTS[first:], Matrix.Translation(grip) @ Matrix.Scale(1.2, 4) @ Matrix.Translation(-grip))


def left_hand():
    W = Vector(ARM_L[-1])
    weights = rigid("hand_L")
    fwd = Vector((0.08, -1.0, -0.15)).normalized()
    lat = Vector((1, 0.08, 0)).normalized()
    upv = lat.cross(fwd).normalized()
    if upv.z < 0:
        upv = -upv
    palm_c = W + fwd * 0.032
    palm = blob("palm_L", palm_c, (0.041, 0.038, 0.03), u=6, v=4, noise=0.08)
    hand_col = lambda co, n: lerp3(col("needle_deep", 0.8), col("leaf_green", 0.9), smoothstep(0.32, 0.41, co.z))
    paint(palm, hand_col, "bark", ao=0.0)
    part(palm, PAINTED, weights, smooth=70)
    for o, ln in ((-0.034, 0.09), (-0.011, 0.108), (0.014, 0.103), (0.036, 0.086)):
        base = palm_c + fwd * 0.025 + lat * o
        spread = lat * o * 0.9
        pts = [base, base + fwd * ln * 0.4 + spread * 0.5 + upv * 0.014,
               base + fwd * ln * 0.75 + spread + upv * 0.0, base + fwd * ln + spread * 1.2 - upv * 0.04]
        f = tube("claw_L", spline(pts, per=2), lambda s: lerp(0.016, 0.003, s ** 0.9), sides=4, caps=("flat", "point"))
        paint(f, lambda co, n, b=base: lerp3(col("needle_deep", 0.8), col("spike", 0.95),
                                             smoothstep(0.04, 0.11, (co - b).length)), "plain", ao=0.0)
        part(f, PAINTED, weights, smooth=60)
    tb = palm_c - lat * 0.036
    thumb = tube("thumb_L", spline([tb, tb - lat * 0.034 + fwd * 0.022, tb - lat * 0.04 + fwd * 0.056 - upv * 0.022], per=2),
                 lambda s: lerp(0.015, 0.003, s), sides=5, caps=("flat", "point"))
    paint(thumb, hand_col, "bark", ao=0.0)
    part(thumb, PAINTED, weights, smooth=60)


# ══ Sceptre ══

def sceptre():
    weights = rigid("hand_R")
    ax = STAFF_AXIS
    z0, z1 = 0.18, 0.85
    shaft = [Vector((ax.x + lerp(0.012, -0.004, i / 4), ax.y + lerp(0.02, -0.008, i / 4), lerp(z0, z1, i / 4)))
             for i in range(5)]
    crook = [Vector((ax.x - 0.008, ax.y - 0.01, 0.9)), Vector((ax.x - 0.04, ax.y - 0.012, 0.942)),
             Vector((ax.x - 0.085, ax.y - 0.012, 0.942)), Vector((ax.x - 0.113, ax.y - 0.011, 0.912)),
             Vector((HOOK.x, ax.y - 0.01, HOOK.z + 0.006))]
    pts = shaft[:-1] + spline(shaft[-1:] + crook, per=2)
    staff = tube("staff", pts, lambda s: lerp(0.022, 0.016, s ** 2) * (1.15 if s < 0.04 else 1.0), sides=6,
                 caps=("flat", "flat"), noise=0.1, twist=0.25)
    paint(staff, lambda co, n: lerp3(col("wood_dark", 0.75), col("wood", 0.95), smoothstep(0.15, 0.95, co.z)), "bark",
          ao=0.2, ao_h=0.2)
    part(staff, PAINTED, weights, smooth=55)
    # Gold capped at 0.78: brighter vertex gold clips under the sun and the specular
    # turns it white.
    gold = lambda co, n: lerp3(col("bronze", 0.6), col("gold", 0.78), 0.5 + 0.5 * n.z)
    # Gold bands and a spiked ferrule.
    for z, h in ((0.265, 0.022), (0.42, 0.03), (0.835, 0.035)):
        f = (z - z0) / (z1 - z0)
        c = Vector((lerp(ax.x + 0.012, ax.x - 0.004, f), lerp(ax.y + 0.02, ax.y - 0.008, f), z))
        band = lathe("band", [(z - h / 2, 0.026), (z, 0.031), (z + h / 2, 0.026)],
                     6, center=(c.x, c.y), bottom=None, top=None)
        paint(band, gold, "gold", ao=0.0)
        part(band, PAINTED, weights, smooth=45)
    fx, fy = ax.x + 0.012, ax.y + 0.02
    ferrule = lathe("ferrule", [(0.175, 0.025), (0.19, 0.027)], 6, center=(fx, fy), bottom=0.125, top=0.198)
    paint(ferrule, gold, "gold", ao=0.0)
    part(ferrule, PAINTED, weights, smooth=45)
    knob = blob("crook_knob", (ax.x - 0.004, ax.y - 0.009, 0.872), (0.031, 0.031, 0.027), u=6, v=4)
    paint(knob, gold, "gold", ao=0.0)
    part(knob, PAINTED, weights, smooth=40)


def lantern(scale=1.35):
    """An iron-and-gold lantern hanging from the crook: a violet crystal flame inside
    a cage of bars, backed by dark glass. The glass is a hexagonal shell facing
    inward, so from any side its far walls frame the glow and its near walls vanish
    (back-face culled). Modelled at 1:1 about the hook, then scaled up to read from
    the game camera."""
    weights = rigid("lantern")
    lx, ly = HOOK.x, HOOK.y
    built = []
    ring = [Vector((lx + 0.013 * math.cos(TAU * k / 6), ly, 0.858 + 0.016 * math.sin(TAU * k / 6))) for k in range(6)]
    built.append(("ring", tube("lantern_ring", ring, 0.0045, sides=3, closed=True, up=(0, 1, 0))))
    built.append(("cap", lathe("lantern_cap", [(0.788, 0.044), (0.796, 0.062), (0.804, 0.06), (0.822, 0.032),
                                               (0.834, 0.014)], 8, center=(lx, ly), bottom=0.79, top=0.846,
                               phase=math.pi / 8)))
    built.append(("base", lathe("lantern_base", [(0.666, 0.03), (0.674, 0.05), (0.684, 0.05), (0.69, 0.042)], 6,
                                center=(lx, ly), bottom=0.635, top=0.692, phase=math.pi / 6)))
    for k in range(6):
        a = TAU * k / 6 + math.pi / 6
        bar = [Vector((lx + r * math.sin(a), ly - r * math.cos(a), z)) for r, z in ((0.044, 0.688), (0.054, 0.74),
                                                                                    (0.046, 0.792))]
        built.append(("bar", tube("lantern_bar", bar, 0.006, sides=3, caps=("flat", "flat"))))
    glass = lathe("lantern_glass", [(0.69, 0.04), (0.74, 0.049), (0.79, 0.041)], 6, center=(lx, ly),
                  phase=math.pi / 6)
    for poly in glass.data.polygons:
        if poly.normal.dot(poly.center - Vector((lx, ly, poly.center.z))) > 0:
            poly.flip()
    glass.data.update()
    built.append(("glass", glass))
    built.append(("core", gem("lantern_core", (lx, ly, 0.736), 0.036, 0.112, sides=6)))
    m = Matrix.Translation(HOOK) @ Matrix.Scale(scale, 4) @ Matrix.Translation(-HOOK)
    z1 = HOOK.z + (0.846 - HOOK.z) * scale
    iron = lambda co, n: lerp3(col("iron_dark", 0.8), col("iron_light", 0.9), 0.4 + 0.5 * max(0.0, n.z))
    gold = lambda co, n: lerp3(col("bronze", 0.6), col("gold", 0.78), 0.45 + 0.5 * max(0.0, n.z))
    for kind, o in built:
        o.data.transform(m)
        o.data.update()
        if kind in ("ring", "bar"):
            paint(o, iron, "metal", ao=0.0)
            part(o, PAINTED, weights)
        elif kind == "cap":
            # Smooth, 8-sided, no brighter than gold 0.78 and matte with its sheen
            # painted on (a lit rim, a darker sunward slope): as polished gold it
            # reflected the sun straight into the strategy camera and blew out to white.
            def cap_col(co, n):
                c = lerp3(col("bronze", 0.6), col("gold", 0.78), smoothstep(z1 - 0.075, z1 - 0.045, co.z))
                c = lerp3(c, col("bronze", 0.66), smoothstep(z1 - 0.035, z1, co.z) * 0.75)
                return tuple(ch * (0.72 if n.z > 0.45 else 1.0) for ch in c)
            paint(o, cap_col, "plain", ao=0.0)
            part(o, PAINTED, weights, smooth=45)
        elif kind == "base":
            paint(o, gold, "gold", ao=0.0)
            part(o, PAINTED, weights, smooth=45)
        elif kind == "glass":
            gab.uv_box(o)
            paint(o, lambda co, n: lerp3(col("shell_dark", 0.6), col("shell", 0.7), 0.3), "crystal", facet=0.1, ao=0.0)
            part(o, PAINTED, weights)
        else:
            paint(o, lambda co, n: col("glow_purple", 0.25), "plain", facet=0.0, ao=0.0)
            part(o, CORE, weights)


# ══ Legs ══

def leg(sign):
    side = "L" if sign > 0 else "R"
    H, K, A, F = (mirror(p, sign) for p in LEG)
    toe_tip = F + Vector((0, -0.12, -0.03))
    weights = chain([(f"thigh_{side}", H, K), (f"shin_{side}", K, A), (f"foot_{side}", A, toe_tip)], blend=0.035)
    pts = spline([H, K, A, F], per=3)

    def rad(s):
        r = lerp(0.092, 0.06, smoothstep(0.0, 0.55, s))
        r += 0.026 * math.exp(-((s - 0.47) / 0.07) ** 2)     # knee burl
        r += 0.018 * smoothstep(0.82, 1.0, s)               # root flare at the foot
        return r
    root_col = lambda co, n: lerp3(col("leg", 0.75), col("bark", 1.12), smoothstep(0.02, 0.34, co.z))
    sides = 8
    main = tube(f"leg_{side}", pts, rad, sides=sides, caps=("flat", "flat"), noise=0.06, twist=0.12, ridges=0.13)
    for v in main.data.vertices:                    # the ridged foot ring clears the ground as the foot rolls
        v.co.z = max(v.co.z, 0.02)
    dist = arclen(pts)

    def leg_col(co, n, vi):
        # Bark ridges on the raised (even) vertices of each ring, spiralling with the
        # twist; grooves dark. Moss on the upper front of the thigh.
        crest = 1.0 if (vi % sides) % 2 == 0 else 0.0
        c = root_col(co, n)
        c = tuple(ch * (0.55 + 0.62 * crest) for ch in c)
        moss = 0.38 * smoothstep(0.27, 0.31, co.z) * smoothstep(0.4, 0.35, co.z) * smoothstep(0.1, -0.5, n.y)
        return lerp3(c, col("leaf_deep", 0.85), moss * (0.6 + 0.4 * crest))
    paint(main, leg_col, "bark", ao=0.25, ao_h=0.12, index=True)
    part(main, PAINTED, weights, smooth=60)
    # A root strand twisting down the leg into the outer toe: pale bark on its crest,
    # dark where it meets the leg, so it reads as a separate root.
    fr = frames(pts)
    hp = []
    for i, p in enumerate(pts):
        s = dist[i] / dist[-1]
        a = 1.4 + TAU * 0.85 * s * sign
        t, nv, bv = fr[i]
        q = p + (nv * math.cos(a) + bv * math.sin(a)) * (rad(s) * 0.97)
        q.z = max(q.z, 0.045)                               # clear of the ground as the foot rolls
        hp.append(q)
    strand = tube(f"leg_strand_{side}", hp, lambda s: lerp(0.026, 0.017, s), sides=4, caps=("flat", "flat"), noise=0.08)

    def strand_col(co, n):
        i = min(range(len(hp)), key=lambda j: (hp[j] - co).length_squared)
        out = (hp[i] - pts[i]).normalized()
        crest = (co - hp[i]).normalized().dot(out)
        return lerp3(col("leg", 0.55), col("bark", 1.3), smoothstep(-0.3, 0.8, crest))
    paint(strand, strand_col, "bark", ao=0.25, ao_h=0.12)
    part(strand, PAINTED, weights, smooth=60)
    # Root toes gripping the ground: three forward, one back.
    for ang, ln, r in ((-0.75, 0.125, 0.031), (-0.1, 0.165, 0.035), (0.6, 0.125, 0.031), (math.pi + 0.15, 0.09, 0.03)):
        a = ang * sign + rng.uniform(-0.1, 0.1)
        d = Vector((math.sin(a), -math.cos(a), 0))
        S = F + d * 0.03
        tip = S + d * ln
        tip.z = 0.0055
        ctrl = [S, S + d * ln * 0.3 + Vector((0, 0, 0.01)), S + d * ln * 0.55 + Vector((0, 0, -0.008)),
                S + d * ln * 0.8 + Vector((0, 0, -0.026)), tip]
        toe = tube("toe", ctrl, lambda s, r=r: lerp(r, 0.0055, s ** 1.2), sides=4,
                   caps=("flat", "point"), noise=0.06)
        paint(toe, root_col, "bark", ao=0.3, ao_h=0.1)
        part(toe, PAINTED, rigid(f"foot_{side}"), smooth=60)


# ══ Rig ══

PELVIS_HEAD = Vector((0, TY, 0.31))
CLOAK_BONES = {"L": ((0.14, 0.2, 0.48), (0.24, 0.32, 0.27), (0.31, 0.4, 0.06)),
               "M": ((0.0, 0.23, 0.48), (0.0, 0.36, 0.27), (0.0, 0.44, 0.06)),
               "R": ((-0.14, 0.2, 0.48), (-0.24, 0.32, 0.27), (-0.31, 0.4, 0.06))}


def bones():
    b = [("root", (0, 0, 0), (0, 0, 0.1), None),
         ("pelvis", tuple(PELVIS_HEAD), (0, TY, 0.41), "root"),
         ("spine", (0, TY, 0.41), (0, TY, 0.55), "pelvis"),
         ("head", (HX, HY, 0.55), (HX, HY, 0.83), "spine"),
         ("stem", tuple(STEM_PTS[0]), tuple(STEM_PTS[1]), "head"),
         ("mantle", (0, TY, 0.5), (0, TY, 0.62), "spine"),
         ("tabard", (0, -0.16, 0.335), (0, -0.18, 0.15), "pelvis")]
    for sign, side in ((1, "L"), (-1, "R")):
        H, K, A, F = (mirror(p, sign) for p in LEG)
        b += [(f"thigh_{side}", tuple(H), tuple(K), "pelvis"),
              (f"shin_{side}", tuple(K), tuple(A), f"thigh_{side}"),
              (f"foot_{side}", tuple(A), tuple(F + Vector((0, -0.11, -0.03))), f"shin_{side}")]
        S, E, W = arm_bones(sign)
        tip = W + Vector((0.01, -0.09, -0.01)) if sign > 0 else Vector((STAFF_AXIS.x, STAFF_AXIS.y, GRIP))
        b += [(f"arm_{side}", tuple(S), tuple(E), "spine"),
              (f"forearm_{side}", tuple(E), tuple(W), f"arm_{side}"),
              (f"hand_{side}", tuple(W), tuple(tip), f"forearm_{side}")]
    for nm, (h, m, t) in CLOAK_BONES.items():
        b += [(f"cloak_{nm}", h, m, "spine"), (f"cloak_{nm}2", m, t, f"cloak_{nm}")]
    b.append(("lantern", tuple(HOOK), (HOOK.x, HOOK.y, 0.65), "hand_R"))
    return b


def R(pitch=0.0, roll=0.0, yaw=0.0):
    """A rotation about the armature axes in degrees: pitch about X (tips an upright
    bone forward, swings a hanging one back), roll about Y (drops the +X side), yaw
    about Z (turns +X backward)."""
    return (Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(roll), 3, "Y")
            @ Matrix.Rotation(math.radians(pitch), 3, "X"))


def act(arm, name, frames_n, sample):
    """Keys every frame from sample(f) -> {bone: (rotation, (x, y, z) offset)}; the
    rotation is a 3x3 matrix about the armature axes through the bone head, relative
    to the parent (a bone's posed rotation is its parents' matrices times its own).
    It is converted to the bone's rest frame; the last frame repeats the first."""
    action = bpy.data.actions.new(name)
    arm.animation_data_create()
    arm.animation_data.action = action
    rest = {b.name: b.matrix_local.to_3x3() for b in arm.data.bones}
    last = {}
    for f in range(frames_n + 1):
        for bone, (rot, loc) in sample(f % frames_n).items():
            pb = arm.pose.bones[bone]
            pb.rotation_mode = "QUATERNION"
            B = rest[bone]
            q = (B.transposed() @ rot @ B).to_quaternion()
            if bone in last and last[bone].dot(q) < 0:
                q.negate()
            last[bone] = q
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=f)
            pb.location = B.transposed() @ Vector(loc)
            pb.keyframe_insert("location", frame=f)
    track = arm.animation_data.nla_tracks.new()
    track.name = name
    track.strips.new(name, 0, action)
    arm.animation_data.action = None


# The stride. Each ankle is planted for DUTY of the cycle, sliding back along the ground
# at walking speed, then arcs forward through the air; both feet are down around each
# footfall (a heavy walk). One 30-frame cycle covers STRIDE model units.
DUTY = 0.55
STEP, STEP_C, LIFT = 0.13, 0.025, 0.07
STRIDE = 2 * STEP / DUTY
REACH = []


def leg_ik(hip, target, knee_rest, ankle_rest, hip_rest):
    """Two-bone IK in the side (Y, Z) plane, knee forward. Returns the world pitch
    of thigh and shin away from their rest directions, in degrees."""
    l1 = (knee_rest - hip_rest).length
    l2 = (ankle_rest - knee_rest).length
    a1r = math.atan2(knee_rest.y - hip_rest.y, knee_rest.x - hip_rest.x)
    a2r = math.atan2(ankle_rest.y - knee_rest.y, ankle_rest.x - knee_rest.x)
    t = target - hip
    REACH.append(t.length / (l1 + l2))
    d = min(t.length, (l1 + l2) * 0.999)
    at = math.atan2(t.y, t.x)
    b = math.acos(max(-1.0, min(1.0, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d))))
    a1 = at - b
    knee = hip + Vector((math.cos(a1), math.sin(a1))) * l1
    end = hip + t.normalized() * d
    a2 = math.atan2(end.y - knee.y, end.x - knee.x)
    return math.degrees(a1 - a1r), math.degrees(a2 - a2r)


def foot_track(q):
    """Ankle offset along y, lift and toe pitch at leg phase q (0 = heel strike)."""
    q %= TAU
    if q < DUTY * TAU:
        return lerp(STEP_C - STEP, STEP_C + STEP, q / (DUTY * TAU)), 0.0, 0.0
    t = (q - DUTY * TAU) / ((1 - DUTY) * TAU)
    e = t * t * (3 - 2 * t)
    return lerp(STEP_C + STEP, STEP_C - STEP, e), LIFT * math.sin(math.pi * t) ** 0.8, -18 * math.sin(math.pi * t ** 1.3)


def walk(f):
    """A heavy, regal stride: left heel strikes at frame 0, right at 15."""
    p = TAU * f / 30
    c, s = math.cos(p), math.sin(p)
    k = {}
    drop = (1 - abs(math.sin(p - 0.25))) ** 2            # 1 just after each footfall
    bob = -0.006 - 0.03 * drop
    P = R(3 + 2.5 * drop, -2.5 * s, -5 * c)            # hips: lean, drop on the swing side, turn
    S = R(4 + 4 * drop, 8 * s, 8 * c)                  # shoulders: slump on contact, sway over the standing leg
    k["pelvis"] = (P, (0, 0, bob))
    k["spine"] = (S, (0, 0, 0))
    k["head"] = (R(-2 + 5 * math.cos(2 * (p - 0.35)), -5 * math.sin(p - 0.4), -5 * c), (0, 0, 0))
    # Secondary motion a frame behind each footfall: the stem sways and dips, the
    # mantle (with the pauldrons and collar) sinks 1.5 cm and settles.
    late = (1 - abs(math.sin(p - 0.25 - TAU / 30))) ** 2
    k["stem"] = (R(4 * math.cos(p - 1.2) + 6 * late, 3 * math.sin(p - 1.2)), (0, 0, 0))
    k["mantle"] = (R(2.5 * late), (0, 0, -0.015 * late))
    D_spine = P @ S
    pelvis_m = (Matrix.Translation((0, 0, bob)) @ Matrix.Translation(PELVIS_HEAD) @ P.to_4x4()
                @ Matrix.Translation(-PELVIS_HEAD))
    thighs = []
    for side, sign, off in (("L", 1, 0.0), ("R", -1, math.pi)):
        H, K, A, F = (mirror(v, sign) for v in LEG)
        ay, lift, toe = foot_track(p + off)
        hip = pelvis_m @ H
        th, sh = leg_ik(Vector((hip.y, hip.z)), Vector((ay, A.z + lift)), Vector((K.y, K.z)), Vector((A.y, A.z)),
                        Vector((H.y, H.z)))
        # World-space pitch only: the legs ignore the hips' roll and turn.
        k[f"thigh_{side}"] = (P.transposed() @ R(th), (0, 0, 0))
        k[f"shin_{side}"] = (R(sh - th), (0, 0, 0))
        k[f"foot_{side}"] = (R(toe - sh), (0, 0, 0))
        thighs.append(th)
    # The tabard swings forward with whichever thigh leads, so it never cuts into it.
    k["tabard"] = (P.transposed() @ R(min(0.0, *thighs) * 0.9 - 2 + 3 * math.cos(2 * p - 0.7)), (0, 0, 0))
    # The claw arm swings against the legs.
    k["arm_L"] = (R(18 * c, 0, 4 * s), (0, 0, 0))
    k["forearm_L"] = (R(-8 + 10 * math.cos(p - 0.5)), (0, 0, 0))
    k["hand_L"] = (R(6 * math.cos(p - 0.9)), (0, 0, 0))
    # The sceptre arm swings a little; the hand cancels everything above it, so the
    # staff stays upright with a deliberate 5-degree sway, and the lantern hangs from
    # it as a pendulum in world space.
    AR, FR = R(-9 * c), R(-4 * math.cos(p - 0.5))
    k["arm_R"] = (AR, (0, 0, 0))
    k["forearm_R"] = (FR, (0, 0, 0))
    W_hand = R(5 * math.cos(p - 0.4), 0, 3 * c)
    k["hand_R"] = ((D_spine @ AR @ FR).transposed() @ W_hand, (0, 0, 0))
    W_lantern = R(-12 * math.cos(p - 1.1), 5 * math.sin(2 * p), 3 * c)
    k["lantern"] = (W_hand.transposed() @ W_lantern, (0, 0, 0))
    # Cloak: the upper row billows and swings with the hips, the lower row follows
    # 0.6 rad later, so the hem ripples.
    lag = 0.6
    waves = {"L": lambda x: 10 + 7 * math.cos(p - 1.3 - x), "R": lambda x: 10 + 7 * math.cos(p + math.pi - 1.3 - x),
             "M": lambda x: 12 + 5 * math.cos(2 * p - 1.9 - x)}
    for nm, wave in waves.items():
        sway = 3 * math.sin(p - 1.0)
        k[f"cloak_{nm}"] = (R(wave(0.0), sway, 0), (0, 0, 0))
        k[f"cloak_{nm}2"] = (R(wave(lag) - 6, 1.5 * math.sin(p - 1.0 - lag), 0), (0, 0, 0))
    return k


# ══ Build ══

head_parts()
body_parts()
cloak_parts()
collar()
fur_mantle()
for sgn in (1, -1):
    pauldron(sgn)
    vine_arm(sgn)
    leg(sgn)
right_hand()
left_hand()
sceptre()
lantern()

counts = {}
for o in PARTS:
    key = o.name.split(".")[0]
    counts[key] = counts.get(key, 0) + gab.triangles(o)
print("godot-agent: parts " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])))

crest = gab.join(PARTS, "hollowtide_crest")
crest.data.name = "hollowtide_crest"
gab.select_only(crest)
bpy.ops.object.material_slot_remove_unused()
zmin = min(v.co.z for v in crest.data.vertices)
print(f"godot-agent: lowest point {zmin:.4f}")

arm = gab.armature("rig", bones())
mod = crest.modifiers.new("Armature", "ARMATURE")
mod.object = arm
crest.parent = arm
act(arm, "walk", 30, walk)
print(f"godot-agent: stride {STRIDE:.4f} model units per cycle = {STRIDE * 1.6:.3f} game units/s at 1.6x; "
      f"leg reach max {max(REACH):.3f}")

POSE = gab.param("pose", -1)
if POSE >= 0:
    # Review only: bake one walk frame into the mesh and drop the rig.
    arm.animation_data.action = bpy.data.actions["walk"]
    bpy.context.scene.frame_set(POSE)
    gab.select_only(crest)
    bpy.ops.object.convert(target="MESH")
    crest = bpy.context.active_object
    crest.parent = None
    crest.matrix_world = Matrix.Identity(4)
    bpy.data.objects.remove(arm)
