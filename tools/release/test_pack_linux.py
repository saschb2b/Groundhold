"""The Linux game's files (pack_linux.py) from one install tree: the program, the menu entry, the hicolor
icons and the AppStream data with the release's line; the AppDir appimagetool is given (AppRun, .DirIcon,
the update information pointing at this repository's newest release); the .deb's tree, control and
DEP-5 copyright (built for real where dpkg-deb is installed); the tar.gz, reproducible, with install.sh,
which writes the user's menu entry and takes it away again. The menu entry, the AppStream data and the
packaging image are read as the systems will read them.

    python3 -m unittest discover -s tools/release -t tools/release
"""

import configparser
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import unittest.mock
import xml.etree.ElementTree as ET

import app_icon
import assemble
import fakes
import pack_linux
import package

ROOT = Path(__file__).resolve().parents[2]
DATE = "2026-11-02"


def desktop_entry(text: str) -> dict:
    cfg = configparser.ConfigParser(interpolation=None, delimiters=("=",))
    cfg.optionxform = str
    cfg.read_string(text)
    return dict(cfg["Desktop Entry"])


class PackLinuxTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.export = self.root / "export"
        self.export.mkdir()
        binary = self.export / "groundhold.x86_64"
        binary.write_bytes(b"\x7fELF the game")
        binary.chmod(0o755)
        self.tools = fakes.Tools(self.root)
        # (appimagetool ... APPDIR NAME, run in the output folder: the AppImage and, with -u, its .zsync)
        self.tools.add("appimagetool", "name = sys.argv[-1]\nPath(name).write_bytes(b'\\x7fELF AppImage')\n"
                                       "Path(name + '.zsync').write_bytes(b'zsync: 0.6.2')")

    def test_the_install_tree(self):
        program = pack_linux.install_tree(self.export / "groundhold.x86_64", self.root / "tree", "1.2.3", DATE)
        usr = self.root / "tree" / "usr"
        self.assertEqual(program, usr / "lib" / "groundhold" / "groundhold")
        self.assertEqual(program.read_bytes(), b"\x7fELF the game")
        self.assertEqual(program.stat().st_mode & 0o777, 0o755)
        share = usr / "share"
        self.assertEqual((share / "applications" / f"{package.APP_ID}.desktop").read_bytes(), pack_linux.DESKTOP.read_bytes())
        for n in app_icon.PNG_SIZES:
            icon = share / "icons" / "hicolor" / f"{n}x{n}" / "apps" / f"{package.APP_ID}.png"
            self.assertEqual(icon.read_bytes(), (package.ICONS / f"{n}.png").read_bytes(), n)
        meta = (share / "metainfo" / f"{package.APP_ID}.metainfo.xml").read_text(encoding="utf-8")
        release = ET.fromstring(meta).find("releases/release")
        self.assertEqual((release.get("version"), release.get("date")), ("1.2.3", DATE))
        self.assertEqual(release.find("url").text, "https://github.com/saschb2b/Groundhold/releases/tag/v1.2.3")
        doc = share / "doc" / "groundhold"
        self.assertEqual(sorted(p.relative_to(doc).as_posix() for p in doc.rglob("*") if p.is_file()),
                         ["LICENSE", "licenses/Godot-Engine.txt", "licenses/Noto-fonts-OFL.txt"])
        for folder in [p for p in (self.root / "tree").rglob("*") if p.is_dir()]:
            self.assertEqual(folder.stat().st_mode & 0o777, 0o755, folder)

    def test_the_appimage_is_made_from_an_appdir_with_its_update_information(self):
        with self.tools.path():
            made = pack_linux.make(self.export, "1.2.3", self.root / "dist", self.root / "work", ["appimage"], DATE)
        self.assertEqual([p.name for p in made], [assemble.APPIMAGE, assemble.ZSYNC])
        self.assertTrue(os.access(made[0], os.X_OK))
        (call,) = [c for c in self.tools.calls() if c["tool"] == "appimagetool"]
        appdir = self.root / "work" / "AppDir"
        self.assertEqual(call["args"], ["--runtime-file", pack_linux.RUNTIME, "--updateinformation",
                                        "gh-releases-zsync|saschb2b|Groundhold|latest|groundhold-x86_64.AppImage.zsync",
                                        str(appdir.resolve()), assemble.APPIMAGE])
        self.assertEqual(Path(call["cwd"]), (self.root / "dist").resolve(), "the .zsync beside the AppImage")
        run = appdir / "AppRun"
        self.assertTrue(os.access(run, os.X_OK))
        self.assertIn('exec "$here/usr/lib/groundhold/groundhold" "$@"', run.read_text())
        self.assertEqual(os.readlink(appdir / ".DirIcon"), f"{package.APP_ID}.png")
        self.assertEqual((appdir / f"{package.APP_ID}.png").read_bytes(), (package.ICONS / "256.png").read_bytes())
        self.assertEqual((appdir / f"{package.APP_ID}.desktop").read_bytes(), pack_linux.DESKTOP.read_bytes())

    def test_an_appimagetool_that_makes_no_zsync_stops_it(self):
        self.tools.add("appimagetool", "Path(sys.argv[-1]).write_bytes(b'AppImage')")
        with self.tools.path(), self.assertRaises(package.PackError) as caught:
            pack_linux.make(self.export, "1.2.3", self.root / "dist", self.root / "work", ["appimage"], DATE)
        self.assertIn("made no groundhold-x86_64.AppImage.zsync", str(caught.exception))

    def test_the_debs_tree(self):
        root = pack_linux.deb_root(self.export / "groundhold.x86_64", self.root / "deb", "1.2.3", DATE)
        self.assertEqual(os.readlink(root / "usr" / "bin" / "groundhold"), "../lib/groundhold/groundhold")
        control = (root / "DEBIAN" / "control").read_text(encoding="utf-8")
        fields = dict(re.findall(r"^([A-Za-z-]+): (.*)$", control, re.M))
        self.assertEqual(fields["Package"], "groundhold")
        self.assertEqual(fields["Version"], "1.2.3")
        self.assertEqual(fields["Architecture"], "amd64")
        self.assertEqual(fields["Section"], "games")
        self.assertEqual(fields["Homepage"], "https://saschb2b.github.io/Groundhold/")
        self.assertRegex(fields["Maintainer"], r"^Sascha Becker <[^>]+@[^>]+>$")
        self.assertRegex(fields["Depends"], r"^libc6 \(>= 2\.\d+\)$")
        self.assertGreater(int(fields["Installed-Size"]), 0)
        self.assertTrue(control.endswith("\n") and "\n " in control, "a long description under the short one")
        copyright_text = (root / "usr" / "share" / "doc" / "groundhold" / "copyright").read_text(encoding="utf-8")
        self.assertTrue(copyright_text.startswith("Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/\n"))
        for paragraph in ("Files: *\n", "\n\nLicense: Expat\n MIT License\n .\n Copyright (c) 2026 Sascha Becker\n",
                          " Permission is hereby granted", "\n\nLicense: OFL-1.1\n Noto Serif"):
            self.assertIn(paragraph, copyright_text)
        self.assertNotIn("\n\n\n", copyright_text)
        self.assertFalse(re.search(r"\n[^ \n][^:\n]*\n", copyright_text.split("\n\nLicense: Expat\n")[0]),
                         "every continuation line is indented")

    @unittest.skipIf(shutil.which("dpkg-deb") is None, "needs dpkg-deb")
    def test_dpkg_deb_builds_it_owned_by_root(self):
        made = pack_linux.make(self.export, "1.2.3", self.root / "dist", self.root / "work", ["deb"], DATE)
        self.assertEqual([p.name for p in made], [assemble.DEB])
        info = subprocess.run(["dpkg-deb", "-f", str(made[0]), "Package", "Version", "Architecture"],
                              capture_output=True, text=True, check=True).stdout
        self.assertEqual(info.splitlines(), ["Package: groundhold", "Version: 1.2.3", "Architecture: amd64"])
        listing = subprocess.run(["dpkg-deb", "-c", str(made[0])], capture_output=True, text=True, check=True,
                                 env=dict(os.environ, TZ="UTC")).stdout
        self.assertRegex(listing, r"lrwxrwxrwx root/root .* \./usr/bin/groundhold -> \.\./lib/groundhold/groundhold")
        self.assertRegex(listing, r"-rwxr-xr-x root/root .* \./usr/lib/groundhold/groundhold\n")
        self.assertIn(f"./usr/share/applications/{package.APP_ID}.desktop", listing)
        self.assertNotIn("DEBIAN", listing)
        self.assertNotIn(f"{os.getuid()}/", listing.replace("root/root", ""), "no builder's user in it")
        self.assertIn(" 2026-11-02 00:00 ", listing, "the files' times are the release's (SOURCE_DATE_EPOCH)")

    def test_the_tarball_is_one_folder_reproducibly(self):
        first = pack_linux.tarball(self.export / "groundhold.x86_64", "1.2.3", self.root / "a", DATE)
        second = pack_linux.tarball(self.export / "groundhold.x86_64", "1.2.3", self.root / "b", DATE)
        self.assertEqual(first.name, assemble.LINUX_TAR)
        self.assertEqual(first.read_bytes(), second.read_bytes(), "the same bytes from the same export")
        with tarfile.open(first) as tar:
            members = {m.name: m for m in tar.getmembers()}
            self.assertTrue(all(name == "Groundhold" or name.startswith("Groundhold/") for name in members))
            self.assertEqual(members["Groundhold/groundhold"].mode, 0o755)
            self.assertEqual(members["Groundhold/install.sh"].mode, 0o755)
            self.assertEqual(members["Groundhold/README-first.txt"].mode, 0o644)
            self.assertTrue(all(m.uid == 0 and m.gid == 0 and m.uname == "root" for m in members.values()))
            self.assertEqual({m.mtime for m in members.values()}, {pack_linux.epoch(DATE)})
            self.assertEqual(sorted(n for n in members if n.startswith("Groundhold/icons/")),
                             sorted(f"Groundhold/icons/{n}.png" for n in app_icon.PNG_SIZES))
            self.assertTrue({"Groundhold/LICENSE", "Groundhold/licenses/Godot-Engine.txt",
                             "Groundhold/licenses/Noto-fonts-OFL.txt"} <= set(members))
            self.assertEqual(tar.extractfile("Groundhold/groundhold").read(), b"\x7fELF the game")
            self.assertIn(b"Groundhold 1.2.3 for Linux", tar.extractfile("Groundhold/README-first.txt").read())

    def test_install_sh_adds_the_menu_entry_and_takes_it_away(self):
        target = pack_linux.tarball(self.export / "groundhold.x86_64", "1.2.3", self.root / "dist", DATE)
        with tarfile.open(target) as tar:
            tar.extractall(self.root / "games", filter="data")
        here = self.root / "games" / "Groundhold"
        data = self.root / "data home"
        env = dict(os.environ, XDG_DATA_HOME=str(data), PATH="/usr/bin:/bin")
        done = subprocess.run(["sh", str(here / "install.sh")], env=env, capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        entry_path = data / "applications" / f"{package.APP_ID}.desktop"
        entry = desktop_entry(entry_path.read_text(encoding="utf-8"))
        packaged = desktop_entry(pack_linux.DESKTOP.read_text(encoding="utf-8"))
        self.assertEqual(entry.pop("Exec"), f'"{here}/groundhold"')
        self.assertEqual(entry.pop("Path"), str(here))
        packaged.pop("Exec")
        self.assertEqual(entry, packaged, "the user's entry says what the packages' says")
        for n in app_icon.PNG_SIZES:
            icon = data / "icons" / "hicolor" / f"{n}x{n}" / "apps" / f"{package.APP_ID}.png"
            self.assertEqual(icon.read_bytes(), (package.ICONS / f"{n}.png").read_bytes(), n)
        done = subprocess.run(["sh", str(here / "install.sh"), "--remove"], env=env, capture_output=True, text=True,
                              check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        left = [p for p in data.rglob("*") if p.is_file() and p.name != "mimeinfo.cache"]
        self.assertEqual(left, [])
        done = subprocess.run(["sh", str(here / "install.sh"), "--uninstall"], env=env, capture_output=True, text=True,
                              check=False)
        self.assertEqual(done.returncode, 2, "an unknown option installs nothing")

    def test_validation_names_a_missing_validator(self):
        pack_linux.install_tree(self.export / "groundhold.x86_64", self.root / "tree", "1.2.3", DATE)
        with unittest.mock.patch.dict(os.environ, {"PATH": str(self.root / "nothing")}):
            self.assertEqual(pack_linux.validate(self.root / "tree"), ["desktop-file-validate", "appstreamcli"])

    def test_a_metainfo_without_its_placeholder_is_refused(self):
        with unittest.mock.patch.object(pack_linux, "METAINFO", self.root / "x.metainfo.xml"):
            (self.root / "x.metainfo.xml").write_text("<component/>")
            with self.assertRaises(package.PackError):
                pack_linux.metainfo("1.2.3", DATE)


class SystemFilesTest(unittest.TestCase):
    """packaging/linux/ and the packaging image, read as a desktop, a software centre and Docker would."""

    def test_the_menu_entry(self):
        entry = desktop_entry(pack_linux.DESKTOP.read_text(encoding="utf-8"))
        self.assertEqual(pack_linux.DESKTOP.name, f"{package.APP_ID}.desktop")
        self.assertEqual(entry["Type"], "Application")
        self.assertEqual(entry["Name"], "Groundhold")
        self.assertEqual(entry["Exec"], "groundhold", "the .deb's /usr/bin/groundhold")
        self.assertEqual(entry["Icon"], package.APP_ID)
        self.assertEqual(entry["Categories"], "Game;StrategyGame;")
        # (Godot names the window's class after the project: config/name; GNOME groups it with the entry)
        self.assertEqual(entry["StartupWMClass"], "Groundhold")
        self.assertIn('config/name="Groundhold"', (ROOT / "project.godot").read_text(encoding="utf-8"))
        for key in ("GenericName", "Comment", "Terminal"):
            self.assertIn(key, entry)

    def test_the_appstream_data(self):
        component = ET.parse(pack_linux.METAINFO).getroot()
        self.assertEqual(component.get("type"), "desktop-application")
        self.assertEqual(component.findtext("id"), package.APP_ID)
        self.assertEqual(component.findtext("launchable"), pack_linux.DESKTOP.name)
        self.assertEqual(component.findtext("provides/binary"), "groundhold")
        self.assertEqual(component.findtext("metadata_license"), "CC0-1.0")
        self.assertEqual(component.findtext("developer/name"), "Sascha Becker")
        self.assertEqual(component.find("content_rating").get("type"), "oars-1.1")
        urls = {url.get("type"): url.text for url in component.findall("url")}
        self.assertEqual(urls["homepage"], package.HOMEPAGE)
        self.assertEqual(urls["vcs-browser"], "https://github.com/saschb2b/Groundhold")
        shots = component.findall("screenshots/screenshot")
        self.assertEqual(sum(1 for s in shots if s.get("type") == "default"), 1)
        for shot in shots:
            url = shot.findtext("image")
            self.assertTrue(url.startswith("https://saschb2b.github.io/Groundhold/media/"), url)
            self.assertTrue((ROOT / "docs" / "media" / url.rsplit("/", 1)[1]).is_file(),
                            f"{url}: the site publishes docs/media/ as media/")
            self.assertTrue(shot.findtext("caption"))
        self.assertIn("<!-- release -->", pack_linux.METAINFO.read_text(encoding="utf-8"))

    def test_install_sh_copies_every_icon_size(self):
        text = pack_linux.INSTALL_SH.read_text(encoding="utf-8")
        sizes = re.search(r'^sizes="([\d ]+)"$', text, re.M).group(1).split()
        self.assertEqual([int(n) for n in sizes], list(app_icon.PNG_SIZES))
        self.assertIn(f"id={package.APP_ID}\n", text)
        self.assertTrue(text.startswith("#!/bin/sh\n"))

    def test_the_packaging_image_has_every_tool_and_pins_the_appimage_ones(self):
        dockerfile = (package.PACKAGING / "Dockerfile").read_text(encoding="utf-8")
        for name in ("python3", "nsis", "zsync", "desktop-file-utils", "appstream"):
            self.assertRegex(dockerfile, rf"\b{re.escape(name)}\b")
        self.assertRegex(dockerfile, r"(?m)^FROM debian:\w+")
        pins = (package.PACKAGING / "appimage.sh").read_text(encoding="utf-8")
        self.assertIn("TOOL_VER=1.9.1\n", pins)
        self.assertRegex(pins, r"TOOL_SHA=[0-9a-f]{64}\n")
        self.assertRegex(pins, r"RUNTIME_VER=\d{8}\n")
        self.assertRegex(pins, r"RUNTIME_SHA=[0-9a-f]{64}\n")
        self.assertEqual(pins.count("sha256sum -c"), 2, "both checked before use")
        self.assertIn("cd /opt/appimage\n", pins)
        self.assertIn("-o runtime-x86_64 ", pins)
        self.assertEqual(pack_linux.RUNTIME, "/opt/appimage/runtime-x86_64", "where the image keeps the runtime")
        self.assertIn("/usr/local/bin/appimagetool", pins, "appimagetool on the path")


if __name__ == "__main__":
    unittest.main()
