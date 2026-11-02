#!/usr/bin/env python3
"""Build a deterministic, dependency-free zipapp of the server: no game assets.

Reused from Cyberworld Endless's server/build.py (MIT, Sascha Becker) with the
renames of docs/design/core-loop.md §6.10: the package groundhold_server, the
contract from shared/net/protocol.json.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile


def zip_entry(archive, name, data, executable=False):
    """Stable archive metadata, independent of checkout time and host OS."""
    entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    entry.create_system = 3
    entry.external_attr = (0o100755 if executable else 0o100644) << 16
    entry.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(entry, data, compresslevel=9)


def version_of(root):
    """project.godot's config/version, or "dev" where the tree has none (groundhold_server.build_info)."""
    try:
        found = re.search(r'^config/version="([^"]+)"', (root / "project.godot").read_text(encoding="utf-8"), re.M)
    except OSError:
        return "dev"
    return found.group(1) if found else "dev"


def commit_of(root, commit=None):
    """The commit built, 12 hex digits: given, or SOURCE_COMMIT (the image's build argument, which
    Coolify and server-image.yml pass), or the checkout's HEAD; None where none is known."""
    commit = commit or os.environ.get("SOURCE_COMMIT") or ""
    if not commit and (root / ".git").exists():
        try:
            commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
                                    timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            commit = ""
    commit = commit.strip().lower()
    return commit[:12] if re.fullmatch(r"[0-9a-f]{7,40}", commit) else None


def build_json(root, version=None, commit=None):
    """build.json's bytes: the release's version (else project.godot's) and the commit, what
    GET /health tells (groundhold_server/build_info.py)."""
    if not version or version == "dev":
        version = version_of(root)
    return (json.dumps({"build": commit_of(root, commit), "version": version}, sort_keys=True) + "\n").encode()


def build(output, version=None, commit=None):
    root = Path(__file__).resolve().parents[1]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        stream.write(b"#!/usr/bin/env python3\n")
        with zipfile.ZipFile(stream, "w") as archive:
            zip_entry(archive, "__main__.py", b"from groundhold_server.cli import main\nmain()\n")
            # Explicit source allowlist: never collect state, logs or the game.
            for source in sorted((root / "server/groundhold_server").glob("*.py")):
                zip_entry(archive, "groundhold_server/" + source.name, source.read_text(encoding="utf-8").encode())
            zip_entry(archive, "groundhold_server/protocol.json", (root / "shared/net/protocol.json").read_bytes())
            zip_entry(archive, "groundhold_server/build.json", build_json(root, version, commit))
            zip_entry(archive, "LICENSE", (root / "LICENSE").read_bytes())
    output.chmod(0o755)
    for source in (root / "LICENSE", root / "server/README.md", root / "server/server.example.ini"):
        destination = output.parent / source.name
        if source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
    return output


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output", type=Path, default=root / "build/server/groundhold-server.pyz")
    parser.add_argument("--version", help="The release's version for /health (default: project.godot's)")
    parser.add_argument("--commit", help="The commit built (default: SOURCE_COMMIT, else git's HEAD)")
    args = parser.parse_args()
    print(build(args.output, args.version, args.commit))


if __name__ == "__main__":
    main()
