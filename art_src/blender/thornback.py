"""Thornback: a slow, armoured hedgehog-boar creep for Wickhollow.

Build:
    godot-agent asset blender . art_src/blender/thornback.py --to res://models/creeps/thornback.glb \
        --seed 1 --review --no-import

A heavy, dark, smooth-shaded boar body lofted from cross-sections, kept well below the dirt path's
value so the creep reads against it; a dark shaggy mantle whose side fringe hangs as locks over the
flank; out of it rise chevron rows of thin, crisp quills (one ridge up, dark to the middle, then a pale
bone tip), three thick banded hero spikes per side splayed out at the shoulder hump, and a dark spine
crest alternating tall and short. A wedge-shaped head (wide jowls into an upturned snout ending in a
flared, flat pig-snout pad with recessed nostrils), a painted mouth line, tusks hooking back beside
the snout, heavy brow ridges over big glowing red eyes whose upper lid is cut flat and slants down
toward the snout, ears standing out beside the forehead crest; a cheek ruff of fur locks; four sturdy
legs with thigh mass, a fetlock tuft and cloven hooves.
Rigged with a small skeleton and a looping 24-frame 'walk' (a heavy diagonal trot: the hips ride on
the planted legs, the body sinks and rolls after each footfall, the head nods late, the ears flop and
the quills follow the body's sway and bristle in a smooth damped shiver after every footfall, rippling
front to back, with a little looping jitter per side).

The scale is set by the body's mass (TARGET_HEIGHT_BODY), so the quill tips stand proud at about 0.58.
The walk matches a ground speed of STRIDE (printed at the end, in game units at the game's 1.35
scale); Game.CREEPS["thornback"]["stride"] should be set to it so the hooves do not slide.

Params:
    pose_frame    bake the walk at this frame into the mesh (preview only; no rig in the output)
    per_row       quills per chevron row (default 12)
    quill_smooth  0 (default) flat-shaded quills with crisp lit and shaded facets, 1 smooth-shaded
    only          preview only: build just these parts (comma list of body,mantle,head,legs,quills,fur)
"""

import math
import random

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

import gab

R = gab.rng
# the painted facet jitter draws from its own generator (seeded from gab.rng), so recolouring a part
# does not reshuffle the quill layout that follows it
FACET_R = random.Random(R.random())

# ── Palette (palettes/hollow.gpl) ──
HIDE = "#6b4a34"
HIDE_DARK = "#4a3324"
LEG = "#3e2a1e"
SPIKE = "#d8c8a8"
TUSK = "#efe6d6"
EYE = "#ff5a3a"
WOOD = "#7a5534"
WOOD_LIGHT = "#a0784a"
WOOD_DARK = "#4e3423"
BARK = "#5b3a29"
SLIT = "#1a1410"
SHELL_DARK = "#2a1e24"
STALK = "#e6dcc3"
PUMPKIN_DARK = "#a8521e"
BRONZE = "#b07a3a"
GLOW_ORANGE = "#ffb040"

# the scale is set by the body's mass (body, mantle, head), not by the quills, so taller spikes
# stand proud instead of shrinking the boar
TARGET_HEIGHT_BODY = 0.445
EYE_EMISSION = (1.0, 0.022, 0.009)     # linear; sRGB about #ff2911, a deeper eye_red for the glow only
EYE_GLOW = 2.2
POSE_FRAME = gab.param("pose_frame", -1)
PER_ROW = gab.param("per_row", 12)
QUILL_SMOOTH = bool(gab.param("quill_smooth", 0))


def lin(c) -> Vector:
    return Vector(gab.rgb(c))


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t


def rust(t=0.35):
    """Warm, saturated reddish brown: wood pushed toward pumpkin_dark."""
    return lerp(lin(WOOD), lin(PUMPKIN_DARK), t)


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


# ── Mesh helpers ──

def finish(obj, smooth=True, recalc=True):
    if recalc:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(obj.data)
        bm.free()
    obj.data.update()
    for poly in obj.data.polygons:
        poly.use_smooth = smooth
    return obj


def ring_points(c, ax, az, bot, ex, sides, phase=0.0):
    pts = []
    for j in range(sides):
        phi = 2 * math.pi * j / sides + phase
        s, k = math.sin(phi), math.cos(phi)
        sx = math.copysign(abs(s) ** ex, s)
        sz = math.copysign(abs(k) ** ex, k)
        if sz < 0:
            sz *= bot
        pts.append(c + ax * sx + az * sz)
    return pts


def loft(name, rings, sides, cap0=0.0, cap1=0.0, phase=0.0, smooth=True):
    """rings: [(center, x half-axis vector, up half-axis vector, bottom factor, exponent)].
    cap0/cap1: the end caps' centre pushed out along the path by this much (None: open)."""
    verts, faces = [], []
    for c, ax, az, bot, ex in rings:
        verts += ring_points(c, ax, az, bot, ex, sides, phase)
    n = len(rings)
    for i in range(n - 1):
        for j in range(sides):
            a, b = i * sides + j, i * sides + (j + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    for which, push in ((0, cap0), (n - 1, cap1)):
        if push is None:
            continue
        c = rings[which][0]
        nb = rings[1][0] if which == 0 else rings[-2][0]
        out = (c - nb).normalized()
        ci = len(verts)
        verts.append(c + out * push)
        base = which * sides
        for j in range(sides):
            faces.append((base + j, base + (j + 1) % sides, ci))
    obj = gab.mesh_object(name, verts, faces)
    return finish(obj, smooth)


def frame_from(t):
    t = t.normalized()
    up = Vector((0, 0, 1)) if abs(t.z) < 0.95 else Vector((0, 1, 0))
    side = t.cross(up).normalized()
    up = side.cross(t).normalized()
    return side, up


def tube(name, points, radii, sides, flat=1.0, tip=True, twist_up=None, smooth=True, cap0=0.0):
    """A tapered tube along points; radii per point. flat squashes the cross-section.
    cap0: the root cap pushed back by this much, or None for an open root (buried in a body)."""
    rings = []
    for i, p in enumerate(points):
        t = (points[min(i + 1, len(points) - 1)] - points[max(i - 1, 0)])
        side, up = frame_from(t)
        if twist_up is not None:
            side = t.normalized().cross(twist_up).normalized()
            up = side.cross(t.normalized()).normalized()
        r = radii[i]
        rings.append((p, side * r, up * r * flat, 1.0, 1.0))
    if tip:
        verts, faces = [], []
        for c, ax, az, bot, ex in rings[:-1]:
            verts += ring_points(c, ax, az, bot, ex, sides)
        n = len(rings) - 1
        for i in range(n - 1):
            for j in range(sides):
                a, b = i * sides + j, i * sides + (j + 1) % sides
                faces.append((a, b, b + sides, a + sides))
        ti = len(verts)
        verts.append(points[-1])
        base = (n - 1) * sides
        for j in range(sides):
            faces.append((base + j, base + (j + 1) % sides, ti))
        if cap0 is not None:
            ci = len(verts)
            verts.append(points[0] - (points[1] - points[0]).normalized() * cap0)
            for j in range(sides):
                faces.append((j, (j + 1) % sides, ci))
        return finish(gab.mesh_object(name, verts, faces), smooth)
    return loft(name, rings, sides, cap0=cap0, cap1=0.0, smooth=smooth)


def fur_uv(obj, scale=1.0, stroke=3.5):
    """Box-projected UVs in metres with v squashed, so the 'thatch' pattern paints short fur
    strokes instead of long straw."""
    gab.uv_box(obj, scale)
    for loop_uv in obj.data.uv_layers["UVMap"].data:
        loop_uv.uv = (loop_uv.uv[0], loop_uv.uv[1] * stroke)
    return obj


def bezier(p0, p1, p2, t):
    return p0 * (1 - t) ** 2 + p1 * 2 * (1 - t) * t + p2 * t * t


def ellipsoid(name, center, axes, segments=6, rings=4, cut=None):
    """A UV ellipsoid stretched along three axis vectors (their lengths are the radii).
    Built from vertex lists rather than the sphere operator, whose face order is not
    repeatable from run to run. cut=(a0, k) flattens the side toward axes[1]: no vertex
    reaches further along it than a0 + k * (its offset along axes[0])."""
    unit = [Vector((0, 0, 1))]
    for i in range(1, rings):
        th = math.pi * i / rings
        for j in range(segments):
            ph = 2 * math.pi * j / segments
            unit.append(Vector((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th))))
    unit.append(Vector((0, 0, -1)))
    bottom = len(unit) - 1
    faces = []
    ring = lambda i, j: 1 + (i - 1) * segments + j % segments  # noqa: E731
    for j in range(segments):
        faces.append((0, ring(1, j), ring(1, j + 1)))
        for i in range(1, rings - 1):
            faces.append((ring(i, j), ring(i + 1, j), ring(i + 1, j + 1), ring(i, j + 1)))
        faces.append((bottom, ring(rings - 1, j + 1), ring(rings - 1, j)))
    m = Matrix((axes[0], axes[1], axes[2])).transposed()
    if m.determinant() < 0:
        faces = [tuple(reversed(f)) for f in faces]
    verts = [center + m @ u for u in unit]
    if cut is not None:
        e0, e1 = axes[0].normalized(), axes[1].normalized()
        for i, v in enumerate(verts):
            d = v - center
            limit = cut[0] + cut[1] * d.dot(e0)
            if d.dot(e1) > limit:
                verts[i] = v - e1 * (d.dot(e1) - limit)
    return finish(gab.mesh_object(name, verts, faces), True, recalc=False)


