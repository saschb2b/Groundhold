"""Scuttler: a fast beetle creep for Lantern Hollow.

    godot-agent asset blender . art_src/blender/scuttler.py --to res://models/creeps/scuttler.glb \
        --seed 1 --review --no-import

A small glossy purple beetle, about 0.22 tall and 0.5 long (the game draws it at
1.5x). Ribbed elytra split down the middle, with pale lips and painted highlight
strokes; a green firefly lantern with a hot tip pokes out from under the parted tips.
A two-lobed pronotum shield with a dark median line carrying the elytral seam to the
head, a pale rim and softer highlight crescents. A raised head with a short horn,
hooked mandibles, clubbed antennae and four glowing green eyes in dark sockets, the
big ones with a hot core and a catchlight. Six dark, matte, bowed legs ending in pale
hooked claws, kept below the shell in value.

Every part is built from parametric rings, so colours are painted per vertex:
dark cool undersides, bright crests, highlight decals with a crisp edge and a soft
centre. The metal pattern runs along the shell. The result is one skinned mesh with
three materials (painted, creep_eyes_green, creep_eyes_green_core).

`--param mask=1` builds a measurement copy instead (never ship it): legs, elytral
crest, highlight strokes and crescents in flat emissive key colours, everything else
black, so an in-game capture of it masks the same pixels in a capture of the real
model (the game's scenarios are deterministic).

It has a 20-frame looping "walk": a tripod gait (L1 R2 L3 against R1 L2 R3) solved
with two-bone IK on the ankle, plus a tarsus bone per leg that keeps the foot flat
on the ground while planted (and curls it in the swing), so every planted claw slides
straight back with the ground at exactly the body's pace, nothing skating. Body,
head, jaws and antennae move at most once or twice per cycle, so the game's
~3x playback reads as skittering, not buzzing. The build prints the body speed
the cycle matches; game.gd's CREEPS.scuttler "stride" should be that speed
times the game's 1.5x scale (0.6075 for this build).

Front faces -Y, Z up, the feet stand on z = 0 at the origin.
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import gab

rng = gab.rng
UP = Vector((0.0, 0.0, 1.0))
G = 0.9  # the whole beetle is modelled a little large, then scaled by G before rigging


# ── Colour ──

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


COOL = hx("#26406e")  # palette: roof_dark, a cool tint for the lowest flanks
# The game's sun is warm (and the grade saturates), which pushes purple toward magenta.
# The shell colours are cooled a fifth of the way toward roof_dark so the beetle still
# reads violet in game; each stays within the palette check of its source colour.
SHELL = mix(hx("#4a2f5a"), COOL, 0.2)        # palette: shell
SHELL_LIGHT = mix(hx("#6e4a82"), COOL, 0.2)  # palette: shell_light
SHELL_DARK = mix(hx("#2a1e24"), COOL, 0.2)   # palette: shell_dark
RIM = hx("#9a6ac0")          # palette: petal_purple
RUNE = hx("#d0a0ff")         # palette: rune, a cool lilac for highlights
SPIKE = hx("#d8c8a8")        # palette: spike
TUSK = hx("#efe6d6")         # palette: tusk
EYE = hx("#9cff5a")          # palette: eye_green
EYE_CORE = hx("#c3e070")     # palette: leaf_tip, the hot core of the big eyes
BLUE_LIGHT = hx("#5a7ec0")   # palette: roof_blue_light
# the painted highlight strokes, cooled toward blue so the warm sun and grade leave
# them violet-white instead of pink
GLOSS = mix(mix(RIM, RUNE, 0.6), BLUE_LIGHT, gab.param("gloss_cool", 0.35))
GLOSS_EDGE = mix(SHELL_LIGHT, RIM, 0.5)  # their crisp outer edge
CREST = SHELL_LIGHT          # the lit crest of the shell
LIP = mix(RIM, RUNE, 0.3)    # the pale rims
KNEE = mix(SHELL_LIGHT, RIM, 0.5)  # muted knee caps
TIP = mix(RIM, SPIKE, 0.3)   # pale tips of horn, spurs and claws (close to palette: rune)
# Legs are matte ('plain') on a metallic shell, and matte paint renders about twice as
# bright as the same colour on metal, so the leg paint stays well below the shell's.
LEG_K = gab.param("leg_value", 0.62)
MASK = gab.param("mask", 0)

PATTERN = {name: (i + 0.5) / 16 for i, name in enumerate(gab.PATTERNS)}


# ── Parts: vertex, colour and UV lists turned into mesh objects ──

PARTS = []


# --param mask=1: flat emissive key colours for measuring the in-game value hierarchy
MASK_COLOURS = {"leg": (0.6, 0.0, 0.0), "crest": (0.0, 0.0, 0.6), "gloss": (0.0, 0.6, 0.6),
                "crescent": (0.6, 0.0, 0.6), "other": None}


def mask_material(kind: str) -> bpy.types.Material:
    mat = gab.material(f"mask_{kind}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    bsdf.inputs["Roughness"].default_value = 1.0
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.0
    colour = MASK_COLOURS[kind]
    if colour:
        bsdf.inputs["Emission Color"].default_value = (*colour, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 1.0
    return mat


class Part:
    """One rigid piece of the beetle, skinned to one bone. Open parts (decals) are
    wound to face `outward(centre)` when that is given. `mask` names the key colour
    of the measurement build; vertices added with tag="crest" key as the crest."""

    def __init__(self, name: str, bone: str, pattern: str = "metal", material: str = "painted",
                 smooth: float | None = 55.0, mottle: float = 0.035, closed: bool = True, outward=None,
                 mask: str = "other"):
        self.name, self.bone, self.pattern, self.material = name, bone, pattern, material
        self.smooth, self.mottle, self.closed, self.outward = smooth, mottle, closed, outward
        self.mask = mask
        self.verts, self.cols, self.uvs, self.faces, self.tags = [], [], [], [], []
        PARTS.append(self)

    def add(self, co, col, uv=None, tag=None) -> int:
        co = tuple(co)
        self.verts.append(co)
        self.cols.append(tuple(col))
        self.uvs.append(tuple(uv) if uv is not None else (co[0], co[1]))
        self.tags.append(tag)
        return len(self.verts) - 1

    def face(self, *idx) -> None:
        clean = []
        for i in idx:
            if i not in clean:
                clean.append(i)
        if len(clean) >= 3:
            self.faces.append(tuple(clean))

    def ring_to_ring(self, a: list, b: list, closed: bool = True) -> None:
        """Quads between two rings of equal length, or a fan when one is a point."""
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
        if self.closed or self.outward:
            bm = bmesh.new()
            bm.from_mesh(mesh)
            if self.closed:
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            else:
                bm.normal_update()
                flip = [f for f in bm.faces if f.normal.dot(self.outward(f.calc_center_median())) < 0]
                bmesh.ops.reverse_faces(bm, faces=flip)
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
        if MASK:
            gab.assign(obj, mask_material(self.mask))
            if any(t == "crest" for t in self.tags):
                mesh.materials.append(mask_material("crest"))
                for poly in mesh.polygons:
                    if all(self.tags[v] == "crest" for v in poly.vertices):
                        poly.material_index = 1
        elif self.material == "painted":
            gab.assign(obj, gab.painted())
        else:
            gab.assign(obj, bpy.data.materials[self.material])
        if self.smooth is None:
            gab.flat(obj)
        else:
            gab.smooth(obj, self.smooth)
        group = obj.vertex_groups.new(name=self.bone)
        group.add(list(range(len(self.verts))), 1.0, "REPLACE")
        return obj


# ── Shape builders ──

def tube(part: Part, pts, radii, sides: int = 6, col=None, squash: float = 1.0, ref_up=UP,
         cap_start: bool = True, cap_end: bool = True) -> None:
    """A tapered tube along a polyline (parallel-transported frames). A radius of 0
    ends in a point. `squash` flattens the tube along its up direction. col(t, up)
    gives the colour at length fraction t for a surface facing `up` (-1..1)."""
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
    up = Vector(ref_up)
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
            rings.append([part.add(pts[i], col(t, tangents[i].z), (0.0, lengths[i]))])
            continue
        ring = []
        for k in range(sides):
            a = math.pi + 2 * math.pi * k / sides  # the UV seam sits underneath
            d = normal * math.cos(a) * squash + binormal * math.sin(a)
            facing = (normal * math.cos(a) + binormal * math.sin(a)).z
            ring.append(part.add(pts[i] + d * r, col(t, facing), ((a - math.pi) * r, lengths[i])))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        part.ring_to_ring(a, b)
    if cap_start and len(rings[0]) > 1:
        c = part.add(pts[0] - tangents[0] * radii[0] * 0.35, col(0.0, -1.0), (0.0, 0.0))
        part.ring_to_ring([c], rings[0])
    if cap_end and len(rings[-1]) > 1:
        c = part.add(pts[-1] + tangents[-1] * radii[-1] * 0.35, col(1.0, 0.0), (0.0, total))
        part.ring_to_ring(rings[-1], [c])


def ellipsoid(part: Part, center, radii, segs: int, rings: int, col, rot: Matrix | None = None) -> None:
    """A UV ellipsoid with its poles on the local Y axis (front/back). col(n) gets the
    unit normal in world orientation."""
    rot = rot or Matrix.Identity(3)
    c = Vector(center)
    rx, ry, rz = radii

    def point(lat, lon):
        # lat 0 = front pole (-Y), pi = back pole (+Y)
        n = Vector((math.sin(lat) * math.cos(lon), -math.cos(lat), math.sin(lat) * math.sin(lon)))
        p = Vector((n.x * rx, n.y * ry, n.z * rz))
        return c + rot @ p, (rot @ n).normalized()

    front_p, front_n = point(0.0, 0.0)
    back_p, back_n = point(math.pi, 0.0)
    front = part.add(front_p, col(front_n))
    rows = []
    for j in range(1, rings):
        lat = math.pi * j / rings
        row = []
        for k in range(segs):
            lon = -math.pi / 2 + 2 * math.pi * k / segs  # seam underneath
            p, nrm = point(lat, lon)
            row.append(part.add(p, col(nrm), (lon * max(rx, rz), p.y)))
        rows.append(row)
    back = part.add(back_p, col(back_n))
    part.ring_to_ring([front], rows[0])
    for a, b in zip(rows, rows[1:]):
        part.ring_to_ring(a, b)
    part.ring_to_ring(rows[-1], [back])


def cone(part: Part, base, tip, radius: float, col_base, col_tip, sides: int = 3, cap: bool = True) -> None:
    base, tip = Vector(base), Vector(tip)
    axis = (tip - base).normalized()
    u = axis.orthogonal().normalized()
    v = axis.cross(u)
    ring = [part.add(base + (u * math.cos(2 * math.pi * k / sides) + v * math.sin(2 * math.pi * k / sides)) * radius,
                     col_base) for k in range(sides)]
    t = part.add(tip, col_tip)
    part.ring_to_ring(ring, [t])
    if cap:
        c = part.add(base - axis * radius * 0.5, col_base)
        part.ring_to_ring([c], ring)


def strip(part: Part, rows, col) -> None:
    """A decal sheet from rows of points (each row the same length); col(i, j)."""
    idx = [[part.add(p, col(i, j)) for j, p in enumerate(row)] for i, row in enumerate(rows)]
    for a, b in zip(idx, idx[1:]):
        for j in range(len(a) - 1):
            part.face(a[j], a[j + 1], b[j + 1], b[j])


def along(pts, values, f: float):
    """The point, direction and interpolated value at length fraction f of a polyline."""
    pts = [Vector(p) for p in pts]
    lengths = [0.0]
    for a, b in zip(pts, pts[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    target = f * lengths[-1]
    for i in range(1, len(pts)):
        if lengths[i] >= target or i == len(pts) - 1:
            seg = lengths[i] - lengths[i - 1]
            u = min(1.0, (target - lengths[i - 1]) / seg) if seg else 0.0
            return (pts[i - 1].lerp(pts[i], u), (pts[i] - pts[i - 1]).normalized(),
                    values[i - 1] + (values[i] - values[i - 1]) * u)


# ── Variation from the seed ──

V = {
    "mandible": rng.uniform(0.92, 1.0),
    "antenna_reach": rng.uniform(0.92, 1.08),
    "antenna_lift": rng.uniform(-0.008, 0.012),
    "eye": rng.uniform(0.95, 1.08),
    "gloss": rng.uniform(0.85, 1.0),
    "horn": rng.uniform(0.85, 1.2),
    "horn_curl": rng.uniform(-0.004, 0.006),
}

# ── Elytra: two glossy halves split down the middle ──

SEAM = 0.0045
EY0, EY1 = -0.08, 0.236


def e_width(p: float) -> float:
    if p < 0.3:
        return 0.103 + 0.016 * math.sin(p / 0.3 * math.pi / 2)
    return 0.119 * max(0.0, 1 - ((p - 0.3) / 0.7) ** 2.2) ** 0.5


def e_height(p: float) -> float:
    if p < 0.38:
        return 0.086 + 0.038 * math.sin(p / 0.38 * math.pi / 2)
    return 0.124 * max(0.0, 1 - ((p - 0.38) / 0.66) ** 2) ** 0.6


def e_rim(p: float) -> float:
    return 0.114 + 0.018 * p ** 2


def e_seam(p: float) -> float:
    return SEAM + 0.011 * smoothstep(0.5, 1.0, p)  # the tips part a little


# cross-section from the inner wall over the crest to the tucked-under rim:
# (lateral fraction of the width, kind); dome kinds take their height from
# e_dome(), with ribs raised and grooves sunk; the others carry their own height.
E_PROFILE = [
    (0.0, "wall"), (0.0, "inner"), (0.045, "bead"), (0.1, "groove"), (0.2, "top"), (0.31, "crest"),
    (0.43, "top"), (0.52, "groove"), (0.58, "rib"), (0.66, "side"), (0.73, "groove"), (0.79, "rib"),
    (0.87, "side"), (0.94, "side"), (1.0, "low"), (1.06, "lip"), (1.045, "lip"), (0.95, "under"), (0.76, "under"),
]
E_FIXED = {"wall": 0.52, "inner": 0.84}
E_BELOW = {"lip": (-0.012, -0.022), "under": (-0.026, -0.018)}  # metres below the rim line


def e_dome(q: float, kind: str) -> float:
    k = max(0.0, 1 - ((q - 0.3) / 0.74) ** 2) ** 0.7
    return k + {"rib": 0.035, "groove": -0.02, "bead": 0.02}.get(kind, 0.0)


def e_point(s: int, p: float, q: float, kind: str = "side", n: int = 0) -> Vector:
    """A point of the elytron cross-section at length fraction p."""
    w, h, zr = e_width(p), e_height(p), e_rim(p)
    x = s * (e_seam(p) + q * w)
    if kind in E_FIXED:
        z = zr + E_FIXED[kind] * h
    elif kind in E_BELOW:
        z = zr + E_BELOW[kind][n]
    else:
        z = zr + e_dome(q, kind) * h
    return Vector((x, EY0 + (EY1 - EY0) * p, z))


def elytron_colour(p: float, q: float, kind: str) -> tuple:
    if kind == "wall":
        return SHELL_DARK
    if kind == "under":
        return mix(SHELL_DARK, SHELL, 0.35)
    if kind == "lip":
        return mix(SHELL_LIGHT, LIP, 0.9)
    if kind == "inner":
        return mix(SHELL_LIGHT, LIP, 0.65)
    # dome: bright crest, darker and cooler down the flanks and toward the tail,
    # shadowed where it tucks under the pronotum. The highlight is a decal.
    side = smoothstep(0.4, 1.0, q)
    c = mul(mix(mul(CREST, 1.12), mix(SHELL, SHELL_DARK, 0.45), side), 0.9)
    c = mix(c, mix(SHELL_DARK, COOL, 0.5), 0.6 * smoothstep(0.6, 1.0, q))
    c = mix(c, mul(SHELL, 0.8), smoothstep(0.6, 1.0, p) * 0.6)
    if kind == "rib":
        c = mix(c, mul(CREST, 1.25), 0.85)
    if kind == "groove":
        c = mul(c, 0.45)
    if kind == "bead":
        c = mix(c, SHELL_LIGHT, 0.5)
    if kind == "low":  # a dark band just inside the pale lip
        c = mix(c, SHELL_DARK, 0.5)
    return mul(c, 0.7 + 0.3 * smoothstep(0.0, 0.14, p))


def elytron(s: int) -> None:
    part = Part(f"elytron_{'L' if s > 0 else 'R'}", "body", mottle=0.05, mask="other")
    rows = []
    n_rings = 10
    for i in range(n_rings):
        t = i / n_rings
        p = 1 - (1 - t) ** 1.45
        row, arc, prev = [], 0.0, None
        count = {}
        for q, kind in E_PROFILE:
            co = e_point(s, p, q, kind, count.get(kind, 0))
            count[kind] = count.get(kind, 0) + 1
            if prev is not None:
                arc += (co - prev).length
            prev = co
            # the crest: the lit upper dome between the seam bead and the first side rib
            tag = "crest" if kind in ("bead", "groove", "top", "crest", "rib") and 0.04 < q < 0.6 else None
            row.append(part.add(co, elytron_colour(p, q, kind), (arc, co.y), tag))
        rows.append(row)
    tip = part.add((s * (SEAM + 0.017), EY1 + 0.008, e_rim(1.0) + 0.012), mix(SHELL, SHELL_LIGHT, 0.3), (0.0, EY1))
    for a, b in zip(rows, rows[1:]):
        part.ring_to_ring(a, b)
    part.ring_to_ring(rows[-1], [tip])
    part.face(*reversed(rows[0]))  # front cap, under the pronotum


GLOSS_FALLOFF = (0.0, 0.62, 1.0, 0.62, 0.0)  # edge to centre to edge, across a stroke


def elytron_gloss(s: int) -> None:
    """A painted highlight stroke over each shoulder, a decal floating just above the
    shell: matte, so the metal reflections cannot wash it out. Five columns: a crisp
    mid-tone edge falling in to one bright centre line."""
    part = Part(f"gloss_{'L' if s > 0 else 'R'}", "body", pattern="plain", smooth=40.0, mottle=0.02,
                closed=False, outward=lambda c: c - Vector((0.0, c.y, 0.06)), mask="gloss")
    g = V["gloss"]
    rows = []
    steps = 6
    for i in range(steps + 1):
        u = i / steps
        p = 0.07 + 0.47 * u
        half = 0.095 * math.sin(math.pi * min(1.0, u * 1.25)) ** 0.7 + 0.008  # a tapered brush stroke
        qc = 0.31 - 0.03 * u
        row = []
        for q in (qc - half * 0.8, qc - half * 0.4, qc, qc + half * 0.5, qc + half):
            point = e_point(s, p, q, "top")
            nrm = (point - Vector((s * 0.02, point.y, 0.05))).normalized()
            row.append(point + nrm * 0.0016)
        rows.append(row)

    def col(i, j):
        u = i / steps
        peak = mix(GLOSS, mix(RIM, SHELL_LIGHT, 0.3), smoothstep(0.35, 1.0, u))  # fades toward the tail
        return mul(mix(GLOSS_EDGE, peak, GLOSS_FALLOFF[j]), g)

    strip(part, rows, col)


# ── Pronotum: the shield behind the head ──

PRO_C = Vector((0.0, -0.106, 0.214))  # centre (x, y) and top height


def pro_boundary(phi):
    c, s = math.cos(phi), math.sin(phi)
    n = 2.6
    ux = math.copysign(abs(c) ** (2 / n), c)
    uy = math.copysign(abs(s) ** (2 / n), s)
    hw = 0.09 + 0.024 * uy
    dx = ux * hw * (1 + 0.07 * math.exp(-((uy - 0.75) / 0.2) ** 2))  # flared back corners
    dy = uy * 0.064
    if uy < 0:
        dy += 0.016 * math.exp(-(ux / 0.5) ** 2) * (-uy)  # notch the head sits in
    return dx, dy, ux, uy


def pro_rim_z(uy):
    return 0.122 + 0.082 * max(0.0, uy) ** 1.6


def pro_relief(r: float, ux: float) -> float:
    """Two lobes either side of a median groove, fading out toward the rim."""
    r = min(r, 1.0)
    return 0.008 * max(0.0, 1 - r * r) * (smoothstep(0.1, 0.5, abs(ux)) - 0.6 * math.exp(-(ux / 0.12) ** 2))


def pro_point(r: float, phi: float) -> Vector:
    dx, dy, ux, uy = pro_boundary(phi)
    zr = pro_rim_z(uy)
    z = zr + (PRO_C.z - zr) * max(0.0, 1 - min(r, 1.0) ** 2.4) ** 0.5 + pro_relief(r, ux)
    return Vector((PRO_C.x + r * dx, PRO_C.y + r * dy, z))


# 16 even spokes plus two either side of the median line, so the groove stays narrow
PRO_PHIS = sorted([2 * math.pi * k / 16 for k in range(16)] + [math.radians(a) for a in (80, 100, 260, 280)])


def pronotum() -> None:
    part = Part("pronotum", "body", mottle=0.05)

    def colour(r, ux, uy, kind):
        if kind == "lip":
            return mix(SHELL_LIGHT, LIP, 0.8)
        if kind == "under":
            return SHELL_DARK
        c = mix(mul(CREST, 1.05), mix(SHELL, SHELL_DARK, 0.35), smoothstep(0.3, 1.0, r))
        c = mul(c, 1.0 - 0.25 * smoothstep(-0.3, -1.0, uy) * smoothstep(0.5, 1.0, r))  # shadowed over the head
        # the dark median line carries the elytral seam forward to the head
        c = mix(c, mix(SHELL_DARK, SHELL, 0.35), math.exp(-(ux / 0.1) ** 2) * (1.0 - 0.3 * smoothstep(0.85, 1.0, r)))
        if r > 0.9:  # a dark band just inside the pale lip
            c = mix(c, SHELL_DARK, 0.55)
        return c

    center = part.add(PRO_C + Vector((0, 0, pro_relief(0.0, 0.0))), colour(0.0, 0.0, 0.0, "dome"), (PRO_C.x, PRO_C.y))
    rings = []
    for r in (0.25, 0.48, 0.68, 0.84, 0.95, 1.0, 1.035, 0.9):
        ring = []
        for phi in PRO_PHIS:
            dx, dy, ux, uy = pro_boundary(phi)
            zr = pro_rim_z(uy)
            co = pro_point(r, phi)
            kind = "dome" if r < 1.0 else "lip"
            if r > 1.0:
                co.z = zr - 0.005
            if len(rings) == 7:  # tucked under
                co.z = zr - 0.02
                kind = "under"
            ring.append(part.add(co, colour(min(r, 1.0), ux, uy, kind), (co.x, co.y)))
        rings.append(ring)
    part.ring_to_ring([center], rings[0])
    for a, b in zip(rings, rings[1:]):
        part.ring_to_ring(a, b)
    bottom = part.add((PRO_C.x, PRO_C.y, 0.1), SHELL_DARK)
    part.ring_to_ring(rings[-1], [bottom])


def pronotum_gloss() -> None:
    """Two highlight crescents following the shield's flanks, riding on the lobes: a
    crisp edge, a brighter centre line, and a fifth dimmer than the wing-case strokes
    so they do not compete with them."""
    part = Part("pronotum_gloss", "body", pattern="plain", smooth=40.0, mottle=0.02, closed=False,
                outward=lambda c: c - Vector((PRO_C.x, PRO_C.y, 0.08)), mask="crescent")
    g = V["gloss"] * 0.8
    for s in (1, -1):
        rows = []
        steps = 5
        for i in range(steps + 1):
            u = i / steps
            phi = (0.0 if s > 0 else math.pi) + s * math.radians(-58 + 110 * u)  # front-side round to the back
            w = 0.14 * math.sin(math.pi * u) ** 0.8 + 0.01
            rin = 0.64 - 0.04 * u
            lift = Vector((0, 0, 0.0018))
            rows.append([pro_point(rin + w * f, phi) + lift for f in (0.0, 0.45, 1.0)])

        def col(i, j):
            peak = mix(GLOSS, RIM, 0.25 + 0.5 * abs(i / steps - 0.4))
            return mul(mix(GLOSS_EDGE, peak, (0.0, 1.0, 0.0)[j]), g)

        strip(part, rows, col)


# ── Abdomen: banded segments under the elytra, peeking out at the tail ──

def abdomen() -> None:
    """Banded sternites under the elytra (the hidden middle is a single span), ending
    in a glowing firefly lantern that pokes out from under the parted tips."""
    part = Part("abdomen", "body", mottle=0.03)
    # sternite plates: each band swells to a lighter lip, then steps in
    ys = [-0.075, 0.1, 0.14, 0.152, 0.18, 0.192, 0.212, 0.218]
    rs = [0.06, 0.085, 0.078, 0.07, 0.068, 0.058, 0.054, 0.0]
    zs = [0.108, 0.106, 0.11, 0.111, 0.114, 0.116, 0.119, 0.122]
    bands = {2, 4, 6}

    def col_for(i):
        def col(t, up):
            c = mix(SHELL_DARK, SHELL, smoothstep(-0.8, 0.6, up))
            if i in bands:
                c = mix(c, mix(SHELL_LIGHT, RIM, 0.4), 0.65 * smoothstep(-0.6, 0.4, up) + 0.15)
            return c
        return col

    def section(target: Part, ys, rs, zs, col_for, sides: int, flat: float) -> list:
        rings = []
        for i, (y, r, z) in enumerate(zip(ys, rs, zs)):
            col = col_for(i)
            if r <= 0:
                rings.append([target.add((0, y, z), col(1, 0), (0, y))])
                continue
            ring = []
            for k in range(sides):
                a = math.pi / 2 + 2 * math.pi * k / sides
                x, dz = math.cos(a) * r, math.sin(a) * r * flat
                ring.append(target.add((x, y, z + dz), col(0, math.sin(a)), (a * r, y)))
            rings.append(ring)
        for a, b in zip(rings, rings[1:]):
            target.ring_to_ring(a, b)
        return rings

    rings = section(part, ys, rs, zs, col_for, 8, 0.52)
    c = part.add((0, ys[0] - 0.01, zs[0]), SHELL_DARK)
    part.ring_to_ring([c], rings[0])

    # the lantern: the last segments glow, rising into the gap between the wing tips
    # and reaching a little past them, so it reads from above and behind
    lamp = Part("lantern", "body", material="creep_eyes_green", smooth=70.0, mottle=0.0)
    ly = [0.204, 0.222, 0.238]
    lr = [0.044, 0.042, 0.034]
    lz = [0.12, 0.124, 0.13]
    rings = section(lamp, ly, lr, lz, lambda i: (lambda t, up: EYE), 8, 0.62)
    c = lamp.add((0, ly[0] - 0.004, lz[0]), EYE)
    lamp.ring_to_ring([c], rings[0])
    # its tip burns hotter, like the eyes' cores
    tip = Part("lantern_tip", "body", material="creep_eyes_green_core", smooth=70.0, mottle=0.0)
    section(tip, [0.238, 0.25, 0.257], [0.034, 0.022, 0.0], [0.13, 0.134, 0.136],
            lambda i: (lambda t, up: EYE_CORE), 8, 0.62)


# ── Head, eyes, mandibles, antennae ──

HEAD_C = Vector((0.0, -0.196, 0.14))
HEAD_R = (0.061, 0.056, 0.047)
HEAD_ROT = Matrix.Rotation(math.radians(14), 3, "X")


def H(x: float, y: float, z: float) -> Vector:
    """A point relative to the head centre, so the face moves with the head."""
    return HEAD_C + Vector((x, y, z))


def head() -> None:
    part = Part("head", "head")

    def col(n):
        c = mix(mix(SHELL_DARK, SHELL, 0.4), mul(SHELL, 1.15), smoothstep(-0.7, 0.5, n.z))
        c = mix(c, mul(SHELL_LIGHT, 1.1), 0.75 * smoothstep(0.3, 1.0, n.z) * smoothstep(0.45, -0.5, n.y))
        return mix(c, SHELL_DARK, 0.75 * smoothstep(0.4, 0.85, n.y))  # dark contact band at the neck

    ellipsoid(part, HEAD_C, HEAD_R, 10, 6, col, HEAD_ROT)
    # clypeus: a flat plate over the jaws
    plate = Part("clypeus", "head")
    tube(plate, [H(0, -0.022, 0.023), H(0, -0.046, 0.017), H(0, -0.066, 0.004)], [0.034, 0.029, 0.017], sides=6,
         squash=0.32, col=lambda t, up: mix(mix(SHELL, SHELL_LIGHT, 0.6 * smoothstep(-0.2, 0.8, up)),
                                            SHELL_DARK, smoothstep(0.0, -0.8, up)))
    # a short horn curling up from the crown
    horn = Part("horn", "head", pattern="plain", smooth=80.0)
    k, curl = V["horn"], V["horn_curl"]
    base = H(0, -0.024, 0.032)
    tube(horn, [base, base + Vector((0, -0.016 * k, 0.026 * k)), base + Vector((0, -0.01 * k + curl, 0.047 * k))],
         [0.0125, 0.0078, 0.0], sides=5, squash=0.85, cap_end=False,
         col=lambda t, up: mix(mix(SHELL_DARK, SHELL_LIGHT, smoothstep(0.0, 0.5, t)), TIP, smoothstep(0.55, 1.0, t)))


BIG_EYE = (0.051, -0.019, 0.02)  # relative to the head centre
SMALL_EYE = (0.024, -0.043, 0.037)


EYE_TILT = Vector((0.0, -0.3, 0.6))     # each eye bulges up and forward, toward the camera
CORE_LIFT = Vector((0.0, -0.45, 0.45))  # the core sits on the eye's upper front
SHINE_DIR = Vector((0.0, 0.3, 1.0))     # the catchlight on its top, a little back


def eyes() -> None:
    part = Part("eyes", "head", material="creep_eyes_green", smooth=60.0, mottle=0.0)
    cores = Part("eye_cores", "head", material="creep_eyes_green_core", smooth=60.0, mottle=0.0)
    sockets = Part("eye_sockets", "head", pattern="plain", smooth=60.0, mottle=0.02)
    shine = Part("eye_shine", "head", pattern="plain", smooth=None, mottle=0.0, closed=False,
                 outward=lambda c: c - HEAD_C)
    k = V["eye"] * 1.2
    for s in (1, -1):
        # the eye bulges out of a slightly larger dark socket sunk into the head, which
        # shows as a dark ring around the glow
        # the socket hides the half of the eye facing away from `n_out`, so tilting the
        # bulge up keeps the glowing cap, its core and its catchlight in the camera's view
        c = H(s * BIG_EYE[0], BIG_EYE[1], BIG_EYE[2])
        r = Vector((0.021 * k, 0.025 * k, 0.022 * k))
        n_out = ((c - HEAD_C).normalized() + EYE_TILT).normalized()
        out = n_out * sum(r) / 3
        centre = c + out * 0.28
        ellipsoid(sockets, c - out * 0.15, r * 1.2, 8, 4, lambda n: mix(SHELL_DARK, SHELL, 0.25))
        ellipsoid(part, centre, r, 8, 4, lambda n: EYE)

        def on_eye(direction: Vector, depth: float) -> Vector:
            d = direction.normalized()
            return centre + Vector((d.x * r.x, d.y * r.y, d.z * r.z)) * depth

        # a hot core pokes through the eye's upper front, like a lit filament
        ellipsoid(cores, on_eye(n_out + CORE_LIFT, 0.7), r * 0.52, 6, 3, lambda n: EYE_CORE)
        # a catchlight: one small pale diamond just off the top of the eye
        d = (n_out * 0.45 + SHINE_DIR).normalized()
        top = on_eye(d, 1.0)
        nrm = Vector((d.x / r.x, d.y / r.y, d.z / r.z)).normalized()
        u = nrm.cross(Vector((0, 1, 0))).normalized()
        v = nrm.cross(u).normalized()
        p0 = top + nrm * 0.0005
        a = 0.0062 * k
        quad = [shine.add(p0 + u * a * 0.55, TUSK), shine.add(p0 + v * a, TUSK),
                shine.add(p0 - u * a * 0.55, TUSK), shine.add(p0 - v * a, TUSK)]
        shine.face(*quad)
        ellipsoid(part, H(s * SMALL_EYE[0], SMALL_EYE[1], SMALL_EYE[2]), (0.0105 * k / 1.2,) * 3, 5, 3,
                  lambda n: EYE)


def mandible_points(s: int):
    m = V["mandible"]
    base = H(s * 0.029, -0.044, -0.021)
    pts = [base,
           base + Vector((s * 0.015, -0.03 * m, -0.004)),
           base + Vector((s * 0.016, -0.06 * m, -0.006)),
           base + Vector((s * 0.002, -0.083 * m, -0.006)),
           base + Vector((-s * 0.015, -0.093 * m, -0.004))]
    return pts


def mandibles() -> None:
    for s in (1, -1):
        part = Part(f"mandible_{'L' if s > 0 else 'R'}", f"mand_{'L' if s > 0 else 'R'}", pattern="plain",
                    smooth=80.0)
        pts = mandible_points(s)

        def col(t, up):
            c = mix(SHELL_DARK, mix(SHELL, SHELL_LIGHT, 0.75), smoothstep(0.1, 0.5, t))
            c = mix(c, mix(SPIKE, TUSK, 0.3), smoothstep(0.5, 0.9, t))
            return mul(c, 0.82 + 0.22 * smoothstep(-0.6, 0.8, up))

        tube(part, pts, [0.017, 0.016, 0.0125, 0.0078, 0.0], sides=6, squash=0.6, col=col)
        # an inner tooth
        mid = pts[2]
        cone(part, mid + Vector((-s * 0.004, 0, 0)), mid + Vector((-s * 0.018, -0.008, 0.0)), 0.0045,
             mix(SHELL_LIGHT, SPIKE, 0.4), mix(SPIKE, TUSK, 0.3))


ANT_SIDE = {s: (rng.uniform(0.94, 1.06), rng.uniform(-0.006, 0.006)) for s in (1, -1)}


def antenna_points(s: int):
    """Scape forward and a little up from the front of the head, an elbow, then a short
    whip out and forward ending in a club. Kept low and forward so that, from the
    game's camera, it passes in front of the face rather than across the big eyes."""
    reach, lift = V["antenna_reach"] * ANT_SIDE[s][0], V["antenna_lift"] + ANT_SIDE[s][1]
    base = H(s * 0.03, -0.048, 0.024)
    elbow = base + Vector((s * 0.022, -0.034, 0.03 + lift * 0.5))
    pts = [base, base + Vector((s * 0.012, -0.02, 0.016)), elbow]
    for i in range(1, 6):
        t = i / 5
        pts.append(elbow + Vector((s * 0.072 * reach * t ** 0.8,
                                   -0.036 * reach * math.sin(t * math.pi / 2),
                                   (0.02 + lift) * math.sin(t * math.pi) * 0.8 - 0.008 * t)))
    return pts


