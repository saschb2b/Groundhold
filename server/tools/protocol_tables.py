#!/usr/bin/env python3
"""Write shared/net/README.md's byte tables from shared/net/protocol.json, so the
two cannot drift (the tables sit between the README's `protocol.json tables`
markers; everything else in the README is prose kept by hand).

  python3 server/tools/protocol_tables.py           # rewrite the tables
  python3 server/tools/protocol_tables.py --check   # fail if they are stale
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from groundhold_server import protocol          # noqa: E402
from groundhold_server.protocol import SPEC     # noqa: E402

README = ROOT / "shared" / "net" / "README.md"
BEGIN = "<!-- protocol.json tables: begin (server/tools/protocol_tables.py writes them) -->"
END = "<!-- protocol.json tables: end -->"
GROUPS = (("Connection and hub", 1, 29), ("Loading", 30, 39), ("In a match", 40, 99))
DIRECTIONS = {"c2s": "C→S", "s2c": "S→C", "both": "both"}


def field_text(field):
    if field.kind in protocol.SCALARS:
        return f"{field.kind} {field.name}"
    if field.size is not None:
        return f"{field.size} bytes {field.name}"
    if field.kind == "s8":
        return f"u8 + UTF-8 {field.name} (≤ {field.most} bytes)"
    if field.kind == "d16":
        return f"u16 + bytes {field.name} (≤ {field.most})"
    inner = ", ".join(field_text(sub) for sub in field.fields)
    return f"u8 n, then n × {field.name} [{inner}] (n ≤ {field.most})"


def payload(message):
    text = ", ".join(field_text(field) for field in message.fields) or "nothing"
    if message.switch:
        key, by_name, _ = message.switch
        cases = "; ".join(f"{name} ({wire}): " + (", ".join(field_text(f) for f in fields) or "nothing")
                          for name, (wire, fields) in by_name.items())
        text += f"; then by {key}: {cases}"
    return text


def size_text(message):
    least, most = message.sizes()
    return str(least) if least == most else f"{least} to {most}"


def ranges(args):
    def one(low, high):
        if low == high:
            return str(low)
        return f"{low} to {high}"
    return [one(*pair) for pair in args]


def enum_row(name):
    values = SPEC[name]
    return f"| `{name}` | " + ", ".join(f"{key} {value}" for key, value in values.items()) + " |"


def tables():
    lines = [BEGIN, ""]
    for title, low, high in GROUPS:
        lines += [f"#### {title}", "",
                  "| Id | Message | Dir | Bucket | Bytes | Payload after the type byte |",
                  "|---|---|---|---|---|---|"]
        for message in sorted(protocol.MESSAGES.values(), key=lambda m: m.id):
            if low <= message.id <= high:
                lines.append(f"| {message.id} | `{message.name}` | {DIRECTIONS[message.dir]} | "
                             f"{message.bucket or ''} | {size_text(message)} | {payload(message)} |")
        lines.append("")
    lines += ["#### Commands (`CMD.type`; seat 0 to 3 in `TURN`)", "",
              "| Type | Command | a | b | c |", "|---|---|---|---|---|"]
    for name, spec in SPEC["commands"].items():
        lines.append(f"| {spec['type']} | `{name}` | " + " | ".join(ranges(spec["args"])) + " |")
    lines += ["", "#### System commands (seat 255 in `TURN`; a game never sends them)", "",
              "| Type | Command | a | b | c |", "|---|---|---|---|---|"]
    for name, spec in SPEC["system_commands"].items():
        lines.append(f"| {spec['type']} | `{name}` | " + " | ".join(ranges(spec["args"])) + " |")
    lines += ["", "#### Numbered values", "", "| Key | Values |", "|---|---|"]
    for name in ("errors", "notices", "outcomes", "end_reasons", "load_states", "member_states", "party_phases",
                 "party_ops", "queue_ops", "queue_states", "hello_flags", "welcome_flags", "seat_flags",
                 "hash_flags", "link_flags", "party_flags", "maps", "builders"):
        lines.append(enum_row(name))
    modes = ", ".join(f"{name} {spec['id']} ({spec['teams']} team{'s' if spec['teams'] > 1 else ''}, "
                      f"{spec['seats'][0]} to {spec['seats'][1]} seats)" for name, spec in SPEC["modes"].items())
    lines += [f"| `modes` | {modes} |", "", END]
    return "\n".join(lines)


def current(text):
    start, stop = text.index(BEGIN), text.index(END) + len(END)
    return text[:start] + tables() + text[stop:]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = README.read_text(encoding="utf-8")
    fresh = current(text)
    if args.check:
        print("stale" if fresh != text else "current")
        return 1 if fresh != text else 0
    README.write_text(fresh, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
