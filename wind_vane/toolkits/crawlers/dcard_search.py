"""Dcard search toolkit — Google web search, snippet only (no full content crawl).

Dcard has no public API and blocks scrapers. We use Google to surface public
posts and store only the title + snippet. limit is capped at 10 per spec
because Dcard throttles search referrals aggressively.
"""

from __future__ import annotations

from urllib.parse import quote

import httpx
import structlog
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import Forum, ForumBoard
from wind_vane.toolkits.crawlers.upsert import log_crawl_finish, log_crawl_start, upsert_post, upsert_search_query

log = structlog.get_logger()

GOOGLE_SEARCH_URL = "https://www.google.com/search"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9",
}


def _build_query(keyword: str, board_code: str | None) -> str:
    """Build Google search query: site: operator first, then keyword."""
    site = f"site:dcard.tw/f/{board_code}" if board_code else "site:dcard.tw"
    return f"{site} {keyword}"


def _parse_google_results(html: str, limit: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for g in soup.select("div.g, div[data-hveid]")[:limit * 2]:
        title_tag = g.select_one("h3")
        link_tag = g.select_one("a[href]")
        snippet_tag = (
            g.select_one("div.VwiC3b")
            or g.select_one("span.aCOpRe")
            or g.select_one("div[data-sncf]")
        )
        if not title_tag or not link_tag:
            continue
        href = link_tag.get("href", "")
        if not href.startswith("http") or "dcard.tw" not in href:
            continue
        results.append({
            "title": title_tag.get_text(strip=True),
            "url": href,
            "content": snippet_tag.get_text(strip=True) if snippet_tag else "",
        })
        if len(results) >= limit:
            break
    return results


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

    query = _build_query(keyword, board_code)

    crawl_log = await log_crawl_start(session, forum.id, "dcard_search", keyword)
    collected: list[dict] = []
    error_msg: str | None = None

    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=15, follow_redirects=True) as client:
            resp = await client.get(GOOGLE_SEARCH_URL, params={"q": query, "num": min(limit, 10)})
            resp.raise_for_status()
        collected = _parse_google_results(resp.text, limit)
    except httpx.HTTPStatusError as exc:
        error_msg = f"HTTP {exc.response.status_code}"
        log.warning("dcard_search: google returned error", status=exc.response.status_code)
    except Exception as exc:
        error_msg = str(exc)
        log.error("dcard_search: request failed", exc=error_msg)

    results = []
    new_count = 0
    for item in collected:
        post, is_new = await upsert_post(
            session,
            forum_id=forum.id,
            board_id=board.id if board else None,
            native_post_id=None,
            url=item["url"],
            title=item["title"],
            author=None,
            content=item["content"] or None,
            posted_at=None,
            pushes=0,
            boos=0,
            comment_count=0,
        )
        if is_new:
            new_count += 1
        results.append({"title": post.title, "snippet": post.content, "url": post.url, "posted_at": None})

    await log_crawl_finish(crawl_log, posts_fetched=len(results), posts_new=new_count, error_msg=error_msg)

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
