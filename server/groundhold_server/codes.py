"""Party codes (docs/design/core-loop.md §5.3): five symbols from an
alphabet with no vowels and none of `0 O 1 I L`, so a code never spells a
word and never reads two ways; shown as `K7Q-4M`.

A code is read leniently: lower case is upper case, spaces and hyphens are
ignored (`k7q-4m`, `K7Q 4M` and `K7Q4M` are one code). On the wire it is
the five symbols as ASCII bytes (`PARTY join`'s `code`, `PARTY_STATE`'s);
the server reads those leniently too. Five zero bytes in `PARTY_STATE` say
"in no party".
"""

import secrets

ALPHABET = "23456789BCDFGHJKMNPQRSTVWXYZ"
LENGTH = 5
NONE = bytes(LENGTH)        # PARTY_STATE's code when the player is in no party
_SYMBOLS = frozenset(ALPHABET)


def parse(text):
    """A typed or received code as its five wire bytes, or None where it is
    not one. Accepts str or bytes; lower case, spaces and hyphens are fine."""
    if isinstance(text, (bytes, bytearray)):
        try:
            text = bytes(text).decode("ascii")
        except UnicodeDecodeError:
            return None
    if not isinstance(text, str):
        return None
    symbols = "".join(text.split()).replace("-", "").upper()
    if len(symbols) != LENGTH or not set(symbols) <= _SYMBOLS:
        return None
    return symbols.encode("ascii")


def shown(code):
    """A code as players see it: `K7Q-4M`."""
    text = bytes(code).decode("ascii")
    return text[:3] + "-" + text[3:]


TRIES = 32


def generate(taken=(), rng=None, tries=TRIES):
    """A new code none of `taken` has, or None after `tries` draws that all
    clashed. `taken` is only asked `code in taken` (the lobby's party
    table, never copied or walked, so a draw costs the same however many
    parties a server holds). `rng` is anything with `choice` (a seeded
    random.Random in tests and transcripts); the system's cryptographic
    source by default, so codes cannot be predicted."""
    choose = (rng or secrets.SystemRandom()).choice
    # (28^5 = 17,210,368 codes and a server holds at most party_cap parties:
    # a clash is rare, 32 in a row all but impossible)
    for _ in range(tries):
        code = "".join(choose(ALPHABET) for _ in range(LENGTH)).encode("ascii")
        if code not in taken:
            return code
    return None
