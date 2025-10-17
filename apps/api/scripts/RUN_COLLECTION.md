# Quick Start - Pitch Collection

## Run Collection Now

### Option 1: Test Run (Recommended First)
```bash
cd apps/api/scripts
python run_all_pitch_collections.py --test
```
**Collects:** 5 prospects per season (2021-2025)
**Time:** 15-30 minutes
**Purpose:** Validate setup and check data quality

### Option 2: Full Collection (All Seasons)
```bash
cd apps/api/scripts
python run_all_pitch_collections.py
```
**Collects:** All tracked prospects (2021-2025)
**Time:** 6-10 hours
**Data:** ~42M pitch records

### Option 3: Single Season
```bash
cd apps/api/scripts
python collect_pitch_data_2024.py              # Full 2024 collection
python collect_pitch_data_2024.py --limit 100  # Test with 100 prospects
```
**Collects:** One season at a time
**Time:** 1-2 hours per season

### Option 4: Specific Seasons
```bash
cd apps/api/scripts
python run_all_pitch_collections.py --seasons 2024 2025
python run_all_pitch_collections.py --seasons 2024 2025 --limit 50
```
**Collects:** Only specified seasons
**Time:** Varies by season count

---

## What Gets Collected

✅ **Prospects only** (from `prospects` table)
✅ **Every pitch** seen as batter
✅ **Every pitch** thrown as pitcher
✅ **Velocity, spin, movement** per pitch
✅ **Batted ball data** (exit velo, launch angle)
✅ **Swing decisions** (whiff, contact, chase)

---

## Monitor Progress

The scripts log progress in real-time:
```
[2024] - INFO - Found 1,234 players for 2024
[1/1234] Juan Soto (New York Yankees)
  Processing Juan Soto (ID: 665742)
    Found 89 games
      Progress: 40/89 games
    Collected 1,847 pitches

Progress: 100/1234 players
Pitches collected: 823,456
Games processed: 6,789
```

---

## Verify After Collection

```bash
# Quick SQL check
psql $DATABASE_URL -c "
SELECT season, COUNT(*) as pitches, COUNT(DISTINCT mlb_batter_id) as prospects
FROM milb_batter_pitches
GROUP BY season
ORDER BY season;
"
```

---

## Full Documentation

- **Usage Guide:** [PITCH_COLLECTION_README.md](PITCH_COLLECTION_README.md)
- **Complete Analysis:** [../../../PITCH_BY_PITCH_REVIEW_SUMMARY.md](../../../PITCH_BY_PITCH_REVIEW_SUMMARY.md)
- **Ready to Run:** [../../../PITCH_COLLECTION_READY_TO_RUN.md](../../../PITCH_COLLECTION_READY_TO_RUN.md)

---

## Need Help?

Check [PITCH_COLLECTION_README.md](PITCH_COLLECTION_README.md) for:
- Troubleshooting
- Database setup
- Verification queries
- Use case examples
