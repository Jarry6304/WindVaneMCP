"""Tests for query_recommendations — priority query selection."""

from datetime import datetime

import pytest
from sqlalchemy import select

from wind_vane.db.models import SearchQuery
from wind_vane.toolkits.queries.query_recommendations import query_recommendations


@pytest.fixture
async def sq_db(db_session):
    rows = [
        SearchQuery(keyword="戰鬥陀螺代購", forum_code="bahamut", board_code="beyblade",
                    use_count=10, is_priority=True, status="active",
                    avg_score=8.5, hit_rate=60.0, peak_post_count=5,
                    last_used_at=datetime(2026, 5, 1)),
        SearchQuery(keyword="戰鬥陀螺 UX", forum_code="ptt", board_code="Toy_Hobby",
                    use_count=5, is_priority=True, status="active",
                    avg_score=7.2, hit_rate=45.0, peak_post_count=2,
                    last_used_at=datetime(2026, 4, 20)),
        SearchQuery(keyword="日本代購", forum_code="ptt", board_code="e-shopping",
                    use_count=3, is_priority=False, status="active",
                    avg_score=4.0, hit_rate=20.0, peak_post_count=0,
                    last_used_at=datetime(2026, 4, 10)),
        SearchQuery(keyword="戰鬥陀螺 deprecated", forum_code="ptt", board_code="HelpBuy",
                    use_count=2, is_priority=True, status="deprecated",
                    avg_score=6.0, hit_rate=30.0, peak_post_count=1,
                    last_used_at=datetime(2026, 3, 1)),
    ]
    db_session.add_all(rows)
    await db_session.flush()
    return db_session


async def test_returns_only_priority(sq_db):
    results = await query_recommendations(sq_db, topic="戰鬥陀螺")
    for r in results:
        assert r["forum_code"] in ("bahamut", "ptt")
    # non-priority "日本代購" should not appear
    assert not any(r["keyword"] == "日本代購" for r in results)


async def test_topic_filter_applied(sq_db):
    results = await query_recommendations(sq_db, topic="戰鬥陀螺")
    assert all("戰鬥陀螺" in r["keyword"] for r in results)


async def test_only_active_status(sq_db):
    results = await query_recommendations(sq_db, topic="戰鬥陀螺")
    assert not any(r["keyword"] == "戰鬥陀螺 deprecated" for r in results)


async def test_ordered_by_avg_score_desc(sq_db):
    results = await query_recommendations(sq_db, topic="戰鬥陀螺")
    scores = [r["avg_score"] for r in results if r["avg_score"] is not None]
    assert scores == sorted(scores, reverse=True)


async def test_limit_respected(sq_db):
    results = await query_recommendations(sq_db, topic="戰鬥陀螺", limit=1)
    assert len(results) == 1


async def test_no_match_returns_empty(sq_db):
    results = await query_recommendations(sq_db, topic="完全不存在的關鍵字XYZ")
    assert results == []


async def test_result_shape(sq_db):
    results = await query_recommendations(sq_db, topic="戰鬥陀螺", limit=1)
    r = results[0]
    for key in ("id", "keyword", "forum_code", "board_code", "use_count", "hit_rate", "avg_score", "peak_post_count"):
        assert key in r
