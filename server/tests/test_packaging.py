"""The server's packages (docs/design/core-loop.md §7.3 test_packaging, M5 track A): the zipapp
is reproducible and holds its allowlist alone; a release archive holds its program, a README for
its system, the licence, the example settings and BUILD.json; the zipapp's archive runs outside
the checkout (smoke.py: help, /health, a game's HELLO, the roster, a backup, a clean stop), and
the smoke fails a package that needs the checkout; a failed smoke leaves no archive; a native
archive's notices come from the build host and never from git; the build tools are pinned by
hash, and the native targets are the workflows'.

Adapted from Cyberworld Endless's server/tests/test_packaging.py (MIT, Sascha Becker)."""

import contextlib
import importlib.metadata
import importlib.util
import io
import json
from pathlib import Path
import platform
import re
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

from support import ROOT   # (server/ on the path, and the test process's memory cap)
import build                # noqa: E402
import notices              # noqa: E402
import release              # noqa: E402
import smoke                # noqa: E402
from groundhold_server.protocol import SPEC   # noqa: E402


def release_files():
    spec = importlib.util.spec_from_file_location("release_files", ROOT / "tools/release/assemble.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def has_licence():
    try:
        notices.interpreter_licence()
        return True
    except RuntimeError:
        return False


class ZipappTests(unittest.TestCase):
    def test_the_zipapp_is_reproducible_and_holds_its_allowlist_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            first = build.build(Path(directory) / "a/server.pyz")
            second = build.build(Path(directory) / "b/server.pyz")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            expected = {"__main__.py", "LICENSE", "groundhold_server/protocol.json"}
            expected.update("groundhold_server/" + file.name for file in (ROOT / "server/groundhold_server").glob("*.py"))
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(set(archive.namelist()), expected)
                self.assertEqual(json.loads(archive.read("groundhold_server/protocol.json")),
                                 json.loads((ROOT / "shared/net/protocol.json").read_text()))
                self.assertTrue(all(entry.date_time == (1980, 1, 1, 0, 0, 0) for entry in archive.infolist()))
            self.assertEqual(sorted(path.name for path in first.parent.iterdir()),
                             ["LICENSE", "README.md", "server.example.ini", "server.pyz"])


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="groundhold-release-")
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_a_release_archive_holds_its_program_its_readme_and_its_build_record(self):
        program = build.build(self.root / "work/groundhold-server.pyz")
        archive = release.archive(program, "python", self.root / "out", "1.2.3")
        self.assertEqual(archive.name, "groundhold-server-python.zip")
        top = "groundhold-server-1.2.3-python/"
        with zipfile.ZipFile(archive) as bundle:
            # (one folder, as the game's zips hold theirs: an unzip in Downloads makes that folder alone)
            self.assertEqual(bundle.namelist(), [top + name for name in ("groundhold-server.pyz", "README.txt", "LICENSE",
                                                                         "server.example.ini", "BUILD.json")])
            self.assertEqual(bundle.read(top + "groundhold-server.pyz"), program.read_bytes())
            self.assertEqual(bundle.getinfo(top + "groundhold-server.pyz").external_attr >> 16, 0o100755)
            record = json.loads(bundle.read(top + "BUILD.json"))
            self.assertEqual(record, {"target": "python", "version": "1.2.3", "executable": "groundhold-server.pyz",
                                      "python": platform.python_version(), "protocol": SPEC["version"]})
            self.assertIn("Groundhold server 1.2.3", bundle.read(top + "README.txt").decode())

    def test_a_native_archive_carries_its_notices_and_its_pyinstaller(self):
        program = self.root / "groundhold-server"
        program.write_bytes(b"\x7fELF not really")
        archive = release.archive(program, "macos-arm64", self.root / "out", "1.2.3",
                                  [("Python.txt", b"PSF"), ("README.md", b"# notices")], pyinstaller="6.16.0")
        top = "groundhold-server-1.2.3-macos-arm64/"
        with zipfile.ZipFile(archive) as bundle:
            self.assertEqual(bundle.namelist(), [top + name for name in (
                "groundhold-server", "README.txt", "LICENSE", "server.example.ini", "licenses/Python.txt",
                "licenses/README.md", "BUILD.json")])
            self.assertEqual(json.loads(bundle.read(top + "BUILD.json"))["pyinstaller"], "6.16.0")
            self.assertIn("licenses/", bundle.read(top + "README.txt").decode())

    def test_the_smoke_refuses_an_archive_without_its_one_folder(self):
        # (files loose at the top, as an unzip in Downloads would scatter them)
        program = build.build(self.root / "work/groundhold-server.pyz")
        flat = self.root / "flat.zip"
        with zipfile.ZipFile(release.archive(program, "python", self.root / "out", "1.2.3")) as good, \
                zipfile.ZipFile(flat, "w") as bad:
            for entry in good.infolist():
                bad.writestr(entry.filename.split("/", 1)[1], good.read(entry))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "not one folder"):
                smoke.program(flat, Path(directory))

    def test_each_systems_readme_says_how_to_start_it_there(self):
        for target in ["python"] + sorted(set(release.TARGETS.values())):
            text = release.readme(target, "1.2.3")
            # (Nearby hears the beacon on UDP 8767: review M5 round 2, the archive named TCP alone)
            for common in ("Join panel", "server-data", "server.example.ini", "TCP port 8766", "UDP port 8767",
                           release.GUIDE):
                self.assertIn(common, text, target)
            self.assertTrue(all(len(line) <= 100 for line in text.splitlines()), target)
            self.assertTrue(text.isascii(), target)
        self.assertIn("python3 groundhold-server.pyz", release.readme("python", "1"))
        self.assertIn("Python 3.11", release.readme("python", "1"))
        windows = release.readme("windows-x64", "1")
        for words in ("groundhold-server.exe", "SmartScreen", "Run anyway", "private networks"):
            self.assertIn(words, windows)
        for target in ("macos-x64", "macos-arm64"):
            mac = release.readme(target, "1")
            for words in ("./groundhold-server", "xattr -d com.apple.quarantine groundhold-server",
                          "Privacy & Security", "Open Anyway", "~/server-data"):
                self.assertIn(words, mac, target)
        self.assertIn("chmod +x groundhold-server", release.readme("linux-arm64", "1"))
        self.assertNotIn("xattr", release.readme("linux-x64", "1"))

    def test_the_zipapps_archive_runs_outside_the_checkout(self):
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            archive = release.main(["--version", "0.0.0-test", "--output", str(self.root / "out"),
                                    "--work", str(self.root / "work")])
        self.assertIn("Packaged server passed: groundhold-server-python.zip", printed.getvalue())
        self.assertEqual(archive, self.root / "out/groundhold-server-python.zip")
        self.assertTrue(archive.is_file())

    def test_the_smoke_fails_a_package_that_needs_the_checkout(self):
        # (a zipapp without protocol.json finds none outside the checkout: it cannot start)
        broken = self.root / "broken.pyz"
        with zipfile.ZipFile(build.build(self.root / "good/groundhold-server.pyz")) as good, \
                zipfile.ZipFile(broken, "w") as bad:
            for entry in good.infolist():
                if entry.filename != "groundhold_server/protocol.json":
                    bad.writestr(entry, good.read(entry))
        with self.assertRaises(Exception):
            smoke.smoke(broken)

    def test_a_failed_smoke_leaves_no_archive(self):
        with mock.patch.object(release, "smoke", side_effect=RuntimeError("no /health")):
            with self.assertRaises(RuntimeError):
                release.main(["--output", str(self.root / "out"), "--work", str(self.root / "work")])
        self.assertEqual(list((self.root / "out").iterdir()), [])


