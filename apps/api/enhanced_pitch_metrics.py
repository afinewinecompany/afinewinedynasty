"""
Enhanced pitch metrics that can be calculated from available data
Even when launch speed, velocity, and zone data are missing
"""

# Based on Jesús Made's data, here are metrics we CAN calculate:

AVAILABLE_METRICS = {
    # Basic Swing Decisions (100% available)
    'swing_rate': {
        'formula': 'swings / total_pitches',
        'description': 'How often the batter swings',
        'better': 'moderate (40-50% ideal)'
    },

    # Contact Ability (100% available)
    'contact_rate': {
        'formula': 'contact / swings',
        'description': 'Contact rate when swinging',
        'better': 'higher'
    },
    'whiff_rate': {
        'formula': 'swing_and_miss / swings',
        'description': 'Swing and miss rate',
        'better': 'lower'
    },
    'foul_rate': {
        'formula': 'fouls / swings',
        'description': 'Foul ball rate on swings',
        'better': 'moderate'
    },

    # Outcome Metrics (100% available)
    'strike_rate': {
        'formula': 'strikes / total_pitches',
        'description': 'Percentage ending in strikes',
        'better': 'lower for hitters'
    },
    'ball_rate': {
        'formula': 'balls / total_pitches',
        'description': 'Percentage ending in balls',
        'better': 'higher for hitters'
    },
    'called_strike_rate': {
        'formula': 'called_strikes / total_pitches',
        'description': 'Looking strikes',
        'better': 'lower'
    },
    'swinging_strike_rate': {
        'formula': 'swinging_strikes / total_pitches',
        'description': 'SwStr%',
        'better': 'lower'
    },

    # Count Leverage (100% available)
    'two_strike_approach': {
        'metrics': {
            'two_strike_swing_rate': 'swing_rate with 2 strikes',
            'two_strike_contact_rate': 'contact_rate with 2 strikes',
            'two_strike_chase_rate': 'chase_rate with 2 strikes (if zone available)'
        }
    },
    'first_pitch_swing_rate': {
        'formula': 'swings on 0-0 / total 0-0 pitches',
        'description': 'Aggressiveness on first pitch',
        'better': 'moderate'
    },
    'ahead_in_count_swing_rate': {
        'formula': 'swings when ahead / pitches when ahead',
        'description': 'Selectivity when ahead',
        'better': 'lower (more selective)'
    },
    'behind_in_count_contact_rate': {
        'formula': 'contact when behind / swings when behind',
        'description': 'Ability to protect',
        'better': 'higher'
    },

    # Advanced Approach Metrics
    'in_play_rate': {
        'formula': '(contact - fouls) / total_pitches',
        'description': 'Balls put in play rate',
        'better': 'higher'
    },
    'productive_swing_rate': {
        'formula': '(contact - fouls) / swings',
        'description': 'Non-foul contact rate',
        'better': 'higher'
    },

    # Discipline Proxy (even without zone data)
    'selectivity_score': {
        'formula': 'weighted average of swing_rate, contact_rate, ball_rate',
        'description': 'Overall plate discipline',
        'better': 'higher'
    }
}

