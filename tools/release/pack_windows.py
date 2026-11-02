"""The Windows game's two release files (tools/release/package.py windows):

    groundhold-windows-x64-setup.exe   an NSIS installer (packaging/windows/installer.nsi) for the
                                       user who runs it, no administrator: %LOCALAPPDATA%\\Programs\\Groundhold,
                                       a Start menu entry, a desktop shortcut if ticked, an entry in
                                       Settings > Apps whose uninstaller leaves the player's files
    groundhold-windows-x64.zip         the same files in one folder, Groundhold/, to unpack anywhere

Both hold Groundhold.exe as Godot exported it, with the brand's icon and the release's version
already written into it (export_presets.cfg's application/modify_resources; pe_resources.py checks
it), README-first.txt, LICENSE.txt and licenses/, every text file with Windows' line ends. The
installer is made by makensis (the packaging image's NSIS) from the staged folder.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import stat
import zipfile

import assemble
import package as common

EXE = "Groundhold.exe"
FOLDER = "Groundhold"  # the zip's one folder
NSI = common.PACKAGING / "windows" / "installer.nsi"
ICO = common.ICONS / "groundhold.ico"
SIDE = common.ICONS / "installer.bmp"  # the welcome and finish pages' picture (app_icon.py)
PARTS = ("zip", "setup")


def stage(export: Path, version: str, work: Path) -> Path:
    """work/Groundhold/ with what both files hold."""
    exe = export / EXE
    if not exe.is_file():
        raise common.PackError(f"{export} has no {EXE}")
    folder = work / FOLDER
    if folder.exists():
        shutil.rmtree(folder)
    (folder / "licenses").mkdir(parents=True)
    shutil.copyfile(exe, folder / EXE)
    (folder / common.README).write_bytes(common.readme("windows", version).encode("utf-8"))
    (folder / "LICENSE.txt").write_bytes(common.crlf(common.LICENSE.read_text(encoding="utf-8")).encode("utf-8"))
    for name, source in common.LICENSES.items():
        (folder / "licenses" / name).write_bytes(common.crlf(source.read_text(encoding="utf-8")).encode("utf-8"))
    return folder


def _entry(name: str, mode: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (mode & 0xFFFF) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def portable_zip(folder: Path, out: Path) -> Path:
    """groundhold-windows-x64.zip: the folder as Groundhold/, in a fixed order and time."""
    out.mkdir(parents=True, exist_ok=True)
    target = out / assemble.WINDOWS_ZIP
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            name = f"{FOLDER}/{path.relative_to(folder).as_posix()}"
            with path.open("rb") as stream:
                archive.writestr(_entry(name, stat.S_IFREG | 0o644), stream.read())
    return target


def setup_command(folder: Path, version: str, out: Path, makensis: str = "makensis") -> list[str]:
    size_kb = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) // 1024
    return [makensis, "-V2", "-INPUTCHARSET", "UTF8", f"-DVERSION={version}",
            f"-DFILEVERSION={common.file_version(version)}", f"-DSTAGE={folder.resolve()}",
            f"-DICON={ICO.resolve()}", f"-DSIDE={SIDE.resolve()}",
            f"-DOUT={(out / assemble.WINDOWS_SETUP).resolve()}",
            f"-DSIZE_KB={size_kb}", str(NSI)]


def setup(folder: Path, version: str, out: Path, makensis: str = "makensis") -> Path:
    """groundhold-windows-x64-setup.exe, made by makensis."""
    out.mkdir(parents=True, exist_ok=True)
    target = out / assemble.WINDOWS_SETUP
    target.unlink(missing_ok=True)
    common.run(setup_command(folder, version, out, makensis))
    if not target.is_file() or target.read_bytes()[:2] != b"MZ":
        raise common.PackError(f"makensis made no {target.name}")
    return target


def make(export: Path, version: str, out: Path, work: Path, only=None) -> list[Path]:
    parts = list(only or PARTS)
    wrong = sorted(set(parts) - set(PARTS))
    if wrong:
        raise common.PackError(f"no Windows part {', '.join(wrong)}: one of {', '.join(PARTS)}")
    folder = stage(export, version, work)
    made = []
    if "setup" in parts:
        made.append(setup(folder, version, out))
    if "zip" in parts:
        made.append(portable_zip(folder, out))
    return made
