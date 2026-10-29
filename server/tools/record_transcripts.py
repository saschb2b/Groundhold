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
        ("PARTY_STATE", dict(code=b"K7Q4M", mode=1, flags=1, leader=0, phase=1, countdown_ms=3000,
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
