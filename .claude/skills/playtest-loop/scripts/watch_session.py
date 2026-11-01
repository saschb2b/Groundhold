#!/usr/bin/env python3
"""watch_session.py NAME [--budget N] [--alert]: how a playtest session is going, from the
kit's session files in .build/play/NAME (`godot-agent play`): the calls so far against the
budget, the frame, what the screen shows now (the state's screen and phase lines), the pace
(frames and pictures a call over the last ten), how many calls the current match has taken,
and the minutes since the persona's last note and last call. Each run adds a snapshot to
NAME/watch.log, from which the match's length is measured.

With --alert it exits 1 when something wants a look, and 0 while all is well: the call
budget spent, 20 minutes without a note while playing, no call for 10 minutes while the game
runs, the game stopped (crashed, or stopped early), under 150 frames a call over the last ten
in a match, over 10 pictures a call over the last ten, or a match past 120 calls. The loop to
run in the background while a persona plays, which ends (and so wakes you) at the first
alert, or after 15 minutes of none:

  for i in 1 2 3; do sleep 300; python3 .claude/skills/playtest-loop/scripts/watch_session.py halv --alert || break; done

(and start it again after looking). Never `until ... --alert`: that ends at once while all is
well and sleeps on through every alert."""
import glob
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
BUDGET = 220
SLOW_FRAMES = 150
MANY_PICTURES = 10
LONG_MATCH = 120


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def alive(home):
    """Whether the session's game runs (the kit's pid file: "godot PID" and "xvfb PID")."""
    words = read(os.path.join(home, "pid")).split()
    if "godot" not in words:
        return False
    try:
        pid = int(words[words.index("godot") + 1])
        os.kill(pid, 0)
    except (ValueError, IndexError, OSError):
        return False
    stat = read(f"/proc/{pid}/stat")
    return not (") " in stat and stat.split(") ", 1)[1].startswith("Z"))


def batches(home):
    """history.txt's batches: (end frame, pictures) each."""
    out = []
    for line in read(os.path.join(home, "history.txt")).splitlines():
        if line.startswith("#") or "  # frame " not in line:
            continue
        frame = int(re.search(r"  # frame (\d+)", line).group(1))
        pictures = re.search(r"  # pictures (\d+)", line)
        out.append((frame, int(pictures.group(1)) if pictures else 1))
    return out


def earlier_calls(home):
    """Calls of this session's earlier starts (a restart keeps the last start's history as
    history-N.txt): those written since the launch (NAME/launched, which persona_prompt.py
    writes as it prints the prompt)."""
    launched = os.path.join(home, "launched")
    if not os.path.exists(launched):
        return 0
    since = os.path.getmtime(launched)
    count = 0
    for path in glob.glob(os.path.join(home, "history-*.txt")):
        if os.path.getmtime(path) >= since:
            count += sum(1 for l in read(path).splitlines() if "  # frame " in l and not l.startswith("#"))
    return count


def match_wave(phase, screen):
    """The wave a match stands on, from the state's phase line ("Wave 6/12 ...", "Surge 2/3 ..."
    after the twelfth): -1 off a match."""
    if not screen.startswith("match"):
        return -1
    m = re.match(r"(Wave|Surge) (\d+)", phase)
    if not m:
        return 0
    return int(m.group(2)) + (100 if m.group(1) == "Surge" else 0)


def main():
    args = sys.argv[1:]
    if not args or args[0].startswith("-"):
        sys.exit(__doc__)
    name, budget, alert = args[0], BUDGET, "--alert" in args
    if "--budget" in args:
        budget = int(args[args.index("--budget") + 1])
    home = os.path.join(ROOT, ".build", "play", name)
    if not os.path.isdir(home):
        sys.exit(f"no session {name} in {os.path.dirname(home)}")
    now = time.time()
    done = batches(home)
    calls = len(done) + earlier_calls(home)
    frame = done[-1][0] if done else 0
    state = read(os.path.join(home, "state.txt")).splitlines()
    screen = next((l[len("screen: "):] for l in state if l.startswith("screen: ")), "?")
    phase = next((l for l in state if l.startswith(("Wave ", "Surge ", "before wave"))), "")
    kind = (screen.split(" · ")[0].split() or ["?"])[0]
    running = alive(home)
    history = os.path.join(home, "history.txt")
    call_age = (now - os.path.getmtime(history)) / 60 if os.path.exists(history) else 0
    notes = sorted(glob.glob(os.path.join(home, "notes-s*.md")), key=os.path.getmtime)
    launched = os.path.join(home, "launched")
    note_age = 0.0
    if notes:
        note_age = (now - os.path.getmtime(notes[-1])) / 60
    elif os.path.exists(launched):
        note_age = (now - os.path.getmtime(launched)) / 60

    # The snapshot, and the current match's first snapshot among the earlier ones. Snapshots
    # five minutes apart can miss a results screen between two matches, so a match also ends
    # where the mode changes (the screen line) or the wave goes back (a new match of one mode).
    log = os.path.join(home, "watch.log")
    wave = match_wave(phase, screen)
    where = screen.replace(" ", "_")
    snaps = []
    for line in read(log).splitlines():
        p = line.split()
        try:
            snaps.append((float(p[0]), int(p[1]), int(p[2]), p[3],
                          int(p[4]) if len(p) > 4 else -1, p[5] if len(p) > 5 else ""))
        except (IndexError, ValueError):
            continue
    snaps.append((now, calls, frame, kind, wave, where))
    with open(log, "a") as f:
        f.write(f"{now:.0f} {calls} {frame} {kind} {wave} {where}\n")
    start = None
    for s in reversed(snaps):
        if s[3] != "match" or (start and (s[5] != start[5] or (0 <= start[4] < s[4]))):
            break
        start = s

    pace = pictures = None
    if len(done) > 10:
        pace = (done[-1][0] - done[-11][0]) / 10
        pictures = sum(p for _, p in done[-10:]) / 10
    line = (f"{name}: {calls} calls (budget {budget}), frame {frame}, screen {screen}"
            + (f", {phase}" if phase else "") + (f"; {pace:.0f} frames and {pictures:.1f} pictures a call over the "
                                                  "last ten" if pace is not None else "")
            + f"; last call {call_age:.0f} min ago, last note {note_age:.0f} min ago"
            + ("" if running else "; game stopped"))
    print(line)
    want = []
    if start and kind == "match":
        n = calls - start[1]
        print(f"  this match: {n} calls, {(now - start[0]) / 60:.0f} min so far")
        if n > LONG_MATCH:
            want.append("a long match (stuck, or tiny batches?)")
    if calls > budget:
        want.append("the call budget is spent")
    if running and note_age > 20 and call_age < 5:
        want.append("no note for 20 minutes")
    if running and call_age > 10:
        want.append("no call for 10 minutes")
    if not running and call_age < 10 and done:
        errors = [l for l in read(os.path.join(home, "log")).splitlines() if l.startswith("ERROR")]
        want.append("the game stopped" + (f" ({len(errors)} engine errors in its log)" if errors else ""))
    if pace is not None and kind == "match" and pace < SLOW_FRAMES:
        want.append("a slow pace")
    if pictures is not None and pictures > MANY_PICTURES:
        want.append("many pictures a call")
    shots = sorted(glob.glob(os.path.join(home, "shots", "*.png")), key=os.path.getmtime)
    if shots:
        print(f"  latest picture: {shots[-1]}")
    if want:
        print("  look: " + ", ".join(want))
    sys.exit(1 if alert and want else 0)


if __name__ == "__main__":
    main()
