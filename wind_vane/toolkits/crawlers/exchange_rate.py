"""Exchange rate toolkit — fetches JPY/TWD spot rate from Bank of Taiwan CSV.

Not stored in DB; caller gets a fresh value every invocation.

BOT CSV columns (1-indexed in their docs, 0-indexed here):
  0: 幣別 (currency)
  1: 現金買入 (cash buy)
  2: 現金賣出 (cash sell)
  3: 即期買入 (spot buy)   ← mid-rate numerator
  4: 即期賣出 (spot sell)  ← mid-rate denominator
  5+: forward rates (unused)
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

import httpx
import structlog

log = structlog.get_logger()

BOT_CSV_URL = "https://rate.bot.com.tw/xrt/flcsv/0/day"
_JPY_IDENTIFIERS = ("JPY", "日幣", "日圓")


def _parse_jpy_row(row: list[str]) -> dict | None:
    """Parse one CSV row; return rate dict if it's a JPY row, else None."""
    if not row or len(row) < 5:
        return None
    currency = row[0].strip()
    if not any(tag in currency for tag in _JPY_IDENTIFIERS):
        return None
    try:
        spot_buy = float(row[3].strip()) if row[3].strip() else 0.0
        spot_sell = float(row[4].strip()) if row[4].strip() else 0.0
    except ValueError:
        return None
    if not spot_buy and not spot_sell:
        return None
    mid = (spot_buy + spot_sell) / 2 if spot_buy and spot_sell else spot_buy or spot_sell
    return {
        "currency": "JPY",
        "rate": round(mid, 6),
        "spot_buy": round(spot_buy, 6),
        "spot_sell": round(spot_sell, 6),
        "captured_at": datetime.now(UTC).isoformat(),
    }


async def exchange_rate() -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(BOT_CSV_URL)
        resp.raise_for_status()

    reader = csv.reader(io.StringIO(resp.text))
    for row in reader:
        result = _parse_jpy_row(row)
        if result:
            return result

    raise RuntimeError("JPY rate not found in Bank of Taiwan CSV")
