"""Backfills daily_booking_stats from existing appointment history — useful in
a fresh dev/demo environment where the nightly Celery Beat rollup (docs plan
§12) hasn't had a chance to run yet.

Usage:
    python -m scripts.backfill_analytics --days 90
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from app.db.session import async_session_factory
from app.tasks.analytics import rollup_day


async def backfill(days: int) -> None:
    today = datetime.now(UTC).date()
    async with async_session_factory() as db:
        for offset in range(days, -1, -1):
            target_date = today - timedelta(days=offset)
            await rollup_day(db, target_date)
            print(f"Rolled up {target_date.isoformat()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=90, help="How many past days to backfill (plus today).")
    args = parser.parse_args()
    asyncio.run(backfill(args.days))


if __name__ == "__main__":
    main()
