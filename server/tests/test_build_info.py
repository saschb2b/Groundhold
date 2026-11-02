"""What GET /health says of the build: the release's version and the commit, read from the
build.json build.py and release.py pack beside the package, or from a checkout's project.godot
(groundhold_server/build_info.py)."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from support import ROOT
from groundhold_server import build_info

sys.path.insert(0, str(ROOT / "server"))
import build   # noqa: E402  (server/build.py)


class BuildInfoTests(unittest.TestCase):
    def test_a_checkout_names_project_godots_version_and_no_commit(self):
        self.assertEqual(build_info.VERSION, build_info.version_of(ROOT))
        self.assertRegex(build_info.VERSION, r"^\d+\.\d+\.\d+$")
        self.assertIsNone(build_info.BUILD)

    def test_a_tree_without_project_godot_is_dev(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(build_info.version_of(directory), "dev")
            self.assertEqual(build.version_of(Path(directory)), "dev")

    def test_build_json_takes_the_release_or_the_tree_and_a_commit_of_hex_alone(self):
        stamp = json.loads(build.build_json(ROOT, "9.9.9", "ABCDEF0123456789abcdef0123456789abcdef01"))
        self.assertEqual(stamp, {"version": "9.9.9", "build": "abcdef012345"})
        stamp = json.loads(build.build_json(ROOT, "dev", "not a commit; rm -rf /"))
        self.assertEqual(stamp, {"version": build_info.version_of(ROOT), "build": None})

    def test_the_zipapp_tells_its_own_build(self):
        with tempfile.TemporaryDirectory(prefix="groundhold-build-info-") as directory:
            built = build.build(Path(directory) / "groundhold-server.pyz", "1.2.3", "0123456789abcdef")
            probe = ("import sys; sys.path.insert(0, sys.argv[1]); "
                     "from groundhold_server.build_info import VERSION, BUILD; print(VERSION, BUILD)")
            result = subprocess.run([sys.executable, "-I", "-c", probe, str(built)], capture_output=True, text=True,
                                    timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split(), ["1.2.3", "0123456789ab"])


if __name__ == "__main__":
    unittest.main()
