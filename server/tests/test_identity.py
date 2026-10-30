"""Identity without accounts (docs/design/core-loop.md §6.12, §8 M3
test_identity): a game's token is stable per server origin and unlinkable
across origins; the server's public identity is stable on one server,
across restarts, and unlinkable across servers; and the moderation it
carries (bans, the allowlist, kicks, mutes), as in Cyberworld."""

import json
import os
from pathlib import Path
import stat
import tempfile
import time
import unittest

from support import RULES, TICK0, Client, HubTest, state, until
from groundhold_server.identity import IdentityStore, client_token, origin, public_identity
from groundhold_server.protocol import SPEC

ERRORS = SPEC["errors"]
DEVICE = bytes(range(16))


class TokenTests(unittest.TestCase):
    def test_origins_normalise_as_the_game_keys_them(self):
        for url, expected in (("ws://192.168.1.20:8766/causeway", "ws://192.168.1.20:8766"),
                              ("WS://192.168.1.20:8766/", "ws://192.168.1.20:8766"),
                              ("wss://Groundhold.saschb2b.com./causeway", "wss://groundhold.saschb2b.com:443"),
                              ("ws://example.org/causeway", "ws://example.org:80"),
                              ("ws://[fd00::1]:8766/causeway", "ws://[fd00::1]:8766")):
            self.assertEqual(origin(url), expected, url)
        for wrong in ("http://example.org/", "ws://", "ws://host:0/", "ws://host:70000/", "groundhold"):
            self.assertIsNone(origin(wrong), wrong)

    def test_a_token_is_stable_per_origin_and_unlinkable_across(self):
        lan = client_token(DEVICE, "ws://192.168.1.20:8766/causeway")
        self.assertEqual(lan, client_token(DEVICE, "ws://192.168.1.20:8766/"))
        self.assertEqual(len(lan), 16)
        others = {client_token(DEVICE, url) for url in (
            "wss://192.168.1.20:8766/causeway",        # (ws and wss apart: a plaintext host never reuses a TLS key)
            "ws://192.168.1.20:8767/causeway",
            "ws://192.168.1.21:8766/causeway",
            "wss://groundhold.saschb2b.com/causeway")}
        self.assertEqual(len(others), 4)
        self.assertNotIn(lan, others)
        # (another device, another token for the same server)
        self.assertNotEqual(client_token(bytes(16), "ws://192.168.1.20:8766/causeway"), lan)
        # (the reference value shared/net/README.md gives the game's derivation)
        self.assertEqual(client_token(DEVICE, "wss://groundhold.saschb2b.com/causeway").hex(),
                         "5c0d37e02b41a1060b3bfe6a5c10af52")

    def test_the_public_identity_is_stable_per_server_and_unlinkable_across(self):
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            first = IdentityStore(one)
            token = client_token(DEVICE, "ws://192.168.1.20:8766/causeway")
            seen = first.identity(token)
            self.assertEqual(seen, public_identity(first.secret, token))
            # (the key is made once, owner-only, and read again after a restart)
            key = Path(one) / "identity.key"
            self.assertEqual(len(key.read_bytes()), 32)
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(key.stat().st_mode), 0o600)
            self.assertEqual(IdentityStore(one).identity(token), seen)
            # (another server: another key, so even the same token is another identity)
            self.assertNotEqual(IdentityStore(two).identity(token), seen)
            key.write_bytes(b"short")
            with self.assertRaises(ValueError):
                IdentityStore(one)


