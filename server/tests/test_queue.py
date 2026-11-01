"""The public queue on the real server (docs/design/core-loop.md §5.1, §5.2,
§5.5, §3.6; contract-m6.md §6, §9 test_queue): who may queue, merging open
parties up to four and pairing race teams of one size, keying on the mode and
the rules hash, Match Found and its accepts, a decline or the timeout
requeueing the others at the front, Builder clashes between strangers, the
caretakers offered at 60 s and starting with them, the strangers' barrier, and
each party its own again after the match."""

from pathlib import Path
import random
import re
import unittest

from support import (BUILDERS, LOAD, MEMBER, MODES, NOTICES, PHASES, RULES, TICK0, HubTest, drain, named, party,
                     settle, state, sync)
from groundhold_server import protocol, queue
from groundhold_server.protocol import SPEC

OPS = SPEC["queue_ops"]
QUEUE = SPEC["queue_states"]
ERRORS = SPEC["errors"]
OUTCOMES = SPEC["outcomes"]
CARETAKER = SPEC["seat_flags"]["caretaker"]
OPEN = SPEC["party_flags"]["open"]
OTHER_RULES = bytes.fromhex("99887766554433ff")
ROOT = Path(__file__).resolve().parents[2]
NAMES = {value: name for name, value in BUILDERS.items()}


def idle():
    return dict(state=QUEUE["idle"], elapsed_ms=0, caretaker_offer=0)


class QueueTest(HubTest):
    async def start(self, **options):
        options.setdefault("queue_rng", random.Random(6))
        return await super().start(**options)

    async def solo(self, name, number, mode="high_water", main="lamplighter", backup="lookout", open_seats=True,
                   **hello):
        """A game in a party of one of its own, its Builders and open seats set, every state read."""
        client = await self.join(name, number, **hello)
        await party(client, "create", mode=MODES[mode])
        await state(client)
        if (main, backup) != ("lamplighter", "lookout"):
            await party(client, "builders", main=BUILDERS[main], backup=BUILDERS[backup])
            await state(client)
        if open_seats:
            await party(client, "open", on=1)
            await state(client)
        client.name = name
        return client

    async def group(self, names, first, mode="high_water", open_seats=True, team=None, mains=None):
        """A party of `names` (tokens from `first` on), every member Ready and every state read."""
        clients = [await self.join(name, first + index) for index, name in enumerate(names)]
        await party(clients[0], "create", mode=MODES[mode])
        code = (await state(clients[0]))["code"]
        for index, client in enumerate(clients[1:], start=1):
            await party(client, "join", code=code)
            for earlier in clients[:index + 1]:
                await state(earlier)
        for index, main in enumerate(mains or ()):
            await party(clients[index], "builders", main=BUILDERS[main[0]], backup=BUILDERS[main[1]])
            await self.everyone(clients)
        if team is not None:
            for number in range(1, len(clients)):
                await party(clients[0], "team", member=number, team=team)
                await self.everyone(clients)
        if open_seats:
            await party(clients[0], "open", on=1)
            await self.everyone(clients)
        await self.ready_all(clients)
        for client, name in zip(clients, names):
            client.name = name
        return clients

    def code_of(self, leader):
        """The code of the party `leader` (a name) leads."""
        return next(code for code, p in self.server.lobby.parties.items() if p.leader and p.leader.name == leader)

    async def enter(self, leader, members=()):
        """QUEUE enter from the leader: its QUEUE_STATE (and each member's), read."""
        await leader.send_message("QUEUE", op=OPS["enter"])
        got = await leader.until("QUEUE_STATE", skip=("PARTY_STATE", "PONG"))
        for member in members:
            await member.until("QUEUE_STATE", skip=("PARTY_STATE", "PONG"))
        return got

    async def found(self, clients):
        """Each game's next MATCH_FOUND."""
        return [await client.until("MATCH_FOUND", skip=("PARTY_STATE", "QUEUE_STATE", "PONG")) for client in clients]

    async def accept(self, clients, match_id, yes=1):
        """ACCEPT from each, the server has read them (what came back kept for the next reads)."""
        for client in clients:
            await client.send_message("ACCEPT", match=match_id, yes=yes)
            await settle(client)


