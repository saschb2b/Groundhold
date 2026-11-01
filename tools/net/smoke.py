#!/usr/bin/env python3
"""A whole networked match end to end (design §7.1 level 4, §8 M1 track E).

Starts the real server (server/main.py --dev-match MODE:CLIENTS --port 0) and
CLIENTS headless games of this project that join it, each played by the plan
bot:

    godot --headless --path . -- --join=127.0.0.1:PORT --bot --quit-after-match
          --hash-log=<out>/clientK.hashes --name=SmokeK

and checks that every client finished the match the server agreed on
(MATCH_END won/lost/draw, reason "result"), that each printed the same RESULT
line, and that their HASH streams (tick and state hash every 60 ticks) are
equal at every tick they share and cover the match to its last minute.

    python3 tools/net/smoke.py --mode classic --clients 2
    python3 tools/net/smoke.py --clients 2 --turn-ms 10      # five times faster, for CI

--mode is any mode of shared/net/protocol.json. A two-team mode (Tide Race, M6) takes an
even number of clients within its seats, half on each team (a dev match's team is
seat × teams div seats: a 1v1 is seat 1 against seat 2), and its check is the race's:
every client's RESULT names the same final tick and hash, the clients of one team end
with one outcome, and the two teams' outcomes answer each other (won and lost, or both
draw). It plays only where the build has the mode's rules (content.gd RULES).

    python3 tools/net/smoke.py --mode tide_race --clients 2 --turn-ms 10

--mode undertow (M7) is the duel: two clients, one a side (seat 1 on team 0 against seat 2
on team 1), each played by the plan bot, checked as a race is (one RESULT tick and hash, and
won against lost or a draw for both) and as a duel: the plan bot (tests/bot.gd) builds and
forks from its seat's plan and plays the duel as the caretaker would, through the game's own
duel orders, so its CORK (the client's commitment to a salt of its own), its UNCORK (the
reveal) and its SEAWALL cross the real server. From each game's BOT lines the check is that
the simulation stood a bottle of each game's (its CORK ran) and took an uncorking of each
bot's own (its UNCORK's reveal matched), and that at least one uncorked pack walked a rival's
road; with the hash streams equal to the end, both games ran every one of those orders alike.
The Seawall rises only where creeps crowd a Holdfast, so it is counted, not required. With
--no-bot nobody corks and only the race's check is made.

    python3 tools/net/smoke.py --mode undertow --turn-ms 10      # about three minutes

With --flow it plays the whole loop around a match instead (design §8 M3): the
server runs with its hub (no --dev-match, its state in <out>/state), and each
game boots into the hub with tests/net/flow_bot.gd at the controls:

    godot --headless --path . -- --server=127.0.0.1:PORT --flow-bot --party=N
          --name=FlowK --main=BUILDER [--code-out=FILE | --code-in=FILE] ...

Client 1 makes a party and writes its code to <out>/party_code.txt; the others
join by that code. The members say Ready, the leader starts, the 3-2-1 runs,
the loading barrier opens the match (High Water, the hub's mode, with each
member's main: --builders, default lamplighter,lookout), the plan bots play
their seats and call each wave as soon as they may (--no-bot: they only call
the waves, so the Tide wins in about a minute and a half), the results show,
each presses Play again, and all are back in the party, forming. The check:
every game printed each step of that (FLOW lines) with one party code, the
match finished (won, lost or draw, by result), the HASH streams agree to the
end, and every game came back to a party of N, forming.

    python3 tools/net/smoke.py --flow                         # two games, about two minutes
    python3 tools/net/smoke.py --flow --no-bot --linger 20    # 20 s on the results first

--linger S keeps every game S seconds on the results before Play again: longer
than the server's silence_ms (15 s), the plate must keep the connection alive.

With --flow --queue (M6) the four games meet through the server's queue instead:
each makes a party of one of its own, turns open seats on and presses Find
players (--queue), the server's queue.py merges the four tickets into one High
Water match of strangers, Match Found comes to every game and each accepts, the
match forms with the strangers' Builders unclashed by the server (every main
--builders names, default all Lamplighters: the first queued keeps the main, the
next takes the backup, the rest are drawn from Server.queue_rng), it plays and
ends, and each game's Play again queues it again, as for a player who came alone
through the queue. The check: every game went party -> queued -> found -> loading
-> match -> end -> results -> back (queued again), in four parties of its own, one
found match, one MATCH_CONFIG whose four Builders are four different ones, one seat
each, the hash streams equal to the end.

    python3 tools/net/smoke.py --flow --queue --no-bot      # four games, about two minutes

--flow --queue --mode undertow (M7) finds a rival for a duel instead (--mode tide_race for a
race of one a side): two games, each a party of one in that mode (the flow bot picks it on the
hub, which offers it only where the build has the mode's rules), press Find a rival, the
server's queue pairs them, both accept, the duel plays one a side with each game's main (a
Builder clash never crosses the sides, so two Lamplighters both play the Lamplighter), ends
with one outcome a side, answering each other, and Play again queues each again. With the
plan bots (the default) the duel is checked as --mode undertow's is: each game corked and its
bot uncorked, and an uncorked pack walked a rival's road. Their --ready-calls wait in a duel
until the bot has played the window both hollows share (tests/bot.gd played_window), so a
Ready on both sides never sounds the horn before the corking.

    python3 tools/net/smoke.py --flow --queue --mode undertow             # about twelve minutes
    python3 tools/net/smoke.py --flow --queue --mode undertow --no-bot    # the waves called only

With --shaper (design §8 M4) the last client plays through tools/net/shaper.py:
150 ± 50 ms each way and, --stall-at seconds after it connects, a 3 s stall
(--stall-ms). Besides the match's end and equal hash streams, the check is that
every other client's tick rate never dropped: its HASH lines, stamped as they
appear in its log, advance at least --rate-floor (0.8) of the server's pace
over every 3 s of the match. With --faults the shaper cuts that client's link
at --cut-at seconds and refuses it for --cut-ms (8 s: its seat goes AWAY and
the caretaker builds), and the check is that it rejoined (its log says RESYNC
rejoin), caught up and ended the match with the others. --server runs another
checkout's server/main.py (the integrator's, say).

    python3 tools/net/smoke.py --shaper --turn-ms 10
    python3 tools/net/smoke.py --faults --turn-ms 10

Godot is $GODOT_PATH, else `godot` on PATH. Logs and hash streams go to --out
(default: a new folder under the system's temp directory), and the folder is
printed. Every process runs in its own process group and is stopped with it,
on success, failure, timeout or Ctrl-C. Exit code 0 when the match finished
with equal hash streams, 1 otherwise. Python 3.11+, no dependencies.
"""

