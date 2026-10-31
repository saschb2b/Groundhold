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
READY = re.compile(r"listening.*port\D*(?P<port>\d+)")
HASH = re.compile(r"^HASH (\d+) ([0-9a-f]+)$")
RESULT = re.compile(r"^RESULT (\d+) ([0-9a-f]+) (\w+)$")
MATCH_END = re.compile(r"^MATCH_END (\w+) (\w+) (\d+)$")
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


def missing_results(ends, results):
    """The clients whose missing RESULT line is a problem: every client sends
    RESULT at the match's end, but once a majority's RESULT ends the match, one
    a few ticks short gets MATCH_END(finished, result) before it gets there.
    Its missing line is fine when another client printed the RESULT of that
    final tick; its hash stream is checked against the others' anyway."""
    finals = {line.split()[1] for line in results.values()}
    return [k for k in sorted(ends) if k not in results
            and not (ends[k][0] in FINISHED and ends[k][1] == "result" and ends[k][2] in finals)]


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

    def check(self, clients):
        problems = []
        streams, results, ends = {}, {}, {}
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
        if len(set(results.values())) > 1:
            problems.append("the clients' RESULT lines differ: " + "; ".join(sorted(set(results.values()))))
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
                "clients": {k: {"hashes": len(streams[k]), "end": ends.get(k), "tick_rate": rates.get(k),
                                "resyncs": resyncs.get(k), "shaped": k == self.shaped()} for k in streams}}

    def summarise(self, report):
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Play one networked match: the real server and headless clients")
    parser.add_argument("--mode", default="classic", help="the dev match's mode (default classic)")
    parser.add_argument("--clients", type=int, default=2, help="headless clients, one per seat (default 2)")
    parser.add_argument("--seed", type=int, default=1, help="the match seed (default 1)")
    parser.add_argument("--turn-ms", type=int, default=0,
                        help="the server's turn length in ms (default the protocol's 50; 10 plays five times faster)")
    parser.add_argument("--timeout", type=float, default=900, help="seconds for the whole match (default 900)")
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
    parser.add_argument("--builders", default="lamplighter,lookout",
                        help="with --flow: the members' mains in order, repeated as needed (default lamplighter,lookout)")
    args = parser.parse_args(argv)
    if not 1 <= args.clients <= 4:
        parser.error("--clients is 1 to 4")
    if args.flow and args.turn_ms:
        parser.error("--turn-ms is a dev match's; the hub's matches keep the protocol's turns")
    if args.flow and (args.shaper or args.faults):
        parser.error("--shaper and --faults shape a dev match's client, not --flow's")
    if (args.shaper or args.faults) and args.clients < 2:
        parser.error("--shaper and --faults need two clients or more: one shaped, the others measured")
    smoke = Flow(args) if args.flow else Smoke(args)
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
