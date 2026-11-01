"""The duel's orders through the server's CMD path (M7, contract-m7 §2; design 1.4, 6.5):
in an Undertow dev match, CORK(tier, the commit's halves), UNCORK(pack, the salt's halves)
and SEAWALL come back to both games in the turn that was open when they arrived, stamped
with the sender's seat and every 32-bit half as sent (the commitment and the salt use the
whole signed range), again in a TURN_REQUEST's answer, and a duel's command outside its
limits is refused as any CMD is, closing that game's link only. The server never simulates:
what a CORK commits to or whether an UNCORK reveals it is the games' (SimUndertow), so it
passes them unread."""

import asyncio
import struct
import unittest

from support import Client, ManualClock, masked, server, start_match, until
from groundhold_server import protocol
from groundhold_server.protocol import SPEC

CORK, UNCORK, SEAWALL = (SPEC["commands"][name]["type"] for name in ("CORK", "UNCORK", "SEAWALL"))
# (a real commitment: bot_duels_through_its_orders's first cork, seat 1's in window 2 of seed
# 1 under the scenario's fixed salt, tests/net/duel_checks.gd's fixed_salt(1, 1); SimUndertow.commit's
# halves, carried as the signed i32 with the same bits)
COMMIT = (-648443039, 1174251496)
LOW, HIGH = -2 ** 31, 2 ** 31 - 1


def stamped(turn):
    return [(c["seat"], c["seq"], c["type"], c["a"], c["b"], c["c"]) for c in turn["commands"]]


class DuelCommandShapes(unittest.TestCase):
    def test_a_cork_and_an_uncork_carry_any_32_bit_halves_and_the_seawall_none(self):
        for kind in (CORK, UNCORK):
            for a, b, c in ((0, *COMMIT), (2, LOW, HIGH), (3, HIGH, LOW), (15, 0, -1)):
                protocol.check_command(kind, a, b, c)
        protocol.check_command(SEAWALL, 0, 0, 0)
        for kind, a, b, c in ((CORK, 16, 0, 0), (CORK, -1, 0, 0), (UNCORK, 16, 0, 0), (UNCORK, -1, 0, 0),
                              (SEAWALL, 1, 0, 0), (SEAWALL, 0, 1, 0), (SEAWALL, 0, 0, -1)):
            with self.assertRaises(protocol.ProtocolError) as caught:
                protocol.check_command(kind, a, b, c)
            self.assertEqual(caught.exception.code, SPEC["errors"]["out_of_limits"])


class DuelCommandTurns(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = ManualClock()
        self.server = server(dev_match="undertow:2", clock=self.clock)
        self.port = await self.server.start("127.0.0.1", 0)
        self.one, self.two = Client(), Client()
        await self.one.hello(self.port, "Tamsin", token=b"\x01" * 16)
        await self.two.hello(self.port, "Edda", token=b"\x02" * 16)
        configs = await start_match(self.clock, (self.one, self.two))
        self.assertEqual(configs[0]["mode"], SPEC["modes"]["undertow"]["id"])
        self.match = next(iter(self.server.matches.values()))

    async def asyncTearDown(self):
        for client in (self.one, self.two):
            await client.drop()
        await self.server.close()

    async def arrived(self, count):
        await until(lambda: len(self.match.sequencer.pending) == count)

    async def turn(self, client):
        return await client.until("TURN", skip=("LINKS",))

    async def test_cork_uncork_and_seawall_reach_both_games_stamped_as_sent(self):
        # Turn 0, the window: a cork each, seat 0's a game's real commitment, seat 1's the
        # range's ends.
        await self.one.send_message("CMD", seq=1, type=CORK, a=0, b=COMMIT[0], c=COMMIT[1])
        await self.two.send_message("CMD", seq=1, type=CORK, a=2, b=LOW, c=HIGH)
        await self.arrived(2)
        await self.clock.turns(1)
        corks = [(0, 1, CORK, 0, *COMMIT), (1, 1, CORK, 2, LOW, HIGH)]
        for client in (self.one, self.two):
            turn = await self.turn(client)
            self.assertEqual(turn["turn"], 0)
            self.assertEqual(stamped(turn), corks)
        # Turn 1, the wave: seat 1 leads the rotation; its uncorking and its Seawall, then
        # seat 0's uncorking, each salt's halves as sent.
        await self.two.send_message("CMD", seq=2, type=UNCORK, a=3, b=HIGH, c=LOW)
        await self.two.send_message("CMD", seq=3, type=SEAWALL, a=0, b=0, c=0)
        await self.one.send_message("CMD", seq=2, type=UNCORK, a=3, b=0x1234567, c=-1)
        await self.arrived(3)
        await self.clock.turns(1)
        reveals = [(1, 2, UNCORK, 3, HIGH, LOW), (1, 3, SEAWALL, 0, 0, 0), (0, 2, UNCORK, 3, 0x1234567, -1)]
        for client in (self.one, self.two):
            turn = await self.turn(client)
            self.assertEqual(turn["turn"], 1)
            self.assertEqual(stamped(turn), reveals)
        # A game that missed them asks again: the same turns, the same bytes' values.
        await self.one.send_message("TURN_REQUEST", first_missing=0)
        again = [await self.turn(self.one) for _ in range(2)]
        self.assertEqual([(t["turn"], stamped(t)) for t in again], [(0, corks), (1, reveals)])

    async def test_a_duel_order_outside_its_limits_closes_that_connection_only(self):
        # (a tier past the protocol's 15, as any CMD outside its limits: ERROR, the seat let
        # go of at once and held, the link read no more and closed with the game's close;
        # the other side's Seawall goes into the turn as ever, over its own link)
        await self.one.send_message("CMD", seq=1, type=CORK, a=16, b=0, c=0)
        error = await self.one.until("ERROR", skip=("TURN", "LINKS"))
        self.assertEqual(error["code"], SPEC["errors"]["out_of_limits"])
        self.assertEqual(self.match.sequencer.pending, [])
        await until(lambda: self.match.seats[0].player is None)
        await self.one.send_message("PING", client_ms=1, rtt_ms=1)
        self.assertTrue(await self.one.quiet(0.3))
        self.one.writer.write(masked(struct.pack("!H", 1000), opcode=8))
        await self.one.writer.drain()
        self.assertEqual(await self.one.next(), ("CLOSE", None))
        self.assertEqual(await asyncio.wait_for(self.one.reader.read(), 2), b"")
        await self.two.send_message("CMD", seq=1, type=SEAWALL, a=0, b=0, c=0)
        await self.arrived(1)
        await self.clock.turns(1)
        self.assertEqual(stamped(await self.turn(self.two)), [(1, 1, SEAWALL, 0, 0, 0)])
        self.assertIsNotNone(self.match.seats[1].player)
        self.assertEqual(len(self.server.matches), 1)


if __name__ == "__main__":
    unittest.main()
