#!/usr/bin/env python3
"""A bad network between one game and the server (design §8 M4, track D).

A TCP proxy: the game connects to the shaper's port, the shaper connects on to
the server, and everything in between is held back as a poor link would:

- latency: every chunk waits DELAY ± JITTER ms (uniform, seeded) in its own
  direction, in order as TCP keeps it (a chunk never overtakes the one before);
- stalls: from STALL_AT seconds after the first connection, nothing moves
  either way for STALL_MS, then what waited goes in order (a busy laptop, a
  tunnel on a train);
- cuts: at CUT_AT seconds every open connection is closed at once, both ways,
  with what was on its way (the cable pulled), and for CUT_MS new connections
  are closed as they come (no server answers); after that they pass again, so
  a game that reconnects with a resume HELLO gets its seat back.

    python3 tools/net/shaper.py --to 127.0.0.1:8765 --delay-ms 150 --jitter-ms 50 \\
        --stall-at 25 --stall-ms 3000
    python3 tools/net/shaper.py --to 127.0.0.1:8765 --cut-at 25 --cut-ms 5000

It prints `shaper: listening on 127.0.0.1:PORT` once it listens (--port 0 picks
one), a line per stall and cut as it happens, and on SIGTERM or Ctrl-C a JSON
summary (`shaper: {...}`: connections, bytes each way, stalls and cuts done,
the longest any chunk was held). tools/net/smoke.py --shaper and --faults run
it in front of one client. Every timer reads time.monotonic(), and every wait
has its end: the proxy never holds more than one connection's worth of
chunks per direction, and stops when its listener closes. Python 3.11+, no
dependencies.
"""

import argparse
import asyncio
import contextlib
import json
import random
import signal
import sys
import time

CHUNK = 65536


