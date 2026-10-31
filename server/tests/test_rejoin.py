"""A match seat taken back (docs/design/core-loop.md §6.7 Reconnect;
shared/net/README.md, Resilience: Rejoin): a resume HELLO names the match
and the seat it held, since two windows on one computer share an identity;
the server seats it there (an old connection still open gets ERROR 12),
sends the party's PARTY_STATE, MATCH_CONFIG with the rejoin flag and
RESYNC(rejoin) from the latest checkpoint, and the seat's HASHes count again
from the checkpoint. A seat not held hears NOTICE no_held_seat. A rejoin while
the match still loads gets MATCH_CONFIG as at the start and loads."""

import unittest

from support import (CHECKPOINT, MEMBER, PHASES, REASONS, RESUME, TICK0, Client, HubTest, MatchTest, named, news,
                     start_match, state, states, state_bytes, sync, turn_numbers, until, upload)
from groundhold_server import protocol
from groundhold_server.protocol import SPEC

ERRORS, NOTICES = SPEC["errors"], SPEC["notices"]
REJOIN = SPEC["config_flags"]["rejoin"]
STATE = state_bytes(1800)
AGREED = protocol.digest(STATE)
GOOD = b"h" * 8


def checkpoint_at(*ticks):
    return dict(digest=lambda game, tick: AGREED if tick in ticks else GOOD,
                flags=lambda game, tick: CHECKPOINT if tick in ticks else 0)


async def keep(games, tick):
    for game in games:
        if named(await news(game), "CHECKPOINT_ASK"):
            await upload(game, tick, STATE)
            await sync(game)


