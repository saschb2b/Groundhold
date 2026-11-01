## Strategy camera: fixed pitch, pans over the map and zooms.
##   Arrow keys pan, mouse wheel zooms, middle mouse drags. Home shows my whole hollow (with
##   one hollow, the map). In a race (design 5.7) V jumps to the rival's hollow, keeping
##   the same view of it, and V again jumps back; the arrows pan over both.
class_name CameraRig
extends Camera3D

const PITCH := 56.0
const PAN_SPEED := 9.0
const MIN_DISTANCE := 8.0
const MAX_DISTANCE := 23.0

var focus := Vector3.ZERO
var distance := 16.0
var bounds := Rect2()
## Each hollow's ground on the board (x, z), and which one is mine.
var hollows: Array[Rect2] = []
var home := 0
var _overview_focus := Vector3.ZERO
var _overview_distance := 21.0
var _dragging := false


## `map_bounds` is the board the camera may look over; `hollow_rects` each hollow's part
## of it (none: the board is one hollow) and `my_hollow` the one it starts over and Home
## frames.
func setup(
	map_bounds: Rect2,
	start_focus: Vector3,
	start_distance: float,
	overview_distance: float,
	hollow_rects: Array[Rect2] = [],
	my_hollow := 0
) -> void:
	bounds = map_bounds
	hollows = hollow_rects.duplicate()
	if hollows.is_empty():
		hollows.append(bounds)
	home = clampi(my_hollow, 0, hollows.size() - 1)
	var mine := hollows[home]
	_overview_focus = Vector3(mine.get_center().x, 0, mine.get_center().y + 1.9)
	_overview_distance = overview_distance
	look_from(start_focus, start_distance)


## Moves the camera to look at a point from a distance (clamped to the map).
func look_from(at: Vector3, from_distance: float) -> void:
	distance = clampf(from_distance, MIN_DISTANCE, MAX_DISTANCE)
	focus = Vector3(
		clampf(at.x, bounds.position.x, bounds.end.x),
		0.0,
		clampf(at.z, bounds.position.y, bounds.end.y + 2.0)
	)
	var pitch := deg_to_rad(PITCH)
	position = focus + Vector3(0, sin(pitch), cos(pitch)) * distance
	look_at(focus, Vector3.UP)


## Home: my whole hollow.
func overview() -> void:
	look_from(_overview_focus, _overview_distance)


## The hollow the camera looks at now: the one whose ground is nearest its focus.
func viewing() -> int:
	var best := 0
	var nearest := INF
	for h in hollows.size():
		var r := hollows[h]
		var gap := maxf(0.0, maxf(r.position.x - focus.x, focus.x - r.end.x))
		if gap < nearest:
			nearest = gap
			best = h
	return best


## V: from my hollow to the rival's (the next one), from any other back to mine, the
## same spot of the other hollow at the same distance. False with one hollow.
func toggle_rival() -> bool:
	if hollows.size() < 2:
		return false
	var now := viewing()
	var to := (home + 1) % hollows.size() if now == home else home
	var shift := hollows[to].position - hollows[now].position
	look_from(focus + Vector3(shift.x, 0, shift.y), distance)
	return true


func _process(delta: float) -> void:
	var pan := Vector2(
		float(Input.is_key_pressed(KEY_RIGHT)) - float(Input.is_key_pressed(KEY_LEFT)),
		float(Input.is_key_pressed(KEY_DOWN)) - float(Input.is_key_pressed(KEY_UP))
	)
	if pan != Vector2.ZERO:
		# Pan faster when zoomed out, so the screen moves at a similar rate.
		var step := pan.normalized() * PAN_SPEED * delta * (distance / 16.0)
		look_from(focus + Vector3(step.x, 0, step.y), distance)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var button := event as InputEventMouseButton
		if button.button_index == MOUSE_BUTTON_WHEEL_UP and button.pressed:
			look_from(focus, distance - 1.5)
		elif button.button_index == MOUSE_BUTTON_WHEEL_DOWN and button.pressed:
			look_from(focus, distance + 1.5)
		elif button.button_index == MOUSE_BUTTON_MIDDLE:
			_dragging = button.pressed
	elif event is InputEventMouseMotion and _dragging:
		var motion := event as InputEventMouseMotion
		var scale := distance / 900.0
		look_from(focus - Vector3(motion.relative.x, 0, motion.relative.y) * scale * 1.6, distance)
	elif event is InputEventKey and (event as InputEventKey).pressed and not (event as InputEventKey).echo:
		match (event as InputEventKey).keycode:
			KEY_HOME:
				overview()
			KEY_V:
				if toggle_rival():
					get_viewport().set_input_as_handled()
