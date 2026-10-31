"""The M4 contract (docs/design/contract-m4.md): what protocol.json fixed for
resilience, appended to M1's and M3's without moving a number; the codec's
rules both sides share (a checkpoint's digest and its parts, a resume HELLO's
held seat); the VISIBILITY states and their LINKS flag; and catchup.py's
interface, which the server track fills in."""

import hashlib
import inspect
import unittest

from support import Client, ManualClock, MatchTest, server, start_match, until
from groundhold_server import catchup, protocol
from groundhold_server.protocol import ProtocolError, SPEC

# Every message id and enum value M1 to M3 fixed: M4 only appends.
MESSAGE_IDS = {
    "HELLO": 1, "WELCOME": 2, "ERROR": 5, "PING": 6, "PONG": 7, "NOTICE": 14, "BYE": 15, "PARTY": 20,
    "PARTY_STATE": 21, "QUEUE": 22, "QUEUE_STATE": 23, "MATCH_FOUND": 24, "ACCEPT": 25, "MATCH_CONFIG": 30,
    "LOADING": 31, "LOAD_STATE": 32, "LOADED": 33, "START": 34, "CMD": 40, "TURN": 41, "HASH": 42,
    "CHECKPOINT_ASK": 43, "CHECKPOINT_PART": 44, "RESYNC": 45, "TURN_REQUEST": 46, "VISIBILITY": 47,
    "RESULT": 48, "MATCH_END": 49, "LEAVE_MATCH": 50, "LINKS": 52,
}
BEFORE_M4 = {
    "errors": {"protocol": 1, "game_older": 2, "bad_name": 5, "out_of_limits": 6, "full": 7, "rate": 8,
               "bad_token": 9, "banned": 10, "allowlist": 11, "replaced": 12, "kicked": 14, "maintenance": 16,
               "server_older": 17},
    "notices": {"party_full": 1, "no_such_party": 2, "removed": 3, "match_dissolved": 4, "needs_reload": 5,
                "caretakers_offered": 6, "tick0_mismatch": 7, "parties_full": 8},
    "end_reasons": {"result": 0, "desync": 1, "tick0_mismatch": 2, "rules_mismatch": 3, "everyone_left": 4,
                    "timeout": 5, "server_closing": 6},
    "outcomes": {"won": 0, "lost": 1, "draw": 2, "desynced": 3, "aborted": 4},
    "hello_flags": {"resume": 1, "web": 2},
    "hash_flags": {"checkpoint": 1},
    "link_flags": {"hidden": 1, "silent": 2},
    "seat_flags": {"caretaker": 1},
}
M4_NUMBERS = {
    "checkpoint_ticks": 1800, "checkpoints_kept": 2, "max_checkpoint_parts": 64, "checkpoint_wait_ms": 5000,
    "catchup_bytes": 2048, "catchup_ms": 50, "catchup_output": 4096, "max_resyncs": 1, "reconnect_ms": 2000,
}
M4_VALUES = {
    "config_flags": {"rejoin": 1},
    "visibility_states": {"shown": 0, "hidden": 1, "catching_up": 2},
    "resync_reasons": {"rejoin": 0, "desync": 1, "behind": 2},
}
# The digest vectors contract_m4_wire_and_seams checks the GDScript side against.
DIGESTS = {b"": "e3b0c44298fc1c14", b"Groundhold": "948c7975fbd6b867"}


def fields(name):
    return [(field.name, field.kind) for field in protocol.MESSAGES[name].fields]


