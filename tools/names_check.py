#!/usr/bin/env python3
"""Fail on the game's retired names anywhere in the tracked tree.

The game is Groundhold (docs/design/world.md, "Rename map"). Its old title, site,
server package, protocol id, URL path, boss, Builder epithet, test player, mode names
and the Duel's old words are retired; this check prints every tracked path, and every
line of a tracked text file, that still carries one, as path:line, and exits 1.
Binary files' contents (models, images, sounds, the transcripts' .bin) are skipped,
their paths are not. A few places name the old words on purpose and are allowed
below; keep that list small and say why each entry is there. Before it looks at the
tree the check proves its own patterns on SAMPLES and exits 2 if one is wrong.

    python3 tools/names_check.py              # the working tree's tracked files
    python3 tools/names_check.py --rev main   # the tree of a commit instead

Python 3.11 or newer, standard library only.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (pattern, what replaced it), one or more per row of world.md's Rename map.
# Case-insensitive; spaces, '.', '-' and '_' are interchangeable where an id spells the
# same name. A word that must not run into a longer one is fenced with (?<![a-z]) and
# (?![a-z]) rather than \b, because '_' is a word character: vigil_first and
# hessel_bramble are caught, vigilant is not. (?-i:...) marks a case-sensitive part; a
# case-sensitive fence lets the capital that starts the next word of a CamelCase id
# count as a boundary (VigilMode, vigilRules).
RETIRED = [
    (r"lantern[ ._-]?hollow", "the game is Groundhold; the map is Wickhollow"),
    (r"lantern\.saschb2b", "the site is groundhold.saschb2b.com"),
    (r"lantern[ ._-]?server", "the server package is groundhold_server (GROUNDHOLD_SERVER_*)"),
    # the old WebSocket path; data/hollow.txt and palettes/hollow.gpl keep their names,
    # and a full stop that ends a sentence is not an extension
    (r"/hollow(?!\w|\.\w)", "the WebSocket path is /causeway"),
    (r"(?:(?<![a-z])vigil|(?-i:(?<=[a-z])Vigil))(?:s|\d+)?(?-i:(?![a-z]))",
     "the co-op mode is High Water (high_water)"),
    (r"lantern[ ._-]?race", "the race mode is Tide Race (tide_race)"),
    (r"rift[ _-]?duel", "the duel mode is Undertow (undertow)"),
    (r"rift[ _-]?offer", "the Duel's offer is the Drift"),
    (r"(?<![a-z])rous(?:e[sd]?|ings?)(?![a-z])", "a send is corked (CORK, NO_CORKS_LEFT)"),
    # 'loose' stays an English word ("a loose dome"); only the command and its ids are retired
    (r"(?-i:(?<![A-Za-z])LOOSE(?![A-Za-z]))|(?<![a-z])loose_|_loose(?![a-z])",
     "a send is uncorked (UNCORK)"),
    # the refusal's id only: a turn is still sealed, and "nothing sealed" is plain English
    (r"nothing_sealed", "the refusal is NOTHING_CORKED"),
    (r"sealed[ _-]?lanterns?", "a send waits as a corked bottle"),
    (r"last[ _-]?light", "the Duel's comeback is the Seawall (SEAWALL)"),
    # Last Light's command ids, case-sensitive: the art scripts' English 'flare' ("a
    # flared rim", "flaring out") and gourdling.py's FLARE_R stay
    (r"(?-i:(?<![A-Za-z])FLARE(?![A-Za-z_])|FLARING)",
     "the Duel's comeback is SEAWALL (SEAWALL_STANDING)"),
    (r"long[ _-]?night", "the Duel's late waves are the Surge"),
    (r"nightfall", "the Duel's end is Spring Tide"),
    # only models/props/rift_gate.glb(.import) and art_src/models/rift_gate.json keep the
    # name; any other spelling (RiftGate, riftgate, rift_gate_light) is retired
    (r"rift(?:[ -]?gate|_gate(?!\.(?:glb|json)))",
     "a map's road starts at the Welling (Wickhollow's: the sunken field gate)"),
    (r"hollow[ _-]?king", "the boss is the Hollowtide Crest (hollowtide_crest)"),
    (r"owl[ _-]?watch", "Edda Greyplume is the Lookout (lookout)"),
    (r"(?<![a-z])hessel(?![a-z])", "the Beekeeper is Sefa Amberwell"),
    # the old Beekeeper's name only: a bramble is still a plant any map may grow
    (r"hessel[ _-]?bramble|bramble,? the beekeeper", "the Beekeeper is Sefa Amberwell"),
    (r"(?<![a-z])skeps?(?![a-z])", "the Beekeeper's hive is the Clay Hive"),
]
PATTERNS = [(re.compile(p, re.IGNORECASE), hint) for p, hint in RETIRED]

# The patterns' own test, run before every check: each retired sample must be caught,
# and no kept sample may be.
SAMPLES = {
    "retired": [
        "Lantern Hollow TD", "lantern-hollow.v1", "lantern.saschb2b.com", "lantern.server",
        "LANTERN_SERVER_PORT", "server/lantern_server/app.py", "ws://127.0.0.1:8766/hollow",
        "it listens at /hollow.", "Vigil", "Vigils", "vigil12", "vigil_first",
        "bot_wins_vigil_2p", "VigilMode", "vigilRules", "coopVigil", "Lantern Race",
        "Rift Duel", "the Rift Offer", "rift_offer.gd", "ROUSE", "CMD_ROUSE",
        "rouse_commit_hides_pack", "a roused creep", "NO_ROUSINGS_LEFT", "LOOSE(pack, salt)",
        "CMD_LOOSE", "loose_t", "fizzle_after_loose", "NOTHING_SEALED", "a sealed lantern",
        "sealed-lantern", "Last Light", "last_light_charges_every_four", "CMD_FLARE",
        '"FLARE"', "COMMAND[\"FLARE\"]", "| 8 | `FLARE` |", "ALREADY_FLARING",
        "REFUSE_ALREADY_FLARING", "the Long Night", "long_night_freezes", "Nightfall",
        "the rift gate", "rift-gate", "RiftGate", 'gate.name = "RiftGate"', "riftgate",
        "rift_gate_light", "var rift_gate := 1", "Hollow King", "hollow_king.glb", "Owlwatch",
        "owlwatch.json", "Hessel", "hessel_bramble", "Hessel Bramble", "HesselBramble",
        "Bramble the Beekeeper", "her Skep", "skep_tower",
    ],
    "kept": [
        "Groundhold", "Wickhollow", "Hollowtide", "data/hollow.txt", "palettes/hollow.gpl",
        "res://data/hollow.txt", "scripts/hollow_map.gd", "models/props/rift_gate.glb",
        "models/props/rift_gate.glb.import", "res://.godot/imported/rift_gate.glb-31eb040e.scn",
        "art_src/models/rift_gate.json", "the Hollowtide Crest", "a loose dome",
        "cork it, and loose it at a rival's shore", "vigilant", "Vigilance", "invigilate",
        "a carousel", "arousing", "the sunken field gate", "hearth.glb", "Lamplighter",
        "lantern", "the lands fell out of step", "SEAWALL", "SEAWALL_STANDING", "NO_CORKS_LEFT",
        "NOTHING_CORKED", "nothing sealed after TIMEOUT", "FLARE_R = 0.052", "[FLARE_R, 0.032]",
        "a flared rim", "a stem flaring out of", "flare = 1 + 0.1 * impact(lag2)",
        "a Holdfast flare", "the Drift", "a bramble hedge", "Brambles line the lane",
    ],
}


def _after_first_release(lines):
    """CHANGELOG.md: the released history, from the first release's heading on (the
    Unreleased section above it is checked)."""
    allowed, released = set(), False
    for number, line in enumerate(lines, 1):
        released = released or (line.startswith("## ") and line.strip() != "## Unreleased")
        if released:
            allowed.add(number)
    return allowed


def _world_rename_record(lines):
    """docs/design/world.md, only where it records what was renamed: the rows of its
    three name tables (Names, The v1 Builders, Rename map), the paragraphs on why Sefa
    replaces the old Beekeeper and on what the autumn map keeps, the section on the
    changes that follow from the umbrella, and the rename-order item of "Still to
    check". The pitch, the premise, the vetting and the other open checks are checked."""
    tables = ("**Names**", "**The v1 Builders**", "**Rename map**")
    paragraphs = ("Sefa replaces ", "**The autumn hollow as one map.**")
    allowed, block, paragraph, section, item = set(), "", False, "", False
    for number, line in enumerate(lines, 1):
        if line.startswith("## "):
            section, block, item = line, "", False
        elif line.startswith("**"):
            block = line
        paragraph = (paragraph and line.strip() != "") or line.startswith(paragraphs)
        if line.startswith("- "):
            item = line.startswith("- **Rename in a fixed order")
        if (
            (line.startswith("|") and block.startswith(tables))
            or paragraph
            or section.startswith("## Changes that follow from the umbrella")
            or (section.startswith("## Still to check") and item)
        ):
            allowed.add(number)
    return allowed