def antennae() -> None:
    for s in (1, -1):
        part = Part(f"antenna_{'L' if s > 0 else 'R'}", f"ant_{'L' if s > 0 else 'R'}", pattern="plain", smooth=80.0)
        pts = antenna_points(s)

        def col(t, up):
            c = mix(SHELL_DARK, mix(SHELL, SHELL_LIGHT, 0.5), smoothstep(0.1, 0.6, t))  # a dark shaft
            c = mix(c, mix(RIM, TIP, 0.4), smoothstep(0.72, 0.95, t) * 0.9)              # a pale club
            return mul(c, 0.85 + 0.2 * smoothstep(-0.5, 0.8, up))

        radii = [0.0095, 0.0085, 0.008, 0.0072, 0.0068, 0.0105, 0.0128, 0.0]
        tube(part, pts, radii, sides=5, col=col)


# ── Legs ──

# per pair: hip, knee, foot, tarsus tip (for the +X side); the -X side mirrors
LEGS = {
    "1": ((0.045, -0.122, 0.106), (0.13, -0.172, 0.172), (0.168, -0.235, 0.022), (0.178, -0.272, 0.011)),
    "2": ((0.06, -0.035, 0.104), (0.158, -0.046, 0.178), (0.205, -0.066, 0.022), (0.235, -0.078, 0.011)),
    "3": ((0.058, 0.045, 0.104), (0.145, 0.104, 0.172), (0.196, 0.175, 0.022), (0.212, 0.212, 0.011)),
}
FEMUR_R = {"1": 0.027, "2": 0.028, "3": 0.033}  # thick enough to read at the default zoom
TARSUS_SQUASH = 0.62
CLAW_GROUND = 0.0015  # the claw tips rest just above z = 0


