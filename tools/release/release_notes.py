#!/usr/bin/env python3
"""The text of a GitHub release (docs/design/core-loop.md 7.6; .claude/skills/release/SKILL.md says how a
release's page and its pictures are made): the release's own page, docs/releases/vX.Y.Z.md, where there
is one, else CHANGELOG.md's section for its version; then the Downloads block, every file the release
attaches (tools/release/assemble.py's table_for its version: TABLE, or ZIPS for 0.6.0 to 0.9.0) under
the system it is for, in its words.

    python3 tools/release/release_notes.py v0.9.0 > NOTES.md     # the notes
    python3 tools/release/release_notes.py v0.9.0 --dist dist    # with each file's size, and the
                                                                 # checksums from dist/SHA256SUMS.txt
    gh release view v0.9.0 --json assets > assets.json           # (a release already published:)
    python3 tools/release/release_notes.py v0.9.0 --assets assets.json
                                                                 # its sizes and digests, and a failure
                                                                 # unless it attaches exactly the table's
    python3 tools/release/release_notes.py v0.9.0 --title        # the release's title: Groundhold v0.9.0
    python3 tools/release/release_notes.py v0.9.0 --ref main     # pictures and links at another ref than
                                                                 # the tag (a page written after its tag)
    python3 tools/release/release_notes.py --check               # every page keeps the rules (below)

A page names its pictures and links by paths relative to itself ("media/v0.9.0/hero.webp",
"../../CHANGELOG.md"), so GitHub's view of the file shows them on any branch before the tag exists; the
release's text gets them at the tag: pictures (and anything a link opens that is a picture or a clip) as
raw files, other links as the blob view. Its `<!-- downloads -->`, under the summary, becomes one
centred line of direct links, each system's file to pick first and the browser game (GitHub gives a
release's headings no anchors). A page may open with YAML frontmatter, which is not the release's text:
its `stage:` (say `beta`) goes in the title, "Groundhold v1.0.0 (beta)", and its `hosts:` is a line for
those who host a server, inside the Downloads block's server fold. Exits 1, naming each, when there is
no page and no CHANGELOG section, or when the page names a file the tree lacks.

`--check` holds every page to the rules: each picture has alt text and a width, sits in the page's own
media/vX.Y.Z/ folder and is no larger than LIMITS says, the page has its `<!-- downloads -->` line and
is listed in docs/releases/index.md with its tagline, and every path it names exists. Python 3.11 or
newer, standard library only.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import assemble  # noqa: E402
import gate  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PAGES = Path("docs") / "releases"
REPO = os.environ.get("GITHUB_REPOSITORY", "saschb2b/Groundhold")
TAG = gate.TAG
PLAY = "https://saschb2b.github.io/Groundhold/play/"
POLICY = "https://saschb2b.github.io/Groundhold/policy.html"
OFFICIAL = "wss://groundhold.saschb2b.com/causeway"
IMAGE = "ghcr.io/saschb2b/groundhold-server"
# what a link may open that is shown as a picture or played, never a page: its raw file
MEDIA = (".png", ".webp", ".gif", ".jpg", ".jpeg", ".svg", ".mp4", ".webm")
# the largest file of each kind a page may show (GitHub draws the release from these raw files)
LIMITS = {".gif": 4 * 1024 * 1024, ".webp": 1024 * 1024, ".png": 1536 * 1024, ".jpg": 1024 * 1024}

# where a page's summary gives way to the line of downloads
QUICK = "<!-- downloads -->"
# The game's systems, in the order the Downloads block gives them: (key, heading, what it runs on). Each
# file's system, its words and the one to pick first are its release's table's (assemble.table_for).
SYSTEMS = (
    ("windows", "🪟 Windows", "64-bit Windows 10 or 11"),
    ("macos", "🍎 macOS", "one app for Apple silicon and Intel"),
    ("linux", "🐧 Linux", "64-bit x86, any distribution"),
)


class NotesError(Exception):
    """Notes that cannot be written, with why."""


def version_of(tag: str) -> str:
    matched = TAG.fullmatch(tag)
    if not matched:
        raise NotesError(f"the tag {tag!r} is not vX.Y.Z")
    return matched.group(1)


def page_path(root: Path, tag: str) -> Path:
    return root / PAGES / f"{tag}.md"


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """({key: value} of a leading YAML block of `key: value` lines, the text after it)."""
    found = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if not found:
        return {}, text
    keys = {}
    for line in found.group(1).splitlines():
        key, colon, value = line.partition(":")
        if colon and key.strip() and not key.startswith((" ", "\t", "#")):
            keys[key.strip()] = value.strip().strip("\"'")
    return keys, text[found.end():]


# a page's references: <img src="...">, <a href="...">, ![alt](...) and [text](...)
REFERENCE = re.compile(r'(?P<attr>\b(?:src|href)=")(?P<html>[^"]+)"|(?P<bang>!?)\[(?P<text>[^\]]*)\]\((?P<md>[^)\s]+)\)')


def local(target: str) -> bool:
    """Whether a reference names a file of the repository (not a site, an anchor or a mail)."""
    return not re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:|#|//", target)


def resolve(target: str) -> str:
    """A page's relative path as a path from the repository's root (its #anchor kept apart)."""
    path, _, _ = target.partition("#")
    parts = []
    for part in (PAGES / path).as_posix().split("/"):
        if part == "..":
            if not parts:
                raise NotesError(f"{target} leads out of the repository")
            parts.pop()
        elif part not in ("", "."):
            parts.append(part)
    return "/".join(parts)


def references(text: str) -> list[tuple[str, bool]]:
    """(each local path the page names, from the repository's root; whether it is shown as a picture)."""
    found = []
    for match in REFERENCE.finditer(text):
        target = match.group("html") or match.group("md")
        shown = match.group("attr") == 'src="' or match.group("bang") == "!"
        if target and local(target):
            found.append((resolve(target), shown))
    return found


def pin(text: str, ref: str, root: Path = ROOT) -> str:
    """The page's relative paths at `ref`: pictures, and what a link opens that is a picture or a clip,
    as raw files; other links as the blob view (a folder's as the tree view). NotesError naming every
    path the tree at `root` lacks."""
    missing = sorted({path for path, _ in references(text) if not (root / path).exists()})
    if missing:
        raise NotesError("the page names what the tree lacks: " + ", ".join(missing))

    def url(target: str, shown: bool) -> str:
        path = resolve(target)
        anchor = target[len(target.partition("#")[0]):]
        if shown or path.lower().endswith(MEDIA):
            return f"https://raw.githubusercontent.com/{REPO}/{ref}/{path}"
        view = "tree" if (root / path).is_dir() else "blob"
        return f"https://github.com/{REPO}/{view}/{ref}/{path}{anchor}"

    def swap(match: re.Match) -> str:
        if match.group("attr"):
            target = match.group("html")
            if not local(target):
                return match.group(0)
            shown = match.group("attr") == 'src="'
            return f'{match.group("attr")}{url(target, shown)}"'
        target = match.group("md")
        if not local(target):
            return match.group(0)
        return f'{match.group("bang")}[{match.group("text")}]({url(target, match.group("bang") == "!")})'

    return REFERENCE.sub(swap, text)


def body(root: Path, tag: str, ref: str | None = None) -> str:
    """The release's own words: its page at `ref` (the tag by default), its line of downloads in place,
    else its CHANGELOG section."""
    page = page_path(root, tag)
    if page.exists():
        _, text = split_frontmatter(page.read_text(encoding="utf-8"))
        return pin(text.strip(), ref or tag, root).replace(QUICK, quick_line(tag))
    section = gate.changelog_section(root, version_of(tag))
    if not section:
        raise NotesError(f"no {page.relative_to(root)} and no CHANGELOG.md section '## {version_of(tag)}'")
    return section


def title(root: Path, tag: str) -> str:
    """The release's title: "Groundhold vX.Y.Z", and its page's stage after it where it names one."""
    version_of(tag)
    page = page_path(root, tag)
    stage = split_frontmatter(page.read_text(encoding="utf-8"))[0].get("stage", "") if page.exists() else ""
    return f"Groundhold {tag}" + (f" ({stage})" if stage else "")


def size_text(size: int) -> str:
    if size >= 10 * 1024 * 1024:
        return f"{round(size / (1024 * 1024))} MB"
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{max(1, round(size / 1024))} KB"


def quick_line(tag: str, table=None) -> str:
    """The page's centred line of downloads: each system's file to pick first, by direct link, and the
    browser game."""
    table = assemble.table_for(version_of(tag)) if table is None else table
    base = f"https://github.com/{REPO}/releases/download/{tag}/"
    links = [f'<a href="{base}{row.name}">{row.first}</a>' for key, _, _ in SYSTEMS
             for row in table if row.system == key and row.first]
    links.append(f'<a href="{PLAY}">Play in the browser</a>')
    return '<p align="center"><b>Download:</b> ' + " · ".join(links) + "</p>"


def read_assets(path: Path) -> dict[str, tuple[int, str]]:
    """{name: (size, SHA-256 hex or "")} from `gh release view <tag> --json assets`'s output (or its list)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("assets", []) if isinstance(data, dict) else data
    found = {}
    for row in rows:
        digest = str(row.get("digest") or "")
        found[row["name"]] = (int(row.get("size", 0)), digest.removeprefix("sha256:") if digest.startswith("sha256:") else "")
    return found


def downloads(tag: str, table=None, dist: Path | None = None, assets: dict | None = None, hosts: str = "") -> str:
    """The Downloads block: each system's file to pick first in bold, the others under it, the help for
    an unsigned build, then the server's archives and image and the checksums, each folded. `table` is
    assemble.table_for the tag's version unless given; with `dist`, each file's size and the checksums
    from its SHA256SUMS.txt; with `assets` (read_assets: a release already published), its sizes and
    digests, and NotesError unless it attaches exactly the table's files and the checksums. `hosts` is
    a line for those who host a server."""
    version = version_of(tag)
    table = list(assemble.table_for(version) if table is None else table)
    base = f"https://github.com/{REPO}/releases/download/{tag}/"
    known = {key for key, _, _ in SYSTEMS} | {"server"}
    unknown = [f"{row.name} ({row.system!r})" for row in table if row.system not in known]
    if unknown:
        raise NotesError("no system for " + ", ".join(unknown) + ": it is windows, macos, linux or server")
    names = {row.name for row in table}
    lost = [row.name for row in table if row.inside and (row.inside not in names or
            "{link}" not in next(r.what for r in table if r.name == row.inside))]
    if lost:
        raise NotesError("no words link " + ", ".join(lost) + ": its `inside` file's words need a {link}")
    if assets is not None:
        wanted, attached = names | {assemble.SUMS}, set(assets)
        if wanted != attached:
            raise NotesError(f"{tag}'s release attaches other files than its table: "
                             + "; ".join(part for part in (
                                 "missing " + ", ".join(sorted(wanted - attached)) if wanted - attached else "",
                                 "not in the table " + ", ".join(sorted(attached - wanted)) if attached - wanted
                                 else "") if part))

    def size(name: str) -> str:
        if assets is not None and name in assets:
            return f" · {size_text(assets[name][0])}"
        path = dist / name if dist else None
        return f" · {size_text(path.stat().st_size)}" if path and path.is_file() else ""

    def words(row) -> str:
        helper = next((r for r in table if r.inside == row.name), None)
        link = f"[{helper.what}]({base}{helper.name})" if helper else ""
        return row.what.format(name=row.name, link=link)

    out = ["## ⬇️ Download", "",
           f"Pick your system. Or play at once in the browser: **[{PLAY.removeprefix('https://')}]({PLAY})**, "
           "nothing to install, on the official server.", ""]
    for key, heading, runs_on in SYSTEMS:
        mine = [row for row in table if row.system == key and row.choice]
        if not mine:
            continue
        first = next((row for row in mine if row.first), mine[0])
        out += [f"### {heading}", "", f"<sub>{runs_on}</sub>", "",
                f"**[{first.choice}]({base}{first.name})**{size(first.name)}<br>", words(first), ""]
        others = [f"[{row.choice}]({base}{row.name}){size(row.name)} · {words(row)}" for row in mine if row is not first]
        if others:
            out += ["<sub><b>Also:</b> " + "<br>\n".join(others) + "</sub>", ""]
    out += ["<details>", f"<summary><b>{assemble.HELP}</b></summary>", "",
            "The builds carry no publisher's signature that Windows or Apple knows, so each system warns the "
            "first time.", "",
            "**Windows:** if SmartScreen says it protected your PC, choose **More info**, then **Run anyway**.", "",
            "**macOS:** Groundhold is not notarised by Apple, so macOS refuses to open it the first time (\"Apple "
            "could not verify...\" or \"cannot be opened\"). On macOS 15 and newer, after that refusal, open "
            "**System Settings › Privacy & Security** and choose **Open Anyway**; on macOS 14 and older, "
            "Control-click `Groundhold.app`, choose **Open**, then **Open** again. If it still will not open, or "
            "macOS says it \"is damaged\", run once in Terminal `xattr -dr com.apple.quarantine "
            "/Applications/Groundhold.app` and open it; should an Apple silicon Mac still say \"is damaged\", "
            "`codesign --force --deep --sign - /Applications/Groundhold.app` signs it for that Mac alone. The "
            "server's archive needs the same, in its folder: `xattr -d com.apple.quarantine groundhold-server`.", ""]
    if any(row.name.endswith(".AppImage") for row in table):
        out += ["**Linux:** an AppImage that will not start on a system without FUSE runs with "
                "`--appimage-extract-and-run`.", ""]
    out += ["</details>", ""]
    servers = [row for row in table if row.system == "server"]
    out += ["<details>", "<summary><b>🖥️ Host a server</b></summary>", "",
            f"The browser game and the desktop game play online on the official server, `{OFFICIAL}` "
            f"([its policy]({POLICY})). To play on your own network, or to host for friends, run one of these; "
            f"[server/README.md](https://github.com/{REPO}/blob/{tag}/server/README.md) says how.", "",
            "| Download | For |", "| --- | --- |"]
    out += [f"| [`{row.name}`]({base}{row.name}){size(row.name)} | {row.what.format(name=row.name)} |"
            for row in servers]
    out += ["", f"Or the image: `docker pull {IMAGE}:{version}`, with a Compose file for it in "
            f"[deploy/selfhost/](https://github.com/{REPO}/tree/{tag}/deploy/selfhost).", ""]
    if hosts:
        out += [f"**New for hosts in {version}:** {hosts}", ""]
    out += ["</details>", ""]
    if assets is not None:
        sums = "".join(f"{assets[row.name][1]}  {row.name}\n" for row in table if assets[row.name][1])
    else:
        path = dist / assemble.SUMS if dist else None
        sums = path.read_text(encoding="utf-8") if path and path.is_file() else ""
    out += ["<details>", "<summary><b>Checksums</b></summary>", "",
            f"[`{assemble.SUMS}`]({base}{assemble.SUMS}) lists every file's SHA-256. Beside your download, "
            f"`sha256sum -c {assemble.SUMS} --ignore-missing` checks it on Linux, `shasum -a 256 -c {assemble.SUMS} "
            "--ignore-missing` on macOS, and `certutil -hashfile <file> SHA256` shows it on Windows."]
    if sums.strip():
        out += ["", "```", sums.strip(), "```"]
    out += ["", "</details>"]
    return "\n".join(out) + "\n"


def notes(root: Path, tag: str, ref: str | None = None, dist: Path | None = None, assets: dict | None = None) -> str:
    page = page_path(root, tag)
    hosts = split_frontmatter(page.read_text(encoding="utf-8"))[0].get("hosts", "") if page.exists() else ""
    return f"{body(root, tag, ref)}\n\n---\n\n{downloads(tag, dist=dist, assets=assets, hosts=hosts)}"


def pages(root: Path) -> list[Path]:
    """Every release's page, newest first."""
    found = [path for path in (root / PAGES).glob("v*.md") if TAG.fullmatch(path.stem)]
    return sorted(found, key=lambda path: tuple(int(n) for n in path.stem[1:].split(".")), reverse=True)


def tagline(text: str) -> str:
    found = re.search(r'<h2 align="center">(.*?)</h2>', text, re.S)
    return re.sub(r"\s+", " ", found.group(1)).strip() if found else ""


def page_problems(root: Path, path: Path) -> list[str]:
    """Where one release page breaks the rules (the module's docstring)."""
    tag, out = path.stem, []
    _, text = split_frontmatter(path.read_text(encoding="utf-8"))
    name = path.relative_to(root).as_posix()
    if not tagline(text):
        out.append(f'{name}: no tagline (<h2 align="center">...</h2>)')
    if text.count(QUICK) != 1:
        out.append(f"{name}: no {QUICK} line under the summary, where the release's text puts its downloads")
    try:
        pin(text, tag, root)
    except NotesError as exc:
        out.append(f"{name}: {exc}")
    for match in re.finditer(r"<img\b[^>]*>", text):
        img = match.group(0)
        src = re.search(r'\bsrc="([^"]+)"', img)
        if not src:
            out.append(f"{name}: an <img> without src")
            continue
        alt = re.search(r'\balt="([^"]*)"', img)
        if not alt or len(alt.group(1).split()) < 6:
            out.append(f"{name}: {src.group(1)} has no alt text that says what it shows (six words or more)")
        if not re.search(r'\bwidth="\d+"', img):
            out.append(f"{name}: {src.group(1)} has no width")
        if local(src.group(1)):
            where = resolve(src.group(1))
            if not where.startswith(f"{PAGES.as_posix()}/media/{tag}/"):
                out.append(f"{name}: {src.group(1)} is not in media/{tag}/, the page's own pictures")
            file = root / where
            limit = LIMITS.get(file.suffix.lower())
            if file.is_file() and limit and file.stat().st_size > limit:
                out.append(f"{name}: {src.group(1)} is {-(-file.stat().st_size // 1024)} KB, over {limit // 1024} KB")
    if re.search(r"!\[[^\]]*\]\(", text):
        out.append(f"{name}: a Markdown picture; use <img> with a width and alt text")
    index = root / PAGES / "index.md"
    listed = index.read_text(encoding="utf-8") if index.exists() else ""
    if f"]({path.name})" not in listed or (tagline(text) and tagline(text) not in listed):
        out.append(f"docs/releases/index.md does not list {path.name} with its tagline")
    return out


def check(root: Path) -> list[str]:
    out = []
    for path in pages(root):
        out += page_problems(root, path)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("tag", nargs="?", help="the release, vX.Y.Z")
    parser.add_argument("--root", type=Path, default=ROOT, help="the tree to read (default: this checkout)")
    parser.add_argument("--ref", help="pin pictures and links at this ref, not the tag")
    parser.add_argument("--dist", type=Path, help="the release's files: their sizes and SHA256SUMS.txt")
    parser.add_argument("--assets", type=Path, help="a published release's assets (gh release view TAG --json "
                        "assets): their sizes and digests, checked against the table")
    parser.add_argument("--title", action="store_true", help="print the release's title instead")
    parser.add_argument("--check", action="store_true", help="hold every page to the rules")
    args = parser.parse_args(argv)
    try:
        if args.check:
            found = check(args.root)
            for problem in found:
                print(f"::error title=Release notes::{problem}", file=sys.stderr)
            if not found:
                print(f"{len(pages(args.root))} release pages keep the rules")
            return 1 if found else 0
        if not args.tag:
            parser.error("give the release's tag, vX.Y.Z, or --check")
        assets = read_assets(args.assets) if args.assets else None
        print(title(args.root, args.tag) if args.title else notes(args.root, args.tag, args.ref, args.dist, assets),
              end="\n" if args.title else "")
    except NotesError as exc:
        print(f"::error title=Release notes::{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
