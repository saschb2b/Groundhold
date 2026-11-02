#!/usr/bin/env python3
"""A release page's pictures, from the real game (.claude/skills/release/SKILL.md): every scenario in
tools/release/shots/vX.Y.Z/ is rendered as the browser build draws it, and what its "pictures" list
asks for is cut from its captures into docs/releases/media/vX.Y.Z/, where the page shows them.

    python3 tools/release/pictures.py v0.9.0                  # every scenario of 0.9.0's, then its pictures
    python3 tools/release/pictures.py v0.9.0 stacked_waves    # only these scenarios
    python3 tools/release/pictures.py v0.9.0 --old v0.8.0     # the release before it (default: the newest
                                                              # tag below the version)
    python3 tools/release/pictures.py v0.9.0 --again          # the pictures again from the last renders,
                                                              # nothing rendered (crops, sizes, labels)

A scenario is a godot-agent scenario (tools/media's kind), run with `--renderer gl_compatibility -j 1`
into .build/release-shots/vX.Y.Z/, plus a "pictures" list; each entry names its file (`out`, under the
release's media folder: .webp or .png for a still, .gif for a clip) and where it comes from:

    {"out": "hero.webp", "capture": "hero", "width": 1280}
        one capture, cut to `crop` ([x0, y0, x1, y1] in capture pixels, the whole frame without one) and
        scaled to `width` pixels (its own width without one);
    {"out": "x.gif", "clip": "clip", "crop": [...], "width": 720, "fps": 12, "hold": 1.25}
        every capture of that label in order, a GIF by ffmpeg's palettegen and paletteuse, kept under
        GIF_LIMIT by fewer colours, then a smaller width; capture every 5 frames at one tick a frame for
        real time at 12 fps; `hold` keeps the last frame that many seconds more before it loops;
    {"out": "x.webp", "pair": ["normal", "very_hard"], "labels": ["Normal", "Very Hard"], "crop": [...]}
        two captures of this run side by side (`"layout": "stack"`: one over the other), each under its
        label;
    {"out": "compare-x.webp", "compare": "label", "crop": [...]}
        before and after: the same scenario run on the release before (a git worktree of its tag in
        .build/before/<tag>/, imported once; the scenario copied into it, with its "before" keys laid
        over it, say other steps where the old game lacks what the new one has) and on this tree, the
        old capture on the left under the old version, the new on the right under this one;
    {"out": "compare-x.webp", "compare": ["royal", {"capture": "guard", "crop": [...]}], "crop": [...]}
        several captures a version, each its own crop where it names one: each version's side by side in
        a row under its version, their bottoms level, the old row over the new.

Any entry's `crops` ([[x0, y0, x1, y1], ...]) in place of `crop` cuts each region of a capture and
stacks them, one under the other, as one picture (two rows of a long list, say).

Labels are in the game's own font and the console's colours. Needs Pillow, ffmpeg, godot and
godot-agent; Godot runs one process at a time.
"""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "tools" / "release" / "shots"
MEDIA = ROOT / "docs" / "releases" / "media"
RUNS = ROOT / ".build" / "release-shots"
BEFORE = ROOT / ".build" / "before"
FONT = ROOT / "fonts" / "NotoSerif-Bold.ttf"
# the console's colours (scripts/hud.gd): the ink behind a label, the old build's dim words, the new one's gold
INK = (18, 14, 10)
DIM = (163, 149, 125)
GOLD = (240, 207, 134)
TEXT = (236, 226, 204)
GAP = 8
GIF_LIMIT = 4 * 1024 * 1024
TAG = re.compile(r"v(\d+)\.(\d+)\.(\d+)")


class PictureError(Exception):
    """A picture that cannot be made, with why."""


def scenarios(tag: str, names: list[str]) -> list[Path]:
    folder = SHOTS / tag
    found = sorted(folder.glob("*.json"))
    if names:
        found = [path for path in found if path.stem in names]
        missing = set(names) - {path.stem for path in found}
        if missing:
            raise PictureError(f"no {', '.join(sorted(missing))} in {folder.relative_to(ROOT)}")
    if not found:
        raise PictureError(f"no scenarios in {folder.relative_to(ROOT)}")
    return found


def spec_of(path: Path) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("name") != path.stem:
        raise PictureError(f"{path.name}: its name must be {path.stem!r}, the folder its captures land in")
    return spec


def previous_tag(tag: str) -> str:
    """The newest release tag below `tag`."""
    want = tuple(int(n) for n in TAG.fullmatch(tag).groups())
    tags = subprocess.run(["git", "tag", "--list", "v*"], cwd=ROOT, check=True, capture_output=True,
                          text=True).stdout.split()
    older = sorted((tuple(int(n) for n in m.groups()), t) for t in tags if (m := TAG.fullmatch(t)) and
                   tuple(int(n) for n in m.groups()) < want)
    if not older:
        raise PictureError(f"no release before {tag} to compare with")
    return older[-1][1]


