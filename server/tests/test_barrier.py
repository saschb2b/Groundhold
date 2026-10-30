"""The loading barrier's timers (docs/design/core-loop.md §6.6, Appendix A,
§7.3 test_barrier): the 4 s minimum, Slow at 15 s, the leader's start
without the slow seats at 30 s, a strangers' match starting by itself at
45 s, the 120 s ceiling, and tick-0 hashes apart aborting back to the
party. Every timer is the server's clock, moved by hand."""

import unittest

from support import LOAD, MEMBER, NOTICES, PHASES, RULES, TICK0, HubTest, party, state, states, until
from groundhold_server.protocol import SPEC

SYSTEM = SPEC["system_commands"]
OUTCOMES = SPEC["outcomes"]
REASONS = SPEC["end_reasons"]


def system(turn):
    return [(SYSTEM_NAMES[c["type"]], c["a"]) for c in turn["commands"] if c["seat"] == SPEC["system_seat"]]


SYSTEM_NAMES = {spec["type"]: name for name, spec in SYSTEM.items()}


class BarrierTests(HubTest, unittest.IsolatedAsyncioTestCase):
    async def loading(self, *names):
        clients, _ = await self.party_of(*names)
        await self.ready_all(clients)
        configs = await self.to_loading(clients)
        for client in clients:
            await client.until("LOAD_STATE")
        return clients, configs

    async def loaded(self, client, tick0=TICK0):
        await client.send_message("LOADED", rules_hash=RULES, tick0_hash=tick0)

    async def first_turn(self, client, started=False):
        """Through START (unless read already) and the start delay to TURN(0)."""
        if not started:
            await client.until("START", skip=("LOAD_STATE", "PARTY_STATE"))
        await self.clock.advance(SPEC["start_delay_ms"])
        await self.clock.turns(1)
        return await client.until("TURN", skip=("LOAD_STATE", "PARTY_STATE"))

    async def test_the_minimum_shows_four_seconds_and_none_alone(self):
        await self.start()
        (tamsin, edda), _ = await self.loading("Tamsin", "Edda")
        await self.loaded(tamsin)
        await self.loaded(edda)
        await self.clock.advance(SPEC["loading_min_ms"] - 1)
        await tamsin.until("LOAD_STATE")
        await tamsin.until("LOAD_STATE")
        await tamsin.until("LOAD_STATE")
        self.assertTrue(await tamsin.quiet())
        await self.clock.advance(1)
        await tamsin.until("START")
        # (a party of one starts as soon as it loads)
        sefa = await self.join("Sefa", 9)
        await party(sefa, "create", mode=SPEC["modes"]["high_water"]["id"])
        await state(sefa)
        await party(sefa, "start")
        await state(sefa)
        await self.clock.advance(3000)
        await sefa.until("MATCH_CONFIG", skip=("PARTY_STATE",))
        await self.loaded(sefa)
        await self.clock.advance(0)
        await sefa.until("START", skip=("LOAD_STATE",))

    async def test_a_seat_not_loaded_at_fifteen_seconds_is_slow(self):
        await self.start()
        (tamsin, edda), _ = await self.loading("Tamsin", "Edda")
        await self.loaded(tamsin)
        await edda.send_message("LOADING", per_mille=250)
        for client in (tamsin, edda):
            await client.until("LOAD_STATE")
            await client.until("LOAD_STATE")
        await self.clock.advance(15_000 - 1)
        self.assertTrue(await tamsin.quiet())
        await self.clock.advance(1)
        slow = await tamsin.until("LOAD_STATE")
        self.assertEqual(slow, dict(seconds=15, seats=[dict(seat=0, per_mille=1000, state=LOAD["checking"]),
                                                       dict(seat=1, per_mille=250, state=LOAD["slow"])]))
        # (still slow as it reports progress; LOADED ends it)
        await edda.send_message("LOADING", per_mille=900)
        self.assertEqual((await tamsin.until("LOAD_STATE"))["seats"][1], dict(seat=1, per_mille=900, state=LOAD["slow"]))
        await self.loaded(edda)
        await tamsin.until("LOAD_STATE")
        ready = await tamsin.until("LOAD_STATE")
        self.assertEqual({s["state"] for s in ready["seats"]}, {LOAD["ready"]})
        await tamsin.until("START")

    async def test_the_leader_may_start_without_a_slow_seat_from_thirty_seconds(self):
        await self.start()
        (tamsin, edda), _ = await self.loading("Tamsin", "Edda")
        await self.loaded(tamsin)
        await self.clock.advance(30_000 - 1)
        await party(tamsin, "start")
        refused = await tamsin.until("PARTY_STATE", skip=("LOAD_STATE",))
        self.assertEqual(refused["phase"], PHASES["loading"])
        await self.clock.advance(1)
        thirty = await tamsin.until("LOAD_STATE")
        self.assertEqual(thirty["seconds"], 30)
        await party(edda, "start")                    # (a member's: refused)
        self.assertEqual((await edda.until("PARTY_STATE", skip=("LOAD_STATE",)))["phase"], PHASES["loading"])
        await party(tamsin, "start")
        await tamsin.until("START", skip=("LOAD_STATE",))
        playing = await state(tamsin)
        self.assertEqual(playing["phase"], PHASES["in_match"])
        turn = await self.first_turn(tamsin, started=True)
        # (the seat still loading begins AWAY: the caretaker plays it)
        self.assertEqual(system(turn), [("AWAY", 1)])
        # (its LOADING and PINGs bring no BACK; its LOADED with the same hashes does)
        await edda.send_message("LOADING", per_mille=800)
        await edda.send_message("PING", client_ms=1, rtt_ms=9)
        await edda.until("PONG", skip=("START", "TURN", "LOAD_STATE", "PARTY_STATE"))
        await self.clock.turns(1)
        self.assertEqual(system(await tamsin.until("TURN", skip=("LINKS",))), [])
        await self.loaded(edda)
        await until(lambda: self.match().seats[1].state == "present")
        await self.clock.turns(1)
        self.assertEqual(system(await tamsin.until("TURN", skip=("LINKS",))), [("BACK", 1)])

    async def test_a_late_seat_with_another_tick0_hash_is_out(self):
        await self.start()
        (tamsin, edda), _ = await self.loading("Tamsin", "Edda")
        await self.loaded(tamsin)
        await self.clock.advance(30_000)
        await party(tamsin, "start")
        await self.first_turn(tamsin)
        await self.loaded(edda, bytes(8))
        notice = await edda.until("NOTICE", skip=("START", "TURN", "LOAD_STATE", "PARTY_STATE", "LINKS"))
        self.assertEqual(notice, dict(code=NOTICES["tick0_mismatch"], argument=1))
        end = await edda.until("MATCH_END")
        self.assertEqual((end["outcome"], end["reason"]), (OUTCOMES["aborted"], REASONS["tick0_mismatch"]))
        await self.clock.turns(1)
        self.assertEqual(system(await tamsin.until("TURN", skip=("PARTY_STATE",))), [("LEFT", 1)])

    async def test_a_match_of_strangers_starts_by_itself_at_forty_five_seconds(self):
        await self.start(dev_match="classic:2")
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        for client in (one, two):
            await client.until("MATCH_CONFIG")
        await self.loaded(one)
        await self.clock.advance(45_000 - 1)
        self.assertEqual(self.match().phase, "loading")
        await self.clock.advance(1)
        turn = await self.first_turn(two)
        self.assertEqual(system(turn), [("AWAY", 1)])

    async def test_the_ceiling_puts_the_seats_still_loading_out(self):
        await self.start()
        (tamsin, edda, ottilie), _ = await self.loading("Tamsin", "Edda", "Ottilie")
        await self.loaded(tamsin)
        await self.loaded(ottilie)
        await self.clock.advance(120_000 - 1)
        self.assertEqual(self.match().phase, "loading")
        await self.clock.advance(1)
        end = await edda.until("MATCH_END", skip=("LOAD_STATE",))
        self.assertEqual(end, dict(outcome=OUTCOMES["aborted"], reason=REASONS["timeout"], final_tick=0))
        # (back in the party's hub at once, while the others play)
        back = await edda.until("PARTY_STATE")
        self.assertEqual(states(back), {"Tamsin": MEMBER["in_match"], "Edda": MEMBER["here"],
                                        "Ottilie": MEMBER["in_match"]})
        turn = await self.first_turn(tamsin)
        self.assertEqual(system(turn), [("LEFT", 1)])

    async def test_nobody_loaded_at_the_ceiling_brings_the_party_back(self):
        await self.start()
        (tamsin, edda), _ = await self.loading("Tamsin", "Edda")
        await self.clock.advance(120_000)
        for client in (tamsin, edda):
            end = await client.until("MATCH_END", skip=("LOAD_STATE",))
            self.assertEqual((end["outcome"], end["reason"]), (OUTCOMES["aborted"], REASONS["timeout"]))
            back = await state(client)
            self.assertEqual((back["phase"], set(states(back).values())), (PHASES["forming"], {MEMBER["here"]}))
        self.assertFalse(self.server.matches)

    async def test_nobody_loaded_dissolves_a_match_of_strangers(self):
        await self.start(dev_match="classic:2")
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        await self.clock.advance(120_000)
        for client in (one, two):
            notice = await client.until("NOTICE", skip=("MATCH_CONFIG", "LOAD_STATE"))
            self.assertEqual(notice, dict(code=NOTICES["match_dissolved"], argument=0))
            end = await client.until("MATCH_END")
            self.assertEqual((end["outcome"], end["reason"]), (OUTCOMES["aborted"], REASONS["timeout"]))

    async def test_the_ceiling_still_comes_for_a_seat_started_without(self):
        sealed = []
        await self.start(observer=lambda turn, now, entries: sealed.extend(
            (turn, SYSTEM_NAMES[e[2]], e[3]) for e in entries if e[0] == SPEC["system_seat"]))
        (tamsin, edda), _ = await self.loading("Tamsin", "Edda")
        await self.loaded(tamsin)
        await self.clock.advance(30_000)
        await party(tamsin, "start")
        await self.first_turn(tamsin)
        # (Tamsin plays on and pings; Edda never loads)
        for _ in range(45):
            await self.clock.advance(2000)
            await tamsin.send_message("PING", client_ms=0, rtt_ms=5)
            await tamsin.until("PONG", skip=("TURN", "LINKS", "PARTY_STATE"))
        end = await edda.until("MATCH_END", skip=("START", "TURN", "LOAD_STATE", "PARTY_STATE", "LINKS"))
        self.assertEqual((end["outcome"], end["reason"]), (OUTCOMES["aborted"], REASONS["timeout"]))
        # (AWAY in turn 0; LEFT in the first turn sealed once 120 s since
        # MATCH_CONFIG passed: the clock moves 2 s, 40 turns, at a time)
        ceiling_turn = (120_000 - 30_000 - SPEC["start_delay_ms"]) // SPEC["turn_ms"]
        self.assertEqual([entry[1:] for entry in sealed], [("AWAY", 1), ("LEFT", 1)])
        self.assertEqual(sealed[0][0], 0)
        self.assertTrue(ceiling_turn - 40 < sealed[1][0] <= ceiling_turn, sealed)

    async def test_tick0_hashes_apart_abort_back_to_the_party_naming_the_seat(self):
        await self.start()
        clients, _ = await self.loading("Tamsin", "Edda", "Ottilie")
        for client, tick0 in zip(clients, (TICK0, bytes(8), TICK0)):
            await self.loaded(client, tick0)
        for client in clients:
            notice = await client.until("NOTICE", skip=("LOAD_STATE",))
            self.assertEqual(notice, dict(code=NOTICES["tick0_mismatch"], argument=1))
            end = await client.until("MATCH_END")
            self.assertEqual((end["outcome"], end["reason"]), (OUTCOMES["aborted"], REASONS["tick0_mismatch"]))
            back = await state(client)
            self.assertEqual((back["phase"], set(states(back).values())), (PHASES["forming"], {MEMBER["here"]}))


if __name__ == "__main__":
    unittest.main()
