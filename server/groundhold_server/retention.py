"""What the server keeps in its state directory, and for how long
(docs/design/core-loop.md §6.12; server/README.md, What the state keeps).

Kept for as long as the server lives: `identity.key` (the salt of every
public identity, no player's data) and the bans and mutes of
`moderation.json`, until a moderator lifts them. Everything else that
names a player goes by itself:

- `moderation.json`'s kicks once they end;
- `logs/players-DATE.jsonl`, who came under which name (the events that
  carry a public identity or a name), a file a UTC day: `log_days` days,
  0 by default, so none is written unless the host asks for one;
- `players.json`, the roster: the players connected now, rewritten as
  they come and go and emptied when the server stops.

`stats.jsonl`, the daily totals (stats.py), names no player: a line a UTC
day, `stats_days` days. No match is logged to disk: a match's turns live
in memory and go with it.

A pass prunes them at the start and every hour, in a thread, under the
state directory's lock (identity.state_lock). Backups (backup.py) keep
`backup_days` days of the key and the moderation lists.

Reused from Cyberworld Endless's server/cyberworld_server/retention.py
(MIT, Sascha Becker), without the trades' and the Board's keys, and with
Groundhold's defaults: `log_days` 0, `stats_days` 365, `backup_days` 14.
"""

import dataclasses
import json
from pathlib import Path
import re
import time

from .identity import append_log, prune_moderation, rewrite_log, state_lock
from . import stats

DAY = 24 * 3600
PASS = 3600             # seconds between the retention's passes
LIMITS = {"log_days": (0, 365), "backup_days": (1, 365), "stats_days": (0, 3650)}
PERSONAL = ("identity", "name")     # an event's fields the players' log keeps and the console's does not


@dataclasses.dataclass(frozen=True)
class Retention:
    """How long each thing is kept: server.ini's keys of the same names."""
    log_days: int = 0
    backup_days: int = 14
    stats_days: int = 365

    def __post_init__(self):
        for field, (low, high) in LIMITS.items():
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise ValueError(f"{field} must be {low} to {high}")

    @classmethod
    def from_settings(cls, settings):
        """From an INI section (configparser), each key at its default where absent."""
        return cls(**{field.name: settings.getint(field.name, field.default) for field in dataclasses.fields(cls)})


class PlayersLog:
    """The players' log: a JSONL file a UTC day in the state directory's
    `logs/`, each line an event that names a player, kept `days` days
    (none written where 0)."""
    NAME = re.compile(r"players-(\d{4}-\d{2}-\d{2})\.jsonl")

    def __init__(self, directory, days=Retention.log_days):
        self.state = Path(directory) if directory else None
        self.days = days

    @staticmethod
    def name(now):
        return "players-" + time.strftime("%Y-%m-%d", time.gmtime(now)) + ".jsonl"

    def write(self, entry, now):
        if not self.state or not self.days:
            return
        (self.state / "logs").mkdir(mode=0o700, exist_ok=True)
        append_log(self.state, "logs/" + self.name(now), dict(entry, time=round(now, 3)))

    def files(self):
        """The log's files as (date, name), oldest first."""
        try:
            names = sorted(path.name for path in (self.state / "logs").iterdir()) if self.state else []
        except FileNotFoundError:
            return []
        return [(found.group(1), name) for name in names for found in [self.NAME.fullmatch(name)] if found]

    def prune(self, now):
        """The days past `days` deleted (every day where 0): how many files went."""
        if not self.state:
            return 0
        first = self.name(now - (self.days - 1) * DAY)[len("players-"):-len(".jsonl")] if self.days else "9999"
        gone = 0
        with state_lock(self.state):
            for date, name in self.files():
                if date < first:
                    (self.state / "logs" / name).unlink(missing_ok=True)
                    gone += 1
        return gone

    def forget(self, identity):
        """A public identity's lines taken out of every day: how many went."""
        return sum(rewrite_log(self.state, "logs/" + name,
                               lambda entries: [e for e in entries if e.get("identity") != identity])[1]
                   for _, name in self.files())


def console(entry):
    """An event as the console's log shows it: without what names a player."""
    return json.dumps({field: value for field, value in entry.items() if field not in PERSONAL}, separators=(",", ":"))


def personal(entry):
    return any(field in entry for field in PERSONAL)


def apply(directory, policy, now):
    """One pass over the state directory: each kept thing pruned to its
    days. Returns what went, by file, where something did."""
    gone = {"moderation": prune_moderation(directory, now),
            "logs": PlayersLog(directory, policy.log_days).prune(now),
            "stats": stats.prune(directory, now, policy.stats_days)}
    return {kind: count for kind, count in gone.items() if count}
