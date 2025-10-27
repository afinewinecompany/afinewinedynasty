# MLB Stat Projection System - Progress Summary

**Date:** October 20, 2025
**Status:** ✅ Hitters Complete | ⚠️ Pitchers Blocked

---

## 🎉 Major Success: Prospects Table Population

Successfully added **1,010 MLB players** to the prospects table!

### Before & After
| Metric | Before | After | Change |
|--------|--------|-------|---------|
| Total Prospects | 1,349 | 2,359 | +75% |
| MLB Player IDs | 1,326 | 2,336 | +76% |
| Missing MLB Players | 1,010 | 0 | -100% |

### Results
- ✅ **0 failures** during population
- ✅ All 1,010 players fetched from MLB Stats API
- ✅ Metadata populated: name, position, height, weight, birth date, draft info

---

## 📊 Hitter Training Data: SUCCESS!

### Training Dataset Growth
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| MiLB→MLB Transitions Found | 1,040 | 1,040 | - |
| Training Samples Extracted | 22 | **399** | **+1,714%** |
| Features per Sample | 37 | 37 | - |
| Target Stats | 13 | 13 | - |

### 18x Increase in Training Data!
From 22 samples → 399 samples

### Notable Players in Dataset
- Bobby Witt Jr. (SS)
- Cal Raleigh (C)
- Daulton Varsho (CF)
- Brandon Marsh (CF)
- And 395 more...

### Training Data File
**Location:** `apps/api/stat_projection_hitters_train_20251020_124431.csv`

**Structure:**
```
- Features (37): MiLB stats (PA, HR, BB, SO, SB, etc.) + derived metrics (ISO, BB%, K%, power-speed number) + Fangraphs grades
- Targets (13): MLB career stats (AVG, OBP, SLG, OPS, ISO, BB%, K%, HR/600, SB/600, RBI/600, Runs/600, games, PA)
```

---

## ⚠️ Pitcher Training Data: BLOCKED

### Problem Identified
**We don't have MLB pitching data!**

### Investigation Results
| Data Source | Status | Count |
|-------------|--------|-------|
| MiLB Pitcher Appearances | ✅ Available | 17,375 rows (379 pitchers) |
| MLB Pitcher Game Logs | ❌ Missing | 0 rows |
| MLB Statcast Pitching | ❌ Empty Table | 0 rows |

### Root Cause
The `mlb_game_logs` table only contains **batting statistics**. There's no MLB pitching data collected for the 2021-2025 period.

**Tables checked:**
- `mlb_game_logs` - Only batting stats (PA, HR, AVG, etc.)
- `mlb_statcast_pitching` - Empty (0 rows)
- No `mlb_pitcher_appearances` or `mlb_pitching_stats` table exists

### Why This Happened
The population script fetched players from `mlb_game_logs` which only tracks batting appearances. Pitchers who **only pitched** (no batting appearances) were not added to prospects table, and even if they were, we have no MLB pitching outcomes to train on.

---

## 📋 Current State

### ✅ What We Have
1. **Complete Prospects Table** - 2,359 prospects with 2,336 MLB Player IDs
2. **Hitter Training Data** - 399 samples ready for model training
3. **MiLB Pitcher Data** - 17,375 appearances for 379 pitchers

### ❌ What We're Missing
1. **MLB Pitching Data** - No pitching game logs or outcomes
2. **Pitcher Training Data** - Can't build dataset without MLB outcomes

---

## 🚀 Next Steps

### Option 1: Collect MLB Pitching Data (RECOMMENDED)
**Collect MLB pitching game logs (2021-2025) from MLB Stats API**

**Approach:**
1. Query MLB Stats API for pitcher game logs (ERA, IP, K, BB, WHIP, etc.)
2. Create `mlb_pitcher_appearances` table (similar to `milb_pitcher_appearances`)
3. Populate with pitching lines for all pitchers who debuted 2021+
4. Re-run training data builder to extract pitcher samples

**Estimated effort:** 4-6 hours (API collection + schema design + data validation)

**Expected result:** 200-400 pitcher training samples

---

### Option 2: Start with Hitters Only
**Train and deploy hitter stat projection model first**

**Approach:**
1. ✅ Training data ready (399 samples)
2. Build multi-output XGBoost regressor
3. Train on 13 MLB stat targets
4. Deploy to API endpoint
5. Add to Projections page (hitters only)

**Estimated effort:** 2-3 hours

**Benefits:**
- Ship 50% of the feature immediately
- Validate ML pipeline end-to-end
- Collect pitching data in parallel

