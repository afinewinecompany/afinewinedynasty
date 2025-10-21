"""
Create Enhanced ML Training Data for Hitters
=============================================

Adds new derived features to improve hitter model performance:
1. plus_tool_count - How many 55+ tools
2. offensive_ceiling - Max of hit/power (need ONE elite skill)
3. defensive_floor - Min of fielding/speed (can you stay on field?)
4. hit_power_ratio - Contact vs power profile
5. power_speed_number_v2 - Enhanced PSN
6. age_relative_ops - Performance vs age/level baseline
7. contact_profile - One-hot: slugger/contact/balanced
8. levels_per_year - Promotion speed
9. has_elite_tool - Binary: ANY tool 60+

Expected improvement: +0.03-0.05 F1 (0.684 → 0.73)
"""

import asyncio
import asyncpg
import pandas as pd
import numpy as np
from datetime import datetime
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"


def calculate_plus_tool_count(row):
    """Count how many tools are 55+ (above average)."""
    tools = [
        row.get('hit_future', 0),
        row.get('game_power_future', 0),
        row.get('raw_power_future', 0),
        row.get('speed_future', 0),
        row.get('fielding_future', 0)
    ]
    return sum(1 for t in tools if t >= 55)


def calculate_offensive_ceiling(row):
    """Maximum offensive tool (hit or power)."""
    return max(
        row.get('hit_future', 0),
        row.get('game_power_future', 0)
    )


def calculate_defensive_floor(row):
    """Minimum defensive tool (fielding and speed)."""
    return min(
        row.get('fielding_future', 50),
        row.get('speed_future', 50)
    )


def calculate_hit_power_ratio(row):
    """
    Ratio of hit tool to power tool.

    >1.2: Contact-first hitter
    0.8-1.2: Balanced
    <0.8: Power-first hitter
    """
    hit = row.get('hit_future', 50)
    power = row.get('game_power_future', 50)

    if power > 0:
        return hit / power
    return 1.0


def calculate_power_speed_number_v2(row):
    """
    Enhanced Power-Speed Number blending stats and grades.

    Traditional: 2*HR*SB / (HR+SB)
    Enhanced: 60% grades + 40% stats
    """
    # Stats-based PSN
    hr = row.get('total_hr', 0)
    sb = row.get('total_sb', 0)
    psn_stats = (2 * hr * sb) / (hr + sb) if (hr + sb) > 0 else 0

    # Grade-based PSN
    power_grade = row.get('game_power_future', 50)
    speed_grade = row.get('speed_future', 50)
    psn_grades = (power_grade + speed_grade) / 2

    # Blend
    return 0.6 * psn_grades + 0.4 * psn_stats


def calculate_age_relative_ops(row):
    """
    Compare OPS to age/level baseline.

    Positive = outperforming
    Negative = underperforming
    """
    ops = row.get('avg_ops')
    age = row.get('avg_age')
    level = row.get('highest_level')

    # Handle missing values
    if ops is None or age is None or level is None:
        return 0.0

    # Age-level baselines (empirical estimates)
    baselines = {
        (1, 18): 0.600, (1, 19): 0.650, (1, 20): 0.700,
        (2, 19): 0.650, (2, 20): 0.700, (2, 21): 0.750,
        (3, 20): 0.700, (3, 21): 0.750, (3, 22): 0.800,
        (4, 21): 0.750, (4, 22): 0.800, (4, 23): 0.850,
        (5, 22): 0.800, (5, 23): 0.850, (5, 24): 0.900
    }

    baseline = baselines.get((int(level), int(age)), 0.750)
    return float(ops) - baseline


def determine_contact_profile(row):
    """
    Classify hitter as slugger/contact/balanced based on K rate and ISO.

    Returns one-hot encoded dict.
    """
    k_rate = row.get('k_rate', 0.25)
    iso = row.get('isolated_power', 0.100)

    if k_rate > 0.30 and iso > 0.200:
        profile = 'power_slugger'
    elif k_rate < 0.15 and iso < 0.150:
        profile = 'contact_hitter'
    elif k_rate < 0.20 and iso > 0.200:
        profile = 'balanced_star'
    else:
        profile = 'average_hitter'

    return {
        'is_power_slugger': 1 if profile == 'power_slugger' else 0,
        'is_contact_hitter': 1 if profile == 'contact_hitter' else 0,
        'is_balanced_star': 1 if profile == 'balanced_star' else 0,
        'is_average_hitter': 1 if profile == 'average_hitter' else 0
    }


