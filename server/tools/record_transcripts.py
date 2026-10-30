#!/usr/bin/env python3
"""Record the golden byte transcripts in shared/net/transcripts/ (docs/design/core-loop.md §7.4).

Each transcript is a scripted session against the real server on a hand-moved
clock, so it comes out byte for byte the same every time: re-recording is a
deliberate step, reviewed like any other change. The GDScript codec decodes
every record into the values its .json beside it lists and encodes those
values back into the same bytes.

  m1_handshake   HELLO and WELCOME, PING and PONG, BYE; the refusals (errors 2, 17, 5, 9)
  m1_dev_match   a whole --dev-match classic:2: MATCH_CONFIG, the loading barrier, START,
                 turns with every command type, TURN_REQUEST, HASH, LINKS, AWAY, BACK,
                 LEFT, TIMEOUT, RESULT, MATCH_END, BYE
  m1_codec       every message of protocol.json once (each PARTY op, each command type),
                 encoded by server/groundhold_server/protocol.py with canonical values
  m3_party       the hub: a party created and joined by a lenient code, a wrong code, another
                 rules hash, Builders, Ready, a refused start, a removal, mode and team, open
                 seats, QUEUE answered idle, the countdown, its cancel, MATCH_CONFIG
  m3_barrier     a party's loading barrier: progress, Slow at 15 s, the leader's start without
                 the slow seat at 30 s, AWAY in turn 0 and BACK on its LOADED
  m3_back        a party's match to its end and back: a member who left mid-match, RESULT,
                 MATCH_END, the results plate, LEAVE_MATCH and Ready back to forming; a drop
                 held and taken back by a resume HELLO; a hold that runs out after 40 s

The .bin format (all big-endian): "GHTX", u8 format (1), u16 protocol version,
u8 clients, u32 records; then each record: u8 direction (0 game to server,
1 server to game), u8 client, u16 length, the message (no WebSocket framing).
The .json lists the same records decoded: {"dir", "client", "type", "fields"},
fixed bytes and blobs as lowercase hex, lists as arrays, PARTY's op by name.

  python3 server/tools/record_transcripts.py            # rewrite shared/net/transcripts/
  python3 server/tools/record_transcripts.py --check    # fail if they would change
"""

import argparse
import asyncio
import json
from pathlib import Path
import random
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server" / "tests"))

from support import Client, ManualClock, server, start_match, until   # noqa: E402
from groundhold_server import protocol                                    # noqa: E402
from groundhold_server.protocol import SPEC                               # noqa: E402

TRANSCRIPTS = ROOT / "shared" / "net" / "transcripts"
MAGIC = b"GHTX"
FORMAT = 1
RULES = bytes.fromhex("47726f756e646831")  # "Groundh1"
TICK0 = bytes.fromhex("9e3779b97f4a7c15")
HASH_60 = bytes.fromhex("0123456789abcdef")
FINAL = bytes.fromhex("fedcba9876543210")
TAMSIN = bytes(range(1, 17))
EDDA = bytes(range(17, 33))
COMMAND = protocol.COMMAND


def options():
    """The server every transcript is recorded against: fixed name, key and seed."""
    return dict(name="Groundhold", motd="Hold the road together", identity_key=bytes(range(32)), seed=20261029)


async def handshake(record):
    clock = ManualClock()
    game = server(clock=clock, **options())
    port = await game.start("127.0.0.1", 0)
    try:
        tamsin = Client(record, 0)
        await tamsin.hello(port, "Tamsin", token=TAMSIN, build_seq=7, rules_hash=RULES)
        await tamsin.send_message("PING", client_ms=1000, rtt_ms=0)
        await tamsin.until("PONG")
        await tamsin.send_message("VISIBILITY", hidden=1)
        await tamsin.bye()
        refusals = ((dict(name="Old", version=0, subprotocol="groundhold.v0"), 1),
                    (dict(name="New", version=2, subprotocol="groundhold.v2"), 2),
                    (dict(name="bad<name>"), 3),
                    (dict(name="Zero", token=bytes(16)), 4))
        for hello, index in refusals:
            client = Client(record, index)
            name = hello.pop("name")
            hello.setdefault("token", bytes((index,)) * 16)
            answer = await client.hello(port, name, rules_hash=RULES, **hello)
            assert answer[0] == "ERROR", answer
            await client.drop()
    finally:
        await game.close()
    return 5


