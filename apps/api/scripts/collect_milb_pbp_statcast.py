"""
Collect play-by-play Statcast data for MiLB players.

This script collects detailed batted ball data including:
- Exit velocity (launch speed)
- Launch angle
- Distance
- Trajectory (GB, LD, FB, PU)
- Hardness (soft, medium, hard)
- Spray chart location
"""

import asyncio
import aiohttp
from datetime import datetime
from typing import Optional, Dict, List, Any
import logging
from sqlalchemy import text
from app.db.database import engine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MiLBStatcastCollector:
    """Collects play-by-play Statcast data for MiLB players."""

    BASE_URL = "https://statsapi.mlb.com/api"
    SPORT_IDS = {
        11: "AAA",
        12: "AA",
        13: "A+",
        14: "A",
        15: "Rookie",
        16: "Rookie+"
    }

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.games_processed = 0
        self.plate_appearances_collected = 0
        self.batted_balls_collected = 0

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch_json(self, url: str) -> Optional[Dict]:
        """Fetch JSON data from URL."""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    logger.debug(f"Not found: {url}")
                else:
                    logger.warning(f"Error {response.status}: {url}")
        except Exception as e:
            logger.error(f"Exception fetching {url}: {e}")
        return None

    async def get_player_games(self, player_id: int, season: int, sport_id: int) -> List[int]:
        """Get list of game IDs for a player in a season."""
        url = f"{self.BASE_URL}/v1/people/{player_id}/stats?stats=gameLog&season={season}&group=hitting&sportId={sport_id}"

        data = await self.fetch_json(url)
        if not data:
            return []

        game_pks = []
        stats = data.get('stats', [])
        if stats:
            splits = stats[0].get('splits', [])
            for split in splits:
                game = split.get('game', {})
                game_pk = game.get('gamePk')
                if game_pk:
                    game_pks.append(game_pk)

        return game_pks

    async def get_game_play_by_play(self, game_pk: int) -> Optional[Dict]:
        """Get full play-by-play data for a game."""
        url = f"{self.BASE_URL}/v1.1/game/{game_pk}/feed/live"
        return await self.fetch_json(url)

    def extract_batted_ball_data(self, play_event: Dict) -> Optional[Dict]:
        """Extract Statcast batted ball data from a play event."""
        hit_data = play_event.get('hitData', {})

        if not hit_data:
            return None

        # Convert location to integer if it's a string
        location = hit_data.get('location')
        if location is not None:
            if isinstance(location, str):
                try:
                    location = int(location)
                except (ValueError, TypeError):
                    location = None

        return {
            'launch_speed': hit_data.get('launchSpeed'),
            'launch_angle': hit_data.get('launchAngle'),
            'total_distance': hit_data.get('totalDistance'),
            'trajectory': hit_data.get('trajectory'),  # ground_ball, line_drive, fly_ball, popup
            'hardness': hit_data.get('hardness'),  # soft, medium, hard
            'location': location,  # spray chart zone (converted to int)
            'coord_x': hit_data.get('coordinates', {}).get('coordX'),
            'coord_y': hit_data.get('coordinates', {}).get('coordY')
        }

    async def process_game_for_player(
        self,
        player_id: int,
        game_pk: int,
        season: int,
        level: str
    ) -> int:
        """Process a single game and extract player's plate appearances."""
        game_data = await self.get_game_play_by_play(game_pk)

        if not game_data:
            return 0

        live_data = game_data.get('liveData', {})
        plays_data = live_data.get('plays', {})
        all_plays = plays_data.get('allPlays', [])

        game_date_str = game_data.get('gameData', {}).get('datetime', {}).get('officialDate')
        game_date = datetime.strptime(game_date_str, '%Y-%m-%d').date() if game_date_str else None

        pas_collected = 0

        for play in all_plays:
            # Check if this plate appearance involves our player
            matchup = play.get('matchup', {})
            batter = matchup.get('batter', {})
            batter_id = batter.get('id')

            if batter_id != player_id:
                continue

            # Extract play result
            result = play.get('result', {})
            event_type = result.get('event')
            event_type_desc = result.get('eventType')
            description = result.get('description')

            # Extract play events to find batted ball data
            play_events = play.get('playEvents', [])

            batted_ball_data = None
            for event in play_events:
                bb_data = self.extract_batted_ball_data(event)
                if bb_data:
                    batted_ball_data = bb_data
                    self.batted_balls_collected += 1
                    break

            # Save plate appearance
            await self.save_plate_appearance(
                player_id=player_id,
                game_pk=game_pk,
                game_date=game_date,
                season=season,
                level=level,
                at_bat_index=play.get('atBatIndex'),
                inning=play.get('about', {}).get('inning'),
                half_inning=play.get('about', {}).get('halfInning'),
                event_type=event_type,
                event_type_desc=event_type_desc,
                description=description,
                batted_ball_data=batted_ball_data
            )

            pas_collected += 1

        return pas_collected

    async def save_plate_appearance(
        self,
        player_id: int,
        game_pk: int,
        game_date: datetime.date,
        season: int,
        level: str,
        at_bat_index: int,
        inning: int,
        half_inning: str,
        event_type: str,
        event_type_desc: str,
        description: str,
        batted_ball_data: Optional[Dict]
    ):
        """Save plate appearance to database."""
        async with engine.begin() as conn:
            # Check if already exists
            result = await conn.execute(
                text("""
                    SELECT id FROM milb_plate_appearances
                    WHERE mlb_player_id = :player_id
                    AND game_pk = :game_pk
                    AND at_bat_index = :at_bat_index
                """),
                {
                    'player_id': player_id,
                    'game_pk': game_pk,
                    'at_bat_index': at_bat_index
                }
            )

            if result.fetchone():
                return  # Already exists

            # Insert
            await conn.execute(text("""
                INSERT INTO milb_plate_appearances
                (mlb_player_id, game_pk, game_date, season, level, at_bat_index,
                 inning, half_inning, event_type, event_type_desc, description,
                 launch_speed, launch_angle, total_distance, trajectory, hardness,
                 location, coord_x, coord_y, created_at)
                VALUES
                (:player_id, :game_pk, :game_date, :season, :level, :at_bat_index,
                 :inning, :half_inning, :event_type, :event_type_desc, :description,
                 :launch_speed, :launch_angle, :total_distance, :trajectory, :hardness,
                 :location, :coord_x, :coord_y, NOW())
            """), {
                'player_id': player_id,
                'game_pk': game_pk,
                'game_date': game_date,
                'season': season,
                'level': level,
                'at_bat_index': at_bat_index,
                'inning': inning,
                'half_inning': half_inning,
                'event_type': event_type,
                'event_type_desc': event_type_desc,
                'description': description,
                'launch_speed': batted_ball_data.get('launch_speed') if batted_ball_data else None,
                'launch_angle': batted_ball_data.get('launch_angle') if batted_ball_data else None,
                'total_distance': batted_ball_data.get('total_distance') if batted_ball_data else None,
                'trajectory': batted_ball_data.get('trajectory') if batted_ball_data else None,
                'hardness': batted_ball_data.get('hardness') if batted_ball_data else None,
                'location': batted_ball_data.get('location') if batted_ball_data else None,
                'coord_x': batted_ball_data.get('coord_x') if batted_ball_data else None,
                'coord_y': batted_ball_data.get('coord_y') if batted_ball_data else None
            })

    async def collect_player_pbp(
        self,
        player_id: int,
        seasons: List[int],
        sport_ids: List[int] = None
    ):
        """Collect play-by-play data for a player across seasons and levels."""
        if sport_ids is None:
            sport_ids = [11, 12, 13]  # AAA, AA, A+

        logger.info(f"Collecting PBP for player {player_id}")

        total_pas = 0

        for season in seasons:
            for sport_id in sport_ids:
                level = self.SPORT_IDS[sport_id]

                # Get games for this player/season/level
                game_pks = await self.get_player_games(player_id, season, sport_id)

                if not game_pks:
                    continue

                logger.info(f"  Player {player_id}: {len(game_pks)} games in {season} {level}")

                for game_pk in game_pks:
                    pas = await self.process_game_for_player(player_id, game_pk, season, level)
                    total_pas += pas
                    self.games_processed += 1

                    if self.games_processed % 10 == 0:
                        logger.info(f"    Progress: {self.games_processed} games, {total_pas} PAs, {self.batted_balls_collected} batted balls")

                    # Rate limiting
                    await asyncio.sleep(0.2)

        logger.info(f"Completed player {player_id}: {total_pas} PAs, {self.batted_balls_collected} batted balls")
        return total_pas

    async def collect_all_players_pbp(
        self,
        seasons: List[int],
        sport_ids: List[int] = None,
        limit: int = None
    ):
        """Collect PBP for all players in game logs."""
        logger.info("Getting list of players...")

        async with engine.begin() as conn:
            query = """
                SELECT DISTINCT mlb_player_id
                FROM milb_game_logs
                WHERE data_source = 'mlb_stats_api_gamelog'
                AND mlb_player_id IS NOT NULL
                ORDER BY mlb_player_id
            """
            if limit:
                query += f" LIMIT {limit}"

            result = await conn.execute(text(query))
            player_ids = [row[0] for row in result.fetchall()]

        logger.info(f"Collecting PBP for {len(player_ids)} players")

        for i, player_id in enumerate(player_ids, 1):
            logger.info(f"\nPlayer {i}/{len(player_ids)}: {player_id}")

            try:
                await self.collect_player_pbp(player_id, seasons, sport_ids)
            except Exception as e:
                logger.error(f"Error collecting player {player_id}: {e}")
                continue

            if i % 10 == 0:
                logger.info(f"\n=== Overall Progress: {i}/{len(player_ids)} players ===")
                logger.info(f"Total PAs: {self.plate_appearances_collected}")
                logger.info(f"Total Batted Balls: {self.batted_balls_collected}")


