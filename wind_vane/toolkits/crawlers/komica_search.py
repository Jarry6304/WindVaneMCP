"""Komica search toolkit — crawl latest N pages, filter by keyword."""

from __future__ import annotations

import structlog
from crawlee.beautifulsoup_crawler import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import Forum, ForumBoard
from wind_vane.toolkits.crawlers.upsert import upsert_post, upsert_search_query

log = structlog.get_logger()

KOMICA_BASE = "https://www.komica.org"


async def komica_search(
    session: AsyncSession,
    keyword: str,
    board_code: str,
    limit: int = 10,
) -> list[dict]:
    forum = (await session.execute(select(Forum).where(Forum.code == "komica"))).scalar_one()
    board = (
        await session.execute(
            select(ForumBoard).where(
                ForumBoard.forum_id == forum.id,
                ForumBoard.board_code == board_code,
                ForumBoard.is_active.is_(True),
            )
        )
    ).scalar_one()

    board_url = KOMICA_BASE + (board.url_path or "")
    collected: list[dict] = []
    kw_lower = keyword.lower()

    crawler = BeautifulSoupCrawler(max_requests_per_crawl=5)

    @crawler.router.default_handler
    async def handler(ctx: BeautifulSoupCrawlingContext) -> None:
        soup = ctx.parsed_content
        for thread in soup.select("div.thread, article"):
            title_tag = thread.select_one("h2, .title, a")
            if not title_tag:
                continue
            title = title_tag.text.strip()
            if kw_lower not in title.lower():
                continue
            link = title_tag.get("href") if title_tag.name == "a" else (
                thread.select_one("a") and thread.select_one("a").get("href")
            )
            if not link:
                continue
            url = link if link.startswith("http") else KOMICA_BASE + link
            content_tag = thread.select_one("blockquote, .post-content")
            content = content_tag.text.strip() if content_tag else ""
            collected.append({"title": title, "url": url, "content": content})

    await crawler.run([board_url])

    results = []
    for item in collected[:limit]:
        post, _ = await upsert_post(
            session,
            forum_id=forum.id,
            board_id=board.id,
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
            "latest_score": post.latest_score,
        })

    await upsert_search_query(
        session,
        keyword=keyword,
        forum_code="komica",
        board_code=board_code,
        operators=None,
        posts_found=len(results),
        passed=len(results),
        avg_score=None,
        peak_count=0,
    )
    await session.commit()
    return results
