<h1 align="center">Groundhold</h1>

<p align="center">
<b>Every land was raised out of the Tide, and the Tide wants it back; Builders from every shore hold one another's ground.</b><br>
A small tower defense: hold Wickhollow's winding road from the Welling to the Holdfast with three towers,
through eight waves and the Hollowtide Crest.
</p>

<p align="center">
<a href="https://saschb2b.github.io/Groundhold/play/"><b>Play in the browser</b></a>
&nbsp;·&nbsp;
<a href="https://saschb2b.github.io/Groundhold/">Project page</a>
&nbsp;·&nbsp;
<a href="#how-to-play">How to play</a>
&nbsp;·&nbsp;
<a href="CHANGELOG.md">Changelog</a>
</p>

<p align="center">
<a href="https://saschb2b.github.io/Groundhold/play/"><img src="docs/media/hero.webp" width="760" alt="Wave 7 in Wickhollow: creeps file along the road past arrow, cannon and frost towers. A low bronze console along the bottom holds the minimap, the selected Arrow Tower in an arched portrait with its stats, and the command card; gold, lives and the wave hang from a strip at the top right"></a>
</p>

<p align="center">
An angled camera over Wickhollow, a hand-painted harvest valley at dusk. A console with a minimap, a live portrait and a
command card, three towers with an upgrade each, and creeps that walk one road. About six minutes for a full game.
</p>

<h2 align="center">The towers</h2>

<table align="center">
<tr>
<td align="center" width="33%"><img src="ui/icons/arrow_tower.png" width="64" alt="Arrow Tower icon"><br><b>Arrow Tower · 40</b><br><sub>Quick bolts at the creep closest to the Holdfast. Upgrade for 60: twice the damage.</sub></td>
<td align="center" width="33%"><img src="ui/icons/cannon_tower.png" width="64" alt="Cannon Tower icon"><br><b>Cannon Tower · 70</b><br><sub>Slow shells that burst and hit every creep nearby. Upgrade for 80: a bigger blast.</sub></td>
<td align="center" width="33%"><img src="ui/icons/frost_tower.png" width="64" alt="Frost Spire icon"><br><b>Frost Spire · 60</b><br><sub>Ice shards that slow creeps by 45% for two seconds. Upgrade for 60: 60%.</sub></td>
</tr>
</table>

<p align="center">
<img src="docs/media/towers.webp" width="760" alt="Close up: a cannon tower firing beside two blue-roofed arrow towers, one upgraded with gold trim, and the selected frost spire with a floating crystal, shown in the console portrait with its damage, range, cooldown and slow">
</p>

<h2 align="center">What comes down the road</h2>

<table align="center">
<tr>
<td align="center" width="25%"><img src="ui/icons/gourdling.png" width="56" alt="Gourdling icon"><br><b>Gourdling</b><br><sub>Plenty of them, early and often.</sub></td>
<td align="center" width="25%"><img src="ui/icons/scuttler.png" width="56" alt="Scuttler icon"><br><b>Scuttler</b><br><sub>Fast and fragile. Frost buys time.</sub></td>
<td align="center" width="25%"><img src="ui/icons/thornback.png" width="56" alt="Thornback icon"><br><b>Thornback</b><br><sub>Slow, tough, costs two lives.</sub></td>
<td align="center" width="25%"><img src="ui/icons/hollowtide_crest.png" width="56" alt="Hollowtide Crest icon"><br><b>The Hollowtide Crest</b><br><sub>Wave 8. Ten lives if it gets through.</sub></td>
</tr>
</table>

<table align="center">
<tr>
<td align="center" width="50%"><img src="docs/media/combat.webp" width="380" alt="A few seconds of combat: arrows and cannon shells hit gourdlings, which burst into gold"><br><sub>Every kill pays gold. Each wave is 22% tougher than the last.</sub></td>
<td align="center" width="50%"><img src="docs/media/boss.webp" width="380" alt="The Hollowtide Crest, a crowned pumpkin with a glowing face, walking past the Welling; the console portrait shows it with its health, speed, bounty and the ten lives it would take"><br><sub>Click a creep to see its health in the console.</sub></td>
</tr>
</table>

## How to play

| Input | Does |
|---|---|
| <kbd>A</kbd> <kbd>C</kbd> <kbd>F</kbd> | Choose Arrow Tower, Cannon Tower or Frost Spire, then left-click a grass tile. The ghost turns red where you cannot build; hold <kbd>Shift</kbd> to keep placing |
| Click a tower | Select it and see its range. <kbd>U</kbd> upgrades, <kbd>S</kbd> sells for 70% of what you paid |
| Click a creep | Its health, speed, bounty and toll (the lives it would take) in the console |
| <kbd>N</kbd> | Ready: the war horn calls the next wave now; the seconds left are paid as gold |
| Arrow keys, wheel, middle-drag, minimap | Move and zoom the view; <kbd>Home</kbd> shows the whole map |
| Right click, <kbd>Esc</kbd> | Cancel building or the selection |

