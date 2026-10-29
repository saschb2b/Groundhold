## The client's socket (design 6.2): Godot's WebSocketPeer, one message per binary frame.
##
## The subprotocol is lantern-hollow.v1; text frames are refused both ways. The inbound
## buffer is raised to 1 MiB so a hidden browser tab can hold far more turns than it will
## ever be sent while its loop sleeps. There are no custom handshake headers and no
## heartbeat (neither works in web exports): liveness is the game's own PING.
##
## tests/net/fake_link.gd stands in for this class in the in-process tests, so whatever
## talks to a server sees one interface: open, poll, send, receive, close, status.
class_name NetLink
extends RefCounted

enum Status { IDLE, CONNECTING, OPEN, CLOSED }

const INBOUND_BYTES := 1048576
## Enough queued packets for the inbound buffer to fill before the count limit does.
const QUEUED_PACKETS := 65536

var url := ""
## Why the link closed, for the player: the close reason or a short description.
var close_reason := ""
var close_code := -1

var _socket: WebSocketPeer
var _status := Status.IDLE
var _inbox: Array[PackedByteArray] = []


func open(address_url: String) -> Error:
	url = address_url
	_socket = WebSocketPeer.new()
	_socket.supported_protocols = PackedStringArray([str(NetProtocol.spec()["subprotocol"])])
	_socket.inbound_buffer_size = INBOUND_BYTES
	_socket.max_queued_packets = QUEUED_PACKETS
	var tls: TLSOptions = TLSOptions.client() if url.begins_with("wss://") else null
	var err := _socket.connect_to_url(url, tls)
	if err != OK:
		_close_with("Could not open %s (%s)" % [url, error_string(err)])
		return err
	_status = Status.CONNECTING
	return OK


## Reads the socket: call once a frame. New messages wait in receive().
func poll() -> void:
	if _socket == null or _status == Status.CLOSED:
		return
	_socket.poll()
	var state := _socket.get_ready_state()
	if state == WebSocketPeer.STATE_OPEN and _status == Status.CONNECTING:
		_status = Status.OPEN
		if not OS.has_feature("web"):
			_socket.set_no_delay(true)
	while _socket.get_available_packet_count() > 0:
		var packet := _socket.get_packet()
		if _socket.was_string_packet():
			_socket.close(1003, "Binary frames only")
			_close_with("The server sent text")
			return
		_inbox.append(packet)
	if state == WebSocketPeer.STATE_CLOSED:
		close_code = _socket.get_close_code()
		var reason := _socket.get_close_reason()
		_close_with(reason if reason != "" else "The connection closed")


## Sends one message as one binary frame; false when the link is not open.
func send(message: PackedByteArray) -> bool:
	if _status != Status.OPEN:
		return false
	return _socket.send(message, WebSocketPeer.WRITE_MODE_BINARY) == OK


## The messages that arrived since the last call, oldest first.
func receive() -> Array[PackedByteArray]:
	var out := _inbox
	_inbox = []
	return out


func close(code := 1000, reason := "") -> void:
	if _socket and _status in [Status.CONNECTING, Status.OPEN]:
		_socket.close(code, reason)
		_socket.poll()
	_close_with(reason if reason != "" else "Closed")


func status() -> Status:
	return _status


func is_open() -> bool:
	return _status == Status.OPEN


func is_closed() -> bool:
	return _status == Status.CLOSED


## Bytes written but not yet sent.
func outbound_bytes() -> int:
	return _socket.get_current_outbound_buffered_amount() if _socket else 0


func _close_with(reason: String) -> void:
	if _status == Status.CLOSED:
		return
	_status = Status.CLOSED
	close_reason = reason
