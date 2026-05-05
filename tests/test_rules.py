"""Tests for rule engine R1-R4."""

from decimal import Decimal

import pytest

from wind_vane.rules.engine import _check_r1, _check_r2, _check_r3
from wind_vane.db.models import SearchQuery
from datetime import UTC, datetime, timedelta


def make_sq(**kwargs) -> SearchQuery:
    defaults = dict(
        keyword="test",
        forum_code="ptt",
        board_code="e-shopping",
        use_count=0,
        total_posts_found=0,
        passed_posts=0,
        hit_rate=None,
        avg_score=None,
        peak_post_count=0,
        is_priority=False,
        needs_optimization=False,
        status="active",
        manual_override=False,
        last_used_at=datetime.now(UTC),
    )
    defaults.update(kwargs)
    sq = SearchQuery(**defaults)
    return sq


# R1 — is_priority

def test_r1a_avg_score_and_use_count():
    sq = make_sq(avg_score=Decimal("7.5"), use_count=3)
    assert _check_r1(sq) is True


def test_r1a_fails_low_use_count():
    sq = make_sq(avg_score=Decimal("8.0"), use_count=2)
    assert _check_r1(sq) is False


def test_r1b_hit_rate_and_use_count():
    sq = make_sq(hit_rate=Decimal("55.0"), use_count=5)
    assert _check_r1(sq) is True


def test_r1c_peak_post_count():
    sq = make_sq(peak_post_count=3)
    assert _check_r1(sq) is True


def test_r1_none_conditions():
    sq = make_sq()
    assert _check_r1(sq) is False


# R2 — needs_optimization

def test_r2a_low_hit_rate():
    sq = make_sq(hit_rate=Decimal("5.0"), use_count=5)
    assert _check_r2(sq) is True


def test_r2b_low_avg_score():
    sq = make_sq(avg_score=Decimal("2.0"), use_count=5)
    assert _check_r2(sq) is True


def test_r2c_zero_passed():
    sq = make_sq(passed_posts=0, use_count=3)
    assert _check_r2(sq) is True


def test_r2_not_enough_uses():
    sq = make_sq(hit_rate=Decimal("0.0"), use_count=2)
    assert _check_r2(sq) is False


# R3 — deprecated

def test_r3_old_query_deprecated():
    sq = make_sq(last_used_at=datetime.now(UTC) - timedelta(days=91))
    assert _check_r3(sq) == "deprecated"


def test_r3_recent_query_not_deprecated():
    sq = make_sq(last_used_at=datetime.now(UTC) - timedelta(days=30))
    assert _check_r3(sq) is None


def test_r3_no_last_used():
    sq = make_sq(last_used_at=None)
    assert _check_r3(sq) is None