def mirror(p, s):
    return Vector((p[0] * s, p[1], p[2]))


def leg_name(s: int, pair: str) -> str:
    return f"{'L' if s > 0 else 'R'}{pair}"


def tarsus(foot: Vector, toe: Vector, fr: float):
    """The beaded foot: points and radii, arching over and hooking down into a claw
    that stretches out past the toe, so a pale hook shows beyond the shin."""
    d = toe - foot
    h = Vector((d.x, d.y, 0.0)).normalized()
    pts = [foot, foot + d * 0.45 + Vector((0, 0, -0.002)), toe,
           toe + h * 0.012 + Vector((0, 0, 0.002)),
           Vector((toe.x, toe.y, CLAW_GROUND)) + h * 0.022]
    radii = [fr * 0.38, fr * 0.36, fr * 0.32, fr * 0.22, 0.0]
    return pts, radii


def leg_colour(c) -> tuple:
    return mul(c, LEG_K)


def tibia_points(knee: Vector, foot: Vector, fr: float, s: int):
    """The shin bows out and up between knee and foot, like a beetle's curved tibia."""
    tdir = (foot - knee).normalized()
    out = Vector((s, 0, 0))
    pts = [knee - tdir * 0.004,
           knee.lerp(foot, 0.45) + out * fr * 0.4 + Vector((0, 0, 0.012)),
           knee.lerp(foot, 0.78) + out * fr * 0.18 + Vector((0, 0, 0.005)),
           foot]
    radii = [fr * 0.72, fr * 0.6, fr * 0.42, fr * 0.34]
    return pts, radii


