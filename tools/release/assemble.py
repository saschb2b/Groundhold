#!/usr/bin/env python3
"""The files of a GitHub release, gathered in one folder and checked before anything is published.

    python3 tools/release/assemble.py dist --list files.txt

`dist` holds what release.yml's jobs made: the desktop game (tools/release/package.py: for Windows
an installer and a portable zip, for macOS a disk image, for Linux an AppImage with its .zsync, a
.deb and a tar.gz) and the server's archives (groundhold-server-<target>.zip for its five native
targets and groundhold-server-python.zip, the zipapp for any computer with Python 3.11 or newer;
server-native.yml). TABLE is that list with what each file is, the one table of a release's files:
FILES, which this checks `dist` against, is its names, and the release's Downloads block
(tools/release/release_notes.py) lists its rows and nothing else; every page that tells players what
to download names only FILES (README.md, server/README.md, the site; tools/release/test_workflows.py
holds them to it). It fails, naming each, on a file missing or one no release has; then it writes
SHA256SUMS.txt and the list of files to attach (one path a line, the checksums last). Standard
library only.
"""

import argparse
import hashlib
from pathlib import Path
import sys
from typing import NamedTuple

# the game, as tools/release/package.py makes it (versionless names, so releases/latest/download/<file>
# lasts; the AppImage's update information names its .zsync, so neither may change)
WINDOWS_SETUP = "groundhold-windows-x64-setup.exe"
WINDOWS_ZIP = "groundhold-windows-x64.zip"
MACOS_DMG = "groundhold-macos.dmg"
APPIMAGE = "groundhold-x86_64.AppImage"
ZSYNC = APPIMAGE + ".zsync"
DEB = "groundhold_amd64.deb"
LINUX_TAR = "groundhold-linux-x64.tar.gz"
# the server's native targets, as server/release.py and server-native.yml name them
SERVER_TARGETS = ("windows-x64", "macos-arm64", "macos-x64", "linux-x64", "linux-arm64")
SUMS = "SHA256SUMS.txt"


class File(NamedTuple):
    """A file of a release, as its Downloads block shows it."""

    name: str
    system: str          # the heading it is listed under: windows, macos, linux or server
    what: str            # what it is and how to start it, in a player's words ({name} is its name)
    choice: str = ""     # its link's word where a player picks between a system's files; "" for a
                         # file that only serves another (the AppImage's .zsync), shown in small type
    first: bool = False  # the one to pick first, marked "recommended" where there is a choice


# Every file of a release, in the order its page lists them.
TABLE = (
    File(WINDOWS_SETUP, "windows", "Installs Groundhold for your account alone, no administrator needed, with a "
         "Start menu entry and, if you tick it, one on the desktop. **Settings › Apps** removes it again; your "
         "saves stay.", "Installer", True),
    File(WINDOWS_ZIP, "windows", "Nothing to install: unpack it anywhere and run `Groundhold.exe` in its "
         "`Groundhold` folder.", "Portable"),
    File(MACOS_DMG, "macos", "Open it and drag Groundhold onto Applications. The first start needs one step "
         "more, below.", "Disk image", True),
    File(APPIMAGE, "linux", "One file: make it executable (`chmod +x {name}`) and run it. AppImageUpdate or "
         "Gear Lever brings it up to date from the newest release, fetching only what changed.", "AppImage", True),
    File(ZSYNC, "linux", "the AppImage's update file, which AppImageUpdate reads to fetch only what changed; "
         "you need not download it"),
    File(DEB, "linux", "For Debian, Ubuntu, Mint and their kin: `sudo apt install ./{name}` puts Groundhold in "
         "your menu.", "Debian package"),
    File(LINUX_TAR, "linux", "Unpack it anywhere: `./install.sh` in its `Groundhold` folder adds Groundhold to "
         "your menu for you alone, and `./install.sh --remove` takes it out again.", "Archive"),
    File("groundhold-server-python.zip", "server", "The server for any computer with Python 3.11 or newer"),
    File("groundhold-server-windows-x64.zip", "server", "The server for 64-bit Windows, nothing to install"),
    File("groundhold-server-macos-arm64.zip", "server", "The server for an Apple silicon Mac"),
    File("groundhold-server-macos-x64.zip", "server", "The server for an Intel Mac"),
    File("groundhold-server-linux-x64.zip", "server", "The server for Linux on x86-64"),
    File("groundhold-server-linux-arm64.zip", "server", "The server for Linux on ARM64 (a 64-bit Raspberry Pi OS)"),
)
FILES = [row.name for row in TABLE]
GAME = [row.name for row in TABLE if row.system != "server"]
SERVER = [row.name for row in TABLE if row.system == "server"]


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
