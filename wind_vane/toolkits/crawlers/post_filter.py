"""Post filter toolkit — pure scoring logic, reads from DB.

Scoring breakdown:
  Keyword tier   : tier1=10pt, tier2=5pt, tier3=3pt  × keyword.weight
  Affinity bonus : board_keyword_affinity.affinity_score (0=hard-reject)
  Commercial     : commercial_signals.weight per hit
  Pushes bonus   : min(pushes // 10, 10)
  Pass threshold : score >= 5 AND at least one keyword matched
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import BlacklistPattern, BoardKeywordAffinity, CommercialSignal, Keyword, Post

_TIER_SCORE = {1: 10, 2: 5, 3: 3}


async def post_filter(
    session: AsyncSession,
    post: dict,
    keywords: list[str] | None = None,
) -> dict:
    title = post.get("title", "")
    content = post.get("content", "") or ""
    board_id: int | None = post.get("board_id")
    pushes: int = post.get("pushes", 0) or 0

    # Load keyword rows from DB (always, even when list is pre-supplied,
    # so we can apply tier weights and affinity scores)
    kw_rows = (
        await session.execute(select(Keyword).where(Keyword.is_active.is_(True)))
    ).scalars().all()
    kw_id_map = {kw.keyword: kw for kw in kw_rows}

    # If caller supplied a list, restrict matching to those keywords only
    keyword_list = keywords if keywords is not None else [kw.keyword for kw in kw_rows]

    blacklist = (
        await session.execute(select(BlacklistPattern).where(BlacklistPattern.is_active.is_(True)))
    ).scalars().all()

    signals = (
        await session.execute(select(CommercialSignal).where(CommercialSignal.is_active.is_(True)))
    ).scalars().all()

    affinity_map: dict[int, int] = {}
    if board_id:
        affinities = (
            await session.execute(
                select(BoardKeywordAffinity).where(BoardKeywordAffinity.board_id == board_id)
            )
        ).scalars().all()
        affinity_map = {a.keyword_id: a.affinity_score for a in affinities}

    # ── Hard-reject: title too short ──────────────────────────────────────────
    if len(title) < 5:
        return {"passed": False, "score": 0, "matched_keywords": [], "reason": "title too short"}

    # ── Hard-reject: blacklist ────────────────────────────────────────────────
    combined = f"{title} {content}"
    for bp in blacklist:
        if bp.applies_to == "title":
            target = title
        elif bp.applies_to == "content":
            target = content
        else:
            target = combined

        hit = (
            bool(re.search(bp.pattern, target))
            if bp.pattern_type == "regex"
            else bp.pattern in target
        )
        if hit:
            return {
                "passed": False,
                "score": 0,
                "matched_keywords": [],
                "reason": f"blacklist:{bp.pattern}",
            }

    # ── Keyword scoring ───────────────────────────────────────────────────────
    score = 0
    matched: list[str] = []

    for kw_text in keyword_list:
        if kw_text.lower() not in combined.lower():
            continue
        matched.append(kw_text)
        kw_obj = kw_id_map.get(kw_text)
        if kw_obj:
            tier_pts = _TIER_SCORE.get(kw_obj.tier, 1) * kw_obj.weight
            score += tier_pts
            # Affinity: default 5 if no record; 0 = hard-reject
            affinity = affinity_map.get(kw_obj.id, 5)
            if affinity == 0:
                return {
                    "passed": False,
                    "score": 0,
                    "matched_keywords": [],
                    "reason": f"affinity=0:{kw_text}",
                }
            score += affinity
        else:
            # Keyword not in DB (explicitly supplied, no weight info) → flat score
            score += 5

    # ── Commercial signals ────────────────────────────────────────────────────
    for sig in signals:
        if sig.signal_text in combined:
            score += sig.weight

    # ── Interaction bonus ─────────────────────────────────────────────────────
    score += min(pushes // 10, 10)

    # ── Verdict ───────────────────────────────────────────────────────────────
    passed = score >= 5 and bool(matched)
    return {
        "passed": passed,
        "score": score,
        "matched_keywords": matched,
        "reason": "ok" if passed else "low score or no keyword match",
    }


async def filter_and_update_post(
    session: AsyncSession,
    post: Post,
    keywords: list[str] | None = None,
) -> dict:
    """Run post_filter on a Post ORM object and write score back to the DB row."""
    result = await post_filter(
        session,
        {
            "title": post.title,
            "content": post.content,
            "pushes": post.pushes,
            "board_id": post.board_id,
        },
        keywords=keywords,
    )
    post.latest_score = result["score"]
    post.matched_keywords = result["matched_keywords"] or None
    return result
