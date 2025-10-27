# Pitch Data Collection Analysis Report

## Executive Summary

We've identified a critical issue with missing pitch data for many prospects, including Leo De Vries. This explains why composite rankings show incomplete pitch counts.

## Key Findings

### 1. Leo De Vries Issue Confirmed
- **Total games played in 2025**: 118 games
- **Games with pitch data**: Only 10 games
- **Missing pitch data**: 108 games (91.5% missing!)
- **Pitches collected**: 165 (only from Sept 4-14, 2025)
- **Expected pitches**: ~2,036 (based on 536 PAs × 3.8 pitches/PA)
- **Coverage**: Only 8.1% of expected data

### 2. Issue Breakdown

Leo De Vries played 118 games across two levels in 2025:
- **A+ Level**: Multiple games from April through August
- **AA Level**: Promoted in late August

However, pitch data was only collected for his final 10 games (Sept 4-14) at AA level.

### 3. Root Cause

The pitch data collection appears to have gaps for many prospects. Specifically:
- Game logs are being collected properly (118 games for Leo)
- Pitch-by-pitch data is NOT being collected for most games
- Only recent games (last few weeks of season) have pitch data

## Impact on Composite Rankings

The composite rankings depend on pitch-level metrics like:
- Exit velocity (90th percentile)
- Hard hit rate
- Contact rate
- Whiff rate
- Chase rate

With only 8% of Leo's pitch data collected, the rankings show:
- **Current**: 165 pitches (incorrect/incomplete)
- **Should be**: ~2,000+ pitches (full season)

## Solution Already Implemented

We've already fixed the pitch data aggregator to:
1. ✅ Aggregate across all levels (AAA + AA + A+, etc.)
2. ✅ Use full season data instead of 60-day window
3. ✅ Properly handle multi-level players

However, this only helps if the underlying pitch data exists!

## Next Steps Required

### Immediate Action
1. **Run pitch data collection for Leo De Vries**
   - Need to collect pitch data for his 108 missing games
   - Priority: April-August 2025 games

2. **Identify all affected prospects**
   - Run comprehensive audit of all prospects
   - Find everyone with game logs but missing pitch data

3. **Bulk collection process**
   - Create prioritized list (top prospects first)
   - Run collection in batches
   - Monitor progress

### Verification
After collection completes:
1. Re-run composite rankings
2. Verify pitch counts match expectations
3. Confirm all metrics calculate properly

## Technical Details

```sql
-- Example: Leo De Vries missing games
SELECT game_pk, game_date, level, plate_appearances
FROM milb_game_logs
WHERE mlb_player_id = 815888
  AND season = 2025
  AND game_pk NOT IN (
    SELECT DISTINCT game_pk
    FROM milb_batter_pitches
    WHERE mlb_batter_id = 815888
  )
ORDER BY game_date;
-- Returns: 108 games without pitch data
```

## Conclusion

The issue is **confirmed**: Leo De Vries (and likely many other prospects) are missing pitch-by-pitch data for most of their 2025 games. The composite rankings are showing low pitch counts because the data simply doesn't exist in the database yet.

The fix to the aggregator code is working correctly - it just needs the underlying pitch data to be collected first.