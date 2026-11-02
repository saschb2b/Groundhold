"""Which build this server is, for GET /health: the release's version and the commit it was
built from, so a deploy can be checked and a game can tell it is out of date.

build.py (the zipapp, and with it the image) and release.py (the native programs) pack
build.json beside this module; a checkout reads project.godot's config/version and knows no
commit. Nothing else about the build is told: no Python, system or library versions, no paths.
"""

import json
import re
from importlib.resources import files
from pathlib import Path

VERSION_LINE = re.compile(r'^config/version="([^"]+)"', re.MULTILINE)


def version_of(root):
    """project.godot's config/version under `root`, or "dev" where there is none."""
    try:
        found = VERSION_LINE.search((Path(root) / "project.godot").read_text(encoding="utf-8"))
    except OSError:
        return "dev"
    return found.group(1) if found else "dev"


def _read():
    # (the zipapp and the native programs carry build.json beside this module: build.py,
    # release.py; a checkout reads the version from the repository)
    try:
        packed = json.loads(files(__package__).joinpath("build.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, NotADirectoryError, ValueError):
        return version_of(Path(__file__).resolve().parents[2]), None
    return str(packed.get("version") or "dev"), packed.get("build") or None


VERSION, BUILD = _read()
