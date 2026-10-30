"""What the state directory keeps and for how long (retention.py), the
players' log, a player's data forgotten, the moderators' CLI (admin.py)
and the backups (backup.py); docs/design/core-loop.md §6.12.

Adapted from Cyberworld Endless's server/tests/test_retention.py (MIT,
Sascha Becker), without the trades and the Board."""

import asyncio
import configparser
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest

from support import ROOT, HubTest
from groundhold_server import admin, backup
from groundhold_server.identity import read_json, write_json
from groundhold_server.retention import DAY, PlayersLog, Retention

NOW = 1792627200            # Thursday 22 October 2026, 00:00 UTC
ALPHA, BETA, GAMMA = "a" * 32, "b" * 32, "c" * 32


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


class RetentionTests(HubTest, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.temporary = tempfile.TemporaryDirectory(prefix="groundhold-retention-")
        self.dir = Path(self.temporary.name)

    async def asyncTearDown(self):
        await super().asyncTearDown()
        self.temporary.cleanup()

    async def start(self, **policy):
        return await super().start(state_dir=self.dir, identity_key=None, policy=Retention(**policy))

    def test_the_policy_is_read_from_the_ini_and_bounded(self):
        self.assertEqual(Retention(), Retention(log_days=0, backup_days=14, stats_days=365))
        config = configparser.ConfigParser()
        config.read_string("[server]\nlog_days = 7\nstats_days = 30\n")
        self.assertEqual(Retention.from_settings(config["server"]), Retention(log_days=7, stats_days=30))
        for wrong in ({"log_days": -1}, {"backup_days": 0}, {"log_days": 366}, {"stats_days": True}):
            with self.assertRaises(ValueError):
                Retention(**wrong)

    async def test_the_pass_runs_at_the_start_and_then_hourly(self):
        await self.start()
        write_json(self.dir / "moderation.json", {"bans": {}, "mutes": {},
                                                 "kicks": {ALPHA: {"time": 1, "reason": "", "expires": 2}}})
        await self.clock.advance(1000)
        await asyncio.gather(self.server.retention_task)
        self.assertEqual(read_json(self.dir / "moderation.json", {})["kicks"], {})
        write_json(self.dir / "moderation.json", {"bans": {}, "mutes": {},
                                                 "kicks": {ALPHA: {"time": 1, "reason": "", "expires": 2}}})
        await self.clock.advance(3599 * 1000)
        self.assertIn(ALPHA, read_json(self.dir / "moderation.json", {})["kicks"])
        await self.clock.advance(1000)
        await asyncio.gather(self.server.retention_task)
        self.assertEqual(read_json(self.dir / "moderation.json", {})["kicks"], {})

    async def test_ended_kicks_go_but_bans_and_mutes_stay(self):
        await self.start()
        now = time.time()
        write_json(self.dir / "moderation.json", {
            "bans": {ALPHA: {"time": 1, "reason": ""}}, "mutes": {BETA: {"time": 1, "reason": ""}},
            "kicks": {GAMMA: {"time": 1, "reason": "", "expires": now + 600}, BETA: {"time": 1, "reason": "", "expires": 5}}})
        self.assertEqual(await self.server.retain(), {"moderation": 1})
        rules = read_json(self.dir / "moderation.json", {})
        self.assertEqual({key: sorted(value) for key, value in rules.items()},
                         {"bans": [ALPHA], "mutes": [BETA], "kicks": [GAMMA]})
        # (a file that will not load is never written over)
        (self.dir / "moderation.json").write_text("{broken")
        self.assertEqual(await self.server.retain(), {})
        self.assertEqual((self.dir / "moderation.json").read_text(), "{broken")

    async def test_names_and_identities_go_to_the_players_log_alone_and_none_by_default(self):
        await self.start()
        await self.join("Alpha", 1)
        await asyncio.sleep(0.05)
        self.assertFalse((self.dir / "logs").exists())      # (log_days = 0: none written)
        await self.server.close()
        self.server = None
        await self.start(log_days=14)
        with self.assertLogs("groundhold.server", "INFO") as console:
            alpha = await self.join("Alpha", 1)
            await asyncio.sleep(0.05)
        identity = alpha.welcome["identity"].hex()
        self.assertTrue(any('"event":"join"' in line for line in console.output))
        self.assertFalse(any(identity in line or "Alpha" in line for line in console.output))
        today = PlayersLog.name(time.time())
        joined = lines(self.dir / "logs" / today)
        self.assertEqual((joined[0]["event"], joined[0]["identity"], joined[0]["name"]), ("join", identity, "Alpha"))
        logs = PlayersLog(self.dir, 14)
        for days in (13, 14, 30):
            (self.dir / "logs" / PlayersLog.name(time.time() - days * DAY)).write_text("{}\n")
        self.assertEqual(logs.prune(time.time()), 2)
        self.assertEqual([name for _, name in logs.files()], [PlayersLog.name(time.time() - 13 * DAY), today])
        self.assertEqual(PlayersLog(self.dir, 0).prune(time.time()), 2)

    async def test_forget_takes_a_player_out_of_every_record_but_a_ban(self):
        await self.start(log_days=14)
        alpha = (await self.join("Alpha", 1)).welcome["identity"].hex()
        beta = (await self.join("Beta", 2)).welcome["identity"].hex()
        await asyncio.sleep(0.05)
        await self.server.close()
        self.server = None
        admin.perform("kick", self.dir, alpha, minutes=60)
        admin.perform("ban", self.dir, alpha, "harassment")
        result = admin.perform("forget", self.dir, alpha)
        self.assertEqual((result["logs"], result["moderation"]), (1, 1))
        everything = "".join(path.read_text() for path in self.dir.rglob("*") if path.is_file() and path.suffix != ".key")
        self.assertEqual(everything.count(alpha), 1)       # (the ban alone)
        self.assertIn(alpha, read_json(self.dir / "moderation.json", {})["bans"])
        self.assertIn(beta, everything)


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="groundhold-admin-")
        self.dir = Path(self.temporary.name)
        (self.dir / "identity.key").write_bytes(bytes(range(32)))

    def tearDown(self):
        self.temporary.cleanup()

    def test_each_action_changes_the_moderation_lists(self):
        admin.perform("ban", self.dir, ALPHA.upper().lower(), "spam")
        admin.perform("mute", self.dir, BETA)
        kicked = admin.perform("kick", self.dir, GAMMA, minutes=30)
        self.assertAlmostEqual(kicked["expires"], time.time() + 1800, delta=5)
        listed = admin.perform("list", self.dir)["moderation"]
        self.assertEqual({key: sorted(value) for key, value in listed.items()},
                         {"bans": [ALPHA], "mutes": [BETA], "kicks": [GAMMA]})
        for action, identity in (("unban", ALPHA), ("unmute", BETA), ("unkick", GAMMA)):
            admin.perform(action, self.dir, identity)
        self.assertEqual(read_json(self.dir / "moderation.json", {}), {"bans": {}, "mutes": {}, "kicks": {}})

    def test_it_refuses_what_it_cannot_do(self):
        for args in (("ban", self.dir, "xyz"), ("kick", self.dir, ALPHA, "", 0), ("mute", self.dir, ALPHA, "", 5),
                     ("ban", self.dir, None), ("ban", self.dir, ALPHA, "line\nbreak"), ("hide", self.dir, ALPHA),
                     ("list", self.dir.parent / "nowhere")):
            with self.assertRaises(ValueError, msg=args):
                admin.perform(*args)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="groundhold-backup-")
        root = Path(self.temporary.name)
        self.state, self.backups = root / "state", root / "backups"
        self.state.mkdir()
        self.backups.mkdir()
        (self.state / "identity.key").write_bytes(bytes(range(32)))
        write_json(self.state / "moderation.json", {"bans": {ALPHA: {"time": 1, "reason": ""}}})
        (self.state / "players.json").write_text("{}")
        (self.state / "stats.jsonl").write_text("{}\n")

    def tearDown(self):
        self.temporary.cleanup()

    def files(self):
        return {name: (self.state / name).read_bytes() for name in backup.FILES if (self.state / name).exists()}

    def test_an_archive_holds_the_key_and_the_moderation_alone(self):
        path = backup.archive(self.state, self.backups, NOW)
        self.assertEqual(path.name, "groundhold-state-20261022-000000.tar.gz")
        with tarfile.open(path) as tar:
            self.assertEqual(sorted(tar.getnames()), sorted(backup.FILES))
        self.assertEqual(backup.read(path), self.files())
        (self.state / "identity.key").unlink()
        with self.assertRaises(ValueError):
            backup.archive(self.state, self.backups, NOW)

    def test_one_archive_a_day_kept_its_days(self):
        slept = []

        class clock:
            now = NOW + 1800

        def sleep(seconds):
            slept.append(seconds)
            clock.now += seconds
            if len(slept) == 24 * 20:
                raise StopIteration
        with self.assertRaises(StopIteration):
            backup.run(self.state, self.backups, 14, clock=lambda: clock.now, sleep=sleep)
        names = sorted(p.name for p in self.backups.iterdir())
        self.assertEqual(len(names), 14)
        self.assertEqual((names[0], names[-1]), ("groundhold-state-20261028-003000.tar.gz",
                                                 "groundhold-state-20261110-003000.tar.gz"))
        self.assertEqual(set(slept), {backup.LOOK})

    def test_a_failed_backup_is_tried_again_a_minute_later(self):
        (self.state / "identity.key").unlink()
        waits = []

        def sleep(seconds):
            waits.append(seconds)
            if len(waits) == 1:
                (self.state / "identity.key").write_bytes(bytes(range(32)))
            else:
                raise StopIteration
        with self.assertLogs("groundhold.server", "ERROR"), self.assertRaises(StopIteration):
            backup.run(self.state, self.backups, 14, clock=lambda: NOW, sleep=sleep)
        self.assertEqual(waits, [backup.RETRY, backup.LOOK])

    def test_a_restore_puts_the_state_back_as_it_was(self):
        before = self.files()
        path = backup.archive(self.state, self.backups, NOW)
        (self.state / "identity.key").write_bytes(b"x" * 32)
        write_json(self.state / "moderation.json", {})
        self.assertEqual(backup.restore(path, self.state), sorted(backup.FILES))
        self.assertEqual(self.files(), before)
        if os.name != "nt":
            self.assertEqual((self.state / "identity.key").stat().st_mode & 0o777, 0o600)
        (self.state / "moderation.json").unlink()
        sparse = backup.archive(self.state, self.backups, NOW + 60)
        backup.restore(path, self.state)
        backup.restore(sparse, self.state)
        self.assertFalse((self.state / "moderation.json").exists())

    def test_a_restore_refuses_what_is_not_a_backup(self):
        def made(members):
            path = self.backups / "made.tar.gz"
            with tarfile.open(path, "w:gz") as tar:
                for info, content in members:
                    tar.addfile(info, io.BytesIO(content) if content is not None else None)
            return path

        def member(name, content=b"", kind=tarfile.REGTYPE):
            info = tarfile.TarInfo(name)
            info.type, info.size = kind, len(content or b"")
            return info, content
        key = bytes(range(32))
        link = member("moderation.json", None, tarfile.SYMTYPE)
        link[0].linkname = "/etc/passwd"
        for members in ([member("moderation.json", b"{}")], [member("identity.key", b"short")],
                        [member("identity.key", key), link],
                        [member("identity.key", key), member("identity.key", key)]):
            with self.assertRaises(ValueError):
                backup.restore(made(members), self.state)
        (self.backups / "plain.tar.gz").write_bytes(b"not an archive")
        with self.assertRaises(ValueError):
            backup.restore(self.backups / "plain.tar.gz", self.state)
        backup.restore(made([member("./identity.key", key), member("../escape", b"x"), member("logs/a", b"x")]),
                       self.state)
        self.assertFalse((self.state.parent / "escape").exists())
        self.assertFalse((self.state / "logs").exists())


