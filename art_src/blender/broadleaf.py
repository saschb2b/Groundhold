"""Broadleaf tree: a gnarled, hand-painted oak-like tree for the hollow's woods.

Build (one per variant; the seed picks the shape, the params the foliage colours):
    godot-agent asset blender . art_src/blender/broadleaf.py --to res://models/vegetation/tree_green_1.glb \
        --seed 1 --param leaf=#3f7a2e --param leaf_light=#7fb444 --param tip=#c3e070 --review --no-import

The game's variants: tree_green_1..3 (seeds 1-3; #3f7a2e, #7fb444, #c3e070), tree_amber_1..3
(seeds 11-13; #c0602a, #e8a040, #f6d070), tree_red_1..2 (seeds 21-22; #a83a24, #d8682e, #f0a050).

Built for the game's perspective camera, which sees a tree from about 35 degrees (top of the
screen) to 70 degrees (bottom). At its middle pitch, 56 degrees, the trunk must show at least
CLEAR = 0.32 up its axis from every yaw: each lump is settled (lifted, or drawn in toward the
axis) until no point of it hides the trunk lower than that, using the exact worst yaw of every
point (z - tan(56) * distance from the axis), and a hard check on the finished mesh fails the
build otherwise. The crown's underside therefore rises along the camera's line of sight, and a
few small dark "under" lumps hug the limbs above that line so the crown reads full from the side.

Wood: a thick, twisted, fluted trunk (radius 0.19-0.21 at the base, 0.13-0.15 at the fork) on
bulbous root knees (two big, two or three small, each swelling where it leaves the flare and
diving into the ground still fat), a broken stub low down, and 3-5 six-sided limbs that start
inside the trunk below the fork and S-curve out into the crown, plus a leader. On every other
seed, two or three glowing shelf fungi sit on the lower trunk where the camera looks (glow
material, #f6d070): the hollow's lantern light.

Crown: 5-8 big lumps (a ring at the limb ends, one or two higher up, a top lump, one or two
florets out on the rim, in one of four silhouettes picked by the seed: round, egg, umbrella or
lopsided), plus 2-3 under lumps. Each lump is an opaque, low-poly leaf core (an icosahedron,
painted a shade darker than its leaves, so any gap shows shaded leaves, never the ground, and
every lump shadows the one below) wrapped in crossed pairs of big foliage_leaves clump cards,
0.65-0.85 units across, so each painted leaf is about 5 px at the game's default zoom rather
than sub-pixel fur. A clump card is an octagon cut just outside the texture's opaque clump (8
triangles round a centre vertex, domed a little), so no transparent corner widens the tree or
hides the trunk, and its vertex colour can lift the texture's darker rows where they show.

On the upper part of a lump the cards lie like shingles, 22-35 degrees off horizontal toward
the lump's outside, their texture's dark foot cut away and the clump's lit top turned toward the
lump's crown (+-35 degrees at random): the darker leaves gather round each lump's edge and
outline it, instead of speckling its lit cap. Their fronts stay within 35 degrees of the sky, so
no camera between 35 and 70 degrees sees their backs (the engine shades a card's back as facing
into the crown). The rim cards stand crossed about the vertical, yawed 25-40 degrees off the
lump's outside and tilted 22-32 degrees to the sky, so they are never edge-on (a dark line) from
the game camera except on a lump's far side, behind its core.

Each lump shades as its own ball: a lit cap over a darker skirt, a crevice shade wherever it
runs into a neighbour (both sides, so every clump is outlined), a contact shade where a higher
lump overhangs it, and a crown-wide height gradient on top. Ramps: green runs from a cool deep
shade through the leaf body colour (most of the crown) to lime only on the highest caps; autumn
shade turns crimson and richer rather than brown, amber's body is a touch richer than its
params, and its lit top is held below a value ceiling (before the foot lift) so the shader's
tint boost cannot clip it to straw; red keeps more of its body colour and leans crimson so it
stays clear of amber. The crown's vertex alpha holds a per-lump random phase (0-1) for a wind
shader that wants lumps to sway on their own (foliage.gdshader ignores it today).

Trunk base at the origin; at most 2.18 units tall and 1.72 across; at most 2380 triangles
(about 720-860 wood, cores and fungi, the rest crown cards).

Params:
    leaf, leaf_light, tip   foliage tints, dark-to-bright (hex)
    shape                   round | egg | umbrella | lopsided (default: picked from the seed)
    density                 crossed card pairs per m2 of lump surface (30; half that beneath).
                            Lowered automatically to keep within the triangle budget.
    glow                    1 adds the glowing shelf fungi (default: odd seeds)
    debug                   1 prints every lump (kind, radius from the axis, height, cards);
                            2 also paints each lump its own colour
    crown_only              1 leaves the wood out (for measuring the crown's colours)
    tex_in, dome, curl, rim_lift, ring, lift, lift_cap
                            look-development knobs (shingle texture direction, card dome, rim
                            card tilt, ring lump distance from the axis, foot lift); the
                            defaults are the shipped look
"""

import colorsys
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

import gab

rng = gab.rng

