# Groundhold: the world

The game is **Groundhold**. Chosen on 2026-10-29 from four finalists (Groundhold, Crosshold, Frayward, Stonesworn);
the other three packages and the naming research are not kept in the repository. This file is the umbrella every Builder, map and
mode hangs from. [`core-loop.md`](core-loop.md) still uses the old names until the rename pass; where they differ, this
file wins.

**Pitch.** Every land was raised out of the Tide, and the Tide wants it back; Builders from every shore hold one
another's ground.

**Premise.** Every land was raised by hand out of the Tide, the grey unmade water under all ground, and now and
then the Tide floods back for it, walking inland as wrack made from whatever it finds. Anyone who meets the flood
with a craft is a Builder, and at low water Builders cross the bared Flats to hold one another's ground.

**How it holds together.**

- **Why Builders gather.** There is no council and no list of members. The Tide is one water, so a land given up
  raises it on every other shore; the custom is "hold my ground in this flood and I will hold yours in the next".
- **Why waves come.** The Tide floods in surges, and each surge is a wave. The build window is slack water. A match
  is one flood rising to a crest.
- **Why lands of different ages meet.** At low water the Flats lie bare, like the Wadden Sea at ebb, and anyone can
  walk from one shore to another. The Tide keeps no calendar, so a bronze-age beekeeper and a steam-age
  engine-wright can share a road. No portals and no rifts are needed.
- **Race.** At spring tide the flood lies so still that it mirrors the land. Two crews hold a land and its
  reflection against the same surges. The mirror explains the shared seed and why the same Builder can be on both
  sides.
- **Duel.** A Builder who knows the Tide can hook wrack out of the passing drift, cork it, and loose it at a
  rival's shore. The two are rivals, not enemies.
- **New Builders.** Each one comes with a land, a craft and one line in the fable's formula: *"When the Tide came
  to ⟨land⟩, it came as ⟨wrack⟩. ⟨Builder⟩ answered with ⟨craft⟩."* The formula scales to the fiftieth Builder.
- **Motto.** A real Frisian dike proverb that German players will recognise: *Wer nicht will deichen, der muss
  weichen* ("who will not build must give way").

**A Builder is** a Builder. The fable's proverb is the reason for keeping the plain word.

**The antagonist: the Tide and its wrack.** The Tide is the world's oldest weather. It is not a people and holds no
grudge. It surfaces at a land's thin place (a sluice, a dry well, a cliff lip, a field gate) and takes its shape
from local stuff, always in the same five forms:

| Form | Check |
|---|---|
| Froth | Swarm |
| Runnel | Swift |
| Ballast | Armored |
| Spindrift | Winged |
| Crest | boss |

Every piece of wrack carries a sea-glass-teal waterline and foam-white eyes, so the enemy reads the same in every
land. Wrack falls apart into its stuff with a hiss of foam. There is no gore.

**Names**

| Part | Name | Note |
|---|---|---|
| Co-op (Vigil) | **High Water** | Holding a land through a whole flood; German *Hochwasser* |
| Race (Lantern Race) | **Tide Race** | A real sea term for a fast current through a strait |
| Duel (Rift Duel) | **Undertow** | The current that pulls toward the other side, which is what a send does |
| Hub | **the Causeway** | A raised road across the Flats where crews meet and set out. The hub's backdrop is the causeway at low water |
| Start of a map (rift gate) | **the Welling** | Where the Tide wells up |
| End of a map (hearth) | **the Holdfast** | What holds a land in place, as a kelp holdfast holds to a rock. Lives show as a floodmark climbing it |
| Menu lines | Match Found: *"The tide turns at Wickhollow"* · Loading: *"Walking out"* · Results: *"the Ebb"* | |

**The v1 Builders**

| Was | Now | Home | Identity |
|---|---|---|---|
| Tamsin Wick, the Lamplighter | **Tamsin Wick, the Lamplighter** | Wickhollow, a harvest valley | She keeps every lamp on the hollow road lit through Hollowtide, so that nobody walks it blind. |
| Edda Greyplume, the Owlwatch | **Edda Greyplume, the Lookout** | Fogholm, cliff isles above a sea of fog | Her people watched the fog-sea for a thousand years and called that enough; she left the perch to do something about it. |
| Ottilie Brass, the Bellfounder | **Ottilie Brass, the Bellfounder** | Brackwater, a marsh of dikes and windmills | She casts the storm bells that ring when the dikes are threatened, and a bell struck at the right moment stops wrack dead. |
| Hessel Bramble, the Beekeeper | **Sefa Amberwell, the Beekeeper** | Thousandwell, a red-rock city of stepped cisterns | She keeps bees in clay pipes on the rooftops; when the Tide came up the wells, only her bees would go down after it. |

Sefa replaces Hessel because a bramble is a northern hedgerow, and Thousandwell is a desert city. Her Skep becomes
a **Clay Hive**, with the same numbers.

**The autumn hollow as one map.** It becomes **Wickhollow**, Tamsin's home. The flood comes at harvest's end, and
the hollowfolk call it **Hollowtide** (as others say Yuletide; a wink at the real *Hallowtide*). They carve gourds
and light lamps along the road to see what walks it. It is the only land with lanterns, jack-o'-lanterns and
night. The Tide wells up through the sunken field gate, today's rift gate, and walks to the mill-house hearth,
Wickhollow's Holdfast. Its wrack is made from the harvest:

- Gourdlings (Froth)
- Scuttlers (Runnel)
- Thornbacks (Ballast)
- Duskmoths (Spindrift), whose orange glow is drawn to the hollow's lamps
- the Bristlesow (a half-flood Crest)
- the Hollowtide Crest

`data/hollow.txt`, the road, the gate model and the hearth model stay as they are.

**Rename map**

| Today | Groundhold |
|---|---|
| Lantern Hollow TD (title, `config/name`) | Groundhold |
| `lantern.saschb2b.com` | `groundhold.saschb2b.com` |
| `lantern_server` (`LANTERN_SERVER_*`, `lantern-hollow-server`) | `groundhold_server` (`GROUNDHOLD_SERVER_*`, `groundhold-server`) |
| `lantern-hollow.v1` | `groundhold.v1` |
| `/hollow` | `/causeway` |
| Vigil | High Water |
| Lantern Race | Tide Race |
| Rift Duel | Undertow |
| Rift Offer · rouse/loose · sealed lantern | the Drift · cork/uncork · a corked bottle |
| Last Light · Long Night · Nightfall | Seawall · the Surge · Spring Tide |
| rift gate | the Welling (Wickhollow's: the sunken field gate) |
| hearth | the Holdfast (Wickhollow's: the mill-house hearth) |
| Lantern Hollow (the map) | Wickhollow |
| Gourdling | Gourdling (kept; Wickhollow's Froth only) |
| Hollow King | the Hollowtide Crest |
| Lamplighter | Lamplighter (kept; Tamsin's alone) |
| Owlwatch | the Lookout |
| Bellfounder | Bellfounder (kept) |
| Beekeeper | Beekeeper (kept; now Sefa Amberwell) |

**Vetting and risks**

- **The name is green.** No game, app or US filing turned up on Steam, itch.io, Google Play or the App Store, and
  Trademarkia lists nothing.
- **Nearby names:** Groundless (a 2v2 arena game), Groundhound (an itch.io developer) and Groundhog. "Ground hold"
  is also an air-traffic term, which does no harm.
- **Language:** German speakers hear *Grund*. The name is easy to say in both languages, and the slug is clean.
- **It survives a change of lore.** If the Tide is ever cut, "holding ground" still fits any of the other three
  worlds.
- **Mode names were not vetted.**
  - *High Water* sits next to *Highwater* (Netflix, 2023), a tactics game set in a flooded world.
  - *Undertow* was a 2007 Xbox Live Arcade game.

  Both are mode labels, not brands.
- **The lore shares the crowded Tide vocabulary of 2026–27.** That is acceptable as long as no Tide- word reaches
  the logo.

---

## Changes that follow from the umbrella

These follow from the brief:

1. **Lanterns, gourds and night stay in the autumn map and on Tamsin Wick.** They leave the logo, the hub, the
   menus and every system that runs on every map: the sealed-lantern send, the "lantern colours" cosmetics (now
   pennant colours), and the Warden role icon, a "lantern on a pole", which becomes a wall-stone or an open gate.
2. **The hub's backdrop changes.** Today "the hollow at dusk" stays behind every screen (`core-loop.md` §5.1).
   Each package names its own hub place, and later the backdrop can show the selected Builder's home.
3. **Check icons stop being creep faces.** "The Gourdling's icon is the Swarm icon" only works on one map. Each
   package gives four glyphs (tide forms, plant forms, knots, mason's marks), with the local creep's portrait beside
   them.
4. **Owlwatch becomes a craft noun,** like the other three epithets. "Owlwatch" also sits close to *Overwatch*.
5. **The Hollow King is renamed.** "King" is Legion TD 2's word, "Hollow King" sits next to *Hollow Knight*, and
   "Hollow" leaves the brand. The id `hollow_king` touches `Game.CREEPS`, `art_src/blender/hollow_king.py`,
   `models/creeps/hollow_king.glb`, `ui/icons/hollow_king.png` and their `asset_manifest.json` entries. Its display
   name (`"name": "The Hollow King"` in `scripts/game.gd`) can change first.
6. **The autumn map keeps its creeps and files.** Gourdling, Scuttler, Thornback, Duskmoth and Bristlesow stay
   there. So do `data/hollow.txt`, `palettes/hollow.gpl` and the gate and hearth props: they belong to the map, and
   the map is still a hollow.
7. **The wave list is named after the map, not the mode.** `vigil12` becomes `hollow12`, since each future map
   brings its own list.
8. **One rule covers every identifier.** The slug is the lowercase name. It gives `<slug>.saschb2b.com`,
   `<slug>.v1`, `<slug>_server`, `<SLUG>_SERVER_*`, `<slug>-server`, `config/name="<Name>"` and, optionally, the
   repository name.
9. **The UI keeps "Builder", and the roles stay** (Warden, Marksman, Breaker, Sweeper). "Builder" is the genre's
   word, and the roles are jobs, not cultures. In-world words such as Mender or Sworn appear in lore lines.

## Still to check

- **Search the EU registers.** The vetting checked only the US register. The chosen name needs an EUIPO and DPMA
  search in classes 9, 28 and 41, and a check of the .com, .net and .de domains, which nobody has done yet.
- **Search the co-op mode name.** The in-world words in this note (modes, hub, places, creatures) are not brands
  and were not vetted, but the co-op mode name will appear on store pages and deserves a quick store search.
- **Rename in a fixed order:**
  1. display names, so players see the change;
  2. protocol and server ids, together with the M1 server work, because `lantern-hollow.v1` already appears in
     `shared/net/protocol.json` on the multiplayer worktree;
  3. asset ids last, since they touch `asset_manifest.json`.