import argparse
import contextlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


def missing_classes(root=ROOT):
    """The class_names the project's scripts declare that Godot's class cache does not list
    (a fresh clone, or a pull that brought a script): games started from the checkout would
    fail to parse every script that names one, so the project is imported first."""
    cache = root / ".godot" / "global_script_class_cache.cfg"
    listed = set(re.findall(r'"class": &"(\w+)"', cache.read_text(encoding="utf-8"))) if cache.exists() else set()
    declared = set()
    for folder in ("scripts", "tests", "tools"):
        for script in (root / folder).rglob("*.gd"):
            found = re.search(r"^class_name\s+(\w+)", script.read_text(encoding="utf-8", errors="replace"), re.M)
            if found:
                declared.add(found.group(1))
    return sorted(declared - listed)
READY = re.compile(r"listening.*port\D*(?P<port>\d+)")
HASH = re.compile(r"^HASH (\d+) ([0-9a-f]+)$")
RESULT = re.compile(r"^RESULT (\d+) ([0-9a-f]+) (\w+)$")
MATCH_END = re.compile(r"^MATCH_END (\w+) (\w+) (\d+)$")
MATCH = re.compile(r"^MATCH (\d+) seat (\d+) of (\d+) seed (\d+)$")
PROTOCOL = ROOT / "shared" / "net" / "protocol.json"
RESYNC = re.compile(r"^RESYNC (\w+) (\d+)$")
SHAPER_READY = re.compile(r"listening on [\d.]+:(?P<port>\d+)")
# The protocol's turn: 3 ticks in 50 ms (protocol.json turn_ms, turn_ticks).
TURN_MS, TURN_TICKS = 50, 3
# The window the tick rate is measured over (s).
RATE_WINDOW = 3.0
FINISHED = ("won", "lost", "draw")
# The Builders this build shows as themselves; any other main is fielded as a
# Lamplighter until its towers are painted (Profile.fielded).
FIELDED = ("lamplighter", "lookout")
FLOW_PARTY = re.compile(r"^FLOW party (\w+) members (\d+) me (\d+) (leader|member)$")
FLOW_MATCH = re.compile(r"^FLOW match (\w+) seat (\d+) of (\d+) builders ([\w,]+)$")
FLOW_RESULTS = re.compile(r"^FLOW results (\w+) (.*)$")
FLOW_BACK = re.compile(r"^FLOW back (\w+) members (\d+) phase (\w+)$")
FLOW_FAILED = re.compile(r"^FLOW failed (.*)$")
FLOW_QUEUED = re.compile(r"^FLOW queued (\w+)$")
FLOW_FOUND = re.compile(r"^FLOW found (\d+) seats (\d+)$")
FLOW_CONFIG = re.compile(r"^FLOW config builders ([\w,]+)$")
# The steps a game of --flow --queue goes through, in order.
QUEUE_STEPS = ["party", "queued", "found", "loading", "match", "end", "results", "back"]
# What a build that lacks a mode's rules says when the server's MATCH_CONFIG names it.
NO_RULES = "cannot play the server's mode"
# The plan bot's duel lines (tests/bot.gd): the orders it sent, and what the simulation did.
BOT_CORK = re.compile(r"^BOT cork (\w+) window (\d+) seq (\d+)$")
BOT_UNCORK = re.compile(r"^BOT uncork bottle (\d+) window (\d+) seq (\d+)$")
BOT_SEAWALL = re.compile(r"^BOT seawall wave (\d+) seq (\d+)$")
BOT_CORKED = re.compile(r"^BOT bottle (\d+) window (\d+) tier (\d+) corked$")
BOT_UNCORKED = re.compile(r"^BOT bottle (\d+) window (\d+) uncorked (\w+) by (bot|client)$")
BOT_FIZZLED = re.compile(r"^BOT bottle (\d+) window (\d+) fizzled$")
BOT_WALKING = re.compile(r"^BOT walking wave (\d+) hollow (\d+) creeps (\d+)$")
BOT_ROSE = re.compile(r"^BOT seawall rose wave (\d+) charges (\d+)$")


def rate_floor(stamps, window):
    """The lowest tick rate over any stretch of at least `window` seconds: from
    each HASH stamp [wall s, tick] to the first stamp `window` or more after
    it, the ticks between them over the stamps' own time between them, and
    where the worst began (s from the first stamp); None with too few stamps.
    Measured by the stamps' own span, not a fixed window: at the protocol's
    50 ms turns a HASH comes once a second, and a fixed 3 s window holds 2 or
    3 of their steps by a few ms of phase, so a steady 60 a second read as 40."""
    if len(stamps) < 3 or stamps[-1][0] - stamps[0][0] < window:
        return None
    worst, at = None, 0.0
    j = 0
    for t, tick in stamps:
        while j < len(stamps) and stamps[j][0] - t < window:
            j += 1
        if j == len(stamps):
            break
        rate = (stamps[j][1] - tick) / (stamps[j][0] - t)
        if worst is None or rate < worst:
            worst, at = rate, t - stamps[0][0]
    return worst, at


def modes():
    """protocol.json's modes: name -> {"id", "teams", "seats": [low, high]}."""
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))["modes"]


def mode_problem(mode, clients):
    """Why --mode MODE --clients N cannot be a dev match ("" where it can): a mode the
    protocol knows, a seat count it takes, and two even teams in a two-team mode."""
    known = modes()
    if mode not in known:
        return f"--mode is one of {', '.join(known)}"
    low, high = known[mode]["seats"]
    if not low <= clients <= high:
        return f"--mode {mode} takes {low} to {high} clients"
    if clients % known[mode]["teams"]:
        return f"--mode {mode} plays {known[mode]['teams']} teams of one size: an even number of clients"
    return ""


def result_key(line, race):
    """What every client's RESULT line must share: all of it, or in a race the final tick
    and the hash (each team prints its own outcome)."""
    return " ".join(line.split()[:3]) if race else line


