"""Tests for pushes_history FIFO logic (spec section 3.3)."""

import pytest

from wind_vane.toolkits.crawlers.upsert import _update_pushes_history


def test_first_entry():
    h, d = _update_pushes_history(None, None, 10, "2026-05-01")
    assert h == "10"
    assert d == "2026-05-01"


def test_same_day_overwrites():
    h, d = _update_pushes_history("10", "2026-05-01", 25, "2026-05-01")
    assert h == "25"
    assert d == "2026-05-01"


def test_cross_day_no_change_skips():
    h, d = _update_pushes_history("10", "2026-05-01", 10, "2026-05-02")
    assert h == "10"
    assert d == "2026-05-01"


def test_cross_day_with_change_appends():
    h, d = _update_pushes_history("10", "2026-05-01", 25, "2026-05-02")
    assert h == "10;25"
    assert d == "2026-05-01;2026-05-02"


def test_fifo_caps_at_10():
    pushes = ";".join(str(i) for i in range(10))
    dates = ";".join(f"2026-04-{i+1:02d}" for i in range(10))
    h, d = _update_pushes_history(pushes, dates, 999, "2026-05-11")
    assert len(h.split(";")) == 10
    assert h.split(";")[-1] == "999"
    assert h.split(";")[0] == "1"  # oldest (0) evicted


def test_multiple_same_day_only_last_kept():
    h, d = _update_pushes_history("10", "2026-05-01", 15, "2026-05-01")
    assert h == "15"
    h, d = _update_pushes_history(h, d, 20, "2026-05-01")
    assert h == "20"
    assert len(h.split(";")) == 1


def test_empty_strings_treated_as_none():
    h, d = _update_pushes_history("", "", 5, "2026-05-01")
    assert h == "5"
    assert d == "2026-05-01"
