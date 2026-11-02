#!/usr/bin/env python3
"""Reads what a Windows .exe carries in its resources: its icons, its version information and its
manifest. The release checks that the game's export wrote the brand's icon and the release's
version into Groundhold.exe (export_presets.cfg's application/modify_resources, which Godot does
itself, with no rcedit or Wine) before it is packed.

    python3 tools/release/pe_resources.py build/desktop/windows/Groundhold.exe
    python3 tools/release/pe_resources.py Groundhold.exe --icon packaging/icons/groundhold.ico --version 0.9.0

It prints the icon sizes, the version strings and whether there is a manifest; with --icon it
fails unless every picture of the exe's main icon group is that .ico's of its size, byte for
byte, and 16, 32, 48 and 256 px are among them, with --version unless
FileVersion and ProductVersion begin with it and the fixed version says it in four numbers.
Standard library only.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import struct
import sys

RT_ICON, RT_GROUP_ICON, RT_VERSION, RT_MANIFEST = 3, 14, 16, 24
NEEDED = {16, 32, 48, 256}  # the sizes Explorer, the taskbar and Alt-Tab draw from


class PEError(Exception):
    pass


def _sections(data: bytes):
    if data[:2] != b"MZ":
        raise PEError("not a Windows executable (no MZ header)")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise PEError("no PE header")
    count, optional_size = struct.unpack_from("<H12xH", data, pe + 6)
    optional = pe + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    directories = optional + (112 if magic == 0x20B else 96)
    rva, size = struct.unpack_from("<II", data, directories + 2 * 8)  # the resource directory
    table = optional + optional_size
    sections = []
    for i in range(count):
        at = table + 40 * i
        vsize, vaddr, raw_size, raw_at = struct.unpack_from("<IIII", data, at + 8)
        sections.append((vaddr, max(vsize, raw_size), raw_at))
    return rva, size, sections


def _offset(sections, rva: int) -> int:
    for vaddr, size, raw_at in sections:
        if vaddr <= rva < vaddr + size:
            return rva - vaddr + raw_at
    raise PEError(f"RVA {rva:#x} is in no section")


def resources(data: bytes) -> dict[int, dict]:
    """{type: {name: bytes}} of the first language of each, names as ints or strings."""
    rva, size, sections = _sections(data)
    if not rva:
        return {}
    base = _offset(sections, rva)

    def entries(at):
        named, ids = struct.unpack_from("<HH", data, base + at + 12)
        for i in range(named + ids):
            name, target = struct.unpack_from("<II", data, base + at + 16 + 8 * i)
            if name & 0x80000000:
                length = struct.unpack_from("<H", data, base + (name & 0x7FFFFFFF))[0]
                start = base + (name & 0x7FFFFFFF) + 2
                name = data[start:start + 2 * length].decode("utf-16-le")
            yield name, target

    out: dict[int, dict] = {}
    for kind, at in entries(0):
        if not at & 0x80000000:
            continue
        found = out.setdefault(kind, {})
        for name, at_name in entries(at & 0x7FFFFFFF):
            target = at_name
            while target & 0x80000000:  # the language level: the first one
                target = next(entries(target & 0x7FFFFFFF))[1]
            data_rva, data_size = struct.unpack_from("<II", data, base + target)
            start = _offset(sections, data_rva)
            found[name] = data[start:start + data_size]
    return out


def icons(found: dict[int, dict]) -> list[tuple[int, bytes]]:
    """The first icon group's pictures, (pixels, bytes) each, in its order."""
    groups = found.get(RT_GROUP_ICON, {})
    if not groups:
        return []
    group = groups[sorted(groups, key=lambda n: (isinstance(n, int), n))[0]]
    _, _, count = struct.unpack_from("<HHH", group, 0)
    out = []
    for i in range(count):
        width, _, _, _, _, _, _, ident = struct.unpack_from("<BBBBHHIH", group, 6 + 14 * i)
        out.append((width or 256, found.get(RT_ICON, {}).get(ident, b"")))
    return out


