"""Gourdling: a walking pumpkin goblin, the first creep of Wickhollow.

    godot-agent asset blender . art_src/blender/gourdling.py --to res://models/creeps/gourdling.glb \
        --seed 1 --review --no-import

A dark, lobed gourd with lit crests and a carved jack-o-lantern face: real pockets cut by
a boolean, each with a glowing floor, a white-hot core and lit inner walls. A zig-zag lid
seam around the stem and one bold, branching crack across a back lobe burn a lower, warmer
ember orange, so the creep shows candlelight from every heading (and in the HUD portrait,
which turns it round) while only the face is white-hot. Splayed root legs with planted
feet, braided vine arms with an elbow leaf and leaf claws, a smooth stem flaring out of
the rind with a dried, broken tip and a corkscrew curl, a pumpkin leaf, and a skirt of
drooping leaves (two of them dry) under the belly.

Rigged (root, body, stem, ruff, two-bone legs with feet, two-bone arms) with a looping
'walk' (24 frames at 30 fps): a rolling, hopping vault over stiff legs whose feet stay
planted while the creep moves at the speed the walk was authored for (see STRIDE); the
stem, the top leaves' edges and the leaf skirt follow through a couple of frames late, and
the arms swing out and away from the legs on the back-swing. Plus an 'idle' (48 frames).

Front faces -Y, feet at the origin, about 0.5 units tall before the game's 1.5x scale.

Params:
    pose=walk:6   bake that frame of an action into the mesh and drop the rig (for
                  previewing poses on a review sheet; never used for the game file)
    check=1       print per-part triangles, material use, and per-frame ground clearance and
                  planted-foot slip of the walk (any value changes nothing in the model)
    rind=thatch   the painted pattern on the rind (uscale/vscale size its streaks)
    ember, ember_k  the lid seam and back crack glow colour and strength (#ffb040, 1.6)
"""

import math

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector, noise
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

import gab

rng = gab.rng

# ── Colours (hollow palette where it has them) ──

HEX = {
    "pumpkin": "#d9772b", "pumpkin_dark": "#a8521e", "pumpkin_deep": "#b5541f",
    "ember": "#f0a050", "autumn": "#f6d070", "amber_light": "#e8b44a", "amber": "#d08a2e",
    "glow_yellow": "#ffd860", "glow_orange": "#ffb040", "glow_pale": "#ffef7a",
    "stem": "#5a6b2e", "leaf_deep": "#3f7a2e", "leaf": "#5a8a3a", "leaf_light": "#7fa848",
    "leaf_bright": "#7fb444", "leaf_tip": "#c3e070", "needle_deep": "#1d4528", "needle": "#2f5f3e",
    "needle_light": "#3f7a4a", "grass_light": "#8fb84e",
    "bark": "#5b3a29", "leg": "#3e2a1e", "hide": "#6b4a34", "hide_dark": "#4a3324",
    "wood": "#7a5534", "wood_light": "#a0784a", "wood_dark": "#4e3423", "stalk": "#e6dcc3",
    "shadow": "#5c2616",   # below pumpkin_dark: the cool underside of the gourd
    "groove": "#7a2c14",   # the creases between lobes
}


def col(name_or_hex):
    h = HEX.get(name_or_hex, name_or_hex)
    return Vector(gab.rgb(h))


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def ramp(stops, t):
    """stops: [(t, Vector)], sorted by t."""
    if t <= stops[0][0]:
        return stops[0][1].copy()
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            return lerp(c0, c1, (t - t0) / (t1 - t0))
    return stops[-1][1].copy()


NOISE_AT = Vector((rng.uniform(-50, 50), rng.uniform(-50, 50), rng.uniform(-50, 50)))


def mottle(co, a=0.06, b=0.03):
    """Painterly value variation from position, so neighbouring faces share their
    vertices (no per-face jitter, which splits every vertex on export)."""
    return 1 + a * noise.noise(co * 18 + NOISE_AT) + b * noise.noise(co * 45 - NOISE_AT)


def paint_fn(obj, fn, pattern="plain", faces=None):
    """Vertex colours from fn(vertex_index, co, polygon) -> linear Vector, for the
    painted material; alpha carries the pattern like gab.paint()."""
    mesh = obj.data
    layer = gab._color_layer(mesh)
    alpha = (gab.PATTERNS.index(pattern) + 0.5) / 16
    chosen = set(faces) if faces is not None else None
    for poly in mesh.polygons:
        if chosen is not None and poly.index not in chosen:
            continue
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index
            c = fn(vi, mesh.vertices[vi].co, poly)
            layer.data[li].color = (*(min(1.0, max(0.0, x)) for x in c), alpha)
    return obj


# ── Geometry helpers ──

def build(name, verts, faces, uvs=None, mats=None, recalc=True):
    obj = gab.mesh_object(name, verts, faces, uvs)
    if recalc:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(obj.data)
        bm.free()
    if mats:
        for m in mats:
            obj.data.materials.append(m)
    return obj


def tube(name, pts, radii, sides=6, cap_start=False, cap_end=True, twist=0.0, ridges=0.0, jitter=0.0,
         start_angle=0.0):
    """A tube along a polyline, rings oriented by parallel transport. A radius of 0 at
    the end makes a pointed tip. Returns (object, per-vertex t along the path 0..1).
    UVs in metres (u around, v along) so painted patterns keep their size."""
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
    verts, ts, rings = [], [], []
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
            ts.append(lengths[i] / total)
            continue
        ring = []
        for k in range(sides):
            a = start_angle + 2 * math.pi * k / sides + twist * i
            rr = r * (1 + (ridges if k % 2 == 0 else -ridges)) * (1 + rng.uniform(-jitter, jitter))
            ring.append(len(verts))
            verts.append(pts[i] + (side * math.cos(a) + b * math.sin(a)) * rr)
            ts.append(lengths[i] / total)
        rings.append(ring)
    faces, uvs = [], []
    for i in range(n - 1):
        A, B = rings[i], rings[i + 1]
        ra = max(radii[i], 0.004)
        circ = 2 * math.pi * ra
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
    if cap_start and len(rings[0]) > 1:
        faces.append(tuple(reversed(rings[0])))
        uvs.append([(0, 0)] * sides)
    if cap_end and len(rings[-1]) > 1:
        faces.append(tuple(rings[-1]))
        uvs.append([(0, 0)] * sides)
    return build(name, verts, faces, uvs), ts


def blade(name, base, direction, normal, length, width, fold=0.3, curl=0.0, segs=3, twist=0.0):
    """A pointed leaf (finger, sepal): a spine from base to tip with edges folded down
    along it, curling by `curl` metres (along -normal) at the tip. Two-sided: the
    second half of the faces faces the other way. Returns (object, per-vertex t, front
    count, set of midrib vertex indices)."""
    d = Vector(direction).normalized()
    nrm = Vector(normal)
    nrm = (nrm - d * nrm.dot(d)).normalized()
    side = d.cross(nrm).normalized()
    base = Vector(base)
    spine, left, right, ts = [], [], [], []
    verts = []
    for i in range(segs + 1):
        t = i / segs
        p = base + d * length * t - nrm * curl * t * t
        spine.append(len(verts))
        verts.append(p)
        ts.append(t)
        if 0 < i < segs:
            w = width * 0.5 * math.sin(math.pi * t ** 0.8) ** 0.7
            s = side * math.cos(twist * t) + nrm * math.sin(twist * t)
            for lst, sign in ((left, -1), (right, 1)):
                lst.append(len(verts))
                verts.append(p + s * sign * w - nrm * fold * w)
                ts.append(t)
    faces = []
    for i in range(segs):
        a, b = spine[i], spine[i + 1]
        for edge in (left, right):
            e0 = edge[i - 1] if i > 0 else None
            e1 = edge[i] if i < segs - 1 else None
            if e0 is None:
                faces.append((a, e1, b))
            elif e1 is None:
                faces.append((a, e0, b))
            else:
                faces.append((a, e0, e1, b))
    obj_verts = verts + verts
    off = len(verts)
    front = []
    for f in faces:
        pts = [verts[i] for i in f]
        nn = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        front.append(f if nn.dot(nrm) >= 0 else f[::-1])
    back = [tuple(i + off for i in reversed(f)) for f in front]
    obj = build(name, obj_verts, front + back, recalc=False)
    return obj, ts + ts, len(front), set(spine) | {i + off for i in spine}


def triangulate2d(shape):
    """Triangles (index triples) of a simple 2D polygon."""
    bm = bmesh.new()
    bvs = [bm.verts.new((u, v, 0.0)) for u, v in shape]
    bm.faces.new(bvs)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="EAR_CLIP")
    bm.verts.index_update()
    tris = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    return tris


def inside2d(p, poly):
    x, y = p
    hit = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            hit = not hit
    return hit


