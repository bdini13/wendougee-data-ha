"""Narrow research-only reads; not installed HA actions or executable recipes.

Facts: pinned GeeFlow register/compiler map and LitaLite profile layout. Only
active/bound staged banks are considered; no speculative extra slots or mode 4.
Decoding describes stored words, not proven machine execution semantics.
"""

from .modbus import build_read_holding_registers_request

BANKS = (2048, 2560)
PROFILE_READS = frozenset(
    [(87, 2)]
    + [(base, 7) for base in BANKS]
    + [(base + 8 + 9 * stage, 6) for base in BANKS for stage in range(18)]
)


def profile_request(address: int, count: int) -> bytes:
    """Construct FC03 only, restricted to two documented banks and selectors."""
    if (address, count) not in PROFILE_READS:
        raise ValueError("Not an allowlisted profile read")
    return build_read_holding_registers_request(address, count)


def _words(words: list[int], count: int) -> None:
    if len(words) != count or any(
        type(w) is not int or not 0 <= w <= 65535 for w in words
    ):
        raise ValueError("Invalid register words")


def decode_header(words: list[int]) -> dict:
    """Decode only a recognizable staged header; reject direct layout."""
    _words(words, 7)
    if any(words[i] not in (0, 1) for i in (0, 1, 2, 3, 6)) or words[2] != 1:
        raise ValueError("Unsupported profile header/layout")
    return {
        "finish_kind": "volume" if words[0] else "weight",
        "target_ml": words[4],
        "target_g": words[5],
        "mode_flag": words[1],
        "variable_flow_flag": words[3],
        "auto_link_flag": words[6],
    }


def decode_stage(words: list[int]) -> dict:
    """Decode raw staged parameters without declaring safe execution bounds."""
    _words(words, 6)
    if words[4] not in (0, 1) or words[5] not in (0, 1):
        raise ValueError("Unknown stage flags")
    return {
        "time_seconds": words[0],
        "pressure_bar": words[1] / 10,
        "flow_ml_s": words[2] / 10,
        "wait_seconds": words[3],
        "last": bool(words[4]),
        "priority": "flow" if words[5] else "pressure",
    }
