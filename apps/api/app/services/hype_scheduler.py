"""
HYPE Data Collection Scheduler
Background tasks for periodic data collection and score calculation
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.hype import PlayerHype
from app.models.prospect import Prospect
from app.services.social_collector import SocialMediaCollector
from app.services.hype_calculator import HypeCalculator

logger = logging.getLogger(__name__)


class HypeScheduler:
    """Manages scheduled HYPE data collection tasks"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False

    def start(self):
        """Start the scheduler"""
        if not self.is_running:
            # Schedule tasks
            self._schedule_tasks()

            # Start scheduler
            self.scheduler.start()
            self.is_running = True
            logger.info("HYPE scheduler started")

    def stop(self):
        """Stop the scheduler"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("HYPE scheduler stopped")

    def _schedule_tasks(self):
        """Configure scheduled tasks"""

        # Collect social data every 30 minutes for top players
        self.scheduler.add_job(
            self.collect_top_players_data,
            IntervalTrigger(minutes=30),
            id='collect_top_players',
            name='Collect HYPE data for top players',
            max_instances=1
        )

        # Collect data hourly for all tracked players
        self.scheduler.add_job(
            self.collect_all_players_data,
            IntervalTrigger(hours=1),
            id='collect_all_players',
            name='Collect HYPE data for all players',
            max_instances=1
        )

        # Calculate HYPE scores every 15 minutes
        self.scheduler.add_job(
            self.calculate_hype_scores,
            IntervalTrigger(minutes=15),
            id='calculate_scores',
            name='Calculate HYPE scores',
            max_instances=1
        )

        # Clean old data daily
        self.scheduler.add_job(
            self.cleanup_old_data,
            IntervalTrigger(days=1),
            id='cleanup_data',
            name='Clean up old HYPE data',
            max_instances=1
        )

    async def collect_top_players_data(self):
        """Collect data for top prospects and trending players"""
        logger.info("Starting top players HYPE data collection")

        db = SessionLocal()
        try:
            # Get top prospects from FanGraphs grades
            # Order by id (newest first) to get recently added prospects
            top_prospects = db.query(Prospect).order_by(
                Prospect.id.desc()
            ).limit(50).all()

            # Get trending players (high HYPE score or trend)
            trending_players = db.query(PlayerHype).filter(
                (PlayerHype.hype_score > 70) | (PlayerHype.hype_trend > 10)
            ).all()

            # Combine player lists
            players_to_update = []

            for prospect in top_prospects:
                players_to_update.append({
                    'id': f"prospect_{prospect.mlb_id}",  # Use mlb_id as unique identifier
                    'name': prospect.name  # Use the single name field
                })

            for player in trending_players:
                if player.player_id not in [p['id'] for p in players_to_update]:
                    players_to_update.append({
                        'id': player.player_id,
                        'name': player.player_name
                    })

            # Collect data for each player
            collector = SocialMediaCollector(db)
            for player in players_to_update[:20]:  # Limit to top 20 for rate limiting
                try:
                    await collector.collect_all_platforms(
                        player['name'],
                        player['id']
                    )
                    logger.info(f"Collected HYPE data for {player['name']}")
                except Exception as e:
                    logger.error(f"Error collecting data for {player['name']}: {e}")

        except Exception as e:
            logger.error(f"Error in top players collection: {e}")
        finally:
            db.close()

    async def collect_all_players_data(self):
        """Collect data for all tracked players"""
        logger.info("Starting all players HYPE data collection")

        db = SessionLocal()
        try:
            # Get all players with recent activity
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            active_players = db.query(PlayerHype).filter(
                PlayerHype.last_calculated > cutoff_date
            ).all()

            collector = SocialMediaCollector(db)

            # Process in batches to respect rate limits
            batch_size = 10
            for i in range(0, len(active_players), batch_size):
                batch = active_players[i:i+batch_size]

                tasks = []
                for player in batch:
                    tasks.append(
                        collector.collect_all_platforms(
                            player.player_name,
                            player.player_id
                        )
                    )

                # Run batch concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for j, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Error collecting data for {batch[j].player_name}: {result}")

                # Delay between batches to respect rate limits
                await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Error in all players collection: {e}")
        finally:
            db.close()

    async def calculate_hype_scores(self):
        """Calculate HYPE scores for players with new data"""
        logger.info("Starting HYPE score calculation")

        db = SessionLocal()
        try:
            # Get players that need score updates
            cutoff_time = datetime.utcnow() - timedelta(minutes=15)

            # Players with recent social mentions that haven't been calculated
            players_to_update = db.query(PlayerHype).filter(
                PlayerHype.last_calculated < cutoff_time
            ).limit(50).all()

            calculator = HypeCalculator(db)

            for player in players_to_update:
                try:
                    result = calculator.calculate_hype_score(player.player_id)
                    logger.info(
                        f"Updated HYPE score for {player.player_name}: "
                        f"{result['hype_score']:.1f} (trend: {result['trend']:+.1f}%)"
                    )
                except Exception as e:
                    logger.error(f"Error calculating score for {player.player_name}: {e}")

        except Exception as e:
            logger.error(f"Error in HYPE score calculation: {e}")
        finally:
            db.close()

    async def cleanup_old_data(self):
        """Clean up old social mentions and historical data"""
        logger.info("Starting HYPE data cleanup")

        db = SessionLocal()
        try:
            # Delete social mentions older than 30 days
            cutoff_date = datetime.utcnow() - timedelta(days=30)

            deleted_count = db.query(SocialMention).filter(
                SocialMention.posted_at < cutoff_date
            ).delete()

            db.commit()
            logger.info(f"Deleted {deleted_count} old social mentions")

            # Archive old historical data (older than 1 year)
            # This would typically move to a data warehouse
            archive_date = datetime.utcnow() - timedelta(days=365)

            # For now, just log what would be archived
            archive_count = db.query(HypeHistory).filter(
                HypeHistory.period_end < archive_date
            ).count()

            if archive_count > 0:
                logger.info(f"Would archive {archive_count} historical records")

        except Exception as e:
            logger.error(f"Error in cleanup: {e}")
            db.rollback()
        finally:
            db.close()


# Global scheduler instance
hype_scheduler = HypeScheduler()


def start_hype_scheduler():
    """Start the HYPE scheduler (called on app startup)"""
    hype_scheduler.start()


def stop_hype_scheduler():
    """Stop the HYPE scheduler (called on app shutdown)"""
    hype_scheduler.stop()