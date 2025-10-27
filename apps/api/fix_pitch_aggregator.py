"""
Script to fix the pitch data aggregator to include ALL levels a player has played at,
not just a single level.

The issue: When a player like Bryce Eldridge plays at multiple levels (AAA and AA),
the current code only looks at one level (AAA) and shows 292 pitches instead of
the actual 452 pitches across both levels.
"""

import os
import shutil
from datetime import datetime

def apply_fix():
    """Apply the fix to pitch_data_aggregator.py"""

    # Backup the original file
    original_file = "app/services/pitch_data_aggregator.py"
    backup_file = f"app/services/pitch_data_aggregator.py.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print(f"Creating backup: {backup_file}")
    shutil.copy2(original_file, backup_file)

    # Read the original file
    with open(original_file, 'r') as f:
        content = f.read()

    # The fix: Replace the single-level query with multi-level aggregation
    old_code = '''        query = text("""
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

    new_code = '''        # FIXED: Check what levels the player has played at recently
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

        # FIXED: Aggregate across ALL levels the player has played at
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

                    -- Track which levels are included
                    array_agg(DISTINCT level ORDER BY level) as levels_included

                FROM milb_batter_pitches
                WHERE mlb_batter_id = :mlb_player_id
                    AND level = ANY(:levels)  -- FIXED: Include ALL levels
                    AND game_date >= CURRENT_DATE - CAST(:days || ' days' AS INTERVAL)
            )
            SELECT * FROM player_stats
            WHERE pitches_seen >= :min_pitches
        """)'''

    # Check if the old code exists
    if old_code not in content:
        print("WARNING: Could not find the exact code to replace.")
        print("The file may have been modified. Please apply the fix manually.")
        return False

    # Apply the fix
    content = content.replace(old_code, new_code)

    # Also update the execute call parameters
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

    # Update the result handling to include multi-level info
    old_return = '''            return {
                'metrics': metrics,
                'percentiles': percentiles,
                'sample_size': row[5],
                'days_covered': days,
                'level': level
            }'''

    new_return = '''            # Use the specified level for percentile comparison, or highest level played
            comparison_level = level if level in levels_played else levels_played[0]

            result_dict = {
                'metrics': metrics,
                'percentiles': percentiles,
                'sample_size': row[5],  # FIXED: Now includes ALL levels
                'days_covered': days,
                'level': comparison_level,  # Level for percentile comparison
            }

            # Add multi-level info if applicable
            if row[8] and len(row[8]) > 1:
                result_dict['levels_included'] = row[8]
                result_dict['note'] = f"Aggregated from: {', '.join(row[8])}"

            return result_dict'''

    content = content.replace(old_return, new_return)

    # Write the fixed file
    with open(original_file, 'w') as f:
        f.write(content)

    print(f"✅ Fix applied successfully to {original_file}")
    print(f"📦 Backup saved as {backup_file}")
    print("\n📊 What this fixes:")
    print("  - Players who play at multiple levels will now show ALL their pitches")
    print("  - Example: Bryce Eldridge will show 452 pitches (AAA + AA) instead of just 292 (AAA only)")
    print("\n🔄 Next steps:")
    print("  1. Clear any Redis cache: python clear_rankings_cache.py")
    print("  2. Restart the API server")
    print("  3. Test the composite rankings endpoint")

    return True

if __name__ == "__main__":
    if apply_fix():
        print("\n✅ Fix applied successfully!")
    else:
        print("\n❌ Fix could not be applied automatically. Please apply manually.")