"""A release page's picture tool without Godot: the old build's copy of a scenario takes its "before" keys,
captures are found in the order taken, a compare and a pair are labelled side by side or one over the
other, a clip becomes a GIF under its limit, and every release's shot scenarios are named for their files
and list pictures the tool can make. Needs Pillow (and ffmpeg for the GIF); skipped where they are missing.

    python3 -m unittest discover -s tools/release -t tools/release
"""

import json
from pathlib import Path
import shutil
import tempfile
import unittest

try:
    from PIL import Image
    import pictures
except ImportError:  # (the release's runner has no Pillow: the tool runs where pictures are made)
    pictures = None

ROOT = Path(__file__).resolve().parents[2]


def opened(path: Path):
    """The picture at `path`, read and its file closed."""
    with Image.open(path) as image:
        image.load()
        return image.copy()


@unittest.skipIf(pictures is None, "needs Pillow")
class PicturesTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)

    def shot(self, run: Path, name: str, label: str, n: int, colour, size=(64, 36)):
        captures = run / name / "captures"
        captures.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, colour).save(captures / f"{n:03d}_{label}.png")

    def test_the_old_build_runs_the_scenario_with_its_before_keys(self):
        spec = {"name": "levels", "seed": 1, "steps": [{"capture": "new"}], "pictures": [{"out": "a.webp",
                "compare": "x"}], "before": {"steps": [{"capture": "old"}]}}
        plain = {"name": "plain", "steps": [], "pictures": [{"out": "b.webp", "capture": "y"}]}
        written = pictures.before_files([(Path("levels.json"), spec), (Path("plain.json"), plain)], self.root)
        self.assertEqual([path.name for path in written], ["levels.json"], "only a scenario with a compare")
        old = json.loads(written[0].read_text(encoding="utf-8"))
        self.assertEqual(old, {"name": "levels", "seed": 1, "steps": [{"capture": "old"}]})

    def test_captures_in_the_order_taken(self):
        run = self.root / "run"
        for n in (2, 0, 11):
            self.shot(run, "s", "clip", n, (n, 0, 0))
        self.shot(run, "s", "clipper", 5, (0, 0, 0))
        self.assertEqual([path.name for path in pictures.captures(run, "s", "clip")],
                         ["000_clip.png", "002_clip.png", "011_clip.png"])
        with self.assertRaisesRegex(pictures.PictureError, "no capture 'gone'"):
            pictures.captures(run, "s", "gone")

    def test_a_compare_side_by_side_and_stacked(self):
        new, old = self.root / "new", self.root / "old"
        self.shot(old, "s", "tip", 0, (200, 0, 0), size=(100, 60))
        self.shot(new, "s", "tip", 0, (0, 200, 0), size=(100, 60))
        spec = {"name": "s"}
        out = pictures.make(spec, {"out": "c.webp", "compare": "tip", "crop": [0, 0, 80, 40]}, new, old,
                            self.root / "media", "0.8.0", "0.9.0")
        image = opened(out).convert("RGB")
        self.assertEqual(image.width, 80 + pictures.GAP + 80)
        bar = image.height - 40
        self.assertGreater(bar, 20, "a label over each")
        left, right = image.getpixel((40, bar + 20)), image.getpixel((80 + pictures.GAP + 40, bar + 20))
        self.assertGreater(left[0], 150, "the old build on the left")
        self.assertGreater(right[1], 150, "the new on the right")
        stacked = pictures.make(spec, {"out": "d.png", "compare": "tip", "layout": "stack"}, new, old,
                                self.root / "media", "0.8.0", "0.9.0")
        image = opened(stacked)
        self.assertEqual(image.width, 100)
        self.assertGreater(image.height, 120 + pictures.GAP)
        with self.assertRaisesRegex(pictures.PictureError, "needs the old build"):
            pictures.make(spec, {"out": "e.webp", "compare": "tip"}, new, None, self.root, "", "0.9.0")

    def test_a_still_cut_and_scaled(self):
        run = self.root / "run"
        self.shot(run, "s", "hero", 0, (10, 20, 30), size=(1280, 720))
        out = pictures.make({"name": "s"}, {"out": "hero.webp", "capture": "hero", "crop": [0, 0, 640, 360],
                                            "width": 320}, run, None, self.root / "media", "", "0.9.0")
        self.assertEqual(opened(out).size, (320, 180))
        with self.assertRaisesRegex(pictures.PictureError, "a still is .webp or .png"):
            pictures.make({"name": "s"}, {"out": "hero.jpg", "capture": "hero"}, run, None, self.root, "", "0.9.0")

    @unittest.skipIf(shutil.which("ffmpeg") is None, "needs ffmpeg")
    def test_a_clip_is_a_gif_of_its_frames(self):
        run = self.root / "run"
        for n in range(6):
            self.shot(run, "s", "clip", n, (40 * n, 100, 200 - 30 * n), size=(160, 90))
        out = pictures.make({"name": "s"}, {"out": "c.gif", "clip": "clip", "width": 80, "fps": 12}, run, None,
                            self.root / "media", "", "0.9.0")
        with Image.open(out) as gif:
            self.assertEqual((gif.size, gif.n_frames), ((80, 45), 6))
        self.assertLessEqual(out.stat().st_size, pictures.GIF_LIMIT)

    def test_every_releases_shots_are_made_as_they_say(self):
        kinds = {"capture", "clip", "pair", "compare"}
        for folder in sorted(pictures.SHOTS.glob("v*")):
            for path in sorted(folder.glob("*.json")):
                with self.subTest(shot=f"{folder.name}/{path.name}"):
                    spec = pictures.spec_of(path)
                    self.assertTrue(spec.get("pictures"), "a shot makes pictures")
                    for entry in spec["pictures"]:
                        self.assertEqual(len(kinds & set(entry)), 1, entry)
                        self.assertTrue((pictures.MEDIA / folder.name / entry["out"]).is_file(),
                                        f"{entry['out']} is made and committed")
                        if "clip" in entry:
                            self.assertTrue(entry["out"].endswith(".gif"))


if __name__ == "__main__":
    unittest.main()
