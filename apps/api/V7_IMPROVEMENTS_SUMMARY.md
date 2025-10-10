# V7 Ranking Improvements Summary

## Changes Made

### 1. FG Score Formula Adjustment
**Changed FV weight from 20% to 50%** in the FanGraphs composite score calculation:

**Old Formula:**
```
FG Score =
  FV * 20% +
  Power * 15% +
  Hit * 12% +
  Performance * 12% +
  Speed * 10% +
  Age * 15% +     ← Young age bias
  Top100 * 8% +
  Field * 5% +
  Athleticism * 3%
```

**New Formula:**
```
FG Score =
  FV * 50% +      ← PRIMARY DRIVER (was 20%)
  Power * 12% +
  Hit * 10% +
  Performance * 8% +
  Speed * 8% +
  Age * 5% +      ← Reduced from 15%
  Top100 * 5% +
  Field * 2% +
  Athleticism * 0%  ← Removed (often missing/negative)
```

**Rationale:** FV is the industry consensus grade that scouts assign after evaluating ALL tools, performance, age, and projection. By weighting it at only 20%, individual tool grades could override the consensus. This caused FV:35 prospects to outscore FV:40 prospects.

### 2. V7 Weight Adjustment
**Changed from 70/20/10 to 50/40/10:**

- **FanGraphs:** 70% → 50% (reduced to give performance more weight)
- **V4 Performance:** 20% → 40% (doubled to reward current production)
- **V5 ML Projection:** 10% → 10% (unchanged)

**Rationale:** 70% FG weight was too high when many prospects lack 2025 data. The 50/40/10 split better balances expert scouting opinion with actual statistical performance.

## Results: User-Identified Problem Players

### Old Rankings (70% FG, 20% V4, 10% V5) with 20% FV weight:

| Player | FV | Old Rank | Issue |
|--------|----|---------:|-------|
| **Douglas Glod** | 35 | **#100** | Too high (poor 2025 stats: .667 OPS) |
| **Chase DeLauter** | 50 | #159 | Too low (top prospect, no 2025 data) |
| **Sal Stewart** | 45 | #248 | Too low (in MLB with 55 AB) |
| **Eric Bitonti** | 40 | **#288** | **WAY too low** (excellent 2025: .753 OPS, 19 HR, 17 SB) |

### New Rankings (50% FG, 40% V4, 10% V5) with 50% FV weight:

| Player | FV | New Rank | Change | Notes |
|--------|----|---------:|-------:|-------|
| **Eric Bitonti** | 40 | **#206** | **+82** | Now properly ranked based on performance |
| **Douglas Glod** | 35 | **#285** | **+185** | Dropped significantly (FV:35 now matters more) |
| **Chase DeLauter** | 50 | **#121** | **+38** | Improved (FV:50 weighted higher) |
| **Sal Stewart** | 45 | **#239** | **+9** | Slight improvement |

## Key Improvements

### 1. Bitonti vs Glod Fixed ✓
- **Old:** Glod #100, Bitonti #288 (Glod ranked 188 spots higher despite worse FV and stats)
- **New:** Bitonti #206, Glod #285 (Bitonti now ranked 79 spots higher - CORRECT)

**Why this happened:**
- Glod (FV:35) had strong individual tool grades (Hit:55, Power:50) and young age (18.7) which boosted his FG score despite low FV
- Bitonti (FV:40) had weaker tool grades (Hit:35) and missing performance grade, dragging down his FG score
- With 50% FV weight, Bitonti's higher FV (40 > 35) now properly outweighs Glod's individual tools
- With 40% V4 weight, Bitonti's excellent 2025 performance (.753 OPS, 19 HR) matters much more

### 2. DeLauter Improvement ✓
- **Old:** #159
- **New:** #121 (+38 spots)
- His FV:50 grade now carries more weight, partially offsetting missing 2025 data

### 3. Stewart Slight Improvement ✓
- **Old:** #248
- **New:** #239 (+9 spots)
- Still low due to missing 2025 MiLB data (promoted to MLB)

## Remaining Issues

### Missing 2025 Data Crisis

**CRITICAL FINDING:** 52.3% of FV 40+ prospects (473 of 904) have NO 2025 data at all.

**High-profile prospects missing ALL 2025 data:**
- Jesús Made (FV:65) - Currently #1 in V7 but NO 2025 data!
- Konnor Griffin (FV:65) - Currently #2 in V7 but NO 2025 data!
- Sebastian Walcott (FV:60) - #3
- Max Clark (FV:60) - #9
- 152 total FV 45+ prospects with no 2025 data

**Why this is a problem:**
- V4 score formula heavily weights 2025 performance
- Prospects without 2025 data get penalized even if they're elite
- Top 2 prospects in V7 have ZERO 2025 data - they're ranked purely on FG grades

**Possible causes:**
1. 2025 MiLB season is incomplete/not fully collected
2. Many top prospects promoted to MLB (like Stewart)
3. Injuries (DeLauter has no 2025 data anywhere)
4. Some prospects not linked properly (37% missing mlb_player_id)

### FanGraphs Linking Issues

**37.1% of FanGraphs prospects (336 of 905) still missing mlb_player_id:**
- These prospects can't be linked to MiLB/MLB game data
- Includes many top prospects (Made, Griffin, Walcott, etc.)
- The improved linking script helped but many remain unlinked
- These players likely don't have mlb_player_id assigned yet (international signings, new draft picks)

## Recommendations

### Immediate Actions

1. **Use the new V7 formula (50% FG with 50% FV weight, 40% V4, 10% V5)**
   - This provides much better balance than previous versions
   - Bitonti/Glod issue is largely resolved
   - DeLauter properly elevated

2. **Investigate 2025 data collection**
   - Check if MiLB data collection for 2025 is complete
   - Consider using 2024 as fallback for prospects without 2025 data
   - Or apply lighter recency penalty when 2025 data is missing

3. **Manual adjustments for edge cases**
   - Stewart (#239): Consider using his 2025 MLB stats for V4 calculation
   - Top prospects without any 2025 data: May need separate "prospect watch" list

### Long-term Improvements

1. **Improve MiLB ID linking**
   - Work on linking the 336 unlinked FanGraphs prospects
   - May need to use MLB draft data, international signing data
   - Consider fuzzy matching on more fields

2. **Handle missing data gracefully**
   - Don't penalize prospects for missing 2025 data as heavily
   - Use most recent season available with recency discount
   - Add data quality flags to rankings

3. **Regular FanGraphs updates**
   - FG grades change throughout the season
   - Bitonti's 2025 breakout may not be reflected in his FG grade yet
   - Consider scraping/importing mid-season grade updates

4. **Hybrid approach for promoted prospects**
   - Stewart has 2025 MLB data but no MiLB data
   - Could calculate V4-equivalent score using MLB stats with appropriate adjustment

## Summary

The updated V7 formula (50% FG with 50% FV weight, 40% V4, 10% V5) significantly improves ranking quality:

✅ **Bitonti properly ranks ahead of Glod** (#206 vs #285)
✅ **FV is now the primary driver** of FG scores (50% vs 20%)
✅ **Age bias reduced** (5% vs 15%)
✅ **Performance matters more** (40% V4 vs 20%)

However, **the missing 2025 data issue is severe** and affects 52% of rated prospects. This is a bigger problem than the formula weights and needs immediate investigation.

**Next Steps:**
1. Use the new V7 formula going forward
2. Investigate why 52% of prospects are missing 2025 data
3. Consider fallback to 2024 data for prospects without 2025 stats
4. Work on linking the 336 unlinked FanGraphs prospects
