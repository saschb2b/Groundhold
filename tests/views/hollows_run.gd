## A busy match on the match scene for `godot-agent run`, to see it and time its frames as
## the browser draws it (--renderer gl_compatibility):
##   godot-agent run . --scene res://tests/views/two_hollows_run.tscn --renderer gl_compatibility --frames 300
##   godot-agent run . --scene res://tests/views/one_hollow_run.tscn --renderer gl_compatibility --frames 300
## Two hollows (a Tide Race of two teams of one) or one (High Water, one team of two) with
## the same towers and the same waves: eight towers a seat, and from wave 7 on a wave called
## the moment a window opens, so creeps walk every road all the time. Nothing in the game
## reaches it.
##
## The run's own telemetry counts every frame, the first ones too, where this route builds
## the world a second time for two hollows (the scene stood with one before the race began;
## a race that starts with two builds it once, while it loads). So the driver times the
## frames itself from WARMUP on and prints, every
## REPORT_EVERY counted frames, the steady match so far:
##   HOLLOWS_FRAMES hollows=2 frames=240 draw_calls=p50/p95 primitives=p50/p95
##     frame_ms=p50/p95 physics_ms=p50/p95 creeps=N towers=N
## frame_ms is the wall clock between frames (the compatibility renderer draws on the main
## thread, so it holds the drawing too), physics_ms the physics frame's own time (the
## simulation's ticks and the views that follow them). The last line a run prints is its
## summary; compare two runs of the same length on the same renderer. On a software GPU
## (llvmpipe) frame_ms is the rasteriser's: draw calls and primitives carry over to a GPU,
## the milliseconds do not.
extends Node

const MAIN := "res://scenes/main.tscn"
## Each seat's towers, as [kit slot, x, z] on its own hollow (the band between the road's
## lower stretches and round the bends, where the plans build).
const BUILDS := [
	[0, 6, 11], [1, 8, 11], [2, 10, 11], [0, 12, 11],
	[1, 6, 12], [0, 10, 12], [2, 12, 12], [0, 14, 11],
]
## A second seat on the same hollow (one hollow) builds on these instead.
const BUILDS_BESIDE := [
	[0, 8, 5], [1, 10, 5], [2, 9, 5], [0, 14, 5],
	[1, 8, 7], [0, 10, 7], [2, 12, 7], [0, 14, 7],
]
## Frames after the match began before timing starts: the towers stand, the busy waves are
## on (from frame 20) and the world has been built for its hollows.
const WARMUP := 60
const REPORT_EVERY := 60

## How many hollows: 2 (a race's two teams of one) or 1 (one team of two).
@export var hollows := 2


func _ready() -> void:
	var driver := Driver.new()
	driver.name = "HollowsDriver"
	driver.hollows = hollows
	get_tree().root.add_child.call_deferred(driver)
	get_tree().change_scene_to_file.call_deferred(MAIN)


class Driver:
	extends Node

	var hollows := 2
	var _scene: Node
	var _frames := 0
	var _last_us := 0
	var _frame_us := PackedInt64Array()
	var _physics_us := PackedInt64Array()
	var _draws := PackedInt64Array()
	var _primitives := PackedInt64Array()

	func _physics_process(_delta: float) -> void:
		var scene := get_tree().current_scene
		if scene == null or not scene.has_method("begin") or not scene.is_node_ready():
			return
		if _scene != scene:
			_scene = scene
			_start(scene)
		_frames += 1
		if _frames == 20:
			# (the towers stand: on to the busy waves on every hollow)
			for h in Game.sim.hollows.size():
				Game.debug(SimTypes.DBG_WAVE, h, 6)
				Game.debug(SimTypes.DBG_COUNTDOWN, h, 30)
		elif _frames > 20:
			for h in Game.sim.hollows:
				if h.phase == SimTypes.PHASE_PREP and h.countdown_t > 30:
					Game.debug(SimTypes.DBG_COUNTDOWN, h.id, 30)

	func _process(_delta: float) -> void:
		var now := Time.get_ticks_usec()
		if _scene != null and _frames > WARMUP and _last_us > 0:
			_frame_us.append(now - _last_us)
			_physics_us.append(roundi(Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000000.0))
			_draws.append(int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)))
			_primitives.append(int(Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)))
			if _frame_us.size() % REPORT_EVERY == 0:
				_report()
		_last_us = now

	func _report() -> void:
		print(
			(
				"HOLLOWS_FRAMES hollows=%d frames=%d draw_calls=%s primitives=%s frame_ms=%s physics_ms=%s creeps=%d towers=%d"
				% [
					Game.sim.hollows.size(),
					_frame_us.size(),
					_spread(_draws, 1.0),
					_spread(_primitives, 1.0),
					_spread(_frame_us, 1000.0),
					_spread(_physics_us, 1000.0),
					Game.sim.creeps.size(),
					Game.sim.towers.size(),
				]
			)
		)

	## "p50/p95" of `values`, each divided by `unit` (1000 for microseconds as ms).
	@warning_ignore("integer_division")
	static func _spread(values: PackedInt64Array, unit: float) -> String:
		var sorted := values.duplicate()
		sorted.sort()
		var p50 := sorted[mini(sorted.size() - 1, sorted.size() / 2)] / unit
		var p95 := sorted[mini(sorted.size() - 1, sorted.size() * 95 / 100)] / unit
		if unit == 1.0:
			return "%d/%d" % [roundi(p50), roundi(p95)]
		return "%.1f/%.1f" % [p50, p95]

	func _start(scene: Node) -> void:
		var seats := [
			{"team": 0, "builder": "lamplighter"},
			{"team": 1 if hollows > 1 else 0, "builder": "lookout"},
		]
		scene.call("begin", "tide_race" if hollows > 1 else "high_water", seats, 1, LocalSequencer.new(2, 1), 1)
		var source: LocalSequencer = scene.get("source")
		for n in [1, 2]:
			Game.debug(SimTypes.DBG_GOLD, n, 5000)
			var cells: Array = BUILDS if hollows > 1 or n == 1 else BUILDS_BESIDE
			for b: Array in cells:
				source.submit_as(n, SimTypes.CMD_BUILD, b[0], b[1], b[2])
		print("HOLLOWS %d seats %d" % [Game.sim.hollows.size(), Game.sim.seats.size()])
