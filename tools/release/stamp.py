#!/usr/bin/env python3
"""Numbers a build (docs/design/core-loop.md 6.8, 6.9): its build_seq is the CI run number.

    python3 tools/release/stamp.py build-json --build-seq 42 --commit "$GITHUB_SHA"
        writes data/build.json, {"build_seq": 42, "commit": ..., "version": ...}, before an
        export: the game reads it (Session.build_seq) and sends it in HELLO, where a party
        tells the older build from the newer by it
    python3 tools/release/stamp.py shell --build-seq 42 site/play/game/index.html
        after a Web export, writes the number into the exported shell (web/shell.html's
        @BUILD_SEQ@ mark), which then asks for its .js, .wasm and .pck as ?v=42: Pages serves
        every file for 10 minutes, and a reload must never pair one build's .wasm with another's
        .pck. A shell without the mark fails, so a shell that lost it is noticed.

data/build.json is ignored by git: a local export without it is build 0. Standard library only.
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
MARK = "@BUILD_SEQ@"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402


def build_json(root: Path, build_seq: int, commit: str) -> Path:
    path = root / "data" / "build.json"
    record = {"build_seq": build_seq, "commit": commit, "version": gate.project_version(root)}
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


def stamp_shell(path: Path, build_seq: int) -> int:
    """Writes the number over every mark in an exported shell; how many it wrote."""
    text = path.read_text(encoding="utf-8")
    count = text.count(MARK)
    if count:
        path.write_text(text.replace(MARK, str(build_seq)), encoding="utf-8")
    return count


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="the tree to write into (default: this checkout)")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("build-json", help="write data/build.json before an export")
    one.add_argument("--build-seq", type=int, required=True)
    one.add_argument("--commit", default="")
    two = sub.add_parser("shell", help="number an exported Web shell's files")
    two.add_argument("--build-seq", type=int, required=True)
    two.add_argument("shells", nargs="+", type=Path)
    args = parser.parse_args(argv)
    if args.build_seq < 0 or args.build_seq > 0xFFFFFFFF:
        parser.error("--build-seq is HELLO's u32")
    if args.command == "build-json":
        print(f"{build_json(args.root, args.build_seq, args.commit)}: build {args.build_seq}")
        return 0
    for shell in args.shells:
        if stamp_shell(shell, args.build_seq) == 0:
            print(f"::error::{shell} has no {MARK} mark (web/shell.html)", file=sys.stderr)
            return 1
        print(f"{shell}: its files asked for as ?v={args.build_seq}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
