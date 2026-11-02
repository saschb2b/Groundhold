"""The Linux game's release files, all from one install tree (tools/release/package.py linux):

    usr/lib/groundhold/groundhold                         the export (its pack embedded)
    usr/share/applications/io.github.saschb2b.Groundhold.desktop
    usr/share/icons/hicolor/<n>x<n>/apps/io.github.saschb2b.Groundhold.png   16 to 512 px (app_icon.py)
    usr/share/metainfo/io.github.saschb2b.Groundhold.metainfo.xml      AppStream, with this release's line
    usr/share/doc/groundhold/                             LICENSE and licenses/

    groundhold-x86_64.AppImage   the tree in an AppDir (AppRun, the .desktop, the icon, .DirIcon),
                                 made by appimagetool 1.9.1 on the static type-2 runtime (no libfuse2
                                 needed; APPIMAGE_EXTRACT_AND_RUN=1 where there is no FUSE), its update
                                 information gh-releases-zsync|saschb2b|Groundhold|latest|<name>.zsync
    ....AppImage.zsync           that update file (zsyncmake, called by appimagetool), beside it
    groundhold_amd64.deb         the tree, a /usr/bin/groundhold link, a DEP-5 copyright, its control
                                 and md5sums, by dpkg-deb --root-owner-group -Zxz
    groundhold-linux-x64.tar.gz  one folder, Groundhold/: the game, README-first.txt, the licences,
                                 icons/ and install.sh, which writes a menu entry for the user
                                 (--remove takes it away)

appimagetool, zsyncmake and dpkg-deb are the packaging image's (packaging/Dockerfile); the tar.gz is
Python's, reproducible (fixed times, owners and order).
"""

from __future__ import annotations

import datetime
import gzip
import hashlib
import io
import os
from pathlib import Path
import shutil
import tarfile
import tempfile

import app_icon
import assemble
import package as common

BINARY = "groundhold"  # the command, in /usr/bin and the tar.gz
EXPORT = "groundhold.x86_64"  # what the Linux preset exports
FOLDER = "Groundhold"  # the tar.gz's one folder
DOC = "groundhold"  # usr/share/doc/<package>
LINUX = common.PACKAGING / "linux"
DESKTOP = LINUX / f"{common.APP_ID}.desktop"
METAINFO = LINUX / f"{common.APP_ID}.metainfo.xml"
INSTALL_SH = LINUX / "install.sh"
RUNTIME = "/opt/appimage/runtime-x86_64"  # the packaging image's (packaging/appimage.sh)
UPDATE = f"gh-releases-zsync|{common.REPOSITORY.replace('/', '|')}|latest|{assemble.ZSYNC}"
PARTS = ("appimage", "deb", "tarball")
DESCRIPTION = """\
co-op tower defense for one to four players
 Every land was raised out of the Tide, and the Tide wants it back. Each
 player is a Builder with three towers of their own, and the party holds
 one road together, from the Welling, where the Tide wells up, to the
 Holdfast. Play alone, or with up to three others online on the official
 server or over your own network."""


def export_binary(export: Path) -> Path:
    binary = export / EXPORT if export.is_dir() else export
    if not binary.is_file():
        raise common.PackError(f"{export} has no {EXPORT}")
    return binary


def metainfo(version: str, date: str) -> str:
    """The AppStream data with this release's line in place of its placeholder."""
    text = METAINFO.read_text(encoding="utf-8")
    line = (f'<release version="{version}" date="{date}">\n      <url type="details">'
            f"https://github.com/{common.REPOSITORY}/releases/tag/v{version}</url>\n    </release>")
    if "<!-- release -->" not in text:
        raise common.PackError(f"{METAINFO.name} has no <!-- release --> placeholder")
    return text.replace("<!-- release -->", line)


