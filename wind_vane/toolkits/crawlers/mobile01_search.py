"""Mobile01 search toolkit — Crawlee BeautifulSoupCrawler."""

from __future__ import annotations

import structlog
from crawlee.beautifulsoup_crawler import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import Forum, ForumBoard
from wind_vane.toolkits.crawlers.upsert import upsert_post, upsert_search_query

log = structlog.get_logger()

MOBILE01_BASE = "https://www.mobile01.com"


async def mobile01_search(
    session: AsyncSession,
    keyword: str,
    board_code: str | None = None,
    limit: int = 20,
) -> list[dict]:
    forum = (await session.execute(select(Forum).where(Forum.code == "mobile01"))).scalar_one()

    board = None
    query_str = keyword
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
        query_str = f"{keyword} site:mobile01.com/topiclist.php?f={board.native_id}"

    search_url = f"{MOBILE01_BASE}/googlesearch.php?q={query_str}"

    collected: list[dict] = []

    crawler = BeautifulSoupCrawler(max_requests_per_crawl=limit + 5)

    @crawler.router.default_handler
    async def handler(ctx: BeautifulSoupCrawlingContext) -> None:
        soup = ctx.parsed_content
        for result in soup.select(".search-result-item")[:limit]:
            title_tag = result.select_one("h3 a") or result.select_one("a")
            if not title_tag:
                continue
            href = title_tag.get("href", "")
            url = href if href.startswith("http") else MOBILE01_BASE + href
            title = title_tag.text.strip()
            snippet_tag = result.select_one(".snippet") or result.select_one("p")
            snippet = snippet_tag.text.strip() if snippet_tag else ""
            collected.append({"title": title, "url": url, "content": snippet})

    await crawler.run([search_url])

    results = []
    for item in collected[:limit]:
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
            "url": post.url,
            "content": post.content,
            "posted_at": post.posted_at.isoformat() if post.posted_at else None,
            "latest_score": post.latest_score,
        })

    await upsert_search_query(
        session,
        keyword=keyword,
        forum_code="mobile01",
        board_code=board_code or "_all",
        operators=None,
        posts_found=len(results),
        passed=len(results),
        avg_score=None,
        peak_count=0,
    )
    await session.commit()
    return results
