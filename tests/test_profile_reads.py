"""Synthetic profile research fixtures, not hardware validation."""

import pytest

from wendougee_data.profile_reads import decode_header, decode_stage, profile_request


def test_allowlist_rejects_arbitrary_and_write_ranges():
    assert profile_request(87, 2)[:6] == bytes.fromhex("010300570002")
    assert profile_request(2560, 7)[:6] == bytes.fromhex("01030a000007")
    for address, count in [(30, 1), (154, 1), (3048, 7), (2048, 125), (2218, 6)]:
        with pytest.raises(ValueError):
            profile_request(address, count)


def test_staged_decode_retains_uncertainty():
    assert decode_header([1, 1, 1, 1, 65, 0, 0])["target_ml"] == 65
    assert decode_stage([30, 90, 0, 0, 1, 0])["pressure_bar"] == 9
    with pytest.raises(ValueError):
        decode_header([1, 1, 0, 1, 65, 0, 0])
    with pytest.raises(ValueError):
        decode_stage([30, 90, 0, 0, 7, 0])


@pytest.mark.parametrize("words", [[], [1] * 6, [True] * 7, [65536] * 7])
def test_invalid_header_words_rejected(words):
    with pytest.raises(ValueError):
        decode_header(words)


def test_last_documented_stage_and_next_stage_boundary():
    for base in (2048, 2560):
        assert profile_request(base + 8 + 17 * 9, 6)[1] == 3
        with pytest.raises(ValueError):
            profile_request(base + 8 + 18 * 9, 6)