def _write(path: Path, data: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(mode)


def install_tree(binary: Path, root: Path, version: str, date: str) -> Path:
    """The installed layout under root/usr; the program's path."""
    if root.exists():
        shutil.rmtree(root)
    usr = root / "usr"
    program = usr / "lib" / BINARY / BINARY
    program.parent.mkdir(parents=True)
    shutil.copyfile(binary, program)
    program.chmod(0o755)
    share = usr / "share"
    _write(share / "applications" / DESKTOP.name, DESKTOP.read_bytes())
    for n in app_icon.PNG_SIZES:
        _write(share / "icons" / "hicolor" / f"{n}x{n}" / "apps" / f"{common.APP_ID}.png",
               (common.ICONS / f"{n}.png").read_bytes())
    _write(share / "metainfo" / METAINFO.name, metainfo(version, date).encode("utf-8"))
    doc = share / "doc" / DOC
    _write(doc / "LICENSE", common.LICENSE.read_bytes())
    for name, source in common.LICENSES.items():
        _write(doc / "licenses" / name, source.read_bytes())
    for folder in [root, *[p for p in root.rglob("*") if p.is_dir()]]:
        folder.chmod(0o755)
    return program


def validate(root: Path) -> list[str]:
    """The tree's menu entry and AppStream data checked by desktop-file-validate and appstreamcli (the
    packaging image has both; where one is missing it is named, not run)."""
    share = root / "usr" / "share"
    skipped = []
    for tool, args in (("desktop-file-validate", [share / "applications" / DESKTOP.name]),
                       ("appstreamcli", ["validate", "--no-net", share / "metainfo" / METAINFO.name])):
        if shutil.which(tool):
            common.run([tool, *args])
        else:
            skipped.append(tool)
    return skipped


def appdir(binary: Path, root: Path, version: str, date: str) -> Path:
    """The AppImage's AppDir: the tree, AppRun, the .desktop and the 256 px icon at its top."""
    install_tree(binary, root, version, date)
    run = root / "AppRun"
    _write(run, b'#!/bin/sh\nhere="$(dirname "$(readlink -f "$0")")"\n'
                b'exec "$here/usr/lib/groundhold/groundhold" "$@"\n', 0o755)
    _write(root / DESKTOP.name, DESKTOP.read_bytes())
    _write(root / f"{common.APP_ID}.png", (common.ICONS / "256.png").read_bytes())
    (root / ".DirIcon").symlink_to(f"{common.APP_ID}.png")
    return root


def appimage(root: Path, out: Path, tool: str = "appimagetool", runtime: str = RUNTIME) -> list[Path]:
    """groundhold-x86_64.AppImage and its .zsync, made by appimagetool in `out`."""
    out.mkdir(parents=True, exist_ok=True)
    targets = [out / assemble.APPIMAGE, out / assemble.ZSYNC]
    for target in targets:
        target.unlink(missing_ok=True)
    # (a home of its own: a container's user may have none it can write)
    with tempfile.TemporaryDirectory(prefix="groundhold-appimage-") as home:
        env = dict(os.environ, ARCH="x86_64", HOME=home)
        common.run([tool, "--runtime-file", runtime, "--updateinformation", UPDATE, root.resolve(),
                    assemble.APPIMAGE], cwd=out, env=env)
    for target in targets:
        if not target.is_file() or target.stat().st_size == 0:
            raise common.PackError(f"appimagetool made no {target.name}")
    targets[0].chmod(0o755)
    return targets


def copyright_file() -> str:
    """Debian's machine-readable copyright (DEP-5) for the package."""
    def text(path: Path) -> str:
        lines = path.read_text(encoding="utf-8").strip("\n").splitlines()
        return "\n".join(" " + line if line.strip() else " ." for line in lines)

    return (
        "Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/\n"
        f"Upstream-Name: {common.NAME}\n"
        f"Source: https://github.com/{common.REPOSITORY}\n\n"
        "Files: *\n"
        "Copyright: 2026 Sascha Becker\n"
        "License: Expat\n\n"
        f"Files: usr/lib/{BINARY}/{BINARY}\n"
        "Copyright: 2026 Sascha Becker\n"
        " 2014-present Godot Engine contributors\n"
        " 2007-2014 Juan Linietsky, Ariel Manzur\n"
        " 2022 The Noto Project Authors\n"
        "License: Expat and OFL-1.1\n"
        "Comment: The game runs on Godot Engine (licenses/Godot-Engine.txt, which links the\n"
        " engine's own COPYRIGHT.txt for its third-party components) and embeds the Noto Serif\n"
        " fonts (licenses/Noto-fonts-OFL.txt).\n\n"
        f"License: Expat\n{text(common.LICENSE)}\n\n"
        f"License: OFL-1.1\n{text(common.LICENSES['Noto-fonts-OFL.txt'])}\n"
    )


def control(version: str, installed_kb: int) -> str:
    return (f"Package: {BINARY}\n"
            f"Version: {version}\n"
            "Architecture: amd64\n"
            "Maintainer: Sascha Becker <saschb2b@gmail.com>\n"
            f"Installed-Size: {installed_kb}\n"
            "Depends: libc6 (>= 2.28)\n"
            # (the engine loads these itself at run time, so no shared-library check finds them; every
            # desktop has them, a minimal system may not)
            "Recommends: libvulkan1, libgl1, libx11-6, libxcursor1, libxinerama1, libxrandr2, libxi6, libxext6, "
            "libpulse0 | libasound2t64 | libasound2\n"
            "Section: games\n"
            "Priority: optional\n"
            f"Homepage: {common.HOMEPAGE}\n"
            f"Description: {DESCRIPTION}\n")


def deb_root(binary: Path, root: Path, version: str, date: str) -> Path:
    """The .deb's tree: the install tree, /usr/bin/groundhold, the copyright and DEBIAN/control."""
    install_tree(binary, root, version, date)
    (root / "usr" / "bin").mkdir()
    (root / "usr" / "bin").chmod(0o755)
    (root / "usr" / "bin" / BINARY).symlink_to(f"../lib/{BINARY}/{BINARY}")
    _write(root / "usr" / "share" / "doc" / DOC / "copyright", copyright_file().encode("utf-8"))
    size = sum(p.stat().st_size for p in root.rglob("*") if p.is_file() and not p.is_symlink())
    (root / "DEBIAN").mkdir()
    (root / "DEBIAN").chmod(0o755)
    _write(root / "DEBIAN" / "control", control(version, (size + 1023) // 1024).encode("utf-8"))
    _write(root / "DEBIAN" / "md5sums", md5sums(root).encode("utf-8"))
    return root


def md5sums(root: Path) -> str:
    """DEBIAN/md5sums: every file the package installs (no link, nothing of DEBIAN), by its path, so
    dpkg --verify and debsums can check them."""
    files = sorted(p for p in root.rglob("*") if p.is_file() and not p.is_symlink()
                   and p.relative_to(root).parts[0] != "DEBIAN")
    lines = []
    for path in files:
        digest = hashlib.md5()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1 << 20), b""):
                digest.update(block)
        lines.append(f"{digest.hexdigest()}  {path.relative_to(root).as_posix()}\n")
    return "".join(lines)


def epoch(date: str) -> int:
    return int(datetime.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp())


def deb(root: Path, out: Path, date: str, tool: str = "dpkg-deb") -> Path:
    """groundhold_amd64.deb; its files' times no later than the release's date (SOURCE_DATE_EPOCH)."""
    out.mkdir(parents=True, exist_ok=True)
    target = out / assemble.DEB
    target.unlink(missing_ok=True)
    common.run([tool, "--root-owner-group", "-Zxz", "--build", root, target],
               env=dict(os.environ, SOURCE_DATE_EPOCH=str(epoch(date))))
    return target


def tarball(binary: Path, version: str, out: Path, date: str) -> Path:
    """groundhold-linux-x64.tar.gz: Groundhold/ with the game, README-first.txt, the licences, icons/ and
    install.sh, owned by root, every time the release's date, in a fixed order."""
    when = epoch(date)
    files: list[tuple[str, bytes, int]] = [
        (BINARY, binary.read_bytes(), 0o755),
        ("install.sh", INSTALL_SH.read_bytes(), 0o755),
        (common.README, common.readme("linux", version).encode("utf-8"), 0o644),
        ("LICENSE", common.LICENSE.read_bytes(), 0o644),
    ]
    files += [(f"licenses/{name}", source.read_bytes(), 0o644) for name, source in common.LICENSES.items()]
    files += [(f"icons/{n}.png", (common.ICONS / f"{n}.png").read_bytes(), 0o644) for n in app_icon.PNG_SIZES]
    out.mkdir(parents=True, exist_ok=True)
    target = out / assemble.LINUX_TAR

    def entry(name: str, kind: bytes, mode: int, size: int = 0) -> tarfile.TarInfo:
        info = tarfile.TarInfo(name)
        info.type, info.mode, info.size, info.mtime = kind, mode, size, when
        info.uid = info.gid = 0
        info.uname = info.gname = "root"
        return info

    with open(target, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=when,
                                                  compresslevel=9) as zipped, \
            tarfile.open(fileobj=zipped, mode="w", format=tarfile.GNU_FORMAT) as tar:
        folders = sorted({FOLDER} | {f"{FOLDER}/{name.rsplit('/', 1)[0]}" for name, _, _ in files if "/" in name})
        for folder in folders:
            tar.addfile(entry(folder, tarfile.DIRTYPE, 0o755))
        for name, data, mode in sorted(files):
            tar.addfile(entry(f"{FOLDER}/{name}", tarfile.REGTYPE, mode, len(data)), io.BytesIO(data))
    return target


def make(export: Path, version: str, out: Path, work: Path, only=None, date: str | None = None) -> list[Path]:
    parts = list(only or PARTS)
    wrong = sorted(set(parts) - set(PARTS))
    if wrong:
        raise common.PackError(f"no Linux part {', '.join(wrong)}: one of {', '.join(PARTS)}")
    binary = export_binary(export)
    date = date or common.release_date(version)
    install_tree(binary, work / "tree", version, date)
    for tool in validate(work / "tree"):
        print(f"(no {tool} here: the tree is not validated by it)")
    made = []
    if "appimage" in parts:
        made += appimage(appdir(binary, work / "AppDir", version, date), out)
    if "deb" in parts:
        made.append(deb(deb_root(binary, work / "deb", version, date), out, date))
    if "tarball" in parts:
        made.append(tarball(binary, version, out, date))
    return made

