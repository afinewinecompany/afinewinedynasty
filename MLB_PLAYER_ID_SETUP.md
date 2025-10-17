# MLB Player ID Population - Setup Guide

## Overview

This document describes the setup for populating MLB player IDs in the prospect table using the MLB Stats API.

## Database Changes

### New Column Added

A new column `mlb_player_id` has been added to the `prospects` table:

- **Column Name**: `mlb_player_id`
- **Type**: `VARCHAR(20)`
- **Nullable**: `YES`
- **Indexed**: `YES`
- **Purpose**: Store the official MLB Stats API player ID for pitch-by-pitch data collection

### Migration

Migration file: `apps/api/alembic/versions/a9a3952fbabf_add_mlb_player_id_to_prospects.py`

The column already existed in production, so the migration will be skipped automatically.

### Model Update

Updated `apps/api/app/db/models.py`:

```python
class Prospect(Base):
    # ...
    mlb_player_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)  # MLB Stats API player ID
```

## Population Script

### Script Location

`apps/api/scripts/populate_mlb_player_ids.py`

### Features

The script uses advanced matching logic with multiple criteria:

1. **Name Matching** (base score 0.0-1.0)
   - Full name similarity
   - Last name + first name weighted scoring
   - Suffix normalization (Jr, Sr, II, III, IV)

2. **Team Matching** (+0.15 bonus)
   - Matches current organization/team abbreviation

3. **Birth Date Matching** (+0.20 bonus)
   - Exact birth date comparison
   - Most reliable matching criterion

4. **Age Matching** (+0.10 bonus)
   - Allows 1-year difference for timing variations

5. **Position Matching** (+0.10 bonus)
   - Handles pitcher position variants (P, SP, RP)

### Usage

```bash
# Test with 10 prospects (dry-run, no database updates)
python scripts/populate_mlb_player_ids.py --limit 10 --dry-run

# Test with 50 prospects (actual updates)
python scripts/populate_mlb_player_ids.py --limit 50

# Run for all unmatched prospects
python scripts/populate_mlb_player_ids.py
```

### Command Line Options

- `--limit N`: Only process N prospects (useful for testing)
- `--dry-run`: Run without making database updates (test mode)

### Rate Limiting

The script includes built-in rate limiting:
- 1 second pause every 10 requests
- Respects MLB Stats API usage guidelines

## Expected Results

Based on testing with 50 prospects:
- **Match Rate**: ~84% (42 out of 50 found)
- **High Confidence**: All matches have score ≥ 0.85
- **Match Details**: Shows which criteria were used (team, age, position, birth date)

### Example Output

```
[1] Konnor Griffin (PIT) -> Konnor Griffin (ID: 804606)
     [score: 1.20, matched: age:19, pos:SS]
```

This shows:
- Prospect name and team
- Matched MLB player name
- MLB Stats API player ID
- Final confidence score
- Which criteria matched

## Database Statistics

### Before Population
- Total prospects: 1,274
- With MLB player ID: 12 (0.9%)
- Without MLB player ID: 1,262

### After Population (Estimated)
- Expected match rate: ~80-85%
- Expected final count: ~1,050-1,100 prospects with MLB player IDs

## Next Steps

Once the MLB player IDs are populated, you can:

1. **Collect Pitch-by-Pitch Data**
   - Use the `mlb_player_id` to query MLB Stats API
   - Collect detailed pitch data for analysis
   - Example endpoint: `/api/v1/people/{mlb_player_id}/stats`

2. **Cross-Reference with Game Logs**
   - Join with `milb_game_logs` table using `mlb_player_id`
   - Validate matches have game log data

3. **Handle Unmatched Prospects**
   - Review prospects without MLB player IDs
   - May need manual matching for:
     - Very recent signees
     - International players not yet in system
     - Name variations/spelling differences

## Data Quality

### High Confidence Matches
- Score ≥ 1.0: Multiple criteria matched (team, age, position)
- Score ≥ 0.9: Strong name match + 1-2 supporting criteria
- Score ≥ 0.85: Good name match + at least one criterion

### Unmatched Prospects
Common reasons for no match:
1. Player too new (not yet in MLB API)
2. International player without MLB assignment
3. Name spelling variations
4. Player released/retired

## Monitoring

To check population status:

```sql
-- Overall statistics
SELECT
    COUNT(*) as total,
    COUNT(mlb_player_id) as with_mlb_id,
    ROUND(COUNT(mlb_player_id)::numeric / COUNT(*) * 100, 1) as percentage
FROM prospects;

-- By organization
SELECT
    organization,
    COUNT(*) as total,
    COUNT(mlb_player_id) as with_mlb_id
FROM prospects
GROUP BY organization
ORDER BY total DESC;

-- Sample matched prospects
SELECT name, organization, position, age, mlb_player_id
FROM prospects
WHERE mlb_player_id IS NOT NULL
LIMIT 10;
```

## Troubleshooting

### Script Issues

1. **Rate Limiting Errors**: Increase sleep time in script
2. **API Timeouts**: Check internet connection and MLB API status
3. **Database Connection**: Verify `SQLALCHEMY_DATABASE_URI` in `.env`

### Low Match Rate

If match rate is lower than expected:
1. Check data quality in prospects table
2. Verify names are properly formatted
3. Review age/birth_date accuracy
4. Consider manual matching for important prospects

## Future Enhancements

Potential improvements:
1. Add FanGraphs ID matching via Chadwick Bureau
2. Implement manual override interface
3. Add batch processing for large prospect lists
4. Include minor league team affiliations in matching
5. Add fuzzy matching for name variations