async def dev_match(record):
    clock = ManualClock()
    game = server(clock=clock, dev_match="classic:2", match_cap_ms=6500, **options())
    port = await game.start("127.0.0.1", 0)
    tamsin, edda = Client(record, 0), Client(record, 1)
    both = (tamsin, edda)

    async def each(name, clients=both, skip=()):
        return [await client.until(name, skip=skip) for client in clients]

    async def arrived(count, system=0):
        match = next(iter(game.matches.values()))
        await until(lambda: len(match.sequencer.pending) == count and len(match.sequencer.system) == system)

    async def turns(count, clients=both):
        for _ in range(count):
            await clock.turns(1)
            for client in clients:
                await client.until("TURN", skip=("LINKS",))

    try:
        await tamsin.hello(port, "Tamsin", token=TAMSIN, build_seq=7, rules_hash=RULES)
        await edda.hello(port, "Edda", token=EDDA, build_seq=7, rules_hash=RULES)
        await each("MATCH_CONFIG")
        await each("LOAD_STATE")
        await tamsin.send_message("LOADING", per_mille=400)
        await each("LOAD_STATE")
        await edda.send_message("LOADING", per_mille=1000)
        await each("LOAD_STATE")
        await tamsin.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        await each("LOAD_STATE")
        await edda.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        await each("LOAD_STATE")
        await each("LOAD_STATE")
        await clock.advance(SPEC["loading_min_ms"])
        await each("START")
        await clock.advance(SPEC["start_delay_ms"])
        # Turn 0: a tower each. Turn 1: seat 1 leads the rotation.
        await tamsin.send_message("CMD", seq=1, type=COMMAND["BUILD"], a=0, b=8, c=3)
        await edda.send_message("CMD", seq=1, type=COMMAND["BUILD"], a=1, b=10, c=8)
        await arrived(2)
        await turns(1)
        await tamsin.send_message("CMD", seq=2, type=COMMAND["READY"], a=1, b=0, c=0)
        await edda.send_message("CMD", seq=2, type=COMMAND["SIGNAL"], a=8500, b=3500, c=0)
        await arrived(2)
        await turns(1)
        # Turn 2: every other command type (the simulation refuses what its mode lacks).
        await tamsin.send_message("CMD", seq=3, type=COMMAND["FORK"], a=1, b=0, c=0)
        await tamsin.send_message("CMD", seq=4, type=COMMAND["SELL"], a=2, b=0, c=0)
        await edda.send_message("CMD", seq=3, type=COMMAND["CORK"], a=1, b=0x12345678, c=-1)
        await edda.send_message("CMD", seq=4, type=COMMAND["UNCORK"], a=0, b=-2147483648, c=2147483647)
        await edda.send_message("CMD", seq=5, type=COMMAND["SEAWALL"], a=0, b=0, c=0)
        await arrived(5)
        await turns(1)
        await tamsin.send_message("PING", client_ms=1234, rtt_ms=12)
        await tamsin.until("PONG")
        await tamsin.send_message("TURN_REQUEST", first_missing=1)
        await tamsin.until("TURN")
        await tamsin.until("TURN")
        # Tick 60's hash, once turn 19 is sealed; then Edda's tab goes to the background.
        await turns(17)
        for client in both:
            await client.send_message("HASH", tick=60, hash=HASH_60, flags=0)
        await edda.send_message("VISIBILITY", hidden=1)
        # (read by the server before the clock moves on: her silence counts from here)
        match = next(iter(game.matches.values()))
        await until(lambda: match.seats[1].player.hidden and 60 in match.agreed)
        await turns(20)
        for _ in range(2):
            await tamsin.send_message("PING", client_ms=5000, rtt_ms=12)
            await tamsin.until("PONG")
            await turns(40)
        # Five seconds without a word from Edda: AWAY. She speaks: BACK. She leaves: LEFT.
        await tamsin.send_message("PING", client_ms=7000, rtt_ms=12)
        await tamsin.until("PONG")
        await edda.send_message("PING", client_ms=900, rtt_ms=0)
        await edda.until("PONG")
        await edda.send_message("VISIBILITY", hidden=0)
        await arrived(0, 1)
        await turns(1)
        await edda.send_message("LEAVE_MATCH")
        await arrived(0, 1)
        await turns(10, (tamsin,))
        # TIMEOUT in turn 130 (match_cap_ms 6500): the simulation ends, the result is agreed.
        await tamsin.send_message("RESULT", tick=390, hash=FINAL, outcomes=[dict(outcome=SPEC["outcomes"]["lost"])])
        await tamsin.until("MATCH_END")
        await tamsin.bye()
        await edda.bye()
    finally:
        await game.close()
    return 2