# ── Colour and weights ──

def vcolor(obj, fn, pattern="plain", facet=0.015):
    """Per-corner colour from fn(world co, face normal, vertex index) -> linear Vector."""
    mesh = obj.data
    layer = mesh.color_attributes.get("Color")
    if layer is None:
        layer = mesh.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="CORNER")
    mesh.color_attributes.active_color = layer
    alpha = (gab.PATTERNS.index(pattern) + 0.5) / 16
    mw = obj.matrix_world
    rot = mw.to_3x3()
    for poly in mesh.polygons:
        shade = 1.0 + FACET_R.uniform(-facet, facet)
        n = (rot @ poly.normal).normalized()
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index
            co = mw @ mesh.vertices[vi].co
            c = fn(co, n, vi)
            layer.data[li].color = (*(max(0.0, min(1.0, ch * shade)) for ch in c), alpha)
    return obj


def weigh(obj, fn):
    """Vertex groups from fn(world co, vertex index) -> {bone: weight}, normalised."""
    groups = {}
    mw = obj.matrix_world
    for v in obj.data.vertices:
        w = {k: x for k, x in fn(mw @ v.co, v.index).items() if x > 1e-4}
        total = sum(w.values()) or 1.0
        for bone, x in w.items():
            if bone not in groups:
                groups[bone] = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
            groups[bone].add([v.index], x / total, "REPLACE")
    return obj


def torso_w(co):
    y = co.y
    if y > 0.0:
        return {"body": 1.0}
    if y > -0.12:
        t = smoothstep(0.0, -0.12, y)
        return {"body": 1 - t, "chest": t}
    if y > -0.165:
        return {"chest": 1.0}
    t = smoothstep(-0.165, -0.205, y)
    return {"chest": 1 - t, "head": t}


def head_w(co, vi):
    return {"head": 1.0}


PARTS = []
TRIS = {}


def part(obj, mat=None, weights=None):
    gab.assign(obj, mat or gab.painted())
    if weights is not None:
        weigh(obj, weights)
    PARTS.append(obj)
    key = obj.name.split(".")[0]
    TRIS[key] = TRIS.get(key, 0) + gab.triangles(obj)
    return obj


# ── Body ──
# (y, z centre, half width, half height above, half height below, exponent)
BODY = [
    (0.300, 0.282, 0.050, 0.045, 0.040, 1.0),
    (0.278, 0.288, 0.110, 0.092, 0.085, 0.9),
    (0.232, 0.293, 0.150, 0.116, 0.108, 0.85),
    (0.165, 0.297, 0.176, 0.130, 0.122, 0.82),
    (0.090, 0.300, 0.190, 0.138, 0.133, 0.8),
    (0.010, 0.307, 0.197, 0.146, 0.138, 0.8),
    (-0.065, 0.315, 0.193, 0.153, 0.130, 0.8),
    (-0.125, 0.312, 0.178, 0.146, 0.122, 0.82),
    (-0.170, 0.302, 0.155, 0.128, 0.114, 0.85),
    (-0.205, 0.292, 0.130, 0.106, 0.102, 0.9),
]


def body_section(y):
    """Interpolated body cross-section at y."""
    secs = BODY
    if y >= secs[0][0]:
        return secs[0]
    for a, b in zip(secs, secs[1:]):
        if a[0] >= y >= b[0]:
            t = (a[0] - y) / (a[0] - b[0])
            return tuple(a[i] + (b[i] - a[i]) * t for i in range(6))
    return secs[-1]


def body_point(y, phi):
    _, zc, w, top, bot, ex = body_section(y)
    s, k = math.sin(phi), math.cos(phi)
    sx = math.copysign(abs(s) ** ex, s)
    sz = math.copysign(abs(k) ** ex, k)
    sz *= top if sz >= 0 else bot
    return Vector((w * sx, y, zc + sz))


def body_normal(y, phi):
    e = 0.004
    dy = body_point(y + e, phi) - body_point(y - e, phi)
    dp = body_point(y, phi + e) - body_point(y, phi - e)
    n = dp.cross(dy).normalized()
    p = body_point(y, phi)
    if n.dot(p - Vector((0, y, body_section(y)[1]))) < 0:
        n = -n
    return n


# ── Mantle: a shaggy dark cape over the back with a jagged fringe ──
MANTLE_Y0, MANTLE_Y1 = -0.228, 0.275


def mantle_edge(u):
    """The mantle's lower edge as an angle from the top (radians), u: 0 neck .. 1 rump."""
    return math.radians(70 + 24 * smoothstep(0.0, 0.3, u) - 18 * smoothstep(0.8, 1.0, u))


def mantle_edge_z(y):
    u = (y - MANTLE_Y0) / (MANTLE_Y1 - MANTLE_Y0)
    return body_point(y, mantle_edge(max(0.0, min(1.0, u)))).z


