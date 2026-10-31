#!/usr/bin/env python3
"""A native server archive's third-party notices, written at build time
(server/README.md, Releases; release.py puts them in the archive's licenses/).

Nothing here is committed: each freeze carries the notices of what it froze.
CPython's own comes from the building interpreter's LICENSE file (found as
site.py's license() finds it). Each native library PyInstaller froze from
outside that interpreter's install brings its licence file from the build
host: its Debian or Ubuntu package's copyright file, else the LICENSE or
COPYING file beside it (a Homebrew keg's). A library inside the
interpreter's install ships under the interpreter's own notices, as it does
in that interpreter. A frozen library with no notice found fails the build.

Reused from Cyberworld Endless's server/notices.py (MIT, Sascha Becker); the
README's words are Groundhold's, and a system's own Python (prefix /usr,
which every library of the system shares) counts only its standard library
as its install.
"""
import ast
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import sysconfig

NOTICE = re.compile(r"(licen[cs]e|copying|notice|copyright)([.-].*)?", re.IGNORECASE)


def interpreter_licence():
    """CPython's LICENSE as this interpreter carries it."""
    here = Path(getattr(sys, "_stdlib_dir", None) or os.path.dirname(os.__file__))
    for directory in (here.parent, here):
        for name in ("LICENSE.txt", "LICENSE"):
            if (directory / name).is_file():
                return directory / name
    raise RuntimeError("This Python carries no LICENSE file to ship; "
                       "freeze with one that does (python.org's, actions/setup-python's)")


def frozen_libraries(work):
    """The native libraries (not Python's extension modules) in PyInstaller's analysis."""
    found = {}

    def walk(value):
        if isinstance(value, (list, tuple)):
            if (len(value) == 3 and all(isinstance(part, str) for part in value)
                    and value[2] == "BINARY"):
                found[value[0]] = Path(value[1])
            else:
                for part in value:
                    walk(part)

    tocs = sorted(Path(work).rglob("Analysis-*.toc"))
    if not tocs:
        raise RuntimeError("PyInstaller's analysis was not found under " + str(work))
    for toc in tocs:
        walk(ast.literal_eval(toc.read_text(encoding="utf-8")))
    return found


def interpreter_root():
    """The interpreter's own install: its prefix, or for a system's Python,
    whose prefix (/usr) holds the system's libraries too, its standard library."""
    prefix = Path(sys.base_prefix)
    if prefix.resolve() in (Path("/usr"), Path("/")):
        return Path(sysconfig.get_paths()["stdlib"])
    return prefix


def inside(path, root):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def debian_copyright(path):
    """The copyright file of the Debian package that owns a library, if any."""
    if not shutil.which("dpkg-query"):
        return None
    candidates = {str(path), str(path.resolve())}
    for text in list(candidates):
        # merged-/usr systems: dpkg may know either spelling
        candidates.add(text[4:] if text.startswith("/usr/") else "/usr" + text)
    for candidate in sorted(candidates):
        result = subprocess.run(["dpkg-query", "-S", candidate], capture_output=True, text=True)
        if result.returncode == 0:
            package = result.stdout.split(":", 1)[0].split(",")[0].strip()
            copyright = Path("/usr/share/doc") / package / "copyright"
            if copyright.is_file():
                return package, [copyright]
    return None


def nearby_notices(path):
    """LICENSE/COPYING files in the library's directory or up to three above it."""
    directory = path.resolve().parent
    for _ in range(4):
        files = sorted(entry for entry in directory.iterdir() if entry.is_file() and NOTICE.fullmatch(entry.name))
        if files:
            return directory.name, files
        directory = directory.parent
    return None


def collect(work):
    """[(archive name, source path, what it covers)] for licenses/, and
    {archive name: [libraries it covers]}; RuntimeError for a library with
    no notice."""
    python = interpreter_licence()
    notices = [("Python.txt", python, f"CPython {platform.python_version()} ({python})")]
    prefix = interpreter_root()
    covered, missing = {}, []
    for name, path in sorted(frozen_libraries(work).items()):
        if inside(path, prefix) or name.lower().startswith(("libpython", "python")):
            covered.setdefault("Python.txt", []).append(name)
            continue
        found = debian_copyright(path) or nearby_notices(path)
        if not found:
            missing.append(f"{name} ({path})")
            continue
        package, files = found
        for index, source in enumerate(files):
            target = f"{package}.txt" if len(files) == 1 else f"{package}-{source.name}.txt"
            if target not in covered:
                notices.append((target, source, f"{package} ({source})"))
            covered.setdefault(target, [])
            if index == 0:
                covered[target].append(name)
    if missing:
        raise RuntimeError("No licence file on this build host for the frozen libraries: " + ", ".join(missing))
    return notices, covered


def readme(notices, covered, target):
    """licenses/README.md: which file covers which frozen library."""
    lines = ["# The standalone server's runtime notices", "",
             f"Written when `{target}` was frozen, from the build host's own files.",
             "The server is Groundhold's own code (`LICENSE`, MIT); it is frozen with",
             "an unmodified CPython and the PyInstaller bootloader. No part of the game",
             "is bundled.", ""]
    for name, _, origin in notices:
        libraries = ", ".join(f"`{library}`" for library in covered.get(name, []))
        lines.append(f"- `{name}`: {origin}" + (f"; covers {libraries}" if libraries else ""))
    lines += ["- `PyInstaller.txt`: the pinned PyInstaller wheel's licence, with its bootloader exception", "",
              "`BUILD.json` names the interpreter version and target."]
    return "\n".join(lines) + "\n"