OTTILIE = bytes(range(33, 49))
SEFA = bytes(range(49, 65))
OLDER = bytes.fromhex("47726f756e646830")   # "Groundh0": an older build's rules
MODE = {name: spec["id"] for name, spec in SPEC["modes"].items()}
BUILDER = SPEC["builders"]


def hub_options():
    """A hub server (no dev match), its party codes from a seeded random."""
    return dict(options(), code_rng=random.Random(20261030))


async def each(name, clients, skip=()):
    return [await client.until(name, skip=skip) for client in clients]


async def party_flow(record):
    clock = ManualClock()
    game = server(clock=clock, **hub_options())
    port = await game.start("127.0.0.1", 0)
    tamsin, edda, ottilie = Client(record, 0), Client(record, 1), Client(record, 2)
    both = (tamsin, edda)
    try:
        await tamsin.hello(port, "Tamsin", token=TAMSIN, build_seq=8, rules_hash=RULES)
        await tamsin.send_message("PARTY", op="create", mode=MODE["high_water"])
        code = (await tamsin.until("PARTY_STATE"))["code"]
        await edda.hello(port, "Edda", token=EDDA, build_seq=8, rules_hash=RULES)
        await edda.send_message("PARTY", op="join", code=b"ZZZZZ")
        await edda.until("NOTICE")
        # (typed in lower case: the server reads a code leniently)
        await edda.send_message("PARTY", op="join", code=code.lower())
        await each("PARTY_STATE", both)
        await edda.send_message("PARTY", op="builders", main=BUILDER["lookout"], backup=BUILDER["lamplighter"])
        await each("PARTY_STATE", both)
        # (an older build: it needs to reload, and the party cannot start)
        await ottilie.hello(port, "Ottilie", token=OTTILIE, build_seq=7, rules_hash=OLDER)
        await ottilie.send_message("PARTY", op="join", code=code)
        await ottilie.until("NOTICE")
        await each("PARTY_STATE", (tamsin, edda, ottilie))
        await edda.send_message("PARTY", op="ready", on=1)
        await each("PARTY_STATE", (tamsin, edda, ottilie))
        await tamsin.send_message("PARTY", op="start")
        await tamsin.until("PARTY_STATE")
        await tamsin.send_message("PARTY", op="remove", member=2)
        await ottilie.until("NOTICE")
        await ottilie.until("PARTY_STATE")
        await each("PARTY_STATE", both)
        await ottilie.send_message("PARTY", op="join", code=code)
        await ottilie.until("NOTICE")
        await ottilie.bye()
        # (mode, then a Race's teams, then back: every change clears Ready)
        await tamsin.send_message("PARTY", op="mode", mode=MODE["tide_race"])
        await each("PARTY_STATE", both)
        await tamsin.send_message("PARTY", op="team", member=1, team=0)
        await each("PARTY_STATE", both)
        await tamsin.send_message("PARTY", op="mode", mode=MODE["high_water"])
        await each("PARTY_STATE", both)
        await tamsin.send_message("PARTY", op="open", on=1)
        await each("PARTY_STATE", both)
        await tamsin.send_message("QUEUE", op=SPEC["queue_ops"]["enter"])
        await tamsin.until("QUEUE_STATE")
        await edda.send_message("PARTY", op="ready", on=1)
        await each("PARTY_STATE", both)
        await tamsin.send_message("PARTY", op="start")
        await each("PARTY_STATE", both)
        await clock.advance(1000)
        await edda.send_message("PARTY", op="cancel")
        await each("PARTY_STATE", both)
        await tamsin.send_message("PARTY", op="start")
        await each("PARTY_STATE", both)
        await clock.advance(3000)
        await each("PARTY_STATE", both)
        await each("MATCH_CONFIG", both)
        await each("LOAD_STATE", both)
        await tamsin.bye()
        await edda.bye()
    finally:
        await game.close()
    return 3


