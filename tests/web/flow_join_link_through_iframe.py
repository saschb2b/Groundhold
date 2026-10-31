#!/usr/bin/env python3
"""flow_join_link_through_iframe: a party's link, play/?join=CODE, opened in a browser, reaches the
game in the page's frame and joins that party on the official server (design 6.8, M5).

    godot --headless --path . --import                                   # once, after a clone
    mkdir -p build/web && godot --headless --path . --export-release Web build/web/index.html
    python3 tests/web/flow_join_link_through_iframe.py --game build/web [--out DIR]

Everything is real but the server's address. It serves the site as Pages lays it out (the play page
from web/play/, the export as play/game/) on 127.0.0.1, runs the real server (server/main.py, hub
mode, this page's origin allowed) with a party made by a small client over the wire, and opens the
page in headless Chrome with agent-browser. The export knows only data/net.json's official URL, so
the served game page gets one script first that sends a WebSocket for that URL to the local server
instead, and keeps the first bytes of every message the game sends. Then:

1. play/?join=K7Q4M (the acceptance's code; no party has it): the frame opens game/?join=K7Q4M. The
   browser is new, so the game asks for a name first and connects to nothing until it has one (HELLO
   is the only message that carries a name). The check types one, Wren, into the prompt; then the
   game connects to the official server with that name in its HELLO and asks it to join K7Q4M (PARTY
   join, code K7Q4M).
2. A small client makes a party, with the build and rules hash the game's HELLO carried.
3. play/?join=<that party's code as a friend types it, k7q-4m style>: the game, named now, joins it at
   once; the server's event log says party_join and the host's PARTY_STATE lists Edda and Wren.

It prints one line per check and exits 1 on the first that fails. --build-seq N also checks that a
stamped shell (tools/release/stamp.py shell) fetched index.wasm?v=N and index.pck?v=N. The run's
server's log and events, the files the page fetched, the browser's console and a screenshot (and,
on a failure, what the page and the game had done) go to --out. Needs Node's agent-browser
(npm i -g agent-browser) and Chrome; every wait is bounded; everything started is stopped.
"""

import argparse
import base64
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
from groundhold_server import protocol  # noqa: E402
from groundhold_server.protocol import SPEC  # noqa: E402

CODE = "K7Q4M"
NAME = "Wren"
PARTY_ID = SPEC["messages"]["PARTY"]["id"]
JOIN_OP = SPEC["party_ops"]["join"]

# The first script of the served game page: the official URL's socket goes to the local server, and
# the first 64 bytes of every message the game sends are kept in window.__groundhold.sent (a HELLO's
# name ends by its 50th).
REDIRECT_JS = """<script>
(function () {
  var official = %s, local = %s, Native = window.WebSocket;
  var seen = window.__groundhold = { urls: [], sent: [] };
  function Redirected(url, protocols) {
    seen.urls.push(String(url));
    var ws = new Native(String(url) === official ? local : url, protocols);
    var send = ws.send.bind(ws);
    ws.send = function (data) {
      try {
        var bytes = data instanceof ArrayBuffer ? new Uint8Array(data) : new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
        seen.sent.push(Array.prototype.slice.call(bytes, 0, 64));
      } catch (e) {}
      return send(data);
    };
    return ws;
  }
  Redirected.prototype = Native.prototype;
  ["CONNECTING", "OPEN", "CLOSING", "CLOSED"].forEach(function (k) { Redirected[k] = Native[k]; });
  window.WebSocket = Redirected;
})();
</script>
"""


# The files the game's user:// holds in the browser's IndexedDB (Godot keeps it in the database
# /userfs and writes a file there some seconds after it is saved), as a JSON list of paths.
SAVED_JS = """new Promise(function (done) {
  var opened = document.getElementById('game').contentWindow.indexedDB.open('/userfs');
  opened.onerror = function () { done('[]'); };
  opened.onsuccess = function () {
    try {
      var keys = opened.result.transaction('FILE_DATA', 'readonly').objectStore('FILE_DATA').getAllKeys();
      keys.onsuccess = function () { done(JSON.stringify(keys.result)); };
      keys.onerror = function () { done('[]'); };
    } catch (e) { done('[]'); }
  };
})"""