def old_tree(tag: str) -> Path:
    """A worktree of `tag` in .build/before/, made and imported the first time."""
    tree = BEFORE / tag
    if not tree.exists():
        subprocess.run(["git", "worktree", "add", "--detach", str(tree), tag], cwd=ROOT, check=True)
    if not (tree / ".godot" / "imported").is_dir():
        print(f"importing {tag}'s tree (once)")
        subprocess.run(["godot", "--headless", "--path", str(tree), "--import"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return tree


def render(project: Path, files: list[Path], out: Path) -> None:
    """The scenarios rendered as the browser build draws them, one Godot at a time, each into
    out/<name>/ (the other scenarios' renders there stay, for --again)."""
    fresh = out.parent / (out.name + ".rendering")
    if fresh.exists():
        shutil.rmtree(fresh)
    done = subprocess.run(["godot-agent", "scenario", str(project), *map(str, files), "-j", "1",
                           "--renderer", "gl_compatibility", "--timeout", "900", "--out", str(fresh)])
    summary = fresh / "summary.json"
    if done.returncode != 0 or not summary.exists() or not json.loads(summary.read_text())["passed"]:
        raise PictureError(f"a scenario failed in {project}: see {fresh}")
    out.mkdir(parents=True, exist_ok=True)
    for path in files:
        if (out / path.stem).exists():
            shutil.rmtree(out / path.stem)
        (fresh / path.stem).rename(out / path.stem)
    shutil.rmtree(fresh)


def before_files(specs: list[tuple[Path, dict]], tree: Path) -> list[Path]:
    """Each scenario with a compare, as the old tree runs it: its "before" keys laid over it, written
    into the old tree (which may not have it)."""
    folder = tree / ".build" / "release-shots"
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for path, spec in specs:
        if any("compare" in entry for entry in spec.get("pictures", [])):
            old = {key: value for key, value in spec.items() if key not in ("before", "pictures")}
            old.update(spec.get("before", {}))
            target = folder / path.name
            target.write_text(json.dumps(old, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            out.append(target)
    return out


def captures(run: Path, name: str, label: str) -> list[Path]:
    """Every capture of `label` in scenario `name`'s run, in the order taken."""
    found = sorted((run / name / "captures").glob(f"[0-9][0-9][0-9]_{label}.png"))
    if not found:
        raise PictureError(f"{name}: no capture {label!r} in {run}")
    return found


def cut(path: Path, entry: dict) -> Image.Image:
    """The capture cut to the entry's `crop`, or its `crops` stacked, one region under the other."""
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    if "crops" in entry:
        parts = [image.crop(tuple(box)) for box in entry["crops"]]
        sheet = Image.new("RGB", (max(part.width for part in parts),
                                  sum(part.height for part in parts) + GAP // 2 * (len(parts) - 1)), INK)
        y = 0
        for part in parts:
            sheet.paste(part, (0, y))
            y += part.height + GAP // 2
        return sheet
    if "crop" in entry:
        image = image.crop(tuple(entry["crop"]))
    return image


def row(images: list[Image.Image]) -> Image.Image:
    """The images side by side, GAP apart, their bottoms level (a tooltip grows up from the card), on the
    console's ink."""
    height = max(image.height for image in images)
    sheet = Image.new("RGB", (sum(image.width for image in images) + GAP * (len(images) - 1), height), INK)
    x = 0
    for image in images:
        sheet.paste(image, (x, height - image.height))
        x += image.width + GAP
    return sheet


def scaled(image: Image.Image, width: int | None) -> Image.Image:
    if not width or width == image.width:
        return image
    return image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)


def labelled(images: list[Image.Image], labels: list[str], colours: list[tuple], layout: str) -> Image.Image:
    """The images side by side (or one over the other), each under its label on the console's ink."""
    size = max(15, min(22, round(max(image.width for image in images) / 28)))
    font = ImageFont.truetype(str(FONT), size)
    bar = round(size * 1.8)
    if layout == "stack":
        width = max(image.width for image in images)
        height = sum(bar + image.height for image in images) + GAP * (len(images) - 1)
    else:
        width = sum(image.width for image in images) + GAP * (len(images) - 1)
        height = bar + max(image.height for image in images)
    sheet = Image.new("RGB", (width, height), INK)
    draw = ImageDraw.Draw(sheet)
    x = y = 0
    for image, label, colour in zip(images, labels, colours):
        draw.text((x + image.width // 2, y + bar // 2), label, fill=colour, font=font, anchor="mm")
        sheet.paste(image, (x, y + bar))
        if layout == "stack":
            y += bar + image.height + GAP
        else:
            x += image.width + GAP
    return sheet


def save(image: Image.Image, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".webp":
        image.save(out, quality=90, method=6)
    elif out.suffix == ".png":
        image.save(out, optimize=True)
    else:
        raise PictureError(f"{out.name}: a still is .webp or .png")


def gif(frames: list[Path], entry: dict, out: Path) -> None:
    """The frames as a GIF at `fps`, under GIF_LIMIT: fewer colours first, then a smaller width."""
    fps, width = int(entry.get("fps", 12)), entry.get("width")
    frames = list(frames) + [frames[-1]] * round(float(entry.get("hold", 0)) * fps)
    for colours, shrink in ((256, 1.0), (160, 1.0), (128, 0.9), (96, 0.8), (64, 0.7)):
        with tempfile.TemporaryDirectory() as temp:
            for i, path in enumerate(frames):
                image = scaled(cut(path, entry), round(width * shrink) if width else None)
                image.save(Path(temp) / f"f{i:04d}.png")
            graph = (f"split[a][b];[a]palettegen=max_colors={colours}:stats_mode=diff[p];"
                     "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-i", str(Path(temp) / "f%04d.png"),
                            "-filter_complex", graph, "-loop", "0", str(out)], check=True)
        if out.stat().st_size <= GIF_LIMIT:
            return
        print(f"  {out.name}: {out.stat().st_size // 1024} KB at {colours} colours, width x{shrink}: smaller")
    raise PictureError(f"{out.name} stays over {GIF_LIMIT // (1024 * 1024)} MB: fewer frames or a tighter crop")


def make(spec: dict, entry: dict, new_run: Path, old_run: Path | None, folder: Path, old: str, new: str) -> Path:
    name, out = spec["name"], folder / entry["out"]
    out.parent.mkdir(parents=True, exist_ok=True)
    if "clip" in entry:
        if out.suffix != ".gif":
            raise PictureError(f"{out.name}: a clip is a .gif")
        gif(captures(new_run, name, entry["clip"]), entry, out)
    elif "capture" in entry:
        save(scaled(cut(captures(new_run, name, entry["capture"])[-1], entry), entry.get("width")), out)
    elif "pair" in entry:
        images = [scaled(cut(captures(new_run, name, label)[-1], entry), entry.get("each")) for label in entry["pair"]]
        save(scaled(labelled(images, entry["labels"], [TEXT] * len(images), entry.get("layout", "side")),
                    entry.get("width")), out)
    elif "compare" in entry:
        if old_run is None:
            raise PictureError(f"{name}: a compare needs the old build's run")
        items = entry["compare"] if isinstance(entry["compare"], list) else [entry["compare"]]
        items = [item if isinstance(item, dict) else {"capture": item} for item in items]
        images = [row([scaled(cut(captures(run, name, item["capture"])[-1], {**entry, **item}), entry.get("each"))
                       for item in items]) for run in (old_run, new_run)]
        layout = "stack" if len(items) > 1 else entry.get("layout", "side")
        save(scaled(labelled(images, [old, new], [DIM, GOLD], layout), entry.get("width")), out)
    else:
        raise PictureError(f"{name}: {entry['out']} names no capture, clip, pair or compare")
    with Image.open(out) as image:
        width, height = image.size
    shown = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    print(f"{shown}  {width} x {height}  {out.stat().st_size // 1024} KB")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("tag", help="the release, vX.Y.Z")
    parser.add_argument("names", nargs="*", help="only these scenarios (default: all of the release's)")
    parser.add_argument("--old", help="the release to compare with (default: the newest tag below)")
    parser.add_argument("--again", action="store_true", help="remake the pictures from the last renders")
    args = parser.parse_args(argv)
    try:
        if not TAG.fullmatch(args.tag):
            raise PictureError(f"{args.tag!r} is not vX.Y.Z")
        files = scenarios(args.tag, args.names)
        specs = [(path, spec_of(path)) for path in files]
        compares = any("compare" in entry for _, spec in specs for entry in spec.get("pictures", []))
        old = args.old or (previous_tag(args.tag) if compares else "")
        new_run, old_run = RUNS / args.tag / "new", RUNS / args.tag / f"old-{old}" if old else None
        if not args.again:
            render(ROOT, files, new_run)
            if compares:
                tree = old_tree(old)
                render(tree, before_files(specs, tree), old_run)
        folder = MEDIA / args.tag
        for _, spec in specs:
            for entry in spec.get("pictures", []):
                make(spec, entry, new_run, old_run, folder, old.lstrip("v"), args.tag.lstrip("v"))
        made = {entry["out"] for path in scenarios(args.tag, []) for entry in spec_of(path).get("pictures", [])}
        for path in sorted(folder.iterdir()):
            if path.name not in made:
                print(f"warning: no scenario makes {path.relative_to(ROOT)}: list it in one or delete it")
    except (PictureError, subprocess.CalledProcessError) as exc:
        print(f"pictures: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
