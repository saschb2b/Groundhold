"""Away and back (docs/design/core-loop.md §6.6 to §6.8, §7.3; shared/net/README.md,
Absence and Resilience): 5 s of silence put a seat AWAY and the caretaker
plays it; its next word brings it BACK, except while its connection says
`catching_up`: then only `shown` does. A dropped seat is held to the end, and
a resume HELLO with the same identity gets the checkpoint, the turns and then,
at its `shown`, BACK. A seat started without its player, or a tab back from
the background behind the latest checkpoint, is resynced from it (behind)."""

import asyncio
import unittest

from support import (CHECKPOINT, REASONS, RESUME, VISIBLE, Client, HubTest, MatchTest, drain, named, news, party,
                     state, state_bytes, sync, turn_numbers, upload)
from groundhold_server import protocol
from groundhold_server.protocol import SPEC

SYSTEM = SPEC["system_commands"]
AWAY, BACK, LEFT = (SYSTEM[name]["type"] for name in ("AWAY", "BACK", "LEFT"))
LINK = SPEC["link_flags"]
STATE = state_bytes(2500)
AGREED = protocol.digest(STATE)
GOOD = b"h" * 8


def marked(messages):
    """The system commands in the TURNs among `messages`: [(turn, type, seat)]."""
    return [(fields["turn"], command["type"], command["a"]) for name, fields in messages if name == "TURN"
            for command in fields["commands"] if command["seat"] == protocol.SYSTEM_SEAT]


def checkpoint_at(*ticks):
    return dict(digest=lambda game, tick: AGREED if tick in ticks else GOOD,
                flags=lambda game, tick: CHECKPOINT if tick in ticks else 0)


