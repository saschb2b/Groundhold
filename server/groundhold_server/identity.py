"""Identity without accounts, and the server's private state (docs/design/
core-loop.md §6.12; server/README.md, Identity and moderation).

The game keeps a random 16-byte key on the device, made once, and never
sends it. For each server it derives a token, HMAC-SHA1 over a domain
string and the server's normalised origin (`client_token` below is the
reference the GDScript derivation follows, shared/net/README.md), and
sends only that in HELLO. The server makes the public identity
`HMAC-SHA256(identity.key, token)[:16]`: stable on one server (one origin,
one token; one `identity.key`, kept across restarts in the state
directory), unlinkable across servers (another origin gives another token,
and another server has another key). Resetting the device key evades a
ban; `allowlist` exists for stricter hosts.

The state directory holds `identity.key` and `moderation.json` (bans,
mutes, kicks), the roster `players.json` of the players connected now, and
what retention.py bounds. Every write takes the directory's lock.

Reused from Cyberworld Endless's server/cyberworld_server/identity.py
(MIT, Sascha Becker): the salted HMAC identity, `state_lock`, the atomic
writes, `moderation.json`'s hot reload that keeps the last good rules,
expiring kicks. The Board's `hidden` list is gone (no Board), and
`client_token` is new: the game's side of the derivation, in Python, from
Cyberworld's network_server_identity.c.
"""

import contextlib
import errno
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import secrets
import tempfile
import time
from urllib.parse import urlsplit

MAX_STATE_BYTES = 1024 * 1024
MODERATION = ("bans", "mutes", "kicks")
KICK_MINUTES = 10
KEY_BYTES = 32
TOKEN_DOMAIN = b"Groundhold identity v1\n"
LOG = logging.getLogger("groundhold.server")
_UNSET = object()


def origin(url):
    """A server's normalised origin, as the game keys its token by:
    `scheme://host:port`, the scheme ws or wss (kept apart, so a plaintext
    server never reuses a TLS server's token), the host in lower case
    without a trailing dot, the port numeric (80 and 443 where none is
    given). None where `url` is no ws:// or wss:// URL."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except (ValueError, TypeError):
        return None
    if parts.scheme not in ("ws", "wss") or not parts.hostname or port == 0:
        return None
    host = parts.hostname.rstrip(".").lower()
    if not host:
        return None
    if ":" in host:
        host = "[" + host + "]"
    return f"{parts.scheme}://{host}:{port or (443 if parts.scheme == 'wss' else 80)}"


def client_token(device_key, url):
    """The token a game sends a server: HMAC-SHA1(device key, domain +
    origin)[:16]. The device key never leaves the device."""
    where = origin(url)
    if where is None or len(device_key) != 16:
        raise ValueError("A 16-byte device key and a ws:// or wss:// URL are required")
    return hmac.new(device_key, TOKEN_DOMAIN + where.encode("ascii"), hashlib.sha1).digest()[:16]


def public_identity(key, token):
    """The public identity of `token` on the server whose key is `key`."""
    return hmac.new(key, token, hashlib.sha256).digest()[:16]


@contextlib.contextmanager
def state_lock(directory):
    """The state directory's lock (its file `moderation.lock`): held by every
    write of moderation.json, by the logs as they are appended or pruned,
    and by a backup or a restore, so a moderator's command never meets a
    half-written file. One process or several."""
    descriptor = os.open(Path(directory) / "moderation.lock", os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "r+b") as stream:
        if os.name != "nt":
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield
            return
        import msvcrt
        # (Windows: the file's first byte, which may be locked past its end
        # and is never read; LK_LOCK gives up after ten seconds, so it is
        # asked again while another holds it, and let go before the close)
        while True:
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
                break
            except OSError as error:
                if error.errno not in (errno.EACCES, getattr(errno, "EDEADLOCK", errno.EDEADLK)):
                    raise
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def write_json(path, value, durable=True):
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if len(encoded) > MAX_STATE_BYTES:
        raise ValueError("Server state exceeds 1 MiB")
    write_text(path, encoded, durable)


def write_text(path, encoded, durable=True):
    """Replace a state file whole (text, or bytes): a temporary file beside
    it, readable by its owner alone, then a rename."""
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix=".server-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb" if isinstance(encoded, bytes) else "w",
                       encoding=None if isinstance(encoded, bytes) else "utf-8") as stream:
            stream.write(encoded)
            stream.flush()
            if durable:
                os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def append_log(directory, name, entry):
    """One entry appended to a JSONL log of the state directory, under its lock."""
    with state_lock(directory):
        with open(Path(directory) / name, "a", encoding="utf-8") as log:
            log.write(json.dumps(entry, separators=(",", ":"), sort_keys=True) + "\n")


def rewrite_log(directory, name, edit):
    """A JSONL log of the state directory rewritten under its lock: `edit`
    takes its entries (a line that is not a JSON object is dropped) and
    returns those to keep. The file is replaced only where that changed it.
    Returns the entries kept and how many lines went."""
    path = Path(directory) / name
    with state_lock(directory):
        try:
            with path.open("r", encoding="utf-8") as log:
                lines = log.read().splitlines()
        except FileNotFoundError:
            return [], 0
        entries = []
        for line in lines:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict):
                entries.append(entry)
        kept = edit([dict(entry) for entry in entries])
        if kept != entries or len(entries) != len(lines):
            write_text(path, "".join(json.dumps(entry, separators=(",", ":"), sort_keys=True) + "\n" for entry in kept))
        return kept, len(lines) - len(kept)


def read_json(path, default):
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            encoded = stream.read(MAX_STATE_BYTES + 1)
    except FileNotFoundError:
        return default
    if len(encoded) > MAX_STATE_BYTES:
        raise ValueError("Server state exceeds 1 MiB")
    value = json.loads(encoded)
    if not isinstance(value, dict):
        raise ValueError("Server state must be a JSON object")
    return value


def public_id(text):
    """A public identity as moderation writes it: 32 lowercase hex digits."""
    if not isinstance(text, str) or len(text) != 32:
        raise ValueError("Public identity must be 32 hexadecimal characters")
    try:
        normalized = bytes.fromhex(text).hex()
        if normalized != text.lower():
            raise ValueError("Noncanonical public identity")
        return normalized
    except ValueError as exc:
        raise ValueError("Public identity must be 32 hexadecimal characters") from exc


def empty_rules():
    return {action: {} for action in MODERATION}


def checked_rules(rules):
    """moderation.json's lists, or ValueError naming what is wrong with them."""
    for action in MODERATION:
        entries = rules.setdefault(action, {})
        if not isinstance(entries, dict) or len(entries) > 4096:
            raise ValueError("Invalid moderation list")
        for identity, entry in entries.items():
            public_id(identity)
            if not isinstance(entry, dict) or not isinstance(entry.get("time"), (float, int)):
                raise ValueError("Invalid moderation entry")
            if not isinstance(entry.get("expires", 0), (float, int)):
                raise ValueError("Invalid kick expiry")
    return rules


