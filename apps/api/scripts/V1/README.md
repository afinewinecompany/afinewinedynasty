# MiLB Data Collection V1

This directory contains scripts for collecting Minor League Baseball (MiLB) player statistics using the MLB StatsAPI wrapper.

## Overview

The collection system gathers comprehensive game-by-game statistics for all minor league players across multiple levels for seasons 2021-2025. It includes both hitting and pitching statistics and stores them in the PostgreSQL database.

## Scripts

### 1. `collect_milb_stats.py`
- Basic collection script for single season/level
- Demonstrates core functionality
- Good for understanding the collection process

### 2. `collect_milb_all_seasons.py`
- Main collection script for 2021-2025 seasons
- Includes checkpoint/resume capability
- Handles all minor league levels:
  - Triple-A
  - Double-A
  - High-A
  - Single-A
  - Rookie
  - Complex leagues

### 3. `run_collection.py`
- Runner script with command-line interface
- Provides test mode and full collection options
- Recommended entry point for collections

### 4. `check_collection_status.py`
- Monitoring script to check collection progress
- Shows statistics by season and data quality metrics
- Useful for tracking collection status

## Installation

1. **Install required packages:**
```bash
pip install MLB-StatsAPI asyncpg tabulate
```

2. **Ensure database is configured:**
- Database connection is configured in `app/core/config.py`
- The `milb_game_logs` table must exist (created by migration 017)

## Usage

### Test Collection (Recommended First)

Run a small test to verify everything works:

```bash
cd apps/api/scripts/V1
python run_collection.py --test
```

This will collect data for 2 Triple-A teams from 2024 season.

### Check Current Status

Check what data has already been collected:

```bash
python check_collection_status.py
```

### Collect Specific Season

Collect data for a single season:

```bash
python run_collection.py --season 2024
```

### Full Collection (All Seasons)

Run the complete collection for 2021-2025:

```bash
python run_collection.py --full
```

⚠️ **Note:** Full collection can take several hours to days depending on rate limits.

## Data Collected

### Player Game Logs Include:

**Hitting Statistics:**
- At-bats, hits, runs, RBIs
- Doubles, triples, home runs
- Walks, strikeouts, stolen bases
- Batting average, OBP, SLG, OPS

**Pitching Statistics:**
- Innings pitched, batters faced
- Wins, losses, saves, holds
- Hits/runs/earned runs allowed
- Strikeouts, walks, home runs allowed
- ERA, WHIP, batting average against

## Resume Capability

The collection system automatically saves progress in `collection_checkpoint.json`. If interrupted, it will resume from the last checkpoint when restarted.

## Rate Limiting

The scripts include built-in rate limiting to respect API limits:
- 0.1 second delay between player requests
- 2 second delay between teams
- 30 second delay between seasons

## Database Schema

Data is stored in the `milb_game_logs` table with the following key columns:
- `mlb_player_id`: MLB's unique player identifier
- `season`: Year of the season
- `game_pk`: Unique game identifier
- `game_date`: Date of the game
- Full hitting and pitching statistics (99+ columns total)

## Monitoring Progress

### Log Files
Collection progress is logged to `logs/milb_collection_2021_2025.log`

### Database Queries
You can also monitor progress directly:

```sql
-- Count total game logs
SELECT COUNT(*) FROM milb_game_logs;

-- Count by season
SELECT season, COUNT(*)
FROM milb_game_logs
GROUP BY season
ORDER BY season;

-- Count unique players
SELECT COUNT(DISTINCT mlb_player_id)
FROM milb_game_logs;
```

## Troubleshooting

### Connection Issues
- Verify database connection in `.env` file
- Ensure PostgreSQL is running
- Check network connectivity to MLB Stats API

### Missing Data
- Some players may not have game logs available
- Spring training and playoff games are separate (use different game types)
- Data availability varies by year and level

### Performance
- If collection is slow, check rate limits in the script
- Consider running during off-peak hours
- Monitor database performance for large datasets

## Next Steps

After collecting the data, you can:
1. Run data quality checks
2. Calculate advanced statistics
3. Build ML models for player projections
4. Generate prospect rankings

## Support

For issues or questions, check:
- Log files in `V1/logs/` directory
- Checkpoint file for resume status
- Database for collected records