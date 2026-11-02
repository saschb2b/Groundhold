"""pe_resources.py reads a Windows executable's icons, version information and manifest, and fails a
Groundhold.exe whose export did not write the brand's icon or the release's version into it. The
executables here are built by the test: a PE32+ header and one .rsrc section.

    python3 -m unittest discover -s tools/release -t tools/release
"""

import contextlib
import io
from pathlib import Path
import struct
import tempfile
import unittest

import app_icon
import pe_resources as pe

ICO = app_icon.OUT / app_icon.ICO


def rsrc(resources: dict, base_rva: int) -> bytes:
    """A resource section of {type: {name: bytes}} (one language each), as a linker lays it out."""
    keys = [(t, n) for t in sorted(resources) for n in sorted(resources[t], key=lambda n: (not isinstance(n, str), n))]
    types = sorted(resources)
    at = 16 + 8 * len(types)
    type_dirs, name_dirs, entries, strings, datas = {}, {}, {}, {}, {}
    for t in types:
        type_dirs[t] = at
        at += 16 + 8 * len(resources[t])
    for key in keys:
        name_dirs[key] = at
        at += 24
    for key in keys:
        entries[key] = at
        at += 16
    for t, n in keys:
        if isinstance(n, str):
            strings[(t, n)] = at
            at = (at + 2 + 2 * len(n) + 3) & ~3
    for t, n in keys:
        datas[(t, n)] = at
        at = (at + len(resources[t][n]) + 3) & ~3
    buf = bytearray(at)

    def directory(where, named, ids, items):
        struct.pack_into("<IIHHHH", buf, where, 0, 0, 4, 0, named, ids)
        for i, (name, target) in enumerate(items):
            struct.pack_into("<II", buf, where + 16 + 8 * i, name, target)

    directory(0, 0, len(types), [(t, 0x80000000 | type_dirs[t]) for t in types])
    for t in types:
        names = [n for tt, n in keys if tt == t]
        named = [n for n in names if isinstance(n, str)]
        directory(type_dirs[t], len(named), len(names) - len(named),
                  [((0x80000000 | strings[(t, n)]) if isinstance(n, str) else n, 0x80000000 | name_dirs[(t, n)])
                   for n in names])
    for t, n in keys:
        data = resources[t][n]
        directory(name_dirs[(t, n)], 0, 1, [(1033, entries[(t, n)])])
        struct.pack_into("<IIII", buf, entries[(t, n)], base_rva + datas[(t, n)], len(data), 0, 0)
        if isinstance(n, str):
            struct.pack_into("<H", buf, strings[(t, n)], len(n))
            buf[strings[(t, n)] + 2:strings[(t, n)] + 2 + 2 * len(n)] = n.encode("utf-16-le")
        buf[datas[(t, n)]:datas[(t, n)] + len(data)] = data
    return bytes(buf)


def executable(resources: dict) -> bytes:
    rva, raw_at = 0x1000, 0x200
    section = rsrc(resources, rva)
    head = bytearray(raw_at)
    head[0:2] = b"MZ"
    struct.pack_into("<I", head, 0x3C, 0x40)
    head[0x40:0x44] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", head, 0x44, 0x8664, 1, 0, 0, 0, 240, 0x22)
    optional = 0x58
    struct.pack_into("<H", head, optional, 0x20B)
    struct.pack_into("<II", head, optional + 112 + 16, rva, len(section))
    table = optional + 240
    head[table:table + 8] = b".rsrc\0\0\0"
    struct.pack_into("<IIII", head, table + 8, len(section), rva, len(section), raw_at)
    return bytes(head) + section


