"""Groundhold's wire messages: big-endian records with a one-byte type.

The layouts live in shared/net/protocol.json, the one contract the game's
GDScript codec reads too (docs/design/core-loop.md §6.5); this module builds
its encoder and decoder from them. Every reader checks the exact length and
bounds every field, and a bad message raises ProtocolError(reason, code).

Adapted from Cyberworld Endless's server/cyberworld_server/protocol.py
(MIT, Sascha Becker): the spec loaded from JSON as package data,
`ProtocolError`, `hello_version()` read before anything else, the name rule
and the maintenance line are its; the message set is Groundhold's.
"""

import hashlib
import json
import re
import struct
from importlib.resources import files
from pathlib import Path


def _load_spec():
    # (the zipapp carries protocol.json beside this module: build.py; a
    # checkout reads it from shared/net/)
    try:
        return json.loads(files(__package__).joinpath("protocol.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, NotADirectoryError):
        return json.loads((Path(__file__).resolve().parents[2] / "shared/net/protocol.json").read_text(encoding="utf-8"))


SPEC = _load_spec()
ERRORS = SPEC["errors"]
NOTICES = SPEC["notices"]
OUTCOMES = SPEC["outcomes"]
END_REASONS = SPEC["end_reasons"]
LOAD_STATES = SPEC["load_states"]
VISIBILITY = SPEC["visibility_states"]
RESYNC_REASONS = SPEC["resync_reasons"]
SYSTEM_SEAT = SPEC["system_seat"]
NAME = re.compile(SPEC["name_pattern"])
SCALARS = {"u8": struct.Struct("!B"), "u16": struct.Struct("!H"), "u32": struct.Struct("!I"),
           "u64": struct.Struct("!Q"), "i32": struct.Struct("!i")}


class ProtocolError(Exception):
    """A rejected message or connection, with an actionable, non-sensitive reason."""

    def __init__(self, reason, code=ERRORS["protocol"]):
        super().__init__(reason)
        self.code = code


class Field:
    """One field of a layout: [name, kind] or [name, kind, max] (s8, d16) or
    [name, "l8", fields, max] (a u8 count, then that many records)."""

    def __init__(self, entry):
        self.name, self.kind = entry[0], entry[1]
        self.most = None
        self.fields = None
        self.size = None
        if self.kind in SCALARS:
            pass
        elif re.fullmatch(r"b[0-9]+", self.kind):
            self.size = int(self.kind[1:])
        elif self.kind in ("s8", "d16"):
            self.most = entry[2]
        elif self.kind == "l8":
            self.fields = [Field(sub) for sub in entry[2]]
            self.most = entry[3]
        else:
            raise ValueError("protocol.json: unknown field kind " + self.kind)


class Message:
    def __init__(self, name, spec):
        self.name, self.id, self.dir = name, spec["id"], spec["dir"]
        self.bucket = spec.get("bucket")
        self.fields = [Field(entry) for entry in spec["fields"]]
        self.switch = None
        if "switch" in spec:
            # (a field whose value picks the fields that follow, PARTY's op:
            # named in the codec's dictionaries, its enum's value on the wire)
            switch = spec["switch"]
            values = SPEC[switch["enum"]]
            if set(switch["cases"]) != set(values):
                raise ValueError(f"protocol.json: {name}'s cases are not {switch['enum']}")
            self.switch = (switch["field"],
                           {case: (values[case], [Field(entry) for entry in fields]) for case, fields in switch["cases"].items()},
                           {values[case]: case for case in switch["cases"]})

    @property
    def from_client(self):
        return self.dir in ("c2s", "both")

    def sizes(self):
        """(least, most) bytes of the message, its type byte included."""
        least, most = _sizes(self.fields)
        if self.switch:
            cases = [_sizes(fields) for _, fields in self.switch[1].values()]
            least, most = least + min(c[0] for c in cases), most + max(c[1] for c in cases)
        return 1 + least, 1 + most


def _sizes(fields):
    least = most = 0
    for field in fields:
        if field.kind in SCALARS:
            least += SCALARS[field.kind].size
            most += SCALARS[field.kind].size
        elif field.size is not None:
            least += field.size
            most += field.size
        elif field.kind == "s8":
            least, most = least + 1, most + 1 + field.most
        elif field.kind == "d16":
            least, most = least + 2, most + 2 + field.most
        else:
            least, most = least + 1, most + 1 + field.most * _sizes(field.fields)[1]
    return least, most


MESSAGES = {name: Message(name, spec) for name, spec in SPEC["messages"].items()}
BY_ID = {message.id: message for message in MESSAGES.values()}
if len(BY_ID) != len(MESSAGES):
    raise ValueError("protocol.json: two messages share an id")
COMMANDS = {spec["type"]: (name, spec["args"]) for name, spec in SPEC["commands"].items()}
SYSTEM_COMMANDS = {spec["type"]: (name, spec["args"]) for name, spec in SPEC["system_commands"].items()}
COMMAND = {name: spec["type"] for name, spec in list(SPEC["commands"].items()) + list(SPEC["system_commands"].items())}


def _put(fields, values, out, where):
    for field in fields:
        if field.name not in values:
            raise ValueError(f"{where}: {field.name} is missing")
        value = values[field.name]
        kind = field.kind
        if kind in SCALARS:
            try:
                out += SCALARS[kind].pack(value)
            except struct.error as exc:
                raise ValueError(f"{where}: {field.name} = {value!r} does not fit {kind}") from exc
        elif field.size is not None:
            if not isinstance(value, (bytes, bytearray)) or len(value) != field.size:
                raise ValueError(f"{where}: {field.name} must be {field.size} bytes")
            out += value
        elif kind == "s8":
            data = value.encode("utf-8")
            if "\x00" in value or value.startswith("\ufeff"):
                raise ValueError(f"{where}: {field.name} holds a NUL or starts with a BOM")
            if len(data) > field.most:
                raise ValueError(f"{where}: {field.name} is longer than {field.most} bytes")
            out.append(len(data))
            out += data
        elif kind == "d16":
            if len(value) > field.most:
                raise ValueError(f"{where}: {field.name} is longer than {field.most} bytes")
            out += SCALARS["u16"].pack(len(value))
            out += value
        else:
            if len(value) > field.most:
                raise ValueError(f"{where}: {field.name} has more than {field.most} entries")
            out.append(len(value))
            for item in value:
                _put(field.fields, item, out, where)


def encode(kind, /, **values):
    """A message as bytes: its type, then its fields in layout order."""
    message = MESSAGES[kind]
    out = bytearray((message.id,))
    if message.switch:
        key, by_name, _ = message.switch
        if values.get(key) not in by_name:
            raise ValueError(f"{kind}: unknown {key} {values.get(key)!r}")
        wire, fields = by_name[values[key]]
        _put(message.fields, dict(values, **{key: wire}), out, kind)
        _put(fields, values, out, kind)
    else:
        _put(message.fields, values, out, kind)
    return bytes(out)


def _get(fields, data, offset, where):
    values = {}
    for field in fields:
        kind = field.kind
        if kind in SCALARS:
            scalar = SCALARS[kind]
            if offset + scalar.size > len(data):
                raise ProtocolError("Malformed " + where)
            values[field.name] = scalar.unpack_from(data, offset)[0]
            offset += scalar.size
        elif field.size is not None:
            if offset + field.size > len(data):
                raise ProtocolError("Malformed " + where)
            values[field.name] = bytes(data[offset:offset + field.size])
            offset += field.size
        elif kind == "s8":
            if offset >= len(data):
                raise ProtocolError("Malformed " + where)
            length = data[offset]
            text = bytes(data[offset + 1:offset + 1 + length])
            if length > field.most or len(text) != length:
                raise ProtocolError("Malformed " + where)
            try:
                values[field.name] = text.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ProtocolError("Malformed " + where) from exc
            # (as the GDScript codec reads strings: a NUL ends a Godot string, and
            # a leading byte-order mark is skipped, so either reads back changed)
            if "\x00" in values[field.name] or values[field.name].startswith("\ufeff"):
                raise ProtocolError("Malformed " + where)
            offset += 1 + length
        elif kind == "d16":
            if offset + 2 > len(data):
                raise ProtocolError("Malformed " + where)
            length = SCALARS["u16"].unpack_from(data, offset)[0]
            blob = bytes(data[offset + 2:offset + 2 + length])
            if length > field.most or len(blob) != length:
                raise ProtocolError("Malformed " + where)
            values[field.name] = blob
            offset += 2 + length
        else:
            if offset >= len(data):
                raise ProtocolError("Malformed " + where)
            count = data[offset]
            offset += 1
            if count > field.most:
                raise ProtocolError("Malformed " + where)
            items = []
            for _ in range(count):
                item, offset = _get(field.fields, data, offset, where)
                items.append(item)
            values[field.name] = items
    return values, offset


def decode(data):
    """(name, fields) of a message, its length exact and every field bounded."""
    if not data:
        raise ProtocolError("Empty message")
    message = BY_ID.get(data[0])
    if message is None:
        raise ProtocolError("Unknown message")
    values, offset = _get(message.fields, data, 1, message.name)
    if message.switch:
        key, by_name, by_value = message.switch
        case = by_value.get(values[key])
        if case is None:
            raise ProtocolError("Malformed " + message.name)
        values[key] = case
        more, offset = _get(by_name[case][1], data, offset, message.name)
        values.update(more)
    if offset != len(data):
        raise ProtocolError("Malformed " + message.name)
    return message.name, values


def decode_client(data):
    """A message a game may send: a server's own message from a game is refused."""
    name, values = decode(data)
    if not MESSAGES[name].from_client:
        raise ProtocolError("Unknown or out-of-order message")
    return name, values


def hello_version(data):
    """The protocol version a HELLO says, before it is checked, as another
    version's HELLO may be shaped otherwise (Cyberworld's v10 lesson); None
    where it is none."""
    if len(data) < 3 or data[0] != MESSAGES["HELLO"].id:
        return None
    return SCALARS["u16"].unpack_from(data, 1)[0]


def read_hello(data):
    """HELLO checked, in order: the version (error 2: the game is older; 17:
    the server is), its shape, a non-zero token (9), the name rule (5)."""
    version = hello_version(data)
    if version is not None and version != SPEC["version"]:
        if version > SPEC["version"]:
            raise ProtocolError("This server is older than the game", ERRORS["server_older"])
        raise ProtocolError("A newer version is out: reload", ERRORS["game_older"])
    name, hello = decode(data)
    if name != "HELLO":
        raise ProtocolError("Expected HELLO")
    if hello["flags"] & ~sum(SPEC["hello_flags"].values()):
        raise ProtocolError("Malformed HELLO")
    if not any(hello["token"]):
        raise ProtocolError("A random token is required", ERRORS["bad_token"])
    if not NAME.fullmatch(hello["name"]):
        raise ProtocolError("Use 1-16 ASCII letters, digits, spaces, _ or -", ERRORS["bad_name"])
    # (a resume names the seat it held: a wire seat and its match, or 255 and 0 for none)
    if hello["seat"] != SYSTEM_SEAT and (hello["seat"] >= SPEC["max_seats"] or hello["match"] == 0):
        raise ProtocolError("Malformed HELLO")
    return hello


def check_command(kind, a, b, c):
    """A CMD's shape: a type a game may send, its arguments inside their
    ranges (protocol.json's commands). Everything else is the simulation's."""
    entry = COMMANDS.get(kind)
    if entry is None:
        raise ProtocolError("Unknown command type", ERRORS["out_of_limits"])
    name, ranges = entry
    for value, (low, high) in zip((a, b, c), ranges):
        if not low <= value <= high:
            raise ProtocolError(name + " argument outside its limits", ERRORS["out_of_limits"])
    return name


def digest(data):
    """A state's hash from its bytes: the first 8 bytes of SHA-256, as the
    game's SimMatch.state_hash() is of SimCodec's bytes. An uploaded
    checkpoint is kept only when its digest is the hash the seats agreed for
    its tick (docs/design/contract-m4.md)."""
    return hashlib.sha256(data).digest()[:SPEC["hash_bytes"]]


def checkpoint_parts(tick, data):
    """A checkpoint's bytes as CHECKPOINT_PART messages: parts of
    checkpoint_part bytes in order from 0, every one but the last full. A
    game uploads them so, and a RESYNC sends them so; tick 0 has none (every
    game builds it from MATCH_CONFIG)."""
    size = SPEC["checkpoint_part"]
    chunks = [data[start:start + size] for start in range(0, len(data), size)]
    if len(chunks) > SPEC["max_checkpoint_parts"]:
        raise ValueError(f"a checkpoint of {len(data)} bytes is more than max_checkpoint_parts")
    return [encode("CHECKPOINT_PART", tick=tick, part=index, parts=len(chunks), data=chunk)
            for index, chunk in enumerate(chunks)]


def error(exc):
    """ERROR for a ProtocolError: its code and its reason, printable ASCII."""
    text = str(exc).encode("ascii", "replace")[:SPEC["text_bytes"]].decode("ascii")
    return encode("ERROR", code=exc.code, text=text)


def turn(number, entries):
    """TURN(number): its commands as (seat, seq, type, a, b, c), in order."""
    return encode("TURN", turn=number, commands=[dict(seat=seat, seq=seq, type=kind, a=a, b=b, c=c)
                                                 for seat, seq, kind, a, b, c in entries])


def printable(text, most):
    """server.ini's name or motd as WELCOME carries it: printable characters
    only (no NUL, no control or format character such as a byte-order mark,
    which a game's codec would refuse), at most `most` bytes of UTF-8."""
    text = "".join(ch for ch in (text or "") if ch.isprintable())
    return text.encode("utf-8")[:most].decode("utf-8", "ignore")


def maintenance_line(text):
    """server.ini's maintenance: the host's line ("until 14:00 UTC"), printable
    ASCII, at most maintenance_bytes, sent as ERROR 16's reason to every game
    that comes; empty: open. (Cyberworld's, unchanged.)"""
    text = " ".join((text or "").split())
    if len(text) > SPEC["maintenance_bytes"] or not all(32 <= ord(c) < 127 for c in text):
        raise ValueError(f"maintenance is at most {SPEC['maintenance_bytes']} printable ASCII characters")
    return text
