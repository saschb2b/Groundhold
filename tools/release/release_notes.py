#!/usr/bin/env python3
"""The text of a GitHub release (docs/design/core-loop.md 7.6; .claude/skills/release/SKILL.md says how a
release's page and its pictures are made): the release's own page, docs/releases/vX.Y.Z.md, where there
is one, else CHANGELOG.md's section for its version; then the Downloads block, every row of
tools/release/assemble.py's TABLE (the files the release attaches, and nothing else) under the system it
is for, in its words.

    python3 tools/release/release_notes.py v0.9.0 > NOTES.md     # the notes
    python3 tools/release/release_notes.py v0.9.0 --dist dist    # with each file's size, and the
                                                                 # checksums from dist/SHA256SUMS.txt
    python3 tools/release/release_notes.py v0.9.0 --title        # the release's title: Groundhold v0.9.0
    python3 tools/release/release_notes.py v0.9.0 --ref main     # pictures and links at another ref than
                                                                 # the tag (a page written after its tag)
    python3 tools/release/release_notes.py --check               # every page keeps the rules (below)

A page names its pictures and links by paths relative to itself ("media/v0.9.0/hero.webp",
"../../CHANGELOG.md"), so GitHub's view of the file shows them on any branch before the tag exists; the
release's text gets them at the tag: pictures (and anything a link opens that is a picture or a clip) as
raw files, other links as the blob view. A page may open with YAML frontmatter, which is not the
release's text; its `stage:` (say `beta`) goes in the title, "Groundhold v1.0.0 (beta)". Exits 1, naming
each, when there is no page and no CHANGELOG section, or when the page names a file the tree lacks.

`--check` holds every page to the rules: each picture has alt text and a width, sits in the page's own
media/vX.Y.Z/ folder and is no larger than LIMITS says, the page is listed in docs/releases/index.md
with its tagline, and every path it names exists. Python 3.11 or newer, standard library only.
"""

import argparse
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

# The game's systems, in the order the Downloads block gives them: (key, heading, what it runs on). Each
# file's system, its words and the one to pick first are assemble.TABLE's.
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
    """The release's own words: its page at `ref` (the tag by default), else its CHANGELOG section."""
    page = page_path(root, tag)
    if page.exists():
        _, text = split_frontmatter(page.read_text(encoding="utf-8"))
        return pin(text.strip(), ref or tag, root)
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


def downloads(tag: str, table=None, dist: Path | None = None) -> str:
    """The Downloads block: each system's files, the one to pick first marked where there is a choice,
    the browser game, the server's archives and image, the help for an unsigned build, the checksums.
    `table` is assemble.TABLE unless given; with `dist`, each file's size, and the checksums from its
    SHA256SUMS.txt."""
    table = list(assemble.TABLE if table is None else table)
    version = version_of(tag)
    base = f"https://github.com/{REPO}/releases/download/{tag}/"
    known = {key for key, _, _ in SYSTEMS} | {"server"}
    unknown = [f"{row.name} ({row.system!r})" for row in table if row.system not in known]
    if unknown:
        raise NotesError("no system for " + ", ".join(unknown) + ": it is windows, macos, linux or server")

    def size(name: str) -> str:
        path = dist / name if dist else None
        return f" · {size_text(path.stat().st_size)}" if path and path.is_file() else ""

    out = ["## ⬇️ Download", "",
           f"Pick your system. Or play at once in the browser: **[{PLAY.removeprefix('https://')}]({PLAY})**, "
           "nothing to install, on the official server.", ""]
    for key, heading, runs_on in SYSTEMS:
        mine = [row for row in table if row.system == key]
        if not mine:
            continue
        # (the one to pick first, then the table's order; a file that serves another last, in small type)
        choices = sorted((row for row in mine if row.choice), key=lambda row: not row.first)
        out += [f"### {heading}", "", f"<sub>{runs_on}</sub>", ""]
        for row in choices:
            mark = " · recommended" if row.first and len(choices) > 1 else ""
            out.append(f"- **[{row.choice}]({base}{row.name})**{mark} · `{row.name}`{size(row.name)}<br>"
                       f"{row.what.format(name=row.name)}")
        for row in mine:
            if not row.choice:
                out.append(f"- <sub>[`{row.name}`]({base}{row.name}){size(row.name)}: "
                           f"{row.what.format(name=row.name)}.</sub>")
        out.append("")
    servers = [row for row in table if row.system == "server"]
    out += ["## 🖥️ Host a server", "",
            f"The browser game and the desktop game play online on the official server, `{OFFICIAL}` "
            f"([its policy]({POLICY})). To play on your own network, or to host for friends, run one of these; "
            f"[server/README.md](https://github.com/{REPO}/blob/{tag}/server/README.md) says how.", "",
            "| Download | For |", "| --- | --- |"]
    out += [f"| [`{row.name}`]({base}{row.name}){size(row.name)} | {row.what.format(name=row.name)} |"
            for row in servers]
    out += ["", f"Or the image: `docker pull {IMAGE}:{version}`, with a Compose file for it in "
            f"[deploy/selfhost/](https://github.com/{REPO}/tree/{tag}/deploy/selfhost).", ""]
    out += ["<details>", "<summary><b>Your system will not start it?</b></summary>", "",
            "The builds carry no publisher's signature that Windows or Apple knows, so each system warns the "
            "first time.", "",
            "**Windows:** if SmartScreen says it protected your PC, choose **More info**, then **Run anyway**.", "",
            "**macOS:** Groundhold is signed for itself alone and not notarised by Apple, so macOS refuses to open "
            "it at first (\"Apple could not verify...\" or \"cannot be opened\"). Once, in Terminal: `xattr -dr "
            "com.apple.quarantine /Applications/Groundhold.app`, then open it (the server: `xattr -d "
            "com.apple.quarantine groundhold-server` in its folder). If an Apple silicon Mac then says it \"is "
            "damaged\", `codesign --force --deep --sign - /Applications/Groundhold.app` signs it for that Mac "
            "alone. Without Terminal: on macOS 15 and newer, after the first refusal, **System Settings › Privacy & "
            "Security**, then **Open Anyway**; on macOS 14 and older, Control-click `Groundhold.app`, choose Open, "
            "then Open again.", ""]
    if any(row.name.endswith(".AppImage") for row in table):
        out += ["**Linux:** an AppImage that will not start on a system without FUSE runs with "
                "`--appimage-extract-and-run`.", ""]
    out += ["</details>", ""]
    sums = dist / assemble.SUMS if dist else None
    out += [f"**Checksums:** [`{assemble.SUMS}`]({base}{assemble.SUMS}) lists every file's SHA-256. Beside your "
            f"download, `sha256sum -c {assemble.SUMS} --ignore-missing` checks it on Linux, `shasum -a 256 -c "
            f"{assemble.SUMS} --ignore-missing` on macOS, and `certutil -hashfile <file> SHA256` shows it on Windows."]
    if sums and sums.is_file():
        out += ["", "<details>", f"<summary>{assemble.SUMS}</summary>", "", "```",
                sums.read_text(encoding="utf-8").strip(), "```", "", "</details>"]
    return "\n".join(out) + "\n"


def notes(root: Path, tag: str, ref: str | None = None, dist: Path | None = None) -> str:
    return f"{body(root, tag, ref)}\n\n---\n\n{downloads(tag, dist=dist)}"


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
        print(title(args.root, args.tag) if args.title else notes(args.root, args.tag, args.ref, args.dist), end="\n" if args.title else "")
    except NotesError as exc:
        print(f"::error title=Release notes::{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
