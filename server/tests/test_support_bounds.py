"""The harness's own bounds (support.py). The machine ran out of memory once: a
test run against the code before its change, to see it fail, waited in a loop
for a catch-up that never came and grew a list to 25 GB. So the test process
may use at most GROUNDHOLD_TEST_MEMORY_GB (4 GB), and every helper that reads
until a message comes reads at most MOST_MESSAGES and then fails: a server that
keeps sending everything but what a test waits for fails the test, it never
spins (or grows a transcript's record) for ever."""

import asyncio
import os
import resource
import unittest
from unittest import mock

import support
from support import Client, drain, sync
from groundhold_server import protocol, websocket

LINKS = protocol.encode("LINKS", seats=[dict(seat=0, rtt_ms=40, flags=0)])
BOUND = 50          # (MOST_MESSAGES for these tests: the stream below is twice as long)


class Writer:
    """Where a game's own messages go: nowhere."""

    def write(self, data):
        pass

    async def drain(self):
        pass


def stream(count, message=LINKS):
    """A game whose server has sent `count` of `message`, then nothing."""
    client = Client()
    client.reader, client.writer = asyncio.StreamReader(), Writer()
    client.reader.feed_data(websocket.frame(message) * count)
    return client


class BoundTests(unittest.IsolatedAsyncioTestCase):
    def test_the_test_process_may_use_at_most_its_memory_cap(self):
        cap = int(float(os.environ.get("GROUNDHOLD_TEST_MEMORY_GB", "4")) * 1024 ** 3)
        soft, _ = resource.getrlimit(resource.RLIMIT_AS)
        self.assertNotEqual(soft, resource.RLIM_INFINITY)
        self.assertLessEqual(soft, cap)

    async def test_until_fails_after_its_bound_of_skipped_messages(self):
        client = stream(2 * BOUND)
        with mock.patch.object(support, "MOST_MESSAGES", BOUND, create=True):
            with self.assertRaisesRegex(AssertionError, f"no TURN among {BOUND} messages"):
                await client.until("TURN", timeout=0.2, skip=("LINKS",))
        # (it stopped there: the rest are still unread)
        self.assertEqual(len(await drain(client, 0.01)), BOUND)

    async def test_drain_fails_when_the_server_never_falls_silent(self):
        client = stream(2 * BOUND)
        with mock.patch.object(support, "MOST_MESSAGES", BOUND, create=True):
            with self.assertRaisesRegex(AssertionError, f"still sending after {BOUND} messages"):
                await drain(client, 0.01)

    async def test_sync_fails_after_its_bound_without_a_pong(self):
        client = stream(2 * BOUND)
        with mock.patch.object(support, "MOST_MESSAGES", BOUND, create=True):
            with self.assertRaisesRegex(AssertionError, f"no PONG among {BOUND} messages"):
                await sync(client)

    async def test_within_the_bound_the_helpers_read_as_before(self):
        client = stream(BOUND - 2)
        client.reader.feed_data(websocket.frame(protocol.encode("PONG", client_ms=1, turn=0)))
        with mock.patch.object(support, "MOST_MESSAGES", BOUND, create=True):
            self.assertEqual(len(await sync(client)), BOUND - 2)
            client.reader.feed_data(websocket.frame(LINKS) * (BOUND - 1))
            self.assertEqual(len(await drain(client, 0.01)), BOUND - 1)
            client.reader.feed_data(websocket.frame(LINKS) * (BOUND - 1)
                                    + websocket.frame(protocol.encode("PONG", client_ms=2, turn=0)))
            self.assertEqual((await client.until("PONG", skip=("LINKS",)))["client_ms"], 2)


if __name__ == "__main__":
    unittest.main()
