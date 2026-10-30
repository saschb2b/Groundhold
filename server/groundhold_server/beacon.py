"""The LAN beacon (docs/design/core-loop.md §6.2): a server on a home
network says it is there, so desktop games list it under Nearby in the
Join panel without anyone typing an address.

Once a second, the server broadcasts one small UDP datagram to
255.255.255.255 on protocol.json's `beacon_port` (8767), all big-endian:

| Bytes | Field |
|---|---|
| 4 | `GHB1` |
| 2 | protocol version |
| 2 | the WebSocket port |
| 1 | open parties: parties with open seats on and a seat free (at most 255) |
| 1 + n | the server's name (u8 length, UTF-8, at most 64 bytes) |

A game keys servers by the datagram's source address and the port, lists
only those whose version is its own (`listed`), and drops one silent for
3 s. Nothing in it names a player.

No beacon where it would say nothing true: in a container (its broadcast
stays on the container's network, and its address is not the host's),
on a server that listens on this computer alone (127.0.0.1), behind TLS (an
internet server, reached by its domain), or with `beacon = false`.

New in Groundhold; nothing in Cyberworld broadcasts.
"""

import asyncio
import contextlib
import ipaddress
import logging
import socket
import struct

from .protocol import SPEC

MAGIC = b"GHB1"
HEAD = struct.Struct("!4sHHB")
INTERVAL_MS = 1000
SILENT_MS = 3000            # a game drops a server it has not heard this long
BROADCAST = "255.255.255.255"
MS = 1_000_000
LOG = logging.getLogger("groundhold.server")


def datagram(port, open_parties, name, version=SPEC["version"]):
    """The beacon's datagram."""
    encoded = name.encode("utf-8")[:SPEC["server_name_bytes"]].decode("utf-8", "ignore").encode("utf-8")
    return HEAD.pack(MAGIC, version, port, max(0, min(255, open_parties))) + bytes((len(encoded),)) + encoded


def parse(data):
    """A datagram read back as {"version", "port", "open", "name"}, or None
    where it is not a beacon's: the magic, the exact length, a port, UTF-8."""
    if len(data) < HEAD.size + 1:
        return None
    magic, version, port, open_parties = HEAD.unpack_from(data)
    length = data[HEAD.size]
    if magic != MAGIC or len(data) != HEAD.size + 1 + length or length > SPEC["server_name_bytes"] or not port:
        return None
    try:
        name = bytes(data[HEAD.size + 1:]).decode("utf-8")
    except UnicodeDecodeError:
        return None
    return {"version": version, "port": port, "open": open_parties, "name": name}


def listed(data, version=SPEC["version"]):
    """What Nearby lists for a datagram: the beacon, or None where it is
    none or speaks another protocol version (a game cannot play there)."""
    beacon = parse(data)
    return beacon if beacon and beacon["version"] == version else None


def wanted(host, secure, contained, setting=True):
    """Whether a server listening on `host` should broadcast."""
    if not setting or secure or contained:
        return False
    if host in (None, "", "0.0.0.0", "::"):
        return True
    if host == "localhost":
        return False
    try:
        return not ipaddress.ip_address(host).is_loopback
    except ValueError:
        return True


class Beacon:
    """The datagram once every INTERVAL_MS of the server's clock, the first
    at once; what it says is read from the server each time."""

    def __init__(self, server, port, target=None):
        self.server, self.port = server, port
        self.target = target or (BROADCAST, SPEC["beacon_port"])
        self.transport = None
        self.task = None
        self.sent = 0
        self.failing = False

    async def start(self):
        loop = asyncio.get_running_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            asyncio.DatagramProtocol, family=socket.AF_INET, allow_broadcast=True, local_addr=("0.0.0.0", 0))
        self.task = asyncio.create_task(self.run(self.server.clock.now()))
        self.server.event("beacon", port=self.target[1])

    async def run(self, origin):
        clock = self.server.clock
        beat = 0
        while True:
            await clock.sleep_until(origin + beat * INTERVAL_MS * MS)
            # (a late wake sends once, not a burst: the next beat after now)
            beat = max(beat, (clock.now() - origin) // (INTERVAL_MS * MS)) + 1
            data = datagram(self.port, self.server.lobby.open_parties(), self.server.name)
            try:
                self.transport.sendto(data, self.target)
                self.sent += 1
                self.failing = False
            except OSError as exc:
                # (a computer with no network now: said once, tried again each second)
                if not self.failing:
                    LOG.warning("The LAN beacon could not be sent: %s", exc)
                self.failing = True

    async def close(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        if self.transport:
            self.transport.close()
