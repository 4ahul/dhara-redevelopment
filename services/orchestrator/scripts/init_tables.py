import asyncio
import sys
import os

# Add service dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db import init_db, close_db

async def main():
    print("🚀 Initializing orchestrator_db tables...")
    await init_db()
    await close_db()
    print("✅ Tables created successfully.")

if __name__ == "__main__":
    asyncio.run(main())