def race_problems(ends, seats, teams=2):
    """A race's outcomes by team (`ends`: client -> MATCH_END's (outcome, reason, tick);
    `seats`: client -> (seat, of)): one outcome a team, and the teams' answering each
    other (won and lost, or a draw for both)."""
    problems, by_team = [], {}
    for k, (seat, of) in sorted(seats.items()):
        if k in ends:
            by_team.setdefault((seat - 1) * teams // of, set()).add(ends[k][0])
    for team, outcomes in sorted(by_team.items()):
        if len(outcomes) > 1:
            problems.append(f"team {team} ended with {', '.join(sorted(outcomes))}, not one outcome")
    if len(by_team) == teams and all(len(o) == 1 for o in by_team.values()):
        pair = sorted(next(iter(o)) for o in by_team.values())
        if pair not in (["lost", "won"], ["draw", "draw"]):
            problems.append(f"the teams ended {' and '.join(pair)}: one wins and one loses, or both draw")
    elif len(by_team) != teams:
        problems.append(f"the clients sat on {len(by_team)} team(s), not {teams}")
    return problems


def missing_results(ends, results):
    """The clients whose missing RESULT line is a problem: every client sends
    RESULT at the match's end, but once a majority's RESULT ends the match, one
    a few ticks short gets MATCH_END(finished, result) before it gets there.
    Its missing line is fine when another client printed the RESULT of that
    final tick; its hash stream is checked against the others' anyway."""
    finals = {line.split()[1] for line in results.values()}
    return [k for k in sorted(ends) if k not in results
            and not (ends[k][0] in FINISHED and ends[k][1] == "result" and ends[k][2] in finals)]


def queue_game(lines):
    """What one --flow --queue game's log says: its steps (QUEUE_STEPS' names, each once, in
    the order first seen) and the party code, the match found ((match, seats)), the match as
    fielded ((mode, seat, of, builders)), MATCH_CONFIG's Builders, MATCH_END, the way back
    ((code, members, phase)) and any failure."""
    seen = {"steps": [], "failed": []}
    for line in (line.strip() for line in lines):
        step = None
        if m := FLOW_PARTY.match(line):
            seen.setdefault("party", m.group(1))
            step = "party"
        elif FLOW_QUEUED.match(line):
            step = "queued"
        elif m := FLOW_FOUND.match(line):
            seen.setdefault("found", m.groups())
            step = "found"
        elif line == "FLOW state LOADING":
            step = "loading"
        elif m := FLOW_MATCH.match(line):
            seen["match"] = m.groups()
            step = "match"
        elif m := FLOW_CONFIG.match(line):
            seen["config"] = m.group(1).split(",")
        elif m := MATCH_END.match(line):
            seen["end"] = m.groups()
            step = "end"
        elif FLOW_RESULTS.match(line):
            step = "results"
        elif m := FLOW_BACK.match(line):
            seen["back"] = m.groups()
            step = "back"
        elif m := FLOW_FAILED.match(line):
            seen["failed"].append(m.group(1))
        if step and step not in seen["steps"]:
            seen["steps"].append(step)
    return seen


def queue_problems(games, seats=4, mode="high_water", mains=()):
    """--flow --queue's check on what the games' logs say (`games`: client -> queue_game):
    every game through every step to queued again, each in a party of its own, one match
    found of `seats` for all, one MATCH_CONFIG whose Builders are all different (strangers
    on one team never share one: with every main a Lamplighter, the first queued keeps it,
    the next takes the backup and the server draws the rest), one seat each, and a finished
    match of `mode`. In a two-team mode (a duel, or a race of one a side) every party is a
    side of its own, so no Builder is unclashed: MATCH_CONFIG's are the games' `mains`."""
    problems = []
    for k, seen in sorted(games.items()):
        problems += [f"client {k}: {why}" for why in seen["failed"]]
        if seen["steps"] != QUEUE_STEPS:
            went = " -> ".join(seen["steps"]) or "nowhere"
            problems.append(f"client {k} went {went}, not {' -> '.join(QUEUE_STEPS)}")
        end = seen.get("end")
        if end and (end[0] not in FINISHED or end[1] != "result"):
            problems.append(f"client {k}: the match ended {end[0]} ({end[1]}) at tick {end[2]}")
        back = seen.get("back")
        if back and (back[1] != "1" or back[2] != "queued"):
            problems.append(f"client {k} came back to {back[1]} members, {back[2]}: Play again did not queue it again")
    codes = [seen.get("party") for seen in games.values()]
    if None in codes or len(set(codes)) != len(codes):
        problems.append("the games were not each in a party of its own: " + ", ".join(map(str, codes)))
    found = {seen.get("found") for seen in games.values()}
    if len(found) != 1 or None in found:
        problems.append("the games did not all find one match: " + ", ".join(map(str, sorted(found, key=str))))
    elif int(next(iter(found))[1]) != seats:
        problems.append(f"Match Found named {next(iter(found))[1]} seats, not {seats}")
    configs = {tuple(seen.get("config", ())) for seen in games.values()}
    if len(configs) != 1:
        problems.append("the games were configured with different Builders: "
                        + "; ".join(",".join(c) for c in sorted(configs)))
    else:
        chosen = list(next(iter(configs)))
        if two_teams(mode):
            if sorted(chosen) != sorted(mains):
                problems.append(f"MATCH_CONFIG's Builders {','.join(chosen) or 'none'}, the games' mains are"
                                f" {','.join(mains)}: a clash never crosses the sides")
        elif len(chosen) != seats or len(set(chosen)) != len(chosen):
            problems.append(f"MATCH_CONFIG's Builders {','.join(chosen) or 'none'}: strangers on one team share one")
    matched = [seen["match"] for seen in games.values() if "match" in seen]
    if sorted(int(m[1]) for m in matched) != list(range(1, seats + 1)):
        problems.append("the seats were not one each: " + ", ".join(m[1] for m in matched))
    if {m[0] for m in matched} - {mode}:
        problems.append(f"the queue's match was not {mode}: " + ", ".join(sorted({m[0] for m in matched})))
    return problems


def two_teams(mode):
    """Whether protocol.json's `mode` sets two teams against each other (Tide Race, Undertow)."""
    return modes().get(mode, {}).get("teams", 1) > 1


def is_duel(mode):
    """Whether protocol.json's `mode` is a duel: two teams of one seat each (Undertow, M7)."""
    spec = modes().get(mode, {})
    return two_teams(mode) and spec["seats"][1] == spec["teams"]


def queue_mode(args):
    """The mode --flow --queue plays: --mode's, or High Water when --mode is left at its default."""
    return "high_water" if args.mode == "classic" else args.mode


def duel_game(lines):
    """What one duelling game's plan bot says of its duel (tests/bot.gd's BOT lines): the
    orders it sent (CORKs, UNCORKs, SEAWALLs, each a count), the bottles the simulation stood
    ([(id, window, tier)]), those it saw uncorked ([(id, window, pack, by)], by "bot" where Game
    settled an UNCORK of the bot's own as the one that ran, "client" for the client's own at
    auto_uncork_t) and fizzled ([id]), its uncorked
    creeps walking the rival's road ([(wave, hollow, creeps)]) and the Seawalls that rose."""
    seen = {"corks": 0, "uncorks": 0, "seawalls": 0, "corked": [], "uncorked": [], "fizzled": [],
            "walking": [], "rose": 0}
    for line in (line.strip() for line in lines):
        if BOT_CORK.match(line):
            seen["corks"] += 1
        elif BOT_UNCORK.match(line):
            seen["uncorks"] += 1
        elif BOT_SEAWALL.match(line):
            seen["seawalls"] += 1
        elif m := BOT_CORKED.match(line):
            seen["corked"].append(tuple(int(v) for v in m.groups()))
        elif m := BOT_UNCORKED.match(line):
            seen["uncorked"].append((int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)))
        elif m := BOT_FIZZLED.match(line):
            seen["fizzled"].append(int(m.group(1)))
        elif m := BOT_WALKING.match(line):
            seen["walking"].append(tuple(int(v) for v in m.groups()))
        elif BOT_ROSE.match(line):
            seen["rose"] += 1
    return seen