def node(key: str, value: bytes = b"", text: bool = False, children: bytes = b"") -> bytes:
    """One VS_VERSIONINFO node, padded to four bytes."""
    head = struct.pack("<HHH", 0, len(value) // 2 if text else len(value), 1 if text else 0)
    head += (key + "\0").encode("utf-16-le")
    head += b"\0" * (-len(head) % 4)
    body = value + b"\0" * (-len(value) % 4) + children
    blob = bytearray(head + body)
    struct.pack_into("<H", blob, 0, len(blob))
    return bytes(blob)


def version_blob(fixed: str, strings: dict[str, str]) -> bytes:
    a, b, c, d = (int(x) for x in fixed.split("."))
    info = struct.pack("<13I", 0xFEEF04BD, 0x10000, a << 16 | b, c << 16 | d, a << 16 | b, c << 16 | d,
                       0x3F, 0, 0x40004, 1, 0, 0, 0)
    table = b"".join(node(k, (v + "\0").encode("utf-16-le"), text=True) for k, v in strings.items())
    file_info = node("StringFileInfo", text=True, children=node("040904b0", text=True, children=table))
    var = node("VarFileInfo", text=True, children=node("Translation", struct.pack("<HH", 0x409, 1200)))
    return node("VS_VERSION_INFO", info, children=file_info + var)


def group(pictures: list[tuple[int, bytes]]) -> tuple[bytes, dict]:
    head = struct.pack("<HHH", 0, 1, len(pictures))
    icons = {}
    for i, (n, data) in enumerate(pictures, 1):
        head += struct.pack("<BBBBHHIH", 0 if n >= 256 else n, 0 if n >= 256 else n, 0, 0, 1, 32, len(data), i)
        icons[i] = data
    return head, icons


class PEResourcesTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)

    def game(self, pictures=None, version="1.2.3.0", strings=None, manifest=True) -> Path:
        """An exe as Godot's export writes Groundhold.exe: its template's sizes from the .ico."""
        ico = dict(pe.ico_pictures(ICO.read_bytes()))
        pictures = pictures if pictures is not None else [(n, ico[n]) for n in (16, 32, 48, 64, 128, 256)]
        head, icons = group(pictures)
        resources = {pe.RT_ICON: icons, pe.RT_GROUP_ICON: {"GODOT_ICON": head},
                     pe.RT_VERSION: {1: version_blob(version, strings or {
                         "CompanyName": "Sascha Becker", "FileVersion": "1.2.3.0", "ProductVersion": "1.2.3.0",
                         "ProductName": "Groundhold"})}}
        if manifest:
            resources[pe.RT_MANIFEST] = {1: b"<assembly/>"}
        path = self.root / "Groundhold.exe"
        path.write_bytes(executable(resources))
        return path

    def test_it_reads_the_icons_version_and_manifest(self):
        found = pe.resources(self.game().read_bytes())
        self.assertEqual([n for n, _ in pe.icons(found)], [16, 32, 48, 64, 128, 256])
        info = pe.version_info(found)
        self.assertEqual(info["fixed_file"], "1.2.3.0")
        self.assertEqual(info["fixed_product"], "1.2.3.0")
        self.assertEqual(info["ProductName"], "Groundhold")
        self.assertEqual(info["FileVersion"], "1.2.3.0")
        self.assertEqual(found[pe.RT_MANIFEST][1], b"<assembly/>")

    def test_a_game_with_the_icon_and_version_passes(self):
        self.assertEqual(pe.problems(self.game(), ICO, "1.2.3"), [])

    def test_another_icon_fails(self):
        ico = dict(pe.ico_pictures(ICO.read_bytes()))
        exe = self.game([(16, ico[16]), (32, b"\x89PNG Godot's own"), (48, ico[48]), (256, ico[256])])
        self.assertEqual(pe.problems(exe, ICO, None), ["its [32] px icons are not groundhold.ico's"])
        exe = self.game([(256, ico[256])])
        self.assertEqual(pe.problems(exe, ICO, None), ["its icon has no [16, 32, 48] px picture"])
        exe = self.game([])
        self.assertEqual(pe.problems(exe, ICO, None), ["no icon"])

    def test_another_version_or_no_manifest_fails(self):
        exe = self.game(version="0.0.0.0", strings={"FileVersion": "", "ProductVersion": "1.2.3"}, manifest=False)
        self.assertEqual(pe.problems(exe, None, "1.2.3"), [
            "FileVersion is '', not 1.2.3", "the fixed file version is '0.0.0.0', not 1.2.3.0",
            "the fixed product version is '0.0.0.0', not 1.2.3.0", "no manifest"])

    def test_the_command_fails_on_what_is_no_executable(self):
        path = self.root / "notes.txt"
        path.write_text("not a program")
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(pe.main([str(path)]), 1)
        self.assertIn("no MZ header", err.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pe.main([str(self.game()), "--icon", str(ICO), "--version", "1.2.3"]), 0)


if __name__ == "__main__":
    unittest.main()