def legs() -> None:
    for s in (1, -1):
        for pair, (hip, knee, foot, toe) in LEGS.items():
            name = leg_name(s, pair)
            hip, knee, foot, toe = (mirror(p, s) for p in (hip, knee, foot, toe))
            hip += Vector((rng.uniform(-0.003, 0.003), rng.uniform(-0.003, 0.003), 0))
            fr = FEMUR_R[pair]

            femur = Part(f"femur_{name}", f"femur_{name}", pattern="plain", smooth=80.0, mask="leg")
            kdir = (knee - hip).normalized()

            def fcol(t, up):
                # dark at the hip, the shell's mid-tone along the top fading over the
                # upper half, and a muted cap over the knee
                c = mix(SHELL_DARK, mul(SHELL, 0.95), smoothstep(0.0, 0.7, t))
                c = mix(c, SHELL, 0.5 * smoothstep(-0.3, 1.0, up) * smoothstep(0.1, 0.5, t))
                c = mix(c, SHELL_DARK, 0.4 * smoothstep(0.1, -0.9, up))  # the underside falls away
                return leg_colour(mix(c, KNEE, 0.6 * smoothstep(0.88, 0.98, t)))

            tube(femur, [hip - kdir * 0.01, hip.lerp(knee, 0.28), hip.lerp(knee, 0.6), knee, knee + kdir * 0.016],
                 [fr * 0.55, fr * 0.95, fr, fr * 0.72, 0.0], sides=8, squash=0.82, col=fcol)

            tibia = Part(f"tibia_{name}", f"tibia_{name}", pattern="plain", smooth=80.0, mask="leg")
            tdir = (foot - knee).normalized()

            def tcol(t, up):
                c = mix(mix(SHELL, SHELL_DARK, 0.3), SHELL_DARK, smoothstep(0.15, 1.0, t))
                return leg_colour(mix(c, SHELL_LIGHT, 0.2 * smoothstep(-0.3, 1.0, up) * (1 - 0.6 * t)))

            tpts, tradii = tibia_points(knee, foot, fr, s)
            # no end cap: the tarsus starts wider, so the shin's end is always inside it
            tube(tibia, tpts, tradii, sides=6, col=tcol, cap_end=False)
            # spurs raking out from the outer edge of the shin: dark, only the tips pale
            out = Vector((s, 0, 0))
            for f, ln in ((0.4, 0.032), (0.68, 0.026)):
                centre, _, radius = along(tpts, tradii, f)
                base = centre + out * radius * 0.7
                rake = (out * 1.0 + tdir * 0.45 + Vector((0, 0, 0.2))).normalized()
                cone(tibia, base, base + rake * ln, 0.006, leg_colour(SHELL_DARK),
                     leg_colour(mix(SHELL_LIGHT, TIP, 0.45)), cap=False)
            # tarsus: a few beads ending in a pale hooked claw, on its own bone so it
            # can lie flat on the ground while the shin sweeps over it
            foot_part = Part(f"tarsus_{name}", f"tarsus_{name}", pattern="plain", smooth=80.0, mask="leg")
            pts, radii = tarsus(foot, toe, fr)
            tube(foot_part, pts, radii, sides=4, squash=TARSUS_SQUASH,
                 col=lambda t, up: mix(leg_colour(mix(SHELL, SHELL_DARK, 0.5)), mul(TIP, 0.9),
                                       smoothstep(0.55, 0.95, t)))


