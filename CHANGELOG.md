# Changelog

## 0.9.0 · 2026-11-02

Stacked waves and harder levels (M8). In High Water and Tide Race the horn can call the next wave while one still
runs, up to three on the road at once, for the skipped window's gold and more for the lives at stake; and a party's
leader picks Normal, Hard or Very Hard, where Hard is a close win at wave 12 and Very Hard closer still. Every fork
now has its own job, a life lost in Tide Race costs a minute, and Undertow's sends are a real threat: each pack
breaks through the Builders weak to its check, and the caretaker sends what your defence has shown. With it come the
fixes from three sessions of a persona playtester, a Warcraft III tower defense veteran, among them a duel's Ready
that never takes your corking window and a wave-6 boss that every Builder can stop at Normal.

- Undertow's sends are a threat now, not a tax: a sent creep comes a quarter stronger than the wave's own (the Drift
  tray says so), and the packs are bigger (see the next entry). A tier I cork costs 45 gold and a tier III pack adds
  +12 a wave to your stipend, so each tier pays its price back about once from its first window and a pack your
  rival holds is no longer a pure loss. The caretaker sends what your defence has shown, all of it what you could
  see too: the check it has let through most, a Moth Cloud when your towers hardly reach the sky, else the pack
  your towers take longest to kill; never anything from your corked bottles. About half the sent packs now take a
  life, where one in four did.
- Every Undertow pack is a threat to the Builders weak to its check, not only the Moth Cloud: in the third Veteran
  playtest Moth Clouds broke through a Lamplighter 6 times in 7 and no other pack ever did, and measured over every
  Builder the Gourd Rush took a life from nobody. The Gourd Rush now sends 6, 14 or 20 Gourdlings, each half again
  as strong as the wave's own and bunched a quarter second apart, so it swamps a defence that strikes one creep at a
  time (the Lookout's, the Bellfounder's) while a splash still answers it; the Scuttle 8, 17 or 28 Scuttlers, two
  fifths stronger; the Thorn Herd 3, 5 or 9 Thornbacks walking a second apart, so a splash finds one at a time and
  only hits that go through armour hold it; the Moth Cloud 4, 5 or 7 Duskmoths. Against the caretaker each pack
  now takes a life from the two Builders weak to it 44% to 52% of the time (the Moth Cloud 83%) and from those that
  cover it about a fifth of the time or less; the Drift tray says each pack's own strength. A Lamplighter who has
  forked her Iron Mortar still holds a Thorn Herd, as one with Skyward Lofts holds a tier II Moth Cloud: a patch you
  can see on the board is a defence to read.
- Hard and Very Hard on the wire (M8): a party has a level, Normal at first, which its leader picks as the mode;
  changing it clears every Ready and stops a countdown, a member sees the party's level and cannot change it, and
  the party keeps its level when the mode changes (a duel always plays Normal). A party you make starts at your
  own level, which your profile keeps beside the mode, and every match the hub starts plays the level it shows:
  Play, Try and Race the caretaker. The queue only puts parties of one level together, so a Hard party never meets
  strangers at Normal; the caretakers it offers after a minute play at the party's level, and so does a match taken
  back after a lost link or a restarted game. This is protocol version 2: a game and a server of different versions
  say which one needs updating (a 0.7 game hears "A newer version is out"). `server/main.py --dev-match
  high_water:2:hard` plays a dev match at a level, `/stats` counts the matches at Hard and Very Hard apart, a desync
  report names the level, and `smoke.py --flow --difficulty hard` plays the loop at Hard against the real server.
- The results' Towers column counts the towers standing at the end and how many of them stand forked, "9 (4
  forked)". It counted every fork ever made, a sold tower's too, so a player who sold and forked again all match
  read "9 (18 forked)".
- A fork branch that patches a weak check says what "passable" means by what one tower of it holds alone, on the
  match's card and the Builders screen's kit plate alike: "Lifts Armored from weak to passable: one alone holds the
  early armored waves; later ones need more". The Sky Toll says it holds them only inside a bend (outside one, a
  lone Sky Toll takes none of wave 5's Duskmoths, at any level), and the Rime Spire and the Drowsy Clay Hive, which
  slow, say that alone they hold no wave.
- Tower and creep numbers show at most two decimals and none they do not need, on the card's tooltips, the plates
  and the Builders screen alike: the Queen's Guard's cooldown reads 1.43s, not 1.43333333333333s, a fork's damage
  "18 to 54", not "18.0 to 54.0", and a Thornback's speed 0.85, no longer rounded to 0.8.
- Waves stack (M8, the rules; the screens follow): in High Water and Tide Race, Ready during a wave calls the next
  wave at once, and the waves truly overlap: the called wave sets out the moment the horn sounds, its creeps walking
  in among the current wave's while that one is still sending its own, and the window between the two is skipped.
  Call early in a wave and both whole waves come at you together; call once the wave has set out and the new one
  walks in behind it. At most three waves walk the road at once, every player present must say Ready (the horn
  sounds as the last Ready lands), and a call is refused while three waves walk, during the last wave, and while a
  partner is being handed back from the caretaker. A call pays each player the whole window it skips (10 gold
  alone, 15 with company) and 2 gold for every 5 lives the waves on the road could still take, counting the creeps
  still to come, so an early call pays the most: wave 2 called as wave 1 begins pays 14, wave 3 called right after
  it 21. Each creep keeps its own wave's health. Waves still clear in order, each paying its own clear bonus; when
  the last wave on the road clears, the next window opens as usual, and a Ready said during a wave whose call never
  sounded stands into it. In Tide Race each hollow stacks on its own clock, and a crew that falls with two or three
  waves on its road fell on the oldest. Undertow and classic never stack. Stacking every wave is a gamble now: a
  Builder alone that does it loses at least 5 lives more than one calling only its good waves, or falls, and in a
  race it wins only where its defence holds three waves at once.
- The caretaker stacks in Tide Race the waves its Builder's plan lists (the Lamplighter's 2 and 3, so her first
  three waves set out together; the Lookout's 5, the Bellfounder's 4, the Beekeeper's 2), each early in the wave
  before it, once its builds are paid, at Normal only; a crew of two caretakers stacks every wave either of their plans lists.
  Beside a player in High Water it never calls a wave.