def _whole_file(lines):
    return set(range(1, len(lines) + 1))


ALLOWED = {
    # The released history keeps the names the game shipped with.
    "CHANGELOG.md": _after_first_release,
    # The rename's own record.
    "docs/design/world.md": _world_rename_record,
    # This check spells the retired names it looks for.
    "tools/names_check.py": _whole_file,
}


def _git(*args, data=None):
    return subprocess.run(["git", *args], cwd=ROOT, input=data, capture_output=True, check=True).stdout


def tracked_files(rev=None):
    """{path: bytes} of every tracked file, from the working tree or from commit `rev`."""
    if rev is None:
        files = {}
        for name in _git("ls-files", "-z").decode().split("\0"):
            path = ROOT / name
            if name and path.is_file():
                files[name] = path.read_bytes()
        return files
    names = [n for n in _git("ls-tree", "-r", "-z", "--name-only", rev).decode().split("\0") if n]
    out = _git("cat-file", "--batch", data="".join(f"{rev}:{n}\n" for n in names).encode())
    files, offset = {}, 0
    for name in names:
        header_end = out.index(b"\n", offset)
        size = int(out[offset:header_end].split()[2])
        files[name] = out[header_end + 1:header_end + 1 + size]
        offset = header_end + 1 + size + 1
    return files


