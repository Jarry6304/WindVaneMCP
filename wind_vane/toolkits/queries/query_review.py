"""query_review and query_review_update — LLM-driven query optimization."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import SearchQuery


async def query_review(
    session: AsyncSession,
    filter: str = "needs_optimization",
    limit: int = 20,
) -> list[dict]:
    stmt = select(SearchQuery)

    if filter == "needs_optimization":
        stmt = stmt.where(SearchQuery.needs_optimization.is_(True))
    elif filter == "deprecated":
        stmt = stmt.where(SearchQuery.status == "deprecated")

    stmt = stmt.order_by(SearchQuery.last_used_at.desc()).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()

    return [
        {
            "id": sq.id,
            "keyword": sq.keyword,
            "forum_code": sq.forum_code,
            "board_code": sq.board_code,
            "use_count": sq.use_count,
            "hit_rate": float(sq.hit_rate) if sq.hit_rate else None,
            "avg_score": float(sq.avg_score) if sq.avg_score else None,
            "status": sq.status,
            "needs_optimization": sq.needs_optimization,
            "manual_override": sq.manual_override,
            "optimization_note": sq.optimization_note,
        }
        for sq in rows
    ]


async def query_review_update(
    session: AsyncSession,
    query_id: int,
    reason: str,
    is_priority: bool | None = None,
    needs_optimization: bool | None = None,
    status: str | None = None,
) -> dict:
    values: dict = {
        "manual_override": True,
        "override_reason": reason,
        "override_at": datetime.now(UTC),
        "override_by": "llm",
    }
    if is_priority is not None:
        values["is_priority"] = is_priority
    if needs_optimization is not None:
        values["needs_optimization"] = needs_optimization
    if status is not None:
        values["status"] = status

    await session.execute(
        update(SearchQuery).where(SearchQuery.id == query_id).values(**values)
    )
    await session.commit()
    return {"updated": query_id, "values": values}