- Hard and Very Hard (M8, the rules; the hub's words follow): High Water and Tide Race take a level, both crews of
  a race the same. Hard gives 15 lives, creeps a tenth more health, and the Bristlesow and the Hollowtide Crest
  half again as much and 1 more armour; Very Hard 10 lives, creeps 15% more health, and the bosses 55% more health
  and 1 more armour, so the Crest's toll is every life left and wave 12 is close: the caretaker playing each
  Builder's plan alone kills the Crest 4 to 14 s before it would reach the Holdfast and wins on 1 to 5 lives, and
  the Bellfounder with the Beekeeper leaves it a sliver of health and loses. At twice the health and 2 more armour,
  as first planned, the Bristlesow was a wall at wave 6 and no Builder alone won. Gold, waves, windows, bounties
  and tolls are Normal's at every level. Undertow and classic always play Normal.
- Calling a wave early on screen (M8): during a wave of High Water or Tide Race the horn (D, N, Space or a click)
  calls the next wave, which sets out at once among the creeps on the road. A call takes a second press within two
  seconds ("Call wave 8 now? Press again"), so a stray key never sends a wave, and one press takes it back; so does a
  press in a build window's last moments, which would land after the window's horn (online the question comes as
  early as your connection's round trip needs): one press there calls nothing, never two waves at once, and the
  second calls the wave after the window's once its horn has sounded. A Ready names the wave it calls, so one that
  arrives too late for its horn is dropped, beside a partner too, instead of standing as a call for the next wave
  and carrying into the window after it. The horn's tooltip names the wave it would call, its checks and what it pays now ("+10 for the window, +4 for
  the lives on the road"), or why it cannot: three waves on the road, the last wave, a partner being handed back; in a
  duel waves never stack, and its tooltip says so. Its cost shows what a call pays. Alone the wave sets out as the call
  lands, and so it does beside caretakers only (offline company, or a teammate away or gone), which the tooltip
  says; with another player present the call waits for every partner, and the strip says who has called ("Ready 1/2"), as the party
  strip's marks do (a rival caretaker's mark lights only once it has called). With waves on the road together the strip
  says "Waves 7–8/12" or "Waves 7–9/12" and counts every wave's creeps, the waves to come start at the oldest, the
  call's banner says what it paid ("Wave 8 called early · +14 gold"), and each wave clears on its own banner with its
  own bonus and the lives its own creeps took; waves that clear together share one ("Waves 1–2 cleared · 28 lives
  lost · +22 gold"). In Tide Race the rival line names the waves on the rival's road. The results count a kill or a
  leak on its creep's own wave, and so do the clear banners, also for creeps that set out and were gone while the
  game caught up after a hidden tab or a lost link. A creep you select names its own wave, not the newest on the
  road, and a race decided while a crew still had stacked waves on its road says so on the results ("on waves
  2–3 at 0:08").
- Picking Hard and Very Hard in the hub (M8): Normal · Hard · Very Hard stand beside the mode line, the party's
  level lit; the leader clicks one, a member sees it, and each word's tooltip says what it changes ("Hard: creeps
  have 10% more health, the bosses 50% more and 1 more armour; 15 lives"). In Undertow they grey: a duel is played
  at Normal. A level other than Normal is named wherever the mode is: the mode line, Match Found, the loading title,
  the results (the lives counted out of the level's own: "4 of 10 lives left"), the Esc menu and Try's tooltip.
  Play, Try and Race the caretaker offline now play the level the hub shows (a Try from Undertow, where the hub shows
  none, plays Normal), and the leader's words pick only while the party forms: queued or playing they stand fixed.
- The hub's Normal · Hard · Very Hard stand still when you click one: the mode line beside them keeps the width of
  its longest wording and each word the width it has lit, so naming the level in the line no longer slides the words
  out from under the pointer (a click on Hard used to leave it on Normal, where a second click undid the pick).
- A rival's corked bottle shows what it may hold (M8): under each bottle in the Drift tray, the packs its window
  offered at its tier, small and dim, never which one; its tooltip names them with their counts ("It holds one of:
  14 Gourdlings (Gourd Rush), 5 Thornbacks (Thorn Herd) or 5 Duskmoths (Moth Cloud)"), and the duel bar's rival
  row ends with their checks ("corked II: Swarm, Armored or Winged"), so you know which defence to hold gold for.
- Every fork is a choice (M8, the fork pass): each branch now does a quarter more than its sibling at its own job,
  and no branch is ahead at both, measured on a bench of one tower against held creeps, lines of them and a
  teammate's battery, at the creep health of every level and party size and on every cell the caretakers build
  the tower on. The Beekeeper's Apiary forks part for good: the Royal Apiary hits 24, and 56.4 to a flier (it was
  34 and 51), so it takes a late Duskmoth in two bolts and is her tower for the sky; the Queen's Guard hits 54
  every 1.43 s, ignores 4 armour, gets no bonus against fliers and aims at the creep with the most health in its
  reach (it was 50 every 1.2 s, ignoring 3). Her Clay Hives part too: the Great Clay Hive stings for 5 (was 4), the
  Drowsy Clay Hive for 1.5 (was 3) and slows 35% (was 25%). Her Long Hum hastens by 18% (was 15%). The
  Lamplighter's Iron Mortar hits 52 (was 45); her Arrow, Cannon and Frost Spire and their first branches, which the
  classic game plays, are unchanged. The Lookout's Kestrel Flock strikes bounce on to three more creeps (was two)
  and her Twin Gaze marks for +25% (was +20%). The Bellfounder's Clapper Tower strikes for 35 (was 30), her Great
  Clapper for 80 every 1.4 s (was 72 every 1.6 s), her Ringing Clapper for 32 over 1.2 tiles (was 24 over 1.0),
  her Sky Toll slows fliers by a third (was half) and does 160% more to them (23.4, was 80% and 16.2), and her Long
  Chime cracks 3 armour within 4 tiles (was 2 within 3.2).
- Hard and Very Hard for every Builder alone: the Bellfounder's Clapper Tower takes a Gourdling of the second wave
  in one strike at every level, and the caretaker's Lookout forks her first Hawk Roost into a Kestrel Flock before
  she builds the second and stands her first Siege Perch before the Owl's Eye; the Bellfounder builds her fourth
  Clapper before her third Toll Tower. Both now win Hard and Very Hard alone. A duel's
  caretaker Lookout keeps her old order. The caretaker's Beekeeper forks her first Queen's Guard before her first
  Royal Apiary, so the Thornbacks of wave 4 meet a tower made for armour.
- At Normal the Bristlesow, wave 6's boss, dies to every Builder's plan alone. It had walked through the
  Lamplighter's and the Lookout's for 5 lives in every match. The caretaker's Lamplighter now forks an Iron Mortar
  before her third arrow, and her Lookout builds a Siege Perch before her second Kestrel Flock. The Lamplighter
  kills it 6 s before it would reach the Holdfast, the Lookout 20 s before. The boss itself is unchanged. At Hard and
  Very Hard it still takes 5 lives, but these openings now deal three fifths to three quarters of its health,
  where they dealt about a third. In a duel both caretakers keep their old order.
- Tide Race: a life lost now adds a minute to your race time (it was 10 s). With waves that truly overlap, a crew
  that stacked every wave saved three or four minutes, and 10 s a life paid back any leak; now stacking every wave
  wins a race only for a crew whose defence holds three waves at once, and a crew that leaks to it loses to the
  same crew calling the waves its plans list. The rival line and the results show the lives' part in seconds
  ("6:12 +120 s").
- 0.8.0's playtest fixes on M8's screens: the waves to come give each creep's health and armour at the level you
  play (a boss's with the level's extra armour), from the oldest wave on the road, each wave on it with its own
  creeps' health; waves cleared together share one banner that still names the Tithe and the stipend they paid;
  your own race clock and the hub's race rule count a minute a life ("each life lost adds 60 s"), the hub's mode line
  ending with "+60 s a life lost" beside the level's words and giving the whole rule when hovered; and in a duel,
  hovering the rival's corked bottles at the end of the duel bar explains them as the Drift tray does, not the
  Seawall beside them.
- The server's `GET /health` names the release it runs and the commit it was built from (`"version": "0.8.0",
  "build": "ef83fd29c820"`), so a deploy can be checked from outside and a self-host knows its release; nothing
  else about the build or the host is told. The image's build context lets in `project.godot` for its version line,
  and the image takes the commit as the build argument `SOURCE_COMMIT`.

## 0.8.0 · 2026-11-02

Undertow, the duel (M7). Two players, each on their own hollow under one clock, cork packs from the Drift and
uncork them on each other's road; the Seawall holds a Holdfast in trouble, the Surge settles a duel both survive,
and the caretaker duels anyone without a rival. With it come the fixes from the first playtests by a persona
playtester, a Warcraft III tower defense veteran: a match can no longer end on a stray click, and the waves to
come show every creep's health and armour, a boss's checks and the duel's Surge.

- Undertow's rules (M7): two players, each on their own hollow, build and start every wave together under one clock.
  From the second window the Drift brings three of the four packs, the same for both, never leaving out the same one
  twice running. Cork one (two from window 9): the gold goes at once and the rival sees only a bottle and its price,
  the pack hidden by a commitment until you uncork it, from 3 s into the next wave; a bottle not uncorked by 25 s
  fizzles, and a wave a rival's bottle is corked for is not over until the pack has come or the bottle has fizzled,
  even with the road empty. Uncorked packs walk the rival's road and add a stipend paid at every wave clear; one that
  breaks through takes its lives and pays you twice its bounty, one the rival kills pays the rival. Every 4 lives
  lost charge the Seawall (up to 2), which stuns and wounds every creep near the Holdfast. A Holdfast that falls
  loses at once; both standing after wave 12, the Surge repeats waves 9 to 11 harder, with short windows, half-price
  corks and stipends that no longer grow, and then more lives wins, then more breach dealt.
- The caretaker duels: it corks the pack its rival's towers handle worst while its corks stay within a fifth of
  what it holds, uncorks them itself, and raises the Seawall when creeps crowd its Holdfast. The duel's balance
  gates hold its play and four others to the design's matrix.
- The duel on screen (M7, Undertow). In a duel the Drift tray stands over the minimap: the three packs the window
  offers (Gourd Rush, Scuttle, Thorn Herd and Moth Cloud on Wickhollow), each with the tier's price, corked with a
  click or keys 1 to 3; your corked bottles, each with its pack and, during its wave, the seconds until it uncorks
  by itself 24 s after the horn; and your rival's bottles, which show only their tier. A window's packs show once
  the window is open for both hollows; until your rival's wave is over the tray and the countdown say so. Space
  during a duel's wave uncorks your next bottle (from 3 s after the horn), even once your own hollow has cleared,
  and never says Ready while the wave still runs on either hollow; a click uncorks the one you pick, in the same
  moments as Space, and F bursts a Seawall round your Holdfast. A bottle whose salt this game no longer holds says
  so and fizzles, and a fizzle, yours or your rival's, is told; a bottle the caretaker corked for you while you were
  away shows its pack and is uncorked by the caretaker, and never takes the salt of a cork of yours the link lost.
  A wave that waits on your rival's corked bottle with your road empty says so on the strip. In the Surge the strip
  says "Surge 2/3" and the banner which wave it repeats; the wave list shows the Surge's waves as S1 to S3, and a
  clear or a fall in the Surge is told by the Surge's wave, not as wave 14. The duel bar under the resource strip
  shows both sides' lives, the breach each has dealt, their
  stipends and their Seawall charges. A corked pack's salt is 8 random bytes that stay on your machine until you
  uncork it, through a lost link, a resync, or a game closed mid-duel and started again; a cork, an uncorking or a
  Seawall lost with the link never holds up the next one. Uncorked creeps carry a small glinting bottle in the sender's colour,
  a pack wells up at the Welling it sets out from, a Seawall sends a see-through ring of surf in the hollow's water,
  broken foam along its crest, out from the Holdfast to its reach, lying down where it meets the hollow's cliffs and
  gone in about a second, and the results say "The Tide
  Took Your Rival", "The Tide Took You" or "Even Tide" with the rule that decided it and each side's breach dealt.
  New art and sounds: the tray and its sockets, the corked bottle, the Seawall, four pack icons, and the cork, the
  uncorking, a breach and the Seawall.
- Undertow around the match (M7): the server's queue finds a rival for a duel, one player a side, and each keeps
  their own Builder, since a clash never crosses the sides; after a minute in the queue the duellist may duel the
  caretaker, a rival of their own Builder, and a duel's result names each side's outcome. On the hub, Undertow's
  button lights once the build has the duel's rules; a party of one duels the caretaker offline or finds a rival
  online, a party of two is both sides and starts, and no row moves onto a duel's side already taken (a race's rows
  still move freely). Match Found says "Undertow · 1v1", the queue's offer of caretakers is said in each mode's
  words, and Play again queues a duellist who came alone again. `smoke.py --mode undertow` plays a duel as a dev
  match, and `smoke.py --flow --queue --mode undertow` has two games find each other through the real server's
  queue; the `m7_duel` transcript records the server's side.
- The duel's orders across the real wire (M7): the plan bot (`--bot`) duels as the caretaker would, through the
  game's own corking, uncorking and Seawall, so each CORK carries the game's commitment to a salt of its own and
  each UNCORK reveals it. `smoke.py --mode undertow` now checks from both games that each corked and uncorked a
  pack, that an uncorked pack walked the rival's road and that both ran it all alike; the queue's duel smoke plays
  the bots' duel to its end, one outcome a side. The server's tests carry CORK, UNCORK and SEAWALL through its
  turns with every 32-bit half as sent.
- A creep you selected stops being the selection the moment it is killed or gets through to the Holdfast: the
  plate goes back to the Holdfast instead of showing a creep that is gone.
- Leave to hub and Restart in a match's Esc menu ask first ("Leave the match?", "Restart the match?"), offline and
  online, with Stay as the default (Enter, Space; Esc goes back to the menu). The answer that ends the match never
  stands where Restart or Leave to hub stood, so one stray click, or two, no longer ends a match.
- On the Builders screen an open tower card follows the Builder shown: with the pointer on W, pressing 2 to 4 shows
  that Builder's own tower on W instead of keeping the first Builder's card open.
- A wave's clear banner says what got through cost: "Wave 6 cleared · 5 lives lost · +20 gold". A wave that
  cost nothing still says "Wave 6 cleared · +20 gold".
- The waves to come (hover the wave) show a boss's own checks after "boss" on its row: the Bristlesow's and the
  Hollowtide Crest's Armored glyph, and no Winged glyph, since neither flies.
- The results' line for the wave a player killed most in says so: "Most kills in wave 11" instead of "Held wave
  11".
- A fork branch that patches a weak check says what "passable" means, on the match's card and the Builders
  screen's kit plate alike: "Lifts Swift from weak to passable: enough to hold it alone".
- The duel after its review (M7): a cork made in the same moment as the horn, at a fast-forward or a networked game
  running several ticks at once, keeps its salt, so the bottle opens at 24 s instead of showing "lost" and fizzling.
  In the Surge's last wave a player whose hollow has cleared can still uncork a bottle the rival's wave waits on
  (Space, a click, or by itself at 24 s), which was refused as "The match is over"; every other order stays shut.
  A networked game running behind the server's turns sends its own uncorking early by as much, so the bottle still
  opens at about 24 s instead of fizzling quietly past 25 s. The caretaker no longer builds while its hollow waits
  for the rival's wave to end, so when the window opens it still has the gold to cork before it builds.
  Coming back from a lost link or a resync, the duel's corks, uncorkings, fizzles, breaches and Seawalls since the
  checkpoint no longer replay their sounds and notices all at once, and the seconds the tray and the notices name
  follow the duel's rules. After a resync whose world numbers the bottles otherwise, each corked pack's salt still
  finds its own bottle, so none shows "lost" or fizzles for it.
- In a duel the waves to come (hover the wave) go on into the Surge from the first window: after wave 12 a line
  says when it is played ("The Surge, if both Holdfasts stand after wave 12: health +35%"), then S1 to S3, each
  with the checks and creeps of the wave it repeats and "wave 9 again". The list no longer stands empty while your
  hollow has cleared wave 12 and your rival's is still running.
- The waves to come give each creep's health at that wave and its armour beside its count ("×4 140 hp · armour 4",
  the Bristlesow "boss 1125 hp · armour 6"), grown for the wave and scaled for the seats on your hollow as the
  creep will spawn, so a boss can be planned for before it walks in; a duel's Surge rows show the Surge's extra
  health. Classic, which has no armour, shows health only.
- In a duel, hovering the Seawall on the duel bar explains it: F during a wave bursts surf round your Holdfast,
  stunning every creep within 3 tiles for 2 s and taking a quarter of its health (a boss loses 8% and is slowed
  50%); a charge comes for every 4 lives lost, at most 2, and the next burst may follow 15 s after the last. It also
  says where yours stands: how many more lives lost earn a charge, a charge ready, or, after a burst, that the
  seconds beside F count down to when the next may burst. Your rival's Seawall says its charges.
- In a duel, once your hollow has cleared its wave and your rival's is still running, D, N, Space and the card's
  horn no longer say Ready: they say "The window opens once both waves are over", and the card's Ready greys with
  the same words. A Ready said then sounded the horn the moment your rival cleared, so your window to cork and
  build never came. The tray's empty pack slots say the packs come when the window opens, once both waves are over.
  A cork pressed in the window's last instant that the horn beats now says "The horn sounded before your cork went
  in" instead of "Not now" (likewise an uncorking or a Seawall the wave's end beats).
- Tide Race shows your own race clock: the line under the resource strip starts with "You 6:10 +10 s", your time
  so far and the 10 s each life lost adds, before the rival's. Where Tide Race is chosen, its button's tooltip says
  how a race is won ("The lower time to clear wave 12 wins; each life lost adds 10 s") and the hub's mode line
  says it in short ("fastest clear of wave 12 wins, +10 s a life lost").
- A wave's clear banner names what else the clear paid you: the Beekeeper's Hive Tithe ("Wave 1 cleared · +10
  gold · Tithe +4") and, in a duel, the stipend your uncorked packs earn ("Stipend +4"). Before, the banner gave
  only the bonus while your gold rose by more.

## 0.7.0 · 2026-11-01

The full roster, Tide Race and the queue (M6). Ottilie Brass, the Bellfounder, and Sefa Amberwell, the Beekeeper,
join Tamsin and Edda; Tide Race sets two crews racing on Wickhollow and its reflection; and the official server finds
players and rivals for a party that asks.

- The rules of the Bellfounder and the Beekeeper (M6). The Toll Tower rings every 2.4 s and strikes every
  ground creep in its reach at once, stunning each for 0.6 s; a stunned creep is then immune for a second, so
  stuns never chain, and a boss is slowed 50% for the stun's length instead. Its Sky Toll reaches the sky and
  slows fliers. The Clay Hive's bee cloud stings every creep near the one it aims at, fliers too. The Chime
  Post takes armour off every creep in its reach for every tower's hits, and the Hive Hum makes every tower
  beside it fire faster, whoever built it; of two cracks or two hums the stronger counts. A hit on a creep
  someone else stunned or cracked, or from a tower someone else's hum hastens, is that player's Help. Bronze
  Hand: the Bellfounder's hits ignore 2 armour. Hive Tithe: each Clay Hive and Hive Hum of the Beekeeper's pays
  her 2 gold at every wave clear, at most 12.
- Tide Race in the simulation: two teams of one or two, each on its own copy of the hollow with its own clock,
  the same waves on both. The race is decided as soon as the outcome is certain: the lower race time (the clear
  of wave 12 plus 10 s for every life lost), or the rival's fall once you have cleared the wave it fell on, or
  at the 20-minute cap the waves cleared, then the lives. The caretaker races too: it calls each wave once its
  builds for the window are done.
- The caretaker plays the Bellfounder and the Beekeeper from their own plans, and the balance gates now cover
  every Builder alone, three and four players, the Bellfounder with the Beekeeper, the Lamplighter and the Lookout
  each beside each of them, and the race (a mirror draws; a bot that calls every wave beats one that waits). Tuned against them: the Toll Tower's pulse deals 8, not 6,
  and the Sky Toll slows a flier for 2 s, not 1, and deals it 80% more; the Queen's Guard stings for 50, not
  40, and ignores 3 armour, so the Beekeeper's fork for Armored beats her Royal Apiary against armour.
- Art for the Bellfounder and the Beekeeper (M6). Ottilie Brass, a stout bell-caster in a Delft-blue smock, a
  leather apron and a teal oilskin sou'wester, holds up a bronze hand bell, her small hammer on a chain at her
  belt; Sefa Amberwell, in a terracotta tunic under a veiled straw sun hat, holds a bee smoker with its smoke
  rising. Each has a figure, a portrait bust, a glyph and an emblem. Their eighteen towers have models and
  command icons: the Clapper Tower, Toll Tower and Chime Post in Brackwater brick and bronze on a turf dike, and
  the Clay Hive, Apiary and Hive Hum on the stepped red rock of Thousandwell. Each branch changes its base's
  crown, roof or head. The Apiary has a bee to fire, and there are six new sounds: the toll, the clapper's clap,
  the chime, the bees, Match Found and the countdown's tick. The views wire them in later in M6.
- `art_src/models/towers/m6_kits.py` writes the eighteen tower recipes, their icon-only variants and the two
  emblems' props from shared pieces, so every branch stays on its base; `--check` says whether the recipes and the
  models built from them are current. `art_src/sfx/sfx.py` makes the sounds the kit's one-oscillator
  synthesizer cannot: bells built from inharmonic partials over a strike, and a swarm of bees.
  `art_m6_painted` checks every M6 model, icon, Builder and sound, and holds each M6 model to its triangle budget,
  size, materials and palette in `asset_style.json`.
- The queue (M6): on a server the leader of a party turns open seats on, and **Find players** fills them with
  players from the queue, up to four; in Tide Race a team of one or two presses **Find a rival**. Parties are
  matched only with players of the same mode and the same version, earliest first. While queued the hub shows a
  pill with the time ("Finding players 0:42"), which follows into the Builders screen, and the leader's button
  cancels. When a match is found, everyone gets 15 s to accept on the Match Found plate; if someone declines or
  the time runs out, the match is off, the party that did not accept goes back to the hub and everyone else keeps
  their place at the front of the queue. Strangers on one team never get the same Builder: whoever queued first
  keeps their main, the next takes their backup, and the server picks a free one for anyone still clashing (Tide
  Race's rival teams play their own hollows and keep their mains). After a minute queued the leader may **Start
  with caretakers** (Tide Race: **Race the caretaker**), which fills the free seats with caretakers whose
  Builders cover what the party lacks, or sets a caretaker team with the same Builders against it. After a match
  each party is on its own results again, and a player who came alone through the queue to a match of strangers
  is queued again by Play again (a start with caretakers comes back to the party, as after Start). While the
  party is queued only the leader can leave the queue, so a member's Try waits until the party is out of it. Open
  seats belong to High Water: switching the party to Tide Race turns them off.
- A Tide Race party shows its two teams in the party panel, and the leader clicks a row to move a player to the
  other team. Offline, a party of one in Tide Race races the caretaker once the build has the race's rules.
- The server's queue (`server/groundhold_server/queue.py`) is documented in `shared/net/README.md` (The queue)
  and recorded in the golden transcripts `m6_queue`, `m6_caretakers` and `m6_race`. `tools/net/smoke.py --mode
  tide_race` plays a dev match of two teams and checks that the teams' outcomes answer each other (on a build
  without the race's rules it says so first). `tools/net/smoke.py --flow --queue` plays the queue end to end
  against the real server: four games, each a party of one, find each other, accept Match Found, play a High
  Water match with the Builders the server unclashed, and are queued again by Play again.
- The Bellfounder and the Beekeeper stand on the board as themselves (M6's race views, first part). Each of their
  eighteen tower forms has its view: the Clapper Tower's strike lands as a bronze clap on its creep, the Toll
  Tower's bell rings a wave out to its reach, a Chime Post's cracked creeps shimmer bronze, a Clay Hive's bees
  swarm over the creep its cloud stings, the Apiary fires bees, and a tower a Hive Hum hastens glows at its foot.
  Until their models and sounds are made, the towers stand as grey stand-ins and play silent, and the hub fields
  both Builders as themselves rather than as a Lamplighter.
- A Tide Race shows both hollows: Wickhollow and its copy side by side beyond a wooded ridge, every tower and
  creep on its own hollow. The camera starts over yours, Home frames it and V shows your rival's and back; the
  minimap shows both with your rival's veiled; a tower placed or a signal given on the rival's hollow is refused
  with "That is your rival's hollow".
- A selected tower of the new kits shows its stun, cloud, crack or haste beside its range, and a cracked creep
  says by how much.
- Tide Race on screen (M6's race views). Play in Tide Race races the caretaker: both hollows stand from the
  start, the mirror builds on its own and calls its own waves. Under the resource strip a second line follows
  the rival: "Rival · Wave 7 · 18 lives · 6:12 +20 s", its wave, its lives and its race clock with 10 s for each
  life lost; once its Holdfast goes under it says what wins: "Your rival fell on wave 9. Clear wave 9 to win".
  Banners mark a crew clearing wave 12 (the time to beat) or falling, and the end waits for the race's decision,
  not for your own hollow. The party strip shows both teams, yours first. The loading screen lays a race out in
  two rows, team A above team B, a gilt rule between them and each team's coverage under its cards. The results
  say "You Outran the Tide", "Your Rival Outran the Tide" or "Two Crews, One Time", the rule that decided it in
  one line ("You cleared wave 12 first", "Your rival fell on wave 9", "Twenty minutes: more waves cleared"), and
  one block per crew with its race time, its lives along its waves and its players.
- Fixed: an offline race was judged by your own hollow, so a race won by the rival's fall said lost, a race lost
  on time with your hollow cleared said won, a draw was never shown and the 20-minute cap was ignored. The
  results now take the outcome the simulation decided, offline and online. An offline match also stops where it
  was decided, so its results show the decided race.
- The Bellfounder's and the Beekeeper's tooltips follow the tuned numbers: the Sky Toll slows fliers by half for
  2 s and strikes them 80% harder, the Queen's Guard's slower, far heavier stings pierce armour, the Apiary shows
  its +50% against fliers, and an aura shows no cooldown. A Bellfounder's fork no longer reads as losing her
  Bronze Hand's pierce. Their towers' sounds now sit level with the others' (they played 3 to 8 dB quieter), and
  every muzzle is measured on its model: the bee leaves the Apiary from its top ring of holes, and the Sky Toll's
  ring bursts from its bell high under the arch.
- Fixed: a race won on the same tick by fewer lives lost said "You cleared wave 12 first"; it now says "Fewer
  lives lost: your race time is the lower". A drawn race no longer repeats its title as its rule but says which
  rule tied: "Both cleared wave 12 in the same race time", "Both fell on wave 6 with as many of its creeps
  killed" or "Twenty minutes: as many waves cleared and lives kept".
- Fixed: once a race was decided while your own hollow was still in a window or a wave, towers could still be
  placed and the horn called under the end plate until the server ended the match. The match is over for you
  as soon as the race is decided: the card greys and an order says "The match is over".
- The command card's tooltip counts the Bellfounder's Bronze Hand (Pierce 2), as the build description beside
  it does, and shows a tower's own pierce; an aura, which strikes nothing, shows none. A selected Sky Toll shows
  its slow of fliers beside its +80% against them.

## 0.6.1 · 2026-11-01

- Fixed: a party's link opened by a returning player on a slow computer could leave them offline. The game
  opens its connection while its first frames are still loading, and the server closed any connection whose
  `HELLO` came more than 5 s after it connected. The 5 s now cover only the connection's upgrade; `HELLO` has
  30 s after it (`hello_ms`), and a connection that never says it shows as `hello_timeout` in the server's
  event log instead of vanishing without a word.
- Fixed: back from a hidden tab, the overlay could say "Catching up 100%" for half a minute. Its bar counted
  only the turns that were there when the catch-up began, while the server kept sealing new ones; it now counts
  those too, and fills as the catch-up ends.
- Fixed: a game whose link dropped while the match loaded gave up and went offline, and the match started
  without it. It now reconnects as it does mid-match: the server takes its seat back while the match loads,
  the game says it has loaded again, and if the match started without it meanwhile it catches up from there.
- The server's log no longer gives every refused request its own line: requests that never became a game's
  socket (a wrong path, no WebSocket upgrade, which on a public port is mostly scanners) are summed into one
  `refused_requests` line a minute, by reason.
- The workflows that build and release the game run every action from outside the repository at a pinned
  commit, with the version it was pinned at beside it, so a moved tag cannot change what a release runs.
- `tools/net/smoke.py` imports the project before its games start when the class cache lacks a script's
  class (a fresh clone, or a pull that brought one), instead of starting games that cannot parse.

## 0.6.0 · 2026-10-31

Ship it (M5): online play on the official server, desktop builds, a server to download, and the release that makes
them all from one tag. This version also carries M2, M3 and M4 below, everything since 0.5.0.

What a player sees:

- The browser game plays online on the official server, `wss://groundhold.saschb2b.com/causeway`. Join's
  Official row connects there, a party code typed alone joins that party there, and the party strip's copy link
  (`https://saschb2b.github.io/Groundhold/play/?join=K7Q4M`) opens the game in a friend's browser and joins it.
  A friend who opens the link on a first visit names themselves first, and the party sees that name. The link
  always opens the official server, so a party on a LAN or another server offers its code alone. The browser game
  joins only the official server; a server of your own serves the desktop game.
- The game for Windows, macOS and Linux is on the release page: `groundhold-windows-x64.zip`,
  `groundhold-macos.zip` (one app for Apple silicon and Intel) and `groundhold-linux-x64.zip`, each with a
  `README-first.txt`. The desktop game plays online like the browser, and on your own network with a server
  from the same page. The builds are not signed: macOS asks for its quarantine steps once (README.md, Play
  together, says how), and Windows SmartScreen for More info, then Run anyway.
- The server for a LAN party: `groundhold-server-windows-x64.zip`, `-macos-arm64.zip`, `-macos-x64.zip`,
  `-linux-x64.zip` and `-linux-arm64.zip` need nothing installed; `groundhold-server-python.zip` runs wherever
  Python 3.11 or newer does. Each unpacks into one folder and says how to start it on its system.
- The official server has a policy: who runs it, who moderates, the rules, what it keeps and for how long, and
  how to have your identity forgotten. It is on the site (`policy.html`, linked from the footers) and in
  `server/README.md`.
- The browser build asks for its files by its build number, so a reload just after a new build never mixes the
  old build's code with the new one's data. The game prints its version, its build and the official server as it
  starts.
- The results of a party match keep the connection: read them as long as you like, and Play again finds the
  party. Before, a player who stayed on the results for more than 15 s lost the party without a word. If the link
  goes on the results, the hub says the party went with it and the game is offline, a party of one.
- A party link with anything but a whole code (`?join=k7q-4m extra`) opens the game plainly instead of looking
  for another party.

Hosting:

- The server's image, `ghcr.io/saschb2b/groundhold-server`, for x86-64 and ARM64, tagged with each release
  (`0.6.0`; `0.6` and `latest` while it is the newest of its 0.6 and of all). It runs as an unprivileged user on a
  read-only filesystem and writes only its state and its backups. It is pushed only once the release's desktop
  exports and server archives have passed, one release at a time.
- `--port 0` without `--host` listens on one port for IPv4 and IPv6 alike, the one it prints; before, each family
  got a port of its own, and the printed one refused IPv4.
- `deploy/selfhost/compose.yaml` runs a server of your own on any computer with Docker and a domain: the image,
  its daily backup, and Caddy with a Let's Encrypt certificate and no access log. Set `DOMAIN=` and run
  `docker compose up -d`.
- `deploy/coolify/` runs the official server in Coolify, beside Cyberworld Endless's: the server and its backup,
  both hardened, with health checks. It deploys at a release and at no other time: the release moves the
  `release` branch the Coolify app follows, then asks Coolify's API to deploy where the repository has the
  secrets for it. A tag moves it only forward, to the newest release (two releases at once never leave the older
  one deployed); a release of an older tag by hand rolls back. A restart ends the matches running, so a push to
  `main` never restarts it.
- `--backup DIR` makes its folder when there is none yet, and an empty `--restore ""` (or `--backup`,
  `--state-dir`, `--config`, `--event-log`) is refused rather than starting a server.

For developers:

- `.github/workflows/release.yml` makes a release from a tag `vX.Y.Z`. Its gate refuses a tag that is not on
  `main`, is not `project.godot`'s `config/version` or has no dated section here; then the desktop exports (Godot
  and its templates checked against Godot's published SHA-512 sums first; the Linux one booted headless to the
  hub), the server's five native builds and its zipapp (each archive smoke-tested outside the checkout) and its
  image; then the GitHub release with every file and `SHA256SUMS.txt`; last the deploy. Run by hand it is a dry
  run: everything built and checked, the files kept as the run's artifact, nothing published. `server/README.md`,
  At a release, is the checklist.
- `server.yml` runs the server's tests on Python 3.11, the release tools' tests, the zipapp's archive and
  `deploy/check.sh` (both Compose files, the image's build context, a bare hardened container, both stacks
  healthy) on every change to the server, its contract, the deployment or the release.
- `server-data/` and `server-backups/`, where a server started in a checkout keeps its identity key, its
  moderation and its archives, are ignored by git.
- `tools/release/` holds the release's steps (`gate.py`, `stamp.py`, `package.py`, `desktop_smoke.py`,
  `assemble.py`, `deploy.py`) and their tests; `server/release.py`, `smoke.py` and `notices.py` package the
  server. `assemble.py` lists the release's files, and the tests hold every page that names a download to that
  list.
- `export_presets.cfg` has Linux, Windows and macOS presets beside Web; the data and the wire contract go into
  each, the server, the deployment, the tests and the tools stay out. `data/net.json` names the official server;
  CI writes `data/build.json` (the build number is the run number). Pages' `join-link` job runs
  `tests/web/flow_join_link_through_iframe.py`: the exported site in headless Chrome, a `play/?join=` link
  joining a party on a real server.

Resilience (M4): a dropped connection, a browser tab in the background or a game that fell out of step no longer
ends anyone's match.

What a player sees:

- When the connection drops, your world keeps running and a small bronze plate above the console says
  "Reconnecting... your towers keep firing". The game tries again every 2 s and gives up after 30 s. While you
  are gone the caretaker plays your seat with your gold. Once you are back in, the game loads the latest
  checkpoint everyone agreed on, the plate says "Catching up" with a bar, and your seat is yours again at the
  next build window. A party match keeps its party through all of it.
- A game joined straight to a server (`--join`) that crashed, or was closed or killed in the middle of a match,
  takes its seat back when you start it again the same way: it remembers the match and the seat on this
  computer until the match ends. If the match is over by then, it simply joins as a new game. (A game started
  again from the hub does not do this yet.)
- In the browser, a tab in the background tells the others ("in another tab") and flashes the page title. When
  you come back the game catches up, fetches any turns a full buffer lost, and says the caretaker keeps the seat
  until the next build window.
- With three or more players, a game whose state parts from the others' is reloaded from the latest agreed
  checkpoint and plays on; the same game parting a second time is taken out (the caretaker keeps its seat) and
  goes back to the party. Two players apart still end the match "out of step". Each game then saves a report,
  `user://desync/<match>-<seat>.bin`, and the plate names it: the report holds enough to replay that game's side
  up to the tick where they parted.
- Orders wait while the game reconnects or catches up, and the card says why.

The server:

- It compares every seat's state hash each second. At each checkpoint (every 30 s, and as each wave starts) it
  asks one game in turn to upload its state, and keeps the upload only if its fingerprint is the hash everyone
  agreed on; it keeps the last two and never reads them.
- It holds a dropped seat until the match ends, during maintenance and on a full server too, and gives it back
  to a resume from the same profile; a second window of that profile takes the seat over from the first.
- It sends a catch-up at 2 KB per 50 ms while the connection's unsent output stays under 4 KB, a pace a browser
  keeps up with, and the live turns queue behind it. A tab back from the background, or a player the party
  started without, catches up from the latest checkpoint when that is nearer, and gets control back only once
  its game says it is level.
- `/stats` counts desyncs, resyncs and rejoins.

The simulation:

- The caretaker takes over a seat mid-match without undoing the player's work: a plan step whose cell already
  holds one of the seat's towers counts as done, and it forks only the kind of tower its plan built on a cell.
- A seat changes state only when AWAY, BACK or LEFT or the next build window moves it, and the party strip hears
  of it only then.
- Each tick the creeps are sorted along the road once and every tower walks that order, instead of testing every
  creep: a busy tick (four seats at wave 11) steps at about 13,000 ticks a second natively, up from about 5,000,
  so 30 s of turns take about a seventh of a second. Every match plays exactly as before, down to its state
  hashes.

Fixes:

- A game started with `--join` (or any match flag) no longer prints an engine error as it leaves the hub for the
  match: the scene change waits for the hub to finish loading.
- A resync from a server further away than an hour of turns is refused instead of growing the turn log toward it.
- Every test loop that waits for something has a bound and says what never came (the server's tests also cap
  their own memory at 4 GB), after one such loop ran the machine out of memory.

For developers:

- The real-server topologies in `tests/net/live/` now cover the faults: a socket dropped mid-match, a whole game
  killed and started again, a minority of three resynced, and two seats apart ending with both dumps checked.
  `tools/net/shaper.py` puts latency, stalls and cuts in front of one game, and `smoke.py --shaper` and
  `--faults` play whole matches through it. The protocol's transcripts gained `m4_resilience`, recorded from the
  server. `sim_bench` measures the simulation's speed at a busy moment.
- `docs/design/contract-m4.md` fixed what the four tracks shared. The protocol stays version 1 (nothing has
  shipped): `HELLO`, `MATCH_CONFIG` and `RESYNC` got longer, so a game and a server from before M4 cannot talk
  to ones from after it.

The README and the site describe Groundhold as it is now: the hub, the Builders, parties, High Water on Wickhollow
and the results, each with a new screenshot drawn as the browser build draws it; how to play together (in the
browser online only, on desktop over your network, two windows on one computer); and what a player sees when a
link drops, in another tab and out of step. `play/?join=K7Q4M` hands a party code on to the game in its frame.

Builders and checks (M2): High Water is playable. Tamsin Wick, the Lamplighter, and Edda Greyplume, the Lookout,
hold Wickhollow together through twelve waves.

- High Water is a mode of its own on Wickhollow's twelve waves. Each early wave teaches one check: Swarm
  (Gourdlings), Swift (Scuttlers), Armored (Thornbacks) and Winged (the new Duskmoths). The Bristlesow, a larger,
  darker Thornback, comes at wave 6 and the Hollowtide Crest at wave 12. Creep health grows with every wave and
  with the number of players. The classic match plays as before, down to its state hashes.
- Armour takes a flat amount off every hit, never more than three quarters of it. Duskmoths fly: only towers that
  reach the sky aim at them, and splash leaves them alone. Bosses shake off part of every slow.
- Every tower forks once, for good, into one of two branches. The Lamplighter's second branches answer what she
  lacks: the Skyward Loft and the Rime Spire reach the sky, the Iron Mortar pierces armour. The Lookout builds
  Perch Ballistas, Hawk Roosts that hunt fliers first, Kestrel Flocks whose strikes fly on to two more creeps,
  and the Owl's Eye, whose mark makes every tower hit the strongest creep 20% harder.
- Slows and marks never stack; the strongest applies. A hit on a creep a teammate slowed or marked counts as that
  teammate's Help. Perks: the Lamplighter's towers sell for 90%, the Lookout's reach 0.4 tiles farther.
- The command card is the same for every Builder: Q, W and E place your three towers, or choose a branch on your
  own tower; A signals, S sells, D is Ready (N and Space too). This replaces A, C, F, U, S and N. A teammate's
  tower names its owner and cannot be sold. Tooltips say what a fork changes in numbers and which check it lifts.
- The strip shows the next wave's checks, each beside the portrait of the creep that brings it; hovering the wave
  lists every wave to come. Every tower form stands as its own model, Duskmoths hover and glow without lights,
  marked creeps wear a gold rune, and the minimap shows towers in their owners' colours.
- The caretaker plays either Builder and forks for what the team lacks. Balance gates (`tests/balance/`) check
  each Builder alone, the pair, idle teams and the match's length. Tuned to pass them: health grows 25% a wave
  (was 20%), two players face twice the health (was 1.85 times), the Bristlesow has 500 health (was 900), and
  waves 3 and 5 come a little slower.

The hub, parties and the way back (M3): the game opens on the Causeway at low water, where a party forms before a
match and comes back to after it.

- The hub shows your party, your Builder in the arch with the checks the party covers, the modes and one button.
  Alone, Play starts an offline match at once. A first launch asks for the name the others see.
- Builders (B) shows each Builder's role, perk and kit with both branches, with the command card's own tooltips;
  there you set your main and backup, or Try one in a practice match.
- Join (J) takes a party code in any case, with or without its hyphen, lists servers on the home network
  (desktop only) and takes an address: `192.168.1.20` means the LAN, a name means online.
- In a party the leader starts once everyone is Ready, and anyone can cancel the 3-2-1. Loading shows a card per
  player (Connecting, a percentage, Checking, Ready, Slow from 15 s) and names whom everyone waits for. The results
  give each player's numbers and one line of praise; Play again goes back to the hub with the party as it was.
- A server started without `--dev-match` keeps parties by code: Ready and the countdown, the loading timers (4,
  15, 30, 45 and 120 s), the results and the way back, and a dropped player's place held for 40 s. Servers on a
  home network announce themselves. Identities need no accounts: stable on one server, unlinkable across servers.
  Hosts get moderation, the day's totals at `/stats`, retention and daily backups.
- Tamsin Wick and Edda Greyplume stand as figures: the hub's arch shows your main's head and shoulders, the
  Builders screen the whole figure, and party rows, loading cards and the party strip show their faces. The
  console gained the pieces these screens are drawn from, and the Causeway's props are modelled.

M2 and M3 together.

- From the hub, the Lamplighter and the Lookout play as themselves and High Water by its own rules; the stand-ins
  (a Lamplighter for the Lookout, the classic match behind High Water) are gone.
- A build now has one rules hash for every mode. Before, a game said hello with classic's hash, so a party's High
  Water match on a real server could never match it.
- The server tells each party member its own row (`you` in `PARTY_STATE`), and Play again tells it the player has
  left the results. The protocol's transcripts were recorded again.
- `python3 tools/net/smoke.py --flow` plays the loop with two headless games against the real server: a party by
  code, Ready and Start, loading, a High Water match with a Lamplighter and a Lookout, the results, and both back
  in the party with equal hash streams. `tests/net/live/flow_party_by_code_live.json` does the same up to the
  match. CI runs both, and the balance gates.

The Builders' new look: Tamsin and Edda are chibi toon figures now, after League's champions in spirit and The
Wind Waker and A Hat in Time in style: about three heads tall, faces of a few flat shapes, one big hat or hood and
one big tool each (Tamsin's lamp pole, Edda's spyglass), lit in two tones with a crisp edge so a Builder stands out
from the painted towers. Their portraits, busts and icons are rebuilt from the same scripts, and the browser build
lights them like the desktop one.

Fixes from the first review of M2 and M3.

- Two slows on one creep: the stronger one lasts only its own time, and a weaker slow with time left takes over
  the moment it lapses, so a teammate's slow never leaves a creep walking free.
- The rules hash covers the checks each Builder covers, which the caretaker's forks follow, so two builds that
  differ there are never matched together.
- The game never sends its device key: each server gets its own token, derived from the key and the server's
  address, so no server can sign in as you elsewhere or link you across servers.
- A Try, or Play alone, while in a party on a server keeps the connection and the party.
- The server refuses party changes from a player whose match is running, a row held through a long match can
  still be taken back after 40 s, and a LOADED that crosses the loading limit no longer costs the party row.
- Esc in a match opens a small menu: Resume, Restart (offline) and Leave to hub. An offline match waits while it
  is open. From 30 s of loading the leader can start without a stuck player.
- A match opens with the camera on the Welling, the Holdfast and the band where both Builders build. The card's
  Signal has its own icon, a pennant over the ring a signal draws. Tooltips mark fork branches with a sign
  instead of "A" and "B", which read like the A key.
- The hub stands on the Causeway at low water in 3D: the road, tide poles, cairns and wrack under a low sun,
  with the camera drifting along the road. Text fields, rules, panels, loading cards and bars use the console's
  painted pieces. Long names end in an ellipsis instead of being cut, and every perk shows in full.

The game is called Groundhold now, after its world (`docs/design/world.md`).

- The game, the site and the server are called Groundhold. The map it plays on is Wickhollow, whose road runs
  from the Welling to the Holdfast, and its last wave brings the Hollowtide Crest. Lanterns, gourds and the
  autumn night stay Wickhollow's own.
- Ids and the protocol follow the name: the server is `server/groundhold_server` (set from
  `GROUNDHOLD_SERVER_*`, built as `groundhold-server.pyz`) and speaks `groundhold.v1` at `/causeway`. On the wire
  the modes are `classic`, `high_water`, `tide_race` and `undertow`, the second Builder is the `lookout`, a
  send is corked and uncorked (`CORK`, `UNCORK`, refused with `NO_CORKS_LEFT` and `NOTHING_CORKED`), and the
  comeback is the `SEAWALL` (`SEAWALL_STANDING`); every id keeps its number. The boss's id is `hollowtide_crest`.
- The repository is `saschb2b/Groundhold` and the site moved to https://saschb2b.github.io/Groundhold/. GitHub
  forwards the old repository address; the old site address does not forward.
- `tools/names_check.py` fails on a retired name anywhere in the tracked tree, and CI runs it next to the
  simulation lint.

The same game on a new engine room: the first step towards playing together (design M1a).

- Every rule now runs in an integer simulation (`scripts/sim/`) that steps 60 ticks a second from the match's
  seed and its turns, with no floats, clocks or scene tree. The same orders give the same match on any machine
  and at any speed; a state hash every second and a checkpoint prove it.
- Solo plays as before: the same eight waves, towers, prices and bounties. Orders go through an in-process turn
  source and land within 50 ms; a tower you place shows as a pulsing ghost, its cost greyed out of your gold,
  until then.
- Next Wave is now **Ready** (still <kbd>N</kbd>, still the war horn): when everyone is Ready the horn sounds at
  once and each second left pays a gold. With company the strip shows how many are Ready.
- Two to four seats already work in the simulation: shared lives, own gold, every kill's full bounty to every
  seat, only the owner upgrades or sells, and contested cells go to each seat in turn.
- Creeps, towers, shells and effects are views of the simulation; a cannon's barrel no longer decides where its
  shell lands.
- Boot flags `--seed`, `--bot`, `--hash-log`, `--quit-after-match` and `--ticks-per-frame` for headless runs.
- Tests fast-forward tick-exactly with `ticks_per_frame`; new scenarios check tick exactness, replays,
  checkpoints, range by road intervals, the co-op rules and the turn order.

One road, two players: a match over a server (design M1b).

- `server/` is the multiplayer server, forked from Cyberworld Endless's: a turn sequencer that never simulates.
  `python3 server/main.py --dev-match classic:2` forms a match from the first two games that join.
- `--join=127.0.0.1` joins it. The game says HELLO, builds the match the server describes, checks its tick-0
  state against everyone's, and plays the server's turns at 60 ticks a second behind a small buffer sized from
  its ping. A stalled game stalls alone and catches up at up to 8 ticks a frame; a state hash goes up every
  second, and two games that part end the match "desynced".
- A party strip at the top left shows each player's glyph in their seat colour, name, gold, link and Ready mark;
  "away", "caretaker" and "left" replace the gold while the caretaker holds a seat. Before the match it says
  where the link stands.
- `--name`, and `--shot-at`/`--shot-dir` to save the window at given ticks. The plan bot plays any seat; seat 2
  builds on its own cells.
- The wire contract (`shared/net/protocol.json`) is read by the game at runtime; a scenario decodes the server's
  recorded transcripts byte for byte. Loopback scenarios run two clients against a fake sequencer in one
  process; `tests/net/live/` runs them against the real server; `tools/net/smoke.py` plays a whole match with
  two headless games and compares their hash streams.
- The server ends a match only on a result most of the present players agree on; with two, both. A player
  still on the way is waited for, and one whose game has played past someone's claimed end disagrees, so the
  match ends "desynced" rather than on one player's word. A result, like a hash, is bounded by the turns
  sealed.
- Asking the server for missing turns costs it at most 100 turns per request and one answer per quarter
  second, so no game can stall everyone else's turns by asking.
- Orders wait for the match: before it starts, and after the link is lost, the commands are greyed, the
  countdown and the horn's early gold are hidden, and a key or click says why ("The match has not started",
  "No link to the server"). Orders that will never land drop their ghosts.
- The game keeps to the server's command rate itself. Ready goes out one at a time and the last press counts,
  so mashing <kbd>N</kbd> no longer costs the connection; any other order past the limit says "Not so fast".
  When the server does refuse a game, the game now reads why before the connection closes.
- Upgrade and Sell grey out for a partner's tower; my plate on the party strip shows my gold less what my
  orders on their way will spend, and keeps its width when the Ready mark goes; the Holdfast counts every
  tower standing, a partner's too.
- The caretaker acts on the first tick of a build window, not up to half a second later; a portrait turns
  from its subject's front when something new is selected.

## 0.5.0 · 2026-10-29

A smaller, crafted console.

- The 208 px bar is gone. A low bronze-over-stone console holds the minimap and the command card on two wings,
  and rises only at the centre into an arched portrait window with a keystone and an amber gem; between them
  the hollow shows through. Gold, lives and the wave hang from a slim strip at the top right.
- The command card holds only its six commands: the three towers, Upgrade (a hammer), Sell (a purse) and Next
  Wave (a war horn). Each icon has its own coloured backdrop, a cost on a shaded foot and a hotkey tab.
  Tooltips give the hotkey, the cost and, for an upgrade, the numbers it changes.
- The info shows numbers, not prose: damage, range, cooldown and slow or splash for a tower; health, speed,
  bounty and toll (the lives it would take) for a creep.
- Wave titles get a gilt rule fitted to the text; "Cannot build there" and "Not enough gold" are small notices
  over the console instead.
- The console is painted at twice its size, so it stays sharp at 1080p and above, and the portrait looks the
  same in the browser as on desktop.
- Fixed: the portrait sometimes framed a newly selected creep tiny or not at all.

## 0.4.0 · 2026-10-29

Hand-modelled plants and creatures, built in Blender.

- Pines with tiers of drooping needle boughs, dark blue-green inside and lit at the tips, and broadleaf
  trees with gnarled trunks and lumpy, layered crowns in green, amber and red. Foliage is painted cards that
  sway in the wind.
- New bushes, ferns, grass tufts, reeds, flowers, mushrooms, mossy rocks, a cut stump, lobed pumpkins and
  lily pads. Ferns now grow in the woods.
- The creeps are rebuilt as rigged models with walk cycles that keep pace with the ground and slow down
  under frost. The gourdling is a jack-o'-lantern goblin on root legs, the scuttler a glossy purple beetle
  with glowing eyes, the thornback a quilled boar, and the Hollow King a crowned pumpkin lord in a cloak
  who carries a lantern sceptre.
- Every model is a Blender build script in `art_src/blender/`, rebuilt with `godot-agent asset blender`.

## 0.3.0 · 2026-10-28

Richer light and forests.

- Tall layered pines with jagged, drooping boughs, dark at the base and bright at the tips, and broadleaf
  trees in green, amber and red with lit crowns. Woods are dense, with stumps among them.
- A low late-afternoon sun from the upper left: faces toward the camera are lit and long, crisp shadows fall
  away. Soft contact shadows under every creep, tower, tree and landmark; SSAO on desktop.
- Deeper greens with darker clumps and bare earth showing through, light haze at the far edge of the view,
  warmer colour grading and a vignette.

## 0.2.0 · 2026-10-28

The ground and the water get the hand-painted treatment.

- Painted, seamless ground textures: grass with blade strokes and autumn patches, a meadow with flowers,
  a pebbled dirt road, sand, mud and stone. The road's borders are ragged, with grass creeping over them.
- The grass rolls in gentle rises and dips; the road stays level, and towers and props stand on the ground.
- The pond is a rounded bowl with sloping sandy banks instead of square tiles: turquoise shallows into deep
  blue, a foam line that laps at the shore, drifting ripples with sun glints, reeds and lily pads.

## 0.1.0 · 2026-10-28

The first public build, playable in the browser.

- A tiled hollow at dusk: a winding road from the rift gate to the hearth, cliffs, a pond, autumn woods and meadows.
- Three towers with an upgrade each: the Arrow Tower, the Cannon Tower (splash, a turning bronze cannon that recoils)
  and the Frost Spire (slows, a floating crystal with orbiting shards). Sell any tower for 70% of what it cost.
- Eight waves of Gourdlings, Scuttlers and Thornbacks, ending with the Hollow King.
- A Warcraft III style console: a minimap you can click, a live 3D portrait of the selection, its stats, and a
  command card of framed icon buttons with hotkeys and tooltips.
- Muzzle flashes, impacts, death bursts with floating gold, build dust, blast rings and frost novas, and a sound for
  each of them.
- Pan and zoom with the arrow keys, the wheel, middle-drag or the minimap.