LEAF = gab.param("leaf", "#3f7a2e")
LEAF_LIGHT = gab.param("leaf_light", "#7fb444")
TIP = gab.param("tip", "#c3e070")
DENSITY = gab.param("density", 30.0)        # pairs per m2 where the lump faces up
DENSITY_LOW = DENSITY * 0.5                 # and where it faces down
SHAPES = ("round", "egg", "umbrella", "lopsided")
# Seeds 1-3, 11-13 and 21-22 get every silhouette twice, and the three greens three different ones.
SHAPE = gab.param("shape", SHAPES[(gab.seed % 10 - 1 + 3 * (gab.seed // 10)) % 4])
GLOW = gab.param("glow", gab.seed % 2)
UP = Vector((0, 0, 1))

# ── Bark colours (hollow palette) ──
ROOT_DARK = "#3e2a1e"   # leg
BARK_DARK = "#4e3423"   # wood_dark
BARK = "#5b3a29"        # bark
BARK_MID = "#6b4a34"    # hide
WOOD = "#7a5534"        # wood
WOOD_LIGHT = "#a0784a"  # wood_light
MOSS = "#5a6b2e"        # stem
MOSS_LIGHT = "#6a9a3c"  # grass
FUNGUS = "#f6d070"      # the lantern glow

# ── Limits ──
REACH = 0.86            # no card corner beyond this from the axis (footprint < 1.8)
MAX_TRIS = 2380
MAX_HEIGHT = 2.18
TAN_CAM = math.tan(math.radians(56.0))     # the game camera's middle pitch
CLEAR = 0.32            # the trunk axis must show at least this high from every yaw
CLEAR_MARGIN = 0.015
MAX_TILT = 35.0         # upper cards: the front within this of the sky (the camera's lowest pitch)

# The leaf card texture: where its leaves are (u, v), the clump's centre and radius (in the
# texture square), and where its dark foot ends. LEAF_LUM: the texture's linear brightness by
# height v (opaque texels), for lifting its darker rows with the vertex colour.
U0, U1 = 0.05, 0.97
CLUMP_U, CLUMP_V, CLUMP_R = 0.505, 0.47, 0.46
V_CROP = 0.30           # cards facing up: the darkest leaves cut away
LEAF_LUM = [(0.0, 0.045), (0.1, 0.041), (0.2, 0.052), (0.3, 0.085), (0.35, 0.1), (0.4, 0.182), (0.45, 0.212),
            (0.5, 0.393), (0.6, 0.439), (0.7, 0.451), (0.8, 0.591), (1.0, 0.6)]
CARD_K = (0.58, 0.7)    # card size: CARD_K x sqrt(lump radius / 0.31) / (U1 - U0), the leaves ~5 px in play
LAYERS = (0.42, 0.58)   # card centres at these fractions of the lump radius
TEX_IN = gab.param("tex_in", 1)     # shingles: the clump's lit top toward the lump's crown (0: outward)
DOME = (gab.param("dome", 0.12), gab.param("curl", 0.04))
RING = (gab.param("ring", 0.2), gab.param("ring", 0.2) + 0.14)
RIM_LIFT = (gab.param("rim_lift", 22.0), gab.param("rim_lift", 22.0) + 10.0)
SPIN = 35.0             # shingles: the clump's lit top turned at random by up to this (degrees)


def col(h) -> Vector:
    return Vector(gab.rgb(h))


def lerp(a, b, t):
    return a + (b - a) * t


def clamp01(x):
    return max(0.0, min(1.0, x))


def smoothstep(e0, e1, x):
    t = clamp01((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def ramp(stops, t):
    if t <= stops[0][0]:
        return stops[0][1].copy()
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            return lerp(c0, c1, (t - t0) / (t1 - t0))
    return stops[-1][1].copy()


def hue_of(hex_color):
    h = hex_color.lstrip("#")
    return colorsys.rgb_to_hsv(*(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)))[0]


def cool(hex_color, amount=0.06, dv=-0.2, ds=0.05):
    """A shadow tone: the hue pulled toward blue by `amount` turns (the short way round),
    darker and a little richer."""
    hue = hue_of(hex_color)
    d = (0.62 - hue + 0.5) % 1.0 - 0.5
    return gab.hsv(hex_color, max(-amount, min(amount, d)), ds, dv)


def to_srgb(c):
    c = clamp01(c)
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def floor_value(c, vmin):
    """Lifts a linear colour so its HSV value (in sRGB) is at least vmin, keeping hue and
    saturation."""
    s = [to_srgb(x) for x in c]
    v = max(s)
    if v >= vmin:
        return c
    s = [vmin] * 3 if v <= 1e-4 else [x * vmin / v for x in s]
    return Vector(gab._linear(x) for x in s)


def ceil_value(c, vmax):
    """Lowers a linear colour so its HSV value (in sRGB) is at most vmax, keeping hue and
    saturation: the mirror of floor_value."""
    s = [to_srgb(x) for x in c]
    v = max(s)
    if v <= vmax:
        return c
    return Vector(gab._linear(x * vmax / v) for x in s)


def shift(c, dh=0.0, ds=0.0):
    """A linear colour turned by dh (turns) in hue and ds in saturation (in sRGB HSV)."""
    h, s, v = colorsys.rgb_to_hsv(*(to_srgb(x) for x in c))
    return Vector(gab._linear(x) for x in colorsys.hsv_to_rgb((h + dh) % 1.0, clamp01(s + ds), v))


def paint_fn(obj, fn, pattern="plain", facet=0.04):
    """Vertex colours from fn(vertex_index, co, normal, polygon) -> linear Vector; the
    alpha carries the painted pattern like gab.paint()."""
    mesh = obj.data
    layer = gab._color_layer(mesh)
    alpha = (gab.PATTERNS.index(pattern) + 0.5) / 16
    normals = [v.normal.copy() for v in mesh.vertices]
    for poly in mesh.polygons:
        shade = 1.0 + rng.uniform(-facet, facet)
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index
            c = fn(vi, mesh.vertices[vi].co, normals[vi], poly)
            layer.data[li].color = (*(min(1.0, max(0.0, x * shade)) for x in c), alpha)
    return obj


# ── Geometry helpers ──

def catmull(ctrl, n):
    """n points along a Catmull-Rom spline through the control points."""
    ctrl = [Vector(p) for p in ctrl]
    pts = [ctrl[0] * 2 - ctrl[1]] + ctrl + [ctrl[-1] * 2 - ctrl[-2]]
    out = []
    segs = len(ctrl) - 1
    for i in range(n):
        u = i / (n - 1) * segs
        k = min(int(u), segs - 1)
        t = u - k
        p0, p1, p2, p3 = pts[k], pts[k + 1], pts[k + 2], pts[k + 3]
        t2, t3 = t * t, t * t * t
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    return out


def tube(name, pts, radii, sides=7, flute=0.0, flutes=5, twist=0.0, jitter=0.0, cap_end=True):
    """A tube along a polyline, rings oriented by parallel transport. `flute` grooves the
    surface into `flutes` ridges that spiral by `twist` radians per metre (a gnarled,
    twisted trunk). A radius of 0 ends the tube in a point. Returns (object, per-vertex
    info dicts: t along, crest -1..1, cap). UVs in metres (u around, v along) so the bark
    pattern keeps its size."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    tangents = []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
        tangents.append(t.normalized())
    ref = Vector((0, 0, 1)) if abs(tangents[0].z) < 0.9 else Vector((1, 0, 0))
    side = tangents[0].cross(ref).normalized()
    lengths = [0.0]
    for i in range(1, n):
        lengths.append(lengths[-1] + (pts[i] - pts[i - 1]).length)
    total = lengths[-1] or 1.0
    phase = rng.uniform(0, 2 * math.pi)
    verts, info, rings = [], [], []
    for i in range(n):
        t = tangents[i]
        if i > 0:
            prev = tangents[i - 1]
            axis = prev.cross(t)
            if axis.length > 1e-7:
                side = Matrix.Rotation(prev.angle(t), 3, axis.normalized()) @ side
                side = (side - t * side.dot(t)).normalized()
        b = t.cross(side).normalized()
        r = radii[i]
        if r <= 0.0:
            rings.append([len(verts)])
            verts.append(pts[i])
            info.append({"t": lengths[i] / total, "crest": 0.0, "cap": False})
            continue
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            crest = math.cos(flutes * a + phase + twist * lengths[i])
            rr = r * (1 + flute * crest) * (1 + rng.uniform(-jitter, jitter))
            ring.append(len(verts))
            verts.append(pts[i] + (side * math.cos(a) + b * math.sin(a)) * rr)
            info.append({"t": lengths[i] / total, "crest": crest if flute > 0 else 0.0, "cap": False})
        rings.append(ring)
    faces, uvs = [], []
    for i in range(n - 1):
        A, B = rings[i], rings[i + 1]
        circ = 2 * math.pi * max(radii[i], 0.01)
        v0, v1 = lengths[i], lengths[i + 1]
        if len(B) == 1:
            for k in range(sides):
                faces.append((A[k], A[(k + 1) % sides], B[0]))
                u0, u1 = circ * k / sides, circ * (k + 1) / sides
                uvs.append([(u0, v0), (u1, v0), ((u0 + u1) / 2, v1)])
        else:
            for k in range(sides):
                faces.append((A[k], A[(k + 1) % sides], B[(k + 1) % sides], B[k]))
                u0, u1 = circ * k / sides, circ * (k + 1) / sides
                uvs.append([(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
    cap_face = None
    if cap_end and len(rings[-1]) > 1:
        # A separate cap ring so the end stays flat while the bark is smooth.
        c0 = len(verts)
        for vi in rings[-1]:
            verts.append(verts[vi].copy())
            info.append({"t": 1.0, "crest": 0.0, "cap": True})
        cap_face = len(faces)
        faces.append(tuple(range(c0, c0 + sides)))
        uvs.append([(verts[c0 + k] - pts[-1]).to_2d()[:] for k in range(sides)])
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    layer = mesh.uv_layers.new(name="UVMap")
    i = 0
    for face_uvs in uvs:
        for uv in face_uvs:
            layer.data[i].uv = uv
            i += 1
    mesh.update()
    obj = gab.link(bpy.data.objects.new(name, mesh))
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(mesh)
    bm.free()
    gab.smooth(obj, 80)
    if cap_face is not None:
        mesh.polygons[cap_face].use_smooth = False
    return obj, info


def flat(v):
    return Vector((v.x, v.y, 0))


def seen_from(points):
    """How high up the trunk axis these points hide it from the 56-degree camera, at each
    point's worst yaw (the camera on the far side of the axis from the point)."""
    return min((p.z - TAN_CAM * math.hypot(p.x, p.y) for p in points), default=9.0)


# ── Shape of this tree ──

TOP_Z = rng.uniform(2.1, 2.17)              # the top of the crown (card tips)
FORK = rng.uniform(0.76, 0.86)              # where the trunk splits
LIMBS = rng.choice([3, 4, 4, 5])

lean = Vector((rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06), 0))
bend = Vector((rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05), 0))
fork_pt = Vector((0, 0, FORK)) + lean
trunk_ctrl = [Vector((0, 0, -0.05)), Vector((0, 0, FORK * 0.3)) + lean * 0.15 - bend,
              Vector((0, 0, FORK * 0.66)) + lean * 0.55 + bend, fork_pt]
TRUNK_N = 7
trunk_pts = catmull(trunk_ctrl, TRUNK_N)
r_base, r_top = rng.uniform(0.19, 0.21), rng.uniform(0.13, 0.15)


def trunk_radius(z):
    t = clamp01((z + 0.05) / (FORK + 0.05))
    return lerp(r_base, r_top, t ** 0.7) + 0.07 * math.exp(-max(0.0, z) / 0.13)


trunk_radii = [trunk_radius(p.z) for p in trunk_pts]
wood_parts = []
trunk, trunk_info = tube("trunk", trunk_pts, trunk_radii, sides=10, flute=0.12, flutes=5, twist=3.2,
                         jitter=0.03, cap_end=True)
wood_parts.append((trunk, trunk_info, "trunk"))
dense = catmull(trunk_ctrl, 40)


def trunk_at(z):
    return min(dense, key=lambda p: abs(p.z - z))


# Roots: two big knees and two or three small ones, each swelling where it leaves the flare and
# diving into the ground still fat, so the base reads as bulbous rather than clawed.
n_roots = rng.choice([4, 5])
root_kinds = ["big", "big"] + ["small"] * (n_roots - 2)
rng.shuffle(root_kinds)
a0 = rng.uniform(0, 2 * math.pi)
root_angles = []
for i, kind in enumerate(root_kinds):
    a = a0 + 2 * math.pi * (i + rng.uniform(-0.15, 0.15)) / n_roots
    root_angles.append(a)
    d = Vector((math.cos(a), math.sin(a), 0))
    s = Vector((-d.y, d.x, 0)) * rng.uniform(-0.06, 0.06)
    if kind == "big":
        r0, reach, hump, z_in = rng.uniform(0.09, 0.10), rng.uniform(0.38, 0.43), rng.uniform(0.06, 0.09), 0.42
    else:
        r0, reach, hump, z_in = rng.uniform(0.05, 0.06), rng.uniform(0.3, 0.34), rng.uniform(0.04, 0.06), 0.3
    # An arch: out of the flare, a knee standing proud of the trunk, then down steeply.
    ctrl = [d * 0.05 + Vector((0, 0, z_in)), d * (reach * 0.55) + Vector((0, 0, 0.1 + hump)),
            d * (reach - 0.06) + s + Vector((0, 0, 0.05 + hump * 0.5)), d * reach + s * 1.4 + Vector((0, 0, 0.0))]
    pts = catmull(ctrl, 5)
    # Still fat where it meets the ground, closed by a point straight under its end (flattened
    # into the ground below), so it dives in blunt instead of tapering to a claw.
    pts.append(pts[-1] + Vector((0, 0, -0.1)))
    root, info = tube(f"root_{i}", pts, [r0 * 1.0, r0 * 1.15, r0 * 1.0, r0 * 0.82, r0 * 0.68, 0.0],
                      sides=6 if kind == "big" else 5, flute=0.08, flutes=3, twist=4.0, jitter=0.05, cap_end=False)
    wood_parts.append((root, info, "root"))

# A broken stub low on the trunk, where the game camera sees it, end grain showing.
stub_a = rng.uniform(0, 2 * math.pi)
sd = Vector((math.cos(stub_a), math.sin(stub_a), 0))
stub_z = rng.uniform(0.34, 0.44)
stub_base = trunk_at(stub_z)
r_here = trunk_radius(stub_z)
stub_pts = [stub_base + sd * (r_here * 0.5), stub_base + sd * (r_here + 0.07) + Vector((0, 0, 0.05)),
            stub_base + sd * (r_here + 0.13) + Vector((0, 0, 0.1))]
stub, info = tube("stub", stub_pts, [0.055, 0.045, 0.038], sides=6, flute=0.05, flutes=3)
wood_parts.append((stub, info, "stub"))

LIMB_N, LIMB_SIDES = 5, 6
limb_tris = (LIMBS + 1) * ((LIMB_N - 2) * LIMB_SIDES * 2 + LIMB_SIDES)     # limbs + leader, pointed tips


# ── Crown lumps ──

class Lump:
    def __init__(self, centre, radius, kind):
        self.c = Vector(centre)
        self.r = radius
        self.kind = kind
        self.seed = rng.randrange(1 << 30)     # its own stream, so moving it keeps its cards
        self.tone = rng.uniform(-0.07, 0.07)
        self.hue = rng.uniform(-0.012, 0.012)
        self.phase = rng.random()              # the wind phase, in the crown's vertex alpha
        self.rot = rng.uniform(0, 2 * math.pi)  # how its core is turned


lumps = []
limb_dirs = []
a0 = rng.uniform(0, 2 * math.pi)
k_ring = {3: 1.05, 4: 1.0, 5: 0.92}[LIMBS]
# A ring of big lumps at the limb ends, one or two above them, a top lump. Heights are only a
# wish: settle() below lifts each lump until the game camera sees the trunk past it.
for i in range(LIMBS):
    a = a0 + 2 * math.pi * (i + rng.uniform(-0.18, 0.18)) / LIMBS
    d = Vector((math.cos(a), math.sin(a), 0))
    limb_dirs.append(d)
    lumps.append(Lump(d * rng.uniform(RING[0], RING[1]) + Vector((0, 0, rng.uniform(1.36, 1.46))),
                      rng.uniform(0.33, 0.41) * k_ring, "low"))
n_up = 2 if LIMBS == 3 else 1
b0 = a0 + math.pi / LIMBS
for i in range(n_up):
    a = b0 + 2 * math.pi * (i + rng.uniform(-0.15, 0.15)) / n_up
    d = Vector((math.cos(a), math.sin(a), 0))
    lumps.append(Lump(d * rng.uniform(0.14, 0.22) + Vector((0, 0, rng.uniform(1.62, 1.7))),
                      rng.uniform(0.3, 0.36), "up"))
top_lump = Lump((rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05), 1.85), rng.uniform(0.32, 0.38), "top")
lumps.append(top_lump)
# Florets on the rim, in the gaps between the limb-end lumps, pushed out so the outline is
# notched rather than one smooth curve.
n_florets = 2 if LIMBS == 3 else 1
gaps = sorted(range(LIMBS), key=lambda _: rng.random())[:n_florets]
for i in gaps:
    a = a0 + 2 * math.pi * (i + 0.5 + rng.uniform(-0.12, 0.12)) / LIMBS
    d = Vector((math.cos(a), math.sin(a), 0))
    lumps.append(Lump(d * 0.5 + Vector((0, 0, rng.uniform(1.52, 1.62))), rng.uniform(0.24, 0.3), "floret"))

# The silhouette: the crown stretched along one direction and squeezed across it, then shaped.
stretch_a = rng.uniform(0, math.pi)
sa = Vector((math.cos(stretch_a), math.sin(stretch_a), 0))
sb = Vector((-sa.y, sa.x, 0))
k_a, k_b = rng.uniform(1.12, 1.30), rng.uniform(0.82, 0.92)
if SHAPE == "round":
    k_a, k_b = rng.uniform(1.08, 1.14), rng.uniform(0.9, 0.94)
for lump in lumps:
    c = lump.c
    lump.c = sa * (c.dot(sa) * k_a) + sb * (c.dot(sb) * k_b) + Vector((0, 0, c.z))
top_drop = 0.0
if SHAPE == "egg":
    # Taller and narrower: pulled in toward the axis and stretched 1.15 down from the top.
    for lump in lumps:
        lump.c = flat(lump.c) * 0.86 + Vector((0, 0, 1.95 - (1.95 - lump.c.z) * 1.15))
        if lump.kind == "low":
            lump.r *= 1.04
elif SHAPE == "umbrella":
    # Wide and flat: the top pressed down, the rim pushed out toward the footprint's edge.
    top_drop = 0.05
    for lump in lumps:
        if lump.kind == "up":
            lump.c.z -= 0.05
            lump.c += flat(lump.c).normalized() * 0.06
        elif lump.kind in ("low", "floret"):
            lump.c = flat(lump.c).normalized() * (REACH - lump.r * 1.25) + Vector((0, 0, lump.c.z))
elif SHAPE == "lopsided":
    # A few lumps thrown toward one side: the crown leans over like a wind-blown oak.
    side_a = rng.uniform(0, 2 * math.pi)
    sv = Vector((math.cos(side_a), math.sin(side_a), 0))
    rim = [l for l in lumps if l.kind in ("low", "floret")]
    rim.sort(key=lambda l: -flat(l.c).normalized().dot(sv))
    for lump in rim[:2]:
        lump.c += sv * 0.14
    top_lump.c += sv * 0.08
    for lump in rim[-2:]:
        lump.c -= flat(lump.c).normalized() * 0.06
# The florets stand out at the rim.
for lump in lumps:
    if lump.kind == "floret":
        lump.c = flat(lump.c).normalized() * (REACH - lump.r * 1.25) + Vector((0, 0, lump.c.z))


# ── Crown cards ──

def fib_dirs(n, r):
    rot = Quaternion(Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1))).normalized(),
                     r.uniform(0, math.pi))
    out = []
    g = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        rr = math.sqrt(max(0.0, 1 - z * z))
        out.append(rot @ Vector((math.cos(g * i) * rr, math.sin(g * i) * rr, z)))
    return out


