"""Rule engine R1-R4 for search_queries auto-classification.

Runs after each UPSERT to search_queries — only re-evaluates the affected row.
Rows with manual_override=True are skipped for status/flag changes (R4).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import SearchQuery


async def apply_rules(session: AsyncSession, query_id: int) -> None:
    result = await session.execute(select(SearchQuery).where(SearchQuery.id == query_id))
    sq = result.scalar_one_or_none()
    if sq is None:
        return

    updates: dict = {}

    if not sq.manual_override:
        is_priority = _check_r1(sq)
        needs_optimization = _check_r2(sq)
        status = _check_r3(sq)

        updates["is_priority"] = is_priority
        updates["needs_optimization"] = needs_optimization
        if status:
            updates["status"] = status

    if updates:
        await session.execute(
            update(SearchQuery).where(SearchQuery.id == query_id).values(**updates)
        )
        await session.flush()


def _check_r1(sq: SearchQuery) -> bool:
    """R1: Mark is_priority=True if any condition holds."""
    avg_score = float(sq.avg_score) if sq.avg_score else 0.0
    hit_rate = float(sq.hit_rate) if sq.hit_rate else 0.0

    r1a = avg_score >= 7 and sq.use_count >= 3
    r1b = hit_rate >= 50 and sq.use_count >= 5
    r1c = sq.peak_post_count >= 3
    return r1a or r1b or r1c


def _check_r2(sq: SearchQuery) -> bool:
    """R2: Mark needs_optimization=True if any condition holds."""
    hit_rate = float(sq.hit_rate) if sq.hit_rate else 0.0
    avg_score = float(sq.avg_score) if sq.avg_score else 0.0

    r2a = hit_rate < 10 and sq.use_count >= 5
    r2b = avg_score < 3 and sq.use_count >= 5
    r2c = sq.passed_posts == 0 and sq.use_count >= 3
    return r2a or r2b or r2c


def _check_r3(sq: SearchQuery) -> str | None:
    """R3: Deprecate queries unused for 90+ days."""
    if sq.last_used_at and sq.last_used_at < datetime.now(UTC) - timedelta(days=90):
        return "deprecated"
    return None
