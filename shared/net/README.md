# Groundhold's wire protocol, version 1

`protocol.json` is the contract between the game and the server
(`docs/design/core-loop.md` §6.5). The server loads it as package data
(`server/groundhold_server/protocol.py` builds its codec from the layouts); the
game reads it at runtime with `FileAccess.get_file_as_string("res://shared/net/protocol.json")`,
so a desktop or web export must include `shared/net/*.json` in its include filter.
The byte tables below are written from it by `python3 server/tools/protocol_tables.py`;
a server test fails when they are stale.

## Transport

- One WebSocket port: **8766**, path **`/causeway`**, subprotocol **`groundhold.v1`**.
  Desktop on a LAN uses `ws://`; online, desktop and browser use `wss://` (TLS at the proxy).
- **One message per binary frame.** A game's frames are masked, unfragmented and at most
  **1,100 bytes** (`max_message`); a larger one, a fragment, a text frame or an unmasked frame ends
  the connection with `ERROR`. Server messages are at most 65,535 bytes.
- The upgrade also accepts another version's `groundhold.vN`, so an older or newer game can say
  its `HELLO` and hear which side is behind (`ERROR` 2 or 17) rather than see the upgrade refused.
- A browser's `Origin` must be on the server's allowlist (default `https://saschb2b.github.io`);
  a native game sends none and passes. This is not player authentication.
- `GET /health` on the same port answers JSON: `status`, `protocol`, `name`, `motd`, `players`,
  `player_cap`, `matches`, `maintenance`, `dev_match`, `turn_ms`.

## Encoding

Every message is a big-endian record: a one-byte type (its id below), then its fields in order.
Every reader checks the exact length and bounds every field; anything else is an `ERROR` and the
connection closes.