def random_tangent(n, r):
    a = Vector((0, 0, 1)) if abs(n.z) < 0.95 else Vector((1, 0, 0))
    t = n.cross(a).normalized()
    return Quaternion(n, r.uniform(0, 2 * math.pi)) @ t


def make_clump(center, normal, size, r, up=None, roll_deg=12.0, v_crop=None, dome=None, curl=None):
    """A leaf-clump card cut to the texture's clump: an octagon (8 triangles round a centre
    vertex) just outside the opaque leaves, so no transparent corner widens the tree or
    hides the trunk. `size` is the side of the texture square it is cut from; the centre
    is domed out by `dome` x size and the rim curls back by `curl` x size, so the clump
    keeps a rounded profile seen edge-on. Its front faces `normal`, the texture's up along
    `up` (world up when None) as far as the facing allows. v_crop cuts the octagon off
    below that texture height (the clump's darkest leaves). Returns (verts, uvs, tris,
    texture v per vertex); vertex 0 is the centre."""
    dome = DOME[0] if dome is None else dome
    curl = DOME[1] if curl is None else curl
    up = Vector((0, 0, 1)) if up is None else Vector(up)
    up = up - normal * up.dot(normal)
    if up.length < 0.2:
        up = random_tangent(normal, r)
    up.normalize()
    up = Quaternion(normal, math.radians(r.uniform(-roll_deg, roll_deg))) @ up
    right = up.cross(normal).normalized()
    mirror = -1.0 if r.random() < 0.5 else 1.0          # mirrored now and then
    lo = v_crop if v_crop is not None else 0.0
    rim = []
    for k in range(8):
        a = math.pi / 8 + k * math.pi / 4
        rim.append((CLUMP_U + CLUMP_R * math.cos(a), max(lo, CLUMP_V + CLUMP_R * math.sin(a))))
    cv = max(CLUMP_V, (lo + CLUMP_V + CLUMP_R) / 2) if v_crop is not None else CLUMP_V
    uv = [(CLUMP_U, cv)] + rim
    verts = []
    for i, (u, v) in enumerate(uv):
        p = center + right * ((u - CLUMP_U) * size * mirror) + up * ((v - cv) * size)
        verts.append(p + normal * (dome * size if i == 0 else -curl * size))
    tris = [(0, 1 + k, 1 + (k + 1) % 8) if mirror > 0 else (0, 1 + (k + 1) % 8, 1 + k) for k in range(8)]
    return verts, uv, tris, [v for _, v in uv]


