"""Tests for query_review and query_review_update."""

from datetime import datetime

import pytest
from sqlalchemy import select

from wind_vane.db.models import SearchQuery
from wind_vane.toolkits.queries.query_review import query_review, query_review_update


@pytest.fixture
async def review_db(db_session):
    rows = [
        SearchQuery(keyword="優化中A", forum_code="ptt", board_code="e-shopping",
                    needs_optimization=True, status="active", use_count=5,
                    last_used_at=datetime(2026, 5, 5)),
        SearchQuery(keyword="優化中B", forum_code="bahamut", board_code="beyblade",
                    needs_optimization=True, status="active", use_count=3,
                    last_used_at=datetime(2026, 5, 1)),
        SearchQuery(keyword="廢棄查詢", forum_code="ptt", board_code="Beauty",
                    needs_optimization=False, status="deprecated", use_count=2,
                    last_used_at=datetime(2026, 3, 1)),
        SearchQuery(keyword="正常查詢", forum_code="dcard", board_code="makeup",
                    needs_optimization=False, status="active", use_count=8,
                    last_used_at=datetime(2026, 5, 4)),
    ]
    db_session.add_all(rows)
    await db_session.flush()
    return db_session


# ── query_review filters ──────────────────────────────────────────────────────

async def test_needs_optimization_filter(review_db):
    results = await query_review(review_db, filter_type="needs_optimization")
    assert len(results) == 2
    assert all(r["needs_optimization"] is True for r in results)


async def test_deprecated_filter(review_db):
    results = await query_review(review_db, filter_type="deprecated")
    assert len(results) == 1
    assert results[0]["keyword"] == "廢棄查詢"


async def test_all_filter_returns_all(review_db):
    results = await query_review(review_db, filter_type="all")
    assert len(results) == 4


async def test_ordered_by_last_used_desc(review_db):
    results = await query_review(review_db, filter_type="needs_optimization")
    keywords = [r["keyword"] for r in results]
    assert keywords[0] == "優化中A"  # May 5 > May 1


async def test_limit_respected(review_db):
    results = await query_review(review_db, filter_type="all", limit=2)
    assert len(results) == 2


async def test_result_shape(review_db):
    results = await query_review(review_db, filter_type="needs_optimization", limit=1)
    r = results[0]
    for key in ("id", "keyword", "forum_code", "board_code", "use_count",
                "hit_rate", "avg_score", "status", "needs_optimization",
                "manual_override", "optimization_note"):
        assert key in r


# ── query_review_update ───────────────────────────────────────────────────────

async def test_update_sets_manual_override(review_db):
    sq = (await review_db.execute(
        select(SearchQuery).where(SearchQuery.keyword == "優化中A")
    )).scalar_one()

    await query_review_update(review_db, query_id=sq.id, reason="LLM 判斷效果差")

    review_db.expire(sq)
    await review_db.refresh(sq)
    assert sq.manual_override is True
    assert sq.override_reason == "LLM 判斷效果差"
    assert sq.override_by == "llm"


async def test_update_status(review_db):
    sq = (await review_db.execute(
        select(SearchQuery).where(SearchQuery.keyword == "優化中B")
    )).scalar_one()

    await query_review_update(review_db, query_id=sq.id, reason="棄用", status="deprecated")

    await review_db.refresh(sq)
    assert sq.status == "deprecated"


async def test_update_is_priority(review_db):
    sq = (await review_db.execute(
        select(SearchQuery).where(SearchQuery.keyword == "正常查詢")
    )).scalar_one()

    await query_review_update(review_db, query_id=sq.id, reason="人工確認效果好", is_priority=True)

    await review_db.refresh(sq)
    assert sq.is_priority is True


async def test_update_needs_optimization_false(review_db):
    sq = (await review_db.execute(
        select(SearchQuery).where(SearchQuery.keyword == "優化中A")
    )).scalar_one()

    await query_review_update(
        review_db, query_id=sq.id, reason="已修正", needs_optimization=False
    )

    await review_db.refresh(sq)
    assert sq.needs_optimization is False
    assert sq.manual_override is True


async def test_update_returns_correct_id(review_db):
    sq = (await review_db.execute(
        select(SearchQuery).where(SearchQuery.keyword == "優化中A")
    )).scalar_one()

    result = await query_review_update(review_db, query_id=sq.id, reason="test")
    assert result["updated"] == sq.id
