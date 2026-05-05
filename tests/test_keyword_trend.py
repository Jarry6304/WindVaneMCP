"""Tests for keyword_trend — mocked to avoid PostgreSQL-specific functions."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from wind_vane.toolkits.queries.keyword_trend import keyword_trend


def _make_row(period_str: str, post_count: int, avg_pushes: float):
    row = MagicMock()
    row.period = datetime.fromisoformat(period_str)
    row.post_count = post_count
    row.avg_pushes = avg_pushes
    return row


async def _run(rows, granularity="week", weeks=4):
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = rows
    mock_session.execute.return_value = mock_result
    return await keyword_trend(mock_session, "代購", granularity=granularity, weeks=weeks)


async def test_returns_formatted_list():
    rows = [_make_row("2026-04-28", 5, 15.0), _make_row("2026-05-05", 3, 8.0)]
    result = await _run(rows)
    assert len(result) == 2


async def test_period_is_iso_string():
    rows = [_make_row("2026-05-01", 2, 10.0)]
    result = await _run(rows)
    assert isinstance(result[0]["period"], str)
    assert "2026" in result[0]["period"]


async def test_post_count_and_avg_pushes():
    rows = [_make_row("2026-05-01", 7, 25.5)]
    result = await _run(rows)
    assert result[0]["post_count"] == 7
    assert result[0]["avg_pushes"] == 25.5


async def test_empty_result():
    result = await _run([])
    assert result == []


async def test_none_avg_pushes_returns_zero():
    row = MagicMock()
    row.period = datetime(2026, 5, 1)
    row.post_count = 3
    row.avg_pushes = None
    result = await _run([row])
    assert result[0]["avg_pushes"] == 0.0


async def test_day_granularity_executes():
    # Just verify the function runs without error for 'day' granularity
    result = await _run([], granularity="day", weeks=2)
    assert result == []