async def party_of_two(clock, port, tamsin, edda):
    """Tamsin's party with Edda Ready, through the countdown to MATCH_CONFIG."""
    both = (tamsin, edda)
    await tamsin.hello(port, "Tamsin", token=TAMSIN, build_seq=8, rules_hash=RULES)
    await tamsin.send_message("PARTY", op="create", mode=MODE["high_water"])
    code = (await tamsin.until("PARTY_STATE"))["code"]
    await edda.hello(port, "Edda", token=EDDA, build_seq=8, rules_hash=RULES)
    await edda.send_message("PARTY", op="join", code=code)
    await each("PARTY_STATE", both)
    await edda.send_message("PARTY", op="builders", main=BUILDER["lookout"], backup=BUILDER["lamplighter"])
    await each("PARTY_STATE", both)
    await edda.send_message("PARTY", op="ready", on=1)
    await each("PARTY_STATE", both)
    await tamsin.send_message("PARTY", op="start")
    await each("PARTY_STATE", both)
    await clock.advance(3000)
    await each("PARTY_STATE", both)
    await each("MATCH_CONFIG", both)
    await each("LOAD_STATE", both)
    return code


async def barrier(record):
    clock = ManualClock()
    game = server(clock=clock, **hub_options())
    port = await game.start("127.0.0.1", 0)
    tamsin, edda = Client(record, 0), Client(record, 1)
    both = (tamsin, edda)
    try:
        await party_of_two(clock, port, tamsin, edda)
        await tamsin.send_message("LOADING", per_mille=500)
        await each("LOAD_STATE", both)
        await tamsin.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        await each("LOAD_STATE", both)
        await edda.send_message("LOADING", per_mille=250)
        await each("LOAD_STATE", both)
        # (15 s: Edda is slow; her progress keeps her slow)
        await clock.advance(15_000)
        await each("LOAD_STATE", both)
        await edda.send_message("LOADING", per_mille=400)
        await each("LOAD_STATE", both)
        # (30 s: the leader may start without her)
        await clock.advance(15_000)
        await each("LOAD_STATE", both)
        await tamsin.send_message("PARTY", op="start")
        await each("LOAD_STATE", both)
        await each("START", both)
        await each("PARTY_STATE", both)
        await clock.advance(SPEC["start_delay_ms"])
        await clock.turns(1)
        await each("TURN", both)
        # (her LOADED, with the same hashes, hands her seat BACK)
        await edda.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        match = next(iter(game.matches.values()))
        await until(lambda: match.seats[1].state == "present")
        await clock.turns(1)
        await each("TURN", both)
        await tamsin.bye()
        await edda.bye()
    finally:
        await game.close()
    return 2


