## The levels' rules as MatchRules builds them (M8, contract-m8 §3), for net_* scenarios: every
## mode of protocol.json at every level, held to the rules track's table by the numbers.
extends RefCounted


## "<mode> <level>: <what differs>" for each mode and level whose rules do not carry their
## level's numbers (MatchRules.level_problem against SimContent.DIFFICULTIES); [] when all
## do. `fallback`: the rules the fallback lays (MatchRules.laid_over) instead of of()'s.
static func problems(fallback := false) -> Array:
	var out := []
	var modes: Dictionary = NetProtocol.spec()["modes"]
	var levels: Dictionary = NetProtocol.spec()["difficulties"]
	for mode: String in modes:
		if not SimContent.RULES.has(mode):
			continue
		for level: String in levels:
			var rules := (
				MatchRules.laid_over(SimContent.rules(mode), MatchRules.level_of(mode, level), SimContent.DIFFICULTIES)
				if fallback
				else MatchRules.of(mode, level)
			)
			var problem := MatchRules.level_problem(rules)
			if problem != "":
				out.append("%s %s: %s" % [mode, level, problem])
	return out
