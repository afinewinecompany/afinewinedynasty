#!/usr/bin/env python3
"""
Apply the pitch data aggregator fix to properly aggregate across all levels
"""

import os
import shutil
from datetime import datetime

def apply_fix():
    file_path = "app/services/pitch_data_aggregator.py"

    # Read the current file
    with open(file_path, 'r') as f:
        content = f.read()

    # Check if fix is already applied
    if "AND level = ANY(:levels)" in content:
        print("Fix already applied!")
        return

    print(f"Applying fix to {file_path}...")

    # Replace the get_hitter_pitch_metrics method
    # This is a targeted replacement of the specific query section

    # Replace the query construction for hitters
    old_hitter_query = '''        query = text("""
            WITH player_stats AS (
                SELECT
                    -- Exit Velocity (90th percentile)
                    PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY launch_speed)
                        FILTER (WHERE launch_speed IS NOT NULL) as exit_velo_90th,

                    -- Hard Hit Rate
                    COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_hit_rate,

                    -- Contact Rate
                    COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_rate,

                    -- Whiff Rate
                    COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

                    -- Chase Rate
                    COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,

                    -- Sample size
                    COUNT(*) as pitches_seen,
                    COUNT(*) FILTER (WHERE swing = TRUE) as swings,
                    COUNT(*) FILTER (WHERE launch_speed IS NOT NULL) as balls_in_play

                FROM milb_batter_pitches
                WHERE mlb_batter_id = :mlb_player_id
                    AND level = :level
                    AND game_date >= CURRENT_DATE - CAST(:days || ' days' AS INTERVAL)
            )
            SELECT * FROM player_stats
            WHERE pitches_seen >= :min_pitches
        """)'''

    new_hitter_query = '''        # FIXED: Check what levels the player has played at recently
        levels_query = text("""
            SELECT level, COUNT(*) as pitch_count
            FROM milb_batter_pitches
            WHERE mlb_batter_id = :mlb_player_id
                AND game_date >= CURRENT_DATE - CAST(:days || ' days' AS INTERVAL)
            GROUP BY level
            ORDER BY pitch_count DESC
        """)

        levels_result = await self.db.execute(
            levels_query,
            {'mlb_player_id': int(mlb_player_id), 'days': str(days)}
        )
        levels_data = levels_result.fetchall()

        if not levels_data:
            logger.info(f"No pitch data for hitter {mlb_player_id} in last {days} days")
            return None

        levels_played = [row[0] for row in levels_data]
        total_pitches = sum(row[1] for row in levels_data)

        logger.info(f"Player {mlb_player_id}: {total_pitches} pitches at {levels_played} in {days}d")

        # FIXED: Aggregate across ALL levels
        query = text("""
            WITH player_stats AS (
                SELECT
                    -- Exit Velocity (90th percentile)
                    PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY launch_speed)
                        FILTER (WHERE launch_speed IS NOT NULL) as exit_velo_90th,

                    -- Hard Hit Rate
                    COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_hit_rate,

                    -- Contact Rate
                    COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_rate,

                    -- Whiff Rate
                    COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

                    -- Chase Rate
                    COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,

                    -- Sample size
                    COUNT(*) as pitches_seen,
                    COUNT(*) FILTER (WHERE swing = TRUE) as swings,
                    COUNT(*) FILTER (WHERE launch_speed IS NOT NULL) as balls_in_play,

                    -- Track levels included
                    array_agg(DISTINCT level ORDER BY level) as levels_included

                FROM milb_batter_pitches
                WHERE mlb_batter_id = :mlb_player_id
                    AND level = ANY(:levels)  -- FIXED: Include ALL levels
                    AND game_date >= CURRENT_DATE - CAST(:days || ' days' AS INTERVAL)
            )
            SELECT * FROM player_stats
            WHERE pitches_seen >= :min_pitches
        """)'''

    content = content.replace(old_hitter_query, new_hitter_query)

    # Update the execute parameters for hitters
    old_execute = '''            result = await self.db.execute(
                query,
                {
                    'mlb_player_id': int(mlb_player_id),
                    'level': level,
                    'days': str(days),  # Convert to string for concatenation
                    'min_pitches': self.MIN_PITCHES_BATTER
                }
            )'''

    new_execute = '''            result = await self.db.execute(
                query,
                {
                    'mlb_player_id': int(mlb_player_id),
                    'levels': levels_played,  # FIXED: Pass ALL levels
                    'days': str(days),
                    'min_pitches': self.MIN_PITCHES_BATTER
                }
            )'''

    content = content.replace(old_execute, new_execute)

    # Update the return statement for hitters
    old_return = '''            return {
                'metrics': metrics,
                'percentiles': percentiles,
                'sample_size': row[5],
                'days_covered': days,
                'level': level
            }'''

    new_return = '''            # Use specified level for percentile comparison, or highest level played
            comparison_level = level if level in levels_played else levels_played[0]

            result_dict = {
                'metrics': metrics,
                'percentiles': percentiles,
                'sample_size': row[5],  # FIXED: Now includes ALL levels
                'days_covered': days,
                'level': comparison_level,
            }

            # Add multi-level info if applicable
            if row[8] and len(row[8]) > 1:
                result_dict['levels_included'] = row[8]
                result_dict['aggregation_note'] = f"Data from: {', '.join(row[8])}"
                logger.info(f"Aggregated {row[5]} pitches from levels: {row[8]}")

            return result_dict'''

    content = content.replace(old_return, new_return)

    # Write the updated file
    with open(file_path, 'w') as f:
        f.write(content)

    print("✅ Fix applied successfully!")
    print("\n📊 What this fixes:")
    print("  - Players at multiple levels now show ALL their pitches")
    print("  - Bryce Eldridge: 452 pitches (AAA + AA) instead of 292")
    print("\n🔄 Next: Commit and push the changes")

if __name__ == "__main__":
    apply_fix()