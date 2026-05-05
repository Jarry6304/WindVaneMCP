"""Tests for upsert_post — requires in-memory SQLite via conftest."""

import pytest

from wind_vane.db.models import Forum, ForumBoard
from wind_vane.toolkits.crawlers.upsert import upsert_post


@pytest.fixture
async def forum_and_board(db_session):
    forum = Forum(
        code="ptt",
        name_zh="PTT",
        base_url="https://www.ptt.cc",
        requires_js=False,
        rate_limit_per_min=60,
        is_active=True,
    )
    db_session.add(forum)
    await db_session.flush()

    board = ForumBoard(
        forum_id=forum.id,
        board_code="e-shopping",
        name_zh="線上購物板",
        value_score=10,
        is_active=True,
    )
    db_session.add(board)
    await db_session.flush()
    return forum, board


async def test_new_post_is_inserted(db_session, forum_and_board):
    forum, board = forum_and_board
    post, is_new = await upsert_post(
        db_session,
        forum_id=forum.id,
        board_id=board.id,
        native_post_id=None,
        url="https://www.ptt.cc/bbs/e-shopping/M.123.A.html",
        title="代購日本零食",
        author="user1",
        content="內文",
        posted_at=None,
        pushes=10,
        boos=0,
        comment_count=10,
    )
    assert is_new is True
    assert post.crawl_count == 1
    assert post.pushes_history == "10"


async def test_same_url_updates_not_inserts(db_session, forum_and_board):
    forum, board = forum_and_board
    url = "https://www.ptt.cc/bbs/e-shopping/M.456.A.html"

    _, is_new = await upsert_post(
        db_session,
        forum_id=forum.id,
        board_id=board.id,
        native_post_id=None,
        url=url,
        title="Title",
        author=None,
        content=None,
        posted_at=None,
        pushes=5,
        boos=0,
        comment_count=5,
    )
    assert is_new is True

    post, is_new2 = await upsert_post(
        db_session,
        forum_id=forum.id,
        board_id=board.id,
        native_post_id=None,
        url=url,
        title="Title",
        author=None,
        content=None,
        posted_at=None,
        pushes=5,
        boos=0,
        comment_count=5,
    )
    assert is_new2 is False
    assert post.crawl_count == 2


async def test_crawl_count_increments(db_session, forum_and_board):
    forum, board = forum_and_board
    url = "https://www.ptt.cc/bbs/e-shopping/M.789.A.html"
    for i in range(3):
        await upsert_post(
            db_session,
            forum_id=forum.id,
            board_id=board.id,
            native_post_id=None,
            url=url,
            title="Title",
            author=None,
            content=None,
            posted_at=None,
            pushes=i * 10,
            boos=0,
            comment_count=0,
        )
    from sqlalchemy import select
    from wind_vane.db.models import Post
    p = (await db_session.execute(select(Post).where(Post.url == url))).scalar_one()
    assert p.crawl_count == 3
