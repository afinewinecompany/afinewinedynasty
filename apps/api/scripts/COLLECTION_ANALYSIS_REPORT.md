# Prospect Data Collection Analysis Report
*Generated: October 17, 2025*

## Executive Summary

We have completed a comprehensive analysis of prospect data collection across play-by-play and pitch-by-pitch datasets from 2021-2025. The analysis revealed significant gaps in pitch-by-pitch collection and identified 89 out of the Top 100 MLB prospects needing data collection.

## Key Findings

### 1. Overall Collection Status
- **Total prospects in database**: 1,274
- **Prospects with play-by-play data**: 2,399 unique players
- **Prospects with pitch-by-pitch data**: 172 batters (MAJOR GAP!)
- **Total plate appearances collected**: 777,317
- **Total pitches collected**: 431,990

### 2. Top 100 Prospects Analysis
- **79 prospects missing from CSV** were not in our database initially
- **321 prospects matched** between CSV and database
- **89 of Top 100 prospects** need some form of data collection:
  - 10 not in database at all
  - 41 have NO data whatsoever
  - 38 need pitch-by-pitch data

### 3. Data Coverage by Year

| Year | Play-by-Play Players | Pitch-by-Pitch Batters | Gap    |
|------|---------------------|------------------------|--------|
| 2021 | 98                  | 46                     | -52    |
| 2022 | 783                 | 45                     | -738   |
| 2023 | 848                 | 23                     | -825   |
| 2024 | 902                 | 48                     | -854   |
| 2025 | 1,128               | 66                     | -1,062 |

**Critical Issue**: Pitch-by-pitch collection is severely lacking across all years!

## Priority Collection Targets

### Priority 1: Top Prospects with NO Data (20 prospects)
Highest-ranked prospects missing all data:
- Rank #6: Samuel Basallo (BAL) - MLB ID: 694212
- Rank #7: Bryce Eldridge (SF) - MLB ID: 805811
- Rank #13: Nolan McLean (NYM) - MLB ID: 690997
- Rank #20: Payton Tolle (BOS) - MLB ID: 801139
- Rank #21: Bubba Chandler (PIT) - MLB ID: 696149

### Priority 2: Top Prospects Needing Pitch Data (38 prospects)
Including the #1 and #2 ranked prospects:
- Rank #1: Konnor Griffin (PIT) - MLB ID: 804606
- Rank #2: Kevin McGonigle (DET) - MLB ID: 805808
- Rank #4: Leo De Vries (ATH) - MLB ID: 815888
- Rank #8: JJ Wetherholt (STL) - MLB ID: 802139

### Priority 3: Prospects to Add to Database (10 prospects)
- Rank #3: Jesus Made (MIL)
- Rank #18: Luis Pena (MIL)
- Rank #48: Josue Briceno (DET)
- And 7 others

## Generated Collection Assets

1. **collection_priority_top20.txt** - MLB IDs for top 20 prospects with no data
2. **collection_pitch_only.txt** - MLB IDs for 38 prospects needing pitch data
3. **prospects_to_add_to_database.txt** - 10 prospects not in database

## Recommended Action Plan

### Immediate Actions (Today)
1. Add the 10 missing prospects to database using MLB Stats API
2. Start collection for top 20 prospects with no data (focus on 2024-2025)

### Short-term (This Week)
1. Run pitch-by-pitch collection for 38 prospects with existing PBP data
2. Verify data quality for collected records
3. Set up automated collection monitoring

### Medium-term (This Month)
1. Backfill pitch-by-pitch data for 2021-2023 seasons
2. Expand collection to include next 100 prospects (101-200)
3. Implement incremental collection updates

## Technical Recommendations

1. **API Optimization**: Batch requests to minimize API calls
2. **Collection Priority**: Focus on 2024-2025 seasons for recent performance
3. **Data Validation**: Implement checks for complete game coverage
4. **Monitoring**: Set up alerts for collection failures
5. **Documentation**: Track which players/dates have been collected

## Files Generated

- `missing_prospects_20251017_093027.csv` - 79 prospects not in database
- `matched_prospects_20251017_093027.csv` - 321 matched prospects
- `top_100_collection_needs_20251017_093441.csv` - Collection needs analysis
- `prospects_with_no_data_20251017_093442.csv` - Prospects with zero data
- Collection scripts and priority lists as detailed above

## Conclusion

The analysis reveals a critical gap in pitch-by-pitch data collection, with only 172 batters having this detailed data compared to 2,399 with play-by-play data. Immediate action should focus on:

1. Adding missing top prospects to the database
2. Collecting comprehensive data for the top 20 prospects with no data
3. Expanding pitch-by-pitch collection across all prospects

This will ensure comprehensive coverage for player evaluation and model training purposes.