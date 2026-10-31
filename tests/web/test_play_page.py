"""The site's play page (web/play/index.html) hands a party link's code on to the game in its frame:
play/?join=K7Q4M opens game/?join=K7Q4M, where WebBridge.query("join") reads it (design 6.8,
docs/design/contract-m4.md). The page's own script runs under Node, given the query string.

    python3 -m unittest discover -s tests/web -t tests/web

Needs Node (any version with URLSearchParams); skipped without it.
"""

import json
import pathlib
import re
import shutil
import subprocess
import unittest

PAGE = pathlib.Path(__file__).resolve().parents[2] / "web" / "play" / "index.html"
NODE = shutil.which("node")


def frame_source(search: str) -> str:
    """The iframe's src the page sets for a location whose query string is `search`."""
    html = PAGE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    if not scripts:
        raise AssertionError("the play page has no script")
    harness = """
const gameFrame = { src: "game/", requestFullscreen() {}, focus() {} };
const document = { getElementById: (id) => id === "game" ? gameFrame : { addEventListener() {} } };
const location = { search: %s };
%s
process.stdout.write(gameFrame.src);
""" % (json.dumps(search), scripts[-1])
    run = subprocess.run([NODE, "-e", harness], capture_output=True, text=True, timeout=30, check=False)
    if run.returncode != 0:
        raise AssertionError(run.stderr)
    return run.stdout


@unittest.skipIf(NODE is None, "needs node")
class PlayPageTest(unittest.TestCase):
    def test_forwards_join(self):
        self.assertEqual(frame_source("?join=K7Q4M"), "game/?join=K7Q4M")

    def test_forwards_a_lenient_code(self):
        self.assertEqual(frame_source("?join=k7q-4m&utm=x"), "game/?join=k7q-4m")

    def test_without_join_plays_plainly(self):
        self.assertEqual(frame_source(""), "game/")
        self.assertEqual(frame_source("?join="), "game/")

    def test_passes_only_code_symbols(self):
        self.assertEqual(frame_source("?join=%22%3E%3Cb%3EK7Q4M"), "game/?join=bK7Q4M")
        self.assertEqual(frame_source("?join=K7Q4M0123456789"), "game/?join=K7Q4M0123")


if __name__ == "__main__":
    unittest.main()
