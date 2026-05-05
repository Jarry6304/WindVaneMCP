"""query_recommendations — return historically high-priority search queries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import SearchQuery


async def query_recommendations(
    session: AsyncSession,
    topic: str,
    limit: int = 10,
) -> list[dict]:
    stmt = (
        select(SearchQuery)
        .where(
            SearchQuery.is_priority.is_(True),
            SearchQuery.keyword.ilike(f"%{topic}%"),
            SearchQuery.status == "active",
        )
        .order_by(SearchQuery.avg_score.desc().nulls_last())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": sq.id,
            "keyword": sq.keyword,
            "forum_code": sq.forum_code,
            "board_code": sq.board_code,
            "operators": sq.operators,
            "use_count": sq.use_count,
            "hit_rate": float(sq.hit_rate) if sq.hit_rate else None,
            "avg_score": float(sq.avg_score) if sq.avg_score else None,
            "peak_post_count": sq.peak_post_count,
        }
        for sq in rows
    ]
