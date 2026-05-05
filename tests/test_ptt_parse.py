"""Tests for PTT-specific parsing helpers."""

import pytest

from wind_vane.toolkits.crawlers.ptt_search import _parse_push


@pytest.mark.parametrize("text,expected", [
    ("爆", (100, 0)),
    ("X", (0, 100)),
    ("XX", (0, 100)),
    ("50", (50, 0)),
    ("0", (0, 0)),
    ("-20", (0, 20)),
    ("abc", (0, 0)),
    ("", (0, 0)),
])
def test_parse_push(text, expected):
    assert _parse_push(text) == expected
