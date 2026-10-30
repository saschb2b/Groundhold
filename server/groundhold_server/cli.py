"""Command-line configuration: a server on this computer with nothing set,
or a TLS endpoint behind its INI (server/README.md, Host your own); and the
local tools on its state directory: moderation (--admin), backups
(--backup, --restore).

Reused from Cyberworld Endless's server/cyberworld_server/cli.py (MIT,
Sascha Becker): the INI beside the program, GROUNDHOLD_SERVER_* environment
overrides, the free_text refusal, TLS, the state directory, --admin,
--backup and --restore, the allowlist, the retention's keys, the banner
looked up off the loop and the signal handling. New: --dev-match, the
`listening port=N` line and the LAN beacon.
"""

import argparse
import asyncio
import configparser
import contextlib
import json
import logging
import os
from pathlib import Path
import signal
import ssl
import sys
import threading

from .app import Server, dev_match_spec
from . import admin, backup, beacon, hosting
from .identity import public_id
from .protocol import SPEC
from .retention import Retention

# (the published browser build's page: its players come to any server that
# serves wss://; server.ini's `origins =` empty lets native games alone in)
ORIGINS = "https://saschb2b.github.io"
STATE_DIR = "server-data"


def config_path(args):
    """The INI read: --config's, else a server.ini in the folder the server
    starts in or beside its program, else none (the defaults)."""
    if args.config:
        return Path(args.config)
    return hosting.find_config((Path.cwd(), hosting.program_folder()))


def configured(args, environ=os.environ):
    """The [server] section, from the INI with the environment's
    GROUNDHOLD_SERVER_* over it."""
    config = configparser.ConfigParser()
    path = config_path(args)
    if path and not config.read(path):
        raise ValueError("Could not read server config: " + str(path))
    if not config.has_section("server"):
        config.add_section("server")
    settings = config["server"]
    settings.update(hosting.environment_settings(environ))
    return settings


def state_dir(args, settings, dev=False):
    """The private state directory: --state-dir, the INI's state_dir, else
    server-data in the folder the server starts in. A dev match keeps its
    state in memory unless one is named."""
    named = getattr(args, "state_dir", None) or settings.get("state_dir")
    return named or (None if dev else STATE_DIR)


def backups(args):
    """--backup (an archive a day, or --once now) and --restore (backup.py)."""
    settings = configured(args)
    directory = state_dir(args, settings)
    if args.restore:
        restored = backup.restore(args.restore, directory)
        print(json.dumps({"restored": restored, "from": args.restore, "then": "restart the server"}, indent=2))
        return
    days = Retention.from_settings(settings).backup_days
    # (as a container's first process, SIGTERM ends it only through a handler)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    path = backup.run(directory, args.backup, days, once=args.once)
    if args.once:
        print(json.dumps({"archive": str(path)}, indent=2))


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
    contained = hosting.contained()
    broadcast = beacon.wanted(host, tls is not None, contained, settings.getboolean("beacon", True))
    directory = state_dir(args, settings, bool(dev))
    with contextlib.ExitStack() as stack:
        events = stack.enter_context(open(args.event_log, "a", encoding="utf-8")) if args.event_log else None
        server = Server(name=settings.get("name", "Groundhold"), motd=settings.get("motd", "Hold the road together"),
                        origins=tuple(settings.get("origins", ORIGINS).split()), event_log=events,
                        player_cap=settings.getint("player_cap", 64), maintenance=settings.get("maintenance", ""),
                        party_cap=settings.getint("party_cap") if settings.get("party_cap") else None,
                        dev_match=dev, seed=seed, turn_ms=turn_ms, state_dir=directory,
                        policy=Retention.from_settings(settings),
                        allowlist=tuple(public_id(value) for value in settings.get("allowlist", "").split()),
                        lan=tls is None and not contained, beacon=broadcast)
        port = await server.start(host, port, tls)
        # (handlers first: a harness may stop the server as soon as it reads the line below)
        stop = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                asyncio.get_running_loop().add_signal_handler(sig, stop.set)
        try:
            # (the line a harness waits for: the port, chosen by the system under --port 0)
            print(f"listening port={port} host={host or '*'} path={SPEC['path']}", flush=True)
            announcing = asyncio.create_task(announce(server, host, port, tls is not None, config_path(args),
                                                      directory, broadcast))
            await stop.wait()
            announcing.cancel()
            await asyncio.gather(announcing, return_exceptions=True)
        finally:
            await server.close()


async def announce(server, host, port, secure, config, directory, broadcast):
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
                                    hosting.contained(), os.name == "nt", server.dev_match,
                                    state_dir=directory, beacon=broadcast))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Groundhold server: sequences the turns of multiplayer matches; "
                                                 "it never runs one")
    parser.add_argument("--config", help="The INI to read (default: server.ini in this folder or beside the server, if there is one)")
    parser.add_argument("--host", help="Where to listen (default: every interface; 127.0.0.1 this computer alone)")
    parser.add_argument("--port", type=int, help=f"The port (default {SPEC['port']}; 0: one the system picks, printed as listening port=N)")
    parser.add_argument("--event-log", help="Optional JSONL of connections and matches; contains display names")
    parser.add_argument("--state-dir", help=f"Private directory for the identity key and moderation (default {STATE_DIR}; "
                                            "keep it across upgrades)")
    parser.add_argument("--dev-match", metavar="MODE:SEATS",
                        help="Form a match from the first SEATS players to connect (classic:2), for development")
    parser.add_argument("--seed", type=int, help="With --dev-match: every match's seed (default: a random one each)")
    parser.add_argument("--turn-ms", type=int, help=f"With --dev-match: the turn length in ms (default {SPEC['turn_ms']}); "
                                                    "games pace by it, so 10 plays a match five times faster")
    parser.add_argument("--admin", choices=admin.ACTIONS, help="A local moderation action instead of starting the server")
    parser.add_argument("--identity", help="With --admin: a public identity from --admin list")
    parser.add_argument("--reason", default="", help="With --admin: a local note, never sent to players")
    parser.add_argument("--minutes", type=int, help="With --admin kick: how long it refuses the profile (default 10)")
    parser.add_argument("--backup", metavar="DIR", help="Archive the state directory into DIR once a UTC day, keeping "
                                                        "backup_days days, instead of starting the server")
    parser.add_argument("--once", action="store_true", help="With --backup: one archive now, then exit")
    parser.add_argument("--restore", metavar="ARCHIVE", help="Put the state directory back as a backup's ARCHIVE holds "
                                                             "it, then restart the server")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.once and not args.backup:
        parser.error("--once applies only to --backup")
    try:
        if args.admin:
            directory = state_dir(args, configured(args))
            print(json.dumps(admin.perform(args.admin, directory, args.identity, args.reason, args.minutes), indent=2))
            return
        if args.backup or args.restore:
            backups(args)
            return
        if args.dev_match:
            dev_match_spec(args.dev_match)
        asyncio.run(run(args))
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + "\n")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