class WhoQueues(QueueTest, unittest.IsolatedAsyncioTestCase):
    async def test_a_party_of_one_with_open_seats_queues(self):
        await self.start()
        tamsin = await self.solo("Tamsin", 1)
        await tamsin.send_message("QUEUE", op=OPS["enter"])
        queued = await state(tamsin)
        self.assertEqual(queued["phase"], PHASES["queued"])
        self.assertEqual(await tamsin.until("QUEUE_STATE"), dict(state=QUEUE["queued"], elapsed_ms=0, caretaker_offer=0))
        await self.clock.advance(4200)
        # (asked again while queued: the state as it is, the time since it queued)
        self.assertEqual(await self.enter(tamsin), dict(state=QUEUE["queued"], elapsed_ms=4200, caretaker_offer=0))
        self.assertEqual(self.server.lobby.open_parties(), 1)

    async def test_what_cannot_queue_is_answered_with_the_state_as_it_is(self):
        await self.start()
        # (open seats off: nothing to find; Play is an offline match)
        closed = await self.solo("Closed", 1, open_seats=False)
        self.assertEqual(await self.enter(closed), idle())
        # (a member not Ready; a member's own ask)
        tamsin, edda = (await self.join("Tamsin", 2)), (await self.join("Edda", 3))
        await party(tamsin, "create", mode=MODES["high_water"])
        code = (await state(tamsin))["code"]
        await party(edda, "join", code=code)
        await self.everyone((tamsin, edda))
        await party(tamsin, "open", on=1)
        await self.everyone((tamsin, edda))
        self.assertEqual(await self.enter(tamsin), idle())
        await party(edda, "ready", on=1)
        await self.everyone((tamsin, edda))
        self.assertEqual(await self.enter(edda), idle())
        self.assertEqual(self.server.lobby.parties[code].phase, PHASES["forming"])
        # (four members: no seat is free)
        full = await self.group(["A", "B", "C", "D"], 10)
        self.assertEqual(await self.enter(full[0]), idle())
        # (a member on another rules hash needs to reload)
        reload = await self.group(["E", "F"], 20)
        old = await self.join("Old", 30, rules_hash=OTHER_RULES, build_seq=6)
        await party(old, "join", code=self.code_of("E"))
        await drain(old)
        await drain(reload[0])
        await drain(reload[1])
        self.assertEqual(await self.enter(reload[0]), idle())
        # (a race of two teams, or a team too large, finds no rival: Start, or nothing)
        race = await self.group(["G", "H"], 40, mode="tide_race", open_seats=False)
        self.assertEqual(await self.enter(race[0]), idle())
        three = await self.group(["I", "J", "K"], 50, mode="tide_race", open_seats=False, team=0)
        self.assertEqual(await self.enter(three[0]), idle())
        # (no party at all)
        alone = await self.join("Alone", 60)
        self.assertEqual(await self.enter(alone), idle())
        self.assertFalse(self.server.lobby.queue.tickets)

    async def test_the_leader_leaves_the_queue_a_member_cannot(self):
        await self.start()
        tamsin, edda = await self.group(["Tamsin", "Edda"], 1)
        await self.enter(tamsin, [edda])
        await edda.send_message("QUEUE", op=OPS["leave"])
        self.assertEqual((await edda.until("QUEUE_STATE"))["state"], QUEUE["queued"])
        await tamsin.send_message("QUEUE", op=OPS["leave"])
        for client in (tamsin, edda):
            self.assertEqual(await client.until("QUEUE_STATE"), idle())
            left = await state(client)
            self.assertEqual(left["phase"], PHASES["forming"])
        # (Ready stays: the leader may queue again at once)
        self.assertEqual({m["name"]: m["state"] for m in left["members"]}["Edda"], MEMBER["ready"])
        self.assertEqual((await self.enter(tamsin, [edda]))["state"], QUEUE["queued"])

    async def test_a_join_a_leave_a_drop_or_open_seats_off_take_the_party_out(self):
        await self.start()
        tamsin, edda = await self.group(["Tamsin", "Edda"], 1)
        code = self.code_of("Tamsin")
        await self.enter(tamsin, [edda])
        # (a Builder change while queued is for the match it finds: it keeps the queue and the Ready)
        await party(edda, "builders", main=BUILDERS["bellfounder"], backup=BUILDERS["lookout"])
        kept = await self.everyone((tamsin, edda))
        self.assertEqual(kept[0]["phase"], PHASES["queued"])
        self.assertEqual({m["name"]: m["state"] for m in kept[0]["members"]}["Edda"], MEMBER["ready"])
        # (a member's Ready while queued: refused, the party as it is)
        await party(edda, "ready", on=0)
        self.assertEqual((await state(edda))["phase"], PHASES["queued"])
        # (a join: out, the newcomer is not Ready)
        ottilie = await self.join("Ottilie", 3)
        await party(ottilie, "join", code=code)
        for client in (tamsin, edda):
            self.assertEqual(await client.until("QUEUE_STATE"), idle())
            self.assertEqual((await state(client))["phase"], PHASES["forming"])
        await state(ottilie)
        await party(ottilie, "leave")
        await state(ottilie)
        await self.everyone((tamsin, edda))
        # (open seats off)
        await self.enter(tamsin, [edda])
        await party(tamsin, "open", on=0)
        for client in (tamsin, edda):
            self.assertEqual(await client.until("QUEUE_STATE"), idle())
            self.assertEqual((await state(client))["phase"], PHASES["forming"])
        await party(tamsin, "open", on=1)
        await self.everyone((tamsin, edda))
        # (a drop: the row held, the party out)
        await self.enter(tamsin, [edda])
        await edda.drop()
        self.assertEqual(await tamsin.until("QUEUE_STATE"), idle())
        dropped = await state(tamsin)
        self.assertEqual(dropped["phase"], PHASES["forming"])
        self.assertEqual({m["name"]: m["state"] for m in dropped["members"]}["Edda"], MEMBER["away"])
        self.assertFalse(self.server.lobby.queue.tickets)

    async def test_queue_and_accept_outside_their_limits_end_the_connection(self):
        await self.start()
        tamsin = await self.solo("Tamsin", 1)
        await tamsin.send_message("QUEUE", op=9)
        self.assertEqual((await tamsin.until("ERROR"))["code"], ERRORS["out_of_limits"])
        edda = await self.solo("Edda", 2)
        await edda.send_message("ACCEPT", match=1, yes=2)
        self.assertEqual((await edda.until("ERROR"))["code"], ERRORS["out_of_limits"])
        # (an accept of a match that is not the player's, or gone: let pass)
        ottilie = await self.solo("Ottilie", 3)
        await ottilie.send_message("ACCEPT", match=77, yes=1)
        self.assertEqual(await sync(ottilie), [])

    async def test_open_seats_are_a_one_team_modes(self):
        # (a race's queue finds a rival team, never strangers for its seats: a switch to Tide
        # Race turns them off, and the beacon stops counting the party)
        await self.start()
        tamsin = await self.solo("Tamsin", 1)
        self.assertEqual(self.server.lobby.open_parties(), 1)
        await party(tamsin, "mode", mode=MODES["tide_race"])
        self.assertEqual((await state(tamsin))["flags"] & OPEN, 0)
        self.assertEqual(self.server.lobby.open_parties(), 0)
        # (and they cannot be turned on in a race: the party as it is)
        await party(tamsin, "open", on=1)
        self.assertEqual((await state(tamsin))["flags"] & OPEN, 0)
        self.assertEqual(self.server.lobby.open_parties(), 0)
        # (back in High Water they stay off until the leader turns them on again)
        await party(tamsin, "mode", mode=MODES["high_water"])
        self.assertEqual((await state(tamsin))["flags"] & OPEN, 0)
        await party(tamsin, "open", on=1)
        self.assertEqual((await state(tamsin))["flags"] & OPEN, OPEN)
        self.assertEqual(self.server.lobby.open_parties(), 1)


