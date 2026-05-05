"""Bahamut search toolkit — Crawlee PlaywrightCrawler, dual scope."""

from __future__ import annotations

from urllib.parse import quote

import structlog
from crawlee import Request
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import Forum, ForumBoard
from wind_vane.toolkits.crawlers.upsert import log_crawl_finish, log_crawl_start, upsert_post, upsert_search_query

log = structlog.get_logger()

BAHAMUT_BASE = "https://forum.gamer.com.tw"


def _build_search_url(scope: str, bsn: str | None, keyword: str) -> str:
    kw = quote(keyword, safe="")
    if scope == "board":
        return f"{BAHAMUT_BASE}/B.php?bsn={bsn}&qt=2&q={kw}"
    return f"{BAHAMUT_BASE}/G2.php?qt=2&q={kw}"


async def bahamut_search(
    session: AsyncSession,
    keyword: str,
    scope: str = "board",
    board_code: str | None = None,
    limit: int = 20,
) -> list[dict]:
    if scope == "board" and not board_code:
        raise ValueError("board_code is required when scope='board'")

    forum = (await session.execute(select(Forum).where(Forum.code == "bahamut"))).scalar_one()

    board = None
    bsn: str | None = None
    if scope == "board" and board_code:
        board = (
            await session.execute(
                select(ForumBoard).where(
                    ForumBoard.forum_id == forum.id,
                    ForumBoard.board_code == board_code,
                    ForumBoard.is_active.is_(True),
                )
            )
        ).scalar_one()
        bsn = board.native_id

    search_url = _build_search_url(scope, bsn, keyword)
    collected: list[dict] = []

    # max_concurrency=3 per spec to avoid memory pressure when fetching post content
    crawler = PlaywrightCrawler(max_requests_per_crawl=limit + 5)

    @crawler.router.default_handler
    async def handler(ctx: PlaywrightCrawlingContext) -> None:
        await ctx.page.wait_for_load_state("networkidle", timeout=15000)

        # Board search (B.php) and global search (G2.php) share similar result markup
        rows = await ctx.page.query_selector_all(
            "section.b-list .b-list__row, .search-result .b-list__row, li.b-forum-list__item"
        )

        for row in rows[:limit]:
            # Title + link
            title_el = await row.query_selector(
                ".b-list__main__title, .b-list__title, h4 a, .title a"
            )
            if not title_el:
                continue
            title = (await title_el.text_content() or "").strip()
            href = await title_el.get_attribute("href") or ""
            url = href if href.startswith("http") else BAHAMUT_BASE + href

            # Reply / comment count
            count_el = await row.query_selector(
                ".b-list__count__reply, .b-list__count, .reply-count"
            )
            try:
                comment_count = int((await count_el.text_content() or "0").strip().replace(",", "")) if count_el else 0
            except ValueError:
                comment_count = 0

            # Author
            author_el = await row.query_selector(".b-list__user-name, .username, .author")
            author = (await author_el.text_content() or "").strip() if author_el else None

            if title and url:
                collected.append({"title": title, "url": url, "author": author, "comment_count": comment_count})

    crawl_log = await log_crawl_start(session, forum.id, "bahamut_search", keyword)
    error_msg: str | None = None
    try:
        await crawler.run([Request.from_url(search_url)])
    except Exception as exc:
        error_msg = str(exc)
        log.error("bahamut_search: crawler failed", exc=error_msg)

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
            author=item.get("author"),
            content=None,
            posted_at=None,
            pushes=0,
            boos=0,
            comment_count=item["comment_count"],
        )
        if is_new:
            new_count += 1
        results.append({
            "title": post.title,
            "author": post.author,
            "url": post.url,
            "comment_count": post.comment_count,
            "posted_at": post.posted_at.isoformat() if post.posted_at else None,
            "latest_score": post.latest_score,
        })

    await log_crawl_finish(crawl_log, posts_fetched=len(results), posts_new=new_count, error_msg=error_msg)

    await upsert_search_query(
        session,
        keyword=keyword,
        forum_code="bahamut",
        board_code=board_code or "_global",
        operators={"scope": scope},
        posts_found=len(results),
        passed=len(results),
        avg_score=None,
        peak_count=0,
    )
    await session.commit()
    return results