You start with 120 gold and 20 lives. A creep that reaches the Holdfast costs lives (the Hollowtide Crest costs ten).
Clearing a wave pays a bonus, and the next wave starts after ten seconds unless you are Ready sooner.

## Run it yourself

Godot 4.7.1:

```bash
godot --path .
```

The browser build is what [Pages](.github/workflows/pages.yml) publishes: the `Web` preset in
`export_presets.cfg`, single-threaded so it runs on any static host, with the page in `web/`.

```bash
godot --headless --path . --export-release "Web" build/web/index.html
```

### Two players on one computer

The multiplayer server is in `server/` (Python 3.11 or newer, nothing else). Milestone 1 has no lobby yet: the
server's dev match seats the first two games that join.

```bash
python3 server/main.py --dev-match classic:2 --host 127.0.0.1
godot --path . -- --join=127.0.0.1 --name=Tamsin     # first window
godot --path . -- --join=127.0.0.1 --name=Edda       # second window
```

Each window plays its own seat on the shared map: one pool of lives, your own gold, every kill's full bounty
to both, and the wave comes early only when both are Ready. Add `--bot` to a window to let the plan bot play
that seat. Another computer on your network joins with the address the server's banner prints (leave out
`--host 127.0.0.1` so it can come in).

## How it is made

Nothing here comes from another game. Every asset was generated for this game, and each one
can be rebuilt from its recipe (`asset_manifest.json` records how):

| Path | What |
|---|---|
| `data/hollow.txt` | The map, Wickhollow, one character per tile. The road is traced from `S` to `E`; edit it to redesign the level |
| `art_src/models/` | Recipes for the low-poly towers, props and projectiles: parts with sizes, bevels, colours and painted patterns |
| `art_src/blender/` | Blender build scripts for the trees, plants, rocks and the four rigged, animated creeps |
| `textures/foliage_*.png`, `materials/foliage.gdshader` | Painted needle, leaf, grass and fern cards, tinted per plant and swaying in the wind |
| `materials/painted.gdshader` | Paints bricks, stone, planks, shingles, metal and cloth onto every model, with lit edges and dark grout |
| `textures/`, `shaders/terrain.gdshader`, `shaders/water.gdshader` | Painted grass, meadow, path, sand, mud and rock textures, blended across the tiles with ragged edges; the pond's depth, foam and ripples |
| `art_src/ui/console.py`, `console.json` | The console's painter and its spec: wings, wells, the arched portrait window with its keystone, the rail, the resource strip, the end plate and the banner. `python3 art_src/ui/console.py` paints every piece in one material, a bronze rim over textured stone, at twice the layout's resolution (`"scale": 2`, drawn at half size, so it stays sharp on large screens), and writes `ui/console/layout.json`, the wells and windows the HUD places itself by. Needs only Pillow |
| `art_src/ui/icons.py`, `icons.json` | Frames the command icons as buttons from the model renders in `art_src/ui/renders/` (made with `godot-agent asset icon --size 216`), at twice their size on screen: `python3 art_src/ui/icons.py` |
| `models/`, `ui/icons/`, `ui/console/`, `sfx/` | The generated models, icons, painted console pieces and synthesized sounds |
| `asset_style.json`, `palettes/hollow.gpl` | The style every asset is checked against: triangle budgets, sizes, origins, palette, loudness |
| `scripts/` | The game: the rules as an integer simulation in `sim/` (tables in `sim/content.gd`), stepped from turns so every machine plays the same match; building, towers, creeps, projectiles, terrain and the console as its views |
| `server/`, `shared/net/` | The multiplayer server, a turn sequencer that never simulates, and the wire contract both sides read |
| `tests/scenarios/`, `tests/bot.gd` | Deterministic gameplay tests; a scripted player must win all eight waves and an idle one must lose; two networked clients must stay in step |
| `tools/net/smoke.py` | A whole match against the real server by two headless games, their state hashes compared |
| `tools/names_check.py` | Fails on the game's retired names anywhere in the tracked tree; CI runs it |
| `tools/media/` | The scenarios that stage the screenshots and the clip above |

The models, textures, icon renders and sounds were made with [godot-agent-kit](https://github.com/saschb2b/godot-agent-kit),
an agent toolkit for verifying Godot games and building their assets. It also runs the gameplay scenarios, on every push
before the site is published. The fonts are Noto Serif and Noto Serif Display under the SIL Open Font License
([fonts/OFL.txt](fonts/OFL.txt)).

## License

[MIT](LICENSE) for the code and the generated assets. The fonts keep their own license, the SIL Open Font License 1.1.
