"""Undergrowth for Wickhollow: leafy bushes, ferns, grass tufts and reeds.

    godot-agent asset blender . art_src/blender/undergrowth.py --param kind=bush \
        --to res://models/vegetation/bush_1.glb --seed 1 --review --no-import

    kind=bush   bush_1..3        (seeds 1-3) low leafy domes, about 0.42 tall and 1.4-1.5x as wide
    kind=fern   fern_1..2        (seeds 1-2) arching fronds in three sprays, about 0.35 tall
    kind=grass  grass_tuft_1..3  (seeds 1-3) crossed grass cards and an arching fringe, 0.2-0.27 tall
    kind=reeds  reeds_1..3       (seeds 1-3) a fan of reed blades and slender cattails, about 0.4 tall

Everything ends up in one mesh with one surface per material (painted plus one
foliage card material), so each model costs at most two draw calls in the
MultiMesh. Front faces -Y, the base sits on the origin. The mesh (object and
data) is named after the output file, like the other vegetation.

Shading: foliage carries custom normals, kept per corner in a "tn" attribute while
the parts are built and applied after the join. Bushes shade as one soft dome,
ferns as a low dome, grass mostly like the ground it grows from. The foliage
shader multiplies the grey card texture by the vertex tint (x1.45); the leaf and
grass cards have a dark foot painted in, so each card's tint is multiplied by a
lift measured from the texture along v (LEAF_TEX, GRASS_TEX).

Godot flips the normal on the back face of a double-sided card, so a card whose
normals are bent toward the sky turns black from behind. Grass and the reeds' foot
cards are therefore built as twins: two one-sided copies a millimetre apart, wound
opposite ways, so from either side the nearer copy shows its front with the
authored normal.
"""

import colorsys
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

import gab

rng = gab.rng
KIND = gab.param("kind", "bush")
UP = Vector((0, 0, 1))


def output_stem(default):
    """The output file's stem (bush_1, reeds_3...), read from the runner's --out."""
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
        args = dict(zip(argv[::2], argv[1::2]))
        if "--out" in args:
            return Path(args["--out"]).stem
    return default


# ── Colours (hollow palette, plus two foliage tints of our own) ──

HEX = {
    "bark": "#5b3a29", "wood_dark": "#4e3423", "wood": "#7a5534", "wood_light": "#a0784a",
    "hide": "#6b4a34", "hide_dark": "#4a3324", "leg": "#3e2a1e", "flower_center": "#7a4a20",
    "needle_deep": "#1d4528", "needle": "#2f5f3e", "needle_light": "#3f7a4a", "needle_tip": "#a8d24c",
    "leaf_deep": "#3f7a2e", "leaf": "#5a8a3a", "leaf_light": "#7fa848", "leaf_bright": "#7fb444",
    "leaf_tip": "#c3e070", "grass": "#6a9a3c", "grass_light": "#8fb84e", "stem": "#5a6b2e",
    "leaf_amber": "#d08a2e", "amber_light": "#e8b44a", "autumn_tip": "#f6d070", "ember_tip": "#f0a050",
    "leaf_red": "#b8452c", "cap": "#b8432f", "pumpkin_dark": "#a8521e",
    "petal_white": "#efe6d6", "petal_yellow": "#e8c04a", "stalk": "#e6dcc3", "plaster": "#e9d6aa",
    "snow": "#eef4f8",
    "olive": "#7a8a3a",          # reed blades (foliage tint, not palette-checked)
}


def col(name):
    return Vector(gab.rgb(HEX.get(name, name)))


def lerp(a, b, t):
    return a + (b - a) * t


def clamp01(x):
    return max(0.0, min(1.0, x))


