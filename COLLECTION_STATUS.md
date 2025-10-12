# MiLB Play-by-Play Collection Status

**Last Updated:** October 11, 2025 9:26 PM

## Overview

Successfully launched **8 concurrent collection processes** to gather MiLB play-by-play data for seasons 2021-2024.

## Active Collections

### 2021 Season
- **Batch 1**: 100 players (RUNNING)
- **Batch 2**: 1,000 players (RUNNING)
- **Priority**: HIGHEST (currently 0 plate appearances in database)

### 2022 Season
- **Batch 1**: 100 players (RUNNING)
- **Batch 2**: 1,000 players (RUNNING)
- **Current Coverage**: 8.3% (54,295 plate appearances)

### 2023 Season
- **Batch 1**: 100 players (RUNNING)
- **Batch 2**: 1,000 players (RUNNING)
- **Current Coverage**: 9.0% (75,818 plate appearances)

### 2024 Season
- **Batch 1**: 100 players (RUNNING)
- **Batch 2**: 1,000 players (RUNNING)
- **Current Coverage**: 8.9% (74,550 plate appearances)

## Collection Details

### Database
- **Host**: Railway PostgreSQL
- **Table**: `milb_plate_appearances`
- **Connection**: ✅ Working

### Script Updates Made
1. Added `dotenv` environment loading at script initialization
2. Updated query to pull from `milb_game_logs` instead of `prospects` table
3. Filters players with >20 games to focus on meaningful data
4. Processes by player-season combinations for accurate tracking

### Estimated Completion Time

**Batch 1 (100 players per year)**: 2-3 hours
**Batch 2 (1000 players per year)**: 1-2 days

Each player averages ~120-140 games, and the API requests are rate-limited at 0.5 seconds per request.

## Monitoring

Check real-time status:
```bash
python monitor_collections.py
```

View logs:
- 2021 Batch 1: `logs/pbp_2021.log`
- 2021 Batch 2: `logs/pbp_2021_batch2.log`
- 2022 Batch 1: `logs/pbp_2022.log`
- 2022 Batch 2: `logs/pbp_2022_batch2.log`
- 2023 Batch 1: `logs/pbp_2023.log`
- 2023 Batch 2: `logs/pbp_2023_batch2.log`
- 2024 Batch 1: `logs/pbp_2024.log`
- 2024 Batch 2: `logs/pbp_2024_batch2.log`

## Next Steps

After current batches complete:
1. Verify data in Railway database
2. Check coverage percentages
3. Launch additional batches if needed to reach 100% coverage
4. Can run unlimited collections by removing `--limit` parameter

## Technical Notes

- All collections run independently in background
- Database handles concurrent inserts via unique constraints
- Duplicate data is automatically prevented by composite keys
- Rate limiting prevents API throttling (0.5s delay per request)
- Each collection saves progress continuously to database
