"""The M8 contract's wire (docs/design/contract-m8.md §1, §3 and §5): protocol
version 2 for the level's fields and nothing else; the levels' wire ids and
which modes take one, as protocol.json says it for the server, which never
reads content.gd; PARTY op difficulty 12, the level right after `mode` in
PARTY_STATE and MATCH_CONFIG; every other message and command as M7 left it,
but READY's b, which names the wave a READY 1 calls (the review's fix: a press
that lands after its horn calls nothing); and the server's side: the party's level and its rule, the queue keyed on mode,
rules hash and level, and --dev-match MODE:N[:LEVEL]."""

import inspect
import unittest

import support  # noqa: F401  (puts server/ on the path)
from groundhold_server import app, party, protocol, queue
from groundhold_server.protocol import SPEC

LEVELS = {"normal": 0, "hard": 1, "very_hard": 2}
TAKES_A_LEVEL = {"classic": False, "high_water": True, "tide_race": True, "undertow": False}
# The layouts M8 leaves as M7 had them (contract §5, Unchanged), field by field.
UNCHANGED = {
    "HELLO": [("version", "u16"), ("build_seq", "u32"), ("rules_hash", "b8"), ("token", "b16"), ("flags", "u8"),
              ("name", "s8"), ("match", "u32"), ("seat", "u8")],
    "LOADED": [("rules_hash", "b8"), ("tick0_hash", "b8")],
    "MATCH_FOUND": [("match", "u32"), ("mode", "u8"), ("seats", "u8"), ("accepted", "u8"), ("ms_left", "u32")],
    "QUEUE": [("op", "u8")],
    "QUEUE_STATE": [("state", "u8"), ("elapsed_ms", "u32"), ("caretaker_offer", "u8")],
    "ACCEPT": [("match", "u32"), ("yes", "u8")],
    "RESULT": [("tick", "u32"), ("hash", "b8"), ("outcomes", "l8")],
    "MATCH_END": [("outcome", "u8"), ("reason", "u8"), ("final_tick", "u32")],
}
M7_PARTY_OPS = {"create": 1, "join": 2, "leave": 3, "remove": 4, "mode": 5, "builders": 6, "ready": 7, "team": 8,
                "open": 9, "start": 10, "cancel": 11}
COMMANDS = {"BUILD": 1, "FORK": 2, "SELL": 3, "READY": 4, "SIGNAL": 5, "CORK": 6, "UNCORK": 7, "SEAWALL": 8}


def fields(name):
    return [(field.name, field.kind) for field in protocol.MESSAGES[name].fields]


class ContractM8Wire(unittest.TestCase):
    def test_version_2_speaks_groundhold_v2(self):
        self.assertEqual((SPEC["version"], SPEC["subprotocol"]), (2, "groundhold.v2"))

    def test_the_levels_and_the_modes_that_take_one(self):
        self.assertEqual(SPEC["difficulties"], LEVELS)
        self.assertEqual((protocol.NORMAL, protocol.DIFFICULTY_NAMES), (0, {0: "normal", 1: "hard", 2: "very_hard"}))
        for mode, takes in TAKES_A_LEVEL.items():
            self.assertIs(SPEC["modes"][mode].get("levels", False), takes, mode)
            # (a mode without levels plays Normal whatever is asked: SimContent.level_of's rule)
            self.assertEqual([protocol.level_of(mode, level) for level in LEVELS.values()],
                             list(LEVELS.values()) if takes else [0, 0, 0], mode)

    def test_the_party_op_and_the_two_messages_that_carry_the_level(self):
        self.assertEqual(SPEC["party_ops"], dict(M7_PARTY_OPS, difficulty=12))
        self.assertEqual(SPEC["messages"]["PARTY"]["switch"]["cases"]["difficulty"], [["difficulty", "u8"]])
        self.assertEqual(SPEC["messages"]["PARTY"]["switch"]["cases"]["create"], [["mode", "u8"]])
        for name in ("PARTY_STATE", "MATCH_CONFIG"):
            names = fields(name)
            at = names.index(("mode", "u8"))
            self.assertEqual(names[at + 1], ("difficulty", "u8"), name)
        self.assertEqual(protocol.MESSAGES["PARTY_STATE"].sizes(), (17, 161))
        self.assertEqual(protocol.MESSAGES["MATCH_CONFIG"].sizes(), (23, 107))
        self.assertEqual(protocol.MESSAGES["PARTY"].sizes(), (2, 7))

    def test_everything_else_is_as_m7_left_it(self):
        for name, layout in UNCHANGED.items():
            self.assertEqual(fields(name), layout, name)
        self.assertEqual({name: spec["type"] for name, spec in SPEC["commands"].items()}, COMMANDS)
        # (READY's b names the wave a READY 1 calls, 0 none: its range is the server's whole check)
        self.assertEqual(SPEC["commands"]["READY"]["args"], [[0, 1], [0, 65535], [0, 0]])
        protocol.check_command(COMMANDS["READY"], 1, 12, 0)
        protocol.check_command(COMMANDS["READY"], 1, 0, 0)
        for b in (-1, 65536):
            with self.assertRaises(protocol.ProtocolError):
                protocol.check_command(COMMANDS["READY"], 1, b, 0)
        for name, message in protocol.MESSAGES.items():
            if name not in ("PARTY", "PARTY_STATE", "MATCH_CONFIG"):
                self.assertNotIn("difficulty", [f.name for f in message.fields], name)

    def test_the_servers_side(self):
        # (the party's level, Normal at first, and the level its match plays)
        made = party.Party(b"K7Q4M", SPEC["modes"]["undertow"]["id"])
        self.assertEqual(made.difficulty, protocol.NORMAL)
        made.set_difficulty(LEVELS["hard"])
        self.assertEqual((made.difficulty, made.level()), (LEVELS["hard"], protocol.NORMAL))
        made.set_mode(SPEC["modes"]["tide_race"]["id"])
        self.assertEqual((made.difficulty, made.level()), (LEVELS["hard"], LEVELS["hard"]))
        # (the queue's key: mode, rules hash and level)
        self.assertEqual(list(inspect.signature(queue.Queue.waiting).parameters), ["self", "mode", "rules", "level"])
        self.assertIn("level", [f.name for f in queue.Ticket.__dataclass_fields__.values()])
        self.assertEqual(app.dev_match_spec("high_water:2:hard"), ("high_water", 2, LEVELS["hard"]))
        self.assertEqual(app.dev_match_spec("classic:2"), ("classic", 2, LEVELS["normal"]))


if __name__ == "__main__":
    unittest.main()