def ico_pictures(data: bytes) -> list[tuple[int, bytes]]:
    _, _, count = struct.unpack_from("<HHH", data, 0)
    out = []
    for i in range(count):
        width, _, _, _, _, _, length, offset = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        out.append((width or 256, data[offset:offset + length]))
    return out


def version_info(found: dict[int, dict]) -> dict[str, str]:
    """The version resource's strings, and its fixed file and product versions as `fixed_file`
    and `fixed_product` (four numbers)."""
    blobs = found.get(RT_VERSION, {})
    if not blobs:
        return {}
    blob = next(iter(blobs.values()))
    out: dict[str, str] = {}

    def node(at):
        length, value_length, kind = struct.unpack_from("<HHH", blob, at)
        end_key = blob.index(b"\0\0", at + 6)
        while (end_key - at - 6) % 2:
            end_key = blob.index(b"\0\0", end_key + 1)
        key = blob[at + 6:end_key].decode("utf-16-le")
        value_at = (end_key + 2 + 3) & ~3
        return length, value_length, kind, key, value_at

    length, value_length, _, key, value_at = node(0)
    if key != "VS_VERSION_INFO":
        raise PEError("the version resource is not a VS_VERSION_INFO")
    if value_length >= 52:
        ms, ls, pms, pls = struct.unpack_from("<IIII", blob, value_at + 8)
        out["fixed_file"] = f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
        out["fixed_product"] = f"{pms >> 16}.{pms & 0xFFFF}.{pls >> 16}.{pls & 0xFFFF}"

    def walk(at, end):
        while at < end:
            length, value_length, kind, key, value_at = node(at)
            if not length:
                break
            if kind == 1 and value_length and value_at < at + length:
                text = blob[value_at:min(value_at + 2 * value_length, at + length)].decode("utf-16-le")
                out[key] = text.split("\0", 1)[0]
            else:
                child = value_at + (value_length if kind == 0 else 2 * value_length)
                walk((child + 3) & ~3, at + length)
            at = (at + length + 3) & ~3

    walk((value_at + value_length + 3) & ~3, length)
    return out


def problems(exe: Path, icon: Path | None, version: str | None) -> list[str]:
    found = resources(exe.read_bytes())
    wrong = []
    if icon is not None:
        # (Godot writes the sizes its template's icon has, 16 to 256 px without 24, each the .ico's
        # picture of that size as it is)
        mine, wanted = icons(found), dict(ico_pictures(icon.read_bytes()))
        if not mine:
            wrong.append("no icon")
        else:
            other = [n for n, picture in mine if wanted.get(n) != picture]
            if other:
                wrong.append(f"its {other} px icons are not {icon.name}'s")
            missing = sorted(NEEDED - {n for n, _ in mine})
            if missing:
                wrong.append(f"its icon has no {missing} px picture")
    if version is not None:
        info = version_info(found)
        four = ".".join((version.split(".") + ["0"] * 4)[:4])
        for key in ("FileVersion", "ProductVersion"):
            if not info.get(key, "").startswith(version):
                wrong.append(f"{key} is {info.get(key)!r}, not {version}")
        for key in ("fixed_file", "fixed_product"):
            if info.get(key) != four:
                wrong.append(f"the {key.replace('_', ' ')} version is {info.get(key)!r}, not {four}")
    if not found.get(RT_MANIFEST):
        wrong.append("no manifest")
    return wrong


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("exe", type=Path)
    parser.add_argument("--icon", type=Path, help="the .ico it must carry")
    parser.add_argument("--version", help="the version it must say, X.Y.Z")
    args = parser.parse_args(argv)
    try:
        found = resources(args.exe.read_bytes())
        print(f"{args.exe.name}: icon {[n for n, _ in icons(found)]} px, "
              f"{'a manifest' if found.get(RT_MANIFEST) else 'no manifest'}")
        for key, value in version_info(found).items():
            print(f"  {key}: {value}")
        wrong = problems(args.exe, args.icon, args.version)
    except (OSError, PEError, struct.error, ValueError) as exc:
        wrong = [str(exc)]
    for problem in wrong:
        print(f"::error title=Windows resources::{args.exe.name}: {problem}", file=sys.stderr)
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
