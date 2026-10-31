"""A desktop export packs as groundhold-<platform>.zip (assemble.GAME): one folder with the export,
its executables still executable, and a README-first.txt for that system (macOS: the
quarantine steps of an unsigned app).

    python3 -m unittest discover -s tools/release -t tools/release
"""

import contextlib
import io
from pathlib import Path
import re
import stat
import tempfile
import unittest
import zipfile

import assemble
import package


def mode_of(info: zipfile.ZipInfo) -> int:
    return info.external_attr >> 16


class PackageTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)

    def test_linux_keeps_the_binary_executable(self):
        export = self.root / "linux"
        export.mkdir()
        binary = export / "groundhold.x86_64"
        binary.write_bytes(b"\x7fELF game")
        binary.chmod(0o755)
        target = package.package(export, "1.2.0", "linux-x64", self.root / "dist")
        self.assertEqual(target.name, "groundhold-linux-x64.zip", "no version: the newest release's link stays")
        with zipfile.ZipFile(target) as archive:
            names = sorted(archive.namelist())
            self.assertEqual(names, ["groundhold-1.2.0-linux-x64/README-first.txt",
                                     "groundhold-1.2.0-linux-x64/groundhold.x86_64"])
            game = archive.getinfo("groundhold-1.2.0-linux-x64/groundhold.x86_64")
            self.assertTrue(mode_of(game) & stat.S_IXUSR, "the binary keeps its executable bit")
            self.assertEqual(archive.read(game), b"\x7fELF game")
            text = archive.read("groundhold-1.2.0-linux-x64/README-first.txt").decode()
            self.assertIn("Groundhold 1.2.0 for Linux", text)
            self.assertIn("./groundhold.x86_64", text)
            self.assertIn("wss://groundhold.saschb2b.com/causeway", text)
            self.assertNotIn("$", text, "every placeholder filled")

    def test_windows_readme_has_windows_line_ends(self):
        export = self.root / "windows"
        export.mkdir()
        (export / "Groundhold.exe").write_bytes(b"MZ")
        target = package.package(export, "1.2.0", "windows-x64", self.root / "dist")
        with zipfile.ZipFile(target) as archive:
            text = archive.read("groundhold-1.2.0-windows-x64/README-first.txt")
        self.assertIn(b"Groundhold 1.2.0 for Windows (x86_64)\r\n", text)
        self.assertIn(b"More info, then Run anyway", text, "the SmartScreen step of an unsigned game")
        self.assertNotIn(b"\n", text.replace(b"\r\n", b""), "Notepad's line ends throughout")

    def test_macos_copies_godots_zip_with_its_modes_and_the_quarantine_steps(self):
        export = self.root / "Groundhold.zip"
        with zipfile.ZipFile(export, "w") as archive:
            folder = zipfile.ZipInfo("Groundhold.app/")
            folder.external_attr = (stat.S_IFDIR | 0o755) << 16
            archive.writestr(folder, b"")
            app = zipfile.ZipInfo("Groundhold.app/Contents/MacOS/Groundhold")
            app.create_system = 3
            app.external_attr = (stat.S_IFREG | 0o755) << 16
            archive.writestr(app, b"\xca\xfe\xba\xbe")
            archive.writestr("Groundhold.app/Contents/Info.plist", b"<plist/>")
        target = package.package(export, "1.2.0", "macos", self.root / "dist")
        self.assertEqual(target.name, "groundhold-macos.zip")
        with zipfile.ZipFile(target) as archive:
            top = "groundhold-1.2.0-macos/"
            binary = archive.getinfo(top + "Groundhold.app/Contents/MacOS/Groundhold")
            self.assertTrue(mode_of(binary) & stat.S_IXUSR, "the app's executable keeps its bit")
            self.assertEqual(archive.read(binary), b"\xca\xfe\xba\xbe")
            self.assertTrue(archive.getinfo(top + "Groundhold.app/").is_dir())
            text = archive.read(top + "README-first.txt").decode()
        self.assertIn("xattr -dr com.apple.quarantine /Applications/Groundhold.app", text)
        self.assertIn("Control-click", text)
        self.assertIn("Open Anyway", text)
        # (the Terminal step first: Open and Open Anyway do not get past "is damaged", which an
        # unsigned app on Apple silicon is likely to be called)
        self.assertLess(text.index("xattr -dr"), text.index("Control-click"))
        self.assertLess(text.index("xattr -dr"), text.index("Open Anyway"))

    def test_an_unknown_platform_or_empty_export_is_refused(self):
        with self.assertRaises(ValueError):
            package.package(self.root, "1.2.0", "amiga", self.root / "dist")
        (self.root / "empty").mkdir()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = package.main(["--version", "1.2.0", "--platform", "linux-x64",
                                 str(self.root / "empty"), "--out", str(self.root / "dist")])
        self.assertEqual(code, 1)
        self.assertIn("is empty", err.getvalue())

    def test_the_platforms_make_the_releases_game_files(self):
        self.assertEqual({platform: package.zip_name(platform) for platform in package.PLATFORMS}, assemble.GAME)

    def test_every_readme_names_the_servers_archives_for_its_system_and_the_policy(self):
        for platform, wanted in (("linux-x64", ["linux-x64", "linux-arm64", "python"]),
                                 ("windows-x64", ["windows-x64", "python"]),
                                 ("macos", ["macos-arm64", "macos-x64", "python"])):
            text = package.readme(platform, "1.2.0")
            for target in wanted:
                self.assertIn(f"groundhold-server-{target}.zip", text, platform)
            for name in set(re.findall(r"groundhold-server[\w.-]*\.(?:zip|pyz)", text)):
                self.assertIn(name, assemble.SERVER, f"{platform}: {name} is no file of a release")
            self.assertIn("https://saschb2b.github.io/Groundhold/policy.html", text, platform)


if __name__ == "__main__":
    unittest.main()
