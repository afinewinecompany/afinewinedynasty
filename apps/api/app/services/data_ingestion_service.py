import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

# from app.db.database import get_async_session
from app.db.models import Prospect, ProspectStats, User
from app.services.mlb_api_service import MLBAPIClient, MLBStatsAPIError
from app.core.config import settings

logger = logging.getLogger(__name__)


class DataIngestionError(Exception):
    """Custom exception for data ingestion errors."""
    pass


class DataIngestionService:
    """Service for ingesting prospect data from MLB Stats API."""

    def __init__(self, db: Optional[AsyncSession] = None):
        self.mlb_client = MLBAPIClient()
        self.db = db  # Optional database session for direct use
        self.ingestion_stats = {
            "prospects_processed": 0,
            "prospects_added": 0,
            "prospects_updated": 0,
            "stats_records_added": 0,
            "errors": []
        }

    async def run_daily_ingestion(self) -> Dict[str, Any]:
        """
        Run complete daily data ingestion pipeline.

        Returns:
            Dict containing ingestion statistics and results
        """
        logger.info("Starting daily data ingestion pipeline")
        start_time = datetime.now()

        try:
            # Reset statistics
            self._reset_stats()

            # async with self.mlb_client as client:
            #     # Get database session
            #     async for session in get_async_session():
            #         try:
            #             # Step 1: Ingest prospect basic information
            #             await self._ingest_prospects_data(client, session)

            #             # Step 2: Ingest current season statistics
            #             await self._ingest_current_season_stats(client, session)

            #             # Commit all changes
            #             await session.commit()

            #         except Exception as e:
            #             await session.rollback()
            #             raise
            #         finally:
            #             await session.close()
            #         break  # Only take first session from generator

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            result = {
                **self.ingestion_stats,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "status": "completed" if not self.ingestion_stats["errors"] else "completed_with_errors"
            }

            logger.info(f"Daily ingestion completed in {duration:.2f}s: {result}")
            return result

        except Exception as e:
            logger.error(f"Daily ingestion pipeline failed: {str(e)}")
            self.ingestion_stats["errors"].append({
                "type": "pipeline_failure",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            })
            raise DataIngestionError(f"Ingestion pipeline failed: {str(e)}")

    async def _ingest_prospects_data(self, client: MLBAPIClient, session: AsyncSession) -> None:
        """
        Ingest prospect basic information from MLB API.

        Args:
            client: MLB API client
            session: Database session
        """
        logger.info("Ingesting prospects basic data")

        try:
            # Get prospects data from MLB API
            # Note: MLB API doesn't have a direct prospects endpoint, so we'll simulate
            # by getting players from minor league teams
            teams_data = await client.get_teams_data("11,12,13,14")  # Minor league sport IDs

            if not teams_data.get("teams"):
                logger.warning("No teams data received from MLB API")
                return

            for team in teams_data["teams"][:10]:  # Limit to first 10 teams for demo
                try:
                    # Get team roster (simplified for MVP)
                    team_id = team.get("id")
                    if not team_id:
                        continue

                    # Create sample prospect data (in real implementation, this would come from API)
                    prospect_data = self._create_sample_prospect_data(team)

                    await self._process_prospect_record(prospect_data, session)
                    self.ingestion_stats["prospects_processed"] += 1

                    # Add small delay to respect rate limits
                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"Error processing team {team.get('id', 'unknown')}: {str(e)}")
                    self.ingestion_stats["errors"].append({
                        "type": "prospect_processing_error",
                        "team_id": team.get("id"),
                        "message": str(e),
                        "timestamp": datetime.now().isoformat()
                    })

        except MLBStatsAPIError as e:
            logger.error(f"MLB API error during prospects ingestion: {str(e)}")
            raise DataIngestionError(f"Failed to fetch prospects data: {str(e)}")

    async def _ingest_current_season_stats(self, client: MLBAPIClient, session: AsyncSession) -> None:
        """
        Ingest current season statistics for existing prospects.

        Args:
            client: MLB API client
            session: Database session
        """
        logger.info("Ingesting current season statistics")
        current_year = datetime.now().year

        try:
            # Get existing prospects from database
            result = await session.execute(
                select(Prospect).where(Prospect.mlb_id.isnot(None))
            )
            prospects = result.scalars().all()

            for prospect in prospects[:20]:  # Limit to first 20 for demo
                try:
                    if not prospect.mlb_id:
                        continue

                    # Create sample stats data (in real implementation, fetch from API)
                    stats_data = self._create_sample_stats_data(prospect, current_year)

                    await self._process_stats_record(stats_data, prospect.id, session)

                    # Add delay to respect rate limits
                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"Error processing stats for prospect {prospect.id}: {str(e)}")
                    self.ingestion_stats["errors"].append({
                        "type": "stats_processing_error",
                        "prospect_id": prospect.id,
                        "message": str(e),
                        "timestamp": datetime.now().isoformat()
                    })

        except Exception as e:
            logger.error(f"Error during stats ingestion: {str(e)}")
            raise DataIngestionError(f"Failed to ingest stats data: {str(e)}")

    async def _process_prospect_record(self, prospect_data: Dict[str, Any], session: AsyncSession) -> None:
        """
        Process and save prospect record to database.

        Args:
            prospect_data: Prospect data from API
            session: Database session
        """
        mlb_id = prospect_data.get("mlb_id")
        if not mlb_id:
            return

        # Check if prospect already exists
        result = await session.execute(
            select(Prospect).where(Prospect.mlb_id == mlb_id)
        )
        existing_prospect = result.scalar_one_or_none()

        if existing_prospect:
            # Update existing prospect
            for key, value in prospect_data.items():
                if hasattr(existing_prospect, key) and value is not None:
                    setattr(existing_prospect, key, value)
            existing_prospect.updated_at = datetime.utcnow()
            self.ingestion_stats["prospects_updated"] += 1
            logger.debug(f"Updated existing prospect: {mlb_id}")
        else:
            # Create new prospect
            new_prospect = Prospect(**prospect_data)
            session.add(new_prospect)
            self.ingestion_stats["prospects_added"] += 1
            logger.debug(f"Added new prospect: {mlb_id}")

    async def _process_stats_record(self, stats_data: Dict[str, Any], prospect_id: int, session: AsyncSession) -> None:
        """
        Process and save stats record to database.

        Args:
            stats_data: Statistics data
            prospect_id: Prospect ID
            session: Database session
        """
        # Check if stats record already exists for this date
        result = await session.execute(
            select(ProspectStats).where(
                and_(
                    ProspectStats.prospect_id == prospect_id,
                    ProspectStats.date_recorded == stats_data["date"]
                )
            )
        )
        existing_stats = result.scalar_one_or_none()

        if existing_stats:
            # Update existing stats
            for key, value in stats_data.items():
                if hasattr(existing_stats, key) and value is not None:
                    setattr(existing_stats, key, value)
            logger.debug(f"Updated stats for prospect {prospect_id}")
        else:
            # Create new stats record
            stats_data["prospect_id"] = prospect_id
            # Map 'date' field to 'date_recorded' for database model
            if "date" in stats_data:
                stats_data["date_recorded"] = stats_data.pop("date")
            new_stats = ProspectStats(**stats_data)
            session.add(new_stats)
            self.ingestion_stats["stats_records_added"] += 1
            logger.debug(f"Added new stats for prospect {prospect_id}")

    def _create_sample_prospect_data(self, team_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create sample prospect data for demonstration."""
        team_id = team_data.get("id", 0)
        return {
            "mlb_id": f"P{team_id:06d}",
            "name": f"Sample Player {team_id}",
            "position": "OF",
            "organization": team_data.get("name", "Unknown Team"),
            "level": "AA",
            "age": 22,
            "eta_year": 2026,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

    def _create_sample_stats_data(self, prospect: Prospect, season: int) -> Dict[str, Any]:
        """Create sample stats data for demonstration."""
        return {
            "date": datetime.now().date(),
            "season": season,
            "games_played": 100,
            "at_bats": 350,
            "hits": 95,
            "home_runs": 12,
            "rbi": 55,
            "stolen_bases": 15,
            "walks": 45,
            "strikeouts": 85,
            "batting_avg": 0.271,
            "on_base_pct": 0.355,
            "slugging_pct": 0.420,
            "woba": 0.340,
            "wrc_plus": 115
        }

    def _reset_stats(self) -> None:
        """Reset ingestion statistics."""
        self.ingestion_stats = {
            "prospects_processed": 0,
            "prospects_added": 0,
            "prospects_updated": 0,
            "stats_records_added": 0,
            "errors": []
        }

    async def get_ingestion_status(self) -> Dict[str, Any]:
        """Get current ingestion status and statistics."""
        return {
            **self.ingestion_stats,
            "mlb_api_stats": self.mlb_client.get_request_stats(),
            "last_run": "Not implemented yet"  # Would track in database
        }

    async def refresh_prospect_data(self, prospect_id: int) -> bool:
        """
        Refresh data for a specific prospect.

        Args:
            prospect_id: The prospect ID to refresh

        Returns:
            bool: True if refresh was successful, False otherwise
        """
        try:
            # Use provided db session if available, otherwise get one
            if self.db:
                session = self.db
                should_close = False
            else:
                async for session in get_async_session():
                    should_close = True
                    break

            # Get the prospect from database
            result = await session.execute(
                select(Prospect).where(Prospect.id == prospect_id)
            )
            prospect = result.scalar_one_or_none()

            if not prospect:
                logger.warning(f"Prospect {prospect_id} not found")
                return False

            # Use the existing process_prospect_data method
            prospect_data = {
                "mlb_id": prospect.mlb_id,
                "name": prospect.name,
                "position": prospect.position,
                "organization": prospect.organization,
                "level": prospect.level,
                "age": prospect.age,
                "eta_year": prospect.eta_year
            }

            async with self.mlb_client as client:
                await self._process_prospect_data(prospect_data, session)

                # Get fresh stats for this prospect
                if prospect.mlb_id:
                    stats_data = await client.get_player_stats(int(prospect.mlb_id))
                    if stats_data and "stats" in stats_data:
                        await self._process_prospect_stats(prospect.id, stats_data["stats"], session)

            await session.commit()
            logger.info(f"Successfully refreshed data for prospect {prospect_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to refresh prospect {prospect_id}: {str(e)}")
            return False


# Singleton instance for backward compatibility
data_ingestion_service = DataIngestionService()