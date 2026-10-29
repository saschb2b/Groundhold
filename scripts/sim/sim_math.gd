## Integer helpers for the simulation: square roots and rounding without leaving ints.
## Every operand of / and % here is non-negative, so results never depend on how a
## platform rounds negative quotients.
@warning_ignore_start("integer_division")
class_name SimMath
extends RefCounted


## The largest r with r * r <= n, by Newton's method on ints (0 for n <= 0).
static func isqrt(n: int) -> int:
	if n <= 0:
		return 0
	var x := n
	var y := (x + 1) / 2
	while y < x:
		x = y
		y = (x + n / x) / 2
	return x


## a / b rounded up, for a >= 0 and b > 0.
static func ceil_div(a: int, b: int) -> int:
	return (a + b - 1) / b


## a * pm / 1000 rounded half up, for a >= 0 and pm >= 0.
static func per_mille(a: int, pm: int) -> int:
	return (a * pm + 500) / 1000
