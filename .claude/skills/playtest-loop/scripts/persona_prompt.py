#!/usr/bin/env python3
"""persona_prompt.py N GOALS [--last FILE] [--notes FILE] [--name NAME] [--persona ID]

The persona's prompt for session N: persona.md below its line, with {{PERSONA}} taken from
personas/ID.md below its line (ID: --persona, else NAME), {{ORDINAL}}, {{N}}, {{N-1}} and
{{NAME}} filled in, and the {{...}} blocks from files: GOALS always; for a later session LAST
(the last session in two sentences) and NOTES (the patch notes), which a first session has
none of (its part of persona.md says so, and the developers start it with --fresh). The game
guide (<!-- guide --> to <!-- end guide -->) stays for every persona but one whose file says
<!-- guide: none --> above its line, which gets the <!-- no guide --> part instead. Prints the
prompt; fails where a placeholder is left. It also writes .build/play/NAME/launched, from which
the watchdog counts the session's calls. NAME is the play session's name (default halv; the
personas are halv, ysr, teo and noa, and halv2, ... run more instances of one persona beside it,
with --persona halv).
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SKILL)))
DEFAULT_NAME = "halv"
FIRST, LATER, END = "<!-- first session -->", "<!-- later sessions -->", "<!-- end -->"
GUIDE = ("<!-- guide -->", "<!-- end guide -->")
NO_GUIDE = ("<!-- no guide -->", "<!-- end no guide -->")
GUIDE_NONE = "<!-- guide: none -->"


def ordinal(n):
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def below_line(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if "\n---\n" not in text:
        sys.exit(f"{path} has no line (---) above its prompt part")
    return text.split("\n---\n", 1)[1].strip()


def fill(body, key, text):
    """Replaces the one {{KEY: ...}} block of persona.md with text."""
    body, count = re.subn(r"\{\{" + re.escape(key) + r":[^}]*\}\}", lambda _m: text, body)
    if count != 1:
        sys.exit(f"persona.md has {count} {{{{{key}: ...}}}} blocks, not one")
    return body


def session_part(body, first):
    """Keeps the first session's part of persona.md or the later sessions' part."""
    try:
        head, rest = body.split(FIRST, 1)
        first_part, rest = rest.split(LATER, 1)
        later_part, tail = rest.split(END, 1)
    except ValueError:
        sys.exit(f"persona.md needs {FIRST}, {LATER} and {END}, in that order")
    return head + (first_part if first else later_part).strip("\n") + "\n\n" + tail.lstrip("\n")


def above_line(path):
    with open(path, encoding="utf-8") as f:
        return f.read().split("\n---\n", 1)[0]


def keep_part(body, marks, keep):
    """Keeps the one part of persona.md between marks (without them), or drops it."""
    start, end = marks
    if body.count(start) != 1 or body.count(end) != 1 or body.index(start) > body.index(end):
        sys.exit(f"persona.md needs one {start} ... {end}")
    head, rest = body.split(start, 1)
    part, tail = rest.split(end, 1)
    return head + (part.strip("\n") + "\n\n" if keep else "") + tail.lstrip("\n")


def read(path, what):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read().strip()
    except OSError as e:
        sys.exit(f"{what}: {e}")
    if not text:
        sys.exit(f"{what} ({path}) is empty")
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("n", type=int, help="the session's number, 1 for the persona's first")
    parser.add_argument("goals", help="a file: what to play, what to check, what to judge")
    parser.add_argument("--last", help="a file: the last session in two sentences (sessions 2 on)")
    parser.add_argument("--notes", help="a file: the patch notes since the last session (sessions 2 on)")
    parser.add_argument("--name", default=DEFAULT_NAME, help="the play session's name (default halv)")
    parser.add_argument("--persona", help="who plays: personas/PERSONA.md (default: NAME's)")
    args = parser.parse_args()
    if args.n < 1:
        sys.exit("N counts from 1")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", args.name):
        sys.exit("NAME is a lower-case session name: halv, halv2, ...")
    first = args.n == 1
    if first and (args.last or args.notes):
        sys.exit("a first session has no last session and no patch notes")
    if not first and not (args.last and args.notes):
        sys.exit("sessions from 2 on need --last and --notes")
    persona_id = args.persona or args.name
    persona_file = os.path.join(SKILL, "personas", persona_id + ".md")
    if not os.path.exists(persona_file):
        known = sorted(f[:-3] for f in os.listdir(os.path.join(SKILL, "personas")) if f.endswith(".md"))
        sys.exit(f"no persona {persona_id} in personas/ ({', '.join(known)}): pass --persona")

    body = session_part(below_line(os.path.join(SKILL, "persona.md")), first)
    guided = GUIDE_NONE not in above_line(persona_file)
    body = keep_part(keep_part(body, GUIDE, guided), NO_GUIDE, not guided)
    if body.count("{{PERSONA}}") != 1:
        sys.exit("persona.md needs one {{PERSONA}}")
    body = body.replace("{{PERSONA}}", below_line(persona_file))
    body = (body.replace("{{ORDINAL}}", ordinal(args.n)).replace("{{N-1}}", str(args.n - 1))
            .replace("{{N}}", str(args.n)).replace("{{NAME}}", args.name))
    body = fill(body, "GOALS", read(args.goals, "GOALS"))
    if not first:
        body = fill(body, "LAST SESSION", read(args.last, "--last"))
        body = fill(body, "PATCH NOTES", read(args.notes, "--notes"))
    left = re.findall(r"\{\{[^}]*\}\}", body)
    if left:
        sys.exit(f"left unfilled: {left}")
    # (the launch, for the watchdog: calls of this session's restarts count from here)
    home = os.path.join(ROOT, ".build", "play", args.name)
    os.makedirs(home, exist_ok=True)
    with open(os.path.join(home, "launched"), "w", encoding="utf-8") as f:
        f.write(f"session {args.n}\n")
    print(body.strip())


if __name__ == "__main__":
    main()
