"""top_posts — query hottest posts by pushes or score."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import Forum, ForumBoard, Post


async def top_posts(
    session: AsyncSession,
    forum_code: str | None = None,
    board_code: str | None = None,
    posted_after: datetime | None = None,
    order_by: str = "pushes",
    limit: int = 20,
) -> list[dict]:
    stmt = select(Post)
    conditions = []

    if forum_code:
        forum_id = (
            await session.execute(select(Forum.id).where(Forum.code == forum_code))
        ).scalar_one()
        conditions.append(Post.forum_id == forum_id)

    if board_code:
        board_id = (
            await session.execute(
                select(ForumBoard.id).where(ForumBoard.board_code == board_code)
            )
        ).scalar_one()
        conditions.append(Post.board_id == board_id)

    if posted_after:
        conditions.append(Post.posted_at >= posted_after)

    if conditions:
        from sqlalchemy import and_
        stmt = stmt.where(and_(*conditions))

    sort_col = Post.pushes if order_by == "pushes" else Post.latest_score
    stmt = stmt.order_by(sort_col.desc().nulls_last()).limit(limit)

    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "title": p.title,
            "author": p.author,
            "url": p.url,
            "pushes": p.pushes,
            "latest_score": p.latest_score,
            "posted_at": p.posted_at.isoformat() if p.posted_at else None,
        }
        for p in rows
    ]