async def create_table():
    """Create milb_plate_appearances table if it doesn't exist."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS milb_plate_appearances (
                id SERIAL PRIMARY KEY,
                mlb_player_id INTEGER NOT NULL,
                game_pk BIGINT NOT NULL,
                game_date DATE,
                season INTEGER,
                level VARCHAR(20),
                at_bat_index INTEGER,
                inning INTEGER,
                half_inning VARCHAR(10),
                event_type VARCHAR(50),
                event_type_desc VARCHAR(50),
                description TEXT,
                launch_speed FLOAT,
                launch_angle FLOAT,
                total_distance FLOAT,
                trajectory VARCHAR(20),
                hardness VARCHAR(20),
                location INTEGER,
                coord_x FLOAT,
                coord_y FLOAT,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(mlb_player_id, game_pk, at_bat_index)
            )
        """))

        # Create indexes
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_milb_pa_player
            ON milb_plate_appearances(mlb_player_id)
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_milb_pa_launch_speed
            ON milb_plate_appearances(launch_speed)
            WHERE launch_speed IS NOT NULL
        """))

        logger.info("Table created/verified")


async def main():
    """Main execution."""
    import argparse

    parser = argparse.ArgumentParser(description='Collect MiLB play-by-play Statcast data')
    parser.add_argument('--seasons', nargs='+', type=int, default=[2024, 2023, 2022],
                       help='Seasons to collect')
    parser.add_argument('--levels', nargs='+', choices=['AAA', 'AA', 'A+', 'A', 'Rookie', 'Rookie+'],
                       default=['AAA', 'AA', 'A+'], help='Levels to collect')
    parser.add_argument('--limit', type=int, help='Limit number of players')

    args = parser.parse_args()

    # Map levels to sport IDs
    level_to_sport_id = {
        'AAA': 11, 'AA': 12, 'A+': 13, 'A': 14, 'Rookie': 15, 'Rookie+': 16
    }
    sport_ids = [level_to_sport_id[level] for level in args.levels]

    logger.info("="*80)
    logger.info("MiLB Play-by-Play Statcast Data Collection")
    logger.info("="*80)
    logger.info(f"Seasons: {args.seasons}")
    logger.info(f"Levels: {args.levels}")

    # Create table
    await create_table()

    # Collect data
    async with MiLBStatcastCollector() as collector:
        await collector.collect_all_players_pbp(args.seasons, sport_ids, args.limit)

    logger.info("\n" + "="*80)
    logger.info("Collection Complete!")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
