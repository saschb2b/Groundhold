# Changelog

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
