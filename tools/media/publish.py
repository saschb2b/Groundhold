#!/usr/bin/env python3
"""Copies the shots a `godot-agent scenario . tools/media --out RUN` run captured into docs/media/,
where the README shows them and the site build copies them to media/.

    python3 tools/media/publish.py RUN

Each capture `RUN/<scenario>/captures/NNN_<label>.png` becomes `docs/media/<label>.webp` (lossy
WebP, quality 85), except the social card, `social`, which stays a JPEG (`social.jpg`, quality 88,
1200 x 630) because not every site that shows link previews reads WebP. A label shot twice keeps
the last one. Needs only Pillow.
"""

import argparse
import pathlib
import re
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
MEDIA = ROOT / "docs" / "media"
SOCIAL = "social"
SOCIAL_SIZE = (1200, 630)


def captures(run: pathlib.Path) -> dict[str, pathlib.Path]:
    shots = {}
    for path in sorted(run.glob("*/captures/*.png")):
        match = re.fullmatch(r"\d+_(.+)\.png", path.name)
        if match:
            shots[match.group(1)] = path
    return shots


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run", type=pathlib.Path, help="the --out folder of a tools/media run")
    args = parser.parse_args()
    shots = captures(args.run)
    if not shots:
        print(f"no captures under {args.run}", file=sys.stderr)
        return 1
    MEDIA.mkdir(parents=True, exist_ok=True)
    for label, path in shots.items():
        image = Image.open(path).convert("RGB")
        if label == SOCIAL:
            if image.size != SOCIAL_SIZE:
                print(f"{path}: the social card is {image.size}, not {SOCIAL_SIZE}", file=sys.stderr)
                return 1
            out = MEDIA / "social.jpg"
            image.save(out, quality=88, optimize=True, progressive=True)
        else:
            out = MEDIA / f"{label}.webp"
            image.save(out, quality=85, method=6)
        print(f"{out.relative_to(ROOT)}  {image.size[0]} x {image.size[1]}  {out.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