class Merging(QueueTest, unittest.IsolatedAsyncioTestCase):
    async def test_open_parties_merge_up_to_four_in_the_order_they_came(self):
        await self.start()
        pair = await self.group(["Tamsin", "Edda"], 1)
        await self.enter(pair[0], pair[1:])
        ottilie = await self.solo("Ottilie", 3)
        await self.enter(ottilie)
        self.assertEqual(await sync(ottilie), [])       # (three of four: nothing found yet)
        sefa = await self.solo("Sefa", 4)
        await sefa.send_message("QUEUE", op=OPS["enter"])
        everyone = pair + [ottilie, sefa]
        found = await self.found(everyone)
        self.assertEqual(len({f["match"] for f in found}), 1)
        self.assertEqual(found[0], dict(match=found[0]["match"], mode=MODES["high_water"], seats=4, accepted=0,
                                        ms_left=SPEC["accept_ms"]))
        await self.clock.advance(1000)
        await self.accept(everyone[:3], found[0]["match"])
        # (each accept tells everyone how many have, and the ms left by the server's clock)
        updates = [named(await drain(client), "MATCH_FOUND") for client in everyone]
        self.assertEqual([u[-1]["accepted"] for u in updates], [3, 3, 3, 3])
        self.assertEqual(updates[3][-1]["ms_left"], SPEC["accept_ms"] - 1000)
        await self.accept(everyone[3:], found[0]["match"])
        configs = [await client.until("MATCH_CONFIG", skip=("PARTY_STATE", "MATCH_FOUND", "PONG"))
                   for client in everyone]
        self.assertEqual([c["your_seat"] for c in configs], [0, 1, 2, 3])
        self.assertEqual([s["name"] for s in configs[0]["seats"]], ["Tamsin", "Edda", "Ottilie", "Sefa"])
        self.assertEqual(configs[0]["match"], found[0]["match"])
        self.assertEqual((configs[0]["mode"], configs[0]["rules_hash"]), (MODES["high_water"], RULES))
        # (each party is loading its own match, a match of strangers)
        self.assertEqual(len(self.server.matches), 1)
        match = self.match()
        self.assertEqual(len(match.parties), 3)
        self.assertTrue(match.barrier.strangers)
        self.assertEqual({p.phase for p in match.parties}, {PHASES["loading"]})
        self.assertFalse(self.server.lobby.queue.tickets)

    async def test_the_front_party_first_and_one_too_large_waits(self):
        await self.start()
        three = await self.group(["A", "B", "C"], 1)
        await self.enter(three[0], three[1:])
        pair = await self.group(["D", "E"], 10)
        await self.enter(pair[0], pair[1:])
        single = await self.solo("F", 20)
        await single.send_message("QUEUE", op=OPS["enter"])
        found = await self.found(three + [single])
        self.assertEqual(found[0]["seats"], 4)
        self.assertEqual([named(await drain(c), "MATCH_FOUND") for c in pair], [[], []])
        self.assertEqual(self.server.lobby.parties[self.code_of("D")].phase, PHASES["queued"])

    async def test_parties_merge_only_by_mode_and_rules_hash(self):
        await self.start()
        newer = [await self.solo(name, index + 1) for index, name in enumerate(("A", "B", "C"))]
        older = await self.solo("Old", 9, rules_hash=OTHER_RULES)
        for client in newer + [older]:
            await self.enter(client)
        self.assertEqual([named(await drain(c), "MATCH_FOUND") for c in newer + [older]], [[], [], [], []])
        # (classic is another mode: it never fills High Water's seats)
        classic = await self.solo("Classic", 10, mode="classic")
        await self.enter(classic)
        self.assertEqual(named(await drain(classic), "MATCH_FOUND"), [])
        fourth = await self.solo("D", 4)
        await fourth.send_message("QUEUE", op=OPS["enter"])
        found = await self.found(newer + [fourth])
        self.assertEqual(found[0]["seats"], 4)
        self.assertEqual(named(await drain(older), "MATCH_FOUND"), [])
        keys = {(t.mode, t.rules) for t in self.server.lobby.queue.tickets.values() if t.found is None}
        self.assertEqual(keys, {("high_water", OTHER_RULES), ("classic", RULES)})

    async def test_tide_race_pairs_a_team_with_a_rival_team_of_its_size(self):
        await self.start()
        pair = await self.group(["Tamsin", "Edda"], 1, mode="tide_race", open_seats=False, team=0)
        await self.enter(pair[0], pair[1:])
        one = await self.solo("Ottilie", 3, mode="tide_race", open_seats=False)
        await self.enter(one)
        self.assertEqual(named(await drain(one), "MATCH_FOUND"), [])
        rival = await self.solo("Sefa", 4, mode="tide_race", open_seats=False, main="beekeeper", backup="lookout")
        await rival.send_message("QUEUE", op=OPS["enter"])
        found = await self.found([one, rival])
        self.assertEqual((found[0]["mode"], found[0]["seats"]), (MODES["tide_race"], 2))
        await self.accept([one, rival], found[0]["match"])
        configs = [await c.until("MATCH_CONFIG", skip=("PARTY_STATE", "MATCH_FOUND", "PONG")) for c in (one, rival)]
        self.assertEqual([(s["seat"], s["team"], s["name"]) for s in configs[0]["seats"]],
                         [(0, 0, "Ottilie"), (1, 1, "Sefa")])
        # (two of two: a 2v2, the earlier pair team 0)
        other = await self.group(["Bram", "Wen"], 10, mode="tide_race", open_seats=False, team=0)
        await other[0].send_message("QUEUE", op=OPS["enter"])
        found = await self.found(pair + other)
        self.assertEqual(found[0]["seats"], 4)
        await self.accept(pair + other, found[0]["match"])
        config = await pair[0].until("MATCH_CONFIG", skip=("PARTY_STATE", "MATCH_FOUND", "PONG"))
        self.assertEqual([(s["team"], s["name"]) for s in config["seats"]],
                         [(0, "Tamsin"), (0, "Edda"), (1, "Bram"), (1, "Wen")])


class Filling(unittest.TestCase):
    """The queue's choice of tickets alone: the earliest that fill the seats."""

    def tickets(self, *sizes):
        return [_T(size, index) for index, size in enumerate(sizes)]

    def test_the_earliest_fill(self):
        fill = queue.earliest_fill
        t = self.tickets(1, 2, 2)
        # (first fit would take the 1 and then miss; the two of two fill it)
        self.assertEqual(fill(t[1:], 2), [t[1]])
        self.assertEqual(fill(t, 2), [t[1]])
        t = self.tickets(2, 1, 2)
        self.assertEqual(fill(t, 2), [t[0]])
        # (1 + 1 + 1 at places 0, 2, 3 beats 2 + 1 at places 0, 4: the earliest places first)
        t = self.tickets(1, 3, 1, 1, 2)
        self.assertEqual(fill(t, 3), [t[0], t[2], t[3]])
        self.assertIsNone(fill(self.tickets(3, 3, 2), 1))
        self.assertEqual(list(queue.parts(3)), [(3,), (2, 1), (1, 1, 1)])