def dist2d(p, poly):
    best = 9.0
    for a, b in zip(poly, poly[1:] + poly[:1]):
        a, b, q = Vector(a), Vector(b), Vector(p)
        ab = b - a
        t = max(0.0, min(1.0, (q - a).dot(ab) / max(ab.length_squared, 1e-12)))
        best = min(best, (a + ab * t - q).length)
    return best


def lobe(theta):
    x = (theta - THETA0) * LOBES / (2 * math.pi)
    k = math.floor(x)
    return math.sin(math.pi * (x - k)), int(k) % LOBES


# ── Body: a lobed pumpkin, raised on longer legs ──

LOBES, SPL, RINGS = 8, 4, 11
SEG = LOBES * SPL
R, H, ZC = 0.155, 0.125, 0.30
DEPTH = 0.17
THETA0 = -math.pi / 2  # a groove at the front centre: the eyes sit on two lobes
lobe_var = [rng.uniform(-0.05, 0.05) for _ in range(LOBES)]
lobe_hvar = [rng.uniform(-0.035, 0.035) for _ in range(LOBES)]


def profile(phi):
    r = math.sin(phi) ** 0.92
    z = -math.cos(phi)
    z -= 0.36 * math.exp(-((math.pi - phi) / 0.42) ** 2)   # stem dimple
    z += 0.24 * math.exp(-(phi / 0.4) ** 2)                # blossom dimple
    return r, z


def body_pos(theta, phi):
    s, k = lobe(theta)
    r, z = profile(phi)
    shape = (1 - DEPTH * (1 - s ** 0.55)) * (1 + lobe_var[k] * s)
    rr = R * r * shape
    zz = ZC + H * z * (1 + lobe_hvar[k] * s * math.sin(phi))
    return Vector((rr * math.cos(theta), rr * math.sin(theta), zz))


def make_body():
    verts = [Vector((0, 0, ZC + H * profile(0.0)[1]))]
    phis = [lerp(0.22, math.pi - 0.2, (i / (RINGS - 1)) ** 0.95) for i in range(RINGS)]
    for phi in phis:
        for j in range(SEG):
            verts.append(body_pos(THETA0 + 2 * math.pi * j / SEG, phi))
    verts.append(Vector((0, 0, ZC + H * profile(math.pi)[1])))
    top = len(verts) - 1
    faces = []
    idx = lambda i, j: 1 + i * SEG + (j % SEG)  # noqa: E731
    for j in range(SEG):
        faces.append((0, idx(0, j + 1), idx(0, j)))
    for i in range(RINGS - 1):
        for j in range(SEG):
            faces.append((idx(i, j), idx(i, j + 1), idx(i + 1, j + 1), idx(i + 1, j)))
    for j in range(SEG):
        faces.append((idx(RINGS - 1, j), idx(RINGS - 1, j + 1), top))
    return build("body", verts, faces)


# ── The carving: face, lid seam and back cracks ──

FACE_TILT = 19.0   # the face looks up a little, toward the strategy camera
FOCAL = 0.17
RIND = 0.026
CENTER = Vector((0, 0, ZC))
M_PAINT, M_GLOW, M_WALL, M_CORE, M_EMBER = range(5)


def frame(theta, tilt_deg):
    t = math.radians(tilt_deg)
    F = Vector((math.cos(theta) * math.cos(t), math.sin(theta) * math.cos(t), math.sin(t)))
    X = Vector((-math.sin(theta), math.cos(theta), 0.0))
    return F, X, F.cross(X)


def wrapped(F, X, U):
    """(u, v) on a cylinder of radius FOCAL around U -> a ray direction: u is arc
    length, so wide features (the grin) wrap around the gourd instead of flattening."""
    return lambda u, v: (F * (FOCAL * math.cos(u / FOCAL)) + X * (FOCAL * math.sin(u / FOCAL)) + U * v).normalized()


def scaled(shape, k, about=None):
    cu = sum(p[0] for p in shape) / len(shape) if about is None else about[0]
    cv = sum(p[1] for p in shape) / len(shape) if about is None else about[1]
    return [(cu + (u - cu) * k, cv + (v - cv) * k) for u, v in shape]


def face_shapes():
    """[(outline, core outline or None)] in face (u, v) metres."""
    j = lambda a: a + rng.uniform(-0.004, 0.004)  # noqa: E731
    eye = [(0.016, 0.028), (0.052, 0.0), (0.084, 0.018), (0.1, 0.074), (0.054, 0.052)]
    eye = scaled(eye, 1.15)
    right = [(j(u), j(v)) for u, v in eye]
    left = [(-j(u), j(v)) for u, v in reversed(eye)]
    # The hot core of an eye sits low and inward, like a pupil glaring at the camera.
    out = []
    for e in (right, left):
        c = (sum(p[0] for p in e) / len(e), sum(p[1] for p in e) / len(e) - 0.006)
        out.append((e, scaled(e, 0.48, c)))
    nose = scaled([(-0.015, -0.018), (0.016, -0.017), (0.0, 0.008)], 1.15)
    out.append((nose, scaled(nose, 0.45)))
    # A wide grin wrapping ~54 degrees each way, corners turned up, two fangs hanging
    # from the top lip, a lower fang and an odd square tooth standing on the bottom one.
    cu, cv = 0.16, -0.018
    top = lambda u: -0.048 + (cv + 0.048) * (u / cu) ** 2  # noqa: E731
    bot = lambda u: -0.118 + (cv + 0.118) * (u / cu) ** 2  # noqa: E731
    pts = [(-cu, cv)]
    upper = [-0.145, -0.12, -0.095, (-0.062, "fang"), -0.032, 0.0, 0.026, (0.056, "fang"), 0.09, 0.12, 0.145]
    for item in upper:
        if isinstance(item, tuple):
            u = item[0]
            w = 0.028
            pts += [(u - w / 2, top(u - w / 2)), (u + rng.uniform(-0.003, 0.003), top(u) - 0.031),
                    (u + w / 2, top(u + w / 2))]
        else:
            pts.append((item, top(item)))
    pts.append((cu, cv))
    lower = [0.145, 0.12, 0.09, (0.033, "tooth"), 0.0, -0.035, (-0.088, "fang"), -0.12, -0.145]
    for item in lower:
        if isinstance(item, tuple):
            u, kind = item
            if kind == "tooth":
                w = 0.028
                pts += [(u + w / 2, bot(u + w / 2)), (u + w / 2 - 0.002, bot(u) + 0.026),
                        (u - w / 2 + 0.002, bot(u) + 0.026), (u - w / 2, bot(u - w / 2))]
            else:
                w = 0.026
                pts += [(u + w / 2, bot(u + w / 2)), (u, bot(u) + 0.025), (u - w / 2, bot(u - w / 2))]
        else:
            pts.append((item, bot(item)))
    # The core of the grin: the outline squeezed toward the mouth's midline, so the
    # teeth shrink with it and it stays inside the cut. Checked, and shrunk if not.
    mid = lambda u: (top(u) + bot(u)) / 2  # noqa: E731
    for k in (0.42, 0.36, 0.3, 0.24):
        core = [(0.84 * u, mid(0.84 * u) + k * (v - mid(u))) for u, v in pts]
        samples = core + [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(core, core[1:] + core[:1])]
        if all(inside2d(p, pts) and dist2d(p, pts) > 0.0025 for p in samples):
            break
    out.append((pts, core))
    return out


def make_cutter(loops2d, dirs, depth, wall_out, wall_in, floor, name="cutter"):
    """A closed solid that runs along rays from the body centre, from outside the rind
    down to `depth` below it, so pocket walls stand square to the surface. One loop is a
    prism; two loops (outer, inner, same count) a band such as the lid seam. Walls take
    `wall_out` above half depth and `wall_in` below it; the floor takes `floor`.
    Returns (object, floor BVH)."""
    levels = (0.07, -depth * 0.5, -depth) if wall_out != wall_in else (0.07, -depth)
    verts, rows = [], []
    for loop in dirs:
        hits = []
        for d in loop:
            hit = raw_bvh.ray_cast(CENTER, d)
            hits.append((d, hit[3] if hit[0] is not None else FOCAL))
        loop_rows = []
        for off in levels:
            loop_rows.append(list(range(len(verts), len(verts) + len(hits))))
            verts += [CENTER + d * (s + off) for d, s in hits]
        rows.append(loop_rows)
    n = len(dirs[0])
    faces, mats, floor_faces = [], [], []
    for loop_rows in rows:
        for k in range(n):
            a, b = k, (k + 1) % n
            for lv, m in ((0, wall_out), (1, wall_in))[:len(levels) - 1]:
                hi, lo = loop_rows[lv], loop_rows[lv + 1]
                faces.append((hi[a], hi[b], lo[b], lo[a]))
                mats.append(m)
    if len(rows) == 1:
        out, flo = rows[0][0], rows[0][-1]
        for tri in triangulate2d(loops2d[0]):
            faces.append(tuple(out[i] for i in tri))
            mats.append(M_PAINT)
            faces.append(tuple(flo[i] for i in reversed(tri)))
            mats.append(floor)
            floor_faces.append(faces[-1])
    else:
        o, i_ = rows
        for k in range(n):
            a, b = k, (k + 1) % n
            faces.append((o[0][a], o[0][b], i_[0][b], i_[0][a]))
            mats.append(M_PAINT)
            faces.append((o[-1][a], i_[-1][a], i_[-1][b], o[-1][b]))
            mats.append(floor)
            floor_faces.append(faces[-1])
    cut = build(name, verts, faces)
    for poly, m in zip(cut.data.polygons, mats):
        poly.material_index = m
    # recalc_face_normals can turn a thin, curved prism inside out; the boolean then
    # cuts nothing. The signed volume tells.
    bm = bmesh.new()
    bm.from_mesh(cut.data)
    if bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.to_mesh(cut.data)
    bm.free()
    for m in BODY_MATS:
        cut.data.materials.append(m)
    return cut, BVHTree.FromPolygons(verts, floor_faces)