def fit(verts):
    """Slides a card toward the trunk axis until it fits the footprint."""
    over = max(Vector((p.x, p.y)).length for p in verts) - REACH
    if over > 0:
        d = flat(verts[0]).normalized()
        verts = [p - d * over for p in verts]
    return verts


class Card:
    __slots__ = ("p", "uv", "tris", "v", "li", "n", "role")

    def __init__(self, made, li, n, role):
        self.p, self.uv, self.tris, self.v = made
        self.li, self.n, self.role = li, n, role


def lump_cards(li, density, exclude=True):
    """One lump's crossed pairs of clump cards. Without `exclude` it keeps the cards buried
    in neighbours (for settling the lump on its own)."""
    lump = lumps[li]
    r_ = random.Random(lump.seed)
    c, rad = lump.c, lump.r
    under = lump.kind == "under"
    outer = flat(c).length > 0.4 and not under
    out_dir = flat(c).normalized() if flat(c).length > 0.1 else None
    cards = []
    n_pts = max(5, round(4 * math.pi * rad * rad * density))
    for k, n in enumerate(fib_dirs(n_pts, r_)):
        n = (n + Vector((r_.uniform(-0.1, 0.1), r_.uniform(-0.1, 0.1), r_.uniform(-0.1, 0.1)))).normalized()
        keep_low = r_.random() <= DENSITY_LOW / DENSITY
        layer = LAYERS[k % 2]
        size = r_.uniform(*CARD_K) * math.sqrt(rad / 0.31) / (U1 - U0) * (0.85 if under else 1.0)
        sizes = (r_.uniform(0.92, 1.06), r_.uniform(0.92, 1.06))
        yaws = (math.radians(r_.uniform(25, 40)), -math.radians(r_.uniform(25, 40)))
        spins = (math.radians(r_.uniform(-SPIN, SPIN)), math.radians(r_.uniform(-SPIN, SPIN)))
        tilt_j = r_.uniform(-3.0, 3.0)
        lift = math.radians(r_.uniform(*RIM_LIFT))
        card_rng = random.Random(r_.random())
        if n.z < 0.0 and not keep_low:
            continue    # sparser beneath: little of it is seen
        if n.z < -0.55:
            continue    # the very bottom is the core's
        if outer and n.z < -0.2:
            continue    # outer lumps have no belly: the crown's underside rises to its rim
        if out_dir is not None and n.z - TAN_CAM * n.dot(out_dir) < -1.45:
            continue    # nor does any lump face down along the camera's line of sight to the trunk
        if exclude and any((c + n * rad - o.c).length < o.r for j, o in enumerate(lumps) if j != li):
            continue    # buried in a neighbour
        centre = c + n * rad * layer
        if n.z > 0.3:
            # The upper lump: shingles tilted 22-35 degrees toward the lump's outside (never
            # further, so the 35-degree camera cannot see their backs), the pair splayed
            # +-25-40 degrees round the vertical. The clump's lit top points back toward the
            # lump's crown, turned at random by up to SPIN, so its darker lower leaves gather
            # at the lump's edge; the darkest of them are cut away.
            o = flat(n)
            if o.length < 0.12:
                o = flat(centre) if flat(centre).length > 0.05 else random_tangent(UP, card_rng)
            o.normalize()
            tilt = math.radians(min(MAX_TILT, lerp(35.0, 22.0, smoothstep(0.3, 0.95, n.z)) + tilt_j))
            for y, k_s, spin in zip(yaws, sizes, spins):
                ok = Quaternion(UP, y) @ o
                f = (UP * math.cos(tilt) + ok * math.sin(tilt)).normalized()
                tex_up = Quaternion(f, spin) @ (-ok if TEX_IN else ok)
                cards.append(Card(make_clump(centre, f, size * k_s * 1.08, card_rng, up=tex_up, roll_deg=0,
                                             v_crop=V_CROP), li, n, "top"))
        else:
            # The rim and below: a pair crossed about the vertical, each yawed off the lump's
            # outside and tilted 22-32 degrees to the sky (an upright card turns edge-on to
            # the game camera at the lump's sides: a dark line), texture up.
            role = "rim"
            if out_dir is not None and n.dot(out_dir) > 0.4 and n.z <= 0.2:
                # The crown's lower outer rim: smaller cards pulled in, no beard.
                role = "low"
                centre = c + n * rad * 0.62 * layer / LAYERS[1]
                size *= 0.74
            h = flat(n).normalized()
            for y, k_s in zip(yaws, sizes):
                f = Quaternion(UP, y) @ h
                f = (f * math.cos(lift) + UP * math.sin(lift)).normalized()
                cards.append(Card(make_clump(centre, f, size * k_s, card_rng), li, n, role))
    for cd in cards:
        cd.p = fit(cd.p)
    return cards


