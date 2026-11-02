#!/usr/bin/env python3
"""The desktop game's application icon in every size a system asks for, made from Groundhold's
brand mark: the holdfast knot on its stone roundel, painted again by the brand's own painter at
its own spec (art_src/ui/wordmark.py and wordmark.json, docs/design/front-end.md §4.7), never
drawn anew.

    python3 tools/release/app_icon.py            # rewrites packaging/icons/
    python3 tools/release/app_icon.py --check    # exit 1 when a file there is not what it paints

    packaging/icons/<n>.png       16, 24, 32, 48, 64, 128, 256 and 512 px: the Linux packages'
                                  hicolor icons (usr/share/icons/hicolor/<n>x<n>/apps/<id>.png)
    packaging/icons/groundhold.ico   16 to 256 px: the Windows game's, written into
                                  Groundhold.exe by the export (export_presets.cfg's
                                  application/icon), and the installer's
    packaging/icons/groundhold.icns  16 to 1024 px: the macOS app's (Contents/Resources), the
                                  export's application/icon too
    packaging/icons/installer.bmp    164 x 314 px: the Windows installer's welcome and finish
                                  pages' picture (NSIS's MUI_WELCOMEFINISHPAGE_BITMAP), the
                                  emblem at 128 px on the favicon's dark stone under a gilt rule

At 32 px and below a system is given the brand's small cut, the favicon's (2, 3) knot with a
band near twice as thick, which the brand made because the emblem's (3, 4) knot blurs to a ring
that small; above, the emblem, painted at 1024 px and filtered down as the brand filters its own
sizes, so the 256 px is ui/brand/icon.png (the window icon, project.godot's config/icon) pixel
for pixel. Both containers hold PNG entries (Windows Vista and macOS 10.7 on read them). Needs
Pillow; the outputs are committed, so a release builds without it. Run it again after the mark
changes.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "packaging" / "icons"
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
# the .icns's entries, Apple's types by their pixels (ic11 to ic14 the @2x ones, 16 to 256 points)
ICNS = (("icp4", 16), ("icp5", 32), ("ic11", 32), ("ic12", 64), ("ic07", 128), ("ic08", 256),
        ("ic13", 256), ("ic09", 512), ("ic14", 512), ("ic10", 1024))
SMALL = 32  # at this size and below, the favicon's cut
ICO = "groundhold.ico"
ICNS_NAME = "groundhold.icns"
# the installer's side picture: NSIS's Modern UI draws it at 164 x 314, a 24-bit BMP, left of the
# welcome and finish pages' words (its own stock picture, a blue wizard, where there is none)
SIDE = "installer.bmp"
SIDE_SIZE = (164, 314)
SIDE_EMBLEM = 128
SIDE_STONE = ("#2b251f", "#110d0a")  # the favicon's stone, top to bottom, darker below the emblem
SIDE_GILT = "#b98a3e"  # the favicon's rim


def sizes() -> list[int]:
    return sorted(set(PNG_SIZES) | set(ICO_SIZES) | {pixels for _, pixels in ICNS})


def paint() -> dict:
    """Every size as a Pillow image, painted by the brand's painter."""
    sys.path.insert(0, str(ROOT / "art_src" / "ui"))
    import wordmark  # noqa: E402  (art_src/ui: the brand's painter, and the console's helpers)

    images: dict = {}

    class Capture(wordmark._Brand):
        def save(self, name: str, img) -> None:
            images[int(name)] = img

    spec = json.loads((ROOT / "art_src" / "ui" / "wordmark.json").read_text(encoding="utf-8"))
    spec["emblem"] = dict(spec.get("emblem", {}), out=[[str(n), n] for n in sizes() if n > SMALL])
    spec["favicon"] = dict(spec.get("favicon", {}), out=[[str(n), n] for n in sizes() if n <= SMALL])
    brand = Capture(spec, ROOT, OUT)
    brand.emblem()
    brand.favicon()
    return images


def png(img) -> bytes:
    data = io.BytesIO()
    img.save(data, format="PNG", optimize=True)
    return data.getvalue()


