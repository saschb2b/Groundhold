"""RESYNC for a minority (docs/design/core-loop.md §6.7; shared/net/README.md,
Resilience: RESYNC and Desyncs): with three seats or more a seat whose hash
differs from the agreed one is brought back from the latest checkpoint kept
before its last HASH: RESYNC(desync), the checkpoint's parts, the turns since
and the live ones; apart again after one resync, it is out of the match
(desynced_twice) and back in its party's hub as after LEAVE_MATCH."""

import unittest

from support import (CHECKPOINT, MEMBER, REASONS, TICK0, HubTest, MatchTest, named, news, state, states,
                     state_bytes, sync, turn_numbers, upload)
from groundhold_server import protocol
from groundhold_server.protocol import SPEC

OUTCOMES, ENDS = SPEC["outcomes"], SPEC["end_reasons"]
GOOD, BAD = b"h" * 8, b"z" * 8


def states_at(ticks):
    """Checkpoints at `ticks`, each its own bytes."""
    return {tick: state_bytes(3000 + tick, salt=tick % 7) for tick in ticks}


class MinorityResyncTests(MatchTest, unittest.IsolatedAsyncioTestCase):
    async def test_a_minority_resyncs_from_the_latest_checkpoint_before_its_last_hash(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        kept = states_at((120, 240))
        checkpoint = dict(digest=lambda game, tick: protocol.digest(kept[tick]) if tick in kept else GOOD,
                          flags=lambda game, tick: CHECKPOINT if tick in kept else 0)
        for tick in (120, 240):
            await self.play(tick - 60, tick, games, **checkpoint)
            for game in games:
                if named(await news(game), "CHECKPOINT_ASK"):
                    await upload(game, tick, kept[tick])
                    await sync(game)
        self.assertEqual([tick for tick, _, _ in self.match().checkpoints], [120, 240])
        await self.play(300, 360, games, digest=lambda game, tick: BAD if game.seat == 2 and tick == 360 else GOOD)
        open_turn = self.match().loop.turn
        await self.clock.turns(4)
        got = await news(games[2])
        resync = named(got, "RESYNC")
        self.assertEqual(resync, [dict(checkpoint_tick=240, first_turn=80, reason=REASONS["desync"], open_turn=open_turn,
                                       checkpoint_hash=protocol.digest(kept[240]), parts=4)])
        after = got[[name for name, _ in got].index("RESYNC"):]
        self.assertEqual(b"".join(part["data"] for part in named(after, "CHECKPOINT_PART")), kept[240])
        self.assertEqual(turn_numbers(after), list(range(80, self.match().loop.turn)))
        # (she goes back to tick 240 and hashes on from it: compared, and agreed)
        for tick in (300, 360):
            await games[2].send_message("HASH", tick=tick, hash=GOOD, flags=0)
        await sync(games[2])
        self.assertEqual((self.match().seats[2].muted, self.match().seats[2].hash_tick), (False, 360))
        await self.play(420, 420, games)
        self.assertEqual([seat.state for seat in self.match().seats], ["present"] * 3)

    async def test_a_minority_without_a_checkpoint_before_its_hash_starts_from_tick_0(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        kept = states_at((120,))
        await self.play(60, 120, games, digest=lambda game, tick: protocol.digest(kept[120]) if tick == 120 else
                        (BAD if game.seat == 1 else GOOD), flags=lambda game, tick: CHECKPOINT if tick == 120 else 0)
        await self.clock.turns(1)
        resync = named(await news(games[1]), "RESYNC")
        self.assertEqual([(r["checkpoint_tick"], r["checkpoint_hash"], r["parts"]) for r in resync], [(0, TICK0, 0)])


class PartyDesyncTests(HubTest, unittest.IsolatedAsyncioTestCase):
    async def test_a_member_apart_twice_is_back_in_the_hub_and_its_seat_left(self):
        await self.start()
        games, _ = await self.party_of("Tamsin", "Edda", "Ottilie")
        await self.ready_all(games)
        configs = await self.to_loading(games)
        for game in games:
            await game.send_message("LOADED", rules_hash=configs[0]["rules_hash"], tick0_hash=TICK0)
        await self.clock.advance(SPEC["loading_min_ms"])
        for game in games:
            await game.until("START", skip=("LOAD_STATE",))
            await state(game)
        await self.clock.advance(SPEC["start_delay_ms"])
        # (Ottilie's game parts at 60, goes back to tick 0 and parts again at 120)
        for tick, digests in ((60, (GOOD, GOOD, BAD)), (120, (GOOD, GOOD, BAD))):
            await self.clock.turns(20)
            if tick == 120:
                await games[2].send_message("HASH", tick=60, hash=GOOD, flags=0)
            for game, digest in zip(games, digests):
                await game.send_message("HASH", tick=tick, hash=digest, flags=0)
            for game in games:
                await sync(game)
        self.assertEqual(named(games[2].inbox, "MATCH_END"), [dict(outcome=OUTCOMES["desynced"],
                                                                   reason=ENDS["desynced_twice"], final_tick=120)])
        seen = named(await news(games[0]), "PARTY_STATE")[-1]
        self.assertEqual(states(seen), {"Tamsin": MEMBER["in_match"], "Edda": MEMBER["in_match"],
                                        "Ottilie": MEMBER["here"]})
        self.assertEqual(self.match().seats[2].state, "left")
        self.assertEqual(len(self.server.matches), 1)


if __name__ == "__main__":
    unittest.main()
