#!/usr/bin/env python3
"""Package the server for a release (server/README.md, Releases).

Without --native: the zipapp (build.py) as groundhold-server-python.zip, for
any system with Python 3.11 or newer. With --native: a PyInstaller one-file
build for this computer's system and architecture, as
groundhold-server-TARGET.zip (TARGETS below); PyInstaller does not
cross-compile, so each target is built on its own system
(.github/workflows/server-native.yml). Each archive holds one folder,
groundhold-server-VERSION-TARGET/ (as the game's zips hold theirs, so an
unzip in Downloads makes one folder, where the server's state lands too),
with the program, a short README.txt for its system (the macOS quarantine
steps among them), LICENSE, server.example.ini and BUILD.json; a native one
also holds licenses/, the notices of what it froze (notices.py). Each
archive is then
extracted outside the checkout and smoke-tested there (smoke.py); one that
fails is deleted.

    python3 server/release.py                          # build/release/groundhold-server-python.zip
    python -m pip install --require-hashes --only-binary=:all: -r server/requirements-build.txt
    python server/release.py --native --target linux-x64 --version 1.0.0

Adapted from Cyberworld Endless's server/release.py (MIT, Sascha Becker):
the targets are named as Groundhold's workflows name them, the README is
short and per system, and the archive itself is what the smoke runs.
"""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile

from build import build, zip_entry
from notices import collect, readme as notices_readme
from smoke import smoke

ROOT = Path(__file__).resolve().parents[1]
NAME = "groundhold-server"
PYINSTALLER = "6.16.0"    # (server/requirements-build.txt pins it, with every dependency, by hash)
GUIDE = "https://github.com/saschb2b/Groundhold/blob/main/server/README.md"
# (platform.system(), platform.machine()) -> target; server-native.yml has one runner for each
TARGETS = {("Linux", "x86_64"): "linux-x64", ("Linux", "aarch64"): "linux-arm64",
           ("Windows", "AMD64"): "windows-x64", ("Darwin", "x86_64"): "macos-x64",
           ("Darwin", "arm64"): "macos-arm64"}
SYSTEMS = {"python": "any system with Python 3.11 or newer", "linux-x64": "Linux on x86-64 (glibc 2.35 or newer)",
           "linux-arm64": "Linux on ARM64 (glibc 2.35 or newer; a Raspberry Pi too)",
           "windows-x64": "64-bit Windows 10 or 11", "macos-x64": "an Intel Mac, macOS 15 or newer",
           "macos-arm64": "an Apple Silicon Mac, macOS 15 or newer"}


def target_for(system, machine):
    """The native target this computer builds, None for one no release ships."""
    return TARGETS.get((system, machine))


def executable_name(target):
    if target == "python":
        return NAME + ".pyz"
    return NAME + (".exe" if target.startswith("windows") else "")


def readme(target, version):
    """README.txt: how to start the server on this archive's system, and where the rest is."""
    program = executable_name(target)
    lines = [f"Groundhold server {version} for {SYSTEMS[target]}", "",
             "The multiplayer server for Groundhold. It never plays a match itself: it keeps the hub",
             "(parties by code) and sends every game in a match the same turns. It holds none of the game.",
             "", "START IT", ""]
    if target == "python":
        lines += [f"  python3 {program}          (Windows: py {program})", "",
                  "  Python 3.11 or newer is all it needs (https://www.python.org/downloads/)."]
    elif target.startswith("windows"):
        lines += [f"  Double-click {program}, or run it in a terminal.", "",
                  "  The build is not signed: if Windows SmartScreen says it protected your PC, choose",
                  "  More info, then Run anyway. When Windows Firewall asks, allow it on private networks."]
    elif target.startswith("macos"):
        lines += [f"  In Terminal, in this folder:   ./{program}", "",
                  "  The build is not signed by an Apple developer account, so the first time macOS refuses",
                  "  to open it (\"Apple could not verify ...\"). Either, once, in Terminal in this folder:",
                  "",
                  f"    xattr -d com.apple.quarantine {program}",
                  "",
                  "  or open it, choose Done, then System Settings > Privacy & Security, find",
                  f"  \"{program}\" was blocked, choose Open Anyway and open it again.",
                  "  Double-clicked, it starts in your home folder, so its state is ~/server-data."]
    else:
        lines += [f"  In a terminal, in this folder:   ./{program}", "",
                  f"  (If your unzip lost the executable bit: chmod +x {program})"]
    lines += ["",
              "The console then lists the addresses players type into Groundhold's Join panel, and says",
              "the LAN beacon is on: games on the same network also list the server under Nearby. A",
              "firewall must let TCP port 8766 in, and UDP port 8767 for Nearby. Ctrl+C stops it.",
              "", "ITS STATE", "",
              "  server-data/ in the folder it starts in: the identity key and the moderation lists.",
              "  Keep it across upgrades and never publish it: without it every player's identity",
              "  changes and the bans are gone.",
              "", "SETTINGS", "",
              "  None are needed. To change one, copy server.example.ini to server.ini beside the",
              "  program, edit it and start the server again.",
              "", "MORE", "",
              f"  {GUIDE}",
              "  (hosting on the internet with a domain, moderation, backups, what is kept and for how long)",
              "",
              "LICENSE is the server's licence (MIT). BUILD.json says how this archive was built."]
    if target != "python":
        lines.append("licenses/ holds the notices of the Python runtime frozen into the program.")
    return "\n".join(lines) + "\n"


