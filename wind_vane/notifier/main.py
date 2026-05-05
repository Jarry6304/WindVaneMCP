"""Notifier — independent scheduler module, no MCP dependency.

Deploy via Windows Task Scheduler:
    schtasks /create /tn "WindVane Notifier" ^
             /tr "uv --directory <project_path> run python -m wind_vane.notifier" ^
             /sc daily /st 09:00
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from email.mime.text import MIMEText

import aiosmtplib
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.config import settings
from wind_vane.db.connection import AsyncSessionLocal
from wind_vane.db.models import SearchQuery, SystemNotification
from wind_vane.log import setup_logging

log = structlog.get_logger()


async def run_notification_check() -> None:
    async with AsyncSessionLocal() as session:
        if await _is_quarterly_review_due(session):
            notif = await _create_notification(session, "quarterly_review")
            await _send_email(notif, _build_quarterly_email(notif))

        if await _is_rule_drift_triggered(session):
            notif = await _create_notification(session, "rule_drift")
            await _send_email(notif, _build_rule_drift_email(notif))

        rigid_queries = await _find_rigid_queries(session)
        if rigid_queries:
            notif = await _create_notification(
                session, "rigidity_warning", scope={"query_ids": [q.id for q in rigid_queries]}
            )
            await _send_email(notif, _build_rigidity_email(rigid_queries))

        await session.commit()


async def _is_quarterly_review_due(session: AsyncSession) -> bool:
    oldest = (
        await session.execute(select(func.min(SearchQuery.created_at)))
    ).scalar_one_or_none()
    if not oldest:
        return False
    oldest_utc = oldest.replace(tzinfo=UTC) if oldest.tzinfo is None else oldest
    if oldest_utc < datetime.now(UTC) - timedelta(days=90):
        last = (
            await session.execute(
                select(SystemNotification)
                .where(
                    SystemNotification.notification_type == "quarterly_review",
                    SystemNotification.triggered_at >= datetime.now(UTC) - timedelta(days=90),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        return last is None
    return False


async def _is_rule_drift_triggered(session: AsyncSession) -> bool:
    count = (
        await session.execute(
            select(func.count(SearchQuery.id)).where(SearchQuery.needs_optimization.is_(True))
        )
    ).scalar_one()
    if count < 20:
        return False
    last = (
        await session.execute(
            select(SystemNotification)
            .where(
                SystemNotification.notification_type == "rule_drift",
                SystemNotification.triggered_at >= datetime.now(UTC) - timedelta(days=30),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return last is None


async def _find_rigid_queries(session: AsyncSession) -> list[SearchQuery]:
    cutoff = datetime.now(UTC) - timedelta(days=30)
    rows = (
        await session.execute(
            select(SearchQuery).where(
                SearchQuery.manual_override.is_(True),
                SearchQuery.last_used_at >= cutoff,
            )
        )
    ).scalars().all()
    return [q for q in rows if _is_hit_rate_declining(q)]


def _is_hit_rate_declining(sq: SearchQuery) -> bool:
    hit_rate = float(sq.hit_rate) if sq.hit_rate else 0.0
    return hit_rate < 20 and (sq.use_count or 0) >= 5


async def _create_notification(
    session: AsyncSession,
    notification_type: str,
    scope: dict | None = None,
) -> SystemNotification:
    notif = SystemNotification(
        notification_type=notification_type,
        scope=scope,
        email_to=settings.notifier_email_to,
    )
    session.add(notif)
    await session.flush()
    return notif


def _build_quarterly_email(notif: SystemNotification) -> str:
    return (
        "風向計季度檢視提醒\n\n"
        "系統已累積超過 90 天的搜尋查詢資料，建議進行季度檢視。\n"
        "請透過 Claude 執行 tool_query_review 檢視待優化查詢。\n"
    )


def _build_rule_drift_email(notif: SystemNotification) -> str:
    return (
        "風向計規則漂移警示\n\n"
        "目前有 20 筆以上的查詢被標記為 needs_optimization。\n"
        "建議透過 Claude 執行 tool_query_review(filter_type='needs_optimization') 進行優化。\n"
    )


def _build_rigidity_email(queries: list[SearchQuery]) -> str:
    lines = ["風向計僵化查詢警示\n"]
    for q in queries[:10]:
        lines.append(f"- [{q.forum_code}/{q.board_code}] {q.keyword}  命中率:{q.hit_rate}%")
    lines.append("\n這些查詢已被人工鎖定，但近期命中率持續偏低，建議評估是否解除鎖定。")
    return "\n".join(lines)


async def _send_email(notif: SystemNotification, body: str) -> None:
    if not settings.notifier_enabled or not settings.notifier_email_to:
        log.warning("notifier: email disabled or no recipient configured")
        return

    subject_map = {
        "quarterly_review": "[風向計] 季度檢視提醒",
        "rule_drift": "[風向計] 規則漂移警示",
        "rigidity_warning": "[風向計] 僵化查詢警示",
    }
    subject = subject_map.get(notif.notification_type, "[風向計] 通知")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.notifier_email_from
    msg["To"] = settings.notifier_email_to

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=False,
            start_tls=settings.smtp_use_tls,
        )
        notif.email_sent = True
        notif.email_sent_at = datetime.now(UTC)
        log.info("notifier: email sent", type=notif.notification_type)
    except Exception as exc:
        log.error("notifier: failed to send email", exc=str(exc))


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run_notification_check())
