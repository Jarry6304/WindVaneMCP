"""PTT search toolkit — Crawlee BeautifulSoupCrawler."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin

import structlog
from crawlee.beautifulsoup_crawler import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import Forum, ForumBoard, ForumSearchOperator
from wind_vane.toolkits.crawlers.upsert import upsert_post, upsert_search_query

log = structlog.get_logger()

PTT_BASE = "https://www.ptt.cc"
OVER18_COOKIE = {"over18": "1"}


async def ptt_search(
    session: AsyncSession,
    keyword: str,
    board_code: str,
    limit: int = 20,
    min_recommend: int | None = None,
    title_only: bool = False,
    author: str | None = None,
) -> list[dict]:
    forum = (await session.execute(select(Forum).where(Forum.code == "ptt"))).scalar_one()
    board = (
        await session.execute(
            select(ForumBoard).where(
                ForumBoard.forum_id == forum.id,
                ForumBoard.board_code == board_code,
                ForumBoard.is_active.is_(True),
            )
        )
    ).scalar_one()

    ops = (
        await session.execute(
            select(ForumSearchOperator).where(ForumSearchOperator.forum_id == forum.id)
        )
    ).scalars().all()
    op_map = {o.operator: o.syntax_template for o in ops}

    parts = [keyword]
    if title_only and "title" in op_map:
        parts = [op_map["title"].format(value=keyword)]
    if author and "author" in op_map:
        parts.append(op_map["author"].format(value=author))
    if min_recommend is not None and "recommend" in op_map:
        parts.append(op_map["recommend"].format(value=min_recommend))

    search_q = " ".join(parts)
    search_url = f"{PTT_BASE}/bbs/{board_code}/search?{urlencode({'q': search_q})}"

    collected: list[dict] = []

    crawler = BeautifulSoupCrawler(max_requests_per_crawl=limit + 5)

    @crawler.router.default_handler
    async def handler(ctx: BeautifulSoupCrawlingContext) -> None:
        soup = ctx.parsed_content
        if soup.select_one("div.over18-notice"):
            log.warning("ptt_search: hit over18 gate, cookie may be missing")
            return

        for entry in soup.select("div.r-ent")[:limit]:
            title_tag = entry.select_one("div.title a")
            if not title_tag:
                continue
            href = title_tag.get("href", "")
            post_url = urljoin(PTT_BASE, href)

            push_tag = entry.select_one("div.nrec span")
            push_text = push_tag.text.strip() if push_tag else "0"
            try:
                pushes = int(push_text) if push_text.isdigit() else (100 if push_text == "爆" else 0)
            except ValueError:
                pushes = 0

            date_tag = entry.select_one("div.date")
            meta_tag = entry.select_one("div.meta div.author")

            collected.append({
                "title": title_tag.text.strip(),
                "author": meta_tag.text.strip() if meta_tag else None,
                "url": post_url,
                "pushes": pushes,
                "boos": 0,
                "comment_count": pushes,
                "content": None,
                "posted_at": None,
            })

    await crawler.run([{"url": search_url, "headers": {}, "user_data": {"cookies": OVER18_COOKIE}}])

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
            author=item.get("author"),
            content=item.get("content"),
            posted_at=item.get("posted_at"),
            pushes=item["pushes"],
            boos=item["boos"],
            comment_count=item["comment_count"],
        )
        if is_new:
            new_count += 1
        results.append({
            "title": post.title,
            "author": post.author,
            "url": post.url,
            "pushes": post.pushes,
            "boos": post.boos,
            "comment_count": post.comment_count,
            "posted_at": post.posted_at.isoformat() if post.posted_at else None,
            "latest_score": post.latest_score,
        })

    operators_used = {}
    if min_recommend is not None:
        operators_used["recommend"] = min_recommend

    await upsert_search_query(
        session,
        keyword=keyword,
        forum_code="ptt",
        board_code=board_code,
        operators=operators_used or None,
        posts_found=len(results),
        passed=len(results),
        avg_score=None,
        peak_count=0,
    )
    await session.commit()
    return results