def build_cards(density):
    return [cd for li in range(len(lumps)) for cd in lump_cards(li, density)]


ICO_V, ICO_F = None, None


def core_points(lump):
    """The opaque core of a lump: an icosahedron (20 triangles) at 0.6 of its radius,
    a little flattened and sunk, turned about the vertical by the lump's own angle."""
    global ICO_V, ICO_F
    if ICO_V is None:
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
        ICO_V = [v.co.copy() for v in bm.verts]
        ICO_F = [[v.index for v in f.verts] for f in bm.faces]
        bm.free()
    m = Matrix.Rotation(lump.rot, 3, "Z")
    k = lump.r * (0.56 if lump.kind == "under" else 0.6)
    return [lump.c + Vector((0, 0, -0.04 * lump.r)) + (m @ v) * k * Vector((1, 1, 0.86)) for v in ICO_V]


def settle(li, density):
    """Lifts a lump just high enough that the camera sees the trunk to CLEAR past it, but no
    higher than the crown top allows; a lump that cannot fit is drawn in toward the axis."""
    lump = lumps[li]
    for _ in range(10):
        pts = [p for cd in lump_cards(li, density, exclude=False) for p in cd.p] + core_points(lump)
        need = CLEAR + CLEAR_MARGIN - seen_from(pts)
        room = TOP_Z - max(p.z for p in pts)
        if lump.kind == "top":
            lump.c.z += room - top_drop
            if need <= room - top_drop:
                return
            lump.c -= flat(lump.c) * 0.3
            continue
        if need <= 0.0:
            return
        if need <= room:
            lump.c.z += need + 0.002
            return
        lump.c.z += max(0.0, room)
        lump.c -= flat(lump.c).normalized() * ((need - max(0.0, room)) / TAN_CAM + 0.01)