def calculate_levels_per_year(row):
    """
    Promotion speed: levels achieved per year in minors.

    Fast risers: 1.5+ levels/year
    Grinders: <0.5 levels/year
    """
    # Approximate years in minors from age
    age = row.get('avg_age')
    highest_level = row.get('highest_level')

    if age is None or highest_level is None:
        return 0.5  # Default average

    # Assume started at 18-20
    years_in_minors = max(age - 19, 1)

    return highest_level / years_in_minors


def has_elite_tool(row):
    """Binary: Does prospect have ANY 60+ tool?"""
    tools = [
        row.get('hit_future', 0),
        row.get('game_power_future', 0),
        row.get('raw_power_future', 0),
        row.get('speed_future', 0),
        row.get('fielding_future', 0)
    ]
    return 1 if any(t >= 60 for t in tools) else 0


def calculate_tool_variance(row):
    """
    Variance in tool grades.

    High variance: Extreme strengths/weaknesses
    Low variance: Well-rounded player
    """
    tools = [
        row.get('hit_future', 50),
        row.get('game_power_future', 50),
        row.get('speed_future', 50),
        row.get('fielding_future', 50)
    ]
    return np.var(tools)


async def get_enhanced_hitter_features(conn, data_year: int, split_name: str):
    """
    Extract ENHANCED features for hitter prospects.

    Includes all original features PLUS 13 new derived features.
    """

    print(f"\nExtracting ENHANCED hitter features for {split_name} ({data_year})...")

    # Start with original query (modified to get more raw data)
    query = """
    WITH prior_season_stats AS (
        SELECT
            p.id as prospect_id,
            p.mlb_player_id,
            p.birth_date,

            -- Aggregate prior season stats
            SUM(gl.plate_appearances) as total_pa,
            SUM(gl.at_bats) as total_ab,
            SUM(gl.hits) as total_hits,
            SUM(gl.doubles) as total_doubles,
            SUM(gl.triples) as total_triples,
            SUM(gl.home_runs) as total_hr,
            SUM(gl.walks) as total_bb,
            SUM(gl.strikeouts) as total_k,
            SUM(gl.stolen_bases) as total_sb,
            SUM(gl.caught_stealing) as total_cs,

            -- Weighted averages
            CASE WHEN SUM(gl.plate_appearances) > 0
                THEN SUM(gl.on_base_pct * gl.plate_appearances) / SUM(gl.plate_appearances)
                ELSE NULL END as avg_obp,
            CASE WHEN SUM(gl.plate_appearances) > 0
                THEN SUM(gl.slugging_pct * gl.plate_appearances) / SUM(gl.plate_appearances)
                ELSE NULL END as avg_slg,
            CASE WHEN SUM(gl.plate_appearances) > 0
                THEN SUM(gl.ops * gl.plate_appearances) / SUM(gl.plate_appearances)
                ELSE NULL END as avg_ops,

            -- Level distribution
            MAX(CASE WHEN gl.level = 'AAA' THEN 1 ELSE 0 END) as played_aaa,
            MAX(CASE WHEN gl.level = 'AA' THEN 1 ELSE 0 END) as played_aa,
            MAX(CASE WHEN gl.level = 'A+' THEN 1 ELSE 0 END) as played_a_plus,

            -- Best level achieved
            MAX(CASE
                WHEN gl.level = 'AAA' THEN 5
                WHEN gl.level = 'AA' THEN 4
                WHEN gl.level = 'A+' THEN 3
                WHEN gl.level = 'A' THEN 2
                ELSE 1
            END) as highest_level,

            -- Age at season
            CASE WHEN p.birth_date IS NOT NULL
                THEN EXTRACT(YEAR FROM AGE(TO_DATE(($1 - 1)::text || '-07-01', 'YYYY-MM-DD'), p.birth_date))
                ELSE NULL END as avg_age

        FROM prospects p
        LEFT JOIN milb_game_logs gl
            ON p.mlb_player_id = gl.mlb_player_id::varchar
            AND gl.season = $1 - 1
        WHERE p.id IN (
            SELECT prospect_id FROM mlb_expectation_labels WHERE data_year = $1
        )
        GROUP BY p.id, p.mlb_player_id, p.birth_date
    ),
    year_over_year_changes AS (
        SELECT
            fg_curr.fangraphs_player_id,

            -- FV trajectory
            fg_curr.fv - COALESCE(fg_prev.fv, fg_curr.fv) as fv_change_1yr,

            -- Tool grade changes
            fg_curr.hit_future - COALESCE(fg_prev.hit_future, fg_curr.hit_future) as hit_change,
            fg_curr.game_power_future - COALESCE(fg_prev.game_power_future, fg_curr.game_power_future) as power_change,
            fg_curr.speed_future - COALESCE(fg_prev.speed_future, fg_curr.speed_future) as speed_change

        FROM fangraphs_hitter_grades fg_curr
        LEFT JOIN fangraphs_hitter_grades fg_prev
            ON fg_curr.fangraphs_player_id = fg_prev.fangraphs_player_id
            AND fg_prev.data_year = fg_curr.data_year - 1
        WHERE fg_curr.data_year = $1
    )
    SELECT
        -- IDs
        l.prospect_id,
        l.data_year,
        p.name,
        p.position,
        p.fg_player_id as fangraphs_id,

        -- TARGET VARIABLE
        l.mlb_expectation_numeric as target,
        l.mlb_expectation as target_label,
        l.fv as fangraphs_fv,

        -- FANGRAPHS TOOL GRADES (Future values)
        fg.hit_future,
        fg.game_power_future,
        fg.raw_power_future,
        fg.speed_future,
        fg.fielding_future,
        fg.hard_hit_pct,

        -- Current vs Future gap
        fg.hit_future - fg.hit_current as hit_upside,
        fg.game_power_future - fg.game_power_current as power_upside,
        fg.speed_future - fg.speed_current as speed_upside,
        fg.fielding_future - fg.fielding_current as fielding_upside,

        -- PHYSICAL ATTRIBUTES
        phys.frame_grade,
        phys.athleticism_grade,
        phys.arm_grade,
        CASE phys.levers
            WHEN 'Short' THEN 1
            WHEN 'Med' THEN 2
            WHEN 'Long' THEN 3
            ELSE 2 END as levers_encoded,

        -- PRIOR SEASON PERFORMANCE
        pss.total_pa,
        pss.total_ab,
        pss.total_hr,
        pss.total_sb,
        pss.avg_obp,
        pss.avg_slg,
        pss.avg_ops,
        CASE WHEN pss.total_ab > 0
            THEN pss.total_hits::float / pss.total_ab
            ELSE NULL END as batting_avg,

        -- Derived stats
        CASE WHEN pss.total_ab > 0
            THEN (pss.total_doubles + 2*pss.total_triples + 3*pss.total_hr)::float / pss.total_ab
            ELSE NULL END as isolated_power,
        CASE WHEN pss.total_k > 0
            THEN pss.total_bb::float / pss.total_k
            ELSE NULL END as bb_k_ratio,
        CASE WHEN pss.total_pa > 0
            THEN pss.total_k::float / pss.total_pa
            ELSE NULL END as k_rate,
        CASE WHEN pss.total_pa > 0
            THEN pss.total_bb::float / pss.total_pa
            ELSE NULL END as bb_rate,

        -- Traditional Power-Speed Number
        CASE WHEN pss.total_hr + pss.total_sb > 0
            THEN (2 * pss.total_hr * pss.total_sb)::float / (pss.total_hr + pss.total_sb)
            ELSE 0 END as power_speed_number,

        -- Level context
        pss.played_aaa,
        pss.played_aa,
        pss.played_a_plus,
        pss.highest_level,
        pss.avg_age,

        -- YEAR-OVER-YEAR CHANGES
        yoy.fv_change_1yr,
        yoy.hit_change,
        yoy.power_change,
        yoy.speed_change

    FROM mlb_expectation_labels l
    JOIN prospects p ON l.prospect_id = p.id
    JOIN fangraphs_hitter_grades fg
        ON p.fg_player_id = fg.fangraphs_player_id
        AND fg.data_year = l.data_year
    LEFT JOIN fangraphs_physical_attributes phys
        ON p.fg_player_id = phys.fangraphs_player_id
        AND phys.data_year = l.data_year
    LEFT JOIN prior_season_stats pss ON l.prospect_id = pss.prospect_id
    LEFT JOIN year_over_year_changes yoy ON p.fg_player_id = yoy.fangraphs_player_id
    WHERE l.data_year = $1
    ORDER BY l.fv DESC, p.name
    """

    rows = await conn.fetch(query, data_year)
    df = pd.DataFrame([dict(r) for r in rows])

    print(f"  [OK] Extracted {len(df):,} base features")

    # Add ENHANCED derived features
    print(f"  [+] Adding enhanced derived features...")

    df['plus_tool_count'] = df.apply(calculate_plus_tool_count, axis=1)
    df['offensive_ceiling'] = df.apply(calculate_offensive_ceiling, axis=1)
    df['defensive_floor'] = df.apply(calculate_defensive_floor, axis=1)
    df['hit_power_ratio'] = df.apply(calculate_hit_power_ratio, axis=1)
    df['power_speed_number_v2'] = df.apply(calculate_power_speed_number_v2, axis=1)
    df['age_relative_ops'] = df.apply(calculate_age_relative_ops, axis=1)
    df['levels_per_year'] = df.apply(calculate_levels_per_year, axis=1)
    df['has_elite_tool'] = df.apply(has_elite_tool, axis=1)
    df['tool_variance'] = df.apply(calculate_tool_variance, axis=1)

    # Contact profile (one-hot)
    contact_profiles = df.apply(determine_contact_profile, axis=1, result_type='expand')
    df = pd.concat([df, contact_profiles], axis=1)

    print(f"  [OK] Added 13 enhanced features")
    print(f"  [OK] Total features: {len([c for c in df.columns if c not in ['prospect_id', 'data_year', 'name', 'position', 'fangraphs_id', 'target', 'target_label', 'fangraphs_fv']])}")
    print(f"       Class distribution: All-Star={sum(df['target']==3)}, Regular={sum(df['target']==2)}, Part-Time={sum(df['target']==1)}, Bench={sum(df['target']==0)}")

    return df