---

### Option 3: Use Pitch-by-Pitch Data (EXPERIMENTAL)
**Aggregate MLB pitch data to create pitcher outcomes**

**Approach:**
1. Check if `mlb_pitcher_pitches` or similar table exists
2. Aggregate pitch-level data to game-level stats (IP, ERA, K, BB, etc.)
3. Use aggregated data as MLB outcomes

**Risk:** Pitch-by-pitch data may not cover all games/appearances

---

## 🎯 Recommendation

**Proceed with Option 1 + Option 2 in parallel:**

1. **Immediate (1-2 days):**
   - Train hitter stat projection model (399 samples)
   - Deploy hitter projections to frontend
   - Ship hitter rankings page

2. **Next phase (3-5 days):**
   - Collect MLB pitching data from API
   - Build pitcher training dataset
   - Train pitcher model
   - Deploy pitcher projections

3. **Final integration (1 day):**
   - Combine hitter + pitcher projections
   - Create unified Projections page with two tabs

---

## 📈 Expected Model Performance

### Hitter Model (399 samples)
**Targets:** 13 continuous stats (AVG, OBP, SLG, OPS, HR/600, etc.)

**Expected R² scores:**
- Rate stats (AVG, OBP, SLG): **0.35-0.50** (moderate correlation)
- Counting stats (HR/600, RBI/600): **0.25-0.40** (challenging)
- Overall: **RMSE ~0.045-0.060 for rate stats**

**Training approach:**
- Multi-output XGBoost regressor
- Features: 37 (MiLB stats + derived + Fangraphs grades)
- Temporal validation: Train on 2018-2022, test on 2023+
- Cross-validation: 5-fold

### Pitcher Model (TBD - once data collected)
**Targets:** ERA, WHIP, K/9, BB/9, FIP, career IP, etc.

**Expected R² scores:** Similar to hitters (0.30-0.50)

---

## 💾 Files Created

### Scripts
- `populate_prospects_from_mlb_debuts.py` - ✅ Completed successfully
- `build_stat_projection_training_data.py` - ✅ Hitters done, pitchers blocked

### Data
- `stat_projection_hitters_train_20251020_124431.csv` - 399 samples, ready for training

### Documentation
- `STAT_PROJECTION_PROGRESS_SUMMARY.md` - This file

---

## 🔍 Technical Notes

### Why Only 399/1,040 Samples Extracted?
The builder found 1,040 prospects with MiLB→MLB transitions, but only extracted 399 training samples (38%).

**Reasons for 641 dropped samples:**
1. **Missing pre-debut MiLB data** - Player's MiLB stats not in season before debut
2. **Insufficient MiLB PA** - Less than threshold for meaningful stats
3. **Missing Fangraphs grades** - No prospect grades available
4. **Data quality issues** - Null values, incomplete records

This is **normal and expected**. A 38% extraction rate is reasonable given:
- Not all players have complete MiLB coverage
- Some debuted without significant MiLB time (international FAs, college seniors)
- Fangraphs grades only cover top prospects

### Hitter Training Data Features (37)

**MiLB Stats (23):**
- season, level, team, games, pa, ab, r, h, doubles, triples, hr, rbi, bb, ibb, so, sb, cs, hbp, sf, avg, obp, slg, ops

**Derived Metrics (9):**
- babip, iso, bb_rate, k_rate, power_speed_number, bb_per_k, xbh, xbh_rate, sb_success_rate

**Fangraphs Grades (5):**
- hit_future, game_power_future, raw_power_future, speed_future, fielding_future

### MLB Target Stats (13)

**Rate Stats:**
- target_avg, target_obp, target_slg, target_ops, target_bb_rate, target_k_rate, target_iso

**Counting Stats (per 600 PA):**
- target_hr_per_600, target_sb_per_600, target_rbi_per_600, target_r_per_600

**Career Stats:**
- target_career_games, target_career_pa

---

## ✅ Summary

### Completed
1. ✅ Populated prospects table (+1,010 MLB players)
2. ✅ Built hitter training dataset (399 samples)
3. ✅ Identified pitcher data gap

### Blocked
1. ⚠️ Pitcher training data - Need MLB pitching stats

### Next Action
**Choose path forward:**
- Option 1: Collect MLB pitching data → Complete system
- Option 2: Ship hitters only → Iterate on pitchers
- Option 3: Use pitch-by-pitch aggregation → Experimental

---

*Ready to proceed with hitter model training or MLB pitching data collection!*
