"""The macOS game's disk image (pack_macos.py): Godot's export zip unpacked with its modes, the licences
put in the app, the app signed ad hoc and verified, then the image made of the app, an Applications
link and the Read me, and verified. Fake codesign and hdiutil stand in for Apple's here; the real ones
run on release.yml's macOS runner.

    python3 -m unittest discover -s tools/release -t tools/release
"""

import os
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

import assemble
import fakes
import pack_macos
import package


def godot_export(path: Path, binary: bool = True, extra: dict | None = None) -> Path:
    """A zip as Godot's macOS preset exports it."""
    with zipfile.ZipFile(path, "w") as archive:
        entries = {"Groundhold.app/Contents/Info.plist": (b"<plist/>", 0o644),
                   "Groundhold.app/Contents/Resources/Groundhold.pck": (b"GDPC", 0o644),
                   "Groundhold.app/Contents/Resources/icon.icns": (b"icns", 0o644)}
        if binary:
            entries["Groundhold.app/Contents/MacOS/Groundhold"] = (b"\xca\xfe\xba\xbe", 0o755)
        entries.update(extra or {})
        for name, (data, mode) in entries.items():
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = (mode if stat.S_IFMT(mode) else stat.S_IFREG | mode) << 16
            archive.writestr(info, data)
    return path


class PackMacosTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.tools = fakes.Tools(self.root)
        self.tools.add("codesign")
        # (hdiutil create ... TARGET makes the image; hdiutil verify reads it)
        self.tools.add("hdiutil", "if sys.argv[1] == 'create':\n    Path(sys.argv[-1]).write_bytes(b'koly')\n"
                                  "elif not Path(sys.argv[-1]).exists():\n    sys.exit(1)")

    def make(self):
        export = godot_export(self.root / "Groundhold.zip")
        with self.tools.path():
            return pack_macos.make(export, "1.2.3", self.root / "dist", self.root / "work")

    def test_the_app_is_signed_then_imaged_with_applications_and_the_read_me(self):
        made = self.make()
        self.assertEqual([p.name for p in made], [assemble.MACOS_DMG])
        stage = self.root / "work" / "dmg"
        app = stage / "Groundhold.app"
        calls = [(c["tool"], c["args"]) for c in self.tools.calls()]
        self.assertEqual(calls, [
            ("codesign", ["--force", "--deep", "--sign", "-", str(app)]),
            ("codesign", ["--verify", "--deep", "--strict", str(app)]),
            ("hdiutil", ["create", "-volname", "Groundhold", "-srcfolder", str(stage), "-ov", "-format", "UDZO",
                         str(self.root / "dist" / assemble.MACOS_DMG)]),
            ("hdiutil", ["verify", str(self.root / "dist" / assemble.MACOS_DMG)]),
        ])
        self.assertEqual(sorted(p.name for p in stage.iterdir()), ["Applications", "Groundhold.app", "Read me.txt"])
        self.assertEqual(os.readlink(stage / "Applications"), "/Applications")
        text = (stage / "Read me.txt").read_text(encoding="utf-8")
        self.assertIn("Groundhold 1.2.3 for macOS", text)
        self.assertIn("xattr -dr com.apple.quarantine /Applications/Groundhold.app", text)

    def test_the_app_keeps_its_modes_and_carries_the_licences(self):
        self.make()
        contents = self.root / "work" / "dmg" / "Groundhold.app" / "Contents"
        self.assertEqual((contents / "MacOS" / "Groundhold").stat().st_mode & 0o777, 0o755)
        self.assertEqual((contents / "MacOS" / "Groundhold").read_bytes(), b"\xca\xfe\xba\xbe")
        self.assertEqual((contents / "Resources" / "Groundhold.pck").stat().st_mode & 0o777, 0o644)
        licenses = contents / "Resources" / "licenses"
        self.assertEqual(sorted(p.name for p in licenses.iterdir()), sorted(["LICENSE.txt", *package.LICENSES]))
        stage = self.root / "work" / "dmg"
        for path in stage.rglob("*"):
            if path.is_symlink():
                continue
            wanted = 0o755 if path.is_dir() or path.name == "Groundhold" else 0o644
            self.assertEqual(path.stat().st_mode & 0o777, wanted, path.relative_to(stage))

    def test_a_link_in_the_app_stays_a_link(self):
        # (a framework's Versions/Current: codesign refuses a bundle whose link became a file)
        export = godot_export(self.root / "Groundhold.zip", extra={
            "Groundhold.app/Contents/Frameworks/X.framework/Versions/Current": (b"A", stat.S_IFLNK | 0o755)})
        app = pack_macos.unpack(export, self.root / "stage")
        self.assertEqual(os.readlink(app / "Contents/Frameworks/X.framework/Versions/Current"), "A")

    def test_a_failed_signature_stops_it_before_any_image(self):
        self.tools.add("codesign", "if '--verify' in sys.argv:\n    print('invalid signature'); sys.exit(1)")
        with self.assertRaises(package.PackError) as caught:
            self.make()
        self.assertIn("invalid signature", str(caught.exception))
        self.assertFalse(any(c["tool"] == "hdiutil" for c in self.tools.calls()))

    def test_an_export_without_the_app_or_with_a_path_outside_is_refused(self):
        with self.assertRaises(package.PackError) as caught:
            pack_macos.unpack(godot_export(self.root / "a.zip", binary=False), self.root / "a")
        self.assertIn("holds no Groundhold.app/Contents/MacOS/Groundhold", str(caught.exception))
        escape = godot_export(self.root / "b.zip", extra={"../outside.txt": (b"x", 0o644)})
        with self.assertRaises(package.PackError):
            pack_macos.unpack(escape, self.root / "b")
        self.assertFalse((self.root / "outside.txt").exists())


if __name__ == "__main__":
    unittest.main()