def log(line):
    print(line, flush=True)


# ── the site, as Pages serves it ──

class Site(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, game: Path, inject: str):
        self.game, self.inject, self.fetched = game, inject, []
        super().__init__(("127.0.0.1", 0), SiteHandler)


class SiteHandler(http.server.BaseHTTPRequestHandler):
    TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".wasm": "application/wasm",
             ".pck": "application/octet-stream", ".css": "text/css", ".png": "image/png", ".ttf": "font/ttf",
             ".json": "application/json", ".webp": "image/webp"}

    def do_GET(self):  # noqa: N802 (http.server's name)
        site: Site = self.server
        url = urllib.parse.urlsplit(self.path)
        site.fetched.append(self.path)
        path = urllib.parse.unquote(url.path)
        if path in ("/play", "/play/game"):
            return self.answer(301, b"", {"Location": path + "/" + ("?" + url.query if url.query else "")})
        if path.endswith("/"):
            path += "index.html"
        parts = [p for p in path.split("/") if p]
        if not parts or ".." in parts:
            return self.answer(404, b"not here")
        if parts[:2] == ["play", "game"]:
            file = site.game.joinpath(*parts[2:])
        elif parts == ["play", "index.html"]:
            file = ROOT / "web" / "play" / "index.html"
        elif parts[0] == "assets":
            file = ROOT.joinpath("web", *parts)
        elif parts[0] in ("ui", "fonts"):
            file = ROOT.joinpath(*parts)
        else:
            return self.answer(404, b"not here")
        if not file.is_file():
            return self.answer(404, b"not here")
        data = file.read_bytes()
        if parts == ["play", "game", "index.html"]:
            html = data.decode("utf-8")
            data = html.replace("<head>", "<head>\n" + site.inject, 1).encode("utf-8")
        self.answer(200, data, {"Content-Type": self.TYPES.get(file.suffix, "application/octet-stream"),
                                "Cache-Control": "no-store"})

    def answer(self, status, body, headers=None):
        self.send_response(status)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


# ── a party's host over the wire ──

class Host:
    """A game as far as the wire goes: HELLO, a party, PINGs; it keeps every PARTY_STATE."""

    def __init__(self, port, build_seq=0, rules_hash=bytes(8)):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET {SPEC['path']} HTTP/1.1\r\nHost: 127.0.0.1\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: {key}\r\n"
                           f"Sec-WebSocket-Protocol: {SPEC['subprotocol']}\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("the server closed the upgrade")
            head += chunk
        if not head.startswith(b"HTTP/1.1 101"):
            raise RuntimeError(f"no upgrade: {head[:80]!r}")
        self.buffer = head.split(b"\r\n\r\n", 1)[1]
        self.states, self.lock, self.closed = [], threading.Lock(), False
        self.send(protocol.encode("HELLO", version=SPEC["version"], build_seq=build_seq, rules_hash=rules_hash,
                                  token=os.urandom(16), flags=0, name="Edda", match=0, seat=SPEC["system_seat"]))
        name, _ = self.next()
        if name != "WELCOME":
            raise RuntimeError(f"HELLO answered {name}")
        self.send(protocol.encode("PARTY", op="create", mode=SPEC["modes"]["high_water"]["id"]))
        name, fields = self.next()
        while name != "PARTY_STATE":
            name, fields = self.next()
        self.states.append(fields)
        self.code = bytes(fields["code"]).decode()
        self.thread = threading.Thread(target=self.keep, daemon=True)
        self.thread.start()

    def send(self, data):
        mask = os.urandom(4)
        header = bytes((0x82, 0x80 | len(data))) if len(data) < 126 else struct.pack("!BBH", 0x82, 254, len(data))
        self.sock.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def read(self, n):
        while len(self.buffer) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("closed")
            self.buffer += chunk
        out, self.buffer = self.buffer[:n], self.buffer[n:]
        return out

    def next(self):
        first, size = self.read(2)
        if size == 126:
            size = struct.unpack("!H", self.read(2))[0]
        elif size == 127:
            size = struct.unpack("!Q", self.read(8))[0]
        data = self.read(size)
        if first & 0x0F == 0x8:
            raise ConnectionError("closed by the server")
        return protocol.decode(data)

    def keep(self):
        self.sock.settimeout(0.5)
        pinged = 0.0
        while not self.closed:
            if time.monotonic() - pinged >= SPEC["ping_ms"] / 1000:
                pinged = time.monotonic()
                try:
                    self.send(protocol.encode("PING", client_ms=int(pinged * 1000) & 0xFFFFFFFF, rtt_ms=0))
                except OSError:
                    return
            try:
                name, fields = self.next()
            except socket.timeout:
                continue
            except (OSError, ConnectionError, ValueError):
                return
            if name == "PARTY_STATE":
                with self.lock:
                    self.states.append(fields)

    def members(self):
        with self.lock:
            return [m["name"] for m in self.states[-1]["members"]]

    def close(self):
        self.closed = True
        try:
            self.sock.close()
        except OSError:
            pass


