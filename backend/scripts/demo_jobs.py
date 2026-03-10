"""Demo job runner entrypoint.

Usage:
    docker compose exec api python scripts/demo_jobs.py status
    docker compose exec api python scripts/demo_jobs.py dunning
    docker compose exec api python scripts/demo_jobs.py trials
    docker compose exec api python scripts/demo_jobs.py purge
    docker compose exec api python scripts/demo_jobs.py advance --days 7
    docker compose exec api python scripts/demo_jobs.py advance --days 14
"""

import argparse
import asyncio
import json
import os
import sys

# Ensure the app package is importable (same pattern as scripts/seed_demo.py)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main() -> None:
    from demo.jobs import (
        advance_invoice_dates,
        run_dunning,
        run_generate_platform_invoices,
        run_purge,
        run_trials,
        show_status,
    )

    parser = argparse.ArgumentParser(description="Demo job runner")
    parser.add_argument(
        "command",
        choices=["dunning", "trials", "purge", "advance", "status", "generate-invoices"],
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Dagen om facturen te verschuiven (alleen bij 'advance')",
    )
    parser.add_argument(
        "--month",
        type=str,
        default=None,
        help="'current' voor huidige maand, of MM/YYYY (alleen bij 'generate-invoices')",
    )
    args = parser.parse_args()

    if args.command == "dunning":
        result = await run_dunning()
    elif args.command == "trials":
        result = await run_trials()
    elif args.command == "purge":
        result = await run_purge()
    elif args.command == "advance":
        result = await advance_invoice_dates(args.days)
    elif args.command == "generate-invoices":
        from datetime import datetime
        period_year, period_month = None, None
        if args.month == "current":
            now = datetime.now()
            period_year, period_month = now.year, now.month
        elif args.month and "/" in args.month:
            parts = args.month.split("/")
            period_month, period_year = int(parts[0]), int(parts[1])
        result = await run_generate_platform_invoices(period_year, period_month)
    elif args.command == "status":
        result = await show_status()

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