async def back_to_party(record):
    clock = ManualClock()
    game = server(clock=clock, **hub_options())
    port = await game.start("127.0.0.1", 0)
    tamsin, edda, ottilie, again = Client(record, 0), Client(record, 1), Client(record, 2), Client(record, 3)
    three = (tamsin, edda, ottilie)
    try:
        code = await party_of_two(clock, port, tamsin, edda)
        # (the two load; Ottilie joins the party while they play and waits in the hub)
        for client in (tamsin, edda):
            await client.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
            await each("LOAD_STATE", (tamsin, edda))
        await each("LOAD_STATE", (tamsin, edda))
        await clock.advance(SPEC["loading_min_ms"])
        await each("START", (tamsin, edda))
        await each("PARTY_STATE", (tamsin, edda))
        await ottilie.hello(port, "Ottilie", token=OTTILIE, build_seq=8, rules_hash=RULES)
        await ottilie.send_message("PARTY", op="join", code=code)
        await each("PARTY_STATE", three)
        await clock.advance(SPEC["start_delay_ms"])
        await clock.turns(2)
        for client in (tamsin, edda):
            await client.until("TURN")
            await client.until("TURN")
        # (both report the end: the match ends with their result, and the
        # party shows the results plate)
        for client in (tamsin, edda):
            await client.send_message("RESULT", tick=6, hash=FINAL, outcomes=[dict(outcome=SPEC["outcomes"]["won"])])
        await each("MATCH_END", (tamsin, edda))
        await each("PARTY_STATE", three)
        # (Play again: LEAVE_MATCH; a Ready from the plate brings its member back too)
        await tamsin.send_message("LEAVE_MATCH")
        await each("PARTY_STATE", three)
        await edda.send_message("PARTY", op="ready", on=1)
        await each("PARTY_STATE", three)
        # (Edda's link drops: her row is held; her game comes back with the resume bit)
        await edda.drop()
        await each("PARTY_STATE", (tamsin, ottilie))
        await clock.advance(20_000)
        await again.hello(port, "Edda", token=EDDA, build_seq=8, rules_hash=RULES, flags=SPEC["hello_flags"]["resume"])
        await each("PARTY_STATE", (tamsin, ottilie, again))
        # (Ottilie's drops and stays gone: 40 s later her row is free)
        await ottilie.drop()
        await each("PARTY_STATE", (tamsin, again))
        await clock.advance(40_000)
        await each("PARTY_STATE", (tamsin, again))
        await tamsin.bye()
        await again.bye()
    finally:
        await game.close()
    return 4


