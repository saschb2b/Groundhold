#!/usr/bin/env python3
"""The release gate (docs/design/core-loop.md 7.6): a tag releases only the version the tree says
it is, and only with its notes written and dated.

    python3 tools/release/gate.py plan              # what this run of release.yml releases, from its
                                                    # environment: tag, version and publish as
                                                    # key=value lines, to $GITHUB_OUTPUT too
    python3 tools/release/gate.py check v1.0.0      # exit 1 with every reason, unless the tag is
                                                    # vX.Y.Z, project.godot's config/version is X.Y.Z
                                                    # and CHANGELOG.md has a "## X.Y.Z · YYYY-MM-DD"
                                                    # section with text in it (--dry-run: a heading
                                                    # without its date only warns)
    python3 tools/release/gate.py notes v1.0.0      # the release's notes: that section, then what
                                                    # each file is and how to start it
    python3 tools/release/gate.py version           # project.godot's config/version
    python3 tools/release/gate.py on-main <commit> origin/main
                                                    # exit 1 unless the commit is on main (a
                                                    # release is a tag on main; --dry-run warns)

release.yml runs `plan` and `check` before it builds anything and `notes` for the GitHub release.
A pushed tag is published. A run by hand is a dry run unless dry_run is false, which needs an
existing tag; a dry run without a tag releases nothing at project.godot's version. The CHANGELOG's
headings read "## 1.0.0 · 2026-11-02": the version, then anything after a space, which must hold
the release's date; "## 0.6.0 · TBD" is a release being prepared. `--root` points it at another
tree (its tests do). Python 3.11 or newer, standard library only.
"""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import assemble  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TAG = re.compile(r"v(\d+\.\d+\.\d+)")
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
REPOSITORY = "https://github.com/saschb2b/Groundhold"


class GateError(Exception):
    """A run that cannot go on, with what to do about it."""


def project_version(root: Path) -> str:
    """project.godot's application/config/version, "" without one."""
    section = ""
    for line in (root / "project.godot").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
        elif section == "application" and line.startswith("config/version="):
            value = line.split("=", 1)[1].strip()
            return value[1:-1] if len(value) >= 2 and value[0] == value[-1] == '"' else value
    return ""


def _section(root: Path, version: str):
    path = root / "CHANGELOG.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    return re.search(r"^## " + re.escape(version) + r"([ \t][^\n]*)?\n(.*?)(?=^## |\Z)", text, re.M | re.S)


def changelog_section(root: Path, version: str) -> str | None:
    """The text under CHANGELOG.md's "## <version>" heading up to the next "## ", stripped;
    None when there is no such heading."""
    found = _section(root, version)
    return found.group(2).strip() if found else None


def changelog_heading(root: Path, version: str) -> str | None:
    """What follows the version on its heading ("· 2026-11-02"), stripped; None without one."""
    found = _section(root, version)
    return (found.group(1) or "").strip() if found else None


def problems(root: Path, tag: str, need_date: bool = True) -> list[str]:
    """Why `tag` may not be released from the tree at `root`; empty when it may."""
    out = []
    matched = TAG.fullmatch(tag)
    if not matched:
        return [f"the tag {tag!r} is not vX.Y.Z"]
    version = matched.group(1)
    have = project_version(root)
    if have == "":
        out.append("project.godot has no application/config/version")
    elif have != version:
        out.append(f"the tag is {tag} but project.godot's config/version is {have}")
    notes = changelog_section(root, version)
    if notes is None:
        out.append(f"CHANGELOG.md has no section '## {version}'")
    elif notes == "":
        out.append(f"CHANGELOG.md's section '## {version}' is empty")
    elif need_date and not DATE.search(changelog_heading(root, version)):
        heading = f"## {version} {changelog_heading(root, version)}".rstrip()
        out.append(f"CHANGELOG.md's heading '{heading}' has no date: write the release's (YYYY-MM-DD) on it, "
                   f"as '## {version} · 2026-11-02'")
    return out


def plan(environ, root: Path) -> dict:
    """{tag, version, publish} for this run of release.yml, from the environment its gate job sets
    (EVENT, REF_TYPE, REF_NAME, INPUT_TAG, INPUT_DRY_RUN); GateError for a run that releases nothing
    it could name."""
    event = environ.get("EVENT", "")
    if event == "push":
        if environ.get("REF_TYPE") != "tag":
            raise GateError("a release starts from a pushed tag vX.Y.Z")
        tag, dry = environ.get("REF_NAME", ""), False
    elif event == "workflow_dispatch":
        tag, dry = environ.get("INPUT_TAG", "").strip(), environ.get("INPUT_DRY_RUN", "true") != "false"
        if not tag and not dry:
            raise GateError("publishing needs a tag: give the run an existing tag vX.Y.Z, or leave it a dry run")
    else:
        raise GateError(f"release.yml runs on a tag or by hand, not on {event or 'nothing'}")
    if tag:
        matched = TAG.fullmatch(tag)
        if not matched:
            raise GateError(f"the tag {tag!r} is not vX.Y.Z")
        version = matched.group(1)
    else:
        version = project_version(root)
        if not re.fullmatch(r"\d+\.\d+\.\d+", version):
            raise GateError(f"project.godot's config/version {version!r} is not X.Y.Z")
    return {"tag": tag, "version": version, "publish": "false" if dry else "true"}