class MatchFound(QueueTest, unittest.IsolatedAsyncioTestCase):
    async def four(self, first=1):
        clients = [await self.solo(name, first + index) for index, name in enumerate(("Ana", "Ben", "Cai", "Dot"))]
        for client in clients[:3]:
            await self.enter(client)
        await self.clock.advance(2000)
        await clients[3].send_message("QUEUE", op=OPS["enter"])
        return clients, (await self.found(clients))[0]["match"]

    async def test_a_decline_requeues_the_others_at_the_front(self):
        await self.start()
        clients, match_id = await self.four()
        ana, ben, cai, dot = clients
        # (while they decide, three more queue behind them: not four, so they wait)
        await self.clock.advance(1000)
        later = [await self.solo(name, 20 + index) for index, name in enumerate(("Xan", "Yva", "Zed"))]
        for client in later:
            await self.enter(client)
        await self.accept([ana, ben], match_id)
        await cai.send_message("ACCEPT", match=match_id, yes=0)
        # (the decliner's party back to forming)
        self.assertEqual(await cai.until("QUEUE_STATE", skip=("MATCH_FOUND",)), idle())
        self.assertEqual((await state(cai))["phase"], PHASES["forming"])
        # (the others at the front, keeping their time: Ana queued 3 s ago; with Xan, the
        # first behind them, they are four again at once, and Yva and Zed wait)
        for client in (ana, ben, dot):
            got = await drain(client)
            got = got[got.index(("NOTICE", dict(code=NOTICES["match_dissolved"], argument=0))):]
            self.assertEqual([name for name, _ in got], ["NOTICE", "QUEUE_STATE", "MATCH_FOUND"])
            self.assertEqual(got[1][1]["state"], QUEUE["queued"])
            again = got[2][1]
        self.assertEqual(named(ana.inbox, "QUEUE_STATE")[-1]["elapsed_ms"], 3000)
        self.assertNotEqual(again["match"], match_id)
        self.assertEqual((again["seats"], again["accepted"]), (4, 0))
        self.assertEqual(named(await drain(later[0]), "MATCH_FOUND"), [again])
        self.assertEqual([named(await drain(c), "MATCH_FOUND") for c in later[1:]], [[], []])
        # (the new match's seats: the earliest queued first, Ana, Ben, Dot, then Xan)
        found = self.server.lobby.queue.found[again["match"]]
        self.assertEqual([t.party.leader.name for t in found.tickets], ["Ana", "Ben", "Dot", "Xan"])
        # (an answer to the dissolved match is let pass)
        await ana.send_message("ACCEPT", match=match_id, yes=1)
        self.assertEqual(named(await sync(ana), "MATCH_FOUND"), [])

    async def test_the_timeout_dissolves_those_who_did_not_accept(self):
        await self.start()
        clients, match_id = await self.four()
        ana, ben, cai, dot = clients
        await self.accept([ana, ben, dot], match_id)
        await self.clock.advance(SPEC["accept_ms"] - 1)
        self.assertTrue(self.server.lobby.queue.found)
        await self.clock.advance(1)
        self.assertFalse(self.server.lobby.queue.found)
        self.assertEqual(named(await drain(cai), "QUEUE_STATE")[-1], idle())
        for client in (ana, ben, dot):
            got = await drain(client)
            self.assertIn(("NOTICE", dict(code=NOTICES["match_dissolved"], argument=0)), got)
            self.assertEqual(named(got, "QUEUE_STATE")[-1]["state"], QUEUE["queued"])
        phases = {p.leader.name: p.phase for p in self.server.lobby.parties.values()}
        self.assertEqual(phases, {"Ana": PHASES["queued"], "Ben": PHASES["queued"], "Cai": PHASES["forming"],
                                  "Dot": PHASES["queued"]})

    async def test_a_leave_or_a_drop_in_match_found_is_a_decline(self):
        await self.start()
        clients, match_id = await self.four()
        ana, ben, cai, dot = clients
        await ana.send_message("QUEUE", op=OPS["leave"])
        self.assertEqual(named(await drain(ana), "QUEUE_STATE")[-1], idle())
        for client in (ben, cai, dot):
            self.assertIn(("NOTICE", dict(code=NOTICES["match_dissolved"], argument=0)), await drain(client))
        eve = await self.solo("Eve", 9)
        await eve.send_message("QUEUE", op=OPS["enter"])
        match_id = (await self.found([ben, cai, dot, eve]))[0]["match"]
        await eve.drop()
        for client in (ben, cai, dot):
            self.assertIn(("NOTICE", dict(code=NOTICES["match_dissolved"], argument=0)), await drain(client))
        self.assertFalse(self.server.lobby.queue.found)
        self.assertNotIn(match_id, self.server.matches)

    async def test_everyone_accepts_a_strangers_match_and_each_party_its_own_after(self):
        await self.start()
        clients, match_id = await self.four()
        await self.accept(clients, match_id)
        configs = [await c.until("MATCH_CONFIG", skip=("PARTY_STATE", "MATCH_FOUND", "PONG")) for c in clients]
        match = self.match()
        # (the strangers' barrier: 45 s, then it starts with the seats loaded)
        for client in clients[:2]:
            await client.send_message("LOADED", rules_hash=configs[0]["rules_hash"], tick0_hash=TICK0)
        await self.clock.advance(44_999)
        self.assertEqual(match.phase, "loading")
        await self.clock.advance(1)
        for client in clients:
            await client.until("START", skip=("LOAD_STATE", "PARTY_STATE"))
        await self.clock.advance(SPEC["start_delay_ms"])
        await self.clock.turns(2)
        for client in clients[:2]:
            await client.send_message("RESULT", tick=6, hash=b"r" * 8, outcomes=[dict(outcome=SPEC["outcomes"]["won"])])
        for client in clients:
            await client.until("MATCH_END", skip=("TURN", "LINKS", "PARTY_STATE", "LOAD_STATE"))
        # (four parties, each on its own results plate, then back on its own)
        parties = sorted(self.server.lobby.parties.values(), key=lambda p: p.leader.name)
        self.assertEqual([len(p.members) for p in parties], [1, 1, 1, 1])
        self.assertEqual([p.phase for p in parties], [PHASES["results"]] * 4)
        await clients[0].send_message("LEAVE_MATCH")
        await sync(clients[0])
        self.assertEqual(parties[0].phase, PHASES["forming"])
        self.assertEqual(parties[1].phase, PHASES["results"])
        # (Play again for a player who came alone: queued again, open seats still on)
        self.assertEqual((await self.enter(clients[0]))["state"], QUEUE["queued"])