class NativeTests(unittest.TestCase):
    def test_the_native_targets_are_the_workflows(self):
        files = release_files()
        self.assertEqual(sorted(set(release.TARGETS.values())), sorted(files.SERVER_TARGETS))
        self.assertEqual(release.target_for("Linux", "x86_64"), "linux-x64")
        self.assertEqual(release.target_for("Darwin", "arm64"), "macos-arm64")
        self.assertIsNone(release.target_for("Windows", "ARM64"))
        self.assertEqual(release.executable_name("windows-x64"), "groundhold-server.exe")
        self.assertEqual(release.executable_name("macos-x64"), "groundhold-server")

    def test_a_native_build_refuses_another_computers_target_before_building(self):
        here = release.target_for(platform.system(), platform.machine())
        other = next(target for target in sorted(set(release.TARGETS.values())) if target != here)
        with mock.patch.object(release, "native") as native, mock.patch("sys.stderr"):
            with self.assertRaises(SystemExit):
                release.main(["--native", "--target", other])
            with self.assertRaises(SystemExit):
                release.main(["--target", other])
        native.assert_not_called()

    def test_a_native_build_needs_the_pinned_pyinstaller(self):
        with tempfile.TemporaryDirectory() as directory:
            for found in ("6.0.0", importlib.metadata.PackageNotFoundError("pyinstaller")):
                answer = {"side_effect": found} if isinstance(found, Exception) else {"return_value": found}
                with mock.patch.object(release.importlib.metadata, "version", **answer), \
                        mock.patch.object(release.subprocess, "run") as run:
                    with self.assertRaisesRegex(RuntimeError, "PyInstaller 6.16.0"):
                        release.native(Path(directory))
                    run.assert_not_called()

    def test_the_build_tools_are_pinned_by_hash(self):
        text = (ROOT / "server/requirements-build.txt").read_text()
        requirements = [block for block in re.split(r"\n\s*\n", text) if block.strip() and not block.startswith("#")]
        self.assertGreaterEqual(len(requirements), 5)
        pins = {}
        for block in requirements:
            pin = re.match(r"([A-Za-z0-9_.-]+)==([0-9][0-9A-Za-z.]*)", block)
            self.assertIsNotNone(pin, block)
            pins[pin[1].lower()] = pin[2]
            self.assertTrue(re.findall(r"--hash=sha256:[0-9a-f]{64}", block), block)
        self.assertEqual(pins["pyinstaller"], release.PYINSTALLER)

    def test_no_third_party_licence_text_is_committed(self):
        self.assertFalse((ROOT / "server/licenses").exists())

    @unittest.skipUnless(has_licence(), "this Python carries no LICENSE file")
    def test_the_notices_cover_every_frozen_library_or_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            keg = work / "keg"
            (keg / "lib").mkdir(parents=True)
            (keg / "lib/libkeg.so.1").write_bytes(b"")
            (keg / "LICENSE.txt").write_text("keg licence\n")
            bare = work / "a/b/c/d"
            bare.mkdir(parents=True)
            (bare / "libbare.so.1").write_bytes(b"")
            inside = str(notices.interpreter_root() / "libinside.so.1")
            toc = work / "work/groundhold-server/Analysis-00.toc"
            toc.parent.mkdir(parents=True)
            toc.write_text(repr((["main.py"], [("libinside.so.1", inside, "BINARY"),
                                               ("libkeg.so.1", str(keg / "lib/libkeg.so.1"), "BINARY"),
                                               ("_ssl.so", "/x/_ssl.so", "EXTENSION")])))
            found, covered = notices.collect(work)
            self.assertEqual([name for name, _, _ in found], ["Python.txt", "keg.txt"])
            self.assertEqual(covered, {"Python.txt": ["libinside.so.1"], "keg.txt": ["libkeg.so.1"]})
            self.assertIn("`keg.txt`", notices.readme(found, covered, "linux-x64"))
            toc.write_text(repr([("libbare.so.1", str(bare / "libbare.so.1"), "BINARY")]))
            with self.assertRaisesRegex(RuntimeError, "libbare.so.1"):
                notices.collect(work)

    def test_a_systems_python_counts_its_standard_library_alone_as_its_install(self):
        # (prefix /usr holds every library of the system: libssl there is not Python's to cover)
        with mock.patch.object(sys, "base_prefix", "/usr"):
            root = notices.interpreter_root()
        self.assertNotEqual(root, Path("/usr"))
        self.assertFalse(notices.inside(Path("/usr/lib/x86_64-linux-gnu/libssl.so.3"), root))
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(sys, "base_prefix", directory):
            self.assertEqual(notices.interpreter_root(), Path(directory))


if __name__ == "__main__":
    unittest.main()
