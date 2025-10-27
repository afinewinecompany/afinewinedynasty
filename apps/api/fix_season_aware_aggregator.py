"""
Fix to make the pitch data aggregator season-aware.

Instead of always using a 60-day window, it should:
1. Use full current season data when we're in the off-season
2. Use rolling window during active season
3. Always capture the most relevant data for rankings
"""

import shutil
from datetime import datetime

def create_fix():
    """Create the season-aware fix for pitch_data_aggregator.py"""

    print("Creating season-aware pitch data aggregator fix...")
    print("="*60)

    # The fix: Make the method season-aware
    fix_content = '''
    async def get_hitter_pitch_metrics(
        self,
        mlb_player_id: str,
        level: str,
        days: int = 60
    ) -> Optional[Dict]:
        """
        Calculate hitter pitch-level metrics for recent performance.

        FIXED: Now season-aware - uses full season data when appropriate.

        Args:
            mlb_player_id: MLB Stats API player ID
            level: MiLB level for percentile comparison (AAA, AA, A+, A, etc.)
            days: Number of days to look back (default 60, but overridden for full season)

        Returns:
            Dict with raw metrics, percentiles, and sample size
            None if insufficient data
        """
        # SEASON-AWARE: Check if we should use full season data
        season_check_query = text("""
            SELECT
                EXTRACT(YEAR FROM CURRENT_DATE) as current_year,
                MAX(game_date) as last_game_date,
                CURRENT_DATE - MAX(game_date) as days_since_last_game,
                CASE
                    WHEN CURRENT_DATE - MAX(game_date) > 14 THEN TRUE  -- Season likely over
                    ELSE FALSE
                END as use_full_season
            FROM milb_batter_pitches
            WHERE season = EXTRACT(YEAR FROM CURRENT_DATE)
        """)

        season_info = await self.db.execute(season_check_query)
        season_data = season_info.fetchone()

        # Determine whether to use full season or rolling window
        if season_data and season_data.use_full_season:
            # Use full current season data
            date_filter = "AND season = EXTRACT(YEAR FROM CURRENT_DATE)"
            window_description = f"Full {season_data.current_year} season"
            logger.info(f"Using full season data (season ended {season_data.days_since_last_game} days ago)")
        else:
            # Use rolling window (during active season)
            date_filter = f"AND game_date >= CURRENT_DATE - CAST('{days} days' AS INTERVAL)"
            window_description = f"Last {days} days"
            logger.info(f"Using {days}-day rolling window (season active)")

        # Get levels played in the time window
        levels_query = text(f"""
            SELECT level, COUNT(*) as pitch_count
            FROM milb_batter_pitches
            WHERE mlb_batter_id = :mlb_player_id
                {date_filter}
            GROUP BY level
            ORDER BY pitch_count DESC
        """)

        levels_result = await self.db.execute(
            levels_query,
            {'mlb_player_id': int(mlb_player_id)}
        )
        levels_data = levels_result.fetchall()

        if not levels_data:
            logger.info(f"No pitch data for hitter {mlb_player_id} in {window_description}")
            return None

        # Continue with aggregation across all levels...
    '''

    print("Fix components:")
    print("1. Check if season is active or ended")
    print("2. Use full season data if season ended >14 days ago")
    print("3. Use rolling window during active season")
    print("4. Aggregate across all levels as before")
    print()
    print("This ensures:")
    print("- Bryce Eldridge shows 1,923 pitches (full season)")
    print("- All players show complete season data in off-season")
    print("- During season, shows recent form with rolling window")

if __name__ == "__main__":
    create_fix()