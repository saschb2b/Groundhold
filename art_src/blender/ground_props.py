"""Ground props for Wickhollow: stones, a stump, toadstools, pumpkins, flowers, lily pads.

    godot-agent asset blender . art_src/blender/ground_props.py --to res://models/vegetation/rock_1.glb \
        --seed 1 --param kind=rock --review --no-import

    kind=rock      rock_1..4.glb       seeds 1..4: a boulder, a pair, a standing stone, a staircase of slabs
    kind=stump     stump.glb           seed 1
    kind=mushroom  mushroom_1..2.glb   seeds 1..2: clusters of two to four toadstools
    kind=pumpkin   pumpkin_1..3.glb    seeds 1..3
    kind=flower    flower_<c>_1..2.glb seeds 1..2, --param petal=#e8c04a (buttercups),
                                       #efe6d6 (daisies) or #9a6ac0 (crocus cups)
    kind=lily      lily_pad_1..3.glb   seeds 1..3; --param blossom=1|0 overrides the seed's choice
                                       (a lilac-white water lily with a golden heart, or a bud)

Every prop is one mesh on the painted material (vertex colour gradients, painted patterns
from metre-scaled UVs), the pivot on the ground (on the water surface for lily pads) and
the front facing -Y. Colours come only from palettes/hollow.gpl: a blend that drifts off
the palette is pulled back onto the nearest palette paint, so the gradients stay legal.
The game lights everything with a low orange sun from the camera's side, a +22% top light
on up-facing normals, an ambient lift, filmic tone mapping and a +18% saturation grade, so
the paints here sit well below how they should look (stone most of all: see STONE_RAMP).
"""

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector, noise
from mathutils.bvhtree import BVHTree

import gab

rng = gab.rng
KIND = gab.param("kind", "rock")
SEED = gab.seed

# ── Palette ──

PALETTE_FILE = Path(__file__).resolve().parents[2] / "palettes" / "hollow.gpl"


def _load_palette():
    names = {}
    for line in PALETTE_FILE.read_text().splitlines():
        parts = line.split()
        if len(parts) >= 4 and all(p.isdigit() for p in parts[:3]):
            names[parts[3]] = tuple(int(p) for p in parts[:3])
    return names


PAL = _load_palette()
PAL_RGB = list(PAL.values())


def col(name_or_hex):
    """A palette name, '#rrggbb' or (r, g, b) → linear Vector."""
    if isinstance(name_or_hex, str) and not name_or_hex.startswith("#"):
        return Vector(gab.rgb(PAL[name_or_hex]))
    return Vector(gab.rgb(name_or_hex))


def _to_srgb8(c):
    out = []
    for x in c:
        x = max(0.0, min(1.0, x))
        out.append(255.0 * (12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055))
    return out


def snap(c, tol=23.0, k_lo=0.56, k_hi=1.17):
    """Keeps a blended colour on the palette: the colour if it is already a palette paint
    under some light (k·p), otherwise the nearest such paint. Matches the style check
    (k in [0.5, 1.25], tolerance 26) with a margin for rounding."""
    s = _to_srgb8(c)
    best, best_d = None, 1e9
    for p in PAL_RGB:
        norm = sum(b * b for b in p) or 1
        k = min(k_hi, max(k_lo, sum(a * b for a, b in zip(s, p)) / norm))
        q = [k * b for b in p]
        d = math.dist(s, q)
        if d <= tol:
            return c
        if d < best_d:
            best, best_d = q, d
    return Vector(gab.rgb(tuple(max(0, min(255, round(v))) for v in best)))


def lerp(a, b, t):
    return a + (b - a) * t


def clamp01(x):
    return max(0.0, min(1.0, x))


def smoothstep(e0, e1, x):
    t = clamp01((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def ramp(stops, t):
    """stops: [(t, colour)], sorted by t; colours as names, hex or Vectors."""
    stops = [(s, c if isinstance(c, Vector) else col(c)) for s, c in stops]
    if t <= stops[0][0]:
        return stops[0][1].copy()
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            return lerp(c0, c1, (t - t0) / (t1 - t0))
    return stops[-1][1].copy()


def paint_fn(obj, fn, pattern="plain", facet=0.04, faces=None, ao=0.0, ao_height=0.08):
    """Vertex colours from fn(vertex_index, co, polygon) → linear Vector, with a small
    per-face shade, optional ground darkening and the pattern in alpha (as gab.paint)."""
    mesh = obj.data
    layer = gab._color_layer(mesh)
    alpha = (gab.PATTERNS.index(pattern) + 0.5) / 16
    chosen = set(faces) if faces is not None else None
    for poly in mesh.polygons:
        if chosen is not None and poly.index not in chosen:
            continue
        shade = 1.0 + rng.uniform(-facet, facet)
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index
            co = mesh.vertices[vi].co
            c = fn(vi, co, poly) * shade
            if ao > 0:
                c = c * (1.0 - ao * max(0.0, 1.0 - co.z / ao_height))
            c = snap(Vector([min(1.0, max(0.0, x)) for x in c]))
            layer.data[li].color = (*c, alpha)
    return obj


# ── Geometry helpers ──

def build(name, verts, faces, uvs=None):
    return gab.mesh_object(name, verts, faces, uvs)


def two_sided(verts, faces):
    """The faces again, reversed, on a copy of the vertices: thin leaves and petals seen
    from both sides under the back-face-culled painted material."""
    n = len(verts)
    return list(verts) + list(verts), list(faces) + [tuple(i + n for i in reversed(f)) for f in faces]


def lathe(name, profile, sides, rmod=None, zmod=None, start=0.0):
    """A surface of revolution about Z. profile: [(r, z)] in order; the surface's outside
    is on the right of the walk, so walking up the outside gives outward normals. r = 0
    makes a pole. rmod(angle, i) scales a ring's radius, zmod(angle, i) offsets its z.
    Returns (object, per-vertex profile index, per-vertex angle)."""
    verts, idx, ang, rings = [], [], [], []
    for i, (r, z) in enumerate(profile):
        if r <= 1e-6:
            rings.append([len(verts)])
            verts.append(Vector((0, 0, z)))
            idx.append(i)
            ang.append(0.0)
            continue
        ring = []
        for k in range(sides):
            a = start + 2 * math.pi * k / sides
            rr = r * (rmod(a, i) if rmod else 1.0)
            zz = z + (zmod(a, i) if zmod else 0.0)
            ring.append(len(verts))
            verts.append(Vector((rr * math.cos(a), rr * math.sin(a), zz)))
            idx.append(i)
            ang.append(a)
        rings.append(ring)
    faces = []
    for A, B in zip(rings, rings[1:]):
        if len(A) == 1 and len(B) == 1:
            continue
        if len(A) == 1:
            for k in range(sides):
                faces.append((A[0], B[(k + 1) % sides], B[k]))
        elif len(B) == 1:
            for k in range(sides):
                faces.append((A[k], A[(k + 1) % sides], B[0]))
        else:
            for k in range(sides):
                faces.append((A[k], A[(k + 1) % sides], B[(k + 1) % sides], B[k]))
    return build(name, verts, faces), idx, ang


def tube(name, pts, radii, sides=5, jitter=0.0, twist=0.0, cap_end=False, flat=1.0, face_up=False):
    """A tube along a polyline, rings carried by parallel transport; radius 0 makes a
    pointed tip. `flat` squashes the cross-section (roots hugging the ground); `face_up`
    turns the rings so a flat face, not a vertex ridge, looks at the sky.
    Returns (object, per-vertex t along the path)."""
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
    up = Vector((0, 0, 1)) if abs(tangents[0].z) < 0.9 else Vector((1, 0, 0))
    side = tangents[0].cross(up).normalized()
    lengths = [0.0]
    for i in range(1, n):
        lengths.append(lengths[-1] + (pts[i] - pts[i - 1]).length)
    total = lengths[-1] or 1.0
    start = 0.0
    if face_up:
        b0 = tangents[0].cross(side).normalized()
        start = math.atan2(Vector((0, 0, 1)).dot(b0), Vector((0, 0, 1)).dot(side)) - math.pi / sides
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
            a = start + 2 * math.pi * k / sides + twist * i
            rr = r * (1 + rng.uniform(-jitter, jitter))
            ring.append(len(verts))
            verts.append(pts[i] + side * math.cos(a) * rr + b * math.sin(a) * rr * flat)
            ts.append(lengths[i] / total)
        rings.append(ring)
    faces = []
    for A, B in zip(rings, rings[1:]):
        if len(B) == 1:
            for k in range(sides):
                faces.append((A[k], A[(k + 1) % sides], B[0]))
        else:
            for k in range(sides):
                faces.append((A[k], A[(k + 1) % sides], B[(k + 1) % sides], B[k]))
    if cap_end and len(rings[-1]) > 1:
        faces.append(tuple(rings[-1]))
    obj = build(name, verts, faces)
    # Outward normals regardless of the transport's handedness.
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    flip = 0
    for f in bm.faces:
        c = f.calc_center_median()
        # nearest path point
        j = min(range(n), key=lambda q: (pts[q] - c).length_squared)
        flip += 1 if f.normal.dot(c - pts[j]) < 0 else -1
    if flip > 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.to_mesh(obj.data)
    bm.free()
    return obj, ts


def blade(name, base, direction, normal, length, width, segs=3, fold=0.25, curl=0.0, shape=0.8,
          two=True, tip_round=0.0):
    """A pointed leaf or petal: a spine from base to tip with its edges folded back along
    `normal` (a gutter), curling by `curl` metres against the normal toward the tip.
    shape < 1 puts the widest point toward the tip. Returns (object, per-vertex t, per-vertex
    edge 0 spine..1 rim)."""
    d = Vector(direction).normalized()
    nrm = Vector(normal)
    nrm = (nrm - d * nrm.dot(d)).normalized()
    side = d.cross(nrm).normalized()
    base = Vector(base)
    verts, ts, es, spine, left, right = [], [], [], [], [], []
    for i in range(segs + 1):
        t = i / segs
        p = base + d * length * t - nrm * curl * t * t
        spine.append(len(verts))
        verts.append(p)
        ts.append(t)
        es.append(0.0)
        if 0 < i < segs or (i == segs and tip_round > 0):
            w = width * 0.5 * (math.sin(math.pi * min(t, 0.999) ** shape) ** 0.7 if i < segs else tip_round)
            for lst, sign in ((left, -1), (right, 1)):
                lst.append(len(verts))
                verts.append(p + side * sign * w + nrm * fold * w)
                ts.append(t)
                es.append(1.0)
    faces = []
    m = len(left)
    for i in range(segs):
        a, b = spine[i], spine[i + 1]
        for edge, sign in ((left, -1), (right, 1)):
            e0 = edge[i - 1] if 0 < i <= m else None
            e1 = edge[i] if i < m else None
            if e0 is None and e1 is None:
                continue
            if e0 is None:
                f = (a, e1, b)
            elif e1 is None:
                f = (a, e0, b)
            else:
                f = (a, e0, e1, b)
            faces.append(f)
    front = []
    for f in faces:
        pts = [verts[i] for i in f]
        nn = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        front.append(f if nn.dot(nrm) >= 0 else f[::-1])
    if two:
        verts2, faces2 = two_sided(verts, front)
        return build(name, verts2, faces2), ts + ts, es + es
    return build(name, verts, front), ts, es


def petal(name, base, direction, normal, length, width, shape="diamond", fold=0.3, widest=0.55, lift_tip=0.0,
          two=True):
    """A cheap petal: a diamond (2 triangles a side, folded along its spine) or a
    round-tipped strap (4 a side). Edges rise along `normal` by `fold` × half-width, so the
    petal cups; `lift_tip` moves the tip along the normal; `two=False` keeps only the front
    (petals whose backs face the ground). Returns (object, per-vertex t from base to tip,
    number of front vertices, per-vertex 1 on the edge / 0 on the spine)."""
    d = Vector(direction).normalized()
    nrm = Vector(normal)
    nrm = (nrm - d * nrm.dot(d)).normalized()
    side = d.cross(nrm).normalized()
    base = Vector(base)
    w = width * 0.5
    mid = base + d * length * widest
    tip = base + d * length + nrm * lift_tip * length
    left = mid - side * w + nrm * fold * w
    right = mid + side * w + nrm * fold * w
    if shape == "round":
        tl = base + d * length * 0.95 - side * w * 0.55 + nrm * (lift_tip * length + fold * w * 0.5)
        tr = base + d * length * 0.95 + side * w * 0.55 + nrm * (lift_tip * length + fold * w * 0.5)
        verts = [base, left, right, tl, tr, tip]
        ts = [0.0, widest, widest, 0.95, 0.95, 1.0]
        es = [0.0, 1.0, 1.0, 0.8, 0.8, 0.0]
        faces = [(0, 2, 4), (0, 4, 5), (0, 5, 3), (0, 3, 1)]
    else:
        verts = [base, left, right, tip]
        ts = [0.0, widest, widest, 1.0]
        es = [0.0, 1.0, 1.0, 0.0]
        faces = [(0, 2, 3), (0, 3, 1)]
    front = []
    for f in faces:
        pts = [verts[i] for i in f]
        nn = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        front.append(f if nn.dot(nrm) >= 0 else f[::-1])
    if not two:
        return build(name, verts, front), ts, len(verts), es
    verts2, faces2 = two_sided(verts, front)
    return build(name, verts2, faces2), ts + ts, len(verts), es + es


def recentre(obj):
    """Moves the footprint's centre onto the origin (for clusters)."""
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    c = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, 0))
    for v in obj.data.vertices:
        v.co -= c
    return obj


