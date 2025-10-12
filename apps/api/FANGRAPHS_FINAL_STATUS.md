# Fangraphs Integration Final Status

## Data Import Summary
- **File imported**: `fangraphs-the-board-pitchers-2025.csv`
- **Total records**: 1,321 players (both hitters and pitchers)
- **943 position players** + **378 pitchers**

## Database Schema Issue
The imported CSV contains both hitters and pitchers, but the database schema only supports **pitching grades**:
- ✅ FB (Fastball) grade
- ✅ SL (Slider) grade
- ✅ CB (Curveball) grade
- ✅ CH (Changeup) grade
- ✅ CMD (Command) grade
- ✅ FV (Future Value)
- ✅ Velocity (sits/tops)
- ❌ Hit grade (not in database)
- ❌ Power grade (not in database)
- ❌ Speed grade (not in database)
- ❌ Field grade (not in database)

## Linkage Status
- **No direct ID matches**: Fangraphs IDs (like "sa3065496", "28824") don't match MLB player IDs
- **Name-based matching required**: Must use fuzzy matching on player names
- **Expected match rate**: 30-40% for prospects

## Median Fallback System ✅ IMPLEMENTED

### How it works:
1. **Matched players**: Get actual Fangraphs grades
2. **Unmatched players**: Use median grades from all Fangraphs prospects
3. **Indicator field**: `has_fg_grades` shows match status:
   - `1.0` = Matched to actual Fangraphs player
   - `0.5` = Using median fallback values
   - `0.0` = No grades available

### Benefits:
- **All players get reasonable scouting grades** instead of zeros
- **Reduces bias** in ML models toward matched players
- **Better generalization** for the majority of unmatched players

## ML Pipeline Integration

The ML training pipeline will now:
1. Try to match players by name (fuzzy matching)
2. Use actual grades when matched (~30-40% of prospects)
3. Use median grades for unmatched players (~60-70%)
4. Train models with this hybrid approach

### Expected Impact:
- **More stable predictions** for all players
- **Reduced overfitting** to the small matched subset
- **Better baseline** for unknown prospects

## Recommendations

1. **Get complete Fangraphs data**:
   - Need hitting tool grades (Hit, Power, Speed, Field)
   - Currently missing for position players
   - Would significantly improve predictions for hitters

2. **Improve linkage**:
   - Build a manual mapping table for top prospects
   - Use additional data sources for better matching
   - Consider using birth dates or draft info for matching

3. **Current status is usable**:
   - Pitchers have full scouting grades
   - Hitters use FV (Future Value) only
   - Median fallback prevents null values
   - System is ready for ML training

## Usage

```python
# The ML pipeline automatically uses Fangraphs with fallback
from train_projection_model import ProjectionModelTrainer

trainer = ProjectionModelTrainer(target='wrc_plus')
model = await trainer.train_full_pipeline()
# Will use FangraphsFeatureEngineer with median fallback
```

## Summary
✅ Fangraphs data imported (1,321 players)
✅ Median fallback system implemented
✅ ML pipeline integrated
⚠️ Only pitching grades available (hitter grades missing)
⚠️ ~30-40% match rate expected
✅ Ready for training with fallback for unmatched players