# SQL query to calculate all these metrics
ENHANCED_METRICS_QUERY = """
WITH pitch_data AS (
    SELECT * FROM milb_batter_pitches
    WHERE mlb_batter_id = :mlb_player_id
        AND season = :season
),
count_situations AS (
    SELECT
        -- Two strike situations
        COUNT(*) FILTER (WHERE strikes = 2) as two_strike_pitches,
        COUNT(*) FILTER (WHERE swing = TRUE AND strikes = 2) as two_strike_swings,
        COUNT(*) FILTER (WHERE contact = TRUE AND strikes = 2) as two_strike_contacts,

        -- First pitch
        COUNT(*) FILTER (WHERE balls = 0 AND strikes = 0) as first_pitches,
        COUNT(*) FILTER (WHERE swing = TRUE AND balls = 0 AND strikes = 0) as first_pitch_swings,

        -- Ahead in count (hitter's advantage)
        COUNT(*) FILTER (WHERE
            (balls = 1 AND strikes = 0) OR
            (balls = 2 AND strikes = 0) OR
            (balls = 2 AND strikes = 1) OR
            (balls = 3 AND strikes = 0) OR
            (balls = 3 AND strikes = 1)
        ) as ahead_pitches,
        COUNT(*) FILTER (WHERE swing = TRUE AND (
            (balls = 1 AND strikes = 0) OR
            (balls = 2 AND strikes = 0) OR
            (balls = 2 AND strikes = 1) OR
            (balls = 3 AND strikes = 0) OR
            (balls = 3 AND strikes = 1)
        )) as ahead_swings,

        -- Behind in count (pitcher's advantage)
        COUNT(*) FILTER (WHERE
            (balls = 0 AND strikes = 1) OR
            (balls = 0 AND strikes = 2) OR
            (balls = 1 AND strikes = 2)
        ) as behind_pitches,
        COUNT(*) FILTER (WHERE swing = TRUE AND (
            (balls = 0 AND strikes = 1) OR
            (balls = 0 AND strikes = 2) OR
            (balls = 1 AND strikes = 2)
        )) as behind_swings,
        COUNT(*) FILTER (WHERE contact = TRUE AND (
            (balls = 0 AND strikes = 1) OR
            (balls = 0 AND strikes = 2) OR
            (balls = 1 AND strikes = 2)
        )) as behind_contacts

    FROM pitch_data
)
SELECT
    -- Basic rates
    COUNT(*) as total_pitches,
    COUNT(*) FILTER (WHERE swing = TRUE) as swings,
    COUNT(*) FILTER (WHERE contact = TRUE) as contacts,
    COUNT(*) FILTER (WHERE swing_and_miss = TRUE) as whiffs,
    COUNT(*) FILTER (WHERE foul = TRUE) as fouls,

    -- Basic percentages
    COUNT(*) FILTER (WHERE swing = TRUE) * 100.0 / NULLIF(COUNT(*), 0) as swing_rate,
    COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_rate,
    COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,
    COUNT(*) FILTER (WHERE foul = TRUE) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as foul_rate,

    -- Outcome rates
    COUNT(*) FILTER (WHERE is_strike = TRUE) * 100.0 / NULLIF(COUNT(*), 0) as strike_rate,
    COUNT(*) FILTER (WHERE pitch_call = 'B') * 100.0 / NULLIF(COUNT(*), 0) as ball_rate,
    COUNT(*) FILTER (WHERE pitch_call = 'S' AND swing = FALSE) * 100.0 / NULLIF(COUNT(*), 0) as called_strike_rate,
    COUNT(*) FILTER (WHERE pitch_result = 'Swinging Strike') * 100.0 / NULLIF(COUNT(*), 0) as swinging_strike_rate,

    -- In play rate (contact that's not a foul)
    COUNT(*) FILTER (WHERE contact = TRUE AND foul = FALSE) * 100.0 / NULLIF(COUNT(*), 0) as in_play_rate,
    COUNT(*) FILTER (WHERE contact = TRUE AND foul = FALSE) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as productive_swing_rate,

    -- Count leverage metrics
    cs.two_strike_swings * 100.0 / NULLIF(cs.two_strike_pitches, 0) as two_strike_swing_rate,
    cs.two_strike_contacts * 100.0 / NULLIF(cs.two_strike_swings, 0) as two_strike_contact_rate,
    cs.first_pitch_swings * 100.0 / NULLIF(cs.first_pitches, 0) as first_pitch_swing_rate,
    cs.ahead_swings * 100.0 / NULLIF(cs.ahead_pitches, 0) as ahead_swing_rate,
    cs.behind_contacts * 100.0 / NULLIF(cs.behind_swings, 0) as behind_contact_rate,

    -- Calculate a discipline score (weighted composite)
    -- Higher contact rate = good
    -- Lower whiff rate = good
    -- Moderate swing rate = good (penalty for too high or too low)
    -- Higher ball rate = good (making pitchers throw strikes)
    (
        (COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0)) * 0.30 +
        (100 - COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0)) * 0.30 +
        CASE
            WHEN COUNT(*) FILTER (WHERE swing = TRUE) * 100.0 / NULLIF(COUNT(*), 0) BETWEEN 40 AND 50 THEN 100
            WHEN COUNT(*) FILTER (WHERE swing = TRUE) * 100.0 / NULLIF(COUNT(*), 0) BETWEEN 35 AND 55 THEN 75
            ELSE 50
        END * 0.20 +
        COUNT(*) FILTER (WHERE pitch_call = 'B') * 100.0 / NULLIF(COUNT(*), 0) * 0.20
    ) as discipline_score

FROM pitch_data, count_situations;
"""

def get_enhanced_metrics_for_player(conn, mlb_player_id, season=2025):
    """
    Calculate enhanced metrics for a player using available data
    """
    cursor = conn.cursor()

    # Execute the enhanced metrics query
    cursor.execute(ENHANCED_METRICS_QUERY.replace(':mlb_player_id', str(mlb_player_id)).replace(':season', str(season)))

    columns = [desc[0] for desc in cursor.description]
    result = cursor.fetchone()

    if result:
        metrics = dict(zip(columns, result))

        # Add interpretations
        metrics['interpretations'] = {
            'contact_ability': 'Elite' if metrics.get('contact_rate', 0) > 80 else 'Good' if metrics.get('contact_rate', 0) > 75 else 'Average',
            'whiff_tendency': 'Low' if metrics.get('whiff_rate', 0) < 20 else 'Average' if metrics.get('whiff_rate', 0) < 25 else 'High',
            'two_strike_approach': 'Excellent' if metrics.get('two_strike_contact_rate', 0) > 80 else 'Good' if metrics.get('two_strike_contact_rate', 0) > 75 else 'Needs Work',
            'plate_discipline': 'Strong' if metrics.get('discipline_score', 0) > 70 else 'Average' if metrics.get('discipline_score', 0) > 60 else 'Weak'
        }

        return metrics

    return None