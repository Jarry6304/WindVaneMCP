"""Mobile01 search toolkit — Crawlee BeautifulSoupCrawler + Google CSE."""

from __future__ import annotations

from urllib.parse import quote

import structlog
from crawlee import Request
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import Forum, ForumBoard
from wind_vane.toolkits.crawlers.upsert import log_crawl_finish, log_crawl_start, upsert_post, upsert_search_query

log = structlog.get_logger()

MOBILE01_BASE = "https://www.mobile01.com"


def _build_search_url(keyword: str, fid: str | None = None) -> str:
    """Build Mobile01 Google CSE search URL, optionally scoped to a sub-forum."""
    query = keyword
    if fid:
        query = f"{keyword} site:mobile01.com/topiclist.php?f={fid}"
    return f"{MOBILE01_BASE}/googlesearch.php?q={quote(query, safe='')}"


def _parse_result(tag) -> dict | None:
    """Extract title, URL, snippet from one search-result element."""
    # Mobile01 CSE renders results in several possible structures
    title_tag = (
        tag.select_one("h3 > a")
        or tag.select_one(".gs-title a")
        or tag.select_one("a.r")
        or tag.select_one("a")
    )
    if not title_tag:
        return None

    title = title_tag.get_text(strip=True)
    href = title_tag.get("href", "")
    if not href or href.startswith("#"):
        return None
    url = href if href.startswith("http") else MOBILE01_BASE + href

    snippet_tag = (
        tag.select_one(".gs-snippet")
        or tag.select_one(".snippet")
        or tag.select_one("p")
    )
    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

    return {"title": title, "url": url, "content": snippet}


async def mobile01_search(
    session: AsyncSession,
    keyword: str,
    board_code: str | None = None,
    limit: int = 20,
) -> list[dict]:
    forum = (await session.execute(select(Forum).where(Forum.code == "mobile01"))).scalar_one()

    board = None
    fid: str | None = None
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
        fid = board.native_id

    search_url = _build_search_url(keyword, fid)
    collected: list[dict] = []

    crawler = BeautifulSoupCrawler(max_requests_per_crawl=limit + 5)

    @crawler.router.default_handler
    async def handler(ctx: BeautifulSoupCrawlingContext) -> None:
        soup = ctx.parsed_content
        # Try multiple container selectors for CSE / native search
        containers = soup.select(
            ".search-result-item, .gsc-result, .gs-result, div.g"
        )
        # Fallback: any <li> that has a link
        if not containers:
            containers = soup.select("li:has(a[href])")

        for tag in containers[:limit]:
            parsed = _parse_result(tag)
            if parsed:
                collected.append(parsed)

    crawl_log = await log_crawl_start(session, forum.id, "mobile01_search", keyword)
    error_msg: str | None = None
    try:
        await crawler.run([Request.from_url(search_url)])
    except Exception as exc:
        error_msg = str(exc)
        log.error("mobile01_search: crawler failed", exc=error_msg)

    results = []
    new_count = 0
    for item in collected[:limit]:
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
        results.append({
            "title": post.title,
            "url": post.url,
            "content": post.content,
            "posted_at": post.posted_at.isoformat() if post.posted_at else None,
            "latest_score": post.latest_score,
        })

    await log_crawl_finish(crawl_log, posts_fetched=len(results), posts_new=new_count, error_msg=error_msg)

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
