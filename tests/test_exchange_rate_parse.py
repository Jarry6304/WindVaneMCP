"""Unit tests for exchange_rate CSV parsing (no HTTP calls)."""

import pytest

from wind_vane.toolkits.crawlers.exchange_rate import _parse_jpy_row

# Realistic BOT CSV row: 幣別, cash_buy, cash_sell, spot_buy, spot_sell, ...
_JPY_ROW = ["日幣 (JPY)", "0.2030", "0.2150", "0.2080", "0.2100", "0.2100", "0.2095"]
_USD_ROW = ["美金 (USD)", "30.80", "31.30", "31.00", "31.10"]
_HEADER_ROW = ["幣別", "現金買入", "現金賣出", "即期買入", "即期賣出"]
_EMPTY_ROW: list[str] = []


def test_jpy_row_returns_dict():
    result = _parse_jpy_row(_JPY_ROW)
    assert result is not None
    assert result["currency"] == "JPY"


def test_mid_rate_is_average_of_spot():
    result = _parse_jpy_row(_JPY_ROW)
    assert result is not None
    expected_mid = round((0.2080 + 0.2100) / 2, 6)
    assert result["rate"] == expected_mid


def test_spot_buy_and_sell_included():
    result = _parse_jpy_row(_JPY_ROW)
    assert result["spot_buy"] == 0.2080
    assert result["spot_sell"] == 0.2100


def test_usd_row_returns_none():
    assert _parse_jpy_row(_USD_ROW) is None


def test_header_row_returns_none():
    assert _parse_jpy_row(_HEADER_ROW) is None


def test_empty_row_returns_none():
    assert _parse_jpy_row(_EMPTY_ROW) is None


def test_short_row_returns_none():
    assert _parse_jpy_row(["日幣 (JPY)", "0.20"]) is None


def test_jpy_identifier_variants():
    for currency in ["JPY (日幣)", "日圓 (JPY)", "日幣"]:
        row = [currency, "0.20", "0.21", "0.205", "0.208"]
        assert _parse_jpy_row(row) is not None


def test_invalid_float_returns_none():
    bad_row = ["日幣 (JPY)", "0.20", "0.21", "N/A", "N/A"]
    assert _parse_jpy_row(bad_row) is None


def test_captured_at_present():
    result = _parse_jpy_row(_JPY_ROW)
    assert result is not None
    assert "captured_at" in result
    assert "T" in result["captured_at"]  # ISO8601
