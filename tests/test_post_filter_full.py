"""Comprehensive tests for post_filter — W4 coverage.

Covers: tier-weighted scoring, affinity hard-reject, regex blacklist,
'both' applies_to, explicit keyword list with DB weights, pipeline write-back.
"""

from datetime import datetime

import pytest

from wind_vane.db.models import (
    BlacklistPattern,
    BoardKeywordAffinity,
    CommercialSignal,
    Forum,
    ForumBoard,
    Keyword,
    Post,
)
from wind_vane.toolkits.crawlers.post_filter import filter_and_update_post, post_filter


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def base_db(db_session):
    """Forum + board + tier-1 and tier-3 keywords + signals + blacklist."""
    forum = Forum(
        code="ptt", name_zh="PTT", base_url="https://www.ptt.cc",
        requires_js=False, rate_limit_per_min=60, is_active=True,
    )
    db_session.add(forum)
    await db_session.flush()

    board = ForumBoard(
        forum_id=forum.id, board_code="Toy_Hobby", name_zh="玩具收藏板",
        value_score=9, is_active=True,
    )
    db_session.add(board)
    await db_session.flush()

    kw1 = Keyword(keyword="戰鬥陀螺", tier=1, category="toy", weight=5, is_active=True)
    kw2 = Keyword(keyword="代購", tier=3, category="generic", weight=5, is_active=True)
    kw3 = Keyword(keyword="日本玩具", tier=2, category="toy", weight=4, is_active=True)
    db_session.add_all([kw1, kw2, kw3])
    await db_session.flush()

    db_session.add(CommercialSignal(signal_text="現貨", weight=5, category="availability", is_active=True))
    db_session.add(CommercialSignal(signal_text="開團", weight=5, category="transaction", is_active=True))
    db_session.add(BlacklistPattern(pattern="徵", pattern_type="keyword", applies_to="title", is_active=True))
    db_session.add(BlacklistPattern(pattern="廣告.*限時", pattern_type="regex", applies_to="both", is_active=True))
    await db_session.flush()

    return {"session": db_session, "forum": forum, "board": board, "kw1": kw1, "kw2": kw2, "kw3": kw3}


# ── Tier-weighted scoring ─────────────────────────────────────────────────────

async def test_tier1_keyword_scores_higher_than_tier3(base_db):
    session = base_db["session"]
    r1 = await post_filter(session, {"title": "戰鬥陀螺開箱心得", "content": ""})
    r3 = await post_filter(session, {"title": "日本代購開箱心得", "content": ""})
    # tier1 weight=5 → 10*5=50 pts; tier3 weight=5 → 3*5=15 pts
    assert r1["score"] > r3["score"]


async def test_tier1_score_calculation(base_db):
    session = base_db["session"]
    # 戰鬥陀螺: tier1 → 10 * weight(5) = 50, affinity default 5 → total 55
    result = await post_filter(session, {"title": "戰鬥陀螺特賣代購", "content": ""})
    assert result["passed"] is True
    assert "戰鬥陀螺" in result["matched_keywords"]
    assert result["score"] >= 50


async def test_tier2_score_calculation(base_db):
    session = base_db["session"]
    # 日本玩具: tier2 → 5 * weight(4) = 20, affinity default 5 → total 25
    result = await post_filter(session, {"title": "日本玩具開箱分享", "content": ""})
    assert "日本玩具" in result["matched_keywords"]
    assert result["score"] >= 20


# ── Affinity hard-reject ──────────────────────────────────────────────────────

async def test_affinity_zero_rejects_post(base_db):
    session, board, kw2 = base_db["session"], base_db["board"], base_db["kw2"]
    # 代購 × Toy_Hobby = affinity 0 (forbidden combo)
    session.add(BoardKeywordAffinity(
        board_id=board.id, keyword_id=kw2.id, affinity_score=0
    ))
    await session.flush()

    result = await post_filter(
        session, {"title": "代購訂單整理", "content": "", "board_id": board.id}
    )
    assert result["passed"] is False
    assert "affinity=0" in result["reason"]


async def test_affinity_high_adds_score(base_db):
    session, board, kw1 = base_db["session"], base_db["board"], base_db["kw1"]
    session.add(BoardKeywordAffinity(
        board_id=board.id, keyword_id=kw1.id, affinity_score=10
    ))
    await session.flush()

    r_with = await post_filter(
        session, {"title": "戰鬥陀螺", "content": "", "board_id": board.id}
    )
    r_without = await post_filter(
        session, {"title": "戰鬥陀螺", "content": ""}
    )
    assert r_with["score"] > r_without["score"]


