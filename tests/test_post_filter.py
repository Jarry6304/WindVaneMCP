"""Tests for post_filter scoring logic."""

import pytest

from wind_vane.db.models import BlacklistPattern, CommercialSignal, Forum, ForumBoard, Keyword
from wind_vane.toolkits.crawlers.post_filter import post_filter


@pytest.fixture
async def filter_db(db_session):
    forum = Forum(
        code="ptt", name_zh="PTT", base_url="https://www.ptt.cc",
        requires_js=False, rate_limit_per_min=60, is_active=True,
    )
    db_session.add(forum)
    await db_session.flush()

    kw = Keyword(keyword="代購", tier=3, category="generic", weight=5, is_active=True)
    db_session.add(kw)

    bl = BlacklistPattern(pattern="徵", pattern_type="keyword", applies_to="title", is_active=True)
    db_session.add(bl)

    sig = CommercialSignal(signal_text="現貨", weight=5, category="availability", is_active=True)
    db_session.add(sig)

    await db_session.flush()
    return db_session


async def test_keyword_match_passes(filter_db):
    post = {"title": "日本代購零食開箱", "content": "現貨 含運", "pushes": 0}
    result = await post_filter(filter_db, post)
    assert result["passed"] is True
    assert "代購" in result["matched_keywords"]


async def test_blacklist_rejects(filter_db):
    post = {"title": "徵求日本代購", "content": "求代購", "pushes": 0}
    result = await post_filter(filter_db, post)
    assert result["passed"] is False
    assert "blacklist" in result["reason"]


async def test_no_keyword_fails(filter_db):
    post = {"title": "今天吃什麼好", "content": "隨便", "pushes": 0}
    result = await post_filter(filter_db, post)
    assert result["passed"] is False


async def test_commercial_signal_adds_score(filter_db):
    post = {"title": "日本代購現貨", "content": "現貨供應", "pushes": 20}
    result = await post_filter(filter_db, post)
    assert result["score"] > 10


async def test_short_title_rejected(filter_db):
    post = {"title": "hi", "content": "代購", "pushes": 0}
    result = await post_filter(filter_db, post)
    assert result["passed"] is False
    assert result["reason"] == "title too short"


async def test_pushes_bonus_applied(filter_db):
    post_low = {"title": "日本代購零食", "content": "", "pushes": 0}
    post_high = {"title": "日本代購零食", "content": "", "pushes": 100}
    r_low = await post_filter(filter_db, post_low)
    r_high = await post_filter(filter_db, post_high)
    assert r_high["score"] > r_low["score"]