class ContractM4Tests(unittest.TestCase):
    def test_numbers_are_appended_never_moved(self):
        self.assertEqual({name: message.id for name, message in protocol.MESSAGES.items()}, MESSAGE_IDS)
        for table, values in BEFORE_M4.items():
            self.assertEqual({key: SPEC[table][key] for key in values}, values, table)
        self.assertEqual(SPEC["notices"]["no_held_seat"], 9)
        self.assertEqual(SPEC["end_reasons"]["desynced_twice"], 7)
        self.assertEqual(SPEC["link_flags"]["catching_up"], 4)
        for table, values in M4_VALUES.items():
            self.assertEqual(SPEC[table], values, table)
        for key, value in M4_NUMBERS.items():
            self.assertEqual(SPEC[key], value, key)
        # (a checkpoint tick is a hash tick; the most parts hold Appendix A's 10 KB many times over)
        self.assertEqual(SPEC["checkpoint_ticks"] % SPEC["hash_every"], 0)
        self.assertGreaterEqual(SPEC["max_checkpoint_parts"] * SPEC["checkpoint_part"], 64 * 1024)

    def test_layouts_append_their_new_fields(self):
        self.assertEqual(fields("HELLO")[-3:], [("name", "s8"), ("match", "u32"), ("seat", "u8")])
        self.assertEqual(fields("MATCH_CONFIG")[-2:], [("seats", "l8"), ("flags", "u8")])
        self.assertEqual(fields("RESYNC"), [("checkpoint_tick", "u32"), ("first_turn", "u32"), ("reason", "u8"),
                                            ("open_turn", "u32"), ("checkpoint_hash", "b8"), ("parts", "u16")])
        self.assertEqual(fields("VISIBILITY"), [("state", "u8")])
        sizes = {name: message.sizes() for name, message in protocol.MESSAGES.items()}
        self.assertEqual(sizes["HELLO"], (38, 54))
        self.assertEqual(sizes["MATCH_CONFIG"], (22, 106))
        self.assertEqual(sizes["RESYNC"], (24, 24))
        self.assertEqual(sizes["VISIBILITY"], (2, 2))

    def test_a_checkpoint_digest_is_sha256_cut_to_a_hash(self):
        for data, hex_digest in DIGESTS.items():
            self.assertEqual(protocol.digest(data).hex(), hex_digest)
            self.assertEqual(protocol.digest(data), hashlib.sha256(data).digest()[:SPEC["hash_bytes"]])

    def test_a_checkpoint_goes_in_full_parts_but_the_last(self):
        data = bytes(range(256)) * 9 + b"tail"                  # 2,308 bytes
        parts = [protocol.decode(message)[1] for message in protocol.checkpoint_parts(1800, data)]
        self.assertEqual([(p["tick"], p["part"], p["parts"], len(p["data"])) for p in parts],
                         [(1800, 0, 3, 1024), (1800, 1, 3, 1024), (1800, 2, 3, 260)])
        self.assertEqual(b"".join(p["data"] for p in parts), data)
        self.assertEqual(protocol.checkpoint_parts(0, b""), [])
        self.assertEqual(len(protocol.checkpoint_parts(60, bytes(64 * 1024))), 64)
        with self.assertRaises(ValueError):
            protocol.checkpoint_parts(60, bytes(64 * 1024 + 1))

    def test_a_resume_hello_names_its_held_seat_or_none(self):
        def hello(**held):
            return protocol.encode("HELLO", version=SPEC["version"], build_seq=7, rules_hash=bytes(8),
                                   token=bytes(range(1, 17)), flags=SPEC["hello_flags"]["resume"], name="Edda", **held)
        self.assertEqual(protocol.read_hello(hello(match=0, seat=255))["seat"], 255)
        self.assertEqual(protocol.read_hello(hello(match=9, seat=3))["match"], 9)
        for held in (dict(match=9, seat=4), dict(match=0, seat=1)):
            with self.assertRaises(ProtocolError) as refused:
                protocol.read_hello(hello(**held))
            self.assertEqual(refused.exception.code, SPEC["errors"]["protocol"], held)

    def test_catchup_keeps_the_contracts_interface(self):
        self.assertEqual((catchup.BYTES, catchup.EVERY_MS, catchup.OUTPUT), (2048, 50, 4096))
        self.assertEqual(list(inspect.signature(catchup.CatchUp).parameters), ["write", "buffered", "budget", "below"])
        for method in ("queue", "pump"):
            self.assertTrue(callable(getattr(catchup.CatchUp, method)), method)
        written = []
        pacer = catchup.CatchUp(written.append, lambda: 0)
        self.assertTrue(pacer.done)
        pacer.queue(protocol.turn(5, ()))
        self.assertFalse(pacer.done)
        self.assertEqual(pacer.total, 6)
        self.assertIsInstance(pacer.pump(), int)


class VisibilityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = ManualClock()
        self.server = server(dev_match="classic:2", clock=self.clock)
        self.port = await self.server.start("127.0.0.1", 0)
        self.clients = []

    async def asyncTearDown(self):
        for client in self.clients:
            await client.drop()
        await self.server.close()

    async def join(self, name, number):
        client = Client()
        self.clients.append(client)
        welcome = await client.hello(self.port, name, token=bytes((number,)) * 16)
        self.assertEqual(welcome[0], "WELCOME")
        return client

    async def test_catching_up_shows_in_links_and_an_unknown_state_ends_the_link(self):
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        await start_match(self.clock, (one, two))
        match = next(iter(self.server.matches.values()))
        await two.send_message("VISIBILITY", state=SPEC["visibility_states"]["catching_up"])
        await until(lambda: match.seats[1].player.catching_up)
        self.assertFalse(match.seats[1].player.hidden)
        await self.clock.turns(SPEC["links_ms"] // SPEC["turn_ms"])
        links = await one.until("LINKS", skip=("TURN",))
        self.assertEqual([seat["flags"] for seat in links["seats"]], [0, SPEC["link_flags"]["catching_up"]])
        await two.send_message("VISIBILITY", state=SPEC["visibility_states"]["shown"])
        await until(lambda: not match.seats[1].player.catching_up)
        await one.send_message("VISIBILITY", state=3)
        error = await one.until("ERROR", skip=("TURN", "LINKS"))
        self.assertEqual(error["code"], SPEC["errors"]["out_of_limits"])


class RejoinContractTests(MatchTest, unittest.IsolatedAsyncioTestCase):
    async def test_rejoin_names_its_seat(self):
        """README, Resilience: Rejoin. A resume HELLO naming the seat its
        identity holds: ERROR 12 (replaced) to the old link still open,
        MATCH_CONFIG with the rejoin flag, then RESYNC(rejoin); one naming a
        seat it does not hold: NOTICE no_held_seat after WELCOME."""
        tamsin, edda = await self.seated("Tamsin", "Edda")
        match = self.match()
        await self.clock.turns(3)
        again = await self.join("Edda", 2, flags=SPEC["hello_flags"]["resume"], match=match.id, seat=1)
        self.assertEqual(again.answer[0], "WELCOME")
        name, config = await again.next()
        self.assertEqual((name, config["match"], config["your_seat"], config["flags"]),
                         ("MATCH_CONFIG", match.id, 1, SPEC["config_flags"]["rejoin"]))
        self.assertEqual(await edda.until("ERROR", skip=("TURN",)),
                         dict(code=SPEC["errors"]["replaced"], text="Replaced by another session of this profile"))
        await self.clock.turns(1)
        resync = await again.until("RESYNC", skip=("LINKS",))
        self.assertEqual((resync["reason"], resync["checkpoint_tick"], resync["open_turn"]),
                         (SPEC["resync_reasons"]["rejoin"], 0, 3))
        for held in (dict(match=match.id, seat=0), dict(match=match.id + 1, seat=1)):
            other = await self.join("Edda", 2, flags=SPEC["hello_flags"]["resume"], **held)
            self.assertEqual(other.answer[0], "WELCOME")
            self.assertEqual(await other.next(), ("NOTICE", dict(code=SPEC["notices"]["no_held_seat"], argument=0)))
        self.assertIs(match.seats[1].player.match, match)


if __name__ == "__main__":
    unittest.main()