async def main():
    print("=" * 80)
    print("ENHANCED HITTER FEATURE EXTRACTION")
    print("=" * 80)
    print("\nNew Features Added:")
    print("  1. plus_tool_count - Count of 55+ tools")
    print("  2. offensive_ceiling - Max(hit, power)")
    print("  3. defensive_floor - Min(fielding, speed)")
    print("  4. hit_power_ratio - Contact vs power profile")
    print("  5. power_speed_number_v2 - Enhanced PSN")
    print("  6. age_relative_ops - Performance vs baseline")
    print("  7. levels_per_year - Promotion speed")
    print("  8. has_elite_tool - ANY 60+ tool?")
    print("  9. tool_variance - Tool grade variance")
    print("  10-13. Contact profile (one-hot: slugger/contact/balanced/average)")

    conn = await asyncpg.connect(DATABASE_URL)
    print("\n[OK] Connected to database")

    # Extract enhanced features for all splits
    splits = {
        'train': [2022, 2023],
        'val': [2024],
        'test': [2025]
    }

    for split_name, years in splits.items():
        print(f"\n{'='*80}")
        print(f"CREATING ENHANCED {split_name.upper()} DATASET")
        print(f"Years: {years}")
        print("=" * 80)

        all_data = []

        for year in years:
            df = await get_enhanced_hitter_features(conn, year, split_name)
            all_data.append(df)

        # Combine years
        combined = pd.concat(all_data, ignore_index=True)

        # Save to CSV
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"ml_data_hitters_enhanced_{split_name}_{timestamp}.csv"
        combined.to_csv(filename, index=False)

        print(f"\n[OK] Saved: {filename}")
        print(f"     Samples: {len(combined):,}")
        print(f"     Features: {len(combined.columns)}")
        print(f"     Enhanced features: 13")

    await conn.close()
    print("\n[OK] Database connection closed")

    print("\n" + "=" * 80)
    print("ENHANCED FEATURE EXTRACTION COMPLETE")
    print("=" * 80)
    print("\nNext Steps:")
    print("  1. Train baseline RF model with enhanced features")
    print("  2. Compare F1 to original (0.684)")
    print("  3. Expected improvement: +0.03-0.05 F1 (0.71-0.73)")
    print("\nCommand:")
    print("  python train_baseline_model_v2.py --player-type hitters --enhanced")


if __name__ == "__main__":
    asyncio.run(main())