def carve(cutter):
    mod = body.modifiers.new("carve", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    mod.material_mode = "TRANSFER"
    gab.apply_modifiers(body)
    bpy.data.objects.remove(cutter)


def lid_dirs(points):
    """Ray directions whose hits on the gourd's top lie at these plan positions."""
    out = []
    for x, y in points:
        r_t = math.hypot(x, y)
        a = math.atan2(y, x)
        lo, hi = 0.0, 0.4
        for _ in range(22):
            rho = (lo + hi) / 2
            d = Vector((rho * math.cos(a), rho * math.sin(a), 0.09)).normalized()
            hit = raw_bvh.ray_cast(CENTER, d)
            r = math.hypot(hit[0].x, hit[0].y) if hit[0] is not None else 1.0
            lo, hi = (rho, hi) if r < r_t else (lo, rho)
        out.append(Vector((rho * math.cos(a), rho * math.sin(a), 0.09)).normalized())
    return out


def lid_band(radius=0.056, teeth=9, amp=0.01, width=0.0068):
    """The zig-zag seam of a carved lid, as outer and inner plan loops."""
    spin = rng.uniform(0, 2 * math.pi)
    mid = []
    for i in range(2 * teeth):
        a = spin + math.pi * i / teeth
        r = radius + (amp if i % 2 == 0 else -amp) * rng.uniform(0.8, 1.15)
        mid.append(Vector((r * math.cos(a), r * math.sin(a))))
    outer, inner = [], []
    n = len(mid)
    for i in range(n):
        p0, p1, p2 = mid[i - 1], mid[i], mid[(i + 1) % n]
        n0 = Vector(((p1 - p0).y, -(p1 - p0).x)).normalized()
        n1 = Vector(((p2 - p1).y, -(p2 - p1).x)).normalized()
        m = (n0 + n1).normalized()
        k = width / 2 / max(0.45, m.dot(n1))
        if m.dot(p1) < 0:
            m = -m
        outer.append(tuple(p1 + m * k))
        inner.append(tuple(p1 - m * k))
    return outer, inner


def crack_shape(length=0.06, width=0.0062, kinks=4, jag=0.005):
    """A jagged vertical sliver, pointed at both ends. Returns (outline, centre line
    [(u, v, half width)]) in (u, v) metres, the top end at v = +length / 2."""
    left, right, centre = [], [], []
    for i in range(kinks + 1):
        t = i / kinks
        v = (0.5 - t) * length
        u = rng.uniform(-jag, jag) if 0 < i < kinks else 0.0
        w = width * 0.5 * math.sin(math.pi * t) ** 0.6
        left.append((u - w, v))
        right.append((u + w, v))
        centre.append((u, v, w))
    return right + left[::-1][1:-1], centre


def crack_core(centre, k=0.4, trim=0.14):
    """A thin hot sliver along a crack's centre line, inside the cut: k of the crack's
    width, its ends pulled in by `trim` of the length so they stay inside the points."""
    n = len(centre) - 1

    def at(t):
        x = t * n
        i = min(int(x), n - 1)
        f = x - i
        (u0, v0, w0), (u1, v1, w1) = centre[i], centre[i + 1]
        return u0 + (u1 - u0) * f, v0 + (v1 - v0) * f, w0 + (w1 - w0) * f

    ts = [trim] + [i / n for i in range(1, n) if trim < i / n < 1 - trim] + [1 - trim]
    pts = [at(t) for t in ts]
    left = [(u - k * w, v) for u, v, w in pts[1:-1]]
    right = [(u + k * w, v) for u, v, w in pts[1:-1]]
    return [pts[0][:2]] + right + [pts[-1][:2]] + left[::-1]


def rotated(shape, deg, to=(0.0, 0.0)):
    a = math.radians(deg)
    c, s_ = math.cos(a), math.sin(a)
    return [(to[0] + u * c - v * s_, to[1] + u * s_ + v * c) for u, v in shape]


# ── Build ──

pose_param = gab.param("pose", "")

PAINTED = gab.painted()
GLOW = gab.glow("creep_face", "#ffd860", 3.0)
CUTWALL = gab.material("cutwall_tmp")
CORE = gab.glow("creep_face_core", "#fff2b0", 3.6)
# The lid seam and the back crack burn a lower, warmer orange than the face, so only
# the face is white-hot and the rest reads as candlelight leaking through the rind.
EMBER = gab.glow("creep_ember", gab.param("ember", "#ffb040"), gab.param("ember_k", 1.6))
BODY_MATS = (PAINTED, GLOW, CUTWALL, CORE, EMBER)

body = make_body()
gab.displace_noise(body, strength=0.006, size=0.09)   # a hand-grown gourd, not a lathe-turned one
for m in BODY_MATS:
    body.data.materials.append(m)
gab.smooth(body, 180)
uncut = KDTree(len(body.data.vertices))
uncut_normals = []
for v in body.data.vertices:
    uncut.insert(v.co, v.index)
    uncut_normals.append(v.normal.copy())
uncut.balance()
raw_bvh = BVHTree.FromPolygons([v.co.copy() for v in body.data.vertices],
                                [p.vertices[:] for p in body.data.polygons])

# The face: one cutter per feature, then a floating hot core in each pocket.
cores = []
F, X, U = frame(-math.pi / 2, FACE_TILT)
face_dir = wrapped(F, X, U)
for shape, core in face_shapes():
    cutter, floor_bvh = make_cutter([shape], [[face_dir(u, v) for u, v in shape]], RIND, M_WALL, M_GLOW, M_GLOW)
    carve(cutter)
    if core:
        cv = []
        for u, v in core:
            d = face_dir(u, v)
            hit = floor_bvh.ray_cast(CENTER, d)
            cv.append(CENTER + d * ((hit[3] if hit[0] is not None else FOCAL - RIND) + 0.0025))
        cores.append(build("core", cv, triangulate2d(core)))

# The lid seam: a zig-zag ring cut around the stem, seen from any heading: amber
# flesh in its upper walls, ember light below.
outer, inner = lid_band(radius=0.07, width=0.009)
cutter, _ = make_cutter([outer, inner], [lid_dirs(outer), lid_dirs(inner)], 0.016, M_WALL, M_EMBER, M_EMBER)
carve(cutter)

# One bold, branching crack across a back lobe, turned up toward the strategy camera,
# so a creep walking away still shows its light. A hot core runs along its middle.
crack_cores = []
theta = math.radians(90 - 22.5 + rng.uniform(-3, 3))   # the back crest between the two top leaves
Fc, Xc, Uc = frame(theta, 22)
d_back = wrapped(Fc, Xc, Uc)
CRACK_LEN = 0.13
main, centre = crack_shape(CRACK_LEN, 0.022, kinks=6, jag=0.007)
tilt = rng.uniform(8, 14) * (1 if rng.random() < 0.5 else -1)   # runs a little diagonal across the lobe
main = rotated(main, tilt)
centre = [(u, v, w) for (u, v), (_, _, w) in zip(rotated([c[:2] for c in centre], tilt), centre)]
cutter, floor_bvh = make_cutter([main], [[d_back(u, v) for u, v in main]], 0.018, M_WALL, M_EMBER, M_EMBER)
carve(cutter)
core = crack_core(centre)
cv = []
for u, v in core:
    d = d_back(u, v)
    hit = floor_bvh.ray_cast(CENTER, d)
    cv.append(CENTER + d * ((hit[3] if hit[0] is not None else FOCAL - 0.018) + 0.0025))
crack_cores.append(build("crack_core", cv, triangulate2d(core)))
# A branch forks off 40% of the way down the main crack, angled away from its lean.
i_fork = round(0.4 * (len(centre) - 1))
fork_u, fork_v = centre[i_fork][0], centre[i_fork][1]
branch, _ = crack_shape(0.06, 0.014, kinks=4, jag=0.004)
branch = [(u, v - 0.026) for u, v in branch]   # its top end at the fork
branch = rotated(branch, tilt + 38 * (-1 if tilt > 0 else 1), (fork_u, fork_v))
cutter, _ = make_cutter([branch], [[d_back(u, v) for u, v in branch]], 0.016, M_WALL, M_EMBER, M_EMBER)
carve(cutter)

core_obj = gab.join(cores, "face_core")
core_obj.data.materials.append(CORE)
crack_core_obj = crack_cores[0]
crack_core_obj.name = "crack_core"
crack_core_obj.data.materials.append(GLOW)


def tidy_rind():
    """The booleans leave long slivers in the rind around every cut, which smear vertex
    colours into dark wedges: merge the tiny edges and re-triangulate the rind (never
    across a material border) into fatter triangles."""
    i_paint = [m.name for m in body.data.materials].index("painted")
    bm = bmesh.new()
    bm.from_mesh(body.data)
    inner_edges = [e for e in bm.edges if e.link_faces and all(f.material_index == i_paint for f in e.link_faces)]
    bmesh.ops.dissolve_degenerate(bm, dist=0.0015, edges=inner_edges)

    def at_cut(f):
        return any(g.material_index != i_paint for v in f.verts for g in v.link_faces)

    rind = [f for f in bm.faces if f.material_index == i_paint and (len(f.verts) > 4 or at_cut(f))]
    if gab.param("check", 0):
        sizes = {}
        for f in bm.faces:
            if f.material_index == i_paint:
                sizes[len(f.verts)] = sizes.get(len(f.verts), 0) + 1
        print(f"check rind faces by corners before tidy: {sorted(sizes.items())}, {len(rind)} re-triangulated")
    bmesh.ops.triangulate(bm, faces=rind, quad_method="BEAUTY", ngon_method="BEAUTY")
    tris = {f for f in bm.faces if f.material_index == i_paint and len(f.verts) == 3}
    edges = [e for e in bm.edges if len(e.link_faces) == 2 and all(f in tris for f in e.link_faces)]
    bmesh.ops.beautify_fill(bm, faces=list(tris), edges=edges, method="ANGLE")
    bm.to_mesh(body.data)
    bm.free()


tidy_rind()

# Which faces are rind, cut wall and glow, after the booleans.
mats = [m.name for m in body.data.materials]
if gab.param("check", 0):
    use = {}
    for poly in body.data.polygons:
        use[mats[poly.material_index]] = use.get(mats[poly.material_index], 0) + 1
    print(f"check body slots {mats}, faces per material {use}")
i_glow, i_wall, i_core = mats.index("creep_face"), mats.index("cutwall_tmp"), mats.index("creep_face_core")
i_ember = mats.index("creep_ember")
glow_faces = [p.index for p in body.data.polygons if p.material_index in (i_glow, i_core)]
ember_faces = [p.index for p in body.data.polygons if p.material_index == i_ember]
wall_faces = [p.index for p in body.data.polygons if p.material_index == i_wall]
rind_faces = [p.index for p in body.data.polygons if p.material_index not in (i_glow, i_wall, i_core, i_ember)]
glow_verts = {v for i in glow_faces + ember_faces for v in body.data.polygons[i].vertices}
wall_verts = {v for i in wall_faces for v in body.data.polygons[i].vertices}
rind_verts = {v for i in rind_faces for v in body.data.polygons[i].vertices}
rim = KDTree(len(body.data.vertices))
n_rim = 0
for v in (rind_verts & (wall_verts | glow_verts)):
    rim.insert(body.data.vertices[v].co, v)
    n_rim += 1
rim.balance()

body_bvh = BVHTree.FromPolygons([v.co.copy() for v in body.data.vertices],
                                 [p.vertices[:] for p in body.data.polygons])

parts = []   # (object, {bone: weights or None for all 1.0})
shade_casters = []   # parts that lie on the gourd and paint a contact shadow on it


def weight_groups(obj, weights):
    """Vertex groups set on a part before it is joined: {bone: [weight per vertex]}."""
    for bone_name, ws in weights.items():
        g = obj.vertex_groups.get(bone_name) or obj.vertex_groups.new(name=bone_name)
        for vi, w in enumerate(ws):
            if w > 0.001:
                g.add([vi], w, "REPLACE")


# ── Legs: gnarled roots that splay into planted toes ──

HIP_Z, ANKLE_Z = 0.25, 0.04
HIP_X, SPLAY = 0.09, 1.45
LEG_LEN = HIP_Z - ANKLE_Z


def make_leg(sign):
    x = HIP_X * sign
    knot = rng.uniform(0.95, 1.15)
    ankle = Vector((x * SPLAY, 0.0, ANKLE_Z))
    path = [(x * 0.92, 0.0, 0.29), (x * 1.06, -0.012, 0.212), (x * 1.17, -0.02, 0.158), (x * 1.31, -0.016, 0.105),
            tuple(ankle), tuple(ankle + Vector((0.004 * sign, 0.004, -0.02)))]
    radii = [0.042, 0.034, 0.04 * knot, 0.026, 0.031, 0.0]
    leg, ts = tube(f"leg_{sign}", path, radii, sides=7, twist=0.35, jitter=0.1)
    gab.smooth(leg, 70)

    def leg_color(vi, co, poly):
        t = co.z / 0.27
        c = ramp([(0.0, col("wood_dark")), (0.2, col("wood")), (0.72, col("wood_light")), (1.0, col("bark"))], t)
        moss = smoothstep(0.035, 0.06, co.z) * smoothstep(0.12, 0.075, co.z)
        moss *= 0.5 + 0.5 * noise.noise(co * 40 + NOISE_AT)
        c = lerp(c, col("leaf_deep"), 0.75 * max(0.0, moss))
        return c * mottle(co)

    paint_fn(leg, leg_color, "bark")
    leg.data.materials.append(PAINTED)

    # Rootlets: thin side roots sprouting from the knot and the shin, reaching out and down.
    roots = [leg]
    for at, yaw, reach in ((Vector(path[2]), rng.uniform(-30, 10), 0.06), (Vector(path[3]), rng.uniform(150, 200), 0.05)):
        a = math.radians(yaw)
        out_dir = Vector((math.cos(a) * sign, math.sin(a), 0))
        p0 = at + out_dir * 0.024
        p1 = p0 + out_dir * reach * 0.55 + Vector((0, 0, -0.012))
        p2 = p0 + out_dir * reach + Vector((0, 0, -0.04))
        p2.z = max(p2.z, 0.03)
        rt, rts = tube("rootlet", [p0, p1, p2], [0.009, 0.0065, 0.0], sides=4, jitter=0.1)
        gab.smooth(rt, 70)
        paint_fn(rt, lambda vi, co, p, rts=rts: ramp([(0, col("wood")), (0.6, col("wood_light")), (1, col("stalk"))],
                                                    rts[vi]) * mottle(co), "plain")
        rt.data.materials.append(PAINTED)
        roots.append(rt)
    leg = gab.join(roots, f"leg_{sign}")

    toes = []
    for yaw, length in ((-92 + 14 * sign, 0.078), (-92 + 62 * sign, 0.066), (90 - 30 * sign, 0.052),
                        (-92 - 32 * sign, 0.058)):
        a = math.radians(yaw + rng.uniform(-8, 8))
        d = Vector((math.cos(a), math.sin(a), 0))
        root = ankle + Vector((0, 0, 0.004))
        mid = ankle + d * length * 0.5 + Vector((0, 0, -0.014))
        tip = ankle + d * length
        tip.z = 0.002
        toe, tts = tube("toe", [root, mid, tip], [0.021, 0.0145, 0.0], sides=5, jitter=0.1)
        gab.smooth(toe, 70)
        paint_fn(toe, lambda vi, co, p, tts=tts: ramp([(0, col("wood")), (0.55, col("wood_light")),
                                                        (1, col("stalk"))], tts[vi]) * mottle(co), "plain")
        toe.data.materials.append(PAINTED)
        toes.append(toe)
    return leg, gab.join(toes, f"foot_{sign}")


for sign, side in ((1, "L"), (-1, "R")):
    leg, foot = make_leg(sign)
    parts.append((leg, {f"leg_{side}": None}))
    parts.append((foot, {f"foot_{side}": None}))


# ── Arms: vines that hang out past the gourd, ending in big leaf claws ──

ARM = [(0.118, -0.012, 0.318), (0.176, -0.03, 0.304), (0.214, -0.052, 0.266), (0.226, -0.08, 0.228),
       (0.229, -0.104, 0.197)]
ELBOW = 2


def arm_points(sign):
    return [Vector((x * sign, y, z)) for x, y, z in ARM]


def make_arm(sign, side):
    pts = arm_points(sign)
    vine, ts = tube(f"vine_{side}", pts, [0.03, 0.026, 0.024, 0.019, 0.017], sides=6, twist=0.75 * sign)
    gab.smooth(vine, 80)
    t_elbow = ts[ELBOW * 6]

    def vine_color(vi, co, p):
        t = ts[vi]
        c = ramp([(0, col("leaf_deep")), (0.45, col("leaf")), (1, col("leaf_light"))], t)
        # Two dark strands spiral down the twisted vertex rings: a braided vine.
        if vi % 6 in (0, 3):
            c = c * 0.72
        # A darker node at the elbow, where the leaf and the tendril sprout.
        c = lerp(c, col("leaf_deep") * 0.85, 0.7 * smoothstep(0.1, 0.0, abs(t - t_elbow)))
        return c * mottle(co)

    paint_fn(vine, vine_color, "plain")
    vine.data.materials.append(PAINTED)
    w_fore = {i: smoothstep(0.42, 0.7, t) for i, t in enumerate(ts)}
    out = [(vine, {f"arm_{side}": {i: 1 - w for i, w in w_fore.items()}, f"fore_{side}": w_fore})]
    shade_casters.append(vine)

    # Tendril: a tapering corkscrew off the elbow, curling back and up.
    elbow = pts[ELBOW]
    axis = Vector((0.6 * sign, 0.7, 0.45)).normalized()
    u = axis.cross(Vector((0, 0, 1))).normalized()
    v = axis.cross(u)
    coil = []
    for i in range(6):
        t = i / 5
        a = 2 * math.pi * 1.8 * t
        rad = 0.015 * (1 - 0.55 * t)
        coil.append(elbow + axis * (0.022 + 0.05 * t) + (u * math.cos(a) + v * math.sin(a)) * rad)
    ten, tts = tube(f"tendril_{side}", coil, [0.0038] * 5 + [0.0], sides=3)
    paint_fn(ten, lambda vi, co, p: lerp(col("leaf"), col("leaf_tip"), tts[vi]), "plain")
    ten.data.materials.append(PAINTED)
    gab.smooth(ten, 80)
    out.append((ten, {f"fore_{side}": None}))

    # A vine leaf on the elbow node, reaching out and up, the tendril curling behind it.
    out_dir = Vector((sign, 0.0, 0.35)).normalized()
    d = Vector((0.55 * sign, 0.12, 0.83)).normalized()
    lf, lts, nf, rib = blade(f"elbow_leaf_{side}", elbow + out_dir * 0.016, d, Vector((0.2 * sign, -1, 0.5)), 0.058,
                             0.042, fold=0.22, curl=0.018, segs=3, twist=0.25 * sign)

    def el_color(vi, co, poly, lts=lts, nf=nf, rib=rib):
        c = ramp([(0, col("leaf_deep")), (0.6, col("leaf")), (1, col("leaf_bright"))], lts[vi])
        c = c * (0.78 if vi in rib and lts[vi] < 0.99 else 1.0)
        return c * (0.55 if poly.index >= nf else 1.0)

    paint_fn(lf, el_color, "plain")
    lf.data.materials.append(PAINTED)
    gab.smooth(lf, 60)
    out.append((lf, {f"fore_{side}": None}))

    # Leaf claws: three fingers and a thumb fanning out of the wrist, reaching forward.
    wrist = pts[-1]
    fwd = ((pts[-1] - pts[-2]).normalized() + Vector((0, -0.9, 0.3))).normalized()
    across = Vector((1, 0, 0)) * sign
    across = (across - fwd * across.dot(fwd)).normalized()
    palm_n = fwd.cross(across).normalized() * sign
    claws = []
    for spread, length, lift in ((-0.55, 0.076, 0.0), (0.0, 0.086, -0.08), (0.55, 0.076, 0.0),
                                 (1.45, 0.058, 0.35)):
        d = (fwd * math.cos(spread) + across * math.sin(spread) + palm_n * lift).normalized()
        b, bts, nf, rib = blade("claw", wrist - fwd * 0.006, d, palm_n, length + rng.uniform(-0.006, 0.006),
                                0.038, fold=0.32, curl=0.036, segs=3)

        def claw_color(vi, co, poly, bts=bts, nf=nf, rib=rib):
            c = ramp([(0, col("leaf_deep")), (0.55, col("leaf")), (0.9, col("leaf_bright")), (1, col("leaf_tip"))],
                     bts[vi])
            c = c * (0.75 if vi in rib and bts[vi] < 0.99 else 1.0)
            return c * (0.5 if poly.index >= nf else 1.0)

        paint_fn(b, claw_color, "plain")
        b.data.materials.append(PAINTED)
        gab.smooth(b, 60)
        claws.append(b)
    out.append((gab.join(claws, f"hand_{side}"), {f"fore_{side}": None}))
    return out


for sign, side in ((1, "L"), (-1, "R")):
    parts += make_arm(sign, side)


# ── Stem: tall, ridged and hooked, with a big corkscrew curl ──

top_z = ZC + H * profile(math.pi)[1]
lean = math.radians(rng.uniform(-30, 30)) + math.pi  # leans back, away from the face... roughly
lean_dir = Vector((math.sin(lean) * 0.6, -math.cos(lean), 0)).normalized()
hook_dir = lean_dir.cross(Vector((0, 0, 1))) * (1 if rng.random() < 0.5 else -1)
s0 = Vector((0, 0, top_z + 0.016))
# The base flares into a skirt that lies just over the dimple's bowl (its rim tucked
# under the rind), so the stem grows out of the gourd instead of standing in a hole.
FLARE_R = 0.052
stem_pts = [Vector((0, 0, top_z + 0.010)), s0,
            s0 + Vector((0, 0, 0.041)) + lean_dir * 0.006,
            s0 + Vector((0, 0, 0.081)) + lean_dir * 0.026,
            s0 + Vector((0, 0, 0.108)) + lean_dir * 0.055 + hook_dir * 0.01,
            s0 + Vector((0, 0, 0.102)) + lean_dir * 0.078 + hook_dir * 0.03]
stem_pts.append(stem_pts[-1] + (stem_pts[-1] - stem_pts[-2]).normalized() * 0.012)   # a rounded, broken tip
STEM_SIDES = 8
stem, sts = tube("stem", stem_pts, [FLARE_R, 0.032, 0.025, 0.021, 0.019, 0.017, 0.0], sides=STEM_SIDES,
                 ridges=0.05, twist=0.15, cap_end=False)
gab.smooth(stem, 60)


def stem_color(vi, co, poly):
    t = sts[vi]
    c = ramp([(0, col("needle")), (0.3, col("stem")), (0.6, col("leaf")), (0.85, col("wood")),
              (1, col("wood_dark"))], t)
    # A dark ring where the stem meets the rind.
    c = lerp(col("needle_deep"), c, smoothstep(0.0, 0.1, t))
    # Painted ridges: four dark grooves running up the stem, between the lit ribs.
    if vi < len(sts) - 1:
        c = c * (1.0 if (vi % STEM_SIDES) % 2 == 0 else 0.74)
    return c * mottle(co, 0.05, 0.02)


paint_fn(stem, stem_color, "bark")
stem.data.materials.append(PAINTED)
# The flared skirt stays on the rind; the stem bends above it.
parts.append((stem, {"body": {i: 1.0 for i in range(STEM_SIDES)},
                     "stem": {i: 1.0 for i in range(STEM_SIDES, len(stem.data.vertices))}}))
shade_casters.append(stem)

# A corkscrew tendril spiralling off the stem base: the topknot of the silhouette.
side_dir = -hook_dir   # the curl springs out opposite the hook
coil = []
for i in range(11):
    t = i / 10
    a = 2 * math.pi * 2.2 * t
    rad = 0.024 * (1 - 0.5 * t)
    center = stem_pts[1] + side_dir * (0.035 + 0.085 * t) + Vector((0, 0, 0.035 * t + 0.05 * t * t))
    coil.append(center + (side_dir * math.cos(a) + Vector((0, 0, 1)) * math.sin(a)) * rad * 0.6
                + lean_dir * math.sin(a) * rad)
curl, cts = tube("curl", coil, [0.0052] * 10 + [0.0], sides=3)
gab.smooth(curl, 80)
paint_fn(curl, lambda vi, co, p: lerp(col("stem"), col("leaf_tip"), cts[vi] ** 1.5), "plain")
curl.data.materials.append(PAINTED)
parts.append((curl, {"stem": None}))


def surface(bvh, p, lift):
    """p pulled onto the pumpkin along the ray from the body centre, lifted off it."""
    c = Vector((0, 0, ZC - 0.03))
    d = (p - c).normalized()
    hit = bvh.ray_cast(c + d * 0.4, -d)
    if hit[0] is None:
        return p
    return hit[0] + hit[1] * lift


def make_top_leaf(yaw_deg, L, name, N=16, lobes=5):
    yaw = math.radians(yaw_deg)
    d = Vector((math.cos(yaw), math.sin(yaw), 0))
    s = Vector((-d.y, d.x, 0))
    base = Vector((0, 0, top_z)) + d * 0.03
    c2 = 0.55 * L
    outline, mid = [], []
    for i in range(N):
        a = -math.pi + 2 * math.pi * (i + 0.5) / N
        rho = 0.5 * L * (0.78 + 0.22 * math.cos(lobes * a)) * (1 - 0.6 * math.exp(-((abs(a) - math.pi) / 0.35) ** 2))
        rho *= 1 + rng.uniform(-0.06, 0.06)
        outline.append((c2 + rho * math.cos(a), rho * math.sin(a), 1.0, math.cos(lobes * a)))
        mid.append((c2 + 0.5 * rho * math.cos(a), 0.5 * rho * math.sin(a), 0.5, math.cos(lobes * a)))
    flat_pts = [(c2, 0.0, 0.0, 1.0)] + mid + outline
    verts, info = [], []
    for a, b, ring, vein in flat_pts:
        p = base + d * a + s * b + Vector((0, 0, 0.05))
        lift = 0.008 + 0.02 * ring ** 2 + 0.006 * max(0.0, vein) * ring
        verts.append(surface(body_bvh, p, lift))
        info.append((ring, vein))
    faces = []
    for i in range(N):
        j = (i + 1) % N
        faces.append((0, 1 + i, 1 + j))
        faces.append((1 + i, 1 + N + i, 1 + N + j, 1 + j))
    off = len(verts)
    front = []
    for f in faces:
        pts = [verts[k] for k in f]
        nn = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        front.append(f if nn.z >= 0 else f[::-1])
    back = [tuple(k + off for k in reversed(f)) for f in front]
    leaf = build("top_leaf", verts + verts, front + back, recalc=False)
    nf = len(front)
    info = info + info

    def leaf_color(vi, co, poly):
        ring, vein = info[vi]
        c = ramp([(0, col("needle")), (0.5, col("leaf_deep")), (1, col("leaf_light"))], ring)
        c = lerp(c, col("leaf_tip"), 0.55 * max(0.0, vein) * ring ** 2)
        c = lerp(c, col("needle_deep"), 0.45 * max(0.0, -vein) * ring)
        return c * (0.55 if poly.index >= nf else 1.0)

    paint_fn(leaf, leaf_color, "plain")
    gab.smooth(leaf, 70)
    leaf.data.materials.append(PAINTED)
    # The leaf's edge flutters with the lagging stem.
    weight_groups(leaf, {"stem": [0.4 * r ** 2 for r, _ in info], "body": [1 - 0.4 * r ** 2 for r, _ in info]})
    stalk, _ = tube("leaf_stalk", [stem_pts[1] + Vector((0, 0, -0.004)), base + d * 0.012 + Vector((0, 0, 0.012)),
                                   verts[0] * 0.5 + base * 0.5],
                    [0.007, 0.006, 0.004], sides=4)
    paint_fn(stalk, lambda vi, co, p: col("stem"), "plain")
    stalk.data.materials.append(PAINTED)
    weight_groups(stalk, {"body": [1.0] * len(stalk.data.vertices)})
    return gab.join([leaf, stalk], name)


for yaw, L, name, n, lobes in ((rng.uniform(105, 140), 0.165, "top_leaf", 15, 5),
                               (rng.uniform(5, 35), 0.1, "small_leaf", 12, 3)):
    leaf = make_top_leaf(yaw, L, name, n, lobes)
    parts.append((leaf, {}))
    shade_casters.append(leaf)


# ── Shoulder vines: from the stem over the gourd's shoulders into the arms ──

def make_shoulder_vine(sign, side):
    end = arm_points(sign)[0]
    end_theta = math.atan2(end.y, end.x)
    start_theta = end_theta + sign * math.radians(rng.uniform(35, 55))  # starts behind, wraps forward
    pts = []
    for i in range(8):
        t = i / 7
        theta = lerp(start_theta, end_theta, t ** 0.8)
        elev = lerp(1.25, 0.08, t ** 1.2)
        p = Vector((math.cos(theta) * math.cos(elev) * 0.2, math.sin(theta) * math.cos(elev) * 0.2,
                    ZC + math.sin(elev) * 0.2))
        pts.append(surface(body_bvh, p, 0.007) if i > 0 else Vector((0, 0, top_z + 0.004)))
    pts[-1] = end + Vector((0.01 * sign, 0, 0.008))
    vine, ts = tube(f"shoulder_{side}", pts, [lerp(0.0065, 0.013, (i / 7)) for i in range(8)], sides=4,
                    twist=0.3)
    gab.smooth(vine, 80)
    paint_fn(vine, lambda vi, co, p: ramp([(0, col("leaf_light")), (0.5, col("leaf")), (1, col("leaf_deep"))],
                                          ts[vi]) * mottle(co), "plain")
    vine.data.materials.append(PAINTED)
    out = [vine]
    for at in (3, 5):
        p0 = pts[at]
        outward = (p0 - Vector((0, 0, ZC))).normalized()
        along = (pts[at + 1] - pts[at - 1]).normalized()
        d = (along * 0.5 + outward * 0.35 + Vector((0, 0, 0.3)) + along.cross(outward) * sign * 0.4).normalized()
        b, bts, nf, rib = blade("vine_leaf", p0, d, outward, 0.045 + rng.uniform(-0.005, 0.008), 0.032, fold=0.25,
                           curl=0.012, segs=3)

        def vl_color(vi, co, poly, bts=bts, nf=nf, rib=rib):
            c = ramp([(0, col("leaf_deep")), (0.6, col("leaf_bright")), (1, col("leaf_tip"))], bts[vi])
            c = c * (0.78 if vi in rib and bts[vi] < 0.99 else 1.0)
            return c * (0.6 if poly.index >= nf else 1.0)

        paint_fn(b, vl_color, "plain")
        b.data.materials.append(PAINTED)
        gab.smooth(b, 60)
        out.append(b)
    vines = gab.join(out, f"shoulder_{side}")
    shade_casters.append(vines)
    return vines


for sign, side in ((1, "L"), (-1, "R")):
    parts.append((make_shoulder_vine(sign, side), {"body": None}))


# ── A ruff of leaves drooping from under the belly like a skirt, clear of the legs ──

RUFF_Z = 0.212
ruff = []
ruff_angles = [-145, -112, -68, -38, 38, 68, 90, 112, 145]
dried = set(rng.sample(range(len(ruff_angles)), 2))   # two dry, autumn leaves among the green
for i, deg in enumerate(ruff_angles):
    a = math.radians(deg + rng.uniform(-6, 6))
    out_dir = Vector((math.cos(a), math.sin(a), 0))
    root = surface(body_bvh, Vector((0, 0, RUFF_Z + rng.uniform(-0.006, 0.006))) + out_dir * 0.12, -0.004)
    pitch = math.radians(rng.uniform(-38, -28))
    d = out_dir * math.cos(pitch) + Vector((0, 0, math.sin(pitch)))
    nrm = Vector((0, 0, 1)) - d * d.z
    L = rng.uniform(0.075, 0.105)
    b, bts, nf, rib = blade("ruff", root, d, nrm, L, 0.06, fold=0.3, curl=0.034, segs=3,
                            twist=rng.uniform(-0.3, 0.3))
    if i in dried:
        tone = ("wood", "amber", "autumn")
    else:
        tone = [("needle_deep", "leaf_deep", "leaf_bright"), ("needle", "leaf", "leaf_light"),
                ("needle_deep", "leaf_deep", "grass_light")][i % 3]

    def ruff_color(vi, co, poly, bts=bts, nf=nf, tone=tone, rib=rib):
        c = ramp([(0, col(tone[0])), (0.45, col(tone[1])), (1, col(tone[2]))], bts[vi])
        c = c * (0.75 if vi in rib and bts[vi] < 0.99 else 1.0)
        return c * (0.55 if poly.index >= nf else 1.0)

    paint_fn(b, ruff_color, "plain")
    b.data.materials.append(PAINTED)
    gab.smooth(b, 60)
    # The leaves hang from the belly and swing on their own bone: roots fixed, tips free.
    weight_groups(b, {"ruff": bts, "body": [1 - t for t in bts]})
    ruff.append(b)
ruff_obj = gab.join(ruff, "ruff")
parts.append((ruff_obj, {}))
shade_casters.append(ruff_obj)


# ── Paint the gourd, now that everything lying on it is known ──

caster_bvh = []
for o in shade_casters:
    caster_bvh.append(BVHTree.FromPolygons([v.co.copy() for v in o.data.vertices],
                                           [p.vertices[:] for p in o.data.polygons]))


def contact(co):
    """0..1: how close the nearest leaf, vine or stem lies over this point."""
    best = 1.0
    for bvh in caster_bvh:
        hit = bvh.find_nearest(co)
        if hit[0] is not None:
            best = min(best, hit[3])
    return smoothstep(0.032, 0.008, best)


def uv_meridian(obj, faces, scale_u=0.5, scale_v=0.5):
    """UVs that run along the lobes: u = angle x a fixed radius, v = height, so a
    streaky pattern follows the ribs and meets at the stem."""
    mesh = obj.data
    layer = mesh.uv_layers.get("UVMap") or mesh.uv_layers.new(name="UVMap")
    for i in faces:
        poly = mesh.polygons[i]
        coords = [mesh.vertices[mesh.loops[li].vertex_index].co for li in poly.loop_indices]
        angles = [math.atan2(c.y, c.x) for c in coords]
        if max(angles) - min(angles) > math.pi:
            angles = [a + 2 * math.pi if a < 0 else a for a in angles]
        for li, c, a in zip(poly.loop_indices, coords, angles):
            layer.data[li].uv = (a * R * scale_u, c.z * scale_v)


gab.uv_cylinder(body)
uv_meridian(body, rind_faces, gab.param("uscale", 0.35), gab.param("vscale", 0.5))
gab.smooth(body, 48)

z_lo = min(v.co.z for v in body.data.vertices)
z_hi = max(v.co.z for v in body.data.vertices)
# Darker and redder than the orange pumpkins by the road: the full pumpkin and ember
# tones only on the lit crests, autumn yellow on the tips of the top ones.
BODY_RAMP = [(0.0, col("shadow")), (0.35, col("pumpkin_dark")), (0.65, col("pumpkin_deep")),
             (0.9, col("pumpkin")), (1.0, col("pumpkin"))]
lobe_tone = [rng.uniform(-0.07, 0.07) for _ in range(LOBES)]


def body_color(vi, co, poly):
    t = (co.z - z_lo) / (z_hi - z_lo)
    c = ramp(BODY_RAMP, t)
    s, k = lobe(math.atan2(co.y, co.x))
    c = c * (1 + lobe_tone[k] * s)
    groove = (1 - s) ** 2.2
    c = lerp(c, col("groove"), 0.75 * groove * (0.6 + 0.4 * t))
    c = lerp(c, col("shadow") * 0.8, 0.5 * groove * (1 - t))
    crest = s ** 3 * smoothstep(0.45, 0.95, t)
    c = lerp(c, col("ember"), 0.55 * crest)
    c = lerp(c, col("autumn"), 0.75 * s ** 4 * smoothstep(0.8, 0.97, t))
    # An olive blush where the stem grows out.
    rxy = math.hypot(co.x, co.y)
    c = lerp(c, col("#8a6a26"), 0.55 * smoothstep(0.075, 0.03, rxy) * smoothstep(0.75, 0.95, t))
    # Scorched rind around every cut, so the glow stands out against it.
    if n_rim:
        _, _, d = rim.find(co)
        c = lerp(c, col("groove") * 0.6, 0.6 * math.exp(-d / 0.005))
    # Painted contact shadow under the leaves, vines and stem.
    c = c * (1 - 0.38 * contact(co))
    return c * mottle(co)


def wall_color(vi, co, poly):
    # Pale flesh, lit from the inside: bright where it meets the glowing half.
    return col("amber_light") if vi in glow_verts else col("amber")


paint_fn(body, body_color, gab.param("rind", "thatch"), rind_faces)
paint_fn(body, wall_color, "plain", wall_faces)
paint_fn(body, lambda vi, co, p: col("glow_yellow"), "plain", glow_faces)
paint_fn(body, lambda vi, co, p: col("glow_orange"), "plain", ember_faces)
# Drop the temporary cut-wall slot (its faces are painted flesh). The slots are rebuilt
# by name: materials.pop() shifts face indices itself in some Blender versions.
face_mats = ["painted" if mats[p.material_index] == "cutwall_tmp" else mats[p.material_index]
             for p in body.data.polygons]
body.data.materials.clear()
final_mats = [PAINTED, GLOW, CORE, EMBER]
for m in final_mats:
    body.data.materials.append(m)
order = [m.name for m in final_mats]
for poly, name in zip(body.data.polygons, face_mats):
    poly.material_index = order.index(name)
bpy.data.materials.remove(CUTWALL)


def uncut_normal(co):
    """The smooth normal the gourd had here before it was carved."""
    n, total = Vector(), 0.0
    for _, i, d in uncut.find_n(co, 4):
        w = 1.0 / (d + 1e-4) ** 2
        n += uncut_normals[i] * w
        total += w
    return (n / total).normalized()


# The booleans re-triangulate the rind around every cut, which bends smooth normals
# into blotches; the rind keeps the normals of the uncut gourd instead.
rind_set = set(rind_faces)
loop_normals = [(0.0, 0.0, 0.0)] * len(body.data.loops)
for poly in body.data.polygons:
    if poly.index in rind_set:
        for li in poly.loop_indices:
            loop_normals[li] = tuple(uncut_normal(body.data.vertices[body.data.loops[li].vertex_index].co))
body.data.normals_split_custom_set(loop_normals)
paint_fn(core_obj, lambda vi, co, p: col("glow_pale"), "plain")
paint_fn(crack_core_obj, lambda vi, co, p: col("glow_yellow"), "plain")
parts.insert(0, (body, {"body": None}))
parts.insert(1, (core_obj, {"body": None}))
parts.insert(2, (crack_core_obj, {"body": None}))


# ── Rig ──

bones = [
    ("root", (0, 0, 0), (0, 0, 0.06), None),
    ("body", (0, 0, HIP_Z - 0.01), (0, 0, 0.4), "root"),
    ("stem", tuple(stem_pts[1]), tuple(stem_pts[-2]), "body"),
    ("ruff", (0, 0, RUFF_Z), (0, 0, RUFF_Z + 0.04), "body"),
]
for sign, side in ((1, "L"), (-1, "R")):
    ankle = (HIP_X * SPLAY * sign, 0.0, ANKLE_Z)
    bones.append((f"leg_{side}", (HIP_X * sign, 0.0, HIP_Z), ankle, "root"))
    bones.append((f"foot_{side}", ankle, (ankle[0] + 0.01 * sign, -0.06, 0.012), f"leg_{side}"))
    pts = arm_points(sign)
    bones.append((f"arm_{side}", tuple(pts[0]), tuple(pts[ELBOW]), "body"))
    bones.append((f"fore_{side}", tuple(pts[ELBOW]), tuple(pts[-1]), f"arm_{side}"))
arm = gab.armature("rig", bones)

for obj, groups in parts:
    for bone_name, weights in groups.items():
        g = obj.vertex_groups.get(bone_name) or obj.vertex_groups.new(name=bone_name)
        if weights is None:
            g.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
        else:
            for vi, w in weights.items():
                if w > 0.001:
                    g.add([vi], w, "REPLACE")
if gab.param("check", 0):
    for obj, _ in parts:
        print(f"check part {obj.name}: {gab.triangles(obj)} tris, {len(obj.data.vertices)} verts")
gourd = gab.join([p[0] for p in parts], "gourdling")
if gab.param("check", 0):
    gm = [m.name for m in gourd.data.materials]
    use = {}
    for poly in gourd.data.polygons:
        use[gm[poly.material_index]] = use.get(gm[poly.material_index], 0) + 1
    print(f"check gourd slots {gm}, faces per material {use}")
mod = gourd.modifiers.new("Armature", "ARMATURE")
mod.object = arm
gourd.parent = arm


# ── Animation ──

def act(name, frames, sample):
    """Keys every frame from sample(frame) -> {bone: (rot_deg, loc, scale)}. Rotations
    and offsets are given in armature axes (X right, -Y forward, Z up) about the bone
    head and converted to each bone's local frame, so the poses read the way they are
    written. The last frame repeats the first so the loop closes."""
    action = bpy.data.actions.new(name)
    arm.animation_data_create()
    arm.animation_data.action = action
    rest = {b.name: b.matrix_local.to_3x3() for b in arm.data.bones}
    last = {}
    for f in range(frames + 1):
        for bone_name, (rot, loc, scl) in sample(f % frames).items():
            pb = arm.pose.bones[bone_name]
            pb.rotation_mode = "QUATERNION"
            B = rest[bone_name]
            Rw = Euler([math.radians(a) for a in rot], "XYZ").to_matrix()
            q = (B.inverted() @ Rw @ B).to_quaternion()
            if bone_name in last and last[bone_name].dot(q) < 0:
                q.negate()
            last[bone_name] = q
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=f)
            pb.location = B.inverted() @ Vector(loc)
            pb.keyframe_insert("location", frame=f)
            if scl is not None:
                pb.scale = scl
                pb.keyframe_insert("scale", frame=f)
    track = arm.animation_data.nla_tracks.new()
    track.name = name
    track.strips.new(name, 0, action)
    arm.animation_data.action = None