| Kind | Bytes |
|---|---|
| `u8`, `u16`, `u32`, `u64`, `i32` | unsigned or signed integers, big-endian |
| `bN` (shown as "N bytes") | exactly N raw bytes: tokens, identities, hashes, party codes |
| `s8` | u8 length, then that many bytes of UTF-8 (each field names its most) |
| `d16` | u16 length, then that many bytes (`CHECKPOINT_PART`'s data, at most 1,024) |
| `l8` | u8 count (each list names its most), then that many records of the listed fields |
| `switch` | `PARTY` only: its `op` picks the fields that follow (`party_ops`) |

In GDScript: `StreamPeerBuffer` with `big_endian = true`; `get_u32()` and friends return `int`.
Hashes, the rules hash, tokens and identities are kept as `PackedByteArray` (8 or 16 bytes), never
as an `int`, so no value needs 64 unsigned bits. `JSON.parse_string` gives every number as a
`float`; every number in `protocol.json` and the transcripts is below 2^53, so `int()` is exact.

**Names** match `[A-Za-z0-9][A-Za-z0-9 _-]{0,15}` (ASCII, 1 to 16 characters, sent as typed).

## The handshake

1. The game opens the socket and sends `HELLO` within 5 s of connecting.
2. The server checks, in order: the version (`ERROR` 2 when the game is older, 17 when the server is),
   the shape, a non-zero token (9), the name (5); then maintenance (16, with the host's line), a ban
   (10), the allowlist (11), a kick (14, with the minutes left) and room (7). A refusal is `ERROR`,
   then the close: the server reads and drops whatever the game
   still sends until the game closes (a game closes on `ERROR`), at most `linger_ms` (1 s) and at
   most a hub bucket's burst of frames (40), and only then sends its close frame (1008). A close or
   a reset right behind `ERROR` could take it away unread; this way every refusal, here or later
   (`ERROR` 6, 8), reaches the player with its reason. A lingering connection holds one of the
   `pending_cap` (16) places of unfinished handshakes, so refusals cannot pile up unread work.
3. Otherwise `WELCOME`: the session id, the public identity (`HMAC-SHA256(server key, token)[:16]`:
   stable on this server, unlinkable across servers), the turn length, the hash interval and the
   server's name and line. Flag `dev_match` says the server forms a match from the first `HELLO`s
   (`--dev-match`), so `MATCH_CONFIG` follows with no hub.
4. `PING` every 2 s carries the game's clock and its last measured round trip; `PONG` echoes the
   clock and says the open turn. 15 s without any message closes the connection.
5. `BYE` (or a close frame) is a goodbye: in a match it is `LEFT`, in a party it frees the row at once.

**The token** (identity without accounts, design §6.12). The game makes a random 16-byte device key
once and never sends it. For each server it sends `token = HMAC-SHA1(device key, "Groundhold identity
v1\n" + origin)[:16]`, where the origin is `scheme://host:port` of the URL it connects to: the scheme
`ws` or `wss` (kept apart, so a plaintext server never reuses a TLS server's token), the host in lower
case without a trailing dot (an IPv6 address in brackets), the port numeric, 80 for `ws` and 443 for
`wss` where the URL names none. One server, one token; another server, another. Reference
(`client_token` in `server/groundhold_server/identity.py`): the device key `000102...0f` and
`wss://groundhold.saschb2b.com/causeway` give the origin `wss://groundhold.saschb2b.com:443` and the
token `5c0d37e02b41a1060b3bfe6a5c10af52`; `ws://192.168.1.20:8766/causeway` gives
`b6c7c14ce43e4cf09ae7c7c89131b15d`. The server keeps its `identity.key` in its state directory, so a
token's public identity stays the same across restarts.

## The hub

A server without `--dev-match` has a hub: parties by code, their countdown, their matches and the
way back. `PARTY_STATE` is the whole party, sent to every member after every change; its `you` is
the recipient's own member number (255 outside a party), so a game knows its row. An op the
party's rules do not allow now (a member's start, an op from a former leader, a phase that moved
on) is answered to the asker alone with the party as it is, so a game always shows the truth; an
op outside its limits (an unknown mode or Builder, `on` or `team` past 1, a member past 3) ends the
connection with `ERROR` 6. A player in no party (after `leave`, a removal, or an op with no party)
gets the **no-party state**: a code of five zero bytes, leader and `you` 255, no members.

| Op | Who | What |
|---|---|---|
| `create(mode)` | anyone | a new party with a new code, the creator its leader (out of any party first) |
| `join(code)` | anyone | the party with that code: see Codes below |
| `leave` | a member | out; the member who joined earliest leads if the leader left |
| `remove(member)` | the leader | that member out with `NOTICE removed`; its identity cannot rejoin that code |
| `mode(mode)` | the leader | every Ready cleared; a two-team mode lays the teams out alternately by joining order |
| `builders(main, backup)` | a member, its own | its own Ready cleared; allowed in a match too (for the next one) |
| `ready(on)` | a member, its own | the leader's Ready is its Start, so the leader needs none |
| `team(member, team)` | the leader, two-team modes | that member's Ready cleared |
| `open(on)` | the leader | the flag (`PARTY_STATE` flags, the beacon's count); the public queue comes in M6 |
| `start` | the leader | forming: the countdown, if every other member is Ready, everyone has one rules hash, the party is a size the mode takes (`seats` in `modes`) and, in a two-team mode, two equal teams. Loading: start without the slow seats (the barrier, below) |
| `cancel` | any member | the countdown stops; Ready stays |

**Codes** are five symbols of `23456789BCDFGHJKMNPQRSTVWXYZ` sent as ASCII; games show them as
`K7Q-4M`. The server reads them leniently too (lower case is upper case). A join answers `NOTICE`
`no_such_party` (argument 0) for a code it does not know or that is not a code, `party_full` (the
argument: members) for four members, and `removed` for an identity the leader removed. Each
connection has five lookups at once and one more every 5 s: past that a join makes no lookup and
answers `no_such_party` with the seconds until the next one as the argument. A party whose last
member left keeps its code 15 minutes (anyone may join it again and lead it); then it is gone.
A server keeps at most `party_cap` parties (four per `player_cap` by default) and an identity at
most one empty one (leaving another empty drops the one it left before). A `create` at the cap
drops the empty party that has waited longest; with none empty it answers `NOTICE parties_full`
(argument 0) and the player keeps the party it has.

**Members** are numbered 0 to 3 (the row, kept while they stay; a newcomer takes the lowest free
one). Their `state`: `here`; `ready`; `away` (the connection dropped: the row is held 40 s,
"reconnecting"); `needs_reload` (another rules hash than the newest build's: the highest
`build_seq`, the leader's on a tie; the party cannot start, and the member gets `NOTICE
needs_reload` with its number when it starts to need one); `in_match` (in the party's match, or on
its results plate). A joiner in a two-team mode goes to the smaller team.

**Phases**: `forming`; `countdown` (`countdown_ms` is what is left when the state is sent: 3,000 at
the start); `loading`; `in_match`; `results`; `queued` is not used before the queue (M6). Anything
that breaks the start's rule stops the countdown: a cancel, an un-Ready, a Builder, team or mode
change, a join, a leave, a drop. At its end the party's match forms: `PARTY_STATE` (`loading`, each
member `in_match`), then `MATCH_CONFIG` to each member, one seat each in seat order (by team, then by
member number); a seat's Builder is its member's main. (Until M2 merges, the contract has matches
field a Lamplighter for a Builder the game cannot play yet, `docs/design/contract-m2m3.md` §7: a rule
every game applies alike, so they stay in step; the server names the main either way.)

**Held rows.** A connection that drops without a goodbye keeps its row 40 s, `away`. A `HELLO` with
the `resume` flag from the same public identity takes it back (row, team, Builders; Ready cleared),
and so does a `join` of the same code by that identity; the others see it `here` again. A
goodbye or a moderator's removal frees the row at once. A row whose member's match still runs is
kept until 40 s after the match ends.

**No public queue yet.** `QUEUE` is answered with `QUEUE_STATE` idle (state 0, no caretaker offer)
whatever its op, `ACCEPT` is let pass, and the server never sends `MATCH_FOUND`: the queue, Match
Found and strangers' matches are M6.

## A match

**Barrier.** `MATCH_CONFIG` names the match, mode, map, seed, rules hash, the recipient's seat and
every seat (team, Builder, flags, name). Each game reports `LOADING` (per mille) and then
`LOADED(rules_hash, tick-0 hash)`; every change goes out as `LOAD_STATE`. When every connected seat is
`LOADED` with equal tick-0 hashes and at least 4 s have passed since `MATCH_CONFIG` (0 s with one
human), the server sends `START(1500)`: turn 0 opens 1.5 s later. Tick-0 hashes apart: `NOTICE`
(`tick0_mismatch`, the differing seat, or 255 without a majority) and `MATCH_END` (aborted). A seat
whose connection is gone at the start begins `AWAY` (or `LEFT`) in turn 0.

The barrier's timers run from `MATCH_CONFIG` on the server's clock (design §6.6):

| Time | What happens |
|---|---|
| 0 to 4 s | the minimum: nothing starts before it (0 s with one human) |
| 15 s | each seat not yet `LOADED` is `slow` (and stays so as its `LOADING` comes, until its `LOADED`); `LOAD_STATE` goes out with `seconds` 15 |
| 30 s | a party's match: `LOAD_STATE` with `seconds` 30, and from now the leader's `PARTY start` starts without the seats still loading (at least one seat loaded; before 30 s, or from anyone else, it is refused with the party's state) |
| 45 s | a match of strangers (the queue's, M6, or `--dev-match`'s): it starts by itself with the seats loaded |
| 120 s | every seat still not `LOADED` is out: `MATCH_END` (aborted, reason `timeout`) to its game and `LEFT` in the turns; with nobody loaded the match ends there (a strangers' match after `NOTICE match_dissolved`) |

The seats loaded at a start without the others must agree on the tick-0 hash, as at any start. A seat
started without its player begins `AWAY` in turn 0 (the caretaker plays it) and gets `START` and the
turns like any other; its `LOADING`, `PING`s and other messages do not bring it back. Its `LOADED`
does: with the match's rules hash and the tick-0 hash the seats agreed, `BACK(seat)` follows in the
next turn; with another, `NOTICE tick0_mismatch` (its seat) and `MATCH_END` (aborted, reason
`tick0_mismatch` or `rules_mismatch`) to it, and `LEFT` in the turns.

**Seats** are 0-based on the wire (0 to 3; the game shows 1 to 4). A party's seats are its members in
order of team, then member number; a dev match's team is `seat × teams div seats`. Either way a Race
of four is seats 0 and 1 against 2 and 3. Seat 255 is the server.

**Turns.** Turn *k* covers ticks 3*k* to 3*k* + 2 and closes at `origin + (k + 1) × 50 ms`, an
absolute deadline on the server's monotonic clock; a late server closes every missed turn at once,
in order, so the turn count always tracks wall time. `TURN(k)` lists the commands that reached the
server while turn *k* was open (the lowest turn not yet sent), each stamped with the sender's seat
(from the connection, never from the message) and its sequence number:

1. system commands first, in the order the server made them (their `seq` is the match's own count);
2. then the seats in rotation from seat `k mod seats`, so nobody always wins a contested cell;
3. each seat's commands by sequence number.

A game executes `TURN(k)` at the start of tick 3*k*, in listed order, and simulates tick *t* only
once `TURN(t div 3)` has arrived. An empty `TURN` is 6 bytes. A `TURN` holds at most 255 commands;
more wait for the next turn, in order.

**Commands.** `CMD(seq, type, a, b, c)`. The server checks only the shape (a type a game may send,
each argument in its range below), the sequence (strictly increasing per seat; the first may be
anything) and the rate; the simulation validates everything else identically on every game and
turns a refused command into a `REJECTED` event. Simulation ids start at 1, so 0 means "none"
(`SIGNAL`'s target). A command outside its shape ends the connection with `ERROR` 6.

**Hashes.** Every 60 ticks each game sends `HASH(tick, 8 bytes, flags)`: the tick is a multiple of
60, at most 3 × the turns sealed, and increases per seat; flags hold only `checkpoint`. Once every present seat has reported a tick, or
2 s after the first report, the server compares: all equal, or with three seats or more a strict
majority, is agreement. Two seats apart (or no majority) end the match `desynced`
(`MATCH_END`, reason `desync`, the tick). A report arriving after its tick was agreed is compared
with the agreed hash. (With three seats or more, a minority is only logged in M1; M4 sends it
`RESYNC`.)

**Absence.** A seat silent for 5 s (no message of any kind) gets `AWAY(seat)` in the next turn, and
the caretaker plays it. The next message on the same connection brings `BACK(seat)`; the simulation
hands control back at the next build window. `LEAVE_MATCH` or `BYE` brings `LEFT(seat)`: the caretaker
keeps the seat to the end. A dropped connection is held as `AWAY` (the resume `HELLO` comes in M4).
The match ends when no seat has a connection.

**The end.** Each game sends `RESULT(final tick, hash, outcome per team)` once, its tick no later than
3 × the turns sealed and no earlier than its own last `HASH`. The seats present now vote (a seat away,
left or dropped neither votes nor holds the end up): a result that a strict majority of them sent (all
of them, with one or two seats) ends the match, and `MATCH_END` tells each seat its team's outcome.
Short of that, the match plays on while a majority can still form from the present seats with no
result yet that are still playing (a `HASH` in the last `result_wait_ms`, 10 s): one whose last
`HASH` is at or before a claimed final tick may yet agree with that claim (once it hashes past the
tick, its simulation ran past the claimed end and it disagrees), and together they may agree on an
end of their own. So with three seats or more a claim the others ran past is outvoted while they
play on; with two, a lone claim the other ran past ends the match. When no majority can form any
more, the match ends `desynced` (reason `desync`, the earliest claimed tick), never with a claim's
outcome: one seat's word never decides for another that is present, and a seat that keeps talking
but stops hashing holds the end up 10 s at most. At the
server's hard cap (`match_cap_ms`, 60 minutes) it seals `TIMEOUT` into the turn and no more turns; if
no result is agreed 10 s later, `MATCH_END` is `aborted` with reason `timeout`. After `MATCH_END` the
connection stays; match messages already on their way are let pass.

**Back to the party.** When a party's match ends, `PARTY_STATE` says `results`: each member who was
in the match at its end stays `in_match` (on the results plate). `LEAVE_MATCH` after `MATCH_END`
(Play again, or Hub) brings it back: `here`, its Ready cleared; so does a `PARTY ready` or `builders`
from the plate. When everyone is back the phase is `forming`, with the party's code, mode, open
seats, teams and Builders as they were. A member who sends `LEAVE_MATCH` during the match is back in
the hub at once (the caretaker keeps its seat). A match that ends before it starts (tick-0 hashes
apart, nobody loaded at the ceiling) brings everyone back at once, with no results plate.

**Links.** Every 2 s `LINKS` gives each seat's round trip (from its `PING`) and flags: `hidden` (its
`VISIBILITY`) and `silent` (away, left or dropped).

**Gaps.** `TURN_REQUEST(first missing)` re-sends the sealed turns from there, at most
`turn_request_turns` (100, 5 s of turns) per request, never one below the seat's last `HASH` tick / 3
(it holds those already). A game asks again for the same gap every `turn_request_ms` (500 ms), and
for a gap that moved (the last answer came) after half of that and one turn more; the server answers
a seat at most once per half of `turn_request_ms` and ignores requests in between, so one message
never costs more than 100 turns of work and a game that keeps to its pace is never ignored (a
repair of 100 turns every 300 ms).

**Rate limits**, token buckets per connection (burst, refill per second): `cmd` 10 and 5 (`CMD`);
`net` 150 and 120 (`PING`, `HASH`, `LOADING`, `CHECKPOINT_PART`, `TURN_REQUEST`, `VISIBILITY`); `hub`
40 and 30 (everything else, WebSocket pings and closes too). An empty bucket ends the connection
with `ERROR` 8, and a seat is held. A connection whose unsent output passes 64 KiB is dropped, and
its seat is held.

**Not served yet** (their layouts are fixed here): `CHECKPOINT_PART` (M4) is answered with `ERROR` 1;
the server never sends `MATCH_FOUND` (the queue, M6), `CHECKPOINT_ASK` or `RESYNC` (M4). A `--dev-match`
server has no hub: `PARTY`, `QUEUE` and `ACCEPT` are `ERROR` 1 there. One profile may connect twice,
because two windows on one computer share their `user://` key (`ERROR` 12 and a match seat's resume
come with M4's reconnect; M3's resume bit takes back a party row).

## The LAN beacon

A server on a home network (not in a container, not behind TLS, not on 127.0.0.1 alone, `beacon` not
turned off) broadcasts one UDP datagram a second of its clock to `255.255.255.255` on `beacon_port`
(8767), all big-endian:

| Bytes | Field |
|---|---|
| 4 | `GHB1` |
| 2 | protocol version |
| 2 | the WebSocket port |
| 1 | open parties: parties with open seats on, a seat free and no match under way (at most 255) |
| 1 + n | the server's name (u8 length, UTF-8, at most 64 bytes) |

The datagram is exactly that long. A game keys servers by the datagram's source address and the port,
lists only those whose version is its own (another version could not play there), and drops a server
it has not heard for 3 s. `server/groundhold_server/beacon.py`'s `parse` and `listed` are the reference.

## Messages

<!-- protocol.json tables: begin (server/tools/protocol_tables.py writes them) -->

#### Connection and hub

| Id | Message | Dir | Bucket | Bytes | Payload after the type byte |
|---|---|---|---|---|---|
| 1 | `HELLO` | C→S | hub | 33 to 49 | u16 version, u32 build_seq, 8 bytes rules_hash, 16 bytes token, u8 flags, u8 + UTF-8 name (≤ 16 bytes) |
| 2 | `WELCOME` | S→C |  | 29 to 253 | u32 session, 16 bytes identity, u16 turn_ms, u8 turn_ticks, u16 hash_every, u8 flags, u8 + UTF-8 server_name (≤ 64 bytes), u8 + UTF-8 motd (≤ 160 bytes) |
| 5 | `ERROR` | S→C |  | 3 to 123 | u8 code, u8 + UTF-8 text (≤ 120 bytes) |
| 6 | `PING` | C→S | net | 7 | u32 client_ms, u16 rtt_ms |
| 7 | `PONG` | S→C |  | 9 | u32 client_ms, u32 turn |
| 14 | `NOTICE` | S→C |  | 6 | u8 code, u32 argument |
| 15 | `BYE` | both | hub | 1 | nothing |
| 20 | `PARTY` | C→S | hub | 2 to 7 | u8 op; then by op: create (1): u8 mode; join (2): 5 bytes code; leave (3): nothing; remove (4): u8 member; mode (5): u8 mode; builders (6): u8 main, u8 backup; ready (7): u8 on; team (8): u8 member, u8 team; open (9): u8 on; start (10): nothing; cancel (11): nothing |
| 21 | `PARTY_STATE` | S→C |  | 16 to 160 | 5 bytes code, u8 mode, u8 flags, u8 leader, u8 you, u8 phase, u32 countdown_ms, u8 n, then n × members [u8 member, u8 team, u8 main, u8 backup, u8 state, u16 rtt_ms, u32 build_seq, 8 bytes rules_hash, u8 + UTF-8 name (≤ 16 bytes)] (n ≤ 4) |
| 22 | `QUEUE` | C→S | hub | 2 | u8 op |
| 23 | `QUEUE_STATE` | S→C |  | 7 | u8 state, u32 elapsed_ms, u8 caretaker_offer |
| 24 | `MATCH_FOUND` | S→C |  | 12 | u32 match, u8 mode, u8 seats, u8 accepted, u32 ms_left |
| 25 | `ACCEPT` | C→S | hub | 6 | u32 match, u8 yes |

#### Loading

| Id | Message | Dir | Bucket | Bytes | Payload after the type byte |
|---|---|---|---|---|---|
| 30 | `MATCH_CONFIG` | S→C |  | 21 to 105 | u32 match, u8 mode, u8 map, u32 seed, 8 bytes rules_hash, u8 your_seat, u8 n, then n × seats [u8 seat, u8 team, u8 builder, u8 flags, u8 + UTF-8 name (≤ 16 bytes)] (n ≤ 4) |
| 31 | `LOADING` | C→S | net | 3 | u16 per_mille |
| 32 | `LOAD_STATE` | S→C |  | 4 to 20 | u8 n, then n × seats [u8 seat, u16 per_mille, u8 state] (n ≤ 4), u16 seconds |
| 33 | `LOADED` | C→S | hub | 17 | 8 bytes rules_hash, 8 bytes tick0_hash |
| 34 | `START` | S→C |  | 3 | u16 ms_until_turn0 |

#### In a match

| Id | Message | Dir | Bucket | Bytes | Payload after the type byte |
|---|---|---|---|---|---|
| 40 | `CMD` | C→S | cmd | 16 | u16 seq, u8 type, i32 a, i32 b, i32 c |
| 41 | `TURN` | S→C |  | 6 to 4086 | u32 turn, u8 n, then n × commands [u8 seat, u16 seq, u8 type, i32 a, i32 b, i32 c] (n ≤ 255) |
| 42 | `HASH` | C→S | net | 14 | u32 tick, 8 bytes hash, u8 flags |
| 43 | `CHECKPOINT_ASK` | S→C |  | 5 | u32 tick |
| 44 | `CHECKPOINT_PART` | both | net | 11 to 1035 | u32 tick, u16 part, u16 parts, u16 + bytes data (≤ 1024) |
| 45 | `RESYNC` | S→C |  | 9 | u32 checkpoint_tick, u32 first_turn |
| 46 | `TURN_REQUEST` | C→S | net | 5 | u32 first_missing |
| 47 | `VISIBILITY` | C→S | net | 2 | u8 hidden |
| 48 | `RESULT` | C→S | hub | 14 to 16 | u32 tick, 8 bytes hash, u8 n, then n × outcomes [u8 outcome] (n ≤ 2) |
| 49 | `MATCH_END` | S→C |  | 7 | u8 outcome, u8 reason, u32 final_tick |
| 50 | `LEAVE_MATCH` | C→S | hub | 1 | nothing |
| 52 | `LINKS` | S→C |  | 2 to 18 | u8 n, then n × seats [u8 seat, u16 rtt_ms, u8 flags] (n ≤ 4) |

#### Commands (`CMD.type`; seat 0 to 3 in `TURN`)

| Type | Command | a | b | c |
|---|---|---|---|---|
| 1 | `BUILD` | 0 to 2 | 0 to 255 | 0 to 255 |
| 2 | `FORK` | 1 to 2147483647 | 0 to 1 | 0 |
| 3 | `SELL` | 1 to 2147483647 | 0 | 0 |
| 4 | `READY` | 0 to 1 | 0 | 0 |
| 5 | `SIGNAL` | -262144 to 262144 | -262144 to 262144 | 0 to 2147483647 |
| 6 | `CORK` | 0 to 15 | -2147483648 to 2147483647 | -2147483648 to 2147483647 |
| 7 | `UNCORK` | 0 to 15 | -2147483648 to 2147483647 | -2147483648 to 2147483647 |
| 8 | `SEAWALL` | 0 | 0 | 0 |

#### System commands (seat 255 in `TURN`; a game never sends them)

| Type | Command | a | b | c |
|---|---|---|---|---|
| 64 | `AWAY` | 0 to 3 | 0 | 0 |
| 65 | `BACK` | 0 to 3 | 0 | 0 |
| 66 | `LEFT` | 0 to 3 | 0 | 0 |
| 67 | `TIMEOUT` | 0 | 0 | 0 |

#### Numbered values

| Key | Values |
|---|---|
| `errors` | protocol 1, game_older 2, bad_name 5, out_of_limits 6, full 7, rate 8, bad_token 9, banned 10, allowlist 11, replaced 12, kicked 14, maintenance 16, server_older 17 |
| `notices` | party_full 1, no_such_party 2, removed 3, match_dissolved 4, needs_reload 5, caretakers_offered 6, tick0_mismatch 7, parties_full 8 |
| `outcomes` | won 0, lost 1, draw 2, desynced 3, aborted 4 |
| `end_reasons` | result 0, desync 1, tick0_mismatch 2, rules_mismatch 3, everyone_left 4, timeout 5, server_closing 6 |
| `load_states` | connecting 0, loading 1, checking 2, ready 3, slow 4, gone 5 |
| `member_states` | here 0, ready 1, away 2, needs_reload 3, in_match 4 |
| `party_phases` | forming 0, countdown 1, queued 2, loading 3, in_match 4, results 5 |
| `party_ops` | create 1, join 2, leave 3, remove 4, mode 5, builders 6, ready 7, team 8, open 9, start 10, cancel 11 |
| `queue_ops` | enter 1, leave 2, start_with_caretakers 3 |
| `queue_states` | idle 0, entering 1, queued 2, leaving 3 |
| `hello_flags` | resume 1, web 2 |
| `welcome_flags` | maintenance 1, dev_match 2 |
| `seat_flags` | caretaker 1 |
| `hash_flags` | checkpoint 1 |
| `link_flags` | hidden 1, silent 2 |
| `party_flags` | open 1, lan 2 |
| `maps` | hollow 0 |
| `builders` | lamplighter 0, lookout 1, bellfounder 2, beekeeper 3 |
| `modes` | classic 0 (1 team, 1 to 4 seats), high_water 1 (1 team, 1 to 4 seats), tide_race 2 (2 teams, 2 to 4 seats), undertow 3 (2 teams, 2 to 2 seats) |

<!-- protocol.json tables: end -->

## Golden transcripts

`transcripts/*.bin` are byte streams recorded from the real server on a hand-moved clock
(`python3 server/tools/record_transcripts.py`; a server test fails when re-recording would change a
byte). Each `.json` beside one lists the same records decoded, which is what the GDScript codec must
produce (`protocol_golden_m1`, `protocol_golden_m3`), and encoding those values must give the same
bytes back. The `m3_*` ones are also the hub's conversations in order, for testing the game's
session against the real server's answers.

| File | What it holds |
|---|---|
| `m1_handshake` | `HELLO`, `WELCOME`, `PING`, `PONG`, `VISIBILITY`, `BYE`; refused `HELLO`s: an older game (`ERROR` 2), a newer one (17), a bad name (5), a zero token (9) |
| `m1_dev_match` | a whole `--dev-match classic:2`: `MATCH_CONFIG`, every `LOAD_STATE` of the barrier, `START`, turns with every command type and both rotations, `PONG`, `TURN_REQUEST`, `HASH`, `LINKS`, `AWAY`, `BACK`, `LEFT`, `TIMEOUT`, `RESULT`, `MATCH_END`, `BYE` |
| `m1_codec` | every message of `protocol.json` once with canonical values: each `PARTY` op, each command type, every system command in one `TURN`, a 1,024-byte `CHECKPOINT_PART`, UTF-8 beyond ASCII in a `motd` |
| `m3_party` | the hub (party codes from `random.Random(20261030)`): `create`, a wrong code (`NOTICE no_such_party`), a `join` in lower case, `builders`, an older build (`NOTICE needs_reload`), `ready`, a refused `start`, `remove` (`NOTICE removed`, the no-party state, a refused rejoin), `mode` and `team` in a Race, `open`, `QUEUE` answered idle, the countdown, its `cancel`, and the countdown's end: `PARTY_STATE` loading, `MATCH_CONFIG` with each member's main |
| `m3_barrier` | a party's barrier: `LOADING`, `LOADED`, `slow` at 15 s, `seconds` 30, the leader's start without the slow seat, `START`, `PARTY_STATE` in_match, `AWAY` in turn 0 and `BACK` after her `LOADED` |
| `m3_back` | a party's match to its end and back: a member joining during the match, `RESULT` and `MATCH_END`, the results plate, `LEAVE_MATCH` and a `ready` back to forming; a dropped member held (`away`) and taken back by a resume `HELLO`; another's row freed 40 s after its drop |

The `.bin` layout, big-endian: `"GHTX"`, u8 format (1), u16 protocol version, u8 clients, u32
records; then per record u8 direction (0 game to server, 1 server to game), u8 client, u16 length and
the message itself (no WebSocket framing). In the `.json`, fixed bytes and blobs are lowercase hex,
lists are arrays of objects and `PARTY`'s `op` is its name.

## Where this contract decides what §6.5 left open

- `rules_hash` travels as 8 raw bytes (byte-identical to a big-endian u64 of the SHA-256 prefix), so
  GDScript never handles an unsigned 64-bit int.
- `RESULT`'s per-team outcomes are a counted list (`u8 n`, then n × u8), so its length is checked
  without knowing the mode.
- `ERROR` is `u8 code, u8 + text` (Cyberworld's was u16 code and raw text); `NOTICE` is `u8 code, u32
  argument`.
- Seats are 0-based; system commands are types 64 to 67 so they can never collide with a game's.
- The command ranges in `commands` are the server's shape check (cells 0 to 255, signal coordinates
  within ±262,144 mm, slots 0 to 2, branches 0 and 1); the simulation enforces the real rules.
- Load states: `connecting` (nothing yet), `loading` (a `LOADING` came), `checking` (`LOADED`, waiting for
  the others), `ready`, `slow` (M3, 15 s), `gone`.
- Welcome flags: `maintenance` (draining: only resumes are let in; M4) and `dev_match`.
- Silence for `AWAY` counts from `START`; any message counts as a word, WebSocket pings included
  (but a seat started without its player comes back only with its `LOADED`).
- The hub (M3): "back to the party" is `LEAVE_MATCH` after `MATCH_END`; "start without Ben" is the
  leader's `PARTY start` while the party is `loading`; "in no party" is a `PARTY_STATE` with a zero
  code; `NOTICE no_such_party`'s argument is 0, or the seconds until the connection may look a code
  up again; `NOTICE party_full`'s is the member count, `needs_reload`'s the member's number. The
  member state `away` is a held row ("reconnecting"); `in_match` covers the results plate.
- `PARTY_STATE`'s `rtt_ms` is each member's last reported round trip; a change of it alone is sent
  at most every 2 s (`links_ms`), outside a match.