class Builders(QueueTest, unittest.IsolatedAsyncioTestCase):
    async def test_the_first_queued_keeps_the_main_the_next_the_backup_then_a_free_one(self):
        await self.start(queue_rng=random.Random(1))
        pair = await self.group(["Tamsin", "Twin"], 1)     # (two Lamplighters in one party: both stay)
        await self.enter(pair[0], pair[1:])
        edda = await self.solo("Edda", 3, main="lamplighter", backup="lookout")
        await self.enter(edda)
        ottilie = await self.solo("Ottilie", 4, main="lookout", backup="lamplighter")
        await ottilie.send_message("QUEUE", op=OPS["enter"])
        everyone = pair + [edda, ottilie]
        match_id = (await self.found(everyone))[0]["match"]
        await self.accept(everyone, match_id)
        config = await pair[0].until("MATCH_CONFIG", skip=("PARTY_STATE", "MATCH_FOUND", "PONG"))
        chosen = [NAMES[s["builder"]] for s in config["seats"]]
        self.assertEqual(chosen[:3], ["lamplighter", "lamplighter", "lookout"])
        # (Ottilie's main and backup are both taken: a free one, from the server's random)
        free = [name for name in ("bellfounder", "beekeeper")]
        self.assertIn(chosen[3], free)
        expected = queue.builders_for([[_M(0, 1), _M(0, 1)], [_M(0, 1)], [_M(1, 0)]], True, random.Random(1))
        self.assertEqual(chosen[3], NAMES[expected[2][0]])

    def test_clash_rules_alone(self):
        rng = random.Random(3)
        lamp, look, bell, bee = (BUILDERS[n] for n in ("lamplighter", "lookout", "bellfounder", "beekeeper"))
        # (no clash: everyone their main)
        self.assertEqual(queue.builders_for([[_M(lamp, look)], [_M(bell, bee)]], True, rng), [[lamp], [bell]])
        # (in a race nobody shares a team with a stranger: mains, duplicates and all)
        self.assertEqual(queue.builders_for([[_M(lamp, look)], [_M(lamp, look)]], False, rng), [[lamp], [lamp]])
        # (the backup taken too: one of the free two, never a taken one)
        draws = {queue.builders_for([[_M(lamp, look), _M(look, lamp)], [_M(lamp, look)]], True,
                                    random.Random(seed))[1][0] for seed in range(40)}
        self.assertEqual(draws, {bell, bee})

    def test_caretakers_cover_what_the_party_lacks(self):
        lamp, look, bell, bee = (BUILDERS[n] for n in ("lamplighter", "lookout", "bellfounder", "beekeeper"))
        self.assertEqual(queue.caretaker_builders([lamp], 3), [look, bell, bee])
        self.assertEqual(queue.caretaker_builders([look], 3), [lamp, bell, bee])
        # (the Bellfounder lacks Swarm and Winged: the Beekeeper covers both)
        self.assertEqual(queue.caretaker_builders([bell], 1), [bee])
        self.assertEqual(queue.caretaker_builders([lamp, look], 2), [bell, bee])
        # (nothing lacking: a Builder not on the team yet, in BUILDER_IDS order)
        self.assertEqual(queue.caretaker_builders([lamp, lamp, look], 1), [bell])

    def test_covers_are_the_simulations(self):
        text = (ROOT / "scripts" / "sim" / "content.gd").read_text(encoding="utf-8")
        body = text[text.index("const BUILDERS := {"):]
        listed = dict(re.findall(r'^\t"(\w+)":\s*\{.*?"covers": \[([^\]]*)\]', body, re.M | re.S))
        self.assertEqual(sorted(listed), sorted(queue.COVERS))
        for name, covers in queue.COVERS.items():
            self.assertEqual(tuple(re.findall(r'"(\w+)"', listed[name])), covers, name)
        self.assertEqual(queue.BUILDER_IDS, ["lamplighter", "lookout", "bellfounder", "beekeeper"])


class Caretakers(QueueTest, unittest.IsolatedAsyncioTestCase):
    async def test_offered_after_60_s_then_high_water_fills_the_open_seats(self):
        await self.start()
        tamsin = await self.solo("Tamsin", 1)
        await self.enter(tamsin)
        # (before the offer: refused, the state as it is)
        await tamsin.send_message("QUEUE", op=OPS["start_with_caretakers"])
        self.assertEqual((await tamsin.until("QUEUE_STATE"))["caretaker_offer"], 0)
        await self.clock.advance(SPEC["caretaker_offer_ms"] - 1)
        self.assertEqual(await sync(tamsin), [])
        await self.clock.advance(1)
        got = await sync(tamsin)
        self.assertEqual(got, [("NOTICE", dict(code=NOTICES["caretakers_offered"], argument=0)),
                               ("QUEUE_STATE", dict(state=QUEUE["queued"], elapsed_ms=SPEC["caretaker_offer_ms"],
                                                    caretaker_offer=1))])
        await tamsin.send_message("QUEUE", op=OPS["start_with_caretakers"])
        config = await tamsin.until("MATCH_CONFIG", skip=("PARTY_STATE",))
        self.assertEqual([(s["name"], NAMES[s["builder"]], s["flags"]) for s in config["seats"]],
                         [("Tamsin", "lamplighter", 0), ("Caretaker 1", "lookout", CARETAKER),
                          ("Caretaker 2", "bellfounder", CARETAKER), ("Caretaker 3", "beekeeper", CARETAKER)])
        self.assertFalse(self.server.lobby.queue.tickets)
        match = self.match()
        self.assertFalse(match.barrier.strangers)       # (the party's own match, its caretakers beside it)
        loading = await tamsin.until("LOAD_STATE")
        self.assertEqual([s["state"] for s in loading["seats"]], [LOAD["connecting"]] + [LOAD["gone"]] * 3)
        # (one human: no minimum; the caretakers' seats are nobody's to wait for or to inject)
        await tamsin.send_message("LOADED", rules_hash=config["rules_hash"], tick0_hash=TICK0)
        await tamsin.until("START", skip=("LOAD_STATE", "PARTY_STATE"))
        await self.clock.advance(SPEC["start_delay_ms"])
        await self.clock.turns(1)
        turn = await tamsin.until("TURN", skip=("PARTY_STATE",))
        self.assertEqual(turn, dict(turn=0, commands=[]))
        self.assertEqual([s.index for s in match.present()], [0])

    async def test_race_the_caretaker_mirrors_the_party(self):
        await self.start()
        pair = await self.group(["Tamsin", "Edda"], 1, mode="tide_race", open_seats=False, team=0,
                                mains=[("lookout", "lamplighter"), ("beekeeper", "lookout")])
        await self.enter(pair[0], pair[1:])
        await self.clock.advance(SPEC["caretaker_offer_ms"])
        for client in pair:
            self.assertIn(("NOTICE", dict(code=NOTICES["caretakers_offered"], argument=0)), await drain(client))
        await pair[0].send_message("QUEUE", op=OPS["start_with_caretakers"])
        config = await pair[1].until("MATCH_CONFIG", skip=("PARTY_STATE",))
        self.assertEqual([(s["team"], s["name"], NAMES[s["builder"]], s["flags"]) for s in config["seats"]],
                         [(0, "Tamsin", "lookout", 0), (0, "Edda", "beekeeper", 0),
                          (1, "Caretaker 1", "lookout", CARETAKER), (1, "Caretaker 2", "beekeeper", CARETAKER)])

    async def test_the_offer_survives_match_found_and_a_member_cannot_take_it(self):
        await self.start()
        pair = await self.group(["Tamsin", "Edda"], 1)
        await self.enter(pair[0], pair[1:])
        await self.clock.advance(SPEC["caretaker_offer_ms"])
        await drain(pair[0])
        await drain(pair[1])
        await pair[1].send_message("QUEUE", op=OPS["start_with_caretakers"])
        self.assertEqual((await pair[1].until("QUEUE_STATE"))["caretaker_offer"], 1)
        self.assertFalse(self.server.matches)
        # (two strangers fill the seats; one declines; the pair back at the front, still offered)
        a, b = await self.solo("Ana", 10), await self.solo("Ben", 11)
        await self.enter(a)
        await b.send_message("QUEUE", op=OPS["enter"])
        match_id = (await self.found(pair + [a, b]))[0]["match"]
        await b.send_message("ACCEPT", match=match_id, yes=0)
        got = await drain(pair[0])
        self.assertEqual(named(got, "QUEUE_STATE")[-1]["caretaker_offer"], 1)
        self.assertEqual(named(got, "NOTICE"), [dict(code=NOTICES["match_dissolved"], argument=0)])


