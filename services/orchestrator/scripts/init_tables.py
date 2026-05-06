import asyncio
import os
import sys

# Add service dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Models implicitly loaded when Base is loaded
# Ensure models are imported so Base.metadata reflects all tables
from ..db import base as _db_base
from ..db import close_db, init_db

_ = _db_base.Base  # referenced to avoid unused-import warning


async def main():
    await init_db()
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