def codec_records():
    """Every message once, with canonical values (and each PARTY op, each command type)."""
    rules, token, identity = RULES, TAMSIN, bytes(range(16, 32))
    commands = [dict(seq=seq, type=spec["type"], a=spec["args"][0][1], b=spec["args"][1][0], c=spec["args"][2][1])
                for seq, spec in enumerate(SPEC["commands"].values(), start=1)]
    party = [dict(op="create", mode=1), dict(op="join", code=b"K7Q4M"), dict(op="leave"), dict(op="remove", member=2),
             dict(op="mode", mode=2), dict(op="builders", main=0, backup=1), dict(op="ready", on=1),
             dict(op="team", member=3, team=1), dict(op="open", on=1), dict(op="start"), dict(op="cancel")]
    member = dict(member=0, team=0, main=0, backup=1, state=1, rtt_ms=38, build_seq=7, rules_hash=rules, name="Tamsin")
    seats = [dict(seat=i, team=i // 2, builder=i, flags=1 if i == 3 else 0, name=name)
             for i, name in enumerate(("Tamsin", "Edda", "Ottilie", "Sefa"))]
    system = [dict(seat=SPEC["system_seat"], seq=i + 1, type=spec["type"], a=1 if name != "TIMEOUT" else 0, b=0, c=0)
              for i, (name, spec) in enumerate(SPEC["system_commands"].items())]
    stamped = [dict(seat=1, seq=c["seq"], type=c["type"], a=c["a"], b=c["b"], c=c["c"]) for c in commands]
    records = [
        ("HELLO", dict(version=1, build_seq=0xffffffff, rules_hash=rules, token=token, flags=3, name="Tamsin Wick")),
        ("WELCOME", dict(session=1, identity=identity, turn_ms=50, turn_ticks=3, hash_every=60, flags=2,
                         server_name="Groundhold", motd="Hüte den Grund bis zur Ebbe")),
        ("ERROR", dict(code=2, text="A newer version is out: reload")),
        ("PING", dict(client_ms=0xffffffff, rtt_ms=0xffff)),
        ("PONG", dict(client_ms=123456, turn=72000)),
        ("NOTICE", dict(code=7, argument=255)),
        ("BYE", {}),
        *[("PARTY", op) for op in party],
        ("PARTY_STATE", dict(code=b"K7Q4M", mode=1, flags=1, leader=0, you=1, phase=1, countdown_ms=3000,
                             members=[member, dict(member, member=1, team=0, main=1, backup=0, state=3, rtt_ms=0,
                                                   build_seq=6, rules_hash=bytes(8), name="Edda")])),
        *[("QUEUE", dict(op=value)) for value in SPEC["queue_ops"].values()],
        ("QUEUE_STATE", dict(state=2, elapsed_ms=61000, caretaker_offer=1)),
        ("MATCH_FOUND", dict(match=9, mode=2, seats=4, accepted=3, ms_left=15000)),
        ("ACCEPT", dict(match=9, yes=1)),
        ("MATCH_CONFIG", dict(match=9, mode=2, map=0, seed=0xdeadbeef, rules_hash=rules, your_seat=2, seats=seats)),
        ("LOADING", dict(per_mille=750)),
        ("LOAD_STATE", dict(seats=[dict(seat=i, per_mille=pm, state=state) for i, (pm, state) in
                                   enumerate(((1000, 3), (1000, 2), (420, 1), (0, 4)))], seconds=16)),
        ("LOADED", dict(rules_hash=rules, tick0_hash=TICK0)),
        ("START", dict(ms_until_turn0=1500)),
        *[("CMD", command) for command in commands],
        ("TURN", dict(turn=0, commands=[])),
        ("TURN", dict(turn=0xffffffff, commands=system + stamped)),
        ("HASH", dict(tick=1800, hash=HASH_60, flags=1)),
        ("CHECKPOINT_ASK", dict(tick=1800)),
        ("CHECKPOINT_PART", dict(tick=1800, part=0, parts=2, data=bytes(range(256)) * 4)),
        ("CHECKPOINT_PART", dict(tick=1800, part=1, parts=2, data=b"\x00\xff")),
        ("RESYNC", dict(checkpoint_tick=1800, first_turn=600)),
        ("TURN_REQUEST", dict(first_missing=600)),
        ("VISIBILITY", dict(hidden=1)),
        ("RESULT", dict(tick=43200, hash=FINAL, outcomes=[dict(outcome=0), dict(outcome=1)])),
        ("MATCH_END", dict(outcome=3, reason=1, final_tick=1860)),
        ("LEAVE_MATCH", {}),
        ("LINKS", dict(seats=[dict(seat=0, rtt_ms=38, flags=0), dict(seat=1, rtt_ms=0, flags=3)])),
    ]
    out = []
    for name, fields in records:
        direction = protocol.MESSAGES[name].dir
        data = protocol.encode(name, **fields)
        for side in ((0, 1) if direction == "both" else (0 if direction == "c2s" else 1,)):
            out.append((side, 0, data))
    return out


def plain(value):
    """A decoded value as the .json keeps it: bytes as hex, lists and dicts within."""
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, list):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    return value


