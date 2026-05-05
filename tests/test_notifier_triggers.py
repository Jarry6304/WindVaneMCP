"""DB integration tests for notifier trigger functions."""

from datetime import UTC, datetime, timedelta

import pytest

from wind_vane.db.models import SearchQuery, SystemNotification
from wind_vane.notifier.main import (
    _find_rigid_queries,
    _is_quarterly_review_due,
    _is_rule_drift_triggered,
)


# ── _is_quarterly_review_due ──────────────────────────────────────────────────

async def test_quarterly_not_due_when_no_queries(db_session):
    result = await _is_quarterly_review_due(db_session)
    assert result is False


async def test_quarterly_not_due_when_data_too_recent(db_session):
    sq = SearchQuery(
        keyword="新查詢",
        forum_code="ptt",
        board_code="board",
        created_at=datetime.now(UTC) - timedelta(days=10),
        last_used_at=datetime.now(UTC),
    )
    db_session.add(sq)
    await db_session.flush()

    result = await _is_quarterly_review_due(db_session)
    assert result is False


async def test_quarterly_due_when_old_data_no_recent_notification(db_session):
    sq = SearchQuery(
        keyword="舊查詢",
        forum_code="ptt",
        board_code="board",
        created_at=datetime.now(UTC) - timedelta(days=91),
        last_used_at=datetime.now(UTC),
    )
    db_session.add(sq)
    await db_session.flush()

    result = await _is_quarterly_review_due(db_session)
    assert result is True


async def test_quarterly_not_due_when_recent_notification_exists(db_session):
    sq = SearchQuery(
        keyword="舊查詢",
        forum_code="ptt",
        board_code="board",
        created_at=datetime.now(UTC) - timedelta(days=95),
        last_used_at=datetime.now(UTC),
    )
    db_session.add(sq)

    notif = SystemNotification(
        notification_type="quarterly_review",
        triggered_at=datetime.now(UTC) - timedelta(days=5),
        email_to="test@example.com",
    )
    db_session.add(notif)
    await db_session.flush()

    result = await _is_quarterly_review_due(db_session)
    assert result is False


# ── _is_rule_drift_triggered ──────────────────────────────────────────────────

async def test_drift_not_triggered_when_few_needs_optimization(db_session):
    for i in range(5):
        db_session.add(SearchQuery(
            keyword=f"kw{i}", forum_code="ptt", board_code="b",
            needs_optimization=True, last_used_at=datetime.now(UTC),
        ))
    await db_session.flush()

    result = await _is_rule_drift_triggered(db_session)
    assert result is False


async def test_drift_triggered_when_20_needs_optimization_no_notification(db_session):
    for i in range(20):
        db_session.add(SearchQuery(
            keyword=f"kw{i}", forum_code="ptt", board_code=f"b{i}",
            needs_optimization=True, last_used_at=datetime.now(UTC),
        ))
    await db_session.flush()

    result = await _is_rule_drift_triggered(db_session)
    assert result is True


async def test_drift_not_triggered_when_recent_notification_exists(db_session):
    for i in range(20):
        db_session.add(SearchQuery(
            keyword=f"kw{i}", forum_code="ptt", board_code=f"b{i}",
            needs_optimization=True, last_used_at=datetime.now(UTC),
        ))
    db_session.add(SystemNotification(
        notification_type="rule_drift",
        triggered_at=datetime.now(UTC) - timedelta(days=3),
        email_to="test@example.com",
    ))
    await db_session.flush()

    result = await _is_rule_drift_triggered(db_session)
    assert result is False


# ── _find_rigid_queries ───────────────────────────────────────────────────────

async def test_find_rigid_excludes_non_override(db_session):
    db_session.add(SearchQuery(
        keyword="非鎖定",
        forum_code="ptt",
        board_code="b",
        manual_override=False,
        hit_rate=5.0,
        use_count=10,
        last_used_at=datetime.now(UTC) - timedelta(days=5),
    ))
    await db_session.flush()

    result = await _find_rigid_queries(db_session)
    assert result == []


async def test_find_rigid_excludes_old_last_used(db_session):
    db_session.add(SearchQuery(
        keyword="過期鎖定",
        forum_code="ptt",
        board_code="b",
        manual_override=True,
        hit_rate=5.0,
        use_count=10,
        last_used_at=datetime.now(UTC) - timedelta(days=45),
    ))
    await db_session.flush()

    result = await _find_rigid_queries(db_session)
    assert result == []


async def test_find_rigid_returns_declining_override_queries(db_session):
    db_session.add(SearchQuery(
        keyword="僵化查詢",
        forum_code="ptt",
        board_code="b",
        manual_override=True,
        hit_rate=8.0,
        use_count=10,
        last_used_at=datetime.now(UTC) - timedelta(days=5),
    ))
    await db_session.flush()

    result = await _find_rigid_queries(db_session)
    assert len(result) == 1
    assert result[0].keyword == "僵化查詢"


async def test_find_rigid_excludes_high_hit_rate(db_session):
    db_session.add(SearchQuery(
        keyword="高命中率鎖定",
        forum_code="ptt",
        board_code="b",
        manual_override=True,
        hit_rate=50.0,
        use_count=10,
        last_used_at=datetime.now(UTC) - timedelta(days=5),
    ))
    await db_session.flush()

    result = await _find_rigid_queries(db_session)
    assert result == []