# The walk is a vault over stiff legs. A planted foot moves back at a constant speed
# (the sine of the leg angle runs linearly), and the hips drop as the leg leans so
# that foot stays on the ground: the creep hops onto each foot. STRIDE is the ground
# speed in game units per second (the game draws creeps 1.5x) at which the planted
# feet do not slide; creep.gd plays the cycle at speed / stride, and stride defaults
# to 1.0, so the swing is sized for exactly that.
WALK_FRAMES, FPS, GAME_SCALE = 24, 30, 1.5
STRIDE = 1.0
STANCE_S = WALK_FRAMES / FPS / 2
SWING = (STRIDE * STANCE_S / GAME_SCALE) / (2 * LEG_LEN)   # sin of the widest leg angle
LIFT = 0.065


def wrap01(x):
    return x - math.floor(x)


def leg_state(p):
    """p in radians: 0..pi planted (front to back), pi..2pi swinging forward.
    Returns (leg angle deg, lift, foot pitch deg in the world, planted angle or None)."""
    p = p % (2 * math.pi)
    if p < math.pi:
        a = math.asin(SWING * (2 * p / math.pi - 1))
        return math.degrees(a), 0.0, 0.0, a
    u = (p - math.pi) / math.pi
    a = math.asin(SWING * (0.5 * (1 - 2 * u) + 0.5 * math.cos(math.pi * u)))
    up = math.sin(math.pi * u)
    # Toes trail down as the foot leaves the ground, curl under at the top, and come
    # level again (a little up, reaching) just before it lands.
    toe = 24 * up ** 2 * (1 - u) - 8 * math.sin(math.pi * min(1.0, max(0.0, (u - 0.6) / 0.4)))
    return math.degrees(a), LIFT * up ** 0.8, toe, None


