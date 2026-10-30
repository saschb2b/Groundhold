"""The LAN beacon (docs/design/core-loop.md §6.2, §7.3 test_beacon): the
datagram's layout, a mismatched version not listed, no beacon where it
would say nothing true (a container, this computer alone, TLS), and a real
server broadcasting once a second of its clock with its open parties."""

import asyncio
import socket
import struct
import unittest

from support import MODES, HubTest, party, state
from groundhold_server import beacon
from groundhold_server.protocol import SPEC


class DatagramTests(unittest.TestCase):
    def test_the_layout(self):
        data = beacon.datagram(8766, 2, "Sascha's server")
        self.assertEqual(data, b"GHB1" + struct.pack("!HHB", SPEC["version"], 8766, 2) + bytes((15,)) + b"Sascha's server")
        self.assertEqual(beacon.parse(data), {"version": 1, "port": 8766, "open": 2, "name": "Sascha's server"})
        self.assertEqual(SPEC["beacon_port"], 8767)
        # (bounded: at most 255 open parties, a name of at most 64 bytes, UTF-8 kept whole)
        long = beacon.datagram(8766, 900, "Wöhrden " * 20)
        parsed = beacon.parse(long)
        self.assertEqual(parsed["open"], 255)
        self.assertLessEqual(len(parsed["name"].encode()), SPEC["server_name_bytes"])
        self.assertTrue(parsed["name"].startswith("Wöhrden"))

    def test_only_a_well_formed_datagram_of_this_version_is_listed(self):
        good = beacon.datagram(9000, 0, "Flats")
        self.assertEqual(beacon.listed(good)["port"], 9000)
        other = beacon.datagram(9000, 0, "Flats", version=SPEC["version"] + 1)
        self.assertIsNotNone(beacon.parse(other))
        self.assertIsNone(beacon.listed(other))
        for wrong in (good[:-1], good + b"x", b"GHB2" + good[4:], good[:9], b"",
                      beacon.datagram(0, 0, "Flats"), good[:10] + bytes((2,)) + b"\xff\xfe"):
            self.assertIsNone(beacon.parse(wrong), wrong)

    def test_no_beacon_where_it_would_say_nothing_true(self):
        self.assertTrue(beacon.wanted(None, secure=False, contained=False))
        self.assertTrue(beacon.wanted("0.0.0.0", secure=False, contained=False))
        self.assertTrue(beacon.wanted("192.168.1.20", secure=False, contained=False))
        self.assertFalse(beacon.wanted(None, secure=False, contained=True))       # (in a container)
        self.assertFalse(beacon.wanted("127.0.0.1", secure=False, contained=False))
        self.assertFalse(beacon.wanted("localhost", secure=False, contained=False))
        self.assertFalse(beacon.wanted("::1", secure=False, contained=False))
        self.assertFalse(beacon.wanted(None, secure=True, contained=False))       # (an internet server, TLS)
        self.assertFalse(beacon.wanted(None, secure=False, contained=False, setting=False))


class Listener(asyncio.DatagramProtocol):
    def __init__(self):
        self.heard = asyncio.Queue()

    def datagram_received(self, data, address):
        self.heard.put_nowait(data)


class BroadcastTests(HubTest, unittest.IsolatedAsyncioTestCase):
    async def test_a_server_says_it_is_there_once_a_second_of_its_clock(self):
        loop = asyncio.get_running_loop()
        transport, listener = await loop.create_datagram_endpoint(Listener, local_addr=("127.0.0.1", 0),
                                                                  family=socket.AF_INET)
        try:
            target = transport.get_extra_info("sockname")
            await self.start(beacon=target, name="Sascha's server")
            first = beacon.listed(await asyncio.wait_for(listener.heard.get(), 2))
            self.assertEqual(first, {"version": SPEC["version"], "port": self.port, "open": 0, "name": "Sascha's server"})
            await asyncio.sleep(0.05)
            self.assertTrue(listener.heard.empty())     # (the clock stands: no second beat)
            tamsin = await self.join("Tamsin", 1)
            await party(tamsin, "create", mode=MODES["high_water"])
            await state(tamsin)
            await party(tamsin, "open", on=1)
            await state(tamsin)
            await self.clock.advance(999)
            await asyncio.sleep(0.05)
            self.assertTrue(listener.heard.empty())
            await self.clock.advance(1)
            self.assertEqual(beacon.listed(await asyncio.wait_for(listener.heard.get(), 2))["open"], 1)
            # (a late clock sends once, not a burst)
            await self.clock.advance(5000)
            await asyncio.wait_for(listener.heard.get(), 2)
            await asyncio.sleep(0.05)
            self.assertTrue(listener.heard.empty())
            self.assertEqual(self.server.beacon.sent, 3)
        finally:
            transport.close()

    async def test_no_beacon_unless_asked(self):
        await self.start()
        self.assertIsNone(self.server.beacon)


if __name__ == "__main__":
    unittest.main()