# ── Build ──

# Emission above ~1 is bleached toward cream by the game's filmic tonemap and glow, so the
# eyes stay just under it (and the base colour is dark) to read as green in game.
EYE_MAT = gab.glow("creep_eyes_green", "#9cff5a", gab.param("eye_glow", 0.7))  # eyes and the tail lantern
EYE_MAT.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*lin(mul(EYE, 0.3)), 1.0)
# the hot cores of the big eyes and the lantern's tip: paler and brighter (bleaching a
# little toward cream in game), so they read as lit from inside
CORE_MAT = gab.glow("creep_eyes_green_core", "#c3e070", gab.param("core_glow", 1.4))
CORE_MAT.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*lin(mul(EYE_CORE, 0.5)), 1.0)
elytron(1)
elytron(-1)
elytron_gloss(1)
elytron_gloss(-1)
pronotum()
pronotum_gloss()
abdomen()
head()
eyes()
mandibles()
antennae()
legs()

# scutellum: the little triangle where the elytra meet the pronotum
scut = Part("scutellum", "body", smooth=None)
a = scut.add((0.0, -0.05, 0.226), SHELL_LIGHT)
b = scut.add((-0.016, -0.055, 0.214), SHELL)
c = scut.add((0.016, -0.055, 0.214), SHELL)
d = scut.add((0.0, -0.022, 0.216), mix(SHELL_LIGHT, RIM, 0.5))
e = scut.add((0.0, -0.05, 0.2), SHELL_DARK)
scut.face(a, b, d)
scut.face(a, d, c)
scut.face(a, c, b)
scut.face(e, d, b)
scut.face(e, c, d)
scut.face(e, b, c)