def ico(pngs: dict[int, bytes]) -> bytes:
    """An .ico of PNG entries, smallest first."""
    head = struct.pack("<HHH", 0, 1, len(ICO_SIZES))
    offset = len(head) + 16 * len(ICO_SIZES)
    entries, data = b"", b""
    for n in ICO_SIZES:
        body = pngs[n]
        side = 0 if n >= 256 else n  # (0 stands for 256)
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(body), offset + len(data))
        data += body
    return head + entries + data


def icns(pngs: dict[int, bytes]) -> bytes:
    body = b"".join(kind.encode("ascii") + struct.pack(">I", 8 + len(pngs[n])) + pngs[n] for kind, n in ICNS)
    return b"icns" + struct.pack(">I", 8 + len(body)) + body


def side(emblem) -> bytes:
    """The installer's side picture: the stone's gradient, the emblem in its upper part and a short
    gilt rule under it, as a 24-bit BMP."""
    from PIL import Image, ImageDraw

    width, height = SIDE_SIZE
    top, bottom = (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in SIDE_STONE)
    picture = Image.new("RGB", SIDE_SIZE)
    draw = ImageDraw.Draw(picture)
    for y in range(height):
        t = y / (height - 1)
        draw.line([(0, y), (width - 1, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    if emblem.size != (SIDE_EMBLEM, SIDE_EMBLEM):
        raise ValueError(f"the emblem is {emblem.size}, not {SIDE_EMBLEM} px")
    x, y = (width - SIDE_EMBLEM) // 2, 58
    picture.paste(emblem, (x, y), emblem)
    rule = y + SIDE_EMBLEM + 16
    draw.line([(width // 2 - 36, rule), (width // 2 + 36, rule)], fill=SIDE_GILT, width=1)
    data = io.BytesIO()
    picture.save(data, format="BMP")
    return data.getvalue()


def files(images: dict) -> dict[str, bytes]:
    """packaging/icons/'s files by name."""
    pngs = {n: png(img) for n, img in images.items()}
    out = {f"{n}.png": pngs[n] for n in PNG_SIZES}
    out[ICO] = ico(pngs)
    out[ICNS_NAME] = icns(pngs)
    out[SIDE] = side(images[SIDE_EMBLEM])
    return out


def write(out: Path, made: dict[str, bytes]) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, data in made.items():
        path = out / name
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)
            written.append(path)
    return written


def pictures(data: bytes) -> list[tuple[str, bytes]]:
    """The PNG entries of an .ico or .icns, (where, PNG bytes) each."""
    if data[:4] == b"icns":
        out, at = [], 8
        while at < len(data):
            kind, length = data[at:at + 4].decode("ascii"), struct.unpack(">I", data[at + 4:at + 8])[0]
            out.append((kind, data[at + 8:at + length]))
            at += length
        return out
    _, kind, count = struct.unpack("<HHH", data[:6])
    out = []
    for i in range(count):
        side, _, _, _, _, _, length, offset = struct.unpack("<BBBBHHII", data[6 + 16 * i:22 + 16 * i])
        out.append((str(side or 256), data[offset:offset + length]))
    return out


def same_pixels(a: bytes, b: bytes) -> bool:
    from PIL import Image

    first, second = (Image.open(io.BytesIO(x)) for x in (a, b))
    return first.size == second.size and first.convert("RGBA").tobytes() == second.convert("RGBA").tobytes()


def differences(out: Path, made: dict[str, bytes]) -> list[str]:
    """What in `out` is not what the painter makes, compared by their pixels (zlib builds differ)."""
    wrong = []
    for name, data in made.items():
        path = out / name
        if not path.exists():
            wrong.append(f"{name} is missing")
            continue
        have = path.read_bytes()
        if name.endswith((".png", ".bmp")):
            if not same_pixels(have, data):
                wrong.append(f"{name} differs")
            continue
        theirs, mine = pictures(have), pictures(data)
        if [k for k, _ in theirs] != [k for k, _ in mine] or not all(
                same_pixels(a, b) for (_, a), (_, b) in zip(theirs, mine)):
            wrong.append(f"{name} differs")
    return wrong


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--check", action="store_true", help="change nothing; exit 1 when a file is not current")
    args = parser.parse_args(argv)
    made = files(paint())
    if args.check:
        wrong = differences(args.out, made)
        for problem in wrong:
            print(f"::error title=App icon::{problem}: run python3 tools/release/app_icon.py", file=sys.stderr)
        return 1 if wrong else 0
    for path in write(args.out, made):
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