def kick_expires(entry):
    """A kick lasts until its expiry; one without lasts the default."""
    return entry.get("expires", entry["time"] + KICK_MINUTES * 60)


def prune_kicks(rules, now):
    kicks = rules.get("kicks", {})
    for identity in [identity for identity, entry in kicks.items() if kick_expires(entry) <= now]:
        del kicks[identity]
    return rules


def prune_moderation(directory, now, forget=None):
    """moderation.json without the kicks that ended, and without `forget`'s
    kick (a ban or a mute stays while it lasts): how many entries went. A
    file that will not load is left as it is; the server keeps its last
    good rules and says so."""
    path = Path(directory) / "moderation.json"
    with state_lock(directory):
        if not path.exists():
            return 0
        try:
            rules = checked_rules(read_json(path, {}))
        except (OSError, ValueError):
            return 0
        count = sum(len(rules[action]) for action in MODERATION)
        prune_kicks(rules, now)
        if forget:
            rules["kicks"].pop(forget, None)
        gone = count - sum(len(rules[action]) for action in MODERATION)
        if gone:
            write_json(path, rules)
        return gone


class IdentityStore:
    """The key public identities are made with, and the moderation rules.
    With a directory, the key is made once and kept there (`identity.key`,
    32 bytes, owner-only) and moderation.json is read from it; without one
    (a dev match, a test) the key lives in memory, `secret` or a random one,
    and there are no rules."""

    def __init__(self, directory=None, secret=None):
        self.directory = Path(directory) if directory else None
        self.secret = secret or secrets.token_bytes(KEY_BYTES)
        self.rules = empty_rules()
        self.stamp = None       # moderation.json's stat when last read
        self.failed = _UNSET    # the stat of a file that would not load, logged once
        self.loads = 0
        if self.directory:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            secret_path = self.directory / "identity.key"
            try:
                descriptor = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                self.secret = secret_path.read_bytes()
            else:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(self.secret)
                    stream.flush()
                    os.fsync(stream.fileno())
            # A bad file at startup refuses the start: there is no good copy to keep.
            self.reload()
        if len(self.secret) != KEY_BYTES:
            raise ValueError("Invalid server identity.key; restore the server backup")

    def identity(self, token):
        return public_identity(self.secret, token)

    def _stamp(self):
        try:
            stat = os.stat(self.directory / "moderation.json")
        except FileNotFoundError:
            return None
        return stat.st_mtime_ns, stat.st_size, stat.st_ino, stat.st_dev

    def reload(self):
        """Read moderation.json now; ValueError or OSError if it cannot be used."""
        if not self.directory:
            return
        stamp = self._stamp()
        rules = checked_rules(read_json(self.directory / "moderation.json", empty_rules())) if stamp else empty_rules()
        self.rules, self.stamp, self.failed = rules, stamp, _UNSET
        self.loads += 1

    def refresh(self):
        """Re-read moderation.json only when its stat changed. Never raises: a
        file that will not load keeps the last good rules and is logged once."""
        if not self.directory:
            return
        try:
            stamp = self._stamp()
        except OSError as exc:
            stamp, error = "unreadable", exc
        else:
            if stamp == self.stamp or stamp == self.failed:
                return
            try:
                self.reload()
                return
            except (OSError, ValueError) as exc:
                error = exc
        if stamp != self.failed:
            self.failed = stamp
            LOG.error("moderation.json not loaded, keeping the last good rules: %s", error)

    def contains(self, action, identity):
        return identity.hex() in self.rules.get(action, {})

    def kick(self, identity, now):
        """The kick on this identity while it lasts, else None."""
        entry = self.rules.get("kicks", {}).get(identity.hex())
        return entry if entry and kick_expires(entry) > now else None

    def roster(self, entries):
        """The local roster for moderators: rewritten often, so not fsynced."""
        if self.directory:
            write_json(self.directory / "players.json", {"updated": time.time(), "players": list(entries)}, durable=False)