def limb_path(i, end):
    d = limb_dirs[i]
    s = Vector((-d.y, d.x, 0))
    start = fork_pt + d * 0.03 + Vector((0, 0, -0.2 + 0.04 * i / LIMBS))
    curl = rng.uniform(0.1, 0.18) * rng.choice([-1, 1])
    elbow = flat(end) * rng.uniform(0.5, 0.62) + Vector((0, 0, lerp(FORK, end.z, 0.45)))
    ctrl = [start, fork_pt + d * 0.12 + s * curl * 0.6 + Vector((0, 0, 0.1)), elbow - s * curl, end]
    return catmull(ctrl, LIMB_N)


# The card budget: what the wood, the leaf cores (20 triangles a lump, under lumps included) and
# the fungi leave, at 8 triangles a card.
fixed_tris = sum(gab.triangles(o) for o, _, _ in wood_parts) + limb_tris + 20 * (len(lumps) + 3) + 12 * 3
MAX_CARDS = (MAX_TRIS - fixed_tris) // 8
main = list(range(len(lumps)))
start_pos = [l.c.copy() for l in lumps]
density = DENSITY
for attempt in range(6):
    for li in main:
        lumps[li].c = start_pos[li].copy()
        settle(li, density)
    n_main = sum(len(lump_cards(li, density)) for li in main)
    if n_main <= MAX_CARDS * 0.86:
        break
    density *= MAX_CARDS * 0.84 / n_main

# ── Limbs: from inside the trunk below the fork, an S-curve out and up into the ring lumps ──
limb_paths = [limb_path(i, lumps[i].c - Vector((0, 0, 0.04))) for i in range(LIMBS)]

# Under lumps: small, dark clumps hugging two or three limbs above the camera's line of sight
# to the trunk, so the crown has a full underside from the side instead of a lid on sticks.
n_under = min(LIMBS, rng.choice([2, 3, 3]))
for i in sorted(range(LIMBS), key=lambda _: rng.random())[:n_under]:
    want = rng.uniform(1.1, 1.22)
    cands = [p for p in limb_paths[i] if 0.16 <= flat(p).length <= 0.34] or limb_paths[i][1:3]
    p = min(cands, key=lambda q: abs(q.z - want))
    s = Vector((-limb_dirs[i].y, limb_dirs[i].x, 0))
    lump = Lump(p + limb_dirs[i] * 0.02 + s * rng.uniform(-0.04, 0.04) + Vector((0, 0, 0.02)),
                rng.uniform(0.18, 0.24), "under")
    lumps.append(lump)
    settle(len(lumps) - 1, density)

cards = build_cards(density)
lifts = 0
for attempt in range(40):
    pts = [p for cd in cards for p in cd.p] + [p for l in lumps for p in core_points(l)]
    top = max(p.z for p in pts)
    need = (CLEAR + CLEAR_MARGIN) * max(1.0, top / MAX_HEIGHT)
    bad = {cd.li for cd in cards if seen_from(cd.p) < need}
    bad |= {li for li, l in enumerate(lumps) if seen_from(core_points(l)) < need}
    if not bad and len(cards) <= MAX_CARDS:
        break
    if len(cards) > MAX_CARDS:
        density *= MAX_CARDS / len(cards) * 0.98
    # Lift the lumps that hide the trunk (and draw them in a touch) until the check holds.
    for li in bad:
        lumps[li].c.z += 0.03
        lumps[li].c -= flat(lumps[li].c) * 0.02
    lifts += bool(bad)
    cards = build_cards(density)
else:
    raise RuntimeError(f"crown still hides the trunk below {CLEAR} or has {len(cards)} cards")

for i in range(LIMBS):
    pts = limb_paths[i]
    pts[-1] = lumps[i].c - Vector((0, 0, 0.04))      # the lump may have been lifted since
    r0 = rng.uniform(0.09, 0.1)
    limb, info = tube(f"limb_{i}", pts, [r0, r0 * 0.82, r0 * 0.64, r0 * 0.46, 0.0], sides=LIMB_SIDES, cap_end=False)
    wood_parts.append((limb, info, "limb"))

# A leader up the middle into the top lump.
lead_ctrl = [fork_pt + Vector((0, 0, -0.12)), fork_pt + Vector((0.02, -0.01, 0.28)), top_lump.c - Vector((0, 0, 0.12))]
leader, info = tube("leader", catmull(lead_ctrl, LIMB_N), [0.085, 0.07, 0.052, 0.035, 0.0], sides=LIMB_SIDES,
                    cap_end=False)
wood_parts.append((leader, info, "limb"))


def bark_color(info, kind):
    def fn(vi, co, n, poly):
        inf = info[vi]
        if inf["cap"]:
            # End grain on the stub; the fork's cap is hidden bark.
            return col(WOOD_LIGHT) * 0.95 if kind == "stub" else col(BARK_DARK)
        z = co.z
        c = ramp([(0.0, col(ROOT_DARK)), (0.2, col(BARK_DARK)), (0.55, col(BARK)), (1.0, col(BARK_MID)),
                  (1.6, col(WOOD))], z)
        # Ridges catch the light, grooves stay dark.
        crest = inf["crest"]
        c = lerp(c, col(ROOT_DARK) * 0.8, 0.45 * max(0.0, -crest))
        c = lerp(c, col(WOOD_LIGHT), 0.34 * max(0.0, crest) * max(0.0, n.z + 0.5))
        # Top-lit: upper faces warm, lower faces cool and dark.
        c = c * (0.8 + 0.28 * max(0.0, n.z) + 0.15 * min(0.0, n.z))
        # Moss on the up-facing tops of the roots.
        if kind == "root":
            moss = smoothstep(0.3, 0.8, n.z) * smoothstep(0.02, 0.08, z) * smoothstep(0.34, 0.16, z)
            c = lerp(c, lerp(col(MOSS), col(MOSS_LIGHT), 0.3 * max(0.0, crest)), 0.5 * moss)
        return c
    return fn


