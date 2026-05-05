"""posts_query — pure DB query, no crawling.

Keyword filter uses PostgreSQL full-text search (GIN index).
On other dialects (e.g., SQLite in tests) it falls back to LIKE matching.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import Forum, ForumBoard, Post


def _keyword_condition(keywords: list[str], dialect_name: str):
    """Return a WHERE condition for keyword search, dialect-aware."""
    if dialect_name == "postgresql":
        kw_expr = " | ".join(keywords)
        return text(
            "to_tsvector('simple', title || ' ' || COALESCE(content, '')) "
            "@@ to_tsquery('simple', :kw)"
        ).bindparams(kw=kw_expr)
    # Fallback: LIKE on title (SQLite / testing)
    return or_(*(Post.title.ilike(f"%{kw}%") for kw in keywords))


async def posts_query(
    session: AsyncSession,
    keywords: list[str] | None = None,
    forum_codes: list[str] | None = None,
    board_codes: list[str] | None = None,
    posted_after: datetime | None = None,
    min_pushes: int | None = None,
    min_score: int | None = None,
    limit: int = 50,
) -> list[dict]:
    stmt = select(Post)
    conditions = []

    if forum_codes:
        forum_ids = (
            await session.execute(select(Forum.id).where(Forum.code.in_(forum_codes)))
        ).scalars().all()
        conditions.append(Post.forum_id.in_(forum_ids))

    if board_codes:
        board_ids = (
            await session.execute(select(ForumBoard.id).where(ForumBoard.board_code.in_(board_codes)))
        ).scalars().all()
        conditions.append(Post.board_id.in_(board_ids))

    if posted_after:
        dt = posted_after.replace(tzinfo=None) if posted_after.tzinfo else posted_after
        conditions.append(Post.posted_at >= dt)

    if min_pushes is not None:
        conditions.append(Post.pushes >= min_pushes)

    if min_score is not None:
        conditions.append(Post.latest_score >= min_score)

    if keywords:
        conn = await session.connection()
        conditions.append(_keyword_condition(keywords, conn.dialect.name))

    if conditions:
        stmt = stmt.where(and_(*conditions))

    stmt = stmt.order_by(Post.posted_at.desc().nulls_last()).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()

    return [
        {
            "id": p.id,
            "title": p.title,
            "author": p.author,
            "url": p.url,
            "pushes": p.pushes,
            "boos": p.boos,
            "comment_count": p.comment_count,
            "posted_at": p.posted_at.isoformat() if p.posted_at else None,
            "latest_score": p.latest_score,
            "matched_keywords": p.matched_keywords,
        }
        for p in rows
    ]