def smoothstep(e0, e1, x):
    t = clamp01((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def ramp(stops, t):
    """stops: [(t, colour name or Vector)], sorted by t; returns a linear Vector."""
    stops = [(s, col(c) if isinstance(c, str) else c) for s, c in stops]
    if t <= stops[0][0]:
        return stops[0][1].copy()
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            return lerp(c0, c1, (t - t0) / (t1 - t0))
    return stops[-1][1].copy()


def hue_shift(c, dh, ds=0.0):
    """A linear colour turned around the hue circle by `dh` turns (for greens a
    negative turn leans toward yellow, a positive one toward blue-green) and made
    `ds` more saturated."""
    h, sat, v = colorsys.rgb_to_hsv(*c)
    return Vector(colorsys.hsv_to_rgb((h + dh) % 1.0, clamp01(sat + ds), v))


def colorize(obj, fn, pattern="plain", facet=0.04):
    """Vertex colours from fn(vertex_index, co) -> linear Vector; alpha carries the
    painted pattern exactly as gab.paint() writes it."""
    mesh = obj.data
    layer = gab._color_layer(mesh)
    alpha = (gab.PATTERNS.index(pattern) + 0.5) / 16
    for poly in mesh.polygons:
        shade = 1.0 + rng.uniform(-facet, facet)
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index
            c = fn(vi, mesh.vertices[vi].co) * shade
            layer.data[li].color = (clamp01(c.x), clamp01(c.y), clamp01(c.z), alpha)
    return obj


def store_normals(obj, fn):
    """Target normals per corner, fn(vertex_index, co, polygon) -> Vector, kept in the
    'tn' attribute; finish() turns them into custom normals after the join."""
    mesh = obj.data
    attr = mesh.attributes.get("tn") or mesh.attributes.new("tn", "FLOAT_VECTOR", "CORNER")
    for poly in mesh.polygons:
        poly.use_smooth = True
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index
            attr.data[li].vector = fn(vi, mesh.vertices[vi].co, poly).normalized()
    return obj


def twin(obj, offset=0.0012):
    """Makes `obj` one half of a one-sided pair: a copy wound the other way joins it,
    and each moves `offset` toward its own front. Seen from either side, the nearer
    copy faces the viewer, so its authored (sky-bent) normal is used as it is,
    instead of the negated normal Godot gives the back of a double-sided card.
    Returns the copy; call store_normals() on both afterwards."""
    copy = obj.copy()
    copy.data = obj.data.copy()
    copy.name = obj.name + "_back"
    gab.link(copy)
    copy.data.flip_normals()
    for o in (obj, copy):
        mesh = o.data
        mesh.update()
        moved = [v.co + v.normal * offset for v in mesh.vertices]
        for v, p in zip(mesh.vertices, moved):
            v.co = p
        mesh.update()
    return copy


def make(name, verts, faces, vert_uvs=None, face_uvs=None, mat=None):
    """A mesh object; UVs per vertex (no seams) or per face corner."""
    if vert_uvs is not None:
        face_uvs = [[vert_uvs[i] for i in f] for f in faces]
    obj = gab.mesh_object(name, verts, faces, face_uvs)
    if mat is not None:
        gab.assign(obj, mat)
    return obj


def frame(direction, up=UP):
    """Two unit vectors perpendicular to `direction`: (side, normal)."""
    d = direction.normalized()
    ref = up if abs(d.dot(up)) < 0.95 else Vector((1, 0, 0))
    side = d.cross(ref).normalized()
    return side, side.cross(d).normalized()


def horizontal(v):
    h = Vector((v.x, v.y, 0.0))
    return h.normalized() if h.length > 1e-6 else Vector((0, 0, 0))


def tex_lift(v, table, target, strength, cap):
    """How much to brighten a card's tint at texture height v so the texture's darker
    rows come up toward `target` (linear luminance), partially (`strength`)."""
    lum = table[-1][1]
    if v <= table[0][0]:
        lum = table[0][1]
    else:
        for (v0, l0), (v1, l1) in zip(table, table[1:]):
            if v <= v1:
                lum = lerp(l0, l1, (v - v0) / (v1 - v0))
                break
    return max(1.0, min(cap, (target / lum) ** strength))


# Linear brightness of the card textures along v (alpha-weighted, opaque texels only),
# measured from textures/foliage_leaves.png and foliage_grass.png.
LEAF_TEX = [(0.0, 0.045), (0.1, 0.041), (0.2, 0.052), (0.3, 0.085), (0.35, 0.1), (0.4, 0.182), (0.45, 0.212),
            (0.5, 0.393), (0.6, 0.439), (0.7, 0.451), (0.8, 0.591), (1.0, 0.6)]
GRASS_TEX = [(0.0, 0.044), (0.05, 0.063), (0.1, 0.135), (0.15, 0.227), (0.2, 0.293), (0.25, 0.381), (0.3, 0.439),
             (0.35, 0.513), (0.4, 0.576), (0.5, 0.62), (0.6, 0.697), (0.65, 0.731), (1.0, 0.72)]


# ── Builders ──

def ribbon(name, centers, sides, widths, lift=0.0, along="u", tip=False, mat=None, band=(0.0, 1.0),
           vrange=(0.0, 1.0), tvals=None, across=3):
    """A strip through `centers`, `across` vertices wide (3: edge, spine, edge, so the
    edges can lift along the strip's normal into a cup or a keel; 2: a flat blade).
    along='u': texture u runs root to tip (fern fronds, like gab.bough);
    along='v': texture v runs bottom to top (upright grass cards, like gab.card).
    `band` squeezes the across coordinate into part of the texture, `vrange` the
    along coordinate; `tvals` places the rows (default: evenly). tip=True collapses
    the last row into a point. The front (side x tangent) is the face normal.
    Returns (obj, ts) where ts[i] is how far along the strip vertex i sits (0..1)."""
    n = len(centers)
    tvals = tvals or [i / (n - 1) for i in range(n)]
    ks = (0, 1, 2) if across == 3 else (0, 2)
    verts, uvs, ts, faces = [], [], [], []
    for i, c in enumerate(centers):
        t = tvals[i]
        tv = lerp(vrange[0], vrange[1], t)
        tangent = (centers[min(i + 1, n - 1)] - centers[max(i - 1, 0)]).normalized()
        side = sides[i].normalized()
        normal = side.cross(tangent).normalized()
        w = widths[i]
        up = normal * (lift * w)
        if tip and i == n - 1:
            verts.append(c.copy())
            mid = lerp(band[0], band[1], 0.5)
            uvs.append((tv, mid) if along == "u" else (mid, tv))
            ts.append(t)
            continue
        for k in ks:
            p = c + side * ((k - 1) * w / 2) + (up if k != 1 else Vector())
            verts.append(p)
            a = lerp(band[0], band[1], k / 2)
            uvs.append((tv, a) if along == "u" else (a, tv))
            ts.append(t)
    m = len(ks)
    for i in range(n - 1):
        a = m * i
        if tip and i == n - 2:
            p = m * (n - 1)
            faces += [(a + j, a + j + 1, p) for j in range(m - 1)]
        else:
            b = a + m
            faces += [(a + j, a + j + 1, b + j + 1, b + j) for j in range(m - 1)]
    obj = make(name, verts, faces, vert_uvs=uvs, mat=mat)
    return obj, ts


def tube(name, path, radii, sides=5, close_start=False, close_end=False, mat=None, twist=0.0, uv_scale=1.0):
    """A tube along `path` with a ring of `sides` per point (parallel-transported, so
    it never kinks), UVs in metres around and along for bark-like patterns. Closed
    ends become cone points. Returns (obj, ts) with ts[i] in 0..1 along the path."""
    n = len(path)
    tangents = [(path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized() for i in range(n)]
    side, normal = frame(tangents[0])
    frames = []
    for i in range(n):
        if i > 0:
            rot = tangents[i - 1].rotation_difference(tangents[i])
            side = (rot @ side).normalized()
            normal = (rot @ normal).normalized()
        frames.append((side, normal))
    lengths = [0.0]
    for i in range(1, n):
        lengths.append(lengths[-1] + (path[i] - path[i - 1]).length)
    total = lengths[-1] or 1.0
    verts, ts, faces, face_uvs = [], [], [], []
    ring_start = []

    def is_point(i):
        return (close_start and i == 0) or (close_end and i == n - 1)

    for i in range(n):
        ring_start.append(len(verts))
        if is_point(i):
            verts.append(path[i].copy())
            ts.append(lengths[i] / total)
            continue
        s, nm = frames[i]
        for j in range(sides):
            a = 2 * math.pi * j / sides + twist * i
            verts.append(path[i] + (s * math.cos(a) + nm * math.sin(a)) * radii[i])
            ts.append(lengths[i] / total)
    k = uv_scale
    for i in range(n - 1):
        r0, r1 = ring_start[i], ring_start[i + 1]
        c0 = 2 * math.pi * max(radii[i], 0.004) * k
        c1 = 2 * math.pi * max(radii[i + 1], 0.004) * k
        v0, v1 = lengths[i] * k, lengths[i + 1] * k
        for j in range(sides):
            j1 = (j + 1) % sides
            u0, u1 = j / sides, (j + 1) / sides
            # wound so the normals point out of the tube (the painted shader culls backs)
            if is_point(i):
                faces.append((r0, r1 + j, r1 + j1))
                face_uvs.append([((u0 + u1) / 2 * c1, v0), (u0 * c1, v1), (u1 * c1, v1)])
            elif is_point(i + 1):
                faces.append((r0 + j, r1, r0 + j1))
                face_uvs.append([(u0 * c0, v0), ((u0 + u1) / 2 * c0, v1), (u1 * c0, v0)])
            else:
                faces.append((r0 + j, r1 + j, r1 + j1, r0 + j1))
                face_uvs.append([(u0 * c0, v0), (u0 * c1, v1), (u1 * c1, v1), (u1 * c0, v0)])
    obj = make(name, verts, faces, face_uvs=face_uvs, mat=mat)
    return obj, ts


PILLOW_FACES = [(0, 1, 4), (0, 4, 3), (1, 2, 4), (2, 5, 4), (3, 4, 6), (4, 7, 6), (4, 5, 8), (4, 8, 7)]


def pillow(name, center, normal, size, up_hint=UP, spin=0.0, cup=0.16, mat=None, uv=(0.03, 0.07, 0.97, 0.93)):
    """A leaf-clump card facing `normal`: a 3x3 vertex grid (8 triangles) domed out
    by `cup` x size in the middle and curling back a little at the corners, so it
    reads as a rounded mass. The texture's top points along `up_hint` (projected
    onto the card), turned by `spin`. `uv` crops the texture's empty margins.
    Returns (obj, vs) with vs[i] the texture v of vertex i."""
    n = normal.normalized()
    up = up_hint - n * up_hint.dot(n)
    if up.length < 0.15:
        up = Vector((1, 0, 0)) - n * n.x
    up = Matrix.Rotation(spin, 3, n) @ up.normalized()
    right = up.cross(n).normalized()
    up = n.cross(right).normalized()
    h = size / 2
    verts, uvs = [], []
    for j in range(3):
        for i in range(3):
            x, y = i - 1, j - 1
            dome = cup * size * (1 - 0.6 * (x * x + y * y))
            verts.append(center + right * (x * h) + up * (y * h) + n * dome)
            uvs.append((lerp(uv[0], uv[2], i / 2), lerp(uv[1], uv[3], j / 2)))
    obj = make(name, verts, PILLOW_FACES, vert_uvs=uvs, mat=mat)
    return obj, [v for _, v in uvs]


def bead(name, center, radius, mat):
    """A berry: an octahedron (8 triangles), randomly turned about the vertical, smooth
    shaded so it reads round; the poles stay up and down so the colour ramp is top-lit."""
    rot = Euler((0, 0, rng.uniform(0, 6.3))).to_matrix()
    dirs = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    verts = [center + (rot @ Vector(d)) * radius for d in dirs]
    faces = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
    return make(name, verts, faces, vert_uvs=[(v.x, v.y) for v in verts], mat=mat)


def blossom(name, center, normal, radius, mat):
    """A cupped five-petal flower facing `normal` (20 triangles): a raised yellow
    centre, and petals from a cream base up to white tips that curl up by a third
    of the radius. Returns (obj, part) where part[vi] is 'eye', 'base', 'side' or 'tip'."""
    side, nm = frame(normal)
    n = normal.normalized()
    spin = rng.uniform(0, 72)
    verts, part = [center + n * radius * 0.3], ["eye"]

    def at(angle, r, lift):
        a = math.radians(spin + angle)
        return center + (side * math.cos(a) + nm * math.sin(a)) * r + n * lift

    eye = []
    for k in range(5):
        eye.append(len(verts))
        verts.append(at(k * 72 + 36, radius * 0.26, radius * 0.18))
        part.append("eye")
    base = []
    for k in range(5):
        base.append(len(verts))
        verts.append(at(k * 72 + 36, radius * 0.26, radius * 0.14))
        part.append("base")
    faces = [(0, eye[k], eye[(k + 1) % 5]) for k in range(5)]
    for k in range(5):
        r = radius * rng.uniform(0.92, 1.06)
        s1, tp, s2 = len(verts), len(verts) + 1, len(verts) + 2
        verts += [at(k * 72 - 22, r * 0.84, radius * 0.22), at(k * 72, r, radius * 0.35),
                  at(k * 72 + 22, r * 0.84, radius * 0.22)]
        part += ["side", "tip", "side"]
        b0, b1 = base[(k - 1) % 5], base[k]
        faces += [(b0, s1, tp), (b0, tp, s2), (b0, s2, b1)]
    # wind every face toward `normal` (the painted material culls back faces)
    fixed = []
    for f in faces:
        a, b, c = (verts[i] for i in f)
        fixed.append(f if (b - a).cross(c - a).dot(n) >= 0 else (f[0], f[2], f[1]))
    uvs = [((v - center).dot(side), (v - center).dot(nm)) for v in verts]
    return make(name, verts, fixed, vert_uvs=uvs, mat=mat), part


def finish(objs, kind, height=None):
    """Join everything into one object (one surface per material) named after the
    output file, centre it, scale it to `height` if given, keep it above the ground
    with the lowest point on the origin, and turn the stored 'tn' corner normals
    into custom normals."""
    name = output_stem(kind)
    obj = gab.join(objs, name)
    obj.data.name = name
    mesh = obj.data
    xs = [v.co.x for v in mesh.vertices]
    ys = [v.co.y for v in mesh.vertices]
    shift = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, 0))
    k = 1.0
    if height:
        k = height / max(v.co.z for v in mesh.vertices)
    for v in mesh.vertices:
        v.co = (v.co - shift) * k
        if v.co.z < 0.0:
            v.co.z = 0.0
    mesh.update()
    attr = mesh.attributes.get("tn")
    if attr is not None:
        normals = [Vector(d.vector) for d in attr.data]
        # zero vectors keep the automatic normal (the painted parts)
        mesh.normals_split_custom_set([tuple(nv) if nv.length > 0.5 else (0.0, 0.0, 0.0) for nv in normals])
        mesh.attributes.remove(mesh.attributes["tn"])
    mesh.update()
    xs = [v.co.x for v in mesh.vertices]
    ys = [v.co.y for v in mesh.vertices]
    zs = [v.co.z for v in mesh.vertices]
    print(f"{kind}: {name} {max(xs) - min(xs):.3f} x {max(ys) - min(ys):.3f} x {max(zs):.3f}")
    return obj


def surface_of(objs):
    """A BVH over the given objects' polygons, to put accents on the visible leaves."""
    verts, polys = [], []
    for o in objs:
        base = len(verts)
        verts += [v.co.copy() for v in o.data.vertices]
        polys += [[base + i for i in p.vertices] for p in o.data.polygons]
    return BVHTree.FromPolygons(verts, polys)


def mesh_bvh(obj):
    return BVHTree.FromPolygons([v.co.copy() for v in obj.data.vertices], [list(p.vertices) for p in obj.data.polygons])


def sample_surface(obj, min_dist, accept, limit, attempts=6000, avoid=()):
    """Area-weighted random points on a mesh, at least `min_dist` apart (dart
    throwing) and from the points in `avoid`; accept(point, normal) filters them.
    Returns [(point, normal)]."""
    mesh = obj.data
    mesh.calc_loop_triangles()
    tris = [(tuple(mesh.vertices[i].co.copy() for i in lt.vertices), lt.normal.copy(), lt.area)
            for lt in mesh.loop_triangles]
    total = sum(t[2] for t in tris)
    cum, acc = [], 0.0
    for t in tris:
        acc += t[2]
        cum.append(acc)
    out = []
    for _ in range(attempts):
        if len(out) >= limit:
            break
        x = rng.uniform(0, total)
        lo, hi = 0, len(cum) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if cum[mid] < x:
                lo = mid + 1
            else:
                hi = mid
        (a, b, c), nrm, _ = tris[lo]
        u, v = rng.random(), rng.random()
        if u + v > 1:
            u, v = 1 - u, 1 - v
        p = a + (b - a) * u + (c - a) * v
        if not accept(p, nrm):
            continue
        if any((p - q).length < min_dist for q, _ in out) or any((p - q).length < min_dist for q in avoid):
            continue
        out.append((p, nrm))
    return out


# ── Bush ──

def cool(hex_color, amount=0.06, dv=-0.2, ds=0.05):
    """A shadow tone (as broadleaf.py makes them): the hue pulled toward blue by
    `amount` turns, darker and a little richer."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hue = colorsys.rgb_to_hsv(r, g, b)[0]
    d = (0.62 - hue + 0.5) % 1.0 - 0.5
    return gab.hsv(hex_color, max(-amount, min(amount, d)), ds, dv)


def fit(c):
    """A linear colour scaled down until no channel exceeds 1, so lifting a tint never
    clips green first and turns it yellow."""
    m = max(c.x, c.y, c.z)
    return c / m if m > 1.0 else c


# Body ramp from the green trees' tints (broadleaf.py with leaf #3f7a2e, leaf_light
# #7fb444, tip #c3e070): cool deep shade, leaf_deep, leaf_bright, a little of the pale
# tip on the crown (the shader's top light brightens up-facing leaves by another 25%).
# t = 0.55 h + 0.35 up + 0.1, so the crown reaches leaf_bright while the foot sits in
# the cool shade tones.
LEAF_RAMP = [(0.0, cool("#3f7a2e", 0.08, -0.14, 0.08)), (0.22, cool("#3f7a2e", 0.05, -0.04, 0.06)),
             (0.5, "leaf_deep"), (0.85, "leaf_bright"), (1.25, "leaf_tip")]
SPRIG_TOP = 0.88           # sprigs stop just past leaf_bright: no pale squares on the rim
NEW_GROWTH = [(0.0, "leaf_bright"), (1.0, "needle_tip")]     # bush_1's vivid lime shoots


def bush():
    flavor = ("plain", "berries", "blossoms")[(gab.seed - 1) % 3]
    painted, leaves = gab.painted(), gab.foliage("foliage_leaves")
    H = rng.uniform(0.40, 0.45)
    S = H / 0.47                                   # leaf scale relative to tree_green_1
    W = H * rng.uniform(1.45, 1.55)
    H_core, W_core = H - 0.05 * S, W - 0.19 * S    # the leaf cards stand proud of the core

    # One low dome: a broad crown sunk into a ring of lower lobes pulled in close,
    # merged by metaballs, smoothed so the crevices fill, then squashed to size.
    r_main = 0.15
    oa = rng.uniform(0, 2 * math.pi)
    off = rng.uniform(0.02, 0.045)
    lobes = [(Vector((math.cos(oa) * off, math.sin(oa) * off, r_main * rng.uniform(1.3, 1.5))), r_main * 1.15)]
    count = rng.randint(4, 6)
    a0 = rng.uniform(0, 2 * math.pi)
    for i in range(count):
        a = a0 + i * 2 * math.pi / count + rng.uniform(-0.3, 0.3)
        r = r_main * rng.uniform(0.55, 0.8)
        d = (r_main + r) * rng.uniform(0.35, 0.5)
        lobes.append((Vector((math.cos(a) * d, math.sin(a) * d, r * rng.uniform(0.85, 1.05))), r))
    hue = rng.uniform(-0.006, 0.006)

    mball = bpy.data.metaballs.new("core")
    mball.resolution = 0.028
    mball.render_resolution = 0.028
    core_obj = gab.link(bpy.data.objects.new("core", mball))
    for c, r in lobes:
        el = mball.elements.new()
        el.co = c
        el.radius = r * 0.8 / 0.62
    gab.select_only(core_obj)
    bpy.ops.object.convert(target="MESH")
    hull = bpy.context.active_object
    gab.apply_transform(hull)
    sm = hull.modifiers.new("Smooth", "SMOOTH")
    sm.factor = 0.8
    sm.iterations = 8
    gab.apply_modifiers(hull)
    vs = hull.data.vertices
    z_min = min(v.co.z for v in vs)
    for v in vs:
        v.co.z -= z_min
    wx = max(v.co.x for v in vs) - min(v.co.x for v in vs)
    wy = max(v.co.y for v in vs) - min(v.co.y for v in vs)
    kx = W_core / max(wx, wy)
    kz = H_core / max(v.co.z for v in vs)
    for v in vs:
        v.co = Vector((v.co.x * kx, v.co.y * kx, v.co.z * kz))
    hull.data.update()
    lobes = [(Vector((c.x * kx, c.y * kx, (c.z - z_min) * kz)), Vector((r * kx, r * kx, r * kz))) for c, r in lobes]
    print(f"bush: {count + 1} lobes, squash {kz / kx:.2f}, core {W_core:.2f} x {H_core:.2f}")
    hull_bvh = mesh_bvh(hull)
    lobe_tone = [rng.uniform(-0.03, 0.03) for _ in lobes]
    lobe_hue = [rng.uniform(-0.005, 0.005) for _ in lobes]

    def owner(p):
        return min(range(len(lobes)), key=lambda k: Vector(((p - lobes[k][0]).x / lobes[k][1].x,
                                                            (p - lobes[k][0]).y / lobes[k][1].y,
                                                            (p - lobes[k][0]).z / lobes[k][1].z)).length)

    def core_normal(p):
        loc, nrm, _, _ = hull_bvh.find_nearest(p)
        return nrm if nrm is not None else UP

    def mound_normal(p):
        return Vector((p.x / (W / 2), p.y / (W / 2), max(p.z, 0.0) / H)).normalized()

    objs, cards, card_meta = [], [], []

    def leaf_card(name, center, facing, size, bright, spin_range=0.5, ramp_stops=LEAF_RAMP, top=1.0, cup=0.16,
                  t_scale=1.0, foot=0.07):
        """One clump card; `foot` is where its texture starts (body cards skip most of
        the clump's darkest lower rows, which they tuck under the cards beside them)."""
        radial = horizontal(center)
        card, vs = pillow(name, center, facing, size, up_hint=UP + radial * 0.6,
                          spin=rng.uniform(-spin_range, spin_range), cup=cup, mat=leaves, uv=(0.03, foot, 0.97, 0.93))
        k = owner(center)
        fn = facing.normalized()

        def tint(vi, co):
            mn = mound_normal(co)
            h = clamp01(co.z / H)
            t = 0.55 * h + 0.35 * clamp01(mn.z * 0.5 + 0.5) + 0.1 + bright + lobe_tone[k]
            t = min(t, top) * t_scale
            # cool blue-green toward the foot, a touch warmer toward the crown
            c = hue_shift(ramp(ramp_stops, t), hue + lobe_hue[k] + lerp(0.045, 0.018, clamp01(t)), 0.06)
            return fit(c * tex_lift(vs[vi], LEAF_TEX, 0.44, 0.6, 2.5))
        colorize(card, tint, facet=0.02)
        store_normals(card, lambda vi, co, poly: mound_normal(co) * 0.7 + core_normal(co) * 0.25 + fn * 0.1)
        cards.append(card)
        card_meta.append((center, size))
        objs.append(card)
        return card

    def card_size():
        return rng.uniform(0.26, 0.32) * S

    # Body: one layer of big clump cards spread evenly over the dome (not its
    # underside), each just off the surface and turned a little toward the sky.
    body = sample_surface(hull, 0.5 * 0.29 * S, lambda p, n: n.z >= -0.1 and p.z > 0.03 * S, limit=40)
    for i, (p, n) in enumerate(body):
        facing = (n + Vector((0, 0, 0.5))).normalized()
        leaf_card(f"leaf{i}", p + n * 0.015 * S, facing, card_size(), rng.uniform(-0.04, 0.04), foot=0.16)

    # Skirt: cards lying nearly flat round the foot, hanging over the ground line,
    # so the bush sits on the ground and nothing low is seen edge-on from above.
    n_skirt = rng.randint(6, 7)
    s0 = rng.uniform(0, 2 * math.pi)
    for i in range(n_skirt):
        a = s0 + i * 2 * math.pi / n_skirt + rng.uniform(-0.25, 0.25)
        out = Vector((math.cos(a), math.sin(a), 0))
        z = rng.uniform(0.04, 0.07) * S
        hit, _, _, _ = hull_bvh.ray_cast(out * 1.0 + Vector((0, 0, z + 0.03)), -out, 1.0)
        edge = hit if hit is not None else out * (W_core / 2)
        tilt = math.radians(rng.uniform(58, 68))
        facing = out * math.cos(tilt) + UP * math.sin(tilt)
        center = Vector((edge.x, edge.y, z)) - out * 0.05 * S
        leaf_card(f"skirt{i}", center, facing, card_size() * 0.8, rng.uniform(-0.06, 0.0))

    # Sprigs: small crossed leaf clusters standing proud, half of them on the flanks
    # (so the side outline breaks up too), half on the shoulders and the crown.
    # Their colour stops at leaf_bright, so no pale squares stand on the rim.
    n_sprigs = rng.randint(8, 11)
    flank = sample_surface(hull, 0.11 * S, lambda p, n: abs(n.z) < 0.35 and 0.1 * H < p.z < 0.5 * H,
                           limit=(n_sprigs + 1) // 2)
    crest = sample_surface(hull, 0.11 * S, lambda p, n: n.z > 0.2 and p.z >= 0.5 * H,
                           limit=n_sprigs - len(flank), avoid=[p for p, _ in flank])
    rim = flank + crest
    fresh = set()
    if flavor == "plain":
        tops = sorted(range(len(rim)), key=lambda k: -rim[k][0].z)[:4]
        fresh = set(rng.sample(tops, min(len(tops), rng.randint(2, 3))))
    for i, (p, n) in enumerate(rim):
        d = (n + Vector((0, 0, 0.3))).normalized()
        at = p + n * rng.uniform(0.04, 0.055) * S
        size = rng.uniform(0.12, 0.15) * S
        side, nm = frame(d)
        spin0 = rng.uniform(0, math.pi)
        for j in range(2):
            a = spin0 + j * math.pi
            dn = (d * 0.8 + (side * math.cos(a) + nm * math.sin(a)) * 0.45).normalized()
            if i in fresh:
                leaf_card(f"sprig{i}_{j}", at + dn * size * 0.1, dn, size, 0.0, spin_range=0.7,
                          ramp_stops=NEW_GROWTH, top=1.0, cup=0.2, t_scale=0.85)
            else:
                leaf_card(f"sprig{i}_{j}", at + dn * size * 0.1, dn, size, rng.uniform(0.0, 0.08),
                          spin_range=0.7, top=SPRIG_TOP, cup=0.2)

    # Twigs: two or three bare tips poking out of the leaves, each with a tiny sprig.
    pokes = sample_surface(hull, 0.15 * S, lambda p, n: -0.05 < n.z < 0.55 and p.z > 0.1 * S,
                           limit=rng.randint(2, 3))
    for k, (p, n) in enumerate(pokes):
        out = horizontal(n)
        d = (out + UP * rng.uniform(0.35, 0.7)).normalized()
        start = p - n * 0.06 * S
        end = p + d * rng.uniform(0.1, 0.12) * S
        bend = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)) * 0.01
        path = [start, lerp(start, end, 0.45) + bend, lerp(start, end, 0.75) + bend * 0.6, end]
        twig, ts = tube(f"twig{k}", path, [0.009, 0.007, 0.005, 0.0], sides=4, close_end=True, mat=painted)
        gab.smooth(twig, 70)
        colorize(twig, lambda vi, co, ts=ts: ramp([(0, "leg"), (0.5, "bark"), (1.0, "wood_light")], ts[vi]),
                 pattern="bark")
        objs.append(twig)
        side, nm = frame(d)
        for j in range(2):
            a = rng.uniform(0, math.pi) + j * math.pi / 2
            dn = (d * 0.5 + (side * math.cos(a) + nm * math.sin(a)) * 0.8).normalized()
            leaf_card(f"tipsprig{k}_{j}", end - d * 0.01 + dn * 0.008, dn, rng.uniform(0.08, 0.1) * S,
                      0.04, spin_range=0.8, top=SPRIG_TOP, cup=0.2)

    # Plug the gaps a high camera would see: rays from above that reach the core
    # without passing through the leafy middle of a card get one more card there.
    covered = surface_of(cards)

    def sees_core(origin, d):
        hull_hit = hull_bvh.ray_cast(origin, d, 2.0)
        if hull_hit[0] is None:
            return None
        p, dist = origin, 0.0
        for _ in range(8):
            hit, _, poly, far = covered.ray_cast(p, d, 2.0)
            if hit is None or dist + far > hull_hit[3]:
                return hull_hit
            middle, size = card_meta[poly // 8]
            if (hit - middle).length < size * 0.36:
                return None
            p, dist = hit + d * 0.002, dist + far + 0.002
        return None

    plugs = 0
    for _ in range(300):
        if plugs >= 16:
            break
        el, az = math.radians(rng.uniform(22, 90)), rng.uniform(0, 2 * math.pi)
        d = -Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
        aim = Vector((rng.uniform(-0.5, 0.5) * W_core, rng.uniform(-0.5, 0.5) * W_core, rng.uniform(0.3, 0.8) * H_core))
        gap = sees_core(aim - d * 1.0, d)
        if gap is None or gap[1].z < -0.1:
            continue
        p, n = gap[0], gap[1]
        leaf_card(f"plug{plugs}", p + n * 0.006 * S, (n + Vector((0, 0, 0.5))).normalized(), card_size() * 0.85,
                  rng.uniform(-0.04, 0.0), foot=0.16)
        covered = surface_of(cards)
        plugs += 1
    print(f"bush: {len(body)} body cards, {plugs} gap cards, {len(rim)} sprigs")

    # Core: the merged dome, decimated and painted as shaded leaves (dark at the
    # foot, leaf_deep higher up), so a gap between the cards reads as shade.
    for v in hull.data.vertices:
        v.co.z = max(v.co.z, 0.0)
    gab.decimate(hull, min(1.0, 120 / max(1, gab.triangles(hull))))
    gab.assign(hull, painted)
    gab.uv_box(hull)
    gab.smooth(hull, 80)
    core_ramp = [(0.0, col("needle_deep") * 0.8), (0.6, "leaf_deep"), (1.0, col("leaf_deep") * 1.1)]
    colorize(hull, lambda vi, co: ramp(core_ramp, clamp01(co.z / H_core)) * 0.7, pattern="leaves", facet=0.02)
    objs.append(hull)

    # Accents on the upper, outer leaves: berry clusters or little cupped blossoms,
    # set on the opaque middle of a visible card.
    if flavor != "plain":
        bvh = surface_of(cards)

        def find_spot(target_spread, min_gap, taken, near=None, min_up=0.6):
            for _ in range(600):
                d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(0.35, 1.0))).normalized()
                if d.z < min_up:
                    continue
                if near is None:
                    target = Vector((rng.uniform(-1, 1) * W_core * 0.3, rng.uniform(-1, 1) * W_core * 0.3, H * 0.4))
                else:
                    target = near + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)) * target_spread
                hit, _, poly, _ = bvh.ray_cast(target + d * 1.0, -d, 1.2)
                if hit is None or hit.z < 0.16 * S:
                    continue
                middle, size = card_meta[poly // 8]
                if (hit - middle).length > size * 0.3:
                    continue
                if any((hit - q).length < min_gap for q, _ in taken):
                    continue
                return hit, d
            return None

        if flavor == "berries":
            spots = []
            for _ in range(rng.randint(4, 5)):
                spot = find_spot(0, 0.1, spots)
                if spot:
                    spots.append(spot)
            highlight = col("#ff5a3a")     # palette eye_red: a glossy, brighter red on top of each berry
            room = (895 - gab.triangles()) // 8          # berries the budget still allows
            for i, (hit, d) in enumerate(spots):
                q = hit + d * 0.006
                side, nm = frame(d)
                n_berries = min(rng.randint(5, 7), room // (len(spots) - i))
                room -= n_berries
                for b in range(n_berries):
                    a = b * 2.39996 + rng.uniform(-0.3, 0.3)
                    rr = 0.025 * math.sqrt((b + 0.5) / n_berries)
                    radius = rng.uniform(0.013, 0.016)
                    at = q + (side * math.cos(a) + nm * math.sin(a)) * rr + d * rng.uniform(-0.002, 0.004)
                    berry = bead(f"berry{i}_{b}", at, radius, painted)
                    gab.smooth(berry, 80)
                    colorize(berry, lambda vi, co, zc=at.z, r=radius: ramp(
                        [(0, "leaf_red"), (0.6, "cap"), (1, highlight)], clamp01((co.z - zc) / (2 * r) + 0.5)),
                        facet=0.04)
                    objs.append(berry)
            print(f"bush: {len(spots)} berry clusters")
        else:
            groups, flowers = [], []
            for _ in range(rng.randint(4, 5)):
                spot = find_spot(0, 0.11, groups, min_up=0.35)
                if spot:
                    groups.append(spot)
            for hit, d in groups:
                flowers.append((hit, d))
                for _ in range(rng.randint(1, 2)):
                    spot = find_spot(0.05, 0.045, flowers, near=hit, min_up=0.35)
                    if spot:
                        flowers.append(spot)
            room = (880 - gab.triangles()) // 20
            for i, (hit, d) in enumerate(flowers[:room]):
                face = (d + Vector((0, 0, 1.2))).normalized()
                flower, part = blossom(f"blossom{i}", hit + d * 0.006, face, rng.uniform(0.024, 0.031), painted)
                shade = rng.uniform(0.94, 1.04)

                def petal_col(vi, co, part=part, shade=shade):
                    return {"eye": col("petal_yellow"), "base": col("plaster"),
                            "side": col("petal_white"), "tip": lerp(col("petal_white"), col("snow"), 0.6)}[part[vi]] \
                        * shade * (0.82 if vi == 0 else 1.0)
                colorize(flower, petal_col, facet=0.0)
                objs.append(flower)
    print(f"bush: {len(cards)} cards, {gab.triangles()} triangles before the join")
    return finish(objs, "bush", height=H)


# ── Fern ──

def frond_path(base, yaw, pitch, arc, length, segments, kink=None, tilt=None):
    """Points of an arching frond: it leaves the crown at `pitch` degrees and curls
    down by `arc` degrees toward the tip; kink=(t, degrees) snaps it partway. `tilt`
    (a rotation matrix) leans the whole crown; the path never dips below the ground."""
    pts = [base.copy()]
    p = base.copy()
    for i in range(segments):
        t = (i + 0.5) / segments
        elev = pitch - arc * t ** 1.4
        if kink and t > kink[0]:
            elev -= kink[1]
        e = math.radians(elev)
        step = length / segments
        d = Vector((math.cos(yaw) * math.cos(e), math.sin(yaw) * math.cos(e), math.sin(e)))
        if tilt is not None:
            d = tilt @ d
        p = p + d * step
        p.z = max(p.z, 0.006)
        pts.append(p.copy())
    return pts


def fern():
    painted, fern_mat = gab.painted(), gab.foliage("foliage_fern")
    objs = []
    H = rng.uniform(0.34, 0.4)
    L = H / 0.37
    amber = (gab.seed % 2 == 0)

    # The whole crown leans 8-14 degrees about one horizontal axis: one side stands
    # up, the other lies down.
    ax = rng.uniform(0, 2 * math.pi)
    tilt = Matrix.Rotation(math.radians(rng.uniform(8, 14)), 3, Vector((math.cos(ax), math.sin(ax), 0)))

    # Three sprays with 50-80 degree gaps between them instead of an even star.
    gaps = [math.radians(rng.uniform(50, 80)) for _ in range(3)]
    weights = [rng.uniform(0.8, 1.2) for _ in range(3)]
    room = 2 * math.pi - sum(gaps)
    spans = [room * w / sum(weights) for w in weights]
    g = rng.uniform(0, 2 * math.pi)
    groups = []
    for k in range(3):
        groups.append((g, g + spans[k]))
        g += spans[k] + gaps[k]

    def yaws(count, offset):
        """`count` yaws spread over the three sprays, roughly by their width."""
        per = [1] * 3
        for _ in range(count - 3):
            k = max(range(3), key=lambda k: spans[k] / per[k] + rng.uniform(0, 0.15))
            per[k] += 1
        out = []
        for k, (g0, g1) in enumerate(groups):
            for i in range(per[k]):
                f = (i + 0.5 + offset) / (per[k] + offset * 0.5)
                out.append(lerp(g0, g1, clamp01(f)) + rng.uniform(-0.12, 0.12))
        return out

    def add_frond(name, yaw, length, pitch, arc, wr, bright, dead=False, kink=None, young=False):
        base = tilt @ (Vector((math.cos(yaw), math.sin(yaw), 0)) * 0.02 + Vector((0, 0, 0.012)))
        pts = frond_path(base, yaw, pitch, arc, length, 5, kink, tilt)
        roll = math.radians(rng.uniform(-14, 14))
        sides = []
        for j, p in enumerate(pts):
            tan = (pts[min(j + 1, 5)] - pts[max(j - 1, 0)]).normalized()
            s = tilt @ Vector((math.sin(yaw), -math.cos(yaw), 0))     # front (side x tangent) faces up
            sides.append(Matrix.Rotation(roll, 3, tan) @ s)
        width = length * wr
        widths = [width * (0.75 if young else 1.0)] * len(pts)
        obj, ts = ribbon(name, pts, sides, widths, lift=-0.12, along="u", mat=fern_mat)

        def frond_col(vi, co, ts=ts):
            t = clamp01(ts[vi] * 0.75 + clamp01(co.z / H) * 0.45 + bright)
            if dead:
                c = ramp([(0, "leg"), (0.4, "hide_dark"), (0.75, "wood"), (1, "wood_light")], t * 0.8)
                return lerp(c, col("stem") * 0.9, 0.25)     # dry and a little ochre, never rust-red
            if kink:
                return ramp([(0, "needle_deep"), (0.3, "needle"), (0.6, "stem"), (0.85, "leaf"),
                             (1.0, "leaf_light")], t)
            return ramp([(0, "needle_deep"), (0.25, "needle"), (0.5, "leaf"), (0.75, "leaf_light"),
                         (0.92, "leaf_bright"), (1.1, "leaf_tip")], t)
        colorize(obj, frond_col, facet=0.05)
        # One low dome: each frond's upper side, bent outward and toward the sky.
        store_normals(obj, lambda vi, co, poly: poly.normal * 0.45 + UP * 0.4 + horizontal(co) * 0.35)
        objs.append(obj)

    # Outer fronds: long, low and arching; inner fronds: steeper and shorter, except
    # one or two that arch out over the outer ring.
    outer = yaws(rng.randint(7, 8), 0.0)
    dead_at = rng.randrange(len(outer)) if amber else -1
    for i, yaw in enumerate(outer):
        scale = rng.uniform(0.65, 1.1)
        if i == dead_at:
            add_frond(f"frond0_{i}", yaw, rng.uniform(0.26, 0.3) * L, rng.uniform(28, 38), rng.uniform(50, 70),
                      0.5, rng.uniform(-0.05, 0.05), dead=True)
            continue
        add_frond(f"frond0_{i}", yaw, rng.uniform(0.24, 0.28) * L * scale, rng.uniform(44, 56), rng.uniform(85, 105),
                  0.55, rng.uniform(-0.05, 0.05))
    inner = yaws(rng.randint(5, 6), 0.5)
    crossers = set(rng.sample(range(len(inner)), rng.randint(1, 2)))
    leader = min(set(range(len(inner))) - crossers)       # the tallest frond, nearly upright
    for i, yaw in enumerate(inner):
        if i == leader:
            add_frond(f"frond1_{i}", yaw, rng.uniform(0.37, 0.4) * L, rng.uniform(86, 89), rng.uniform(22, 30),
                      0.5, 0.16)
        elif i in crossers:
            add_frond(f"frond1_{i}", yaw, rng.uniform(0.36, 0.42) * L, rng.uniform(64, 72), rng.uniform(60, 75),
                      0.5, 0.1)
        else:
            add_frond(f"frond1_{i}", yaw, rng.uniform(0.3, 0.36) * L * rng.uniform(0.85, 1.1), rng.uniform(80, 88),
                      rng.uniform(25, 40), 0.5, 0.14 + rng.uniform(-0.05, 0.05))

    # Odd fronds break the rosette: a short young frond still rising, and on every
    # other fern one snapped partway so its tip hangs.
    yaw = rng.uniform(0, 2 * math.pi)
    add_frond("young", yaw, rng.uniform(0.13, 0.17) * L, rng.uniform(78, 86), rng.uniform(15, 30), 0.42, 0.22,
              young=True)
    if not amber:
        yaw = rng.uniform(0, 2 * math.pi)
        add_frond("broken", yaw, rng.uniform(0.24, 0.28) * L, rng.uniform(58, 66), rng.uniform(20, 30), 0.5,
                  0.0, kink=(rng.uniform(0.4, 0.55), rng.uniform(70, 95)))

    # A fiddlehead: a young frond still coiled, standing in the middle, big and pale
    # enough to read as a curl from the game camera.
    yaw = rng.uniform(0, 2 * math.pi)
    out = Vector((math.cos(yaw), math.sin(yaw), 0))
    base = out * 0.012
    hgt = H * rng.uniform(0.38, 0.48)
    top = base + out * 0.03 + Vector((0, 0, hgt))
    path = [base, lerp(base, top, 0.45) + out * 0.004, top]
    r0 = 0.032
    center = top + out * r0
    turns = 6.4
    coil = 7
    for s in range(1, coil + 1):
        th = turns * s / coil
        r = r0 * math.exp(-0.16 * th)
        path.append(center + (-out * math.cos(th) + UP * math.sin(th)) * r)
    radii = [0.0075, 0.0085, 0.01] + [0.01 * (1 - 0.45 * s / coil) for s in range(1, coil + 1)]
    radii[-1] = 0.0
    path = [tilt @ p for p in path]
    obj, ts = tube("fiddle", path, radii, sides=4, close_end=True, mat=painted)
    gab.smooth(obj, 80)
    colorize(obj, lambda vi, co, ts=ts: ramp([(0, "leaf"), (0.3, "leaf_light"), (1, "leaf_tip")], ts[vi]),
             facet=0.02)
    objs.append(obj)

    # A dark root crown so the fronds grow out of something.
    crown = gab.primitive("ico_sphere", subdivisions=1, radius=0.04, location=(0, 0, 0.0))
    crown.scale = (1, 1, 0.55)
    gab.apply_transform(crown)
    gab.assign(crown, painted)
    gab.uv_box(crown)
    gab.smooth(crown, 80)
    colorize(crown, lambda vi, co: ramp([(0, "leg"), (1, "wood_dark")], clamp01(co.z / 0.022)), pattern="bark")
    objs.append(crown)
    return finish(objs, "fern")


# ── Grass tuft ──

# Grass: a cool, darker base than the meadow (leaf_deep, the meadow's own hue), the
# palette grass in the middle, and tips stopping well short of the pale leaf_tip; all
# turned a little toward green against the warm sun, which yellows lit foliage.
GRASS_TOP = lerp(col("grass_light"), col("leaf_tip"), 0.35)
GRASS_RAMP = [(t, hue_shift(col(c) if isinstance(c, str) else c, 0.015, 0.05)) for t, c in
              [(0.0, col("leaf_deep") * 0.7), (0.22, "leaf_deep"), (0.5, "grass"), (0.8, "grass_light"), (1.0, GRASS_TOP)]]


def grass_card(name, base, yaw, height, width, lean_deg, mat, arch_deg=0.0, rows=(0.0, 0.15, 0.4, 0.7, 1.0),
               bright=0.0, v0=0.06, stops=GRASS_RAMP, taper=1.0):
    """One grass card, built as a twin (see twin()), leaning outward by `lean_deg`
    from vertical and arching over by `arch_deg` more toward the top. Its fronts
    carry normals bent toward the sky so it is lit like the ground it grows from.
    `taper` narrows the top row (1 keeps the card square)."""
    facing = Vector((math.cos(yaw), math.sin(yaw), 0))        # the way the card leans
    side = Vector((-facing.y, facing.x, 0))
    pts, p = [base.copy()], base.copy()
    for t0, t1 in zip(rows, rows[1:]):
        ang = math.radians(lean_deg + arch_deg * ((t0 + t1) / 2) ** 1.3)
        p = p + (facing * math.sin(ang) + UP * math.cos(ang)) * height * (t1 - t0)
        pts.append(p.copy())
    # front = side x tangent; make it the up-facing side
    tangent = (pts[-1] - pts[0]).normalized()
    if side.cross(tangent).z < 0:
        side = -side
    widths = [width * lerp(1.0, taper, t) for t in rows]
    obj, ts = ribbon(name, pts, [side] * len(pts), widths, along="v", mat=mat, vrange=(v0, 1.0), tvals=list(rows),
                     across=2)
    vmap = [lerp(v0, 1.0, t) for t in ts]
    colorize(obj, lambda vi, co: fit(ramp(stops, clamp01(ts[vi] + bright)) * tex_lift(vmap[vi], GRASS_TEX, 0.6, 0.65,
                                                                                      2.8)), facet=0.05)
    back = twin(obj)
    for o in (obj, back):
        store_normals(o, lambda vi, co, poly: UP * 0.75 + poly.normal * 0.3 + horizontal(co) * 0.25)
    return [obj, back]


def grass():
    grass_mat = gab.foliage("foliage_grass")
    objs = []
    H = rng.uniform(0.2, 0.27)
    seeded = gab.seed % 2 == 0
    # The heart: three crossed cards, upright and only slightly leaning.
    y0 = rng.uniform(0, 2 * math.pi)
    for k in range(3):
        yaw = y0 + math.radians(k * 60 + rng.uniform(-15, 15)) + (math.pi if rng.random() < 0.5 else 0.0)
        height = H * rng.uniform(0.85, 1.0)
        objs += grass_card(f"tuft{k}", Vector((0, 0, 0)), yaw, height, height * rng.uniform(0.6, 0.7),
                           rng.uniform(8, 18), grass_mat, arch_deg=rng.uniform(5, 15), bright=rng.uniform(-0.04, 0.04))
    # The fringe: two or three narrower cards arching outward like a fountain.
    n_out = 2 if seeded else 3
    s0 = rng.uniform(0, 2 * math.pi)
    for k in range(n_out):
        yaw = s0 + k * 2 * math.pi / n_out + rng.uniform(-0.4, 0.4)
        out = Vector((math.cos(yaw), math.sin(yaw), 0))
        height = H * rng.uniform(0.7, 0.85)
        objs += grass_card(f"fringe{k}", out * 0.012, yaw, height, height * 0.45, rng.uniform(25, 40), grass_mat,
                           arch_deg=rng.uniform(30, 45), bright=rng.uniform(0.0, 0.06), v0=0.1, taper=0.8)

    # Every other tuft has gone to seed: stalks nodding over, each carrying a warm
    # plume of spikelets big enough to read from the game camera.
    if seeded:
        painted = gab.painted()
        s0 = rng.uniform(0, 2 * math.pi)
        for k in range(3):
            yaw = s0 + k * 2.1 + rng.uniform(-0.3, 0.3)
            out = Vector((math.cos(yaw), math.sin(yaw), 0))
            side = Vector((-out.y, out.x, 0))
            tall = H * rng.uniform(1.05, 1.25)
            nod = math.radians(rng.uniform(25, 40))
            base = out * 0.008
            p1 = base + out * 0.014 + Vector((0, 0, tall * 0.55))
            p2 = p1 + out * 0.016 + Vector((0, 0, tall * 0.33))
            head_dir = (out * math.sin(nod + 0.25) + UP * math.cos(nod + 0.25)).normalized()
            stalk, ts = tube(f"seed_stalk{k}", [base, p1, p2], [0.0042, 0.004, 0.0036], sides=4, mat=painted)
            colorize(stalk, lambda vi, co, ts=ts: ramp([(0, "stem"), (0.4, "grass"), (1, "wood_light")], ts[vi]))
            gab.smooth(stalk, 80)
            objs.append(stalk)
            # spikelets alternate left and right along the head, smaller toward the tip
            hl = rng.uniform(0.045, 0.055)
            n_sp = 5
            spine = [p2 + head_dir * hl * (s / (n_sp - 1)) for s in range(n_sp)]
            for s, at in enumerate(spine):
                lr = 1 if s % 2 == 0 else -1
                ln = rng.uniform(0.022, 0.026) * (1 - 0.25 * s / n_sp)
                d = (head_dir * 0.8 + side * lr * 0.5 + UP * 0.1).normalized()
                tip = at + d * ln
                sd, sn = frame(d)
                r = 0.0035
                ring = [at + (sd * math.cos(a) + sn * math.sin(a)) * r for a in (0, 2.094, 4.189)]
                verts = ring + [tip]
                faces = [(0, 1, 3), (1, 2, 3), (2, 0, 3)]      # open at the base, where it sits on the stalk
                cen = (ring[0] + ring[1] + ring[2] + tip) / 4
                fixed = []
                for f in faces:
                    a, b, c = (verts[i] for i in f)
                    nrm = (b - a).cross(c - a)
                    fixed.append(f if nrm.dot((a + b + c) / 3 - cen) >= 0 else (f[0], f[2], f[1]))
                sp = make(f"spikelet{k}_{s}", verts, fixed, vert_uvs=[(v.x, v.z) for v in verts], mat=painted)
                colorize(sp, lambda vi, co: col("autumn_tip") if vi == 3 else col("wood_light"), pattern="thatch",
                         facet=0.06)
                gab.smooth(sp, 80)
                objs.append(sp)
    return finish(objs, "grass_tuft")


# ── Reeds ──

REED = lerp(col("olive"), col("leaf_deep"), 0.65)       # slightly olive, greener than straw


def reeds():
    painted, grass_mat = gab.painted(), gab.foliage("foliage_grass")
    objs = []
    H = rng.uniform(0.38, 0.43)

    # A low clump of grass cards round the foot, so the reeds grow out of the bank.
    a0 = rng.uniform(0, 2 * math.pi)
    foot_stops = [(0.0, "stem"), (0.35, REED), (1.0, "grass_light")]
    for i in range(2):
        yaw = a0 + i * math.pi + rng.uniform(-0.5, 0.5)
        hh = H * rng.uniform(0.32, 0.4)
        objs += grass_card(f"foot{i}", Vector((0, 0, 0)), yaw, hh, hh * 1.0, rng.uniform(15, 30), grass_mat,
                           arch_deg=15, rows=(0.0, 0.35, 1.0), stops=foot_stops, v0=0.2)

    # Cattails: slender stems bowing apart, a long velvety head lit on one side, a
    # pale collar where the thin spike leaves it.
    n_tails = rng.randint(2, 3)
    c0 = rng.uniform(0, 2 * math.pi)
    lit = Vector((-0.5, 0.4, 0.75)).normalized()
    head_tops = []
    for k in range(n_tails):
        yaw = c0 + k * 2 * math.pi / n_tails + rng.uniform(-0.4, 0.4)
        out = Vector((math.cos(yaw), math.sin(yaw), 0))
        side = Vector((-out.y, out.x, 0))
        base = out * rng.uniform(0.0, 0.015)
        head_len = rng.uniform(0.11, 0.13)
        head_r = rng.uniform(0.011, 0.013)
        spike = rng.uniform(0.03, 0.04)
        top_h = H * rng.uniform(0.86, 1.0)
        splay = math.radians(rng.uniform(4, 10))
        axis = (out * math.sin(splay) + UP * math.cos(splay)).normalized()
        stem_len = (top_h - head_len - spike) / axis.z
        h0 = base + axis * stem_len
        bow = side * rng.uniform(-0.01, 0.01) - out * 0.008
        stem_pts = [base, lerp(base, h0, 0.4) + bow, lerp(base, h0, 0.75) + bow * 0.6, h0 + axis * 0.008]
        stem, ts = tube(f"cattail_stem{k}", stem_pts, [0.0055, 0.005, 0.0045, 0.004], sides=3, mat=painted)
        colorize(stem, lambda vi, co, ts=ts: ramp([(0, col("stem") * 0.6), (0.4, "stem"), (1, "olive")], ts[vi]))
        gab.smooth(stem, 80)
        objs.append(stem)
        hp = [h0 - axis * 0.002, h0 + axis * 0.012, h0 + axis * head_len * 0.5, h0 + axis * (head_len - 0.012),
              h0 + axis * (head_len + 0.002)]
        hr = [0.0, head_r * 0.85, head_r * 1.0, head_r * 0.9, 0.0]
        head, ts = tube(f"cattail_head{k}", hp, hr, sides=6, close_start=True, close_end=True, mat=painted,
                        twist=0.2, uv_scale=3.0)

        def head_col(vi, co, ts=ts, h0=h0, axis=axis, head_len=head_len):
            rel = co - (h0 + axis * (ts[vi] * head_len))
            rel -= axis * rel.dot(axis)
            sun = clamp01(rel.normalized().dot(lit) * 0.5 + 0.5) if rel.length > 1e-6 else 0.5
            t = clamp01(0.3 * ts[vi] + 0.7 * sun)
            c = ramp([(0, "leg"), (0.4, "hide_dark"), (0.8, "wood_dark"), (1.0, "hide")], t)
            return lerp(c, col("wood_light"), 0.5 * smoothstep(0.55, 0.9, sun))
        colorize(head, head_col, pattern="cloth", facet=0.02)
        gab.smooth(head, 80)
        objs.append(head)
        top = h0 + axis * (head_len + spike)
        head_tops.append(top.z)
        sp = [h0 + axis * (head_len - 0.004), h0 + axis * (head_len + 0.007), top]
        spk, ts = tube(f"cattail_spike{k}", sp, [0.0052, 0.0024, 0.0], sides=4, close_end=True, mat=painted)
        colorize(spk, lambda vi, co, ts=ts: ramp([(0, "stalk"), (0.2, "wood_light"), (1, "wood")], ts[vi]),
                 facet=0.0)
        gab.smooth(spk, 80)
        objs.append(spk)

    # Reed blades: tapering strips cut from the middle of the grass card, so they
    # carry painted blades, soft alpha edges and the wind. They fan out into a V
    # fountain that shows its faces to the high camera; one or two snap and hang.
    budget = 398 - gab.triangles()
    b0 = rng.uniform(0, 2 * math.pi)
    kinks = set(rng.sample(range(3, 10), rng.randint(1, 2)))
    i = 0
    while True:
        yaw = b0 + i * 2.39996 + rng.uniform(-0.3, 0.3)
        out = Vector((math.cos(yaw), math.sin(yaw), 0))
        kink = i in kinks
        segs = 6 if kink else 4
        cost = 2 * (segs - 1) + 1
        if cost > budget:
            break
        budget -= cost
        base = out * rng.uniform(0.003, 0.03)
        height = H * rng.uniform(0.7, 1.12)
        lean = math.radians(rng.uniform(6, 20))
        curve = rng.uniform(0.05, 0.15)
        d0 = (out * math.sin(lean) + UP * math.cos(lean)).normalized()
        if kink:
            tk = rng.uniform(0.55, 0.75)
            bend = math.radians(rng.uniform(40, 70))
        pts, p = [base.copy()], base.copy()
        for j in range(1, segs + 1):
            t0, t1 = (j - 1) / segs, j / segs
            d = (d0 + out * curve * t1 * 2).normalized()
            if kink and t1 > tk:
                # past the kink the blade folds outward and hangs a little more each step
                ang = bend + math.radians(15) * (t1 - tk) / (1 - tk)
                d = (d0 * math.cos(ang) + out * math.sin(ang)).normalized()
            p = p + d * height * (t1 - t0)
            pts.append(p.copy())
        side = Vector((-out.y, out.x, 0))
        twist = rng.uniform(-0.5, 0.5)
        sides = [Matrix.Rotation(twist * j / segs, 3, UP) @ side for j in range(segs + 1)]
        w = rng.uniform(0.018, 0.028)
        widths = [w * (1 - 0.55 * (j / segs) ** 1.4) for j in range(segs + 1)]
        obj, ts = ribbon(f"blade{i}", pts, sides, widths, along="v", tip=True, mat=grass_mat, band=(0.41, 0.51),
                         vrange=(0.03, 0.9), across=2)
        r = rng.random()
        tipc = "autumn_tip" if r < 0.08 else "wood_light" if r < 0.22 else "grass_light"
        bright = rng.uniform(-0.06, 0.06)
        vmap = [lerp(0.03, 0.9, t) for t in ts]
        colorize(obj, lambda vi, co, ts=ts, tipc=tipc, bright=bright, vmap=vmap: fit(ramp(
            [(0, col("stem") * 0.85), (0.25, "stem"), (0.5, REED), (0.8, REED), (1, tipc)],
            clamp01(ts[vi] + bright)) * tex_lift(vmap[vi], GRASS_TEX, 0.6, 0.5, 2.2)), facet=0.04)
        gab.smooth(obj, 89)
        objs.append(obj)
        i += 1
    print(f"reeds: {n_tails} cattails (heads up to {max(head_tops):.2f}), {i} blades")
    return finish(objs, "reeds")


BUILDERS = {"bush": bush, "fern": fern, "grass": grass, "reeds": reeds}
result = BUILDERS[KIND]()
print(f"undergrowth: {KIND} seed {gab.seed}: {gab.triangles()} triangles")
