# Groundhold multiplayer: the core loop

Merged design, 29 October 2026. It judges the three competing designs (`coop_first.md`, `versus_first.md`,
`ship_it.md`), takes the strongest as the spine, grafts the best of the others onto it, and replaces every design's
networking chapter with the model the user asked for: a server hosted the way Cyberworld Endless's is, forked from
its Python code. It is written so an engineer can build each part without asking.

Base read for this document:

- **Repo, as of 0.5.0:** `AGENTS.md`, `README.md`, `CHANGELOG.md`, `scripts/game.gd`, `main.gd`, `wave_director.gd`,
  `build_controller.gd`, `tower.gd`, `creep.gd`, `hud.gd`, `hollow_map.gd`, `tests/bot.gd`, the 15 scenarios in
  `tests/scenarios/`, the 4 in `tools/media/`, `export_presets.cfg` (one preset, Web) and
  `.github/workflows/pages.yml`.
- **Design inputs:** the three designs and the eight research briefs in `scratchpad/mp/research/` (`builders`,
  `client_flow`, `coop_maps`, `versus_maps`, `modern_td`, `netcode`, `gaps`, `cyberworld`).
- **Cyberworld Endless:** the server package, `shared/online/protocol.json`, `deploy/coolify/` and the workflows were
  spot-checked in its repo for the facts this design relies on (`max_message` 512, the drifting
  `asyncio.sleep(1 / tick_hz)` loop, `--event-log`, the Coolify Compose file).
- **Godot 4.7.1:** every engine API named here was looked up in the installed class reference with
  `godot-agent api show` (Appendix C lists them).

Every number below is Groundhold's own starting value for the balance bots to tune. None is taken from another
game's tables. Builder, creep, tower, place and mode names are original. [`world.md`](world.md) sets them and gives
the world they come from; where the two documents differ, it wins.

---

## 0. The verdict

### 0.1 Scores

| Design | (a) Fidelity to the vision | (b) Fun and originality | (c) Technical soundness and testability | (d) Less is more | Sum |
|---|---|---|---|---|---|
| `coop_first` | 8 | 7 | 6 | 6 | 27 |
| `versus_first` | 9 | 9 | 5 | 4 | 27 |
| `ship_it` | 6 | 5 | 7 | 9 | 27 |

**coop_first.**

- *Fidelity 8.* It is the only design where a team's constellation shows in play and not just in a coverage table.
  Every Builder brings one team tower whose effect helps any player's towers, effects never stack, and a Help
  column credits the support. It has co-op, a race, the whole hub-to-hub loop, LAN and online. Its only
  competitive v1 mode is a race with no interaction.
- *Fun 7.* The wave list is written around the roster: each of waves 7 to 10 is one Builder's strong pair. It adds
  a mid-game boss and makes support visible. The race is thin.
- *Technical 6.* Sound simulation discipline and four test levels. But it puts a headless Godot authority in Docker
  behind Caddy on a new Hetzner VPS, which the user's direction rules out, and it keeps `sqrt` in the simulation.
- *Scope 6.* Four Builders with forks (30 new tower models), signals, a queue and the race, all in v1.

**versus_first.**

- *Fidelity 9.* Real competition in v1 (1v1 and 2v2). A rival's weak checks become what you send, and co-op comes
  from the same parts.
- *Fun 9.* The most original of the three:
  - the **Drift**: three seeded packs, the same for both sides;
  - **corked bottles** that you uncork at a moment you choose;
  - defending that pays;
  - **Seawall**, a comeback charged by losing lives;
  - the **Surge** as a hard end.

  It also carries an explicit guard against reading as Legion TD 2.
- *Technical 5.* Its corked sends depend on the server filtering what each client sees, which the chosen model
  cannot do without a trick (§1.4 supplies one). It mixes `@rpc` with raw packets and needs a new mirrored map.
- *Scope 4.* Everything at once: a twin map, a send economy, the seawall, the surge, pings with seven meanings,
  phrases, 2v2 and four Builders with forks.

**ship_it.**

- *Fidelity 6.* Four Builders, but upgrades are linear, and "weak, never blind" coverage makes partner choice a
  soft matter. Its competitive mode is a race.
- *Fun 5.* The Woodpile (an economy tower) and Kindling (death bursts) are good ideas; there is little else for a
  team to argue about.
- *Technical 7.* The best engineering of the three:
  - one code path for solo, LAN and online;
  - a written tick order;
  - range checks as intervals of road distance;
  - an integer units table;
  - server deploys separate from Pages, so a push does not end running matches;
  - API names checked against 4.7.1.

  It too puts Godot on the server.
- *Scope 9.* The smallest v1.

### 0.2 The spine and the grafts

The sums tie, so the choice is made on the heart of the user's vision: a roster like League's, where the team's
constellation matters. **`coop_first` is the spine.** It is the only design that makes the team's makeup felt in
every wave, and it scores at least 6 on every axis. Grafted onto it:

| From | What |
|---|---|
| `ship_it` | The engineering spine: one code path (solo runs the same simulation through an in-process turn source); M1 split into M1a (solo on the new simulation) and M1b (two players over the server); the explicit tick order; range as road intervals; the integer units table; a creep shown with every check (now the local creep's portrait beside a tide-form glyph, `world.md`); Builders shown only as portraits and pennants in v1; "start with who's here" when a queue is quiet; separate server releases |
| `versus_first` | The competitive design after v1 (the Drift, corking and uncorking, defending that pays, Seawall, the Surge); Okabe-Ito seat colours with glyphs; racing or duelling the caretaker offline; the originality guard against Legion TD 2; the Bellfounder and the Beekeeper |
| The Cyberworld study and the user | The whole networking, server, hosting and operations chapter (§6). All three designs chose a headless Godot authority; that is overruled |

### 0.3 Decisions on one page

1. **v1 modes:** **High Water**, co-op for 1 to 4 players on one shared hollow (12 waves, about 13 minutes), and
   **Tide Race** (the Race), competitive for 1v1 or 2v2 on two copies of the hollow with the same seed and waves
   and no creeps crossing over. **Undertow** (the Duel: 1v1 with sends) is milestone 7, the first release after
   v1; the simulation and protocol are built for it from M1. The hollow is **Wickhollow**, Tamsin Wick's home and
   v1's one map.
2. **Builders:** four in v1, each with two signature towers and one **team tower**, a two-way **fork** on every
   tower (A deepens the role, B patches a weakness) and one passive. No active abilities, so the six-slot command
   card keeps its shape. Everything is unlocked; there are no accounts.
3. **Checks:** four, each shown by a tide-form glyph with the local creep's portrait beside it, and each taught on
   Wickhollow by one creep: Swarm (the Froth glyph; Gourdling), Swift (Runnel; Scuttler), Armored (Ballast;
   Thornback, flat armour 4), Winged (Spindrift; the new **Duskmoth**, which only `air` towers can target). The
   Bristlesow (wave 6) and the Hollowtide Crest (wave 12) are the exams that combine them.
4. **Constellation:** the Builders sit on a cycle (Swarm, Swift, Armored, Winged), each strong on two neighbours.
   Only 2 of the 6 possible duos are strong on all four checks. Team towers (slow, mark, crack, haste) help any
   player's towers, the strongest effect applies, and the player whose effect applied is credited with **Help**.
5. **Economy:** every kill pays its full bounty to every player on the team; clear bonus and early-Ready gold go to
   each player. No interest, no gifts, no second currency. Two to four players get the same wave list with more
   creep health (a per-mille table), so tolls read the same at every size.
6. **Authority:** **server-sequenced deterministic lockstep.** The server never simulates. It closes a **turn**
   every 50 ms (3 ticks) and broadcasts the commands that arrived, each stamped with the sender's seat. Every
   client runs the same integer-only GDScript simulation from (seed, rules, turns) at 60 Hz. No client waits for
   another, only for the server's turns. No rollback, no prediction: a command lands about RTT + 0.1 to 0.3 s
   later, covered by an immediate ghost.
7. **Keeping clients in step:** a state hash every 60 ticks, compared by the server; an agreed checkpoint at every
   wave start and at least every 30 s; reconnects start from it. A seat is held until the match ends, and a
   deterministic in-simulation **caretaker** plays it after 5 s away. A minority desync with 3 or more seats
   reloads the checkpoint; with 2 seats the match ends "desynced" and both clients write dumps.
8. **The server** is a fork of Cyberworld's dependency-free Python 3.11 asyncio WebSocket server: the hub, parties,
   the queue, the loading barrier and one turn clock per match. It ships the way Cyberworld's ships: a
   deterministic zipapp, five native binaries for LAN hosts, a multi-arch `ghcr.io` image, a Coolify Compose file
   and a Caddy Compose file for self-hosters.
9. **Transport:** WebSocket everywhere. Clients use Godot's `WebSocketPeer`; the server speaks Cyberworld's
   bounded RFC 6455 subset on one port (8766, path `/causeway`, subprotocol `groundhold.v1`). Desktop LAN uses
   `ws://`; online, desktop and browser use `wss://`, with TLS terminated by Coolify's proxy.
10. **Hosting:** the official server is a second app in the user's existing Coolify, next to
    `wss://cyberworld.saschb2b.com/presence`, at a new subdomain (proposed `wss://groundhold.saschb2b.com/causeway`).
    The only new thing is a DNS record; the extra cost is nil.
11. **LAN** is a desktop feature: download the server, double-click it, and desktop players find it under
    **Nearby** (a UDP beacon the server sends) or type the address its banner shows. Browsers play online only.
12. **Screens:** Hub (party, mode, your Builder, one button), Builders (roster, main and backup, Try), Match Found
    (an overlay, strangers only), Loading (per-player sync status), the Game, Results, and back to the Hub with the
    party intact. All of it reuses the bronze console's wells.
13. **Testing:** a match is a pure function of (seed, rules, turns). Six test levels: the simulation alone, an
    in-process fake sequencer with N clients, Python unit tests over real sockets, golden byte transcripts that keep
    the GDScript and Python codecs honest, a multi-process smoke run, and a native-against-web replay check.
    §7.5 lists the kit extensions.
14. **Milestone 1** is a playable two-player co-op match over localhost: two desktop windows and the forked server
    on `ws://127.0.0.1:8766/causeway`. Seven milestones in all; v1 is M1 to M6.

### 0.4 Every conflict, resolved

| # | Topic | `coop_first` | `versus_first` | `ship_it` | Merged decision, and why |
|---|---|---|---|---|---|
| 1 | Match authority | headless Godot | headless Godot | headless Godot | **Server-sequenced lockstep** (§6.1): the user's hosting direction, plus the study's evidence (reuse, Coolify, LAN binary, a match as a pure function) |
| 2 | Server software | Godot export | Godot export | Godot export | **Fork of Cyberworld's Python server** (§6.10) |
| 3 | Hosting | Hetzner + Caddy | Hetzner + Caddy | Hetzner + Caddy | **The user's Coolify**, a self-host Caddy Compose and LAN binaries, as Cyberworld does |
| 4 | LAN host | listen server in the desktop game | same | same | **The downloadable server binary**; a "Host on this computer" button that launches it comes after v1 |
| 5 | Client transport | `SceneMultiplayer.send_bytes` | `@rpc` plus `send_bytes` | raw `WebSocketMultiplayerPeer` | **`WebSocketPeer`** with binary frames; no `SceneMultiplayer` (the server is not Godot) |
| 6 | Competitive in v1 | Race | Duel with sends | Race | **Race in v1, Duel in M7.** A send economy needs its own balance gates; under lockstep the race is two hollows in one simulation and costs almost no netcode |
| 7 | Upgrades | fork | fork | linear | **Fork.** It is the one mid-game choice system v1 keeps, and it is how a solo player patches a blind spot |
| 8 | Bounty | full to every player | split evenly with a remainder rule | full to every player | **Full to every player:** integers, no remainders, nothing to steal |
| 9 | Scaling by players | health only | count and health | count and health | **Health only.** Wave lists and tolls read the same for 1 and 4 players |
| 10 | Armour | 6, floor ¼ | 4, floor ¼ | 4, floor 30% | **4, floor ¼:** two of three agree; 4 keeps the Lamplighter, the starter, viable before forks |
| 11 | Winged blind spot | ✕ until a fork | ✕ until a fork | never blind | **✕ until a fork** for two Builders: a real check. The strip shows the moth a window ahead |
| 12 | Build windows | 25 s then 15 s in a team; 15 s then 10 s solo | 20 then 12 | 20 then 12 | **`coop_first`'s:** a team needs time to agree; solo keeps today's 15 and 10 |
| 13 | Hollowtide Crest toll | ends the match | 10 | 10 | **10**, as today |
| 14 | Hotkeys | positional Q W E / A S D | Builder letters, U and I | Q W E plus U S N | **Positional Q W E / A S D**, the same for every Builder; N and Space still toggle Ready. A user decision (§10) |
| 15 | Team effects | a team tower per Builder | one amplifier | one armour shred | **A team tower per Builder**, four distinct effects |
| 16 | Co-op mode name | a night-watch word, now retired | Hold the Hollow | Hold the Hollow | **High Water** (`world.md`: holding a land through a whole flood) |
| 17 | Comeback device | none in co-op | Seawall everywhere | none | **Seawall only in the Duel** (M7); co-op has none |
| 18 | Pings | one meaning | seven meanings | one meaning | **One meaning**, "look here", rate-limited |
| 19 | Seat colours | amber, sky, rose, ivory with shapes | Okabe-Ito with glyphs | numbered pips | **Okabe-Ito colours plus a glyph plus a pennant shape** |
| 20 | Match Found window | 10 s | 12 s | 15 s | **15 s**: a browser player may need to switch tabs |
| 21 | Caretaker after | 5 s | 30 s | 10 s | **5 s** (the study): towers fire regardless, and the caretaker only spends the seat's gold |
| 22 | Hand-back | next build window | same | same | **Same**, enforced inside the simulation, because the server cannot see waves |
| 23 | Loading, slow player | leader prompt at 30 s, auto at 45 s | prompt at 45 s | prompt at 45 s | **Prompt at 30 s for a party; automatic at 45 s for strangers** |
| 24 | Race layout | one simulation per team | twin mirrored map | second copy at an offset | **Second copy at an offset, in one simulation** |
| 25 | Content tables | float, converted | float | float, compiled to ints | **Authored in integer units** in `scripts/sim/content.gd`; names, models and icons stay in `game.gd` |
| 26 | Server deploys | with every push | with every push | from tags | **From releases**, when the protocol changes. Balance changes need none: `rules_hash` is a matchmaking key (§6.9) |
| 27 | Pause | solo only | solo only | solo only | **Same** |
| 28 | Party seat after a drop | 60 s | 60 s | 60 s | **40 s**, Cyberworld's proven `holds.py` |
| 29 | Fifth check (Veiled) | later | later | later | **Later**, with a fifth Builder |
| 30 | Mid-game boss | Bristlesow | none | none | **Keep it:** a scaled, darkened Thornback, no new mesh |

---

## 1. The match core loop

### 1.1 The rhythm every mode shares

```
  BUILD WINDOW                HORN                 WAVE                          PAYOFF
  read the next wave's   ->   creeps leave    ->   towers fire on their own;  ->  clear bonus to each player,
  check icons; build,         the Welling          emergency builds and sells;     next wave's icons appear,
  fork, sell; signal;                              signals; watch the lives         the next window opens
  press Ready (D)
```

- **Window length** (server-independent, counted in ticks by the simulation): the first window is 15 s solo and
  25 s with 2 to 4 players; later windows are 10 s solo and 15 s with company.
- **Ready.** When every present player of a hollow is Ready, the horn sounds at once and each player is paid one
  gold per whole second left (today's early-call rule, now team-wide). Caretaken seats count as Ready.
- **Waves stack (M8, §2.7).** In High Water and Tide Race, Ready may also be called during a wave: the next wave
  sets out the moment the horn sounds, its creeps walking in among the current wave's, and the window between them
  is skipped. At most three waves are on the road at once. A call in a wave pays the whole window it skips and
  0.4 gold more for each life the waves on the road could still take, walking or still to come. classic and
  Undertow do not stack.
- **Building, forking and selling during a wave** stay allowed, as today: the safety valve for a player who is
  behind.
- **A wave clears** when it and every wave before it have nothing left to spawn and no creep on the road; waves
  clear in order. When no wave is left on the road, the next window opens.
- **Felt latency.** Online, a command lands about RTT + 0.1 to 0.3 s after the click (LAN: about 0.1 s; solo:
  at most 50 ms). The client draws the ghost tower, the hammer and the greyed gold at once and confirms or
  withdraws them when the command runs (§6.3).

### 1.2 High Water (co-op, 1 to 4 players)

**Fantasy.** Holding a land through a whole flood. The Tide wells up twelve times; the players hold the road
together until its Crest comes for the Holdfast. On Wickhollow the flood is one Hollowtide night, and its Crest is
the Hollowtide Crest.

**Minute by minute** (2 to 4 players; the balance bots confirm the times):

| Clock | Phase | On the board | What the players decide |
|---|---|---|---|
| −0:10 to 0:00 | Loading | One card per player with their Builder, the team's coverage row, each card's sync state | Nothing; see who came and what the team covers |
| 0:00 to 0:25 | First window (25 s) | 120 gold each; the strip shows wave 1's icon | Opening towers; who takes which stretch of road (signals) |
| 0:25 to 1:00 | Wave 1, warm-up | 10 Gourdlings | Finish placing |
| 1:00 to 2:00 | Window, wave 2: **Swarm** | 18 Gourdlings close together | Area damage now; first forks |
| 2:00 to 3:00 | Wave 3: **Swift** | 12 Scuttlers | Slows and stuns; where creeps bunch |
| 3:00 to 4:10 | Wave 4: **Armored** | Thornbacks among Gourdlings | Heavy hits or cracked armour; the first team-tower synergies |
| 4:10 to 5:20 | Wave 5: **Winged** | 8 Duskmoths over the road | "Who reaches the sky?" The first composition moment; a team without anti-air forks for it |
| 5:20 to 6:40 | Wave 6: **the Bristlesow** | A huge armoured boar and three Thornbacks; toll 5 | Focus: marks, cracks and heavy towers on the long straight |
| 6:40 to 7:40 | Wave 7: Swarm + Swift | the Lamplighter's wave | Waves 7 to 10 are each exactly one Builder's strong pair |
| 7:40 to 8:50 | Wave 8: Armored + Winged | the Lookout's wave | |
| 8:50 to 10:00 | Wave 9: Swift + Armored | the Bellfounder's wave | |
| 10:00 to 11:10 | Wave 10: Winged + Swarm | the Beekeeper's wave | |
| 11:10 to 12:20 | Wave 11: **all four** | every check at once | Last big spend; fill the gaps the coverage row showed |
| 12:20 to 13:45 | Wave 12: **the Hollowtide Crest** | the Crest with Duskmoths and Thornbacks | Everything into the road ahead of it |
| 13:45 | Results | Title, team line, lives per wave, one row per player | Play again, or the hub |

- **Session:** loading about 10 s, match about 13 minutes, results about 30 s: hub to hub in about 14 to 15
  minutes. Solo, with shorter windows, runs about 12 minutes.
- **Win:** wave 12 cleared with lives left. **Lose:** lives reach 0.
- **Decisions, by size:**
  - *Before the match:* which Builder, read against the party's coverage row, and (M8) how hard: Normal, Hard or
    Very Hard (§2.6).
  - *Every window:* what to build and where, which fork branch, when to press Ready.
  - *During a wave:* emergency towers, selling a misplaced tower, signals, and (M8) whether to call the next wave
    in behind this one (§2.7).
  - *Three larger moments*, each announced a window ahead: wave 5 (first Winged), wave 6 (first boss), wave 12.
- **Nobody falls behind on income**, because income is equal by rule; "behind" can only mean poor placement. A
  quiet stretch of road is still a good place for a team tower. The caretaker covers anyone who drops.

### 1.3 Tide Race (competitive, v1)

**Fantasy.** The still flood mirrors the land, and two crews hold the hollow and its reflection against the same
surges. Whose Holdfast holds best, and fastest?

- **Teams:** two, of 1 or 2 players (1v1 or 2v2). Each team plays High Water on its own copy of the hollow, with
  the same seed and the same wave list. Nothing crosses between the hollows. Each hollow keeps its **own clock**,
  so calling waves early with Ready is the race lever. From M8 a team may also stack (§2.7): a wave called during
  the one before saves that window and walks beside it. Race time still counts the same way; a stacked race simply
  clears wave 12 sooner, and the lives its risk costs add a minute each, or the Holdfast that cannot hold the waves
  together falls and loses the race.
- **Difficulty** (M8, §2.6): both teams play the party's level.
- **Race time** = the tick at which a team clears wave 12, plus **3,600 ticks (60 s) for every life lost**
  (`tide_race`'s `race.life_t`). M6 set 10 s a life; the owner raised it on 2 November 2026 ("Raise the cost of a
  life") once stacked waves truly overlapped (§2.7): a crew stacking every wave saved 170 to 230 s, which 10 s a
  life never paid for, so stacking every wave won any race its Holdfast survived, whatever it leaked. The strip
  shows both teams' race times as they go, the lives' part after the clock ("6:12 +120 s").
- **Win order:**
  1. Both teams clear wave 12: the lower race time wins; equal ticks are a draw.
  2. A Holdfast goes under on wave *W*: the other team wins as soon as it clears wave *W* ("Your rival fell
     on wave 9. Clear wave 9 to win"). If both fall, the later wave wins; on the same wave, more of that wave's
     creeps killed; then a draw.
  3. Hard cap at 20 minutes of match time: compare waves cleared, then lives, then race time.
- **Practice:** race the caretaker offline (it plays the rival hollow from its plan).

| Clock (1v1) | What happens | What you decide |
|---|---|---|
| 0:00 to 0:25 | First window, as in High Water | How greedy to open |
| 0:25 to about 5:00 | Waves 1 to 5; each side presses Ready as early as it dares | Ready early (faster, and gold for the skipped seconds) or late (safer); from M8, call the next wave while this one walks |
| about 5:00 to 6:30 | Wave 6, the Bristlesow | Whether to call a boss early |
| 6:30 to 11:00 | Waves 7 to 11; the strip shows the rival's wave, lives and race time; **V** shows the rival's hollow | Chase or protect: the rival's line is the information |
| 11:00 to 13:00 | Wave 12; the first team to finish sets the time to beat | |
| end | Results, both teams side by side | |

The race is the stepping stone: it proves two-team matches, two hollows and the results layout, and it costs
almost nothing in netcode, since both hollows live in one simulation that every client runs. Its weakness is the
lack of direct pressure, which the Duel adds.

### 1.4 Undertow (milestone 7, the first release after v1)

Specified now so the v1 simulation and protocol leave room for it. It is `versus_first`'s design, cut to 1v1 and
adapted to lockstep.

- **Layout:** the race layout (two copies of the hollow), with **one shared clock**: both sides build and start
  each wave together, so every wave is a simultaneous reveal. The window opens for both once both have cleared the
  wave; until then no Ready is taken from a side whose hollow has cleared (D, N, Space and the horn say "The window
  opens once both waves are over"), since a Ready said early would sound the horn the moment the window opened and
  spend its corking.
- **The Drift.** From window 2, each window offers three of four packs, drawn from the match's random
  stream and identical for both sides. The left-out pack never repeats twice in a row.

  | Pack (on Wickhollow) | Check | Tier I (windows 2 to 4) | Tier II (5 to 8) | Tier III (9 to 12) |
  |---|---|---|---|---|
  | Gourd Rush | Swarm | 6 Gourdlings | 14 | 20 |
  | Scuttle | Swift | 8 Scuttlers | 17 | 28 |
  | Thorn Herd | Armored | 3 Thornbacks | 5 | 9 |
  | Moth Cloud | Winged | 4 Duskmoths | 5 | 7 |
  | **Price, same for every pack in a tier** | | 45 gold | 55 | 85 |
  | **Stipend gain** for the rest of the match | | +4 a wave | +6 | +12 |

  A sent creep comes with a quarter more health than the wave's own of its kind, as a mercenary is stronger: a
  Gourdling half again, a Scuttler two fifths more, since a small creep a weak defence still kills in a strike or
  two was no threat at a quarter. A Gourd Rush comes bunched, a quarter second apart, so a splash answers it and a
  tower striking one creep at a time falls behind; a Thorn Herd walks a second apart, so a splash finds one
  Thornback at a time and only hits that go through armour hold it; the others half a second apart. Paid
  at every clear from the wave its pack walks to the Surge's last, a tier's stipend pays its price back about once
  from its first window (56 of 45 from window 2, 66 of 55 from window 5, 84 of 85 from window 9) and 48 from its
  last (107%, 87%, 56%), so a pack the rival holds is not a pure loss. (The sends' pass, the owner's
  decision of 2 November 2026, "Stronger packs, fairer stipend": before it a quarter of the uncorked packs breached,
  a tier III one one time in nine; the Scuttle was 6, 10, 14, the Thorn Herd 2, 3, 5, the tier II Moth Cloud 6,
  tier I cost 30 and tier III's stipend was +8.)

  A send is read from the rival's defence: each pack is a threat to the Builders weak to its check and much less
  to those that cover it (the packs' matrix, §4.4). After the sends' pass the Moth Cloud breached the two Builders
  whose openings reach no sky three times in four and the Gourd Rush no Builder at all, so the first Moth Cloud a
  Lamplighter mirror offered was free lives and the rest of the Drift a stipend paid into (the Veteran's third
  playtest). Now, against the caretaker, the Gourd Rush breaches the Lookout half the time and the Bellfounder a
  third, the Scuttle the Beekeeper three times in four and the Lookout a third, the Thorn Herd the Beekeeper three
  times in five and the Lamplighter a third, and the Moth Cloud its two four times in five, each against the
  Builders that cover it about a fifth of the time or less. (The Gourd Rush was 6, 10, 14, the Scuttle 8, 13, 18,
  the Thorn Herd 3, 5, 7 and the Moth Cloud 4, 5, 9, all a quarter stronger and half a second apart.) A weakness a
  plan patches is held once the patch stands: a Lamplighter who has forked her Iron Mortar holds a Thorn Herd (no
  tier III herd has broken her), one with Skyward Lofts a tier II Moth Cloud, and the board shows both. The duel's
  gates cap how far a pack can go: one that breaches a Lookout much more than half the time lets a corker who
  sends the most it can every window beat her turtle, and lifts the share of all sends that breach past a half.

- **Cork and uncork.** In a window a player may **cork** one pack (two from window 9): the gold is taken at once.
  During the next wave, from 3 s after the horn, the player chooses when to **uncork** it (Space or a click on the
  corked bottle); the client uncorks it by itself at 24 s. The pack then walks the rival's road. The stipend
  gain starts when the pack is uncorked.
- **Corked under lockstep, without a referee.** Every client holds the whole state, so a corked pack cannot simply
  be withheld from the rival. A commitment hides it instead:
  - `CORK(tier, commit)` carries `commit = SHA-256(match_seed ‖ seat ‖ window ‖ pack ‖ salt)[:8]`, where the
    8-byte random `salt` stays on the sender's machine until the uncorking. Trying every salt for each of three
    packs is out of reach, so the commitment hides the pack.
  - Every simulation charges the tier's price (equal for every pack in the tier, so the gold reveals nothing)
    and shows the rival a corked bottle.
  - `UNCORK(pack, salt)` reveals the pack. Every simulation recomputes the hash and spawns the pack only if it
    matches. Both values fit one command: `a` = tier or pack, `b` and `c` = the two 32-bit halves of the commit or
    the salt.
  - If no valid reveal arrives by 25 s after the horn (the sender dropped, or cheated), the corked pack fizzles:
    the gold stays spent, and no creeps or stipend follow.
  - Hashing uses `HashingContext`, which is deterministic on every platform. A caretaker's corked packs are not
    hidden (it has no private salt), which is a fair price for being absent.
- **What a rival's bottle shows** (M8). Its tier and its **candidates**: the packs its window offered at that
  tier, never which one ("Gourd Rush, Thorn Herd or Moth Cloud"). The Drift is the same for both sides and lies in
  every client's state, so the candidates add nothing to `CORK` and reveal nothing the commitment hides; they put on
  screen what a careful player could already work out, so the defender can hold gold for the right check. With one
  tier a window, as the preset has it, a bottle's candidates are its window's three offered packs.
- **No stacked waves and no difficulty levels in a duel** (M8). The shared clock needs a window between waves:
  the Drift draws in it, corks are made only in it, and a corked bottle holds both hollows' next one. A wave called
  during a wave would skip a window of corking for one side or both, so Ready in a duel's wave stays refused, as
  in M7. A duel's challenge is the rival, and its prices, packs and Seawall are tuned to Normal's 20 lives, so it
  plays Normal whatever the party chose.
- **Defending pays.** Each uncorked creep a defender kills pays its normal bounty, though it comes a quarter
  stronger than the wave's own. An uncorked creep that reaches the rival Holdfast (a **breach**) costs the toll
  and pays its sender twice its bounty.
- **The caretaker sends what the defence has shown.** It reads only what both sides see: the check of which the
  most creeps have got through the rival's Holdfast so far (from two), else the Moth Cloud where the rival's towers
  deal a flier less than half what they deal the ground, else the pack its towers take longest to kill. A rival's
  corked bottle never enters it, a caretaker's own being in plain sight.
- **Seawall** (the one comeback device):
  - Every 4 lives a Holdfast loses add a charge, up to 2.
  - **F** spends one: a seawall bursts up in a ring around the Holdfast, radius 3.0 m. It stuns every creep inside
    for 2 s and takes 25% of each one's maximum health; the Hollowtide Crest loses 8% and is slowed 50% instead.
  - Cooldown 15 s.
  - On screen, hovering the duel bar's Seawall (or its caption) explains it in these numbers, read from the rules,
    with where yours stands: no charge yet and how many lives earn one, a charge ready, or what the seconds beside F
    count down to after a burst.
- **The Surge.** If both Holdfasts stand after wave 12, three surge waves follow (waves 9, 10 and 11 again,
  with +35% health each). Windows last 8 s, stipends freeze, and corks cost half. After the third surge wave,
  more lives wins; then more breach dealt; then a draw. No duel runs past about 16 minutes.
- **Originality guard** (`versus_first`'s, kept as a design rule): persistent towers, one currency, no workers, a
  seeded shared drift instead of a mercenary shop, corked packs uncorked at a moment the sender picks, a Holdfast
  that does not fight back, a comeback charged by damage taken. That is the genre's send-for-income convention,
  not Legion TD 2's package.

### 1.5 Solo, Try and practice

- **Solo** is High Water with one seat. It runs offline through the in-process turn source, needs no server, and may
  pause (Esc). It is today's game with a Builder.
- **Try** on the Builders screen starts a solo High Water match with that Builder (from M8 at the level the hub
  shows, §2.6).
- **Race the caretaker** (and, from M7, **duel the caretaker**) start offline from the hub with the caretaker in
  the rival seat, so the competitive modes are playable with nobody online.

---

## 2. Modes and maps

### 2.1 Modes are presets over one rules dictionary

One simulation runs every mode; a mode is a dictionary in `scripts/sim/content.gd` (§4.2).

| Key | High Water | Tide Race | Undertow (M7) |
|---|---|---|---|
| Teams × players | 1 × 1-4 | 2 × 1-2 | 2 × 1 |
| Hollows | 1, shared | 1 per team | 1 per team |
| Space | build anywhere on grass; a tower belongs to whoever built it | own hollow per team | own hollow |
| Lives | 20 per team | 20 per team | 20 per team |
| Waves | `hollow12` | `hollow12`, same seed | `hollow12` plus the Drift, then the Surge |
| Clock | per hollow | per hollow (independent) | shared |
| Sends | none | none | the Drift |
| Comeback | none | none | Seawall |
| Duplicate Builders | allowed | allowed | allowed across sides |
| Stacked waves (M8, §2.7) | up to 2 on the road | up to 2 on each hollow, on its own clock | none |
| Difficulty (M8, §2.6) | Normal, Hard, Very Hard | the same; both teams at the party's level | Normal only |
| End | wave 12 cleared, or lives 0 | §1.3 | §1.4 |
| Pause | solo only | never | never |

Solo is High Water with one seat, so `bot_wins` and `idle_player_loses` keep testing the real code path.

### 2.2 How Wickhollow becomes the multiplayer maps

- **High Water** uses Wickhollow's `data/hollow.txt` unchanged: 24 × 16 tiles, one road of 51 tiles (50 m between
  the Welling's and the Holdfast's centres, 6 bends), 206 grass tiles, 86 of them touching the road (diagonals
  included) and 141 within 3 steps of it. Counted for this document. Today's bot builds 10 towers over 8 waves;
  four players at 10 to 15 towers each use 40 to 60 of the 141. That fits, but crowds at four (§9).
- **Race and Duel** place a second instance of the same file at a world offset of 26 tiles in x, with a two-tile
  cliff band between the copies that the terrain builder fills in. The simulation sees two hollows, each with its
  own road, Welling, Holdfast and cells; a cell is addressed as `(hollow, x, z)`. The camera starts over your hollow,
  **V** jumps to the rival's and back, and the minimap shows both with yours brighter.
- **Seats:** 1 to 4. High Water seats share hollow 0. Race seats 1-2 are team A on hollow 0, seats 3-4 team B
  on hollow 1. A seat fixes the player's colour, glyph and pennant shape (§5.9).
- **Later maps** (not v1): a braided map where digits `1` to `4` mark per-seat Wellings whose roads join a shared
  trunk before `E` (the parser grows a road graph; ownership follows the nearest Welling's road), and
  `versus_first`'s Twin Hollow, two mirrored halves of Wickhollow around one shared Welling
  (`scratchpad/mp/design/twin.py` generates it from `hollow.txt`).

### 2.3 Wickhollow's wave list (`hollow12`)

Spawn intervals are authored in ticks (shown here in seconds). Counts never change with the number of players.

| Wave | Groups (creep × count @ interval) | Checks shown | Banner |
|---|---|---|---|
| 1 | Gourdling ×10 @0.9 | Swarm | Wave 1 · Gourdlings |
| 2 | Gourdling ×18 @0.45 | Swarm | Wave 2 · A swarm of Gourdlings |
| 3 | Scuttler ×12 @0.7 | Swift | Wave 3 · Scuttlers |
| 4 | Gourdling ×8 @0.7, Thornback ×4 @1.4 | Armored | Wave 4 · Thornbacks |
| 5 | Duskmoth ×8 @1.2 | Winged | Wave 5 · Duskmoths |
| 6 | Thornback ×3 @1.2, Bristlesow ×1 | Boss, Armored | Wave 6 · The Bristlesow |
| 7 | Gourdling ×20 @0.4, Scuttler ×10 @0.4 | Swarm, Swift | |
| 8 | Thornback ×6 @1.1, Duskmoth ×8 @0.7 | Armored, Winged | |
| 9 | Scuttler ×16 @0.4, Thornback ×5 @1.0 | Swift, Armored | |
| 10 | Duskmoth ×12 @0.6, Gourdling ×20 @0.35 | Winged, Swarm | |
| 11 | Gourdling ×16 @0.35, Scuttler ×10 @0.4, Thornback ×5 @1.0, Duskmoth ×8 @0.6 | all four | Wave 11 · The heart of Hollowtide |
| 12 | Duskmoth ×6 @0.7, Thornback ×4 @1.0, the Hollowtide Crest | Boss, Winged, Armored | Final wave · The Hollowtide Crest |

Waves 3 and 5 were tuned by the M2 balance gates (§4.4) from @0.5 and @0.9, which ended both waves in about twenty
seconds; `content.gd` says why beside each tuned number. Each check is taught alone (waves 1 to 5), tested as exactly
one Builder's strong pair (7 to 10), then all at once
(11). Each boss is announced a window ahead. Nothing is hidden: hovering the wave label lists every remaining wave
as rows of creep icons, each with its count, its health at that wave on your hollow (grown and scaled for the seats
and, from M8, the level, as the simulation spawns it, so it matches the creep's plate) and its armour, a boss's with
the level's added: "×4 140 hp · armour 4".

### 2.4 Creeps

| Creep | HP | Speed (m/s) | Armour | Bounty | Toll | Traits | Art |
|---|---|---|---|---|---|---|---|
| Gourdling | 24 | 1.3 | 0 | 3 | 1 | ground | exists |
| Scuttler | 16 | 2.0 | 0 | 2 | 1 | ground | exists |
| Thornback | 80 | 0.85 | 4 | 6 | 2 | ground | exists; gains armour |
| **Duskmoth** | 30 | 1.5 | 0 | 3 | 1 | **winged**: hovers about 1 m over the road; only `air` towers can target it | **new**: a Blender build script with a flap cycle |
| **Bristlesow** | 500 | 0.7 | 6 | 50 | 5 | ground, boss, 30% control resistance | the Thornback model at 2× scale with a darker tint; no new mesh |
| The Hollowtide Crest | 700 | 0.6 | 4 | 60 | 10 | ground, boss, 50% control resistance | exists |

- The Duskmoth is a large grey-brown moth whose wings glow orange, drawn up through Wickhollow's sunken field gate
  toward the hollow's lamps. The glow is an emissive material, not a light: WebGL 2 allows 8 lights per object and
  32 per frame (`rendering/limits/opengl/*`). It follows the road like every creep, so its position stays one
  number and no new pathing is needed. Its `stride` (the flight speed its flap cycle was made for) is printed by its
  build script, as `AGENTS.md` asks.
- **Control resistance** scales slows and turns stuns on bosses into a 50% slow of the same length: a 45% slow on
  the Hollowtide Crest is 22.5%.
- **Health growth:** each wave adds 25% of base health (wave 12 creeps have 3.75× base health; classic keeps M1's
  22% over 8 waves).
- Tuned by the M2 balance gates (§4.4): the Bristlesow from 900 health and the growth from 20% (at 20% every bot
  lost nothing but the Bristlesow).
- (M8) At Normal every Builder's plan alone kills the Bristlesow (§10, item 19). Its numbers stay; the plans answer
  it. The Bellfounder and the Beekeeper already did (57 s and 52 s into its walk, which takes 71 to 77 s to reach
  the Holdfast, as the plans' slows hold it). The Lamplighter
  dealt 793 of its 1,125 and the Lookout 646, each losing 5 lives. Now the Lamplighter forks her Skyward Loft on
  (11, 11) and her Iron Mortar before her third arrow, and kills it at 71 s of 77. The Lookout builds her Siege
  Perch on (12, 9) before her second Kestrel Flock and her Perch Ballista on (11, 9), and kills it at 51 s of 71.
  Other orders were measured. The Mortar before the Skyward Lofts leaks wave 5's eight Duskmoths. A Skyward Loft on
  (8, 11) with the Mortar leaves the Bristlesow 14 health short. Two Skyward Lofts and the Mortar before the Frost
  Spire kill it at 61 s, but then stacking every wave costs the Lamplighter 3 lives more than her list, under
  `stacking_every_wave_costs_lives`'s bar of 5. Every Lookout order measured that kills it clears waves 4 to 6
  of the Lamplighter-and-Lookout match sooner; the chosen one keeps `high_water_length_2p` at 39,690
  ticks, against a floor of 39,600 and 39,810 before. Both duels keep the old orders (their plans' `undertow`
  blocks), so no duel gate moved. At Hard and Very Hard it stays a toll that a strong opening comes near: the two
  openings deal 63% and 76% of Hard's (38% and 32% before) and 61% and 74% of Very Hard's.

### 2.5 Player-count scaling (High Water and each Race team)

| Players on the hollow | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| Creep health (per mille) | 1000 | 2000 | 2650 | 3400 |
| First window | 15 s | 25 s | 25 s | 25 s |
| Later windows | 10 s | 15 s | 15 s | 15 s |
| Start gold, each | 120 | 120 | 120 | 120 |
| Lives | 20 | 20 | 20 | 20 |

Two players were tuned by the M2 balance gates (§4.4) from 1850: a Lamplighter and a Lookout cleared the waves so
fast that their match fell short of eleven minutes. Each extra player brings a full solo income (§4.1), so the team
has n times the gold. Health grows a little slower
than n, because coordination costs time and the best tiles are shared; team effects push the other way. Seats
held by a caretaker count. The balance gates (§4.4) run every player count, so none can drift.

### 2.6 Difficulty

v1 had one difficulty, so the balance gates stayed at 4 Builders by 4 player counts. The first playtest (`halv`,
session 1, P5) found High Water solved by the third match: one build held with 16 of 20 lives and raced the
caretaker with all 20, and no match came down to wave 12. **M8 adds two levels**, chosen for the whole party as the mode is: **Normal** (the default, the
game as the gates tuned it), **Hard** and **Very Hard**. A level lays a few numbers over the mode's preset. It never
changes the waves, the counts, the gold or the windows, so the wave list and every tooltip read the same, and only
the creeps' plates and the lives show the difference.

| Over the mode's preset | Normal | Hard | Very Hard |
|---|---|---|---|
| Creep health, per mille, after the wave growth and the seat scaling | 1000 | 1100 | 1150 |
| A boss's health instead (the Bristlesow, the Hollowtide Crest) | 1000 | 1500 | 1550 |
| A boss's armour | +0 | +1 | +1 |
| Lives | 20 | 15 | 10 |
| Bounties, start gold, clear bonus, windows, Ready's pay, tolls | the preset's | the same | the same |

- **Numbers** (all *tunable*, `SimContent.DIFFICULTIES`; tuned by the gates, §4.4, from the first proposal's 1300
  and 1600 creep health and Very Hard's 2000 and +2 for the bosses). Solo, wave 12's Crest has 2,625 health and
  armour 4 at Normal, about 3,940 and 5 at Hard, about 4,070 and 5 at Very Hard; wave 6's Bristlesow 1,125 and 6,
  about 1,690 and 7, about 1,740 and 7. The gold stays Normal's, so more health is harder by itself. At Very Hard
  the Crest's toll is every life the team has: it must die on the road, which is what "a close wave 12" asks for.
- **Exactly** (`SimWaves.spawn`): `max_hp = hp × (1000 + growth) × seats_pm / 1000000`, as before, then
  `× level_pm / 1000`, where `level_pm` is the level's boss health for a boss and its creep health for any other
  creep. A boss's armour gains the level's boss armour where the rules turn armour on. At Normal the health is
  1000 per mille and the armour +0, which changes no number and no state hash.
- **Modes.** High Water and Tide Race take a level; a race's two teams play the same one. Undertow plays Normal
  only (§1.4) and classic keeps M1's game.
- **Where it lives.** The party's leader picks it, like the mode (§5.2); a change clears every Ready. Offline and
  in a party of one it is the profile's, saved like the mode. Every match the hub starts plays the level it shows:
  Play, Try and Race the caretaker; Duel the caretaker plays Normal. `MATCH_CONFIG` carries it, and the queue
  matches only parties of one level (§6.5, §6.9).
- **On screen** the levels are plain words (`world.md`): Normal, Hard, Very Hard. A level other than Normal is
  named wherever the mode is: the hub's mode line, Match Found, the loading title, the results and the Esc menu.
- **The caretaker** plays the same plan at every level, and stacks waves only at Normal (§2.7). A plan may later
  carry a level's own block; M8 adds none.
- **Gates** (§4.4): the plan bots must win Hard with a third of their lives; at Very Hard they must reach wave 12's
  Crest and end close: the Crest dies, or reaches the Holdfast with at most a quarter of its health left, a win
  keeps at most half the lives, and at least half the crews (each Builder alone, the two complementary pairs) win.
- **Very Hard's bosses, measured** (2 November 2026, the playtest `halv` s3, H3-02: "a wall at wave 6, not a close
  wave 12"; the plan bots, the caretaker playing each plan). At the first 2000 and +2 every Builder alone stood to
  wave 12 and fell to a Crest of 5,250 and armour 6 it had dealt 74 to 94% of; of the six crews only the Lamplighter
  with the Lookout won, and the gates passed, since any fall to wave 12 counted as close. At 1550 and +1 (Hard's
  armour) the Lamplighter, the Lookout, the Bellfounder and the Beekeeper alone and the Lamplighter with the Lookout
  kill the Crest 67 to 83 s into a walk of 87 to 91 s and win on 4, 5, 1, 4 and 4 lives, and the Bellfounder with the
  Beekeeper leaks it with 4% of its health left. At 1600 four of the six won, the Beekeeper's Crest dying 1 s from
  the Holdfast; at 1650 two; at +2 with 1550 three. The Bristlesow still takes 5 lives from every plan: its health
  stays above Hard's, where every plan leaks it too, and the best opening, the Beekeeper's, deals 86% of it (the
  Lookout's 74%, the Bellfounder's 65%, the Lamplighter's 61%, since their openings answer it at Normal, §2.4; 31%
  and 37% before), where it dealt 64% of the first one (2,250 and armour 8; the Lamplighter's 24%). A plan that
  killed it would win with more than half its lives, which the gates call no close wave 12, so the lives it takes
  are the level's. The playtester's two builds left the first one at 50% and
  40% of its health; at about a fifth less health to deal and an armour less on each hit they would come within
  roughly a third and a fifth of killing this one (an estimate, not measured). Creep health cannot take over the
  bosses' part: from 1167 a Clapper Tower's strike (35) no longer takes wave 2's Gourdling (30.00 at Normal) and the
  Bellfounder alone falls on wave 2.

### 2.7 Stacked waves (M8)

The same playtest (P6) found Ready no decision: it paid 9 to 11 gold every window and the next wave still came
only after the clear, so it was "a tax on not clicking". M8 lets a wave be called while the last still walks, as
sending early did in Element TD, and pays for the risk. The owner's decision of 2 November 2026 (§10, item 18):
**the waves truly overlap.** A first version held the stacked horn until the Welling had sent the newest wave's
last creep, so a stacked wave walked one interval behind it: the road read as one long wave, a skipped window cost
nothing (building is allowed during a wave), and stacking every wave was always the best play.

- **When Ready counts.** In a build window, as before. During a wave, in a mode that stacks (High Water and Tide
  Race: `stack_max` 3, tuned), a present player's Ready is taken while fewer than three waves are on the hollow's
  road, the newest is not the last wave, and no seat of the hollow is returning from the caretaker (its hand-back
  needs a window, §6.7). Otherwise it is refused (`NO_STACK`), and the screen says why. Un-Ready is always taken.
  A Ready names the wave it calls (`READY`'s `b`: the window's wave, or during a wave the next), and is taken only
  for that wave (M8's review): online a press made in a window's last moments may land after the window's horn,
  and there it is refused (`WRONG_PHASE`, unsaid, as a Ready too late for its horn always was) instead of calling
  the wave after it, or, beside a partner, standing as a call for it and carrying into the next window.
- **The stacked horn** sounds on the tick the call is complete: the tick the Ready lands that leaves every present
  player of the hollow Ready (caretaken seats count, as in a window; with company a Ready said earlier waits for
  the partners, as in a window). The called wave sets out at once: its first creep leaves the Welling on the
  horn's tick, as at a window's horn, and the rest follow at the intervals its groups list, counted from that tick.
  Whatever the older waves have still to send keeps its own schedule, on the ticks it had. Both schedules run and
  the Welling sends both, so the waves' creeps walk the road among each other; on a tick when both send, the older
  wave's creep comes first. **More creeps at once is the risk**: a call on the tick after the wave before sounded
  puts both whole waves on the road together, twice the creeps in the same seconds.
- **The timing is the decision.** A call early in a wave walks the waves together and stakes all of the older; a
  call once the older has set out in full stakes only what still walks and puts the new wave in behind it. Both
  skip the window; the early one is faster, pays more and is the riskier.
- **On the road.** A wave is on the road from its horn until it clears. Wave *k* clears when every creep of waves
  1 to *k* has set out (an older wave may still be sending after a younger was called) and none of them is on the
  road, so waves clear in order: a younger wave whose creeps are all gone clears in the same tick, right after the
  older one. The hollow counts its waves cleared, each creep knows its wave, and each creep grows with its own
  wave's health (§2.4), whenever it sets out.
- **Gold.** Bounties pay at each kill, as always. Each wave's clear pays its own clear bonus (8 + 2 × its number)
  and the Hive Tithe, whenever it clears; stipends are the duel's, which never stacks. A window's horn pays one
  gold per whole second left, as before. A stacked horn pays each player the **whole window it skips** (10 s solo,
  15 s with company: 10 or 15 gold) plus the **stake**: 0.4 gold (`stake_pm` 400, tuned) for each life the waves
  on the road could still take at the horn, rounded down: the tolls of their creeps walking the road and of those
  the Welling has still to send. Calling wave 2 on the tick after wave 1's horn (its ten Gourdlings to come) pays
  10 + 4; calling wave 3 at once after that (wave 1's ten and wave 2's eighteen) pays 10 + 11; calling the Crest's
  wave once wave 11 has set out with 18 lives' worth still walking pays 10 + 7.
- **Why the stake, not the time saved.** The stake is known when the call is made, so the strip can show it
  before the player commits, and it grows with exactly the risk taken: how much of the waves on the road is still
  to reach the Holdfast, all of it for a call made while the older wave is still setting out. Paying for the time
  between the call and the older wave's clear would pay more the longer a weak defence let that wave linger. Time
  saved is still rewarded where it matters, in Tide Race's clock.
- **Why three, and 400.** With two waves at most, a plan bot alone held two waves at once with lives to spare:
  stacking every wave cost the Lamplighter one life against her list's at any stake and the Beekeeper none, so it
  was still free. With three, stacking every wave costs every Builder alone at least five lives against its list,
  or its Holdfast (§4.4), while the lists still pay. Above about 700 the stake's gold buys those lives back.
- **Windows.** No window comes between stacked waves: the call skips it. When the last wave on the road clears,
  the next window opens with its usual length (10 s solo, 15 s with company), or the hollow is done after its last
  wave. Wave 1 always comes from the first window. A Ready said during a wave that clears before its horn sounded
  (a partner was not Ready yet) carries into the window that opens.
- **Co-op.** Every present player Ready, as in a window: one player cannot stack the team alone. The party strip
  shows Ready marks during a wave too, and "Waiting for you" glows in a wave as in a window.
- **Tide Race.** Each hollow stacks on its own clock, otherwise unchanged. Race time counts as before, at a minute a
  life since M8 (§1.3). A Holdfast that falls with two or three waves on its road fell on the oldest (its waves
  cleared plus one), and "more of that wave's creeps killed" counts the kills of that wave's creeps, whichever horn
  they came with. The rival line names the waves on the rival's road: "Rival · Waves 8–9 · 18 lives · 6:12 +120 s".
  In a race, time is the reward and a life costs a minute, so stacking every wave wins a race only for a crew whose
  defence holds three waves at once without a leak; a crew that leaks to it loses to the same crew calling its
  lists, and one that cannot hold the waves together falls (§4.4's `race_stacking_every_wave_not_dominant` and
  `race_pair_stacking_every_wave_not_dominant`). At M6's 10 s a life stacking every wave won by about 2x for a crew
  of two (the Lamplighter and the Lookout 13,220 against 26,597, the Bellfounder and the Beekeeper 17,233 against
  26,545): the minutes it saved bought back every life it cost. Measured after the fork pass, the crews of two that
  leak to it need at least 2,445 ticks a life to lose (the Bellfounder and the Beekeeper clear wave 12 at 14,234
  with 5 lives lost against 26,458 with none), the Lamplighter alone more than 2,628; at 3,600 each loses by a
  minute and a half or more. The three crews whose defence holds three waves without a leak more than their lists
  cost (the Lamplighter with the Lookout or the Beekeeper, who lose nothing either way, and with the Bellfounder,
  who lose 6 lives stacking every wave and 5 calling their lists) still win by stacking every wave: there the
  defence earns its time.
- **Undertow and classic** never stack (§1.4): Ready in their waves stays refused as before.
- **The caretaker** stacks only where it calls waves itself: in a race (as M6's caretaker calls each window's
  wave) and for the harness's seats played by command that stack (the gates, §4.4). Beside a present player it
  only counts as Ready, as before: the players decide. A plan names the waves it stacks (`"stack"` in
  `data/plans/<builder>.json`): the caretaker says Ready during wave *k* − 1 for each listed wave *k*, once the
  build steps it can pay for are done and its step does not hold Ready, so its horn sounds early in that wave and
  the listed wave walks with the one before. It never stacks at Hard or Very Hard. The lists (*tunable*) stack each
  Builder's own checks during a wave of its own checks, never behind a boss: the Lamplighter waves 2 and 3 (so her
  waves 1 to 3 set out together), the Lookout 5, the Bellfounder 4, the Beekeeper 2.
- **On screen** (§5.7): the strip names the waves on the road ("Waves 6–7 / 12", "Waves 6–8 / 12"); the Ready
  slot's tooltip names the wave it would call, its checks and what it would pay now ("Call wave 8 now: +10 for the
  window, +7 for the lives on the road"); during a wave a call takes a second press within 2 s, so a stray key
  never sends a wave; the horn's banner reads "Wave 8 called early · +17 gold".

---

## 3. Builders

### 3.1 Two axes: role and coverage

A Builder has **one role** (its identity in a word, shown with an icon) and a **coverage profile** over the four
checks (what makes the team's makeup matter). Roles are labels, never locks: no queue or party ever requires one.

| Role | Icon | Job | v1 Builder |
|---|---|---|---|
| **Warden** | wall-stone | hold the road: area damage and slows | Tamsin Wick, the Lamplighter |
| **Marksman** | feather | delete the big and the high: heavy single hits, anti-air | Edda Greyplume, the Lookout |
| **Breaker** | bell | stop and break: stuns, heavy bronze, cracked armour | Ottilie Brass, the Bellfounder |
| **Sweeper** | bee | blanket the road: clouds that reach the sky, hives that pay | Sefa Amberwell, the Beekeeper |
| **Kindler** (after v1) | candle | light and amplify; answers the Veiled check | a fifth Builder |

### 3.2 Checks and the damage model

| Check | Glyph, and the creep that teaches it on Wickhollow (its portrait sits beside the glyph) | What it demands | Answered by |
|---|---|---|---|
| **Swarm** | Froth; Gourdling packs | hitting several at once | splash, bounces, clouds |
| **Swift** | Runnel; Scuttler | keeping them in range | slows, stuns, fast fire |
| **Armored** | Ballast; Thornback (and both bosses) | big hits | heavy hits, armour piercing, cracks |
| **Winged** | Spindrift; Duskmoth | reaching the sky | towers flagged `air` |

There is **no attack and armour table to learn**. Two rules carry the checks:

- **Flat armour per hit, with a floor.** In the simulation's units (hundredths):
  `raw = hit × (1000 + mark‰) / 1000`, `armour_left = max(0, armour − pierce − crack − passive)`,
  `dealt = max(raw − armour_left, raw / 4)`. An 8-damage arrow does 4 to a Thornback (armour 4); a 32-damage bolt
  that pierces 3 does 31; a 3-damage bee sting does 0.75. Many small hits are weak against armour by construction.
- **Winged is binary.** A tower without `air` cannot target a winged creep, and its splash, pulse or cloud does not
  touch one.

**Team effects never stack; the strongest applies.**

| Effect | Comes from | On | Rule |
|---|---|---|---|
| Slow | Frost Spire; also Pinning Ballista, Drowsy Clay Hive, Sky Toll on fliers | creep | the strongest active slow applies, scaled by control resistance, for its own time; a weaker slow with time left waits under it and takes over when it lapses |
| Stun | Toll Tower | creep | speed 0 for the duration; then 1 s of stun immunity, so stuns cannot chain; on a boss, a 50% slow instead |
| Mark | Owl's Eye | creep | takes +X% from every tower; the strongest mark applies (of two as strong, the one lasting longest, and its player earns the Help); lasts while the Eye keeps it in range, plus 1 s, so an Eye that re-picks leaves its last creep marked for that second (a lingering mark, not a stacked one) |
| Crack | Chime Post | creep | armour reduced by X while inside the post's radius; the strongest applies |
| Haste | Hive Hum | tower | cooldown divided by (1 + X); the strongest hive in range applies; recomputed when any tower or hive is built, forked or sold |

**Help.** When a hit lands on a creep that another player's tower has slowed, stunned, marked or cracked, or comes
from a tower another player's hive hastens, the damage dealt is added to that player's **Help**, in full, once
for each distinct helper. Damage and Help count what each hit dealt, the last hit's overkill included, as the Damage
column has since M1 (it is in every match's state, classic's recorded hashes among them). Results show Help next to
damage, so support is visible.

**Targeting** (ties always go to the lower creep id): towers fire at the creep furthest along the road and keep it
until it dies or leaves range; the Hawk Roost and the Apiary prefer winged creeps; the Owl's Eye marks the highest
current health; the Toll Tower and the Clay Hive pulse at everything in reach.

### 3.3 Coverage of the v1 roster

● strong · ◐ passable through a fork branch · ○ weak · ✕ cannot (Winged only)

| Builder (role, difficulty) | Swarm | Swift | Armored | Winged | Complementary partner |
|---|---|---|---|---|---|
| Tamsin Wick, the **Lamplighter** (Warden, ★) | ● | ● | ○ → ◐ Iron Mortar | ✕ → ◐ Skyward Loft, Rime Spire | Lookout |
| Edda Greyplume, the **Lookout** (Marksman, ★★) | ○ → ◐ Kestrel Flock | ○ → ◐ Pinning Ballista | ● | ● | Lamplighter |
| Ottilie Brass, the **Bellfounder** (Breaker, ★★) | ○ → ◐ Ringing Clapper | ● | ● | ✕ → ◐ Sky Toll | Beekeeper |
| Sefa Amberwell, the **Beekeeper** (Sweeper, ★★★) | ● | ○ → ◐ Drowsy Clay Hive | ○ → ◐ Queen's Guard | ● | Bellfounder |

- **The cycle.** Each Builder is strong on two neighbouring checks. Of the six possible duos, exactly two
  (Lamplighter with Lookout, Bellfounder with Beekeeper) are strong on all four, which is the smallest roster where
  the choice of partner matters (`gaps.md` §5). Any trio or quartet of different Builders is strong on all four;
  there the team's makeup matters through **depth**, which the double-check waves 7 to 11 test, and through which
  team effects it brings.
- **Duplicates** are allowed in a party; four Lamplighters have no strong answer to Armored or Winged, and the
  coverage row says so before the match.
- **A fork lifts a weakness to passable, never to strong.** Every Builder can win alone with the right forks
  (a balance gate, §4.4); teams still do better. Passable takes numbers: one tower of a patch branch holds the
  early waves of its check alone (those before wave 6), at every level, and some of every later one gets past it;
  the plans, which hold their Builder's weak checks alone (none of those creeps leaks at Normal, a few at Hard and
  Very Hard), build one to four of each beside their Builder's other towers. The Sky Toll holds even
  wave 5 only inside a bend (7 of Wickhollow's 206 cells; outside a bend it takes none of the 8 Duskmoths), and
  the Rime Spire and the Drowsy Clay Hive, which slow, hold no wave alone. The branch's glyph says so
  (`Game.lifts_line`, held to the simulation by `patch_lift_words_measured`).
- **Each of waves 7 to 10 is one Builder's strong pair**, so every Builder has "its" wave and its partner shares
  the load.

### 3.4 The roster

Costs in gold; damage per hit; cooldown in seconds; range and radii in tiles. The tables follow the numbers as M8's
fork pass (§3.8) left them; `content.gd` holds them, each tuned one with its reason (the M2 and M6 balance passes and
the fork pass). Every fork costs its "Fork" price whichever branch is taken, and a fork is
final. Keys are positional (§5.7): the three towers sit on Q, W and E for every Builder; on a selected, unforked
tower of yours, Q and W choose branch A and branch B.

#### Tamsin Wick, the Lamplighter · Warden · ★ (the recommended first Builder)

*Wickhollow's lamplighter: a broad, cheerful woman in a waxed oilskin coat with a brass lighting pole and a ring of
keys. She knows every bend of the road and lights it at dusk.* She plays forgivingly: place, try, sell and place
again. Strong against Swarm and Swift. **Signature:** slow, then splash: the Frost Spire holds a crowd where the
Cannon lands.

**Passive, Thrifty:** her towers sell for 90% of what was paid instead of 70%.

| Tower (key) | Cost | Base | Fork | A, deepen | B, patch |
|---|---|---|---|---|---|
| Arrow Tower (Q) | 40 | 8 dmg, 0.5 s, range 3.2, ground | 60 | **Longbow Loft**: 16 dmg, 0.4 s, 3.6 (today's upgrade and model) | **Skyward Loft**: 12 dmg, 0.45 s, 3.6, **air** |
| Cannon Tower (W) | 70 | 20 dmg, splash 1.1, 1.5 s, 3.0, ground | 80 | **Great Cannon**: 40 dmg, splash 1.35, 1.3 s, 3.3 (today's) | **Iron Mortar**: 52 dmg, splash 0.6, 1.4 s, 3.3, pierces 4 armour |
| Frost Spire (E), **team: slow** | 60 | 4 dmg, 0.9 s, 2.8, slows 45% for 2 s, ground | 60 | **Deep Frost**: 8 dmg, slow 60%, 3.2 (today's) | **Rime Spire**: 6 dmg, slow 40%, 3.2, **air** |

#### Edda Greyplume, the Lookout · Marksman · ★★

*An owl-folk lookout from Fogholm, tall and grey-feathered in a hooded leather mantle, who left the high perches
over the fog-sea to do something about the Tide. She speaks rarely and does not miss.* She plays few, expensive
towers on long sight lines; the target matters more than the count. Strong against Armored and Winged.
**Signature:** the mark, v1's only amplifier, which makes every teammate's hits land harder on the creep that
matters.

**Passive, Keen Sight:** her towers reach 0.4 tiles farther.

| Tower (key) | Cost | Base | Fork | A, deepen | B, patch |
|---|---|---|---|---|---|
| Perch Ballista (Q) | 75 | 32 dmg, 1.6 s, 4.0, **air**, pierces 3 | 90 | **Siege Perch**: 64 dmg, 1.5 s, pierces 6 | **Pinning Ballista**: 36 dmg; each hit slows 50% for 1 s |
| Hawk Roost (W) | 55 | 10 dmg, 0.7 s, 3.4, **air**, prefers winged | 70 | **Falcon Roost**: 18 dmg, 0.55 s | **Kestrel Flock**: 9 dmg; each strike bounces to 3 more creeps within 1.2 |
| Owl's Eye (E), **team: mark** | 65 | no damage; marks the highest-health creep within 3.6: +20% damage taken from every tower | 70 | **Owl's Glare**: +35% | **Twin Gaze**: marks the two highest, +25% |

#### Ottilie Brass, the Bellfounder · Breaker · ★★

*A stout bell-caster from Brackwater with scorched leather gloves and a hammer on a chain, who casts the storm bells
that ring when the dikes are threatened. A bell struck at the right moment stops wrack dead.* She plays on
placement and timing: stun the creeps where the road bends, then break them where they bunch. Strong against Swift
and Armored.
**Signature:** the Toll Tower's stun pulse, v1's only hard control, and the Chime that cracks armour for everyone.

**Passive, Bronze Hand:** her hits ignore 2 armour.

| Tower (key) | Cost | Base | Fork | A, deepen | B, patch |
|---|---|---|---|---|---|
| Clapper Tower (Q) | 75 | 35 dmg, 1.4 s, 2.6, ground | 85 | **Great Clapper**: 80 dmg, 1.4 s, 2.8 | **Ringing Clapper**: 32 dmg, splash 1.2, 1.3 s |
| Toll Tower (W) | 65 | a pulse every 2.4 s: 8 dmg and a 0.6 s stun to every ground creep within 2.2 | 70 | **Great Toll**: 10 dmg, 0.9 s stun, 2.6 | **Sky Toll**: 9 dmg, 2.4; also reaches fliers, which take 160% more (23.4) and are slowed 33% for 2 s instead of stunned |
| Chime Post (E), **team: crack** | 60 | no damage; creeps within 2.5 have 2 less armour | 60 | **Deep Chime**: 4 less | **Long Chime**: 3 less, radius 4.0 |

#### Sefa Amberwell, the Beekeeper · Sweeper · ★★★

*A wiry, sun-browned beekeeper from Thousandwell in a veiled straw hat, who keeps her bees in clay pipes on the
rooftops and talks to every hive. When the Tide came up the wells, only her bees would go down after it; they chase
anything that crawls or flies, and the honey pays her way.* She plays greedy: clouds over the road and hives that
pay, timed against what the next wave brings. Strong against Winged and Swarm.
**Signature:** bee clouds that hit ground and sky alike, and the only personal income in co-op.

**Passive, Hive Tithe:** each Clay Hive and Hive Hum she owns pays her 2 gold at every wave clear, at most 12. The
clear's banner names it beside the bonus ("Wave 1 cleared · +10 gold · Tithe +4"), as a duel's names its stipend.

| Tower (key) | Cost | Base | Fork | A, deepen | B, patch |
|---|---|---|---|---|---|
| Clay Hive (Q) | 60 | a bee cloud over the foremost creep within 3.0 stings every creep, ground or air, within 0.9 of it: 3 dmg every 0.3 s | 70 | **Great Clay Hive**: cloud 1.2, 5 dmg | **Drowsy Clay Hive**: 1.5 dmg; stung creeps are slowed 35% for 1 s |
| Apiary (W) | 85 | 18 dmg, 0.8 s, 4.2, **air**, prefers winged, +50% to fliers | 80 | **Royal Apiary**: 24 dmg, +135% to fliers | **Queen's Guard**: 54 dmg, 1.43 s, pierces 4, no flier bonus, aims at the creep with the most health in reach |
| Hive Hum (E), **team: haste** | 60 | no damage; every tower within 2.2, whoever owns it, fires 15% faster | 70 | **Great Hum**: 25% | **Long Hum**: 18%, radius 3.0 |

### 3.5 How the three existing towers fit in

- They are the Lamplighter's kit, unchanged at base level. Their level-2 models and numbers become branch A, so
  every existing model, icon and the solo game's feel carry over.
- Branch B needs three new models (Skyward Loft, Iron Mortar, Rime Spire), made as kit mesh recipes in
  `art_src/models/towers/` that reuse the base mesh and change the crown, head or roof.
- The Arrow Tower becomes ground-only. Today nothing flies, so no current behaviour changes.
- A new profile starts with the Lamplighter selected and the others shown by difficulty, because High Water opens
  with her two checks.

### 3.6 Ownership, unlocks and "manage Builders"

- **Everything is unlocked.** No accounts, no currency. A LAN server cannot verify ownership anyway, and gating
  gameplay behind grind costs goodwill (`builders.md` §4.4).
- **"Manage Builders" in v1** means the Builders screen: browse the roster, read each kit (towers, both branches of
  every fork and the check each branch helps), set a **main** and a **backup**, and **Try** one solo. Main and
  backup live in `user://profile.cfg`. This reading is a decision for the user to confirm (§10).
- **Duplicates:** allowed in a party; friends settle the makeup in the party panel with the coverage row as the
  hint. When the queue fills open seats with strangers, the server avoids duplicates: whoever queued first keeps
  their main, the other gets their backup, and a still-clashing seat gets a free Builder from the server's
  random number generator. The server decides and writes the result into `MATCH_CONFIG`, so no client rolls dice.
- **Builders on the map:** not in v1. A Builder appears as a live model in the hub's arched portrait, on its card,
  on loading cards and as an icon on result rows; in a match a player's presence is the pennant colour and shape
  on every tower they own and their row in the party strip. An idle avatar at the owner's last build site is the
  first candidate after v1; it needs no rule change.
- **Progression**, if it ever comes, unlocks cosmetics only (pennant patterns and colours), never Builders.

### 3.7 Art budget

| Item | Count | Pipeline |
|---|---|---|
| Tower models | 36 = 4 Builders × 3 towers × (base + 2 branches); 6 exist, **30 new** | kit mesh recipes in `art_src/models/towers/`; branches reuse their base mesh and change the head or roof, roughly halving the work |
| Projectiles and effects | ballista bolt, hawk, bee; bell ring, chime shimmer, bee cloud and mark rune as `Fx` | kit mesh recipes and `scripts/fx.gd` |
| Creeps | Duskmoth (new); Bristlesow (scaled, tinted Thornback) | Blender build script in `art_src/blender/` |
| Builder characters | 4, each a posed figure with a signature prop and a short idle cycle; portraits and cards only, so no walk cycle | Blender build scripts |
| Icons | 30 towers, 4 Builders, 4 roles, 4 check glyphs, the Duskmoth, Signal, Ready | `godot-agent asset icon`, then `art_src/ui/icons.py` |
| Sounds | signal chime, ready, toll, chime hum, bees, mark, match found, countdown tick | `godot-agent asset sfx` |
| Console pieces | loading card plate, wide results plate, party strip plate, join panel, queue pill | `art_src/ui/console.json` and `console.py` |

Order of production: the Lamplighter's three B branches, the Duskmoth and the whole Lookout in M2 (the
complementary pair first); the Bellfounder and the Beekeeper in M6. Art can start the day M2's content format is
fixed and runs beside everything else.

### 3.8 Fork jobs and the fork pass (M8)

The first playtest (P7) found the Beekeeper's Apiary fork no choice: the Queen's Guard (50 every 1.2 s, pierces
3) and the Royal Apiary (34 every 0.8 s) do 41.7 and 42.5 a second at armour 0, 40.8 and 37.5 at 4, 39.2 and 35 at
6, and 62.5 and 63.8 to a flier, within 10% on every job. Other forks were real choices (Longbow or Skyward, Great
Cannon or Iron Mortar). M8's fork pass gives every branch a job, measures each pair on both jobs in the
simulation, and spreads the pairs so each branch wins its own clearly.

**Each branch's job**, from §3.4's deepen and patch and the check a branch helps:

| Builder | Tower | Branch A and its job | Branch B and its job |
|---|---|---|---|
| Lamplighter | Arrow | Longbow Loft: one ground creep | Skyward Loft: one flier |
| | Cannon | Great Cannon: a crowd | Iron Mortar: armour |
| | Frost Spire | Deep Frost: holding ground creeps | Rime Spire: holding fliers |
| Lookout | Perch Ballista | Siege Perch: armour | Pinning Ballista: holding ground creeps |
| | Hawk Roost | Falcon Roost: one flier | Kestrel Flock: a crowd |
| | Owl's Eye | Owl's Glare: lifting the team on one big creep | Twin Gaze: lifting the team on a pack |
| Bellfounder | Clapper Tower | Great Clapper: armour | Ringing Clapper: a crowd |
| | Toll Tower | Great Toll: holding ground creeps | Sky Toll: fliers (damage and slow) |
| | Chime Post | Deep Chime: lifting the team on high armour | Long Chime: lifting the team along more road |
| Beekeeper | Clay Hive | Great Clay Hive: a crowd | Drowsy Clay Hive: holding ground creeps |
| | Apiary | Royal Apiary: one flier | Queen's Guard: armour |
| | Hive Hum | Great Hum: lifting a tight battery | Long Hum: lifting a wide battery |

**The measurements** (the fork bench, `tests/sim/fork_bench.gd`): bare simulations in the sim harness, High Water
at Normal, one seat of the form's Builder with its perk (Bronze Hand and Keen Sight count), the form built and
forked on the bench cell (8, 11), between the two lower stretches of road, where the Lamplighter's plan starts.
Both branches of a pair stand on the same cell against the same creeps. What a form does is read from the
simulation's HIT events as **health removed**: each hit's damage less the overkill of the hit that killed, so a
big hit on a small creep counts what it took, not what it rolled.

| Job | Measure |
|---|---|
| One creep: ground, flier | `single(creep)`: health removed per second from one creep at wave 12's health, held still in the middle of the form's reach, a fresh one the tick after it dies, over 60 s; a Gourdling (armour 0), a Duskmoth (a flier) |
| Armour | `single` against a Thornback (armour 4) and a Bristlesow (armour 6): both must hold |
| A crowd | `crowd(creep)`: the share of a line's health removed as 12 creeps at wave 7's health, spaced as wave 7 sends them, walk through the reach once; Gourdlings, and Duskmoths for a form that reaches them |
| Holding | `control(creep)`: the seconds a line of 12 Scuttlers (Duskmoths for a form that holds fliers) spends in the reach beyond its unslowed time, per creep |
| Lifting the team | `lift(lane)`: the extra health a fixed battery of another seat's towers removes on a lane because the form stands (the lane with it, less the lane without it). The battery is three Arrow Towers and a Cannon Tower of a Lamplighter around the bench cell, the lanes one held Bristlesow and a line of Thornbacks; a hum's tight battery is three Arrow Towers within 2.2 of it and its wide one six, three of them between 2.2 and 3.0, on a line of Gourdlings |

The two branches of a fork cost the same, so a pair's ratio is its ratio per gold too; across pairs the bench
reports each form's measures per gold for the record.

**Acceptance** (the `fork_pairs_apart` gate, §4.4):

1. On its own job each branch does at least **25%** more than its sibling (`JOB_MARGIN_PM` 250, *tunable*). A
   quarter is what a player sees at once in the tooltip's from-to numbers; within 10% is placement noise. A
   sibling that cannot do the job at all (a ground form against a flier) is apart by definition.
2. No branch beats its sibling by 10% on both jobs: a fork is a choice, never a trap.
3. A patch lifts its check to passable, never to strong: a patch branch's measure on its job is at most 90% of the
   best form, base or branch, of a Builder strong against that check.
4. Every balance gate still holds with its bar unchanged; where one fails, the plans move first (they are
   balance's first lever), then the numbers.
5. Every changed number sits in `content.gd` with the reason beside it, as the M6 pass's do. The numbers classic
   plays never change (the Lamplighter's three bases and her three A branches: `contract_ids_keep_state_hashes`
   holds the classic match to its recorded hashes). §3.4's tables, `fork_branch_stats` and the scenarios that pin
   a form's numbers follow the pass.

**Where the arithmetic points first** (one target, by the armour rule; the bench decides, and every number here
is a first proposal, *tunable*):

| Pair | On its own job today | First proposal |
|---|---|---|
| Royal Apiary, Queen's Guard | a flier: 63.8 against 62.5 a second (+2%); armour 4: 40.8 against 37.5 (+9%) | Royal Apiary 28 every 0.8 s, +100% to fliers: 70 a second to a flier against the Queen's Guard's 38.6 (+81%). Queen's Guard 54 every 1.4 s, pierces 4, no flier bonus, and aims at the creep with the most health in reach: 38.6 a second at armour 4 against 30 (+29%), 37.1 at armour 6 against 27.5 (+35%), 87% of the Siege Perch's 42.7, so still passable |
| Great Cannon, Iron Mortar | armour 4: 32.1 against 27.7 (+16%) | Iron Mortar every 1.3 s, not 1.4: 34.6 at armour 4 (+25%), 33.1 at armour 6 (+26%); the Great Cannon, which classic plays, keeps its numbers |
| Falcon Roost, Kestrel Flock | a crowd: 38.6 against 32.7 a second over three creeps (+18%) | Kestrel Flock 10 a strike: 42.9 (+31%) |
| Owl's Glare, Twin Gaze | a pack of two: 40% against 35% (+14%) | Twin Gaze marks two at +25%: 50% against 35% on a pack (+43%); Owl's Glare keeps +35% against 25% on one boss (+40%) |
| Great Hum, Long Hum | a wide battery: 6 × 15% against 3 × 25% (+20%) | Long Hum 18%: 108% against 75% (+44%); a tight battery stays Great Hum's, 75% against 54% (+39%) |
| Great Clapper, Ringing Clapper | a crowd of Gourdlings: about even by arithmetic | measure first |
| Deep Chime, Long Chime | Long Chime's reach against Deep Chime's depth: with Bronze Hand, a crack of 2 already strips a Thornback | measure first |

The Lamplighter's other two forks, the Lookout's Perch Ballista, the Bellfounder's Toll Tower and the Beekeeper's
Clay Hive split by air or by control and are expected apart already; the bench holds them too.

**What the bench measured, and what the pass set** (M8, track D; `fork_pairs_apart` prints one `FORK_BENCH` line a
pair). The bench reads the table above with choices of its own, each to keep a measure from saturating or from
resting on one set-up: a crowd's line has three times wave 7's health (at wave 7's own a lone Great Cannon removed all
of it, 1000 per mille, and every crowd form came out alike), a holding line and a lifting line fifty times (none dies,
so holding and the battery's extra damage are measured, not killing); a `single` is taken at every creep health the
game plays (one to four seats at every level: 1.0, 1.1, 1.15, 2.0, 2.2, 2.3, 2.65, 2.92, 3.05, 3.4, 3.74 and 3.91
times one seat's at Normal), since what the killing hit wastes moves with the health and decides how many hits a kill
takes; a crowd and a hold are taken on the bench cell and on every cell its Builder's plan builds the base on, since
a bend reaches more road than a straight; and the Sky Toll's job, fliers, is measured by the damage it does one and
by how long it holds a line of them (the Great Toll reaches none, so the pair is apart either way, and the slow is
held to the patch ceiling). A pair must be apart at every health and on every cell. Per pair, each branch on its own
job against its sibling, before the pass and after (single and lift per second or per mille as the table says;
armour at 4, then 6; after the pass, the bench's own health and cell, then the least lead over all of them):

| Pair | Before | After | What changed |
|---|---|---|---|
| Longbow Loft, Skyward Loft | ground 37.5 against 25.2; a flier 25.2 against none | the same (+40% at worst, at two seats' health) | nothing |
| Great Cannon, Iron Mortar | crowd 743 against 463; armour 30.8 and 30.8 against 25.6 and 26.1 (+20%, +18%) | crowd 743 against 534 (+31% at worst, 539 against 409 on (5, 12)); armour 35.9 and 35.4 (+32% at worst, 33.9 against 25.6 at Hard's health) | Iron Mortar 52 a shell, not 45, every 1.4 s with its burst of 0.6. The pass first set it every 1.3 s with a burst of 0.4: 25% ahead at Hard's health and 21% at two seats' (14 shells a kill against 17), and the faster mortar let the Lamplighter stacking every wave keep 10 or 11 lives against her list's 15, which the narrower burst bought back with a third of its crowd. At 52 every 1.4 s she keeps 5 |
| Deep Frost, Rime Spire | holding ground 0.55 s against 0.24; fliers 0.40 against none | the same | nothing |
| Siege Perch, Pinning Ballista | armour 40.0 and 41.9 against 21.2 and 20.9; holding 0.32 s against none | the same | nothing |
| Falcon Roost, Kestrel Flock | a flier 29.3 against 12.4; crowd 362 against 300 (+21%) | crowd 475 against 300 (+47% at worst, 429 against 291 on (13, 12)) | Kestrel Flock strikes bounce on to three, not two, at its 9 a strike. The pass first set 9.5: 27% ahead on the bench cell but 24% and 22% on (12, 8) and (6, 12), where the Lookout's plan forks it; 10 made the Lookout's duels defend so well that the balanced corker drew the turtle |
| Owl's Glare, Twin Gaze | one boss 999 against 571; a pack 98 against 93 (+5%) | one boss 999 against 709; a pack 122 against 93 (+31%) | Twin Gaze +25% on each of two, not +20% |
| Great Clapper, Ringing Clapper | armour 38.5 and 42.6 against 16.8 and 15.7; crowd 308 against 350 (the patch behind) | armour 53.9 and 54.0 against 23.5 and 21.9 (+103% at worst); crowd 549 against 425 (+25% at worst, 394 against 314 on (5, 12)) | Ringing Clapper 32 dmg in 1.2, not 24 in 1.0; Great Clapper 80 every 1.4 s, not 72 every 1.6 s, for Hard (below) |
| Great Toll, Sky Toll | holding 2.06 s against 0.97; a flier 6.7 against none | holding 2.06 s against 0.97 (+72% at worst, on (4, 11)); a flier 9.4 against none; fliers held 1.13 s (1.84 s on (14, 8)) against none | Sky Toll slows fliers by a third, not half, for 2 s, and does +160% to them, not +80%, for Hard (below) |
| Deep Chime, Long Chime | one boss 1238 against 617; a line 249 against 359 (the long one behind) | one boss 1238 against 937 (+32%); a line 481 against 359 (+34%) | Long Chime cracks 3, not 2, within 4.0, not 3.2: a crack of 2 over 3.2 tiles lifted a line less than Deep Chime's 4 over 2.5 |
| Great Clay Hive, Drowsy Clay Hive | crowd 405 against 429 (the deepening one behind: the slow kept creeps in the cloud); holding 0.74 s against none | crowd 504 against 271 (+48% at worst, 347 against 234 on (4, 12)); holding 1.35 s against none | Great Clay Hive 5 a sting, not 4; Drowsy Clay Hive 1.5, not 3, slowing 35%, not 25%, for 1 s (at 2 it still out-stung the Great one on (4, 12), 312 against 347; 40% for 1.5 s held 1.92 s, past 90% of the Great Toll's 2.06) |
| Royal Apiary, Queen's Guard | a flier 46.9 against 46.9; armour 35.8 and 39.1 against 37.5 and 35.0 (no choice, as the playtest found) | a flier 70.3 against 26.2 (+77% at worst, at Hard's health with two seats); armour 35.0 and 35.6 against 25.0 and 22.5 (+35% at worst, 33.0 against 24.3 at Hard's health) | Royal Apiary 24 and +135% to fliers, not 34 and +50% (56.4 takes wave 12's Duskmoth in two bolts); Queen's Guard 54 every 1.43 s piercing 4, no flier bonus, aiming at the most health in reach, not 50 every 1.2 s piercing 3. The pass first set the Royal Apiary at 27 and +110%: the Guard was then 20% ahead at Hard's health, and a Guard every 1.3 s killed the Bristlesow while the Beekeeper stacked every wave (stacking cost her 2 lives against her list) |
| Great Hum, Long Hum | a tight battery 224 against 130; a wide one 130 against 115 (+13%) | a tight battery 224 against 177 (+26%); a wide one 173 against 115 (+50%) | Long Hum 18%, not 15% (a 30-tick Arrow Tower fires every 25 ticks under anything from 16% to 20%, so 17% measures as 18%) |

Every patch stays under 90% of a strong Builder's best at its job, at every health and on every cell; the largest
shares: the Ringing Clapper 87% of the Great Cannon on (6, 12) (532 against 609), the Sky Toll's hold 83% of the
Drowsy Clay Hive's on (4, 11) (1.81 s against 2.16), the Queen's Guard 71% and the Iron Mortar 70% of the Great
Clapper, the Drowsy Clay Hive 70% of the Great Toll on (11, 11), the Kestrel Flock 66% of the Great Cannon on (12, 8),
the Skyward Loft 48% of the Royal Apiary, the Pinning Ballista 31% of the Great Toll and the Rime Spire 17% of the
Drowsy Clay Hive. The tightest leads are the Ringing Clapper's (+25% on (5, 12), with the Great Clapper's crowd on one
side and the Great Cannon's ceiling on the other: faster Great Clappers, every 1.33 s, leave it 24% ahead on (13, 8),
and it cannot rise 3% before it passes 90% of the Great Cannon on (6, 12)) and the Great Hum's (+26% on a tight
battery).

Two decisions the bench does not make. The Royal Apiary is the Apiary's anti-air, and the Queen's Guard also leads it
on unarmoured ground creeps (31.5 a second against 28.2 on one Gourdling, 341 per mille against 277 on a crowd): rule
2 compares the pair's own jobs, a flier and armour, and the Royal Apiary keeps the flier by 77% at worst. And the Sky
Toll's damage to a flock is not held to the ceiling: on its bends, (14, 8) and (4, 11), its pulse does to a line of
Duskmoths what the Royal Apiary does there (346 per mille against 354; 242 against 479 on the bench cell). It is the
Bellfounder's one tower for the sky, and her Hard (below) needs three pulses to take wave 5's Duskmoth; its hold on
fliers, the slow, is held. The Queen's Guard's aim at the most health is held by `queens_guard_aims_at_most_health`,
since the bench measures one creep at a time.

**Hard and Very Hard's openings** (the gates the rules track held, §4.4): any creep health above Normal's put wave
2's Gourdling past a Clapper Tower's one strike and a Hawk Roost's three, so the Bellfounder alone leaked 10 of wave
2 and the Lookout 6. The Clapper Tower now deals 35, one strike at every level (30.00, 33.00 at Hard, 34.50 at Very
Hard); then the Bellfounder alone still lost Hard to the Crest and wave 5's Duskmoths, so the Great Clapper hits 80
every 1.4 s, her plan builds her fourth Clapper and its Great Clapper before her third Toll Tower, and the Sky Toll's
pulse grew against fliers. It does +160%, 23.4 to a flier: once the review held its slow (a third, not half, for 2 s;
at half it held a flier 3.50 s on (14, 8) against the Drowsy Clay Hive's 2.30 there) a Duskmoth crossed her one Sky
Toll of wave 5 in a pulse less, and at the pass's +130% (20.7) three pulses left wave 5's (66.00 at Hard, 69.00 at
Very Hard) standing and 4 of them got through; at +80% four pulses of 16.2 did, and at +100% six of wave 11's 18
(115.50) stood and 4 got through. The Lookout's plan forks her first Hawk Roost into a Kestrel Flock before she
builds the second (its bouncing strikes clear wave 2 at any health) and builds her second Perch Ballista and forks it
into a Siege Perch before the Owl's Eye, so wave 8's Thornbacks meet it at Hard and Very Hard; her duel keeps M7's
order (her plan's `undertow` block), since the duel plays Normal only and its gates were tuned on it (with the new
order a Lookout that only defends drew the balanced corker). The Beekeeper's plan forks her first Queen's Guard
before her first Royal Apiary, the playtest's wave-4 armour hole, which also makes stacking every wave cost her 11
lives against her list's none, not 5. Measured: the Bellfounder alone wins Hard on 8 of 15 lives and the Lookout on
10, at Normal they keep 20 and 15 (15 and 13 before), and both fall to the Crest at Very Hard after standing to wave
12's horn (at its first bosses; since Very Hard's boss pass, §2.6, both kill it). The lives do not tell the margin
at Hard, though: the Crest's toll is 10, more than either keeps, so whether it dies decides the match. It dies 80 s
into its walk for the Bellfounder and 72 s for the Lookout, while it reaches the Holdfast at 88 s and 89 s at Very
Hard, where neither kills it: about 8 s to spare for the Bellfounder and 17 s for the Lookout. At Very Hard the
Bellfounder reaches wave 12's horn on 2 of her 10 lives (the Bristlesow's 5 and 3 Gourdlings of wave 7), the Lookout
on 5 (since §2.6's boss pass the Bellfounder kills that Crest at 82 s and wins on 1). The Bellfounder's 8 s are as
far as the Great Clapper goes: every 1.33 s it takes the Crest 2 s sooner and leaves the Ringing Clapper under its
25% (above). The Sky Toll's held slow also gave back the counter-corker's Bellfounder duel (§4.4): at the pass's
numbers its pulses held the winged packs the counter-corker sends (the same duel at +80% and half: the
counter-corker wins it), and `duel_counter_cork_beats_random` fell from 4 wins and a draw to 3; with the slow held it wins 4 again, its Bellfounder mirror by 8 lives to 7.

---

## 4. Economy and balance

### 4.1 Gold and lives

| Source or rule | Who | Value |
|---|---|---|
| Start | each player | 120 |
| Kill bounty | **every player on the team receives the creep's full bounty**, whoever's tower killed it | creep table |
| Clear bonus | each player | 8 + 2 × wave (today's formula) |
| Early Ready | when every present player of the hollow is Ready, each receives one gold per whole second left | 0 to 25 |
| Stacked call (M8, §2.7) | when every present player is Ready during a wave, each receives the whole window it skips plus one gold for each life the creeps on the road could still take | about 12 to 35 |
| Sell | the owner gets 70% of what was put in (Lamplighter 90%), rounded half up | |
| Hive Tithe | the Beekeeper | 2 per Clay Hive or Hive Hum at each clear, at most 12 |
| Interest | none: it rewards hoarding and widens skill gaps | |
| Gold gifts | none: income is equal by rule | |
| Lives | one pool per team; a leak costs the creep's toll | 20 (M8: 15 at Hard, 10 at Very Hard, §2.6) |
| Duel only (M7) | stipend: each uncorked pack's tier gain (+4, +6, +12), paid at every clear from then on; breach pays the sender 2 × bounty | |

Why "every player gets the full bounty" rather than a split: it keeps gold in integers with no remainder rule, it
makes everyone's income identical, and it leaves difficulty for 2 to 4 players to a single table (creep health).

### 4.2 Rules, units and content

The simulation's tables are authored **in integer units** in `scripts/sim/content.gd`; the HUD formats them for
people. Names, descriptions, model paths and icons stay in `scripts/game.gd`, keyed by the same ids, and are not
part of the rules hash. The lint (§6.4) forbids float literals in `scripts/sim/`, so a stray `0.5` cannot creep in.

| Quantity | Unit in the simulation | Example |
|---|---|---|
| Time | tick (1/60 s) | a 0.5 s cooldown is 30 ticks; a 15 s window is 900 |
| World position, range, radius | millimetre | a cell is 1,000 mm; its centre is `cell × 1000 + 500`; range 3.2 is 3,200 |
| Progress along the road | micrometre | the road is 50,000,000 µm |
| Speed | micrometres per tick | 1.3 m/s is 21,667 |
| Health, damage, armour | hundredths | 24 HP is 2,400; armour 4 is 400 |
| Slow, mark, haste, refund, scaling | per mille | 45% is 450 |
| Gold, lives, waves, ids | plain int | |

```gdscript
# scripts/sim/content.gd (excerpt). Every number is an int in the unit its key names.
const SIM_VERSION := 1

const RULES := {
	"high_water": {
		"teams": 1, "seats": [1, 4], "map": "hollow", "waves": "hollow12", "clock": "hollow",
		"start_gold": 120, "lives": 20, "hp_growth_pm": 250,
		"hp_by_seats_pm": [1000, 2000, 2650, 3400],
		"window_first_t": [900, 1500, 1500, 1500], "window_t": [600, 900, 900, 900],
		"sell_pm": 700, "clear_bonus": [8, 2], "ready_pays": true, "cap_t": 0,
		"stack_max": 2, "stake_pm": 1000, "levels": true,  # M8: stacked waves (§2.7), difficulty (§2.6)
	},
	"tide_race": {  # "high_water" plus:
		"teams": 2, "seats": [1, 2], "race": true, "life_penalty_t": 600, "cap_t": 72000,
	},
	"undertow": {  # M7; "tide_race" plus:
		"seats": [1, 1], "clock": "shared", "drift": true, "corks": [1, 2], "uncork_t": [180, 1500],
		"breach_mult": 2, "seawall": [4, 2], "surge_waves": 3, "surge_hp_pm": 1350, "surge_window_t": 480,
		"stack_max": 1,  # M8: no stacked waves and no "levels" in a duel (§1.4)
	},
}

const DIFFICULTIES := {  # M8 (§2.6): what a level lays over a preset with "levels"
	"normal": {},
	"hard": {"lives": 15, "hp_pm": 1100, "boss_hp_pm": 1500, "boss_armor_c": 100},
	"very_hard": {"lives": 10, "hp_pm": 1150, "boss_hp_pm": 1550, "boss_armor_c": 100},
}

const TOWERS := {
	"arrow": {
		"builder": "lamplighter", "slot": 0, "cost": 40, "dmg_c": 800, "cd_t": 30, "range_mm": 3200,
		"air": false, "shot_um_t": 233333, "fork_cost": 60,
		"a": {"id": "longbow_loft", "dmg_c": 1600, "cd_t": 24, "range_mm": 3600},
		"b": {"id": "skyward_loft", "dmg_c": 1200, "cd_t": 27, "range_mm": 3600, "air": true},
	},
	# ...
}

const CREEPS := {
	"gourdling": {"hp_c": 2400, "speed_um_t": 21667, "armor_c": 0, "bounty": 3, "toll": 1},
	"duskmoth": {"hp_c": 3000, "speed_um_t": 25000, "armor_c": 0, "bounty": 3, "toll": 1, "winged": true},
	"hollowtide_crest": {"hp_c": 70000, "speed_um_t": 10000, "armor_c": 400, "bounty": 60, "toll": 10,
		"boss": true, "control_resist_pm": 500},
	# ...
}
```

`rules_hash()` is the first 8 bytes of SHA-256 (through `HashingContext`) over a canonical byte dump of
`SIM_VERSION`, `RULES`, `TOWERS`, `CREEPS`, `WAVES`, `BUILDERS`, the caretaker plans in `data/plans/` and the map
text; from M8 also `DIFFICULTIES` and each plan's `stack` list, still one hash per build for every mode and level.
It is the matchmaking key (§6.9).

### 4.3 Knobs

| Knob | Start | Effect when raised |
|---|---|---|
| `hp_growth_pm` | 250 per wave | later waves harder; armour matters relatively less |
| `hp_by_seats_pm` | 1000 / 2000 / 2650 / 3400 | multiplayer harder |
| Window lengths | 15/10 s solo, 25/15 s team | more thinking time, longer match |
| `lives` | 20 | more forgiving |
| Tolls | 1 / 1 / 2 / 1 / 5 / 10 | leaks hurt more |
| Clear bonus | 8 + 2 × wave | more gold late, faster snowball |
| Fork prices | 60 to 90 | towers spread out rather than deepened |
| Armour | Thornback 4, Bristlesow 6, Hollowtide Crest 4 | the Armored check sharper |
| Control resistance | 30% Bristlesow, 50% Hollowtide Crest | slows and stuns matter less against bosses |
| Team effect sizes | slow 45%, mark 20%, crack 2, haste 15% | synergy stronger; watch for a must-pick Builder |
| `stack_max` (M8) | 3 waves on the road (tuned from 2: at 2 a defence held two waves together for free) | more overlap, faster races, harder to read |
| `stake_pm` (M8) | 400: 0.4 gold a life the waves on the road could still take (tuned from 1000) | stacking pays more; at too much, its gold buys back the lives stacking every wave costs, and that becomes the only play |
| `DIFFICULTIES` (M8) | Hard 1100 / 1500 / +1 / 15; Very Hard 1150 / 1550 / +1 / 10 (health, boss health, boss armour, lives; tuned from 1300 / 1500 / +1 / 15 and 1600 / 2000 / +2 / 10, §2.6) | the levels further apart |
| `JOB_MARGIN_PM` (M8, the fork bench) | 250 | each fork branch's job further from its sibling's |
| Race time a life (`tide_race` `race.life_t`) | 3,600 ticks, 60 s (M6's 600, raised in M8, §1.3) | lives count for more of a race than time; below about 2,450 a crew of two that leaks to stacking every wave wins by it |

### 4.4 Balance gates (how `bot_wins` and `idle_player_loses` extend to multiplayer)

`AGENTS.md`'s two gates become a matrix. Each case is a scenario.

- **Where they run:** a pure simulation (no views, no network) through `tests/sim/sim_harness.tscn`, which steps
  thousands of ticks per frame, so a 12-wave match takes seconds.
- **Who plays:** the bots *are* the caretaker. A seat marked as a bot from tick 0 is played by
  `scripts/sim/caretaker.gd`, which follows its Builder's plan in `data/plans/<builder>.json`. The gates therefore
  test the code that holds absent players' seats.
- **The command path stays covered:** `tests/bot.gd` stays as a thin wrapper that sends the same plan as commands
  through a client, so `bot_wins` exercises the real input route too.

| Gate | Cases | Must hold |
|---|---|---|
| `bot_wins` (kept) | 1 | the Lamplighter's plan, sent as commands through the local client, wins High Water solo with at least 10 lives |
| `bot_wins_solo_<builder>` | 4 | each Builder alone, forking for its weak checks, wins with at least 10 lives |
| `bot_wins_high_water_2p` / `_3p` / `_4p` | 3 | Lamplighter + Lookout; + Bellfounder; + Beekeeper: win with at least 10 lives |
| `idle_player_loses` (kept) | 1 | two towers and nothing else lose before wave 12 |
| `idle_team_loses_2p` / `_3p` / `_4p` | 3 | every seat builds two towers and nothing else; the Holdfast falls before wave 12 |
| `one_idle_of_two_loses` | 1 | one plan bot carrying an idle partner at two-player scaling loses: every seat matters |
| `caretaker_holds_seat_2p` | 1 | the two-player win above, with seat 2 caretaken from wave 4, still wins |
| `coverage_matters_winged` | 1 | two Lamplighters that never fork for air lose at least 4 lives on waves 5 and 8 |
| `coverage_holds_complementary` | 2 | both complementary duos lose at most 2 lives over waves 5 to 10 |
| `high_water_length_2p` | 1 | the two-player bot match lasts 11 to 15 minutes of match time |
| `race_mirror_is_fair` | 1 | the same plan on both hollows: equal lives and equal clear tick |
| `race_bots_both_finish` | 1 | one bot readies at once, one waits out every window; both clear wave 12 and the result follows the race-time rule |

M7 adds the Duel's gates: `duel_mirror_is_draw`, `duel_turtle_holds` (a defend-only bot against a passive rival
keeps at least 10 lives), `duel_balanced_beats_turtle` and `duel_turtle_beats_reckless` (each over seeds 1 to 5,
at least 3 wins), `duel_counter_cork_beats_random` (corking the rival's weak checks wins at least 3 of 5) and
`duel_seawall_saves`. The sends' pass adds `duel_sends_breach`: in the four Builders' mirrors, played by the
caretaker and by the balanced style over seeds 1 to 5, a third to a half of the uncorked packs breach, more than
a fifth of each tier's, at most four in five of tier I's, and some in every mirror (measured 41.5%: tier I 60%,
II 62%, III 30%; after the packs' matrix 48.1%: 60%, 73%, 39%). The packs' matrix adds one gate a pack,
`duel_<check>_pack_breaches_the_weak`: corked by the balanced style wherever the Drift offers it, in each Builder's
mirror against the caretaker over seeds 1 to 5 (`sim_harness.gd` `pack_matrix`), the pack breaches the two Builders
weak to its check in at least 40% of its uncorkings together and each of them in at least 30%, and those that
cover it less often (measured: the Gourd Rush 44% against 21%, the Scuttle 48% against 15%, the Thorn Herd 52%
against 17%, the Moth Cloud 83% against none; before it 0%, 4.5%, 30% and 78%).

M8 adds the gates of stacked waves, of the difficulty levels and of the fork pass. No gate above calls a wave
during a wave: High Water's are played by caretakers alone, which wait out their windows, or by seats that never
press Ready; the duel never stacks; and all play Normal. So M8's rules must leave each of their summaries exactly
as it was, except the two race gates, whose caretaker now stacks its plan's list (re-measured, bars unchanged).
After the fork pass every gate is re-run with its bar unchanged.

| Gate | Cases | Must hold |
|---|---|---|
| `bot_wins_stacking_<builder>` | 4 | each Builder's plan bot by command, Ready at once in every window and stacking its plan's list, wins High Water solo with at least 10 lives |
| `stacking_pays` | 1 | the solo Lamplighter stacking its list clears wave 12 at least 30 s of match time sooner than the same bot Ready at once that never stacks, and its stacked calls pay on average at least the window's 10 gold plus 3 |
| `stacking_every_wave_costs_lives` (the Lamplighter), `_lookout`, `_bellfounder`, `_beekeeper` | 4 | each Builder's plan bot alone stacking every wave it may, the moment its hollow can take it, loses at least 5 lives more than when it stacks its list, or falls: stacking is a decision, not free gold |
| `race_stacking_beats_calling` | 1 | Tide Race: a Lamplighter stacking its list against one that calls every wave at once from its windows; played on, both clear wave 12 and the stacker's race time is the lower |
| `race_stacking_every_wave_not_dominant` | 1 | Tide Race, a series over the four Builders (a race plays alike under every seed): a crew of one stacking every wave against the same Builder stacking its list wins at most two of the four races, and the list wins the others |
| `race_pair_stacking_every_wave_not_dominant` | 1 | Tide Race, the same for crews of two: the two complementary pairs and each M2 Builder beside each M6 one, every wave against the crews' lists (beside a present partner each seat calls only its own list); the crew stacking every wave wins at most three of the six, the lists the others, and it stacked more in every race |
| `bot_wins_hard_solo_<builder>` | 4 | each Builder alone wins Hard with at least 5 of its 15 lives |
| `bot_wins_hard_2p` | 1 | the Lamplighter and the Lookout win Hard with at least 5 lives |
| `bot_reaches_crest_very_hard_solo_<builder>` | 4 | each Builder alone stands until wave 12's Crest at Very Hard, which dies or reaches the Holdfast with at most a quarter of its health left, and a win keeps at most 5 of its 10 lives: a close wave 12, as the playtest asked (until Very Hard's boss pass any fall to wave 12 passed) |
| `bot_reaches_crest_very_hard_2p` | 2 | both complementary duos, the same |
| `difficulty_very_hard_half_win` | 1 | of those six crews at Very Hard, at least half win |
| `bot_kills_bristlesow_solo_<builder>` | 4 | each Builder's plan alone kills wave 6's Bristlesow at Normal (§2.4, §10 item 19) |
| `idle_player_loses_hard`, `_very_hard` | 2 | two towers and nothing else lose before wave 12 |
| `difficulty_orders_the_levels` | 1 | the solo Lamplighter keeps more lives at Normal than at Hard, and at Hard than at Very Hard (a fall counts below any lives, an earlier fall below a later) |
| `race_mirror_is_fair_hard` | 1 | the race mirror at Hard: equal lives, equal clear tick, a draw |
| `fork_pairs_apart` | 1 | the fork bench (§3.8): every pair's branches apart on their own jobs by `JOB_MARGIN_PM`, none ahead on both by 10%, every patch at most 90% of a strong Builder's best |

`AGENTS.md`'s balance rule then reads: every `bot_wins*` wins with half the lives left (Hard's with a third),
every `idle_*` loses, every `coverage_*` holds, every `race_*`, `duel_*`, `stacking_*` and `difficulty_*` gate
holds, every `bot_reaches_crest_*` ends close, and `fork_pairs_apart` holds. Each gate prints a per-check leak
table (leaks grouped by creep kind) as watches, which is what a balance pass reads.

The lives a gate keeps are not always its margin. At Hard the Crest's toll is 10, more than a Builder alone keeps,
so whether it dies decides the match: after the fork pass and its review the Bellfounder alone wins on 8 of 15
lives, but the Crest dies 80 s into its walk and would reach the Holdfast at about 88 s (where it does at Very
Hard), 8 s to spare; the Lookout's dies at 72 s, 17 s to spare (§3.8). At Very Hard the Crest takes every life, so
its gates read the Crest itself: since its boss pass (§2.6) it dies for five of the six crews 67 to 83 s into a walk
of 87 to 91 s, the Bellfounder's 6 s and the Beekeeper's 4 s from the Holdfast, and the Bellfounder with the
Beekeeper leaks it with 4% left. The duel's `duel_balanced_beats_turtle`
wins 3 of 5, its bar; `duel_counter_cork_beats_random` 4 and a draw (3, its bar, at the pass's Sky Toll, whose
pulses held the winged packs a counter-corker sends the Bellfounder); after the sends' pass, balanced 4 of 5,
the turtle 4 of 5 against the reckless corker, the counter-corker 5 of 5 and the Seawall 4 of 5 against 3; after the
packs' matrix balanced 4 of 5, and the turtle against the reckless corker, the counter-corker and the Seawall (3
against 2) each 3 of 5, their bars, since a pack that is a threat to the Builders weak to it is one to a turtle of
them too, and a random pick is a weak one half the time; the Lamplighter's
`stacking_every_wave_costs_lives` loses 10 lives more than her list (6 at the pass's Iron Mortar, every 1.3 s with a
burst of 0.4, and 4, under its bar of 5, with that Mortar's burst back at 0.6), and 19 since her opening answers the
Bristlesow (1 kept against 20, §2.4).

---

## 5. Screens and navigation

### 5.1 The flow

Six places and a few overlays. Outside a match, the Causeway at low water stays behind every one of them; later
the backdrop can show the selected Builder's home.

```
 first launch: a name prompt (one field, prefilled with a generated name, editable)
        |
        v
 +----------------+   B / Builders   +----------------+
 |      HUB       |----------------->|    BUILDERS    |   roster, main + backup, Try (a solo High Water)
 | party, mode,   |<-----------------|                |
 | your Builder,  |    Esc / Back    +----------------+
 | one button     |
 +-------+--------+
         | a party of one, no open seats --------------------> an offline match at once (in-process turns)
         | a party, everyone Ready ------> 3-2-1 countdown (anyone can cancel) --------------------------+
         | open seats, or Find a rival --> queue pill in the hub ("Finding players 0:23")               |
         |                                     | strangers found                                        |
         |                                     v                                                        |
         |                     MATCH FOUND overlay (15 s) -- decline --> hub; the others requeue first  |
         |                                     | everyone accepts                                       |
         v                                     v                                                        v
 +-------------------------------------------------------------------------------------------------------+
 | LOADING = the sync barrier: one card per player with its sync state; at least 4 s on screen           |
 +--------------------------------------------------+----------------------------------------------------+
                                                    | every seat loaded with matching hashes, or the timers
                                                    v
 +-------------------------------------------------------------------------------------------------------+
 | GAME: the console as today, plus the party strip, Ready pips, signals, link and catch-up notices      |
 +--------------------------------------------------+----------------------------------------------------+
                                                    | won, lost, desynced, or everyone left
                                                    v
 +-------------------------------------------------------------------------------------------------------+
 | RESULTS, an overlay on the finished hollow -- Play again --> HUB with the party kept and Ready cleared |
 +-------------------------------------------------------------------------------------------------------+
```

Overlays rather than screens: the name prompt, the Join panel, the queue pill, Match Found, connection notices and
a small Esc menu (volume, fullscreen, name, leave). Not in v1: a separate mode-select screen, a pick or ban screen,
a lobby browser, chat, an honour step, match history, settings beyond name and volume.

The visual language is today's: bronze over stone from `ui/console/`, Noto Serif Display titles with the gilt
rule, the HUD colours (`GOLD #f0cf86`, `TEXT #ece2cc`, `DIM #a3957d`), short notices instead of dialogs. A new
`Shell` (a `CanvasLayer`) decides what each of the console's wells holds per screen; the console art is shared,
not duplicated.

| Screen | Left well (the minimap in game) | Arch and text | Right well (the command card in game) | Strip (top right) |
|---|---|---|---|---|
| Hub | the party | your Builder, live; name, role, difficulty, the team's coverage row | modes on the top row; Builders, Join, Play on the bottom row | where you are: Offline, LAN or Online, and the party code |
| Builders | the four Builders as a 2 × 2 grid | the selected Builder; name, role, difficulty, passive, coverage | its three towers on the top row; Main, Backup, Try on the bottom | |
| Loading, Results | hidden; a wide plate holds the cards | | | |
| Game | minimap | the selection's portrait and numbers | command card | gold, lives, wave, next wave's icons, Ready pips; party strip at top left |

### 5.2 Hub

**One job:** who am I playing with, as whom, in which mode; then one button.

```
+---------------------------------------------------------------------------------------------------+
|                                            .---------------------------------------------------.  |
|                                            | Online . groundhold.saschb2b.com   Party K7Q-4M   |  |
|                                            | [copy code]  [copy link]                     (=)  |  |
|                                            '---------------------------------------------------'  |
|                   (the Causeway at low water, live; the camera drifts slowly along it)            |
|                                                                                                   |
|  .--------------------.          _.-^^^^^^^^^^-._                          .------------------.   |
|  | PARTY         2/4  |         /                \   Tamsin Wick           |[HiWtr][Tide][  ] |   |
|  | <> Sascha [Lm]  ^  |        |   live model     |  the Lamplighter       |                  |   |
|  | () Ana    [Lk]  ok |        |   (turning)      |  Warden  *             |[Bldr][Join][GO]  |   |
|  | /\ + open seat     |        |                  |  team [Fr][Ru][Ba][Sp] |     START        |   |
|  | [] + open seat     |         \________________/   High Water, 1-4, ~13m |                  |   |
|==|____________________|====================================================|__________________|===|
+---------------------------------------------------------------------------------------------------+
  <> () /\ []  seat glyphs    ^ leader    ok Ready    [Fr][Ru][Ba][Sp] check glyphs, lit when the
  party has a strong answer (here all four: Lamplighter + Lookout)
```

- **Left well, the party:** up to four rows: seat glyph in seat colour, name, Builder icon, and a state (leader
  crown, Ready tick, "in Builders", "connecting", "back from results", "needs to reload"). Empty rows read
  "+ open seat" when open seats are on, otherwise "+ invite" (copies the link).
- **Arch:** your Builder turning slowly (`Portrait.show_model`). Beside it: name, epithet, role, difficulty and the
  **team coverage row**, four check glyphs, lit when any party member is strong against that check, with a tooltip
  on a dim one ("Nobody here is strong against Winged").
- **Right well, the command card's six slots:** top row the modes (**High Water**, **Tide Race**, and one slot
  reserved for Undertow, greyed until M7); bottom row **Builders** (B), **Join** (J) and the primary button (Enter).
- **The level** (M8, §2.6), not to be confused with a Builder's stars: three words beside the arch's mode line,
  **Normal · Hard · Very Hard**, the party's lit, like the open-seats switch beside it. The leader's click picks
  one (a member sees the choice and cannot change it); the mode line names a level other than Normal ("High Water ·
  Hard · 1–4 players · 12 waves"). Each word's tooltip says what it changes ("Hard: creeps have 30% more health,
  the bosses 50% more and 1 more armour; 15 lives"). In Undertow the words grey, with "A duel is played at Normal:
  your rival sets the pace". No key: the hub's keys stay B, J, Enter and Esc.
- **Strip:** where the party lives. **Offline** (no server; solo, Try, and racing the caretaker), **LAN ·
  192.168.1.20** or **Online · groundhold.saschb2b.com**, with the party code and copy buttons once on a server.

**The primary button** (one call to action, never two):

| Situation | Leader sees | Member sees |
|---|---|---|
| Party of one, High Water, open seats off | **Play** (an offline match at once) | |
| Party of one, Race, offline | **Race the caretaker** | |
| Party, everyone Ready, open seats off | **Start** (3-2-1 over the button; anyone can cancel) | **Ready** / **Not ready** |
| Party, open seats on and free | **Find players** | **Ready** / **Not ready** |
| Race, party of one, online | **Find a rival** | |
| Race, party of 2 or 4 | **Start** once two teams exist (click a row to change team) | **Ready** |
| Queued | **Cancel · 0:42**; after 60 s also **Start with caretakers** (High Water) or **Race the caretaker** | "Finding players 0:42" |
| Request pending | **Entering queue...** / **Leaving queue...** (disabled) | same |
| A member on another rules version | disabled: "Ana needs to reload" (or "You need to reload") | |

**Party rules** (server-side, §6.10): the creator leads; if the leader leaves, the member who joined earliest leads.
The leader picks the mode, the level (M8), open seats and teams, and can remove a member, who cannot rejoin that
code. Members change only their own Builder and Ready. Changing the mode or the level clears every Ready; changing
your Builder clears yours. A new party starts at its creator's level; a party keeps its level through a change
of mode, and a mode without levels plays Normal.
A member who drops keeps the row for 40 s ("reconnecting"). An empty party's code expires after 15 minutes.

### 5.3 Join panel

Opens above the right wing from **Join** (J).

```
                                              .-----------------------------------------------.
                                              |  JOIN A PARTY                                 |
                                              |  code  [ _ _ _ - _ _ ]   joins after 5 symbols |
                                              |  -------------------------------------------  |
                                              |  ONLINE                                       |
                                              |   (o) Official   groundhold.saschb2b.com      |
                                              |  -------------------------------------------  |
                                              |  NEARBY (LAN)                  desktop only   |
                                              |   Sascha's server   2/4  High Water [Go]      |
                                              |   > Server address  [192.168.1.20        ]    |
                                              |  -------------------------------------------  |
                                              |  [Create a party here]       [Leave party]    |
                                              '-----------------------------------------------'
```

- **Codes:** 5 symbols from `23456789BCDFGHJKMNPQRSTVWXYZ` (no vowels, no `0 O 1 I L`), shown as `K7Q-4M`. Input
  accepts lower case and ignores spaces and hyphens. Lookups are rate-limited per connection.
- **Address rule** (ported from Cyberworld's `network_address.c`, about 40 lines of GDScript): a private IPv4
  address (including `100.64/10`), a link-local or IPv6 ULA address, a single-label name or a name ending in
  `.local`, `.lan`, `.home`, `.home.arpa`, `.internal` or `.localdomain` becomes `ws://<addr>:8766/causeway`;
  anything else becomes `wss://<host>/causeway`. LAN players type `192.168.1.20` and never see a scheme or a port.
- **Nearby** lists LAN servers heard on the UDP beacon (§6.2), keyed by address, with name, mode, seats and a
  matching version only; a server silent for 3 s drops off.
- **Join link:** `https://saschb2b.github.io/Groundhold/play/?join=K7Q4M`. The game runs in a same-origin iframe,
  so `web/play/index.html` copies its query string onto the iframe's `src`, and the game reads it through
  `JavaScriptBridge.eval`. A code is not personal data; identity keys never appear in a URL.
- **The browser build hides Nearby and the address field** and shows one line instead: "LAN games need the
  desktop version. Friends on the web can join your party online." (An https page may not open `ws://` to a LAN
  address.) With no address field the published browser build joins only the official server (§6.11).

### 5.4 Builders

**One job:** understand a Builder and choose your main and backup.

```
+---------------------------------------------------------------------------------------------------+
|  < Hub (Esc)                                BUILDERS                                              |
|   .-------------------------------------------------------------------------------------------.   |
|   | KIT                                                                                       |   |
|   | [Arrow Tower 40]  --+--> Longbow Loft     +60   faster, harder bolts                      |   |
|   |                     '--> Skyward Loft     +60   reaches the sky        [Sp]               |   |
|   | [Cannon Tower 70] --+--> Great Cannon     +80   bigger blast                              |   |
|   |                     '--> Iron Mortar      +80   pierces armour         [Ba]               |   |
|   | [Frost Spire 60]  --+--> Deep Frost       +60   stronger slow                             |   |
|   |   (team: slow)      '--> Rime Spire       +60   reaches the sky        [Sp]               |   |
|   | Passive  Thrifty: towers sell for 90%                                                     |   |
|   '-------------------------------------------------------------------------------------------'   |
|  .--------------------.          _.-^^^^^^^^^^-._                          .------------------.   |
|  | [Lamp]*   [Look]   |         /                \   Tamsin Wick           |[Arw] [Can] [Frs] |   |
|  |  Warden   Marksman |        |   live model     |  the Lamplighter       |                  |   |
|  | [Bell]'   [Bee]    |        |                  |  Warden  *             |[Main][Bkup][Try] |   |
|  |  Breaker  Sweeper  |         \________________/   strong [Fr][Ru]       |                  |   |
|  |                    |                              weak   [Ba][Sp]       |                  |   |
|==|____________________|====================================================|__________________|===|
+---------------------------------------------------------------------------------------------------+
   * main   ' backup     [Fr][Ru][Ba][Sp] check glyphs (Froth, Runnel, Ballast, Spindrift)
```

- Hovering a tower button shows exactly the in-game command-card tooltip (cost, numbers, both branches, `air`),
  one source of truth for both.
- **Try** starts a solo High Water match with that Builder, offline, with Esc pause and restart; from M8 at the
  hub's level, which its tooltip names ("A solo High Water match at Hard").
- Builders can be browsed while queued; the queue pill follows into the corner. Changing the main while queued
  applies to the next match and does not drop the queue.
- Not shown: lore pages, per-level stat tables, skins, unlock tracks.

### 5.5 Match Found (overlay, strangers only)

Shown only when the queue joined players from outside the party.

```
                 .---------------------------------------------------.
                 |                    MATCH FOUND                    |
                 |            The tide turns at Wickhollow           |
                 |        High Water  .  4 players  .  ~13 min       |
                 |               (#) (#) ( ) ( )    2 of 4           |
                 |      [=====================-----------]   9 s     |
                 |             [  ACCEPT  ]          decline          |
                 '---------------------------------------------------'
```

- 15 s, timed by the server; the client only draws it. A sound when it opens and a soft tick in the last 3 s.
  Desktop asks for attention with `DisplayServer.window_request_attention()`; the browser flashes the parent
  page's title through `JavaScriptBridge` (the game is in an iframe, so it writes `window.parent.document.title`).
- Everyone accepts: Loading. Someone declines or times out: the match dissolves, those who accepted go back to the
  **front** of the queue ("A player didn't accept. You keep your place."), and the decliner's party returns to the
  hub. No penalties in v1 beyond that notice.
- (M8) The queue finds only parties of one level, so the line names the party's own level when it is not Normal:
  "High Water · Hard · 4 players · ~13 min".

### 5.6 Loading (the sync barrier)

**One job:** reveal the line-up, then start every player on the same turn.

```
+---------------------------------------------------------------------------------------------------+
|                              HIGH WATER  .  WICKHOLLOW  .  12 waves                               |
|                                    ----------- gilt rule -----------                              |
|      .--------------.     .--------------.     .--------------.     .--------------.            |
|      |   Builder    |     |   Builder    |     |   Builder    |     |   Builder    |            |
|      |   portrait   |     |   portrait   |     |   portrait   |     |   portrait   |            |
|      |--------------|     |--------------|     |--------------|     |--------------|            |
|      | <> Sascha    |     | () Ana       |     | /\ Ben       |     | [] Kim       |            |
|      | Lamplighter  |     | Lookout      |     | Bellfounder  |     | Beekeeper    |            |
|      | [#######   ] |     |    Ready     |     | Slow  0:18   |     | Checking     |            |
|      '--------------'     '--------------'     '--------------'     '--------------'            |
|                         team covers:  [Fr] [Ru] [Ba] [Sp]                                         |
|                                         Waiting for Ben                                  leave    |
+---------------------------------------------------------------------------------------------------+
```

- **Card states:** `Connecting`, a progress bar (eased toward the reported value, because the single-threaded web
  build reports in steps), `Checking` (hashes being compared), `Ready`, `Slow 0:18` (amber), `In another tab`
  (a browser tab is hidden), `Caretaker` (the match started without them), `Reconnecting`.
- **The line under the cards** reads *"Walking out"* while the seats load; from 15 s it names the seat
  everyone waits for ("Waiting for Ben", §6.6).
- **What "synced" means** under lockstep: the client has (1) received `MATCH_CONFIG`, (2) loaded every model the
  seats' Builders need and built the hollow, (3) built the simulation at tick 0 and sent `LOADED` with its rules
  hash and its tick-0 state hash, which the server compares across seats, and (4) taken five ping samples to size
  its playout buffer. §6.6 has the timers.
- **Race:** two rows of cards (team A above, team B below) with a gilt rule between them and a coverage row under
  each. No big "VS", no tips.
- (M8) The title names a level other than Normal: "HIGH WATER · HARD · WICKHOLLOW · 12 waves".
- A web player whose tab is hidden shows "In another tab" to the others and sees "Keep this tab open while the
  match loads" on their own card.

### 5.7 In game

The console stays as it is. Three additions and one change.

```
+---------------------------------------------------------------------------------------------------+
| .---------------------------------.                .---------------------------------------------.|
| | <> Sascha [Lm] 142  ||| ok      |                | (o) 142  (lives) 18   Wave 5 / 12           ||
| | () Ana    [Lk]  97  ||  .       |                | next [Sp][Dm]      Ready 1/2 . 9 s          ||
| | /\ Ben    [Bf] caretaker        |                '---------------------------------------------'|
| '---------------------------------'                                                               |
|                                         [ Wave 5 . Duskmoths ]                                    |
|                       (the hollow; every tower flies its owner's pennant; a signal ring pulses)   |
|                                                                                                   |
|  .--minimap-------.             _.-^^^^^^-._     Cannon Tower . Ana's             .--card-------. |
|  | owner colours, |            |  portrait  |    DMG 20  RNG 3.0  CD 1.5  SPL 1.1 | Q   W   E   | |
|  | signal blips   |            |            |                                     | A   S   D   | |
|==|________________|============'------------'=====================================|_____________|=|
+---------------------------------------------------------------------------------------------------+
   ||| link bars from each player's ping     ok Ready this window     . not yet Ready
```

- **Party strip** (top left, new, `scripts/ui/party_strip.gd`): one slim plate per player: glyph in seat colour,
  Builder icon, name, gold, link bars (from the round-trip times the server relays), and a Ready mark during the
  window (from M8 during a wave too, where a mark is a call for the next wave). "away", "caretaker" and "left"
  replace the gold when they apply.
- **Resource strip** (top right, extended): your gold, the team's lives, "Wave 5 / 12", the next wave's check glyphs
  with its creeps' portraits beside them (during a wave, the current wave's), the window countdown and "Ready 1/2".
  Hovering the wave label lists every remaining wave as icon rows, each creep with its count, health and armour
  (§2.3); a Duel's list goes on into the Surge from the first window, under a line that says when it is played ("The
  Surge, if both Holdfasts stand after wave 12: health +35%"), as S1 to S3, each with the wave it repeats ("wave 9
  again"). When everyone else is Ready and you are not, your Ready slot glows and the strip says "Waiting for you".
  **Race** adds a second line, my own race clock and then the rival's: "You 6:10 +60 s | Rival · Wave 7 · 18 lives ·
  6:12 +120 s" (once a Holdfast falls, the wave it fell on decides and my clock goes). Where the race is chosen, its
  button's tooltip says how it is won from its rules ("The lower time to clear wave 12 wins; each life lost adds 60
  s"), and so does the hub's mode line on hover; the line itself, which shares its row with the level's words (M8),
  ends with the cost of a life: "Tide Race · 2–4 players · 12 waves · +60 s a life lost".
- **Stacked waves on screen** (M8, §2.7). With two or three waves on the road the strip says "Waves 6–7 / 12" or
  "Waves 6–8 / 12", its creeps count every wave's, those walking and those still to come, and its glyphs are the
  newest wave's; the wave list starts at the oldest wave on the road and marks each on it "now", every creep with
  its health at its own wave. During a wave the Ready slot's tooltip names the wave it would call, its checks and
  what it would pay now ("Call wave 8 now: +10 for the window, +7 for the lives on the road"; the lives are the
  stake, the waves on the road's creeps walking and still to come), or why it cannot ("Three waves are on the road",
  "Wave 12 is the last", "Ben takes his seat back at the next window", in a duel "Waves do not stack in a duel"). In
  a wave a call takes a second press: the first press of D, N or Space, or a click on Ready, shows "Call wave 8 now?
  Press again" for 2 s, and only the second sends it; un-Ready takes one press. The horn sounds as the call lands,
  so solo nothing waits on screen; with company a Ready said in a wave waits for the partners, as in a window, and
  the party strip shows it. A press in a window's last moments would land after its horn, where its Ready, naming
  the window's wave, calls nothing (§2.7): with less of the countdown left than an order takes to run (the turns the
  game holds, `TurnSource.order_lead`, and its trip there and back, the measured round trip in whole turns) and one
  turn, the press asks "Call wave 8 now? Press again" too, and the second press calls the wave after the window's
  once the window's horn has sounded. The horn's banner: "Wave 8 called early · +17 gold". A race's rival line names
  the waves on the rival's road ("Rival · Waves 8–9 · ...").
- **Signals** (new): Alt+click on the ground, a creep, a tower or the minimap, or A then a click. A ring in your
  colour and glyph with a soft chime, and a blip on the minimap; on a creep it pulses the creep, on a tower it
  outlines the tower. One meaning ("look here"), no wheel, no text, at most 3 per 5 s. No chat in v1.
- **Command card** (changed): six slots in fixed places, with **positional hotkeys**, because four Builders cannot
  share mnemonic letters (today's A, C, F, U, S, N would collide).

| Selection | Q | W | E | A | S | D |
|---|---|---|---|---|---|---|
| Nothing, or placing a tower | Tower 1 | Tower 2 | Tower 3 | Signal | Sell (idle) | **Ready** (the war horn) |
| Your unforked tower | **Branch A** | **Branch B** | (idle) | Signal | Sell | Ready |
| Your forked tower | the branch taken (lit, idle) | the other branch (idle) | (idle) | Signal | Sell | Ready |
| A teammate's tower, or a creep | Tower 1 | Tower 2 | Tower 3 | Signal | (idle) | Ready |

  Today's hammer moves onto the branch buttons' frames; the war horn now means Ready (it toggles, lit while you
  are Ready). N and Space also toggle Ready, except during a Duel wave, where Space uncorks a corked bottle; in a
  wave of a mode that stacks, a call needs the second press above. Branch tooltips give the name, cost, one line
  of what changes in numbers and the check glyph it helps. Selecting a teammate's tower shows the owner in the
  subtitle ("Cannon Tower · Ana's"); the simulation refuses your fork or sell anyway. Shift keeps placing, Esc and
  right click cancel, Home frames the hollow, **V** shows the rival's hollow in a Race.
- **Pending commands** (new): a tower you place appears at once as a ghost with a soft pulse and its cost greyed
  in your gold; when your command runs it becomes the tower, or vanishes with the refusal as a notice ("Cannot
  build there": a teammate took the cell in the same turn).
- **Notices:** today's ("Cannot build there", "Not enough gold") plus "That tower is Ana's", "Ben's link dropped:
  his towers keep firing", "A caretaker builds for Ben", "Ben is back", "The caretaker hands back at the next
  build window".
- **Connection overlay** (a small plate over the portrait, never a modal):

```
     .------------------------------------------.      .------------------------------------------.
     |  Reconnecting...  your towers keep firing |      |  Catching up   [########------]  62%     |
     '------------------------------------------'      '------------------------------------------'
```

  "The lands fell out of step" ends the match on the results plate when the server declares a desync (§6.7), with
  the usual line of the match, "The games disagreed, so the match was stopped. A report was saved." and a Show
  report button (Save report in the browser). Back from another tab or a dropped link while the caretaker still
  holds the seat, the plate says "Welcome back" and when it hands back (after this wave, or after the coming one
  while a window is open), and the seat's own orders are refused for that before any gold check.

### 5.8 Results (the Ebb)

An overlay on the finished hollow, on the plate art widened. It never times out into the hub.

```
+---------------------------------------------------------------------------------------------------+
|                                     THE HOLDFAST HOLDS                                            |
|                       High Water . 12 waves . 13:42 . 17 of 20 lives left                         |
|               lives  ''''''''''''''-.......------------------'''''''   (waves 1 to 12)            |
|                                                                                                   |
|   PLAYER        BUILDER          KILLS    DAMAGE     HELP    TOWERS                                |
|   <> Sascha     Lamplighter        212     48.1k     9.2k    9 (4 forked)   Most kills in wave 7   |
|   () Ana        Lookout             97     31.7k    22.4k    7 (5 forked)   Most help              |
|   /\ Ben        Bellfounder        130     30.2k    12.8k    8 (2 forked)   Most Thornbacks        |
|   [] Kim        Beekeeper      (left at wave 6; the caretaker finished)                           |
|                                                                                                   |
|   Ana and Ben are back in the party                 [ PLAY AGAIN ]            Hub                 |
+---------------------------------------------------------------------------------------------------+
```

- **Titles** in the game's words. High Water: "The Holdfast Holds" / "The Holdfast Goes Under". Race:
  "You Outran the Tide" / "Your Rival Outran the Tide" / "Two Crews, One Time". Desync: "The Lands Fell Out of Step".
- **Every number is computed by the simulation** on every client, so every client shows the same results; the
  server only confirms the outcome.
- **One positive line per player**, picked from a fixed list by the player's best stat relative to the team (Most
  kills in wave N, the wave the player killed most in; Most help, Most kills, Most damage, Most Duskmoths /
  Thornbacks / Scuttlers / Gourdlings, No towers sold, Fastest Ready); ties go to the lower seat, and no line
  repeats. No MVP.
- **No leaks column:** on a shared road a leak belongs to the team, and the lives line shows when it happened.
  **Help** (§3.2) makes the team-tower player's work visible.
- **Race layout:** one block per team, both race times, the rule that decided it in one line.
- (M8) The subtitle names a level other than Normal and counts the lives out of its own: "High Water · Very Hard
  · 12 waves · 13:42 · 4 of 10 lives left". A race's rival line and blocks need no change: both teams play one
  level, and their lives come from the records.

### 5.9 Back to the hub, and seat colours

- **Play again** returns to the hub with the party, mode, teams and Builders unchanged and Ready cleared; the others
  see who is back. A player who came alone through the queue is queued again at once, with "Entering queue..."
  until the server confirms. A stranger's row offers **Invite to party**, which sends them your code. **Hub** does
  the same without queueing.
- After an offline match, the hub opens offline with the same mode and Builder.

| Seat | Colour (Okabe-Ito) | Glyph | Pennant shape |
|---|---|---|---|
| 1 | orange `#E69F00` | ◆ | swallowtail |
| 2 | sky blue `#56B4E9` | ● | square banner |
| 3 | bluish green `#009E73` | ▲ | long triangle |
| 4 | reddish purple `#CC79A7` | ■ | double tail |

Every place a colour identifies a player also shows the glyph or the shape, so colour-blind players can tell seats
apart. The pennant recipe (`art_src/models/towers/pennant.json`) gets four shape variants and a colour parameter.

---

## 6. Networking

### 6.1 The authority model: server-sequenced deterministic lockstep

**Decision.** The server is a **sequencer**, never a simulator. Every 50 ms it closes a turn and broadcasts the
commands that arrived, each stamped with the sender's seat. Every client runs the same integer-only GDScript
simulation from (seed, rules, turns). The server also referees state hashes, keeps agreed checkpoints, and owns the
hub, parties, the queue and the loading barrier. All three designs chose the opposite (a headless Godot authority);
the user's hosting direction and the Cyberworld study's evidence overrule them.

**Why this model, and not a headless Godot authority:**

| Question | Server-sequenced lockstep (chosen) | Headless Godot authority (rejected for v1) |
|---|---|---|
| Hosting the user already runs | The same zipapp, the same five native LAN binaries, the same multi-arch `ghcr.io` image, the same Coolify and Caddy Compose files and runbook as Cyberworld | Godot export templates in the server image; a second operations model |
| Behind Coolify's single domain | One container, one port, one path | Process per match has no clean route: either the Python lobby relays the traffic anyway, or one GDScript server rewrites identity, moderation, retention, stats and backups |
| Server cost | Per match, 20 timer wake-ups a second and about 0.2 KB/s per player; near zero CPU | Measured on today's node game headless: 0.26 ms per tick, at most 61 MB RSS, about 1.6% of a core per co-op match, continuously |
| LAN | The same downloadable binary as Cyberworld's; the host is not a player, so nobody's quitting ends the match | A listen server in the game (the match dies with the host, and a browser can never host) or a large Godot server download |
| One lagging browser on TCP | Stalls only itself: no client waits for another, only for the server's turns. This answers the main objection in `netcode.md` and `gaps.md`, which was about peer lockstep | Stalls only itself |
| Clients' netcode | Apply the turns | Snapshot decoding, interpolation, keyframe resync; a hidden tab overflows the 64 KiB buffer in about 3 s at 15 Hz snapshots |
| Reconnect, spectating, replays | All from one log: a checkpoint plus the turns since (Cyberworld's stands catch-up, proven in the browser) | A keyframe each; a recorder for replays |
| Testing with godot-agent | A match is a pure function `sim(seed, rules, turns)`; N simulations fed the same turns must hash equal | Good in process, but determinism is checked only within one binary |

**Its costs, stated plainly:**

- **A determinism discipline** in `scripts/sim/` (§6.4), enforced by a lint and by a CI check that replays the same
  log natively and in the web export.
- **A desync failure mode** (§6.7), handled by hashes, checkpoints and dumps.
- **No hidden information:** every client holds the whole state. In a Race nothing is hidden anyway. The Duel's
  corked packs use a commitment instead (§1.4).
- **A modified client** can only desync itself: seats are stamped by the server and every simulation enforces the
  rules. With 3 or more seats it is outvoted; with 2 the match ends "desynced". There is no ladder in v1 to cheat
  on.

**The way out**, if ranked play ever needs authority: a **referee**, a headless Godot process that the Python server
feeds the same turn log, used only for ranked matches. Its hash becomes authoritative. Thanks to the discipline it
is an add-on, not a rewrite.

### 6.2 Topologies and transport per platform

```
 Solo / Try / caretaker race   views <- MatchClient <- LocalSequencer (the same turns, zero delay)      one process
 LAN                           desktop clients <-- ws://192.168.x.y:8766/causeway --> groundhold-server
                                                                                      (.pyz or a native binary)
 Online (official)             desktop and browser clients <-- wss://groundhold.saschb2b.com/causeway -->
                                     Coolify's proxy (TLS) <-- ws --> container :8766 (no host port)
```

| | Solo, Try | LAN | Online |
|---|---|---|---|
| **Desktop** (Linux, Windows, macOS exports) | in-process `LocalSequencer` | `ws://<lan-address>:8766/causeway` to the downloadable server; **Nearby** from its UDP beacon on 8767; or the typed address | `wss://groundhold.saschb2b.com/causeway`, or any self-hosted `wss://` server |
| **Browser** (Pages, https, WebGL 2) | in-process | not available: no UDP, and an https page may not open `ws://` to a LAN address (only `ws://localhost` on the server's own machine) | `wss://groundhold.saschb2b.com/causeway` only: no address field (§5.3); a self-hosted server through a web build its host publishes |
| **Server** | none | `.pyz` (Python 3.11+) or one of five native zips: Windows x64, Linux x86_64 and arm64, macOS Intel and arm64; or `docker run` | the `ghcr.io` image behind Coolify's proxy, or the self-host Caddy Compose |

**Client socket** (`scripts/net/link.gd`): Godot's `WebSocketPeer`.

- `supported_protocols = ["groundhold.v1"]`, then `connect_to_url(url, TLSOptions.client())`. On desktop the
  default CA list is Godot's bundled Mozilla bundle; on the web the browser verifies the certificate.
- One message per binary frame (`put_packet`); text frames are refused both ways.
- `inbound_buffer_size = 1048576` (default 65,535), so a hidden browser tab can buffer far more than it will ever
  receive at about 0.2 KB/s.
- No custom handshake headers (unsupported in web exports) and no `heartbeat_interval` (no effect in web exports).
  Liveness is the application's own PING every 2 s, as in Cyberworld.
- The browser sends `Origin: https://saschb2b.github.io`, which the server's `origins` allowlist admits (the same
  origin Cyberworld already allows). Cyberworld's check applies only when an `Origin` header is present; M1's
  handshake test records whether Godot's native client sends one.

**Frames:** the server accepts only masked, unfragmented binary frames up to `max_message` (1,100 bytes client to
server), as Cyberworld's `websocket.py` does with 512. Checkpoints, the only large client payload, are chunked at
the application level into 1,024-byte parts. The M1 smoke test covers that both Godot and browsers send each
message as one frame.

**LAN beacon** (new, `server/groundhold_server/beacon.py`): when not running in a container, the server broadcasts one
small UDP datagram a second to `255.255.255.255:8767`:

| Bytes | Field |
|---|---|
| 4 | `GHB1` |
| 2 | protocol version |
| 2 | WebSocket port |
| 1 | open parties |
| 1 + n | server name (u8 length, UTF-8) |

The desktop client binds 8767 with `PacketPeerUDP.bind()`, polls it in `_process`, keys servers by
`get_packet_ip()` and the port, and lists those with a matching protocol version. Only one game per computer can
bind the port; a second window on the same machine uses the address field. The listener accepts injected datagrams,
so scenarios test discovery without a network.

### 6.3 Turns and playout, in numbers

| Item | Value |
|---|---|
| Simulation | 60 ticks per second, a constant step |
| Turn | 3 ticks, 50 ms. Turn *k* covers ticks 3*k* to 3*k* + 2 |
| Sealing | Per match, on **absolute deadlines**: turn *k* closes at `start + (k + 1) × 50 ms`. A late loop seals the missed turns in a burst, so the turn count always tracks wall time. (Cyberworld's `asyncio.sleep(1 / tick_hz)` drifts; it must not be copied for this) |
| Stamping | A command that reaches the server while turn *k* is open is listed in `TURN(k)` with the sender's seat (from the connection, so it cannot be forged) and the client's sequence number |
| Order inside a turn | system commands first; then seats in rotation starting at seat `k mod seats`, so nobody always wins a contested cell; then by sequence number |
| Execution | at the start of tick 3*k*, on every client, in listed order |
| Client rule | simulate tick *t* only once `TURN(t div 3)` has arrived |
| Playout buffer *B* | `clamp(2, 6, ceil((ping mean + 2 × ping spread) / 50 ms))` over the last 10 pings, ignoring pings timed across a frame longer than 50 ms (Cyberworld's browser lesson) |
| Pacing | 60 ticks/s ± 5% to hold the buffered turns near *B*; more than 20 turns (1 s) behind: catch-up at up to 8 ticks per frame within an 8 ms budget; nothing buffered: wait (the world pauses for that player only) |
| Felt delay | about RTT + 25 ms + *B* × 50 ms: about 130 ms on a LAN, 185 to 300 ms online. WC3 on Battle.net ran about 250 ms; Age of Empires found 250 ms unnoticed (`netcode.md` §3.1) |
| Cover | the immediate ghost, hammer and greyed gold (§5.7) |
| Bandwidth | an empty `TURN` is 6 bytes (plus 2 of framing), 20 a second; a command adds 16 bytes; a hash goes up once a second: about 0.2 KB/s per player |
| Solo | `LocalSequencer` seals a turn every 3 ticks with *B* = 0: a command lands within 50 ms. Pause stops the sequencer. Tests fast-forward with `ticks_per_frame` |

### 6.4 The deterministic simulation (`scripts/sim/`)

The rules move out of the nodes into `RefCounted` records with no Nodes, no signals and no scene tree.

| Record | Holds |
|---|---|
| `SimMatch` | tick, seed, rules preset, RNG state, teams, hollows, seats, towers, creeps, shots, `next_id`, the event queue |
| `SimHollow` | id, team, the road as integer millimetre corner points with cumulative micrometre lengths, buildable and occupied cells, phase (PREP, WAVE, DONE, FALLEN), wave, (M8) waves cleared, countdown in ticks, spawn queue, health scale |
| `SimTeam` | id, lives, hollows, race clock |
| `SimSeat` | seat, team, hollow, Builder, gold, ready, state (present, away, returning, caretaker, left), stats (kills, damage, help, towers, forks), caretaker plan cursor |
| `SimTower` | id, owner seat, hollow, cell, kind, branch (−1, 0, 1), invested, `cooldown_until`, target, range intervals (`PackedInt64Array` of road micrometres), haste and its source seat |
| `SimCreep` | id, hollow, kind, `dist_um`, `hp_c`, `max_hp_c`, `armor_c`, winged, boss, and per effect: strength, until-tick, source seat (slow, stun with its immunity, mark, crack); `sent_by` for the Duel; (M8) its wave |
| `SimShot` | id, tower, target, `land_tick`, `land_dist_um` for splash, payload (damage, pierce, effect) |

```gdscript
class_name SimMatch
extends RefCounted

func _init(rules: Dictionary, seats: Array, seed: int) -> void
func apply_turn(turn: int, commands: Array) -> void  # at tick 3 × turn, before step(); invalid ones become REJECTED events
func step() -> void                                  # one tick; never reads delta or a clock
func drain_events() -> Array                         # SPAWN, FIRE, HIT, EFFECT, DIE, LEAK, BUILT, FORKED, SOLD, GOLD,
                                                     # LIVES, WAVE, READY, SIGNAL, SEAT, REJECTED
func serialize() -> PackedByteArray                  # the canonical state in id order: the checkpoint
static func deserialize(bytes: PackedByteArray, rules: Dictionary) -> SimMatch
func state_hash() -> PackedByteArray                 # SHA-256(serialize()) through HashingContext, first 8 bytes
```

**Tick order:**

1. On a turn boundary: apply system commands, then the turn's commands, validated identically everywhere (gold,
   cell, phase, ownership, the seat's Builder kit). An invalid command is a no-op plus a `REJECTED` event that only
   its sender's UI shows.
2. Per hollow, in id order: the wave clock (countdown, Ready skip, the horn; from M8 also a stacked horn in a wave
   once every present seat is Ready) and spawns: from M8 first those an older wave still has to send after a
   stacked horn, each on its own tick, then the newest wave's.
3. Caretaker: for each caretaken seat, at the window's start and every 30 ticks, `caretaker.gd` picks commands from
   the seat's plan, and they are applied as if received.
4. Creeps move, in id order: effects expire; a stunned creep stands; slows scale its speed; a creep reaching the
   Holdfast leaks its toll from the team's lives, and a hollow at 0 lives is FALLEN.
5. Towers, in id order: cool down, keep or pick a target, fire (schedule a shot) or pulse.
6. Shots landing this tick, in id order: damage by the armour rule, effects, bounces, splash; a death pays the bounty
   to every seat on the team and credits Help.
7. Wave clears, in wave order (M8: two may clear in one tick): clear bonus, Hive Tithe, the next PREP (once no wave
   is left on the road) or DONE, and a checkpoint mark.
8. The match-end check; `tick += 1`. Every 60 ticks the client hashes the state.

**Range without square roots per tick:** when a tower is built or forked, `SimRoad.intervals(cell, range_mm)` finds,
for each straight road segment (they are axis-aligned, between tile centres), the stretch inside the tower's circle
with an integer `isqrt(r² − d²)`, and stores it as micrometre intervals of road distance. "In range" is then a
comparison. The error is under 1 mm; `sim_range_intervals_match_distance` checks it against brute force for every
buildable cell.

**Shots are scheduled, not flown:** `flight = max(1, ceil(isqrt(dx² + dz²) × 1000 / speed_um_per_tick))` ticks.
A homing shot hits its target at `land_tick` if it is still alive. A shell lands where its target will be
(`dist + current speed × flight`, clamped to the road) and splashes by squared millimetres with a falloff of
`dmg × (2r − d) / (2r)`. The view flies a projectile model over exactly `flight` ticks.

**The rules, enforced by a lint on `scripts/sim/`:**

1. **Integers only**, in the units of §4.2. No `float` type and no float literal.
2. **No trigonometry or transcendental functions:** no `sin`, `cos`, `tan`, `atan2`, `pow`, `exp`, `log`, `sqrt`,
   `lerp`, `lerp_angle`, `Vector2`, `Vector3`, `Basis`, `Transform3D` or `look_at`. Ranges compare squared
   distances; lengths use a Newton `isqrt` on ints in `sim_math.gd`.
3. **An own RNG:** xorshift32 with every step masked to 32 bits:
   `x ^= (x << 13) & 0xFFFFFFFF; x ^= x >> 17; x ^= (x << 5) & 0xFFFFFFFF`. Its state is part of the
   checkpoint. No `randi`, `randf`, `randfn`, `shuffle` or `pick_random`.
4. **No overflow:** GDScript ints are 64-bit and the documentation says they wrap, but nothing should rely on it.
   Squares are formed in millimetres, never micrometres; every product stays below 2⁶². Hashing goes through
   `HashingContext`, never `hash()`. Operands of `/` and `%` stay non-negative.
5. **Ordered iteration:** entities live in arrays ordered by id; every tie breaks by id; `Array.sort_custom` is not
   stable (Godot's documentation), so every comparator ends with an id comparison; no dictionary is iterated; no
   `get_tree()` or `get_nodes_in_group()`.
6. **No time:** no `delta`, `Time.`, `OS.get_ticks_*` or `Engine.time_scale`. Fast-forward runs more ticks per
   frame.
7. **Visuals are fed by the simulation, never the other way round.** Views interpolate between the last two ticks
   (`Engine.get_physics_interpolation_fraction()`), and effects and sounds fire from events.
8. **One `SimMatch` has no globals**, so several run in one process (tests, the caretaker race, a later replay
   viewer).

**Today's leaks into gameplay, and where each goes:**

| Today (verified) | In the new code |
|---|---|
| `tower.gd:61-64, 157`: the cannon head turns with `lerp_angle(atan2(...))`, and the shell leaves from `_head.global_basis`, so a visual rotation sets flight time and landing | shells leave the tower's cell centre in the simulation; the view keeps the turning head, the recoil and a fixed muzzle offset per kind and level |
| `creep.gd`: `aim_point()` from the mesh's bounding box (`_model_height`) | view only (hit flashes) |
| `tower.gd:142`, `projectile.gd:103`, `wave_director.gd:37, 70`: `get_nodes_in_group()` in scene-tree order | arrays by id |
| Float timers: `_cooldown`, `slow_left`, `Game.countdown`, `_spawn_wait` | ticks |
| `fx.gd:40` takes particle seeds from `Game.rng` | `Fx` owns a view-only RNG |
| `creep.gd`: `static var _spawned` for the walk-cycle phase | the view derives the phase from the creep id |
| `Creep.predict()` | the simulation computes the landing distance |
| `"time_scale": 8` in `bot_wins` and `idle_player_loses`, which under `--fixed-fps` makes every tick 8/60 s long | `ticks_per_frame` (the real step size) |

**Views and the facade.** `Creep`, `Tower` and `Projectile` become views keyed by simulation id. `MatchClient` steps
the simulation in `_physics_process`; views read the records each tick. `Game` stays an autoload as the **local
seat's facade**: `gold` is mine, `lives` my team's, `wave`, `state`, `countdown` and `kills` come from the
simulation, and the same signals fire, so the HUD changes little. In an offline match, the setters scenarios use
today (`Game.gold`, `Game.countdown`, `Game.wave`, `Game.lives`, a creep view's `distance` or `speed`) write into the
local `SimMatch` and are logged as `DEBUG` entries in the turn log, so a replay reproduces them; on a server they are
refused.

### 6.5 The protocol

**One contract, two codecs.** `shared/net/protocol.json` holds the version, subprotocol, path, ports, message ids,
sizes and limits; `shared/net/README.md` documents every message as a byte table (Cyberworld's pattern). Python
loads the JSON as package data; GDScript reads it at runtime (`FileAccess.get_file_as_string`), so
`export_presets.cfg` adds `shared/net/*.json` to every preset's include filter. Messages are big-endian records
with a one-byte type (Python `struct` with `!`; GDScript `StreamPeerBuffer` with `big_endian = true`). Every reader
checks the exact length and bounds every field. Strings are a u8 length plus UTF-8; names must match
`[A-Za-z0-9][A-Za-z0-9 _-]{0,15}`, Cyberworld's rule.

| Constant | Value |
|---|---|
| `version` | 2 (since M8, for the difficulty's fields; 1 before) |
| `subprotocol` | `groundhold.v2` (`groundhold.v1` before M8) |
| `path`, `port`, `beacon_port` | `/causeway`, 8766 (8765 stays free for a Cyberworld server on the same PC), 8767 |
| `max_message` | 1,100 bytes, client to server |
| `turn_ticks`, `turn_ms`, `hash_every` | 3, 50, 60 |
| `checkpoint_part` | 1,024 bytes |

**Connection and hub**

| Id | Message | Dir | Payload |
|---|---|---|---|
| 1 | `HELLO` | C→S | u16 version, u32 build_seq, u64 rules_hash, 16 bytes token, u8 flags (resume, web), u8 + name, u32 match and u8 seat a resume asks back (0 and 255: none) |
| 2 | `WELCOME` | S→C | u32 session, 16 bytes public identity, u16 turn_ms, u8 turn_ticks, u16 hash_every, u8 flags (maintenance), u8 + server name, u8 + motd |
| 5 | `ERROR` | S→C | u8 code, u8 + text; the connection closes |
| 6 | `PING` | C→S | u32 client ms, u16 last measured RTT in ms |
| 7 | `PONG` | S→C | u32 client ms, u32 current turn (0 outside a match) |
| 14 | `NOTICE` | S→C | u8 code, u32 argument; the connection stays |
| 15 | `BYE` | both | |
| 20 | `PARTY` | C→S | u8 op and its arguments: create(mode), join(5 bytes code), leave, remove(member), mode(mode), builders(main, backup), ready(on), team(member, team), open(on), start, cancel; (M8) difficulty(level) |
| 21 | `PARTY_STATE` | S→C | 5 bytes code, u8 mode, (M8) u8 difficulty, u8 flags (open, LAN), u8 leader, u8 you (the recipient's member), u8 phase, u32 countdown ms, u8 n, then per member: u8 member, u8 team, u8 main, u8 backup, u8 state, u16 RTT, u32 build_seq, u64 rules_hash, u8 + name. A full snapshot on every change |
| 22 | `QUEUE` | C→S | u8 op (enter, leave, start_with_caretakers) |
| 23 | `QUEUE_STATE` | S→C | u8 state (idle, entering, queued, leaving), u32 elapsed ms, u8 caretaker offer |
| 24 | `MATCH_FOUND` | S→C | u32 match id, u8 mode, u8 seats, u8 accepted, u32 ms left |
| 25 | `ACCEPT` | C→S | u32 match id, u8 yes |

**Loading**

| Id | Message | Dir | Payload |
|---|---|---|---|
| 30 | `MATCH_CONFIG` | S→C | u32 match id, u8 mode, (M8) u8 difficulty, u8 map, u32 seed, u64 rules_hash, u8 your seat, u8 n, then per seat: u8 seat, u8 team, u8 Builder, u8 flags (caretaker), u8 + name; u8 flags (rejoin) |
| 31 | `LOADING` | C→S | u16 per mille (at most 4 a second) |
| 32 | `LOAD_STATE` | S→C | u8 n, then per seat: u8 seat, u16 per mille, u8 state; u16 seconds elapsed |
| 33 | `LOADED` | C→S | u64 rules_hash, 8 bytes tick-0 state hash |
| 34 | `START` | S→C | u16 ms until turn 0 opens |

**In a match**

| Id | Message | Dir | Payload |
|---|---|---|---|
| 40 | `CMD` | C→S | u16 seq, u8 type, i32 a, i32 b, i32 c (16 bytes with the type byte) |
| 41 | `TURN` | S→C | u32 turn, u8 n, then per command: u8 seat (255 = system), u16 seq, u8 type, i32 a, i32 b, i32 c |
| 42 | `HASH` | C→S | u32 tick, 8 bytes hash, u8 flags (checkpoint tick) |
| 43 | `CHECKPOINT_ASK` | S→C | u32 tick |
| 44 | `CHECKPOINT_PART` | both | u32 tick, u16 part, u16 parts, u16 length, bytes (at most 1,024) |
| 45 | `RESYNC` | S→C | u32 checkpoint tick, u32 first turn after it, u8 reason (rejoin, desync, behind), u32 open turn, 8 bytes checkpoint hash, u16 parts; then parts and turns follow |
| 46 | `TURN_REQUEST` | C→S | u32 first missing turn |
| 47 | `VISIBILITY` | C→S | u8 state (shown, hidden, catching up) |
| 48 | `RESULT` | C→S | u32 final tick, 8 bytes hash, u8 outcome per team |
| 49 | `MATCH_END` | S→C | u8 outcome (won, lost, draw, desynced, aborted), u8 reason, u32 final tick |
| 50 | `LEAVE_MATCH` | C→S | |
| 52 | `LINKS` | S→C | every 2 s: u8 n, then per seat: u8 seat, u16 RTT ms, u8 flags (hidden, silent, catching up) |

**Commands** (`CMD.type`), all validated by the simulation:

| Type | a, b, c | Refused with |
|---|---|---|
| `BUILD` | slot 0 to 2, x, z | `CANNOT_BUILD_THERE`, `NOT_ENOUGH_GOLD`, `WRONG_PHASE` |
| `FORK` | tower id, branch 0 or 1 | `NOT_YOURS`, `ALREADY_FORKED`, `NOT_ENOUGH_GOLD` |
| `SELL` | tower id | `NOT_YOURS` |
| `READY` | 0 or 1; (M8) the wave a Ready calls, 0 none | `WRONG_PHASE` (M8: also a Ready naming a wave already called); (M8) `NO_STACK` in a wave that cannot take another (§2.7) |
| `SIGNAL` | x mm, z mm, target id | `RATE_LIMITED` |
| `CORK` (M7) | tier, commit high 32 bits, commit low 32 bits | `WRONG_PHASE`, `NO_CORKS_LEFT`, `NOT_ENOUGH_GOLD` |
| `UNCORK` (M7) | pack, salt high 32 bits, salt low 32 bits | `TOO_EARLY`, `NOTHING_CORKED`, `BAD_REVEAL` |
| `SEAWALL` (M7) | | `NO_CHARGE`, `SEAWALL_STANDING` |

**System commands** in a `TURN` (seat 255): `AWAY(seat)`, `BACK(seat)`, `LEFT(seat)`, `TIMEOUT` (the server's
hard match cap). The server checks only a command's **shape** (type and argument ranges), the seat (from the
connection), the **sequence** (increasing) and the **rate**; everything else is the simulation's job.

**Error codes** (fatal) keep Cyberworld's numbers where they mean the same: 2 your game is older, 5 bad name, 7
server full, 8 too many messages, 9 bad token, 10 banned, 11 not on the allowlist, 12 replaced by another session of
the same profile, 14 kicked (minutes left), 16 maintenance (with the host's line), 17 the server is older. **Notice
codes** (non-fatal) are new: party full, no such party, removed from the party, match dissolved ("you keep your
place"), a member needs to reload, caretakers offered, no held seat for a resume. M4's additions are
[`contract-m4.md`](contract-m4.md)'s.

**M8's change** ([`contract-m8.md`](contract-m8.md) §5) is the difficulty's, and only that: `PARTY`'s op
`difficulty` (u8 level: normal 0, hard 1, very hard 2), the level in `PARTY_STATE` and in `MATCH_CONFIG`, each a
u8 after the mode, and the `levels` flag on High Water's and Tide Race's entries in `modes`. Layouts change, so
`version` becomes 2: a game of version 1 hears error 2. `HELLO`, `LOADED`, `MATCH_FOUND`, the queue's messages and
every message of a match stay as they are; stacked waves are the simulation's alone and need no message.

**Rate limits** (token buckets per connection): hub and party messages, burst 40, refill 30 a second (Cyberworld's
values); `CMD`, burst 10, refill 5 a second (a TD player never needs more); network traffic (`PING`, `HASH`,
`LOADING`, `CHECKPOINT_PART`, `TURN_REQUEST`, `VISIBILITY`), burst 150, refill 120 a second. An empty bucket closes
the connection with error 8, and the seat is held. 15 s of silence closes a connection, except a hidden tab's
(its last `VISIBILITY` hidden), which is kept up to 10 minutes of silence (§6.8). A client whose output
buffer passes 64 KiB outside a paced catch-up is dropped, its socket aborted rather than left to flush to a peer
that may never read, and its seat is held.

### 6.6 The loading barrier

1. The server sends `MATCH_CONFIG`. Each client loads the hollow (or two), builds terrain and decor, preloads every
   seat's Builder and tower models, builds the simulation at tick 0, and reports `LOADING` (eased on the web).
2. The client checks the config's rules hash against its own (it cannot differ, because parties and queues match
   on it) and sends `LOADED(rules_hash, tick-0 hash)`. The server compares the tick-0 hashes across seats; a
   mismatch aborts the match back to the party with a notice that names the seat, before anyone plays.
3. When every seat is loaded with equal hashes and at least 4 s have passed since `MATCH_CONFIG` (0 s with one
   human), the server sends `START(1500 ms)` and opens turn 0 that long after. The first build window absorbs any
   difference in arrival.

| Time since `MATCH_CONFIG` | What happens |
|---|---|
| 0 to 4 s | Minimum display, even if everyone is ready at once |
| 15 s | A seat not yet loaded shows `Slow 0:15`; the title says "Waiting for Ben" |
| 30 s | Party or LAN match: the leader gets **Start without Ben** |
| 45 s | Match with strangers: it starts by itself |
| 120 s | Hard limit: anyone still not connected is marked as left; a stranger match where someone never connected dissolves and requeues the others at the front |

A seat that starts without its player begins with `AWAY` in turn 0, so the caretaker plays it from the first
window; the player can still join through the reconnect path. All of these timers are the server's; in godot-agent
scenarios the fake sequencer counts them in turns, so they stay deterministic.

### 6.7 Hashes, checkpoints, reconnect, the caretaker, desyncs

- **Hashes.** Every present seat sends `HASH(tick, 8 bytes)` every 60 ticks. The server compares a tick once every
  present seat has reported (or 2 s after the first report). Agreement means all equal, or, with 3 or more seats,
  a strict majority of the seats present, not of the reports so far: short of one the tick waits for the seats
  still to report (or until they go away, leave or stop hashing), so one early report never decides for seats
  that report late.
- **Checkpoints.** A checkpoint tick is the first hash tick at or after a wave starts, and in any case every 1,800
  ticks (30 s). Every client keeps its own serialized state for the last two checkpoint ticks. The server asks one
  seat in rotation (`CHECKPOINT_ASK`) to upload in parts of at most 1,024 bytes, and keeps the upload only if
  `SHA-256(bytes)[:8]` equals the hash the seats agreed for that tick. Expected size: under 10 KB. `SimCodec`
  writes about 72 bytes per creep, 35 per tower and 47 per shot in flight, besides the seats, and a wave brings
  at most about 40 creeps: over the whole of wave 11 with four seats the largest checkpoint measured 3.9 KB with
  the caretaker's 27 towers, 5.0 KB with four players' 59, and 9.0 KB with a forked tower on every one of the 206
  buildable cells (M4 review). A mode that puts 200 creeps on the road would pass 14 KB on the creeps alone.
- **Away.** A seat silent for 5 s (no message at all; `PING` runs every 2 s) gets `AWAY(seat)` in the next turn.
  The simulation's **caretaker** then plays it: it follows the Builder's plan with the seat's own gold, forks for
  the checks the team lacks, is always Ready, and never sells. Towers keep firing throughout, because every client
  simulates them. `LEAVE_MATCH` sends `LEFT(seat)`: the caretaker keeps the seat to the end.
- **Reconnect.** The returning client sends a resume `HELLO` with the same identity token; the server finds the
  held seat (seats are held until the match ends) and sends `MATCH_CONFIG`, the latest agreed checkpoint and every
  turn since. It paces them at 2 KB per 50 ms while the client's output is under 4 KB, which is Cyberworld's stands
  catch-up, proven in the browser. The client loads the checkpoint and catches up with a progress bar. The server
  then sends `BACK(seat)`; the simulation marks the seat returning and hands control back **at the next build
  window**, refusing the seat's own commands until then ("The caretaker hands back at the next build window").
  The server cannot see waves; the simulation can.
- **Gaps.** A missing turn number (a browser buffer overflow, in theory) triggers `TURN_REQUEST`, and the server
  re-sends from its in-memory turn log.
- **Desync, 3 or more seats, a minority disagrees:** the server sends `RESYNC` with the last agreed checkpoint and
  the turns since to the minority seats; they reload and catch up, and `/stats` counts a desync. The same seat
  desyncing twice in one match is handed to the caretaker (`LEFT`) and returned to the hub with a dump.
- **Desync, 2 seats, or no majority:** the match ends "desynced" (`MATCH_END`). Both clients write a dump to
  `user://desync/<match>-<seat>.bin`: the last agreed checkpoint (the latest kept before the first bad hash tick,
  even when that tick is itself a checkpoint tick), every turn since, their state at the first bad hash tick and
  their hash stream. The results plate says the games disagreed and offers the report (Show report on the
  desktop, Save report in the browser), never Godot's `user://` path.
- **The end.** Each client sends `RESULT(final tick, hash, outcome)`; the server ends the match with the agreed
  outcome by the same rule, and the party returns to the hub.
- **Replays** come free: a client holds every turn it received, so at the end it can save
  `{seed, rules_hash, build_seq, seats, turns}` (about 100 KB for 15 minutes). A replay viewer and spectating (the
  same feed, a few seconds behind, at most 6 watchers) come after v1.

### 6.8 The browser

- **Hidden tabs.** When a tab is hidden, Godot's main loop stops while the browser keeps delivering WebSocket
  messages into the engine's inbound buffer, which drops whole messages once full. Under lockstep the traffic is
  about 0.2 KB/s, so the raised 1 MiB buffer holds well over an hour of turns, and `TURN_REQUEST` repairs any gap.
  The server keeps a hidden tab's link through its silence, up to 10 minutes (`hidden_silence_ms`); past that it
  closes it and the game comes back through the reconnect path. Back, the game says `catching_up` or `shown`
  before anything else, and only `shown` brings its seat `BACK`.
  The client sends `VISIBILITY` from `visibilitychange` (a `JavaScriptBridge.create_callback`), so others see "In
  another tab". Its `PING`s stop with the loop, so after 5 s the caretaker takes the seat; when the tab returns,
  the client catches up (a progress bar) and gets the seat back at the next window.
- **Catch-up speed.** Target at least 2,000 ticks a second in the web export; checkpoints keep a catch-up under
  1,800 ticks. Today's node game takes 0.26 ms per tick natively, an upper bound for the leaner integer
  simulation; the web figure is measured in M4 (`sim_bench`).
- **The iframe.** `play/` embeds the game from `game/`; the outer page forwards `?join=` to the iframe's `src`, and
  the title flash writes to `window.parent.document.title` (same origin, allowed).
- **Caching.** Pages serves every file with `max-age=600`. The custom shell adds `?v=<build_seq>` to the `.pck` and
  `.wasm` URLs, so a reload always fetches a matching pair.

### 6.9 Versions and the rules hash

- **The protocol version is checked strictly** in `HELLO`: error 2 says the game is older ("A newer version is out:
  reload"), error 17 says the server is older ("Online play is being updated"). As in Cyberworld since its v10, the
  server accepts any `groundhold.vN` subprotocol at the upgrade, so it can answer which side is behind instead
  of "no answer".
- **`rules_hash` is a matchmaking key, not a refusal.** Parties and queues merge only players with the same hash.
  A party member with another hash shows "needs to reload"; `build_seq` (the CI run number, written into
  `data/build.json`) says which side is older. **Balance patches therefore need no server deploy.**
- **The level is a key too** (M8). The hash covers every level's numbers, so it stays one per build and `HELLO`
  carries it as before; the queue keys on mode, rules hash and the match's level (Normal for a mode without
  levels), and `MATCH_CONFIG` names the level every game builds its rules from.
- **Server releases** follow protocol or server changes, from tags, as Cyberworld's do ("keep the shared protocol
  in the same release as the game"). Before a restart the owner sets the maintenance line; `/health` reports the
  running matches, so a restart can wait for 0. A restart ends running matches, because they live in memory.

### 6.10 The server: what is taken from Cyberworld

Copy, do not depend: the two repositories release separately, and a shared package would couple their release
cycles for about 1,500 lines of stable code. **Reuse** = copy with renames only (`cyberworld` → `groundhold`,
`CYBERWORLD_SERVER_` → `GROUNDHOLD_SERVER_`, `/presence` → `/causeway`, 8765 → 8766). **Adapt** = keep the structure,
change the content. **Skip** = do not take it.

| Cyberworld piece | Verdict | In Groundhold |
|---|---|---|
| `websocket.py`: the bounded RFC 6455 subset, `/health` and `/stats` on the same port, the origin allowlist, the subprotocol, the other-version passthrough | **Reuse** | path `/causeway`, subprotocol regex `groundhold\.v[0-9]{1,4}`, `max_message` 1,100 |
| `protocol.py` pattern: a spec from JSON, `struct` records, exact lengths, `ProtocolError(reason, code)` | **Adapt** | keeps HELLO, WELCOME, ERROR, NOTICE, PING/PONG with RTT, BYE and the error codes; everything else is the hub, party, loading and match set of §6.5. ROM and Square fields go; `rules_hash` and `build_seq` come in |
| `shared/online/protocol.json` and its README byte tables | **Adapt** | `shared/net/protocol.json` and `shared/net/README.md`; read by GDScript at runtime, so no C header |
| `identity.py`: salted HMAC identity, `state_lock`, atomic writes, `moderation.json` hot reload, expiring kicks | **Reuse** | the privacy core, unchanged |
| `holds.py`: a place held 40 s, the resume bit | **Adapt** | party seats held 40 s; **match seats held until the match ends**, with `AWAY` and `BACK` injected into the turns |
| `app.py`: the server, pending-handshake cap (16; 5 s to the upgrade, 30 s more to `HELLO`), token buckets, output cap, housekeeping | **Adapt** | channels, snapshots and cards go; the tick loop becomes per-match turn clocks on absolute deadlines |
| `arena.py`: challenge, seats, input delay, relay, rematch | **Adapt** into `match.py` | matches come from parties or the queue; the relay becomes the **sequencer**; the server compares **hashes itself**; results by the agreed hash, not by seat 0's word; checkpoints are stored here |
| `stands.py`: the log kept in memory, catch-up under a byte budget, the watcher cap | **Adapt** into `catchup.py` | serves reconnects and resyncs now, spectators later; the "matches now" line for the hub |
| `teams.py` | **Skip** (the pattern only) | parties replace teams; keep its in-memory ask, answer and expiry pattern for `party.py` |
| `social.py`: fixed phrases and emotes | **Skip in v1** | signals are simulation commands; fixed phrases may come later under the same "no free text" rule |
| `trade.py` | **Skip** | no trading |
| `week.py`: a weekly seed | **Skip in v1** | a later "weekly flood" challenge; the derivation is ready when wanted |
| `retention.py` | **Reuse** | without trade and Board keys; `log_days = 0`, `stats_days = 365`, `backup_days = 14`; no match log on disk |
| `stats.py`, `/stats` | **Adapt** | joins, identities (a count), peak, matches started and finished per mode, **desyncs**, reconnects, caretaker seats, HELLOs per protocol version |
| `backup.py` and the backup sidecar | **Reuse** | backs up `identity.key` and `moderation.json` |
| `admin.py` | **Reuse** | minus `hide`/`unhide` (no Board) |
| `cli.py`, `hosting.py` (banner, LAN address probe, container detection, config beside the binary, environment overrides) | **Reuse** | new strings ("Players type this in Groundhold's Join panel"); the banner also says the beacon is on |
| `build.py`, `release.py`, `smoke.py`, `notices.py`, hash-pinned `requirements-build.txt` | **Reuse** | the deterministic zipapp, native freezes, a smoke outside the checkout, licence notices |
| `server/Dockerfile` and its `.dockerignore` | **Reuse** | non-root 10001, allowlisted context, two stages; `shared/net/` instead of `shared/online/` |
| `deploy/coolify/compose.yaml` and `server.ini` | **Reuse** | service `groundhold`, port 8766, the new domain, the same hardening, health checks, log caps and backup service |
| `deploy/selfhost/compose.yaml` (Caddy, Let's Encrypt, no access log) | **Reuse** | desktop games reach any community server with `wss://`; browser players through a web build its host publishes |
| `server.yml`, `server-native.yml`, `server-image.yml` | **Reuse** | plus a small `release.yml` that also attaches the desktop game builds |
| The test harness (`IsolatedAsyncioTestCase`, a real server on port 0, a minimal client) and `test_hardening`, `test_holds`, `test_hosting`, `test_packaging`, `test_retention`, `test_stats` | **Reuse** | plus new tests for turns, parties and the barrier (§7.3) |
| `--event-log` JSONL | **Reuse** | its `listening` event gives the port to the multi-process harness |
| Maintenance line plus error 16; other-version passthrough plus errors 2 and 17 | **Reuse** | |
| The client's address rule (`network_address.c`) | **Adapt** to GDScript | `scripts/net/address.gd` |
| The per-server token and key (`network_server_identity.c`, `network_identity.c`) | **Adapt** to GDScript | `Crypto.generate_random_bytes(16)` kept in `user://net.cfg` (IndexedDB on the web); `HMACContext` over the normalised origin; the key never leaves the device |
| The reconnect loop (30 s of retries, the resume bit), `PING` every 2 s with the RTT in it, the browser ping lesson | **Adapt** | the same timings; the UI says "Reconnecting... your towers keep firing" |
| `arena_sync.c` (hold one tick in twenty while ahead) | **Adapt** | becomes the playout pacing against server turns |
| Hash every 60 frames; "went apart by frame N"; the rules-then-ready start check | **Adapt** | compared on the server; the rules hash, then the tick-0 hash, so a mismatch is told by its cause |
| Per-OS native transports (libcurl, WinHTTP, JNI, NSURLSession) | **Skip** | Godot's `WebSocketPeer` covers desktop and web |
| NetPass and ROM identities in HELLO | **Skip** | becomes `rules_hash` plus `build_seq` |
| The Square, positions, snapshots, Inspect cards, profiles | **Skip** | the hub is a screen, not a walkable world |
| The `server/README.md` structure (host your own; the official server: who, rules, blocking, what is kept for how long, removal; Coolify deployment; the "At a release" checklist) | **Adapt** | rewritten for the TD; it is the privacy and operations answer `gaps.md` left open |

**New in the fork** (nothing in Cyberworld does these): the per-match turn clock and sequencer, the hash referee and
checkpoint store, parties with codes, the queue with Match Found, the loading barrier, the UDP beacon, and system
commands in the turn stream. All are in-memory objects in the same asyncio process.

### 6.11 Hosting

**The official server: a second app in the user's Coolify.**

| Setting | Value |
|---|---|
| Project and app | the existing project that runs `cyberworld-net-square`; a new app, for example `groundhold-server` |
| Build | Docker Compose from the Groundhold repository; Base Directory `/`; Compose Location `/deploy/coolify/compose.yaml`; **Preserve repository** on (for the read-only `server.ini` bind) |
| Domain | `https://groundhold.saschb2b.com` (the user picks it) to container port **8766**; no host port published |
| Services | `groundhold` and `backup`, both from one image, UID 10001, read-only root filesystem, `cap_drop: ALL`, `no-new-privileges`, an 8 MB tmpfs `/tmp`, json-file logs capped |
| Health | `GET /health` every 30 s; the backup sidecar turns unhealthy when the newest archive is older than 26 h |
| Players connect to | `wss://groundhold.saschb2b.com/causeway` (the client's default, from `data/net.json`) |

**What Coolify gives for free** (already set up and verified for Cyberworld): `wss://` with a Let's Encrypt
certificate and WebSocket upgrade forwarding to the container port; Git-based Compose deploys with a history and
one-click redeploy of a previous version, and optional auto-deploy on push; named volumes for `/data` and
`/backups`; health checks and restart policies; a container terminal for `--admin` moderation and `--restore`;
logs with rotation. All of it on the host that already serves `wss://cyberworld.saschb2b.com/presence`: no new
machine, no new bill. **The only new thing is a DNS record.**

**What it does not give:** UDP through the proxy (not needed: WebSocket only); per-match orchestration (not needed:
the server never simulates); off-host backups (copying them off is the owner's job, as for Cyberworld); more than one
region or a DDoS shield beyond the host's. **The proxy's access log must be checked off**, as in Cyberworld's release
step 2, because the server itself writes no IP address anywhere.

**Self-hosting:** `deploy/selfhost/compose.yaml`: the `ghcr.io` image, the backup sidecar and Caddy 2 with Let's
Encrypt and no access log; set `DOMAIN=` in `.env` and run `docker compose up -d`. If the image cannot be pulled it
builds from the repository. A community server reached over `wss://` serves desktop games; the published browser
game joins only the official server (§5.3: no address field), so browser players reach a community server through a
web build its host publishes, with `data/net.json` naming it and that page's origin in `origins`. If the user ever
leaves Coolify, the same file runs on any small VPS (a Hetzner CX23 is about €6 a month with IPv4, `netcode.md`
§8.2).

**LAN:** GitHub Releases carry the server as five native zips and the `.pyz` (Python 3.11+). Double-click it; the
console banner lists the LAN addresses (found by `connect()`ing a UDP socket to `192.0.2.1`, which sends nothing),
with firewall and macOS quarantine hints, and says the beacon is on. Friends over the internet without a server can
use Tailscale or ZeroTier, whose `100.64.0.0/10` addresses count as local (desktop only, plain `ws://`). A "Host on
this computer" button in the desktop game that launches the bundled binary (`OS.create_process`) comes after v1.

### 6.12 Privacy, moderation and operations

- **Identity without accounts:** a random 16-byte key made once and kept on the device; for each server the client
  derives a token with HMAC-SHA1 over a domain string and the server's normalised origin (`ws` and `wss` kept
  apart), and sends only that. The server's public identity is `HMAC-SHA256(identity.key, token)[:16]`: stable per
  server, unlinkable across servers. Resetting the key evades a ban; the allowlist exists for stricter hosts
  (Cyberworld's stated limits).
- **No free text.** Names by the regex, signals only, no chat. With nothing written there is nothing to report:
  players block each other locally by identity. The server refuses to start with `free_text = true`.
- **Moderation** is the local CLI in the container terminal (`list`, `ban`, `unban`, `mute`, `unmute`, `kick
  --minutes`, `unkick`, `forget`); "file access to the private state is authority". No remote admin endpoint.
- **Retention:** no players' log (`log_days = 0`), no IP address written anywhere, no match log on disk (turn logs
  live in memory until 60 s after the match), daily totals kept 365 days, backups 14 days.
- **`/health`**: status, protocol, name, motd, players, player cap, running matches, maintenance. **`/stats`**: the
  totals listed in §6.10; `desyncs` is the health gauge of the lockstep choice.
- **The policy page** (adapted from Cyberworld's server README): who runs it, who moderates, the rules, blocking,
  what is kept and for how long, how to have your identity forgotten. This reads as an answer to the GDPR question;
  it is not legal advice.

### 6.13 What needs the user's account or decision

| Item | Why |
|---|---|
| The subdomain (proposed `groundhold.saschb2b.com`) and its DNS record | `wss://` from an https page needs a certificate for a hostname |
| A new app in the existing Coolify project, with access to the Groundhold repository, the domain and port 8766 set, Preserve repository on | the official server |
| Deploy policy: from tags at releases (proposed) or auto-deploy on push | a restart ends running matches; balance changes need no deploy |
| Making the `ghcr.io/saschb2b/groundhold-server` package public, once, by hand | self-hosters pull it |
| Checking that Coolify's proxy writes no access log for the domain | the privacy promise |
| The policy page text: operator, moderation contact, and whether an imprint is needed | an EU-hosted service handling names and connection data |
| Desktop releases: GitHub Releases for Windows, Linux and macOS; macOS signing and notarisation (an Apple developer account) or unsigned builds with quarantine instructions | LAN play needs desktop builds; today only Web is exported |

---

## 7. Testing

### 7.1 Six levels

| Level | What runs | Deterministic | Where |
|---|---|---|---|
| 0. Simulation | `SimMatch` driven by turn lists from scenario steps; N simulations fed the same turns; whole matches in seconds, no views, no network | yes | `tests/sim/sim_harness.tscn`, `tests/scenarios/sim_*`, `tests/balance/` |
| 1. Fake sequencer | `tests/net/fake_sequencer.gd`, a GDScript port of the server's match side (turn sealing, hash referee, checkpoint store, `AWAY`/`BACK`, `RESYNC`, the loading barrier), counting turns instead of milliseconds, plus N `MatchClient`s in one SceneTree, joined by `tests/net/fake_link.gd` with seeded latency, jitter, stalls, cut-offs and hidden tabs. Client 1 renders; the others run headless | yes; `--determinism` passes | `tests/net/loopback_match.tscn`, `tests/scenarios/net_*`, `flow_*` |
| 2. Python server | `unittest.IsolatedAsyncioTestCase` with a real server on `127.0.0.1:0`, a minimal test client over real sockets and a fake clock for turns and timers (Cyberworld's harness: 108 tests in 20 s there) | yes | `server/tests/` |
| 3. Golden transcripts | byte files recorded by the Python tests, decoded and re-encoded by a godot-agent scenario, and the reverse | yes | `shared/net/transcripts/*.bin`, `tests/scenarios/protocol_golden_*` |
| 4. Several processes | the Python server (`--port 0 --event-log`) and N headless Godot clients (`-- --join=127.0.0.1:<port> --bot --quit-after-match --hash-log=<file>`), optionally through a shaping proxy; finished matches and equal hash streams | eventual | `tools/net/smoke.py`, CI |
| 5. Native against web | one recorded turn log replayed natively and in the web export under headless Chromium; the hash streams compared | yes | a kit gap (§7.5); by hand with agent-browser until then |

**Where the screens are tested.** The lobby's logic lives on the server and is tested in Python. The client only
renders server state, so `flow_*` scenarios feed scripted `PARTY_STATE`, `LOAD_STATE`, `MATCH_FOUND` and
`MATCH_END` messages through the fake sequencer and assert what the screens show. The multi-process smoke drives
the real flow end to end.

### 7.2 Conventions, and an example

The example below is an M2-era scenario (it uses the Lookout).

- The loopback scene exposes `scene.start(config)`, `scene.seq` (the fake sequencer), `scene.client(k)` (with
  `.sim`, `.cmd(type, a, b, c)`, `.last_refusal()`, `.phase()`), `scene.run_turns(n)`, `scene.cut(k, turns)`,
  `scene.hide(k, turns)` (a background tab: the client stops polling while its 64 KiB buffer fills and drops, as the
  web build does), `scene.corrupt(k, field, value)` (for desync tests) and `scene.hashes_agree()`.
- Fast-forward with `ticks_per_frame`, never `time_scale`.
- Every scenario that asserts game state also watches a state hash, so `--determinism` compares the whole
  simulation and not just the asserted fields.

```json
{
  "name": "net_two_clients_converge",
  "scene": "res://tests/net/loopback_match.tscn",
  "seed": 7,
  "watch": {"turn": "scene.seq.turn", "hash": "scene.client(1).sim.state_hash().hex_encode()"},
  "steps": [
    {"eval": "scene.start({'mode': 'high_water', 'clients': 2, 'builders': ['lamplighter', 'lookout'], 'latency_turns': [2, 4], 'jitter_turns': 1})"},
    {"wait_until": "scene.phase() == 'IN_MATCH'", "timeout": 600},
    {"eval": "scene.client(1).cmd('BUILD', 0, 8, 3)"},
    {"eval": "scene.client(2).cmd('BUILD', 1, 10, 8)"},
    {"wait_until": "scene.client(1).sim.towers.size() == 2 and scene.client(2).sim.towers.size() == 2", "timeout": 120},
    {"assert": "scene.client(1).sim.seats[0].gold == 80 and scene.client(1).sim.seats[1].gold == 65", "msg": "each paid for their own tower"},
    {"eval": "scene.client(2).cmd('SELL', scene.client(2).sim.tower_at(0, 8, 3).id, 0, 0)"},
    {"wait": 30},
    {"assert": "scene.client(2).last_refusal() == 'NOT_YOURS'", "msg": "only the owner sells"},
    {"eval": "scene.run_turns(600)"},
    {"assert": "scene.hashes_agree()", "msg": "every hash both clients sent matched"}
  ]
}
```

### 7.3 The Python server's tests

Reused from Cyberworld with renames: `test_hardening` (malformed frames, limits), `test_holds`, `test_hosting`,
`test_packaging`, `test_retention`, `test_stats`. New:

| Test | Asserts |
|---|---|
| `test_turn_clock` | turns seal on absolute deadlines: no drift over 10 minutes of fake clock; a stalled loop seals the missed turns in a burst |
| `test_turn_stamping` | the seat comes from the connection; rotation order inside a turn; sequence numbers must increase |
| `test_cmd_shape_and_rate` | out-of-range arguments and an empty `CMD` bucket are refused |
| `test_hash_referee` | agreement; a minority with 3 seats gets `RESYNC`; 2 seats disagreeing end the match "desynced" |
| `test_checkpoint_accept` | an upload is kept only if its SHA-256 matches the agreed hash |
| `test_catchup_budget` | a reconnect stream is paced at 2 KB per 50 ms while the output is under 4 KB |
| `test_away_back` | 5 s of silence injects `AWAY`; a resume `HELLO` with the same identity gets the checkpoint, the turns and then `BACK` |
| `test_party_codes` | the alphabet (10,000 codes, none containing `0 1 O I L U A E`), lenient input (`k7q-4m`), rate-limited lookups, expiry after 15 minutes |
| `test_party_flow` | Ready, the 3 s countdown and its cancel, leader handover, mode change clears Ready, removal |
| `test_barrier` | the 4 s minimum, `Slow` at 15 s, start-without at 30 s, automatic start at 45 s, the 120 s ceiling, tick-0 mismatch aborts |
| `test_queue` (M6) | parties merge per mode and rules hash; Match Found; a decline sends the others to the front; Builder clashes resolve by queue order and backup |
| `test_versions` | error 2 for an older client, 17 for an older server; a party member with another rules hash is flagged |
| `test_beacon` | the datagram layout; no beacon inside a container |

### 7.4 Golden transcripts

`shared/net/transcripts/` holds recorded byte streams: a handshake, a hub session, a loading barrier and a short
match with every command and system type. Python's `test_golden` replays them against the real server; the
`protocol_golden_decode` scenario decodes every message with the GDScript codec into the expected values, and
`protocol_golden_encode` encodes the canonical command set to the same bytes. Re-recording is a deliberate step
(`python3 server/tools/record_transcripts.py`), reviewed like any other change.

### 7.5 What godot-agent-kit needs

Ordered by when a milestone needs it. Each has a project-side workaround, so no milestone blocks on the kit.

| # | Extension | Needed by | Workaround until then |
|---|---|---|---|
| 1 | **Tick-exact fast-forward:** a `ticks_per_frame` scenario key handed to a documented game hook, and a warning when `time_scale` > 1 runs under `--fixed-fps` (it lengthens every tick; the kit's `max_physics_steps_per_frame` setting is ignored in that mode) | M1 | a `set` step on `MatchClient.ticks_per_frame` |
| 2 | **A determinism lint:** `godot-agent check --sim-lint scripts/sim` with a forbidden-token list (`float`, float literals, `sin(`, `cos(`, `tan(`, `atan2`, `sqrt(`, `pow(`, `exp(`, `log(`, `lerp`, `randf`, `randi`, `randfn`, `shuffle`, `pick_random`, `Vector2`, `Vector3`, `Basis`, `Transform`, `look_at`, `get_tree`, `get_nodes_in_group`, `Time.`, `OS.get_ticks`, `delta`, `time_scale`, `hash(`) and a per-line allow comment | M1 | the `sim_lint_clean` scenario greps the folder through `FileAccess` |
| 3 | **A loopback sequencer** provided by the kit: a fake turn server fed by scenario steps (`{"net": "lag" / "stall" / "cut" / "reconnect" / "hide", "client": 2, "turns": 60}`), with **golden byte transcripts** shared with the Python tests | M1 | the project's `tests/net/fake_sequencer.gd` and `fake_link.gd` |
| 4 | **Multi-process topologies:** an external server command, readiness from its `listening` event (which carries the port when started with `--port 0`), N headless clients with per-client user arguments, per-process logs and results, merged pass or fail, one global timeout, orphan cleanup (including `taskkill /T` on Windows) | M1b, M4 | `tools/net/smoke.py` (Cyberworld's `smoke.py` pattern) |
| 5 | **Steps addressed to one client** (`"client": 2` on `eval`, `assert`, `key`, `click`, `capture`) and bot plans per seat | M3 | `scene.client(k).` helpers |
| 6 | **Cross-process hash-stream comparison and desync bisection:** every process logs `(tick, hash)`; the report names the first differing tick and diffs the two state dumps; `--determinism` extends to topologies | M4 | `smoke.py` diffs the hash logs |
| 7 | **Native against web replay hash checks in headless Chromium:** export the web build, serve it on localhost, replay one log natively and in the browser, compare hash streams. This is the gate the lockstep model depends on | M4 (gate before M5's release) | by hand with agent-browser |
| 8 | **A WebSocket latency and stall proxy:** seeded latency, jitter, stalls and cut-offs between real clients and the real server | M4 | `tools/net/shaper.py` |
| 9 | **Background-tab simulation:** pause one client's main loop while its socket keeps receiving | M4 | `scene.hide(k)` at level 1 |
| 10 | **Parameterised scenarios:** a `matrix` block (Builders × player counts × seeds) expanding one file into named cases with a summary row each | M2 | `tools/gen_balance_scenarios.py` writes the files |
| 11 | **Per-group metrics in reports** (leaks by creep kind) | M2 | watches |
| 12 | **A text-typing step** (`{"type": "k7q-4m"}`) | M3 | `set` on the `LineEdit` plus a `key` Enter |
| 13 | **Per-client captures** through a `SubViewport` per client branch | M3 | one rendering client per scenario |
| 14 | **An opt-out of `--determinism`** for real-socket scenarios (`"deterministic": false`) | M1 | keep them outside `tests/scenarios/` |

### 7.6 CI

| Workflow and job | When | Does |
|---|---|---|
| `pages.yml` `test` (exists) | every push and pull request | `godot-agent scenario . --headless`: simulation, fake-sequencer, view and flow scenarios and the golden transcripts |
| `pages.yml` `balance` (new) | pull requests touching `scripts/sim/`, `data/plans/`, `tests/balance/`; nightly | `godot-agent scenario tests/balance --headless` |
| `pages.yml` `net-smoke` (new) | every pull request | `tools/net/smoke.py`: the Python server plus two headless clients, a two-player High Water and (from M6) a 1v1 Tide Race; finished matches with equal hash streams |
| `pages.yml` `build` (exists) | every push | also writes `data/build.json` (`build_seq` = the run number, and the commit) |
| `server.yml` (from Cyberworld) | pushes and pull requests touching `server/`, `shared/net/`, `deploy/` | unit tests on Python 3.11; the zipapp and a real-process smoke; `docker compose config` and build for both Compose files; a bare `docker run` that must answer `/health` |
| `server-native.yml`, `server-image.yml` (from Cyberworld) | called by `release.yml` | five native server zips; the multi-arch image to `ghcr.io` |
| `release.yml` (new) | a `v*` tag | the server packages and image, plus the desktop game exports (Linux, Windows, macOS), attached to the GitHub release |
| Release gate (manual) | before a tag | `godot-agent scenario . --determinism` and the native-against-web replay check |

---

## 8. Implementation milestones

Rules for every milestone: `godot-agent check .` clean (`--resources` after scene or `.tres` edits), `godot-agent
scenario . --headless` green, every changed behaviour has a scenario that fails without the change, `godot-agent
asset check .` clean, `AGENTS.md` and `CHANGELOG.md` updated. "Tracks" inside a milestone touch disjoint files.
Scenario and test files are new, separately named files, so each track adds the ones for its own behaviour
without touching another track's.

**Day 0 of M1 is a contract commit** that every track builds against: `shared/net/protocol.json` with all message ids
and layouts of §6.5, and `scripts/sim/sim_types.gd` with the command types, refusal reasons, event types and record
field names.

### M1. Two Builders on one road: the integer simulation and a two-player co-op match over localhost

**Goal.** *M1a:* the solo game plays exactly as today (8 waves, today's three towers with today's upgrade standing
in for branch A) on the new integer simulation, through the in-process `LocalSequencer`. *M1b:* two desktop windows
on one machine play that match together through the forked server on `ws://127.0.0.1:8766/causeway`: shared lives,
own gold, full bounty to both, owner-only upgrade and sell, Ready. No hub yet: the server's `--dev-match classic:2`
forms a match from the first two `HELLO`s, and the game takes `-- --join=127.0.0.1`. `content.gd` carries a
`classic` preset (today's 8 waves as `classic8`, no armour, nothing winged) that M2 replaces with `hollow12`.

| Track | Files |
|---|---|
| A. Simulation | `scripts/sim/content.gd`, `sim_types.gd`, `sim_match.gd`, `sim_road.gd`, `sim_records.gd`, `sim_waves.gd`, `sim_math.gd`, `sim_rng.gd`, `sim_codec.gd`, `caretaker.gd`; `data/plans/lamplighter.json`; `tests/sim/sim_harness.tscn`, `tests/sim/sim_harness.gd` |
| B. Server fork | `server/main.py`, `server/build.py`, `server/.gdignore`, `server/groundhold_server/__init__.py`, `websocket.py`, `protocol.py`, `app.py`, `match.py`, `cli.py`, `hosting.py`; `server/tests/test_hardening.py`, `test_turn_clock.py`, `test_turn_stamping.py`, `test_dev_match.py`; `shared/net/protocol.json`, `shared/net/README.md`, `shared/net/transcripts/m1_*.bin` |
| C. Client networking | `scripts/net/protocol.gd`, `link.gd`, `address.gd`, `turn_source.gd`, `local_sequencer.gd`, `remote_sequencer.gd`, `match_client.gd`, `playout.gd`; `tests/net/fake_sequencer.gd`, `fake_link.gd`, `loopback_match.tscn`, `loopback_match.gd` |
| D. Views and the app | `scripts/game.gd` (facade; display tables), `main.gd` (boot flags `--join`, `--bot`, `--seed`, `--hash-log`, `--quit-after-match`), `creep.gd`, `tower.gd`, `projectile.gd`, `build_controller.gd` (commands, ghost), `hud.gd` (Ready replaces Next Wave, Ready pips), `fx.gd` (own RNG); `scripts/ui/party_strip.gd`; delete `scripts/wave_director.gd`; `tests/bot.gd`; every `tests/scenarios/*.json` and `tools/media/*.json` re-baselined; `AGENTS.md` |
| E. Multi-process smoke | `tools/net/smoke.py` |

**Acceptance:**

| Scenario or test | Asserts |
|---|---|
| `bot_wins` (re-baselined) | solo through `LocalSequencer` at `ticks_per_frame` 8 wins with at least 10 lives |
| `idle_player_loses` | still loses before the last wave |
| The other existing scenarios | the same intent through commands; `next_wave_starts` becomes `ready_starts_next_wave` |
| `sim_tick_exact` | the hash at tick 3,000 is the same at 1 and at 8 ticks per frame |
| `sim_ignores_views` | the same hash with views on and off |
| `sim_same_turns_same_hash` | two simulations fed one turn log agree at every 60-tick hash |
| `sim_checkpoint_roundtrip` | `deserialize(serialize())` at tick 2,000 reaches the same hash at tick 6,000 |
| `sim_replay_reproduces_hashes` | a recorded log replayed reproduces every hash |
| `sim_range_intervals_match_distance` | interval membership equals brute-force `d² ≤ r²` for every buildable cell |
| `sim_cannon_ignores_visual_aim` | turning the view's cannon head changes no landing point |
| `sim_lint_clean` | no forbidden token in `scripts/sim/` |
| `coop_bounty_to_every_seat`, `coop_only_owner_sells`, `coop_ready_all_skips_and_pays_each` | the co-op rules of §4.1 |
| `turn_order_rotates` | two `BUILD`s on one cell in one turn: rotation decides, the other gets `CANNOT_BUILD_THERE`, identically on both clients |
| `net_two_clients_converge` | §7.2 |
| `net_slow_client_stalls_alone` | client 2 stalls 3 s: client 1's tick keeps advancing; client 2 catches up; hashes agree |
| `protocol_golden_m1` | the GDScript codec decodes and encodes the M1 transcripts byte for byte |
| Python `test_turn_clock`, `test_turn_stamping`, `test_dev_match`, `test_hardening` | §7.3 |
| `tools/net/smoke.py --mode classic --clients 2` | two headless clients finish the match against the real server with equal hash streams |

**Done when** the above pass and, by hand, `python3 server/main.py --dev-match classic:2` plus two windows of
`godot --path . -- --join=127.0.0.1` play all eight waves together.

### M2. Builders and checks (parallel with M3)

**Goal.** High Water as designed with the complementary pair: the Lamplighter's forks and the whole Lookout; flat
armour, `air`, the Duskmoth, the Bristlesow, team effects and Help, the `hollow12` list, the player-count table,
the positional command card with branches, check glyphs with the creeps' portraits beside them, the wave-list
tooltip and the first balance gates.

| Track | Files |
|---|---|
| A. Rules | `scripts/sim/content.gd`, `sim_match.gd`, `sim_effects.gd`, `sim_targeting.gd`, `caretaker.gd`; `data/plans/lamplighter.json`, `data/plans/lookout.json` |
| B. HUD and input | `scripts/hud.gd`, `resource_strip.gd`, `portrait.gd`, `build_controller.gd`, `minimap.gd`, `game.gd` (display tables) |
| C. Art and views | `art_src/models/towers/*.json` (3 Lamplighter B branches; the Lookout's 3 bases and 6 branches), projectile recipes, `art_src/blender/duskmoth.py`, `art_src/ui/icons.json`, `asset_manifest.json`, `models/`, `ui/icons/`, `sfx/`; `scripts/creep.gd` (hover and flap), `tower.gd`, `projectile.gd`, `fx.gd` (mark rune) |
| D. Bots and balance | `tools/gen_balance_scenarios.py`, `tests/balance/*.json` |

**Acceptance:** `bot_wins` and `idle_player_loses` move to `hollow12` and keep their bars; `armor_reduces_small_hits` (an arrow does 4 to a Thornback; a 32-damage bolt that pierces 3 does
31), `armor_floor_quarter`, `winged_ignores_ground_towers` (an Arrow Tower never fires at a Duskmoth, a Skyward Loft
does, cannon splash leaves moths untouched), `fork_is_final`, `fork_branch_stats`, `effects_strongest_applies`
(Frost Spires at 45% and 60% give 60%), `mark_amplifies_teammate_and_credits_help`, `boss_resists_control`,
`thrifty_sells_for_90`, `keen_sight_range`, `bot_wins_solo_lamplighter`, `bot_wins_solo_lookout`,
`bot_wins_high_water_2p`, `idle_team_loses_2p`, `one_idle_of_two_loses`, `coverage_matters_winged`,
`coverage_holds_complementary_lo`, `high_water_length_2p`, `hud_branch_card` (Q and W show the branches on your
own unforked tower), `hud_check_icons` (the Winged glyph and the Duskmoth's portrait show before wave 5),
`hud_teammate_tower_greys_sell`; `godot-agent asset check .` clean; `godot-agent run . --renderer gl_compatibility`
shows the Duskmoth's glow with no extra lights.

### M3. The loop: hub, Builders, party, loading, results, LAN (parallel with M2)

**Goal.** The game boots into the hub. Parties with codes on a server (localhost or LAN), Ready and the 3-2-1
countdown, the Builders screen with main, backup and Try, the loading barrier with per-player sync states, results
with Play again, back to the hub with the party intact; identity without accounts; LAN by Nearby (beacon) or address;
offline solo from the hub.

| Track | Files |
|---|---|
| A. Server lobby | `server/groundhold_server/party.py`, `codes.py`, `lobby.py` (barrier, match lifecycle, back to party), `identity.py`, `holds.py`, `beacon.py`, `retention.py`, `stats.py`, `admin.py`, `backup.py`, `app.py` (routing); `server/tests/test_party_codes.py`, `test_party_flow.py`, `test_barrier.py`, `test_holds.py`, `test_beacon.py`, `test_identity.py`, `test_retention.py`, `test_stats.py` |
| B. Client session | `scripts/session/session.gd` (autoload state machine: OFFLINE, CONNECTING, HUB, COUNTDOWN, QUEUED, MATCH_FOUND, LOADING, IN_MATCH, RESULTS), `profile.gd`, `identity.gd`; `scripts/net/beacon_listener.gd`; `project.godot` (autoload, main scene) |
| C. Screens | `scenes/hub.tscn`; `scripts/ui/shell.gd`, `hub_panel.gd`, `join_panel.gd`, `builders_screen.gd`, `loading_screen.gd`, `results_panel.gd`, `coverage_row.gd`, `name_prompt.gd`; `scripts/main.gd` (enter from `MATCH_CONFIG`, leave to results) |
| D. Console art and characters | `art_src/ui/console.json`, `art_src/ui/console.py`, `ui/console/`; `art_src/blender/builders/lamplighter.py`, `lookout.py`; `models/builders/` |
| E. Flow tests | `tests/net/fake_sequencer.gd` (hub and loading scripting), `tests/scenarios/flow_*.json` |

**Acceptance:** Python `test_party_codes`, `test_party_flow`, `test_barrier`, `test_holds` (party seat 40 s),
`test_beacon`, `test_identity` (stable per origin, unlinkable across), the back-to-party test; scenarios
`flow_hub_boots_offline` (the main scene is the hub; Play reaches a match in under 300 frames),
`flow_party_panel_renders_state` (2/4, glyphs, Ready ticks, "needs to reload"), `flow_coverage_row` (Lamplighter +
Lookout light all four; two Lamplighters leave Armored and Winged dim), `flow_loading_card_states`
(Connecting, a percentage, Checking, Ready; Slow at 15 s), `flow_results_one_line_each`,
`flow_results_play_again_keeps_party`, `flow_try_from_builders`, `flow_join_code_lenient`, `beacon_lists_server`
(an injected datagram; a mismatched version is not listed), `address_rule` (`192.168.1.20` →
`ws://192.168.1.20:8766/causeway`, `100.64.1.2` → `ws://`, `play.example.org` → `wss://play.example.org/causeway`),
`identity_token_stable`; `tools/net/smoke.py --flow`: two clients go hub, party by code, start, loading, match,
results, and are both back in the party. By hand: two desktops on one LAN find the server under Nearby, play and
return together.

### M4. Resilience: hashes, checkpoints, reconnect, the caretaker, desyncs, background tabs

**Goal.** Everything §6.7 and §6.8 describe, measured; the native-against-web check run by hand.

| Track | Files |
|---|---|
| A. Server | `server/groundhold_server/match.py` (hash referee, checkpoint store, `AWAY`/`BACK`/`LEFT`, `RESULT` agreement, `TURN_REQUEST`), `catchup.py`, `stats.py` (desync and reconnect counters); `server/tests/test_hash_referee.py`, `test_checkpoint_accept.py`, `test_catchup_budget.py`, `test_away_back.py`, `test_versions.py` |
| B. Client | `scripts/net/match_client.gd`, `playout.gd`, `checkpointing.gd`, `desync_dump.gd`, `web_bridge.gd` (`visibilitychange`, title flash, query string); `scripts/ui/connection_overlay.gd` |
| C. Simulation | `scripts/sim/caretaker.gd` (any seat, returning, hand-back at the window), `sim_codec.gd`, `sim_match.gd` (seat states) |
| D. Tools and tests | `tools/net/smoke.py` (faults), `tools/net/shaper.py`; `tests/net/fake_sequencer.gd`, `fake_link.gd` (cut, hide, corrupt); `tests/scenarios/net_*.json`, `tests/scenarios/sim_bench.json` |

**Acceptance:** `net_hashes_agree_long_match` (four clients, a whole `hollow12`), `net_checkpoint_kept_only_if_agreed`,
`net_reconnect_from_checkpoint` (client 2 cut at wave 5 for 20 s rejoins, catches up, hashes agree, and gets the seat
back at the next window), `net_away_after_5s_caretaker_builds` (the caretaker spends the seat's gold and is Ready
every window), `net_hand_back_at_window` (the seat's commands are refused until the window opens),
`net_minority_desync_resyncs` (three clients; client 3's gold corrupted at tick 2,000; `RESYNC`; hashes agree after),
`net_two_seat_desync_ends_with_dumps`, `net_hidden_tab_catches_up` (hidden 120 s: the caretaker took over; on
visible the client catches up and an injected gap is repaired by `TURN_REQUEST`), `party_rules_hash_needs_reload`,
`sim_bench` (four seats at wave-11 load; reports native ticks per second and fails below a floor set from the first measurement, starting at 3,000); Python `test_hash_referee`,
`test_checkpoint_accept`, `test_catchup_budget`, `test_away_back`, `test_versions`; `smoke.py --shaper` (150 ± 50 ms
latency and a 3 s stall on one client: the other's tick rate never drops, and the match ends with equal hash
streams). By hand: the web export replays a recorded log to the same hash stream, and its `sim_bench` reaches 2,000
ticks per second.

### M5. Ship it: online on Coolify, LAN binaries, desktop and browser builds

**Goal.** v1's networking in players' hands: the official server live at the user's subdomain, self-host and LAN
packages, desktop builds for LAN, the browser build online, the join link, the release workflow and the policy page.

| Track | Files |
|---|---|
| A. Packaging and CI | `server/Dockerfile`, `server/Dockerfile.dockerignore`, `server/build.py`, `release.py`, `smoke.py`, `notices.py`, `requirements-build.txt`; `.github/workflows/server.yml`, `server-native.yml`, `server-image.yml`, `release.yml` |
| B. Deployment | `deploy/coolify/compose.yaml`, `deploy/coolify/server.ini`, `deploy/selfhost/compose.yaml`, `deploy/selfhost/.env.example`, `deploy/.gdignore` |
| C. Client release | `export_presets.cfg` (Linux, Windows and macOS presets; `shared/net/*.json` and `data/*.json` included; `server/*` and `deploy/*` excluded), `web/play/index.html` (forward `?join=`), `web/shell.html` (`?v=<build_seq>`), `data/net.json` (the official URL), `.github/workflows/pages.yml` (`build_seq`, the `net-smoke` and `balance` jobs) |
| D. Documentation | `server/README.md` (host your own; the official server and its policy; Coolify deployment; the "At a release" checklist), `README.md` ("Play together"), `CHANGELOG.md`, `AGENTS.md`, `web/index.html` (link to the policy) |

**Acceptance:** `server.yml` green (unit tests on 3.11, the zipapp smoke, both Compose configs, `docker run` answers
`/health`); a release dry run whose native zips answer `--help` and serve `/health` outside the checkout; the desktop
exports build in CI; `flow_join_link_through_iframe` checked with agent-browser (`?join=K7Q4M` reaches the party);
the release gate of §7.6 passes. Live, with the user: a browser on Pages and a desktop build join one party by code
on `wss://groundhold.saschb2b.com/causeway` and finish a High Water match; `/stats` shows the match and no desync;
the Coolify proxy's access log is confirmed off.

### M6. The full roster, Tide Race and the queue

**Goal.** v1 complete: the Bellfounder and the Beekeeper; the Race (two hollows in one simulation, per-hollow
clocks, race time, rival line, the V view, two-team loading and results, racing the caretaker); open seats and Find
a rival with Match Found, front-of-queue requeue, Builder clash resolution and "start with caretakers" after 60 s.

| Track | Files |
|---|---|
| A. Rules | `scripts/sim/content.gd`, `sim_effects.gd` (stun and its immunity, pulses, clouds, crack aura, haste), `sim_match.gd` (two hollows, race rules, the 20-minute cap), `caretaker.gd`; `data/plans/bellfounder.json`, `beekeeper.json` |
| B. Art | the two Builders' 18 tower models, bell and bee effects, two characters, icons and sounds |
| C. Race views | `scripts/main.gd` (two hollows), `terrain.gd`, `decor.gd`, `camera_rig.gd` (V), `minimap.gd`, `resource_strip.gd` (rival line); `scripts/ui/loading_screen.gd`, `results_panel.gd` (two-team layouts) |
| D. Queue | `server/groundhold_server/queue.py`, `server/tests/test_queue.py`; `scripts/ui/match_found.gd`, `hub_panel.gd` (queue states); `scripts/session/session.gd` |

**Acceptance:** `stun_then_immune`, `toll_pulse_hits_all_ground`, `cloud_hits_air_and_ground`,
`crack_lowers_armor_for_all_and_credits_help`, `haste_any_owner`, `tithe_pays_capped`, `bronze_hand_ignores_2`,
`bot_wins_solo_bellfounder`, `bot_wins_solo_beekeeper`, `bot_wins_high_water_3p`, `bot_wins_high_water_4p`,
`idle_team_loses_3p`, `idle_team_loses_4p`, `coverage_holds_complementary_bb`, `race_same_waves_both_hollows`,
`race_independent_clocks`, `race_time_penalty_per_life`, `race_rival_fell_clear_to_win`, `race_cap_20_minutes`,
`race_mirror_is_fair`, `race_bots_both_finish`, `race_rival_view_toggle`, `race_results_two_teams`; Python
`test_queue` (merging open parties, a decline requeues the others at the front, the timeout, Builder clash
resolution, the caretaker offer at 60 s, keying on the rules hash); `smoke.py --mode tide_race`; two hollows in
`godot-agent run . --renderer gl_compatibility` within the browser's frame budget.

### M7. Undertow (v1.1)

**Goal.** Undertow, the Duel of §1.4: the Drift, corked packs by commitment, uncorking, stipends, breaches,
Seawall, the Surge, duelling the caretaker, and its balance gates.

| Track | Files |
|---|---|
| A. Simulation | `scripts/sim/sim_undertow.gd` (drift, cork, commit, reveal, stipend, breach, Seawall, the Surge), `sim_match.gd` (shared clock), `content.gd` (packs, the `undertow` preset) |
| B. Interface | `scripts/ui/duel_bar.gd`, `drift_tray.gd`; `scripts/hud.gd` (duel layout); `art_src/ui/console.json` (drift tray, corked bottle) |
| C. Caretaker and balance | `scripts/sim/caretaker.gd` (a corking policy), `data/plans/*_duel.json`, `tests/balance/duel_*.json` |
| D. Server | `server/groundhold_server/queue.py` (undertow mode), `server/tests/test_queue.py` |

**Acceptance:** `drift_same_for_both_sides`, `drift_seeded`, `drift_never_skips_a_check_twice`,
`cork_commit_hides_pack` (the rival's simulation holds no pack id before the uncorking, and the gold is the same
for every pack of a tier), `uncork_reveal_checked` (a wrong salt gives `BAD_REVEAL`), `uncork_auto_at_24s`,
`fizzle_without_reveal`, `uncorked_creeps_pay_defender`, `breach_pays_double`, `seawall_charges_every_four`,
`seawall_stuns_near_holdfast`, `surge_freezes_stipend`, `tiebreak_lives_then_breach`, the Duel's balance gates of
§4.4, `duel_caretaker_plays_full_match`.

### M8. Stacked waves, Hard and Very Hard, the bottle's candidates and the fork pass

**Goal.** The answers to the first playtest (`halv`, session 1): a call for the next wave during a wave, paid for
its risk (§2.7, P6); Hard and Very Hard for the whole party, matched on in the queue (§2.6, P5); a rival's corked
bottle naming its candidates (§1.4, P3); and every fork pair spread so each branch has its own job (§3.8, P7).
[`contract-m8.md`](contract-m8.md) fixes what the tracks share.

| Track | Files |
|---|---|
| A. Rules | `scripts/sim/content.gd` (`DIFFICULTY_IDS`, `DIFFICULTIES`, the presets' `stack_max`, `stake_pm` and `levels`, `rules(mode, difficulty)`), `sim_waves.gd` and `sim_match.gd` (stacked horns, waves on the road, clears in order, the levels at spawn, the race's fall with two waves), `sim_undertow.gd` (the candidates query), `sim_codec.gd` (the M8 block), `caretaker.gd` (it stacks its plan's list); `data/plans/*.json` (`stack`); `tests/sim/sim_harness.gd` (`difficulty`, stacking seats); `tools/gen_balance_scenarios.py`, `tests/balance/` |
| B. Views and hub | `scripts/game.gd`, `main.gd`, `hud.gd`, `resource_strip.gd`, `build_controller.gd` (Ready in a wave, its second press), `scripts/ui/hub_panel.gd` (the level's words), `builders_screen.gd`, `loading_screen.gd`, `results_panel.gd`, `match_found.gd`, `match_menu.gd`, `party_strip.gd`, `drift_tray.gd` and `duel_bar.gd` (the candidates); `tests/bot.gd` (it can stack its plan's list) |
| C. Server and protocol | `shared/net/protocol.json` (version 2, `difficulties`, the fields), `shared/net/README.md`, transcripts; `server/groundhold_server/party.py`, `queue.py`, `lobby.py`, `match.py` and tests; `scripts/net/*` (`MATCH_CONFIG`'s level into the rules, the replay record, the desync dump's format 2); `scripts/session/*` (the party's and the profile's level); `tests/net/*`, `tools/net/smoke.py` |
| D. Fork pass (after A) | `scripts/sim/content.gd`'s `TOWERS` numbers, `tests/sim/fork_bench.gd`, `fork_branch_stats.gd`; then the plans and gates the pass moves |

**Acceptance:** `stack_ready_in_a_wave`, `sim_stacked_waves_spawn_together`, `stack_at_most_three`,
`stack_pays_window_and_stake`,
`stack_clears_in_order`, `stack_no_window_between`, `stack_ready_carries_into_window`, `stack_waits_for_returning`,
`stack_not_in_classic_or_duel`, `race_stacked_fall_wave`, `sim_caretaker_stacks_its_list_in_a_race`,
`difficulty_rules_apply`, `difficulty_normal_changes_nothing`, `sim_checkpoint_roundtrip_m8`,
`bottle_candidates_are_its_window_offer`, the stacking, difficulty and fork gates of §4.4; `hud_stack_*`,
`view_stack_banners`, `view_difficulty_*`, `view_duel_bottle_candidates`, `bot_stacks_through_its_orders`; Python
`test_party_flow` and `test_queue`'s difficulty cases, `test_versions` (a version-1 game hears error 2),
`test_contract_m8.py`, `protocol_golden_m8`, `flow_difficulty_*`, `net_rejoin_keeps_level`,
`smoke.py --flow --difficulty hard`.

### Dependencies and parallel work

```
 M1a -> M1b --+--> M2 (rules, HUD, art) ---------------+--> M6 (roster, Race, queue) --> M7 (Duel, v1.1) --> M8
              |                                        |
              +--> M3 (lobby, session, screens, LAN) --+--> M4 (resilience) --> M5 (ship) --> v1 release
 Art for M6 (track B) can start as soon as M2's recipe format is fixed. M5's tracks A and B (packaging, Compose
 files) can start once M3's server modules exist, beside M4. In M8, rules (A), views and hub (B) and the server
 and protocol (C) start together; the fork pass (D) starts on A's merge, since balance follows the rules.
```

- **M2 and M3 run in parallel.** M2 owns `scripts/sim/*`, `data/plans/`, `hud.gd`, `resource_strip.gd`,
  `portrait.gd`, `build_controller.gd`, `minimap.gd`, `game.gd`, the view scripts and the art folders. M3 owns
  `server/*`, `scripts/session/`, `scripts/ui/` (except `party_strip.gd`, done in M1), `scenes/hub.tscn`, `main.gd`,
  `project.godot` and the console art. They agree on `content.gd`'s `BUILDERS` field names on M2's first day, which
  is all M3's coverage row reads.
- **v1 ships after M6** (M5 makes it reachable, M6 completes the content). If the user wants real sends in the first
  release, v1 waits for M7 (§10).

---

## 9. Risks and cuts

### 9.1 Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| A cross-platform desync ships (YouTD 2, the one Godot lockstep TD, needed about two years) | medium | the lint; integer units; multi-simulation hash scenarios; every recorded replay becomes a regression scenario; the native-against-web gate; `/stats` counts desyncs; dumps name the first bad tick |
| The sim/view split is larger than it looks: it touches every gameplay script and most scenarios | high | it is all of M1, with a contract commit first; M1a ships alone before any socket; `Game` stays as a facade |
| Catch-up is too slow in the web build | medium | checkpoints every wave or 30 s; range by intervals; `sim_bench` in M4 with a 2,000 ticks-per-second target |
| The felt delay online feels sluggish for far players | low | the adaptive buffer; the immediate ghost; 185 to 300 ms is within what WC3 and Age of Empires players accepted |
| Art budget: 30 tower models, a creep, 4 characters | high | branches reuse base meshes; Builders ship in two pairs (M2, M6); characters need only an idle cycle |
| Four players crowd 141 near-road tiles | medium | measure with the four-player bots; a larger map is a text file |
| A Builder becomes a must-pick through its team tower | medium | strongest applies, never stacks; Help shows who carries; per-Builder solo and team gates |
| Too few players online for a queue | high | codes, links, LAN, caretakers after 60 s, racing the caretaker; High Water scales from 1 |
| Three levels split a thin queue three ways (M8) | high | the level is a party's choice, so friends never wait; strangers get caretakers after 60 s, as before; `/stats` counts matches by mode and level, so a level nobody queues for shows |
| A stray key stacks a wave and loses a match (M8) | medium | in a wave a call needs a second press within 2 s (§5.7), and so does a press in a window's last moments, which may land after its horn and call the next wave at once; with three waves on the road Ready is refused; the duel never stacks |
| A server restart ends running matches | certain | releases from tags only when the protocol changes; the maintenance line; `/health` shows running matches |
| Background browser tabs | certain | 1 MiB buffer, the caretaker after 5 s, catch-up, `TURN_REQUEST` |
| Version skew after a Pages deploy | certain | `rules_hash` as a matchmaking key; `build_seq`; `?v=` on the build files; errors 2 and 17 |
| The Python and GDScript codecs drift | medium | one `protocol.json`; golden transcripts both ways |
| Competitive play later needs hidden information or authority | later | commitments for sends (§1.4); a headless Godot referee on the same turn log for ranked |
| Privacy duties for an EU server | open | Cyberworld's retention rules, no IP written, the policy page; the user decides on legal advice |
| LAN firewalls prompt or block the beacon | medium | the address field; the banner's hints |

### 9.2 Cut from v1, and where each could come back

| Cut | Why | Back in |
|---|---|---|
| Undertow and any sends | Race proves two-team matches first; sends need their own balance gates | M7 (v1.1) |
| Seawall, the Surge | they belong to the Duel | M7 |
| Veiled check, the Kindler, light radii | a fifth check needs a fifth Builder to stay fair, and light drawn as decals for WebGL 2 | after M7 |
| Braided roads, the Twin Hollow, mazing, more maps | one map proves the loop; mazing needs anti-block and invites griefing | later |
| Gold gifts | income is equal by rule | if playtests show stuck players |
| Chat and quick phrases | signals and voice cover friends; free text needs moderation | later, fixed phrases only |
| Boons, Embers, a Holdfast flare, Holdfast upgrades | the fork is v1's one mid-game system | later, one at a time |
| Difficulty choice, overlapping waves | one difficulty keeps the gates at 4 × 4 | M8: Normal, Hard and Very Hard as the party's choice, not a mode (§2.6); stacked waves in High Water and Tide Race (§2.7) |
| Random-pick bonus, drafts, bans | pick before Play is enough for 2 to 4 friends | later modes |
| Ranked, ratings, accounts, friends, progression, cosmetics | no population yet | later; ranked needs the referee |
| Spectating, the replay viewer, a weekly seeded flood | the turn log keeps the door open | after v1 |
| Builder avatars on the map | character art budget | the first candidate after v1 |
| "Host on this computer" in the desktop game | needs the server bundled in desktop exports | after v1 |
| Host migration, ENet, WebRTC, browser LAN | one transport; browser LAN is not portable | later |
| Public lobby browser, commend, AFK vote | codes and open seats cover finding games | later |
| Pausing multiplayer matches | the caretaker covers absences without stalling others | not planned |

---

## 10. Decisions only the user can make

1. **The subdomain** for the official server (proposed `groundhold.saschb2b.com`) and its DNS record.
2. **The Coolify app:** create it in the existing project with access to the Groundhold repository; confirm the
   proxy writes no access log for it.
3. **Server deploy policy:** from tags when the protocol changes (proposed), or auto-deploy on push (every deploy
   ends running matches).
4. **The `ghcr.io` package:** make it public once, by hand, so self-hosters can pull it.
5. **Desktop releases:** GitHub Releases for Windows, Linux and macOS; macOS signing and notarisation (an Apple
   developer account) or unsigned builds with quarantine instructions. LAN play needs desktop builds.
6. **The policy page:** operator name, moderation contact, and whether an imprint is needed (not legal advice).
7. **v1's competitive mode:** ship v1 with Tide Race and Undertow as v1.1 (proposed), or hold v1 until Undertow
   lands.
8. **What "manage Builders" means:** browse, set main and backup, Try, everything unlocked (proposed); or unlocks
   through play; or loadouts per Builder.
9. **Builders on the map:** not in v1 (proposed); an idle avatar after v1.
10. **Party cap and duplicates:** High Water 1 to 4 with duplicates allowed in parties (proposed); the queue avoids
    duplicates among strangers.
11. **A public queue in v1:** only open seats and Find a rival, with caretakers after 60 s (proposed).
12. **Hotkeys:** positional Q W E / A S D for every Builder, replacing today's A C F U S N (proposed).
13. **Names:** settled in [`world.md`](world.md) on 29 October 2026: the game is Groundhold; Tamsin Wick the
    Lamplighter, Edda Greyplume the Lookout, Ottilie Brass the Bellfounder, Sefa Amberwell the Beekeeper; the
    Duskmoth, the Bristlesow and the Hollowtide Crest on Wickhollow; High Water, Tide Race and Undertow. All
    original.
14. **Corked sends in Undertow:** by commitment (proposed, no extra server), or visible as soon as bought (simpler),
    or hidden by a referee (needs a headless Godot on the server).
15. **(M8) The duel and the new rules:** Undertow neither stacks waves nor takes a level (proposed, §1.4: its
    shared windows hold the Drift and the corks, and its rival is its difficulty); or a duel stacks when both
    sides call during the wave, skipping that window's corks for both. Decided on 1 November 2026: Undertow plays
    Normal and never stacks.
16. **(M8) Very Hard's bar:** the plan bots reach wave 12 and end it with at most half their lives, or fall to it
    (proposed: "a close wave 12" for a fixed plan, so a player who adapts can win); or the plan bots must win it.
    Decided on 1 November 2026: a close wave 12, as proposed. Read on the Crest since 2 November 2026 (§2.6, §4.4):
    it dies, or reaches the Holdfast with at most a quarter of its health left; a win keeps at most half the
    lives; and at least half the plan crews win.
17. **(M8) A bottle's candidates:** with one tier a window, every candidate list is the window's three offered
    packs (proposed: keep it, the bluff is "which of three"); or narrow them to two by offering a window's packs at
    different tiers, a new Drift rule with its own gates. Decided on 1 November 2026: three candidates, one tier a
    window.
18. **(M8) How stacked waves overlap:** the stacked horn waits until the Welling has sent the newest wave's last
    creep and the called wave walks one interval behind it (the first version: the road reads as one stream, but a
    skipped window costs nothing while building is allowed in a wave, so stacking every wave was always the best
    play, in High Water and in a race); or the waves truly overlap, the called wave setting out the moment the horn
    sounds, among the current wave's creeps, as sending early did in Element TD. Decided on 2 November 2026: **the
    waves truly overlap**; more creeps at once is the risk, the gold and race time are the reward, and the balance
    gates are measured again (§2.7: the horn on the tick the call is complete, both schedules running, the stake
    over the creeps walking and still to come; `stack_max` 3 and `stake_pm` 400 tuned against §4.4).
19. **(M8) The wave-6 boss at Normal:** should every Builder's plan kill it? A playtester leaked it in every match
    of three sessions, on all 8 sides of 5 matches in the last, and at Normal a sure 5 lives read as a tax.
    Decided on 2 November 2026: **yes, at Normal** ("Yes, at Normal"). Every Builder's plan alone kills it
    (`bot_kills_bristlesow_solo_*`; the Lamplighter's and the Lookout's openings answer it, §2.4). At Hard and Very
    Hard it stays a toll that a strong opening can come near.

---

## Appendix A. Timers

Simulation timers are ticks (60 a second); server timers are milliseconds on the server's clock (the fake sequencer
counts them in turns).

| Timer | Value | Kept by |
|---|---|---|
| Turn | 3 ticks, 50 ms | server |
| Hash | every 60 ticks | clients |
| Checkpoint | the first hash tick of each wave, and every 1,800 ticks | clients and server |
| First window | 900 ticks solo, 1,500 with company | simulation |
| Later windows | 600 ticks solo, 900 with company | simulation |
| Duel surge window | 480 ticks | simulation |
| Duel uncork | from 180 to 1,440 ticks after the horn; reveal deadline 1,500 | simulation |
| Stacked horn (M8) | on the tick every present seat is Ready; the called wave's first creep on that tick, the rest at its own intervals from it, beside what the older waves still send on their own ticks | simulation |
| A call's second press in a wave (M8) | within 2 s of the first; also for a press with less of a window left than the order's lead and one turn | client |
| Slow (Frost Spire) | 120 ticks | simulation |
| Stun immunity | 60 ticks | simulation |
| Caretaker decisions | at each window's start and every 30 ticks | simulation |
| Ping | every 2 s | client |
| Away (caretaker takes the seat) | 5 s of silence | server |
| Connection closed | 15 s of silence | server |
| Party seat held after a drop | 40 s | server |
| Match seat held | until the match ends | server |
| Party countdown | 3 s | server |
| Match Found | 15 s | server |
| Queue: offer caretakers | 60 s | server |
| Loading: minimum, slow, start-without, automatic, ceiling | 4 s, 15 s, 30 s, 45 s, 120 s | server |
| Start delay | 1.5 s | server |
| Empty party code expiry | 15 min | server |
| Race time a life lost | 3,600 ticks (60 s; M6's 600, raised in M8, §1.3) | simulation |
| Race cap | 72,000 ticks (20 min) | simulation |
| Signals | at most 3 per 5 s per player | simulation |

## Appendix B. Files after v1

```
scripts/
  game.gd                 display tables (names, models, icons) and the local seat's facade
  main.gd                 the app: world (one or two hollows), views, boot flags
  sim/                    content.gd, sim_types.gd, sim_match.gd, sim_road.gd, sim_records.gd, sim_waves.gd,
                          sim_effects.gd, sim_targeting.gd, sim_math.gd, sim_rng.gd, sim_codec.gd, caretaker.gd
                          (M7: sim_undertow.gd)
  net/                    protocol.gd, link.gd, address.gd, turn_source.gd, local_sequencer.gd,
                          remote_sequencer.gd, match_client.gd, playout.gd, checkpointing.gd, desync_dump.gd,
                          web_bridge.gd, beacon_listener.gd
  session/                session.gd (autoload), profile.gd, identity.gd
  ui/                     shell.gd, hub_panel.gd, join_panel.gd, builders_screen.gd, match_found.gd,
                          loading_screen.gd, results_panel.gd, coverage_row.gd, name_prompt.gd, party_strip.gd,
                          connection_overlay.gd
  creep.gd tower.gd projectile.gd build_controller.gd hud.gd fx.gd ...   views and input, as today
scenes/   main.tscn (the match), hub.tscn (the boot scene)
data/     hollow.txt, plans/*.json, net.json, build.json (written by CI)
shared/net/   protocol.json, README.md, transcripts/*.bin
server/   main.py, build.py, release.py, smoke.py, notices.py, Dockerfile, README.md, .gdignore,
          groundhold_server/ (websocket, protocol, app, match, catchup, party, codes, lobby, queue, identity, holds,
          beacon, retention, stats, backup, admin, cli, hosting), tests/
deploy/   coolify/compose.yaml, coolify/server.ini, selfhost/compose.yaml, selfhost/.env.example, .gdignore
tests/    bot.gd, sim/, net/ (fake_sequencer.gd, fake_link.gd, loopback_match.tscn), scenarios/, balance/
tools/    media/, net/smoke.py, net/shaper.py, gen_balance_scenarios.py
```

## Appendix C. Godot 4.7.1 APIs this design relies on

Each was looked up with `godot-agent api show` against the installed engine.

| API | What was checked |
|---|---|
| `WebSocketPeer` | `connect_to_url(url, tls_client_options)`, `poll()`, `get_ready_state()`, `put_packet()` / `send(bytes, WRITE_MODE_BINARY)`, `get_packet()`, `was_string_packet()`, `get_selected_protocol()`, `get_current_outbound_buffered_amount()`; properties `supported_protocols`, `inbound_buffer_size` (default 65,535), `outbound_buffer_size`, `max_queued_packets` (4,096); `handshake_headers` is not supported in web exports; `heartbeat_interval` has no effect in web exports |
| `TLSOptions.client()` | uses the default CA list when no chain is given; on the web, verification always uses the browser's CA list |
| `ProjectSettings.network/tls/certificate_bundle_override` | empty means Godot's default Mozilla bundle |
| `HashingContext` | `start(HASH_SHA256)`, `update()`, `finish()` |
| `HMACContext` | `start(hash_type, key)`, `update()`, `finish()` |
| `Crypto.generate_random_bytes(size)` | the identity key |
| `StreamPeerBuffer`, `StreamPeer.big_endian`, `put_u32`, `put_64`, `get_u64` | big-endian codec |
| `PacketPeerUDP` | `bind(port, bind_address, recv_buf_size)`, `get_packet_ip()`, `set_broadcast_enabled()` |
| `JavaScriptBridge` | `eval()`, `get_interface()`, `create_callback()` |
| `OS.get_cmdline_user_args()`, `OS.has_feature()`, `OS.create_process()` | boot flags; the later "Host on this computer" |
| `DisplayServer.window_request_attention()` | Match Found on desktop |
| `Engine.get_physics_interpolation_fraction()`, `Engine.max_physics_steps_per_frame` (default 8), `Node.reset_physics_interpolation()` | view interpolation and catch-up jumps |
| `ResourceLoader.load_threaded_request()` / `load_threaded_get_status(path, progress)` | real loading progress |
| `Array.sort_custom()` | documented as not stable |
| `Dictionary` | documented to preserve insertion order |
| `int` | documented as signed 64-bit, wrapping on overflow |