def duel_problems(games):
    """The duel's check on what its games' plan bots said (`games`: client -> duel_game): each
    game's CORK ran (a bottle of its stood in the simulation) and an UNCORK of its bot's own
    was taken (its reveal matched the commitment), and at least one uncorked pack walked a
    rival's road. Every order crossed the server: a game's simulation runs only the turns."""
    problems = []
    for k, seen in sorted(games.items()):
        if not seen["corked"]:
            problems.append(f"client {k} never corked: no bottle of its stood in the simulation"
                            f" ({seen['corks']} CORK(s) sent)")
        if not any(by == "bot" for *_, by in seen["uncorked"]):
            problems.append(f"client {k}'s bot never uncorked a bottle itself: no UNCORK of its own was taken"
                            f" ({seen['uncorks']} sent, {len(seen['uncorked'])} bottle(s) uncorked)")
    if games and not any(seen["walking"] for seen in games.values()):
        problems.append("no uncorked pack walked a rival's road")
    return problems


def duel_counts(games):
    """A line of what the duel's bots did, per client, for the summary."""
    return "; ".join(f"client {k}: {len(g['corked'])} corked, {sum(1 for *_, by in g['uncorked'] if by == 'bot')}"
                     f" uncorked by the bot, {len(g['uncorked']) - sum(1 for *_, by in g['uncorked'] if by == 'bot')}"
                     f" by the client, {len(g['fizzled'])} fizzled, {sum(w[2] for w in g['walking'])} creeps seen"
                     f" walking in {len(g['walking'])} wave(s), {g['rose']} Seawall(s)"
                     for k, g in sorted(games.items()))


def stream_problems(streams, final):
    """The hash streams' check (client -> {tick: hash}): equal at every tick they share, and
    shared to within a hash of the match's last tick `final`."""
    shared = set.intersection(*(set(s) for s in streams.values())) if streams else set()
    first_bad = next((t for t in sorted(shared) if len({streams[k][t] for k in streams}) > 1), None)
    problems = [f"hash streams differ first at tick {first_bad}"] if first_bad is not None else []
    if not shared:
        problems.append("no tick was hashed by every client")
    elif final and max(shared) < final - 60:
        problems.append(f"the shared hash stream stops at tick {max(shared)}, the match ran to {final}")
    return problems, shared


