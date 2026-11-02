"""A release's text: its own page where there is one, pinned at the tag (pictures as raw files, links as
the blob view), else its CHANGELOG section, else nothing and a failure; then the Downloads block, every
file of the release under the system it is for, the one to pick first marked, the server's apart, the
help for an unsigned build folded, and the checksums; the title; and every page held to the rules.

    python3 -m unittest discover -s tools/release -t tools/release
"""

import contextlib
import io
from pathlib import Path
import re
import tempfile
import unittest

import assemble
import release_notes as notes

ROOT = Path(__file__).resolve().parents[2]
RAW = "https://raw.githubusercontent.com/saschb2b/Groundhold"
BLOB = "https://github.com/saschb2b/Groundhold/blob"
DOWNLOAD = "https://github.com/saschb2b/Groundhold/releases/download"
# (every link to a file of a release in a Downloads block)
LINKED = re.compile(r"\]\(" + re.escape(DOWNLOAD) + r"/v[\d.]+/([^)\s]+)\)")

CHANGELOG = """# Changelog

## 1.2.0 · 2026-11-02

The CHANGELOG's own words.

## 1.1.0 · 2026-10-30

Older notes.
"""

PAGE = """---
title: "Groundhold 1.2.0"
---
<p align="center">
<a href="media/v1.2.0/clip.gif"><img src="media/v1.2.0/hero.webp" width="640" alt="The hero, a wide view of a match with three waves on the road"></a>
</p>

<h2 align="center">A tagline.</h2>

See [the design](../design/core-loop.md#27-stacked-waves), the [changelog](../../CHANGELOG.md), the
[media folder](media/v1.2.0/) and [the site](https://saschb2b.github.io/Groundhold/).
"""


