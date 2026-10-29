"""Command-line configuration: a server on this computer with nothing set,
or a TLS endpoint behind its INI (server/README.md, Host your own).

Reused from Cyberworld Endless's server/cyberworld_server/cli.py (MIT,
Sascha Becker): the INI beside the program, LANTERN_SERVER_* environment
overrides, the free_text refusal, TLS, the banner looked up off the loop and
the signal handling. New: --dev-match and the `listening port=N` line.
"""

import argparse
import asyncio
import configparser
import contextlib
import logging
import os
from pathlib import Path
import signal
import ssl
import sys
import threading

from .app import Server, dev_match_spec
from . import hosting
from .protocol import SPEC

# (the published browser build's page: its players come to any server that
# serves wss://; server.ini's `origins =` empty lets native games alone in)
ORIGINS = "https://saschb2b.github.io"


def config_path(args):
    """The INI read: --config's, else a server.ini in the folder the server
    starts in or beside its program, else none (the defaults)."""
    if args.config:
        return Path(args.config)
    return hosting.find_config((Path.cwd(), hosting.program_folder()))


def configured(args, environ=os.environ):
    """The [server] section, from the INI with the environment's
    LANTERN_SERVER_* over it."""
    config = configparser.ConfigParser()
    path = config_path(args)
    if path and not config.read(path):
        raise ValueError("Could not read server config: " + str(path))
    if not config.has_section("server"):
        config.add_section("server")
    settings = config["server"]
    settings.update(hosting.environment_settings(environ))
    return settings


async def run(args):
    settings = configured(args)
    # (empty: every interface, IPv4 and IPv6, so other computers can come)
    host = args.host or settings.get("host") or None
    port = args.port if args.port is not None else settings.getint("port", SPEC["port"])
    if settings.getboolean("free_text", False):
        raise ValueError("free_text is unavailable: names and signals only")
    dev = args.dev_match or settings.get("dev_match") or None
    dev = dev_match_spec(dev) if dev else None
    seed = args.seed if args.seed is not None else (settings.getint("seed") if settings.get("seed") else None)
    turn_ms = args.turn_ms if args.turn_ms is not None else SPEC["turn_ms"]
    if turn_ms != SPEC["turn_ms"] and not dev:
        raise ValueError("--turn-ms is for --dev-match only")
    tls = None
    cert, key = settings.get("tls_certificate"), settings.get("tls_key")
    if bool(cert) != bool(key):
        raise ValueError("TLS needs both tls_certificate and tls_key")
    if cert:
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.minimum_version = ssl.TLSVersion.TLSv1_2
        tls.load_cert_chain(cert, key)
    with contextlib.ExitStack() as stack:
        events = stack.enter_context(open(args.event_log, "a", encoding="utf-8")) if args.event_log else None
        server = Server(name=settings.get("name", "Lantern Hollow"), motd=settings.get("motd", "Hold the road together"),
                        origins=tuple(settings.get("origins", ORIGINS).split()), event_log=events,
                        player_cap=settings.getint("player_cap", 64), maintenance=settings.get("maintenance", ""),
                        dev_match=dev, seed=seed, turn_ms=turn_ms)
        port = await server.start(host, port, tls)
        # (handlers first: a harness may stop the server as soon as it reads the line below)
        stop = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                asyncio.get_running_loop().add_signal_handler(sig, stop.set)
        try:
            # (the line a harness waits for: the port, chosen by the system under --port 0)
            print(f"listening port={port} host={host or '*'} path={SPEC['path']}", flush=True)
            announcing = asyncio.create_task(announce(server, host, port, tls is not None, config_path(args)))
            await stop.wait()
            announcing.cancel()
            await asyncio.gather(announcing, return_exceptions=True)
        finally:
            await server.close()


async def announce(server, host, port, secure, config):
    """The console's word to the host as the server opens: where players
    come in from (hosting.py); this computer's name's addresses looked up
    off the loop in a daemon thread, and given up after two seconds (a name
    service that never answers must not hold a SIGTERM's exit)."""
    loop = asyncio.get_running_loop()
    found = loop.create_future()

    def look():
        addresses = hosting.local_addresses()
        with contextlib.suppress(RuntimeError):   # (the loop already closed)
            loop.call_soon_threadsafe(lambda: found.done() or found.set_result(addresses))

    threading.Thread(target=look, name="addresses", daemon=True).start()
    try:
        addresses = await asyncio.wait_for(found, 2)
    except asyncio.TimeoutError:
        addresses = hosting.local_addresses(named=False)
    hosting.announce(hosting.banner(server.name, host, port, secure, addresses, config,
                                    hosting.contained(), os.name == "nt", server.dev_match))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Lantern Hollow server: sequences the turns of multiplayer matches; "
                                                 "it never runs one")
    parser.add_argument("--config", help="The INI to read (default: server.ini in this folder or beside the server, if there is one)")
    parser.add_argument("--host", help="Where to listen (default: every interface; 127.0.0.1 this computer alone)")
    parser.add_argument("--port", type=int, help=f"The port (default {SPEC['port']}; 0: one the system picks, printed as listening port=N)")
    parser.add_argument("--event-log", help="Optional JSONL of connections and matches; contains display names")
    parser.add_argument("--dev-match", metavar="MODE:SEATS",
                        help="Form a match from the first SEATS players to connect (classic:2), for development")
    parser.add_argument("--seed", type=int, help="With --dev-match: every match's seed (default: a random one each)")
    parser.add_argument("--turn-ms", type=int, help=f"With --dev-match: the turn length in ms (default {SPEC['turn_ms']}); "
                                                    "games pace by it, so 10 plays a match five times faster")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        if args.dev_match:
            dev_match_spec(args.dev_match)
        asyncio.run(run(args))
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + "\n")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
