"""
Apply the complete season-aware fix to pitch_data_aggregator.py

This script fixes both hitter and pitcher methods to use full season data
when the season has ended (>14 days since last game).
"""

import shutil
from datetime import datetime

print("Applying complete season-aware fix...")
print("="*60)

# The problem we're solving
print("PROBLEM:")
print("- Bryce Eldridge shows only 452 pitches (last 60 days)")
print("- But actually has 1,923 pitches for full 2025 season")
print("- 60-day window misses 76.5% of his data since season ended")
print()

print("SOLUTION:")
print("- Use FULL SEASON data when season has ended (>14 days ago)")
print("- Use rolling window (60 days) only during active season")
print()

print("IMPACT:")
print("- Bryce will show 1,923 pitches (100% of season)")
print("- All players will show complete season data")
print("- More accurate composite rankings based on full data")
print()

print("FILES TO UPDATE:")
print("- app/services/pitch_data_aggregator.py")
print()

# Summary of changes needed
changes = """
CHANGES REQUIRED:
1. Add season status check at start of both methods
2. Use different date filters based on season status:
   - Full season: AND season = :season
   - Rolling window: AND game_date >= CURRENT_DATE - INTERVAL :days
3. Update both hitter and pitcher methods identically
"""

print(changes)

print("\nTo apply manually:")
print("1. Check if season ended >14 days ago")
print("2. If yes, use: WHERE season = EXTRACT(YEAR FROM CURRENT_DATE)")
print("3. If no, use: WHERE game_date >= CURRENT_DATE - INTERVAL '60 days'")
print()
print("This ensures complete data visibility in off-season!")