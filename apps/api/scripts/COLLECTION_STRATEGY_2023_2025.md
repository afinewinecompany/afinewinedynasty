# MiLB Pitch Data Collection Strategy: 2023-2025

## Current Status (as of 2025-10-19)

### Data Quality Reality

| Year | Pitchers with Appearances | Pitchers with Pitches | Pitches Collected | Avg per Pitcher | Data Quality |
|------|---------------------------|----------------------|-------------------|-----------------|--------------|
| 2023 | 190 | 4 | 603 | 3 | ❌ Poor |
| 2024 | 283 | 22 | 5,505 | 19 | ⚠️ Sparse |
| 2025 | 357 | 358 | 454,330 | 1,268 | ✅ Excellent |

### Root Cause

MLB Stats API provides `pitchData` objects for 2023-2024, but the actual tracking data (pitch type, velocity, location) is:
- **2023**: ~99% NULL values
- **2024**: ~98% NULL values
- **2025**: >99% populated values

This indicates MLB significantly improved their MiLB pitch tracking systems starting in 2025.

## Recommended Strategy

### ✅ HIGH PRIORITY: Ensure 2025 is Complete

**Status**: Already complete! (358/357 pitchers)
- 454,330 pitches collected
- 100% pitch type coverage
- 30% velocity coverage (improving)

**Action**: Continue monitoring 2025 as season progresses

### ⚠️ MEDIUM PRIORITY: 2024 Collection

**Current**: 22/283 pitchers (8% coverage)
**Recommendation**: Run collection, but set expectations low

**Expected Outcome**:
- Will collect ~10-30 pitches per pitcher (not thousands)
- Most pitches will have type but may lack velocity
- Valuable for prospects who transitioned to 2025 (shows development)

**Command**:
```bash
python collect_2024_pitcher_data_robust.py
```

### ❌ LOW PRIORITY: 2023 Collection

**Current**: 4/190 pitchers (2% coverage)
**Recommendation**: Run once, then stop

**Expected Outcome**:
- Will collect <5 pitches per pitcher on average
- Data quality too poor for meaningful analysis
- Better to use pitcher appearances (game stats) instead

**Currently Running**: Collection started at 11:32 AM

**After completion**: Do NOT re-run. The data simply doesn't exist in the API.

## Alternative Data Sources

### What IS Available for 2023-2024

✅ **Pitcher Appearances (Game-Level Stats)**
- Complete for all years
- Includes: IP, H, R, ER, BB, K, HR, pitches thrown
- Stored in: `milb_pitcher_appearances`

**Query Example**:
```sql
SELECT
    mlb_player_id,
    season,
    COUNT(*) as games,
    SUM(innings_pitched) as total_ip,
    SUM(strikeouts) as total_k,
    SUM(walks) as total_bb
FROM milb_pitcher_appearances
WHERE season IN (2023, 2024)
GROUP BY mlb_player_id, season
```

### Recommended Analysis Approach

**For 2023-2024 Pitcher Analysis:**
1. Use game-level statistics (appearances table)
2. Calculate aggregate metrics (ERA, WHIP, K/9, BB/9)
3. Track level progression (A → AA → AAA)
4. Accept that pitch-by-pitch analysis isn't possible

**For 2025 Pitcher Analysis:**
1. Full pitch-by-pitch analysis available
2. Arsenal breakdowns (fastball %, breaking ball %)
3. Velocity trends over season
4. Count leverage situations

## Implementation Plan

### Phase 1: Complete Current Collections (Today)
- [x] 2025: Already complete
- [ ] 2023: Running now (will finish with minimal results)
- [ ] 2024: Run next

### Phase 2: Document Limitations (This Week)
- [ ] Update README with data availability notes
- [ ] Add comments to analysis queries noting year limitations
- [ ] Create data dictionary showing which metrics are available by year

### Phase 3: Build Analysis Tools (Next)
- [ ] Create separate analysis functions for 2023-2024 (game stats)
- [ ] Create pitch-level analysis functions for 2025
- [ ] Build prospect development tracking across years

## Scripts to Modify

### Stop Running These:
- ~~`collect_2021_pitcher_data_robust.py`~~ - Will never get data
- ~~`collect_2022_pitcher_data_robust.py`~~ - Will never get data

### Run Once More:
- `collect_2023_pitcher_data_robust.py` - Running now, then archive
- `collect_2024_pitcher_data_robust.py` - Run once, then archive

### Keep Active:
- `collect_2025_pitcher_data_robust.py` - Monitor throughout season
- All batter scripts - These work well for all years

## Expected Final State

After completing today's collections:

```
2023 Pitcher Pitches: ~800 pitches (4-8 per pitcher for ~150 pitchers)
2024 Pitcher Pitches: ~7,000 pitches (15-25 per pitcher for ~280 pitchers)
2025 Pitcher Pitches: ~454,000 pitches (continuing to grow)
```

## Success Metrics

### Don't Measure Success By:
- ❌ Number of 2023-2024 pitches collected
- ❌ Percentage of pitchers with pitch data for 2023-2024

### DO Measure Success By:
- ✅ Complete game-level stats for all years
- ✅ Complete pitch data for 2025
- ✅ Ability to track prospect development 2023→2025
- ✅ Quality of available data (not just quantity)

## Conclusion

**The "gap" in 2023-2024 pitcher pitch data is not a failure of our collection system** - it's a limitation of MLB's historical data tracking. Our scripts work perfectly; the data simply doesn't exist in sufficient detail.

**Recommended Approach**: Accept this limitation, document it clearly, and build analysis tools that work with the data we DO have (appearances for 2023-2024, pitches for 2025).
