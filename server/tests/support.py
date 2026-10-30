"""The test harness: a minimal game-side client over real sockets and the
clocks the tests drive the turns with. Adapted from Cyberworld Endless's
server/tests/test_server.py (MIT, Sascha Becker): a real server on port 0
and a minimal client, now speaking Groundhold's protocol.
"""

import asyncio
import base64
import hashlib
import heapq
import itertools
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from groundhold_server import protocol, websocket   # noqa: E402
from groundhold_server.app import Server            # noqa: E402
from groundhold_server.protocol import SPEC         # noqa: E402

MS = 1_000_000
RULES = bytes.fromhex("1a2b3c4d5e6f7081")
TICK0 = bytes.fromhex("0011223344556677")


def masked(data, opcode=2, mask=b"test"):
    """A client's frame: masked, as RFC 6455 requires of it."""
    if len(data) < 126:
        header = bytes((0x80 | opcode, 0x80 | len(data)))
    else:
        header = struct.pack("!BBH", 0x80 | opcode, 254, len(data))
    return header + mask + bytes(value ^ mask[i % 4] for i, value in enumerate(data))


def hello(name="Tamsin", token=None, version=None, flags=0, rules_hash=RULES, build_seq=7):
    return protocol.encode("HELLO", version=SPEC["version"] if version is None else version, build_seq=build_seq,
                           rules_hash=rules_hash, token=token or bytes(range(1, 17)), flags=flags, name=name)


def upgrade_request(path=None, subprotocol=None, origin=None, key=b"0123456789abcdef"):
    lines = ["GET " + (path or SPEC["path"]) + " HTTP/1.1", "Host: localhost", "Upgrade: websocket",
             "Connection: Upgrade", "Sec-WebSocket-Version: 13",
             "Sec-WebSocket-Key: " + base64.b64encode(key).decode()]
    if subprotocol is not False:
        lines.append("Sec-WebSocket-Protocol: " + (subprotocol or SPEC["subprotocol"]))
    if origin:
        lines.append("Origin: " + origin)
    return ("\r\n".join(lines) + "\r\n\r\n").encode()


class Client:
    """A game, as far as the wire goes. `sent` and `received` keep every
    message payload in order (the golden transcripts are made of them)."""

    def __init__(self, record=None, index=0):
        self.record, self.index = record, index

    async def open(self, port, subprotocol=None, origin=None):
        self.reader, self.writer = await asyncio.open_connection("127.0.0.1", port)
        key = b"0123456789abcdef"
        self.writer.write(upgrade_request(subprotocol=subprotocol, origin=origin, key=key))
        response = await asyncio.wait_for(self.reader.readuntil(b"\r\n\r\n"), 2)
        assert response.startswith(b"HTTP/1.1 101"), response
        accept = base64.b64encode(hashlib.sha1((base64.b64encode(key).decode() + websocket.GUID).encode()).digest())
        assert accept in response
        self.protocol = next(line.split(":", 1)[1].strip() for line in response.decode().split("\r\n")
                             if line.lower().startswith("sec-websocket-protocol:"))
        return self

    async def hello(self, port, name="Tamsin", **options):
        """Open, say HELLO, and return the answer (WELCOME or ERROR) decoded."""
        await self.open(port, subprotocol=options.pop("subprotocol", None))
        await self.send(hello(name, **options))
        return await self.next()

    async def send(self, data):
        if self.record is not None:
            self.record.append((0, self.index, data))
        self.writer.write(masked(data))
        await self.writer.drain()

    async def send_message(self, kind, /, **fields):
        await self.send(protocol.encode(kind, **fields))

    async def raw(self, timeout=2):
        """The next frame's payload, a close frame's too."""
        first, size = await asyncio.wait_for(self.reader.readexactly(2), timeout)
        assert first in (0x82, 0x88, 0x8a) and not size & 0x80, (first, size)
        if size == 126:
            size = struct.unpack("!H", await self.reader.readexactly(2))[0]
        data = await self.reader.readexactly(size)
        if first == 0x88:
            return None
        if self.record is not None:
            self.record.append((1, self.index, data))
        return data

    async def next(self, timeout=2):
        """The next message, decoded: (name, fields); ("CLOSE", None) for a close frame."""
        data = await self.raw(timeout)
        if data is None:
            return "CLOSE", None
        return protocol.decode(data)

    async def until(self, name, timeout=2, skip=()):
        """Messages up to the first `name`; any other than `skip` fails."""
        deadline = time.monotonic() + timeout
        while True:
            got, fields = await self.next(max(0.01, deadline - time.monotonic()))
            if got == name:
                return fields
            assert got in skip, f"expected {name}, got {got} {fields}"

    async def quiet(self, wait=0.05):
        """Nothing arrives for `wait` seconds."""
        try:
            data = await asyncio.wait_for(self.reader.readexactly(1), wait)
        except asyncio.TimeoutError:
            return True
        raise AssertionError(f"unexpected bytes {data!r}")

    async def bye(self):
        if not self.writer.is_closing():
            try:
                await self.send(protocol.encode("BYE"))
            except ConnectionError:
                pass
        await self.drop()

    async def drop(self):
        """The link gone without a word."""
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except ConnectionError:
            pass


