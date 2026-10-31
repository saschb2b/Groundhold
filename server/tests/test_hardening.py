"""Hardening (docs/design/core-loop.md §6.5, §6.9, §7.3): malformed frames,
bounded frames, idle sockets, the origin and subprotocol checks, version
refusals, HELLO's checks, rate buckets, silence, the output cap, /health.

Adapted from Cyberworld Endless's server/tests/test_hardening.py and
test_server.py (MIT, Sascha Becker); its moderation and roster cases come
back with identity.py in M3.
"""

import asyncio
import contextlib
import json
from pathlib import Path
import socket
import struct
import sys
import time
import unittest

from support import (MOST_MESSAGES, RULES, Client, ManualClock, masked, server, start_match, until,
                     upgrade_request)
from groundhold_server import protocol
from groundhold_server.protocol import SPEC

ERRORS = SPEC["errors"]


class HardeningTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = None
        self.clients = []
        self.sockets = []

    async def asyncTearDown(self):
        for client in self.clients:
            client.writer.close()
        for _, writer in self.sockets:
            writer.close()
        if self.server:
            await self.server.close()

    async def start(self, **options):
        self.server = server(**options)
        self.port = await self.server.start("127.0.0.1", 0)
        return self.server

    async def connect(self, name="Tamsin", **options):
        client = Client()
        self.clients.append(client)
        return client, await client.hello(self.port, name, **options)

    async def raw_request(self, request, whole=True):
        """The answer to a hand-made request: all of it, or (`whole` False,
        an upgrade the server keeps open) its head."""
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        self.sockets.append((reader, writer))
        writer.write(request)
        await writer.drain()
        if whole:
            return await asyncio.wait_for(reader.read(), 2)
        return await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 2)

    async def test_welcome_says_the_turn_and_who_this_is(self):
        await self.start()
        _, (name, welcome) = await self.connect()
        self.assertEqual(name, "WELCOME")
        self.assertEqual((welcome["session"], welcome["turn_ms"], welcome["turn_ticks"], welcome["hash_every"]),
                         (1, 50, 3, 60))
        self.assertEqual((welcome["server_name"], welcome["motd"], welcome["flags"]), ("Test Shore", "Hold the road", 0))
        _, (_, again) = await self.connect(token=bytes(range(1, 17)))
        _, (_, other) = await self.connect(token=b"\x09" * 16)
        # (one token, one public identity on this server; another token, another)
        self.assertEqual(again["identity"], welcome["identity"])
        self.assertNotEqual(other["identity"], welcome["identity"])
        self.assertEqual(len(welcome["identity"]), 16)

    async def test_versions_say_which_side_is_behind(self):
        await self.start()
        # (another version's subprotocol is let in to hear which side is behind)
        for version, code in ((0, ERRORS["game_older"]), (2, ERRORS["server_older"]), (900, ERRORS["server_older"])):
            client, (name, error) = await self.connect(version=version, subprotocol=f"groundhold.v{version}")
            self.assertEqual(client.protocol, f"groundhold.v{version}")
            self.assertEqual((name, error["code"]), ("ERROR", code))
            self.assertEqual(await client.next(), ("CLOSE", None))
        self.assertFalse(self.server.players)

    async def test_hello_checks_its_token_its_name_and_its_shape(self):
        await self.start(player_cap=2)
        for options, code in ((dict(token=bytes(16)), ERRORS["bad_token"]), (dict(name="bad<script>"), ERRORS["bad_name"]),
                              (dict(name=" lead"), ERRORS["bad_name"]), (dict(name="Ünder"), ERRORS["bad_name"]),
                              (dict(name="a" * 16 + "b"), ERRORS["protocol"]), (dict(flags=4), ERRORS["protocol"])):
            name = options.pop("name", "Tamsin")
            if len(name) > 16:
                client = Client()
                self.clients.append(client)
                await client.open(self.port)
                # (the name's length byte says 17: HELLO's held match and seat follow the name)
                data = protocol.encode("HELLO", version=1, build_seq=1, rules_hash=RULES,
                                       token=b"\x01" * 16, flags=0, name="x", match=0, seat=255)
                await client.send(data[:-7] + bytes((17,)) + name.encode() + data[-5:])
                answer = await client.next()
            else:
                _, answer = await self.connect(name, **options)
            self.assertEqual(answer[0], "ERROR", options)
            self.assertEqual(answer[1]["code"], code, (name, options))
        client = Client()
        self.clients.append(client)
        await client.open(self.port)
        await client.send(protocol.encode("HELLO", version=1, build_seq=1, rules_hash=RULES, token=b"\x01" * 16,
                                          flags=0, name="Tamsin", match=0, seat=255) + b"x")
        self.assertEqual((await client.next())[1]["code"], ERRORS["protocol"])
        self.assertFalse(self.server.players)

    async def test_full_and_maintenance(self):
        await self.start(player_cap=2)
        await self.connect("One")
        await self.connect("Two")
        _, (name, full) = await self.connect("Three")
        self.assertEqual((name, full["code"]), ("ERROR", ERRORS["full"]))
        await self.server.close()
        await self.start(maintenance="until 14:00 UTC")
        _, (name, closed) = await self.connect()
        self.assertEqual((name, closed["code"], closed["text"]), ("ERROR", ERRORS["maintenance"], "until 14:00 UTC"))
        self.assertEqual(self.server.health()["maintenance"], "until 14:00 UTC")
        with self.assertRaises(ValueError):
            protocol.maintenance_line("x" * 41)

    async def test_rejects_unmasked_fragmented_text_and_oversized_frames(self):
        await self.start()
        frames = (b"\x82\x01x",                                  # unmasked
                  b"\x02\x80test",                               # a fragment
                  b"\x81\x80test",                               # text
                  b"\x82\xff",                                   # a 64-bit length
                  b"\x82\xfe\x00\x10",                           # a noncanonical length
                  masked(bytes(SPEC["max_message"] + 1)))        # one byte past max_message
        for frame in frames:
            client, _ = await self.connect()
            client.writer.write(frame)
            await client.writer.drain()
            name, error = await client.next()
            self.assertEqual(name, "ERROR", frame[:4])
            await client.drop()
        # (max_message itself is a frame the server reads: a checkpoint part fits it)
        self.assertLessEqual(len(protocol.encode("CHECKPOINT_PART", tick=0, part=0, parts=1, data=bytes(1024))),
                             SPEC["max_message"])
        client, _ = await self.connect()
        await client.send(protocol.encode("PING", client_ms=1, rtt_ms=0) + bytes(SPEC["max_message"] - 7))
        name, error = await client.next()
        self.assertEqual((name, error["text"]), ("ERROR", "Malformed PING"))

    async def test_a_servers_message_from_a_game_is_refused(self):
        await self.start()
        client, _ = await self.connect()
        await client.send(protocol.encode("START", ms_until_turn0=0))
        name, error = await client.next()
        self.assertEqual((name, error["code"]), ("ERROR", ERRORS["protocol"]))
        client, _ = await self.connect()
        await client.send(bytes((200,)))
        self.assertEqual((await client.next())[0], "ERROR")

    async def test_the_upgrade_checks_path_subprotocol_and_origin(self):
        await self.start()
        for request in (upgrade_request(path="/presence"), upgrade_request(subprotocol=False),
                        upgrade_request(subprotocol="cyberworld.presence.v15"),
                        upgrade_request(origin="https://untrusted.invalid"),
                        b"GET /causeway HTTP/1.1\r\nHost: x\r\n\r\n"):
            self.assertTrue((await self.raw_request(request)).startswith(b"HTTP/1.1 400"), request)
        # (a browser's page on the allowlist, and a native game with no Origin)
        for request in (upgrade_request(origin="https://saschb2b.github.io"), upgrade_request()):
            self.assertTrue((await self.raw_request(request, whole=False)).startswith(b"HTTP/1.1 101"))
        self.assertFalse(self.server.players)

    async def test_godot_native_handshake_is_accepted_with_origins_set(self):
        # (design 6.2: recorded from Godot 4.7.1's native WebSocketPeer, headers
        # in its order; it sends no Origin, so the allowlist never refuses it)
        await self.start()
        native = ("GET /causeway HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n"
                  "Connection: Upgrade\r\nSec-WebSocket-Key: MDEyMzQ1Njc4OWFiY2RlZg==\r\n"
                  "Sec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: groundhold.v1\r\n\r\n")
        self.assertTrue(self.server.origins)
        answer = await self.raw_request(native.format(port=self.port).encode(), whole=False)
        self.assertTrue(answer.startswith(b"HTTP/1.1 101"), answer)
        self.assertIn(b"Sec-WebSocket-Protocol: groundhold.v1", answer)

    async def test_health_answers_on_the_same_port(self):
        await self.start(dev_match="classic:2")
        await self.connect()
        response = await self.raw_request(b"GET /health HTTP/1.1\r\nHost: x\r\n\r\n")
        self.assertTrue(response.startswith(b"HTTP/1.1 200"))
        health = json.loads(response.split(b"\r\n\r\n", 1)[1])
        self.assertEqual(health, {"status": "ok", "protocol": 1, "name": "Test Shore", "motd": "Hold the road",
                                  "players": 1, "player_cap": 64, "matches": 0, "maintenance": None,
                                  "dev_match": "classic:2", "turn_ms": 50})

    async def test_idle_sockets_are_dropped_and_hold_no_place(self):
        server = await self.start(player_cap=2, pending_cap=4, handshake_timeout=0.3)
        flood = []
        for _ in range(20):
            connection = await asyncio.open_connection("127.0.0.1", self.port)
            self.sockets.append(connection)
            flood.append(connection)
        started = time.monotonic()
        for reader, _ in flood:
            try:
                self.assertEqual(await asyncio.wait_for(reader.read(), 2), b"")
            except ConnectionResetError:
                pass
        self.assertLess(time.monotonic() - started, 1.5)
        await until(lambda: not server.pending)
        _, (one, _) = await self.connect("One")
        _, (two, _) = await self.connect("Two")
        self.assertEqual((one, two), ("WELCOME", "WELCOME"))

    async def test_silence_closes_a_connection(self):
        await self.start(silence_timeout=0.2)
        client, _ = await self.connect()
        self.assertEqual(await asyncio.wait_for(client.reader.read(), 2), b"")
        await until(lambda: not self.server.players)

    async def test_ping_pong_and_its_bucket(self):
        await self.start(clock=ManualClock())
        client, _ = await self.connect()
        await client.send_message("PING", client_ms=0xfffffffe, rtt_ms=42)
        self.assertEqual(await client.until("PONG"), {"client_ms": 0xfffffffe, "turn": 0})
        self.assertEqual(self.server.players[1].round_trip, 42)
        # (network traffic: a bucket of 150; the 151st at once is too many)
        client.writer.write(masked(protocol.encode("PING", client_ms=1, rtt_ms=1)) * 160)
        await client.writer.drain()
        error = await client.until("ERROR", skip=("PONG",))
        self.assertEqual(error["code"], ERRORS["rate"])

    async def test_hub_bucket(self):
        await self.start(clock=ManualClock())
        client, _ = await self.connect()
        client.writer.write(masked(b"", opcode=9) * 41)
        await client.writer.drain()
        for _ in range(40):
            self.assertEqual(await client.raw(), b"")      # (a pong each)
        name, error = await client.next()
        self.assertEqual((name, error["code"]), ("ERROR", ERRORS["rate"]))

    async def test_buckets_refill_on_the_servers_clock(self):
        # (a slow machine's wall clock must not refill a bucket mid-burst: the
        # hub bucket refills 30 a second, so a quarter second of wall time
        # would answer the 41st ping; only the server's clock counts)
        clock = ManualClock()
        await self.start(clock=clock)
        client, _ = await self.connect()
        client.writer.write(masked(b"", opcode=9) * 40)
        await client.writer.drain()
        for _ in range(40):
            self.assertEqual(await client.raw(), b"")
        await asyncio.sleep(0.25)
        await clock.advance(100)                            # (3 tokens)
        client.writer.write(masked(b"", opcode=9) * 4)
        await client.writer.drain()
        for _ in range(3):
            self.assertEqual(await client.raw(), b"")
        name, error = await client.next()
        self.assertEqual((name, error["code"]), ("ERROR", ERRORS["rate"]))

    async def test_command_bucket_holds_the_seat(self):
        clock = ManualClock()
        await self.start(dev_match="classic:2", clock=clock)
        one, _ = await self.connect("One")
        two, _ = await self.connect("Two", token=b"\x02" * 16)
        await start_match(clock, (one, two))
        # (commands: a bucket of 10, refilled 5 a second; the 11th at once is too many)
        one.writer.write(b"".join(masked(protocol.encode("CMD", seq=seq, type=4, a=1, b=0, c=0)) for seq in range(11)))
        await one.writer.drain()
        error = await one.until("ERROR", skip=("TURN",))
        self.assertEqual(error["code"], ERRORS["rate"])
        match = next(iter(self.server.matches.values()))
        await until(lambda: match.seats[0].player is None)
        await clock.turns(1)
        turn = await two.until("TURN")
        self.assertEqual([c["seq"] for c in turn["commands"]], list(range(10)))
        self.assertEqual(len(self.server.matches), 1)

    async def test_a_burst_of_turn_requests_costs_one_window_of_turns(self):
        # (review M1 protocol 2: 135 TURN_REQUEST(0) inside every bucket made
        # the server re-send 1,200 turns each, synchronously, and froze every
        # match's turn clock for half a second)
        clock = ManualClock()
        await self.start(dev_match="classic:2", clock=clock)
        one, _ = await self.connect("One")
        two, _ = await self.connect("Two", token=b"\x02" * 16)
        await start_match(clock, (one, two))
        await clock.turns(1200)
        for client in (one, two):
            for number in range(1200):
                self.assertEqual((await client.until("TURN", skip=("LINKS",)))["turn"], number)
        burst = SPEC["buckets"]["net"]["burst"] - 15
        two.writer.write(masked(protocol.encode("TURN_REQUEST", first_missing=0)) * burst
                         + masked(protocol.encode("PING", client_ms=1, rtt_ms=1)))
        await two.writer.drain()
        # (the PONG comes after the server has read the whole burst)
        again = []
        for _ in range(MOST_MESSAGES):
            if (message := await two.next())[0] == "PONG":
                break
            self.assertEqual(message[0], "TURN")
            again.append(message[1]["turn"])
        # The flooder got one window of turns for the whole burst: the rest
        # came too soon after it. And the observer's next turn comes on time.
        window = SPEC["turn_request_turns"]
        self.assertEqual(again, list(range(window)))
        self.assertTrue(await two.quiet())
        await clock.turns(1)
        self.assertEqual((await one.until("TURN", skip=("LINKS",)))["turn"], 1200)
        self.assertEqual((await two.until("TURN", skip=("LINKS",)))["turn"], 1200)
        # Half the game's own asking interval later it is answered again, never
        # below the turns its last HASH says it holds (tick 600: turns 0 to 199).
        for client in (one, two):
            await client.send_message("HASH", tick=600, hash=b"h" * 8, flags=0)
        await clock.advance(SPEC["turn_request_ms"] // 2)
        two.writer.write(masked(protocol.encode("TURN_REQUEST", first_missing=5))
                         + masked(protocol.encode("PING", client_ms=1, rtt_ms=1)))
        await two.writer.drain()
        again = []
        for _ in range(MOST_MESSAGES):
            if (message := await two.next())[0] == "PONG":
                break
            if message[0] == "TURN" and message[1]["turn"] < 1200:
                again.append(message[1]["turn"])
        self.assertEqual(again, list(range(200, 200 + window)))
        match = next(iter(self.server.matches.values()))
        self.assertEqual([seat.player is not None for seat in match.seats], [True, True])

    async def test_hash_flags_are_bounded(self):
        clock = ManualClock()
        await self.start(dev_match="classic:2", clock=clock)
        one, _ = await self.connect("One")
        two, _ = await self.connect("Two", token=b"\x02" * 16)
        await start_match(clock, (one, two))
        await clock.turns(20)
        await one.send_message("HASH", tick=60, hash=b"h" * 8, flags=0x80)
        error = await one.until("ERROR", skip=("TURN",))
        self.assertEqual(error["code"], ERRORS["out_of_limits"])

    async def test_a_refused_game_reads_error_before_the_close(self):
        # (review M1 feel 3: the close frame and a reset right behind ERROR 8
        # took it away unread, and the player saw only "The connection closed")
        clock = ManualClock()
        await self.start(dev_match="classic:2", clock=clock)
        one, _ = await self.connect("One")
        two, _ = await self.connect("Two", token=b"\x02" * 16)
        await start_match(clock, (one, two))
        one.writer.write(b"".join(masked(protocol.encode("CMD", seq=seq, type=4, a=1, b=0, c=0)) for seq in range(14)))
        await one.writer.drain()
        error = await one.until("ERROR", skip=("TURN",))
        self.assertEqual(error["code"], ERRORS["rate"])
        # The seat is let go at once, but the connection waits for the game to
        # close (it keeps reading and dropping what still comes) ...
        match = next(iter(self.server.matches.values()))
        await until(lambda: match.seats[0].player is None)
        await one.send_message("PING", client_ms=1, rtt_ms=1)
        self.assertTrue(await one.quiet(0.3))
        # ... and closes when the game does.
        one.writer.write(masked(struct.pack("!H", 1000), opcode=8))
        await one.writer.drain()
        self.assertEqual(await one.next(), ("CLOSE", None))
        self.assertEqual(await asyncio.wait_for(one.reader.read(), 2), b"")

    async def test_a_refused_game_that_never_closes_is_closed_after_the_linger(self):
        await self.start()
        client, (name, error) = await self.connect(name="!!")
        self.assertEqual((name, error["code"]), ("ERROR", ERRORS["bad_name"]))
        began = time.monotonic()
        self.assertEqual(await client.next(), ("CLOSE", None))
        self.assertGreaterEqual(time.monotonic() - began, SPEC["linger_ms"] / 1000 - 0.1)

    async def test_a_refused_game_that_keeps_sending_is_closed_after_a_burst(self):
        # (review M1 protocol 2, must-fix 1: the linger read without a limit
        # and outside pending_cap, so one refused HELLO bought a second of
        # 1,100-byte frames unmasked at full speed, and enough such loops
        # stalled every match's turn clock)
        await self.start()
        client, (name, error) = await self.connect(name="!!")
        self.assertEqual((name, error["code"]), ("ERROR", ERRORS["bad_name"]))
        # The lingering connection holds a pending place ...
        await until(lambda: len(self.server.pending) == 1)
        burst = SPEC["buckets"]["hub"]["burst"]
        junk = masked(bytes((protocol.MESSAGES["PING"].id,)) + bytes(SPEC["max_message"] - 1))
        began = time.monotonic()
        closing = asyncio.ensure_future(client.next(SPEC["linger_ms"] / 1000 * 2))
        sent = 0
        while not closing.done() and sent < 4 * burst:
            try:
                client.writer.write(junk)
                await client.writer.drain()
            except ConnectionError:
                break
            sent += 1
            await asyncio.sleep(0.002)
        # ... and is read for a hub burst of frames at most, then closed, long
        # before linger_ms.
        self.assertEqual(await closing, ("CLOSE", None))
        self.assertLess(time.monotonic() - began, SPEC["linger_ms"] / 1000 / 2)
        self.assertLessEqual(sent, burst + 8)
        await until(lambda: not self.server.pending and not self.server.connections)

    async def test_a_reader_past_the_output_cap_is_dropped_and_its_seat_held(self):
        clock = ManualClock()
        await self.start(dev_match="classic:2", clock=clock, output_cap=4096)
        one, _ = await self.connect("One")
        two, _ = await self.connect("Two", token=b"\x02" * 16)
        await start_match(clock, (one, two))
        match = next(iter(self.server.matches.values()))
        slow = match.seats[1].player
        # (its socket stands for one whose kernel buffers are full)
        slow.writer.transport.get_write_buffer_size = lambda: 5000
        await clock.turns(1)
        await until(lambda: match.seats[1].player is None)
        self.assertEqual(match.seats[1].state, "present")      # (held: AWAY after its silence)
        await clock.advance(SPEC["away_ms"])
        self.assertEqual(match.seats[1].state, "away")
        self.assertEqual(len(self.server.matches), 1)



class NeverReadingTests(unittest.IsolatedAsyncioTestCase):
    """A game that never reads again (a zero receive window, which its kernel
    keeps acknowledging): asyncio's close() waits to flush the unsent output
    before the socket goes, and this peer never lets it. Dropped as a slow
    reader, or once its handler ends, its socket is aborted, so it holds no
    file descriptor and no buffers, and server.close() returns (review M4
    network 1). Small socket buffers make it quick to show."""

    LIMIT = 40          # rounds of PINGs at most

    async def test_a_dropped_reader_that_never_reads_leaves_no_open_socket(self):
        from support import hub
        clock = ManualClock()
        game_socket = socket.socket()
        game_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        server_ = hub(clock=clock)
        port = await server_.start("127.0.0.1", 0)
        closed = False
        try:
            game_socket.setblocking(False)
            await asyncio.get_running_loop().sock_connect(game_socket, ("127.0.0.1", port))
            reader, writer = await asyncio.open_connection(sock=game_socket)
            game = Client()
            game.reader, game.writer = reader, writer
            writer.write(upgrade_request())
            await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 2)
            from support import hello
            await game.send(hello("Zed", token=b"\x09" * 16))
            self.assertEqual((await game.next())[0], "WELCOME")
            writer.transport.pause_reading()            # (from here on its receive window closes)
            await until(lambda: len(server_.players) == 1)
            player = next(iter(server_.players.values()))
            transport = player.writer.transport
            transport.get_extra_info("socket").setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024)
            transport.set_write_buffer_limits(high=2048)
            # (PINGs, each answered with a PONG it never reads, until the server's output backs up)
            for _ in range(self.LIMIT):
                if transport.get_write_buffer_size() > 2048 or transport.is_closing():
                    break
                for seq in range(140):
                    writer.write(masked(protocol.encode("PING", client_ms=seq, rtt_ms=0)))
                try:
                    await asyncio.wait_for(writer.drain(), 0.5)
                except asyncio.TimeoutError:
                    break       # (the server stopped reading: it waits on its own drain)
                await asyncio.sleep(0.05)
                await clock.advance(1200)
            # (the PONG's drain times out after 2 s, the handler ends, its close waits 2 s more)
            await until(lambda: not server_.connections, timeout=8)
            self.assertEqual(len(server_.players), 0)
            # (asyncio's own field: the transport lets its socket go a loop pass after its abort)
            try:
                await until(lambda: transport._sock is None, timeout=1)
            except AssertionError:
                self.fail("the dropped connection still holds its socket")
            await asyncio.wait_for(server_.close(), 3)
            closed = True
        finally:
            game_socket.close()
            if not closed:
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(server_.close(), 3)

    async def test_a_slow_reader_past_the_output_cap_is_cut_off_at_once(self):
        clock = ManualClock()
        server_ = server(dev_match="classic:2", clock=clock, output_cap=4096)
        self.port = await server_.start("127.0.0.1", 0)
        clients = []
        try:
            for name, number in (("One", 1), ("Two", 2)):
                client = Client()
                clients.append(client)
                await client.hello(self.port, name, token=bytes((number,)) * 16)
            await start_match(clock, clients)
            match = next(iter(server_.matches.values()))
            transport = match.seats[1].player.writer.transport
            aborted = []
            transport.abort = (lambda original: lambda: (aborted.append(True), original())[1])(transport.abort)
            transport.get_write_buffer_size = lambda: 5000
            await clock.turns(1)
            await until(lambda: match.seats[1].player is None)
            self.assertTrue(aborted, "dropped for its output, the connection is aborted, not left to flush")
        finally:
            for client in clients:
                client.writer.close()
            await server_.close()


