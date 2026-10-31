"""tools/net/shaper.py against an echo server on localhost: its delay, a stall and a cut.

    python3 -m unittest tools/net/test_shaper.py

Every wait has an end (asyncio.wait_for); nothing runs past a few seconds.
"""

import asyncio
import pathlib
import sys
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import shaper  # noqa: E402

LIMIT = 5.0  # seconds any one wait may take before the test fails


async def echo(reader, writer):
    try:
        while data := await reader.read(4096):
            writer.write(data)
            await writer.drain()
    except ConnectionError:
        pass
    finally:
        writer.close()


class ShaperTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.echo = await asyncio.start_server(echo, "127.0.0.1", 0)
        self.echo_port = self.echo.sockets[0].getsockname()[1]
        self.shapers = []

    async def asyncTearDown(self):
        for s in self.shapers:
            s.close()
        self.echo.close()
        await asyncio.wait_for(self.echo.wait_closed(), LIMIT)

    async def shaper(self, *flags):
        args = shaper.parser().parse_args(["--to", f"127.0.0.1:{self.echo_port}", *flags])
        s = shaper.Shaper(args)
        self.shapers.append(s)
        return s, await s.start()

    async def round_trip(self, reader, writer, data=b"turn"):
        began = time.monotonic()
        writer.write(data)
        await writer.drain()
        got = await asyncio.wait_for(reader.readexactly(len(data)), LIMIT)
        return got, time.monotonic() - began

    async def test_delays_each_way_in_order(self):
        s, port = await self.shaper("--delay-ms", "100", "--jitter-ms", "40", "--seed", "3")
        reader, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), LIMIT)
        got, took = await self.round_trip(reader, writer)
        self.assertEqual(got, b"turn")
        self.assertGreaterEqual(took, 0.12)   # (60 to 140 ms each way)
        # a burst comes back whole and in order, however the jitter falls
        burst = b"".join(b"%04d" % i for i in range(200))
        for i in range(200):
            writer.write(b"%04d" % i)
        await writer.drain()
        back = await asyncio.wait_for(reader.readexactly(len(burst)), LIMIT)
        self.assertEqual(back, burst)
        writer.close()

    async def test_a_stall_holds_both_ways_then_lets_go(self):
        s, port = await self.shaper("--delay-ms", "0", "--jitter-ms", "0", "--stall-at", "0.3", "--stall-ms", "600")
        reader, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), LIMIT)
        _, quick = await self.round_trip(reader, writer)
        self.assertLess(quick, 0.25)
        await asyncio.sleep(0.4 - (time.monotonic() - s.started))
        got, took = await self.round_trip(reader, writer, b"held")
        self.assertEqual(got, b"held")
        self.assertGreaterEqual(time.monotonic() - s.started, 0.85)   # (not before the stall's end at 0.9 s)
        self.assertGreaterEqual(took, 0.4)
        self.assertEqual(s.stats["stalls"], 1)
        _, after = await self.round_trip(reader, writer)
        self.assertLess(after, 0.25)
        writer.close()

    async def test_a_cut_drops_the_link_and_refuses_for_a_while(self):
        s, port = await self.shaper("--delay-ms", "0", "--jitter-ms", "0", "--cut-at", "0.3", "--cut-ms", "500")
        reader, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), LIMIT)
        await self.round_trip(reader, writer)
        # the cut: the link closes at 0.3 s
        closed = await asyncio.wait_for(reader.read(), LIMIT)
        self.assertEqual(closed, b"")
        self.assertGreaterEqual(time.monotonic() - s.started, 0.25)
        writer.close()
        # refused while the cut lasts: the connection closes at once
        reader2, writer2 = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), LIMIT)
        self.assertEqual(await asyncio.wait_for(reader2.read(), LIMIT), b"")
        writer2.close()
        self.assertGreaterEqual(s.stats["refused"], 1)
        # after it, a new link passes again (a resume HELLO would get its seat back)
        await asyncio.sleep(max(0.0, 0.85 - (time.monotonic() - s.started)))
        reader3, writer3 = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), LIMIT)
        got, _ = await self.round_trip(reader3, writer3, b"back")
        self.assertEqual(got, b"back")
        self.assertEqual(s.stats["cuts"], 1)
        writer3.close()


if __name__ == "__main__":
    unittest.main()
