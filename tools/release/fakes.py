"""Stand-ins for the packaging tools a test cannot run here (makensis, appimagetool, codesign, hdiutil):
a script on a PATH of the test's own that records each call and makes what the real tool would."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import unittest.mock

SCRIPT = """#!{python}
import json, sys
from pathlib import Path
with open({log!r}, "a", encoding="utf-8") as log:
    log.write(json.dumps({{"tool": {name!r}, "args": sys.argv[1:], "cwd": str(Path.cwd())}}) + "\\n")
{body}
"""


class Tools:
    """Fake tools in `folder`/bin, each a Python body run with sys.argv; `calls()` reads what ran."""

    def __init__(self, folder: Path):
        self.bin = folder / "bin"
        self.bin.mkdir(parents=True, exist_ok=True)
        self.log = folder / "calls.jsonl"

    def add(self, name: str, body: str = "") -> None:
        path = self.bin / name
        path.write_text(SCRIPT.format(python=sys.executable, log=str(self.log), name=name, body=body),
                        encoding="utf-8")
        path.chmod(0o755)

    def path(self):
        """A context in which these tools come first on PATH."""
        return unittest.mock.patch.dict(os.environ, {"PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}"})

    def calls(self) -> list[dict]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]