class ContractTests(unittest.TestCase):
    """protocol.json against §6.5's numbers, its own limits and its README."""

    def test_sizes_and_limits(self):
        sizes = {name: message.sizes() for name, message in protocol.MESSAGES.items()}
        self.assertEqual(sizes["CMD"], (16, 16))            # (16 bytes with the type byte)
        self.assertEqual(sizes["TURN"][0], 6)              # (an empty TURN)
        self.assertEqual(sizes["HELLO"][1], 54)
        for name, message in protocol.MESSAGES.items():
            least, most = sizes[name]
            if message.from_client:
                self.assertLessEqual(most, SPEC["max_message"], name)
                self.assertIn(message.bucket, SPEC["buckets"], name)
            else:
                self.assertIsNone(message.bucket, name)
            self.assertLessEqual(most, SPEC["max_server_message"], name)
        self.assertEqual(SPEC["checkpoint_part"], 1024)
        self.assertEqual((SPEC["turn_ticks"] * 1000) // SPEC["tick_hz"], SPEC["turn_ms"])
        self.assertEqual(SPEC["hash_every"] % SPEC["turn_ticks"], 0)
        self.assertEqual(SPEC["subprotocol"], f"groundhold.v{SPEC['version']}")
        self.assertEqual(SPEC["path"], "/causeway")
        types = [spec["type"] for spec in list(SPEC["commands"].values()) + list(SPEC["system_commands"].values())]
        self.assertEqual(len(types), len(set(types)))
        self.assertTrue(all(0 < kind < 256 for kind in types))

    def test_the_environment_sets_groundhold_server_keys(self):
        from groundhold_server import hosting
        environ = {"GROUNDHOLD_SERVER_PORT": "9000", "GROUNDHOLD_SERVER_NAME": "Flats 100%",
                   "GROUNDHOLD_SERVER_": "no key", "OTHER_SERVER_PORT": "1"}
        self.assertEqual(hosting.environment_settings(environ), {"port": "9000", "name": "Flats 100%%"})

    def test_codec_round_trips_and_refuses_bad_lengths(self):
        data = protocol.encode("PARTY", op="team", member=3, team=1)
        self.assertEqual(protocol.decode(data), ("PARTY", dict(op="team", member=3, team=1)))
        for bad in (data[:-1], data + b"\0", bytes((20, 99)), b"", bytes((41, 0, 0, 0, 1, 1)),
                    protocol.encode("ERROR", code=1, text="x")[:-1]):
            with self.assertRaises(protocol.ProtocolError):
                protocol.decode(bad)
        with self.assertRaises(ValueError):
            protocol.encode("HELLO", version=1, build_seq=1, rules_hash=RULES, token=bytes(15), flags=0, name="x")

    def test_strings_with_a_nul_or_a_leading_bom_are_refused_both_ways(self):
        # (the GDScript codec refuses them, so the server must never send one:
        # a NUL or BOM in server.ini's name would have kept every game in HELLO)
        for text in ("a\x00b", "\ufeffHollow"):
            data = bytes((protocol.MESSAGES["ERROR"].id, 1, len(text.encode()))) + text.encode()
            with self.assertRaises(protocol.ProtocolError):
                protocol.decode(data)
            with self.assertRaises(ValueError):
                protocol.encode("ERROR", code=1, text=text)
        self.assertEqual(protocol.decode(protocol.encode("ERROR", code=1, text="a\ufeffb"))[1]["text"], "a\ufeffb")
        named = server(name="\ufeffGround\x00hold\n", motd="Hold\tthe road")
        self.assertEqual((named.name, named.motd), ("Groundhold", "Holdthe road"))
        protocol.encode("WELCOME", session=1, identity=bytes(16), turn_ms=50, turn_ticks=3, hash_every=60, flags=0,
                        server_name=named.name, motd=named.motd)

    def test_the_readme_tables_are_current(self):
        import protocol_tables
        text = protocol_tables.README.read_text(encoding="utf-8")
        self.assertEqual(protocol_tables.current(text), text, "run python3 server/tools/protocol_tables.py")


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))


if __name__ == "__main__":
    unittest.main()
