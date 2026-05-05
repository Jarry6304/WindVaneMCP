"""Shared UPSERT helpers for posts and search_queries."""

from datetime import UTC, datetime, date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import Post, SearchQuery
from wind_vane.rules.engine import apply_rules


def _update_pushes_history(
    pushes_history: str | None,
    pushes_history_dt: str | None,
    new_pushes: int,
    today_str: str,
) -> tuple[str, str]:
    history = pushes_history.split(";") if pushes_history else []
    dates = pushes_history_dt.split(";") if pushes_history_dt else []

    if not history:
        return str(new_pushes), today_str

    if dates and dates[-1] == today_str:
        history[-1] = str(new_pushes)
        return ";".join(history), ";".join(dates)

    if history and int(history[-1]) == new_pushes:
        return ";".join(history), ";".join(dates)

    history.append(str(new_pushes))
    dates.append(today_str)

    if len(history) > 10:
        history = history[-10:]
        dates = dates[-10:]

    return ";".join(history), ";".join(dates)


async def upsert_post(
    session: AsyncSession,
    *,
    forum_id: int,
    board_id: int | None,
    native_post_id: str | None,
    url: str,
    title: str,
    author: str | None,
    content: str | None,
    posted_at: datetime | None,
    pushes: int,
    boos: int,
    comment_count: int,
    latest_score: int | None = None,
    matched_keywords: list[str] | None = None,
) -> tuple[Post, bool]:
    """UPSERT a post by URL. Returns (post, is_new)."""
    result = await session.execute(select(Post).where(Post.url == url))
    existing = result.scalar_one_or_none()
    today_str = date.today().isoformat()
    now = datetime.now(UTC)

    if existing is None:
        new_history, new_history_dt = _update_pushes_history(None, None, pushes, today_str)
        post = Post(
            forum_id=forum_id,
            board_id=board_id,
            native_post_id=native_post_id,
            url=url,
            title=title,
            author=author,
            content=content,
            posted_at=posted_at,
            pushes=pushes,
            boos=boos,
            comment_count=comment_count,
            pushes_history=new_history,
            pushes_history_dt=new_history_dt,
            latest_score=latest_score,
            matched_keywords=matched_keywords,
            first_crawled_at=now,
            last_crawled_at=now,
            crawl_count=1,
        )
        session.add(post)
        await session.flush()
        return post, True

    new_history, new_history_dt = _update_pushes_history(
        existing.pushes_history, existing.pushes_history_dt, pushes, today_str
    )
    existing.pushes = pushes
    existing.boos = boos
    existing.comment_count = comment_count
    existing.pushes_history = new_history
    existing.pushes_history_dt = new_history_dt
    existing.last_crawled_at = now
    existing.crawl_count = (existing.crawl_count or 0) + 1
    if content:
        existing.content = content
    if latest_score is not None:
        existing.latest_score = latest_score
    if matched_keywords is not None:
        existing.matched_keywords = matched_keywords

    await session.flush()
    return existing, False


async def upsert_search_query(
    session: AsyncSession,
    *,
    keyword: str,
    forum_code: str,
    board_code: str,
    operators: dict | None,
    posts_found: int,
    passed: int,
    avg_score: float | None,
    peak_count: int,
) -> SearchQuery:
    """UPSERT search_queries and trigger rule engine on that row."""
    result = await session.execute(
        select(SearchQuery).where(
            SearchQuery.keyword == keyword,
            SearchQuery.forum_code == forum_code,
            SearchQuery.board_code == board_code,
        )
    )
    sq = result.scalar_one_or_none()
    now = datetime.now(UTC)

    if sq is None:
        sq = SearchQuery(
            keyword=keyword,
            forum_code=forum_code,
            board_code=board_code,
            operators=operators,
            use_count=1,
            total_posts_found=posts_found,
            passed_posts=passed,
            hit_rate=round(passed / posts_found * 100, 2) if posts_found else None,
            avg_score=avg_score,
            peak_post_count=peak_count,
            last_used_at=now,
        )
        session.add(sq)
    else:
        sq.use_count = (sq.use_count or 0) + 1
        sq.total_posts_found = (sq.total_posts_found or 0) + posts_found
        sq.passed_posts = (sq.passed_posts or 0) + passed
        total = sq.total_posts_found
        sq.hit_rate = round(sq.passed_posts / total * 100, 2) if total else None
        if avg_score is not None:
            prev = float(sq.avg_score) if sq.avg_score else 0.0
            sq.avg_score = round((prev * (sq.use_count - 1) + avg_score) / sq.use_count, 2)
        sq.peak_post_count = max(sq.peak_post_count or 0, peak_count)
        sq.last_used_at = now

    await session.flush()
    await apply_rules(session, sq.id)
    return sq