class ProgramTests(unittest.TestCase):
    """The real program: a hub server keeping its state, --admin, --backup and --restore."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="groundhold-program-")
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"

    def tearDown(self):
        self.temporary.cleanup()

    def program(self, *args, **options):
        return subprocess.run([sys.executable, str(ROOT / "server" / "main.py"), *args], cwd=self.root,
                              capture_output=True, text=True, timeout=30, **options)

    def test_a_hub_server_keeps_its_key_and_its_tools_work_on_it(self):
        process = subprocess.Popen([sys.executable, str(ROOT / "server" / "main.py"), "--host", "127.0.0.1",
                                    "--port", "0", "--state-dir", str(self.state)],
                                   cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                   env=dict(os.environ, PYTHONUNBUFFERED="1"))
        try:
            port = int(process.stdout.readline().split()[1].split("=")[1])
            banner = "".join(process.stdout.readline() for _ in range(6))
            self.assertIn("State: " + str(self.state), banner)
            self.assertNotIn("beacon", banner)          # (127.0.0.1: nobody else could come)
            identity = asyncio.run(self.visit(port))
        finally:
            process.terminate()
            process.wait(timeout=10)
            process.stdout.close()
        self.assertEqual(process.returncode, 0)
        self.assertEqual(len((self.state / "identity.key").read_bytes()), 32)
        self.assertEqual(json.loads((self.state / "players.json").read_text())["players"], [])
        self.assertEqual(json.loads((self.state / "stats.jsonl").read_text().splitlines()[0])["joins"], 1)
        banned = self.program("--state-dir", str(self.state), "--admin", "ban", "--identity", identity,
                              "--reason", "test")
        self.assertEqual(banned.returncode, 0, banned.stderr)
        self.assertEqual(json.loads(banned.stdout)["action"], "ban")
        listed = json.loads(self.program("--state-dir", str(self.state), "--admin", "list").stdout)
        self.assertIn(identity, listed["moderation"]["bans"])
        made = self.program("--state-dir", str(self.state), "--backup", str(self.root), "--once")
        archive = json.loads(made.stdout)["archive"]
        self.assertRegex(Path(archive).name, r"^groundhold-state-\d{8}-\d{6}\.tar\.gz$")
        (self.state / "moderation.json").unlink()
        restored = self.program("--state-dir", str(self.state), "--restore", archive)
        self.assertEqual(json.loads(restored.stdout)["restored"], ["identity.key", "moderation.json"])
        self.assertIn(identity, read_json(self.state / "moderation.json", {})["bans"])
        self.assertNotEqual(self.program("--state-dir", str(self.state), "--admin", "ban", "--identity", "x").returncode, 0)

    async def visit(self, port):
        from support import Client, party
        client = Client()
        _, welcome = await client.hello(port, "Tamsin", token=b"\x01" * 16)
        await party(client, "create", mode=0)
        created = await client.until("PARTY_STATE")
        self.assertEqual(len(created["code"]), 5)
        await client.bye()
        return welcome["identity"].hex()

    def test_the_banner_says_the_beacon_is_on(self):
        from groundhold_server import hosting
        lines = hosting.banner("Flats", None, 8766, False, ["192.168.1.20"], beacon=True, state_dir="server-data")
        self.assertIn("The LAN beacon is on: games on this network list it under Nearby (UDP port 8767).", lines)
        self.assertIn("State: server-data (the identity key and moderation: keep it, never publish it).", lines)
        self.assertFalse(any("beacon" in line for line in hosting.banner("Flats", None, 8766, False, [])))


if __name__ == "__main__":
    unittest.main()
