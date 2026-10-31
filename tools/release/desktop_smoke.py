#!/usr/bin/env python3
"""Boots an exported desktop game headless to the hub and quits: a release's Linux build must
start, read its data and stand the hub before it ships.

    python3 tools/release/desktop_smoke.py build/desktop/linux/groundhold.x86_64 [--build-seq 42]

It runs the binary with `--headless --quit-after N` (N frames) in a fresh home folder (so it
never reads or writes the player's own user://), and passes when the binary exits 0 within the
timeout, printed no engine or script error, and printed the hub's banner (Session.banner) with
project.godot's version, the expected build number and data/net.json's official server, so a
build that lost data/net.json or data/build.json is caught. Standard library only.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import gate  # noqa: E402

ERRORS = re.compile(r"^(?:ERROR|SCRIPT ERROR|USER ERROR|FATAL|CrashHandlerException|Parse Error)\b|^\s+at: ", re.M)


def expected_banner(root: Path, build_seq: int) -> str:
    official = json.loads((root / "data" / "net.json").read_text(encoding="utf-8"))["official"]
    return f"Groundhold {gate.project_version(root)} (build {build_seq}), official server {official}"


def run(binary: Path, frames: int, timeout: float) -> tuple[int, str]:
    with tempfile.TemporaryDirectory(prefix="groundhold-smoke-") as home:
        env = dict(os.environ, HOME=home, XDG_DATA_HOME=os.path.join(home, "data"),
                   XDG_CONFIG_HOME=os.path.join(home, "config"), XDG_CACHE_HOME=os.path.join(home, "cache"))
        try:
            done = subprocess.run([str(binary), "--headless", "--quit-after", str(frames)], env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                  errors="replace", timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "replace")
            return -1, out + f"\n(still running after {timeout:.0f} s: stopped)"
        return done.returncode, done.stdout


def check(code: int, output: str, banner: str) -> list[str]:
    out = []
    if code != 0:
        out.append(f"the game exited with {code}")
    if banner not in output.splitlines():
        out.append(f"no banner '{banner}'")
    errors = ERRORS.findall(output)
    if errors:
        out.append(f"{len(errors)} error line(s)")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("binary", type=Path)
    parser.add_argument("--build-seq", type=int, default=0, help="the build number data/build.json gave the export")
    parser.add_argument("--frames", type=int, default=300, help="frames to run before quitting (default 300)")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--root", type=Path, default=ROOT, help="the tree it was exported from")
    args = parser.parse_args(argv)
    code, output = run(args.binary, args.frames, args.timeout)
    print(output)
    found = check(code, output, expected_banner(args.root, args.build_seq))
    for problem in found:
        print(f"::error title=Desktop boot::{args.binary.name}: {problem}", file=sys.stderr)
    if not found:
        print(f"{args.binary.name}: booted to the hub and quit")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