class AwayBackTests(MatchTest, unittest.IsolatedAsyncioTestCase):
    async def keep(self, games, tick):
        """A checkpoint at `tick` (already agreed and flagged): uploaded by the seat asked."""
        for game in games:
            if named(await news(game), "CHECKPOINT_ASK"):
                await upload(game, tick, STATE)
                await sync(game)
        self.assertEqual(self.match().checkpoints[-1][:1], (tick,))

    async def test_silence_puts_a_seat_away_and_its_next_word_brings_it_back(self):
        tamsin, edda = await self.seated("Tamsin", "Edda")
        # (Tamsin hashes every second; not a word from Edda since START)
        await self.play(60, 240, (tamsin,))
        away_turn = (SPEC["away_ms"] - SPEC["start_delay_ms"]) // SPEC["turn_ms"] - 1
        self.assertEqual(marked(tamsin.inbox), [(away_turn, AWAY, 1)])
        self.assertEqual(self.match().seats[1].state, "away")
        await sync(edda)
        await self.clock.turns(1)
        self.assertEqual(marked(await sync(tamsin))[-1:], [(80, BACK, 1)])

    async def test_catching_up_holds_back_until_shown(self):
        tamsin, edda = await self.seated("Tamsin", "Edda")
        await self.play(60, 300, (tamsin,))
        self.assertEqual(self.match().seats[1].state, "away")
        await news(tamsin)
        # Her tab comes back behind: catching_up, then her PINGs, bring nothing back ...
        await edda.send_message("VISIBILITY", state=VISIBLE["catching_up"])
        await sync(edda)
        await self.play(360, 420, (tamsin,), talking=(edda,))
        self.assertEqual(marked(await news(tamsin)), [])
        self.assertEqual(self.match().seats[1].state, "away")
        links = protocol.decode(self.match().links())[1]["seats"]
        self.assertEqual(links[1]["flags"], LINK["silent"] | LINK["catching_up"])
        # ... until she says shown: BACK in the next turn (the simulation hands
        # the seat back at the next build window).
        await edda.send_message("VISIBILITY", state=VISIBLE["shown"])
        await sync(edda)
        turn = self.match().loop.turn
        await self.clock.turns(1)
        self.assertEqual(marked(await news(tamsin)), [(turn, BACK, 1)])
        self.assertEqual(self.match().seats[1].state, "present")

    async def test_a_dropped_seat_is_held_and_its_resume_gets_the_checkpoint_the_turns_and_then_back(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        await self.play(60, 120, games, **checkpoint_at(120))
        await self.keep(games, 120)
        await games[1].drop()
        others = (games[0], games[2])
        # (a minute later her seat is still hers: held until the match ends)
        await self.play(180, 3780, others)
        self.assertEqual(self.match().seats[1].state, "away")
        await news(games[0])
        self.assertIn((AWAY, 1), [entry[1:] for entry in marked(games[0].inbox)])
        again = await self.join("Edda", 2, flags=RESUME, match=self.match().id, seat=1)
        self.assertEqual(again.answer[0], "WELCOME")
        config = await again.until("MATCH_CONFIG")
        self.assertEqual((config["your_seat"], config["flags"], [s["name"] for s in config["seats"]]),
                         (1, SPEC["config_flags"]["rejoin"], ["Tamsin", "Edda", "Ottilie"]))
        open_turn = self.match().loop.turn
        await self.clock.turns(8)
        got = await sync(again)
        self.assertEqual(named(got, "RESYNC"), [dict(checkpoint_tick=120, first_turn=40, reason=REASONS["rejoin"],
                                                     open_turn=open_turn, checkpoint_hash=AGREED, parts=3)])
        parts = named(got, "CHECKPOINT_PART")
        self.assertEqual(b"".join(part["data"] for part in parts), STATE)
        # (then every turn from the checkpoint's, once, in order, the live ones behind)
        self.assertEqual(turn_numbers(got), list(range(40, self.match().loop.turn)))
        # Her game counts as catching up: its words bring nothing back ...
        await self.clock.turns(1)
        await sync(again)
        self.assertEqual(self.match().seats[1].state, "away")
        # ... until it says shown.
        await again.send_message("VISIBILITY", state=VISIBLE["shown"])
        await sync(again)
        await self.clock.turns(1)
        self.assertEqual(marked(await news(games[0]))[-1][1:], (BACK, 1))
        self.assertEqual(self.server.daily.today["rejoins"], 1)

    async def test_a_seat_that_left_is_not_held(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        await games[1].send_message("LEAVE_MATCH")
        await sync(games[1])
        await self.clock.turns(1)
        self.assertEqual(marked(await news(games[0])), [(0, LEFT, 1)])
        again = await self.join("Edda", 2, flags=RESUME, match=self.match().id, seat=1)
        self.assertEqual(again.answer[0], "WELCOME")
        self.assertEqual(await again.next(), ("NOTICE", dict(code=SPEC["notices"]["no_held_seat"], argument=0)))
        self.assertEqual(self.match().seats[1].player, None)

    async def test_a_tab_back_behind_the_latest_checkpoint_is_resynced_once(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        await self.play(60, 120, games)
        # (Edda's tab hides after tick 120: her loop, and so her PINGs, stop)
        await games[1].send_message("VISIBILITY", state=VISIBLE["hidden"])
        others = (games[0], games[2])
        await self.play(180, 480, others)
        self.assertEqual(self.match().seats[1].state, "away")
        await self.play(540, 540, others, **checkpoint_at(540))
        await self.keep(others, 540)
        await self.play(600, 720, others)
        # She comes back behind it: RESYNC(behind) from tick 540.
        await games[1].send_message("VISIBILITY", state=VISIBLE["catching_up"])
        await sync(games[1])
        open_turn = self.match().loop.turn
        await self.clock.turns(4)
        got = await sync(games[1])
        self.assertEqual(named(got, "RESYNC"), [dict(checkpoint_tick=540, first_turn=180, reason=REASONS["behind"],
                                                     open_turn=open_turn, checkpoint_hash=AGREED, parts=3)])
        # (behind the parts every turn from tick 540's, to the live one, once each)
        after = got[[name for name, _ in got].index("RESYNC"):]
        self.assertEqual(turn_numbers(after), list(range(180, self.match().loop.turn)))
        # Saying it again from the same checkpoint brings no second one; her
        # HASHes count on from it, and shown brings BACK.
        await games[1].send_message("VISIBILITY", state=VISIBLE["catching_up"])
        await self.clock.turns(1)
        self.assertEqual(named(await sync(games[1]), "RESYNC"), [])
        for tick in (600, 660):
            await games[1].send_message("HASH", tick=tick, hash=GOOD, flags=0)
        await games[1].send_message("VISIBILITY", state=VISIBLE["shown"])
        await sync(games[1])
        self.assertEqual(self.match().seats[1].hash_tick, 660)
        await self.clock.turns(1)
        self.assertEqual(marked(await news(games[0]))[-1][1:], (BACK, 1))
        self.assertEqual(self.server.daily.today["resyncs"], 1)

    async def test_after_a_resync_behind_its_hashes_never_go_back_again(self):
        """RESYNC(behind) lets a HASH from the checkpoint on go below the seat's
        last one; once its game hashes on past that, none may go back again."""
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        await self.play(60, 120, games)
        await games[1].send_message("VISIBILITY", state=VISIBLE["hidden"])
        others = (games[0], games[2])
        await self.play(180, 480, others)
        await self.play(540, 540, others, **checkpoint_at(540))
        await self.keep(others, 540)
        await self.play(600, 720, others)
        await games[1].send_message("VISIBILITY", state=VISIBLE["catching_up"])
        await sync(games[1])
        await self.clock.turns(4)
        self.assertEqual([f["reason"] for f in named(await sync(games[1]), "RESYNC")], [REASONS["behind"]])
        for tick in (600, 660, 720):
            await games[1].send_message("HASH", tick=tick, hash=GOOD, flags=0)
        await sync(games[1])
        self.assertIsNone(self.match().seats[1].restart, "past its checkpoint the seat counts on as any")
        await games[1].send_message("HASH", tick=660, hash=GOOD, flags=0)
        got = await drain(games[1], 0.1)
        self.assertTrue(named(got, "ERROR"), "a HASH that goes back again is refused")

    async def test_catching_up_with_no_checkpoint_ahead_brings_no_resync(self):
        games = await self.seated("Tamsin", "Edda", "Ottilie")
        await self.play(60, 120, games, **checkpoint_at(120))
        await self.keep(games, 120)
        await self.play(180, 180, games)
        await games[1].send_message("VISIBILITY", state=VISIBLE["catching_up"])
        await self.clock.turns(2)
        self.assertEqual(named(await sync(games[1]), "RESYNC"), [])


class StartedWithoutTests(HubTest, unittest.IsolatedAsyncioTestCase):
    async def test_a_seat_started_without_catches_up_from_the_latest_checkpoint_and_is_back_at_shown(self):
        await self.start()
        (tamsin, edda), _ = await self.party_of("Tamsin", "Edda")
        await self.ready_all((tamsin, edda))
        await self.to_loading((tamsin, edda))
        await tamsin.send_message("LOADED", rules_hash=self.match().rules_hash, tick0_hash=bytes(8))
        # (Edda's game is slow to load: the leader starts without her from 30 s)
        await self.clock.advance(30_000)
        await party(tamsin, "start")
        await tamsin.until("START", skip=("LOAD_STATE",))
        await self.clock.advance(SPEC["start_delay_ms"])
        tamsin.seat, edda.seat = 0, 1
        for tick in (60, 120):
            await self.clock.turns(20)
            await tamsin.send_message("HASH", tick=tick, hash=AGREED if tick == 120 else GOOD,
                                      flags=CHECKPOINT if tick == 120 else 0)
            await sync(tamsin)
        await upload(tamsin, 120, STATE)
        await sync(tamsin)
        self.assertEqual([tick for tick, _, _ in self.match().checkpoints], [120])
        self.assertEqual(self.match().seats[1].state, "away")
        # She knows she was started without (START came before her LOADED):
        # catching_up first, then LOADED, then RESYNC(behind) from tick 120.
        await edda.send_message("VISIBILITY", state=VISIBLE["catching_up"])
        await edda.send_message("LOADED", rules_hash=self.match().rules_hash, tick0_hash=bytes(8))
        await sync(edda)
        open_turn = self.match().loop.turn
        await self.clock.turns(4)
        got = await sync(edda)
        self.assertEqual(named(got, "RESYNC"), [dict(checkpoint_tick=120, first_turn=40, reason=REASONS["behind"],
                                                     open_turn=open_turn, checkpoint_hash=AGREED, parts=3)])
        self.assertEqual(self.match().seats[1].state, "away", "catching up holds her BACK")
        await edda.send_message("VISIBILITY", state=VISIBLE["shown"])
        await sync(edda)
        turn = self.match().loop.turn
        await self.clock.turns(1)
        self.assertIn((turn, BACK, 1), marked(await news(tamsin)))



class HiddenTabTests(MatchTest, unittest.IsolatedAsyncioTestCase):
    """A hidden browser tab (design §6.8; shared/net/README.md, Visibility):
    its loop sleeps, so its PINGs stop and 5 s later its seat is AWAY, but its
    link is kept, the 1 MiB buffer holding the turns, past the silence rule's
    15 s, for up to hidden_silence_ms; and when it comes back, nothing but
    `shown` brings its seat BACK, whatever it sends first (review M4 network 1).
    The silence rules run on the socket's own wait, shortened here to
    fractions of a second."""

    async def test_a_hidden_tab_keeps_its_link_through_the_silence_rule(self):
        tamsin, edda = await self.seated("Tamsin", "Edda", silence_timeout=0.2)
        await edda.send_message("VISIBILITY", state=VISIBLE["hidden"])
        await sync(edda)
        for _ in range(6):          # (three silence timeouts of the hidden tab; Tamsin talks)
            await asyncio.sleep(0.1)
            await sync(tamsin)
        got = await drain(edda, 0.05)
        self.assertFalse(("CLOSE", None) in got or edda.reader.at_eof() or self.match().seats[1].player is None,
                         "the hidden tab's link was closed for silence")
        # (back: its first word is answered as ever)
        await sync(edda)

    async def test_a_hidden_tab_silent_past_hidden_silence_ms_is_closed(self):
        tamsin, edda = await self.seated("Tamsin", "Edda", silence_timeout=0.2, hidden_timeout=0.4)
        await edda.send_message("VISIBILITY", state=VISIBLE["hidden"])
        await sync(edda)
        for _ in range(10):
            await asyncio.sleep(0.1)
            await sync(tamsin)
        try:
            got = await drain(edda, 0.05)
        except asyncio.IncompleteReadError:
            got = [("CLOSE", None)]         # (closed under the read)
        self.assertTrue(("CLOSE", None) in got or edda.reader.at_eof(), "a hidden tab silent for good is let go")
        self.assertIsNone(self.match().seats[1].player, "and its seat is held, as after a drop")

    async def test_a_tab_back_from_hidden_comes_back_only_at_shown(self):
        """Back after 6 s hidden, the game's first words may be a PING or a
        TURN_REQUEST before it says catching_up or shown: none of them brings
        the seat BACK, only shown does."""
        tamsin, edda = await self.seated("Tamsin", "Edda")
        await self.play(60, 60, (tamsin, edda))
        await edda.send_message("VISIBILITY", state=VISIBLE["hidden"])
        await sync(edda)
        await self.play(120, 420, (tamsin,))                # (6 s: AWAY)
        self.assertEqual(self.match().seats[1].state, "away")
        await news(tamsin)
        await edda.send_message("PING", client_ms=77, rtt_ms=0)
        await edda.send_message("TURN_REQUEST", first_missing=100)
        await edda.send_message("VISIBILITY", state=VISIBLE["catching_up"])
        await sync(edda)
        await self.clock.turns(2)
        self.assertEqual(marked(await news(tamsin)), [], "BACK went out while the game catches up")
        await edda.send_message("VISIBILITY", state=VISIBLE["shown"])
        await sync(edda)
        turn = self.match().loop.turn
        await self.clock.turns(1)
        self.assertEqual(marked(await news(tamsin)), [(turn, BACK, 1)])

    async def test_a_tab_shown_again_and_level_comes_back_at_its_shown(self):
        tamsin, edda = await self.seated("Tamsin", "Edda")
        await edda.send_message("VISIBILITY", state=VISIBLE["hidden"])
        await sync(edda)
        await self.play(60, 360, (tamsin,))
        self.assertEqual(self.match().seats[1].state, "away")
        await news(tamsin)
        await edda.send_message("PING", client_ms=78, rtt_ms=0)
        await sync(edda)
        await self.clock.turns(2)
        self.assertEqual(marked(await news(tamsin)), [], "a PING from a tab still hidden brings nothing back")
        await edda.send_message("VISIBILITY", state=VISIBLE["shown"])
        await sync(edda)
        turn = self.match().loop.turn
        await self.clock.turns(1)
        self.assertEqual(marked(await news(tamsin)), [(turn, BACK, 1)])


if __name__ == "__main__":
    unittest.main()
