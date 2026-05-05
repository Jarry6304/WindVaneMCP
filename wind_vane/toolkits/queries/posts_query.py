"""posts_query — pure DB query, no crawling."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import Forum, ForumBoard, Post


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
        conditions.append(Post.posted_at >= posted_after)

    if min_pushes is not None:
        conditions.append(Post.pushes >= min_pushes)

    if min_score is not None:
        conditions.append(Post.latest_score >= min_score)

    if keywords:
        kw_expr = " | ".join(keywords)
        conditions.append(
            text(
                f"to_tsvector('simple', title || ' ' || COALESCE(content, '')) "
                f"@@ to_tsquery('simple', :kw)"
            ).bindparams(kw=kw_expr)
        )

    if conditions:
        stmt = stmt.where(and_(*conditions))

    stmt = stmt.order_by(Post.posted_at.desc()).limit(limit)
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