class Ceiling(QueueTest, unittest.IsolatedAsyncioTestCase):
    async def test_a_strangers_match_nobody_loaded_requeues_its_parties_at_the_front(self):
        await self.start()
        clients = [await self.solo(name, index + 1) for index, name in enumerate(("Ana", "Ben", "Cai", "Dot"))]
        for client in clients[:3]:
            await self.enter(client)
        await clients[3].send_message("QUEUE", op=OPS["enter"])
        match_id = (await self.found(clients))[0]["match"]
        await self.accept(clients, match_id)
        for client in clients:
            await client.until("MATCH_CONFIG", skip=("PARTY_STATE", "MATCH_FOUND", "PONG"))
        await self.clock.advance(120_000)
        for client in clients:
            got = await drain(client)
            self.assertIn(("NOTICE", dict(code=NOTICES["match_dissolved"], argument=0)), got)
            self.assertEqual(named(got, "MATCH_END")[-1]["outcome"], SPEC["outcomes"]["aborted"])
            last = named(got, "QUEUE_STATE")[-1]
            self.assertEqual((last["state"], last["caretaker_offer"]), (QUEUE["queued"], 1))
        # (requeued, they find each other again at once)
        self.assertEqual(len(self.server.lobby.queue.found), 1)

    async def test_a_party_told_of_the_caretakers_is_not_told_again_when_requeued(self):
        await self.start()
        clients = [await self.solo(name, index + 1) for index, name in enumerate(("Ana", "Ben", "Cai", "Dot"))]
        offered = ("NOTICE", dict(code=NOTICES["caretakers_offered"], argument=0))
        for client in clients[:3]:
            await self.enter(client)
        await self.clock.advance(SPEC["caretaker_offer_ms"])
        for client in clients[:3]:
            self.assertEqual((await drain(client)).count(offered), 1)
        await clients[3].send_message("QUEUE", op=OPS["enter"])
        match_id = (await self.found(clients))[0]["match"]
        await self.accept(clients, match_id)
        for client in clients:
            await client.until("MATCH_CONFIG", skip=("PARTY_STATE", "MATCH_FOUND", "QUEUE_STATE", "PONG"))
        await self.clock.advance(120_000)
        for index, client in enumerate(clients):
            got = await drain(client)
            self.assertIn(("NOTICE", dict(code=NOTICES["match_dissolved"], argument=0)), got)
            self.assertEqual(named(got, "QUEUE_STATE")[-1]["caretaker_offer"], 1)
            # (Ana, Ben and Cai heard it before Match Found; Dot, queued only a moment then, now)
            self.assertEqual(got.count(offered), 1 if index == 3 else 0, client.name)