objects = [p.build() for p in PARTS]
if gab.param("verbose", 0):
    for o in objects:
        print(f"  part {o.name:16s} {gab.triangles(o):4d} tris")
beetle = gab.join(objects, "scuttler")
beetle.data.name = "scuttler"
beetle.scale = (G, G, G)
gab.apply_transform(beetle)


def sc(p) -> Vector:
    return Vector(p) * G


# ── Rig (in the scaled space) ──

bones = [
    ("root", (0, 0, 0), sc((0, 0, 0.06)), None),
    ("body", sc((0, 0.03, 0.13)), sc((0, -0.07, 0.13)), "root"),
    ("head", sc(H(0, 0.04, 0.0)), sc(H(0, -0.025, 0.0)), "body"),
]
for s in (1, -1):
    side = "L" if s > 0 else "R"
    mp = mandible_points(s)
    bones.append((f"mand_{side}", sc(mp[0]), sc(mp[2]), "head"))
    ap = antenna_points(s)
    bones.append((f"ant_{side}", sc(ap[0]), sc(ap[3]), "head"))
    for pair, (hip, knee, foot, toe) in LEGS.items():
        name = leg_name(s, pair)
        bones.append((f"femur_{name}", sc(mirror(hip, s)), sc(mirror(knee, s)), "root"))
        bones.append((f"tibia_{name}", sc(mirror(knee, s)), sc(mirror(foot, s)), f"femur_{name}"))
        bones.append((f"tarsus_{name}", sc(mirror(foot, s)), sc(mirror(toe, s)), f"tibia_{name}"))
