#!/usr/bin/env python3
"""Run a packaged server outside the checkout and check that it does its job.

Given a release archive (release.py's groundhold-server-TARGET.zip), it is
extracted into a temporary folder of its own, executable bits kept, and the
program BUILD.json names is run from there; given a program (a .pyz or a
native build), that is run. Either way, with the temporary folder as its
working directory:

- `--help` answers, naming the server;
- a real process on a free port of 127.0.0.1 says `listening` in its event
  log, then serves `/health` (status ok, this checkout's protocol, nobody
  in) and `/stats`;
- a game's handshake: the WebSocket upgrade on the protocol's path and
  subprotocol, HELLO, and WELCOME with the server's name; `/health` counts
  the player, and `--admin list` finds it in the roster;
- `--backup DIR --once` writes an archive holding the identity key;
- SIGTERM ends it cleanly (exit status 0; Windows has no SIGTERM, so the
  process tree is ended there).

A file the archive lacks (protocol.json, a frozen module) fails here, not on
a player's computer. Every wait is bounded. Adapted from Cyberworld
Endless's server/smoke.py (MIT, Sascha Becker): the help, health and
administration checks are its; the archive, the handshake, the backup and
the clean stop are new.

    python3 server/smoke.py build/release/groundhold-server-linux-x64.zip
    python3 server/smoke.py build/server/groundhold-server.pyz
"""
import argparse
import base64
import contextlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from groundhold_server import protocol   # noqa: E402  (the checkout's codec, to speak to the package)
from groundhold_server.protocol import SPEC   # noqa: E402

NAME = "Smoke"
START = 60      # seconds for a first start (a one-file build unpacks itself first)
STEP = 20       # seconds for any other answer


def extract(archive, directory):
    """An archive's files under `directory`, their Unix modes kept (zipfile's
    extractall drops them)."""
    directory = Path(directory)
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            target = (directory / entry.filename).resolve()
            if directory.resolve() not in target.parents:
                raise RuntimeError(f"{archive}: {entry.filename} would land outside the folder")
            bundle.extract(entry, directory)
            mode = entry.external_attr >> 16 & 0o777
            if mode and os.name != "nt":
                target.chmod(mode)
    return directory


def program(path, work):
    """The command that runs the packaged server at `path` (an archive is
    extracted into `work` first)."""
    path = Path(path).resolve()
    if path.suffix == ".zip":
        unpacked = extract(path, work / "package")
        # (a release archive holds one folder, groundhold-server-VERSION-TARGET/, and nothing beside it)
        tops = sorted(unpacked.iterdir())
        if len(tops) != 1 or not tops[0].is_dir():
            raise RuntimeError(f"{path.name} holds {[top.name for top in tops]}, not one folder")
        folder = tops[0]
        build = json.loads((folder / "BUILD.json").read_text(encoding="utf-8"))
        if folder.name != f"groundhold-server-{build['version']}-{build['target']}":
            raise RuntimeError(f"{path.name}'s folder is {folder.name}, not its version's and target's")
        path = folder / build["executable"]
        if not path.is_file():
            raise RuntimeError(f"BUILD.json names {build['executable']}, which the archive lacks")
    return [sys.executable, str(path)] if path.suffix == ".pyz" else [str(path)]


def wait_port(process, events, timeout=START):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"The packaged server exited ({process.returncode}) before it listened")
        if events.exists():
            for line in events.read_text(encoding="utf-8").splitlines():
                with contextlib.suppress(json.JSONDecodeError):
                    event = json.loads(line)
                    if event.get("event") == "listening":
                        return event["port"]
        time.sleep(0.05)
    raise RuntimeError(f"The packaged server did not listen within {timeout} seconds")


def get_json(port, path):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(f"http://127.0.0.1:{port}{path}", timeout=STEP) as response:
        return json.load(response)


def masked(data, opcode=2, mask=b"pkgs"):
    """A client's frame, masked as RFC 6455 asks of it."""
    if len(data) < 126:
        header = bytes((0x80 | opcode, 0x80 | len(data)))
    else:
        header = struct.pack("!BBH", 0x80 | opcode, 0x80 | 126, len(data))
    return header + mask + bytes(value ^ mask[i % 4] for i, value in enumerate(data))


def read_exactly(stream, size):
    data = b""
    while len(data) < size:
        chunk = stream.recv(size - len(data))
        if not chunk:
            raise RuntimeError("The packaged server closed the connection")
        data += chunk
    return data


def next_message(stream):
    """The server's next message, decoded: (name, fields)."""
    first, size = read_exactly(stream, 2)
    if size == 126:
        size = struct.unpack("!H", read_exactly(stream, 2))[0]
    elif size == 127:
        size = struct.unpack("!Q", read_exactly(stream, 8))[0]
    data = read_exactly(stream, size)
    if first & 0x0f == 0x8:
        raise RuntimeError("The packaged server closed the WebSocket: " + repr(data))
    return protocol.decode(data)