class Duel(QueueTest, unittest.IsolatedAsyncioTestCase):
    """Undertow (M7, contract-m7.md §4): Find a rival for one player a side, the duel's
    caretaker of your own Builder after the offer, and a duel's RESULT, one outcome a side."""

    async def duellist(self, name, number, **builders):
        return await self.solo(name, number, mode="undertow", open_seats=False, **builders)

    async def test_a_duellist_queues_alone_and_two_in_a_party_start_instead(self):
        await self.start()
        tamsin = await self.duellist("Tamsin", 1)
        self.assertEqual(await self.enter(tamsin), dict(state=QUEUE["queued"], elapsed_ms=0, caretaker_offer=0))
        # (two in a party are both sides already, one on each team: they Start, never queue)
        pair = await self.group(["Edda", "Ottilie"], 10, mode="undertow", open_seats=False)
        code = self.code_of("Edda")
        duel = self.server.lobby.parties[code]
        self.assertEqual([m.team for m in duel.ordered()], [0, 1])
        self.assertEqual(await self.enter(pair[0]), idle())
        self.assertEqual((duel.startable(), self.server.lobby.queue.refusal(duel)), ("", "two teams"))
        # (two on one side are no duel: neither the queue nor a start takes them)
        await party(pair[0], "team", member=1, team=0)
        await self.everyone(pair)
        await party(pair[1], "ready", on=1)
        await self.everyone(pair)
        self.assertEqual(await self.enter(pair[0]), idle())
        self.assertEqual((duel.startable(), self.server.lobby.queue.refusal(duel)), ("teams", "team size"))
        # (and a duel has no open seats: the queue finds the rival)
        await party(tamsin, "open", on=1)
        self.assertEqual((await state(tamsin))["flags"], 0)
        self.assertEqual(list(self.server.lobby.queue.tickets), [self.server.lobby.parties[self.code_of("Tamsin")]])

    async def test_two_duellists_meet_one_a_side_and_keep_their_mains(self):
        await self.start()
        tamsin = await self.duellist("Tamsin", 1)
        await self.enter(tamsin)
        # (a racer alone is no rival for a duellist: the mode is the queue's key)
        racer = await self.solo("Racer", 2, mode="tide_race", open_seats=False)
        await self.enter(racer)
        self.assertEqual(named(await drain(tamsin), "MATCH_FOUND"), [])
        edda = await self.duellist("Edda", 3)       # (a Lamplighter too: two sides, no clash)
        await edda.send_message("QUEUE", op=OPS["enter"])
        found = await self.found([tamsin, edda])
        self.assertEqual([(f["mode"], f["seats"], f["accepted"]) for f in found], [(MODES["undertow"], 2, 0)] * 2)
        self.assertEqual(found[0]["ms_left"], SPEC["accept_ms"])
        await self.accept([tamsin, edda], found[0]["match"])
        configs = [await c.until("MATCH_CONFIG", skip=("PARTY_STATE", "MATCH_FOUND", "PONG")) for c in (tamsin, edda)]
        self.assertEqual([(s["seat"], s["team"], s["name"], NAMES[s["builder"]], s["flags"])
                          for s in configs[0]["seats"]],
                         [(0, 0, "Tamsin", "lamplighter", 0), (1, 1, "Edda", "lamplighter", 0)])
        self.assertEqual([(c["mode"], c["your_seat"], c["match"]) for c in configs],
                         [(MODES["undertow"], 0, found[0]["match"]), (MODES["undertow"], 1, found[0]["match"])])
        self.assertTrue(self.match().barrier.strangers)
        # (the racer waits on for a racer)
        racing = self.server.lobby.parties[self.code_of("Racer")]
        self.assertEqual([t.party for t in self.server.lobby.queue.tickets.values()], [racing])

    def test_builder_clashes_never_cross_the_sides(self):
        lamp, look, bell, bee = (BUILDERS[n] for n in ("lamplighter", "lookout", "bellfounder", "beekeeper"))
        # (each side is one party alone on its hollow: both keep the main, the same one or not)
        for mains in ((lamp, lamp), (look, look), (bell, bee)):
            sides = [[_M(main, look if main != look else lamp)] for main in mains]
            self.assertEqual(queue.builders_for(sides, False, random.Random(1)), [[mains[0]], [mains[1]]])

    async def test_duel_the_caretaker_after_60_s_a_rival_of_your_builder(self):
        await self.start()
        sefa = await self.duellist("Sefa", 1, main="beekeeper", backup="lookout")
        await self.enter(sefa)
        await self.clock.advance(SPEC["caretaker_offer_ms"])
        self.assertEqual(await sync(sefa), [
            ("NOTICE", dict(code=NOTICES["caretakers_offered"], argument=0)),
            ("QUEUE_STATE", dict(state=QUEUE["queued"], elapsed_ms=SPEC["caretaker_offer_ms"], caretaker_offer=1))])
        await sefa.send_message("QUEUE", op=OPS["start_with_caretakers"])
        config = await sefa.until("MATCH_CONFIG", skip=("PARTY_STATE",))
        self.assertEqual([(s["seat"], s["team"], s["name"], NAMES[s["builder"]], s["flags"]) for s in config["seats"]],
                         [(0, 0, "Sefa", "beekeeper", 0), (1, 1, "Caretaker 1", "beekeeper", CARETAKER)])
        self.assertEqual(config["mode"], MODES["undertow"])
        self.assertFalse(self.server.lobby.queue.tickets)
        match = self.match()
        self.assertFalse(match.barrier.strangers)       # (the party's own match, its rival a caretaker)
        loading = await sefa.until("LOAD_STATE")
        self.assertEqual([s["state"] for s in loading["seats"]], [LOAD["connecting"], LOAD["gone"]])
        await sefa.send_message("LOADED", rules_hash=config["rules_hash"], tick0_hash=TICK0)
        await sefa.until("START", skip=("LOAD_STATE", "PARTY_STATE"))
        await self.clock.advance(SPEC["start_delay_ms"])
        await self.clock.turns(2)
        self.assertEqual([s.index for s in match.present()], [0])
        # (her RESULT names both sides; the caretaker's seat sends none and is never waited on)
        await sefa.send_message("RESULT", tick=3, hash=b"r" * 8,
                                outcomes=[dict(outcome=OUTCOMES["lost"]), dict(outcome=OUTCOMES["won"])])
        end = await sefa.until("MATCH_END", skip=("TURN", "LINKS", "PARTY_STATE", "LOAD_STATE"))
        self.assertEqual(end, dict(outcome=OUTCOMES["lost"], reason=SPEC["end_reasons"]["result"], final_tick=3))

    async def duel(self):
        """Two duellists through the queue to the first turn: (tamsin, edda)."""
        tamsin, edda = await self.duellist("Tamsin", 1), await self.duellist("Edda", 2, main="lookout")
        await self.enter(tamsin)
        await edda.send_message("QUEUE", op=OPS["enter"])
        match_id = (await self.found([tamsin, edda]))[0]["match"]
        await self.accept([tamsin, edda], match_id)
        for client in (tamsin, edda):
            config = await client.until("MATCH_CONFIG", skip=("PARTY_STATE", "MATCH_FOUND", "PONG"))
            await client.send_message("LOADED", rules_hash=config["rules_hash"], tick0_hash=TICK0)
        await self.clock.advance(SPEC["loading_min_ms"])
        for client in (tamsin, edda):
            await client.until("START", skip=("LOAD_STATE", "PARTY_STATE"))
        await self.clock.advance(SPEC["start_delay_ms"])
        await self.clock.turns(4)
        return tamsin, edda

    async def test_a_duels_result_is_one_outcome_a_side_and_play_again_queues_again(self):
        await self.start()
        tamsin, edda = await self.duel()
        won, lost = OUTCOMES["won"], OUTCOMES["lost"]
        for client in (tamsin, edda):
            await client.send_message("RESULT", tick=9, hash=b"r" * 8, outcomes=[dict(outcome=won), dict(outcome=lost)])
        ends = [await c.until("MATCH_END", skip=("TURN", "LINKS", "PARTY_STATE", "LOAD_STATE")) for c in (tamsin, edda)]
        # (each side its own outcome: Tamsin's team 0 won, Edda's team 1 lost)
        self.assertEqual([(e["outcome"], e["reason"], e["final_tick"]) for e in ends],
                         [(won, SPEC["end_reasons"]["result"], 9), (lost, SPEC["end_reasons"]["result"], 9)])
        # (two parties, each on its own results plate; Play again queues the one who came alone)
        parties = [self.server.lobby.parties[self.code_of(name)] for name in ("Tamsin", "Edda")]
        self.assertEqual([p.phase for p in parties], [PHASES["results"]] * 2)
        await tamsin.send_message("LEAVE_MATCH")
        await sync(tamsin)
        self.assertEqual(parties[0].phase, PHASES["forming"])
        self.assertEqual((await self.enter(tamsin))["state"], QUEUE["queued"])
        await edda.send_message("LEAVE_MATCH")
        await sync(edda)
        await edda.send_message("QUEUE", op=OPS["enter"])
        found = await self.found([tamsin, edda])
        self.assertEqual((found[0]["mode"], found[0]["seats"]), (MODES["undertow"], 2))

    async def test_a_duels_result_with_one_outcome_is_outside_its_limits(self):
        await self.start()
        tamsin, edda = await self.duel()
        await tamsin.send_message("RESULT", tick=9, hash=b"r" * 8, outcomes=[dict(outcome=OUTCOMES["won"])])
        error = await tamsin.until("ERROR", skip=("TURN", "LINKS", "PARTY_STATE"))
        self.assertEqual(error["code"], ERRORS["out_of_limits"])
        self.assertIsNone(self.match().seats[0].result)


