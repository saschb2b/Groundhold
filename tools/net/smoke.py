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
FINISHED = ("won", "lost", "draw")
# The Builders this build shows as themselves; any other main is fielded as a
# Lamplighter until its towers are painted (Profile.fielded).
FIELDED = ("lamplighter", "lookout")
FLOW_PARTY = re.compile(r"^FLOW party (\w+) members (\d+) me (\d+) (leader|member)$")
FLOW_MATCH = re.compile(r"^FLOW match (\w+) seat (\d+) of (\d+) builders ([\w,]+)$")
FLOW_RESULTS = re.compile(r"^FLOW results (\w+) (.*)$")
FLOW_BACK = re.compile(r"^FLOW back (\w+) members (\d+) phase (\w+)$")
FLOW_FAILED = re.compile(r"^FLOW failed (.*)$")


class Smoke:
    def __init__(self, args):
        self.args = args
        self.out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="groundhold-smoke-"))
        self.out.mkdir(parents=True, exist_ok=True)
        self.processes = []

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

    def server_command(self):
        command = [sys.executable, "server/main.py", "--dev-match", f"{self.args.mode}:{self.args.clients}",
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

    def start_clients(self, port):
        clients = []
        for k in range(1, self.args.clients + 1):
            hashes = self.out / f"client{k}.hashes"
            command = [self.godot(), "--headless", "--path", str(ROOT), "--",
                       f"--join=127.0.0.1:{port}", "--quit-after-match", f"--hash-log={hashes}",
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
                time.sleep(0.25)
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
            if k not in results:
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
        return {"ok": not problems, "problems": problems, "outcome": outcome, "final_tick": final,
                "hashes_compared": len(shared), "result": next(iter(results.values()), None),
                "clients": {k: {"hashes": len(streams[k]), "end": ends.get(k)} for k in streams}}

    def summarise(self, report):
        if report["ok"]:
            print(f"smoke: PASS · the match ended {report['outcome']} at tick {report['final_tick']}"
                  f" · {report['hashes_compared']} hash ticks equal on every client · {report['seconds']} s")
            print(f"smoke: {report['result']}")
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
    parser.add_argument("--builders", default="lamplighter,lookout",
                        help="with --flow: the members' mains in order, repeated as needed (default lamplighter,lookout)")
    args = parser.parse_args(argv)
    if not 1 <= args.clients <= 4:
        parser.error("--clients is 1 to 4")
    if args.flow and args.turn_ms:
        parser.error("--turn-ms is a dev match's; the hub's matches keep the protocol's turns")
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
