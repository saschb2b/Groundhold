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


class Smoke:
    def __init__(self, args):
        self.args = args
        self.out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="lantern-smoke-"))
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

    def start_server(self):
        log = self.out / "server.log"
        command = [sys.executable, "server/main.py", "--dev-match", f"{self.args.mode}:{self.args.clients}",
                   "--port", "0", "--host", "127.0.0.1", "--seed", str(self.args.seed),
                   "--event-log", str(self.out / "events.jsonl")]
        if self.args.turn_ms:
            command += ["--turn-ms", str(self.args.turn_ms)]
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

    def run(self):
        print(f"smoke: {self.args.mode}:{self.args.clients} seed {self.args.seed}, logs in {self.out}", flush=True)
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
    parser.add_argument("--no-bot", action="store_true", help="the clients only watch (the match is lost)")
    args = parser.parse_args(argv)
    if not 1 <= args.clients <= 4:
        parser.error("--clients is 1 to 4")
    smoke = Smoke(args)
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
