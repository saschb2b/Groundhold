"""A party's rules on the real server (docs/design/core-loop.md §5.2, §6.10,
§7.3 test_party_flow): create and join, Ready, the 3 s countdown and its
cancel, leader handover, a mode change clears Ready, removal, a full party,
"needs to reload", teams in a Race, the refusals and the limits."""

import unittest

from support import (BUILDERS, MEMBER, MODES, NOTICES, PHASES, RULES, HubTest, party, state, states)
from groundhold_server.protocol import SPEC

ERRORS = SPEC["errors"]


class PartyFlowTests(HubTest, unittest.IsolatedAsyncioTestCase):
    async def test_the_creator_leads_and_a_join_shows_everyone(self):
        await self.start()
        tamsin = await self.join("Tamsin", 1)
        await party(tamsin, "create", mode=MODES["high_water"])
        created = await state(tamsin)
        self.assertEqual(len(created["code"]), 5)
        self.assertEqual((created["mode"], created["leader"], created["you"], created["phase"], created["countdown_ms"],
                          created["flags"]), (MODES["high_water"], 0, 0, PHASES["forming"], 0, 0))
        self.assertEqual(created["members"], [dict(member=0, team=0, main=BUILDERS["lamplighter"],
                                                   backup=BUILDERS["lookout"], state=MEMBER["here"], rtt_ms=0,
                                                   build_seq=7, rules_hash=RULES, name="Tamsin")])
        edda = await self.join("Edda", 2)
        await party(edda, "join", code=created["code"])
        seen = await self.everyone((tamsin, edda))
        # (one party for both, each told its own row: a game finds itself by `you`)
        self.assertEqual([seen[0]["you"], seen[1]["you"]], [0, 1])
        self.assertEqual(dict(seen[0], you=None), dict(seen[1], you=None))
        self.assertEqual([(m["member"], m["name"]) for m in seen[0]["members"]], [(0, "Tamsin"), (1, "Edda")])
        self.assertEqual(seen[0]["leader"], 0)

    async def test_ready_the_countdown_and_its_cancel(self):
        await self.start()
        (tamsin, edda, ottilie), _ = await self.party_of("Tamsin", "Edda", "Ottilie")
        everyone = (tamsin, edda, ottilie)
        # (the leader's Start with a member not Ready: refused, the party as it is)
        await party(tamsin, "start")
        refused = await state(tamsin)
        self.assertEqual(refused["phase"], PHASES["forming"])
        self.assertTrue(await edda.quiet())
        # (a member's Start is the leader's alone)
        await self.ready_all(everyone)
        await party(edda, "start")
        self.assertEqual((await state(edda))["phase"], PHASES["forming"])
        await party(tamsin, "start")
        counting = await self.everyone(everyone)
        self.assertEqual((counting[0]["phase"], counting[0]["countdown_ms"]), (PHASES["countdown"], 3000))
        self.assertEqual(states(counting[0]), {"Tamsin": MEMBER["here"], "Edda": MEMBER["ready"],
                                               "Ottilie": MEMBER["ready"]})
        await self.clock.advance(1000)
        await party(ottilie, "cancel")
        cancelled = await self.everyone(everyone)
        self.assertEqual((cancelled[0]["phase"], cancelled[0]["countdown_ms"]), (PHASES["forming"], 0))
        # (anyone may cancel; Ready stays, so the leader may start again)
        self.assertEqual(states(cancelled[0])["Ottilie"], MEMBER["ready"])
        await self.clock.advance(5000)
        self.assertFalse(self.server.matches)
        await party(tamsin, "start")
        await self.everyone(everyone)
        await self.clock.advance(2000)
        await party(edda, "ready", on=1)        # (a repeat: nothing moves)
        self.assertEqual((await state(edda))["countdown_ms"], 1000)
        await self.everyone((tamsin, ottilie))
        await self.clock.advance(999)
        self.assertFalse(self.server.matches)
        await self.clock.advance(1)
        loading = await self.everyone(everyone)
        self.assertEqual(loading[0]["phase"], PHASES["loading"])
        self.assertEqual(set(states(loading[0]).values()), {MEMBER["in_match"]})
        configs = await self.everyone(everyone, "MATCH_CONFIG")
        self.assertEqual([c["your_seat"] for c in configs], [0, 1, 2])
        self.assertEqual([s["name"] for s in configs[0]["seats"]], ["Tamsin", "Edda", "Ottilie"])
        self.assertEqual(configs[0]["mode"], MODES["high_water"])

    async def test_an_un_ready_a_builder_change_or_a_join_stops_the_countdown(self):
        await self.start()
        (tamsin, edda), code = await self.party_of("Tamsin", "Edda")
        for stop in (lambda: party(edda, "ready", on=0), lambda: party(edda, "builders", main=1, backup=0)):
            await party(edda, "ready", on=1)
            await self.everyone((tamsin, edda))
            await party(tamsin, "start")
            await self.everyone((tamsin, edda))
            await stop()
            stopped = await self.everyone((tamsin, edda))
            self.assertEqual(stopped[0]["phase"], PHASES["forming"])
            self.assertEqual(states(stopped[0])["Edda"], MEMBER["here"])
        await party(edda, "ready", on=1)
        await self.everyone((tamsin, edda))
        await party(tamsin, "start")
        await self.everyone((tamsin, edda))
        ottilie = await self.join("Ottilie", 3)
        await party(ottilie, "join", code=code)
        joined = await self.everyone((tamsin, edda, ottilie))
        self.assertEqual(joined[0]["phase"], PHASES["forming"])
        await self.clock.advance(3000)
        self.assertFalse(self.server.matches)

    async def test_builders_are_each_members_own_and_reach_the_match(self):
        await self.start()
        (tamsin, edda), _ = await self.party_of("Tamsin", "Edda")
        await party(edda, "builders", main=BUILDERS["lookout"], backup=BUILDERS["lamplighter"])
        shown = await self.everyone((tamsin, edda))
        edda_row = shown[0]["members"][1]
        self.assertEqual((edda_row["main"], edda_row["backup"]), (BUILDERS["lookout"], BUILDERS["lamplighter"]))
        # (duplicates are allowed in High Water: both may play the Lookout)
        await party(tamsin, "builders", main=BUILDERS["lookout"], backup=BUILDERS["lookout"])
        await self.everyone((tamsin, edda))
        await self.ready_all((tamsin, edda))
        configs = await self.to_loading((tamsin, edda))
        self.assertEqual([s["builder"] for s in configs[0]["seats"]], [BUILDERS["lookout"]] * 2)

    async def test_a_mode_change_clears_every_ready(self):
        await self.start()
        (tamsin, edda, ottilie), _ = await self.party_of("Tamsin", "Edda", "Ottilie")
        await self.ready_all((tamsin, edda, ottilie))
        await party(edda, "mode", mode=MODES["classic"])        # (a member's: refused)
        self.assertEqual((await state(edda))["mode"], MODES["high_water"])
        await party(tamsin, "mode", mode=MODES["classic"])
        changed = await self.everyone((tamsin, edda, ottilie))
        self.assertEqual(changed[0]["mode"], MODES["classic"])
        self.assertEqual(set(states(changed[0]).values()), {MEMBER["here"]})

    async def test_the_earliest_member_leads_when_the_leader_leaves(self):
        await self.start()
        (tamsin, edda, ottilie), _ = await self.party_of("Tamsin", "Edda", "Ottilie")
        await party(tamsin, "leave")
        gone = await state(tamsin)
        self.assertEqual((gone["code"], gone["members"], gone["leader"], gone["you"]), (bytes(5), [], 255, 255))
        left = await self.everyone((edda, ottilie))
        self.assertEqual(left[0]["leader"], 1)                   # (Edda, row 1, joined before Ottilie)
        self.assertEqual([m["name"] for m in left[0]["members"]], ["Edda", "Ottilie"])
        await party(edda, "leave")
        self.assertEqual((await state(ottilie))["leader"], 2)
        # (a newcomer takes the lowest free row; the leader stays Ottilie)
        sefa = await self.join("Sefa", 4)
        await party(sefa, "join", code=left[0]["code"])
        joined = await state(sefa)
        self.assertEqual(([m["member"] for m in joined["members"]], joined["leader"]), ([0, 2], 2))

    async def test_the_leader_removes_a_member_who_cannot_rejoin(self):
        await self.start()
        (tamsin, edda, ottilie), code = await self.party_of("Tamsin", "Edda", "Ottilie")
        await party(edda, "remove", member=2)                    # (a member's: refused)
        self.assertEqual(len((await state(edda))["members"]), 3)
        await party(tamsin, "remove", member=0)                  # (not oneself)
        self.assertEqual(len((await state(tamsin))["members"]), 3)
        await party(tamsin, "remove", member=1)
        notice = await edda.until("NOTICE")
        self.assertEqual(notice, dict(code=NOTICES["removed"], argument=0))
        self.assertEqual((await state(edda))["members"], [])
        kept = await self.everyone((tamsin, ottilie))
        self.assertEqual([m["name"] for m in kept[0]["members"]], ["Tamsin", "Ottilie"])
        await party(edda, "join", code=code)
        self.assertEqual(await edda.until("NOTICE"), dict(code=NOTICES["removed"], argument=0))
        self.assertTrue(await tamsin.quiet())

    async def test_a_party_holds_four(self):
        await self.start()
        clients, code = await self.party_of("A", "B", "C", "D")
        fifth = await self.join("E", 5)
        await party(fifth, "join", code=code)
        self.assertEqual(await fifth.until("NOTICE"), dict(code=NOTICES["party_full"], argument=4))
        self.assertTrue(await clients[0].quiet())

    async def test_another_rules_hash_needs_to_reload_and_holds_the_start(self):
        await self.start()
        tamsin = await self.join("Tamsin", 1, build_seq=8)
        await party(tamsin, "create", mode=MODES["high_water"])
        code = (await state(tamsin))["code"]
        stale = await self.join("Edda", 2, build_seq=7, rules_hash=bytes(8))
        await party(stale, "join", code=code)
        # (the older build is told, and every row shows who needs to reload)
        self.assertEqual(await stale.until("NOTICE"), dict(code=NOTICES["needs_reload"], argument=1))
        shown = await self.everyone((tamsin, stale))
        self.assertEqual(states(shown[0]), {"Tamsin": MEMBER["here"], "Edda": MEMBER["needs_reload"]})
        await party(stale, "ready", on=1)
        await self.everyone((tamsin, stale))
        await party(tamsin, "start")
        self.assertEqual((await state(tamsin))["phase"], PHASES["forming"])
        # (a newer build joining makes the leader the one who needs to reload)
        newer = await self.join("Ottilie", 3, build_seq=9, rules_hash=bytes(range(8)))
        await party(newer, "join", code=code)
        self.assertEqual(await tamsin.until("NOTICE"), dict(code=NOTICES["needs_reload"], argument=0))
        shown = await state(newer)
        self.assertEqual(states(shown), {"Tamsin": MEMBER["needs_reload"], "Edda": MEMBER["needs_reload"],
                                         "Ottilie": MEMBER["here"]})

    async def test_a_race_lays_out_two_teams_the_leader_moves(self):
        await self.start()
        clients, code = await self.party_of("A", "B", "C", mode="tide_race")
        # (a joiner goes to the smaller team: A and C against B)
        self.assertEqual([m.team for m in self.server.lobby.parties[code].ordered()], [0, 1, 0])
        await self.ready_all(clients)
        await party(clients[0], "start")                          # (two against one: refused)
        self.assertEqual((await state(clients[0]))["phase"], PHASES["forming"])
        await party(clients[1], "team", member=2, team=1)         # (a member's: refused)
        self.assertEqual([m["team"] for m in (await state(clients[1]))["members"]], [0, 1, 0])
        await party(clients[2], "leave")
        await state(clients[2])
        await self.everyone(clients[:2])
        # (the leader moves members, itself too; a member moved is no longer Ready)
        await party(clients[0], "team", member=0, team=1)
        await self.everyone(clients[:2])
        await party(clients[0], "team", member=1, team=0)
        moved = await self.everyone(clients[:2])
        self.assertEqual([(m["team"], m["state"]) for m in moved[0]["members"]],
                         [(1, MEMBER["here"]), (0, MEMBER["here"])])
        await party(clients[1], "ready", on=1)
        await self.everyone(clients[:2])
        configs = await self.to_loading(clients[:2])
        self.assertEqual([(s["name"], s["team"]) for s in configs[0]["seats"]], [("B", 0), ("A", 1)])
        self.assertEqual(configs[0]["mode"], MODES["tide_race"])

    async def test_the_team_op_belongs_to_a_race(self):
        await self.start()
        clients, _ = await self.party_of("A", "B")
        await party(clients[0], "team", member=1, team=1)
        self.assertEqual([m["team"] for m in (await state(clients[0]))["members"]], [0, 0])
        await party(clients[0], "mode", mode=MODES["tide_race"])
        raced = await self.everyone(clients)
        self.assertEqual([m["team"] for m in raced[0]["members"]], [0, 1])

    async def test_open_seats_and_the_queue_to_come(self):
        await self.start()
        clients, _ = await self.party_of("A", "B")
        await party(clients[0], "open", on=1)
        opened = await self.everyone(clients)
        self.assertEqual(opened[0]["flags"], SPEC["party_flags"]["open"])
        self.assertEqual(self.server.lobby.open_parties(), 1)
        # (no public queue before M6: every QUEUE op is answered idle)
        for op in SPEC["queue_ops"].values():
            await clients[0].send_message("QUEUE", op=op)
            self.assertEqual(await clients[0].until("QUEUE_STATE"), dict(state=0, elapsed_ms=0, caretaker_offer=0))
        await clients[1].send_message("ACCEPT", match=1, yes=1)
        self.assertTrue(await clients[1].quiet())

    async def test_a_party_op_outside_its_limits_ends_the_connection(self):
        await self.start()
        for op, fields in (("create", dict(mode=9)), ("builders", dict(main=4, backup=0)), ("ready", dict(on=2)),
                           ("team", dict(member=0, team=2)), ("remove", dict(member=4)), ("open", dict(on=7))):
            client = await self.join("Tamsin", 1)
            await party(client, "create", mode=MODES["classic"])
            await state(client)
            await party(client, op, **fields)
            error = await client.until("ERROR", skip=("PARTY_STATE",))
            self.assertEqual(error["code"], ERRORS["out_of_limits"], op)

    async def test_ops_without_a_party_answer_with_no_party(self):
        await self.start()
        client = await self.join("Tamsin", 1)
        for op, fields in (("leave", {}), ("ready", dict(on=1)), ("start", {}), ("cancel", {})):
            await party(client, op, **fields)
            alone = await state(client)
            self.assertEqual((alone["code"], alone["members"]), (bytes(5), []), op)

    async def test_create_while_in_a_party_moves_to_the_new_one(self):
        await self.start()
        (tamsin, edda), code = await self.party_of("Tamsin", "Edda")
        await party(edda, "create", mode=MODES["classic"])
        own = await state(edda)
        self.assertNotEqual(own["code"], code)
        self.assertEqual([m["name"] for m in own["members"]], ["Edda"])
        self.assertEqual([m["name"] for m in (await state(tamsin))["members"]], ["Tamsin"])

    async def test_a_dev_match_server_has_no_hub(self):
        await self.start(dev_match="classic:2")
        client = await self.join("Tamsin", 1)
        await party(client, "create", mode=MODES["classic"])
        self.assertEqual((await client.until("ERROR"))["code"], ERRORS["protocol"])


if __name__ == "__main__":
    unittest.main()
