"""The macOS game's release file, groundhold-macos.dmg (tools/release/package.py macos; on a Mac,
release.yml's macos job on macos-15):

    Groundhold.app      Godot's universal app (Info.plist from the export preset: the bundle id
                        io.github.saschb2b.Groundhold, the versions, the icon, LSMinimumSystemVersion,
                        the category, NSHighResolutionCapable), the licences added in
                        Contents/Resources/licenses, then signed ad hoc, as Apple silicon runs
                        nothing unsigned: codesign --force --deep --sign -, then --verify --strict
    Applications        a link to /Applications to drag it onto
    Read me.txt         tools/release/readme/macos.txt: Gatekeeper's steps for an app not notarised

made by hdiutil create -format UDZO and checked with hdiutil verify. Godot's export zip is unpacked
here with its files' modes (the app's executable keeps its bit); codesign and hdiutil are Apple's.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import stat
import zipfile

import assemble
import package as common

APP = "Groundhold.app"
VOLUME = "Groundhold"
READ_ME = "Read me.txt"


def unpack(export: Path, stage: Path) -> Path:
    """Godot's macOS export zip into `stage`, modes kept; the app's path."""
    if not zipfile.is_zipfile(export):
        raise common.PackError(f"{export} is not Godot's macOS export zip")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    with zipfile.ZipFile(export) as archive:
        for info in archive.infolist():
            target = (stage / info.filename).resolve()
            if not target.is_relative_to(stage.resolve()):
                raise common.PackError(f"{export} holds {info.filename}, outside its folder")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):  # (a framework's Versions/Current, should the app ever carry one)
                target.symlink_to(archive.read(info).decode("utf-8"))
                continue
            target.write_bytes(archive.read(info))
            target.chmod((mode & 0o777) or 0o644)
    app = stage / APP
    binary = app / "Contents" / "MacOS" / "Groundhold"
    if not binary.is_file():
        raise common.PackError(f"{export} holds no {APP}/Contents/MacOS/Groundhold")
    binary.chmod(binary.stat().st_mode | 0o111)
    licenses = app / "Contents" / "Resources" / "licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    for name, source in {"LICENSE.txt": common.LICENSE, **common.LICENSES}.items():
        shutil.copyfile(source, licenses / name)
        (licenses / name).chmod(0o644)
    for folder in [stage, *[p for p in stage.rglob("*") if p.is_dir() and not p.is_symlink()]]:
        folder.chmod(0o755)
    return app


def sign(app: Path, codesign: str = "codesign") -> None:
    common.run([codesign, "--force", "--deep", "--sign", "-", app])
    common.run([codesign, "--verify", "--deep", "--strict", app])


def disk_image(stage: Path, version: str, out: Path, hdiutil: str = "hdiutil") -> Path:
    """The Applications link and the Read me beside the app, then the image of it all."""
    (stage / "Applications").symlink_to("/Applications")
    (stage / READ_ME).write_text(common.readme("macos", version), encoding="utf-8")
    (stage / READ_ME).chmod(0o644)
    out.mkdir(parents=True, exist_ok=True)
    target = out / assemble.MACOS_DMG
    target.unlink(missing_ok=True)
    common.run([hdiutil, "create", "-volname", VOLUME, "-srcfolder", stage, "-ov", "-format", "UDZO", target])
    if not target.is_file():
        raise common.PackError(f"hdiutil made no {target.name}")
    common.run([hdiutil, "verify", target])
    return target


def make(export: Path, version: str, out: Path, work: Path) -> list[Path]:
    stage = work / "dmg"
    app = unpack(export, stage)
    sign(app)
    return [disk_image(stage, version, out)]
