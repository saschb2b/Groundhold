"""What a host needs to know as the server starts (server/README.md, Host
your own): the configuration it read, the addresses players type into
Groundhold's Join panel, read from this computer's own interfaces, and
the lines that say them on the console.

Nothing here sends a packet. The default route's address is read from a UDP
socket connected to a documentation address (RFC 5737's TEST-NET-1), which
connect() alone never sends to; the rest are this computer's name's own
addresses.

Reused from Cyberworld Endless's server/cyberworld_server/hosting.py (MIT,
Sascha Becker) with the renames of docs/design/core-loop.md §6.10 and the
banner's words rewritten for Groundhold.
"""

import contextlib
import ipaddress
from pathlib import Path
import socket
import sys

from .protocol import SPEC

CONFIG = "server.ini"
ENVIRONMENT = "GROUNDHOLD_SERVER_"  # GROUNDHOLD_SERVER_PORT=9000: the INI's port
PROBE = "192.0.2.1"
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
SHOWN = 4   # addresses at most: a computer with many adapters names its likeliest


def program_folder():
    """Where the server's program is: the native build's folder, or the
    zipapp's (or main.py's) own."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(sys.argv[0]).resolve().parent


def find_config(folders):
    """The first server.ini of `folders`, None where none has one."""
    for folder in folders:
        path = Path(folder) / CONFIG
        if path.is_file():
            return path
    return None


def environment_settings(environ):
    """The [server] keys the environment sets, GROUNDHOLD_SERVER_NAME as name;
    '%' kept as typed (the INI's interpolation would read it)."""
    return {key[len(ENVIRONMENT):].lower(): value.replace("%", "%%")
            for key, value in environ.items() if key.startswith(ENVIRONMENT) and len(key) > len(ENVIRONMENT)}


def usable(address):
    """Whether another computer could reach this one at `address`."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return not (ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast)


def route_address():
    """The address this computer's default route leaves from, None offline."""
    with contextlib.suppress(OSError), socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect((PROBE, 9))
        return probe.getsockname()[0]
    return None


def local_addresses(named=True):
    """This computer's IPv4 addresses others can reach it at, the default
    route's first. `named` adds its name's addresses, which can wait on a
    name service: called off the event loop."""
    found = [route_address()]
    if named:
        with contextlib.suppress(OSError, UnicodeError):
            found += [entry[4][0] for entry in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
    addresses = []
    for address in found:
        if address and usable(address) and address not in addresses:
            addresses.append(address)
    return addresses[:SHOWN]


def contained():
    """Whether the server runs in a container (Docker's or Podman's mark),
    where its own addresses are the container's, not the host's."""
    return Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()


def typed(address, port):
    """What a player types for `address`: the port only where it is not the
    game's default (the Join panel adds :8766 and /causeway itself); `port`
    None, the address alone (bracketed if IPv6)."""
    shown = f"[{address}]" if ":" in address else address
    return shown if port in (None, SPEC["port"]) else f"{shown}:{port}"


def banner(name, host, port, secure, addresses, config=None, container=False, windows=False, dev_match=None):
    """The lines the console shows as the server opens."""
    scheme = "wss" if secure else "ws"
    path = SPEC["path"]
    lines = [f'The Groundhold server "{name}" is open on port {port}.']
    if host in LOOPBACK:
        lines += ["Only games on this computer can come in. They type into the Join panel:",
                  f"  {typed('127.0.0.1', port)}    ({scheme}://127.0.0.1:{port}{path})",
                  "(host = 127.0.0.1: leave host empty in server.ini to let other computers in.)"]
    elif secure:
        lines += ["Players type into Groundhold's Join panel the domain its certificate names:",
                  f"  {scheme}://YOUR-DOMAIN:{port}{path}"]
    elif container:
        lines += ["In a container: players type the address of the computer it runs on, with the",
                  f"port published for it ({scheme}://HOST:PORT{path}), or the domain a proxy in front of it serves."]
    else:
        shown = [host] if host and host not in ("0.0.0.0", "::") else addresses
        if shown:
            lines.append("Players type this in Groundhold's Join panel, on this network:")
            lines += [f"  {typed(address, port)}    ({scheme}://{typed(address, None)}:{port}{path})" for address in shown]
        else:
            lines.append("This computer has no network now: players reach it at its address, port " + str(port) + ".")
        lines.append(f"  {typed('127.0.0.1', port)}    (a game on this computer)")
        lines += [f"From the internet: forward TCP port {port} on the router to this computer, or use",
                  "Tailscale or ZeroTier. Browsers need wss:// (a certificate, or a proxy in front)."]
        if windows:
            lines.append("Windows may ask whether to let it through the firewall: allow it on private networks.")
    if dev_match:
        mode, seats = dev_match
        lines.append(f"Dev match: the first {seats} players to connect play {mode} together"
                     f" (start each game with -- --join=ADDRESS).")
    lines.append(f"Settings: {config}" if config else "Settings: the defaults (server.ini beside the server changes them).")
    lines.append("Stopping the container closes the server." if container else "Ctrl+C closes the server.")
    return lines


def announce(lines, stream=None):
    stream = stream or sys.stdout
    stream.write("\n".join(lines) + "\n")
    stream.flush()
