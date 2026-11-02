"""package.py's common parts and its command: each system's README-first.txt (the server's archives
for that system, the official server's policy, Windows' line ends), the version as Windows writes it,
the release's date from the CHANGELOG, a missing packaging tool named, and the command's refusals.
Each system's files are test_pack_windows.py's, test_pack_linux.py's and test_pack_macos.py's.

    python3 -m unittest discover -s tools/release -t tools/release
"""

import contextlib
import io
from pathlib import Path
import re
import tempfile
import unittest

import assemble
import package


class ReadmeTest(unittest.TestCase):
    def test_every_readme_names_the_servers_archives_for_its_system_and_the_policy(self):
        for system, wanted in (("linux", ["linux-x64", "linux-arm64", "python"]),
                               ("windows", ["windows-x64", "python"]),
                               ("macos", ["macos-arm64", "macos-x64", "python"])):
            text = package.readme(system, "1.2.0")
            self.assertIn("Groundhold 1.2.0 for ", text, system)
            self.assertNotIn("$", text, f"{system}: every placeholder filled")
            for target in wanted:
                self.assertIn(f"groundhold-server-{target}.zip", text, system)
            for name in set(re.findall(r"groundhold-server[\w.-]*\.(?:zip|pyz)", text)):
                self.assertIn(name, assemble.SERVER, f"{system}: {name} is no file of a release")
            self.assertIn("https://saschb2b.github.io/Groundhold/policy.html", text, system)
            self.assertIn("wss://groundhold.saschb2b.com/causeway", text, system)

    def test_every_heading_is_underlined_to_its_length(self):
        # (the templates' title is underlined as long as "Groundhold $version for ...": three too many)
        for system in ("linux", "windows", "macos"):
            lines = package.readme(system, "0.9.0").replace("\r\n", "\n").split("\n")
            rules = [i for i, line in enumerate(lines) if line and set(line) in ({"="}, {"-"})]
            self.assertGreaterEqual(len(rules), 3, system)
            for i in rules:
                self.assertEqual(len(lines[i]), len(lines[i - 1]), f"{system}: {lines[i - 1]!r}")
        self.assertEqual(package.underlined("Title 1.10.0\n=======\n\n--\n"), "Title 1.10.0\n============\n\n--\n",
                         "a rule under nothing stays as it is")

    def test_windows_readme_has_windows_line_ends_and_both_ways_to_start(self):
        text = package.readme("windows", "1.2.0")
        self.assertIn("Groundhold 1.2.0 for Windows (x86_64)\r\n", text)
        self.assertNotIn("\n", text.replace("\r\n", ""), "Notepad's line ends throughout")
        flat = " ".join(text.split())
        for words in (assemble.WINDOWS_SETUP, assemble.WINDOWS_ZIP, "Start menu", "More info, then Run anyway",
                      r"%APPDATA%\Godot\app_userdata\Groundhold"):
            self.assertIn(words, flat)

    def test_linux_readme_starts_the_tarballs_game_and_names_the_other_packages(self):
        flat = " ".join(package.readme("linux", "1.2.0").split())
        for words in ("cd Groundhold", "./groundhold", "./install.sh", "./install.sh --remove", assemble.APPIMAGE,
                      assemble.DEB, "sudo apt install ./groundhold_amd64.deb", "--rendering-driver opengl3"):
            self.assertIn(words, flat)
        # (without a Vulkan driver the engine switches to OpenGL itself: the packages' review saw the hub drawn)
        self.assertNotIn("needs a graphics driver with Vulkan", flat)
        self.assertIn("switches to OpenGL by itself", flat)

    def test_macos_read_me_puts_the_terminal_first(self):
        # (Open and Open Anyway do not get past "is damaged"; the quarantine step does)
        text = package.readme("macos", "1.2.0")
        flat = " ".join(text.split())
        self.assertIn("Drag Groundhold onto Applications", flat)
        self.assertIn("xattr -dr com.apple.quarantine /Applications/Groundhold.app", text)
        self.assertIn("codesign --force --deep --sign - /Applications/Groundhold.app", text)
        self.assertLess(text.index("xattr -dr"), text.index("Control-click"))
        self.assertLess(text.index("xattr -dr"), text.index("Open Anyway"))


class CommonTest(unittest.TestCase):
    def test_the_version_in_four_numbers(self):
        self.assertEqual(package.file_version("1.2.3"), "1.2.3.0")
        self.assertEqual(package.file_version("0.9.0"), "0.9.0.0")
        for wrong in ("1.2.3-beta", "v1.2.3", "", "1.2.3.4.5"):
            with self.assertRaises(package.PackError, msg=wrong):
                package.file_version(wrong)

    def test_the_release_date_is_the_changelogs_or_today(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "CHANGELOG.md").write_text("# Changelog\n\n## 1.1.0 · TBD\n\nSoon.\n\n"
                                               "## 1.0.0 · 2026-11-02\n\nFirst.\n", encoding="utf-8")
            self.assertEqual(package.release_date("1.0.0", root), "2026-11-02")
            self.assertRegex(package.release_date("1.1.0", root), r"^\d{4}-\d{2}-\d{2}$")
            self.assertRegex(package.release_date("9.9.9", root), r"^\d{4}-\d{2}-\d{2}$")

    def test_a_missing_tool_says_where_it_lives(self):
        with self.assertRaises(package.PackError) as caught:
            package.run(["groundhold-no-such-tool", "--version"])
        self.assertIn("packaging image", str(caught.exception))
        with self.assertRaises(package.PackError) as caught:
            package.run(["sh", "-c", "echo broken >&2; exit 3"])
        self.assertIn("sh failed (3)", str(caught.exception))
        self.assertIn("broken", str(caught.exception))

    def test_every_licence_a_package_carries_exists(self):
        self.assertTrue(package.LICENSE.is_file())
        for name, source in package.LICENSES.items():
            self.assertTrue(source.is_file(), name)
            self.assertTrue(name.endswith(".txt"), "Notepad opens it")


class CommandTest(unittest.TestCase):
    def run_it(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = package.main(list(argv))
        return code, err.getvalue()

    def test_an_export_without_its_game_or_a_wrong_version_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "empty").mkdir()
            out, work = str(root / "dist"), str(root / "work")
            code, err = self.run_it("windows", str(root / "empty"), "--version", "1.2.0", "--out", out, "--work", work)
            self.assertEqual(code, 1)
            self.assertIn("has no Groundhold.exe", err)
            code, err = self.run_it("linux", str(root / "empty"), "--version", "1.2.0", "--out", out, "--work", work)
            self.assertEqual(code, 1)
            self.assertIn("has no groundhold.x86_64", err)
            code, err = self.run_it("macos", str(root / "empty"), "--version", "1.2.0", "--out", out, "--work", work)
            self.assertEqual(code, 1)
            self.assertIn("is not Godot's macOS export zip", err)
            code, err = self.run_it("linux", str(root / "empty"), "--version", "v1.2", "--out", out)
            self.assertEqual(code, 1)
            self.assertIn("is not X.Y.Z", err)
            code, err = self.run_it("windows", str(root / "empty"), "--version", "1.2.0", "--only", "msi", "--out", out,
                                    "--work", work)
            self.assertEqual(code, 1)
            self.assertIn("no Windows part msi", err)
            self.assertFalse((root / "dist").exists(), "nothing made")


if __name__ == "__main__":
    unittest.main()
