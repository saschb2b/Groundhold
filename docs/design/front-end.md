# Groundhold's front end

*Proposed on 2 November 2026, from research into Blizzard's front-ends, the genre's and the craft's, reviewed as a
greenlight review would; the owner's decisions are §8. Where it differs from [`core-loop.md`](core-loop.md) §5, core-loop
still holds until F0 rewrites it.*

**Summary.** Today the hub is the match's HUD with other contents in its slots. This design removes the console from every screen outside a match. The Causeway becomes a stage. Your Builder stands on a mark on the road, and friends who join stand on the marks beside you. A thin top bar and one large call to action sit over that stage. The Modes band previews each mode on the stage itself. Camera moves join the screens, and 2D plates hold every decision. The front end shares the HUD's bronze, stone and type, but not its layout. Most first visits are alone, offline, in the site's browser frame, so that case comes first: it sets the type scale, the frame budget and the loading plan. Nothing on the wire changes. `Session` keeps its states and its API. The new front end is built in new files behind a boot flag, so the owner sees it before M8 merges. Only the switch-over touches M8's files.

Repository paths are relative to the repository root.

---

## 1. Diagnosis

1. **The hub is the HUD with other contents, and the design asked for that.**
   - `Shell._build_console()` loads the HUD's own pieces: `rail.png`, `wing_left.png`, `wing_right.png`, `crest.png`, `portrait_bg.png` and `strip.tres`.
   - It places them with the same `layout.json` keys: `map_well`, `card_well`, `centre`, `window`, `wing` and `socket`.
   - In `docs/media/party.webp` and `high_water.webp`, the bottom 140 px match in silhouette and in pixels.
   - Core-loop §5.1 asks for this: "the console art is shared, not duplicated". Its table gives each screen a set of wells. §0.3 #12 and AGENTS.md say the same.
   - So the fix starts in the design document, not in the code.

2. **The most important controls are the smallest.**
   - The call to action is one 54 × 54 command socket in the bottom-right corner, the same size as Join. "Not ready" wraps onto two lines. "Cancel · 0:00" spills out under the socket.
   - Mode names shrink to fit, so "Undertow" ends up near 9 px.
   - Party names are 13 px, inside a 168 × 112 minimap well.
   - While you are queued, "Finding players" shows twice: in the pill and on the line above the socket.
   - Valorant's interface redesign named a clear call to action as one of its goals ([Riot](https://playvalorant.com/en-gb/news/game-updates/preview-the-future-of-valorant-s-interface/)). §5.2's rule, one call to action and never two, is right. The problem is that this one call to action sits in a 54 px socket.

