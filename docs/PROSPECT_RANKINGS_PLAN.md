# Prospect Rankings System - Implementation Plan

## Goal
Create an ML-powered prospect ranking system that ranks all MiLB prospects (players with <130 MLB ABs or <50 IP) based on predicted MLB performance.

## Current Status

### ✅ Completed
1. **Data Collection**:
   - MiLB game logs: 164,738 games, 2,140 players
   - MLB game logs: 9,123 games, 120 players
   - Birth dates: 2,427/2,429 players (99.9%)
   - Statcast PBP: ⏳ In progress (8,582+ PAs collected)

2. **ML Model Training**:
   - Trained Random Forest models on 1,626 players
   - Zero-label approach (prospects get 0s for MLB stats)
   - Performance: wRC+ R²=0.309, OBP R²=0.311, wOBA R²=0.282

3. **Feature Engineering**:
   - Age-adjusted features
   - Progression metrics
   - Level-specific stats
   - Statcast metrics (avg EV, max EV, 90th%, hard hit%, barrel%, fly ball EV, avg LA)

### ⏳ In Progress
1. **Statcast Collection**: 3 parallel collections running (2024, 2023, 2022) - ~3-5% complete

### 📝 To Do
1. Fix database schema access issue
2. Generate prospect rankings with ML predictions
3. Create rankings table in database
4. Export rankings to CSV
5. Build API endpoint for rankings

---

## Ranking System Design

### Prospect Definition
**Prospect** = Player with <130 MLB at-bats AND currently active in MiLB system

### Ranking Methodology

**Step 1: Train ML Models**
- Use existing [train_all_players_predictor.py](../apps/api/scripts/train_all_players_predictor.py)
- Train on ALL players (1,626 total):
  - 194 with MLB experience (have target stats)
  - 1,432 prospects/no MLB (get zeros for targets)
- Predict multiple MLB metrics:
  - wRC+ (primary metric)
  - wOBA
  - OPS
  - OBP
  - SLG

**Step 2: Generate Predictions**
- Calculate features for all prospects
- Use trained models to predict MLB performance
- Create composite score:
  ```
  composite_score = (pred_wRC+ × 0.4) + (pred_OPS × 100 × 0.3) + (pred_wOBA × 200 × 0.3)
  ```

**Step 3: Rank Prospects**
- Sort by composite score (descending)
- Assign ranks 1-N
- Include metadata: name, age, position, team, level

**Step 4: Save & Export**
- Save to `prospect_rankings` table
- Export to CSV file
- Provide top 50/100/all rankings

---

## Features Used for Ranking

### Core MiLB Performance
- Total PAs
- Avg OPS, OBP, SLG, BA
- ISO (isolated power)
- BB%, SO%, HR%, SB%

### Age-Adjusted Metrics
- Age at highest level
- Age difference from level average
- Age-adjusted OPS
- Age-adjusted ISO

### Progression Features
- OPS improvement per year
- OPS progression rate (recent vs career)
- Seasons active
- Levels played

### Level-Specific Stats
- Highest level reached
- Highest level OPS, BB%, SO%
- Recent OPS (last 20 games)

### Statcast Metrics (when available)
- Avg exit velocity
- Max exit velocity
- 90th percentile exit velocity
- Hard hit % (≥95 mph)
- Avg launch angle
- Fly ball exit velocity
- Barrel %

---

## Database Schema

### `prospect_rankings` Table

