"""
Test database connection
"""
import asyncio
import asyncpg
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# Make sure we're loading the env from the right place
os.chdir(Path(__file__).parent.parent.parent)

from app.core.config import settings

async def test_connection():
    """Test database connection."""
    print("Testing database connection...")

    # Get and display the connection string
    db_url = str(settings.SQLALCHEMY_DATABASE_URI)
    print(f"Original URL: {db_url[:50]}...")  # Show first 50 chars only

    # Parse for asyncpg
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    print(f"Parsed URL: {db_url[:50]}...")

    try:
        # Try to connect
        conn = await asyncpg.connect(db_url)
        print("Connection successful!")

        # Test query
        result = await conn.fetchval("SELECT COUNT(*) FROM milb_game_logs")
        print(f"Current records in milb_game_logs: {result}")

        await conn.close()
        print("Connection closed successfully.")

    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())