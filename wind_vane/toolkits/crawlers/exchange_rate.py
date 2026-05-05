"""Exchange rate toolkit — fetches JPY/TWD from Bank of Taiwan CSV (no DB storage)."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

import httpx
import structlog

log = structlog.get_logger()

BOT_CSV_URL = "https://rate.bot.com.tw/xrt/flcsv/0/day"


async def exchange_rate() -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(BOT_CSV_URL)
        resp.raise_for_status()

    reader = csv.reader(io.StringIO(resp.text))
    for row in reader:
        if not row:
            continue
        currency = row[0].strip()
        if "JPY" in currency or "日幣" in currency or "日圓" in currency:
            try:
                cash_buy = float(row[2].strip()) if len(row) > 2 else 0.0
                cash_sell = float(row[3].strip()) if len(row) > 3 else 0.0
                spot = (cash_buy + cash_sell) / 2 if cash_buy and cash_sell else cash_buy or cash_sell
                return {
                    "currency": "JPY",
                    "rate": round(spot, 6),
                    "captured_at": datetime.now(UTC).isoformat(),
                }
            except (ValueError, IndexError):
                continue

    raise RuntimeError("JPY rate not found in Bank of Taiwan CSV")
