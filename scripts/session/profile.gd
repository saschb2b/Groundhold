## The player's own choices, kept between launches in user://profile.cfg: the name the
## others see, the main and backup Builder, and the mode last chosen (design 5.2, 5.4).
## Everything is unlocked (design 10, adopted), so any Builder may be main or backup.
##
## Also the two rules every client applies the same way, so they live here as statics:
## which Builder a match fields for a chosen one (fielded) and which mode a chosen one
## plays (played_mode). The Lamplighter and the Lookout play as themselves and High Water
## by its own rules; a Builder whose towers have no views in this build yet (M6's) would
## be fielded as a Lamplighter, and a mode without a preset would play `classic`
## (contract-m2m3.md §1, §7).
class_name Profile
extends RefCounted

signal changed

const PATH := "user://profile.cfg"
## Shore words for a first name, map-neutral (world.md): every land meets the Tide.
const NAME_WORDS := [
	"Curlew", "Dunlin", "Plover", "Heron", "Tern", "Shingle",
	"Driftwood", "Marram", "Sandpiper", "Brine", "Saltreed", "Kittiwake",
]
## The modes the hub offers, in its top row (design 5.2); a third slot waits for Undertow.
const HUB_MODES := ["high_water", "tide_race", "undertow"]
const MODE_NAMES := {
	"classic": "Classic",
	"high_water": "High Water",
	"tide_race": "Tide Race",
	"undertow": "Undertow",
}

var player_name := ""
var main := "lamplighter"
var backup := "lookout"
var mode := "high_water"
## False until the player has confirmed a name (the first-launch prompt).
var named := false


## Reads the saved profile; a first launch gets a generated name, not yet confirmed.
static func load_saved() -> Profile:
	var profile := Profile.new()
	var cfg := ConfigFile.new()
	var found := cfg.load(PATH) == OK
	profile.player_name = str(cfg.get_value("profile", "name", ""))
	profile.named = found and valid_name(profile.player_name)
	if not profile.named:
		profile.player_name = generated_name(Identity.device_key())
	var saved_main := str(cfg.get_value("profile", "main", "lamplighter"))
	var saved_backup := str(cfg.get_value("profile", "backup", "lookout"))
	profile.main = saved_main if SimContent.BUILDERS.has(saved_main) else "lamplighter"
	profile.backup = saved_backup if SimContent.BUILDERS.has(saved_backup) else profile.main
	var saved_mode := str(cfg.get_value("profile", "mode", "high_water"))
	profile.mode = saved_mode if HUB_MODES.has(saved_mode) else "high_water"
	return profile


func save() -> void:
	var cfg := ConfigFile.new()
	if named:
		cfg.set_value("profile", "name", player_name)
	cfg.set_value("profile", "main", main)
	cfg.set_value("profile", "backup", backup)
	cfg.set_value("profile", "mode", mode)
	cfg.save(PATH)


## Takes a name the player typed; false (and nothing changes) when it breaks the rule.
func set_name(typed: String) -> bool:
	var clean := typed.strip_edges()
	if not valid_name(clean):
		return false
	player_name = clean
	named = true
	save()
	changed.emit()
	return true


## Main and backup: choosing the backup as main swaps them, so the two stay apart.
func set_main(builder: String) -> void:
	if not SimContent.BUILDERS.has(builder) or builder == main:
		return
	if builder == backup:
		backup = main
	main = builder
	save()
	changed.emit()


func set_backup(builder: String) -> void:
	if not SimContent.BUILDERS.has(builder) or builder == backup:
		return
	if builder == main:
		main = backup
	backup = builder
	save()
	changed.emit()


func set_mode(id: String) -> void:
	if not HUB_MODES.has(id) or id == mode:
		return
	mode = id
	save()
	changed.emit()


## A name the server takes: 1 to 16 letters, digits, spaces, _ or -, starting with a
## letter or digit (protocol.json name_pattern, Cyberworld's rule).
static func valid_name(text: String) -> bool:
	var pattern := RegEx.create_from_string("^" + str(NetProtocol.spec()["name_pattern"]) + "$")
	return pattern.search(text) != null and text.to_utf8_buffer().size() <= NetProtocol.number("name_bytes")


## A first name from the install's token: one shore word and two digits ("Curlew 42"), the
## same every launch until the player picks their own.
static func generated_name(token: PackedByteArray) -> String:
	var a := token[0] if token.size() > 0 else 0
	var b := token[1] if token.size() > 1 else 0
	return "%s %d" % [NAME_WORDS[a % NAME_WORDS.size()], 10 + b % 90]


## The Builder a match fields for `builder`: itself once its towers have views (their
## models in Game.TOWERS), otherwise the Lamplighter. Every client of one build decides
## alike, so a networked match stays in step.
static func fielded(builder: String) -> String:
	if not SimContent.BUILDERS.has(builder):
		return "lamplighter"
	for tower: String in SimContent.BUILDERS[builder]["towers"]:
		var shown: Dictionary = Game.TOWERS.get(tower, {})
		if not shown.has("model"):
			return "lamplighter"
	return builder


## The rules a chosen mode plays in this build: itself when SimContent.RULES has it,
## otherwise `classic` (the hub plays classic behind High Water until M2's preset).
static func played_mode(chosen: String) -> String:
	return chosen if SimContent.RULES.has(chosen) else "classic"


## The wire id (protocol.json "modes") of the rules a chosen mode plays.
static func wire_mode(chosen: String) -> int:
	return int(NetProtocol.spec()["modes"][played_mode(chosen)]["id"])


## Whether this build offers `chosen` at all (Tide Race comes with M6, Undertow with M7).
static func offers(chosen: String) -> bool:
	return chosen == "high_water" or SimContent.RULES.has(chosen)


static func mode_name(id: String) -> String:
	return str(MODE_NAMES.get(id, id.capitalize()))
