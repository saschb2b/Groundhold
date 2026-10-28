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
`godot-agent asset mesh`, or `godot-agent asset regen . <path>` for anything listed in `asset_manifest.json`.
`godot-agent asset check .` must stay clean. `godot-agent scenario . tools/media` re-renders the README's shots.
