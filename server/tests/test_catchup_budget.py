"""The paced catch-up (docs/design/core-loop.md §6.7, §7.3; shared/net/README.md,
Resilience: Catch-up; catchup.py): RESYNC and everything behind it go out at
most 2 KB a turn, whole messages in order, and only while the connection's
unsent output stays within 4 KB; the live turns wait behind them; a seat
catching up is never dropped by the output cap, which applies again once it
caught up."""

import unittest

from support import (CHECKPOINT, RESUME, MatchTest, drain, named, news, state_bytes, sync, turn_numbers, until,
                     upload)
from groundhold_server import protocol
from groundhold_server.catchup import BYTES, OUTPUT, CatchUp
from groundhold_server.protocol import SPEC

PACED = ("RESYNC", "CHECKPOINT_PART", "TURN")
STATE = state_bytes(9000)                       # (nine parts)
AGREED = protocol.digest(STATE)
# Every loop that waits for a catch-up to finish stops after this many steps, so a run against
# a pacer that never sends (the code before the change) fails instead of growing.
LIMIT = 2000


class PacerTests(unittest.TestCase):
    def pacer(self, unsent=0, grows=False):
        """A CatchUp writing into `self.written`; its connection's unsent
        output starts at `unsent` and, with `grows`, keeps what it is given."""
        self.written, self.unsent = [], unsent

        def write(data):
            self.written.append(data)
            if grows:
                self.unsent += len(data)
        return CatchUp(write, lambda: self.unsent)

    def test_a_pump_writes_whole_messages_in_order_within_two_kilobytes(self):
        pacer = self.pacer()
        messages = [bytes((index % 256,)) * size for index, size in enumerate([24, 1035, 1035, 463] + [6] * 700)]
        for message in messages:
            pacer.queue(message)
        self.assertEqual(pacer.total, sum(map(len, messages)))
        pumps = []
        for _ in range(LIMIT):            # (bounded: a pacer that never sends must fail, not grow)
            if pacer.done:
                break
            pumps.append(pacer.pump())
        self.assertTrue(pacer.done, "the pacer never sent everything")
        self.assertEqual(self.written, messages)
        self.assertEqual(pacer.sent, pacer.total)
        self.assertTrue(all(0 < spent <= BYTES for spent in pumps), pumps)
        self.assertEqual(pumps[:2], [24 + 1035, 1035 + 463 + 6 * 91])
        self.assertEqual(len(pumps), 4)

    def test_a_message_larger_than_the_budget_goes_alone(self):
        pacer = self.pacer()
        big = protocol.turn(7, [(1, seq, 4, 1, 0, 0) for seq in range(255)])
        self.assertGreater(len(big), BYTES)
        for message in (big, protocol.turn(8, ())):
            pacer.queue(message)
        self.assertEqual([pacer.pump(), pacer.pump(), pacer.pump()], [len(big), 6, 0])

    def test_the_unsent_output_never_passes_four_kilobytes(self):
        pacer = self.pacer(grows=True)
        for part in range(9):
            pacer.queue(bytes(1035))
        most = 0
        for _ in range(4):
            pacer.pump()
            most = max(most, self.unsent)
        # (the reader took nothing: three parts, then nothing more fits under 4 KB)
        self.assertEqual((len(self.written), self.unsent), (3, 3105))
        self.assertLessEqual(most, OUTPUT)
        self.unsent = 0                                 # (it read them)
        self.assertEqual(pacer.pump(), 1035)
        self.unsent = OUTPUT
        self.assertEqual(pacer.pump(), 0)


