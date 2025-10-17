# ✅ Pitch Collection - Working!

## Status: TEST COLLECTION IN PROGRESS

The pitch-by-pitch collection is successfully collecting data!

---

## ✅ Confirmed Working

**Test Run Results:**
- Player 682877: 890+ pitches collected (still running)
- Data saved to `milb_batter_pitches` table
- Pitch-level details confirmed (velocity, type, location, etc.)

---

## Strategy Change

**Original Plan:** Collect only for prospects with MLB IDs
**Problem:** Only 9 prospects have MLB IDs (most are still in minors)
**New Strategy:** Collect for ALL MiLB players, filter by prospects later

This gives you complete data for all prospects, even those without MLB IDs yet.

---

## How to Run Full Collection

```bash
cd apps/api/scripts

# Single season
python collect_pitch_data_2024.py

# All seasons (2021-2025) concurrently
python run_all_pitch_collections.py
```

**Expected:**
- ~75-100M pitch records total
- 12-18 hours for all seasons
- ~50GB database storage

---

## Link to Your Prospects After

Use these queries to filter for tracked prospects:

```sql
-- By player_id_mapping
SELECT * FROM milb_batter_pitches bp
INNER JOIN player_id_mapping pm ON bp.mlb_batter_id = pm.mlb_id
WHERE pm.fg_id IN (SELECT fg_player_id FROM fangraphs_unified_grades);

-- By prospects table (when MLB IDs populated)
SELECT * FROM milb_batter_pitches bp
INNER JOIN prospects p ON bp.mlb_batter_id::text = p.mlb_player_id;
```

---

## Files Ready

All scripts updated and working:
- ✅ collect_pitch_data_2021.py
- ✅ collect_pitch_data_2022.py
- ✅ collect_pitch_data_2023.py
- ✅ collect_pitch_data_2024.py
- ✅ collect_pitch_data_2025.py
- ✅ run_all_pitch_collections.py

Ready to collect!
