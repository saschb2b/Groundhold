## Nearby servers (design 5.3 and 6.2): a LAN server says it is there once a second with
## a small UDP datagram to port 8767, and the desktop game lists the servers it hears.
##
##   4 bytes "GHB1" | u16 protocol version | u16 WebSocket port | u8 open parties |
##   u8 length + UTF-8 server name           (big-endian)
##
## Servers are keyed by the sender's address and the port; only those speaking this
## game's protocol version are listed, and one silent for 3 s drops off. Only one game
## per computer can bind the port; a second window uses the address field. The browser
## has no UDP, so it never listens. inject() hands a datagram in without a socket, so a
## scenario tests discovery without a network; `clock` (milliseconds) lets it count frames.
class_name BeaconListener
extends RefCounted

signal changed

const MAGIC := "GHB1"
const SILENT_MS := 3000

## The UDP socket, or null while not listening.
var socket: PacketPeerUDP
## Milliseconds of a monotonic clock; Time.get_ticks_msec unless a test counts frames.
var clock := Callable()
## "address:port" -> {"address", "port", "name", "parties", "version", "heard"}
var _servers := {}
## Datagrams refused: wrong magic, wrong length, or another protocol version.
var refused := 0


## Binds the beacon port; false where that cannot be (the browser, or another game on this
## computer holds it).
func listen() -> bool:
	if OS.has_feature("web") or socket != null:
		return socket != null
	var udp := PacketPeerUDP.new()
	if udp.bind(NetProtocol.number("beacon_port"), "*") != OK:
		return false
	socket = udp
	return true


func stop() -> void:
	if socket:
		socket.close()
	socket = null


## Reads what arrived and forgets servers gone silent: once a frame while listed.
func poll() -> void:
	while socket and socket.get_available_packet_count() > 0:
		var bytes := socket.get_packet()
		inject(bytes, socket.get_packet_ip())
	var now := _now()
	var gone := []
	for key: String in _servers:
		if now - int(_servers[key]["heard"]) >= SILENT_MS:
			gone.append(key)
	for key: String in gone:
		_servers.erase(key)
	if not gone.is_empty():
		changed.emit()


## Takes one datagram as if it came from `ip`; true when it lists (or refreshes) a server.
func inject(bytes: PackedByteArray, ip: String) -> bool:
	var beacon := parse(bytes)
	if beacon.is_empty() or int(beacon["version"]) != NetProtocol.number("version"):
		refused += 1
		return false
	var key := "%s:%d" % [ip, int(beacon["port"])]
	var fresh := not _servers.has(key)
	beacon["address"] = ip
	beacon["heard"] = _now()
	_servers[key] = beacon
	if fresh:
		changed.emit()
	return true


## The servers heard, sorted by name then address: each {"address", "port", "name",
## "parties", "join"}, where "join" is what the Join panel connects to.
func servers() -> Array:
	var out := []
	for key: String in _servers:
		var s: Dictionary = _servers[key]
		var port := int(s["port"])
		var join := str(s["address"])
		if port != NetProtocol.number("port"):
			join = "%s:%d" % [join, port]
		out.append(
			{
				"address": s["address"],
				"port": port,
				"name": s["name"],
				"parties": s["parties"],
				"join": join,
			}
		)
	out.sort_custom(
		func(a: Dictionary, b: Dictionary) -> bool:
			return [str(a["name"]), str(a["join"])] < [str(b["name"]), str(b["join"])]
	)
	return out


## A datagram's fields, or {} when it is not a beacon.
static func parse(bytes: PackedByteArray) -> Dictionary:
	if bytes.size() < 10 or bytes.slice(0, 4).get_string_from_ascii() != MAGIC:
		return {}
	var reader := StreamPeerBuffer.new()
	reader.data_array = bytes
	reader.big_endian = true
	reader.seek(4)
	var version := reader.get_u16()
	var port := reader.get_u16()
	var parties := reader.get_u8()
	var length := reader.get_u8()
	if bytes.size() != 10 + length or length > NetProtocol.number("server_name_bytes"):
		return {}
	var name := bytes.slice(10, 10 + length).get_string_from_utf8()
	if port == 0 or (length > 0 and name == ""):
		return {}
	return {"version": version, "port": port, "parties": parties, "name": name}


## A beacon's bytes, as the server sends it (for tests and tools).
static func datagram(version: int, port: int, parties: int, name: String) -> PackedByteArray:
	var out := StreamPeerBuffer.new()
	out.big_endian = true
	out.put_data(MAGIC.to_ascii_buffer())
	out.put_u16(version)
	out.put_u16(port)
	out.put_u8(parties)
	var text := name.to_utf8_buffer()
	out.put_u8(text.size())
	out.put_data(text)
	return out.data_array


func _now() -> int:
	return int(clock.call()) if clock.is_valid() else Time.get_ticks_msec()
