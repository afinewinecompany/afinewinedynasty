# FanGraphs Scouting Grades ML Prediction System

## Overview
Build machine learning models that predict MLB success from FanGraphs scouting grades, then integrate these predictions into our prospect ranking system.

## Data Pipeline

### 1. FanGraphs Grades Collection ✅
**Files**:
- `fangraphs-the-board-hitters-{2022-2025}.csv`
- `fangraphs-the-board-pitchers-{2022-2025}.csv`
- `fangraphs-the-board-all-{2022-2025}-phys.csv`

**Script**: `scripts/import_fangraphs_csvs.py`

**Database**: `fangraphs_prospect_grades` table
- **Hitter Grades**: Hit, Game Power, Raw Power, Speed, Fielding, Pitch Selection, Bat Control
- **Pitcher Grades**: Fastball, Slider, Curveball, Changeup, Command
- **Physical Attributes**: Frame, Athleticism, Levers, Arm, Performance, Delivery
- **Metadata**: FV (Future Value 20-80), Top 100 Rank, Age, Organization

**Status**: Importing 4 years of data (2022-2025) → ~5,000+ prospect-years

### 2. Match to MLB Performance
**Strategy**:
- **2022 grades** → 2023-2025 MLB stats
- **2023 grades** → 2024-2025 MLB stats
- **2024 grades** → 2025 MLB stats

**Matching Logic**:
```sql
-- Join via fg_player_id
prospects.fg_player_id = fangraphs_prospect_grades.fg_player_id

-- Filter MLB performance AFTER prospect report
mlb.season >= fg.report_year

-- Minimum sample requirements
Hitters: >= 150 MLB PA total
Pitchers: >= 50 MLB IP total
```

**Target Variables**:
- **Hitters**: wRC+, OPS, ISO, BB%, K%, WAR
- **Pitchers**: FIP, ERA, WHIP, K%, BB%, WAR

### 3. ML Model Training

#### Hitter Model
**Features** (14 total):
1. `hit_future` - Hit tool grade (20-80)
2. `game_pwr_future` - Game power grade
3. `raw_pwr_future` - Raw power grade
4. `spd_future` - Speed grade
5. `fld_future` - Fielding grade
6. `pitch_sel` - Pitch selection grade
7. `bat_ctrl` - Bat control grade
8. `frame` - Physical frame (-2 to +2)
9. `athleticism` - Athleticism grade
10. `arm` - Arm strength/accuracy
11. `performance` - Performance grade
12. `hard_hit_pct` - Statcast hard hit % (when available)
13. `age` - Age at prospect report
14. `fv` - Overall Future Value (20-80)
15. `top_100_inverse` - 101 - rank (higher = better prospect)

**Target**: `avg_wrc_plus` (weighted by PA)

**Algorithm**: Random Forest Regressor
- 100 estimators
- Max depth 10
- Min samples per leaf: 5

**Expected Performance**:
- R² ~ 0.30-0.50 (scouting grades are inherently uncertain)
- MAE ~ 15-20 wRC+ points

#### Pitcher Model
**Features** (13 total):
1. `fb_future` - Fastball grade (20-80)
2. `sl_future` - Slider grade
3. `cb_future` - Curveball grade
4. `ch_future` - Changeup grade
5. `cmd_future` - Command grade
6. `frame` - Physical frame
7. `athleticism` - Athleticism grade
8. `arm` - Arm strength
9. `performance` - Performance grade
10. `delivery` - Delivery mechanics grade
11. `age` - Age at prospect report
12. `fv` - Overall Future Value
13. `top_100_inverse` - Inverted rank
14. `has_tj_surgery` - Tommy John surgery indicator

**Target**: `avg_fip` (weighted by IP)

**Algorithm**: Random Forest Regressor (same config)

**Expected Performance**:
- R² ~ 0.25-0.45
- MAE ~ 0.50-0.75 FIP

### 4. Feature Importance Analysis
After training, we'll identify which grades are most predictive:

**Expected Top Hitter Predictors**:
1. Hit tool (contact ability)
2. FV (overall consensus grade)
3. Top 100 rank (market signal)
4. Game power (translates to production)
5. Age (younger = more upside)

**Expected Top Pitcher Predictors**:
1. Command (most critical for MLB success)
2. FV (overall grade)
3. Fastball velocity/quality
4. Age
5. Breaking ball quality (SL/CB)

### 5. Integration into V6 Rankings

#### Current V6 Approach
- 70% V4 (MiLB performance-based)
- 30% V5 (ML projection from MiLB stats)

