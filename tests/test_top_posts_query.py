"""Tests for top_posts — ordering by pushes / score, forum/board scoping."""

from datetime import datetime

import pytest

from wind_vane.db.models import Forum, ForumBoard, Post
from wind_vane.toolkits.queries.top_posts import top_posts


@pytest.fixture
async def posts_db(db_session):
    forum = Forum(
        code="ptt", name_zh="PTT", base_url="https://www.ptt.cc",
        requires_js=False, rate_limit_per_min=60, is_active=True,
    )
    db_session.add(forum)
    await db_session.flush()

    board = ForumBoard(forum_id=forum.id, board_code="e-shopping", name_zh="購物板", value_score=10, is_active=True)
    db_session.add(board)
    await db_session.flush()

    now = datetime(2026, 5, 5)
    data = [
        ("代購A", 100, 9, board.id),
        ("代購B", 50, 7, board.id),
        ("代購C", 20, 3, board.id),
        ("其他D", 200, 1, None),  # no board
    ]
    for title, pushes, score, bid in data:
        db_session.add(Post(
            forum_id=forum.id, board_id=bid,
            url=f"https://ptt.cc/{title}",
            title=title, pushes=pushes, latest_score=score,
            first_crawled_at=now, last_crawled_at=now, posted_at=now,
        ))
    await db_session.flush()
    return {"session": db_session, "forum": forum, "board": board}


async def test_order_by_pushes_descending(posts_db):
    results = await top_posts(posts_db["session"], order_by="pushes")
    push_vals = [r["pushes"] for r in results]
    assert push_vals == sorted(push_vals, reverse=True)


async def test_order_by_score_descending(posts_db):
    results = await top_posts(posts_db["session"], order_by="score")
    scores = [r["latest_score"] for r in results if r["latest_score"] is not None]
    assert scores == sorted(scores, reverse=True)


async def test_forum_code_filter(posts_db):
    results = await top_posts(posts_db["session"], forum_code="ptt")
    assert len(results) == 4


async def test_board_code_filter(posts_db):
    results = await top_posts(posts_db["session"], board_code="e-shopping")
    assert len(results) == 3
    assert all(r["title"].startswith("代購") for r in results)


async def test_limit_respected(posts_db):
    results = await top_posts(posts_db["session"], limit=2)
    assert len(results) == 2


async def test_posted_after_filter(posts_db):
    results = await top_posts(posts_db["session"], posted_after=datetime(2026, 5, 1))
    assert len(results) == 4


async def test_result_shape(posts_db):
    results = await top_posts(posts_db["session"], limit=1)
    r = results[0]
    for key in ("title", "author", "url", "pushes", "latest_score", "posted_at"):
        assert key in r
