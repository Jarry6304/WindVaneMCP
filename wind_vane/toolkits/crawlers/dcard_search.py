"""Dcard search toolkit — Google Custom Search API (snippet only, no content crawl)."""

from __future__ import annotations

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import Forum, ForumBoard
from wind_vane.toolkits.crawlers.upsert import upsert_post, upsert_search_query

log = structlog.get_logger()

GOOGLE_SEARCH_URL = "https://www.google.com/search"


async def dcard_search(
    session: AsyncSession,
    keyword: str,
    board_code: str | None = None,
    limit: int = 10,
) -> list[dict]:
    forum = (await session.execute(select(Forum).where(Forum.code == "dcard"))).scalar_one()

    board = None
    if board_code:
        board = (
            await session.execute(
                select(ForumBoard).where(
                    ForumBoard.forum_id == forum.id,
                    ForumBoard.board_code == board_code,
                    ForumBoard.is_active.is_(True),
                )
            )
        ).scalar_one()
        site_scope = f"site:dcard.tw/f/{board_code}"
    else:
        site_scope = "site:dcard.tw"

    query = f"{site_scope} {keyword}"

    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
        resp = await client.get(GOOGLE_SEARCH_URL, params={"q": query, "num": limit})
        resp.raise_for_status()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "html.parser")
    collected = []
    for g in soup.select("div.g")[:limit]:
        title_tag = g.select_one("h3")
        link_tag = g.select_one("a")
        snippet_tag = g.select_one("div.VwiC3b") or g.select_one("span.aCOpRe")
        if not title_tag or not link_tag:
            continue
        href = link_tag.get("href", "")
        if not href.startswith("http"):
            continue
        collected.append({
            "title": title_tag.text.strip(),
            "url": href,
            "content": snippet_tag.text.strip() if snippet_tag else "",
        })

    results = []
    for item in collected:
        post, _ = await upsert_post(
            session,
            forum_id=forum.id,
            board_id=board.id if board else None,
            native_post_id=None,
            url=item["url"],
            title=item["title"],
            author=None,
            content=item.get("content"),
            posted_at=None,
            pushes=0,
            boos=0,
            comment_count=0,
        )
        results.append({
            "title": post.title,
            "snippet": post.content,
            "url": post.url,
            "posted_at": None,
        })

    await upsert_search_query(
        session,
        keyword=keyword,
        forum_code="dcard",
        board_code=board_code or "_all",
        operators=None,
        posts_found=len(results),
        passed=len(results),
        avg_score=None,
        peak_count=0,
    )
    await session.commit()
    return results
