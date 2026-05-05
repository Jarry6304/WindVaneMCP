"""Komica search toolkit — crawl latest pages and filter by keyword.

Komica has no native search. We crawl the board listing page and filter
threads whose title OR first-post content matches the keyword.
"""

from __future__ import annotations

import structlog
from crawlee import Request
from crawlee.beautifulsoup_crawler import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import Forum, ForumBoard
from wind_vane.toolkits.crawlers.upsert import log_crawl_finish, log_crawl_start, upsert_post, upsert_search_query

log = structlog.get_logger()

KOMICA_BASE = "https://www.komica.org"


def _matches_keyword(title: str, content: str, kw_lower: str) -> bool:
    return kw_lower in title.lower() or kw_lower in content.lower()


def _extract_thread(thread_tag) -> dict | None:
    """Parse one Komica thread block into a dict. Returns None if no usable data."""
    # Title link: <div class="title"><a href="...">text</a></div>
    title_link = thread_tag.select_one("div.title a, .title > a, h3 a, h2 a")
    if not title_link:
        return None

    title = title_link.get_text(strip=True)
    href = title_link.get("href", "")
    if not href:
        return None
    url = href if href.startswith("http") else KOMICA_BASE + href

    content_tag = thread_tag.select_one("blockquote, .post-content, .thread-content")
    content = content_tag.get_text(separator=" ", strip=True) if content_tag else ""

    return {"title": title, "url": url, "content": content}


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
    kw_lower = keyword.lower()
    collected: list[dict] = []

    # Crawl up to 3 listing pages to gather enough threads for filtering
    crawler = BeautifulSoupCrawler(max_requests_per_crawl=3)

    @crawler.router.default_handler
    async def handler(ctx: BeautifulSoupCrawlingContext) -> None:
        soup = ctx.parsed_content

        for thread in soup.select("div.thread, article.thread, div[id^='thread']"):
            parsed = _extract_thread(thread)
            if not parsed:
                continue
            if _matches_keyword(parsed["title"], parsed["content"], kw_lower):
                collected.append(parsed)

    crawl_log = await log_crawl_start(session, forum.id, "komica_search", keyword)
    error_msg: str | None = None
    try:
        await crawler.run([Request.from_url(board_url)])
    except Exception as exc:
        error_msg = str(exc)
        log.error("komica_search: crawler failed", exc=error_msg)

    results = []
    new_count = 0
    for item in collected[:limit]:
        post, is_new = await upsert_post(
            session,
            forum_id=forum.id,
            board_id=board.id,
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
        results.append({
            "title": post.title,
            "url": post.url,
            "content": post.content,
            "latest_score": post.latest_score,
        })

    await log_crawl_finish(crawl_log, posts_fetched=len(results), posts_new=new_count, error_msg=error_msg)

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