class Tree:
    """A small tree of a release's files: a CHANGELOG, a page with its pictures, the index."""

    def __init__(self, test: unittest.TestCase, page: str | None = PAGE, pictures=("hero.webp", "clip.gif"),
                 index: str | None = "- [Groundhold 1.2.0](v1.2.0.md): A tagline.\n"):
        folder = tempfile.TemporaryDirectory()
        test.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        (self.root / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
        (self.root / "docs" / "design").mkdir(parents=True)
        (self.root / "docs" / "design" / "core-loop.md").write_text("# Design\n", encoding="utf-8")
        media = self.root / "docs" / "releases" / "media" / "v1.2.0"
        media.mkdir(parents=True)
        for name in pictures:
            (media / name).write_bytes(b"picture")
        if page is not None:
            (self.root / "docs" / "releases" / "v1.2.0.md").write_text(page, encoding="utf-8")
        if index is not None:
            (self.root / "docs" / "releases" / "index.md").write_text(index, encoding="utf-8")


def run(*args) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = notes.main([str(a) for a in args])
    return code, out.getvalue(), err.getvalue()


class BodyTest(unittest.TestCase):
    def test_the_page_pinned_at_the_tag(self):
        text = notes.body(Tree(self).root, "v1.2.0")
        self.assertFalse(text.startswith("---"), "the frontmatter is the page's, not the release's")
        self.assertTrue(text.startswith('<p align="center">'))
        self.assertIn(f'src="{RAW}/v1.2.0/docs/releases/media/v1.2.0/hero.webp"', text)
        self.assertIn(f'href="{RAW}/v1.2.0/docs/releases/media/v1.2.0/clip.gif"', text, "a link to a clip opens it")
        self.assertIn(f"]({BLOB}/v1.2.0/docs/design/core-loop.md#27-stacked-waves)", text, "a page keeps its anchor")
        self.assertIn(f"]({BLOB}/v1.2.0/CHANGELOG.md)", text)
        self.assertIn("](https://github.com/saschb2b/Groundhold/tree/v1.2.0/docs/releases/media/v1.2.0) and", text)
        self.assertIn("](https://saschb2b.github.io/Groundhold/)", text, "a site's link stays as written")
        self.assertNotIn("CHANGELOG's own words", text)

    def test_a_page_written_after_its_tag_pins_at_another_ref(self):
        text = notes.body(Tree(self).root, "v1.2.0", ref="main")
        self.assertIn(f'src="{RAW}/main/docs/releases/media/v1.2.0/hero.webp"', text)
        self.assertIn(f"]({BLOB}/main/CHANGELOG.md)", text)

    def test_without_a_page_the_changelog_section(self):
        self.assertEqual(notes.body(Tree(self, page=None).root, "v1.2.0"), "The CHANGELOG's own words.")

    def test_without_either_nothing(self):
        root = Tree(self, page=None).root
        with self.assertRaisesRegex(notes.NotesError, "no docs/releases/v1.3.0.md and no CHANGELOG.md section"):
            notes.body(root, "v1.3.0")
        code, out, err = run("v1.3.0", "--root", root)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("::error title=Release notes::", err)

    def test_a_page_naming_what_the_tree_lacks_fails_naming_it(self):
        root = Tree(self, pictures=("hero.webp",)).root
        with self.assertRaisesRegex(notes.NotesError, "docs/releases/media/v1.2.0/clip.gif"):
            notes.body(root, "v1.2.0")

    def test_the_title_and_a_stage(self):
        self.assertEqual(notes.title(Tree(self).root, "v1.2.0"), "Groundhold v1.2.0")
        staged = Tree(self, page=PAGE.replace('title: "Groundhold 1.2.0"', "stage: beta")).root
        self.assertEqual(notes.title(staged, "v1.2.0"), "Groundhold v1.2.0 (beta)")
        self.assertEqual(run("v1.2.0", "--title", "--root", staged)[1], "Groundhold v1.2.0 (beta)\n")
        with self.assertRaises(notes.NotesError):
            notes.title(staged, "1.2.0")


class DownloadsTest(unittest.TestCase):
    def block(self, table=None, dist=None) -> str:
        return notes.downloads("v1.2.0", table=table, dist=dist)

    def section(self, text: str, heading: str) -> str:
        start = text.index(heading)
        found = re.search(r"^##", text[start + len(heading):], re.M)
        return text[start:start + len(heading) + found.start()] if found else text[start:]

    def test_each_system_its_files_the_first_choice_marked(self):
        text = self.block()
        windows, mac, linux = (self.section(text, f"### {h}") for _, h, _ in notes.SYSTEMS)
        self.assertLess(windows.index("groundhold-windows-x64-setup.exe"), windows.index("groundhold-windows-x64.zip"))
        self.assertIn(f"**[Installer]({DOWNLOAD}/v1.2.0/groundhold-windows-x64-setup.exe)** · recommended", windows)
        self.assertIn(f"**[Portable]({DOWNLOAD}/v1.2.0/groundhold-windows-x64.zip)** · `", windows)
        self.assertIn(f"**[Disk image]({DOWNLOAD}/v1.2.0/groundhold-macos.dmg)** · `", mac,
                      "macOS has one choice: nothing to recommend")
        self.assertNotIn("recommended", mac)
        order = [linux.index(name) for name in ("groundhold-x86_64.AppImage`", "groundhold_amd64.deb",
                                                "groundhold-linux-x64.tar.gz", "groundhold-x86_64.AppImage.zsync")]
        self.assertEqual(order, sorted(order), "the AppImage first, then the package and the archive, the zsync last")
        self.assertIn("**[AppImage]", linux)
        self.assertIn("· recommended", linux.split("\n- ")[1], "the AppImage is the one to pick")
        self.assertIn("chmod +x groundhold-x86_64.AppImage", linux)
        self.assertIn("sudo apt install ./groundhold_amd64.deb", linux)
        self.assertIn("./install.sh --remove", linux)
        self.assertIn("<sub>[`groundhold-x86_64.AppImage.zsync`]", linux, "the zsync is a footnote, not a choice")

    def test_the_order_of_the_block(self):
        text = self.block()
        marks = ["## ⬇️ Download", "saschb2b.github.io/Groundhold/play/", "### 🪟 Windows", "### 🍎 macOS",
                 "### 🐧 Linux", "## 🖥️ Host a server", "<details>", "**Checksums:**"]
        found = [text.index(mark) for mark in marks]
        self.assertEqual(found, sorted(found), "the browser first, the systems, then the server, help and sums")

    def test_the_server_apart_with_its_image(self):
        server = self.section(self.block(), "## 🖥️ Host a server")
        for row in assemble.TABLE:
            if row.system == "server":
                self.assertIn(f"| [`{row.name}`]({DOWNLOAD}/v1.2.0/{row.name}) | {row.what} |", server)
        self.assertEqual(LINKED.findall(server[:server.index("<details>")]), assemble.SERVER,
                         "the server's archives, in the table's order")
        self.assertIn("docker pull ghcr.io/saschb2b/groundhold-server:1.2.0", server)
        self.assertIn(f"{BLOB}/v1.2.0/server/README.md", server)
        self.assertIn("wss://groundhold.saschb2b.com/causeway", server)
        self.assertIn("https://saschb2b.github.io/Groundhold/policy.html", server)
        self.assertNotIn("setup.exe", server)

    def test_the_help_for_an_unsigned_build_is_folded(self):
        text = self.block()
        help_ = text[text.index("<details>"):text.index("</details>")]
        for words in ("**More info**", "**Run anyway**", "xattr -dr com.apple.quarantine /Applications/Groundhold.app",
                      "codesign --force --deep --sign - /Applications/Groundhold.app", "**Open Anyway**",
                      "Control-click", "--appimage-extract-and-run"):
            self.assertIn(words, help_)
        self.assertLess(help_.index("xattr -dr"), help_.index("Open Anyway"), "Terminal first")
        self.assertLess(help_.index("xattr -dr"), help_.index("Control-click"), "Terminal first")
        without = [row for row in assemble.TABLE if not row.name.startswith(assemble.APPIMAGE)]
        self.assertNotIn("--appimage-extract-and-run", self.block(table=without), "no AppImage, no word of FUSE")

    def test_the_checksums_and_with_the_files_their_sizes(self):
        text = self.block()
        self.assertIn(f"[`SHA256SUMS.txt`]({DOWNLOAD}/v1.2.0/SHA256SUMS.txt)", text)
        self.assertIn("sha256sum -c SHA256SUMS.txt --ignore-missing", text)
        self.assertNotIn(" MB", text, "no sizes without the files")
        with tempfile.TemporaryDirectory() as folder:
            dist = Path(folder)
            (dist / "groundhold-windows-x64-setup.exe").write_bytes(b"\0" * (95 * 1024 * 1024 + 7))
            (dist / "groundhold-macos.dmg").write_bytes(b"\0" * (3 * 1024 * 1024 // 2))
            (dist / "groundhold-x86_64.AppImage.zsync").write_bytes(b"\0" * 300 * 1024)
            (dist / "SHA256SUMS.txt").write_text("abc  groundhold-macos.dmg\n", encoding="utf-8")
            text = self.block(dist=dist)
        self.assertIn("`groundhold-windows-x64-setup.exe` · 95 MB<br>", text)
        self.assertIn("`groundhold-macos.dmg` · 1.5 MB<br>", text)
        self.assertIn("groundhold-x86_64.AppImage.zsync`](", text)
        self.assertIn(" · 300 KB: the AppImage's update file", text)
        self.assertIn("```\nabc  groundhold-macos.dmg\n```", text, "the sums themselves, folded")

    def test_a_row_is_shown_in_its_own_words(self):
        # (the block has no words of its own for a file: a new row of assemble.TABLE shows as it says)
        table = list(assemble.TABLE) + [assemble.File("groundhold-macos-legacy.zip", "macos", "For an old Mac.",
                                                      "Legacy")]
        mac = self.section(self.block(table=table), "### 🍎 macOS")
        self.assertIn(f"**[Disk image]({DOWNLOAD}/v1.2.0/groundhold-macos.dmg)** · recommended", mac,
                      "two choices now: the first marked")
        self.assertIn(f"**[Legacy]({DOWNLOAD}/v1.2.0/groundhold-macos-legacy.zip)** · `groundhold-macos-legacy.zip`"
                      "<br>For an old Mac.", mac)
        with self.assertRaisesRegex(notes.NotesError, r"no system for groundhold-tvos.ipa \('tvos'\)"):
            self.block(table=[assemble.File("groundhold-tvos.ipa", "tvos", "For a television.", "App")])

    def test_the_block_names_exactly_the_releases_files(self):
        # (assemble.TABLE is the one table of a release's files: assemble.py checks dist against its names,
        # and the block links each of them once, the checksums too, and nothing else)
        text = notes.downloads("v9.9.9")
        self.assertEqual(sorted(LINKED.findall(text)), sorted(assemble.FILES + [assemble.SUMS]))
        for key, heading, _ in notes.SYSTEMS:
            shown = LINKED.findall(self.section(text, f"### {heading}"))
            self.assertEqual(sorted(shown), sorted(row.name for row in assemble.TABLE if row.system == key), heading)
        for row in assemble.TABLE:
            if row.system != "server":
                self.assertIn(row.what.format(name=row.name), text, f"{row.name} in its own words")


class NotesTest(unittest.TestCase):
    def test_the_page_then_the_downloads(self):
        code, out, _ = run("v1.2.0", "--root", Tree(self).root)
        self.assertEqual(code, 0)
        self.assertLess(out.index("<h2 align=\"center\">A tagline.</h2>"), out.index("---\n\n## ⬇️ Download"))
        self.assertTrue(out.endswith("\n") and not out.endswith("\n\n"))

    def test_this_trees_newest_page_builds(self):
        newest = notes.pages(ROOT)[0]
        text = notes.notes(ROOT, newest.stem)
        self.assertIn(f"{RAW}/{newest.stem}/docs/releases/media/{newest.stem}/", text)
        self.assertNotIn('src="media/', text)


class CheckTest(unittest.TestCase):
    def test_this_trees_pages_keep_the_rules(self):
        self.assertEqual(notes.check(ROOT), [])
        self.assertTrue(notes.pages(ROOT), "docs/releases/ has its pages")

    def test_a_kept_page_passes(self):
        self.assertEqual(notes.check(Tree(self).root), [])
        self.assertEqual(run("--check", "--root", Tree(self).root)[0], 0)

    def test_what_the_check_catches(self):
        cases = {
            'alt="A short one"': "has no alt text that says what it shows",
            'width="640" ': "has no width",
            'src="media/v1.2.0/hero.webp"': "is not in media/v1.2.0/",
            '<h2 align="center">A tagline.</h2>': "no tagline",
        }
        for case, problem in cases.items():
            with self.subTest(problem=problem):
                page = PAGE
                if case.startswith("alt="):
                    page = re.sub(r'alt="[^"]*"', case, page)
                elif case.startswith("width="):
                    page = page.replace(case, "")
                elif case.startswith("src="):
                    page = page.replace(case, 'src="../design/hero.webp"')
                else:
                    page = page.replace(case, "")
                tree = Tree(self, page=page)
                (tree.root / "docs" / "design" / "hero.webp").write_bytes(b"picture")
                found = notes.check(tree.root)
                self.assertTrue(any(problem in line for line in found), found)

    def test_an_unlisted_page_and_a_large_picture(self):
        self.assertTrue(any("index.md does not list v1.2.0.md" in p for p in notes.check(Tree(self, index="").root)))
        tree = Tree(self)
        (tree.root / "docs/releases/media/v1.2.0/hero.webp").write_bytes(b"\0" * (notes.LIMITS[".webp"] + 1))
        self.assertTrue(any("hero.webp is 1025 KB, over 1024 KB" in p for p in notes.check(tree.root)),
                        notes.check(tree.root))
        code, _, err = run("--check", "--root", tree.root)
        self.assertEqual(code, 1)
        self.assertIn("::error title=Release notes::", err)


if __name__ == "__main__":
    unittest.main()