def impact(w, at=0.05, width=0.11):
    """A pulse just after each footfall; w is the step phase 0..1."""
    d = min(abs(wrap01(w - at)), 1 - abs(wrap01(w - at)))
    return math.exp(-(d / width) ** 2)


def walk(f):
    ph = 2 * math.pi * f / WALK_FRAMES
    w = wrap01(f / (WALK_FRAMES / 2))               # step phase: 0 at each footfall
    lag2 = wrap01((f - 2) / (WALK_FRAMES / 2))      # the stem follows two frames late
    lag1 = wrap01((f - 1) / (WALK_FRAMES / 2))
    keys = {}
    planted = None
    for side, sign, off in (("L", 1, 0.0), ("R", -1, math.pi)):
        a, lift, toe, plant = leg_state(ph + off)
        if plant is not None:
            planted = plant
        keys[f"leg_{side}"] = ((a, 0, 0), (0, 0, lift), None)
        keys[f"foot_{side}"] = ((toe - a, 0, 0), (0, 0, 0), None)
    drop = -LEG_LEN * (1 - math.cos(planted))
    keys["root"] = ((0, 0, 0), (0, 0, drop), None)
    hit = impact(w)
    air = math.sin(math.pi * w) ** 2
    sz = 1 - 0.10 * hit + 0.05 * air
    sxy = 1 / math.sqrt(sz)
    def body_roll(phase):
        return 11 * math.sin(phase) * (0.75 + 0.25 * abs(math.sin(phase)))

    roll = body_roll(ph)
    keys["body"] = ((5 + 5 * hit - 2 * air, roll, 8 * math.cos(ph)),
                    (0.012 * math.sin(ph), 0, -0.006 * hit), (sxy, sz, sxy))
    keys["stem"] = ((-6 + 14 * impact(lag2) - 4 * math.sin(math.pi * lag2) ** 2,
                     -16 * math.sin(ph - 2 * math.pi * 2 / WALK_FRAMES), 4 * math.cos(ph)), (0, 0, 0), None)
    # The ruff lags the body: it nods and flares out two frames after each footfall and
    # rolls back against the body's rock.
    flare = 1 + 0.1 * impact(lag2)
    keys["ruff"] = ((7 * impact(lag2), -0.6 * body_roll(ph - 2 * math.pi * 2 / WALK_FRAMES), 0), (0, 0, 0),
                    (flare, 1, flare))
    for side, sign, off in (("L", 1, 0.0), ("R", -1, math.pi)):
        p = ph + off
        # Positive X swings the hand back; on the back-swing the arm also lifts out to
        # the side, so from behind it passes beside the legs, not over them.
        keys[f"arm_{side}"] = ((4 + 21 * math.cos(p), -sign * (6 + 14 * impact(lag1) + 8 * max(0.0, math.cos(p))),
                                sign * 6 * math.sin(p)), (0, 0, 0), None)
        keys[f"fore_{side}"] = ((-10 + 16 * math.cos(p - 0.9) - 12 * impact(lag2), 0, sign * 8 * math.sin(p)),
                                (0, 0, 0), None)
    return keys


