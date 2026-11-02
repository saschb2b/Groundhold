"""A release's text: its own page where there is one, pinned at the tag (pictures as raw files, links as
the blob view) with its line of downloads under the summary, else its CHANGELOG section, else nothing
and a failure; then the Downloads block, every file the release attaches (its version's table) under
the system it is for, the one to pick first in bold and the others under it, the help for an unsigned
build next to them, the server's archives and the checksums folded; a published release's assets
checked against its table; the title; and every page held to the rules.

    python3 -m unittest discover -s tools/release -t tools/release
"""

import contextlib
import io
import json
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

<p align="center"><b>New in 1.2.0:</b> the summary.</p>

<!-- downloads -->

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
    def block(self, table=None, dist=None, tag="v1.2.0", assets=None, hosts="") -> str:
        return notes.downloads(tag, table=table, dist=dist, assets=assets, hosts=hosts)

    def section(self, text: str, heading: str) -> str:
        start = text.index(heading)
        found = re.search(r"^(##|<details>)", text[start + len(heading):], re.M)
        return text[start:start + len(heading) + found.start()] if found else text[start:]

    def test_each_system_its_first_choice_in_bold_and_the_others_under_it(self):
        text = self.block()
        windows, mac, linux = (self.section(text, f"### {h}") for _, h, _ in notes.SYSTEMS)
        self.assertIn(f"**[Installer]({DOWNLOAD}/v1.2.0/groundhold-windows-x64-setup.exe)**<br>\nInstalls Groundhold",
                      windows)
        self.assertIn(f"<sub><b>Also:</b> [Portable zip]({DOWNLOAD}/v1.2.0/groundhold-windows-x64.zip) · Nothing to "
                      "install", windows)
        self.assertLess(windows.index("setup.exe"), windows.index("<b>Also:</b>"))
        self.assertIn(f"**[Disk image]({DOWNLOAD}/v1.2.0/groundhold-macos.dmg)**<br>", mac)
        self.assertNotIn("Also:", mac, "macOS has one choice")
        self.assertIn("see **Your system will not start it?** below", mac, "the help named where it is")
        self.assertIn(f"**[AppImage]({DOWNLOAD}/v1.2.0/groundhold-x86_64.AppImage)**<br>", linux)
        self.assertIn(f"from its [update file]({DOWNLOAD}/v1.2.0/groundhold-x86_64.AppImage.zsync).", linux,
                      "the zsync linked in the AppImage's words, no row of its own")
        also = linux[linux.index("<b>Also:</b>"):]
        self.assertLess(also.index("groundhold_amd64.deb"), also.index("groundhold-linux-x64.tar.gz"))
        self.assertIn("chmod +x groundhold-x86_64.AppImage", linux)
        self.assertIn("sudo apt install ./groundhold_amd64.deb", linux)
        self.assertIn("./install.sh --remove", linux)
        for part in (windows, mac, linux):
            self.assertNotIn("recommended", part)
            self.assertNotIn("`groundhold", part.split("<b>Also:</b>")[0].replace("`groundhold-x86_64", ""),
                             "no file name in monospace beside the first choice")

    def test_the_order_of_the_block(self):
        text = self.block()
        marks = ["## ⬇️ Download", "saschb2b.github.io/Groundhold/play/", "### 🪟 Windows", "### 🍎 macOS",
                 "### 🐧 Linux", "<summary><b>Your system will not start it?</b>", "<summary><b>🖥️ Host a server</b>",
                 "<summary><b>Checksums</b>"]
        found = [text.index(mark) for mark in marks]
        self.assertEqual(found, sorted(found), "the browser first, the systems and their help, then the server, sums")
        self.assertEqual(text.count("<details>"), 3)
        self.assertEqual(text.count("</details>"), 3)

    def test_the_server_folded_with_its_image_and_a_word_for_hosts(self):
        server = self.section(self.block(), "<summary><b>🖥️ Host a server</b>")
        for row in assemble.TABLE:
            if row.system == "server":
                self.assertIn(f"| [`{row.name}`]({DOWNLOAD}/v1.2.0/{row.name}) | {row.what} |", server)
        self.assertEqual(LINKED.findall(server), assemble.SERVER, "the server's archives, in the table's order")
        self.assertIn("docker pull ghcr.io/saschb2b/groundhold-server:1.2.0", server)
        self.assertIn(f"{BLOB}/v1.2.0/server/README.md", server)
        self.assertIn("wss://groundhold.saschb2b.com/causeway", server)
        self.assertIn("https://saschb2b.github.io/Groundhold/policy.html", server)
        self.assertNotIn("New for hosts", server)
        hosts = self.section(self.block(hosts="The health check names the release."), "<summary><b>🖥️ Host a server")
        self.assertIn("**New for hosts in 1.2.0:** The health check names the release.\n\n</details>", hosts)

    def test_the_help_for_an_unsigned_build_comes_after_the_systems(self):
        text = self.block()
        help_ = self.section(text, "<summary><b>Your system will not start it?</b>")
        for words in ("**More info**", "**Run anyway**", "xattr -dr com.apple.quarantine /Applications/Groundhold.app",
                      "codesign --force --deep --sign - /Applications/Groundhold.app", "**Open Anyway**",
                      "Control-click", "--appimage-extract-and-run"):
            self.assertIn(words, help_)
        # (the image's app is signed ad hoc: the steps without Terminal open it; Terminal is for "is damaged")
        self.assertLess(help_.index("Open Anyway"), help_.index("xattr -dr"), "no Terminal first")
        self.assertLess(help_.index("Control-click"), help_.index("xattr -dr"), "no Terminal first")
        self.assertLess(help_.index('"is damaged"'), help_.index("xattr -dr"))
        without = [row for row in assemble.TABLE if not row.name.startswith(assemble.APPIMAGE)]
        self.assertNotIn("--appimage-extract-and-run", self.block(table=without), "no AppImage, no word of FUSE")

    def test_the_checksums_folded_and_with_the_files_their_sizes(self):
        text = self.block()
        sums = self.section(text, "<summary><b>Checksums</b>")
        self.assertIn(f"[`SHA256SUMS.txt`]({DOWNLOAD}/v1.2.0/SHA256SUMS.txt)", sums)
        self.assertIn("sha256sum -c SHA256SUMS.txt --ignore-missing", sums)
        self.assertNotIn(" MB", text, "no sizes without the files")
        with tempfile.TemporaryDirectory() as folder:
            dist = Path(folder)
            (dist / "groundhold-windows-x64-setup.exe").write_bytes(b"\0" * (95 * 1024 * 1024 + 7))
            (dist / "groundhold-windows-x64.zip").write_bytes(b"\0" * (3 * 1024 * 1024 // 2))
            (dist / "groundhold-x86_64.AppImage.zsync").write_bytes(b"\0" * 300 * 1024)
            (dist / "SHA256SUMS.txt").write_text("abc  groundhold-macos.dmg\n", encoding="utf-8")
            text = self.block(dist=dist)
        self.assertIn("/groundhold-windows-x64-setup.exe)** · 95 MB<br>", text)
        self.assertIn("/groundhold-windows-x64.zip) · 1.5 MB · Nothing to install", text)
        self.assertIn("```\nabc  groundhold-macos.dmg\n```", self.section(text, "<summary><b>Checksums</b>"),
                      "the sums themselves, folded")

    def test_a_row_is_shown_in_its_own_words(self):
        # (the block has no words of its own for a file: a new row of the table shows as it says)
        table = list(assemble.TABLE) + [assemble.File("groundhold-macos-legacy.zip", "macos", "For an old Mac.",
                                                      "Legacy")]
        mac = self.section(self.block(table=table), "### 🍎 macOS")
        self.assertIn(f"**[Disk image]({DOWNLOAD}/v1.2.0/groundhold-macos.dmg)**<br>", mac, "the first stays first")
        self.assertIn(f"<sub><b>Also:</b> [Legacy]({DOWNLOAD}/v1.2.0/groundhold-macos-legacy.zip) · For an old Mac.",
                      mac)
        with self.assertRaisesRegex(notes.NotesError, r"no system for groundhold-tvos.ipa \('tvos'\)"):
            self.block(table=[assemble.File("groundhold-tvos.ipa", "tvos", "For a television.", "App")])
        stray = [assemble.File("a.AppImage", "linux", "No link here.", "AppImage", "Linux"),
                 assemble.File("a.AppImage.zsync", "linux", "update file", inside="a.AppImage")]
        with self.assertRaisesRegex(notes.NotesError, "no words link a.AppImage.zsync"):
            self.block(table=stray)

    def test_the_block_names_exactly_the_releases_files(self):
        # (a release's table is the one list of its files: assemble.py checks dist against its names, and
        # the block links each of them once, the checksums too, and nothing else)
        for tag in ("v9.9.9", "v0.9.0"):
            table = assemble.table_for(tag[1:])
            text = notes.downloads(tag)
            self.assertEqual(sorted(LINKED.findall(text)), sorted([row.name for row in table] + [assemble.SUMS]), tag)
            for key, heading, _ in notes.SYSTEMS:
                shown = LINKED.findall(self.section(text, f"### {heading}"))
                self.assertEqual(sorted(shown), sorted(row.name for row in table if row.system == key), heading)
            for row in table:
                if row.system != "server" and not row.inside:
                    self.assertIn(row.what.format(name=row.name, link="").split("[")[0][:40], text, row.name)

    def test_a_release_before_the_packages_downloads_its_zips(self):
        # (v0.9.0's GitHub release attaches one zip a system: a link to the installer or the AppImage would 404)
        text = notes.downloads("v0.9.0")
        self.assertEqual(LINKED.findall(text), [
            "groundhold-windows-x64.zip", "groundhold-macos.zip", "groundhold-linux-x64.zip", *assemble.SERVER,
            assemble.SUMS])
        self.assertNotIn(".AppImage", text)
        self.assertNotIn("--appimage-extract-and-run", text)
        self.assertIn(f"**[Zip]({DOWNLOAD}/v0.9.0/groundhold-macos.zip)**<br>", text)

    def test_a_published_releases_assets_give_sizes_and_sums_and_must_be_its_tables(self):
        names = [row.name for row in assemble.ZIPS] + [assemble.SUMS]
        assets = {name: (1024 * 1024 * (i + 1), f"{i:064x}") for i, name in enumerate(names)}
        text = self.block(tag="v0.9.0", assets=assets)
        self.assertIn(f"**[Zip]({DOWNLOAD}/v0.9.0/groundhold-windows-x64.zip)** · 1.0 MB<br>", text)
        sums = self.section(text, "<summary><b>Checksums</b>")
        self.assertIn(f"{0:064x}  groundhold-windows-x64.zip\n{1:064x}  groundhold-macos.zip\n", sums)
        self.assertNotIn("  SHA256SUMS.txt", sums, "the sums list the files, not themselves")
        with self.assertRaisesRegex(notes.NotesError, "missing .*groundhold-x86_64.AppImage"):
            self.block(tag="v1.2.0", assets=assets)
        extra = dict(assets, **{"groundhold-extra.zip": (1, "")})
        with self.assertRaisesRegex(notes.NotesError, "not in the table groundhold-extra.zip"):
            self.block(tag="v0.9.0", assets=extra)

    def test_assets_read_from_gh(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "assets.json"
            path.write_text(json.dumps({"assets": [
                {"name": "groundhold-macos.zip", "size": 72770442, "digest": "sha256:ab12"},
                {"name": "SHA256SUMS.txt", "size": 862}]}), encoding="utf-8")
            self.assertEqual(notes.read_assets(path), {"groundhold-macos.zip": (72770442, "ab12"),
                                                       "SHA256SUMS.txt": (862, "")})


class QuickLineTest(unittest.TestCase):
    def test_each_systems_first_and_the_browser_by_direct_link(self):
        line = notes.quick_line("v1.2.0")
        self.assertEqual(line, '<p align="center"><b>Download:</b> '
                         f'<a href="{DOWNLOAD}/v1.2.0/groundhold-windows-x64-setup.exe">Windows installer</a> · '
                         f'<a href="{DOWNLOAD}/v1.2.0/groundhold-macos.dmg">macOS</a> · '
                         f'<a href="{DOWNLOAD}/v1.2.0/groundhold-x86_64.AppImage">Linux AppImage</a> · '
                         '<a href="https://saschb2b.github.io/Groundhold/play/">Play in the browser</a></p>')
        self.assertIn(f'<a href="{DOWNLOAD}/v0.9.0/groundhold-macos.zip">macOS</a>', notes.quick_line("v0.9.0"))

    def test_the_page_carries_it_under_its_summary(self):
        text = notes.body(Tree(self).root, "v1.2.0")
        self.assertNotIn("<!-- downloads -->", text)
        self.assertIn("the summary.</p>\n\n" + notes.quick_line("v1.2.0"), text)


class NotesTest(unittest.TestCase):
    def test_the_page_then_the_downloads(self):
        code, out, _ = run("v1.2.0", "--root", Tree(self).root)
        self.assertEqual(code, 0)
        self.assertLess(out.index("<h2 align=\"center\">A tagline.</h2>"), out.index("---\n\n## ⬇️ Download"))
        self.assertTrue(out.endswith("\n") and not out.endswith("\n\n"))

    def test_the_hosts_line_comes_from_the_pages_frontmatter(self):
        tree = Tree(self, page=PAGE.replace('title: "Groundhold 1.2.0"', "hosts: The health check names its release."))
        text = notes.notes(tree.root, "v1.2.0")
        self.assertIn("**New for hosts in 1.2.0:** The health check names its release.", text)
        self.assertNotIn("hosts:", text)

    def test_assets_on_the_command_line(self):
        tree = Tree(self)
        names = [row.name for row in assemble.TABLE] + [assemble.SUMS]
        path = tree.root / "assets.json"
        path.write_text(json.dumps({"assets": [{"name": n, "size": 2048, "digest": "sha256:" + "f" * 64}
                                               for n in names]}), encoding="utf-8")
        code, out, err = run("v1.2.0", "--root", tree.root, "--assets", path)
        self.assertEqual(code, 0, err)
        self.assertIn("/groundhold-windows-x64-setup.exe)** · 2 KB<br>", out)
        path.write_text(json.dumps({"assets": [{"name": "groundhold-macos.zip", "size": 1}]}), encoding="utf-8")
        code, out, err = run("v1.2.0", "--root", tree.root, "--assets", path)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("attaches other files than its table", err)

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
            "<!-- downloads -->": "no <!-- downloads --> line",
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
