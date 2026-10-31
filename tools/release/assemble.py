#!/usr/bin/env python3
"""The files of a GitHub release, gathered in one folder and checked before anything is published.

    python3 tools/release/assemble.py dist --list files.txt

`dist` holds what release.yml's jobs made: the desktop game (groundhold-<platform>.zip for
linux-x64, windows-x64 and macos, tools/release/package.py) and the server's archives
(groundhold-server-<target>.zip for its five native targets and groundhold-server-python.zip, the
zipapp for any computer with Python 3.11 or newer; server-native.yml). FILES is that list, the one
every page that tells players what to download names (README.md, server/README.md, the release's
notes; tools/release/test_workflows.py holds them to it). It fails, naming each, on a file missing
or one no release has; then it writes SHA256SUMS.txt and the list of files to attach (one path a
line, the checksums last). Standard library only.
"""

import argparse
import hashlib
from pathlib import Path
import sys

# the game, by tools/release/package.py's platform
GAME = {"windows-x64": "groundhold-windows-x64.zip", "macos": "groundhold-macos.zip",
        "linux-x64": "groundhold-linux-x64.zip"}
# the server's native targets, as server/release.py and server-native.yml name them
SERVER_TARGETS = ("windows-x64", "macos-arm64", "macos-x64", "linux-x64", "linux-arm64")
SERVER = ["groundhold-server-python.zip"] + [f"groundhold-server-{target}.zip" for target in SERVER_TARGETS]
SUMS = "SHA256SUMS.txt"
FILES = list(GAME.values()) + SERVER

# what each file is, for the release's notes (tools/release/gate.py notes)
WHAT = {
    "groundhold-windows-x64.zip": "The game for 64-bit Windows 10 or 11",
    "groundhold-macos.zip": "The game for macOS, Apple silicon and Intel (unsigned: see below)",
    "groundhold-linux-x64.zip": "The game for Linux on x86-64",
    "groundhold-server-python.zip": "The server for any computer with Python 3.11 or newer",
    "groundhold-server-windows-x64.zip": "The server for 64-bit Windows, nothing to install",
    "groundhold-server-macos-arm64.zip": "The server for an Apple silicon Mac",
    "groundhold-server-macos-x64.zip": "The server for an Intel Mac",
    "groundhold-server-linux-x64.zip": "The server for Linux on x86-64",
    "groundhold-server-linux-arm64.zip": "The server for Linux on ARM64 (a 64-bit Raspberry Pi OS)",
    SUMS: "The files' SHA-256 checksums",
}


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()


def assemble(dist: Path) -> tuple[list[Path], list[str]]:
    """(the files to attach, SHA256SUMS.txt last; what is wrong, empty when nothing is)."""
    present = {path.name for path in dist.iterdir() if path.is_file() and path.name != SUMS}
    wrong = [f"{name} is missing" for name in FILES if name not in present]
    wrong += [f"{name} is empty" for name in FILES if name in present and (dist / name).stat().st_size == 0]
    wrong += [f"{name} is no file of a release" for name in sorted(present - set(FILES))]
    if wrong:
        return [], wrong
    files = [dist / name for name in FILES]
    (dist / SUMS).write_text("".join(f"{digest(path)}  {path.name}\n" for path in files), encoding="utf-8")
    return files + [dist / SUMS], []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("dist", type=Path)
    parser.add_argument("--list", type=Path, help="write the files to attach here, one a line")
    args = parser.parse_args(argv)
    files, wrong = assemble(args.dist)
    for problem in wrong:
        print(f"::error title=Release files::{problem}", file=sys.stderr)
    if wrong:
        return 1
    if args.list:
        args.list.write_text("".join(f"{path}\n" for path in files), encoding="utf-8")
    for path in files:
        print(f"{path.stat().st_size // 1024:>8} KB  {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
