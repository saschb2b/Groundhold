"""Party codes (docs/design/core-loop.md §5.3, §7.3 test_party_codes): the
alphabet, lenient input, rate-limited lookups, expiry 15 minutes after the
party empties."""

import random
import unittest

from support import MODES, NOTICES, HubTest, party, state
from groundhold_server import codes


class CodeTests(unittest.TestCase):
    def test_ten_thousand_codes_keep_to_the_alphabet(self):
        rng = random.Random(1)
        made = set()
        for _ in range(10_000):
            code = codes.generate(made, rng)
            self.assertEqual(len(code), 5)
            self.assertNotIn(code, made)
            made.add(code)
        symbols = set(b"".join(made).decode())
        self.assertEqual(symbols, set(codes.ALPHABET))
        self.assertFalse(symbols & set("01OILUAE"))
        self.assertEqual(len(codes.ALPHABET), 28)
        # (the system's source by default: two servers never share a sequence)
        self.assertNotEqual(codes.generate(), codes.generate())

    def test_input_is_lenient(self):
        for typed in ("k7q-4m", "K7Q-4M", "K7Q4M", " k7q 4m ", b"k7q4m", "k-7-q-4-m", "K7Q\t4M"):
            self.assertEqual(codes.parse(typed), b"K7Q4M", typed)
        for wrong in ("K7Q4", "K7Q4MM", "K0Q4M", "KOQ4M", "K1Q4M", "KAQ4M", "KÜQ4M", b"\xff7Q4M", "", None, 5):
            self.assertIsNone(codes.parse(wrong), wrong)
        self.assertEqual(codes.shown(b"K7Q4M"), "K7Q-4M")


class LookupTests(HubTest, unittest.IsolatedAsyncioTestCase):
    async def create(self):
        tamsin = await self.join("Tamsin", 1)
        await party(tamsin, "create", mode=MODES["high_water"])
        return tamsin, (await state(tamsin))["code"]

    async def test_a_lower_case_code_joins(self):
        await self.start()
        tamsin, code = await self.create()
        edda = await self.join("Edda", 2)
        await party(edda, "join", code=code.lower())
        self.assertEqual([m["name"] for m in (await state(edda))["members"]], ["Tamsin", "Edda"])

    async def test_an_unknown_or_malformed_code_is_no_such_party(self):
        await self.start()
        await self.create()
        edda = await self.join("Edda", 2)
        for wrong in (b"ZZZZZ", b"K0Q4M", b"\x00\x00\x00\x00\x00"):
            await party(edda, "join", code=wrong)
            self.assertEqual(await edda.until("NOTICE"), dict(code=NOTICES["no_such_party"], argument=0))

    async def test_lookups_are_rate_limited_per_connection(self):
        await self.start()
        tamsin, code = await self.create()
        edda, sefa = await self.join("Edda", 2), await self.join("Sefa", 3)
        for _ in range(5):
            await party(edda, "join", code=b"ZZZZZ")
            self.assertEqual((await edda.until("NOTICE"))["argument"], 0)
        # (the sixth at once: no lookup at all, the right code included; the
        # argument says how many seconds until the next)
        await party(edda, "join", code=code)
        self.assertEqual(await edda.until("NOTICE"), dict(code=NOTICES["no_such_party"], argument=5))
        # (another connection has its own lookups)
        await party(sefa, "join", code=code)
        await state(sefa)
        await self.clock.advance(4999)
        await party(edda, "join", code=code)
        self.assertEqual((await edda.until("NOTICE"))["argument"], 1)
        await self.clock.advance(5000)
        await party(edda, "join", code=code)
        self.assertEqual(len((await state(edda))["members"]), 3)

    async def test_an_empty_partys_code_expires_after_fifteen_minutes(self):
        await self.start()
        tamsin, code = await self.create()
        await party(tamsin, "leave")
        await state(tamsin)
        await self.clock.advance(15 * 60 * 1000 - 1)
        # (still there a moment before: a join brings it back, and its expiry is off)
        await party(tamsin, "join", code=code)
        back = await state(tamsin)
        self.assertEqual((back["code"], back["leader"]), (code, 0))
        await self.clock.advance(60 * 60 * 1000)
        self.assertIn(code, self.server.lobby.parties)
        await party(tamsin, "leave")
        await state(tamsin)
        await self.clock.advance(15 * 60 * 1000)
        self.assertNotIn(code, self.server.lobby.parties)
        await party(tamsin, "join", code=code)
        self.assertEqual(await tamsin.until("NOTICE"), dict(code=NOTICES["no_such_party"], argument=0))

    async def test_codes_on_one_server_differ(self):
        await self.start(code_rng=random.Random(5))
        seen = set()
        for number in range(1, 9):
            client = await self.join(f"P{number}", number)
            await party(client, "create", mode=MODES["classic"])
            seen.add((await state(client))["code"])
        self.assertEqual(len(seen), 8)


if __name__ == "__main__":
    unittest.main()
