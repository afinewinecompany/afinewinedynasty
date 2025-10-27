# Historical Data Audit Report (2021-2025)

**Generated:** 2025-10-19 07:27:27
**Total Prospects:** 1,295 (440 pitchers, 855 batters)

---

## Executive Summary

This audit reveals **significant coverage gaps** in historical pitch-by-pitch data for seasons 2021-2024, while 2025 data collection is performing well (81% pitcher coverage, 69% batter coverage).

### Key Findings:
- **2025 Coverage:** Excellent - 81% pitchers, 69% batters have pitch data
- **2024 Coverage:** Poor - Only 5% pitchers, 16% batters have pitch data
- **2021-2023 Coverage:** Critical - Near zero pitch-by-pitch data (<6%)
- **Total Database:** 1.56M pitches across all seasons

---

## Detailed Coverage by Season

### Batter Data Coverage

| Season | Batters w/ PA | PA Coverage | Total PAs | Batters w/ Pitches | Pitch Coverage | Total Pitches |
|--------|---------------|-------------|-----------|-----------------------|----------------|---------------|
| 2021   | 98            | 11.5%       | 47,919    | **46**                | **5.4%**       | 66,759        |
| 2022   | 783           | 91.6%       | 108,974   | **45**                | **5.3%**       | 79,439        |
| 2023   | 848           | 99.2%       | 136,729   | **27**                | **3.2%**       | 53,847        |
| 2024   | 902           | 105.5%      | 132,653   | **133**               | **15.6%**      | 150,712       |
| 2025   | 1,245         | 145.6%      | 383,082   | **593**               | **69.4%**      | 753,353       |

**Key Insight:** Plate appearance (PA) data is excellent for 2022-2025 (>90% coverage), but **pitch-by-pitch data is severely lacking** for 2021-2024.

### Pitcher Data Coverage

| Season | Pitchers w/ App | App Coverage | Total Apps | Pitchers w/ Pitches | Pitch Coverage | Total Pitches |
|--------|-----------------|--------------|------------|---------------------|----------------|---------------|
| 2021   | 37              | 8.4%         | 389        | **0**               | **0.0%**       | 0             |
| 2022   | 100             | 22.7%        | 1,522      | **0**               | **0.0%**       | 0             |
| 2023   | 190             | 43.2%        | 3,243      | **4**               | **0.9%**       | 603           |
| 2024   | 283             | 64.3%        | 5,386      | **22**              | **5.0%**       | 5,505         |
| 2025   | 357             | 81.1%        | 6,835      | **358**             | **81.4%**      | 454,330       |

**Key Insight:** 2025 pitcher data is excellent, but **2021-2024 pitcher pitch data is essentially non-existent** (0-5% coverage).

---

## Coverage Gaps Analysis

### Batters Missing Data by Season

| Season | Missing PA Data | Missing Pitch Data |
|--------|-----------------|-------------------|
| 2021   | 854 / 855 (99.9%) | 821 / 855 (96.0%) |
| 2022   | 835 / 855 (97.7%) | 817 / 855 (95.6%) |
| 2023   | 785 / 855 (91.8%) | 830 / 855 (97.1%) |
| 2024   | 729 / 855 (85.3%) | 729 / 855 (85.3%) |
| 2025   | 269 / 855 (31.5%) | 269 / 855 (31.5%) |

### Pitchers Missing Data by Season

| Season | Missing Appearances | Missing Pitch Data |
|--------|-------------------|-------------------|
| 2021   | 403 / 440 (91.6%) | 440 / 440 (100.0%) |
| 2022   | 340 / 440 (77.3%) | 440 / 440 (100.0%) |
| 2023   | 250 / 440 (56.8%) | 436 / 440 (99.1%) |
| 2024   | 157 / 440 (35.7%) | 418 / 440 (95.0%) |
| 2025   | 83 / 440 (18.9%)  | 82 / 440 (18.6%)  |

---

## Overall Database Totals (2021-2025)

- **Total Plate Appearances:** 809,357
- **Total Batter Pitches:** 1,104,110
- **Total Pitcher Appearances:** 17,375
- **Total Pitcher Pitches:** 460,438
- **Total All Pitches:** 1,564,548
- **Total All Events:** 826,732

---

## Recommendations for Data Collection

### HIGH PRIORITY - Critical Gaps

#### 2024 Season (Most Recent Historical)
**Why Priority:** Most recent complete season, essential for current prospect evaluation

