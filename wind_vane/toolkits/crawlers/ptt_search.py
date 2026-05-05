"""PTT search toolkit — Crawlee BeautifulSoupCrawler."""

from __future__ import annotations

from urllib.parse import urlencode, urljoin

import structlog
from crawlee import Request
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import Forum, ForumBoard, ForumSearchOperator
from wind_vane.toolkits.crawlers.upsert import log_crawl_finish, log_crawl_start, upsert_post, upsert_search_query

log = structlog.get_logger()

PTT_BASE = "https://www.ptt.cc"


def _parse_push(text: str) -> tuple[int, int]:
    """Return (pushes, boos) from PTT's nrec span text."""
    t = text.strip()
    if t == "爆":
        return 100, 0
    if t in ("X", "XX"):
        return 0, 100
    try:
        n = int(t)
        return (n, 0) if n >= 0 else (0, abs(n))
    except ValueError:
        return 0, 0


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
            log.warning("ptt_search: over18 gate hit — cookie missing?")
            return

        for entry in soup.select("div.r-ent")[:limit]:
            title_tag = entry.select_one("div.title a")
            if not title_tag:
                continue
            href = title_tag.get("href", "")
            post_url = urljoin(PTT_BASE, href)

            push_tag = entry.select_one("div.nrec span")
            pushes, boos = _parse_push(push_tag.text if push_tag else "0")
            author_tag = entry.select_one("div.meta div.author")

            collected.append({
                "title": title_tag.text.strip(),
                "author": author_tag.text.strip() if author_tag else None,
                "url": post_url,
                "pushes": pushes,
                "boos": boos,
                "comment_count": pushes + boos,
            })

    crawl_log = await log_crawl_start(session, forum.id, "ptt_search", keyword)
    error_msg: str | None = None
    try:
        request = Request.from_url(
            search_url,
            headers={"Cookie": "over18=1"},
        )
        await crawler.run([request])
    except Exception as exc:
        error_msg = str(exc)
        log.error("ptt_search: crawler failed", exc=error_msg)

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
            content=None,
            posted_at=None,
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

    await log_crawl_finish(crawl_log, posts_fetched=len(results), posts_new=new_count, error_msg=error_msg)

    operators_used: dict = {}
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