class ManualClock:
    """A clock the test moves by hand (§7.1 level 2's fake clock). Sleepers
    wake when it passes their deadline; `advance` moves it at once, so a
    jump of more than a turn is a stalled loop."""

    def __init__(self, start=10 ** 12):
        self.time = start
        self.sleepers = []
        self.count = itertools.count()

    def now(self):
        return self.time

    async def sleep_until(self, deadline):
        if deadline <= self.time:
            await asyncio.sleep(0)
            return
        future = asyncio.get_running_loop().create_future()
        heapq.heappush(self.sleepers, (deadline, next(self.count), future))
        await future

    async def settle(self):
        for _ in range(10):
            await asyncio.sleep(0)

    async def advance(self, ms):
        self.time += int(ms * MS)
        while self.sleepers and self.sleepers[0][0] <= self.time:
            _, _, future = heapq.heappop(self.sleepers)
            if not future.done():
                future.set_result(None)
        await self.settle()

    async def turns(self, count):
        """`count` turns, each its own wake (no stall)."""
        for _ in range(count):
            await self.advance(SPEC["turn_ms"])


async def start_match(clock, clients, tick0=TICK0):
    """Through the barrier on a ManualClock: MATCH_CONFIG, LOADED from each
    client, the loading minimum, START, and on to the moment turn 0 opens.
    Returns each client's MATCH_CONFIG."""
    configs = []
    for client in clients:
        configs.append(await client.until("MATCH_CONFIG"))
        await client.send_message("LOADED", rules_hash=configs[-1]["rules_hash"], tick0_hash=tick0)
    await clock.advance(SPEC["loading_min_ms"] if len(clients) > 1 else 0)
    for client in clients:
        await client.until("START", skip=("LOAD_STATE",))
    await clock.advance(SPEC["start_delay_ms"])
    return configs


async def until(condition, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("Condition not reached")
        await asyncio.sleep(0.005)


def server(**options):
    """A server as the tests want it: no browser origins, a fixed key, seed and names."""
    defaults = dict(name="Test Shore", motd="Hold the road", origins=("https://saschb2b.github.io",),
                    identity_key=b"k" * 32, seed=20261029)
    return Server(**dict(defaults, **options))


# -- the hub (M3): parties, the barrier, back to the party

MODES = {name: spec["id"] for name, spec in SPEC["modes"].items()}
BUILDERS = SPEC["builders"]
PHASES = SPEC["party_phases"]
MEMBER = SPEC["member_states"]
NOTICES = SPEC["notices"]
LOAD = SPEC["load_states"]


def hub(**options):
    """A server with a hub (no dev match), its party codes from a seeded
    random, so a test knows the codes it will get."""
    import random
    options.setdefault("code_rng", random.Random(3))
    return server(**options)


class HubTest:
    """A mixin for IsolatedAsyncioTestCase: a hub server on a ManualClock,
    and games that join it."""

    async def asyncSetUp(self):
        self.clock = ManualClock()
        self.clients = []
        self.server = None

    async def asyncTearDown(self):
        for client in self.clients:
            await client.drop()
        if self.server:
            await self.server.close()

    async def start(self, **options):
        options.setdefault("clock", self.clock)
        self.server = hub(**options)
        self.port = await self.server.start("127.0.0.1", 0)
        return self.server

    async def join(self, name, number, **options):
        """A game in the hub: HELLO with token `number` × 16, WELCOME."""
        client = Client()
        self.clients.append(client)
        answer = await client.hello(self.port, name, token=bytes((number,)) * 16, **options)
        assert answer[0] == "WELCOME", answer
        client.welcome = answer[1]
        return client

    async def party_of(self, *names, mode="high_water"):
        """A party: the first creates it, the others join by its code; every
        game has read every PARTY_STATE so far. Returns (clients, code)."""
        clients = [await self.join(name, index + 1) for index, name in enumerate(names)]
        await party(clients[0], "create", mode=MODES[mode])
        code = (await state(clients[0]))["code"]
        for index, client in enumerate(clients[1:], start=1):
            await party(client, "join", code=code)
            for earlier in clients[:index + 1]:
                await state(earlier)
        return clients, code

    async def everyone(self, clients, name="PARTY_STATE", skip=("PONG",)):
        return [await client.until(name, skip=skip) for client in clients]

    async def ready_all(self, clients):
        """Every member but the leader Ready, every state read."""
        for client in clients[1:]:
            await party(client, "ready", on=1)
            await self.everyone(clients)

    async def to_loading(self, clients):
        """Start, the 3 s countdown, MATCH_CONFIG to each: their configs."""
        await party(clients[0], "start")
        await self.everyone(clients)
        await self.clock.advance(3000)
        loading = await self.everyone(clients)
        assert loading[0]["phase"] == PHASES["loading"], loading[0]
        return await self.everyone(clients, "MATCH_CONFIG")

    def match(self):
        return next(iter(self.server.matches.values()))


async def party(client, op, **fields):
    await client.send_message("PARTY", op=op, **fields)


async def state(client, skip=("PONG",)):
    """The next PARTY_STATE (PONGs let pass)."""
    return await client.until("PARTY_STATE", skip=skip)


def states(fields):
    """A PARTY_STATE's members as {name: state number}."""
    return {member["name"]: member["state"] for member in fields["members"]}