arm = gab.armature("scuttler_rig", bones)
# every part already carries a vertex group named after its bone (rigid skinning)
modifier = beetle.modifiers.new("Armature", "ARMATURE")
modifier.object = arm
beetle.parent = arm

# ── Walk: 20 frames, tripod gait ──

FRAMES = 20
STRIDE = 0.15 * G  # each planted foot slides this far back along the body per stance
FOOT_LIFT = 0.037 * G  # how high a swinging ankle rises
FOOT_TUCK = 0.016 * G  # and how far it pulls in toward the body
GROUND = 0.0012  # the lowest a foot may reach

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


def periodic_noise(count: int, amp: float):
    """A smooth looping random curve: a few seeded harmonics."""
    terms = [(h, rng.uniform(0, 2 * math.pi), rng.uniform(0.4, 1.0) / h) for h in range(1, count + 1)]
    norm = sum(t[2] for t in terms)
    return lambda ph: amp * sum(w * math.sin(2 * math.pi * h * ph + o) for h, o, w in terms) / norm


TRIPOD_A = {"L1", "R2", "L3"}
action = bpy.data.actions.new("walk")
arm.animation_data_create()
arm.animation_data.action = action
pose = arm.pose.bones

leg_info = {}
for s in (1, -1):
    for pair, (hip, knee, foot, toe) in LEGS.items():
        name = leg_name(s, pair)
        pts, radii = tarsus(mirror(foot, s), mirror(toe, s), FEMUR_R[pair])
        # the lowest points of the foot: bead undersides and the claw tip
        low = [sc(p - Vector((0, 0, r * TARSUS_SQUASH))) for p, r in zip(pts, radii)]
        along_foot = Vector((pts[2].x - pts[0].x, pts[2].y - pts[0].y, 0.0)).normalized()
        curl_axis = UP.cross(along_foot).normalized()  # turning about it points the claw down
        leg_info[name] = (sc(mirror(hip, s)), sc(mirror(knee, s)), sc(mirror(foot, s)), low, curl_axis,
                          0.0 if name in TRIPOD_A else 0.5)