**Needed:**
- **Pitcher pitch data:** 418 pitchers missing (95.0% gap)
- **Batter pitch data:** 722 batters missing (84.4% gap)

**Action:** Run `collect_2024_pitcher_data_robust.py` and `collect_2024_batter_data_robust.py`

#### 2023 Season
**Why Priority:** Recent season, important for trend analysis

**Needed:**
- **Pitcher pitch data:** 436 pitchers missing (99.1% gap)
- **Batter pitch data:** 828 batters missing (96.8% gap)

**Action:** Run `collect_2023_pitcher_data_robust.py` and `collect_2023_batter_data_robust.py`

### MEDIUM PRIORITY - Older Historical Data

#### 2022 Season
**Needed:**
- **Pitcher pitch data:** 440 pitchers missing (100.0% gap)
- **Batter pitch data:** 810 batters missing (94.7% gap)

**Action:** Run `collect_2022_pitcher_data_robust.py` and `collect_2022_batter_data_robust.py`

#### 2021 Season
**Needed:**
- **Pitcher pitch data:** 440 pitchers missing (100.0% gap)
- **Batter pitch data:** 809 batters missing (94.6% gap)

**Action:** Run `collect_2021_pitcher_data_robust.py` and `collect_2021_batter_data_robust.py`

---

## Available Collection Scripts

### Existing Scripts Found:
```
✓ collect_2021_batter_data_robust.py
✓ collect_2021_pitcher_data_robust.py
✓ collect_2022_batter_data_robust.py
✓ collect_2022_pitcher_data_robust.py
✓ collect_2023_batter_data_robust.py
✓ collect_2023_pitcher_data_robust.py
✓ collect_pitcher_data_2023.py
✓ collect_batter_pitches_2023.py
✓ historical_data_ingestion.py
```

### Current 2025 Collection Status:
- **Script:** `collect_pitcher_data_robust.py` - **COMPLETED** ✓
- **Last Run:** Completed ~6.5 hours ago
- **Results:** 358/440 pitchers collected (81.4%)

---

## Suggested Collection Plan

### Phase 1: Complete 2024 Data (URGENT)
1. Run pitcher collection for 2024
2. Run batter collection for 2024
3. **Estimated Time:** 4-6 hours total
4. **Expected Yield:** ~300-400 pitchers, ~600-700 batters

### Phase 2: Complete 2023 Data (HIGH PRIORITY)
1. Run pitcher collection for 2023
2. Run batter collection for 2023
3. **Estimated Time:** 4-6 hours total
4. **Expected Yield:** ~200-300 pitchers, ~500-600 batters

### Phase 3: Fill 2021-2022 Gaps (MEDIUM PRIORITY)
1. Run 2022 collections
2. Run 2021 collections
3. **Estimated Time:** 6-8 hours total
4. **Expected Yield:** Varies by prospect activity in those years

### Phase 4: Complete Remaining 2025 Gaps (LOW PRIORITY)
1. Remaining 82 pitchers and 269 batters for 2025
2. Many may not have data available (injured, not playing)

---

## Data Quality Notes

### Why Some Prospects Have No Data:
1. **Injured/Did Not Play:** Prospect was injured or did not play in that season
2. **Promoted to MLB:** Prospect was promoted and only has MLB data
3. **International/Other Leagues:** Playing in non-tracked leagues
4. **Retired/Released:** No longer in system
5. **API Limitations:** Data not available via MLB Stats API

### Expected Coverage After Full Collection:
- **2024-2025:** 75-85% coverage (excellent)
- **2022-2023:** 60-75% coverage (good)
- **2021:** 40-60% coverage (fair - many prospects weren't active)

---

## Next Steps

1. **Review existing collection scripts** to ensure they're configured properly
2. **Start with 2024 pitcher collection** as highest priority
3. **Run collections sequentially** to avoid rate limiting
4. **Monitor progress** and log results
5. **Update this audit** after each collection run

---

## Questions to Consider

1. **Do we need pre-2021 data?** (2019-2020 for deeper historical analysis)
2. **Should we prioritize certain prospects?** (Top 100, specific organizations)
3. **What's the MLB API rate limit?** (May affect collection speed)
4. **Do we need MLB (not MiLB) data?** (For graduated prospects)

---

**Report Generated by:** `audit_all_seasons.py`
**Next Audit Recommended:** After completing Phase 1 (2024 data collection)