class RejoinTests(MatchTest, unittest.IsolatedAsyncioTestCase):
    async def test_two_windows_of_one_identity_take_back_the_seat_they_name(self):
        await self.start("classic:2")
        first, second = Client(), Client()
        self.clients += [first, second]
        for game, name in ((first, "Tamsin"), (second, "Edda")):
            await game.hello(self.port, name, token=bytes((1,)) * 16)       # (one profile, two windows)
        await start_match(self.clock, (first, second))
        await second.drop()
        await until(lambda: self.match().seats[1].player is None)
        again = await self.join("Edda", 1, flags=RESUME, match=self.match().id, seat=1)
        self.assertEqual((await again.until("MATCH_CONFIG"))["your_seat"], 1)
        self.assertIsNotNone(self.match().seats[0].player, "the other window keeps its seat")
        # Naming seat 0, whose window is still open, replaces that window.
        third = await self.join("Tamsin", 1, flags=RESUME, match=self.match().id, seat=0)
        self.assertEqual((await third.until("MATCH_CONFIG"))["your_seat"], 0)
        self.assertEqual(await first.next(), ("ERROR", dict(code=ERRORS["replaced"],
                                                            text="Replaced by another session of this profile")))

    async def test_a_rejoin_without_a_checkpoint_starts_from_tick_0(self):
        tamsin, edda = await self.seated("Tamsin", "Edda")
        await self.play(60, 120, (tamsin, edda))
        await edda.drop()
        await self.play(180, 240, (tamsin,))
        again = await self.join("Edda", 2, flags=RESUME, match=self.match().id, seat=1)
        await again.until("MATCH_CONFIG")
        open_turn = self.match().loop.turn
        await self.clock.turns(2)
        got = await sync(again)
        self.assertEqual(named(got, "RESYNC"), [dict(checkpoint_tick=0, first_turn=0, reason=REASONS["rejoin"],
                                                     open_turn=open_turn, checkpoint_hash=TICK0, parts=0)])
        self.assertEqual(turn_numbers(got), list(range(self.match().loop.turn)))
        self.assertEqual(named(got, "CHECKPOINT_PART"), [])

    async def test_its_hashes_count_again_from_the_checkpoint(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        await self.play(60, 120, games, **checkpoint_at(120))
        await keep(games, 120)
        await self.play(180, 360, games)
        await games[1].drop()
        others = (games[0], games[2])
        await self.play(420, 480, others)
        again = await self.join("Edda", 2, flags=RESUME, match=self.match().id, seat=1)
        again.seat = 1
        await again.until("MATCH_CONFIG")
        await self.clock.turns(3)
        self.assertEqual(named(await sync(again), "RESYNC")[0]["checkpoint_tick"], 120)
        # (from tick 120 her game hashes 180 again, below the old link's 360:
        # compared with the agreed hashes, as late reports)
        for tick in range(180, 481, 60):
            await again.send_message("HASH", tick=tick, hash=GOOD, flags=0)
        await sync(again)
        self.assertEqual((self.match().seats[1].hash_tick, self.match().seats[1].resyncs), (480, 0))
        await self.play(540, 540, (games[0], again, games[2]), digest=lambda game, tick: b"z" * 8 if game is again else GOOD)
        self.assertEqual((self.match().seats[1].resyncs, self.match().seats[1].muted), (1, True))

    async def test_a_rejoin_while_loading_loads_as_at_the_start(self):
        await self.start("classic:2")
        tamsin, edda = await self.join("Tamsin", 1), await self.join("Edda", 2)
        for game in (tamsin, edda):
            await game.until("MATCH_CONFIG")
        await edda.drop()
        await until(lambda: self.match().seats[1].player is None)
        again = await self.join("Edda", 2, flags=RESUME, match=self.match().id, seat=1)
        config = await again.until("MATCH_CONFIG")
        self.assertEqual((config["your_seat"], config["flags"]), (1, 0))
        for game in (tamsin, again):
            await game.send_message("LOADED", rules_hash=config["rules_hash"], tick0_hash=TICK0)
        await self.clock.advance(SPEC["loading_min_ms"])
        for game in (tamsin, again):
            await game.until("START", skip=("LOAD_STATE",))
        self.assertEqual([seat.state for seat in self.match().seats], ["present", "present"])


class PartyRejoinTests(HubTest, unittest.IsolatedAsyncioTestCase):
    async def playing(self):
        await self.start()
        games, _ = await self.party_of("Tamsin", "Edda")
        await self.ready_all(games)
        configs = await self.to_loading(games)
        for game in games:
            await game.send_message("LOADED", rules_hash=configs[0]["rules_hash"], tick0_hash=TICK0)
        await self.clock.advance(SPEC["loading_min_ms"])
        for game in games:
            await game.until("START", skip=("LOAD_STATE",))
            await state(game)                                   # (in_match)
        await self.clock.advance(SPEC["start_delay_ms"])
        return games

    async def test_a_party_member_takes_back_its_row_and_then_its_seat(self):
        tamsin, edda = await self.playing()
        await edda.drop()
        dropped = await tamsin.until("PARTY_STATE", skip=("TURN", "LINKS"))
        self.assertEqual(states(dropped)["Edda"], MEMBER["away"])
        again = await self.join("Edda", 2, flags=RESUME, match=self.match().id, seat=1)
        row = await again.next()
        self.assertEqual((row[0], row[1]["you"], states(row[1])["Edda"]), ("PARTY_STATE", 1, MEMBER["in_match"]))
        self.assertEqual(row[1]["phase"], PHASES["in_match"])
        config = await again.next()
        self.assertEqual((config[0], config[1]["flags"], config[1]["your_seat"]), ("MATCH_CONFIG", REJOIN, 1))
        await self.clock.turns(1)
        self.assertEqual(named(await sync(again), "RESYNC")[0]["reason"], REASONS["rejoin"])
        seen = await tamsin.until("PARTY_STATE", skip=("TURN", "LINKS"))
        self.assertEqual(states(seen)["Edda"], MEMBER["in_match"])
        self.assertEqual((self.server.daily.today["reconnects"], self.server.daily.today["rejoins"]), (1, 1))

    async def test_a_resume_after_the_match_ended_hears_no_held_seat_and_gets_its_row(self):
        tamsin, edda = await self.playing()
        match = self.match().id
        await edda.drop()
        await tamsin.until("PARTY_STATE", skip=("TURN", "LINKS"))
        await self.clock.turns(2)
        await tamsin.send_message("RESULT", tick=6, hash=GOOD, outcomes=[dict(outcome=SPEC["outcomes"]["won"])])
        await tamsin.until("MATCH_END", skip=("TURN", "LINKS"))
        again = await self.join("Edda", 2, flags=RESUME, match=match, seat=1)
        self.assertEqual(await again.next(), ("NOTICE", dict(code=NOTICES["no_held_seat"], argument=0)))
        row = await again.until("PARTY_STATE")
        self.assertEqual((row["you"], states(row)["Edda"]), (1, MEMBER["here"]))



class StaleReportTests(MatchTest, unittest.IsolatedAsyncioTestCase):
    """A report the old connection sent just before it dropped, still waiting
    to be decided when a resume takes the seat back, is the old simulation's:
    it is let go, so the new connection gets RESYNC(rejoin) alone, not a
    RESYNC(desync) behind it that its game refuses while the rejoin loads
    (review M4 network 1)."""

    async def test_a_resume_is_not_resynced_again_for_its_old_connections_report(self):
        bad = b"z" * 8
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        await self.play(60, 60, games)
        await self.clock.turns(20)
        await games[1].send_message("HASH", tick=120, hash=bad, flags=0)    # (its last word, parted)
        await sync(games[1])
        await games[1].drop()
        again = await self.join("Edda", 2, flags=RESUME, match=self.match().id, seat=1)
        await self.clock.turns(1)
        for game in (games[0], games[2]):
            await game.send_message("HASH", tick=120, hash=GOOD, flags=0)
            await sync(game)
        await self.clock.turns(3)
        await news(again)
        reasons = [f["reason"] for f in named(again.inbox, "RESYNC")]
        self.assertEqual(reasons, [REASONS["rejoin"]], f"RESYNC reasons to the new connection: {reasons}")
        # (its re-run from the checkpoint reports tick 120 again, and agrees)
        await again.send_message("HASH", tick=60, hash=GOOD, flags=0)
        await again.send_message("HASH", tick=120, hash=GOOD, flags=0)
        await sync(again)
        self.assertEqual(self.match().agreed[120], GOOD)
        self.assertEqual(named(await news(again), "RESYNC", "MATCH_END", "ERROR"), [])


if __name__ == "__main__":
    unittest.main()