def ground(obj, floor=0.0):
    """No vertex below the ground plane: undersides of roots and stones flatten onto it."""
    for v in obj.data.vertices:
        if v.co.z < floor:
            v.co.z = floor
    return obj


def vertex_convexity(obj):
    """Per-vertex convexity: + on ridges and bumps, - in creases, relative to edge length."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    out = []
    for v in bm.verts:
        others = [e.other_vert(v).co for e in v.link_edges]
        if not others:
            out.append(0.0)
            continue
        avg = sum(others, Vector()) / len(others)
        el = sum((o - v.co).length for o in others) / len(others) or 1.0
        out.append((v.co - avg).dot(v.normal) / el)
    normals = [v.normal.copy() for v in bm.verts]
    bm.free()
    return out, normals


def fbm(p, octaves=3):
    total, amp, freq = 0.0, 1.0, 1.0
    for _ in range(octaves):
        total += amp * noise.noise(p * freq)
        amp *= 0.5
        freq *= 2.03
    return total


PAINTED = gab.painted()


def finish(objects, name):
    """One mesh named after the asset (object and mesh data both)."""
    print("parts:", ", ".join(f"{o.name} {gab.triangles(o)}" for o in objects if o is not None))
    obj = gab.join(objects, name)
    obj.data.name = name
    return obj


# ══════════════════════════════════════════════════════════════════════════════
# Rocks
# ══════════════════════════════════════════════════════════════════════════════

STONES = {}      # object name → how it was cut (planes, stretch, placement), for painting


def stone(name, size, at=(0, 0), yaw=0.0, chisel=4, lump=0.22, sub=3, target=280, sink=0.35,
          lean=(0.0, 0.0), flat_top=0.0, moss=1.0, moss_bias=0.0, strata=0, base_z=0.0,
          side_planes=False, smooth=28, cracks=0, tone=1.0, steep=None):
    """A lumpy stone: an icosphere pushed by noise, then really cut by a few chisel planes
    (each cut filled with one flat facet, so its edges stay crisp), stretched to `size`,
    sunk into the ground (open below, nobody sees the bottom) and decimated to `target`.

    The first plane is a near-level top unless `side_planes` (pebbles: only steep cuts).
    `strata` cuts that many ledges into it; `base_z` stands it on something; `cracks`
    carves that many fractures when it is painted."""
    w, d, h = size
    off = Vector((rng.uniform(-60, 60), rng.uniform(-60, 60), rng.uniform(-60, 60)))
    planes = []
    for i in range(chisel):
        a = rng.uniform(0, 2 * math.pi)
        if steep is not None:
            e = rng.uniform(*steep)
        elif side_planes:
            e = rng.uniform(0.1, 0.4)
        else:
            e = rng.uniform(0.05, 1.1) if i else rng.uniform(1.0, 1.4)
        n = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
        planes.append((n, rng.uniform(0.55, 0.8)))
    if flat_top > 0:
        planes.append((Vector((rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15), 1)).normalized(),
                       1.0 - flat_top))
    kz = h / (1 + sink)

    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    for v in bm.verts:
        p = v.co.normalized()
        v.co = p * (1 + lump * noise.noise(p * 1.25 + off) + lump * 0.45 * noise.noise(p * 2.7 + off * 1.3) +
                    lump * 0.18 * noise.noise(p * 5.5 + off * 0.7))
    for n, dist in planes:
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=n * dist, plane_no=n,
                               clear_outer=True)
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
    for v in bm.verts:
        p = v.co
        z = (p.z + sink) * kz
        v.co = Vector((p.x * w / 2 + lean[0] * z, p.y * d / 2 + lean[1] * z, z))
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0),
                           plane_no=(0, 0, 1), clear_inner=True)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = gab.link(bpy.data.objects.new(name, mesh))
    tris = gab.triangles(obj)
    if tris > target:
        gab.decimate(obj, target / tris)
    ground(obj)
    levels = cut_strata(obj, strata) if strata else []
    for v in obj.data.vertices:
        v.co.z += base_z
    obj.rotation_euler = (0, 0, yaw)
    obj.location = (at[0], at[1], 0)
    gab.apply_transform(obj)
    STONES[obj.name] = dict(planes=planes, size=size, sink=sink, lean=lean, yaw=yaw, at=at, base_z=base_z,
                            strata=levels, moss=moss, moss_bias=moss_bias, tone=tone, smooth=smooth,
                            cracks=cracks)
    return obj


def facets(obj):
    """Per face: the chisel plane it lies on (-1 for the rounded body)."""
    info = STONES[obj.name]
    w, d, h = info["size"]
    sink, lean, base_z = info["sink"], info["lean"], info["base_z"]
    kz = h / (1 + sink)
    rot = Matrix.Rotation(-info["yaw"], 3, "Z")
    at = Vector((info["at"][0], info["at"][1], 0))

    def to_unit(co):
        p = rot @ (co - at)
        p.z -= base_z
        return Vector(((p.x - lean[0] * p.z) * 2 / w, (p.y - lean[1] * p.z) * 2 / d, p.z / kz - sink))

    mesh = obj.data
    unit = [to_unit(v.co) for v in mesh.vertices]
    out = []
    for poly in mesh.polygons:
        k = -1
        for j, (n, dist) in enumerate(info["planes"]):
            if all(abs(unit[i].dot(n) - dist) < 0.025 for i in poly.vertices):
                k = j
                break
        out.append(k)
    return out


def cut_strata(obj, n):
    """Ledges: `n` level cuts through the stone, the cut line pulled in a few millimetres
    so each layer overhangs the one below. Returns the cut heights, top first."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    top = max(v.co.z for v in bm.verts)
    levels = [top * (0.76 - 0.34 * k + rng.uniform(-0.04, 0.04)) for k in range(n)]
    cx = sum(v.co.x for v in bm.verts) / len(bm.verts)
    cy = sum(v.co.y for v in bm.verts) / len(bm.verts)
    cut = []
    for zk in levels:
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, zk),
                                     plane_no=(0, 0, 1))
        cut += [g for g in res["geom_cut"] if isinstance(g, bmesh.types.BMVert)]
    for v in set(cut):
        out = Vector((v.co.x - cx, v.co.y - cy, 0))
        if out.length > 1e-4:
            v.co -= out.normalized() * 0.005
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    return levels


def cut_cracks(obj, count):
    """Real fractures: three parallel near-vertical cuts 5 mm apart through the faces around
    a point on the stone's flank, the middle line pushed 5 mm into the stone, so each crack
    is a little V groove running down from the shoulder that tapers out at both ends.
    Returns ({vertex: depth 0..1} along the groove's floor, {vertex: depth} on its lit lip)."""
    if count <= 0:
        return {}, {}
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    top = max(v.co.z for v in bm.verts)
    lo = min(v.co.z for v in bm.verts)
    cand = [v.co.copy() for v in bm.verts if -0.15 < v.normal.z < 0.55 and lo + 0.4 * (top - lo) < v.co.z <
            lo + 0.85 * (top - lo)]
    cnorm = [v.normal.copy() for v in bm.verts if -0.15 < v.normal.z < 0.55 and lo + 0.4 * (top - lo) < v.co.z <
             lo + 0.85 * (top - lo)]
    w = 0.005
    found = []
    used = []
    for _ in range(count):
        if not cand:
            break
        for _try in range(12):
            i = rng.randrange(len(cand))
            if all((cand[i] - u).length > 0.1 for u in used):
                break
        p0, n0 = cand[i], cnorm[i]
        used.append(p0)
        vert = Vector((rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), 1.0)).normalized()
        nc = n0.cross(vert)
        if nc.length < 1e-3:
            continue
        nc.normalize()
        r = (top - lo) * rng.uniform(0.36, 0.46)
        for o in (-w, 0.0, w):
            region = [f for f in bm.faces if (f.calc_center_median() - p0).length < r and f.normal.dot(n0) > -0.1]
            if not region:
                continue
            geom = list({v for f in region for v in f.verts}) + list({e for f in region for e in f.edges}) + region
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=p0 + nc * o, plane_no=nc, dist=1e-6)
        found.append((p0, nc, r))
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    bm.normal_update()
    bm.verts.ensure_lookup_table()
    floor, lip = {}, {}
    for p0, nc, r in found:
        for v in bm.verts:
            dd = (v.co - p0).length
            if dd > r * 1.2 or v.co.z < 0.004:
                continue
            s = (v.co - p0).dot(nc)
            depth = smoothstep(r, r * 0.4, dd)
            if depth <= 0:
                continue
            if abs(s) < 2e-4:
                floor[v.index] = max(floor.get(v.index, 0.0), depth)
            elif abs(s - w) < 2e-4:
                lip[v.index] = max(lip.get(v.index, 0.0), depth)
    for vi, depth in floor.items():
        v = bm.verts[vi]
        v.co -= v.normal * 0.0055 * depth
    bm.to_mesh(obj.data)
    bm.free()
    return floor, lip


