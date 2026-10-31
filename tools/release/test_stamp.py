"""A build is numbered twice: data/build.json inside the export (HELLO's build_seq) and the
exported Web shell's ?v= on its files. A shell without the mark fails the stamp.

    python3 -m unittest discover -s tools/release -t tools/release
"""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import stamp


class StampTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        (self.root / "data").mkdir()
        (self.root / "project.godot").write_text('[application]\nconfig/version="1.2.0"\n', encoding="utf-8")

    def quietly(self, *argv) -> int:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return stamp.main(["--root", str(self.root), *argv])

    def test_build_json_holds_the_number_the_game_reads(self):
        self.assertEqual(self.quietly("build-json", "--build-seq", "42", "--commit", "abc123"), 0)
        record = json.loads((self.root / "data" / "build.json").read_text(encoding="utf-8"))
        self.assertEqual(record, {"build_seq": 42, "commit": "abc123", "version": "1.2.0"})

    def test_the_shell_gets_the_number_over_every_mark(self):
        shell = self.root / "index.html"
        shell.write_text('const BUILD_SEQ = "@BUILD_SEQ@"; // @BUILD_SEQ@', encoding="utf-8")
        self.assertEqual(self.quietly("shell", "--build-seq", "42", str(shell)), 0)
        self.assertEqual(shell.read_text(encoding="utf-8"), 'const BUILD_SEQ = "42"; // 42')

    def test_a_shell_without_the_mark_fails(self):
        shell = self.root / "index.html"
        shell.write_text("<script src=index.js></script>", encoding="utf-8")
        self.assertEqual(self.quietly("shell", "--build-seq", "42", str(shell)), 1)

    def test_the_number_fits_hellos_u32(self):
        with self.assertRaises(SystemExit):
            self.quietly("build-json", "--build-seq", str(1 << 32))

    def test_the_game_reads_the_same_key(self):
        session = (stamp.ROOT / "scripts" / "session" / "session.gd").read_text(encoding="utf-8")
        self.assertIn('res://data/build.json', session)
        self.assertIn('.get("build_seq", 0)', session)


if __name__ == "__main__":
    unittest.main()