3. **The place is empty.**
   - About 70% of the screen is the Causeway. world.md calls it the road "where crews meet and set out", but nobody stands on it.
   - Your Builder is a bust in the 124 × 128 selection-portrait arch. The party is four lines of text.
   - The references show the party in 3D:
     - A 2011 press-event preview of Diablo III's Battle.net interface showed the party's 3D models on the main menu ([Blizzplanet](https://blizzplanet.substack.com/p/diablo-iii-press-event-diablo-iii-battle-net-interface-screenshots)).
     - Overwatch's 2026 relaunch shows the selected hero in a 3D lobby, and its post-match accolades use full 3D hero models. A view of the whole group is announced for a later season ([All Things How](https://allthings.how/overwatch-drops-the-2-and-launches-10-new-heroes-in-2026/)).
     - WoW's Warband gathers up to four characters at a campfire ([Icy Veins](https://www.icy-veins.com/forums/topic/80038-new-war-within-login-screen-animations-added)).
     - Rocket League lines up the party's cars ([esports.net](https://www.esports.net/news/rocket-league/how-to-leave-party-in-rocket-league/), seen only through a search excerpt).

4. **The game has no identity on screen.**
   - The name Groundhold never appears. The window icon and the site's brand mark are both `ui/icons/arrow_tower.png`.
   - There is no music. Outside a match, the only sounds are Match Found's two.
   - Warcraft III: Reforged launched without the old animated menus, and players said those menus had been the heart of the game's look ([Dexerto](https://www.dexerto.com/gaming/warcraft-3-players-upset-missing-features-reforged-release-1320634)).
   - Patch 2.0 updated every front-end menu and the menu flow ([Blizzard](https://news.blizzard.com/en-us/article/24167122/warcraft-iii-reforged-patch-notes-patch-2-0-0)). Patch 3.0.0 made the main menu's music and ambience follow the chosen theme ([Liquipedia](https://liquipedia.net/warcraft/Patch_3.0.0)).

5. **Nothing moves, and nothing carries over between screens.**
   - Screens change by toggling visibility or by `change_scene_to_file` (`session.gd:1305`).
   - The hub and the loading screen each build their own `CausewayView`. The drift starts again at 0, so "Walking out" never continues from anything.
   - The figures are static meshes on a turntable, although §3.7 budgets "a short idle cycle".

6. **Pieces players expect are missing.**
   - There is no Settings screen. The Esc menu lacks the volume, fullscreen and name that §5.1 lists.
   - You cannot change your name after first launch.
   - There is no Quit and no credits page. Godot's licence notice belongs on a credits page.
   - The server sends a `motd` in WELCOME, and the game never shows it.
   - The results keep the HUD on screen, and Enter does not press Play again.
   - The modes, the open-seats switch, Copy, Invite, Main, Backup and Try work only with the mouse.

7. **The hub was least designed for the case players see most.**
   - Every first launch is a party of one, and so is every offline Play. Alone, the hub shows a bust and three empty rows.
   - `web/play/index.html` puts the game in an iframe inside `.wrap`: at most 1120 px wide, with 18 px padding and a 12 px border. The canvas is about 1060 × 596 CSS px, about 0.83 of the 720 base. A 13 px label is about 10.8 px on screen.
   - The web export is single-threaded (`export_presets.cfg`: `variant/thread_support=false`). Browsers block sound until the first click.

8. **The cause is the shared layout, not the shared art.** Warcraft III's classic menus used the same frame-definition files as its in-match UI ([Hive Workshop](https://www.hiveworkshop.com/threads/help-on-creating-custom-huds.322207)). They still had animated backgrounds of their own (Dexerto, above). Groundhold keeps the bronze and drops the wells.

## 2. Principles

1. **The console belongs to the match. The front end is a place.**
   - Hearthstone's team rejected a flat UI frame because it would break immersion. Its menu became a 3D box in a tavern ([hearthstone.wiki.gg](https://hearthstone.wiki.gg/wiki/Design_and_development_of_Hearthstone)).
   - StarCraft II 3.0 put a 3D scene behind every screen ([Blizzard](https://news.blizzard.com/en-us/article/19911221/ii)).
   - At BlizzCon 2008, a Blizzard developer said a good HUD must not be flashy ([Engadget](https://www.engadget.com/2008-10-24-the-creamy-gui-center-blizzcon-ui-wrapup-commentary-and-analysi.html)). Blizzard's menus are rich on purpose. Groundhold lacks that split.
   - In the references we examined, the menu has a layout of its own and does not reuse the match HUD's. This is our reading of their screens. No source states it.
2. **The crew is the subject, and a crew of one is the common case.** The party stands in the scene, as in Diablo III's preview, Overwatch's 3D lobby and accolades, and WoW's Warband (sources above). Apex's design director said its lobby is composed for three ([TheGamer](https://www.thegamer.com/apex-legends-dev-explains-why-dont-have-plans-add-quads/)). Groundhold's composition starts with one figure framed as the hero and widens for two to four.
3. **3D to show, 2D to decide.**
   - Heroes of the Storm replaced its 3D skins with 2D art in draft so that picks read apart ([Blizzard](https://news.blizzard.com/en-us/article/21719349)).
   - Hearthstone's metaphor buried modes, and the menu had to be reshuffled ([Out of Games](https://outof.games/news/3578-hearthstones-main-menu-gets-an-overhaul-play-is-now-hearthstone-battlegrounds-out-of-beta-mercenaries-joins-the-fun/)).
   - Deadlock's 3D Hideout opens ordinary flat menus from its terminals ([Deadlock wiki](https://deadlock.wiki/Hideout)).
4. **One bar, one button, Play always within reach, and a queue that follows you.**
   - StarCraft II 3.0 put navigation and the party in one top bar ([Wccftech](https://wccftech.com/starcraft-ii-patch-30-paves-legacy-void/)).
   - Heroes of the Storm moved its party to the top edge and let players browse while queued ([Blizzard](https://news.blizzard.com/en-us/article/15787795/heroes-technical-alpha-patch-notes-sept-10-2014)).
   - Dota's Play button is on every screen, and searching does not lock you in ([Valve](https://www.dota2.com/reborn/part1?l=english)).
5. **Fewer, larger choices, and no tabs inside tabs.**
   - Rocket League regrouped its modes into a few cards ([devtrackers](https://devtrackers.gg/rocket-league/p/5f93f4a3-first-look-play-menu-changes-coming-to-rocket-league)).
   - Players disliked Fortnite's locker split across tabs ([Sportskeeda](https://www.sportskeeda.com/fortnite/it-s-terrible-fortnite-chapter-5-season-1-locker-ui-disappointed-community)).
   - Diablo III resisted option bloat ([Engadget](https://www.engadget.com/2012-06-04-many-wow-like-improvements-discussed-for-diablo-3.html)).
6. **Fast before pretty, measured in the browser.**
   - A review called Reforged's menus sluggish ([The Technovore](https://thetechnovore.com/2020/03/12/warcraft-iii-reforged-reviewed/)). Blizzard listed poor menu performance at 1440p as a known issue ([Icy Veins](https://www.icy-veins.com/forums/topic/48108-warcraft-iii-reforged-patch-notes-known-issues-list/)).
   - Riot ran a six-month cleanup of the League client ([Inven Global](https://www.invenglobal.com/articles/10551/riot-launches-a-six-month-campaign-aimed-at-improving-the-league-of-legends-client)).
   - Diablo IV's lead UI designer put ease of interaction first and visual polish last ([Blizzard](https://news.blizzard.com/en-us/article/23308274/diablo-iv-quarterly-updatefebruary-2020)).
   - A menu costs a fraction of the match it starts, and the browser build is where that is measured.
7. **Show, don't tell.**
   - Diablo IV's campfire introduced each class by pose, without text ([Blizzplanet](https://diablo.blizzplanet.com/blog/comments/blizzcon-2019-diablo-4-unveiled-panel-transcript/2)).
   - WoW's character-creation redesign kept the character at the centre, darkened the edges, removed decorative side art and cut most text ([devtrackers](https://devtrackers.gg/warcraft/p/4aa62ebb-shadowlands-an-inside-look-at-the-character-creation-ui-redesign)).
8. **Sound and motion make it a place, and each has an order of importance.**
   - WoW gives every login scene its own variation of one theme ([warcraft.wiki.gg](https://warcraft.wiki.gg/wiki/Login_screen)).
   - Hearthstone's innkeeper greets you ([Mein-MMO](https://mein-mmo.de/en/hearthstone-weg-zum-megahit063,32034/)), and its objects bounce when touched (hearthstone.wiki.gg, above).
   - Firaxis builds UI sound in hierarchies ([GDC](https://schedule.gdconf.com/session/civilization-vii-impactful-ui-sound-design-at-scale/915690)).
9. **One family, two grammars.** Laura DeYoung, Riot's art director, described rebuilding the League client as a brand identity of its own, consistent and scalable, separate from the HUD ([GDC Vault](https://gdcvault.com/play/1024452/-League-of-Legends-Client)). The front end and the HUD share tokens and keep separate layouts.
10. **Accessible by default, and tested with new players.**
    - XAG 101 sets minimum default text sizes. For PC it is 18 px at 1080p, measured as body height: from the highest ascender to the lowest descender on a capture. Text must scale to 200% of that minimum without loss, scrolling in one direction at most. At least one sans-serif option is required, and lines of text use sentence case ([Microsoft](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/101)). We measure captures that way, not the theme's font size.
    - XAG 112: everything can be reached from the keyboard alone ([Microsoft](https://devdocs.xbox.com/gaming/accessibility/xbox-accessibility-guidelines/112)).
    - Hearthstone tested with new players on camera (hearthstone.wiki.gg, above). WoW's user testing found that new players feared choosing wrong (devtrackers, above).

**What the sources do not cover.** No tower-defense game is among them. The briefs could not check the menus of Legion TD 2, Element TD 2 or Bloons TD 6, the genre's closest peers. We have no genre evidence. F0 looks at those three on [gameuidatabase.com](https://www.gameuidatabase.com/) by hand and adds notes here before F1.

**The bar ("proud of us", as checks).**
- Every screen has a designed state for empty, alone, waiting, disabled-with-reason, error, queued and reconnecting.
- At 100% text, no label wraps or overflows. This holds at 4:3, 16:10 and 21:9, and in the play page's frame, in English and in the pseudo-locale (§6.4).
- At 200% text, nothing is cut off or overlaps, and nothing needs scrolling in two directions. The reflow rules in §4.3 apply.
- Every input answers in the same frame, with sound once the first gesture has unlocked audio. A panel's transition takes at most 200 ms ([Material](https://m1.material.io/motion/duration-easing.html)). A camera move never blocks input.
- The hub meets §6.7's absolute budget in Chrome at the play page's frame size.
- No single key press loses a queue or a found match.
- A fresh player, alone in the browser, reaches a running match within 30 s of first launch and places a first tower within 60 s, without a guide.
- No screen outside a match contains a console piece. A scenario checks this, so the complaint cannot come back.

## 3. The architecture

### 3.1 The navigation model

**Recommendation: the Causeway as a staged lobby, with a thin top bar, camera stations and 2D plates.** It has no walking and no wells.

| Model | Verdict |
|---|---|
| **A. A staged lobby on the Causeway, with a top bar (recommended)** | world.md already makes the Causeway the crews' meeting place. The figures and the 3D world exist (`BuilderFigure`, `causeway_view.gd`). The party is shown, not listed, and one player is framed as the hero (principles 2 and 3). Stations replace panels with camera moves. |
| B. StarCraft II 3.0's tabbed client over a 3D scene | We take its bar. On its own, the scene stays wallpaper behind panels, which is today's problem in a nicer frame. |
| C. League's party-first client (nav bar, social sidebar, party rows, queue list) | It is built around a store, a collection, friends and chat. Groundhold has none of these in v1: everything is unlocked, and there are no accounts and no chat (core-loop §3.6, §9.2). A sidebar would be empty chrome, and the League client's long-running complaint is its weight (above). |
| D. Hearthstone's full diegesis, where the menu is an object | It costs clicks and buried modes (above). Three modes and four Builders do not need a metaphor bent to fit them. |
| E. A walkable hub (Deep Rock Galactic's Space Rig) | Walking adds friction between launch and play: [Push Square](https://www.pushsquare.com/reviews/ps5/deep-rock-galactic), [Kotaku](https://kotaku.com/enough-with-the-social-hub-in-video-games-1846456448). It is also wrong for a browser game played from the keyboard. |

**Depth.** There are three kinds of screen:
- **Pages:** Home and Builders. Each is a camera station.
- **Sheets over a page:** Modes (a band over the lower half), Join and Invite, Settings, Credits, the Home menu and the name prompt.
- **Modals:** Match Found, and the Esc menu in a match.

Every destination is one click or one key away: B, J and Enter. Every sheet has a visible Back control. Esc and Backspace also go back; Backspace only when no text field has focus. Back must be visible because the browser keeps Esc in fullscreen: Esc exits fullscreen there. The top bar has two tabs, HOME and BUILDERS, because there are two pages. No tab is called Play, so Play is only ever the button. Records or Learn can join the bar after v1. We do not invent pages to fill it.

### 3.2 The screen map

| Screen | Kind | One job | Reached by | Keys |
|---|---|---|---|---|
| **Home** (node `HubPanel`) | page, `home` station | Who I play with, as whom, in which mode; then one button | Boot, Play again, Hub, the HOME tab | Enter (except while queued), B, J; Esc closes a sheet, else opens the Home menu |
| **Modes** | band over Home's lower half; the stage above previews the focused card | Pick the mode. The leader also picks the level and open seats | The mode chip above the call to action | Arrows preview, Enter commits, Back, Esc or Backspace restores |
| **Builders** (node `BuildersScreen`) | page, `builders` station: a dolly to the Builder's mark | Understand a Builder and their towers; set main and backup; Try | B, the BUILDERS tab, "Change" on my nameplate | Back, Esc or Backspace; 1–4; Q W E for the towers; arrows |
| **Join and Invite** (node `JoinPanel`) | sheet | Join by code, address or Nearby; create, leave or invite | J, Join in the bar, "+ Invite" | Back, Esc, Enter |
| **Home menu** | sheet | Settings, Credits, Quit (desktop only; hidden on the web) | Esc on Home with nothing open | Arrows, Enter, Back, Esc |
| **Settings** | sheet; also opened from the in-match Esc menu | Audio, display, accessibility, controls (a read-only key list in v1), name | Gear icon in the bar, Home menu | Back, Esc, arrows |
| **Credits** | sheet | Who made it; tools; fonts and their OFL text; Godot's licence text, its third-party notices and their licences; the version | Home menu, Settings | Back, Esc |
| **Name prompt** | modal, first launch and Settings → Name | Your name, written on your own nameplate | First launch; Settings | Enter |
| **Match Found** (`/root/Session/MatchFound`) | modal on the Session layer, over any page | Accept or decline a match with strangers | MATCH_FOUND | Enter and Esc, taken only after 0.4 s on screen |
| **Loading, "Walking out"** (`/root/Session/LoadingScreen`) | Session layer over the stage's `walkout` station | Reveal the line-up and sync | MATCH_CONFIG; a short walk-out offline | none |
| **The Ebb** (results, `ResultsPanel`) | overlay on the finished hollow, HUD hidden | What happened, a good word for each player, Play again | Match over | Enter Play again; Esc, Backspace or the Hub button for Hub |
| **Esc menu** (`match_menu.gd`) | modal in the match | Resume, Settings, Restart (offline), Leave | Esc, or F10 where the browser keeps Esc | as today |

### 3.3 What persists

- **The top bar** (56 px at the 720 base) is on every page and stays visible under sheets.
  - Left: the Groundhold wordmark, then the tabs HOME and BUILDERS.
  - Centre: the queue pill, while queued.
  - Right: where you are ("Offline", "LAN · 192.168.1.20" or "Online"), the party code chip (Party K7Q-4M, with Copy and Invite), Join (J) and the gear icon.
  - There are no currencies, because everything is unlocked (core-loop §3.6). The party gets that space.
- **The call-to-action cluster**, bottom right on Home and Builders:
  - the mode chip ("High Water · Normal · 1–4 ▾");
  - the button, 360 × 64, with `Session.primary()`'s text unchanged;
  - the line under it;
  - `second` as a smaller button beside it (Start with caretakers, Race the caretaker).

  While queued, the button's slot holds "Cancel · 0:42" drawn as a secondary, stone button rather than the gilt primary. The timer shows in one place only: on that button while the cluster is on screen, otherwise in the bar's pill. This removes today's doubled text.
- **The crew** stands on the stage with their nameplates, from Home through Modes, Match Found and Loading.
- **Notices** show as toasts under the bar. The server's `motd` is one dismissible line under the bar on Home. It shows only when it is non-empty and has changed. It never carries art, and Home never carries news tiles: players complained about promo clutter in Overwatch ([Blizzard forums](https://us.forums.blizzard.com/en/overwatch/t/overwatch-2-interface-is-boring/965731)) and in Dota ([Hawk Live](https://hawk.live/posts/valve-released-an-unusual-update-for-dota-2)).
- **First-run defaults:** the Lamplighter, High Water and Normal are preselected, so a new player has nothing to find before Play.

### 3.4 Sketches (1280 × 720 base)

Home, alone and offline. This is the default case and the README's first shot.

```
+--------------------------------------------------------------------------------------------+
| GROUNDHOLD   HOME  BUILDERS                                              Offline  J  [gear] |
+--------------------------------------------------------------------------------------------+
|  (wrack and a tide pole near the lens, soft)                 (the waymark on the horizon)  |
|                                                                                            |
|                  |>                                       .   .   .   (three bare marks    |
|              (Tamsin, large,                              |   |   |    far back, dressing) |
|               lit, idle)                                                                   |
|                                                                                            |
|            .----------------------.   .----------------.   .--------------------------.   |
|            | <> Tamsin            |   |  + Invite (J)  |   |  + Caretaker partner     |   |
|            | the Lamplighter      |   '----------------'   |    the Lookout  < >      |   |
|            | Change (B)           |                        '--------------------------'   |
|            '----------------------'                                                        |
|  CREW COVERS  Swarm  Swift  (Armored)  (Winged)        .---------------------------------. |
|                                                        | High Water · Normal · 1–4     ▾ | |
|                                                        |              PLAY               | |
|                                                        '---------------------------------' |
|                                                          Alone, or add a caretaker partner  |
+--------------------------------------------------------------------------------------------+
```

- The caretaker plate shows only offline, on one-team modes. It adds a caretaker figure on the nearest bare mark, with a nameplate and Remove. Play then calls `Session.play_offline(builder, false, company, company_builder)`. The plate defaults to the Builder that covers what the crew lacks.
- `play_offline` takes one `company_builder` for every partner today, so v1's partners share one Builder. Giving each partner its own Builder would take a list there: a session change, with no change on the wire.

Home, a party of four. This is the store shot.

```
+--------------------------------------------------------------------------------------------+
| GROUNDHOLD   HOME  BUILDERS          ( Finding players 0:42 )   Online  Party K7Q-4M  J [gear] |
+--------------------------------------------------------------------------------------------+
|  (the server's message, one line, when it has one)                                    x    |
|            |>               |>                |>                  |                         |
|          (Ana)           (Sascha)            (Ben)           (a bare pole)                  |
|       .----------.   .---------------.   .-----------.    .--------------.                 |
|       | () Ana   |   | <> Sascha   ^ |   | /\ Ben    |    |  + Invite    |                 |
|       | Lookout  |   | Lamplighter   |   | Bellfounder|   '--------------'                 |
|       | Ready    |   | Change (B)    |   | Ready     |                                      |
|       '----------'   '---------------'   '-----------'                                      |
|  CREW COVERS  Swarm  Swift  Armored  (Winged)          .---------------------------------.  |
|                                                         | High Water · Hard · 1–4      ▾  |  |
|                                                         |             START               |  |
|                                                         '---------------------------------'  |
|                                                            Everyone is Ready                 |
+--------------------------------------------------------------------------------------------+
   |> a raised seat pennant (Ready)   | a bare pole   ^ leader   (Winged) dim: nobody covers it
```

Modes: a band over the lower half. The stage above it previews the focused card.

```
+--------------------------------------------------------------------------------------------+
| GROUNDHOLD   HOME  BUILDERS                                    Online  Party K7Q-4M  J [gear] |
+--------------------------------------------------------------------------------------------+
|      the stage previews the focused card: here Tide Race, two groups over still water      |
|           |>   |>                     ~ ~ mirror ~ ~                    .   .              |
|         (Ana)(Sascha)                                                (rival marks)          |
|                                                                                            |
|  < Back                                                                Ana picks the mode  |
|  .--------------------------.  .==========================.  .--------------------------.  |
|  | HIGH WATER               |  | TIDE RACE                |  | UNDERTOW                 |  |
|  | Hold one road together.  |  | Two crews play the same  |  | One against one. Send    |  |
|  | 1–4 players · 12 waves · |  | waves on two copies of   |  | creeps to your rival's   |  |
|  | about 13 min             |  | the map. Clear first, or |  | road and hold your own.  |  |
|  |                          |  | lose fewer lives.        |  | Cork packs from the Drift|  |
|  '--------------------------'  '=========================='  '--------------------------'  |
|  LEVEL  Normal  [Hard]  Very Hard        OPEN SEATS  [on] off          Enter choose · Back  |
+--------------------------------------------------------------------------------------------+
```

- Focusing a card previews that mode's formation, tide and camera. Enter commits. Back restores the committed mode.
- Each card leads with the rule in plain words. The world's word for it, where there is one, comes second and dimmer.
- The rule lines come from `Game.race_rule_words` and the presets, through `tr()`. Nobody types card copy by hand.
- Cards share the band's width, at most 360 × 184 each. At 4:3 they narrow, and the text reflows.
- In Undertow the level words are grey: "A duel is played at Normal", the M8 decision.
- A member sees the band read-only, with a line saying who decides.

Builders:

```
+--------------------------------------------------------------------------------------------+
| GROUNDHOLD   HOME  [BUILDERS]                                  Online  Party K7Q-4M  J [gear] |
+--------------------------------------------------------------------------------------------+
|  .--------.                                       TAMSIN WICK                              |
|  | Lamp * |     (the figure, close, idle,         the Lamplighter · Warden · difficulty 1  |
|  | Lookout|      at least 420 px; her three       Thrifty: her towers sell for 90%.        |
|  | Bellf. |      towers on the road beside her;   Strong  Swarm Swift   Weak  Armored Winged|
|  | Beek.  |      the focused one raised, its      .---------. .---------. .---------.      |
|  '--------'      two forks rising behind it)      | Arrow 40| |Cannon 70| | Frost 60|      |
|  < Back                                           | › Longb.| | › Great | | › Deep  |      |
|                                                   | › Skyw. | | › Iron  | | › Rime  |      |
|                                                   '---------' '---------' '---------'      |
|                                                   [Set as main] [Set as backup] [Try]     |
|                                                         .-------------------------------. |
|                                                         | High Water · Normal · 1–4   ▾ | |
|                                                         |             PLAY              | |
+--------------------------------------------------------------------------------------------+
```

- The roster is 2D portrait cards: 2D to decide. The figure and the towers are 3D: 3D to show.
- The kit is three tower cards. Each card's tooltip on focus or hover is `Game.kit_tip`, the text the match shows, so there is one source of truth (core-loop §5.4). The fork mark is `Game.FORK_MARK`.
- The towers stand still, as `Tower.model_of(form)` shows them for the placement ghosts.
- Focusing a Builder previews the crew's coverage: "With the Bellfounder: Armored covered".

### 3.5 The Play flow, by mode

| Mode | Alone, offline | A party of friends | The queue (strangers) |
|---|---|---|---|
| High Water | **Play**, optionally with caretaker partners on the bare marks → a walk-out of about 0.75 s (45 frames; `flow_hub_boots_offline` allows 300) → the match | Each member's Ready raises their pennant → the leader's **Start** → 3-2-1, each Builder raises their tool, a horn → Loading | Leader: open seats on → **Find players** → pill → Match Found → Loading. After 60 s, **Start with caretakers** |
| Tide Race | **Race the caretaker**: a caretaker crew with the same Builders stands across the road | A party of 2 or 4: the leader moves a player across the road by their nameplate (`Session.move_team`) → Ready → **Start** | A team of 1 or 2: **Find a rival** → Match Found → Loading. After 60 s, **Race the caretaker** |
| Undertow | **Duel the caretaker**: one figure faces yours | A party of two, as §5.2's table has it. A larger party sees "A duel is one against one" | A party of one: **Find a rival** → Match Found → Loading |

Every row ends the same way: the match, the Ebb, then **Play again** back to the Causeway, with the crew on its marks and the pennants lowered. A lone stranger is queued again, as today.

### 3.6 The session's states on screen

`Session` stays the state machine. It keeps its states, `primary()`, `screen` ("hub" or "builders", which the party sees as "in Builders") and every call the screens make. The router is a view of it.

| `Session` state | Route | Stage | Call to action |
|---|---|---|---|
| OFFLINE | Home or Builders (`Session.screen`) | My figure framed as the hero; the bare marks set back as dressing; a caretaker plate on one-team modes | Play, Race the caretaker, or Duel the caretaker |
| CONNECTING | Same page. The bar reads "Connecting to …" | Unchanged | Disabled, with the line |
| HUB | Home, Builders, or a sheet | The crew on its marks; pennants show Ready | §5.2's table |
| COUNTDOWN | Same page; open sheets close | Every pennant up; tools raised on 1; a horn on 0 | 3-2-1 (Enter cancels) |
| QUEUED | Any page; the pill | Bare poles on the open marks | "Cancel · 0:42" in stone. Enter does nothing. Esc only closes overlays. Leaving takes a click on Cancel, or holding Esc or Backspace for 0.8 s while a ring fills on Cancel |
| MATCH_FOUND | Match Found modal over the page; its keys wait 0.4 s | The camera turns to the horizon and the water starts to come in. An anonymous pennant rises on an open mark for each accept | The modal's Accept |
| LOADING | The loading layer | `walkout`: the camera sets off down the road past the crew. Strangers' figures land on their marks first. On the web the camera holds still while the match loads (§6.6) | none |
| IN_MATCH | The match scene | Asleep: hidden, not processed, not rendered | none |
| RESULTS | The Ebb (match scene) | Asleep. On Play again it wakes at `home` with the water ebbing | Play again, Hub |

The queue rule replaces today's Esc-leaves-the-queue. AGENTS.md and the `flow_*` scenarios that press Esc to leave change with it.

## 4. The visual language

### 4.1 One family, two grammars

| | Shared | Front end | HUD |
|---|---|---|---|
| Material | Bronze, stone tile, gilt rule; `GOLD #f0cf86`, `TEXT #ece2cc`, `DIM #a3957d` | Lighter plates floating over a full-bleed scene, with dark gradient scrims behind text | The heavy console mass along the bottom |
| Type | Noto Serif family | Large display sizes; Noto Sans body as an option | Compact, numbers first |
| Icons | Check glyphs, seat glyphs and Okabe-Ito seat colours, Builder glyphs | Large cards, 3D figures and towers, pennants | Positional sockets (Q W E / A S D) |
| Motion | One set of easing curves | Camera moves and staged reveals | Nearly still: feedback only |
| Sound | One timbre family from `sfx.py` | Ambience, a full set of UI cues, music | Gameplay first, few UI cues |

**The rule:** the front end may use the console's **materials**: `panel`, `panel_jewel`, `card_frame`, `field`, `bar_*`, `divider` and the theme tokens. It never uses the console's **architecture**: `rail`, `wing_*`, `crest`, `map_well`, `card_well`, `window`, `socket`, `strip.tres` or the HUD's `plate.png`. The scenario `front_no_console_outside_match` checks this.

### 4.2 Framing and scale (at the 1280 × 720 base; ×1.5 at 1080p)

- 32 px side margins, plus `DisplayServer.get_display_safe_area()`.
- The scene is full bleed. On Builders the edges darken, like a spotlight (WoW's character creation, above).
- No decorative side art.
- Sizes: top bar 56 px; call to action 360 × 64; nameplates 220 × 76; mode cards at most 360 × 184; roster cards 120 × 150.
- Figure heights on screen: 220–260 px on Home (the solo hero at the top of that range) and at least 420 px on Builders.
- **The play page gives the game the window.** `web/play/index.html` moves to a theatre layout: the frame fills the viewport's width, up to a 16:9 of its height, under a slim site bar. In a 1920 × 1080 browser window the frame is about 1700 × 956, a scale of about 1.33. The current 1060 × 596 frame stays a size we test, because a small window gives the same frame. `tests/web` covers the page's script.

### 4.3 Typography

| Use | Size and font (720 base) |
|---|---|
| Display: the wordmark on arrival, page titles | 44 / 32 px, Noto Serif Display Bold |
| Call to action | 26 px; it may step down once, to 22 px; it never wraps |
| Heading | 22 px |
| Body | 18 px |
| Caption, the floor | 16 px |

- At 1080p fullscreen the floor is 24 px and the body 27 px. In the theatre frame at a 1080p window they are about 21 and 24 px. In the old 1060 px frame they would be about 13 and 15 px, which is why the play page changes.
- XAG 101's 18 px is body height on screen. `front_text_fits` measures the floor in screen pixels at each frame size, the way XAG 101 describes.
- Nothing is smaller than the floor. Today's 10 and 11 px labels go.
- Running text is in sentence case. Capitals are kept for short headings and the button.
- Noto Sans (OFL, the same superfamily) is the body option under Accessibility. The serif stays the default for tone. Keep the type scale short: Rocket League's mix of sizes and weights was reported hard to read ([Can I Play That?](https://caniplaythat.com/?p=4020)).
- **Text size and UI scale are separate settings.**
  - *Text size*, 100–200%, scales the type tokens only. When text grows, these rules apply: the top bar collapses its tabs and status to icons with tooltips; a nameplate's state line moves to a tooltip, and the pennant still shows Ready; the mode cards scroll vertically inside the band. Nothing scrolls in two directions.
  - *UI scale*, 75–125%, goes through `Window.content_scale_factor` and scales everything. It stops at 125% because a 200% scale leaves a 640 × 360 logical canvas, which no layout here fits.

### 4.4 The living scene

**The colour script.** The match is saturated, painted toon. Today's Causeway is a low-contrast sepia flat, and about 45% of its frame is empty sky. Chibi figures dropped onto it would look pasted on. F0 writes a colour script: keys per station and state, as a palette in `palettes/` with a rendered board. It moves the Causeway toward the match's saturation and plans the values so that nameplates sit on scrims.

**The composition.** Every station has a set lens and camera height, and three planes:
- foreground props near the lens (wrack, a tide pole), soft;
- the crew on the marks in the middle ground;
- a landmark on the horizon, where the road leaves the Flats. The slice chooses it. It belongs to no map and carries no lantern.

**Marks.** Up to four stone slabs set into the road. Each is carved with its seat glyph (◆ ● ▲ ■) and has a pennant pole.
- **Alone:** my mark sits on the frame's left third, and my figure is the hero. The other marks are set back along the road, small, as dressing. A "+ Invite" plate stands beside me, and offline the caretaker plate too.
- **Two to four:** the camera eases back over 36 frames to frame the arc. My mark is second from the left, near the centre.

The formation follows the mode:

| Mode | Formation |
|---|---|
| High Water | Four marks in a shallow arc across the road, facing the camera |
| Tide Race | Two groups across a gap in the road. Under each crew the still water shows its reflection, the spring-tide mirror of world.md. The reflection is a mirrored copy fading under a translucent water plane, not a planar reflection, which the Compatibility renderer handles poorly |
| Undertow | Two marks face to face at the middle of the road; the camera turns side-on; a corked bottle bobs in the channel between them |

The formations stage rivalry by placement only. No screen shows a "VS" word or graphic (core-loop §5.6, amended in F0).

**Figures.** The party's `BuilderFigure`s stand on the marks and play idle loops. A friend who joins rises onto their mark. Strangers appear only at Loading. There is no walk cycle.

**Towers.** On the Builders station, the Builder's three towers stand on the road beside her. Focusing a kit card raises that tower, and its two fork forms rise behind it, smaller.

**Light.** v1 has one pinned daytime sky, chosen by the colour script. It is **never night**: night, lanterns, gourds and autumn are Wickhollow's (AGENTS.md). More skies can come after v1. Each one multiplies QA and determinism work.

**Tide.** `flats.gdshader` gains a water level and a stillness:
- low water on Home;
- the flood begins at Match Found and at the countdown;
- mirror-still while Tide Race is committed or previewed;
- the ebb on the return from results.

The tide belongs to the world, not to a map, so it runs on every map.

**Builders' homes**, after v1: a prop from the Builder's land beside their mark on the Builders page. A Builder's own flavour stays theirs. Tamsin may carry her lamp; the hub never lights one.

### 4.5 Motion

- Pages and sheets take 150–200 ms. Entrances ease out, exits ease in.
- Camera moves take 36–60 frames, counted in physics frames as `CausewayView` counts today, so captures repeat.
- A page takes input as soon as its plates are in, while the camera is still moving.
- Small motion makes things feel physical: the call to action presses down 2 px, a pennant overshoots and settles, cards lift 4 px on focus. This follows Hearthstone's lesson on physicality ([Inven Global](https://www.invenglobal.com/articles/1554/how-hearthstones-art-director-ben-thompson-breathed-life-into-hearthstone)), kept small.
- Reduced motion uses cuts and 100 ms fades. `DisplayServer.accessibility_should_reduce_animation()` returns an int: 1 means reduce, and any other value, including the platform not knowing, means don't. On the web the game reads `prefers-reduced-motion` through `JavaScriptBridge`. Settings overrides both.

### 4.6 Sound and music

Cues, in order of importance:

| Level | Cues |
|---|---|
| 1 | Hover: none |
| 2 | Focus: a quiet wooden tick |
| 3 | Confirm (bronze), back, toggle on and off (distinct), refusal |
| 4 | Sheet open and close |
| 5 | Ready: a cloth snap and a small bell; party join and leave |
| 6 | Countdown: `countdown_tick` |
| 7 | Start: `wave_horn`, the match's own horn, so the match opens with the horn the menu just played |
| 8 | Match Found: `match_found` |

- **Ambience:** a seamless loop of wind over the flats, water moving on sand and a far bell.
- **Music:** an `AudioStreamInteractive` with clips for the hub, the queue, Match Found and Loading, crossfaded by state. Where the music comes from is decision 3.
- **Buses:** a new `default_bus_layout.tres` puts Music, UI and Effects under Master. The match's sounds move to Effects. Settings has a slider for each of the four buses.
- **The first gesture.** Browsers block sound until the user's first gesture in the page. On the web, that gesture is how you enter: the name prompt's Done on first launch, or a "Click to enter" beat over the arrival's still frame on later launches. That click fades the ambience up and starts the arrival. On desktop the arrival plays at once.

### 4.7 Assets to make (all generated, as the project requires)

| Asset | Made by | Phase |
|---|---|---|
| Colour script and the pinned sky | A palette in `palettes/` and a rendered board; uniforms in `flats.gdshader`; the preset in `causeway_view.gd` | F0 |
| Front-end pieces: top bar, tab underline, call-to-action plate (idle, hover, pressed, disabled, counting, and the stone Cancel), mode-card frame, nameplate with a seat-colour chip, sheet panel, chip, toggle, slider knob, focus ring, scrims | A `front` section in `art_src/ui/console.json`, painted by `console.py` into `ui/front/`, with `.tres` through `HdStyleBox`. `layout.json` stays the HUD's | F0 |
| Wordmark and emblem: a holdfast knot in stone, with no Tide word in the logo (world.md); the window icon; the site's brand mark | Drawn as vector outlines kept in `art_src/ui/` as the recipe, and rendered with a gilt bevel by a new painter, `art_src/ui/wordmark.py`. The window icon and `web/`'s brand mark change in the same commit | F0 |
| Marks (a slab with a carved glyph, ×4) and pennant poles | `causeway.py --param piece=mark` and `piece=pole_pennant`. The flags come from `art_src/models/towers/pennant.json` (four shapes, a colour parameter) | F1 |
| Roster cards (256 × 320 renders of the figures) | `icons.py`'s model renderer | F2 |
| Builder actions: idle (a loop) in F2; ready and raise tool in F3; cheer and slump after v1 | Each part rigidly skinned before the join: all of a part's vertices go to one bone (head, body, hat, each arm, the prop). The poses are puppet keyframes in `art_src/blender/builders/*.py`. The kit's `chibi.Figure.finish` gains this option, because today it joins every part into one unrigged mesh | F2, F3 |
| UI cues and ambience | `art_src/sfx/sfx.py` and `sfx.json` | F4 |
| Tide states | Uniforms in `flats.gdshader` | F4 |

There are no rendered mode-card dioramas. The stage is the mode preview. The time this saves goes to the wordmark.

## 5. Signature moments

1. **Your Builder on the Causeway.** You open the game, and your Builder stands on the road, close and lit, with the road running into the haze behind. When friends join, they rise onto the marks beside you. The README's first shot is the solo one. The store's shot is the crew of four.
2. **Ready raises your pennant.** Your seat's pennant runs up its pole with a snap and a small bell. Each pennant has its own shape and colour, so the moment also works for colour-blind players. When every pennant is up, the leader's Start brightens.
3. **3-2-1 and the horn.** On 1, every Builder lifts their tool: the hand bell, the bee smoker, the lamp, the glass. On 0 the horn sounds. It is the same horn that calls every wave.
4. **The mode changes the water.** In the Modes band, focusing Tide Race stills the flats into a mirror, and the crew stands over its reflection. Focusing Undertow turns two figures face to face, with a bottle in the channel between them.
5. **The tide turns.** Match Found turns the camera to the horizon, and water starts to come over the flats. An anonymous pennant rises on an empty mark for each stranger who accepts.
6. **Walking out.** The camera sets off down the road past the crew, who turn to watch it go, while the cards fill. On the web it holds still in the haze while the match loads. Then the haze becomes the hollow. One stage carries all of it, so nothing starts over.
7. **The Ebb.** The console slides away. The camera settles on the Holdfast, which every map has. Each player's good line lands with a bell stroke. Play again brings you back to the Causeway as the water drains, with the crew on its marks.
8. **Your name on the road.** On first launch, the name field is your own nameplate, under your own figure. On the web, its Done is also the click that starts the sound.
9. **The kit on the road.** On the Builders page, the Builder's towers stand beside her. Focusing a card raises that tower, and its two forks rise behind it.

## 6. The Godot architecture

### 6.1 Nodes

```
/root
  Session (autoload; state machine and API unchanged)
    Stage (CanvasLayer, layer -1)             new; one per run (only under --front until the switch-over)
      CausewayView (Control)                  today's view, grown: stations, marks, figures, towers, tide
    MatchFound (CanvasLayer 25)               kept; restyled in F3
    LoadingScreen (CanvasLayer 30)            kept; restyled in F3; draws over Stage
    UiSound (Node)                            new: cues, ambience and music on the UI and Music buses
  Hub (scenes/hub.tscn, the main scene; scenes/front.tscn under --front until the switch-over)
    Shell (CanvasLayer 1)                     name kept; hosts the front end
      FrontEnd (Control: the router)
        Pages: HubPanel (Home), BuildersScreen
        TopBar, Cta (ModeChip, Primary, PrimaryLine, Second), CoverageRow
        Sheets: Modes, JoinPanel, HomeMenu, Settings, Credits, NamePrompt
        Toasts: Notice
```

- Until M8 merges, the new front end lives in new files: `scripts/frontend/*` and `scenes/front.tscn`. The boot flag `--front`, read by `Session`, opens it in place of the hub.
- At the switch-over, `scenes/hub.tscn` takes the new tree and keeps the node names that scenarios read. The new scripts replace `hub_panel.gd` and `builders_screen.gd`, and `front.tscn` and the flag go. `scenes/hub.tscn` stays the main scene, and the match keeps its scene change, so scenarios that assert `scene_path()` still hold.

### 6.2 The router

`scripts/frontend/front_end.gd` holds a stack of `{id, kind (PAGE, SHEET, MODAL), node, focus}`.

- `push`, `pop` and `replace` keep the focus of the page underneath, and make that page deaf through `focus_behavior_recursive` and `mouse_behavior_recursive`. Only the top of the stack takes input. `pop` restores the stored focus.
- `route_for(state, screen) -> StringName` is pure. On `Session.changed` the router reconciles the stack with it. Sheets stay local to the front end. `Session.screen` changes only for pages, so a party row still reads "in Builders".
- Readers: `route()`, `stack()`, `focused()` and `settled()` (no tween running, the camera on its station). A scenario waits with `{"wait_until": "FrontEnd.settled()"}`.

### 6.3 The stage

`CausewayView` moves under `Session` and grows:

- `go_to(station, frames)` for the stations `arrival`, `home`, `modes`, `builders` and `walkout`;
- `formation(mode, teams, party_size)` and `preview(mode)`, which the Modes band calls on focus and undoes on Back;
- `marks()` (seat → Builder, state, pennant up), `figure(seat)`, `towers(builder, focused)`, and `plate_point(seat)`, which unprojects a head point so the 2D nameplate stays sharp and focusable;
- `tide(level, still)`.

**Drawing.**
- The Causeway's 77 road segments and 98 props are separate instances today. They become one MultiMesh per model, as the board's terrain and decor already are.
- Animations run with `callback_mode_process` set to physics, so captures repeat.
- The stage's SubViewport updates every frame while the camera or a figure's one-shot is moving. Otherwise it updates every second frame: 30 Hz under the 60 Hz plates. Players sit on this screen for minutes in the queue.
- It stops updating (`UPDATE_DISABLED`) while the tab is hidden (`WebBridge` already reports this), in IN_MATCH and in RESULTS. There it is also hidden and not processed.

**Quality.** There are two levels, chosen in Settings, and the game never changes them on its own:
- **High:** shadows, MSAA 2×. The desktop default.
- **Low:** no shadows, no MSAA, the SubViewport at 0.75 of the canvas's size, blob-shadow quads under the figures. The web default. A downgrade during play would pop the scene in the middle of the first impression.

The checks of `flow_hub_causeway_backdrop` (`props()`, `camera_z()`, `drift`) stay.

### 6.4 Theme, tokens and strings

`scripts/ui/ui_theme.gd` holds the tokens: colours, the type scale, spacing and durations.
- `UiTheme.hud()` is today's `Shell.theme()`. `Shell.theme()` forwards to it during the move.
- `UiTheme.front()` adds type variations: `TitleXL`, `NavTab`, `ModeCard`, `PrimaryCTA`, `Plate`, `Nameplate` and `BodySans`. Text size scales these tokens. UI scale goes through `Window.content_scale_factor`, and the stretch settings stay `canvas_items` and `expand`.
- **Localisation is prepared, not promised.** No script calls `tr()` today, and copy is built in code (`Session.primary()`, `Game.race_rule_words`).
  - Every new string goes through `tr()`, with placeholders and never concatenation.
  - With no translation loaded, `tr()` returns its key, so scenarios that hold exact strings keep holding.
  - A pseudo-locale (35% longer, accented) runs in `front_primary_fits` and `front_text_fits`. The button and the nameplates are sized for German.
  - Noto covers the character sets.

### 6.5 Input and focus

- The `InputDirector` tracks the last device used. After the mouse it calls `grab_focus(true)`, so no ring shows. After keys or a controller, the painted focus ring shows.
- Focus neighbours are explicit: the marks are a wrapping row, the cards a row, the roster a non-wrapping grid. Every action that is mouse-only today gets a focus path.
- The keys:
  - Home: Enter, B and J.
  - Builders: 1–4 and Q W E.
  - Match Found: Enter and Esc.
  - The Ebb: Enter for Play again, Esc for Hub.
  - Back on every sheet: Back, Esc, and Backspace when no text field has focus.
- No key press throws a queue or a match away by accident:
  - While queued, Enter does nothing, and Esc only closes overlays.
  - Leaving the queue takes a click on Cancel, or holding Esc or Backspace for 0.8 s.
  - Match Found takes keys only after it has been on screen for 0.4 s.
- Controllers work through the `ui_*` actions. They are not a target until a Deck or console build is.
- Every control gets its AccessKit name and role when it is built, in F1 and F2.

### 6.6 Loading

- **Desktop:** `ResourceLoader.load_threaded_request("res://scenes/main.tscn")` starts at the countdown, at Accept and at offline Play. The walk-out covers the wait, and `change_scene_to_packed` follows.
- **Web:** the export has no threads, so a load stalls the main thread. A stall in the middle of the camera move would land on exactly the moment meant to sell quality.
  - The walk-out holds a still beat: the camera stopped in the road's haze, the loading plate in. `main.tscn` loads and builds during that beat. The camera moves only before it and after it, while the others load and the 4 s minimum runs.
  - If the build's stall is still visible there, F4 splits `main.gd`'s world build across frames (terrain, decor, views).
- The loading cards ease toward the reported progress, as today. Today's minimums and timers do not change: at least 4 s on screen, Slow from 15 s, Start without from 30 s.
- `front_stage_persists_into_loading` has a hitch budget: no frame over 50 ms while the camera moves.

### 6.7 Performance

`tests/views/frontend_run.tscn` prints a `FRONTEND_FRAMES` line, as `HOLLOWS_FRAMES` does: draw calls, primitives, and frame time p50 and p95. A web export of it prints the line to the browser console.

- **The budget:** the hub's p95 frame time is at most half of `one_hollow_run`'s p95, measured in the same browser on the same machine, with at most 150 draw calls. Both are measured in Chrome at the play page's frame size, on the Arc B390 and on a weak integrated GPU named in F0.
- The old gate, "no worse than a one-hollow match", would let a menu cost as much as a whole match: 626 ms a frame on llvmpipe, 8.8 ms p95 on the B390. And those numbers leave out the browser's own costs (AGENTS.md).
- The native llvmpipe and B390 runs are still recorded every phase, for the trend.
- The budget blocks a release.

### 6.8 Testability

- `flow_*`, `hub_*`, `race_*` and `view_duel_*` stay green on the old hub until the switch-over.
- Names that stand for something the player sees keep their node names: `Primary`, `PrimaryLine`, `Member1`–`Member4`, `Mode_<id>`, `CodeField`, `SetMain`, `Try`, `ResultsPlayAgain`, `HubPanel.lines()` and others.
- Readers that stood for wells (`Arch`, `portrait._shown`, `Shell.show_builder`) move to `Stage.figure()`. The scenarios that read them, and those that leave the queue with Esc, are rewritten in the switch-over commit.
- New scenarios, each made to fail first:

| Scenario | Checks |
|---|---|
| `front_no_console_outside_match` | No console piece in any tree outside a match |
| `front_route_for_every_state` | `route_for` across every `Session` state |
| `front_back_restores_focus` | Back from any route restores the focus it left |
| `front_keyboard_reaches_every_route` | Every route can be reached from the keyboard alone, Back included |
| `front_home_alone` | The solo composition, the Invite plate, and the caretaker plate offline adding a partner that Play passes to `play_offline` |
| `front_marks_follow_party` | Joins, Ready pennants, the crown, Invite, an open seat, Remove |
| `front_mode_preview` | Focus previews the formation and tide, Back restores them, Enter commits them; the race's two groups and the duel's face-off |
| `front_queue_keys_safe` | Enter does nothing while queued; Esc closes overlays only; a held key leaves; Match Found ignores keys for 0.4 s |
| `front_stage_persists_into_loading` | One `CausewayView`; the camera does not jump; the hitch budget |
| `front_stage_sleeps` | Not rendered in a match or while the tab is hidden; 30 Hz while still |
| `front_primary_fits` | Every `primary()` text on one line, in English and the pseudo-locale |
| `front_text_fits` | 4:3, 16:10, 21:9, the theatre frame and the old 1060 × 596 frame; text at 100% and 200%; the pseudo-locale; the floor in screen pixels |
| `front_rename_outside_party` | Name greyed in a party, with the reason; changed outside one; carried by the next HELLO |
| `front_results_keys` | Enter is Play again, Esc is Hub |
| `art_front_pieces` | The painted pieces and the wordmark are in place |
| `art_builders_animated` | Every Builder is rigidly skinned, one bone per part; its actions exist; the loops loop |

- `tools/play/describe.gd` learns the new layout at the switch-over. The screen word stays "hub", with pages added ("screen: hub · crew", "screen: hub · modes", "screen: builders"), so the personas' memories still make sense. `play_describe_says_what_shows` changes in the same commit.
- New `tools/media` shots: `home` (alone), `home_party` (four), `modes`, `builders`, `loading`, `match_found` and `results`. They are re-rendered every phase and sent to the owner.

### 6.9 Kept, replaced, moved

| Kept | Replaced | Moved |
|---|---|---|
| `Session` (states, API, `primary()`), `Profile` (plus settings keys), `Identity`, `MatchClient`, the protocol and server, `BuilderFigure`, `coverage_row.gd`, the logic in `join_panel.gd`, `name_prompt.gd`, `match_found.gd`, `loading_screen.gd` and `results_panel.gd` (`compute`, `lines()`, `team_lines()`) | `Shell._build_console`; the wells in `hub_panel.gd` and `builders_screen.gd`; `Shell.WidePlate` (`plate.png`) outside the HUD; `ResourceStrip` in the hub; `QueueCancel` in a socket; `Portrait` in the hub; Esc as the way to leave the queue | `CausewayView` from Shell and LoadingScreen into `Session/Stage`; `Shell.theme()` and `words_of` into `UiTheme`; the Esc menu's options into the shared Settings; the match's sounds onto the Effects bus |

**Names.** The name travels only in `HELLO` (16 bytes), and no `PARTY` op renames. So v1 renames only outside a party: offline, or after Leave. In a party the field is greyed with "Leave the party to change your name", and the next `HELLO` carries the new name. Nothing on the wire changes. A rename op would be a change to the server, the transcripts and the golden tests together, after v1.

**Credits.** Credits show `Engine.get_license_text()`, `Engine.get_copyright_info()` and `Engine.get_license_info()`, with the fonts' OFL text. `package.py` puts the same text in each desktop zip, and its tests change with it.

## 7. The phased plan

**Sequencing.** M8's track B owns `hub_panel.gd`, `shell.gd`, `builders_screen.gd`, `loading_screen.gd`, `results_panel.gd`, `match_found.gd`, `match_menu.gd` and `describe.gd`. F0 starts now. F1 and F2 start once the owner approves F0's slice, in new files behind `--front`, and touch none of the eight. The switch-over waits for M8 to merge, carries M8's level words into the mode chip and the Modes band, and ships F1 and F2 in one release, so no release has half a console. F3 follows, because it changes track B's loading, Match Found and results.

| Phase | Delivers | Verified by |
|---|---|---|
| **F0: the decisions, the look and the slice** (no router code) | Core-loop §5.1–5.9 rewritten: the screen map replaces the wells table, and "no separate mode-select screen" and "no settings beyond name and volume" are lifted. §3.6 (Builders stand on the Causeway, and the arched portrait goes), §3.7 (idle, ready and raise; still no walk cycle) and §5.6 (rivalry by placement, no "VS" anywhere) amended. This document adopted. AGENTS.md's screen paragraphs. The three TD menus looked at by hand. The colour script, the pinned sky, the `front` pieces, the wordmark, the window icon and the site's brand mark. The Causeway as MultiMeshes. **A rendered vertical slice of Home**, alone and with four, at 1280 × 720, 1920 × 1080 and both play-page frames, with the figures also rendered at the Builders size. The owner approves it before F1 starts | `names_check.py`, `asset check`, `art_front_pieces`; the slice's renders sent to the owner; the first `FRONTEND_FRAMES` numbers in Chrome on both GPUs |
| **F1: Home on the Causeway** (behind `--front`) | `Session/Stage` (one Causeway, the stations, marks, posed figures, nameplates); the router; the top bar (HOME, BUILDERS); the call-to-action cluster with the queue's key rules; Home alone (Invite, offline caretaker partners) and with a party; first-run defaults; the Modes band with the live preview; Join and Invite restyled; the leader's Remove on a nameplate (`PARTY remove`, which exists); the bus layout; `tr()` and AccessKit names on everything new; the play page's theatre layout | `front_no_console_outside_match`, `_route_for_every_state`, `_home_alone`, `_marks_follow_party`, `_mode_preview`, `_queue_keys_safe`, `_primary_fits`; `tests/web`; the §6.7 budget in Chrome; `home`, `home_party` and `modes` rendered and sent |
| **F2: Builders, Settings and the idle** (behind `--front`) | The Builders page (roster cards, the dolly, the towers on the road, kit cards, Main, Backup and Try with focus paths); Settings (audio on four buses; display with UI scale, quality and reduced motion; accessibility with text size and the sans option; controls as a read-only list; name outside a party); the Home menu with Quit on desktop; Credits; rigid skinning in the kit and an idle loop for every Builder, so no release shows a posed figure | `front_keyboard_reaches_every_route`, `_back_restores_focus`, `_text_fits`, `_rename_outside_party`; `art_builders_animated`. **Personas:** Teo, the Co-op Regular, plays one session alone in the browser (Home to a first match) and hosts the group's night in another. **Bar:** no remark that the menu is the match's interface; the solo screen does not read as "nobody came"; party, Ready, queue and Play again without confusion |
| **Switch-over** (after M8 merges) | `scenes/hub.tscn` takes the new tree; the console code in `shell.gd`, `hub_panel.gd` and `builders_screen.gd` goes; the Esc menu uses Settings (F10 opens it where the browser keeps Esc); `describe.gd` learns the layout; the scenarios that read wells or leave the queue with Esc are rewritten; the flag goes. F1 and F2 ship in this release | Every `flow_*`, `hub_*`, `race_*` and `view_duel_*` scenario; `flow_try_from_builders` and `flow_esc_menu_*`; `play_describe_says_what_shows`; the §6.7 budget again |
| **F3: the rituals** | Ready and raise actions; pennants, the countdown and the horn; Match Found restyled, with pennants on open marks and the 0.4 s key guard; Loading on the shared stage ("Walking out", strangers landing on their marks, the web's held beat); the Ebb (HUD hidden, the camera on the Holdfast, Enter and Esc, a bell per line) | `front_stage_persists_into_loading` with its hitch budget, `_stage_sleeps`, `_results_keys`; `race_loading_two_rows`, `race_results_two_teams`, `view_duel_*`; `loading`, `match_found` and `results` rendered. **Personas:** Teo and Yusra (a race and a duel) |
| **F4: sound and tide** | UI cues and ambience from `sfx.py`; music if decided; tide states by mode, the mirror among them; threaded preload on desktop; the world build split across frames on the web if the hitch budget needs it | `--determinism` (state and pixels); the §6.7 budget in Chrome on both GPUs; `asset check` |
| **F5: first launch and sign-off** | The arrival: the wordmark, then the camera rising onto the road, at most 3 s, played once per launch. Desktop plays it at once, and any input skips it. The web waits for the first gesture (the name prompt's Done, or "Click to enter"), which also starts the sound. The name on your nameplate; a pass at 200% text and in the safe area | **Persona:** a new fresh tester (Noa rotates out after three sessions), alone in the browser, from first launch. **Bar:** a running match within 30 s and a first tower within 60 s, without help; finds mode, level and Builder unaided. Then Halvard once: the front end must not slow a veteran down. Satisfaction in `lessons.md` must rise against the last hub sessions |

## 8. Risks and decisions for the owner

1. **How far into the world?** I recommend a 3D lobby with 2D plates, at the level of Overwatch's shipped one-hero 3D lobby and its 3D post-match accolades. I do not recommend menus that are themselves objects (Hearthstone) or walking (Deep Rock Galactic). Clicks and speed matter more than the metaphor (principles 3 and 6).
2. **Rewrite §5.1, and when.** I recommend lifting its three v1 rules: the shared console, no separate mode-select screen, and no settings beyond name and volume. They become shared materials, a Modes band and a full Settings sheet. Amend §3.6, §3.7 and §5.6 in the same change. Start F0 now and build F1 and F2 behind `--front` once the slice is approved. Only the switch-over waits for M8, so the two tracks never edit the same eight files.
3. **Music.** I recommend that F4 ship the ambience and the full UI cue set from `sfx.py`. They fit the pipeline, need no licence and are enough to make the Causeway feel like a place. Commission one short theme, with stems for the hub, the queue, Match Found and Loading, as a separate decision with its own budget. Never use stock music that other games also use. Without a theme, the front end is quieter than Blizzard's. Without the ambience and the cues, it is dead.
4. **Builder animation.** I recommend rigid skinning and puppet keyframes in the Blender scripts. The kit's `chibi` helper gains the option, and it suits chibi figures. The idle lands in F2 and ready and raise in F3. There is no walk cycle: the walk-out is the camera passing the crew while they turn to watch. Cheer and slump come after v1. Do not hide posed figures behind a bob in code. The idle fixes them, and it lands before the switch-over.
5. **Web performance.** Reforged's sluggish menus are the cautionary tale. I recommend making §6.7's absolute budget, measured in Chrome at the frame size, a release blocker. Low is the web default, with no automatic switch. The stage draws at 30 Hz while still and stops while the tab is hidden. Transitions take at most 200 ms, and camera moves never hold input. If the budget fails, cut the mirror reflection first, then the shadows, then the prop density, before the figures. The crew on the road is the point.
6. **Rivalry on screen.** Core-loop §5.6 says "No big VS" for a race's loading. I recommend keeping that rule on every screen and staging rivalry only by where the figures stand: two crews across a gap, two figures face to face. The alternative, a versus beat at Loading, would reverse §5.6.
7. **Names.** I recommend renaming only outside a party in v1, with nothing on the wire changing. A rename inside a party needs a new `PARTY` op, with the server, the transcripts and the golden tests. That can come after v1.