def moss_cushion(targets, centre, radius, name, segs=12, swell=0.013, rings=(0.45, 0.82, 1.0), stretch=None):
    """A cushion of moss laid over the stones in `targets` from above: a lobed outline around
    `centre` (shrunk wherever it would run off the top), rings of points dropped onto the
    stone and lifted off it, thick in the middle and thinning to nothing at the rim, so it
    hugs the shoulder like a pad instead of sitting on it like a lid. Olive at the crown,
    deep green at the rim, a step darker than the meadow grass."""
    vs, ps = [], []
    for o in targets:
        base = len(vs)
        vs += [v.co.copy() for v in o.data.vertices]
        ps += [[base + i for i in p.vertices] for p in o.data.polygons]
    bvh = BVHTree.FromPolygons(vs, ps)
    ph = [rng.uniform(0, 6.3) for _ in range(3)]
    off = Vector((rng.uniform(-50, 50), rng.uniform(-50, 50), 0))
    c = Vector((centre[0], centre[1], 0))

    def drop(x, y):
        hit = bvh.ray_cast(Vector((x, y, 3.0)), Vector((0, 0, -1)))
        return (hit[0], hit[1]) if hit[0] is not None else (None, None)

    verts, ring_of = [], []
    loc, n = drop(c.x, c.y)
    if loc is None:
        return None
    up = Vector((0, 0, 1))
    verts.append(loc + (n + up).normalized() * swell * (0.9 + 0.2 * noise.noise(loc * 30 + off)))
    ring_of.append(len(rings))
    outline = []
    for k in range(segs):
        a = 2 * math.pi * k / segs
        r = radius * (1 + 0.2 * math.sin(3 * a + ph[0]) + 0.1 * math.sin(5 * a + ph[1]) +
                      0.08 * noise.noise(Vector((math.cos(a), math.sin(a), ph[2]))))
        d = Vector((math.cos(a), math.sin(a), 0))
        if stretch:
            ax = Vector(stretch[0]).normalized()
            along = d.dot(ax)
            d = ax * along * stretch[1] + (d - ax * along) / stretch[1] ** 0.5
        for _ in range(14):
            loc, n = drop(*(c + d * r).xy)
            if loc is not None and n.z > 0.3:
                break
            r *= 0.88
        outline.append((d, r))
    for _ in range(2):      # no notches: each radius eased toward its neighbours'
        rs = [r for _, r in outline]
        outline = [(d, min(rs[k] * 1.1, 0.5 * rs[k] + 0.25 * (rs[k - 1] + rs[(k + 1) % segs])))
                   for k, (d, _) in enumerate(outline)]
    for ri, f in enumerate(rings):
        for d, r in outline:
            loc, n = drop(*(c + d * r * f).xy)
            if loc is None:
                loc, n = drop(c.x, c.y)
            lift = 0.0025 if f >= 1.0 else swell * (1 - f ** 2.6) * (0.8 + 0.4 * clamp01(0.5 + noise.noise(loc * 30 + off)))
            verts.append(loc + (n + up).normalized() * lift)
            ring_of.append(len(rings) - 1 - ri)
    faces = [(0, 1 + k, 1 + (k + 1) % segs) for k in range(segs)]
    for ri in range(len(rings) - 1):
        a0, b0 = 1 + ri * segs, 1 + (ri + 1) * segs
        for k in range(segs):
            faces.append((a0 + k, b0 + k, b0 + (k + 1) % segs, a0 + (k + 1) % segs))
    # Nothing of the stone may poke through the cushion: where a stone vertex stands above
    # the moss surface, lift the cushion's inner points over it (the rim stays tucked down).
    tris = [f if len(f) == 3 else (f[0], f[1], f[2]) for f in faces] + [(f[0], f[2], f[3]) for f in faces if len(f) == 4]
    rim = set(range(1 + (len(rings) - 1) * segs, 1 + len(rings) * segs))
    near = [p for p in vs if (p.xy - c.xy).length < radius * 1.5]
    risen = [0.0] * len(verts)
    for _ in range(3):
        rise = [0.0] * len(verts)
        for p in near:
            for t in tris:
                a, b, q = (verts[i] for i in t)
                det = (b.y - q.y) * (a.x - q.x) + (q.x - b.x) * (a.y - q.y)
                if abs(det) < 1e-12:
                    continue
                l1 = ((b.y - q.y) * (p.x - q.x) + (q.x - b.x) * (p.y - q.y)) / det
                l2 = ((q.y - a.y) * (p.x - q.x) + (a.x - q.x) * (p.y - q.y)) / det
                l3 = 1 - l1 - l2
                if min(l1, l2, l3) < -1e-6:
                    continue
                gap = p.z + 0.0035 - (l1 * a.z + l2 * b.z + l3 * q.z)
                if gap > 0:
                    inner = [i for i in t if i not in rim]
                    w = max(0.6, sum(lv for i, lv in zip(t, (l1, l2, l3)) if i not in rim))
                    for i in inner:
                        rise[i] = max(rise[i], gap / w)
                break
        if not any(rise):
            break
        for i, r in enumerate(rise):
            r = min(r, 0.012 - risen[i])
            if r > 0:
                risen[i] += r
                verts[i] = verts[i] + Vector((0, 0, r))
    shell = build(name, verts, faces)
    bm = bmesh.new()
    bm.from_mesh(shell.data)
    bm.normal_update()
    if sum(f.normal.z for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.to_mesh(shell.data)
    bm.free()
    shell.data.update()
    gab.uv_box(shell, 0.2)
    nz = {}
    for poly in shell.data.polygons:
        for i in poly.vertices:
            nz.setdefault(i, []).append(poly.normal.z)
    nz = {i: sum(v) / len(v) for i, v in nz.items()}

    def moss_color(vi, co, poly):
        c = ramp([(0, col("needle_deep") * 0.72), (1, lerp(col("needle"), col("stem"), 0.5) * 0.82),
                  (2, lerp(col("stem"), col("leaf_deep"), 0.35) * 0.86)], ring_of[vi])
        c = c * (0.88 + 0.16 * noise.noise(co * 30 + off))
        bump = clamp01(0.5 + noise.noise(co * 26 + off))
        c = lerp(c, col("leaf_bright") * 0.72, 0.15 * smoothstep(0.6, 0.9, bump) * min(1, ring_of[vi] / 2))
        return c * lerp(1.0, 0.62, smoothstep(0.55, 0.85, nz.get(vi, 0.0)))

    paint_fn(shell, moss_color, "leaves", 0.02)
    gab.smooth(shell, 70)
    shell.data.materials.append(PAINTED)
    return shell


def moss_spot(obj):
    """Where a stone's moss cushion sits: around the middle of its sky-facing top, nudged
    off centre, sized by the stone's `moss`."""
    info = STONES[obj.name]
    if info["moss"] <= 0:
        return None
    mesh = obj.data
    zs = [v.co.z for v in mesh.vertices]
    z0, z1 = min(zs), max(zs)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.normal_update()
    top = [v.co.copy() for v in bm.verts if v.normal.z > 0.45 and (v.co.z - z0) / (z1 - z0) + info["moss_bias"] > 0.6]
    bm.free()
    if not top:
        return None
    c = sum(top, Vector()) / len(top)
    span = max(max(v.co.x for v in mesh.vertices) - min(v.co.x for v in mesh.vertices),
               max(v.co.y for v in mesh.vertices) - min(v.co.y for v in mesh.vertices))
    a = rng.uniform(0, 2 * math.pi)
    c += Vector((math.cos(a), math.sin(a), 0)) * span * 0.06
    return (c.x, c.y), span * 0.27 * info["moss"]


# The stone ramp (foot → top), in the towers' own stone paints. A step darker than it should
# look: the game's warm sun and top light lift sky-facing stone a long way.
STONE_RAMP = [(0.0, ("stone_shadow", 0.1, 0.0)), (0.3, ("stone_dark", 0.16, 0.04)), (0.6, ("stone_mid", 0.2, 0.08)),
              (0.85, ("stone", 0.23, 0.1)), (1.0, ("stone_warm", 0.31, 0.1))]
# (paint, strength, a touch of needle green). The game's sun is orange and its grade adds
# saturation, so stone painted in pure warm greys comes out beige; STONE_COOL takes some red
# out (in linear light) so lit faces land on a neutral warm grey there.
STONE_COOL = Vector((0.84, 1.0, 0.98))


def paint_stone(obj):
    """Warm grey stone: a dark foot to a lit, warm top, each chisel facet one tone, lit
    ridges and a painted highlight where two facets meet, dark creases, carved cracks with a
    lit lip and a few speckles of pale lichen. Returns the painted stone."""
    info = STONES[obj.name]
    floor, lip = cut_cracks(obj, info["cracks"])
    mesh = obj.data
    plane = facets(obj)
    conv, normals = vertex_convexity(obj)
    zs = [v.co.z for v in mesh.vertices]
    z0 = min(zs)
    z1 = max(zs) or 1.0
    span = max(max(v.co.x for v in mesh.vertices) - min(v.co.x for v in mesh.vertices),
               max(v.co.y for v in mesh.vertices) - min(v.co.y for v in mesh.vertices))
    off = Vector((rng.uniform(-50, 50), rng.uniform(-50, 50), 0))
    tone = info["tone"]
    levels = info["strata"]
    stops = [(t, lerp(col(name), col("needle"), g) * k) for t, (name, k, g) in STONE_RAMP]
    # One tone per chisel facet: lit for those facing up, dim for sides, cool under real undercuts.
    carve = []
    for poly, k in zip(mesh.polygons, plane):
        nz = poly.normal.z
        if k >= 0:
            carve.append(1.06 if nz > 0.55 else 0.82 if nz < -0.3 else 0.9)
        else:
            carve.append(0.8 if nz < -0.5 else 1.0)
    # Where two facets meet (or a facet meets the rounded body on a ridge): a painted bevel.
    planes_at = {}
    for poly, k in zip(mesh.polygons, plane):
        for i in poly.vertices:
            planes_at.setdefault(i, set()).add(k)
    # How sharp the stone is at each vertex: the widest angle between its faces.
    fnorm = {}
    for poly in mesh.polygons:
        for i in poly.vertices:
            fnorm.setdefault(i, []).append(poly.normal.copy())
    sharp = {i: max((a.angle(b, 0.0) for a in ns for b in ns), default=0.0) for i, ns in fnorm.items()}
    bevel = {}
    for i, ks in planes_at.items():
        cut = {k for k in ks if k >= 0}
        edge = smoothstep(math.radians(22), math.radians(45), sharp.get(i, 0.0))
        if conv[i] <= 0.0 or edge <= 0:
            continue
        if len(cut) >= 2:
            bevel[i] = 0.5 * edge
        elif cut and -1 in ks:
            bevel[i] = 0.35 * edge
    # Lichen: a few pale speckles on the sunny flanks, never rust.
    lichens = []
    if span > 0.12:
        spots = [i for i, (v, n) in enumerate(zip(mesh.vertices, normals))
                 if -0.3 < n.z < 0.7 and 0.25 < (v.co.z - z0) / max(1e-4, z1 - z0) < 0.85]
        for _ in range(min(len(spots), rng.randint(2, 3))):
            vi = rng.choice(spots)
            lichens.append((mesh.vertices[vi].co.copy(), span * rng.uniform(0.04, 0.06),
                            rng.choice(("stone_pale", "leaf_tip"))))

    def on_level(z):
        return any(abs(z - zk) < 1e-3 for zk in levels)

    def stone_color(vi, co, poly):
        t = clamp01((co.z - z0) / max(1e-4, z1 - z0))
        nz = normals[vi].z
        c = ramp(stops, t) * tone
        cv = conv[vi]
        c = lerp(c, col("stone_light") * 0.26 * tone, 0.4 * smoothstep(0.1, 0.3, cv) * smoothstep(0.35, 0.8, t))
        c = lerp(c, col("stone_dark") * 0.12, 0.4 * smoothstep(-0.03, -0.15, cv))
        for p, r, name in lichens:
            k = smoothstep(r, r * 0.4, (co - p).length) * smoothstep(0.1, 0.3, noise.noise(co * 45 + off))
            c = lerp(c, col(name) * 0.2, 0.3 * k)
        k = carve[poly.index]
        c = c * k
        if k < 0.85:         # real undercuts and overhang bellies: a cool shadow
            c = lerp(c, col("iron_dark") * 0.3, 0.5 * smoothstep(0.86, 0.78, k))
        if vi in bevel:
            c = lerp(c, col("stone_light") * 0.27 * tone, bevel[vi] * smoothstep(0.0, 0.5, nz) * smoothstep(0.3, 0.7, t))
        # The game's sun and top light double what faces the sky: paint those faces down.
        c = c * lerp(1.0, 0.9, smoothstep(0.35, 0.95, nz))
        c = c * (0.93 + 0.14 * clamp01(0.5 + fbm(co * 14 + off, 2)))
        if levels:
            cz = poly.center.z
            band = sum(1 for zk in levels if zk > cz)
            c = c * (1.0 if band % 2 == 0 else 0.88)
            if on_level(co.z):
                c = c * (0.6 if cz < co.z else 1.1)     # shadow under each ledge, lit lip above
        if vi in floor:
            c = lerp(c, col("stone_shadow") * 0.1, floor[vi])
        elif vi in lip:
            c = c * (1 + 0.14 * lip[vi])
        return c * STONE_COOL

    gab.uv_box(obj, 0.35)
    paint_fn(obj, stone_color, "plain", 0.01, ao=0.3, ao_height=0.05)
    gab.smooth(obj, info["smooth"])
    obj.data.materials.append(PAINTED)
    return obj


def cull_covered(lower, upper):
    """Deletes the faces of `lower` hidden under `upper` (a slab resting on it)."""
    bvh = BVHTree.FromPolygons([v.co.copy() for v in upper.data.vertices], [p.vertices[:] for p in upper.data.polygons])
    bm = bmesh.new()
    bm.from_mesh(lower.data)
    bm.normal_update()
    dead = [f for f in bm.faces if f.normal.z > 0.2 and all(
        bvh.ray_cast(v.co + Vector((0, 0, 0.001)), Vector((0, 0, 1)), 0.3)[0] is not None for v in f.verts)]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(lower.data)
    bm.free()


def pebble(at, size, name="pebble"):
    """A rounded pebble: one steep cut, smooth, a shade darker than the stone beside it."""
    return stone(name, (size, size * rng.uniform(0.7, 0.95), size * rng.uniform(0.45, 0.6)), at=at,
                 yaw=rng.uniform(0, 6.3), chisel=1, side_planes=True, lump=0.25, sub=2, target=36, sink=0.45,
                 moss=0.0, smooth=60, tone=rng.uniform(0.62, 0.82))


def pebbles_by(main, count, size):
    """Two or three pebbles tucked against the main stone's foot, in one cluster."""
    foot = [v.co.copy() for v in main.data.vertices if v.co.z < 0.03]
    c = sum(foot, Vector()) / len(foot)
    a0 = rng.uniform(0, 2 * math.pi)
    out = []
    for i in range(count):
        a = a0 + (i - (count - 1) / 2) * rng.uniform(0.45, 0.65)
        d = Vector((math.cos(a), math.sin(a), 0))
        near = [p for p in foot if (p - c).length > 1e-4 and (p - c).normalized().dot(d) > 0.85] or foot
        reach = max((p - c).dot(d) for p in near)
        s = size * rng.uniform(0.75, 1.1) * (1.0 if i != (count - 1) // 2 else 1.2)
        p = c + d * (reach + s * rng.uniform(0.0, 0.3))
        out.append(pebble((p.x, p.y), s))
    return out


def make_rocks():
    kind = (SEED - 1) % 4
    stones = []
    crevices = []
    step = Vector((1, 0, 0))
    if kind == 0:   # one big rounded boulder, a mossy crown
        main = stone("boulder", (0.42, 0.33, 0.25), chisel=4, lump=0.2, target=200, cracks=2)
        stones += [main] + pebbles_by(main, 3, 0.09)
    elif kind == 1:  # a pair: a mid stone with a smaller one leaning on its flank
        main = stone("big", (0.32, 0.27, 0.23), at=(-0.06, 0.03), chisel=5, lump=0.22, target=165,
                     lean=(-0.12, 0.05), cracks=1)
        stones += [main, stone("small", (0.19, 0.16, 0.13), at=(0.12, -0.07), yaw=0.8, chisel=3, lump=0.25,
                               target=72, lean=(0.15, -0.1), moss=0.8)]
        stones += pebbles_by(main, 2, 0.08)
    elif kind == 2:  # a leaning standing stone
        main = stone("standing", (0.22, 0.19, 0.38), chisel=5, lump=0.16, target=175, sink=0.2,
                     lean=(0.12, 0.06), moss_bias=0.2, moss=0.95, cracks=2)
        stones += [main, stone("foot", (0.15, 0.13, 0.09), at=(-0.12, -0.08), yaw=0.4, chisel=3, target=60)]
        stones += pebbles_by(main, 2, 0.08)
    else:            # layered rock: three broken flagstones stepping up one way, a little staircase
        y0 = rng.uniform(0, 2 * math.pi)
        step = Vector((math.cos(y0 + 0.6), math.sin(y0 + 0.6), 0))
        main = stone("slab", (0.45, 0.34, 0.1), yaw=y0, chisel=5, steep=(0.0, 0.3), lump=0.12, target=115,
                     sink=0.5, flat_top=0.35, moss=0.0, strata=1, cracks=1)
        top0 = max(v.co.z for v in main.data.vertices)
        mp = step * 0.095
        mid = stone("slab2", (0.3, 0.24, 0.085), at=(mp.x, mp.y), yaw=y0 + rng.uniform(-0.15, 0.15), chisel=4,
                    steep=(0.0, 0.3), lump=0.12, target=85, sink=0.5, flat_top=0.3, base_z=top0 - 0.014, moss=0.0,
                    cracks=1)
        top1 = max(v.co.z for v in mid.data.vertices)
        cp = step * 0.165
        cap = stone("slab3", (0.14, 0.11, 0.05), at=(cp.x, cp.y), yaw=y0 + rng.uniform(-0.25, 0.25), chisel=1,
                    side_planes=True, lump=0.25, sub=2, target=48, sink=0.45, base_z=top1 - 0.012, moss=0.0,
                    smooth=60, tone=0.9)
        cull_covered(main, mid)
        cull_covered(mid, cap)
        crevices = [(main, mid)]
        stones += [main, mid, cap] + pebbles_by(main, 2, 0.075)
    parts = []
    spots = [(s, moss_spot(s)) for s in stones]
    for s in stones:
        parts.append(paint_stone(s))
    for s, spot in spots:
        if spot:
            small = spot[1] < 0.05
            parts.append(moss_cushion([s], spot[0], spot[1], s.name + "_moss", segs=9 if small else 12,
                                      rings=(0.55, 1.0) if small else (0.45, 0.82, 1.0)))
    for lower, upper in crevices:
        # moss tucked into the step: along the foot of the riser, on the tread in front of it
        foot = [v.co.copy() for v in upper.data.vertices if v.co.z < min(w.co.z for w in upper.data.vertices) + 0.01]
        c = sum(foot, Vector()) / len(foot)
        front = min(foot, key=lambda p: (p - c).dot(step))
        side = Vector((-step.y, step.x, 0))
        p = front + side * rng.uniform(-0.03, 0.03) - step * 0.008
        parts.append(moss_cushion([lower], (p.x, p.y), 0.048, f"crevice_{upper.name}", segs=12, swell=0.012,
                                  rings=(0.5, 1.0), stretch=(side, 2.1)))
    parts = [p for p in parts if p is not None]
    obj = finish(parts, f"rock_{SEED}")
    recentre(obj)
    return obj

# ══════════════════════════════════════════════════════════════════════════════
# Stump
# ══════════════════════════════════════════════════════════════════════════════

def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def drop_buried(obj, floor=0.001):
    """Deletes faces lying flat on the ground (nobody sees them)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    dead = [f for f in bm.faces if all(v.co.z < floor for v in f.verts)]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def drape(obj, faces, name, lift=0.005, drop=(0.006, 0.02), out=0.004, trim=None):
    """Moss draped over `faces` of a trunk: their copy lifted off the bark, the lower edge
    rounded and hanging in lobes over the bark below. `trim(centre) → True` cuts away parts
    of the (once split) side faces, so the lower edge can hang in tongues finer than the
    trunk's own rings. Deep green at the edge, brighter on the rim where it catches the sky."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    sb = bmesh.new()
    vmap = {}
    off = Vector((rng.uniform(-50, 50), rng.uniform(-50, 50), 0))
    for fi in faces:
        f = bm.faces[fi]
        for v in f.verts:
            if v.index not in vmap:
                vmap[v.index] = sb.verts.new(v.co + v.normal * (lift + 0.004 * clamp01(0.5 + noise.noise(v.co * 40 + off))))
        sb.faces.new([vmap[v.index] for v in f.verts])
    bm.verts.ensure_lookup_table()
    normals = {vmap[i]: bm.verts[i].normal.copy() for i in vmap}
    bm.free()
    if trim:
        sb.normal_update()
        sides = [f for f in sb.faces if abs(f.normal.z) < 0.5]
        bmesh.ops.subdivide_edges(sb, edges=list({e for f in sides for e in f.edges}), cuts=1, use_grid_fill=True)
        bmesh.ops.delete(sb, geom=[f for f in sb.faces if trim(f.calc_center_median())], context="FACES")
        bmesh.ops.triangulate(sb, faces=[f for f in sb.faces if len(f.verts) > 4])
    edge = [v for v in sb.verts if any(e.is_boundary for e in v.link_edges)]
    for _ in range(2):
        moved = {}
        for v in edge:
            nb = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(nb) == 2:
                moved[v] = (v.co * 2 + nb[0].co + nb[1].co) / 4
        for v, c in moved.items():
            v.co = c
    top_z = max(v.co.z for v in sb.verts)
    phase = rng.uniform(0, 6.3)
    for v in edge:
        n = normals.get(v) or Vector((v.co.x, v.co.y, 0)).normalized()
        lobe = max(0.0, math.sin(math.atan2(v.co.y, v.co.x) * 9 + phase))
        hang = lerp(drop[0], drop[1], lobe) if v.co.z < top_z - 0.03 else rng.uniform(0.0, 0.006)
        flat = Vector((n.x, n.y, 0))
        v.co += (flat.normalized() * out if flat.length > 1e-4 else Vector()) - Vector((0, 0, hang))
    depth = {v: 0 for v in edge}
    frontier = list(edge)
    while frontier:
        nxt = []
        for v in frontier:
            for e in v.link_edges:
                o = e.other_vert(v)
                if o not in depth:
                    depth[o] = depth[v] + 1
                    nxt.append(o)
        frontier = nxt
    dep = [depth.get(v, 2) for v in sb.verts]
    shell_mesh = bpy.data.meshes.new(name)
    sb.to_mesh(shell_mesh)
    sb.free()
    shell = gab.link(bpy.data.objects.new(name, shell_mesh))
    gab.uv_cylinder(shell, 0.3)

    def moss_color(vi, co, poly):
        c = ramp([(0, col("needle_deep") * 0.72), (1, lerp(col("needle"), col("stem"), 0.5) * 0.82),
                  (2, lerp(col("stem"), col("leaf_deep"), 0.35) * 0.86)], dep[vi])
        c = lerp(c, col("leaf_bright") * 0.72, 0.15 * smoothstep(top_z - 0.03, top_z, co.z))
        return c * 0.78 * (0.9 + 0.14 * noise.noise(co * 25 + off))

    paint_fn(shell, moss_color, "leaves", 0.02)
    gab.smooth(shell, 70)
    shell.data.materials.append(PAINTED)
    return shell


def make_stump():
    SIDES = 18
    R, H = 0.115, 0.2
    slant_dir = rng.uniform(0, 2 * math.pi)
    slant = 0.022
    n_roots = rng.choice((6, 7))
    a0 = rng.uniform(0, 2 * math.pi)
    root_angles = [a0 + 2 * math.pi * i / n_roots + rng.uniform(-0.28, 0.28) for i in range(n_roots)]
    first = rng.randrange(n_roots)
    long_ids = {first, (first + n_roots // 2 + rng.choice((0, 1))) % n_roots}
    root_len = [rng.uniform(0.11, 0.13) if i in long_ids else rng.uniform(0.05, 0.08) for i in range(n_roots)]
    lump = [rng.uniform(-0.05, 0.05) for _ in range(SIDES)]

    def root_bump(a):
        return max(math.exp(-(wrap(a - ra) / 0.3) ** 2) * (0.5 + 0.5 * (ln - 0.05) / 0.11)
                   for ra, ln in zip(root_angles, root_len))

    def top_z(x, y):
        return H + slant * (x * math.cos(slant_dir) + y * math.sin(slant_dir)) / R

    # Trunk rings bottom to top, then the bark lip, then the cut face inward.
    trunk_z = [0.0, 0.045, 0.12]
    verts, rings = [], []
    for i, z in enumerate(trunk_z + [None]):
        ring = []
        for k in range(SIDES):
            a = 2 * math.pi * k / SIDES
            ridge = 0.05 if k % 2 == 0 else -0.05
            zz = z if z is not None else H
            flare = math.exp(-zz / 0.05)
            r = R * (1 + lump[k] + ridge) * (1 + flare * (0.15 + 0.85 * root_bump(a)))
            x, y = r * math.cos(a), r * math.sin(a)
            if z is None:
                zz = top_z(x, y)
            ring.append(len(verts))
            verts.append(Vector((x, y, zz)))
        rings.append(ring)
    top = rings[-1]
    lip = []
    for k in range(SIDES):
        p = verts[top[k]]
        lip.append(len(verts))
        verts.append(Vector((p.x * 0.93, p.y * 0.93, p.z + 0.007)))
    inner = []
    for k in range(SIDES):
        p = verts[top[k]]
        q = Vector((p.x * 0.84, p.y * 0.84, 0))
        q.z = top_z(q.x, q.y) - 0.003
        inner.append(len(verts))
        verts.append(q)
    rings += [lip, inner]
    # The cut face: a thin cambium ring, pale sapwood, heartwood, around an off-centre pith.
    ecc = Vector((math.cos(slant_dir + 2.0), math.sin(slant_dir + 2.0), 0)) * 0.016
    fracs = [0.77, 0.52, 0.27]
    face_rings = []
    for f in fracs:
        ring = []
        for k in range(SIDES):
            p = verts[inner[k]]
            q = Vector((p.x, p.y, 0)) * (f / 0.84) * (1 + rng.uniform(-0.03, 0.03)) + ecc * (1 - f / 0.84)
            q.z = top_z(q.x, q.y) - 0.003 + rng.uniform(-0.0015, 0.0015)
            ring.append(len(verts))
            verts.append(q)
        face_rings.append(ring)
        rings.append(ring)
    pith = len(verts)
    verts.append(Vector((ecc.x, ecc.y, top_z(ecc.x, ecc.y) - 0.005)))
    # Radial checks: one long crack to the pith, two short ones in from the bark.
    ks = rng.sample(range(SIDES), 3)
    crack_v = {inner[ks[0]]} | {r[ks[0]] for r in face_rings}
    for k in ks[1:]:
        crack_v |= {inner[k], face_rings[0][k]}
    for vi in crack_v:
        verts[vi].z -= 0.006
    faces = []
    for A, B in zip(rings, rings[1:]):
        for k in range(SIDES):
            faces.append((A[k], A[(k + 1) % SIDES], B[(k + 1) % SIDES], B[k]))
    for k in range(SIDES):
        faces.append((face_rings[-1][k], face_rings[-1][(k + 1) % SIDES], pith))
    trunk = build("trunk", verts, faces)
    n_side = len(trunk_z) * SIDES
    n_lip = 2 * SIDES
    side_faces = list(range(n_side))
    lip_faces = list(range(n_side, n_side + n_lip))
    cut_faces = list(range(n_side + n_lip, len(faces)))
    ring_of = {}
    for ri, ring in enumerate([inner] + face_rings):
        for v in ring:
            ring_of[v] = ri
    ring_of[pith] = len(face_rings) + 1
    off = Vector((rng.uniform(-40, 40), rng.uniform(-40, 40), 0))

    # Moss over the rim on one side, its lower edge in lobes.
    moss_dir = slant_dir + math.pi + rng.uniform(-0.5, 0.5)

    tongue_ph = (rng.uniform(0, 6.3), rng.uniform(0, 6.3))

    def moss_depth(a):      # how far the moss hangs below the rim: two or three uneven tongues
        da = wrap(a - moss_dir)
        t = max(0.0, 0.6 * math.sin(da * 5.5 + tongue_ph[0]) + 0.5 * math.sin(da * 9 + tongue_ph[1]))
        return (0.022 + 0.07 * min(1.0, t) ** 1.3) * (1 - 0.7 * smoothstep(0.55, 0.95, abs(da)))

    def moss_edge(da):      # where the moss's damp stain on the bark below it starts
        return H - moss_depth(moss_dir + da) - 0.012

    moss_faces = []
    for fi in side_faces + lip_faces:
        c = trunk.data.polygons[fi].center
        da = abs(wrap(math.atan2(c.y, c.x) - moss_dir))
        if fi in side_faces and da < 0.95 and c.z > 0.09:
            moss_faces.append(fi)
        elif fi in lip_faces and da < 0.75:
            moss_faces.append(fi)

    gab.uv_cylinder(trunk)

    def bark_ramp(z):
        t = clamp01(z / (H + slant))
        return ramp([(0.0, col("leg") * 0.9), (0.3, "hide_dark"), (0.65, "bark"), (0.9, "hide"), (1.0, "wood")], t)

    def moss_stain(co):
        da = wrap(math.atan2(co.y, co.x) - moss_dir)
        e = moss_edge(da)
        return smoothstep(e - 0.03, e, co.z) * (1 - smoothstep(0.8, 1.1, abs(da)))

    def bark_color(vi, co, poly):
        k = vi % SIDES if vi < pith else 0
        groove = 1.0 if (vi < SIDES * len(trunk_z) and k % 2 == 1) else 0.0
        t = clamp01(co.z / (H + slant))
        c = bark_ramp(co.z)
        c = lerp(c, col("hide") * 1.1, 0.35 * (1 - groove) * smoothstep(0.1, 0.6, t))
        c = lerp(c, col("leg") * 0.8, 0.5 * groove)
        return lerp(c, col("leaf_deep") * 0.7, 0.55 * moss_stain(co))

    def lip_color(vi, co, poly):
        return col("wood") * 0.95 if vi in lip else col("hide")

    def cut_color(vi, co, poly):
        if vi in crack_v:
            return col("wood_dark") * 0.62
        band = min(ring_of.get(v, 0) for v in poly.vertices)
        r = ring_of.get(vi, 0)
        if band == 0:            # cambium: a thin dark ring inside the bark
            return col("hide_dark") * 1.05
        if band == len(face_rings):   # heart: darkening into the pith
            return lerp(col("wood_light") * 0.9, col("wood_dark") * 0.9, 1.0 if vi == pith else 0.0)
        base = col("wood_light") if band == 1 else col("wood")
        n = 1 + 0.06 * noise.noise(co * 60 + off)
        return base * (1.06 if r == band else 0.84) * n   # each ring pale outside, darker at its inner line

    paint_fn(trunk, bark_color, "bark", 0.04, side_faces, ao=0.2, ao_height=0.06)
    paint_fn(trunk, lip_color, "bark", 0.03, lip_faces)
    paint_fn(trunk, cut_color, "plain", 0.0, cut_faces)
    gab.smooth(trunk, 55)
    for fi in cut_faces:
        trunk.data.polygons[fi].use_smooth = False
    trunk.data.materials.append(PAINTED)
    def moss_trim(c):        # keep the moss over the rim, hanging down the bark in a few tongues
        return c.z < H - moss_depth(math.atan2(c.y, c.x))

    parts = [trunk, drape(trunk, moss_faces, "moss", trim=moss_trim)]

    # Roots: two long ones and a few stubs, growing out of the flare and diving into the soil.
    for i, (a, ln) in enumerate(zip(root_angles, root_len)):
        side = Vector((-math.sin(a), math.cos(a), 0))
        out = Vector((math.cos(a), math.sin(a), 0))
        wig = rng.uniform(-0.03, 0.03) * ln / 0.15
        start = out * 0.06 + Vector((0, 0, 0.09))
        if ln > 0.1:
            pts = [start,
                   out * (0.1 + ln * 0.3) + side * wig * 0.3 + Vector((0, 0, 0.042)),
                   out * (0.1 + ln * 0.65) + side * wig + Vector((0, 0, 0.018)),
                   out * (0.1 + ln) + side * wig * 1.6 + Vector((0, 0, -0.02))]
            radii = [0.05, 0.042, 0.032 + 0.006, 0.024]       # a knuckle halfway, then it dives
        else:
            pts = [start,
                   out * (0.1 + ln * 0.45) + side * wig + Vector((0, 0, 0.036)),
                   out * (0.1 + ln) + side * wig * 1.5 + Vector((0, 0, -0.02))]
            radii = [0.05, 0.04 + 0.004, 0.028]
        root, ts = tube(f"root_{i}", pts, radii, sides=6, jitter=0.05, flat=0.8, face_up=True)
        ground(root)
        drop_buried(root)
        gab.uv_cylinder(root)
        paint_fn(root, lambda vi, co, p: bark_ramp(co.z) * (0.9 + 0.1 * smoothstep(0.0, 0.03, co.z)), "bark", 0.03,
                 ao=0.2, ao_height=0.04)
        gab.smooth(root, 70)
        root.data.materials.append(PAINTED)
        parts.append(root)

    # Woody shelf fungi on the shady side: two brackets and a small one stacked under the first.
    shelf_dir = moss_dir + math.pi + rng.uniform(-0.4, 0.4)
    for j, (z, s, da) in enumerate(((0.128, 0.05, 0.0), (0.092, 0.036, 0.6), (0.096, 0.03, -0.12))):
        a = shelf_dir + da
        out = Vector((math.cos(a), math.sin(a), 0))
        side = Vector((-math.sin(a), math.cos(a), 0))
        base = out * (R * 0.98) + Vector((0, 0, z))
        rim = []
        sv = [base + Vector((0, 0, 0.008))]
        for q in range(6):
            ang = math.pi * q / 5
            reach = math.sin(ang)
            p = base + side * math.cos(ang) * s + out * reach * s * 1.05 + Vector((0, 0, 0.012 * reach))
            rim.append(len(sv))
            sv.append(p)
        sv.append(base + out * s * 0.4 + Vector((0, 0, 0.022)))    # top dome
        top_c = len(sv) - 1
        sv.append(base + out * s * 0.3 + Vector((0, 0, -0.014)))   # thick underside
        bot_c = len(sv) - 1
        sf = []
        for q in range(5):
            sf.append((rim[q], rim[q + 1], top_c))
            sf.append((rim[q + 1], rim[q], bot_c))
        sf.append((rim[0], 0, top_c))
        sf.append((0, rim[-1], top_c))
        shelf = build(f"shelf_{j}", sv, sf)
        bm = bmesh.new()
        bm.from_mesh(shelf.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(shelf.data)
        bm.free()
        gab.uv_box(shelf)

        def shelf_color(vi, co, poly, top_c=top_c, rim=rim):
            if poly.normal.z <= 0:
                return col("hide") * 0.8             # the gills, in the bracket's shadow
            if vi in rim:
                return col("stalk") * 0.52           # a pale growing edge
            return lerp(col("wood_light"), col("stalk"), 0.25) * 0.6

        paint_fn(shelf, shelf_color, "plain", 0.03)
        gab.smooth(shelf, 80)
        shelf.data.materials.append(PAINTED)
        parts.append(shelf)

    return finish(parts, "stump")


# ══════════════════════════════════════════════════════════════════════════════
# Toadstools
# ══════════════════════════════════════════════════════════════════════════════

def toadstool(at, height, cap_r, tilt=(0.0, 0.0), open_=0.5, sides=12, spots=6, skirt=False):
    """A fly agaric: a pale stalk with a bulb, a red cap (dome to umbrella by `open_`)
    with cream gills underneath and raised white warts."""
    stalk_r = cap_r * 0.24
    h = height
    sp = [(stalk_r * 1.5, 0.0), (stalk_r * 1.3, h * 0.16), (stalk_r * 0.95, h * 0.6), (stalk_r * 0.86, h)]
    stalk_sides = 6 if sides >= 10 else 5 if sides >= 9 else 4
    stalk, sidx, _ = lathe("stalk", sp, stalk_sides, rmod=lambda a, i: 1 + 0.06 * math.sin(3 * a + i))
    gab.uv_cylinder(stalk)
    paint_fn(stalk, lambda vi, co, p: ramp([(0.0, col("stalk") * 0.6), (0.4, col("stalk") * 0.85),
                                            (1.0, "stalk")], sidx[vi] / 3), "plain", 0.03)
    gab.smooth(stalk, 80)
    stalk.data.materials.append(PAINTED)
    parts = [stalk]
    if skirt:
        zr = h * 0.78
        kp = [(stalk_r * 0.95, zr + 0.004), (stalk_r * 1.9, zr - 0.012)]
        ring, _, _ = lathe("skirt", kp, stalk_sides)
        # outer surface faces outward+down; add the inside so it reads from above too
        mesh = ring.data
        vs = [v.co.copy() for v in mesh.vertices]
        fs = [tuple(p.vertices) for p in mesh.polygons]
        vs2, fs2 = two_sided(vs, fs)
        bpy.data.objects.remove(ring)
        ring = build("skirt", vs2, fs2)
        gab.uv_cylinder(ring)
        paint_fn(ring, lambda vi, co, p: col("stalk") * (0.95 if p.normal.z > 0 else 0.7), "plain", 0.03)
        gab.smooth(ring, 80)
        ring.data.materials.append(PAINTED)
        parts.append(ring)

    # Cap profile: from the gills by the stalk out to the rim, round it and up to the crown.
    R = cap_r
    dome = lerp(0.85, 0.38, open_) * R          # crown height above the rim
    drop = lerp(0.35, 0.08, open_) * R          # how far the rim curls down
    base = h - 0.002
    cp = [(stalk_r * 0.85, base + 0.002),
          (R * 0.92, base - drop),                                 # gills meet the rim
          (R * 1.0, base - drop + 0.006),                          # rim lip
          (R * 0.9, base - drop * 0.2 + dome * 0.45),              # shoulder
          (R * 0.5, base + dome * 0.92),
          (0, base + dome)]
    wob = [rng.uniform(-0.05, 0.05) for _ in range(sides)]
    cap, cidx, cang = lathe("cap", cp, sides, rmod=lambda a, i: 1 + wob[int(round(a / (2 * math.pi) * sides)) % sides]
                            * (1 if i >= 2 else 0.3))
    n_cp = len(cp)

    def cap_color(vi, co, poly):
        i = cidx[vi]
        if i <= 1:   # gills: cream, darker toward the stalk
            return ramp([(0, col("stalk") * 0.5), (1, col("stalk") * 0.8)], i)
        t = (i - 2) / (n_cp - 3)
        return ramp([(0.0, col("cap") * 0.45), (0.3, col("cap") * 0.75), (0.65, col("cap") * 0.98),
                     (1.0, col("cap") * 1.1)], t)

    gab.uv_box(cap)
    paint_fn(cap, cap_color, "plain", 0.03)
    gab.smooth(cap, 70)
    cap.data.materials.append(PAINTED)
    parts.append(cap)

    # Warts: low white domes on the cap's upper slope, each standing on the cap's own normal,
    # so they read as raised spots and never break the cap's silhouette.
    placed = []
    seg_pts = [Vector((r, 0, z)) for r, z in cp[2:]]
    tries = 0
    while len(placed) < spots and tries < 200:
        tries += 1
        u = rng.uniform(0.38, 0.85)
        a = rng.uniform(0, 2 * math.pi)
        f = u * (len(seg_pts) - 1)
        j = min(int(f), len(seg_pts) - 2)
        q = lerp(seg_pts[j], seg_pts[j + 1], f - j)
        dr, dz = seg_pts[j + 1].x - seg_pts[j].x, seg_pts[j + 1].z - seg_pts[j].z
        nrm = Vector((dz * math.cos(a), dz * math.sin(a), -dr)).normalized()
        pos = Vector((q.x * math.cos(a), q.x * math.sin(a), q.z))
        size = R * rng.uniform(0.09, 0.14)
        if any((pos - pp).length < (size + ss) * 1.25 for pp, ss, _ in placed):
            continue
        placed.append((pos, size, nrm))
    for si, (pos, size, nrm) in enumerate(placed):
        t1 = nrm.cross(Vector((0, 0, 1)))
        t1 = Vector((1, 0, 0)) if t1.length < 1e-3 else t1.normalized()
        t2 = nrm.cross(t1).normalized()
        k = 6
        sv = [pos + nrm * size * 0.28]
        spin = rng.uniform(0, 2 * math.pi)
        for q in range(k):
            ang = spin + 2 * math.pi * q / k + rng.uniform(-0.2, 0.2)
            rr = size * rng.uniform(0.85, 1.15)
            sv.append(pos + (t1 * math.cos(ang) + t2 * math.sin(ang)) * rr - nrm * size * 0.1)
        sf = [(0, 1 + q, 1 + (q + 1) % k) for q in range(k)]
        wart = build(f"wart_{si}", sv, sf)
        bm = bmesh.new()
        bm.from_mesh(wart.data)
        bm.normal_update()
        bm.faces.ensure_lookup_table()
        if bm.faces[0].normal.dot(nrm) < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
            bm.to_mesh(wart.data)
        bm.free()
        gab.uv_box(wart)
        paint_fn(wart, lambda vi, co, p: col("petal_white") * 0.9 if vi == 0 else col("stalk") * 0.85, "plain", 0.04)
        gab.smooth(wart, 80)
        wart.data.materials.append(PAINTED)
        parts.append(wart)

    obj = gab.join(parts, "toadstool")
    obj.rotation_euler = (math.radians(tilt[0]), math.radians(tilt[1]), rng.uniform(0, 6.28))
    obj.location = (at[0], at[1], 0)
    gab.apply_transform(obj)
    return obj


def make_mushrooms():
    kind = (SEED - 1) % 2
    parts = []
    if kind == 0:
        parts.append(toadstool((-0.02, 0.02), 0.15, 0.08, tilt=(-4, 6), open_=0.55, sides=11, spots=8,
                               skirt=True))
        parts.append(toadstool((0.08, -0.045), 0.095, 0.054, tilt=(10, 14), open_=0.3, sides=9, spots=5))
        parts.append(toadstool((-0.075, -0.065), 0.064, 0.03, tilt=(12, -16), open_=0.1, sides=8, spots=1))
    else:
        parts.append(toadstool((0.0, 0.03), 0.125, 0.07, tilt=(-6, -5), open_=0.8, sides=10, spots=6))
        parts.append(toadstool((-0.08, -0.03), 0.09, 0.052, tilt=(8, -14), open_=0.45, sides=9, spots=4))
        parts.append(toadstool((0.075, -0.05), 0.07, 0.035, tilt=(14, 12), open_=0.2, sides=8, spots=2))
        parts.append(toadstool((0.015, -0.1), 0.046, 0.021, tilt=(20, 0), open_=0.1, sides=7, spots=0))
    obj = finish(parts, f"mushroom_{SEED}")
    ground(obj)
    recentre(obj)
    return obj


# ══════════════════════════════════════════════════════════════════════════════
# Pumpkins
# ══════════════════════════════════════════════════════════════════════════════

def make_pumpkin():
    kind = (SEED - 1) % 3
    LOBES = [8, 9, 10][kind]
    SPL = 4
    SEG = LOBES * SPL
    RINGS = 7
    R = [0.135, 0.115, 0.145][kind]
    H = [0.095, 0.105, 0.075][kind]           # half height
    skin_hue = ["pumpkin", "pumpkin", "leaf_amber"][kind]
    lobe_var = [rng.uniform(-0.06, 0.06) for _ in range(LOBES)]
    lobe_tone = [rng.uniform(-0.08, 0.08) for _ in range(LOBES)]
    theta0 = rng.uniform(0, 2 * math.pi)
    squash = rng.uniform(-0.04, 0.04)

    def lobe(theta):
        x = (theta - theta0) * LOBES / (2 * math.pi)
        k = math.floor(x)
        return math.sin(math.pi * (x - k)), int(k) % LOBES

    def profile(phi):
        r = math.sin(phi) ** 0.85
        z = -math.cos(phi)
        z -= 0.42 * math.exp(-((math.pi - phi) / 0.45) ** 2)     # stem dimple
        z += 0.25 * math.exp(-(phi / 0.42) ** 2)                 # blossom dimple
        return r, z

    zc = H * 0.98
    verts = [Vector((0, 0, zc + H * profile(0.0)[1]))]
    phis = [lerp(0.28, math.pi - 0.3, i / (RINGS - 1)) for i in range(RINGS)]
    for phi in phis:
        for j in range(SEG):
            theta = theta0 + 2 * math.pi * j / SEG
            s, k = lobe(theta)
            r, z = profile(phi)
            shape = (1 - 0.13 * (1 - s ** 0.6)) * (1 + lobe_var[k] * s)
            rr = R * r * shape * (1 + squash * math.cos(theta))
            verts.append(Vector((rr * math.cos(theta), rr * math.sin(theta), zc + H * z)))
    verts.append(Vector((0, 0, zc + H * profile(math.pi)[1])))
    top = len(verts) - 1
    idx = lambda i, j: 1 + i * SEG + (j % SEG)  # noqa: E731
    faces = [(0, idx(0, j + 1), idx(0, j)) for j in range(SEG)]
    for i in range(RINGS - 1):
        for j in range(SEG):
            faces.append((idx(i, j), idx(i, j + 1), idx(i + 1, j + 1), idx(i + 1, j)))
    faces += [(idx(RINGS - 1, j), idx(RINGS - 1, j + 1), top) for j in range(SEG)]
    body = build("body", verts, faces)
    gab.displace_noise(body, strength=0.006, size=0.08)
    ground(body, min(v.co.z for v in body.data.vertices))
    z_lo = min(v.co.z for v in body.data.vertices)
    for v in body.data.vertices:
        v.co.z -= z_lo
    z_hi = max(v.co.z for v in body.data.vertices)
    body_bvh = BVHTree.FromPolygons([v.co.copy() for v in body.data.vertices],
                                    [p.vertices[:] for p in body.data.polygons])

    def surface_z(x, y):
        hit = body_bvh.ray_cast(Vector((x, y, 1.0)), Vector((0, 0, -1)))
        return hit[0].z if hit[0] is not None else -1.0

    gab.uv_cylinder(body)
    gab.smooth(body, 60)
    deep = "pumpkin_deep" if kind < 2 else "pumpkin_dark"

    def skin(vi, co, poly):
        t = co.z / z_hi
        c = ramp([(0.0, col("pumpkin_dark") * 0.5), (0.3, col("pumpkin_dark") * 0.85), (0.6, deep),
                  (0.88, skin_hue), (1.0, skin_hue)], t)
        s, k = lobe(math.atan2(co.y, co.x))
        c = c * (1 + lobe_tone[k] * s)
        c = lerp(c, col("pumpkin_deep") * 0.62, 0.65 * (1 - s) ** 2.4 * (0.5 + 0.5 * t))
        crest = s ** 3 * smoothstep(0.5, 0.95, t)
        c = lerp(c, col("ember_tip" if kind < 2 else "autumn_tip") * 0.9, 0.4 * crest)   # lit crests stay under clipping
        rxy = math.hypot(co.x, co.y)
        c = lerp(c, col("stem") * 0.9, 0.55 * smoothstep(0.05, 0.015, rxy) * smoothstep(0.7, 0.95, t))
        return c

    paint_fn(body, skin, "plain", 0.02)
    body.data.materials.append(PAINTED)
    parts = [body]

    # The stem: a ridged, bent stalk, green at the base drying to brown at the cut end.
    top_z = max(v.co.z for v in body.data.vertices if math.hypot(v.co.x, v.co.y) < R * 0.3)
    dip = z_hi - 0.02
    lean = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)).normalized() * 0.022
    sh = [0.07, 0.075, 0.06][kind]
    spts = [Vector((0, 0, dip - 0.01)), Vector((0, 0, dip + sh * 0.35)), Vector((0, 0, dip + sh * 0.7)) + lean * 0.5,
            Vector((0, 0, dip + sh)) + lean * 1.4 + Vector((0, 0, -0.008))]
    stem, sts = tube("stem", spts, [0.026, 0.019, 0.016, 0.017], sides=6, twist=0.15, cap_end=True)
    # Flutes: push alternate ring vertices in.
    for vi, v in enumerate(stem.data.vertices):
        if vi % 2 == 1:
            j = min(range(len(spts)), key=lambda q: (spts[q] - v.co).length)
            v.co = spts[j] + (v.co - spts[j]) * 0.72
    gab.uv_cylinder(stem)
    n_cap = len(stem.data.polygons) - 1

    def stem_color(vi, co, poly):
        if poly.index == n_cap:
            return col("wood_light")
        return ramp([(0.0, col("stem") * 0.7), (0.4, "stem"), (0.85, "hide"), (1.0, "wood")], sts[vi])

    paint_fn(stem, stem_color, "bark", 0.03)
    gab.smooth(stem, 45)
    stem.data.materials.append(PAINTED)
    parts.append(stem)

    # A curly tendril springing from the stem base, coiling out over the shoulder.
    a0 = rng.uniform(0, 2 * math.pi)
    out = Vector((math.cos(a0), math.sin(a0), 0))
    side = Vector((-out.y, out.x, 0))
    cpts, crad = [], []
    N = 15
    for i in range(N):
        t = i / (N - 1)
        reach = 0.03 + 0.11 * t
        ang = 2 * math.pi * 2.0 * t
        coil = 0.022 * (1 - 0.55 * t)
        p = Vector((0, 0, dip + 0.012)) + out * reach + side * math.cos(ang) * coil + \
            Vector((0, 0, 0.02 * math.sin(ang) + 0.035 * t * (1 - t) * 2))
        # Follow the shoulder of the pumpkin so it does not sink in.
        p.z = max(p.z, surface_z(p.x, p.y) + 0.008)
        cpts.append(p)
        crad.append(0.0055 * (1 - 0.6 * t))
    crad[-1] = 0.0
    tendril, _ = tube("tendril", cpts, crad, sides=3)
    gab.uv_cylinder(tendril)
    paint_fn(tendril, lambda vi, co, p: col("leaf_green") * 0.95, "plain", 0.05)
    gab.smooth(tendril, 80)
    tendril.data.materials.append(PAINTED)
    parts.append(tendril)

    # One broad, lobed pumpkin leaf from the stem, draped over the shoulder.
    la = a0 + math.pi * rng.uniform(0.55, 0.85) * (1 if rng.random() < 0.5 else -1)
    lout = Vector((math.cos(la), math.sin(la), 0))
    lside = Vector((-lout.y, lout.x, 0))
    L = R * rng.uniform(0.66, 0.74)
    root = lout * R * 0.3
    # Keep the leaf on the shoulder: it ends before the gourd's side falls away.
    reach = R * 0.3
    while reach < R * 1.2 and surface_z(*(lout * (reach + 0.005)).xy) > 0.78 * z_hi:
        reach += 0.005
    L = min(L, (reach - R * 0.3) * 1.3)
    NL = 16
    SPREAD = 1.75
    rings = [[], [], []]
    flat = []
    for q in range(NL + 1):
        phi = lerp(-SPREAD, SPREAD, q / NL)
        # five lobes, tips at phi = 0, ±SPREAD/2, ±SPREAD; the side lobes shorter
        lobe_r = 0.42 + 0.58 * (0.5 + 0.5 * math.cos(phi / (SPREAD / 2) * math.pi)) ** 0.8
        lobe_r *= 1 - 0.3 * (abs(phi) / SPREAD) ** 2
        d = lout * math.cos(phi) + lside * math.sin(phi)
        for ri, frac in enumerate((0.35, 0.7, 1.0)):
            rings[ri].append(len(flat))
            flat.append(root + d * L * lobe_r * frac * (1.0 if ri == 2 else 0.85 + 0.15 * lobe_r))
    lverts = []
    for p in [root] + flat:
        z = surface_z(p.x, p.y)
        if z > 0.74 * z_hi:
            lverts.append(Vector((p.x, p.y, z + 0.013)))
        else:
            lverts.append(Vector((p.x, p.y, -1)))
    # Past the body the leaf droops: carry on from the last point on the gourd.
    for ring_i in range(3):
        for q in range(NL + 1):
            vi = 1 + rings[ring_i][q]
            if lverts[vi].z < 0:
                inner_vi = 1 + rings[ring_i - 1][q] if ring_i > 0 else 0
                prev = lverts[inner_vi]
                dist = (lverts[vi].xy - prev.xy).length
                # A stiff leaf: it bends down past the gourd, but never hangs down its face.
                lverts[vi].z = max(0.74 * z_hi, prev.z - dist * 0.35)
    for q in range(NL + 1):      # a wavy rim, and the blade crinkled between the veins
        lverts[1 + rings[2][q]].z += 0.006 * math.sin(q * 1.9)
        for ri in (1, 2):
            lverts[1 + rings[ri][q]].z += rng.uniform(-0.005, 0.005)
    # Nothing closer to the gourd than a leaf's thickness, so the lobes never poke through.
    for i, v in enumerate(lverts):
        loc, nrm, _, _ = body_bvh.find_nearest(v)
        if loc is not None and (v - loc).dot(nrm) < 0.012:
            lverts[i] = loc + nrm * 0.012
    lfaces = []
    for q in range(NL):
        lfaces.append((0, 1 + rings[0][q], 1 + rings[0][q + 1]))
        for ri in range(2):
            a, b = rings[ri], rings[ri + 1]
            lfaces.append((1 + a[q], 1 + b[q], 1 + b[q + 1], 1 + a[q + 1]))
    lverts[0].z += 0.004
    leaf = build("leaf", lverts, lfaces)
    bm = bmesh.new()
    bm.from_mesh(leaf.data)
    bm.normal_update()
    if sum(f.normal.z for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.to_mesh(leaf.data)
    bm.free()
    vein_q = {0, NL // 4, NL // 2, 3 * NL // 4, NL}
    ring_index = {}
    for ri in range(3):
        for q, v in enumerate(rings[ri]):
            ring_index[1 + v] = (ri, q)
    gab.uv_box(leaf)

    autumn = kind == 2
    leaf_body = "needle" if kind == 1 else "leaf_deep"

    def leaf_color(vi, co, poly):
        if vi == 0:
            return col("leaf_bright")
        ri, q = ring_index[vi]
        c = ramp([(0, col(leaf_body) * 0.7), (1, col(leaf_body) * 0.8), (2, col(leaf_body) * 0.95)], ri)
        if q in vein_q and ri < 2:
            c = lerp(c, col("leaf_bright"), 0.75 - 0.25 * ri)
        if autumn and ri == 2:
            c = lerp(c, col("leaf_amber") * 0.85, 0.75)
        return c

    paint_fn(leaf, leaf_color, "plain", 0.05)
    gab.smooth(leaf, 70)
    leaf.data.materials.append(PAINTED)
    parts.append(leaf)
    # The leaf's stalk, from the foot of the stem out to the leaf.
    p_end = lverts[0] + Vector((0, 0, 0.004))
    p_mid = lerp(Vector((0, 0, dip + 0.012)), p_end, 0.5) + Vector((0, 0, 0.01))
    pstalk, _ = tube("petiole", [Vector((0, 0, dip + 0.008)), p_mid, p_end], [0.0075, 0.006, 0.0045], sides=3)
    gab.uv_cylinder(pstalk)
    paint_fn(pstalk, lambda vi, co, p: col("stem") * 1.05, "plain", 0.04)
    gab.smooth(pstalk, 80)
    pstalk.data.materials.append(PAINTED)
    parts.append(pstalk)

    obj = finish(parts, f"pumpkin_{SEED}")
    ground(obj)
    return obj


# ══════════════════════════════════════════════════════════════════════════════
# Flowers
# ══════════════════════════════════════════════════════════════════════════════

def flower_style(petal_hex):
    h = petal_hex.lower().lstrip("#")
    if h == "efe6d6":
        return "daisy"
    if h == "9a6ac0":
        return "crocus"
    return "buttercup"


COLOUR_OF = {"buttercup": "yellow", "daisy": "white", "crocus": "purple"}


def petal_ramp(style):
    if style == "daisy":
        return [(0.0, col("stalk") * 0.7), (0.35, col("petal_white") * 0.82), (1.0, col("petal_white") * 0.9)]
    if style == "crocus":
        return [(0.0, "shell_light"), (0.3, col("petal_purple") * 0.9), (0.7, "petal_purple"), (1.0, "rune")]
    return [(0.0, col("petal_yellow") * 0.9), (0.45, "petal_yellow"), (1.0, "glow_yellow")]


def blossom(centre, facing, style, size, name):
    """One flower head at `centre`, its face toward `facing`: buttercup cups, flat daisies
    or crocus goblets. Petals are cheap two-sided cards; the head reads as a disc of colour."""
    up = Vector(facing).normalized()
    t1 = up.cross(Vector((0, 0, 1)))
    t1 = Vector((1, 0, 0)) if t1.length < 1e-3 else t1.normalized()
    t2 = up.cross(t1).normalized()
    parts = []
    stops = petal_ramp(style)
    two = True
    if style == "daisy":     # round-tipped straps, backs to the ground
        n, length, width, lift, fold, shape, widest, tip = 9, size, size * 0.3, -0.08, 0.25, "round", 0.6, -0.08
        two = False
    elif style == "crocus":
        n, length, width, lift, fold, shape, widest, tip = 6, size * 0.95, size * 0.6, 0.95, 0.5, "diamond", 0.62, 0.1
    else:
        n, length, width, lift, fold, shape, widest, tip = 5, size * 0.9, size * 0.85, 0.42, 0.3, "round", 0.6, 0.12
    spin = rng.uniform(0, 2 * math.pi)
    for i in range(n):
        a = spin + 2 * math.pi * i / n
        if style == "crocus":
            a += (math.pi / n) * (i % 2)   # two whorls of three
        radial = t1 * math.cos(a) + t2 * math.sin(a)
        el = lift * (0.82 if (style == "crocus" and i % 2) else 1.0) + rng.uniform(-0.08, 0.08)
        d = (radial * math.cos(el) + up * math.sin(el)).normalized()
        nrm = up - d * up.dot(d)
        base = Vector(centre) + radial * size * (0.12 if style != "crocus" else 0.06)
        ln = length * rng.uniform(0.9, 1.08)
        p, ts, half, es = petal(f"{name}_petal_{i}", base, d, nrm, ln, width, shape=shape, fold=fold,
                                widest=widest, lift_tip=tip, two=two)
        shade = rng.uniform(0.92, 1.05)

        def pc(vi, co, poly, ts=ts, half=half, es=es, shade=shade):
            c = ramp(stops, ts[vi]) * shade * (1 - 0.1 * es[vi])   # each petal its own tone, edges a touch darker
            return c * 0.72 if vi >= half else c       # the back of the petal: darker

        gab.uv_box(p)
        paint_fn(p, pc, "plain", 0.05)
        gab.smooth(p, 80)
        p.data.materials.append(PAINTED)
        parts.append(p)
    # The centre: a small dome (a disc for daisies, stamens for crocuses), ringed dark.
    cr = size * (0.27 if style == "daisy" else 0.26 if style == "buttercup" else 0.14)
    k = 6
    cv = [Vector(centre) + up * cr * (0.8 if style != "crocus" else 2.6)]
    for q in range(k):
        a = 2 * math.pi * q / k
        cv.append(Vector(centre) + (t1 * math.cos(a) + t2 * math.sin(a)) * cr - up * cr * 0.1)
    cf = [(0, 1 + q, 1 + (q + 1) % k) for q in range(k)]
    cobj = build(f"{name}_centre", cv, cf)
    bm = bmesh.new()
    bm.from_mesh(cobj.data)
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    if bm.faces[0].normal.dot(up) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.to_mesh(cobj.data)
    bm.free()
    centre_col = {"daisy": ("petal_yellow", "glow_yellow"), "buttercup": ("flower_center", "leaf_amber"),
                  "crocus": ("leaf_amber", "glow_yellow")}[style]
    gab.uv_box(cobj)
    paint_fn(cobj, lambda vi, co, p: col(centre_col[1]) if vi == 0 else col(centre_col[0]), "plain", 0.03)
    gab.smooth(cobj, 80)
    cobj.data.materials.append(PAINTED)
    parts.append(cobj)
    return parts


def stalk_tube(name, pts, radii):
    obj, ts = tube(name, pts, radii, sides=3)
    gab.uv_cylinder(obj)
    paint_fn(obj, lambda vi, co, p: ramp([(0, "needle_deep"), (0.08, "stem"), (0.18, "grass")], co.z), "plain", 0.04)
    gab.smooth(obj, 80)
    obj.data.materials.append(PAINTED)
    return obj


def make_flower():
    """A clump of flowers: forked stems holding five to seven big heads in a loose dome, so
    the clump reads as a patch of colour from the game camera; three basal leaves."""
    petal_hex = gab.param("petal", "#e8c04a")
    style = flower_style(petal_hex)
    kind = (SEED - 1) % 2
    parts = []
    n_heads = {"buttercup": [6, 5], "daisy": [6, 5], "crocus": [7, 6]}[style][kind]
    buds = 1 if kind == 1 else 0
    spin = rng.uniform(0, 2 * math.pi)
    golden = math.pi * (3 - math.sqrt(5))
    heads = []
    for i in range(n_heads):
        a = spin + golden * i + rng.uniform(-0.25, 0.25)
        r = 0.012 + 0.062 * math.sqrt((i + 0.5) / n_heads) * rng.uniform(0.85, 1.1)
        out = Vector((math.cos(a), math.sin(a), 0))
        h = 0.17 - 0.055 * (r / 0.074) ** 2 + rng.uniform(-0.01, 0.01)
        heads.append((out * r + Vector((0, 0, max(0.11, h))), out, r))
    # Forked stems: pair the heads by angle, one stem to each pair, branching at mid height.
    order = sorted(range(n_heads), key=lambda j: math.atan2(heads[j][0].y, heads[j][0].x))
    if n_heads > 1 and rng.random() < 0.5:
        order = order[1:] + order[:1]
    pairs = [order[j:j + 2] for j in range(0, n_heads, 2)]
    for si, pair in enumerate(pairs):
        tips = [heads[j][0] for j in pair]
        mid = sum(tips, Vector()) / len(tips)
        base = Vector((mid.x, mid.y, 0)) * 0.2
        fork = base + (Vector((mid.x, mid.y, 0)) - base) * 0.55 + Vector((0, 0, min(t.z for t in tips) * 0.55))
        parts.append(stalk_tube(f"stem_{si}", [base, fork], [0.0065, 0.0052]))
        for j in pair:
            parts.append(stalk_tube(f"branch_{j}", [fork, heads[j][0]], [0.0048, 0.0038]))
    for j, (tip, out, r) in enumerate(heads):
        facing = (out * (0.15 + 2.5 * r) * (0.5 if style == "crocus" else 1.0) + Vector((0, 0, 1))).normalized()
        size = 0.05 * rng.uniform(1.0, 1.1)
        parts += blossom(tip, facing, style, size, f"head_{j}")
    for b in range(buds):
        # A bud on its own stalk, inside the clump: just under the heads, near the middle.
        a = spin + rng.uniform(0, 2 * math.pi)
        out = Vector((math.cos(a), math.sin(a), 0))
        tip = out * rng.uniform(0.035, 0.055) + Vector((0, 0, rng.uniform(0.11, 0.125)))
        parts.append(stalk_tube(f"bud_stem_{b}", [out * 0.006, out * 0.025 + Vector((0, 0, 0.06)), tip],
                                [0.0055, 0.0055, 0.0055]))
        facing = (out * 0.3 + Vector((0, 0, 1))).normalized()
        stops = petal_ramp(style)
        for q in range(3):
            ang = 2 * math.pi * q / 3 + a
            radial = Vector((math.cos(ang), math.sin(ang), 0))
            d = (radial * 0.2 + facing).normalized()
            bl, bts, _ = blade(f"bud_{b}_{q}", tip + radial * 0.002, d, radial, 0.03, 0.019, segs=2, fold=-0.6,
                               curl=0.006, shape=0.6, two=True)
            half = len(bts) // 2
            gab.uv_box(bl)
            paint_fn(bl, lambda vi, co, p, bts=bts, half=half: lerp(col("grass"), ramp(stops, 0.8),
                                                                   smoothstep(0.2, 0.8, bts[vi])) *
                     (0.75 if vi >= half else 1.0), "plain", 0.04)
            gab.smooth(bl, 80)
            bl.data.materials.append(PAINTED)
            parts.append(bl)
    # Basal leaves: three pointed blades, dark at the heart, bright at the tips.
    for j in range(3):
        a = spin + 2 * math.pi * (j + 0.5) / 3 + rng.uniform(-0.3, 0.3)
        out = Vector((math.cos(a), math.sin(a), 0))
        if style == "crocus":
            d = (out * 0.35 + Vector((0, 0, 1))).normalized()
            length, width = rng.uniform(0.09, 0.12), 0.016
        else:
            d = (out + Vector((0, 0, rng.uniform(0.5, 0.9)))).normalized()
            length, width = rng.uniform(0.08, 0.1), 0.03
        bl, ts, es = blade(f"leaf_{j}", out * 0.006, d, Vector((0, 0, 1)) - d * d.z, length, width, segs=3,
                           fold=0.35, curl=length * 0.35, shape=0.9)
        half = len(ts) // 2
        gab.uv_box(bl)
        paint_fn(bl, lambda vi, co, p, ts=ts, half=half: ramp([(0, "needle_deep"), (0.45, "leaf_deep"),
                                                               (1.0, "leaf_green")], ts[vi]) *
                 (0.75 if vi >= half else 1.0), "plain", 0.05)
        gab.smooth(bl, 80)
        bl.data.materials.append(PAINTED)
        parts.append(bl)
    obj = finish(parts, f"flower_{COLOUR_OF[style]}_{SEED}")
    ground(obj)
    recentre(obj)
    return obj


# ══════════════════════════════════════════════════════════════════════════════
# Lily pads
# ══════════════════════════════════════════════════════════════════════════════

# Pad paints a good step darker than they should read: flat, up-facing leaves get the
# shader's full top light, so a mid green comes out lime. (heart, body, rim)
LILY_SCHEMES = [
    (col("leaf_green") * 0.58, col("needle") * 0.62, col("needle_deep") * 0.7),                # cool, deep
    (col("leaf_deep") * 0.72, col("needle_deep") * 0.95, col("needle_deep") * 0.62),           # dark
    (col("leaf_deep") * 0.66, lerp(col("needle"), col("hide"), 0.45) * 0.72, col("hide_dark") * 0.8),  # bronze
]


def lily_pad(at, radius, yaw, name, sectors=16, scheme=0):
    """A floating pad: three rings out to a rim that curls up into a lip, its reddish
    underside showing on the outside (pads under 8 cm skip that skirt); a narrow notch
    whose lobes overlap at the rim; veins from the heart; an irregular outline; tilted a
    few degrees on the water."""
    sectors = max(12, sectors)
    with_skirt = radius >= 0.08
    notch = rng.uniform(0.15, 0.25)
    rn = [rng.uniform(-0.08, 0.08) for _ in range(sectors + 1)]
    rn = [(rn[max(0, q - 1)] + 2 * rn[q] + rn[min(sectors, q + 1)]) / 4 * 1.6 for q in range(sectors + 1)]
    curl = rng.uniform(0.008, 0.01)
    verts = [Vector((0, 0, 0.0055))]
    rings = []
    fr = [0.45, 0.86, 1.0]
    for fi, f in enumerate(fr):
        ring = []
        for q in range(sectors + 1):
            a = notch / 2 + (2 * math.pi - notch) * q / sectors
            r = radius * f * (1 + rn[q] * f)
            z = 0.006 + 0.0015 * math.sin(2 * a + yaw) * f
            if fi == 2:
                z += curl
            if q == sectors:          # one lobe's tip rides a little higher than the other
                z += 0.003 * f
            ring.append(len(verts))
            verts.append(Vector((r * math.cos(a), r * math.sin(a), z)))
        rings.append(ring)
    skirt = []
    if with_skirt:
        for q in range(sectors + 1):
            p = verts[rings[-1][q]]
            skirt.append(len(verts))
            verts.append(Vector((p.x * 0.96, p.y * 0.96, 0.001)))     # tucked under the lip
    bands = ((rings[0], rings[1]), (rings[1], rings[2])) + (((rings[2], skirt),) if with_skirt else ())
    faces = []
    for q in range(sectors):
        faces.append((0, rings[0][q], rings[0][q + 1]))
        for A, B in bands:
            faces.append((A[q], B[q], B[q + 1], A[q + 1]))
    edge = skirt if with_skirt else rings[2]
    faces.append((0, edge[0], rings[2][0]) if with_skirt else (0, rings[1][0], rings[2][0]))
    faces.append((0, rings[2][-1], edge[-1]) if with_skirt else (0, rings[2][-1], rings[1][-1]))
    pad = build(name, verts, faces)
    bm = bmesh.new()
    bm.from_mesh(pad.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    if sum(f.normal.z * f.calc_area() for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(pad.data)
    bm.free()
    ring_of, spoke_of = {0: -1}, {}
    for fi, ring in enumerate(rings):
        for q, v in enumerate(ring):
            ring_of[v] = fi
            spoke_of[v] = q
    for v in skirt:
        ring_of[v] = 3
    heart, body, rim = LILY_SCHEMES[scheme]
    tone = rng.uniform(0.94, 1.04)
    off = Vector((rng.uniform(-40, 40), rng.uniform(-40, 40), 0))

    def pad_color(vi, co, poly):
        r = ring_of.get(vi, 3)
        if r == 3:                       # the skirt: the lip's reddish underside
            return lerp(col("leaf_red") * 0.55, col("hide_dark"), 0.3)
        if r == -1:
            c = lerp(heart, col("leaf_bright") * 0.6, 0.35)
        elif r == 0:
            c = heart
            if spoke_of[vi] % 2 == 0:    # veins, faint, from the heart and gone by ring 1
                c = lerp(c, col("leaf_bright") * 0.6, 0.25)
        elif r == 1:
            c = body
        else:
            c = lerp(rim, col("leaf_red") * 0.6, 0.1)
        c = c * (0.9 + 0.15 * clamp01(0.5 + fbm(co * 25 + off, 2)))
        return c * tone

    tilt_axis = rng.uniform(0, 2 * math.pi)
    tilt = math.radians(rng.uniform(2, 4))
    pad.rotation_euler = (tilt * math.cos(tilt_axis), tilt * math.sin(tilt_axis), yaw)
    pad.location = (at[0], at[1], 0)
    gab.apply_transform(pad)
    gab.uv_box(pad)
    paint_fn(pad, pad_color, "plain", 0.02)
    gab.smooth(pad, 50)
    pad.data.materials.append(PAINTED)
    return pad


def lily_petal_color(ts, half, whorl):
    def pc(vi, co, poly):
        c = ramp([(0.0, col("rune") * 0.82), (0.5, lerp(col("rune") * 0.82, col("petal_white"), 0.7)),
                  (1.0, "petal_white")], ts[vi])
        if whorl == 0:
            c = lerp(c, col("rune") * 0.8, 0.25)
        return c * (0.75 if vi >= half else 1.0)
    return pc


def water_lily(at, size, name):
    """A lilac-blushed water lily: an open whorl of pointed petals around a cup of inner
    ones and a golden heart."""
    parts = []
    centre = Vector((at[0], at[1], 0.012))
    up = Vector((0, 0, 1))
    spin = rng.uniform(0, 2 * math.pi)
    for whorl, (n, lift, length, width) in enumerate(((8, 0.3, size, size * 0.42),
                                                      (7, 0.95, size * 0.78, size * 0.42))):
        for i in range(n):
            a = spin + 2 * math.pi * (i + 0.5 * whorl) / n
            radial = Vector((math.cos(a), math.sin(a), 0))
            d = (radial * math.cos(lift) + up * math.sin(lift)).normalized()
            nrm = up - d * up.dot(d)
            base = centre + radial * size * 0.08 + up * 0.004 * whorl
            ln = length * rng.uniform(0.92, 1.06)
            if whorl == 0:
                p, ts, es = blade(f"{name}_p{whorl}_{i}", base, d, nrm, ln, width, segs=2, fold=0.45,
                                  curl=-ln * 0.15, shape=0.7)
                half = len(ts) // 2
            else:
                p, ts, half, _ = petal(f"{name}_p{whorl}_{i}", base, d, nrm, ln, width, shape="diamond", fold=0.5,
                                       widest=0.5, lift_tip=0.05)
            gab.uv_box(p)
            paint_fn(p, lily_petal_color(ts, half, whorl), "plain", 0.03)
            gab.smooth(p, 80)
            p.data.materials.append(PAINTED)
            parts.append(p)
    k = 6
    cv = [centre + up * size * 0.42]
    for q in range(k):
        a = 2 * math.pi * q / k
        cv.append(centre + Vector((math.cos(a), math.sin(a), 0)) * size * 0.24 + up * size * 0.12)
    cobj = build(f"{name}_heart", cv, [(0, 1 + q, 1 + (q + 1) % k) for q in range(k)])
    bm = bmesh.new()
    bm.from_mesh(cobj.data)
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    if bm.faces[0].normal.z < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.to_mesh(cobj.data)
    bm.free()
    gab.uv_box(cobj)
    # A golden heart, painted (no extra material: it would cost a draw call for a 1.5 cm dot).
    paint_fn(cobj, lambda vi, co, p: col("glow_pale") if vi == 0 else col("glow_yellow") * 0.9, "plain", 0.0)
    gab.smooth(cobj, 80)
    cobj.data.materials.append(PAINTED)
    parts.append(cobj)
    return parts


def lily_bud(at, size, name):
    """A closed bud standing out of the water on a short green neck: a smooth ovoid, green at
    its foot blushing lilac to a pale tip, two green sepals hugging it."""
    parts = []
    base = Vector((at[0], at[1], 0.0))
    top = base + Vector((0.004, 0, size * 0.3))
    neck, _ = tube(f"{name}_neck", [base, top + Vector((0, 0, 0.004))], [0.006, 0.0055], sides=4)
    gab.uv_cylinder(neck)
    paint_fn(neck, lambda vi, co, p: col("leaf_deep") * 0.8, "plain", 0.04)
    neck.data.materials.append(PAINTED)
    parts.append(neck)
    prof = [(0.008, 0.0), (0.016, 0.02), (0.012, 0.04), (0.0, 0.055)]
    bud, bidx, _ = lathe(f"{name}_ovoid", prof, 6, start=rng.uniform(0, 1))
    for v in bud.data.vertices:
        v.co += top
    gab.uv_cylinder(bud)
    paint_fn(bud, lambda vi, co, p: ramp([(0.0, col("leaf_deep") * 0.85), (0.6, col("rune") * 0.8),
                                          (1.0, "petal_white")], bidx[vi] / 3), "plain", 0.03)
    gab.smooth(bud, 70)
    bud.data.materials.append(PAINTED)
    parts.append(bud)
    a0 = rng.uniform(0, 2 * math.pi)
    for q in range(2):
        a = a0 + math.pi * q + rng.uniform(-0.3, 0.3)
        radial = Vector((math.cos(a), math.sin(a), 0))
        d = (radial * 0.5 + Vector((0, 0, 1))).normalized()
        b, bts, _ = blade(f"{name}_sepal_{q}", top + radial * 0.009 + Vector((0, 0, 0.002)), d, radial, 0.042,
                          0.022, segs=2, fold=-0.6, curl=0.012, shape=0.6, two=True)
        half = len(bts) // 2
        gab.uv_box(b)
        paint_fn(b, lambda vi, co, p, bts=bts, half=half: ramp([(0.0, col("needle") * 0.85), (0.7, "leaf_deep"),
                                                                (1.0, col("leaf_red") * 0.7)], bts[vi]) *
                 (0.75 if vi >= half else 1.0), "plain", 0.04)
        gab.smooth(b, 80)
        b.data.materials.append(PAINTED)
        parts.append(b)
    return parts


def make_lily():
    kind = (SEED - 1) % 3
    with_blossom = bool(int(gab.param("blossom", "1" if kind != 1 else "0")))
    schemes = rng.sample(range(3), 3)
    parts = []
    if kind == 0:
        parts.append(lily_pad((0.0, 0.0), 0.13, rng.uniform(0, 6.3), "pad_a", 14, schemes[0]))
        parts.append(lily_pad((0.15, -0.09), 0.075, rng.uniform(0, 6.3), "pad_b", 12, schemes[1]))
        bloom_at = (0.02, -0.01)
    elif kind == 1:
        parts.append(lily_pad((0.0, 0.0), 0.11, rng.uniform(0, 6.3), "pad_a", 12, schemes[0]))
        parts.append(lily_pad((-0.13, 0.08), 0.085, rng.uniform(0, 6.3), "pad_b", 12, schemes[1]))
        parts.append(lily_pad((0.11, 0.1), 0.06, rng.uniform(0, 6.3), "pad_c", 12, schemes[2]))
        bloom_at = (0.0, 0.0)
    else:
        parts.append(lily_pad((0.0, 0.0), 0.15, rng.uniform(0, 6.3), "pad_a", 16, schemes[0]))
        parts.append(lily_pad((-0.12, -0.12), 0.065, rng.uniform(0, 6.3), "pad_b", 12, schemes[1]))
        bloom_at = (-0.03, 0.02)
    if with_blossom:
        parts += water_lily(bloom_at, 0.065, "lily")
    else:
        parts += lily_bud((bloom_at[0] + 0.03, bloom_at[1] - 0.02), 0.075, "bud")
    obj = finish(parts, f"lily_pad_{SEED}")
    ground(obj)
    recentre(obj)
    return obj


# ── Build ──

BUILDERS = {"rock": make_rocks, "stump": make_stump, "mushroom": make_mushrooms, "pumpkin": make_pumpkin,
            "flower": make_flower, "lily": make_lily}
if KIND not in BUILDERS:
    raise ValueError(f"unknown kind {KIND!r}; use one of {sorted(BUILDERS)}")
result = BUILDERS[KIND]()
print(f"ground_props: {KIND} seed {SEED}: {gab.triangles(result)} triangles")