def handshake(port):
    """A game's connection: the upgrade, HELLO and WELCOME. Returns the open
    socket and WELCOME's fields."""
    stream = socket.create_connection(("127.0.0.1", port), timeout=STEP)
    key = base64.b64encode(os.urandom(16)).decode()
    request = (f"GET {SPEC['path']} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
               f"Sec-WebSocket-Protocol: {SPEC['subprotocol']}\r\n\r\n")
    stream.sendall(request.encode())
    answer = b""
    while b"\r\n\r\n" not in answer:
        chunk = stream.recv(1024)
        if not chunk or len(answer) > 8192:
            raise RuntimeError("No WebSocket upgrade: " + repr(answer[:200]))
        answer += chunk
    if not answer.startswith(b"HTTP/1.1 101"):
        raise RuntimeError("No WebSocket upgrade: " + repr(answer.split(b"\r\n", 1)[0]))
    hello = protocol.encode("HELLO", version=SPEC["version"], build_seq=0, rules_hash=bytes(8),
                            token=bytes(range(16)), flags=0, name=NAME, match=0, seat=SPEC["system_seat"])
    stream.sendall(masked(hello))
    name, fields = next_message(stream)
    if name != "WELCOME":
        raise RuntimeError(f"HELLO was answered {name} {fields}")
    return stream, fields


def run(command, work, *args):
    result = subprocess.run(command + list(args), cwd=work, capture_output=True, text=True, timeout=STEP * 3)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed ({result.returncode}): {result.stdout}{result.stderr}")
    return result.stdout


def in_roster(command, work, state):
    """--admin list until the roster names the smoke's game (the server writes
    it within a second); the listing."""
    deadline = time.monotonic() + STEP
    while True:
        listing = json.loads(run(command, work, "--state-dir", str(state), "--admin", "list"))
        if any(player.get("name") == NAME for player in listing["roster"].get("players", [])):
            return listing
        if time.monotonic() > deadline:
            raise RuntimeError("--admin list never named the connected game: " + json.dumps(listing))
        time.sleep(0.25)


def stop(process):
    """Ends the server; its exit status (None where the tree was killed)."""
    if process.poll() is not None:
        return process.returncode
    if os.name == "nt":
        # A one-file build is a bootloader and its child: end this test's tree alone.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        process.wait(timeout=STEP)
        return None
    process.terminate()
    try:
        return process.wait(timeout=STEP)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
        raise RuntimeError(f"The packaged server did not stop within {STEP} seconds of SIGTERM")


def smoke(path):
    """Every check above on the package at `path`; raises RuntimeError on the first that fails."""
    with tempfile.TemporaryDirectory(prefix="groundhold-package-") as directory:
        work = Path(directory)
        command = program(path, work)
        result = subprocess.run(command + ["--help"], cwd=work, capture_output=True, text=True, timeout=START,
                                check=True)
        if "Groundhold server" not in result.stdout or "--state-dir" not in result.stdout:
            raise RuntimeError("Unexpected help from the packaged server: " + result.stdout)
        events, log, state = work / "events.jsonl", work / "process.log", work / "state"
        with log.open("w", encoding="utf-8") as output:
            process = subprocess.Popen(command + ["--host", "127.0.0.1", "--port", "0", "--state-dir", str(state),
                                                  "--event-log", str(events)],
                                       cwd=work, stdout=output, stderr=subprocess.STDOUT)
            stream = None
            try:
                port = wait_port(process, events)
                health = get_json(port, "/health")
                if health.get("status") != "ok" or health.get("protocol") != SPEC["version"] or health.get("players"):
                    raise RuntimeError("Wrong status, protocol or occupancy in /health: " + repr(health))
                if "today" not in get_json(port, "/stats"):
                    raise RuntimeError("/stats has no day")
                stream, welcome = handshake(port)
                if welcome["server_name"] != health["name"]:
                    raise RuntimeError(f"WELCOME names {welcome['server_name']!r}, /health {health['name']!r}")
                if get_json(port, "/health").get("players") != 1:
                    raise RuntimeError("/health does not count the connected game")
                in_roster(command, work, state)
                (work / "backups").mkdir()
                backup = json.loads(run(command, work, "--state-dir", str(state), "--backup", str(work / "backups"),
                                        "--once"))
                with tarfile.open(backup["archive"]) as archive:
                    if "identity.key" not in archive.getnames():
                        raise RuntimeError("The backup holds no identity.key: " + repr(archive.getnames()))
                stream.sendall(masked(protocol.encode("BYE")))
                stream.close()
                stream = None
                status = stop(process)
                if status not in (0, None):
                    raise RuntimeError(f"The packaged server exited {status} on SIGTERM")
            except Exception:
                output.flush()
                print(log.read_text(encoding="utf-8"), file=sys.stderr)
                raise
            finally:
                if stream:
                    stream.close()
                stop(process)
    print(f"Packaged server passed: {Path(path).name} (protocol {SPEC['version']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("package", type=Path, help="A release archive (.zip), a zipapp (.pyz) or a native build")
    smoke(parser.parse_args().package)