def leg_ik(hip: Vector, knee: Vector, foot: Vector, target: Vector):
    """Two-bone IK in armature space: the femur rotation (about the hip) and the
    knee rotation (about the knee, in the femur's frame) that put the foot on
    `target`. The femur turns by yaw then pitch, so the knee stays up."""
    a, b = (knee - hip).length, (foot - knee).length
    dist = min((target - hip).length, (a + b) * 0.995)
    bend_axis = (knee - hip).cross(foot - knee).normalized()
    g0 = (hip - knee).angle(foot - knee)
    g1 = math.acos(max(-1.0, min(1.0, (a * a + b * b - dist * dist) / (2 * a * b))))
    best = None
    for sign in (1, -1):
        rk = Matrix.Rotation(sign * (g1 - g0), 3, bend_axis)
        f1 = knee + rk @ (foot - knee)
        err = abs((f1 - hip).length - dist)
        if best is None or err < best[0]:
            best = (err, rk, f1)
    _, rk, f1 = best
    v, w = f1 - hip, target - hip
    yaw = math.atan2(w.y, w.x) - math.atan2(v.y, v.x)
    rz = Matrix.Rotation(yaw, 3, "Z")
    pitch = (rz @ v).rotation_difference(w).to_matrix()
    return pitch @ rz, rk


# at the game's ~3x playback one cycle lasts about 0.2 s: keep every wobble at one or
# two periods per cycle so it reads as twitching, not as vibration
jit_z = periodic_noise(2, 0.0011 * G)
jit_pitch = periodic_noise(2, math.radians(0.8))
jit_roll = periodic_noise(2, math.radians(0.8))
jit_yaw = periodic_noise(2, math.radians(0.8))
ant_noise = {s: (periodic_noise(2, math.radians(5)), periodic_noise(2, math.radians(4))) for s in (1, -1)}

for frame in range(FRAMES + 1):
    ph = frame / FRAMES
    # body: rolls toward the tripod on the ground, bobs once per step, jitters
    roll = math.radians(2.2) * math.sin(2 * math.pi * ph) + jit_roll(ph)
    yaw = math.radians(2.5) * math.sin(2 * math.pi * ph + 0.6) + jit_yaw(ph)
    pitch = math.radians(0.8) * math.sin(4 * math.pi * ph + 1.0) + jit_pitch(ph)
    bob = 0.0035 * G * math.cos(4 * math.pi * ph) + jit_z(ph)
    rot = (Matrix.Rotation(yaw, 3, "Z") @ Matrix.Rotation(pitch, 3, "X") @ Matrix.Rotation(roll, 3, "Y"))
    key(pose["body"], frame, rot, (0.0, 0.0, bob))
    key(pose["root"], frame, Matrix.Identity(3))
    # head steadies against the body and twitches once a cycle
    hyaw = -0.6 * yaw + math.radians(3) * math.sin(2 * math.pi * ph + 2.0)
    hpitch = math.radians(3) * math.sin(2 * math.pi * ph + 0.3)
    key(pose["head"], frame, Matrix.Rotation(hyaw, 3, "Z") @ Matrix.Rotation(hpitch, 3, "X"))
    for s in (1, -1):
        side = "L" if s > 0 else "R"
        # mandibles snap open and shut once a cycle
        snap = math.radians(8) * max(0.0, math.sin(2 * math.pi * ph + (0.0 if s > 0 else 0.4))) ** 2
        key(pose[f"mand_{side}"], frame, Matrix.Rotation(s * snap - s * math.radians(3), 3, "Z"))
        ny, nx = ant_noise[s]
        key(pose[f"ant_{side}"], frame,
            Matrix.Rotation(ny(ph) + s * math.radians(4) * math.sin(2 * math.pi * ph + s), 3, "Z")
            @ Matrix.Rotation(nx(ph) + math.radians(4) * math.sin(2 * math.pi * ph + 1.2), 3, "X"))
    for name, (hip, knee, foot, low, curl_axis, offset) in leg_info.items():
        lp = (ph + offset) % 1.0
        if lp < 0.5:  # stance: planted, the foot slides straight back at a steady pace
            along = -STRIDE / 2 + STRIDE * (lp / 0.5)
            up = tuck = 0.0
        else:  # swing: up, in and forward
            u = (lp - 0.5) / 0.5
            along = STRIDE / 2 - STRIDE * (u * u * (3 - 2 * u))
            up = FOOT_LIFT * math.sin(math.pi * u)
            tuck = FOOT_TUCK * math.sin(math.pi * u)
        inward = Vector((hip.x - foot.x, 0.0, 0.0)).normalized() * tuck
        # The tarsus keeps its rest pose in the world while planted, lying flat with the
        # claw hooked into the ground, so the whole foot slides back with the ground as
        # the ankle does; in the swing it curls, the claw tucking down and in.
        curl = math.radians(14) * math.sin(math.pi * (lp - 0.5) / 0.5) if lp >= 0.5 else 0.0
        foot_rot = Matrix.Rotation(curl, 3, curl_axis)
        target = foot + Vector((0.0, along, up)) + inward
        for _ in range(4):
            femur_rot, knee_rot = leg_ik(hip, knee, foot, target)
            ankle = hip + femur_rot @ (knee - hip + knee_rot @ (foot - knee))
            lowest = min((ankle + foot_rot @ (p - foot)).z for p in low)
            if lowest >= GROUND - 1e-5:
                break
            target = target + Vector((0, 0, GROUND - lowest))  # never dig into the ground
        key(pose[f"femur_{name}"], frame, femur_rot)
        key(pose[f"tibia_{name}"], frame, knee_rot)
        key(pose[f"tarsus_{name}"], frame, (femur_rot @ knee_rot).inverted() @ foot_rot)

track = arm.animation_data.nla_tracks.new()
track.name = "walk"
track.strips.new("walk", 0, action)
arm.animation_data.action = None
for pb in pose:
    pb.rotation_quaternion = (1, 0, 0, 0)
    pb.location = (0, 0, 0)
bpy.context.scene.frame_start = 0
bpy.context.scene.frame_end = FRAMES

# planted feet slide STRIDE per half cycle: this is the body speed the cycle matches
speed = STRIDE / (FRAMES / 2 / bpy.context.scene.render.fps)
xs = [v.co.x for v in beetle.data.vertices]
ys = [v.co.y for v in beetle.data.vertices]
zs = [v.co.z for v in beetle.data.vertices]
print(f"scuttler: {gab.triangles()} triangles; size {max(xs) - min(xs):.3f} wide x {max(zs):.3f} tall x "
      f"{max(ys) - min(ys):.3f} long (front {min(ys):.3f}, tail {max(ys):.3f}, lowest z {min(zs):.4f}); "
      f"walk matches {speed:.3f} model units/s, so game.gd stride = {speed * 1.5:.4f} at the game's 1.5x scale"
      + ("; MASK BUILD, do not ship" if MASK else ""))
