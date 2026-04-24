import asyncio
import os
import sys

# Add service dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.orchestrator.db import close_db, init_db


async def main():
    print("🚀 Initializing orchestrator_db tables...")
    await init_db()
    await close_db()
    print("✅ Tables created successfully.")

if __name__ == "__main__":
    asyncio.run(main())



