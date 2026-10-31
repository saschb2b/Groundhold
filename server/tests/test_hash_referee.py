"""The hash referee (docs/design/core-loop.md §6.7, §7.3; shared/net/README.md,
Hashes and Resilience): a tick is compared once every present seat reported
it, or 2 s after the first report; all equal, or with three seats or more a
strict majority of the seats present (not of the reports so far), is
agreement. Short of that the tick stays open until the missing seats report
or stop voting (away, gone, left, or no HASH for result_wait_ms). A minority
of three gets RESYNC(desync) and its HASHes on their way before it are not
held against it; the same seat apart again is out (desynced_twice). Two
seats apart, or no majority, end the match "desynced"."""

import unittest

from support import REASONS, TICK0, MatchTest, named, news, sync, turn_numbers
from groundhold_server.protocol import SPEC

OUTCOMES, ENDS = SPEC["outcomes"], SPEC["end_reasons"]
SYSTEM = SPEC["system_commands"]
GOOD, BAD = b"h" * 8, b"z" * 8


def apart(seat, since=0):
    """Digests where the game of `seat` parts from the others at tick `since`."""
    return lambda game, tick: BAD if game.seat == seat and tick >= since else GOOD


class HashRefereeTests(MatchTest, unittest.IsolatedAsyncioTestCase):
    async def everyone(self, games):
        return [await sync(game) for game in games]

    async def test_all_equal_or_a_strict_majority_of_three_is_agreement(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        await self.play(60, 60, games)
        self.assertEqual(self.match().agreed[60], GOOD)
        await self.play(120, 120, games, digest=apart(2))
        self.assertEqual(self.match().agreed[120], GOOD)
        self.assertTrue(self.server.matches, "a minority of three ends nothing")
        self.assertEqual([seat.state for seat in self.match().seats], ["present"] * 3)

    async def test_a_tick_is_compared_two_seconds_after_its_first_report(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        await self.clock.turns(20)
        for game in games[:2]:
            await game.send_message("HASH", tick=60, hash=GOOD, flags=0)
        await self.everyone(games)              # (Ottilie talks, but her game is slow to hash)
        await self.clock.advance(SPEC["hash_wait_ms"] - SPEC["turn_ms"])
        self.assertIn(60, self.match().hashes, "a present seat is waited for")
        self.assertNotIn(60, self.match().agreed)
        await self.clock.turns(1)
        self.assertEqual(self.match().agreed[60], GOOD)
        # (her report, late, is compared with the agreed hash: apart, she is a minority)
        await games[2].send_message("HASH", tick=60, hash=BAD, flags=0)
        await sync(games[2])
        self.assertEqual((self.match().seats[2].muted, self.match().seats[2].resyncs), (True, 1))

    async def test_a_minority_of_three_is_resynced_from_tick_0_without_a_checkpoint(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        await self.play(60, 60, games)
        await self.play(120, 120, games, digest=apart(2))
        open_turn = self.match().loop.turn
        await self.clock.turns(1)
        got = await sync(games[2])
        self.assertEqual(named(got, "RESYNC"), [dict(checkpoint_tick=0, first_turn=0, reason=REASONS["desync"],
                                                     open_turn=open_turn, checkpoint_hash=TICK0, parts=0)])
        # (behind it every turn from the checkpoint's, once and in order, then the live one)
        start = [name for name, _ in got].index("RESYNC")
        self.assertEqual(turn_numbers(got[start:]), list(range(open_turn + 1)))
        for game in games[:2]:
            others = await sync(game)
            self.assertEqual(named(others, "RESYNC"), [])
            self.assertEqual(turn_numbers(others)[-1], open_turn)
        self.assertEqual((self.server.daily.today["desyncs"], self.server.daily.today["resyncs"]), (1, 1))

    async def test_hashes_on_their_way_before_the_resync_are_not_compared(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        await self.play(60, 120, games)
        await self.play(180, 180, games, digest=apart(2))
        # Her game keeps hashing its parted simulation until the RESYNC reaches
        # it: those reports are not held against her.
        await self.play(240, 300, games, digest=apart(2))
        seat = self.match().seats[2]
        self.assertEqual((seat.state, seat.muted, seat.resyncs), ("present", True, 1))
        self.assertEqual(named(games[2].inbox, "MATCH_END"), [])
        self.assertNotIn(2, [s.index for s in self.match().present()], "a minority on its way back does not vote")
        # It loads tick 0 and runs again: its HASHes count from there, each
        # compared with the agreed hash as a late report, and agree.
        for tick in range(60, 301, 60):
            await games[2].send_message("HASH", tick=tick, hash=GOOD, flags=0)
        await sync(games[2])
        self.assertEqual((seat.muted, seat.hash_tick), (False, 300))
        await self.play(360, 420, games)
        self.assertEqual(self.match().agreed[420], GOOD)
        self.assertEqual([s.state for s in self.match().seats], ["present"] * 3)
        self.assertEqual(self.server.daily.today["desyncs"], 1)

    async def test_a_seat_apart_again_after_its_resync_is_out_desynced_twice(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        await self.play(60, 120, games)
        await self.play(180, 180, games, digest=apart(2))
        for tick in range(60, 181, 60):
            await games[2].send_message("HASH", tick=tick, hash=GOOD, flags=0)
        await sync(games[2])
        await self.play(240, 300, games, digest=apart(2, since=300))
        await sync(games[2])
        self.assertEqual(named(games[2].inbox, "MATCH_END"), [dict(outcome=OUTCOMES["desynced"],
                                                                   reason=ENDS["desynced_twice"], final_tick=300)])
        self.assertEqual(self.match().seats[2].state, "left")
        # (the others play on, the caretaker keeping her seat: LEFT in the next turn)
        await self.clock.turns(1)
        for game in games[:2]:
            turns = named(await sync(game), "TURN")
            self.assertEqual(turns[-1]["commands"], [dict(seat=255, seq=1, type=SYSTEM["LEFT"]["type"], a=2, b=0, c=0)])
        await self.play(360, 360, games[:2])
        self.assertTrue(self.server.matches)
        self.assertEqual(self.server.daily.today["desyncs"], 2)
        # (her game is out of the match: a HASH on its way is let pass, as after LEAVE_MATCH)
        await games[2].send_message("HASH", tick=360, hash=BAD, flags=0)
        self.assertEqual(named(await sync(games[2]), "ERROR"), [])

    async def test_two_seats_apart_end_the_match_desynced(self):
        games = await self.seated("Tamsin", "Edda")
        await self.play(60, 60, games)
        await self.play(120, 120, games, digest=apart(1))
        for game in games:
            await sync(game)
            self.assertEqual(named(game.inbox, "MATCH_END"), [dict(outcome=OUTCOMES["desynced"], reason=ENDS["desync"],
                                                                   final_tick=120)])
            self.assertEqual(named(game.inbox, "RESYNC"), [])
        self.assertFalse(self.server.matches)

    async def test_no_majority_ends_the_match_desynced_for_everyone(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie", "Sefa")
        await self.play(60, 60, games, digest=lambda game, tick: GOOD if game.seat < 2 else BAD)
        for game in games:
            await sync(game)
            self.assertEqual(named(game.inbox, "MATCH_END"), [dict(outcome=OUTCOMES["desynced"], reason=ENDS["desync"],
                                                                   final_tick=60)])
        self.assertFalse(self.server.matches)



class LateReportTests(MatchTest, unittest.IsolatedAsyncioTestCase):
    """One game reports a tick and the others more than hash_wait_ms later (a
    stall, a tab hidden for 3 s, a slow Wi-Fi): the majority is counted among
    the seats present, so a lone early report never decides for them (review
    M4 network 1)."""

    async def late(self, games, early, late, digest):
        """`early` games report tick 60, then the clock passes hash_wait_ms
        (everyone talking), then the `late` ones report it."""
        await self.clock.turns(20)
        for index in early:
            await games[index].send_message("HASH", tick=60, hash=digest(index), flags=0)
        for game in games:
            await sync(game)
        await self.clock.advance(SPEC["hash_wait_ms"] + 50)
        for index in late:
            await games[index].send_message("HASH", tick=60, hash=digest(index), flags=0)
        for game in games:
            await sync(game)
        await self.clock.turns(2)

    async def test_one_early_report_does_not_decide_for_two_late_agreeing_seats(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        # (Tamsin's game parted from the others: its hash at 60 is BAD, and it reports first)
        await self.late(games, [0], [1, 2], lambda index: BAD if index == 0 else GOOD)
        resynced = [bool(named(await news(game), "RESYNC")) for game in games]
        self.assertEqual((self.match().agreed.get(60), resynced), (GOOD, [True, False, False]))

    async def test_the_early_parted_seat_cannot_put_the_two_agreeing_ones_out(self):
        """Carried on, every game doing what it is told: one that got RESYNC
        runs again from the checkpoint (tick 0) and reports tick 60 again,
        now with the state the others agreed. Nobody is out of the match."""
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        await self.late(games, [0], [1, 2], lambda index: BAD if index == 0 else GOOD)
        for game in games:
            if named(await news(game), "RESYNC"):
                await game.send_message("HASH", tick=60, hash=GOOD, flags=0)       # (re-run from tick 0)
        await self.play(120, 180, games)
        ends = [named(game.inbox, "MATCH_END", "ERROR") for game in games]
        self.assertEqual(([seat.state for seat in self.match().seats], ends), (["present"] * 3, [[], [], []]))
        self.assertEqual(self.match().agreed[180], GOOD)

    async def test_a_late_third_report_names_the_minority_instead_of_ending_the_match(self):
        """Tamsin and Edda report tick 60 apart (Edda's game parted); Ottilie,
        present and talking, reports 2.05 s later and agrees with Tamsin: two
        of three is a strict majority, so Edda alone is resynced."""
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        await self.late(games, [0, 1], [2], lambda index: BAD if index == 1 else GOOD)
        self.assertTrue(self.server.matches, "the match ended at the 2 s mark")
        self.assertEqual([named(game.inbox, "MATCH_END") for game in games], [[], [], []])
        resynced = [bool(named(await news(game), "RESYNC")) for game in games]
        self.assertEqual((self.match().agreed.get(60), resynced), (GOOD, [False, True, False]))

    async def test_a_lone_report_of_two_waits_for_the_other_seat(self):
        games = await self.seated("Tamsin", "Edda")
        await self.late(games, [0], [1], lambda index: GOOD)
        self.assertEqual(self.match().agreed.get(60), GOOD)
        self.assertEqual([named(game.inbox, "MATCH_END") for game in games], [[], []])
        await self.clock.turns(20)
        await games[0].send_message("HASH", tick=120, hash=GOOD, flags=0)
        await sync(games[0])
        await self.clock.advance(SPEC["hash_wait_ms"] + 50)
        self.assertIn(120, self.match().hashes, "one report of two seats present is no majority: it waits")
        self.assertNotIn(120, self.match().agreed)
        await games[1].send_message("HASH", tick=120, hash=BAD, flags=0)
        await sync(games[1])
        self.assertEqual(named(await news(games[0]), "MATCH_END"),
                         [dict(outcome=OUTCOMES["desynced"], reason=ENDS["desync"], final_tick=120)])

    async def test_a_seat_that_stops_voting_lets_the_open_tick_be_decided(self):
        """The tick waits for a missing seat only while it votes: gone AWAY
        (silent away_ms), or still talking but without a HASH for
        result_wait_ms, it no longer holds the tick open."""
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        match = self.match()
        await self.play(60, 60, games)
        await self.clock.turns(20)
        await games[0].send_message("HASH", tick=120, hash=GOOD, flags=0)
        await games[1].send_message("HASH", tick=120, hash=BAD, flags=0)
        await sync(games[0])
        await sync(games[1])
        await self.clock.advance(SPEC["hash_wait_ms"] + 50)
        await sync(games[0])
        await sync(games[1])
        self.assertIn(120, match.hashes, "one each way, and Ottilie may yet decide it")
        # (Ottilie's game froze: no word for away_ms, AWAY; then two seats apart end the match)
        await self.clock.advance(SPEC["away_ms"] - SPEC["hash_wait_ms"])
        self.assertEqual(match.seats[2].state, "away")
        self.assertEqual(named(await news(games[0]), "MATCH_END"),
                         [dict(outcome=OUTCOMES["desynced"], reason=ENDS["desync"], final_tick=120)])

    async def test_a_talking_seat_that_stops_hashing_holds_a_tick_up_result_wait_ms_at_most(self):
        games = await self.seated("Tamsin", "Edda")
        await self.play(60, 60, games)
        await self.clock.turns(20)
        await games[0].send_message("HASH", tick=120, hash=GOOD, flags=0)
        for _ in range(SPEC["result_wait_ms"] // SPEC["ping_ms"] - 1):
            await self.clock.advance(SPEC["ping_ms"])
            for game in games:
                await sync(game)            # (Edda talks, but her game hashes no more)
        self.assertNotIn(120, self.match().agreed)
        await self.clock.advance(SPEC["ping_ms"])
        for game in games:
            await sync(game)
        self.assertEqual(self.match().agreed.get(120), GOOD)
        self.assertTrue(self.server.matches)


if __name__ == "__main__":
    unittest.main()