# ── the browser ──

class Browser:
    def __init__(self, out: Path):
        self.exe = shutil.which("agent-browser")
        if not self.exe:
            raise RuntimeError("needs agent-browser (npm i -g agent-browser)")
        self.session = f"groundhold-join-link-{os.getpid()}"
        self.out = out

    def run(self, *args, timeout=60):
        done = subprocess.run([self.exe, "--session", self.session, *args], capture_output=True, text=True,
                              timeout=timeout, check=False)
        if done.returncode != 0:
            raise RuntimeError(f"agent-browser {args[0]}: {done.stderr.strip() or done.stdout.strip()}")
        return done.stdout.strip()

    def eval(self, js):
        """A JSON-encoded expression's value, read back."""
        text = self.run("eval", f"JSON.stringify({js})")
        try:
            value = json.loads(text)
            return json.loads(value) if isinstance(value, str) else value
        except ValueError:
            return None

    def saved(self):
        """The paths the game's user:// holds in IndexedDB (SAVED_JS: a promise, which eval awaits)."""
        try:
            value = json.loads(self.run("eval", SAVED_JS))
            value = json.loads(value) if isinstance(value, str) else value
        except ValueError:
            return []
        return value if isinstance(value, list) else []

    def screenshot(self, name):
        self.run("screenshot", str(self.out / name))

    def close(self):
        try:
            subprocess.run([self.exe, "--session", self.session, "close"], capture_output=True, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass


def until(what, probe, timeout, every=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = probe()
        if value:
            return value
        time.sleep(every)
    raise AssertionError(f"never: {what} (within {timeout:.0f} s)")


def game_hello(seen):
    """The build_seq and rules hash of the game's HELLO (its first 15 bytes: id, u16 version, u32
    build_seq, 8 bytes rules hash), so the party's host can run the same build."""
    hello = next((m for m in (seen or {}).get("sent", []) if m and m[0] == SPEC["messages"]["HELLO"]["id"]), None)
    if hello is None or len(hello) < 15:
        raise AssertionError("the game sent no HELLO")
    return struct.unpack("!I", bytes(hello[3:7]))[0], bytes(hello[7:15])


def hello_name(seen):
    """The name in the game's HELLO (after id, version, build_seq, rules hash, token and flags: 32
    bytes, then a length byte and the name's bytes)."""
    hello = next((m for m in (seen or {}).get("sent", []) if m and m[0] == SPEC["messages"]["HELLO"]["id"]), None)
    if hello is None or len(hello) < 33:
        raise AssertionError("the game sent no HELLO")
    return bytes(hello[33:33 + hello[32]]).decode("utf-8", "replace")


def sent_join(seen, code):
    """Whether the game sent PARTY join with `code`."""
    want = [PARTY_ID, JOIN_OP] + list(code.encode())
    return any(message[:len(want)] == want for message in (seen or {}).get("sent", []))


def keep_log(stream, path: Path):
    """The server's console, line by line, into the run's folder."""
    with path.open("w", encoding="utf-8") as out:
        for line in stream:
            out.write(line)
            out.flush()


def events(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def check(args, work: Path) -> None:
    official = json.loads((ROOT / "data" / "net.json").read_text(encoding="utf-8"))["official"]
    site = Site(args.game, "")
    threading.Thread(target=site.serve_forever, daemon=True).start()
    page_origin = f"http://127.0.0.1:{site.server_port}"
    (work / "server.ini").write_text(f"[server]\nname = Groundhold join-link check\norigins = {page_origin}\n"
                                     "beacon = false\n", encoding="utf-8")
    event_log = args.out / "events.jsonl"
    event_log.unlink(missing_ok=True)
    server = subprocess.Popen([sys.executable, str(ROOT / "server" / "main.py"), "--config", str(work / "server.ini"),
                               "--host", "127.0.0.1", "--port", "0", "--state-dir", str(work / "state"),
                               "--event-log", str(event_log)],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    host = browser = None
    passed = False
    try:
        port = None
        deadline = time.monotonic() + 20
        while port is None and time.monotonic() < deadline:
            line = server.stdout.readline()
            if not line:
                break
            found = re.search(r"listening port=(\d+)", line)
            port = int(found.group(1)) if found else None
        if port is None:
            raise AssertionError("the server never said 'listening port=N'")
        threading.Thread(target=keep_log, args=(server.stdout, args.out / "server.log"), daemon=True).start()
        site.inject = REDIRECT_JS % (json.dumps(official), json.dumps(f"ws://127.0.0.1:{port}{SPEC['path']}"))
        log(f"server on 127.0.0.1:{port}, site on {page_origin}, the game's {official} sent there")

        browser = Browser(args.out)
        # 1. The acceptance's code, which no party has: it reaches the game's session.
        opened = time.monotonic()
        browser.run("open", f"{page_origin}/play/?join={CODE}", timeout=90)
        src = browser.eval("document.getElementById('game').getAttribute('src')")
        if src != f"game/?join={CODE}":
            raise AssertionError(f"the frame opened {src!r}, not game/?join={CODE}")
        log(f"ok   play/?join={CODE} opens the frame at {src}")
        # (a first launch: the prompt waits for a name, and the link with it)
        until("the game's hub (its banner in the console)",
              lambda: "official server wss://" in browser.run("console"), args.timeout)
        time.sleep(3)
        early = browser.eval("document.getElementById('game').contentWindow.__groundhold")
        if early is None or early.get("urls"):
            raise AssertionError(f"the game connected before it was named: {early}")
        browser.screenshot("name_prompt.png")
        log("ok   a first launch asks for a name, and the link connects to nothing meanwhile")
        browser.eval("(document.getElementById('game').contentWindow.document.getElementById('canvas').focus(), true)")
        # (key presses, one a character: Godot's canvas reads keydown, which a typed text may not send)
        browser.run("press", "Control+a")
        for key in NAME:
            browser.run("press", key)
        browser.run("press", "Enter")
        seen = until(f"the game asks the server to join {CODE}",
                     lambda: (lambda s: s if sent_join(s, CODE) else None)(
                         browser.eval("document.getElementById('game').contentWindow.__groundhold")),
                     args.timeout)
        if official not in seen["urls"]:
            raise AssertionError(f"the game connected to {seen['urls']}, not {official}")
        log(f"ok   the game connected to {official} and sent PARTY join {CODE} "
            f"({time.monotonic() - opened:.0f} s after the page opened)")
        if hello_name(seen) != NAME:
            raise AssertionError(f"the game's HELLO named {hello_name(seen)!r}, not the {NAME!r} typed")
        log(f"ok   its HELLO carries the name typed into the prompt, {NAME}")
        # (the next visit knows the name: the profile reaches the browser's storage before the page goes)
        until("the name kept: user://profile.cfg in the browser's IndexedDB",
              lambda: any(path.endswith("/profile.cfg") for path in browser.saved()), 60)
        log("ok   the name is kept for the next visit (user://profile.cfg in IndexedDB)")

        build_seq, rules_hash = game_hello(seen)
        host = Host(port, build_seq, rules_hash)
        log(f"ok   a party to join: {host.code}, led by Edda (the game's build {build_seq}, rules {rules_hash.hex()})")

        # 3. A real party's code, as a friend types it: the game joins that party.
        typed = (host.code[:3] + "-" + host.code[3:]).lower()
        opened = time.monotonic()
        browser.run("open", f"{page_origin}/play/?join={typed}", timeout=90)
        until(f"the server's party_join for {host.code}",
              lambda: any(e.get("event") == "party_join" and e.get("party") == host.code for e in events(event_log)),
              args.timeout)
        until("two members in the host's PARTY_STATE", lambda: len(host.members()) == 2, 30, every=0.5)
        if host.members() != ["Edda", NAME]:
            raise AssertionError(f"the party's members are {host.members()}, not Edda and {NAME}")
        log(f"ok   play/?join={typed} joined party {host.code}: {host.members()} "
            f"({time.monotonic() - opened:.0f} s after the page opened)")

        if args.build_seq is not None:
            wanted = [f"/play/game/index.wasm?v={args.build_seq}", f"/play/game/index.pck?v={args.build_seq}"]
            missing = [w for w in wanted if w not in site.fetched]
            if missing:
                raise AssertionError(f"the shell did not fetch {missing}: {sorted(set(site.fetched))}")
            log(f"ok   the shell fetched its build's files as ?v={args.build_seq}")
        browser.screenshot("joined.png")
        passed = True
    finally:
        (args.out / "fetched.txt").write_text("\n".join(site.fetched) + "\n", encoding="utf-8")
        if browser:
            try:
                if not passed:
                    # (what the page and its game had done when a wait ran out)
                    state = browser.eval("{top: document.visibilityState, src: document.getElementById('game').src, "
                                         "frame: document.getElementById('game').contentDocument.visibilityState, "
                                         "seen: document.getElementById('game').contentWindow.__groundhold || null}")
                    (args.out / "failed_state.json").write_text(json.dumps(state, indent=1), encoding="utf-8")
                    browser.run("screenshot", str(args.out / "failed.png"))
                (args.out / "console.txt").write_text(browser.run("console"), encoding="utf-8")
            except (RuntimeError, OSError, subprocess.TimeoutExpired):
                pass
            browser.close()
        if host:
            host.close()
        server.terminate()
        try:
            server.wait(10)
        except subprocess.TimeoutExpired:
            server.kill()
        site.shutdown()
        site.server_close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--game", type=Path, required=True, help="the Web export's folder (index.html, .pck, .wasm)")
    parser.add_argument("--out", type=Path, default=None, help="where the events, console and screenshot go")
    # (the game draws with software WebGL in headless Chrome: its first frames, every shader compiled
    # for the first time, take a while on a busy machine)
    parser.add_argument("--timeout", type=float, default=240, help="seconds each wait may take (default 240)")
    parser.add_argument("--build-seq", type=int, default=None, help="the number a stamped shell asks its files by")
    args = parser.parse_args(argv)
    if not (args.game / "index.html").is_file() or not (args.game / "index.pck").is_file():
        parser.error(f"{args.game} holds no Web export")
    with tempfile.TemporaryDirectory(prefix="groundhold-join-link-") as work:
        args.out = args.out or Path(work) / "out"
        args.out.mkdir(parents=True, exist_ok=True)
        try:
            check(args, Path(work))
        except (AssertionError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
            log(f"FAIL {exc}")
            return 1
    log("flow_join_link_through_iframe: passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
