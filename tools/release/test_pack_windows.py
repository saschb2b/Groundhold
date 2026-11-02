"""The Windows game's files (pack_windows.py): the portable zip holds one folder, Groundhold/, with the
exe as exported, README-first.txt, LICENSE.txt and licenses/ in Windows' line ends; makensis is given
the version, the folder, the icon and the installer's name; and the installer script installs for the
user alone, lists itself in Settings > Apps and uninstalls only what it installed (a fake makensis
stands in for NSIS here; a real one where it is installed).

    python3 -m unittest discover -s tools/release -t tools/release
"""

import fnmatch
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile

import assemble
import fakes
import pack_windows
import package


class PackWindowsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.export = self.root / "export"
        self.export.mkdir()
        (self.export / "Groundhold.exe").write_bytes(b"MZ the game")
        (self.export / "Groundhold.console.exe").write_bytes(b"MZ a debug export's wrapper")
        self.tools = fakes.Tools(self.root)
        # (makensis -DOUT=<file>: the installer, as NSIS writes it)
        self.tools.add("makensis", "out = next(a[6:] for a in sys.argv if a.startswith('-DOUT='))\n"
                                   "Path(out).write_bytes(b'MZ Nullsoft')")

    def make(self, only=None):
        with self.tools.path():
            return pack_windows.make(self.export, "1.2.3", self.root / "dist", self.root / "work", only)

    def test_the_zip_holds_one_folder_with_the_game_its_readme_and_licences(self):
        made = self.make(["zip"])
        self.assertEqual([p.name for p in made], [assemble.WINDOWS_ZIP])
        with zipfile.ZipFile(made[0]) as archive:
            names = archive.namelist()
            self.assertEqual(names, ["Groundhold/Groundhold.exe", "Groundhold/LICENSE.txt", "Groundhold/README-first.txt",
                                     "Groundhold/licenses/Godot-Engine.txt", "Groundhold/licenses/Noto-fonts-OFL.txt"],
                             "one folder; the export's exe alone, as exported")
            self.assertEqual(archive.read("Groundhold/Groundhold.exe"), b"MZ the game")
            for name in names:
                info = archive.getinfo(name)
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0), name)
                if name.endswith(".txt"):
                    text = archive.read(name)
                    self.assertNotIn(b"\n", text.replace(b"\r\n", b""), f"{name}: Notepad's line ends")
            self.assertIn(b"Groundhold 1.2.3 for Windows", archive.read("Groundhold/README-first.txt"))
            self.assertIn(b"MIT License", archive.read("Groundhold/LICENSE.txt"))
        self.assertEqual(self.tools.calls(), [], "the zip needs no NSIS")

    def test_makensis_gets_the_version_the_folder_the_icon_and_the_name(self):
        made = self.make(["setup"])
        self.assertEqual([p.name for p in made], [assemble.WINDOWS_SETUP])
        (call,) = self.tools.calls()
        args = call["args"]
        defines = dict(a[2:].split("=", 1) for a in args if a.startswith("-D"))
        self.assertEqual(defines["VERSION"], "1.2.3")
        self.assertEqual(defines["FILEVERSION"], "1.2.3.0")
        self.assertEqual(Path(defines["STAGE"]), (self.root / "work" / "Groundhold").resolve())
        self.assertEqual(Path(defines["ICON"]), (package.ICONS / "groundhold.ico").resolve())
        self.assertEqual(Path(defines["SIDE"]), (package.ICONS / "installer.bmp").resolve())
        self.assertEqual(Path(defines["OUT"]), (self.root / "dist" / assemble.WINDOWS_SETUP).resolve())
        self.assertGreater(int(defines["SIZE_KB"]), 0)
        self.assertEqual(args[-1], str(pack_windows.NSI))
        self.assertIn("-INPUTCHARSET", args)

    def test_a_failed_or_empty_makensis_stops_it(self):
        self.tools.add("makensis", "print('Error: invalid script'); sys.exit(1)")
        with self.assertRaises(package.PackError) as caught:
            self.make(["setup"])
        self.assertIn("invalid script", str(caught.exception))
        self.tools.add("makensis", "")
        with self.assertRaises(package.PackError) as caught:
            self.make(["setup"])
        self.assertIn("made no groundhold-windows-x64-setup.exe", str(caught.exception))

    def test_both_by_default(self):
        self.assertEqual([p.name for p in self.make()], [assemble.WINDOWS_SETUP, assemble.WINDOWS_ZIP])