# ── Blacklist ─────────────────────────────────────────────────────────────────

async def test_keyword_blacklist_title(base_db):
    result = await post_filter(base_db["session"], {"title": "徵求代購戰鬥陀螺", "content": ""})
    assert result["passed"] is False
    assert "blacklist:徵" in result["reason"]


async def test_regex_blacklist_both(base_db):
    # "廣告.*限時" matches title
    result = await post_filter(
        base_db["session"], {"title": "廣告限時優惠", "content": ""}
    )
    assert result["passed"] is False
    assert "blacklist" in result["reason"]


async def test_regex_blacklist_in_content(base_db):
    # regex applies_to=both, so content also checked
    result = await post_filter(
        base_db["session"], {"title": "代購分享", "content": "廣告限時特惠"}
    )
    assert result["passed"] is False


async def test_blacklist_title_only_ignores_content(base_db):
    # "徵" pattern applies_to=title; in content only → should NOT reject
    result = await post_filter(
        base_db["session"], {"title": "戰鬥陀螺代購", "content": "有人徵求嗎"}
    )
    assert result["passed"] is True


# ── Explicit keyword list uses DB weights ─────────────────────────────────────

async def test_explicit_keywords_still_use_db_weights(base_db):
    session = base_db["session"]
    # Provide only tier-1 keyword; should still score using tier1 weight
    r_explicit = await post_filter(
        session, {"title": "戰鬥陀螺開箱", "content": ""}, keywords=["戰鬥陀螺"]
    )
    r_auto = await post_filter(
        session, {"title": "戰鬥陀螺開箱", "content": ""}
    )
    # Explicit list restricts to 1 keyword, auto finds same 1 → scores should match
    assert r_explicit["score"] == r_auto["score"]


async def test_explicit_keyword_not_in_db_gets_flat_score(base_db):
    session = base_db["session"]
    result = await post_filter(
        session, {"title": "Switch2 特價開箱", "content": ""}, keywords=["Switch2"]
    )
    assert result["passed"] is True
    assert result["score"] >= 5  # flat score for unknown keyword


# ── Commercial signals ────────────────────────────────────────────────────────

async def test_commercial_signal_adds_score(base_db):
    session = base_db["session"]
    r_no_sig = await post_filter(session, {"title": "戰鬥陀螺代購", "content": ""})
    r_with_sig = await post_filter(session, {"title": "戰鬥陀螺代購", "content": "現貨 開團"})
    assert r_with_sig["score"] > r_no_sig["score"]


# ── Pushes bonus ──────────────────────────────────────────────────────────────

async def test_pushes_bonus_capped_at_10(base_db):
    session = base_db["session"]
    r_low = await post_filter(session, {"title": "戰鬥陀螺", "pushes": 0})
    r_high = await post_filter(session, {"title": "戰鬥陀螺", "pushes": 1000})
    r_mid = await post_filter(session, {"title": "戰鬥陀螺", "pushes": 100})
    assert r_high["score"] - r_low["score"] == 10
    assert r_high["score"] == r_mid["score"]  # both capped at +10


# ── Pipeline write-back ───────────────────────────────────────────────────────

async def test_filter_and_update_post_writes_score(base_db):
    session, forum, board = base_db["session"], base_db["forum"], base_db["board"]
    post = Post(
        forum_id=forum.id,
        board_id=board.id,
        url="https://www.ptt.cc/bbs/Toy_Hobby/M.999.A.html",
        title="戰鬥陀螺代購現貨",
        pushes=20,
        first_crawled_at=datetime.utcnow(),
        last_crawled_at=datetime.utcnow(),
    )
    session.add(post)
    await session.flush()

    result = await filter_and_update_post(session, post)
    assert result["passed"] is True
    assert post.latest_score == result["score"]
    assert post.matched_keywords is not None
    assert "戰鬥陀螺" in post.matched_keywords


async def test_filter_and_update_post_on_blacklisted(base_db):
    session, forum = base_db["session"], base_db["forum"]
    post = Post(
        forum_id=forum.id,
        url="https://www.ptt.cc/bbs/Toy_Hobby/M.888.A.html",
        title="徵求戰鬥陀螺",
        pushes=0,
        first_crawled_at=datetime.utcnow(),
        last_crawled_at=datetime.utcnow(),
    )
    session.add(post)
    await session.flush()

    result = await filter_and_update_post(session, post)
    assert result["passed"] is False
    assert post.latest_score == 0
