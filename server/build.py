#!/usr/bin/env python3
"""Build a deterministic, dependency-free zipapp of the server: no game assets.

Reused from Cyberworld Endless's server/build.py (MIT, Sascha Becker) with the
renames of docs/design/core-loop.md §6.10: the package groundhold_server, the
contract from shared/net/protocol.json.
"""
import argparse
from pathlib import Path
import shutil
import zipfile


def zip_entry(archive, name, data, executable=False):
    """Stable archive metadata, independent of checkout time and host OS."""
    entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    entry.create_system = 3
    entry.external_attr = (0o100755 if executable else 0o100644) << 16
    entry.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(entry, data, compresslevel=9)


def build(output):
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
    args = parser.parse_args()
    print(build(args.output))


if __name__ == "__main__":
    main()
