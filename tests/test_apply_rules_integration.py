"""Integration tests for the rule engine through upsert_search_query.

Uses SQLite in-memory so rules are applied end-to-end without PostgreSQL.
"""

import pytest

from wind_vane.db.models import Forum, SearchQuery
from wind_vane.toolkits.crawlers.upsert import upsert_search_query
from sqlalchemy import select


@pytest.fixture
async def ptt_forum(db_session):
    forum = Forum(
        code="ptt", name_zh="PTT", base_url="https://www.ptt.cc",
        requires_js=False, rate_limit_per_min=60, is_active=True,
    )
    db_session.add(forum)
    await db_session.flush()
    return forum


async def _upsert(session, *, keyword="代購", forum_code="ptt", board_code="e-shopping",
                  posts_found=10, passed=5, avg_score=None, peak_count=0):
    return await upsert_search_query(
        session,
        keyword=keyword,
        forum_code=forum_code,
        board_code=board_code,
        operators=None,
        posts_found=posts_found,
        passed=passed,
        avg_score=avg_score,
        peak_count=peak_count,
    )


# ── R1 integration ────────────────────────────────────────────────────────────

async def test_r1c_peak_triggers_priority(db_session, ptt_forum):
    sq = await _upsert(db_session, peak_count=3)
    await db_session.flush()
    # Re-read from DB to get rule-applied values
    refreshed = (await db_session.execute(
        select(SearchQuery).where(SearchQuery.id == sq.id)
    )).scalar_one()
    assert refreshed.is_priority is True


async def test_r1a_requires_3_uses(db_session, ptt_forum):
    # First use: avg_score high but use_count=1 → should NOT be priority yet
    sq = await _upsert(db_session, avg_score=9.0, posts_found=5, passed=5)
    refreshed = (await db_session.execute(
        select(SearchQuery).where(SearchQuery.id == sq.id)
    )).scalar_one()
    assert refreshed.is_priority is False

    # Two more uses (total use_count=3) → should become priority
    for _ in range(2):
        sq = await _upsert(db_session, avg_score=9.0, posts_found=5, passed=5)

    refreshed = (await db_session.execute(
        select(SearchQuery).where(SearchQuery.id == sq.id)
    )).scalar_one()
    assert refreshed.is_priority is True


# ── R2 integration ────────────────────────────────────────────────────────────

async def test_r2c_zero_passed_flags_optimization(db_session, ptt_forum):
    # 3 uses with 0 passed → needs_optimization
    for _ in range(3):
        sq = await _upsert(db_session, posts_found=10, passed=0)
    refreshed = (await db_session.execute(
        select(SearchQuery).where(SearchQuery.id == sq.id)
    )).scalar_one()
    assert refreshed.needs_optimization is True


async def test_r2a_low_hit_rate_after_5_uses(db_session, ptt_forum):
    # 5 uses with 5% hit rate
    for _ in range(5):
        sq = await _upsert(db_session, posts_found=100, passed=5)
    refreshed = (await db_session.execute(
        select(SearchQuery).where(SearchQuery.id == sq.id)
    )).scalar_one()
    assert refreshed.needs_optimization is True


# ── R4 manual_override guard ──────────────────────────────────────────────────

async def test_r4_manual_override_blocks_rule_changes(db_session, ptt_forum):
    # Create and lock a query
    sq = await _upsert(db_session, posts_found=0, passed=0)
    sq.manual_override = True
    sq.is_priority = True  # manually set
    await db_session.flush()

    # More uses that would normally trigger needs_optimization
    for _ in range(3):
        await _upsert(db_session, posts_found=10, passed=0)

    refreshed = (await db_session.execute(
        select(SearchQuery).where(SearchQuery.id == sq.id)
    )).scalar_one()
    # is_priority must remain True (rule engine skipped)
    assert refreshed.is_priority is True
    assert refreshed.manual_override is True


# ── Unique constraint ─────────────────────────────────────────────────────────

async def test_same_key_accumulates_use_count(db_session, ptt_forum):
    for _ in range(4):
        sq = await _upsert(db_session)
    refreshed = (await db_session.execute(
        select(SearchQuery).where(SearchQuery.id == sq.id)
    )).scalar_one()
    assert refreshed.use_count == 4


async def test_different_board_creates_separate_row(db_session, ptt_forum):
    await _upsert(db_session, board_code="e-shopping")
    await _upsert(db_session, board_code="HelpBuy")
    count_result = await db_session.execute(
        select(SearchQuery).where(SearchQuery.keyword == "代購")
    )
    rows = count_result.scalars().all()
    assert len(rows) == 2
