"""WindVane MCP Server — FastMCP entry point.

Start with: uv run python -m wind_vane.server
IMPORTANT: All logging goes to file/stderr. stdout is reserved for MCP stdio protocol.
"""

from __future__ import annotations

from fastmcp import FastMCP

from wind_vane.db.connection import AsyncSessionLocal
from wind_vane.log import setup_logging
from wind_vane.toolkits.crawlers.bahamut_search import bahamut_search
from wind_vane.toolkits.crawlers.dcard_search import dcard_search
from wind_vane.toolkits.crawlers.exchange_rate import exchange_rate
from wind_vane.toolkits.crawlers.komica_search import komica_search
from wind_vane.toolkits.crawlers.mobile01_search import mobile01_search
from wind_vane.toolkits.crawlers.post_filter import post_filter
from wind_vane.toolkits.crawlers.ptt_search import ptt_search
from wind_vane.toolkits.queries.keyword_trend import keyword_trend
from wind_vane.toolkits.queries.posts_query import posts_query
from wind_vane.toolkits.queries.query_recommendations import query_recommendations
from wind_vane.toolkits.queries.query_review import query_review, query_review_update
from wind_vane.toolkits.queries.top_posts import top_posts

setup_logging()

mcp = FastMCP("wind-vane")


# ── Crawler toolkits ──────────────────────────────────────────────────────────

@mcp.tool()
async def tool_ptt_search(
    keyword: str,
    board_code: str,
    limit: int = 20,
    min_recommend: int | None = None,
    title_only: bool = False,
    author: str | None = None,
) -> list[dict]:
    """Search PTT board for posts matching keyword. Supports advanced operators."""
    async with AsyncSessionLocal() as session:
        return await ptt_search(
            session, keyword, board_code, limit, min_recommend, title_only, author
        )


@mcp.tool()
async def tool_bahamut_search(
    keyword: str,
    scope: str = "board",
    board_code: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Search Bahamut forum. scope='board' requires board_code; scope='global' searches all."""
    async with AsyncSessionLocal() as session:
        return await bahamut_search(session, keyword, scope, board_code, limit)


@mcp.tool()
async def tool_mobile01_search(
    keyword: str,
    board_code: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Search Mobile01. Optionally restrict to a specific sub-forum by board_code."""
    async with AsyncSessionLocal() as session:
        return await mobile01_search(session, keyword, board_code, limit)


@mcp.tool()
async def tool_dcard_search(
    keyword: str,
    board_code: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Search Dcard via Google. Returns title + snippet only (no full content)."""
    async with AsyncSessionLocal() as session:
        return await dcard_search(session, keyword, board_code, limit)


@mcp.tool()
async def tool_komica_search(
    keyword: str,
    board_code: str,
    limit: int = 10,
) -> list[dict]:
    """Crawl Komica board latest pages and filter by keyword."""
    async with AsyncSessionLocal() as session:
        return await komica_search(session, keyword, board_code, limit)


@mcp.tool()
async def tool_exchange_rate() -> dict:
    """Fetch current JPY/TWD exchange rate from Bank of Taiwan (not stored in DB)."""
    return await exchange_rate()


@mcp.tool()
async def tool_post_filter(
    post: dict,
    keywords: list[str] | None = None,
) -> dict:
    """Score a post against keywords, blacklist, and commercial signals. Returns passed/score."""
    async with AsyncSessionLocal() as session:
        return await post_filter(session, post, keywords)


# ── Query toolkits ────────────────────────────────────────────────────────────

@mcp.tool()
async def tool_posts_query(
    keywords: list[str] | None = None,
    forum_codes: list[str] | None = None,
    board_codes: list[str] | None = None,
    posted_after: str | None = None,
    min_pushes: int | None = None,
    min_score: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """Query stored posts with filters. posted_after is ISO8601 string."""
    from datetime import datetime
    dt = datetime.fromisoformat(posted_after) if posted_after else None
    async with AsyncSessionLocal() as session:
        return await posts_query(session, keywords, forum_codes, board_codes, dt, min_pushes, min_score, limit)


@mcp.tool()
async def tool_keyword_trend(
    keyword: str,
    granularity: str = "week",
    weeks: int = 4,
) -> list[dict]:
    """Show post volume trend for a keyword. granularity: 'day' or 'week'."""
    async with AsyncSessionLocal() as session:
        return await keyword_trend(session, keyword, granularity, weeks)


@mcp.tool()
async def tool_top_posts(
    forum_code: str | None = None,
    board_code: str | None = None,
    posted_after: str | None = None,
    order_by: str = "pushes",
    limit: int = 20,
) -> list[dict]:
    """Get top posts ordered by pushes or score. posted_after is ISO8601 string."""
    from datetime import datetime
    dt = datetime.fromisoformat(posted_after) if posted_after else None
    async with AsyncSessionLocal() as session:
        return await top_posts(session, forum_code, board_code, dt, order_by, limit)


@mcp.tool()
async def tool_query_recommendations(
    topic: str,
    limit: int = 10,
) -> list[dict]:
    """Return historically priority search queries matching topic. Use before crawling."""
    async with AsyncSessionLocal() as session:
        return await query_recommendations(session, topic, limit)


@mcp.tool()
async def tool_query_review(
    filter_type: str = "needs_optimization",
    limit: int = 20,
) -> list[dict]:
    """List search queries by status. filter_type: 'needs_optimization', 'deprecated', or 'all'."""
    async with AsyncSessionLocal() as session:
        return await query_review(session, filter_type, limit)


@mcp.tool()
async def tool_query_review_update(
    query_id: int,
    reason: str,
    is_priority: bool | None = None,
    needs_optimization: bool | None = None,
    status: str | None = None,
) -> dict:
    """Write LLM override to a search_query row. Sets manual_override=True."""
    async with AsyncSessionLocal() as session:
        return await query_review_update(session, query_id, reason, is_priority, needs_optimization, status)


if __name__ == "__main__":
    mcp.run()
