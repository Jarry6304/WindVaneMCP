"""keyword_trend — group posts by day/week and compute trend stats."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import Post


async def keyword_trend(
    session: AsyncSession,
    keyword: str,
    granularity: str = "week",
    weeks: int = 4,
) -> list[dict]:
    since = datetime.now(UTC) - timedelta(weeks=weeks)

    trunc_unit = "day" if granularity == "day" else "week"
    stmt = (
        select(
            func.date_trunc(trunc_unit, Post.posted_at).label("period"),
            func.count(Post.id).label("post_count"),
            func.avg(Post.pushes).label("avg_pushes"),
        )
        .where(
            Post.posted_at >= since,
            text(
                "to_tsvector('simple', title || ' ' || COALESCE(content, '')) "
                "@@ to_tsquery('simple', :kw)"
            ).bindparams(kw=keyword),
        )
        .group_by(text("1"))
        .order_by(text("1"))
    )

    rows = (await session.execute(stmt)).all()
    return [
        {
            "period": r.period.isoformat() if r.period else None,
            "post_count": r.post_count,
            "avg_pushes": float(r.avg_pushes) if r.avg_pushes else 0.0,
        }
        for r in rows
    ]
