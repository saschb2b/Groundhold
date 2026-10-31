"""The game's page (web/shell.html, the Web export's custom shell) asks for the build's own files
as ?v=<build_seq> once CI has written the number in (tools/release/stamp.py shell): the engine's
.js, .wasm and .pck, and nothing else (design 6.8, caching). Unstamped, as a local export leaves
it, it asks plainly. The shell's script runs under Node with Godot's placeholders filled in as an
export fills them, a fake Engine that fetches as Godot's loader does, and a fake fetch that
records the URLs.

    python3 -m unittest discover -s tests/web -t tests/web

Needs Node; skipped without it.
"""

import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHELL = ROOT / "web" / "shell.html"
NODE = shutil.which("node")
sys.path.insert(0, str(ROOT / "tools" / "release"))
import stamp  # noqa: E402

# What a Web export writes for $GODOT_CONFIG and $GODOT_URL (Godot 4.7, no threads).
CONFIG = {"args": [], "canvasResizePolicy": 2, "executable": "index", "experimentalVK": False,
          "fileSizes": {"index.pck": 11000000, "index.wasm": 39500000}, "focusCanvas": True,
          "gdextensionLibs": []}


def exported(build_seq=None) -> str:
    """The shell as the export writes it, stamped with `build_seq` as CI does (None: as a local
    export leaves it)."""
    html = SHELL.read_text(encoding="utf-8")
    html = html.replace("$GODOT_CONFIG", json.dumps(CONFIG)).replace("$GODOT_URL", "index.js")
    html = html.replace("$GODOT_PROJECT_NAME", "Groundhold").replace("$GODOT_HEAD_INCLUDE", "")
    if build_seq is not None:
        with tempfile.TemporaryDirectory() as folder:
            page = pathlib.Path(folder) / "index.html"
            page.write_text(html, encoding="utf-8")
            if stamp.stamp_shell(page, build_seq) == 0:
                raise AssertionError("the shell has no build mark")
            html = page.read_text(encoding="utf-8")
    return html


def requests(html: str) -> list[str]:
    """Every URL the page's script loads or fetches as the engine starts: the engine script's
    src, then what the engine's loader fetches (its .wasm and .pck by name, and another file)."""
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    if not scripts:
        raise AssertionError("the shell has no inline script")
    harness = """
const seen = [];
const element = (id) => ({ id, style: {}, textContent: "", focus() {}, remove() {}, addEventListener() {} });
const nodes = {};
const document = {
  getElementById: (id) => (nodes[id] = nodes[id] || element(id)),
  createElement: (tag) => ({ tag }),
  body: { appendChild(child) { seen.push(child.src); globalThis.loaded = child; } },
};
const window = { fetch: (url, init) => { seen.push(url); return Promise.resolve({ ok: true }); } };
class Engine {
  constructor(config) { this.config = config; }
  static getMissingFeatures() { return []; }
  startGame() {
    window.fetch(this.config.executable + ".wasm");
    window.fetch(this.config.executable + ".pck");
    window.fetch("index.audio.worklet.js");
    return Promise.resolve();
  }
}
%s
globalThis.loaded.onload();
setTimeout(() => process.stdout.write(JSON.stringify(seen)), 0);
""" % scripts[-1]
    run = subprocess.run([NODE, "-e", harness], capture_output=True, text=True, timeout=30, check=False)
    if run.returncode != 0:
        raise AssertionError(run.stderr)
    return json.loads(run.stdout)


@unittest.skipIf(NODE is None, "needs node")
class ShellTest(unittest.TestCase):
    def test_a_numbered_build_asks_for_its_own_files(self):
        self.assertEqual(requests(exported(42)),
                         ["index.js?v=42", "index.wasm?v=42", "index.pck?v=42", "index.audio.worklet.js"])

    def test_a_local_export_asks_plainly(self):
        self.assertEqual(requests(exported()), ["index.js", "index.wasm", "index.pck", "index.audio.worklet.js"])

    def test_the_mark_is_in_the_shell(self):
        self.assertIn(stamp.MARK, SHELL.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