class Shaper:
    def __init__(self, args):
        self.args = args
        self.host, _, port = args.to.rpartition(":")
        self.port = int(port)
        self.random = random.Random(args.seed)
        self.started = None          # monotonic time of the first connection
        self.connections = set()
        self.stats = {"connections": 0, "refused": 0, "bytes_up": 0, "bytes_down": 0,
                      "stalls": 0, "cuts": 0, "held_ms_max": 0}
        self.stall_windows = []      # [start, end) in monotonic seconds, once started
        self.cut_until = None        # new connections are refused before this
        self.server = None

    # ── Timing ──

    def delay(self):
        low = max(0, self.args.delay_ms - self.args.jitter_ms)
        high = self.args.delay_ms + self.args.jitter_ms
        return self.random.uniform(low, high) / 1000.0

    def release_at(self, arrived, last):
        """When a chunk that arrived at `arrived` goes on: its delay, never
        before the one before it, and never inside a stall."""
        at = max(last, arrived + self.delay())
        for start, end in self.stall_windows:
            if start <= at < end:
                at = end
        return at

    def begin(self):
        if self.started is not None:
            return
        self.started = time.monotonic()
        for at in self.args.stall_at:
            self.stall_windows.append((self.started + at, self.started + at + self.args.stall_ms / 1000.0))
        loop = asyncio.get_running_loop()
        for start, end in self.stall_windows:
            loop.call_at(self.loop_time(start), self.stall)
        for at in self.args.cut_at:
            loop.call_at(self.loop_time(self.started + at), self.cut)

    def loop_time(self, monotonic_at):
        loop = asyncio.get_running_loop()
        return loop.time() + (monotonic_at - time.monotonic())

    def note(self, text):
        elapsed = time.monotonic() - (self.started or time.monotonic())
        print(f"shaper: {elapsed:.1f} s {text}", flush=True)

    def stall(self):
        self.stats["stalls"] += 1
        self.note(f"stall: nothing moves for {self.args.stall_ms} ms")

    def cut(self):
        self.stats["cuts"] += 1
        self.cut_until = time.monotonic() + self.args.cut_ms / 1000.0
        self.note(f"cut {len(self.connections)} connection(s), refusing new ones for {self.args.cut_ms} ms")
        for pair in list(self.connections):
            for writer in pair:
                writer.transport.abort()

    # ── Connections ──

    async def accept(self, reader, writer):
        self.begin()
        if self.cut_until is not None and time.monotonic() < self.cut_until:
            self.stats["refused"] += 1
            writer.transport.abort()
            return
        try:
            up_reader, up_writer = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), 10)
        except (OSError, asyncio.TimeoutError):
            writer.transport.abort()
            return
        self.stats["connections"] += 1
        pair = (writer, up_writer)
        self.connections.add(pair)
        try:
            await asyncio.gather(self.carry(reader, up_writer, "bytes_up"), self.carry(up_reader, writer, "bytes_down"))
        finally:
            self.connections.discard(pair)
            for w in pair:
                w.transport.abort()

    async def carry(self, reader, writer, counter):
        """One direction: read, stamp, hold, write in order. A bounded queue
        (the reader waits while 256 chunks are held) keeps a stall's backlog
        to what the peer's own window lets through."""
        queue = asyncio.Queue(maxsize=256)

        async def read():
            last = 0.0
            try:
                while True:
                    data = await reader.read(CHUNK)
                    if not data:
                        break
                    now = time.monotonic()
                    last = self.release_at(now, last)
                    await queue.put((now, last, data))
            except (ConnectionError, OSError):
                pass
            await queue.put(None)

        async def write():
            while True:
                item = await queue.get()
                if item is None:
                    break
                arrived, at, data = item
                wait = at - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
                if writer.is_closing():
                    break
                writer.write(data)
                self.stats[counter] += len(data)
                self.stats["held_ms_max"] = max(self.stats["held_ms_max"], round((time.monotonic() - arrived) * 1000))
                with contextlib.suppress(ConnectionError, OSError):
                    await writer.drain()
            with contextlib.suppress(OSError, RuntimeError):
                if writer.can_write_eof():
                    writer.write_eof()

        await asyncio.gather(read(), write())

    async def start(self):
        """Listens; returns the port."""
        self.server = await asyncio.start_server(self.accept, self.args.host, self.args.port)
        return self.server.sockets[0].getsockname()[1]

    def close(self):
        """Stops listening and drops every connection."""
        if self.server is not None:
            self.server.close()
        for pair in list(self.connections):
            for writer in pair:
                writer.transport.abort()

    async def run(self):
        port = await self.start()
        print(f"shaper: listening on {self.args.host}:{port} -> {self.args.to}"
              f" · {self.args.delay_ms} ± {self.args.jitter_ms} ms each way"
              + (f" · stalls of {self.args.stall_ms} ms at {self.args.stall_at} s" if self.args.stall_at else "")
              + (f" · cuts of {self.args.cut_ms} ms at {self.args.cut_at} s" if self.args.cut_at else ""), flush=True)
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        if self.args.seconds:
            loop.call_later(self.args.seconds, stop.set)
        await stop.wait()
        self.close()
        print("shaper: " + json.dumps(self.stats), flush=True)


def seconds_list(text):
    return [float(part) for part in text.split(",") if part.strip()] if text else []


def parser():
    parser = argparse.ArgumentParser(description="A TCP proxy that delays, stalls and cuts one game's link")
    parser.add_argument("--to", required=True, help="the server, HOST:PORT")
    parser.add_argument("--host", default="127.0.0.1", help="where to listen (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=0, help="the port to listen on (default 0: any free one)")
    parser.add_argument("--delay-ms", type=int, default=150, help="one-way delay each way (default 150)")
    parser.add_argument("--jitter-ms", type=int, default=50, help="± this much more or less (default 50)")
    parser.add_argument("--stall-at", type=seconds_list, default=[],
                        help="seconds after the first connection at which nothing moves (comma separated)")
    parser.add_argument("--stall-ms", type=int, default=3000, help="how long each stall lasts (default 3000)")
    parser.add_argument("--cut-at", type=seconds_list, default=[],
                        help="seconds after the first connection at which every link is cut (comma separated)")
    parser.add_argument("--cut-ms", type=int, default=5000, help="new connections refused for this long after a cut")
    parser.add_argument("--seed", type=int, default=1, help="the jitter's seed (default 1)")
    parser.add_argument("--seconds", type=float, default=0, help="stop after this long (default: on SIGTERM)")
    return parser


def main(argv=None):
    options = parser()
    args = options.parse_args(argv)
    if args.jitter_ms < 0 or args.delay_ms < 0 or args.stall_ms < 0 or args.cut_ms < 0:
        options.error("times are 0 or more")
    asyncio.run(Shaper(args).run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
