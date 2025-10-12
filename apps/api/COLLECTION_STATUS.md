# MiLB Pitching Data Collection - Status

## Current Status: RUNNING

**Start Time:** 2025-10-07 13:16:26 EST

### Batch Collection Progress

The system is now collecting MiLB game logs with **BOTH hitting and pitching data** for multiple seasons.

**Seasons being collected:**
1. ✨ 2024 (In Progress)
2. ⏳ 2023 (Pending)
3. ⏳ 2022 (Pending)
4. ⏳ 2021 (Pending)

**Levels per season:** AAA, AA, A+

**Expected total players:** ~4,100 per season = ~16,400 total

---

## What's Being Collected

For each player:
- **Hitting Stats** (all players)
  - Games, PA, AB, H, 2B, 3B, HR, RBI, BB, K, SB, CS
  - AVG, OBP, SLG, OPS, BABIP

- **Pitching Stats** (pitchers only: P, SP, RP, LHP, RHP)
  - Games pitched, GS, IP, W, L, SV, HLD, BS
  - Hits allowed, ER, BB, K, HR allowed
  - ERA, WHIP, K/9, BB/9, H/9
  - Plus 40+ additional advanced pitching metrics

---

## All Fixes Applied ✅

1. **Safe float conversion** - Handles MLB API's `.---` undefined values
2. **Database conflict resolution** - Uses correct `(game_pk, mlb_player_id)` unique key
3. **Game type fix** - Uses 'Regular' instead of 'R'
4. **College player filtering** - Excludes non-professional teams
5. **Dual collection** - Fetches both hitting and pitching data

---

## Expected Timeline

**Per season:**
- Discovery: ~5 minutes (finding all players)
- Collection: ~3-6 hours (fetching all game logs with 0.5s delay)

**Total for all 4 seasons:** ~12-24 hours

---

## Monitoring Progress

Check the batch script output:
```bash
cd apps/api
python -c "
import asyncio
from sqlalchemy import text
from app.db.database import engine

async def check_progress():
    async with engine.begin() as conn:
        # Pitching data collected
        result = await conn.execute(text('''
            SELECT
                season,
                COUNT(DISTINCT mlb_player_id) as pitchers,
                COUNT(*) as pitching_games,
                ROUND(AVG(innings_pitched), 2) as avg_ip
            FROM milb_game_logs
            WHERE games_pitched > 0
            GROUP BY season
            ORDER BY season DESC
        '''))
        print('\nPitching Data Collected:')
        print('Season | Pitchers | Games | Avg IP')
        print('-------|----------|-------|-------')
        for row in result:
            print(f'{row[0]}   | {row[1]:8d} | {row[2]:5d} | {row[3]:6.2f}')

        # Hitting data collected
        result = await conn.execute(text('''
            SELECT
                season,
                COUNT(DISTINCT mlb_player_id) as players,
                COUNT(*) as hitting_games
            FROM milb_game_logs
            WHERE games_played > 0
            GROUP BY season
            ORDER BY season DESC
        '''))
        print('\nHitting Data Collected:')
        print('Season | Players | Games')
        print('-------|---------|------')
        for row in result:
            print(f'{row[0]}   | {row[1]:7d} | {row[2]:5d}')

asyncio.run(check_progress())
"
```

---

## When Complete

After all seasons finish collecting:

1. **Verify data quality**
   ```sql
   SELECT
       season,
       COUNT(*) as total_rows,
       COUNT(CASE WHEN games_pitched > 0 THEN 1 END) as pitching_rows,
       COUNT(CASE WHEN games_played > 0 THEN 1 END) as hitting_rows
   FROM milb_game_logs
   GROUP BY season
   ORDER BY season DESC;
   ```

2. **Re-run prospect rankings** to include pitcher game counts
   ```bash
   cd apps/api
   python scripts/generate_prospect_rankings.py
   ```

3. **Update ML models** to use new pitching features

---

## Script Location

**Main collection script:** `apps/api/scripts/collect_all_milb_gamelog.py`

**Batch runner:** `apps/api/run_all_seasons_collection.py`

**This status file:** `apps/api/COLLECTION_STATUS.md`

---

## Troubleshooting

If the script stops or encounters errors:

1. Check logs for specific error messages
2. Most common issues are already fixed (float conversion, constraints)
3. Can resume by running individual seasons:
   ```bash
   cd apps/api
   python -m scripts.collect_all_milb_gamelog --season 2023 --levels AAA AA A+
   ```

---

**Last Updated:** 2025-10-07 13:16:26 EST