PAINTED = gab.painted()
for obj, info, kind in wood_parts:
    paint_fn(obj, bark_color(info, kind), "bark", 0.05)
    obj.data.materials.append(PAINTED)


# ── Glowing shelf fungi on the lower trunk ──

def shelf(name, z, a, rho):
    """A bracket fungus (12 triangles): a domed half-disc standing out of the trunk at
    height z, toward angle a, its underside sloping back into the bark."""
    d = Vector((math.cos(a), math.sin(a), 0))
    s = Vector((-d.y, d.x, 0))
    p = trunk_at(z) + d * (trunk_radius(z) * 0.9)
    p.z = z
    arc = []
    for k in range(7):
        t = math.pi * (k / 6 - 0.5)
        arc.append(p + (d * math.cos(t) * 1.0 + s * math.sin(t) * 1.15) * rho - Vector((0, 0, 0.12 * rho)))
    top_c = p + Vector((0, 0, 0.3 * rho)) - d * 0.01
    bot_c = p - Vector((0, 0, 0.55 * rho)) - d * 0.02
    verts = [top_c, bot_c] + arc
    faces = [(0, 2 + k + 1, 2 + k) for k in range(6)] + [(1, 2 + k, 2 + k + 1) for k in range(6)]
    obj = gab.mesh_object(name, verts, faces)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    gab.flat(obj)
    return obj


fungi = []
if GLOW:
    glow = gab.glow("glow", FUNGUS, 1.5)
    # A pair stacked on one side and one more round the trunk, away from the stub.
    fa = stub_a + math.pi + rng.uniform(-0.6, 0.6)
    spots = [(rng.uniform(0.14, 0.18), fa, rng.uniform(0.07, 0.08)),
             (rng.uniform(0.25, 0.3), fa + rng.uniform(0.35, 0.55) * rng.choice([-1, 1]), rng.uniform(0.055, 0.065))]
    if rng.random() < 0.7:
        spots.append((rng.uniform(0.13, 0.2), fa + math.pi + rng.uniform(-0.8, 0.8), rng.uniform(0.05, 0.06)))
    for k, (z, a, rho) in enumerate(spots):
        f = shelf(f"fungus_{k}", z, a, rho)
        f.data.materials.append(glow)
        fungi.append(f)


# ── Crown mesh, tint and normals ──

crown_lo = min(l.c.z - l.r for l in lumps if l.kind != "under")
crown_hi = max(l.c.z + l.r for l in lumps)
main_l = [l for l in lumps if l.kind != "under"]
cx = sum(l.c.x for l in main_l) / len(main_l)
cy = sum(l.c.y for l in main_l) / len(main_l)
crown_mid = Vector((cx, cy, (crown_lo + crown_hi) / 2))
crown_rx = max(Vector((l.c.x - cx, l.c.y - cy)).length + l.r for l in main_l)
crown_rz = (crown_hi - crown_lo) / 2

# Ramps. Green: a cool deep shade, the leaf body colour over most of the crown, lime only on the
# highest caps. Autumn: crimson shade rather than brown-black, the sun-lit top a richer tip; red
# keeps more of its body colour so it reads crimson next to amber.
WARM = col(LEAF).x > col(LEAF).y
RED = WARM and hue_of(LEAF) * 360 < 15
if WARM:
    # Autumn shade turns toward crimson and gets richer, never brown-black.
    DARK = gab.hsv(LEAF, -0.03, 0.12, -0.08) if RED else gab.hsv(LEAF, -0.03, 0.14, -0.1)
    DEEP = gab.hsv(LEAF, -0.05, 0.18, -0.16) if RED else gab.hsv(LEAF, -0.05, 0.18, -0.18)
    if RED:
        TOP = gab.hsv(TIP, 0.0, 0.15, -0.10)
        stops = [(0.0, col(DEEP)), (0.2, col(DARK)), (0.60, col(LEAF)), (0.95, col(LEAF_LIGHT)), (1.20, col(TOP))]
        HUE_SKEW = -0.012
    else:
        # Amber's body and light a touch richer than the params, so it reads gold-orange
        # rather than tan under a neutral light.
        TOP = gab.hsv(TIP, 0.0, 0.2, -0.10)
        stops = [(0.0, col(DEEP)), (0.2, col(DARK)), (0.42, col(gab.hsv(LEAF, 0, 0.08, 0))),
                 (0.74, col(gab.hsv(LEAF_LIGHT, 0, 0.1, 0))), (1.08, col(TOP))]
        HUE_SKEW = 0.0
    SEAM, OVER, V_FLOOR, BIAS = 0.3, 0.26, 0.36, 0.0
    V_CEIL = 0.80 if RED else 0.74
else:
    DARK = cool(LEAF, 0.08, -0.12, 0.06)
    DEEP = cool(LEAF, 0.12, -0.24, 0.08)
    stops = [(0.0, col(DEEP)), (0.22, col(DARK)), (0.6, col(LEAF)), (0.93, col(LEAF_LIGHT)), (1.15, col(TIP))]
    SEAM, OVER, V_FLOOR, V_CEIL, BIAS, HUE_SKEW = 0.28, 0.24, 0.22, 1.0, -0.10, 0.008
T_DARK = stops[1][0]
LIFT_TOP = (gab.param("lift", 0.7), gab.param("lift_cap", 2.2))
CREVICE = (1.3, 0.85)   # the crevice shade: from this far into a neighbour (in its radii) to full

verts, faces, uvs, owner, roles, texv, card_of = [], [], [], [], [], [], []
for ci, cd in enumerate(cards):
    base = len(verts)
    verts += cd.p
    owner += [cd.li] * len(cd.p)
    roles += [cd.role] * len(cd.p)
    texv += cd.v
    card_of += [ci] * len(cd.p)
    for tri in cd.tris:
        faces.append(tuple(base + i for i in tri))
        uvs.append([cd.uv[i] for i in tri])
crown = gab.mesh_object("crown", verts, faces, uvs)
crown.data.materials.append(gab.foliage("foliage_leaves"))


