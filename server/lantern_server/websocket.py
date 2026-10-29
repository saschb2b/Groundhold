"""The RFC 6455 subset Lantern Hollow speaks: binary, unfragmented, masked,
at most protocol.json's max_message from a game.

Reused from Cyberworld Endless's server/cyberworld_server/websocket.py (MIT,
Sascha Becker) with the renames of docs/design/core-loop.md §6.10: the path
/hollow, the subprotocol lantern-hollow.vN, max_message 1,100.
"""

import asyncio
import base64
import hashlib
import struct
import json
import re

from .protocol import ProtocolError, SPEC

OTHER_VERSION = re.compile(SPEC["subprotocol_pattern"])
REQUEST_LINE = "GET " + SPEC["path"] + " HTTP/1.1"

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def page(writer, value):
    body = json.dumps(value, separators=(",", ":")).encode()
    writer.write(("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nCache-Control: no-store\r\n"
                  "Connection: close\r\nContent-Length: " + str(len(body)) + "\r\n\r\n").encode() + body)


async def upgrade(reader, writer, origins, health=None, subprotocols=None, stats=None):
    """The WebSocket's handshake, or GET /health's JSON (`health`) and
    GET /stats's (`stats()`), then False."""
    try:
        request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
        lines = request.decode("ascii").split("\r\n")
        headers = {}
        for line in lines[1:-2]:
            key, value = line.split(":", 1)
            key = key.lower()
            if key in headers:
                raise ValueError("Duplicate header")
            headers[key] = value.strip()
        served = health if lines[0] == "GET /health HTTP/1.1" else \
            stats() if lines[0] == "GET /stats HTTP/1.1" and stats is not None else None
        if served is not None:
            page(writer, served)
            await asyncio.wait_for(writer.drain(), 2)
            return False
        key = headers.get("sec-websocket-key", "")
        valid_key = len(base64.b64decode(key, validate=True)) == 16
    except (ValueError, UnicodeError, asyncio.LimitOverrunError) as exc:
        raise ProtocolError("Invalid WebSocket request") from exc
    if len(request) > 8192 or lines[0] != REQUEST_LINE:
        raise ProtocolError("Use " + SPEC["path"])
    offered = [part.strip() for part in headers.get("sec-websocket-protocol", "").split(",")]
    selected = next((name for name in (subprotocols or (SPEC["subprotocol"],)) if name in offered), None)
    # (a game of another protocol version is let in to say its HELLO, whose
    # version the server answers with the ERROR that says which side is
    # behind: refused here, it could only say "no answer")
    if not selected and not subprotocols:
        selected = next((name for name in offered if OTHER_VERSION.fullmatch(name)), None)
    if (not valid_key or headers.get("upgrade", "").lower() != "websocket"
            or "upgrade" not in [part.strip() for part in headers.get("connection", "").lower().split(",")]
            or headers.get("sec-websocket-version") != "13"
            or not selected
            or not headers.get("host")):
        raise ProtocolError("WebSocket version or subprotocol mismatch")
    # (only where an Origin is sent: native games send none; a browser's page
    # must be on the allowlist. Not player authentication.)
    if "origin" in headers and headers["origin"] not in origins:
        raise ProtocolError("Origin is not allowed")
    accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
    writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                  "Connection: Upgrade\r\nSec-WebSocket-Accept: " + accept +
                  "\r\nSec-WebSocket-Protocol: " + selected + "\r\n\r\n").encode())
    await asyncio.wait_for(writer.drain(), 2)
    return selected


def frame(data, opcode=2):
    """A server frame (never masked). A TURN of many commands or a party's
    state can pass 125 bytes; nothing the server sends passes 65,535."""
    if len(data) < 126:
        prefix = bytes((0x80 | opcode, len(data)))
    elif len(data) <= 0xffff:
        prefix = struct.pack("!BBH", 0x80 | opcode, 126, len(data))
    else:
        raise ValueError("Server message too large")
    return prefix + data


async def header(reader):
    """A game's frame header, checked: (opcode, payload length, mask)."""
    first, second = await reader.readexactly(2)
    opcode = first & 15
    length = second & 127
    if first & 0x70 or not first & 0x80 or not second & 0x80 or opcode not in (2, 8, 9, 10):
        raise ProtocolError("Only masked, unfragmented binary WebSocket frames")
    if length == 127 or (opcode >= 8 and length > 125):
        raise ProtocolError("WebSocket frame too large")
    if length == 126:
        length = struct.unpack("!H", await reader.readexactly(2))[0]
        if length < 126:
            raise ProtocolError("Noncanonical WebSocket length")
    if length > SPEC["max_message"]:
        raise ProtocolError("WebSocket frame too large")
    if opcode == 8 and length == 1:
        raise ProtocolError("Malformed close frame")
    return opcode, length, await reader.readexactly(4)


async def receive(reader):
    opcode, length, mask = await header(reader)
    payload = await reader.readexactly(length)
    return opcode, bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))


async def discard(reader):
    """A game's next frame read and dropped unmasked (a refused connection's
    leftovers): its opcode."""
    opcode, length, _ = await header(reader)
    await reader.readexactly(length)
    return opcode


async def send(writer, data, opcode=2):
    writer.write(frame(data, opcode))
    # (a timeout's context, not wait_for: Python 3.11's wait_for can swallow
    # a cancellation that lands as the drain finishes, so a shutdown would
    # wait on a player whose welcome was still being sent)
    async with asyncio.timeout(2):
        await writer.drain()
