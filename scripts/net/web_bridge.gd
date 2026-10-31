## The browser around the web build (design 6.8; docs/design/contract-m4.md): the tab's
## visibility, the title flash and the page's query string. On desktop every part of it is
## inert: is_web() is false, nothing is registered, query() is "".
##
## - Visibility: start() registers document's `visibilitychange` through
##   JavaScriptBridge.create_callback (the callback object is kept here, or the browser
##   loses it) and emits visibility_changed(hidden). The MatchClient answers with
##   VISIBILITY: hidden when the tab hides; on return catching_up while it runs the turns it
##   missed (more than Playout.CATCH_UP_TURNS behind), then shown. While the tab is hidden
##   the engine's loop stops, so nothing else happens until it returns. poll() reads
##   document.hidden once a second as well, in case an event was missed.
## - Title flash: flash_title(text) alternates the page title with `text` once a second
##   until stop_flash() or the tab is shown. The game runs in the `play/` page's iframe, so
##   it writes window.parent.document.title (same origin; its own title when there is no
##   parent). The beat is a JavaScript interval: the engine's loop sleeps in a hidden tab,
##   and a hidden tab is when the title is seen.
## - Query string: query("join") reads ?join= from the game's own page (play/index.html
##   forwards it into the iframe's src), else from the outer page.
##
## changed_to(hidden) is the event's handler, which a test can call as the browser would.
class_name WebBridge
extends RefCounted

## The tab was hidden (true) or shown again (false).
signal visibility_changed(hidden: bool)

## How often poll() reads the tab's visibility itself, in milliseconds.
const CHECK_MS := 1000
## The flash's JavaScript: one interval on the window, toggling the title it found.
const FLASH_JS := """(function (text) {
  var w = window;
  var doc = document;
  try { if (w.parent && w.parent !== w && w.parent.document) { doc = w.parent.document; } } catch (e) {}
  if (w.__groundholdFlash) { clearInterval(w.__groundholdFlash.timer); doc.title = w.__groundholdFlash.title; }
  var state = {title: doc.title, doc: doc, on: false};
  state.timer = setInterval(function () { state.on = !state.on; doc.title = state.on ? text : state.title; }, 1000);
  w.__groundholdFlash = state;
})(%s);"""
const STOP_JS := """(function () {
  var s = window.__groundholdFlash;
  if (s) { clearInterval(s.timer); s.doc.title = s.title; window.__groundholdFlash = null; }
})();"""
const QUERY_JS := """(function (key) {
  var v = new URLSearchParams(window.location.search).get(key);
  if (v === null) { try { v = new URLSearchParams(window.parent.location.search).get(key); } catch (e) {} }
  return v === null ? "" : String(v);
})(%s);"""

## The tab's visibility as last reported; false on desktop.
var hidden := false
## The text the title flashes with, "" while it does not.
var flashing := ""

var _document: JavaScriptObject
var _callback: JavaScriptObject
var _checked_at := -1


## Whether this is the web build (the only place the bridge does anything).
static func is_web() -> bool:
	return OS.has_feature("web")


## Starts listening for visibilitychange.
func start() -> void:
	if not is_web() or _callback != null:
		return
	_document = JavaScriptBridge.get_interface("document")
	if _document == null:
		return
	_callback = JavaScriptBridge.create_callback(_on_visibilitychange)
	_document.addEventListener("visibilitychange", _callback)
	hidden = bool(_document.hidden)


## Stops listening and stops any flash.
func stop() -> void:
	stop_flash()
	if _document != null and _callback != null:
		_document.removeEventListener("visibilitychange", _callback)
	_callback = null
	_document = null


## Flashes the page title with `text` until stop_flash() or the tab is shown.
func flash_title(text: String) -> void:
	if text == "" or text == flashing:
		return
	flashing = text
	if is_web():
		JavaScriptBridge.eval(FLASH_JS % JSON.stringify(text))


func stop_flash() -> void:
	if flashing == "":
		return
	flashing = ""
	if is_web():
		JavaScriptBridge.eval(STOP_JS)


## Once a frame with the host's clock in milliseconds: reads the tab's visibility once a
## second, in case the event was missed (the flash keeps its own time in the page).
func poll(now_ms: int) -> void:
	if _document == null or (_checked_at >= 0 and now_ms - _checked_at < CHECK_MS):
		return
	_checked_at = now_ms
	changed_to(bool(_document.hidden))


## The tab is hidden (true) or shown (false), as visibilitychange says: the signal once per
## change, and the flash stops as the tab is shown.
func changed_to(now_hidden: bool) -> void:
	if now_hidden == hidden:
		return
	hidden = now_hidden
	if not hidden:
		stop_flash()
	visibility_changed.emit(hidden)


## The outer page's query value for `key` ("" when absent, and always on desktop).
static func query(key: String) -> String:
	if not is_web() or key == "":
		return ""
	var value: Variant = JavaScriptBridge.eval(QUERY_JS % JSON.stringify(key))
	return str(value) if value != null else ""


func _on_visibilitychange(_args: Array) -> void:
	if _document != null:
		changed_to(bool(_document.hidden))
