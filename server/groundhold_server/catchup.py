"""A seat's paced catch-up (docs/design/core-loop.md §6.7; docs/design/contract-m4.md).

A seat that must be brought up to the open turn gets RESYNC, the checkpoint's parts
(protocol.checkpoint_parts) and every turn since: a rejoin (a resume HELLO took its
held seat back, after MATCH_CONFIG with the rejoin flag), a minority after a desync,
and a seat further behind than the latest kept checkpoint (back from a hidden tab, or
loaded after a start without it). They go out at most `catchup_bytes` (2 KB) per
`catchup_ms` (50 ms, one turn), and only while the connection's unsent output is under
`catchup_output` (4 KB): Cyberworld's stands catch-up, proven in the browser. The live
turns sealed meanwhile wait behind them in the same queue, so the game receives every
turn once and in order; the seat's other messages (PONG, LINKS) may pass them. A seat
catching up is never dropped by the output cap (64 KiB): its pacing keeps the output
small.

The match (match.py) makes a CatchUp when it sends RESYNC, queues the turns behind it
from its turn log a little ahead of the pacing (so a catch-up from tick 0 never holds a
whole match's turns at once), and calls pump() once a wake of its turn loop, a turn.

The pacing, a little stricter than Cyberworld's `feed` (which writes while it has
written under the budget, so a tick could reach the budget plus one message):

- a pump writes whole messages in order while they fit the budget: at most
  `catchup_bytes` a pump, but always the first message, so one larger than the budget
  (a TURN of many commands, up to 4,086 bytes) still goes, alone;
- and only while the connection's unsent output with the message stays within
  `catchup_output`, so the output never passes it by more than one message's frame
  header (Match.write adds 2 to 4 bytes to each: the sizes counted here are the
  messages', as the game's own budget counts them); a message larger than that goes
  only into an empty output.

Adapted from Cyberworld Endless's server/cyberworld_server/stands.py (MIT, Sascha
Becker): BUDGET 2,048 a tick while the output is under PACE 4,096, and a slow reader
falling behind rather than holding anyone up.
"""

import collections

from .protocol import SPEC

BYTES = SPEC["catchup_bytes"]
EVERY_MS = SPEC["catchup_ms"]
OUTPUT = SPEC["catchup_output"]


class CatchUp:
    """One seat's messages to pace out, in order.

    `write(data)` sends one message on the seat's connection (Match.write);
    `buffered()` is the connection's unsent output in bytes
    (transport.get_write_buffer_size())."""

    def __init__(self, write, buffered, budget=BYTES, below=OUTPUT):
        self.write, self.buffered = write, buffered
        self.budget, self.below = budget, below
        self.queued = collections.deque()
        self.total = 0          # bytes queued so far
        self.sent = 0           # bytes written so far

    def queue(self, data):
        """A message behind everything queued: RESYNC first, then the parts,
        the turns since the checkpoint, and the live turns sealed until the
        queue runs dry."""
        self.queued.append(data)
        self.total += len(data)

    @property
    def waiting(self):
        """Bytes queued and not written yet."""
        return self.total - self.sent

    def pump(self):
        """Once per catchup_ms: writes the queued messages in order, whole,
        while this pump's bytes stay within `budget` (the first message
        always goes) and the connection's unsent output with the message
        stays within `below` (a message larger than that only into an empty
        output). The bytes are the messages' own: each frame's header, 2 to
        4 bytes, comes on top. Returns the bytes written."""
        spent = 0
        while self.queued:
            data = self.queued[0]
            if spent and spent + len(data) > self.budget:
                break
            unsent = self.buffered()
            if unsent and unsent + len(data) > self.below:
                break
            self.queued.popleft()
            self.write(data)
            spent += len(data)
            self.sent += len(data)
        return spent

    @property
    def done(self):
        """Nothing left to send: the seat's turns go out directly again."""
        return not self.queued
