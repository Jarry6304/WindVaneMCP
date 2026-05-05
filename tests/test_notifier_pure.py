"""Pure-function tests for wind_vane.notifier.main — no DB, no SMTP."""

from unittest.mock import MagicMock

import pytest

from wind_vane.db.models import SearchQuery, SystemNotification
from wind_vane.notifier.main import (
    _build_quarterly_email,
    _build_rigidity_email,
    _build_rule_drift_email,
    _is_hit_rate_declining,
)


# ── _is_hit_rate_declining ────────────────────────────────────────────────────

def _sq(hit_rate, use_count, manual_override=True):
    sq = MagicMock(spec=SearchQuery)
    sq.hit_rate = hit_rate
    sq.use_count = use_count
    sq.manual_override = manual_override
    return sq


def test_declining_when_low_hit_rate_and_enough_uses():
    assert _is_hit_rate_declining(_sq(hit_rate=10.0, use_count=5)) is True


def test_not_declining_when_hit_rate_above_threshold():
    assert _is_hit_rate_declining(_sq(hit_rate=25.0, use_count=10)) is False


def test_not_declining_when_use_count_too_low():
    assert _is_hit_rate_declining(_sq(hit_rate=5.0, use_count=4)) is False


def test_not_declining_when_hit_rate_exactly_20():
    # 20 is NOT < 20, so should not trigger
    assert _is_hit_rate_declining(_sq(hit_rate=20.0, use_count=10)) is False


def test_declining_when_hit_rate_zero():
    assert _is_hit_rate_declining(_sq(hit_rate=0.0, use_count=5)) is True


def test_none_hit_rate_treated_as_zero():
    assert _is_hit_rate_declining(_sq(hit_rate=None, use_count=5)) is True


# ── email builder functions ───────────────────────────────────────────────────

def test_quarterly_email_contains_key_phrase():
    notif = MagicMock(spec=SystemNotification)
    body = _build_quarterly_email(notif)
    assert "季度檢視" in body
    assert "tool_query_review" in body


def test_rule_drift_email_uses_filter_type_param():
    notif = MagicMock(spec=SystemNotification)
    body = _build_rule_drift_email(notif)
    assert "filter_type=" in body
    assert "filter=" not in body.replace("filter_type=", "")


def test_rule_drift_email_mentions_needs_optimization():
    notif = MagicMock(spec=SystemNotification)
    body = _build_rule_drift_email(notif)
    assert "needs_optimization" in body


def test_rigidity_email_lists_queries():
    queries = []
    for i in range(3):
        sq = MagicMock(spec=SearchQuery)
        sq.forum_code = "ptt"
        sq.board_code = f"board{i}"
        sq.keyword = f"查詢{i}"
        sq.hit_rate = 10.0
        queries.append(sq)

    body = _build_rigidity_email(queries)
    assert "查詢0" in body
    assert "查詢1" in body
    assert "查詢2" in body
    assert "命中率" in body


def test_rigidity_email_caps_at_10_queries():
    queries = []
    for i in range(15):
        sq = MagicMock(spec=SearchQuery)
        sq.forum_code = "ptt"
        sq.board_code = "b"
        sq.keyword = f"q{i}"
        sq.hit_rate = 5.0
        queries.append(sq)

    body = _build_rigidity_email(queries)
    # Queries 11-14 should not appear
    assert "q10" not in body
    assert "q0" in body
