"""Where the server listens: `--port 0` on every interface (no --host) is one
port for every address family, the one it prints, so the banner's LAN
address answers on IPv4 as well as IPv6 (review M5 round 2: the system
picked a port per family, and the printed one was IPv6's alone)."""

import asyncio
import contextlib
import socket
import unittest

from support import hub


def has_ipv6_loopback():
    if not socket.has_ipv6:
        return False
    with contextlib.suppress(OSError), socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as probe:
        probe.bind(("::1", 0))
        return True
    return False


class ListenTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        if getattr(self, "server", None):
            await self.server.close()

    async def connects(self, address, port):
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(address, port), 2)
        except OSError:
            return False
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
        return True

    async def test_port_zero_on_every_interface_is_one_port(self):
        self.server = hub()
        port = await self.server.start(None, 0)
        ports = {sock.getsockname()[1] for sock in self.server.listener.sockets}
        self.assertEqual(ports, {port}, "every family listens on the port the server prints")
        self.assertTrue(await self.connects("127.0.0.1", port), "IPv4 answers on the printed port")
        if has_ipv6_loopback() and any(sock.family == socket.AF_INET6 for sock in self.server.listener.sockets):
            self.assertTrue(await self.connects("::1", port), "IPv6 answers on the printed port")

    async def test_a_named_port_and_host_are_kept(self):
        self.server = hub()
        port = await self.server.start("127.0.0.1", 0)
        self.assertEqual([sock.getsockname() for sock in self.server.listener.sockets], [("127.0.0.1", port)])


if __name__ == "__main__":
    unittest.main()