def idle(f):
    ph = 2 * math.pi * f / 48
    s = math.sin(ph)
    keys = {
        "root": ((0, 0, 0), (0, 0, 0), None),
        "body": ((4 + 2 * s, 3 * math.sin(ph + 1.2), 9 * math.sin(ph - 0.4)), (0, 0, 0.004 * (1 + s)),
                 (1 - 0.015 * s, 1 + 0.03 * s, 1 - 0.015 * s)),
        "stem": ((5 * math.sin(ph - 1.0), 7 * math.sin(2 * ph), 0), (0, 0, 0), None),
        "ruff": ((2 * math.sin(ph - 1.4), -2 * math.sin(ph - 1.0), 0), (0, 0, 0),
                 (1 + 0.03 * math.sin(ph - 1.6), 1, 1 + 0.03 * math.sin(ph - 1.6))),
    }
    for side, sign in (("L", 1), ("R", -1)):
        keys[f"leg_{side}"] = ((0, 0, 0), (0, 0, 0), None)
        keys[f"foot_{side}"] = ((0, 0, 0), (0, 0, 0), None)
        keys[f"arm_{side}"] = ((8 * math.sin(ph + 0.6 * sign), -sign * 6 * (1 + s), 0), (0, 0, 0), None)
        keys[f"fore_{side}"] = ((-16 + 10 * math.sin(ph - 0.7), 0, sign * 7 * math.sin(2 * ph)), (0, 0, 0), None)
    return keys