def build_body():
    rings = [(Vector((0, y, zc)), Vector((w, 0, 0)), Vector((0, 0, top)), bot / top, ex)
             for y, zc, w, top, bot, ex in BODY]
    body = loft("body", rings, 16, cap0=0.012, cap1=0.0)
    fur_uv(body)

    def col(co, n, vi):
        # dark value steps, well below the dirt path's: a cool belly wedge, a dark hide flank and
        # a slightly warmer band just under the mantle fringe (the mantle covers the top)
        ze = mantle_edge_z(max(-0.2, min(0.29, co.y)))
        belly = lerp(lin(SHELL_DARK), lin(HIDE_DARK), 0.45)
        c = lerp(belly, lerp(lin(HIDE_DARK), lin(HIDE), 0.2), smoothstep(0.175, 0.235, co.z))
        c = lerp(c, lerp(lin(HIDE_DARK), lin(WOOD), 0.4), smoothstep(ze - 0.05, ze - 0.02, co.z) * 0.35)
        return c
    vcolor(body, col, "thatch")
    part(body, weights=lambda co, vi: torso_w(co))
    return body


def build_mantle():
    C, RN = 12, 6
    verts, faces, info = [], [], []
    idx = {}
    for c in range(C + 1):
        u = c / C
        y = lerp(MANTLE_Y0, MANTLE_Y1, u)
        phe = mantle_edge(u)
        for r in range(RN + 1):
            s = r / RN * 2 - 1
            side_edge = r in (0, RN)
            phi, yy = s * phe, y
            off = 0.022 * (1 - 0.3 * abs(s) ** 2) + R.uniform(-0.004, 0.004)
            tipness = 0.0
            drop = 0.0
            if side_edge:
                if c % 2 == 0 and 0 < c < C:
                    phi = math.copysign(phe + math.radians(R.uniform(22, 30)), s)
                    yy = y + 0.035
                    tipness = 1.0
                    off = 0.022
                    drop = 0.02
                else:
                    phi = math.copysign(phe - math.radians(7), s)
                    off = 0.012
            if c == 0 and not side_edge:
                yy = y - (0.032 if r % 2 == 0 else 0.0)        # collar locks over the neck
                off = 0.03 if r % 2 == 0 else 0.022
                tipness = 1.0 if r % 2 == 0 else 0.3
            if c == C and not side_edge:
                yy = y + (0.04 if r % 2 == 0 else 0.0)         # rump fringe over the tail
                off = 0.012
                tipness = 1.0 if r % 2 == 0 else 0.3
            p = body_point(yy, phi)
            n = body_normal(yy, phi)
            idx[c, r] = len(verts)
            verts.append(p + n * off - Vector((0, 0, drop)))
            info.append((abs(s), tipness))
    for c in range(C):
        for r in range(RN):
            faces.append((idx[c, r], idx[c, r + 1], idx[c + 1, r + 1], idx[c + 1, r]))
    # the boundary folds back under itself into the body, so the fringe has a lip
    loop = ([(c, 0) for c in range(C + 1)] + [(C, r) for r in range(1, RN + 1)]
            + [(c, RN) for c in range(C - 1, -1, -1)] + [(0, r) for r in range(RN - 1, 0, -1)])
    centre = Vector((0, (MANTLE_Y0 + MANTLE_Y1) / 2, 0.42))
    tucks = []
    for key in loop:
        v = verts[idx[key]]
        inward = (centre - v)
        inward.z = 0.0
        t = v + inward.normalized() * 0.03 + Vector((0, 0, -0.02))
        tucks.append(len(verts))
        verts.append(t)
        info.append((1.0, -1.0))
    for i in range(len(loop)):
        a, b = idx[loop[i]], idx[loop[(i + 1) % len(loop)]]
        ta, tb = tucks[i], tucks[(i + 1) % len(loop)]
        faces.append((b, a, ta, tb))
    obj = gab.mesh_object("mantle", verts, faces)
    finish(obj, True)
    # make sure the cape faces outward
    top = obj.data.polygons[0]
    for poly in obj.data.polygons:
        if poly.center.z > top.center.z:
            top = poly
    if top.normal.z < 0:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.to_mesh(obj.data)
        bm.free()
    fur_uv(obj, 1.0, 3.0)

    def col(co, n, vi):
        a, tip = info[vi]
        if tip < 0:
            return lin(SLIT)
        c = lerp(lin(LEG), lin(HIDE_DARK), a)
        # shaggy locks hang over the flank, a little warmer at their ends (never orange)
        return lerp(c, lerp(lin(HIDE_DARK), lin(WOOD), 0.4), tip * 0.95)
    vcolor(obj, col, "thatch", facet=0.03)
    part(obj, weights=lambda co, vi: torso_w(co))


# ── Head ──
# (y, z centre, half width, above, below, exponent): wide jowls narrowing into an upturned snout
HEAD = [
    (-0.150, 0.302, 0.100, 0.092, 0.098, 0.9),
    (-0.195, 0.300, 0.122, 0.100, 0.112, 0.85),
    (-0.245, 0.288, 0.134, 0.084, 0.118, 0.85),
    (-0.292, 0.270, 0.104, 0.066, 0.084, 0.88),
    (-0.338, 0.252, 0.068, 0.052, 0.060, 0.9),
    (-0.382, 0.253, 0.054, 0.045, 0.046, 0.95),
    (-0.418, 0.256, 0.062, 0.050, 0.048, 0.95),
]
NOSTRIL_Z = 0.262
EAR_BASE = (0.095, -0.205, 0.392)


def head_point(i, phi):
    y, zc, w, top, bot, ex = HEAD[i]
    s, k = math.sin(phi), math.cos(phi)
    sx = math.copysign(abs(s) ** ex, s)
    sz = math.copysign(abs(k) ** ex, k)
    sz *= top if sz >= 0 else bot
    return Vector((w * sx, y, zc + sz))


def head_frame(i, phi):
    """Surface point, outward normal and forward tangent on head ring i."""
    p = head_point(i, phi)
    e = 0.01
    dphi = head_point(i, phi + e) - head_point(i, phi - e)
    dy = head_point(i + 1, phi) - head_point(i - 1, phi)
    n = dy.cross(dphi).normalized()
    if n.dot(p - Vector((0, p.y, HEAD[i][1]))) < 0:
        n = -n
    return p, n, dy.normalized()


def eye_frames():
    """(centre, normal, slant, across, up-on-the-skull) of each eye: slanted down toward the snout and
    turned up toward the angled camera."""
    out = []
    for sx in (-1, 1):
        p, n, fwd = head_frame(3, sx * math.radians(40))
        p = p + fwd * -0.004
        slant = (fwd + Vector((0, 0, -0.45))).normalized()
        slant = (slant - n * slant.dot(n)).normalized()
        across = n.cross(slant).normalized()
        e_up = (Vector((0, 0, 1)) - n * n.z).normalized()
        if across.dot(e_up) < 0:
            across = -across                    # across points up the skull on both sides
        out.append((p, n, slant, across, e_up))
    return out


