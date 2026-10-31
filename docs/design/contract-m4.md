# The M4 contract

M4 (resilience: hashes, checkpoints, reconnect, the caretaker, desyncs, background tabs; [`core-loop.md`](core-loop.md)
§8 M4, on §6.3, §6.5, §6.7, §6.8 and Appendix A) runs four tracks in parallel from one commit, this one. Anything
named here keeps its name and number until the tracks agree to change it. The wire's prose is
[`shared/net/README.md`](../../shared/net/README.md), Resilience (M4); this page says what is fixed, who writes what,
and when each track is done. Two guards hold it: the scenario `contract_m4_wire_and_seams`
(`tests/net/contract_m4.gd`) and `server/tests/test_contract_m4.py`. `contract_ids_keep_state_hashes` and the
`sim_checkpoint_roundtrip*` scenarios show no recorded state hash moved: nothing the simulation stores changed, and
what it does changed only where no recorded hash reaches, a caretaker taking a seat whose towers already stand (it
picks up at the seat's plan cursor over the player's towers, f7291e5). So that a build from before it never shares a
match with one after, the rules hash covers `SimContent.CARETAKER_VERSION` (2), not `SIM_VERSION`, which the codec
writes and which would move every recorded state hash.

## 1. Already built, kept as it is

M1 to M3 built more of M4 than its plan says, and M4 builds on it rather than again: the system commands `AWAY`,
`BACK`, `LEFT`, `TIMEOUT` and the server's 5 s silence; the seat states and the hand-back at the next build window
inside the simulation (`SimWaves.open_window`), with `REFUSE_CARETAKEN` ("The caretaker hands back at the next build
window") for a returning seat's own orders; the caretaker playing any Builder from its plan, always Ready; the hash
referee (all equal, or a strict majority of three or more) and the result referee; `TURN_REQUEST` and the client's gap
repair; `HASH`'s `checkpoint` flag; the ids of `CHECKPOINT_ASK`, `CHECKPOINT_PART`, `RESYNC`, `VISIBILITY`; `LINKS`'
`hidden` and `silent`; the 1 MiB inbound buffer; `SimCodec` round trips mid-flight; held party rows and `HELLO`'s
`resume` bit; `ERROR` 12 `replaced`; `Playout`'s catch-up at 8 ticks a frame.

## 2. The wire (`shared/net/protocol.json`)

Appended only: no id, value or byte before them moved (`VISIBILITY`'s one byte only got a name for its three
values). The protocol stays version 1, since no build has shipped. The transcripts were re-recorded for the new
fields (their records and counts are as before) and `protocol_golden_m1` and `_m3` decode them.

| Kind | Added |
|---|---|
| Numbers | `checkpoint_ticks` 1,800 · `checkpoints_kept` 2 · `max_checkpoint_parts` 64 · `checkpoint_wait_ms` 5,000 · `catchup_bytes` 2,048 per `catchup_ms` 50 while output < `catchup_output` 4,096 · `max_resyncs` 1 · `reconnect_ms` 2,000 · `hidden_silence_ms` 600,000 (after the review: a hidden tab's link outlasts the 15 s silence rule this long) |
| `HELLO` | trailing `u32 match`, `u8 seat`: the seat a resume asks back (wire seat 0 to 3); 0 and 255 for none. Two windows on one computer share an identity, so the seat, not the identity, says which one comes back |
| `MATCH_CONFIG` | trailing `u8 flags`, `config_flags`: `rejoin` 1 (a game sends no `LOADED`; `RESYNC` follows) |
| `RESYNC` | after `checkpoint_tick`, `first_turn` (= `checkpoint_tick / 3`): `u8 reason`, `u32 open_turn` (the catch-up's goal), `8 bytes checkpoint_hash`, `u16 parts` |
| `VISIBILITY` | its byte is `state`, `visibility_states`: `shown` 0, `hidden` 1, `catching_up` 2 (was `hidden` 0 or 1) |
| Values | `resync_reasons`: `rejoin` 0, `desync` 1, `behind` 2 · `link_flags.catching_up` 4 · `notices.no_held_seat` 9 · `end_reasons.desynced_twice` 7 |

The rules each track serves (README, Resilience): a **checkpoint tick** is a hash tick that is a multiple of 1,800 or
where a hollow's wave number changed since the hash tick before; each game decides it from its simulation and flags
it. A checkpoint is the game's `SimCodec` bytes; its **digest** is `SHA-256[:8]`, the state hash, and the server keeps
an upload only when the digest is the agreed hash. **Parts** go in order, all but the last 1,024 bytes. **RESYNC** is
followed by the parts, the turns `first_turn` to `open_turn` − 1, then live turns, paced by the **catch-up**. **BACK**
waits for `shown` while a connection said `catching_up`. A **rejoin** is a resume `HELLO` naming its held seat:
`ERROR` 12 to an old link still open, then `PARTY_STATE`, `MATCH_CONFIG(rejoin)`, `RESYNC(rejoin)`; a seat not held
gets `NOTICE no_held_seat`. A minority **desync** is resynced once; again is `MATCH_END(desynced, desynced_twice)` for
that seat alone. A match ending desynced writes **`user://desync/<match>-<seat>.bin`** (seat 1 to 4). A seat **started
without** knows it when `START` comes before its `LOADED`, says `catching_up`, and after its `LOADED` gets
`RESYNC(behind)` if a checkpoint past tick 0 is kept.

## 3. Simulation vocabulary (`scripts/sim/sim_types.gd`)

No number changed and nothing the codec stores. Added: `CHECKPOINT_EVERY` 1,800 (`protocol_agrees_with_sim_types`
compares it with `checkpoint_ticks`; the simulation never reads it), `SEAT_NAMES` and `seat_state_name()` /
`seat_state()`. The seat states stay `SEAT_PRESENT` 0, `SEAT_AWAY` 1, `SEAT_RETURNING` 2, `SEAT_CARETAKER` 3 (from
tick 0) and `SEAT_LEFT` 4; every state but present is the caretaker's. M4 needs no new event or refusal: `EV_SEAT`
(seat, state) says away, back next window, back and left, and `REFUSE_CARETAKEN` refuses a returning seat's orders.

## 4. Seams

| Where | Fixed now | Stub until its track |
|---|---|---|
| `scripts/net/checkpointing.gd` (`Checkpointing`) | `is_checkpoint_tick(tick, waves_now, waves_then)`, `waves_of(sim)`, `digest(bytes)`, `split(tick, bytes)`; `KEPT`, `ticks`, `kept`, `bytes_at`, `has_tick`, `upload` | `at_hash_tick(sim, tick)` (keeps, returns `HASH` flags), `begin_download(tick, parts, digest)`, `add_part(fields)`, `download_done()`, `downloaded()` |
| `scripts/net/desync_dump.gd` (`DesyncDump`) | `path_for(match, seat)`, the file's layout (its header comment) | `write(client, checkpoints, bad_tick)`, `read(path)` |
| `scripts/net/web_bridge.gd` (`WebBridge`) | signal `visibility_changed(hidden)`; inert on desktop | `start`, `stop`, `flash_title`, `stop_flash`, `poll(now_ms)`, `query(key)` |
| `scripts/ui/connection_overlay.gd` (`ConnectionOverlay`) | `State` (`NONE`, `RECONNECTING`, `CATCHING_UP`, `IN_ANOTHER_TAB`, `DESYNCED`, and appended after the review, `BACK`: back from another tab or a dropped link while the caretaker holds the seat), `TEXTS`, `show_state(state, progress_pm, detail)`, `text()` | the plate (bronze console pieces), hidden until then |
| `scripts/net/match_client.gd` | `held_match`, `held_seat`, sent in every `HELLO` | setting them, the resume flag, `CHECKPOINT_ASK`, `RESYNC` |
| `server/groundhold_server/protocol.py` | `digest(data)`, `checkpoint_parts(tick, data)`; `read_hello` bounds `seat` | |
| `server/groundhold_server/catchup.py` (`CatchUp`) | `CatchUp(write, buffered, budget, below)`, `queue(data)`, `pump()`, `done`, `total`, `sent`; `BYTES`, `EVERY_MS`, `OUTPUT` | `pump()` writes nothing |
| `server/groundhold_server/app.py`, `match.py` | `VISIBILITY` 0 to 2 (3 and up `ERROR` 6), `LINKS` flags `catching_up`, `MATCH_CONFIG` flags 0 | everything else in README, Resilience |

## 5. Who owns what

| Track | Owns (writes) |
|---|---|
| A. Server | `server/*` (`match.py`: checkpoint asks and store, `RESYNC`, rejoin, the `BACK` rule, `desynced_twice`; `catchup.py`; `app.py`, `lobby.py`, `holds.py`: the resume, `ERROR` 12, `no_held_seat`, maintenance letting resumes in; `stats.py`: desyncs, resyncs, rejoins), `server/tests/`, `server/tools/`, `shared/net/*` (a wire change only with the client track's agreement, then re-recorded) |
| B. Client | `scripts/net/*`, `scripts/ui/connection_overlay.gd`, `scripts/main.gd`'s hooks (the overlay, views rebuilt from a loaded checkpoint, refusing orders while catching up), `scripts/session/session.gd`'s reconnect, `tests/net/*` (`fake_sequencer.gd` serves README's Resilience; `fake_link.gd` cut, hide, corrupt), `tools/net/*` (`smoke.py` faults, `shaper.py`), `tests/scenarios/net_*.json`, `party_*.json`, `tests/net/live/` |
| C. Simulation | `scripts/sim/*` (`caretaker.gd` any seat from mid-match, returning, hand-back; `sim_codec.gd`; `sim_match.gd` seat states), `tests/sim/*`, `tests/scenarios/sim_*.json` |
| D. Docs | `README.md` (Play together: a drop, another tab, a desync), `docs/media/` and `tools/media/` (a shot of the overlay), `web/*` (`play/` forwards `?join=`; the parent page the title flash writes to) |

Each track adds its own, newly named scenarios and tests, and its own lines in `AGENTS.md` and `CHANGELOG.md`. A
change to `SimCodec`'s bytes or to classic's behaviour moves state hashes: track C says so in its commit, and
`contract_ids_keep_state_hashes` is re-recorded only with that reason.

## 6. Done when

From §8 M4, by track; every one fails before its track's change, and everything else stays green.

- **A. Server:** `test_hash_referee`, `test_checkpoint_accept` (an upload with another digest is dropped and the next
  seat asked; 5 s without one, too), `test_catchup_budget` (2 KB a turn, never over 4 KB of output, live turns behind),
  `test_away_back` (silence, `catching_up` holding `BACK`, `shown`), `test_versions`, and the contract's
  `test_rejoin_names_its_seat` (`ERROR` 12 to the old link, `MATCH_CONFIG(rejoin)`, `RESYNC(rejoin)`, `NOTICE
  no_held_seat`); a transcript `m4_resilience` recorded from the server; `/stats` counts desyncs, resyncs and rejoins.
- **B. Client:** `net_hashes_agree_long_match` (four clients, a whole `hollow12`), `net_checkpoint_kept_only_if_agreed`,
  `net_reconnect_from_checkpoint` (client 2 cut at wave 5 for 20 s rejoins, catches up with the bar, hashes agree,
  the seat back at the next window), `net_away_after_5s_caretaker_builds`, `net_hand_back_at_window`,
  `net_minority_desync_resyncs` (three clients, client 3's gold corrupted at tick 2,000), `net_two_seat_desync_ends_with_dumps`,
  `net_hidden_tab_catches_up` (120 s hidden; a gap repaired by `TURN_REQUEST`), `party_rules_hash_needs_reload`, the
  contract's `net_late_loader_resyncs_behind`; `smoke.py --shaper` (150 ± 50 ms and a 3 s stall on one client: the
  other's tick rate never drops, equal hash streams); a live reconnect against the real server in `tests/net/live/`.
- **C. Simulation:** `sim_bench` (four seats at wave-11 load, native ticks a second, failing below 3,000 to start), a
  caretaker taking a seat mid-match where its towers already stand, a returning seat refused until the window,
  `sim_checkpoint_roundtrip*` still green.
- **D. Docs:** README says what a player sees on a drop, in another tab and on a desync; a media shot of the overlay;
  `play/` forwards `?join=`; `python3 tools/names_check.py` clean.
- **Integration (the four tracks merged), against the real server:** `tests/net/live/net_reconnect_live` (a socket
  dropped), `net_restart_rejoins_live` (a whole game killed and started again takes its seat back from what
  `user://net.cfg` noted), `net_minority_desync_resyncs_live` (three games, `RESYNC(desync)` to the one apart) and
  `net_two_seat_desync_dumps_live` (two apart end desynced, both dumps read back and replayed); `smoke.py --faults`
  and `--shaper`; `sim_bench`'s native number written in its scenario.
- **By hand, all:** the web export replays a recorded log to the same hash stream, and its `sim_bench` reaches 2,000
  ticks a second.