def native(work):
    """A one-file PyInstaller build of the server for this computer: its path."""
    try:
        installed = importlib.metadata.version("pyinstaller")
    except importlib.metadata.PackageNotFoundError:
        installed = None
    if installed != PYINSTALLER:
        raise RuntimeError(f"PyInstaller {PYINSTALLER} is needed (found {installed}): "
                           "pip install --require-hashes -r server/requirements-build.txt")
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--noupx",
            "--name", NAME, "--distpath", str(work / "dist"), "--workpath", str(work / "work"),
            "--specpath", str(work), "--paths", str(ROOT / "server"),
            # (protocol.json beside the package's modules, where protocol.py's files() looks)
            "--add-data", str(ROOT / "shared/net/protocol.json") + ":groundhold_server",
            str(ROOT / "server/main.py")]
    environment = dict(os.environ, PYTHONHASHSEED="0", SOURCE_DATE_EPOCH="315532800",
                       PYINSTALLER_CONFIG_DIR=str(work / "cache"))
    subprocess.run(args, cwd=ROOT, env=environment, check=True)
    return work / "dist" / (NAME + (".exe" if os.name == "nt" else ""))


def native_notices(work, target):
    """licenses/'s files for a native build: [(name, bytes)]."""
    notices, covered = collect(work)
    files = [(name, source.read_bytes()) for name, source, _ in notices]
    files.append(("README.md", notices_readme(notices, covered, target).encode()))
    package = importlib.metadata.distribution("pyinstaller")
    licence = package.locate_file(next(path for path in package.files if str(path).endswith("/COPYING.txt")))
    files.append(("PyInstaller.txt", Path(licence).read_bytes()))
    return files


def folder_name(version, target):
    """The one folder an archive holds: groundhold-server-1.2.3-linux-x64."""
    return f"{NAME}-{version}-{target}"


def archive(executable, target, output, version, notices=(), pyinstaller=None):
    """The release archive groundhold-server-TARGET.zip in `output`, its files in one folder
    (folder_name): its path."""
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f"{NAME}-{target}.zip"
    program = executable_name(target)
    metadata = {"target": target, "version": version, "executable": program,
                "python": platform.python_version(),
                "protocol": json.loads((ROOT / "shared/net/protocol.json").read_text(encoding="utf-8"))["version"]}
    if pyinstaller:
        metadata["pyinstaller"] = pyinstaller
    top = folder_name(version, target) + "/"
    with zipfile.ZipFile(destination, "w") as bundle:
        zip_entry(bundle, top + program, Path(executable).read_bytes(), executable=True)
        zip_entry(bundle, top + "README.txt", readme(target, version).encode())
        for source in (ROOT / "LICENSE", ROOT / "server/server.example.ini"):
            zip_entry(bundle, top + source.name, source.read_bytes())
        for name, data in notices:
            zip_entry(bundle, top + "licenses/" + name, data)
        zip_entry(bundle, top + "BUILD.json", (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode())
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--native", action="store_true",
                        help="Freeze for this computer's system with the pinned PyInstaller")
    parser.add_argument("--target", choices=sorted(set(TARGETS.values())),
                        help="With --native: the target this computer must build (refuses another)")
    parser.add_argument("--version", default="dev", help="The release's version, for BUILD.json and README.txt")
    parser.add_argument("--output", type=Path, default=ROOT / "build/release")
    parser.add_argument("--work", type=Path, default=ROOT / "build/server-release",
                        help="Where the build's intermediate files go (a folder per target, emptied first)")
    args = parser.parse_args(argv)
    if args.native:
        target = target_for(platform.system(), platform.machine())
        if target is None:
            parser.error(f"No release is built for {platform.system()} on {platform.machine()}")
        if args.target and args.target != target:
            parser.error(f"This computer builds {target}, not {args.target}")
    elif args.target:
        parser.error("--target applies only to --native")
    else:
        target = "python"
    work = args.work / target
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    if args.native:
        executable = native(work)
        destination = archive(executable, target, args.output, args.version, native_notices(work, target),
                              PYINSTALLER)
    else:
        destination = archive(build(work / executable_name(target)), target, args.output, args.version)
    try:
        smoke(destination)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    print(destination)
    return destination


if __name__ == "__main__":
    main()
