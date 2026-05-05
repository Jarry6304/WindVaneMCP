"""Bahamut search toolkit — Crawlee PlaywrightCrawler, dual scope."""

from __future__ import annotations

import structlog
from crawlee.playwright_crawler import PlaywrightCrawler, PlaywrightCrawlingContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import Forum, ForumBoard
from wind_vane.toolkits.crawlers.upsert import upsert_post, upsert_search_query

log = structlog.get_logger()

BAHAMUT_BASE = "https://forum.gamer.com.tw"


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
        search_url = f"{BAHAMUT_BASE}/B.php?bsn={board.native_id}&qt=2&q={keyword}"
    else:
        search_url = f"{BAHAMUT_BASE}/G2.php?qt=2&q={keyword}"

    collected: list[dict] = []

    crawler = PlaywrightCrawler(
        max_requests_per_crawl=limit + 5,
        max_session_rotations=1,
    )

    @crawler.router.default_handler
    async def handler(ctx: PlaywrightCrawlingContext) -> None:
        await ctx.page.wait_for_load_state("networkidle")
        items = await ctx.page.query_selector_all(".b-list__row")
        for item in items[:limit]:
            title_el = await item.query_selector(".b-list__main__title")
            link_el = await item.query_selector("a")
            if not title_el or not link_el:
                continue
            title = (await title_el.text_content() or "").strip()
            href = await link_el.get_attribute("href") or ""
            url = href if href.startswith("http") else BAHAMUT_BASE + href

            push_el = await item.query_selector(".b-list__count__recommend")
            try:
                pushes = int((await push_el.text_content() or "0").strip()) if push_el else 0
            except ValueError:
                pushes = 0

            collected.append({"title": title, "url": url, "pushes": pushes})

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
            content=None,
            posted_at=None,
            pushes=item["pushes"],
            boos=0,
            comment_count=0,
        )
        results.append({
            "title": post.title,
            "url": post.url,
            "pushes": post.pushes,
            "posted_at": post.posted_at.isoformat() if post.posted_at else None,
            "latest_score": post.latest_score,
        })

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
