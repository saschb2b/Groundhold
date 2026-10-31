#!/usr/bin/env python3
"""Packs a desktop export as a release file: groundhold-<platform>.zip (tools/release/assemble.py's
GAME names them all).

    python3 tools/release/package.py --version 1.0.0 --platform linux-x64 build/desktop/linux --out dist
    python3 tools/release/package.py --version 1.0.0 --platform windows-x64 build/desktop/windows --out dist
    python3 tools/release/package.py --version 1.0.0 --platform macos build/desktop/macos/Groundhold.zip --out dist

The zip's name has no version, so a link to the newest release's file stays the same from release
to release (releases/latest/download/groundhold-windows-x64.zip). It holds one folder,
groundhold-<version>-<platform>/, with the export and a README-first.txt written from
tools/release/readme/<os>.txt (how to start it on that system, online and LAN play, and for macOS
the quarantine steps of an unsigned app). The export is a folder (Linux, Windows: its files, their
modes kept, so the Linux binary stays executable) or a zip (Godot's macOS export: its entries
copied as they are, the app's executable bit with them). Standard library only.
"""

import argparse
import os
from pathlib import Path
import stat
import string
import sys
import zipfile

HERE = Path(__file__).resolve().parent
PLATFORMS = {"linux-x64": "linux", "windows-x64": "windows", "macos": "macos"}
README = "README-first.txt"


def readme(platform: str, version: str) -> str:
    template = (HERE / "readme" / (PLATFORMS[platform] + ".txt")).read_text(encoding="utf-8")
    text = string.Template(template).substitute(version=version, folder=folder_name(version, platform))
    return text.replace("\r\n", "\n").replace("\n", "\r\n") if PLATFORMS[platform] == "windows" else text


def folder_name(version: str, platform: str) -> str:
    return f"groundhold-{version}-{platform}"


def zip_name(platform: str) -> str:
    return f"groundhold-{platform}.zip"


def _entry(name: str, mode: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (mode & 0xFFFF) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def package(source: Path, version: str, platform: str, out: Path) -> Path:
    if platform not in PLATFORMS:
        raise ValueError(f"no platform {platform!r}: one of {', '.join(PLATFORMS)}")
    top = folder_name(version, platform)
    out.mkdir(parents=True, exist_ok=True)
    target = out / zip_name(platform)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(_entry(f"{top}/{README}", stat.S_IFREG | 0o644), readme(platform, version))
        if source.is_dir():
            files = sorted(p for p in source.rglob("*") if p.is_file())
            if not files:
                raise ValueError(f"{source} is empty")
            for path in files:
                mode = path.stat().st_mode
                with path.open("rb") as stream:
                    archive.writestr(_entry(f"{top}/{path.relative_to(source).as_posix()}", mode), stream.read())
        elif zipfile.is_zipfile(source):
            with zipfile.ZipFile(source) as export:
                infos = export.infolist()
                if not infos:
                    raise ValueError(f"{source} is empty")
                for info in infos:
                    copied = zipfile.ZipInfo(f"{top}/{info.filename}", info.date_time)
                    copied.create_system = info.create_system
                    copied.external_attr = info.external_attr
                    copied.compress_type = zipfile.ZIP_STORED if info.is_dir() else zipfile.ZIP_DEFLATED
                    archive.writestr(copied, b"" if info.is_dir() else export.read(info))
        else:
            raise ValueError(f"{source} is neither a folder nor a zip")
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source", type=Path, help="the export: a folder, or Godot's macOS zip")
    parser.add_argument("--version", required=True)
    parser.add_argument("--platform", required=True, choices=sorted(PLATFORMS))
    parser.add_argument("--out", type=Path, default=Path("dist"))
    args = parser.parse_args(argv)
    try:
        target = package(args.source, args.version, args.platform, args.out)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    print(f"{target} ({os.path.getsize(target) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