def build_snout_pad():
    """A flared pig-snout pad on the open end of the head: a buried ring, a flared rim and a flat
    front face whose two halves fan into recessed nostril pits."""
    y6, zc, w, top, bot, ex = HEAD[-1]
    sides = 10
    rings = ((-0.411, 0.96), (-0.425, 1.12), (-0.437, 1.0))
    verts = []
    for yy, k in rings:
        verts += ring_points(Vector((0, yy, zc)), Vector((w * k, 0, 0)), Vector((0, 0, top * k)), bot / top, ex, sides)
    faces = []
    for i in range(len(rings) - 1):
        for j in range(sides):
            a, b = i * sides + j, i * sides + (j + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    base = (len(rings) - 1) * sides
    nl, nr = len(verts), len(verts) + 1
    verts += [Vector((-0.022, rings[-1][0] + 0.007, NOSTRIL_Z)), Vector((0.022, rings[-1][0] + 0.007, NOSTRIL_Z))]
    half = sides // 2
    front = []
    for j in range(half):                       # the right half (x > 0) fans into the right nostril
        front.append((base + j, base + j + 1, nr))
    for j in range(half, sides):                # the left half into the left nostril
        front.append((base + j, base + (j + 1) % sides, nl))
    front += [(base, nr, nl), (base + half, nl, nr)]
    faces += front
    obj = gab.mesh_object("snout", verts, faces)
    finish(obj, True)
    for poly in obj.data.polygons[len(faces) - len(front):]:
        poly.use_smooth = False                 # a carved, flat nose plate
    gab.uv_box(obj, 1.0)
    pad = lerp(lin(LEG), lin(BARK), 0.5)

    def col(co, n, vi):
        if vi >= nl:
            return lin(SLIT)
        ring = vi // sides
        if ring == 0:
            return lerp(lin(HIDE_DARK), lin(WOOD), 0.5)
        if ring == 1:
            return lerp(lin(WOOD), pad, 0.25)   # the flared rim catches a little light
        return pad
    vcolor(obj, col, "plain", facet=0.02)
    part(obj, weights=head_w)


def build_head():
    rings = [(Vector((0, y, zc)), Vector((w, 0, 0)), Vector((0, 0, top)), bot / top, ex)
             for y, zc, w, top, bot, ex in HEAD]
    head = loft("head", rings, 14, cap0=0.0, cap1=None)
    fur_uv(head)

    def col(co, n, vi):
        up = smoothstep(0.18, 0.40, co.z)
        c = lerp(lerp(lin(SHELL_DARK), lin(HIDE_DARK), 0.7), lerp(lin(HIDE_DARK), lin(HIDE), 0.6), up)
        # the dark mantle runs over the brow; an earthy muzzle on the snout, kept dark so the red
        # eyes and bone tusks sit in a dark field
        c = lerp(c, lin(HIDE_DARK), smoothstep(0.33, 0.39, co.z) * smoothstep(-0.30, -0.24, co.y))
        muzzle = smoothstep(-0.30, -0.37, co.y) * smoothstep(0.215, 0.27, co.z)
        c = lerp(c, lerp(lin(HIDE_DARK), lin(WOOD), 0.5), muzzle * 0.55)
        # the mouth line where the head meets the jaw
        c = lerp(c, lin(SLIT), smoothstep(0.236, 0.206, co.z) * smoothstep(-0.215, -0.26, co.y) * 0.85)
        return c
    vcolor(head, col, "thatch")
    part(head, weights=head_w)
    build_snout_pad()

    # lower jaw: a darker wedge under the snout; the gap reads as the mouth
    jaw_rings = []
    for y, zc, w, h in ((-0.215, 0.205, 0.092, 0.042), (-0.27, 0.196, 0.082, 0.036),
                        (-0.33, 0.190, 0.060, 0.028), (-0.385, 0.194, 0.042, 0.022)):
        jaw_rings.append((Vector((0, y, zc)), Vector((w, 0, 0)), Vector((0, 0, h)), 1.0, 0.9))
    jaw = loft("jaw", jaw_rings, 10, cap0=0.0, cap1=0.01)
    fur_uv(jaw)
    vcolor(jaw, lambda co, n, vi: lerp(lin(SLIT), lin(HIDE_DARK), smoothstep(0.17, 0.215, co.z)), "thatch")
    part(jaw, weights=head_w)

    # eyes: big glowing eyes in dark sockets with a hot core, their upper lid cut flat and slanting
    # down toward the snout (angry), so the dark socket shows above them as a heavy brow line.
    # The game's Filmic tonemapper clips red and lifts any green in the emission toward peach (#ff5a3a
    # emits 0.10 green, which alone maps to sRGB ~120), so the emission is a deeper red of the same hue
    # family; the base colour (times the vertex colour) stays eye red.
    eye_mat = gab.glow("creep_eyes_red", EYE, EYE_GLOW)
    eye_mat.node_tree.nodes.get("Principled BSDF").inputs["Emission Color"].default_value = (*EYE_EMISSION, 1.0)
    for p, n, slant, across, e_up in eye_frames():
        socket = ellipsoid("socket", p - n * 0.001, (slant * 0.052, across * 0.033, n * 0.012), 12, 3,
                           cut=(0.024, -0.22))
        vcolor(socket, lambda co, n, vi: lin(SLIT), "plain", facet=0.0)
        part(socket, weights=head_w)
        eye = ellipsoid("eye", p + n * 0.007, (slant * 0.042, across * 0.023, n * 0.012), 12, 3,
                        cut=(0.006, -0.26))
        vcolor(eye, lambda co, n, vi: lin(GLOW_ORANGE) if vi == 0 else lin(EYE), "plain", facet=0.0)
        part(eye, mat=eye_mat, weights=head_w)
        # brow: a heavy, open-ended ridge along the eye's flat upper lid, thick and high at the back,
        # sinking toward the snout and overlapping the lid (angry)
        a = p - slant * 0.052 + across * 0.030 + n * 0.006
        mid = p - slant * 0.008 + across * 0.022 + n * 0.012
        b = p + slant * 0.040 + across * 0.004 + n * 0.010
        brow = tube("brow", [a, mid, b], [0.013, 0.014, 0.007], 5, flat=0.7, tip=False, smooth=True, cap0=None)
        fur_uv(brow)
        vcolor(brow, lambda co, n, vi: lerp(lin(LEG), lerp(lin(HIDE_DARK), lin(HIDE), 0.5), smoothstep(-0.1, 0.9, n.z)),
               "thatch")
        part(brow, weights=head_w)

    # tusks: lower tusks sweeping out of the jaw and hooking back beside the snout, below the
    # eye line (never above the snout's profile, so they do not read as a nose horn)
    for sx in (-1, 1):
        p0 = Vector((sx * 0.048, -0.372, 0.205))
        p1 = p0 + Vector((sx * 0.055, -0.035, 0.0))
        p2 = p0 + Vector((sx * 0.072, 0.045, 0.082))
        pts = [bezier(p0, p1, p2, t) for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
        tusk = tube("tusk", pts, [0.018, 0.016, 0.012, 0.007, 0.0], 6, flat=0.85, tip=True, smooth=True, cap0=None)
        gab.uv_box(tusk, 1.0)
        z0, z1 = p0.z, p2.z
        vcolor(tusk, lambda co, n, vi: lerp(lerp(lin(WOOD_LIGHT), lin(SPIKE), 0.4), lin(TUSK),
                                            smoothstep(z0, z1, co.z)), "plain")
        part(tusk, weights=head_w)

        q0 = Vector((sx * 0.050, -0.396, 0.236))
        q1 = q0 + Vector((sx * 0.028, -0.020, 0.004))
        q2 = q0 + Vector((sx * 0.040, 0.008, 0.042))
        pts = [bezier(q0, q1, q2, t) for t in (0.0, 0.4, 0.75, 1.0)]
        small = tube("tusk_small", pts, [0.010, 0.008, 0.005, 0.0], 5, tip=True, smooth=True, cap0=None)
        gab.uv_box(small, 1.0)
        vcolor(small, lambda co, n, vi: lerp(lin(SPIKE), lin(TUSK), smoothstep(0.23, 0.28, co.z)), "plain")
        part(small, weights=head_w)

    # ears: pointed, cupped, standing up and out beside the forehead crest; the right one (sx < 0)
    # droops lower
    for sx in (-1, 1):
        base = Vector((sx * EAR_BASE[0], EAR_BASE[1], EAR_BASE[2]))
        d = Vector((sx * 0.75, 0.30, 0.75)).normalized()
        L = 0.12
        if sx < 0:
            d = Vector((sx * 0.88, 0.30, 0.53)).normalized()
            L = 0.11
        bend = Vector((0, 0.25, -0.15)) * L
        pts = [base - d * 0.02, base + d * L * 0.35, base + d * L * 0.7 + bend * 0.4, base + d * L + bend]
        ear = tube("ear", pts, [0.034, 0.042, 0.026, 0.0], 6, flat=0.32, tip=True, smooth=True,
                   twist_up=Vector((0, -1, 0.35)), cap0=None)
        fur_uv(ear)
        bone = "ear_l" if sx > 0 else "ear_r"

        def ear_col(co, n, vi, base=base, L=L):
            # a dark, cool inner ear: the red eye stays the only hot accent on the head
            inner = smoothstep(0.1, -0.6, n.y)
            t = (co - base).length / L
            c = lerp(lerp(lin(HIDE_DARK), lin(HIDE), 0.6), lin(HIDE_DARK), smoothstep(0.55, 1.0, t))
            return lerp(c, lerp(lin(BARK), lin(HIDE_DARK), 0.4), inner * 0.9 * (1 - smoothstep(0.6, 1.0, t)))
        vcolor(ear, ear_col, "thatch")
        part(ear, weights=lambda co, vi, bone=bone: {bone: 1.0})


# ── Legs ──
LEGS = {
    # name: (hip, knee, fetlock, hoof, upper radius, knee radius, parent torso bone)
    "fl": (Vector((0.112, -0.115, 0.255)), Vector((0.122, -0.118, 0.115)), Vector((0.126, -0.120, 0.040)),
           Vector((0.127, -0.124, 0.0)), 0.078, 0.048, "chest"),
    "bl": (Vector((0.118, 0.175, 0.265)), Vector((0.128, 0.198, 0.100)), Vector((0.130, 0.185, 0.040)),
           Vector((0.131, 0.182, 0.0)), 0.086, 0.045, "body"),
}
for _key in ("fl", "bl"):
    _hip, _knee, _fet, _hoof, _ru, _rk, _parent = LEGS[_key]
    _m = Vector((-1, 1, 1))
    LEGS[_key[0] + "r"] = (_hip * _m, _knee * _m, _fet * _m, _hoof * _m, _ru, _rk, _parent)

HOOF_HALF = 0.052     # half the hoof's length along y
HOOF_SHIFT = -0.014   # the hoof's sole sits this far ahead of the leg's hoof point
# the toe and heel of the sole relative to the leg's hoof point (the toe vertex is pulled in for
# the cleft): the walk keeps the lower of the two on the ground
HOOF_EDGES = (HOOF_SHIFT - HOOF_HALF * 0.62, HOOF_SHIFT + HOOF_HALF)


def leg_w(name):
    hip, knee, fet, hoof, ru, rk, parent = LEGS[name]

    def fn(co, vi):
        up = smoothstep(knee.z - 0.025, knee.z + 0.025, co.z)
        w = {f"{name}_lo": 1 - up, f"{name}_up": up}
        attach = smoothstep(0.19, 0.25, co.z)
        if attach > 0:
            w = {k: v * (1 - attach) for k, v in w.items()}
            for b, x in torso_w(co).items():
                w[b] = w.get(b, 0) + x * attach
        return w
    return fn


def build_hoof(name, hoof):
    """One cloven hoof: a flat-shaded six-sided horn block, slanting forward at the toe, with the
    front vertex pulled in to notch the cleft (painted slit-dark)."""
    sx = 1 if hoof.x > 0 else -1
    c0 = Vector((hoof.x, hoof.y + HOOF_SHIFT + 0.008, 0.0))     # the sole (fwd -0.008) lands at HOOF_SHIFT
    verts = []
    for z, rx, ry, fwd in ((0.0, 0.050, HOOF_HALF, -0.008), (0.050, 0.043, 0.044, 0.0)):
        for j in range(6):
            a = 2 * math.pi * j / 6
            y = -ry * math.cos(a)
            if j == 0:
                y *= 0.62
            verts.append(c0 + Vector((rx * math.sin(a) * (1.0 + 0.06 * sx * math.sin(a)), y + fwd, z)))
    faces = [(j, (j + 1) % 6, 6 + (j + 1) % 6, 6 + j) for j in range(6)]
    obj = gab.mesh_object("hoof", verts, faces)
    finish(obj, smooth=False)
    gab.uv_box(obj, 1.0)
    cleft = {0, 6}

    def col(co, n, vi):
        if vi in cleft:
            return lin(SLIT)
        return lerp(lerp(lin(LEG), lin(WOOD), 0.35), lin(SHELL_DARK), smoothstep(0.0, 0.03, co.z))
    vcolor(obj, col, "plain", facet=0.04)
    part(obj, weights=lambda co, vi: {f"{name}_lo": 1.0})


def build_legs():
    for name, (hip, knee, fet, hoof, ru, rk, parent) in LEGS.items():
        front = name[0] == "f"
        sx = 1 if hip.x > 0 else -1
        # thigh / shoulder mass bulging toward the body's centre
        mid_up = hip.lerp(knee, 0.45) + Vector((sx * 0.006, -0.015 if not front else 0.015, 0))
        pts = [hip + Vector((0, 0, 0.02)), mid_up, knee, knee.lerp(fet, 0.5), fet, hoof + Vector((0, 0, 0.028))]
        radii = [ru * 0.95, ru * 1.22, rk, rk * 0.8, rk * 0.9, rk * 0.95]
        leg = tube(f"leg_{name}", pts, radii, 8, tip=False, smooth=True, cap0=0.0)
        gab.uv_cylinder(leg, 1.0)
        for loop_uv in leg.data.uv_layers["UVMap"].data:
            loop_uv.uv = (loop_uv.uv[0], loop_uv.uv[1] * 3.5)
        vcolor(leg, lambda co, n, vi: lerp(lin(LEG), lin(HIDE_DARK), smoothstep(0.05, 0.24, co.z)), "thatch")
        part(leg, weights=leg_w(name))
        build_hoof(name, hoof)
        # a fetlock tuft: a short lock of coarse hair breaking the leg from the hoof, on the outside
        root = Vector((fet.x + sx * 0.024, fet.y + 0.012, 0.062))
        d = Vector((sx * 0.6, 0.8, -0.9))
        lock("fetlock", root, d, 0.055 * R.uniform(0.9, 1.1), 0.03, lambda co, vi, name=name: {f"{name}_lo": 1.0},
             curl=Vector((0, 0.2, -0.1)), sides=4)


# ── Quills ──
# chevron rows either side of the spine: (fraction of the mantle's reach, length factor, sweep)
CREST = 11          # spine-crest quills
ROWS = [(0.25, 1.00, 0.95), (0.52, 0.88, 1.05), (0.78, 0.77, 1.15)]
QUILL_Y = {"f": -0.12, "m": 0.03, "b": 0.17}


def quill_w(co):
    """Quill-tip weights: blended along the back between the front, middle and back quill bones of
    that side, so the quill mass bends softly instead of in rigid quadrants."""
    side = "l" if co.x > 0 else "r"
    y = co.y
    if y <= QUILL_Y["f"]:
        return {f"q_f{side}": 1.0}
    if y <= QUILL_Y["m"]:
        t = smoothstep(QUILL_Y["f"], QUILL_Y["m"], y)
        return {f"q_f{side}": 1 - t, f"q_m{side}": t}
    if y <= QUILL_Y["b"]:
        t = smoothstep(QUILL_Y["m"], QUILL_Y["b"], y)
        return {f"q_m{side}": 1 - t, f"q_b{side}": t}
    return {f"q_b{side}": 1.0}


def mix_w(a, b, t):
    out = {k: v * (1 - t) for k, v in a.items()}
    for k, v in b.items():
        out[k] = out.get(k, 0) + v * t
    return out


def add_quill(verts, faces, cols, wts, root, direction, length, radius, tip_col, mid_col, band_col=None,
              curl=0.12, root_w=None, tip_w=None, band_at=0.62, sides=4, mid_at=0.45):
    """A straight-sectioned spike from root along direction, curling back toward +Y: a dark root buried
    in the mantle, a dark mid ring at `mid_at` of the length, an optional dark band at `band_at`, and a
    pale tip. One edge faces up (no twist), so each spike carries one clean ridge highlight."""
    d = direction.normalized()
    side, up = frame_from(d)
    embed = 0.035
    root = root - d * embed
    tip = root + d * (length + embed) + Vector((0, curl * length, -0.25 * curl * length))
    phase = math.pi / 2
    rw = root_w if root_w is not None else torso_w(root)
    qw = tip_w if tip_w is not None else quill_w(root)
    rings = [(0.0, 1.0, lin(SHELL_DARK), rw)]
    rings.append((embed + length * mid_at, 0.72, mid_col, mix_w(rw, qw, 0.55)))
    if band_col is not None:
        rings.append((embed + length * band_at, 0.5, band_col, mix_w(rw, qw, 0.8)))
    first = len(verts)
    for k, (dist, scale, col, w) in enumerate(rings):
        c = root + d * dist + Vector((0, curl * length, -0.25 * curl * length)) * (dist / (length + embed)) ** 2
        for j in range(sides):
            a = phase + 2 * math.pi * j / sides
            verts.append(c + (side * math.cos(a) + up * math.sin(a)) * radius * scale)
        cols += [col] * sides
        wts += [w] * sides
    for k in range(len(rings) - 1):
        a0, b0 = first + k * sides, first + (k + 1) * sides
        for j in range(sides):
            faces.append((a0 + j, a0 + (j + 1) % sides, b0 + (j + 1) % sides, b0 + j))
    ti = len(verts)
    verts.append(tip)
    cols.append(tip_col)
    wts.append(qw)
    last = first + (len(rings) - 1) * sides
    for j in range(sides):
        faces.append((last + j, last + (j + 1) % sides, ti))


QUILL_MID = lerp(lin(HIDE_DARK), lin(WOOD), 0.6)
QUILL_BAND = lerp(lin(BARK), lin(HIDE_DARK), 0.5)


def quill_colors(kind, banded):
    """(tip, mid, band) colours: dark to the middle, then a pale tip, never brighter than bone."""
    band = QUILL_BAND if banded else None
    mid = QUILL_MID * R.uniform(0.9, 1.05)
    tone = R.uniform(0.92, 1.0)
    if kind == "dark":
        # dark-tipped: a warm wood middle fading to a dark point, breaking up the pale mass
        return lerp(lin(HIDE_DARK), lin(BARK), 0.5), lerp(lin(WOOD), lin(WOOD_LIGHT), 0.6) * tone, None
    if kind == "tan":
        return lerp(lin(SPIKE), lin(WOOD_LIGHT), R.uniform(0.2, 0.45)) * tone, mid, band
    return lerp(lin(SPIKE), lin(STALK), R.uniform(0, 0.3)) * tone, mid, band


def quill_kind():
    roll = R.random()
    return "dark" if roll < 0.25 else ("tan" if roll > 0.9 else "bone")


def build_quills():
    verts, faces, cols, wts = [], [], [], []
    y_front, y_rear = -0.19, 0.245

    def row_length(y, lf):
        u = (y - y_front) / (y_rear - y_front)
        hump = math.exp(-((y + 0.02) / 0.17) ** 2)
        return 0.175 * (0.62 + 0.45 * hump) * lf * (1 - 0.32 * smoothstep(0.25, 0.0, u)), u

    for sx in (-1, 1):
        for r, (reach, lf, sweep0) in enumerate(ROWS):
            off = 0.5 if r % 2 else 0.0
            for i in range(PER_ROW):
                t = (i + off + R.uniform(-0.12, 0.12)) / (PER_ROW - 0.5)
                y = lerp(y_front, y_rear, t)
                if y > y_rear + 0.005:
                    continue
                um = (y - MANTLE_Y0) / (MANTLE_Y1 - MANTLE_Y0)
                phi_max = mantle_edge(um) - math.radians(12)
                a = reach * R.uniform(0.94, 1.06)
                phi = sx * a * phi_max
                n = body_normal(y, phi)
                p = body_point(y, phi) + n * 0.02
                length, u = row_length(y, lf)
                length *= R.uniform(0.86, 1.1)
                sweep = sweep0 + 0.35 * u + R.uniform(-0.08, 0.08)
                d = n * (1.0 - 0.3 * a) + Vector((0, sweep, 0.08))
                d += Vector((R.uniform(-0.1, 0.1), R.uniform(-0.06, 0.06), R.uniform(-0.06, 0.06)))
                kind = quill_kind()
                banded = kind != "dark" and R.random() < 0.15
                tip, mid, band = quill_colors(kind, banded)
                add_quill(verts, faces, cols, wts, p, d, length, 0.010 + 0.06 * length, tip, mid, band)
        # hero spikes: three long, thick, banded spikes per side at the shoulder hump, splayed out
        # past their neighbours so they break the outline from above (a big-small-big rhythm)
        for i, y in enumerate((-0.07, 0.0, 0.07)):
            y += R.uniform(-0.01, 0.01)
            um = (y - MANTLE_Y0) / (MANTLE_Y1 - MANTLE_Y0)
            phi_max = mantle_edge(um) - math.radians(12)
            a = R.uniform(0.45, 0.6)
            phi = sx * a * phi_max
            n = body_normal(y, phi)
            p = body_point(y, phi) + n * 0.02
            length = row_length(y, 1.0)[0] * 1.45 * R.uniform(0.95, 1.05)
            u = (y - y_front) / (y_rear - y_front)
            d = n * (1.0 - 0.3 * a) + Vector((0, ROWS[0][2] + 0.35 * u + 0.05 * (i - 1), 0.08))
            d = Matrix.Rotation(sx * math.radians(R.uniform(15, 20)), 3, "Y") @ d
            tip = lerp(lin(SPIKE), lin(STALK), R.uniform(0.1, 0.3))
            add_quill(verts, faces, cols, wts, p, d, length, 0.02 + 0.07 * length, tip, QUILL_MID * 0.95,
                      QUILL_BAND, band_at=0.55, sides=5, mid_at=0.35, curl=0.09)
    # the spine crest: the darkest row, alternating tall and short, dark-banded so a dark dorsal stripe
    # reads from above
    for i in range(CREST):
        y = lerp(-0.17, 0.215, i / (CREST - 1)) + R.uniform(-0.008, 0.008)
        phi = R.uniform(-0.08, 0.08)
        p = body_point(y, phi) + body_normal(y, phi) * 0.02
        hump = math.exp(-((y + 0.02) / 0.17) ** 2)
        d = Vector((R.uniform(-0.1, 0.1), 0.75 + 0.45 * (i / (CREST - 1)), 1.0))
        tone = R.uniform(0.86, 0.95)
        tip = lerp(lin(SPIKE), lin(WOOD_LIGHT), R.uniform(0.25, 0.45)) * tone
        mid = lerp(lin(HIDE_DARK), lin(BARK), 0.5)
        band = lerp(lin(LEG), lin(HIDE_DARK), 0.5)
        length = (0.135 + 0.075 * hump) * R.uniform(0.95, 1.05) * (1.05 if i % 2 else 0.78)
        add_quill(verts, faces, cols, wts, p, d, length, 0.012 + 0.05 * length, tip, mid, band, curl=0.18,
                  band_at=0.78)
    obj = gab.mesh_object("quills", verts, faces)
    finish(obj, QUILL_SMOOTH)
    vcolor(obj, lambda co, n, vi: cols[vi], "plain", facet=0.03)
    part(obj, weights=lambda co, vi: wts[vi])
    # head crest: short quills on the forehead between the ears, swept back
    hv, hf, hc, hw = [], [], [], []
    for i in range(5):
        y = lerp(-0.228, -0.17, i / 4)
        x = R.uniform(-0.03, 0.03)
        p = Vector((x, y, 0.388 - (y + 0.17) * 0.55))
        tip, mid, _ = quill_colors("bone" if i % 2 else "tan", False)
        add_quill(hv, hf, hc, hw, p, Vector((x * 2.5, 1.35, 0.75)), 0.05 + 0.04 * (i / 4), 0.013, tip, mid,
                  QUILL_BAND if i % 2 == 0 else None, root_w={"head": 1.0}, tip_w={"head": 1.0})
    crest = gab.mesh_object("crest", hv, hf)
    finish(crest, QUILL_SMOOTH)
    vcolor(crest, lambda co, n, vi: hc[vi], "plain", facet=0.03)
    part(crest, weights=lambda co, vi: hw[vi])


# ── Fur locks (chunky painted clumps) ──

def lock(name, root, direction, length, width, weights, curl=Vector((0, 0, -0.3)), tip=WOOD_LIGHT, sides=5,
         base=HIDE_DARK):
    d = direction.normalized()
    p0 = root - d * 0.01
    p1 = root + d * length * 0.5 + curl * length * 0.15
    p2 = root + d * length + curl * length * 0.45
    obj = tube(name, [p0, p1, p2], [width, width * 0.75, 0.0], sides, flat=0.45, tip=True, smooth=True, cap0=None)
    fur_uv(obj)
    vcolor(obj, lambda co, n, vi: lerp(lin(base), lin(tip), smoothstep(0.0, length, (co - root).dot(d))),
           "thatch")
    part(obj, weights=weights)
    return obj


def build_fur():
    for sx in (-1, 1):
        # cheek ruff: locks sweeping back and out from the jowls
        for i, (y, z, L) in enumerate(((-0.228, 0.262, 0.105), (-0.205, 0.218, 0.095), (-0.190, 0.305, 0.09))):
            root = Vector((sx * 0.112, y, z))
            d = Vector((sx * 0.6, 0.85, -0.2 + 0.12 * i))
            lock("cheek", root, d, L * R.uniform(0.92, 1.08), 0.03, head_w)

    # tail: a short tapered stub ending in a bristle tuft of three small locks
    tail_pts = [Vector((0, 0.285, 0.30)), Vector((0, 0.325, 0.29)), Vector((0, 0.345, 0.255))]
    tail = tube("tail", tail_pts, [0.018, 0.012, 0.0], 5, tip=True, smooth=True, cap0=None)
    gab.uv_box(tail, 1.0)
    vcolor(tail, lambda co, n, vi: lin(HIDE_DARK), "thatch")
    part(tail, weights=lambda co, vi: {"tail": 1.0})
    for k in (-1, 0, 1):
        d = Vector((0.55 * k, 0.35, -1.0))
        lock("tuft", Vector((0.004 * k, 0.338, 0.268)), d, 0.05 * R.uniform(0.9, 1.1), 0.012,
             lambda co, vi: {"tail": 1.0}, curl=Vector((0, 0.3, 0)), sides=4)


# ── Build ──

ONLY = {n for n in str(gab.param("only", "")).split(",") if n}
for _name, _build in (("body", build_body), ("mantle", build_mantle), ("head", build_head), ("legs", build_legs),
                      ("quills", build_quills), ("fur", build_fur)):
    if not ONLY or _name in ONLY:
        _build()

MASS = ("body", "mantle", "head")
top = max((p.matrix_world @ v.co).z for p in PARTS if p.name.split(".")[0] in MASS for v in p.data.vertices)
S = TARGET_HEIGHT_BODY / top
TOPS = {}
for p in PARTS:
    key_ = p.name.split(".")[0]
    TOPS[key_] = max(TOPS.get(key_, 0.0), max((p.matrix_world @ v.co).z for v in p.data.vertices) * S)
for p in PARTS:
    p.scale = (S, S, S)
    gab.apply_transform(p)
low = min((p.matrix_world @ v.co).z for p in PARTS for v in p.data.vertices)
model = gab.join(PARTS, "thornback")
model.data.name = "thornback"
for v in model.data.vertices:
    v.co.z -= low
model.data.color_attributes.active_color = model.data.color_attributes["Color"]


# ── Rig ──

def sv(*xyz):
    return tuple(c * S for c in xyz)


bones = [
    ("root", sv(0, 0, 0), sv(0, 0.12, 0), None),
    ("bob", sv(0, 0.03, 0.14), sv(0, 0.03, 0.22), "root"),
    ("body", sv(0, 0.06, 0.29), sv(0, -0.06, 0.30), "bob"),
    ("chest", sv(0, -0.06, 0.30), sv(0, -0.16, 0.30), "body"),
    ("head", sv(0, -0.17, 0.30), sv(0, -0.30, 0.27), "chest"),
    ("ear_l", sv(*EAR_BASE), sv(EAR_BASE[0] + 0.07, EAR_BASE[1] + 0.025, EAR_BASE[2] + 0.07), "head"),
    ("ear_r", sv(-EAR_BASE[0], *EAR_BASE[1:]), sv(-EAR_BASE[0] - 0.08, EAR_BASE[1] + 0.025, EAR_BASE[2] + 0.05), "head"),
    ("tail", sv(0, 0.285, 0.30), sv(0, 0.34, 0.27), "body"),
]
for seg, parent in (("f", "chest"), ("m", "body"), ("b", "body")):
    y = QUILL_Y[seg]
    for side, sx in (("l", 1), ("r", -1)):
        bones.append((f"q_{seg}{side}", sv(0.0, y, 0.31), sv(sx * 0.06, y + 0.04, 0.41), parent))
for name, (hip, knee, fet, hoof, ru, rk, parent) in LEGS.items():
    bones.append((f"{name}_up", sv(*hip), sv(*knee), "bob"))
    bones.append((f"{name}_lo", sv(*knee), sv(hoof.x, hoof.y, 0.01), f"{name}_up"))
arm = gab.armature("thornback_rig", bones)
mod = model.modifiers.new("Armature", "ARMATURE")
mod.object = arm
model.parent = arm


def to_local(bone, rot=(0, 0, 0), loc=None):
    """A rotation (degrees, about armature axes, around the bone head) and an optional
    offset in armature space, converted to the bone's local pose channels."""
    B = arm.data.bones[bone].matrix_local.to_3x3()
    Rw = Euler([math.radians(a) for a in rot], "XYZ").to_matrix()
    Rl = B.transposed() @ Rw @ B
    e = Rl.to_euler("XYZ")
    out = [tuple(math.degrees(a) for a in e)]
    if loc is not None:
        out.append(tuple(B.transposed() @ Vector(loc) * S))
    return out


FRAMES = 24
FPS = 30
keys = {}


def key(bone, frame, rot=(0, 0, 0), loc=None):
    keys.setdefault(bone, []).append((frame, *to_local(bone, rot, loc)))


def wave(p, period=1.0, phase=0.0):
    return math.sin(2 * math.pi * (p / period - phase))


SWING = 34.0      # degrees either side of vertical
STANCE = 0.52     # fraction of the cycle a hoof is planted


def leg_state(name, p):
    """(swing degrees, knee bend degrees, planted) of a leg at cycle phase p. Diagonal pairs
    (front-left with back-right) run half a cycle apart. A planted hoof sweeps back at constant
    ground speed (sin of the angle is linear in time), so it does not slip."""
    q = (p + (0.0 if name in ("fl", "br") else 0.5)) % 1.0
    smax = math.sin(math.radians(SWING))
    if q < STANCE:
        return math.degrees(math.asin(smax * (1 - 2 * q / STANCE))), 0.0, True
    t = (q - STANCE) / (1 - STANCE)
    fold = 0.8
    return -SWING + 2 * SWING * smoothstep(0, 1, t), 72 * math.sin(math.pi * t ** fold), False


def hoof_lift(name, p):
    """How far the lowest point of a planted, tilted hoof sits above the ground when the hip
    stays at its rest height: the toe and heel swing on arcs about the hip (a hoof ahead of its
    hip rises as the leg reaches forward), and the lower of the two touches down."""
    hip, hoof = LEGS[name][0], LEGS[name][3]
    a = -math.radians(leg_state(name, p)[0])
    lows = []
    for edge in HOOF_EDGES:
        dy, dz = hoof.y + edge - hip.y, -hip.z
        lows.append(hip.z + dy * math.sin(a) + dz * math.cos(a))
    return min(lows)


def body_motion(p):
    """(pitch, roll, yaw) degrees of the body at cycle phase p."""
    roll = 5.0 * wave(p, 1.0, 0.05)
    pitch = 3.0 * math.cos(4 * math.pi * (p - 0.12))
    yaw = 2.0 * wave(p, 1.0, 0.2)
    return pitch, roll, yaw


JITTER = {seg + side: (R.random(), R.random()) for seg in "fmb" for side in "lr"}

for f in range(FRAMES):
    p = f / FRAMES
    # the hips ride on the planted legs (highest at mid-stance), so planted hooves stay on
    # the ground; the body then sinks a little more just after each footfall: heavy
    lifts = [hoof_lift(n, p) for n in LEGS if leg_state(n, p)[2]]
    key("bob", f, (0, 0, 0), (0, 0, -min(lifts)))
    for name in LEGS:
        swing, bend, _ = leg_state(name, p)
        # a forward swing (hoof toward -Y) is a negative rotation about +X for a bone pointing down
        key(f"{name}_up", f, (-swing, 0, 0))
        # front knees fold the hoof back; hind hocks fold it forward and up
        key(f"{name}_lo", f, (bend if name[0] == "f" else -bend * 0.6, 0, 0))
    sink = -0.016 * sum(math.exp(-((p - c - 0.08) / 0.07) ** 2) for c in (-0.5, 0.0, 0.5, 1.0))
    pitch, roll, yaw = body_motion(p)
    key("body", f, (pitch, roll, yaw), (0, 0, sink))
    key("chest", f, (-0.8 * pitch, -0.8 * roll, -0.5 * yaw))
    nod = 9.0 * math.cos(4 * math.pi * (p - 0.17))
    key("head", f, (nod - 1.5, 0, 3.5 * wave(p, 1.0, 0.3)))
    flop = 12.0 * math.cos(4 * math.pi * (p - 0.25))
    key("ear_l", f, (0, -flop, 0))
    key("ear_r", f, (0, flop, 0))
    key("tail", f, (0, 0, 18 * wave(p, 1.0, 0.15)))
    # quills: secondary motion. They follow the body's sway three frames late and amplified, and
    # bristle (lift and spread) in a smooth damped shiver after every footfall (frames 0 and 12)
    # that starts from zero (no snap) and has a six-frame period; the middle and back quills answer
    # two and four frames after the front ones, so a ripple runs front to back along the back. A
    # little looping jitter per bone, out of phase left and right, keeps the sides from moving in
    # lockstep.
    for seg, delay in (("f", 0), ("m", 2), ("b", 4)):
        lp, lr, _ = body_motion((f - 3 - delay) / FRAMES)
        ts = ((f - 1 - delay) % (FRAMES // 2)) / FPS
        flare = 6.0 * math.sin(2 * math.pi * ts / 0.2) * math.exp(-ts / 0.15)
        for side, sgn in (("l", 1), ("r", -1)):
            ph = JITTER[seg + side]
            jx = 1.5 * math.sin(2 * math.pi * (3 * p + ph[0]))
            jy = 1.5 * math.sin(2 * math.pi * (2 * p + ph[1]))
            key(f"q_{seg}{side}", f, (2.5 * lp + flare + jx, 2.5 * lr + sgn * flare * 0.5 + jy, 0))

# The ground speed the cycle matches, in game units (the game scales the model by 1.35):
# Game.CREEPS["thornback"]["stride"] should be this for the hooves not to slide.
_reach = sum(LEGS[n][0].z for n in LEGS) / 4 * S
STRIDE = 2 * _reach * math.sin(math.radians(SWING)) / (STANCE * FRAMES / FPS) * 1.35

gab.animate(arm, "walk", FRAMES, keys)

if POSE_FRAME >= 0:
    # preview: bake the walk at one frame into the mesh, drop the rig
    action = bpy.data.actions["walk"]
    arm.animation_data.action = action
    for track in list(arm.animation_data.nla_tracks):
        arm.animation_data.nla_tracks.remove(track)
    if hasattr(arm.animation_data, "action_slot") and action.slots:
        arm.animation_data.action_slot = action.slots[0]
    bpy.context.scene.frame_set(POSE_FRAME)
    gab.select_only(model)
    bpy.ops.object.modifier_apply(modifier="Armature")
    model.parent = None
    bpy.data.objects.remove(arm)
    bpy.data.actions.remove(action)

print(f"thornback: {gab.triangles(model)} triangles, scale {S:.3f}, stride {STRIDE:.3f}")
print("thornback tops: " + ", ".join(f"{k} {v:.3f}" for k, v in sorted(TOPS.items(), key=lambda kv: -kv[1])[:5]))
print("thornback parts: " + ", ".join(f"{k} {v}" for k, v in sorted(TRIS.items(), key=lambda kv: -kv[1])))
