"""The checkpoint store (docs/design/core-loop.md §6.7, §7.3; shared/net/README.md,
Resilience: Checkpoints): once the seats agree on a hash tick a game flagged
as a checkpoint, one seat in rotation (present, not hidden, not catching up,
one that flagged the agreed hash) is asked for it; an upload is kept only if
SHA-256(bytes)[:8] is the agreed hash, and the last two kept; an upload with
another digest, or not whole 5 s after the ask, is dropped and the next seat
asked. The parts' rules end a link that breaks them."""

import unittest

from support import CHECKPOINT, VISIBLE, MatchTest, drain, named, news, state_bytes, sync, upload
from groundhold_server import protocol
from groundhold_server.protocol import SPEC

ERRORS = SPEC["errors"]
STATE = state_bytes(2500)                       # (three parts: 1,024, 1,024 and 452 bytes)
AGREED = protocol.digest(STATE)
GOOD = b"h" * 8


def at(*ticks, state=STATE):
    """Each game's digest and flags when ticks `ticks` are checkpoints of `state`."""
    def digest(game, tick):
        return protocol.digest(state) if tick in ticks else GOOD

    def flags(game, tick):
        return CHECKPOINT if tick in ticks else 0
    return dict(digest=digest, flags=flags)


class CheckpointCase(MatchTest):
    async def asks(self, games):
        """Each game's CHECKPOINT_ASK ticks since the last look."""
        return [[fields["tick"] for fields in named(await news(game), "CHECKPOINT_ASK")] for game in games]

    async def asked(self):
        """Three seats, tick 120 agreed and flagged: the seat asked for it."""
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        await self.play(60, 120, games, **at(120))
        self.assertEqual(await self.asks(games), [[120], [], []])
        return games


