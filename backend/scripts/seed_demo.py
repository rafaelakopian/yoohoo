"""Demo seed entrypoint.

Usage:
    docker compose exec api python scripts/seed_demo.py              # Seed demo data
    docker compose exec api python scripts/seed_demo.py --reset      # Teardown + re-seed
    docker compose exec api python scripts/seed_demo.py --reset --no-seed   # Teardown only
"""

import asyncio
import os
import sys

# Ensure the app package is importable (same pattern as scripts/seed.py)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main() -> None:
    from demo.runner import seed_all, teardown_all

    do_reset = "--reset" in sys.argv
    do_seed = "--no-seed" not in sys.argv

    if do_reset:
        await teardown_all()

    if do_seed:
        await seed_all()


if __name__ == "__main__":
    asyncio.run(main())
