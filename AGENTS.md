# Working on Lantern Hollow

Godot 4.7.1, GDScript. The game runs from `scenes/main.tscn`; `scripts/main.gd` builds the hollow from
`data/hollow.txt` and wires the systems. Rules and balance live in `scripts/game.gd`.

Verify changes with godot-agent ([godot-agent-kit](https://github.com/saschb2b/godot-agent-kit): clone it and run
its `install.sh` for the CLI, the MCP server and the skill, which explains each command):

- `godot-agent check .` after editing scripts; `--resources` after editing scenes or `.tres` files.
- `godot-agent scenario . --headless` runs every gameplay test in about a second. Add a scenario in
  `tests/scenarios/` for each behaviour you change, and make sure it fails without your change.
- `godot-agent scenario . --determinism` before a release: every scenario twice, state and pixels compared.
- Balance changes: `bot_wins` must still win with half the lives left, `idle_player_loses` must still lose.
- `godot-agent run . --renderer gl_compatibility` shows the scene as the browser build draws it.

Assets are generated, never hand-edited: change the recipe in `art_src/models/` and rebuild with
`godot-agent asset mesh`, or the Blender build script in `art_src/blender/` (plants, rocks, creeps) and rebuild
with `godot-agent asset blender`; `godot-agent asset regen . <path>` rebuilds anything listed in
`asset_manifest.json`. The console art and the command icons come from the game's own painters,
`art_src/ui/console.py` and `art_src/ui/icons.py` (Pillow; their specs sit beside them), and `asset regen` reruns
them too. The HUD places itself by the `ui/console/layout.json` the painter writes. A creep's `stride` in `Game.CREEPS` is the walking speed its walk cycle was made for;
its build script prints the value.
`godot-agent asset check .` must stay clean. `godot-agent scenario . tools/media` re-renders the README's shots.