def text_of(data):
    """The file as text, or None for a binary file."""
    if b"\0" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def self_test():
    """The samples each pattern list gets wrong: retired ones it misses, kept ones it flags."""
    wrong = [f"missed retired sample {s!r}" for s in SAMPLES["retired"]
             if not any(p.search(s) for p, _ in PATTERNS)]
    wrong += [f"flagged kept sample {s!r} ({m.group(0)!r})" for s in SAMPLES["kept"]
              for p, _ in PATTERNS for m in [p.search(s)] if m]
    return wrong


def findings(files):
    found = []
    for name in sorted(files):
        for pattern, hint in PATTERNS:
            match = pattern.search(name)
            if match:
                found.append(f"{name}: retired name '{match.group(0)}' in the path: {hint}")
        text = text_of(files[name])
        if text is None:
            continue
        lines = text.splitlines()
        allowed = ALLOWED[name](lines) if name in ALLOWED else set()
        for number, line in enumerate(lines, 1):
            if number in allowed:
                continue
            for pattern, hint in PATTERNS:
                match = pattern.search(line)
                if match:
                    found.append(f"{name}:{number}: retired name '{match.group(0)}': {hint}")
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--rev", help="check the tree of this commit instead of the working tree")
    args = parser.parse_args(argv)
    wrong = self_test()
    for line in wrong:
        print(f"names check: the patterns {line}")
    if wrong:
        return 2
    files = tracked_files(args.rev)
    found = findings(files)
    for line in found:
        print(line)
    where = args.rev or "the working tree"
    if found:
        print(f"names check: {len(found)} retired names in {where} ({len(files)} tracked files)")
        return 1
    print(f"names check: clean · {len(files)} tracked files in {where}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