class Smoke:
    def __init__(self, args):
        self.args = args
        self.out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="groundhold-smoke-"))
        self.out.mkdir(parents=True, exist_ok=True)
        self.processes = []
        # (per client: [monotonic seconds, tick] as each new HASH line appeared in its log)
        self.stamps = {}
        self._read_at = {}

    def godot(self):
        found = self.args.godot or os.environ.get("GODOT_PATH") or shutil.which("godot")
        if not found:
            raise SystemExit("smoke: no Godot (set GODOT_PATH or --godot)")
        return found

    def import_if_needed(self):
        missing = missing_classes()
        if not missing:
            return
        print(f"smoke: importing the project first (its class cache lacks {', '.join(missing[:3])}"
              f"{', ...' if len(missing) > 3 else ''})", flush=True)
        subprocess.run([self.godot(), "--headless", "--path", str(ROOT), "--import"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, timeout=900)

    def spawn(self, command, log, **options):
        handle = open(log, "w", encoding="utf-8")
        process = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True, **options)
        self.processes.append((process, handle))
        return process

    def stop_all(self):
        for process, handle in self.processes:
            if process.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        for process, handle in self.processes:
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=max(0.1, deadline - time.monotonic()))
            if process.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            handle.close()

    def server_main(self):
        return str(Path(self.args.server).resolve()) if self.args.server else "server/main.py"

    def server_command(self):
        command = [sys.executable, self.server_main(), "--dev-match", f"{self.args.mode}:{self.args.clients}",
                   "--port", "0", "--host", "127.0.0.1", "--seed", str(self.args.seed),
                   "--event-log", str(self.out / "events.jsonl")]
        if self.args.turn_ms:
            command += ["--turn-ms", str(self.args.turn_ms)]
        return command

    def start_server(self):
        log = self.out / "server.log"
        command = self.server_command()
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        process = self.spawn(command, log, cwd=ROOT, env=env)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("the server exited before listening:\n" + tail(log))
            match = READY.search(log.read_text(encoding="utf-8", errors="replace"))
            if match:
                return int(match.group("port"))
            time.sleep(0.05)
        raise RuntimeError("the server did not listen within 15 s:\n" + tail(log))

    def shaped(self):
        """The client the shaper stands in front of (0: none)."""
        return self.args.clients if (self.args.shaper or self.args.faults) else 0

    def start_shaper(self, port):
        command = [sys.executable, str(ROOT / "tools/net/shaper.py"), "--to", f"127.0.0.1:{port}", "--port", "0",
                   "--seed", str(self.args.seed)]
        if self.args.shaper:
            command += ["--delay-ms", "150", "--jitter-ms", "50", "--stall-at", str(self.args.stall_at),
                        "--stall-ms", str(self.args.stall_ms)]
        else:
            command += ["--delay-ms", "0", "--jitter-ms", "0"]
        if self.args.faults:
            command += ["--cut-at", str(self.args.cut_at), "--cut-ms", str(self.args.cut_ms)]
        log = self.out / "shaper.log"
        process = self.spawn(command, log, cwd=ROOT, env=dict(os.environ, PYTHONUNBUFFERED="1"))
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("the shaper exited before listening:\n" + tail(log))
            match = SHAPER_READY.search(log.read_text(encoding="utf-8", errors="replace"))
            if match:
                return int(match.group("port"))
            time.sleep(0.05)
        raise RuntimeError("the shaper did not listen within 10 s:\n" + tail(log))

    def start_clients(self, port):
        clients = []
        shaped_port = self.start_shaper(port) if self.shaped() else port
        for k in range(1, self.args.clients + 1):
            hashes = self.out / f"client{k}.hashes"
            to = shaped_port if k == self.shaped() else port
            command = [self.godot(), "--headless", "--path", str(ROOT), "--",
                       f"--join=127.0.0.1:{to}", "--quit-after-match", f"--hash-log={hashes}",
                       f"--name=Smoke{k}"]
            if not self.args.no_bot:
                command.append("--bot")
            clients.append((k, self.spawn(command, self.out / f"client{k}.log", cwd=ROOT), hashes))
        return clients

    def header(self):
        return f"smoke: {self.args.mode}:{self.args.clients} seed {self.args.seed}, logs in {self.out}"

    def run(self):
        print(self.header(), flush=True)
        self.import_if_needed()
        began = time.monotonic()
        try:
            port = self.start_server()
            print(f"smoke: server on 127.0.0.1:{port}", flush=True)
            clients = self.start_clients(port)
            deadline = began + self.args.timeout
            while any(process.poll() is None for _, process, _ in clients):
                if time.monotonic() > deadline:
                    raise RuntimeError(f"the match did not finish within {self.args.timeout} s")
                self.stamp(clients)
                time.sleep(0.05)
            self.stamp(clients)
            report = self.check(clients)
        except RuntimeError as exc:
            report = {"ok": False, "problems": [str(exc)]}
        finally:
            self.stop_all()
        report["seconds"] = round(time.monotonic() - began, 1)
        report["out"] = str(self.out)
        (self.out / "smoke.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        self.summarise(report)
        return 0 if report["ok"] else 1

    def stamp(self, clients):
        """Reads what each client's log gained since the last look and stamps
        its new HASH ticks with the time now (its tick rate, for --shaper)."""
        now = time.monotonic()
        for k, _, _ in clients:
            log = self.out / f"client{k}.log"
            try:
                with open(log, "rb") as handle:
                    handle.seek(self._read_at.get(k, 0))
                    data = handle.read()
            except OSError:
                continue
            cut = data.rfind(b"\n") + 1   # (whole lines only; the rest next time)
            self._read_at[k] = self._read_at.get(k, 0) + cut
            stamps = self.stamps.setdefault(k, [])
            for line in data[:cut].decode("utf-8", errors="replace").splitlines():
                match = HASH.match(line.strip())
                if match and (not stamps or int(match.group(1)) > stamps[-1][1]):
                    stamps.append([now, int(match.group(1))])

    def tick_rate(self, k):
        """Client k's lowest tick rate over RATE_WINDOW (rate_floor), from its
        first HASH of the match to its last; None with too few stamps."""
        # (tick 0's HASH comes at load time, before START: the match runs from the next one)
        return rate_floor([stamp for stamp in self.stamps.get(k, []) if stamp[1] > 0], RATE_WINDOW)

    def pace(self):
        """The server's ticks a second (a dev match's --turn-ms, else the protocol's)."""
        return TURN_TICKS * 1000 / (self.args.turn_ms or TURN_MS)

    def race(self):
        """The dev match's mode has two teams (Tide Race, or Undertow's duel)."""
        return modes()[self.args.mode]["teams"] > 1

    def duel(self):
        """The dev match's mode is a duel: two teams of one seat (Undertow, M7)."""
        return is_duel(self.args.mode)

    def check(self, clients):
        problems = []
        streams, results, ends, seats = {}, {}, {}, {}
        race = self.race()
        for k, process, hashes in clients:
            log = self.out / f"client{k}.log"
            text = log.read_text(encoding="utf-8", errors="replace")
            # (the log has every line printed; the file may miss its last lines if killed)
            streams[k] = read_hashes(log)
            if hashes.exists():
                streams[k].update(read_hashes(hashes))
            for line in text.splitlines():
                if RESULT.match(line):
                    results[k] = line.strip()
                if MATCH.match(line.strip()):
                    found = MATCH.match(line.strip())
                    seats[k] = (int(found.group(2)), int(found.group(3)))
                if MATCH_END.match(line):
                    ends[k] = MATCH_END.match(line).groups()
            if process.returncode != 0:
                problems.append(f"client {k} exited with {process.returncode}:\n" + tail(log))
            if k not in ends:
                problems.append(f"client {k} never saw MATCH_END")
            elif ends[k][0] not in FINISHED or ends[k][1] != "result":
                problems.append(f"client {k}: the match ended {ends[k][0]} ({ends[k][1]}) at tick {ends[k][2]}")
        for k in missing_results(ends, results) + [k for k, _, _ in clients if k not in ends and k not in results]:
            problems.append(f"client {k} printed no RESULT")
        if any(NO_RULES in (self.out / f"client{k}.log").read_text(encoding="utf-8", errors="replace")
               for k, _, _ in clients):
            # (the cause of everything else: say it first)
            problems.insert(0, f"this build has no {self.args.mode} rules (scripts/sim/content.gd RULES): its games"
                               f" cannot play the server's mode, so no check below can pass")
        if len({result_key(line, race) for line in results.values()}) > 1:
            problems.append("the clients' RESULT lines differ: " + "; ".join(sorted(set(results.values()))))
        if race:
            problems += race_problems(ends, seats, modes()[self.args.mode]["teams"])
        if self.duel() and sorted(seats.values()) != [(1, 2), (2, 2)]:
            problems.append("a duel is seat 1 of 2 against seat 2 of 2: the clients sat "
                            + ", ".join(f"{seat} of {of}" for seat, of in sorted(seats.values())))
        duels = {}
        if self.duel() and not getattr(self.args, "no_bot", False):
            duels = {k: duel_game((self.out / f"client{k}.log").read_text(encoding="utf-8", errors="replace")
                                  .splitlines()) for k, _, _ in clients}
            problems += duel_problems(duels)
        shared = set.intersection(*(set(s) for s in streams.values())) if streams else set()
        first_bad = None
        for tick in sorted(shared):
            if len({streams[k][tick] for k in streams}) > 1:
                first_bad = tick
                break
        if first_bad is not None:
            problems.append(f"hash streams differ first at tick {first_bad}: "
                            + ", ".join(f"client {k} {streams[k][first_bad]}" for k in sorted(streams)))
        final = max((int(end[2]) for end in ends.values()), default=0)
        if not shared:
            problems.append("no tick was hashed by every client")
        elif final and max(shared) < final - 60:
            problems.append(f"the shared hash stream stops at tick {max(shared)}, the match ran to {final}")
        server_log = (self.out / "server.log").read_text(encoding="utf-8", errors="replace")
        if '"event": "desync"' in server_log or '"event":"desync"' in server_log:
            problems.append("the server logged a desync")
        outcome = next(iter(ends.values()))[0] if ends else None
        rates, resyncs = {}, {}
        for k, _, _ in clients:
            measured = self.tick_rate(k)
            rates[k] = None if measured is None else {"ticks_per_second_min": round(measured[0], 1),
                                                       "at_s": round(measured[1], 1)}
            text = (self.out / f"client{k}.log").read_text(encoding="utf-8", errors="replace")
            resyncs[k] = [m.groups() for m in map(RESYNC.match, text.splitlines()) if m]
        floor = self.args.rate_floor * self.pace()
        if self.args.shaper:
            for k, _, _ in clients:
                if k == self.shaped():
                    continue
                if rates[k] is None:
                    problems.append(f"client {k}'s tick rate could not be measured (too few HASH lines)")
                elif rates[k]["ticks_per_second_min"] < floor:
                    problems.append(f"client {k}'s tick rate dropped to {rates[k]['ticks_per_second_min']} a second"
                                    f" {rates[k]['at_s']} s into its match (the floor is {floor:.0f},"
                                    f" the server's pace {self.pace():.0f}) while client {self.shaped()} was shaped")
            shaper_log = (self.out / "shaper.log").read_text(encoding="utf-8", errors="replace")
            if "stall:" not in shaper_log:
                problems.append("the shaper's stall never came: the match ended first (lower --stall-at)")
        if self.args.faults:
            k = self.shaped()
            shaper_log = (self.out / "shaper.log").read_text(encoding="utf-8", errors="replace")
            if " cut " not in shaper_log:
                problems.append("the shaper's cut never came: the match ended first (lower --cut-at)")
            elif not any(reason == "rejoin" for reason, _ in resyncs[k]):
                problems.append(f"client {k} was cut and never rejoined (no RESYNC rejoin in its log):\n"
                                + tail(self.out / f"client{k}.log"))
        return {"ok": not problems, "problems": problems, "outcome": outcome, "final_tick": final,
                "hashes_compared": len(shared), "result": next(iter(results.values()), None),
                "duel": duel_counts(duels) if duels else None,
                "clients": {k: {"hashes": len(streams[k]), "end": ends.get(k), "tick_rate": rates.get(k),
                                "resyncs": resyncs.get(k), "shaped": k == self.shaped(), "duel": duels.get(k)}
                            for k in streams}}

    def summarise(self, report):
        if report.get("duel"):
            print(f"smoke: the duel's orders · {report['duel']}")
        if report["ok"]:
            print(f"smoke: PASS · the match ended {report['outcome']} at tick {report['final_tick']}"
                  f" · {report['hashes_compared']} hash ticks equal on every client · {report['seconds']} s")
            print(f"smoke: {report['result']}")
            for k, c in sorted(report["clients"].items()):
                if self.shaped():
                    rate = c["tick_rate"]["ticks_per_second_min"] if c["tick_rate"] else "?"
                    print(f"smoke: client {k}{' (shaped)' if c['shaped'] else ''}: at least {rate} ticks a second"
                          f" over any {RATE_WINDOW:.0f} s · resyncs {c['resyncs']}")
        else:
            print(f"smoke: FAIL after {report['seconds']} s")
            for problem in report["problems"]:
                print("  - " + problem)
        print(f"smoke: logs in {report['out']}")


class Flow(Smoke):
    """The loop around a match against the real server's hub (--flow)."""

    def server_command(self):
        return [sys.executable, "server/main.py", "--port", "0", "--host", "127.0.0.1",
                "--seed", str(self.args.seed), "--state-dir", str(self.out / "state"),
                "--event-log", str(self.out / "events.jsonl")]

    def builders(self):
        chosen = [b.strip() for b in self.args.builders.split(",") if b.strip()]
        return [chosen[i % len(chosen)] for i in range(self.args.clients)]

    def start_clients(self, port):
        clients = []
        code_file = self.out / "party_code.txt"
        code_file.unlink(missing_ok=True)
        for k, builder in enumerate(self.builders(), start=1):
            hashes = self.out / f"client{k}.hashes"
            command = [self.godot(), "--headless", "--path", str(ROOT), "--",
                       f"--server=127.0.0.1:{port}", "--flow-bot", f"--party={self.args.clients}",
                       f"--name=Flow{k}", f"--main={builder}", f"--hash-log={hashes}", "--quit-after-flow",
                       f"--code-out={code_file}" if k == 1 else f"--code-in={code_file}"]
            command += ["--ready-calls"] if self.args.no_bot else ["--ready-calls", "--bot"]
            if self.args.linger:
                command.append(f"--linger={self.args.linger:g}")
            clients.append((k, self.spawn(command, self.out / f"client{k}.log", cwd=ROOT), hashes))
        return clients

    def header(self):
        played = "idle, calling every wave" if self.args.no_bot else "played by the plan bots, calling every wave"
        return (f"smoke: the loop, {self.args.clients} games ({','.join(self.builders())}, {played})"
                f" seed {self.args.seed}, logs in {self.out}")

    def check(self, clients):
        problems = []
        codes, matches, ends, results, backs, streams = {}, {}, {}, {}, {}, {}
        for k, process, hashes in clients:
            log = self.out / f"client{k}.log"
            lines = [line.strip() for line in log.read_text(encoding="utf-8", errors="replace").splitlines()]
            streams[k] = read_hashes(log)
            if hashes.exists():
                streams[k].update(read_hashes(hashes))
            steps = []
            for line in lines:
                if (m := FLOW_PARTY.match(line)) and int(m.group(2)) == self.args.clients:
                    codes.setdefault(k, m.group(1))
                    steps.append("party")
                elif m := FLOW_MATCH.match(line):
                    matches[k] = m.groups()
                    steps.append("match")
                elif m := MATCH_END.match(line):
                    ends[k] = m.groups()
                    steps.append("end")
                elif m := FLOW_RESULTS.match(line):
                    results[k] = m.groups()
                    steps.append("results")
                elif m := FLOW_BACK.match(line):
                    backs[k] = m.groups()
                    steps.append("back")
                elif m := FLOW_FAILED.match(line):
                    problems.append(f"client {k}: {m.group(1)}")
                elif line == "FLOW state LOADING":
                    steps.append("loading")
            order = [step for i, step in enumerate(steps) if step not in steps[:i]]
            if order != ["party", "loading", "match", "end", "results", "back"]:
                problems.append(f"client {k} went {' -> '.join(order) or 'nowhere'}, not party -> loading -> match"
                                f" -> end -> results -> back:\n" + tail(log))
            if process.returncode != 0:
                problems.append(f"client {k} exited with {process.returncode}")
            if k in ends and (ends[k][0] not in FINISHED or ends[k][1] != "result"):
                problems.append(f"client {k}: the match ended {ends[k][0]} ({ends[k][1]}) at tick {ends[k][2]}")
            if k in backs and (backs[k][1] != str(self.args.clients) or backs[k][2] != "forming"):
                problems.append(f"client {k} came back to {backs[k][1]} members, {backs[k][2]}")
        if len(set(codes.values())) > 1:
            problems.append("the games were in different parties: " + ", ".join(sorted(set(codes.values()))))
        if len({(m[0], m[2], m[3]) for m in matches.values()}) > 1:
            problems.append("the games were configured differently: " + "; ".join(map(str, matches.values())))
        # (seats follow the party's rows, which follow the order the games
        # joined in, not the clients' order: each game's own seat must hold its
        # own main, as this build fields it)
        mains = [b if b in FIELDED else "lamplighter" for b in self.builders()]
        for k, m in matches.items():
            fielded, seat = m[3].split(","), int(m[1])
            if sorted(fielded) != sorted(mains):
                problems.append(f"client {k} fielded {m[3]}, the members' mains are {','.join(mains)}")
            elif not 1 <= seat <= len(fielded) or fielded[seat - 1] != mains[k - 1]:
                problems.append(f"client {k} sat in seat {seat} of {m[3]}, not as its own main {mains[k - 1]}")
        if sorted(int(m[1]) for m in matches.values()) != list(range(1, len(matches) + 1)):
            problems.append("the seats were not one each: " + ", ".join(m[1] for m in matches.values()))
        shared = set.intersection(*(set(s) for s in streams.values())) if streams else set()
        first_bad = next((t for t in sorted(shared) if len({streams[k][t] for k in streams}) > 1), None)
        if first_bad is not None:
            problems.append(f"hash streams differ first at tick {first_bad}")
        final = max((int(end[2]) for end in ends.values()), default=0)
        if not shared:
            problems.append("no tick was hashed by every client")
        elif final and max(shared) < final - 60:
            problems.append(f"the shared hash stream stops at tick {max(shared)}, the match ran to {final}")
        server_log = (self.out / "server.log").read_text(encoding="utf-8", errors="replace")
        if '"event": "desync"' in server_log or '"event":"desync"' in server_log:
            problems.append("the server logged a desync")
        first = next(iter(matches.values()), ("?", "0", "0", ""))
        return {"ok": not problems, "problems": problems, "party": next(iter(codes.values()), None),
                "mode": first[0], "builders": first[3], "outcome": next(iter(ends.values()), (None,))[0],
                "final_tick": final, "hashes_compared": len(shared),
                "result": next(iter(results.values()), None),
                "clients": {k: {"hashes": len(streams[k]), "end": ends.get(k), "back": backs.get(k)} for k in streams}}

    def summarise(self, report):
        if report["ok"]:
            print(f"smoke: PASS · party {report['party']} · {report['mode']} with {report['builders']}"
                  f" · ended {report['outcome']} at tick {report['final_tick']}"
                  f" · {report['hashes_compared']} hash ticks equal · every game back in the party, forming"
                  f" · {report['seconds']} s")
        else:
            print(f"smoke: FAIL after {report['seconds']} s")
            for problem in report["problems"]:
                print("  - " + problem)
        print(f"smoke: logs in {report['out']}")


class QueueFlow(Flow):
    """--flow --queue: four games, each a party of one, meet through the server's queue."""

    def start_clients(self, port):
        clients = []
        for k, builder in enumerate(self.builders(), start=1):
            hashes = self.out / f"client{k}.hashes"
            command = [self.godot(), "--headless", "--path", str(ROOT), "--",
                       f"--server=127.0.0.1:{port}", "--flow-bot", "--queue", f"--name=Queue{k}",
                       f"--main={builder}", f"--hash-log={hashes}", "--quit-after-flow"]
            if queue_mode(self.args) != "high_water":
                command.append(f"--mode={queue_mode(self.args)}")  # (Find a rival, not Find players)
            command += ["--ready-calls"] if self.args.no_bot else ["--ready-calls", "--bot"]
            if self.args.linger:
                command.append(f"--linger={self.args.linger:g}")
            clients.append((k, self.spawn(command, self.out / f"client{k}.log", cwd=ROOT), hashes))
        return clients

    def header(self):
        played = "idle, calling every wave" if self.args.no_bot else "played by the plan bots, calling every wave"
        return (f"smoke: the queue, {self.args.clients} games alone in {queue_mode(self.args)}"
                f" ({','.join(self.builders())}, {played}) seed {self.args.seed}, logs in {self.out}")

    def check(self, clients):
        games, streams, problems = {}, {}, []
        for k, process, hashes in clients:
            log = self.out / f"client{k}.log"
            games[k] = queue_game(log.read_text(encoding="utf-8", errors="replace").splitlines())
            streams[k] = read_hashes(log)
            if hashes.exists():
                streams[k].update(read_hashes(hashes))
            if process.returncode != 0:
                problems.append(f"client {k} exited with {process.returncode}:\n" + tail(log))
        mains = [b if b in FIELDED else "lamplighter" for b in self.builders()]
        problems += queue_problems(games, self.args.clients, queue_mode(self.args), mains)
        if two_teams(queue_mode(self.args)):
            # (rivals: one outcome a side, answering each other)
            ends = {k: g["end"] for k, g in games.items() if "end" in g}
            seats = {k: (int(g["match"][1]), int(g["match"][2])) for k, g in games.items() if "match" in g}
            problems += race_problems(ends, seats, modes()[queue_mode(self.args)]["teams"])
        duels = {}
        if is_duel(queue_mode(self.args)) and not self.args.no_bot:
            duels = {k: duel_game((self.out / f"client{k}.log").read_text(encoding="utf-8", errors="replace")
                                  .splitlines()) for k, _, _ in clients}
            problems += duel_problems(duels)
        final = max((int(g["end"][2]) for g in games.values() if "end" in g), default=0)
        hashed, shared = stream_problems(streams, final)
        problems += hashed
        server_log = (self.out / "server.log").read_text(encoding="utf-8", errors="replace")
        if '"event": "desync"' in server_log or '"event":"desync"' in server_log:
            problems.append("the server logged a desync")
        first = next(iter(games.values()), {})
        return {"ok": not problems, "problems": problems, "builders": ",".join(first.get("config", ())),
                "outcome": first.get("end", (None,))[0], "final_tick": final, "hashes_compared": len(shared),
                "duel": duel_counts(duels) if duels else None,
                "clients": {k: {"party": g.get("party"), "steps": g["steps"], "end": g.get("end"),
                                "back": g.get("back"), "duel": duels.get(k)} for k, g in games.items()}}

    def summarise(self, report):
        if report.get("duel"):
            print(f"smoke: the duel's orders · {report['duel']}")
        if report["ok"]:
            print(f"smoke: PASS · {self.args.clients} parties of one met in the queue · Match Found, all accepted"
                  f" · {queue_mode(self.args)} with {report['builders']} · ended {report['outcome']} at tick"
                  f" {report['final_tick']} · {report['hashes_compared']} hash ticks equal · every game queued"
                  f" again by Play again · {report['seconds']} s")
        else:
            print(f"smoke: FAIL after {report['seconds']} s")
            for problem in report["problems"]:
                print("  - " + problem)
        print(f"smoke: logs in {report['out']}")


def read_hashes(path):
    stream = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = HASH.match(line.strip())
        if match:
            stream[int(match.group(1))] = match.group(2)
    return stream


def tail(path, lines=25):
    try:
        return "\n".join(Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return "(no log)"


def parse_args(argv=None):
    """The command line, its defaults filled and its combinations checked (a refused one exits)."""
    parser = argparse.ArgumentParser(description="Play one networked match: the real server and headless clients")
    parser.add_argument("--mode", default="classic",
                        help="the dev match's mode, one of protocol.json's (default classic; tide_race takes 2 or 4"
                             " clients, two teams; undertow, the duel, 2, one a side); with --flow --queue the mode"
                             " the games queue in (tide_race or undertow: two games find each other as rivals)")
    parser.add_argument("--clients", type=int, default=None,
                        help="headless clients, one per seat (default 2; with --queue 4, or 2 in a two-team mode)")
    parser.add_argument("--seed", type=int, default=1, help="the match seed (default 1)")
    parser.add_argument("--turn-ms", type=int, default=0,
                        help="the server's turn length in ms (default the protocol's 50; 10 plays five times faster)")
    parser.add_argument("--timeout", type=float, default=None,
                        help="seconds for the whole match (default 900; 1500 for the bots' duel through the queue)")
    parser.add_argument("--godot", help="the Godot binary (default $GODOT_PATH, else godot on PATH)")
    parser.add_argument("--out", help="where logs and hash streams go (default a new temp folder)")
    parser.add_argument("--no-bot", action="store_true",
                        help="the clients only watch (the match is lost); with --flow they call every wave at once")
    parser.add_argument("--flow", action="store_true",
                        help="the loop instead: hub, party by code, start, loading, match, results, back in the party")
    parser.add_argument("--shaper", action="store_true",
                        help="the last client plays through tools/net/shaper.py: 150 ± 50 ms each way and a stall;"
                             " every other client's tick rate must never drop")
    parser.add_argument("--faults", action="store_true",
                        help="the shaper cuts the last client's link (--cut-at, --cut-ms): it must rejoin and finish")
    parser.add_argument("--stall-at", type=float, default=25, help="with --shaper: the stall, seconds after it connects")
    parser.add_argument("--stall-ms", type=int, default=3000, help="with --shaper: how long the stall lasts (default 3000)")
    parser.add_argument("--cut-at", type=float, default=30, help="with --faults: the cut, seconds after it connects")
    parser.add_argument("--cut-ms", type=int, default=8000,
                        help="with --faults: how long its new links are refused (default 8000: its seat goes AWAY)")
    parser.add_argument("--rate-floor", type=float, default=0.8,
                        help="with --shaper: the share of the server's pace another client never drops below")
    parser.add_argument("--server", help="another checkout's server/main.py (default this one's)")
    parser.add_argument("--linger", type=float, default=0,
                        help="with --flow: seconds each game stays on the results before Play again")
    parser.add_argument("--builders", default=None,
                        help="with --flow: the members' mains in order, repeated as needed (default"
                             " lamplighter,lookout; with --queue lamplighter for all, so the server unclashes them)")
    parser.add_argument("--queue", action="store_true",
                        help="with --flow: four games, each a party of one, meet through the server's queue (Find"
                             " players, Match Found), play, and are queued again by Play again")
    args = parser.parse_args(argv)
    rivals = args.flow and args.queue and two_teams(queue_mode(args))
    if args.clients is None:
        args.clients = 4 if args.queue and not rivals else 2
    if args.builders is None:
        args.builders = "lamplighter" if args.queue else "lamplighter,lookout"
    if args.timeout is None:
        # (the bots' duel at the protocol's 50 ms turns runs to the Surge's end: about 740 s)
        args.timeout = 1500 if rivals and is_duel(queue_mode(args)) and not args.no_bot else 900
    if not 1 <= args.clients <= 4:
        parser.error("--clients is 1 to 4")
    if args.queue and not args.flow:
        parser.error("--queue is --flow's: the hub's queue, not a dev match")
    if args.queue and args.flow and queue_mode(args) not in modes():
        parser.error(f"--mode is one of {', '.join(modes())}")
    if args.queue and not rivals and args.clients != 4:
        parser.error("--queue plays four games: High Water's queue fills four seats with strangers")
    if rivals and args.clients != 2:
        parser.error(f"--queue --mode {args.mode} plays two games: each a party of one, rivals one a side")
    if args.flow and args.turn_ms:
        parser.error("--turn-ms is a dev match's; the hub's matches keep the protocol's turns")
    if args.flow and args.mode != "classic" and not (args.queue and (rivals or args.mode == "high_water")):
        parser.error("--mode is a dev match's; --flow plays the hub's mode, the leader's (High Water); with"
                     " --queue it may name a two-team mode")
    if not args.flow and mode_problem(args.mode, args.clients):
        parser.error(mode_problem(args.mode, args.clients))
    if args.linger and not args.flow:
        parser.error("--linger is --flow's: a dev match has no results plate to stay on")
    if args.flow and (args.shaper or args.faults):
        parser.error("--shaper and --faults shape a dev match's client, not --flow's")
    if (args.shaper or args.faults) and args.clients < 2:
        parser.error("--shaper and --faults need two clients or more: one shaped, the others measured")
    return args


def main(argv=None):
    args = parse_args(argv)
    smoke = (QueueFlow(args) if args.queue else Flow(args)) if args.flow else Smoke(args)
    previous = signal.getsignal(signal.SIGTERM)

    def stop(signum, frame):
        smoke.stop_all()
        raise SystemExit(1)

    signal.signal(signal.SIGTERM, stop)
    try:
        return smoke.run()
    except KeyboardInterrupt:
        smoke.stop_all()
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    sys.exit(main())