def write(directory, name, records, clients, note):
    body = bytearray(MAGIC + struct.pack("!BHBI", FORMAT, SPEC["version"], clients, len(records)))
    listed = []
    for direction, client, data in records:
        body += struct.pack("!BBH", direction, client, len(data)) + data
        kind, fields = protocol.decode(data)
        listed.append({"dir": "c2s" if direction == 0 else "s2c", "client": client, "type": kind, "fields": plain(fields)})
    (directory / (name + ".bin")).write_bytes(bytes(body))
    text = json.dumps({"transcript": name, "format": FORMAT, "protocol": SPEC["version"], "clients": clients,
                       "note": note, "records": listed}, indent=1, ensure_ascii=False)
    (directory / (name + ".json")).write_text(text + "\n", encoding="utf-8")


def read(path):
    """A .bin's records as (direction, client, data), its header checked."""
    data = path.read_bytes()
    magic, version, protocol_version, clients, count = data[:4], *struct.unpack_from("!BHBI", data, 4)
    if magic != MAGIC or version != FORMAT:
        raise ValueError(f"{path} is not a format {FORMAT} transcript")
    offset, records = 12, []
    for _ in range(count):
        direction, client, length = struct.unpack_from("!BBH", data, offset)
        records.append((direction, client, data[offset + 4:offset + 4 + length]))
        offset += 4 + length
    if offset != len(data):
        raise ValueError(f"{path} has trailing bytes")
    return records


async def record_all(directory):
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    clients = await handshake(records)
    write(directory, "m1_handshake", records, clients,
          "One game's HELLO, WELCOME, PING, PONG, VISIBILITY and BYE; then four refused HELLOs: "
          "an older game (ERROR 2), a newer one (17), a bad name (5), a zero token (9).")
    records = []
    clients = await dev_match(records)
    write(directory, "m1_dev_match", records, clients,
          "A whole --dev-match classic:2 on a hand-moved clock (seed 20261029, match_cap_ms 6500).")
    write(directory, "m1_codec", codec_records(), 1,
          "Every message once with canonical values, as server/groundhold_server/protocol.py encodes it.")
    for name, script, note in (
            ("m3_party", party_flow,
             "The hub on a hand-moved clock (party codes from random.Random(20261030)): Tamsin creates a High "
             "Water party; Edda tries a wrong code, then joins in lower case; Ottilie's older build needs to "
             "reload, the start is refused and she is removed; mode, team, open seats, QUEUE (idle before M6), "
             "Ready, the 3 s countdown, its cancel, and MATCH_CONFIG."),
            ("m3_barrier", barrier,
             "A party's loading barrier: Tamsin loads, Edda is Slow at 15 s, the leader starts without her at "
             "30 s; turn 0 has AWAY for her seat, and her LOADED brings BACK."),
            ("m3_back", back_to_party,
             "A party's match and back: Ottilie waits in the hub, the two players' RESULT ends it, the results "
             "plate, LEAVE_MATCH (Play again) and a Ready back to forming; Edda's link drops and her resume "
             "HELLO takes her row back; Ottilie's drops and her row is freed 40 s later.")):
        records = []
        clients = await script(records)
        write(directory, name, records, clients, note)
    return sorted(path.name for path in directory.iterdir())


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="Fail if re-recording would change a transcript")
    args = parser.parse_args()
    if not args.check:
        for name in asyncio.run(record_all(TRANSCRIPTS)):
            print(TRANSCRIPTS / name)
        return 0
    with tempfile.TemporaryDirectory() as temporary:
        fresh = Path(temporary)
        names = asyncio.run(record_all(fresh))
        changed = [name for name in names if not (TRANSCRIPTS / name).is_file()
                   or (TRANSCRIPTS / name).read_bytes() != (fresh / name).read_bytes()]
    for name in changed:
        print("changed:", name)
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