```sql
CREATE TABLE prospect_rankings (
    id SERIAL PRIMARY KEY,
    mlb_player_id INTEGER NOT NULL UNIQUE,
    rank INTEGER NOT NULL,
    full_name VARCHAR(255),
    current_age FLOAT,
    primary_position VARCHAR(50),
    current_team VARCHAR(255),
    highest_level VARCHAR(20),
    total_milb_pa INTEGER,
    milb_ops FLOAT,
    pred_wrc_plus FLOAT,
    pred_woba FLOAT,
    pred_ops FLOAT,
    pred_obp FLOAT,
    pred_slg FLOAT,
    composite_score FLOAT,
    has_statcast BOOLEAN DEFAULT FALSE,
    avg_ev FLOAT,
    barrel_pct FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Indexes
```sql
CREATE INDEX idx_rankings_rank ON prospect_rankings(rank);
CREATE INDEX idx_rankings_composite ON prospect_rankings(composite_score DESC);
CREATE INDEX idx_rankings_position ON prospect_rankings(primary_position);
CREATE INDEX idx_rankings_team ON prospect_rankings(current_team);
```

---

## Output Format

### CSV Export Format
```csv
rank,mlb_player_id,full_name,age,position,team,level,milb_pas,milb_ops,pred_wrc_plus,pred_woba,pred_ops,composite_score
1,123456,John Doe,22.5,SS,Team A,AAA,1200,0.850,105.2,0.350,0.825,95.3
2,234567,Jane Smith,21.3,OF,Team B,AA,800,0.790,98.5,0.335,0.780,88.7
...
```

### Console Output Format
```
==================================================================================================================
TOP 50 PROSPECTS BY ML PREDICTION
==================================================================================================================
Rank   Name                      Age    Pos    Team                Level    PAs      MiLB OPS   Pred wRC+    Pred wOBA    Pred OPS
------------------------------------------------------------------------------------------------------------------
1      John Doe                  22.5   SS     Team A              AAA      1200     0.850      105.2        0.350        0.825
2      Jane Smith                21.3   OF     Team B              AA       800      0.790      98.5         0.335        0.780
...
```

---

## Ranking Tiers

Rankings will be divided into tiers based on composite score:

| Tier | Composite Score | Description | MLB Projection |
|------|----------------|-------------|----------------|
| **Elite** | 85+ | Top-tier prospects | All-Star potential |
| **Plus** | 70-84 | High-quality prospects | Above-average regular |
| **Average** | 55-69 | Solid prospects | Average regular |
| **Below Average** | 40-54 | Depth prospects | Bench/platoon player |
| **Fringe** | <40 | Organizational depth | Limited MLB potential |

---

## Usage Examples

### Generate Rankings
```bash
cd apps/api
python -m scripts.generate_prospect_rankings
```

### View Top 50
```bash
cd apps/api
python -m scripts.generate_prospect_rankings --top 50
```

### Filter by Position
```sql
SELECT * FROM prospect_rankings
WHERE primary_position = 'SS'
ORDER BY rank;
```

### Filter by Team
```sql
SELECT * FROM prospect_rankings
WHERE current_team = 'Tampa Bay Rays'
ORDER BY rank;
```

### Export All Rankings
```sql
COPY prospect_rankings TO '/path/to/all_rankings.csv' CSV HEADER;
```

---

## API Endpoints (Planned)

### GET /api/prospects/rankings
Returns paginated prospect rankings

**Query Parameters**:
- `page` (int): Page number
- `limit` (int): Results per page
- `position` (string): Filter by position
- `team` (string): Filter by team
- `level` (string): Filter by MiLB level
- `min_age` (float): Minimum age
- `max_age` (float): Maximum age

**Response**:
```json
{
  "rankings": [
    {
      "rank": 1,
      "mlb_player_id": 123456,
      "full_name": "John Doe",
      "age": 22.5,
      "position": "SS",
      "team": "Team A",
      "level": "AAA",
      "milb_pa": 1200,
      "milb_ops": 0.850,
      "predictions": {
        "wrc_plus": 105.2,
        "woba": 0.350,
        "ops": 0.825
      },
      "composite_score": 95.3,
      "tier": "Elite"
    }
  ],
  "total": 1500,
  "page": 1,
  "per_page": 50
}
```

### GET /api/prospects/rankings/{player_id}
Returns ranking details for specific player

### GET /api/prospects/rankings/compare
Compare multiple prospects side-by-side

---

## Update Schedule

### Daily (Automated)
- Recalculate rankings with latest game data
- Update predictions for players with new PAs
- Refresh Statcast metrics as new data arrives

### Weekly
- Retrain ML models with new season data
- Re-evaluate feature importance
- Adjust composite score weights if needed

### Seasonal
- Full model retraining with historical data
- Add new prospects to database
- Archive previous season rankings

---

## Implementation Steps

### Phase 1: Fix Database Access ✋ BLOCKED
1. Identify correct database connection/schema
2. Test queries against actual table structure
3. Update script with correct column names

### Phase 2: Generate Initial Rankings
1. Run existing ML training script ([train_all_players_predictor.py](../apps/api/scripts/train_all_players_predictor.py:1))
2. Save trained models to disk
3. Load models and generate predictions for all prospects
4. Calculate composite scores
5. Assign ranks

### Phase 3: Create Rankings Table
1. Create `prospect_rankings` table
2. Insert rankings data
3. Add indexes for performance
4. Verify data integrity

### Phase 4: Export & Visualize
1. Export rankings to CSV
2. Print top 50 to console
3. Generate summary statistics
4. Create tier breakdowns

### Phase 5: API Development (Future)
1. Create FastAPI endpoints
2. Add filtering/pagination
3. Implement caching
4. Add authentication

---

## Known Issues & Limitations

### Current Limitations
1. **Database Schema Mismatch**: Scripts use different column names than actual schema
2. **Statcast Coverage**: Only ~30-35% of batted balls have Statcast data in MiLB
3. **Limited Historical Data**: Only 2020-2024 seasons collected
4. **No Pitcher Rankings**: Current system only ranks hitters

### Future Improvements
1. **Add Pitcher Rankings**: Separate model for pitching prospects
2. **Include Defensive Metrics**: Add fielding stats when available
3. **Player Comparisons**: Find similar historical players
4. **Projection Confidence**: Add uncertainty estimates to predictions
5. **Interactive Dashboard**: Web UI for exploring rankings
6. **Trade Value**: Incorporate prospect value in trade scenarios

---

## Success Metrics

### Model Performance
- R² > 0.30 for wRC+ predictions (✅ Current: 0.309)
- R² > 0.30 for OBP predictions (✅ Current: 0.311)
- R² > 0.25 for wOBA predictions (✅ Current: 0.282)

### Ranking Quality
- Top 50 prospects should include most highly-regarded industry prospects
- Age adjustments should properly value young vs old prospects at same level
- Statcast features should improve rankings for players with data

### System Performance
- Generate rankings for all prospects in <5 minutes
- API response time <200ms
- Rankings updated daily without manual intervention

---

## References

### Similar Systems
- [MLB Pipeline Prospect Rankings](https://www.mlb.com/prospects)
- [FanGraphs The Board](https://www.fangraphs.com/prospects/the-board)
- [Baseball America Top 100](https://www.baseballamerica.com/rankings/)
- [Baseball Prospectus PECOTA](https://www.baseballprospectus.com/prospects/)

### Methodology Influences
- PECOTA projection system
- ZiPS projection system
- Steamer projection system
- Marcel the Monkey (simple baseline)

### Machine Learning Resources
- Prospect Development Aging Curves
- MiLB to MLB Translation Models
- Statcast Predictive Models

---

**Last Updated**: 2025-10-07
**Next Action**: Fix database schema access to enable ranking generation
