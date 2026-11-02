#!/usr/bin/env python3
"""Packs the desktop game's exports as the release's files, each the way its system installs a game
(tools/release/assemble.py's GAME names them all):

    python3 tools/release/package.py windows build/desktop/windows --version 1.0.0 --out dist
        groundhold-windows-x64-setup.exe, an NSIS installer for the user who runs it, and
        groundhold-windows-x64.zip, the same files in one folder, Groundhold/ (pack_windows.py)
    python3 tools/release/package.py linux build/desktop/linux --version 1.0.0 --out dist
        groundhold-x86_64.AppImage and its .zsync, groundhold_amd64.deb and
        groundhold-linux-x64.tar.gz, all from one install tree (pack_linux.py)
    python3 tools/release/package.py macos build/desktop/macos/Groundhold.zip --version 1.0.0 --out dist
        groundhold-macos.dmg, Godot's app signed ad hoc beside an Applications link and a
        Read me (pack_macos.py; on a Mac, whose codesign and hdiutil it runs)

The installer and the Linux packages need the tools of the packaging image (packaging/Dockerfile:
makensis, appimagetool with the AppImage runtime, zsyncmake, dpkg-deb), so release.yml runs the
first two inside it, as a local build does:

    docker build -t groundhold-packaging packaging
    docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/src" -w /src groundhold-packaging \\
        python3 tools/release/package.py linux build/desktop/linux --version 1.0.0 --out dist

The names carry no version, so a link to the newest release's file stays the same from release to
release. Every package carries a README-first.txt for its system (the .dmg's "Read me.txt"),
written from tools/release/readme/<os>.txt, and the licences: the game's (LICENSE), the engine's
(packaging/licenses/Godot-Engine.txt) and the fonts' (fonts/OFL.txt). `--only` makes some of a
system's files (zip, setup; appimage, deb, tarball), `--work` stages them somewhere other than
build/package/<system>. Standard library only.
"""

from __future__ import annotations

import argparse
import datetime
import os
from pathlib import Path
import string
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import gate  # noqa: E402

NAME = "Groundhold"
APP_ID = "io.github.saschb2b.Groundhold"
REPOSITORY = "saschb2b/Groundhold"
HOMEPAGE = "https://saschb2b.github.io/Groundhold/"
PUBLISHER = "Sascha Becker"
PACKAGING = ROOT / "packaging"
ICONS = PACKAGING / "icons"
README = "README-first.txt"
# the licences every package carries: the game's, then licenses/ (the engine's and the fonts')
LICENSE = ROOT / "LICENSE"
LICENSES = {"Godot-Engine.txt": PACKAGING / "licenses" / "Godot-Engine.txt", "Noto-fonts-OFL.txt": ROOT / "fonts" / "OFL.txt"}
SYSTEMS = ("windows", "linux", "macos")


class PackError(Exception):
    """A package that could not be made, with why."""


def readme(system: str, version: str) -> str:
    """tools/release/readme/<system>.txt with the version filled in (Windows' with its line ends), each
    heading's underline as long as its heading then is."""
    template = (HERE / "readme" / f"{system}.txt").read_text(encoding="utf-8")
    text = underlined(string.Template(template).substitute(version=version))
    return crlf(text) if system == "windows" else text


def underlined(text: str) -> str:
    """Every line of = or - under a heading made as long as the heading (the template's is as long as
    the heading with "$version" in it)."""
    lines = text.split("\n")
    for i in range(1, len(lines)):
        rule, above = lines[i], lines[i - 1]
        if rule and set(rule) <= {"="} | {"-"} and len(set(rule)) == 1 and above.strip():
            lines[i] = rule[0] * len(above)
    return "\n".join(lines)


def crlf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def file_version(version: str) -> str:
    """The version as Windows keeps it, four numbers: 1.2.3 is 1.2.3.0."""
    parts = version.split(".")
    if not 1 <= len(parts) <= 4 or not all(part.isdigit() for part in parts):
        raise PackError(f"the version {version!r} is not X.Y.Z")
    return ".".join(parts + ["0"] * (4 - len(parts)))


def release_date(version: str, root: Path = ROOT) -> str:
    """The release's date from CHANGELOG.md's heading for it (## 1.0.0 · 2026-11-02), else today's (UTC):
    a release being prepared, or a dry run."""
    found = gate.DATE.search(gate.changelog_heading(root, version) or "")
    return found.group(0) if found else datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def run(command: list[str], cwd: Path | None = None, env: dict | None = None) -> str:
    """Runs a packaging tool; PackError with its output when it is missing or fails."""
    try:
        done = subprocess.run([str(part) for part in command], cwd=cwd, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, errors="replace", check=False)
    except FileNotFoundError:
        raise PackError(f"{command[0]} is not installed here: run this in the packaging image "
                        f"(packaging/Dockerfile)") from None
    if done.returncode != 0:
        raise PackError(f"{Path(str(command[0])).name} failed ({done.returncode}):\n{done.stdout.strip()}")
    return done.stdout


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("system", choices=SYSTEMS)
    parser.add_argument("source", type=Path, help="the export: its folder (Windows, Linux) or Godot's macOS zip")
    parser.add_argument("--version", required=True)
    parser.add_argument("--out", type=Path, default=Path("dist"))
    parser.add_argument("--work", type=Path, help="where to stage (default build/package/<system>)")
    parser.add_argument("--only", action="append", help="make only this file (repeatable): "
                        "windows zip, setup; linux appimage, deb, tarball")
    parser.add_argument("--date", help="the release's date for the AppStream data (default: CHANGELOG.md's)")
    args = parser.parse_args(argv)
    work = args.work or ROOT / "build" / "package" / args.system
    try:
        file_version(args.version)
        if args.system == "windows":
            import pack_windows
            made = pack_windows.make(args.source, args.version, args.out, work, args.only)
        elif args.system == "linux":
            import pack_linux
            made = pack_linux.make(args.source, args.version, args.out, work, args.only,
                                   args.date or release_date(args.version))
        else:
            import pack_macos
            made = pack_macos.make(args.source, args.version, args.out, work)
    except (OSError, PackError, ValueError) as exc:
        print(f"::error title=Package {args.system}::{exc}", file=sys.stderr)
        return 1
    for path in made:
        print(f"{path} ({os.path.getsize(path) // 1024} KB)")
    return 0


if __name__ == "__main__":
    # (run as the module the pack_* modules import, so the PackError they raise is the one caught)
    import package
    sys.exit(package.main())
