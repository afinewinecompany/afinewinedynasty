"""
Clear existing data from milb_game_logs table.
"""

import asyncio
import asyncpg
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.core.config import settings


async def clear_milb_game_logs():
    """Clear all data from milb_game_logs table."""
    try:
        # Parse the connection string
        db_url = str(settings.SQLALCHEMY_DATABASE_URI)
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

        # Connect to database
        conn = await asyncpg.connect(db_url)

        # Get current count
        count = await conn.fetchval("SELECT COUNT(*) FROM milb_game_logs")
        print(f"Current records in milb_game_logs: {count:,}")

        if count > 0:
            response = input(f"\nAre you sure you want to delete {count:,} records? (yes/no): ")
            if response.lower() != 'yes':
                print("Operation cancelled.")
                await conn.close()
                return

            # Clear the table
            print("Clearing milb_game_logs table...")
            await conn.execute("TRUNCATE TABLE milb_game_logs RESTART IDENTITY CASCADE")
            print("Table cleared successfully!")

            # Also remove checkpoint file if it exists
            checkpoint_file = Path(__file__).parent / 'collection_checkpoint.json'
            if checkpoint_file.exists():
                checkpoint_file.unlink()
                print("Checkpoint file removed!")
        else:
            print("Table is already empty.")

        await conn.close()

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(clear_milb_game_logs())