class ModerationTests(HubTest, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.temporary = tempfile.TemporaryDirectory(prefix="groundhold-identity-")
        self.dir = Path(self.temporary.name)

    async def asyncTearDown(self):
        await super().asyncTearDown()
        self.temporary.cleanup()

    def rule(self, action, public, **entry):
        path = self.dir / "moderation.json"
        rules = json.loads(path.read_text()) if path.exists() else {"bans": {}, "mutes": {}, "kicks": {}}
        rules[action][public.hex()] = dict({"time": time.time(), "reason": "test"}, **entry)
        path.write_text(json.dumps(rules))

    async def refused(self, number, **options):
        client = Client()
        self.clients.append(client)
        return await client.hello(self.port, "Edda", token=bytes((number,)) * 16, **options)

    async def test_the_same_token_is_the_same_identity_across_a_restart(self):
        await self.start(state_dir=self.dir, identity_key=None)
        first = (await self.join("Tamsin", 1)).welcome["identity"]
        await self.server.close()
        self.server = None
        await self.start(state_dir=self.dir, identity_key=None)
        self.assertEqual((await self.join("Tamsin", 1)).welcome["identity"], first)

    async def test_a_ban_the_allowlist_and_a_kick_refuse_at_hello(self):
        await self.start(state_dir=self.dir)
        banned = public_identity(self.server.store.secret, bytes((2,)) * 16)
        kicked = public_identity(self.server.store.secret, bytes((3,)) * 16)
        self.rule("bans", banned)
        self.rule("kicks", kicked, expires=time.time() + 90)
        name, error = await self.refused(2)
        self.assertEqual((name, error["code"]), ("ERROR", ERRORS["banned"]))
        name, error = await self.refused(3)
        self.assertEqual((name, error["code"], error["text"]),
                         ("ERROR", ERRORS["kicked"], "Kicked by a moderator; try again in 2 min"))
        await self.server.close()
        allowed = public_identity(self.server.store.secret, bytes((4,)) * 16)
        await self.start(state_dir=self.dir, allowlist=(allowed.hex(),))
        name, error = await self.refused(5)
        self.assertEqual((name, error["code"]), ("ERROR", ERRORS["allowlist"]))
        await self.join("Sefa", 4)

    async def test_a_ban_drops_a_connected_player_within_a_second(self):
        await self.start(state_dir=self.dir)
        (tamsin, edda), _ = await self.party_of("Tamsin", "Edda")
        self.rule("bans", public_identity(self.server.store.secret, bytes((2,)) * 16))
        await self.clock.advance(1000)
        self.assertEqual((await edda.until("ERROR"))["code"], ERRORS["banned"])
        # (no row held for a moderator's removal)
        left = await state(tamsin)
        self.assertEqual([m["name"] for m in left["members"]], ["Tamsin"])
        # (players.json, the roster for moderators, names those connected
        # now: written at the next second's housekeeping)
        await self.clock.advance(1000)
        await until(lambda: (self.dir / "players.json").exists()
                    and len(json.loads((self.dir / "players.json").read_text())["players"]) == 1)

    async def test_a_bad_moderation_file_keeps_the_last_good_rules(self):
        await self.start(state_dir=self.dir)
        self.rule("bans", public_identity(self.server.store.secret, bytes((2,)) * 16))
        name, _ = await self.refused(2)
        self.assertEqual(name, "ERROR")
        (self.dir / "moderation.json").write_text("{not json")
        with self.assertLogs("groundhold.server", "ERROR"):
            name, _ = await self.refused(2)
        self.assertEqual(name, "ERROR")

    async def test_a_muted_profiles_signals_reach_no_one(self):
        sealed = []
        await self.start(state_dir=self.dir, observer=lambda turn, now, entries: sealed.extend(entries))
        (tamsin, edda), _ = await self.party_of("Tamsin", "Edda")
        self.rule("mutes", public_identity(self.server.store.secret, bytes((2,)) * 16))
        await self.clock.advance(1000)
        await self.ready_all((tamsin, edda))
        await self.to_loading((tamsin, edda))
        for client in (tamsin, edda):
            await client.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        await self.clock.advance(SPEC["loading_min_ms"])
        await self.clock.advance(SPEC["start_delay_ms"])
        signal = SPEC["commands"]["SIGNAL"]["type"]
        for client in (tamsin, edda):
            await client.send_message("CMD", seq=1, type=signal, a=100, b=200, c=0)
        await edda.send_message("CMD", seq=2, type=SPEC["commands"]["READY"]["type"], a=1, b=0, c=0)
        match = self.match()
        await until(lambda: len(match.sequencer.pending) == 2 and match.sequencer.last_seq[1] == 2)
        await self.clock.turns(1)
        self.assertEqual([(entry[0], entry[2]) for entry in sealed],
                         [(0, signal), (1, SPEC["commands"]["READY"]["type"])])


if __name__ == "__main__":
    unittest.main()
