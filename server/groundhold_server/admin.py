"""Local-only moderation (docs/design/core-loop.md §6.12; server/README.md,
Identity and moderation). File access to the private state is authority:
there is no remote admin endpoint.

`list` shows the roster of the players connected now and the moderation
lists; `ban`, `unban`, `mute`, `unmute`, `kick` (`--minutes`, 1 to 10,080)
and `unkick` change `moderation.json`, which the running server reads
again within a second; `forget` answers a player's request to be removed:
the public identity out of every record that names it (the players' log,
a kick), but a ban or a mute, which stays while it lasts.

A ban refuses the profile (ERROR 10) and drops its sessions; a kick drops
them and refuses the profile until it ends (ERROR 14 with the minutes
left); a mute drops the profile's signals (`SIGNAL` commands never reach
the turns), the one thing a player can show others besides a name.

Reused from Cyberworld Endless's server/cyberworld_server/admin.py (MIT,
Sascha Becker), without `hide` and `unhide` (no Board) and without the
trades' log.
"""

import argparse
import json
from pathlib import Path
import time

from .identity import (KICK_MINUTES, kick_expires, prune_kicks, prune_moderation, public_id, read_json,
                       state_lock, write_json)
from .retention import PlayersLog

ACTIONS = ("list", "ban", "unban", "mute", "unmute", "kick", "unkick", "forget")
KICK_MAX_MINUTES = 7 * 24 * 60


def perform(action, directory, identity=None, reason="", minutes=None):
    directory = Path(directory)
    if action not in ACTIONS:
        raise ValueError("The actions are " + ", ".join(ACTIONS))
    if not (directory / "identity.key").is_file():
        raise ValueError("Use the running server's private state directory")
    if minutes is not None and action != "kick":
        raise ValueError("--minutes applies only to kick")
    if action == "list":
        return {"roster": read_json(directory / "players.json", {}),
                "moderation": prune_kicks(read_json(directory / "moderation.json", {}), time.time())}
    if not identity:
        raise ValueError("An identity from the local player roster is required")
    identity = public_id(identity)
    if action == "forget":
        return forget(directory, identity)
    if len(reason) > 160 or any(ord(c) < 32 for c in reason):
        raise ValueError("Reason must be at most 160 characters with no control characters")
    minutes = KICK_MINUTES if minutes is None else minutes
    if not 1 <= minutes <= KICK_MAX_MINUTES:
        raise ValueError(f"A kick lasts 1 to {KICK_MAX_MINUTES} minutes; ban for longer")
    with state_lock(directory):
        now = time.time()
        rules = read_json(directory / "moderation.json", {"bans": {}, "mutes": {}, "kicks": {}})
        prune_kicks(rules, now)
        target = {"ban": "bans", "mute": "mutes", "kick": "kicks"}[action.removeprefix("un")]
        entries = rules.setdefault(target, {})
        if action.startswith("un"):
            entries.pop(identity, None)
        else:
            entries[identity] = {"time": now, "reason": reason}
            if action == "kick":
                entries[identity]["expires"] = now + minutes * 60
        if len(entries) > 4096:
            raise ValueError("Moderation list is full (4096 entries)")
        write_json(directory / "moderation.json", rules)
    result = {"action": action, "identity": identity, "applies_within_seconds": 1}
    if action == "kick":
        result["expires"] = kick_expires(entries[identity])
    return result


def forget(directory, identity):
    """A public identity taken out of the players' logs and moderation.json's
    kicks. The backups hold it until they age out."""
    logs = PlayersLog(directory).forget(identity)
    moderation = prune_moderation(directory, time.time(), forget=identity)
    return {"action": "forget", "identity": identity, "logs": logs, "moderation": moderation}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=ACTIONS)
    parser.add_argument("identity", nargs="?")
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--reason", default="")
    parser.add_argument("--minutes", type=int, help=f"How long a kick refuses the profile (default {KICK_MINUTES})")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(perform(args.action, args.state_dir, args.identity, args.reason, args.minutes), indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + "\n")