class WireTests(MatchTest, unittest.IsolatedAsyncioTestCase):
    async def away_and_back(self, **options):
        """Edda drops after a 9 KB checkpoint at tick 120 and comes back by a
        resume 30 s later: her new game and her new server-side connection."""
        tamsin, edda = await self.seated("Tamsin", "Edda", **options)
        checkpoint = dict(digest=lambda game, tick: AGREED if tick == 120 else b"h" * 8,
                          flags=lambda game, tick: CHECKPOINT if tick == 120 else 0)
        await self.play(60, 120, (tamsin, edda), **checkpoint)
        for game in (tamsin, edda):
            if named(await news(game), "CHECKPOINT_ASK"):
                await upload(game, 120, STATE)
                await sync(game)
        self.assertEqual([tick for tick, _, _ in self.match().checkpoints], [120])
        await edda.drop()
        await self.play(180, 1920, (tamsin,))
        again = await self.join("Edda", 2, flags=RESUME, match=self.match().id, seat=1)
        await again.until("MATCH_CONFIG")
        return tamsin, again, self.match().seats[1].player

    async def test_a_rejoin_gets_two_kilobytes_a_turn_with_the_live_turns_behind(self):
        tamsin, again, _ = await self.away_and_back()
        backlog = self.match().loop.turn - 40
        shares = []
        for _ in range(LIMIT):
            await self.clock.turns(1)
            got = await drain(again, 0.03)
            shares.append(sum(len(protocol.encode(name, **fields)) for name, fields in got if name in PACED))
            if self.match().seats[1].catchup is None:
                break
        self.assertIsNone(self.match().seats[1].catchup, "the catch-up never finished")
        got = [(name, fields) for name, fields in again.inbox if name in PACED]
        # RESYNC, the nine parts, every turn from the checkpoint's to the live
        # ones, each once and in order, and never more than 2 KB in a turn.
        self.assertEqual([name for name, _ in got[:10]], ["RESYNC"] + ["CHECKPOINT_PART"] * 9)
        self.assertEqual(b"".join(fields["data"] for _, fields in got[1:10]), STATE)
        self.assertEqual(turn_numbers(got), list(range(40, self.match().loop.turn)))
        self.assertTrue(all(share <= BYTES for share in shares), shares)
        self.assertGreaterEqual(len(shares), (24 + len(STATE) + 6 * backlog) // BYTES)
        # (caught up, a live turn goes out directly as each is sealed)
        await self.clock.turns(1)
        self.assertEqual(turn_numbers(await drain(again, 0.03)), [self.match().loop.turn - 1])

    async def test_a_dev_matchs_shorter_turns_still_pace_two_kilobytes_per_50_ms(self):
        """--turn-ms 10: five turns a catchup_ms, and still one share in it."""
        tamsin, again, _ = await self.away_and_back(turn_ms=10)
        windows = []
        for _ in range(LIMIT):
            if self.match().seats[1].catchup is None:
                break
            share = 0
            for _ in range(SPEC["catchup_ms"] // 10):
                await self.clock.advance(10)
                got = await drain(again, 0.02)
                share += sum(len(protocol.encode(name, **fields)) for name, fields in got if name in PACED)
            windows.append(share)
        self.assertIsNone(self.match().seats[1].catchup, "the catch-up never finished")
        self.assertTrue(all(share <= BYTES for share in windows), windows)
        self.assertGreaterEqual(len(windows), (24 + len(STATE)) // BYTES)
        got = [(name, fields) for name, fields in again.inbox if name in PACED]
        self.assertEqual(turn_numbers(got), list(range(40, turn_numbers(got)[-1] + 1)))

    async def test_nothing_goes_while_four_kilobytes_wait_unsent_and_the_cap_waits_for_the_catch_up(self):
        tamsin, again, connection = await self.away_and_back(output_cap=OUTPUT)
        unsent = [OUTPUT + 1000]
        connection.writer.transport.get_write_buffer_size = lambda: unsent[0]
        await self.clock.turns(SPEC["links_ms"] // SPEC["turn_ms"])
        got = await drain(again)
        self.assertEqual([name for name, _ in got], ["LINKS"], "nothing paced, and the link is not dropped")
        unsent[0] = 0
        for _ in range(LIMIT):
            if self.match().seats[1].catchup is None:
                break
            await self.clock.turns(1)
        self.assertIsNone(self.match().seats[1].catchup, "the catch-up never finished")
        self.assertEqual(named(await drain(again), "RESYNC")[0]["checkpoint_tick"], 120)
        # Caught up, the cap is the connection's again: past it, it is dropped and the seat held.
        unsent[0] = OUTPUT + 1000
        await self.clock.turns(1)
        await until(lambda: self.match().seats[1].player is None)
        self.assertEqual(self.match().seats[1].state, "away")


if __name__ == "__main__":
    unittest.main()