class Transcripts(unittest.TestCase):
    """The m6_* and m7_* golden transcripts, as the server served them (README, The queue)."""

    def said(self, name):
        import sys
        sys.path.insert(0, str(ROOT / "server" / "tools"))
        import record_transcripts
        records = record_transcripts.read(record_transcripts.TRANSCRIPTS / (name + ".bin"))
        return [(("c2s", "s2c")[direction], client, *protocol.decode(data)) for direction, client, data in records]

    def test_m6_queue_merges_dissolves_requeues_and_unclashes(self):
        said = self.said("m6_queue")
        found = [(c, f["match"], f["accepted"]) for d, c, kind, f in said if kind == "MATCH_FOUND" and c == 0]
        self.assertEqual(found, [(0, 1, 0), (0, 1, 1), (0, 2, 0), (0, 2, 1), (0, 2, 2), (0, 2, 3)])
        notices = [(c, f["code"]) for d, c, kind, f in said if kind == "NOTICE"]
        self.assertEqual(notices, [(0, NOTICES["match_dissolved"]), (1, NOTICES["match_dissolved"]),
                                   (2, NOTICES["match_dissolved"])])
        config = next(f for d, c, kind, f in said if kind == "MATCH_CONFIG")
        self.assertEqual(config["match"], 2)
        self.assertEqual([(s["name"], NAMES[s["builder"]]) for s in config["seats"]],
                         [("Tamsin", "lamplighter"), ("Edda", "lookout"), ("Ottilie", "bellfounder"),
                          ("Sefa", "beekeeper")])
        # (the requeued kept their time: Tamsin queued 7 s before the decline)
        requeued = [f for d, c, kind, f in said if kind == "QUEUE_STATE" and c == 0][-1]
        self.assertEqual((requeued["state"], requeued["elapsed_ms"]), (QUEUE["queued"], 7000))

    def test_m6_caretakers_and_m6_race(self):
        said = self.said("m6_caretakers")
        config = next(f for d, c, kind, f in said if kind == "MATCH_CONFIG")
        self.assertEqual([s["flags"] for s in config["seats"]], [0, CARETAKER, CARETAKER, CARETAKER])
        self.assertEqual([(c, f["code"]) for d, c, kind, f in said if kind == "NOTICE"],
                         [(0, NOTICES["caretakers_offered"])])
        said = self.said("m6_race")
        config = next(f for d, c, kind, f in said if kind == "MATCH_CONFIG")
        self.assertEqual([(s["team"], NAMES[s["builder"]], s["flags"]) for s in config["seats"]],
                         [(0, "lookout", 0), (1, "lookout", CARETAKER)])
        self.assertEqual([(c, f["code"]) for d, c, kind, f in said if kind == "NOTICE"],
                         [(0, NOTICES["match_dissolved"]), (0, NOTICES["caretakers_offered"])])


    def test_m7_duel_one_a_side_two_outcomes_and_queued_again(self):
        said = self.said("m7_duel")
        found = [(c, f["mode"], f["seats"], f["accepted"]) for d, c, kind, f in said if kind == "MATCH_FOUND"]
        self.assertEqual(found, [(0, MODES["undertow"], 2, 0), (1, MODES["undertow"], 2, 0),
                                 (0, MODES["undertow"], 2, 1), (1, MODES["undertow"], 2, 1)])
        config = next(f for d, c, kind, f in said if kind == "MATCH_CONFIG")
        self.assertEqual([(s["team"], s["name"], NAMES[s["builder"]]) for s in config["seats"]],
                         [(0, "Tamsin", "lamplighter"), (1, "Edda", "lamplighter")])
        results = [len(f["outcomes"]) for d, c, kind, f in said if kind == "RESULT"]
        self.assertEqual(results, [2, 2])
        ends = [(c, f["outcome"]) for d, c, kind, f in said if kind == "MATCH_END"]
        self.assertEqual(ends, [(0, OUTCOMES["won"]), (1, OUTCOMES["lost"])])
        last = [f for d, c, kind, f in said if kind == "QUEUE_STATE" and c == 0][-1]
        self.assertEqual(last["state"], QUEUE["queued"])


class _T:
    """A stand-in ticket: its size."""

    def __init__(self, size, place):
        self.place, self._size = place, size

    def size(self):
        return self._size

    def __repr__(self):
        return f"T{self.place}({self._size})"


class _M:
    """A stand-in member for builders_for: its main and backup."""

    def __init__(self, main, backup):
        self.main, self.backup = main, backup


if __name__ == "__main__":
    unittest.main()
