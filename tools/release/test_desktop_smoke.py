"""The desktop boot check passes a game that reaches the hub's banner and quits cleanly, and
fails one that errs, hangs, exits badly or lost its data. Fake games (small scripts) stand in
for the export; release.yml runs the check on the real Linux build.

    python3 -m unittest discover -s tools/release -t tools/release
"""

import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest

import desktop_smoke

BANNER = desktop_smoke.expected_banner(desktop_smoke.ROOT, 7)


class DesktopSmokeTest(unittest.TestCase):
    def game(self, body: str) -> Path:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "groundhold.x86_64"
        path.write_text(f"#!{sys.executable}\nimport os, sys, time\n{body}\n", encoding="utf-8")
        path.chmod(0o755)
        return path

    def smoke(self, game: Path, *extra) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = desktop_smoke.main([str(game), "--build-seq", "7", "--timeout", "10", *extra])
        return code, out.getvalue()

    def test_the_banner_names_version_build_and_official_server(self):
        self.assertRegex(BANNER, r"^Groundhold \d+\.\d+\.\d+ \(build 7\), official server wss://\S+/causeway$")

    def test_a_game_that_reaches_the_hub_passes(self):
        game = self.game("assert sys.argv[1:] == ['--headless', '--quit-after', '300'], sys.argv\n"
                         "print('Godot Engine v4.7.1.stable.official')\nprint(%r)" % BANNER)
        code, out = self.smoke(game)
        self.assertEqual(code, 0, out)
        self.assertIn("booted to the hub and quit", out)

    def test_it_runs_in_a_home_of_its_own(self):
        game = self.game("assert os.environ['HOME'] != %r, 'the real home'\n"
                         "assert os.environ['XDG_DATA_HOME'].startswith(os.environ['HOME'])\nprint(%r)"
                         % (os.environ.get("HOME", ""), BANNER))
        self.assertEqual(self.smoke(game)[0], 0)

    def test_an_error_line_fails(self):
        game = self.game("print(%r)\nprint('SCRIPT ERROR: Invalid call. Nonexistent function')\n"
                         "print('   at: _ready (res://scripts/ui/shell.gd:48)')" % BANNER)
        code, out = self.smoke(game)
        self.assertEqual(code, 1)
        self.assertIn("error line(s)", out)

    def test_no_banner_fails(self):
        code, out = self.smoke(self.game("print('Godot Engine v4.7.1.stable.official')"))
        self.assertEqual(code, 1)
        self.assertIn("no banner", out)

    def test_another_build_or_server_fails(self):
        game = self.game("print(%r)" % BANNER.replace("(build 7)", "(build 0)"))
        self.assertEqual(self.smoke(game)[0], 1)

    def test_a_bad_exit_fails(self):
        code, out = self.smoke(self.game("print(%r)\nsys.exit(3)" % BANNER))
        self.assertEqual(code, 1)
        self.assertIn("exited with 3", out)

    def test_a_game_that_never_quits_is_stopped(self):
        game = self.game("print(%r, flush=True)\ntime.sleep(60)" % BANNER)
        code, out = self.smoke(game, "--timeout", "1")
        self.assertEqual(code, 1)
        self.assertIn("still running after 1 s", out)


if __name__ == "__main__":
    unittest.main()
