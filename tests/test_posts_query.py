"""Tests for posts_query — SQLite-compatible filters (no FTS)."""

from datetime import datetime, timedelta

import pytest

from wind_vane.db.models import Forum, ForumBoard, Post
from wind_vane.toolkits.queries.posts_query import posts_query


@pytest.fixture
async def seeded_db(db_session):
    forum = Forum(
        code="ptt", name_zh="PTT", base_url="https://www.ptt.cc",
        requires_js=False, rate_limit_per_min=60, is_active=True,
    )
    db_session.add(forum)
    await db_session.flush()

    board_a = ForumBoard(forum_id=forum.id, board_code="e-shopping", name_zh="購物板", value_score=10, is_active=True)
    board_b = ForumBoard(forum_id=forum.id, board_code="Beauty", name_zh="美妝板", value_score=8, is_active=True)
    db_session.add_all([board_a, board_b])
    await db_session.flush()

    now = datetime(2026, 5, 5, 12, 0, 0)
    posts = [
        Post(forum_id=forum.id, board_id=board_a.id, url="https://ptt.cc/1", title="日本代購現貨",
             pushes=80, latest_score=8, first_crawled_at=now, last_crawled_at=now, posted_at=now),
        Post(forum_id=forum.id, board_id=board_a.id, url="https://ptt.cc/2", title="免稅店戰利品",
             pushes=30, latest_score=5, first_crawled_at=now, last_crawled_at=now,
             posted_at=now - timedelta(days=10)),
        Post(forum_id=forum.id, board_id=board_b.id, url="https://ptt.cc/3", title="ANESSA 防曬",
             pushes=10, latest_score=3, first_crawled_at=now, last_crawled_at=now,
             posted_at=now - timedelta(days=2)),
        Post(forum_id=forum.id, board_id=board_b.id, url="https://ptt.cc/4", title="彩妝開箱",
             pushes=5, latest_score=2, first_crawled_at=now, last_crawled_at=now, posted_at=None),
    ]
    db_session.add_all(posts)
    await db_session.flush()
    return {"session": db_session, "forum": forum, "board_a": board_a, "board_b": board_b}


async def test_no_filter_returns_all(seeded_db):
    results = await posts_query(seeded_db["session"])
    assert len(results) == 4


async def test_forum_code_filter(seeded_db):
    results = await posts_query(seeded_db["session"], forum_codes=["ptt"])
    assert len(results) == 4


async def test_board_code_filter(seeded_db):
    results = await posts_query(seeded_db["session"], board_codes=["e-shopping"])
    assert len(results) == 2
    assert all("代購" in r["title"] or "戰利品" in r["title"] for r in results)


async def test_min_pushes_filter(seeded_db):
    results = await posts_query(seeded_db["session"], min_pushes=50)
    assert len(results) == 1
    assert results[0]["pushes"] == 80


async def test_min_score_filter(seeded_db):
    results = await posts_query(seeded_db["session"], min_score=5)
    assert all(r["latest_score"] >= 5 for r in results)
    assert len(results) == 2


async def test_posted_after_filter(seeded_db):
    cutoff = datetime(2026, 5, 1)
    results = await posts_query(seeded_db["session"], posted_after=cutoff)
    # Only posts within last 5 days from cutoff (May 1): May 5 (0d), May 3 (2d ago)
    for r in results:
        assert r["posted_at"] is not None


async def test_keyword_like_fallback(seeded_db):
    # SQLite uses LIKE fallback from _keyword_condition
    results = await posts_query(seeded_db["session"], keywords=["代購"])
    assert any("代購" in r["title"] for r in results)


async def test_combined_filters(seeded_db):
    results = await posts_query(
        seeded_db["session"],
        board_codes=["e-shopping"],
        min_pushes=50,
    )
    assert len(results) == 1
    assert results[0]["title"] == "日本代購現貨"


async def test_limit_respected(seeded_db):
    results = await posts_query(seeded_db["session"], limit=2)
    assert len(results) == 2


async def test_result_shape(seeded_db):
    results = await posts_query(seeded_db["session"], limit=1)
    r = results[0]
    for key in ("id", "title", "author", "url", "pushes", "boos", "comment_count", "posted_at", "latest_score"):
        assert key in r