#### Enhanced V7 with FanGraphs
**Option A: Weighted Blend**
```
V7 = 0.50 * V4_performance
   + 0.25 * V5_milb_projection
   + 0.25 * FG_scout_projection
```

**Option B: Ensemble Voting**
- V4 provides floor (proven performance)
- V5 provides ceiling (statistical upside)
- FG provides expert validation (scout eyes)
- Combine via weighted average or stacking

**Option C: Uncertainty-Weighted**
- Young prospects (Age < 20): Higher FG weight (scouts see tools scouts see tools)
- Mid prospects (20-22): Balanced 33/33/33
- Old prospects (23+): Higher V4 weight (performance matters more)

#### Implementation
**Script**: `scripts/generate_prospect_rankings_v7.py`

**Process**:
1. Load V6 rankings
2. Match prospects to FanGraphs grades (2025 report)
3. Generate FG-based MLB prediction
4. Blend V6 + FG prediction
5. Export V7 rankings

### 6. Validation & Insights

#### Model Validation
- Cross-validation R² scores
- Residual analysis (which prospects over/under-perform grades?)
- Calibration plots (predicted vs actual MLB performance)

#### Scouting Insights
**Questions to Answer**:
1. Which tool grades are most predictive?
2. Does FV correlate with MLB outcomes?
3. Do Top 100 prospects significantly outperform peers?
4. How much does age matter vs tools?
5. Do physical attributes (frame, athleticism) matter beyond tool grades?
6. Is Hard Hit % (Statcast) more predictive than scouting grades?

#### Dynasty League Strategy
**Actionable Findings**:
- Which grades to prioritize in trades
- Whether to trust FanGraphs FV or our ML rankings
- How to weight youth vs proven performance
- Red flags (e.g., low command grade for pitchers)

## Expected Timeline

1. **Data Import** (~5-10 min) ✅
   - Import 4 years FanGraphs CSVs to database

2. **ML Training** (~2-5 min) 🔄
   - Match FG grades to MLB stats
   - Train hitter & pitcher models
   - Analyze feature importance

3. **V7 Generation** (~5 min)
   - Apply models to 2025 prospects
   - Blend with V6 rankings
   - Export final rankings

4. **Analysis & Iteration** (~ongoing)
   - Compare V6 vs V7
   - Validate top prospects
   - Refine blending strategy

## Success Metrics

### Model Performance
- **Hitter R²**: > 0.35 (beats random guessing)
- **Pitcher R²**: > 0.30
- **Calibration**: Predicted wRC+/FIP within ±20% of actual

### Ranking Quality
- **Top 50 Hit Rate**: >60% become useful MLB players (>1 WAR)
- **Top 10 Hit Rate**: >80% become stars (>3 WAR)
- **Age Balance**: Top 50 avg age 19-20 (not over-indexing on AAA vets)

### Insights Gained
- Quantify predictive value of each scouting grade
- Identify market inefficiencies (grades vs performance)
- Improve dynasty league decision-making

## Files

### Scripts
- ✅ `scripts/import_fangraphs_csvs.py` - Import CSV data
- 🔄 `scripts/train_fangraphs_predictor.py` - Train ML models
- ⏳ `scripts/generate_prospect_rankings_v7.py` - Create V7 rankings

### Data
- ✅ `fangraphs_prospect_grades` table (database)
- 🔄 `fangraphs_hitter_predictor.pkl` - Trained hitter model
- 🔄 `fangraphs_pitcher_predictor.pkl` - Trained pitcher model
- ⏳ `prospect_rankings_v7.csv` - Final rankings

### Documentation
- ✅ `FANGRAPHS_ML_PLAN.md` (this file)
- ⏳ `FANGRAPHS_MODEL_RESULTS.md` - Training results & insights
- ⏳ `V7_RANKINGS_SUMMARY.md` - V7 methodology & results

## Next Steps

1. ✅ Wait for FanGraphs import to complete
2. 🔄 Run `train_fangraphs_predictor.py`
3. ⏳ Analyze which grades matter most
4. ⏳ Create V7 rankings script
5. ⏳ Compare V6 vs V7 top 100
6. ⏳ Export final rankings for dynasty league

---

**Goal**: Build the most comprehensive, data-driven prospect ranking system by combining:
- ✅ MiLB performance metrics (V4)
- ✅ Statistical ML projections (V5)
- ✅ Statcast data (Barrel%, EV)
- 🔄 Expert scouting grades (FanGraphs)
- ⏳ Integrated ensemble (V7)
