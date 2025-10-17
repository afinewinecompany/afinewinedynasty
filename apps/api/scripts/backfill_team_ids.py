"""
Backfill my_team_id and my_team_name for existing Fantrax leagues

This script fetches leagues from the Fantrax API for all users with a secret_id
and updates the my_team_id and my_team_name fields in the database.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import engine
from app.db.models import User, FantraxLeague
from app.services.fantrax_secret_api_service import (
    FantraxSecretAPIService,
    get_fantrax_secret_id
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def backfill_team_ids():
    """Backfill team IDs for all existing leagues"""

    async with AsyncSession(engine) as db:
        try:
            # Get all users with Fantrax secret_id
            stmt = select(User).where(User.fantrax_secret_id.isnot(None))
            result = await db.execute(stmt)
            users = result.scalars().all()

            logger.info(f"Found {len(users)} users with Fantrax connections")

            for user in users:
                logger.info(f"\nProcessing user {user.id} ({user.email})...")

                # Get user's secret ID
                secret_id = await get_fantrax_secret_id(db, user.id)

                if not secret_id:
                    logger.warning(f"  Could not decrypt secret_id for user {user.id}")
                    continue

                # Fetch leagues from Fantrax API
                fantrax_service = FantraxSecretAPIService(secret_id)
                api_leagues = await fantrax_service.get_leagues()

                if not api_leagues:
                    logger.warning(f"  No leagues returned from API for user {user.id}")
                    continue

                logger.info(f"  Found {len(api_leagues)} leagues from API")

                # Get existing leagues from database
                stmt = select(FantraxLeague).where(
                    FantraxLeague.user_id == user.id
                )
                result = await db.execute(stmt)
                db_leagues = {league.league_id: league for league in result.scalars().all()}

                updates_made = 0

                # Update leagues with team info
                for api_league in api_leagues:
                    league_id = api_league.get('league_id')

                    if not league_id or league_id not in db_leagues:
                        continue

                    db_league = db_leagues[league_id]

                    # Extract team info from API response
                    teams = api_league.get('teams', [])
                    if teams and len(teams) > 0:
                        # Use first team (typically user only has one team per league)
                        first_team = teams[0]
                        my_team_id = first_team.get('team_id')
                        my_team_name = first_team.get('team_name')

                        if my_team_id:
                            # Update the league
                            db_league.my_team_id = my_team_id
                            db_league.my_team_name = my_team_name
                            updates_made += 1
                            logger.info(f"    Updated {db_league.league_name[:40]}... -> Team: {my_team_name} (ID: {my_team_id})")

                if updates_made > 0:
                    await db.commit()
                    logger.info(f"  ✓ Updated {updates_made} leagues for user {user.id}")
                else:
                    logger.info(f"  No updates needed for user {user.id}")

            logger.info("\n=== Backfill Complete ===")

        except Exception as e:
            logger.error(f"Error during backfill: {str(e)}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(backfill_team_ids())
