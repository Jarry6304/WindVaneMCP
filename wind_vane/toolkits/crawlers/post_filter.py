"""Post filter toolkit — pure scoring logic, reads from DB."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import BlacklistPattern, BoardKeywordAffinity, CommercialSignal, Keyword


async def post_filter(
    session: AsyncSession,
    post: dict,
    keywords: list[str] | None = None,
) -> dict:
    title = post.get("title", "")
    content = post.get("content", "") or ""
    board_id = post.get("board_id")

    # Load keywords from DB if not provided
    if keywords is None:
        kw_rows = (
            await session.execute(select(Keyword).where(Keyword.is_active.is_(True)))
        ).scalars().all()
    else:
        kw_rows = []

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

    # Hard-reject: too short
    if len(title) < 5:
        return {"passed": False, "score": 0, "matched_keywords": [], "reason": "title too short"}

    # Hard-reject: blacklist
    combined = f"{title} {content}"
    for bp in blacklist:
        target = title if bp.applies_to == "title" else (content if bp.applies_to == "content" else combined)
        if bp.pattern_type == "regex":
            if re.search(bp.pattern, target):
                return {"passed": False, "score": 0, "matched_keywords": [], "reason": f"blacklist:{bp.pattern}"}
        else:
            if bp.pattern in target:
                return {"passed": False, "score": 0, "matched_keywords": [], "reason": f"blacklist:{bp.pattern}"}

    score = 0
    matched: list[str] = []

    # Keyword matching
    keyword_list = keywords if keywords is not None else [kw.keyword for kw in kw_rows]
    kw_id_map = {kw.keyword: kw for kw in kw_rows}

    for kw_text in keyword_list:
        if kw_text.lower() in combined.lower():
            matched.append(kw_text)
            kw_obj = kw_id_map.get(kw_text)
            if kw_obj:
                tier_score = {1: 10, 2: 5, 3: 3}.get(kw_obj.tier, 1)
                score += tier_score * kw_obj.weight
                affinity = affinity_map.get(kw_obj.id, 5)
                if affinity == 0:
                    return {"passed": False, "score": 0, "matched_keywords": [], "reason": f"affinity=0:{kw_text}"}
                score += affinity
            else:
                score += 5

    # Commercial signals
    for sig in signals:
        if sig.signal_text in combined:
            score += sig.weight

    # Interaction bonus
    pushes = post.get("pushes", 0) or 0
    score += min(pushes // 10, 10)

    passed = score >= 5 and bool(matched)
    return {
        "passed": passed,
        "score": score,
        "matched_keywords": matched,
        "reason": "ok" if passed else "low score or no keyword match",
    }
