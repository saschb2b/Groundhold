"""The state directory's backup (server/README.md, Backups and restores):
an archive a UTC day of what the server needs to come back as it was, its
`identity.key` and `moderation.json`, kept `backup_days` days
(retention.py), and its restore.

The players' log, the roster and the daily totals are left out: the
first two are kept for moderation alone and go with their days, and the
totals name no one. An archive is `groundhold-state-YYYYMMDD-HHMMSS.tar.gz`
(UTC), made beside the others under a temporary name and renamed when
whole, read under the state's lock (shared: a read-only mount of the
state takes it too), so it never holds half a moderator's edit.

Reused from Cyberworld Endless's server/cyberworld_server/backup.py (MIT,
Sascha Becker): the Board's `weeks.jsonl` is gone, and the archive's name
says groundhold.
"""

import calendar
import contextlib
import io
import json
import logging
import os
from pathlib import Path
import re
import tarfile
import tempfile
import time

from .identity import KEY_BYTES, state_lock, write_text

FILES = ("identity.key", "moderation.json")
PREFIX = "groundhold-state-"
NAME = re.compile(PREFIX + r"(\d{8})-(\d{6})\.tar\.gz")
MAX_FILE = 64 * 1024 * 1024
LOOK = 3600             # seconds between looks for a day without its archive
RETRY = 60              # seconds before another try after a failure (the server not started yet)
DAY = 24 * 3600
LOG = logging.getLogger("groundhold.server")


@contextlib.contextmanager
def _shared_lock(state_dir):
    """The state's lock, shared, through a read-only file (flock needs no
    write); none where the server has not made its file yet, or on Windows."""
    try:
        descriptor = os.open(Path(state_dir) / "moderation.lock", os.O_RDONLY)
    except OSError:
        yield
        return
    with os.fdopen(descriptor, "rb") as stream:
        if os.name != "nt":
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_SH)
        yield


def archives(backup_dir):
    """A backup directory's archives as (time, path), oldest first."""
    found = []
    for path in Path(backup_dir).iterdir():
        match = NAME.fullmatch(path.name)
        if match:
            found.append((calendar.timegm(time.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S")), path))
    return sorted(found)


def archive(state_dir, backup_dir, now):
    """An archive of the state as it is now: its path."""
    state_dir = Path(state_dir)
    contents = {}
    with _shared_lock(state_dir):
        for name in FILES:
            with contextlib.suppress(FileNotFoundError):
                contents[name] = (state_dir / name).read_bytes()
    if "identity.key" not in contents:
        raise ValueError(f"No identity.key in {state_dir}: not a server's state directory")
    path = Path(backup_dir) / time.strftime(PREFIX + "%Y%m%d-%H%M%S.tar.gz", time.gmtime(now))
    descriptor, temporary = tempfile.mkstemp(prefix=".backup-", dir=backup_dir)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            with tarfile.open(fileobj=stream, mode="w:gz") as tar:
                for name, content in contents.items():
                    info = tarfile.TarInfo(name)
                    info.size, info.mtime, info.mode = len(content), int(now), 0o600
                    tar.addfile(info, io.BytesIO(content))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def due(backup_dir, now):
    """Whether today (UTC) has no archive yet."""
    today = time.strftime("%Y%m%d", time.gmtime(now))
    return not any(path.name[len(PREFIX):][:8] == today for _, path in archives(backup_dir))


def prune(backup_dir, now, days):
    """The archives older than `days` days deleted: their names."""
    gone = [path for made, path in archives(backup_dir) if made < now - days * DAY]
    for path in gone:
        path.unlink(missing_ok=True)
    return [path.name for path in gone]


def run(state_dir, backup_dir, days, once=False, clock=time.time, sleep=time.sleep):
    """With `once`, an archive now (its path). Otherwise, forever: an
    archive the first hour of each UTC day it is not there, and those past
    `days` days pruned, looked at every hour; a failure is logged and
    tried again a minute later."""
    while True:
        now, wait = clock(), LOOK
        try:
            if once or due(backup_dir, now):
                path = archive(state_dir, backup_dir, now)
                LOG.info("%s", json.dumps({"event": "backup", "archive": path.name}, separators=(",", ":")))
            for name in prune(backup_dir, now, days):
                LOG.info("%s", json.dumps({"event": "backup_pruned", "archive": name}, separators=(",", ":")))
        except (OSError, ValueError) as exc:
            if once:
                raise
            LOG.error("The backup failed: %s", exc)
            wait = RETRY
        if once:
            return path
        sleep(wait)


def read(archive_path):
    """An archive's state files, checked: regular files, each once, and a
    server's identity.key. Other members are left out, never extracted."""
    contents = {}
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar:
                name = member.name.removeprefix("./")
                if name not in FILES:
                    continue
                if not member.isfile() or name in contents or member.size > MAX_FILE:
                    raise ValueError(f"{archive_path}: {member.name} is not a state file")
                contents[name] = tar.extractfile(member).read()
    except (tarfile.TarError, EOFError) as exc:
        raise ValueError(f"{archive_path} is not a backup's archive: {exc}") from exc
    if len(contents.get("identity.key", b"")) != KEY_BYTES:
        raise ValueError(f"{archive_path} holds no server identity.key")
    return contents


def restore(archive_path, state_dir):
    """The state put back as an archive holds it: its files written whole,
    and those of FILES it lacks removed (they were not there when it was
    made). The server reads the key only as it starts: restart it then.
    Returns the names restored."""
    contents = read(archive_path)
    state_dir = Path(state_dir)
    if not state_dir.is_dir():
        raise ValueError(f"{state_dir} is not a state directory")
    with state_lock(state_dir):
        for name in FILES:
            if name in contents:
                write_text(state_dir / name, contents[name])
            else:
                (state_dir / name).unlink(missing_ok=True)
    return sorted(contents)
