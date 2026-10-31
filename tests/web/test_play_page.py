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

    def test_the_page_knows_the_games_code_symbols(self):
        session = (PAGE.parents[2] / "scripts" / "session" / "session.gd").read_text(encoding="utf-8")
        symbols = re.search(r'const CODE_SYMBOLS := "([^"]+)"', session).group(1)
        self.assertIn("[%s]{5}" % symbols, PAGE.read_text(encoding="utf-8"))

    def test_forwards_a_code_with_spaces_without_them(self):
        self.assertEqual(frame_source("?join=k7q%204m"), "game/?join=k7q4m")

    def test_a_malformed_code_is_ignored_not_cut_into_another(self):
        # (review M5 round 2: k7q-4m extra became k7q-4mext, a wrong code, not no code)
        for search in ("?join=k7q-4m%20extra", "?join=%22%3E%3Cb%3EK7Q4M", "?join=K7Q4M0123456789",
                       "?join=K7Q4", "?join=K7Q4MM", "?join=A7Q4M", "?join=K0Q4M"):
            self.assertEqual(frame_source(search), "game/", search)


if __name__ == "__main__":
    unittest.main()