class CheckpointTests(CheckpointCase, unittest.IsolatedAsyncioTestCase):
    async def test_an_agreed_checkpoint_is_asked_of_one_seat_and_kept_when_its_digest_agrees(self):
        games = await self.asked()
        await upload(games[0], 120, STATE)
        await sync(games[0])
        self.assertEqual(self.match().checkpoints, [(120, STATE, AGREED)])
        self.assertIsNone(self.match().upload)
        # (nobody is told: the next RESYNC starts from it)
        for game in games:
            self.assertEqual(named(await sync(game), "CHECKPOINT_ASK", "RESYNC", "ERROR"), [])

    async def test_an_upload_with_another_digest_is_dropped_and_the_next_seat_asked(self):
        games = await self.asked()
        await upload(games[0], 120, state_bytes(2500, salt=1))      # (as long, other bytes)
        await sync(games[0])
        self.assertEqual(self.match().checkpoints, [])
        self.assertEqual(await self.asks(games), [[], [120], []])
        await upload(games[1], 120, STATE)
        await sync(games[1])
        self.assertEqual(self.match().checkpoints, [(120, STATE, AGREED)])

    async def test_an_upload_not_whole_in_five_seconds_goes_to_the_next_seat(self):
        games = await self.asked()
        parts = protocol.checkpoint_parts(120, STATE)
        await games[0].send(parts[0])
        await self.play(180, 120 + SPEC["checkpoint_wait_ms"] // 1000 * 60 - 60, games)
        self.assertEqual(await self.asks(games), [[], [], []], "under 5 s it is still waited for")
        await self.play(120 + SPEC["checkpoint_wait_ms"] // 1000 * 60, 120 + SPEC["checkpoint_wait_ms"] // 1000 * 60,
                        games)
        self.assertEqual(await self.asks(games), [[], [120], []])
        # (the rest of the first seat's parts, too late, are let pass)
        for part in parts[1:]:
            await games[0].send(part)
        self.assertEqual(named(await sync(games[0]), "ERROR"), [])
        await upload(games[1], 120, STATE)
        await sync(games[1])
        self.assertEqual([tick for tick, _, _ in self.match().checkpoints], [120])

    async def test_a_seat_whose_link_goes_before_its_upload_is_whole_hands_the_ask_on_at_once(self):
        games = await self.asked()
        await games[0].send(protocol.checkpoint_parts(120, STATE)[0])
        await sync(games[0])
        # (its link drops: no more parts will come, so nobody waits 5 s for them)
        await games[0].drop()
        await self.clock.turns(1)
        self.assertEqual((await self.asks(games[1:])), [[120], []])
        # (and the one asked next leaves the match: the last keeper is asked)
        await games[1].send_message("LEAVE_MATCH")
        await self.clock.turns(1)
        self.assertEqual((await self.asks(games[1:])), [[], [120]])
        await upload(games[2], 120, STATE)
        await sync(games[2])
        self.assertEqual(self.match().checkpoints, [(120, STATE, AGREED)])

    async def test_the_seats_are_asked_in_rotation_and_the_last_two_kept(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        kept = []
        for number, tick in enumerate((120, 240, 360, 480)):
            await self.play(tick - 60, tick, games, **at(tick, state=state_bytes(1500 + tick)))
            asks = await self.asks(games)
            self.assertEqual(asks, [[tick] if index == number % 3 else [] for index in range(3)], tick)
            await upload(games[number % 3], tick, state_bytes(1500 + tick))
            await sync(games[number % 3])
            kept = [tick for tick, _, _ in self.match().checkpoints]
        self.assertEqual(kept, [360, 480])
        self.assertEqual(self.match().checkpoints[-1][1], state_bytes(1980))

    async def test_only_a_seat_that_keeps_it_and_may_upload_is_asked(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie", "Sefa")
        await games[0].send_message("VISIBILITY", state=VISIBLE["hidden"])
        await games[1].send_message("VISIBILITY", state=VISIBLE["catching_up"])
        # (Ottilie did not flag the tick: her game keeps no checkpoint there)
        checkpoint = at(120)
        await self.play(60, 120, games, digest=checkpoint["digest"],
                        flags=lambda game, tick: 0 if game.seat == 2 else checkpoint["flags"](game, tick))
        self.assertEqual(await self.asks(games), [[], [], [], [120]])
        # With nobody left who may, the tick is given up.
        await upload(games[3], 120, state_bytes(2500, salt=3))
        await sync(games[3])
        self.assertEqual(await self.asks(games), [[], [], [], []])
        self.assertIsNone(self.match().upload)
        self.assertEqual(self.match().checkpoints, [])

    async def test_a_minority_is_not_asked_and_tick_0_never(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        await self.clock.turns(1)
        for game in games:
            await game.send_message("HASH", tick=0, hash=GOOD, flags=CHECKPOINT)
        self.assertEqual(await self.asks(games), [[], [], []])
        checkpoint = at(120)
        await self.play(60, 120, games, flags=checkpoint["flags"],
                        digest=lambda game, tick: b"z" * 8 if game.seat == 0 and tick == 120 else checkpoint["digest"](game, tick))
        self.assertEqual(await self.asks(games), [[], [120], []])


class PartRuleTests(CheckpointCase, unittest.IsolatedAsyncioTestCase):
    """A part that breaks the rules ends its link, with ERROR 1 (a tick never
    asked of that seat) or ERROR 6 (out of order, past the limit, a changed
    count, a short part before the last)."""

    async def refused(self, game, code):
        await drain(game)
        error = named(game.inbox, "ERROR")
        self.assertEqual([fields["code"] for fields in error], [code])

    async def test_a_part_never_asked_of_the_seat_is_error_1(self):
        games = await self.asked()
        await upload(games[1], 120, STATE)
        await self.refused(games[1], ERRORS["protocol"])
        await upload(games[0], 120, STATE)                  # (the asked seat's is kept)
        await sync(games[0])
        self.assertEqual([tick for tick, _, _ in self.match().checkpoints], [120])

    async def test_a_part_out_of_order_is_error_6(self):
        games = await self.asked()
        await games[0].send(protocol.checkpoint_parts(120, STATE)[1])
        await self.refused(games[0], ERRORS["out_of_limits"])

    async def test_a_changed_count_is_error_6(self):
        games = await self.asked()
        parts = protocol.checkpoint_parts(120, STATE)
        await games[0].send(parts[0])
        await games[0].send_message("CHECKPOINT_PART", tick=120, part=1, parts=4, data=bytes(1024))
        await self.refused(games[0], ERRORS["out_of_limits"])

    async def test_more_than_the_most_parts_is_error_6(self):
        games = await self.asked()
        await upload(games[0], 120, STATE, parts=SPEC["max_checkpoint_parts"] + 1)
        await self.refused(games[0], ERRORS["out_of_limits"])

    async def test_a_short_part_before_the_last_is_error_6(self):
        games = await self.asked()
        await games[0].send_message("CHECKPOINT_PART", tick=120, part=0, parts=3, data=bytes(1000))
        await self.refused(games[0], ERRORS["out_of_limits"])


if __name__ == "__main__":
    unittest.main()