def lump_shade(p, own, li_own):
    """The tint ramp position of a point of lump `own`: crown height, the lump's own lit cap
    over its shaded skirt, seams and contact shade from the lumps around it."""
    nl = (p - own.c).normalized()
    # Crevices: where this lump runs into another, both sides darken, so each clump is
    # outlined by shade instead of melting into its neighbours.
    d2 = min(((p - o.c).length / o.r for j, o in enumerate(lumps) if j != li_own), default=9)
    seam = smoothstep(CREVICE[0], CREVICE[1], d2)
    over = 0.0
    for j, o in enumerate(lumps):
        if j != li_own and o.c.z > own.c.z + 0.02:
            under = smoothstep(1.15, 0.8, flat(p - o.c).length / o.r)
            over = max(over, under * smoothstep(0.0, 0.3, (o.c.z - p.z) / o.r))
    depth = (p - own.c).length / own.r
    outer = smoothstep(0.5, 1.05, depth)
    h = clamp01((p.z - crown_lo) / (crown_hi - crown_lo))
    cap = smoothstep(-0.25, 0.65, nl.z)
    return 0.25 * h + 0.6 * cap + 0.08 * outer - SEAM * seam - OVER * over + BIAS + own.tone, nl


def finish_tint(c, own, li_own):
    c = shift(c, own.hue + HUE_SKEW)
    c = floor_value(c, V_FLOOR)
    return ceil_value(c, V_CEIL)


def tex_lift(v, strength, cap, target=0.44):
    """How much to brighten a card's tint at texture height v so the texture's darker rows
    come up toward `target` (linear luminance), partially (`strength`)."""
    lum = LEAF_LUM[-1][1]
    for (v0, l0), (v1, l1) in zip(LEAF_LUM, LEAF_LUM[1:]):
        if v <= v1:
            lum = lerp(l0, l1, (v - v0) / (v1 - v0))
            break
    return max(1.0, min(cap, (target / lum) ** strength))


def fit_channels(c):
    """A linear colour scaled down until no channel exceeds 1, so a lift never clips one
    channel first and shifts the hue."""
    m = max(c)
    return c / m if m > 1.0 else c


mesh = crown.data
loop_normals = []
layer = gab._color_layer(mesh)
card_shade = [1.0 + rng.uniform(-0.05, 0.05) for _ in cards]
for poly in mesh.polygons:
    fnorm = poly.normal.copy()
    for li in poly.loop_indices:
        vi = mesh.loops[li].vertex_index
        p = mesh.vertices[vi].co
        own_i = owner[vi]
        own = lumps[own_i]
        t, nl = lump_shade(p, own, own_i)
        q = p - crown_mid
        ng = Vector((q.x / crown_rx, q.y / crown_rx, q.z / crown_rz)).normalized()
        nf = (nl * 0.72 + ng * 0.28).normalized()
        loop_normals.append((nf * 0.92 + fnorm * 0.08).normalized())
        if own.kind == "under":
            t = min(t, T_DARK)          # under lumps stay in the crown's shade
        if roles[vi] == "low":
            t = max(t, T_DARK)          # the lower rim: never the deepest crimson
        c = finish_tint(ramp(stops, t) * card_shade[card_of[vi]], own, own_i)
        # The texture's darker lower leaves lifted (fully on the shingles, a little on the
        # upright cards, whose dark foot is the clump's own shade).
        c = fit_channels(c * (tex_lift(texv[vi], LIFT_TOP[0], LIFT_TOP[1]) if roles[vi] == "top" else tex_lift(texv[vi], 0.4, 1.6)))
        if gab.param("debug", 0) == 2:
            c = Vector(colorsys.hsv_to_rgb((own_i * 0.37) % 1.0, 0.8, 0.9)) * (0.4 + 0.6 * clamp01(t))
        layer.data[li].color = (*c, own.phase)
mesh.normals_split_custom_set(loop_normals)

# The cores: one opaque leaf ball per lump, painted a shade darker than its cards, so a gap
# between cards shows shaded leaves (never the ground), and each lump shadows the one below.
core_parts = []
for li, lump in enumerate(lumps):
    pts = core_points(lump)
    core = gab.mesh_object(f"core_{li}", pts, ICO_F)
    bm = bmesh.new()
    bm.from_mesh(core.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(core.data)
    bm.free()
    gab.uv_box(core)
    gab.smooth(core, 89)

    def core_color(vi, co, n, poly, lump=lump, li=li):
        t, nl = lump_shade(co, lump, li)
        # Autumn cores stay in the crimson shade (a dark orange would read brown).
        t = min(t * 0.7, (0.5 if not WARM else 0.32) if lump.kind != "under" else T_DARK)
        return finish_tint(ramp(stops, t) * 0.8, lump, li)
    paint_fn(core, core_color, "leaves", 0.03)
    core.data.materials.append(PAINTED)
    core_parts.append(core)

wood = gab.join([o for o, _, _ in wood_parts] + core_parts + fungi, "wood")
wood.data.name = "wood"
for v in wood.data.vertices:
    v.co.z = max(v.co.z, -0.01)     # what dives into the ground stops just under it
wood_tris = gab.triangles(wood)

# Keep the whole tree under MAX_HEIGHT: scale it about the trunk base.
top = max(max(v.co.z for v in crown.data.vertices), max(v.co.z for v in wood.data.vertices))
scale = 1.0
if top > MAX_HEIGHT:
    scale = MAX_HEIGHT / top
    for obj in (wood, crown):
        obj.scale = (scale, scale, scale)
        gab.apply_transform(obj)
    mesh.normals_split_custom_set(loop_normals)

# The hard checks, on the final mesh: the trunk shows at least CLEAR up its axis from every yaw
# (crown cards and leaf cores), and the triangle budget holds.
final = [crown.matrix_world @ v.co for v in crown.data.vertices]
core_final = [p * scale for l in lumps for p in core_points(l)]
seen = seen_from(final + core_final)
if seen < CLEAR:
    raise RuntimeError(f"crown hides the trunk from {seen:.3f} (need {CLEAR})")
if gab.triangles() > MAX_TRIS:
    raise RuntimeError(f"{gab.triangles()} triangles (budget {MAX_TRIS})")

if gab.param("crown_only", 0):
    bpy.data.objects.remove(wood)      # for measuring the crown's colours on its own
if gab.param("debug", 0):
    for i, l in enumerate(lumps):
        print(f"broadleaf: lump {i} {l.kind:6s} rc {flat(l.c).length:.2f} z {l.c.z:.2f} r {l.r:.2f} "
              f"cards {sum(1 for cd in cards if cd.li == i)}")
print(f"broadleaf: shape {SHAPE}, {LIMBS} limbs, {len(lumps)} lumps ({n_under} under), {len(cards)} cards "
      f"(density {density:.1f}), {lifts} lifts, fungi {len(fungi)}, wood+cores {wood_tris} + crown "
      f"{gab.triangles(crown)} = {gab.triangles()} triangles, trunk seen to {seen:.3f}, scale {scale:.3f}, "
      f"crown z {min(p.z for p in final):.2f}..{max(p.z for p in final):.2f}")
