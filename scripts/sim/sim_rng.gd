## The match's own random number generator: xorshift32 with every step masked to 32
## bits, so every platform draws the same numbers. Its state is part of the checkpoint.
class_name SimRng
extends RefCounted

const MASK := 0xFFFFFFFF
## Xorshift never leaves zero, so a zero seed starts from this instead.
const ZERO_SEED := 0x9E3779B9

var state := ZERO_SEED


func _init(start := 1) -> void:
	state = start & MASK
	if state == 0:
		state = ZERO_SEED


## The next 32-bit number, 0 to 2^32 - 1.
func next_u32() -> int:
	var x := state
	x ^= (x << 13) & MASK
	x ^= x >> 17
	x ^= (x << 5) & MASK
	state = x
	return x


## A number from 0 to n - 1, for n > 0.
func below(n: int) -> int:
	return next_u32() % n
