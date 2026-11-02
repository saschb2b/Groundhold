"""The application icon in packaging/icons/ (tools/release/app_icon.py): every size a system asks for,
the .ico and the .icns holding PNG pictures of the sizes they name, read with the standard library;
and, where Pillow is installed, every file is what the brand's painter makes, its 256 px the window
icon (ui/brand/icon.png) pixel for pixel.

    python3 -m unittest discover -s tools/release -t tools/release
"""

import io
from pathlib import Path
import struct
import tempfile
import unittest

import app_icon

ROOT = Path(__file__).resolve().parents[2]
try:
    from PIL import Image
except ImportError:  # (the painter needs Pillow; the release does not)
    Image = None


def png_size(data: bytes) -> tuple[int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("not a PNG")
    return struct.unpack(">II", data[16:24])


class CommittedIconsTest(unittest.TestCase):
    def test_every_hicolor_size(self):
        for n in app_icon.PNG_SIZES:
            self.assertEqual(png_size((app_icon.OUT / f"{n}.png").read_bytes()), (n, n), n)
        self.assertEqual(sorted(p.name for p in app_icon.OUT.iterdir()),
                         sorted([f"{n}.png" for n in app_icon.PNG_SIZES] + [app_icon.ICO, app_icon.ICNS_NAME,
                                                                             app_icon.SIDE]))

    def test_the_installers_side_picture_is_what_nsis_draws(self):
        # (NSIS's Modern UI: a 164 x 314 BMP; BITMAPFILEHEADER, then BITMAPINFOHEADER's width, height, bits)
        data = (app_icon.OUT / app_icon.SIDE).read_bytes()
        self.assertEqual(data[:2], b"BM")
        width, height = struct.unpack("<ii", data[18:26])
        self.assertEqual((width, abs(height)), app_icon.SIDE_SIZE)
        self.assertEqual(struct.unpack("<H", data[28:30])[0], 24, "24 bits a pixel")

    def test_the_ico_holds_16_to_256_px_as_png(self):
        data = (app_icon.OUT / app_icon.ICO).read_bytes()
        self.assertEqual(struct.unpack("<HH", data[:4]), (0, 1), "an icon, not a cursor")
        pictures = app_icon.pictures(data)
        self.assertEqual([int(n) for n, _ in pictures], list(app_icon.ICO_SIZES))
        for n, picture in pictures:
            self.assertEqual(png_size(picture), (int(n), int(n)))
        self.assertIn(256, app_icon.ICO_SIZES, "Explorer's large icons and Alt-Tab")

    def test_the_icns_holds_16_to_1024_px_as_png(self):
        data = (app_icon.OUT / app_icon.ICNS_NAME).read_bytes()
        self.assertEqual(data[:4], b"icns")
        self.assertEqual(struct.unpack(">I", data[4:8])[0], len(data))
        pictures = app_icon.pictures(data)
        self.assertEqual([kind for kind, _ in pictures], [kind for kind, _ in app_icon.ICNS])
        for (kind, picture), (_, n) in zip(pictures, app_icon.ICNS):
            self.assertEqual(png_size(picture), (n, n), kind)
        self.assertIn(("ic10", 1024), app_icon.ICNS, "the Retina 512 pt, from a 1024 px canvas")

    def test_the_writers_round_trip(self):
        pngs = {n: f"png{n}".encode() for n in app_icon.sizes()}
        self.assertEqual(app_icon.pictures(app_icon.ico(pngs)), [(str(n), f"png{n}".encode()) for n in app_icon.ICO_SIZES])
        self.assertEqual(app_icon.pictures(app_icon.icns(pngs)), [(k, f"png{n}".encode()) for k, n in app_icon.ICNS])

    def test_godot_imports_none_of_them(self):
        # (the export presets read the .ico and .icns from disk; test_workflows.py holds them to it)
        self.assertTrue((ROOT / "packaging" / ".gdignore").exists())


@unittest.skipIf(Image is None, "needs Pillow")
class PaintedIconsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.images = app_icon.paint()
        cls.made = app_icon.files(cls.images)

    def test_the_committed_icons_are_what_the_brand_paints(self):
        self.assertEqual(app_icon.differences(app_icon.OUT, self.made), [],
                         "run python3 tools/release/app_icon.py after the brand changes")

    def test_256_px_is_the_window_icon(self):
        mine = Image.open(io.BytesIO(self.made["256.png"])).convert("RGBA")
        brand = Image.open(ROOT / "ui" / "brand" / "icon.png").convert("RGBA")
        self.assertEqual(mine.tobytes(), brand.tobytes())
        project = (ROOT / "project.godot").read_text(encoding="utf-8")
        self.assertIn('config/icon="res://ui/brand/icon.png"', project)

    def test_the_small_sizes_are_the_favicons_cut(self):
        # (the (2, 3) knot, not the emblem's (3, 4) one scaled down: the pictures differ by far more
        # than a filter would make them)
        def apart(a, b):
            a, b = a.convert("RGBA").tobytes(), b.convert("RGBA").tobytes()
            return sum(abs(x - y) for x, y in zip(a, b)) / len(a)

        emblem = self.images[1024]
        for n in (16, 24, 32):
            self.assertGreater(apart(self.images[n], emblem.resize((n, n), Image.LANCZOS)), 12, n)
        self.assertLess(apart(self.images[64], emblem.resize((64, 64), Image.LANCZOS)), 2)

    def test_check_finds_a_changed_file(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            app_icon.write(out, self.made)
            self.assertEqual(app_icon.differences(out, self.made), [])
            Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(out / "64.png")
            (out / app_icon.ICO).unlink()
            self.assertEqual(app_icon.differences(out, self.made), ["64.png differs", f"{app_icon.ICO} is missing"])


if __name__ == "__main__":
    unittest.main()
