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
# the game's files once the installers land (the packaging track's names), and the server's as they are
PACKAGED = ["groundhold-windows-x64-setup.exe", "groundhold-windows-x64.zip", "groundhold-macos.dmg",
            "groundhold-x86_64.AppImage", "groundhold-x86_64.AppImage.zsync", "groundhold_amd64.deb",
            "groundhold-linux-x64.tar.gz"] + assemble.SERVER
# 0.9.0's game files, before them
ZIPS = ["groundhold-windows-x64.zip", "groundhold-macos.zip", "groundhold-linux-x64.zip"]

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
    def block(self, files=PACKAGED, dist=None) -> str:
        what = {name: assemble.WHAT.get(name, f"what {name} is") for name in files}
        return notes.downloads("v1.2.0", files=list(files), what=what, dist=dist)

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
        for name in assemble.SERVER:
            self.assertIn(f"| [`{name}`]({DOWNLOAD}/v1.2.0/{name}) | {assemble.WHAT[name]} |", server)
        self.assertIn("docker pull ghcr.io/saschb2b/groundhold-server:1.2.0", server)
        self.assertIn(f"{BLOB}/v1.2.0/server/README.md", server)
        self.assertIn("wss://groundhold.saschb2b.com/causeway", server)
        self.assertIn("https://saschb2b.github.io/Groundhold/policy.html", server)
        self.assertNotIn("setup.exe", server)

    def test_the_help_for_an_unsigned_build_is_folded(self):
        text = self.block()
        help_ = text[text.index("<details>"):text.index("</details>")]
        for words in ("**More info**", "**Run anyway**", "xattr -dr com.apple.quarantine /Applications/Groundhold.app",
                      "**Open Anyway**", "--appimage-extract-and-run"):
            self.assertIn(words, help_)
        self.assertLess(help_.index("xattr -dr"), help_.index("Open Anyway"), "Terminal first")
        self.assertNotIn("--appimage-extract-and-run", self.block(files=ZIPS + assemble.SERVER),
                         "no AppImage, no word of FUSE")

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
        self.assertIn(" · 300 KB lets AppImageUpdate", text)
        self.assertIn("```\nabc  groundhold-macos.dmg\n```", text, "the sums themselves, folded")

    def test_a_file_of_no_known_kind_is_still_listed_in_its_own_words(self):
        text = self.block(files=ZIPS + assemble.SERVER)
        mac = self.section(text, "### 🍎 macOS")
        self.assertIn(f"**[Download]({DOWNLOAD}/v1.2.0/groundhold-macos.zip)** · `groundhold-macos.zip`<br>"
                      f"{assemble.WHAT['groundhold-macos.zip']}", mac)
        with self.assertRaisesRegex(notes.NotesError, "no system for groundhold-tvos.ipa"):
            self.block(files=["groundhold-tvos.ipa"])

    def test_every_file_of_the_release_has_its_place(self):
        # (assemble.FILES is the one list of a release's files: the block takes the names from it)
        text = notes.downloads("v9.9.9")
        for name in assemble.FILES + [assemble.SUMS]:
            self.assertIn(f"]({DOWNLOAD}/v9.9.9/{name})", text)

    @unittest.skipIf(set(ZIPS) & set(assemble.FILES),
                     "assemble.FILES still lists 0.9.0's zips: the installers' track has not landed")
    def test_every_game_file_is_a_kind_the_block_knows(self):
        # (once the installers land, each game file gets its own words, not assemble.WHAT's)
        for name in assemble.FILES:
            if notes.system_of(name) != "server":
                kind = notes.kind_of(name) or next((h for h in notes.HELPERS if name.endswith(h[0])), None)
                self.assertIsNotNone(kind, f"{name}: add its kind to release_notes.KINDS")


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
