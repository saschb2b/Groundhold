## Drives a Playout for the net_playout_* scenarios: frames with a fixed number of ticks'
## turns at hand, as a client sees them.
extends RefCounted


## Ticks a playout runs over `frames` frames while `available` ticks are always at hand.
static func run(playout: Playout, available: int, frames: int) -> int:
	var total := 0
	for i in frames:
		total += playout.ticks_for_frame(available)
	return total


## B for `count` round trips of `rtt_ms`, plus `jitter_ms` on every other one.
static func buffer(rtt_ms: int, jitter_ms: int, count := 10) -> int:
	var samples: Array[int] = []
	for i in count:
		samples.append(rtt_ms + (jitter_ms if i % 2 == 1 else 0))
	return Playout.buffer_for(samples, 50)