act("walk", WALK_FRAMES, walk)
act("idle", 48, idle)

stride = 2 * LEG_LEN * SWING * GAME_SCALE / STANCE_S
print(f"gourdling: walk stride {stride:.3f} game units/s (widest leg angle {math.degrees(math.asin(SWING)):.1f} deg, "
      f"hip drop {LEG_LEN * (1 - math.sqrt(1 - SWING ** 2)):.3f})")


def use_action(name):
    arm.animation_data.use_nla = False
    arm.animation_data.action = bpy.data.actions[name]
    if hasattr(arm.animation_data, "action_slot") and len(bpy.data.actions[name].slots):
        arm.animation_data.action_slot = bpy.data.actions[name].slots[0]


if gab.param("check", 0):
    # Ground clearance and planted-foot slip, measured on the deformed mesh.
    use_action("walk")
    rest_tips = [v.index for v in gourd.data.vertices if v.co.z < 0.004]
    left_tips = [i for i in rest_tips if gourd.data.vertices[i].co.x > 0]
    track = []
    for f in range(WALK_FRAMES + 1):
        bpy.context.scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        me = gourd.evaluated_get(dg).to_mesh()
        zs = [v.co.z for v in me.vertices]
        tip = [me.vertices[i].co.copy() for i in left_tips]
        low = min(range(len(zs)), key=lambda i: zs[i])
        if zs[low] < 0.0:
            print(f"check f{f:02d} lowest vertex {low} at {tuple(round(c, 3) for c in me.vertices[low].co)}, "
                  f"rest {tuple(round(c, 3) for c in gourd.data.vertices[low].co)}")
        track.append((f, min(zs), sum(t.y for t in tip) / len(tip), min(t.z for t in tip)))
        gourd.evaluated_get(dg).to_mesh_clear()
    want = STRIDE / GAME_SCALE / FPS
    for (f, zmin, y, tz), (_, _, y1, _) in zip(track, track[1:]):
        tag = "planted" if f < WALK_FRAMES / 2 else "swing"
        print(f"check f{f:02d} min_z {zmin:+.4f} left toes z {tz:+.4f} y {y:+.4f} "
              f"dy {y1 - y:+.4f} (want {want:+.4f} planted) {tag}")
    arm.animation_data.action = None
    arm.animation_data.use_nla = True
    bpy.context.scene.frame_set(0)


# ── Pose preview (pose=walk:6): bake one frame into the mesh, drop the rig ──

if pose_param:
    action_name, frame_no = pose_param.split(":")
    use_action(action_name)
    bpy.context.scene.frame_set(int(frame_no))
    gab.apply_modifiers(gourd)
    gourd.parent = None
    bpy.data.objects.remove(arm)
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)

print(f"gourdling: {gab.triangles()} triangles, {len(gourd.data.vertices) if not pose_param else '-'} vertices")
