"""Commands are stamped with the sender's seat and listed in the turn that
was open when they arrived (docs/design/core-loop.md §6.3, §7.3): the seat
comes from the connection, a turn's order rotates, sequence numbers must
increase, and only well-shaped commands pass."""

import unittest

from support import RULES, TICK0, Client, ManualClock, server
from lantern_server import protocol
from lantern_server.match import Sequencer
from lantern_server.protocol import SPEC

BUILD, FORK, SELL, READY, SIGNAL = (SPEC["commands"][name]["type"] for name in ("BUILD", "FORK", "SELL", "READY", "SIGNAL"))
AWAY, BACK, LEFT, TIMEOUT = (SPEC["system_commands"][name]["type"] for name in ("AWAY", "BACK", "LEFT", "TIMEOUT"))
SYSTEM = SPEC["system_seat"]


def stamped(turn):
    return [(c["seat"], c["seq"], c["type"], c["a"], c["b"], c["c"]) for c in turn["commands"]]


class SequencerTests(unittest.TestCase):
    def test_rotation_starts_at_turn_mod_seats_and_system_commands_lead(self):
        sequencer = Sequencer(3)
        for turn in range(3):
            # (seat 2 always reaches the server first; it leads only its own turns)
            for seat in (2, 0, 1):
                sequencer.command(seat, turn * 10 + 1, READY, 1, 0, 0)
                sequencer.command(seat, turn * 10 + 2, READY, 0, 0, 0)
            sealed = sequencer.seal(turn)
            first = turn % 3
            self.assertEqual([entry[0] for entry in sealed],
                             [first, first, (first + 1) % 3, (first + 1) % 3, (first + 2) % 3, (first + 2) % 3])
            self.assertEqual([entry[1] for entry in sealed], [turn * 10 + 1, turn * 10 + 2] * 3)
        sequencer.command(1, 99, READY, 1, 0, 0)
        sequencer.inject("AWAY", 2)
        sequencer.inject("BACK", 2)
        self.assertEqual(sequencer.seal(3), [(SYSTEM, 1, AWAY, 2, 0, 0), (SYSTEM, 2, BACK, 2, 0, 0),
                                             (1, 99, READY, 1, 0, 0)])
        self.assertEqual(sequencer.seal(4), [])

    def test_sequence_numbers_must_increase_per_seat(self):
        sequencer = Sequencer(2)
        sequencer.command(0, 5, READY, 1, 0, 0)
        sequencer.command(1, 5, READY, 1, 0, 0)     # (another seat's own count)
        with self.assertRaises(protocol.ProtocolError):
            sequencer.command(0, 5, READY, 0, 0, 0)
        with self.assertRaises(protocol.ProtocolError):
            sequencer.command(0, 4, READY, 0, 0, 0)
        sequencer.command(0, 6, READY, 0, 0, 0)

    def test_a_full_turn_carries_the_rest_over_in_order(self):
        sequencer = Sequencer(2)
        for seq in range(300):
            sequencer.command(seq % 2, seq, READY, 1, 0, 0)
        first = sequencer.seal(0)
        self.assertEqual(len(first), SPEC["max_turn_commands"])
        self.assertEqual([entry[1] for entry in first], list(range(0, 300, 2)) + list(range(1, 211, 2)))
        rest = sequencer.seal(1)
        self.assertEqual([entry[1] for entry in rest], list(range(211, 300, 2)))
        self.assertEqual(sequencer.seal(2), [])

    def test_shapes(self):
        protocol.check_command(BUILD, 2, 255, 0)
        protocol.check_command(SIGNAL, -262144, 262144, 0)
        for kind, a, b, c in ((BUILD, 3, 0, 0), (BUILD, 0, -1, 0), (BUILD, 0, 0, 256), (FORK, 0, 0, 0),
                              (FORK, 1, 2, 0), (SELL, 1, 1, 0), (READY, 2, 0, 0), (SIGNAL, 262145, 0, 0),
                              (SIGNAL, 0, 0, -1), (AWAY, 0, 0, 0), (TIMEOUT, 0, 0, 0), (0, 0, 0, 0), (200, 0, 0, 0)):
            with self.assertRaises(protocol.ProtocolError) as caught:
                protocol.check_command(kind, a, b, c)
            self.assertEqual(caught.exception.code, SPEC["errors"]["out_of_limits"])


class StampingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = ManualClock()
        self.server = server(dev_match="classic:2", clock=self.clock)
        self.port = await self.server.start("127.0.0.1", 0)
        self.one, self.two = Client(), Client()
        await self.one.hello(self.port, "Tamsin")
        await self.two.hello(self.port, "Edda", token=b"\x02" * 16)

    async def asyncTearDown(self):
        for client in (self.one, self.two):
            await client.drop()
        await self.server.close()

    async def start_match(self):
        for client in (self.one, self.two):
            await client.until("MATCH_CONFIG")
            await client.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        await self.clock.advance(SPEC["loading_min_ms"])
        for client in (self.one, self.two):
            await client.until("START", skip=("LOAD_STATE",))
        await self.clock.advance(SPEC["start_delay_ms"])
        self.match = next(iter(self.server.matches.values()))

    async def arrived(self, count):
        """Until the server holds `count` commands for the open turn."""
        from support import until
        await until(lambda: len(self.match.sequencer.pending) == count)

    async def turn(self, client):
        return await client.until("TURN", skip=("LINKS",))

    async def test_the_seat_comes_from_the_connection_and_the_open_turn_lists_it(self):
        await self.start_match()
        # Turn 0 is open: both commands land in TURN(0), each with its sender's seat.
        await self.one.send_message("CMD", seq=1, type=BUILD, a=0, b=8, c=3)
        await self.two.send_message("CMD", seq=1, type=BUILD, a=0, b=8, c=3)
        await self.arrived(2)
        await self.clock.turns(1)
        for client in (self.one, self.two):
            turn = await self.turn(client)
            self.assertEqual(turn["turn"], 0)
            self.assertEqual(stamped(turn), [(0, 1, BUILD, 0, 8, 3), (1, 1, BUILD, 0, 8, 3)])
        # Turn 1: the rotation starts at seat 1, whoever was first to the server.
        await self.one.send_message("CMD", seq=2, type=READY, a=1, b=0, c=0)
        await self.arrived(1)
        await self.two.send_message("CMD", seq=2, type=SIGNAL, a=8500, b=3500, c=0)
        await self.arrived(2)
        await self.clock.turns(1)
        for client in (self.one, self.two):
            turn = await self.turn(client)
            self.assertEqual(turn["turn"], 1)
            self.assertEqual(stamped(turn), [(1, 2, SIGNAL, 8500, 3500, 0), (0, 2, READY, 1, 0, 0)])
        # Empty turns until a command comes: it goes to the turn open then, turn 4.
        await self.clock.turns(2)
        await self.one.send_message("CMD", seq=3, type=FORK, a=1, b=1, c=0)
        await self.arrived(1)
        await self.clock.turns(1)
        for client in (self.one, self.two):
            turns = [await self.turn(client) for _ in range(3)]
            self.assertEqual([t["turn"] for t in turns], [2, 3, 4])
            self.assertEqual([stamped(t) for t in turns], [[], [], [(0, 3, FORK, 1, 1, 0)]])

    async def test_a_sequence_that_does_not_increase_closes_that_connection_only(self):
        await self.start_match()
        await self.one.send_message("CMD", seq=9, type=READY, a=1, b=0, c=0)
        await self.arrived(1)
        await self.one.send_message("CMD", seq=9, type=READY, a=0, b=0, c=0)
        error = await self.one.until("ERROR", skip=("TURN", "LINKS"))
        self.assertEqual(error["code"], SPEC["errors"]["protocol"])
        self.assertIn("increase", error["text"])
        # The seat is held and its command of turn 0 stands; the other plays on.
        await self.clock.turns(1)
        turn = await self.turn(self.two)
        self.assertEqual(stamped(turn), [(0, 9, READY, 1, 0, 0)])
        self.assertEqual(len(self.server.matches), 1)

    async def test_out_of_range_arguments_and_system_types_are_refused(self):
        await self.start_match()
        for kind, a in ((BUILD, 3), (AWAY, 0)):
            client = self.one if kind == BUILD else self.two
            await client.send_message("CMD", seq=1, type=kind, a=a, b=0, c=0)
            error = await client.until("ERROR", skip=("TURN", "LINKS"))
            self.assertEqual(error["code"], SPEC["errors"]["out_of_limits"])
        self.assertEqual(self.match.sequencer.pending, [])

    async def test_a_command_before_start_is_out_of_order(self):
        await self.one.until("MATCH_CONFIG")
        await self.one.send_message("CMD", seq=1, type=READY, a=1, b=0, c=0)
        error = await self.one.until("ERROR", skip=("LOAD_STATE",))
        self.assertEqual(error["code"], SPEC["errors"]["protocol"])

    async def test_system_commands_come_first_in_their_turn(self):
        await self.start_match()
        await self.one.send_message("CMD", seq=1, type=READY, a=1, b=0, c=0)
        await self.arrived(1)
        await self.two.send_message("LEAVE_MATCH")
        from support import until
        await until(lambda: self.match.sequencer.system)
        await self.clock.turns(1)
        turn = await self.turn(self.one)
        self.assertEqual(stamped(turn), [(SYSTEM, 1, LEFT, 1, 0, 0), (0, 1, READY, 1, 0, 0)])
        # (seat 2 left: its commands are refused from now on, nothing else is)
        self.assertTrue(await self.two.quiet())


if __name__ == "__main__":
    unittest.main()
