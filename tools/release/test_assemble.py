"""A release gathers exactly its files (the game's seven: the Windows installer and zip, the macOS disk
image, the AppImage and its .zsync, the .deb and the tar.gz; and the server's six archives),
checksums them, and refuses to go on with one missing, empty, or one no release has.

    python3 -m unittest discover -s tools/release -t tools/release
"""

import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

import assemble

ROOT = Path(__file__).resolve().parents[2]


def server_release():
    """server/release.py, which names the server's archives (its own imports from server/)."""
    sys.path.insert(0, str(ROOT / "server"))
    try:
        spec = importlib.util.spec_from_file_location("server_release", ROOT / "server" / "release.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(ROOT / "server"))
    return module


class AssembleTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.dist = Path(folder.name) / "dist"
        self.dist.mkdir()

    def put(self, *names):
        for name in names:
            with zipfile.ZipFile(self.dist / name, "w") as z:
                z.writestr("README.txt", name)

    def run_it(self):
        listing = self.dist.parent / "files.txt"     # (release.yml writes it beside dist/)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = assemble.main([str(self.dist), "--list", str(listing)])
        files = listing.read_text(encoding="utf-8").split() if listing.exists() else []
        return code, [Path(f).name for f in files], out.getvalue()

    def test_the_releases_files(self):
        self.assertEqual(assemble.FILES, [
            "groundhold-windows-x64-setup.exe", "groundhold-windows-x64.zip", "groundhold-macos.dmg",
            "groundhold-x86_64.AppImage", "groundhold-x86_64.AppImage.zsync", "groundhold_amd64.deb",
            "groundhold-linux-x64.tar.gz",
            "groundhold-server-python.zip", "groundhold-server-windows-x64.zip", "groundhold-server-macos-arm64.zip",
            "groundhold-server-macos-x64.zip", "groundhold-server-linux-x64.zip", "groundhold-server-linux-arm64.zip"])
        self.assertEqual(set(assemble.WHAT), set(assemble.FILES) | {assemble.SUMS}, "each file says what it is")

    def test_every_file_and_the_checksums_last(self):
        self.put(*assemble.FILES)
        code, files, out = self.run_it()
        self.assertEqual(code, 0, out)
        self.assertEqual(files, assemble.FILES + ["SHA256SUMS.txt"])
        sums = (self.dist / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(sums), 13)
        for line in sums:
            digest, name = line.split("  ")
            self.assertEqual(digest, hashlib.sha256((self.dist / name).read_bytes()).hexdigest())
        self.assertEqual(self.run_it()[:2], (0, files), "again, the checksums of a first run not counted")

    def test_a_missing_file_stops_the_release(self):
        self.put(*[name for name in assemble.FILES if name != "groundhold-server-linux-arm64.zip"])
        code, files, out = self.run_it()
        self.assertEqual((code, files), (1, []))
        self.assertIn("groundhold-server-linux-arm64.zip is missing", out)
        self.assertFalse((self.dist / "SHA256SUMS.txt").exists())

    def test_an_empty_file_or_one_no_release_has_stops_it(self):
        self.put(*assemble.FILES)
        (self.dist / "groundhold-macos.dmg").write_bytes(b"")
        (self.dist / "groundhold-macos.zip").write_bytes(b"an older release's name")
        code, files, out = self.run_it()
        self.assertEqual((code, files), (1, []))
        self.assertIn("groundhold-macos.dmg is empty", out)
        self.assertIn("groundhold-macos.zip is no file of a release", out)

    def test_the_appimages_update_file_is_a_file_of_every_release(self):
        # (the AppImage's update information asks the newest release for this .zsync: never renamed;
        # test_pack_*.py hold each package to its name here)
        import pack_linux

        self.assertTrue(pack_linux.UPDATE.endswith(f"|latest|{assemble.ZSYNC}"))
        self.assertEqual(assemble.ZSYNC, assemble.APPIMAGE + ".zsync")
        self.assertIn(assemble.ZSYNC, assemble.FILES)

    def test_the_server_files_are_what_its_packaging_makes(self):
        release = server_release()
        self.assertEqual(sorted(assemble.SERVER_TARGETS), sorted(set(release.TARGETS.values())))
        self.assertEqual(sorted(assemble.SERVER), sorted(f"{release.NAME}-{target}.zip" for target in release.SYSTEMS))


if __name__ == "__main__":
    unittest.main()