def files_table() -> str:
    rows = "".join(f"| `{name}` | {assemble.WHAT[name]} |\n" for name in assemble.FILES + [assemble.SUMS])
    return "| File | What it is |\n| --- | --- |\n" + rows


def notes(root: Path, tag: str) -> str:
    """The release's notes: CHANGELOG.md's section for the tag's version, then the files and how to
    start them (README.md's Play together says the same at more length)."""
    version = TAG.fullmatch(tag).group(1)
    return f"""{changelog_section(root, version)}

## Files

{files_table()}
The browser game is at https://saschb2b.github.io/Groundhold/play/ and plays online on the official
server, `wss://groundhold.saschb2b.com/causeway`, whose policy is
https://saschb2b.github.io/Groundhold/policy.html. The desktop game plays there too, and on your own
network with one of the server's archives above. The server's image is
`ghcr.io/saschb2b/groundhold-server:{version}`; [server/README.md]({REPOSITORY}/blob/main/server/README.md)
says how to host one.

**macOS:** the game and the server are not signed or notarised by Apple, so macOS refuses to open
them the first time ("cannot be opened" or "is damaged"). Once, in Terminal:
`xattr -dr com.apple.quarantine /Applications/Groundhold.app` (the server:
`xattr -d com.apple.quarantine groundhold-server` in its folder). Without Terminal, for "cannot be
opened": Control-click `Groundhold.app`, choose Open, then Open; or, after the refusal,
**System Settings > Privacy & Security > Open Anyway**. Each zip's README-first.txt says more.

**Windows:** the builds are not signed either: if SmartScreen says it protected your PC, choose
**More info**, then **Run anyway**.
"""


def on_main(commit: str, main_ref: str, repo: Path) -> str | None:
    """None when `commit` is `main_ref` or one of its ancestors, else what is wrong."""
    done = subprocess.run(["git", "merge-base", "--is-ancestor", commit, main_ref], cwd=repo, check=False,
                          capture_output=True, text=True)
    if done.returncode == 0:
        return None
    if done.returncode == 1:
        return f"{commit} is not on {main_ref}: a release is a tag on main"
    return f"cannot tell whether {commit} is on {main_ref}: {done.stderr.strip()}"


def main(argv=None, environ=None) -> int:
    environ = os.environ if environ is None else environ
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="the tree to read (default: this checkout)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan", help="what this run of release.yml releases")
    check = sub.add_parser("check", help="exit 1 unless the tag may be released")
    check.add_argument("tag")
    check.add_argument("--dry-run", action="store_true", help="a heading without its date only warns")
    sub.add_parser("notes", help="print the release's notes").add_argument("tag")
    sub.add_parser("version", help="print project.godot's config/version")
    branch = sub.add_parser("on-main", help="exit 1 unless the commit is on main")
    branch.add_argument("commit")
    branch.add_argument("main_ref", nargs="?", default="origin/main")
    branch.add_argument("--dry-run", action="store_true", help="only warn")
    args = parser.parse_args(argv)
    if args.command == "version":
        print(project_version(args.root))
        return 0
    if args.command == "on-main":
        problem = on_main(args.commit, args.main_ref, args.root)
        if problem is None:
            print(f"{args.commit} is on {args.main_ref}")
            return 0
        print(f"::{'warning' if args.dry_run else 'error'} title=Release gate::{problem}"
              + (" (a dry run goes on)" if args.dry_run else ""), file=sys.stderr)
        return 0 if args.dry_run else 1
    if args.command == "plan":
        try:
            found = plan(environ, args.root)
        except GateError as exc:
            print(f"::error title=Release gate::{exc}", file=sys.stderr)
            return 1
        text = "".join(f"{key}={value}\n" for key, value in found.items())
        if environ.get("GITHUB_OUTPUT"):
            with open(environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                output.write(text)
        print(text, end="")
        return 0
    dry = getattr(args, "dry_run", False)
    found = problems(args.root, args.tag, need_date=args.command == "check" and not dry)
    if dry and not found:
        for problem in problems(args.root, args.tag):
            print(f"::warning title=Release gate::{problem} (a dry run goes on)", file=sys.stderr)
    if found:
        for problem in found:
            print(f"::error title=Release gate::{problem}", file=sys.stderr)
        return 1
    if args.command == "notes":
        print(notes(args.root, args.tag), end="")
    else:
        print(f"{args.tag}: project.godot and CHANGELOG.md agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
