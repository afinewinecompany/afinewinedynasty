-- COMPREHENSIVE DIAGNOSTIC QUERIES FOR BRYCE ELDRIDGE AA/AAA INVESTIGATION
-- Player: Bryce Eldridge (MLB ID: 805811)
-- Expected: 25 CPX, 556 AA, 1,165 AAA pitches
-- Actual: 25 CPX pitches only

-- ==============================================================================
-- DIAGNOSTIC 1: Check all distinct level values in database
-- ==============================================================================
SELECT DISTINCT level, COUNT(*) as game_count
FROM milb_game_logs
WHERE season IN (2023, 2024, 2025)
GROUP BY level
ORDER BY level;

-- ==============================================================================
-- DIAGNOSTIC 2: Find ALL games for Bryce Eldridge (any level, any season)
-- ==============================================================================
SELECT
    season,
    level,
    COUNT(DISTINCT game_pk) as games,
    SUM(plate_appearances) as total_pa,
    MIN(game_date) as first_game,
    MAX(game_date) as last_game
FROM milb_game_logs
WHERE mlb_player_id = 805811
GROUP BY season, level
ORDER BY season DESC, level;

-- ==============================================================================
-- DIAGNOSTIC 3: Check for AA/AAA games using flexible pattern matching
-- ==============================================================================
SELECT
    game_pk,
    game_date,
    level,
    team,
    opponent,
    plate_appearances,
    hits,
    at_bats
FROM milb_game_logs
WHERE mlb_player_id = 805811
  AND (
    level ILIKE '%AA%' OR
    level ILIKE '%DOUBLE%' OR
    level ILIKE '%TRIPLE%' OR
    level = 'AA' OR
    level = 'AAA'
  )
ORDER BY game_date;

-- ==============================================================================
-- DIAGNOSTIC 4: Verify level values exist in database (sanity check)
-- ==============================================================================
SELECT
    'AA Games in DB' as check_type,
    COUNT(*) as count
FROM milb_game_logs
WHERE level = 'AA' AND season IN (2023, 2024, 2025)
UNION ALL
SELECT
    'AAA Games in DB',
    COUNT(*)
FROM milb_game_logs
WHERE level = 'AAA' AND season IN (2023, 2024, 2025);

-- ==============================================================================
-- DIAGNOSTIC 5: Check pitch data table for any AA/AAA attribution
-- ==============================================================================
SELECT
    season,
    level,
    COUNT(DISTINCT game_pk) as unique_games,
    COUNT(*) as total_pitches,
    MIN(game_date) as first_pitch_date,
    MAX(game_date) as last_pitch_date
FROM milb_batter_pitches
WHERE mlb_batter_id = 805811
GROUP BY season, level
ORDER BY season DESC, level;

-- ==============================================================================
-- DIAGNOSTIC 6: Cross-reference pitch data with game logs
-- ==============================================================================
SELECT
    bp.season,
    bp.level as pitch_level,
    gl.level as gamelog_level,
    bp.game_pk,
    bp.game_date,
    COUNT(*) as pitch_count
FROM milb_batter_pitches bp
LEFT JOIN milb_game_logs gl
    ON bp.game_pk = gl.game_pk
    AND bp.mlb_batter_id = gl.mlb_player_id
WHERE bp.mlb_batter_id = 805811
GROUP BY bp.season, bp.level, gl.level, bp.game_pk, bp.game_date
ORDER BY bp.game_date;

-- ==============================================================================
-- DIAGNOSTIC 7: Search for games by player name pattern (in case ID is wrong)
-- ==============================================================================
SELECT DISTINCT
    mlb_player_id,
    team,
    opponent,
    level,
    season,
    COUNT(*) as games
FROM milb_game_logs
WHERE (team ILIKE '%Eldridge%' OR opponent ILIKE '%Eldridge%')
  AND season IN (2023, 2024, 2025)
GROUP BY mlb_player_id, team, opponent, level, season
ORDER BY season DESC;

-- ==============================================================================
-- DIAGNOSTIC 8: Check prospects table for correct ID mapping
-- ==============================================================================
SELECT
    name,
    mlb_player_id,
    fg_player_id,
    position,
    current_level,
    team
FROM prospects
WHERE mlb_player_id = '805811'
   OR name ILIKE '%Eldridge%';

-- ==============================================================================
-- DIAGNOSTIC 9: Find similar prospects with AA/AAA data (for comparison)
-- ==============================================================================
SELECT
    p.name,
    p.mlb_player_id,
    gl.season,
    gl.level,
    COUNT(DISTINCT gl.game_pk) as games,
    SUM(gl.plate_appearances) as total_pa
FROM prospects p
JOIN milb_game_logs gl ON p.mlb_player_id::integer = gl.mlb_player_id
WHERE gl.level IN ('AA', 'AAA')
  AND gl.season = 2025
  AND p.position IN ('1B', 'C', 'OF', 'DH')  -- Similar positions
GROUP BY p.name, p.mlb_player_id, gl.season, gl.level
HAVING COUNT(DISTINCT gl.game_pk) > 10
ORDER BY total_pa DESC
LIMIT 10;

-- ==============================================================================
-- DIAGNOSTIC 10: Check for orphaned pitch data (pitches without game logs)
-- ==============================================================================
SELECT
    bp.game_pk,
    bp.game_date,
    bp.level,
    COUNT(*) as pitch_count,
    CASE WHEN gl.game_pk IS NULL THEN 'NO GAME LOG' ELSE 'HAS GAME LOG' END as status
FROM milb_batter_pitches bp
LEFT JOIN milb_game_logs gl
    ON bp.game_pk = gl.game_pk
    AND bp.mlb_batter_id = gl.mlb_player_id
WHERE bp.mlb_batter_id = 805811
GROUP BY bp.game_pk, bp.game_date, bp.level, gl.game_pk
ORDER BY bp.game_date;

-- ==============================================================================
-- DIAGNOSTIC 11: Sample AA/AAA games to verify data structure
-- ==============================================================================
SELECT
    game_pk,
    game_date,
    level,
    mlb_player_id,
    team,
    opponent,
    plate_appearances
FROM milb_game_logs
WHERE level IN ('AA', 'AAA')
  AND season = 2025
ORDER BY game_date DESC
LIMIT 10;

-- ==============================================================================
-- SUMMARY QUERY: Complete data picture
-- ==============================================================================
SELECT
    'Game Logs' as source,
    season,
    level,
    COUNT(DISTINCT game_pk) as games,
    SUM(plate_appearances) as pa,
    CAST(SUM(plate_appearances) * 4.5 AS INTEGER) as expected_pitches
FROM milb_game_logs
WHERE mlb_player_id = 805811
GROUP BY season, level
UNION ALL
SELECT
    'Pitch Data' as source,
    season,
    level,
    COUNT(DISTINCT game_pk) as games,
    NULL as pa,
    COUNT(*) as pitches
FROM milb_batter_pitches
WHERE mlb_batter_id = 805811
GROUP BY season, level
ORDER BY source, season DESC, level;