class InstallerScriptTest(unittest.TestCase):
    """packaging/windows/installer.nsi, read as text."""

    def setUp(self):
        self.text = pack_windows.NSI.read_text(encoding="utf-8")
        self.code = "\n".join(line.split(";", 1)[0] if line.lstrip().startswith(";") else line
                              for line in self.text.splitlines())

    def section(self, name):
        found = re.search(r'^Section' + (r' "Uninstall"' if name == "uninstall" else r'\s*$') + r'(.*?)^SectionEnd',
                          self.code, re.M | re.S)
        return found.group(1)

    def test_for_the_user_alone(self):
        for line in ("Unicode true", 'RequestExecutionLevel user', 'InstallDir "$LOCALAPPDATA\\Programs\\${NAME}"',
                     "SetCompressor /SOLID lzma", '!include "MUI2.nsh"', '!define ID "io.github.saschb2b.Groundhold"',
                     'VIProductVersion "${FILEVERSION}"', 'VIAddVersionKey "ProductVersion" "${VERSION}"',
                     '!define MUI_ICON "${ICON}"'):
            self.assertIn(line, self.code)
        self.assertNotIn("HKLM", self.code, "no machine-wide key: no administrator")
        self.assertNotIn("$PROGRAMFILES", self.code)

    def test_its_pages(self):
        pages = re.findall(r"!insertmacro (MUI_(?:UN)?PAGE_\w+)", self.code)
        self.assertEqual(pages, ["MUI_PAGE_WELCOME", "MUI_PAGE_DIRECTORY", "MUI_PAGE_INSTFILES", "MUI_PAGE_FINISH",
                                 "MUI_UNPAGE_CONFIRM", "MUI_UNPAGE_INSTFILES"])
        self.assertIn('!define MUI_FINISHPAGE_RUN "$INSTDIR\\${EXE}"', self.code)
        self.assertIn("!define MUI_FINISHPAGE_SHOWREADME_FUNCTION DesktopShortcut", self.code)
        self.assertIn('CreateShortcut "$DESKTOP\\${NAME}.lnk"', self.code)

    def test_the_desktop_shortcut_waits_for_a_tick(self):
        # (README-first and the release's downloads say "if you tick it": NSIS ticks the Finish page's
        # second box unless told not to; the packages' review found it ticked under Wine)
        self.assertIn("!define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED", self.code)
        self.assertNotIn("MUI_FINISHPAGE_RUN_NOTCHECKED", self.code, "Start Groundhold stays ticked")

    def test_the_welcome_and_finish_pages_wear_the_brand(self):
        # (without these NSIS draws its stock blue wizard there)
        self.assertIn('!define MUI_WELCOMEFINISHPAGE_BITMAP "${SIDE}"', self.code)
        self.assertIn('!define MUI_UNWELCOMEFINISHPAGE_BITMAP "${SIDE}"', self.code)

    def test_it_lists_itself_in_settings_apps(self):
        install = self.section("install")
        self.assertIn('CreateShortcut "$SMPROGRAMS\\${NAME}.lnk" "$INSTDIR\\${EXE}"', install)
        self.assertIn('WriteUninstaller "$INSTDIR\\uninstall.exe"', install)
        keys = set(re.findall(r'WriteReg(?:Str|DWORD) HKCU "\$\{UNINST\}" "(\w+)"', install))
        self.assertTrue({"DisplayName", "DisplayVersion", "Publisher", "DisplayIcon", "InstallLocation", "UninstallString",
                         "QuietUninstallString", "URLInfoAbout", "NoModify", "NoRepair"} <= keys, keys)
        self.assertIn('"QuietUninstallString" \'"$INSTDIR\\uninstall.exe" /S\'', install)

    def test_it_installs_the_staged_folder_and_uninstalls_only_that(self):
        with tempfile.TemporaryDirectory() as folder:
            export = Path(folder) / "export"
            export.mkdir()
            (export / "Groundhold.exe").write_bytes(b"MZ")
            staged = pack_windows.stage(export, "1.2.3", Path(folder) / "work")
            files = sorted(p.relative_to(staged).as_posix() for p in staged.rglob("*") if p.is_file())
        installed = re.findall(r'File "\$\{STAGE\}\\([^"]+)"', self.section("install"))
        installed = [name.replace("${EXE}", "Groundhold.exe").replace("\\", "/") for name in installed]
        for name in files:
            self.assertTrue(any(fnmatch.fnmatchcase(name, pattern) for pattern in installed), f"{name} is not installed")
        for pattern in installed:
            self.assertTrue(any(fnmatch.fnmatchcase(name, pattern) for name in files), f"{pattern} is not staged")
        uninstall = self.section("uninstall")
        deleted = [name.replace("${EXE}", "Groundhold.exe").replace("\\", "/")
                   for name in re.findall(r'Delete "\$INSTDIR\\([^"]+)"', uninstall)]
        self.assertEqual(sorted(deleted), sorted(installed + ["uninstall.exe"]))
        self.assertNotIn("RMDir /r", uninstall, "never a folder and all in it: the player chose the folder")
        self.assertNotIn("app_userdata", uninstall, "the player's name, Builders and settings stay")
        self.assertIn('DeleteRegKey HKCU "${UNINST}"', uninstall)

    @unittest.skipIf(shutil.which("makensis") is None, "needs NSIS (the packaging image has it)")
    def test_makensis_builds_it(self):
        with tempfile.TemporaryDirectory() as folder:
            export = Path(folder) / "export"
            export.mkdir()
            (export / "Groundhold.exe").write_bytes(b"MZ" + b"\0" * 1024)
            (made,) = pack_windows.make(export, "1.2.3", Path(folder) / "dist", Path(folder) / "work", ["setup"])
            data = made.read_bytes()
            self.assertEqual(data[:2], b"MZ")
            self.assertIn(b"Nullsoft", data)
            done = subprocess.run(["file", str(made)], capture_output=True, text=True, check=False)
            if done.returncode == 0:
                self.assertIn("Nullsoft Installer", done.stdout)


if __name__ == "__main__":
    unittest.main()
