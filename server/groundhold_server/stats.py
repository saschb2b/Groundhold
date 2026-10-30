"""The server's daily totals (docs/design/core-loop.md §6.10, §6.12;
server/README.md, The daily totals): counts of each UTC day, with no
personal data, served at `GET /stats`.

A day counts its joins; its distinct public identities, as a number only
(a set held in memory for the day and dropped at its end, never written
and never served); the most players online at once; the matches started
and finished per mode (finished: ended by an agreed result); the desyncs,
the health gauge of the lockstep choice (every disagreement the hash or
result referee found, a minority of three included); the reconnects (a
party seat taken back after a drop); the caretaker seats (each seat of a
match the caretaker played, once a match); and the HELLOs by the protocol
version they carry, those of another version refused (so the older and
newer games that tried show here).

Each day is written once, a line of `stats.jsonl` in the state directory,
at its end or as the server stops. A restart on the same day takes that
day's line up again and writes it over. The retention's pass keeps
`stats_days` days (retention.py; none written where 0), and `GET /stats`
serves today so far and the last 30 days.

Adapted from Cyberworld Endless's server/cyberworld_server/stats.py (MIT,
Sascha Becker): the day's line, the identities as a count, the restart
rule, the pruning; the counts are Groundhold's.
"""

import json
from pathlib import Path
import time

from .identity import rewrite_log, state_lock

LOG = "stats.jsonl"
SHOWN = 30              # the days /stats serves besides today
VERSIONS = 16           # protocol versions counted apart; the rest as "other"
COUNTS = ("joins", "peak", "desyncs", "reconnects", "caretaker_seats")
TABLES = ("started", "finished", "versions")     # per mode, per mode, per protocol version


def day_of(now):
    return time.strftime("%Y-%m-%d", time.gmtime(now))


def fresh(day):
    return dict({"day": day, "identities": 0}, **{field: 0 for field in COUNTS}, **{table: {} for table in TABLES})


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def checked(entry):
    """A line read back: only the totals' own fields, numbers and the day, or None."""
    if not isinstance(entry, dict) or not isinstance(entry.get("day"), str) or len(entry["day"]) != 10:
        return None
    out = fresh(entry["day"])
    for field in COUNTS + ("identities",):
        out[field] = _count(entry.get(field, 0))
    for table in TABLES:
        found = entry.get(table, {})
        out[table] = {str(key): value for key, value in found.items() if _count(value) == value} \
            if isinstance(found, dict) else {}
    return out


def prune(directory, now, days):
    """The days past `days` taken out of stats.jsonl (every day where 0):
    how many lines went."""
    if not directory:
        return 0
    first = day_of(now - (days - 1) * 86400) if days else "9999"
    return rewrite_log(directory, LOG, lambda entries: [e for e in entries if str(e.get("day", "")) >= first])[1]


class Daily:
    """Today's totals in memory, the days written before them, and the
    file they go to (`directory`'s stats.jsonl, kept `days` days)."""

    def __init__(self, directory=None, days=365, clock=time.time):
        self.directory = Path(directory) if directory else None
        self.days, self.clock = days, clock
        self.today = fresh(day_of(clock()))
        self.seen = set()       # today's public identities: counted, never written
        self.before = 0         # ... and those of today's line before a restart
        self.past = []          # the days written, oldest first (the last SHOWN kept)
        self.load()

    def load(self):
        if not self.directory:
            return
        try:
            with state_lock(self.directory), open(self.directory / LOG, encoding="utf-8") as log:
                lines = log.read().splitlines()
        except FileNotFoundError:
            return
        for line in lines:
            try:
                entry = checked(json.loads(line))
            except ValueError:
                continue
            if not entry:
                continue
            if entry["day"] == self.today["day"]:
                self.today, self.before = entry, entry["identities"]
            elif entry["day"] < self.today["day"]:
                self.past.append(entry)
        self.past = sorted(self.past, key=lambda entry: entry["day"])[-SHOWN:]

    # ---- the counts ----

    def tally(self, table, key):
        found = self.today[table]
        key = str(key)
        if table == "versions" and key not in found and len(found) >= VERSIONS:
            key = "other"
        found[key] = found.get(key, 0) + 1

    def hello(self, version):
        self.tally("versions", version)

    def join(self, identity, players):
        self.today["joins"] += 1
        self.seen.add(bytes(identity))
        self.today["peak"] = max(self.today["peak"], players)

    def count(self, field):
        if field not in COUNTS or field in ("joins", "peak"):
            raise ValueError(field)
        self.today[field] += 1

    def snapshot(self):
        """Today so far: its totals, the identities as a number."""
        day = dict(self.today, **{table: dict(self.today[table]) for table in TABLES})
        day["identities"] = self.before + len(self.seen)
        return day

    def public(self):
        """GET /stats: today so far and the last SHOWN days, oldest first."""
        return {"today": self.snapshot(), "days": list(self.past[-SHOWN:])}

    # ---- the days ----

    def rollover(self):
        """A new UTC day begun: the day ended (to write), and the new one's
        totals begun, the identities dropped; None the same day."""
        day = day_of(self.clock())
        if day == self.today["day"]:
            return None
        ended = self.snapshot()
        self.past = (self.past + [ended])[-SHOWN:]
        self.today, self.seen, self.before = fresh(day), set(), 0
        return ended

    def write(self, entry):
        """A day's line written over that day's earlier one (a restart's),
        the days past `days` pruned with it; nothing where `days` is 0."""
        if not self.directory or not self.days:
            return
        first = day_of(self.clock() - (self.days - 1) * 86400)
        line = {field: entry[field] for field in fresh("").keys()}

        def edit(entries):
            kept = [e for e in entries if str(e.get("day", "")) >= first and e.get("day") != line["day"]]
            return sorted(kept + [line], key=lambda e: str(e.get("day", "")))

        (self.directory / LOG).touch(mode=0o600, exist_ok=True)
        rewrite_log(self.directory, LOG, edit)
