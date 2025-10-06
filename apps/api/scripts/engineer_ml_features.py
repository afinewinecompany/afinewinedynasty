#!/usr/bin/env python3
"""
ML Feature Engineering Pipeline
================================
Transforms raw prospect data into ML-ready features.

Feature Categories:
1. Bio Features (~10) - Age, draft position, physical attributes
2. Scouting Features (~25) - Tool grades, future value, risk
3. MiLB Performance Features (~40) - Aggregated stats by level
4. MiLB Progression Features (~20) - Improvement over time
5. MiLB Consistency Features (~15) - Variance, streaks
6. Derived Features (~10) - Tool grade vs performance alignment

Total: ~120 features

Usage:
    python engineer_ml_features.py --year 2024
"""

import sys
import os
import argparse
from datetime import datetime
from typing import Dict, List, Optional
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import get_db_sync
from sqlalchemy import text
import numpy as np


class MLFeatureEngineer:
    """Engineer ML features from raw prospect data."""

    def __init__(self, as_of_year: int):
        self.as_of_year = as_of_year
        self.feature_version = "v1.0"

    def engineer_features_for_prospect(self, prospect_id: int, db) -> Optional[Dict]:
        """Engineer all features for a single prospect."""

        features = {}

        # Get prospect data
        prospect = self.get_prospect_data(prospect_id, db)
        if not prospect:
            return None

        # 1. Bio Features
        bio_features = self.engineer_bio_features(prospect, db)
        features.update(bio_features)

        # 2. Scouting Features
        scouting_features = self.engineer_scouting_features(prospect_id, db)
        features.update(scouting_features)

        # 3. MiLB Performance Features
        milb_features = self.engineer_milb_performance_features(prospect_id, db)
        features.update(milb_features)

        # 4. MiLB Progression Features
        progression_features = self.engineer_progression_features(prospect_id, db)
        features.update(progression_features)

        # 5. MiLB Consistency Features
        consistency_features = self.engineer_consistency_features(prospect_id, db)
        features.update(consistency_features)

        # 6. Derived Features
        derived_features = self.engineer_derived_features(prospect, scouting_features, milb_features)
        features.update(derived_features)

        return features

    def get_prospect_data(self, prospect_id: int, db) -> Optional[Dict]:
        """Get prospect core data."""
        query = text("""
            SELECT id, name, position, bats, throws,
                   height_inches, weight_lbs, birth_date,
                   draft_year, draft_round, draft_pick,
                   current_organization, current_level
            FROM prospects
            WHERE id = :prospect_id
        """)

        result = db.execute(query, {'prospect_id': prospect_id})
        row = result.fetchone()

        if not row:
            return None

        return {
            'id': row[0],
            'name': row[1],
            'position': row[2],
            'bats': row[3],
            'throws': row[4],
            'height_inches': row[5],
            'weight_lbs': row[6],
            'birth_date': row[7],
            'draft_year': row[8],
            'draft_round': row[9],
            'draft_pick': row[10],
            'current_organization': row[11],
            'current_level': row[12],
        }

    def engineer_bio_features(self, prospect: Dict, db) -> Dict:
        """Engineer biographical features."""
        features = {}

        # Age at as_of_year
        if prospect['birth_date']:
            age = self.as_of_year - prospect['birth_date'].year
            features['age'] = age
            features['age_squared'] = age ** 2  # Non-linear age effect
        else:
            features['age'] = None
            features['age_squared'] = None

        # Physical attributes
        features['height_inches'] = prospect['height_inches']
        features['weight_lbs'] = prospect['weight_lbs']

        # BMI if both available
        if prospect['height_inches'] and prospect['weight_lbs']:
            height_m = prospect['height_inches'] * 0.0254
            weight_kg = prospect['weight_lbs'] * 0.453592
            features['bmi'] = weight_kg / (height_m ** 2)
        else:
            features['bmi'] = None

        # Draft information
        features['draft_year'] = prospect['draft_year']
        features['draft_round'] = prospect['draft_round']
        features['draft_pick'] = prospect['draft_pick']

        # Overall draft position
        if prospect['draft_round'] and prospect['draft_pick']:
            features['draft_overall_pick'] = (prospect['draft_round'] - 1) * 40 + prospect['draft_pick']
        else:
            features['draft_overall_pick'] = None

        # Years since draft
        if prospect['draft_year']:
            features['years_since_draft'] = self.as_of_year - prospect['draft_year']
        else:
            features['years_since_draft'] = None

        # Position encoding (one-hot)
        position = prospect['position']
        features['is_pitcher'] = 1 if position in ['P', 'SP', 'RP', 'RHP', 'LHP'] else 0
        features['is_catcher'] = 1 if position == 'C' else 0
        features['is_infielder'] = 1 if position in ['1B', '2B', '3B', 'SS', 'IF'] else 0
        features['is_outfielder'] = 1 if position in ['LF', 'CF', 'RF', 'OF'] else 0

        return features

    def engineer_scouting_features(self, prospect_id: int, db) -> Dict:
        """Engineer scouting-based features."""
        # Get most recent scouting report
        query = text("""
            SELECT future_value, risk_level, eta_year,
                   hit_present, power_present, raw_power_present, speed_present, field_present, arm_present,
                   hit_future, power_future, raw_power_future, speed_future, field_future, arm_future,
                   fastball_grade, slider_grade, curveball_grade, changeup_grade, control_grade, command_grade,
                   rank_overall
            FROM scouting_grades
            WHERE prospect_id = :prospect_id
            ORDER BY ranking_year DESC, date_recorded DESC
            LIMIT 1
        """)

        result = db.execute(query, {'prospect_id': prospect_id})
        row = result.fetchone()

        features = {}

        if not row:
            # No scouting data - fill with nulls
            return {f'scout_{i}': None for i in range(25)}

        # Future Value & Risk
        features['scout_future_value'] = row[0]
        features['scout_risk_level'] = self._encode_risk(row[1])
        features['scout_eta_year'] = row[2]

        # Present tool grades (hitter)
        features['scout_hit_present'] = row[3]
        features['scout_power_present'] = row[4]
        features['scout_raw_power_present'] = row[5]
        features['scout_speed_present'] = row[6]
        features['scout_field_present'] = row[7]
        features['scout_arm_present'] = row[8]

        # Future tool grades (hitter)
        features['scout_hit_future'] = row[9]
        features['scout_power_future'] = row[10]
        features['scout_raw_power_future'] = row[11]
        features['scout_speed_future'] = row[12]
        features['scout_field_future'] = row[13]
        features['scout_arm_future'] = row[14]

        # Pitcher grades
        features['scout_fastball'] = row[15]
        features['scout_slider'] = row[16]
        features['scout_curveball'] = row[17]
        features['scout_changeup'] = row[18]
        features['scout_control'] = row[19]
        features['scout_command'] = row[20]

        # Overall rank
        features['scout_rank_overall'] = row[21]

        # Derived scouting features
        # Average present tools (hitters)
        present_tools = [row[3], row[4], row[6], row[7], row[8]]  # Hit, Power, Speed, Field, Arm
        present_tools = [t for t in present_tools if t is not None]
        features['scout_avg_present_tools'] = np.mean(present_tools) if present_tools else None

        # Average future tools (hitters)
        future_tools = [row[9], row[10], row[12], row[13], row[14]]
        future_tools = [t for t in future_tools if t is not None]
        features['scout_avg_future_tools'] = np.mean(future_tools) if future_tools else None

        # Tool improvement (future - present)
        if features['scout_avg_future_tools'] and features['scout_avg_present_tools']:
            features['scout_tool_improvement'] = features['scout_avg_future_tools'] - features['scout_avg_present_tools']
        else:
            features['scout_tool_improvement'] = None

        return features

    def engineer_milb_performance_features(self, prospect_id: int, db) -> Dict:
        """Engineer MiLB performance features."""
        # Get game logs
        query = text("""
            SELECT level, season,
                   SUM(plate_appearances) as pa, SUM(at_bats) as ab,
                   SUM(hits) as h, SUM(doubles) as doubles, SUM(triples) as triples, SUM(home_runs) as hr,
                   SUM(walks) as bb, SUM(strikeouts) as so, SUM(stolen_bases) as sb,
                   SUM(runs) as r, SUM(rbi) as rbi
            FROM milb_game_logs
            WHERE prospect_id = :prospect_id
            AND season <= :as_of_year
            GROUP BY level, season
            ORDER BY season DESC, level DESC
        """)

        result = db.execute(query, {'prospect_id': prospect_id, 'as_of_year': self.as_of_year})
        rows = result.fetchall()

        features = {}

        if not rows:
            # No MiLB data
            return {f'milb_{i}': None for i in range(40)}

        # Aggregate across all levels (filtering None values)
        total_pa = sum(row[2] for row in rows if row[2] is not None)
        total_ab = sum(row[3] for row in rows if row[3] is not None)
        total_h = sum(row[4] for row in rows if row[4] is not None)
        total_2b = sum(row[5] for row in rows if row[5] is not None)
        total_3b = sum(row[6] for row in rows if row[6] is not None)
        total_hr = sum(row[7] for row in rows if row[7] is not None)
        total_bb = sum(row[8] for row in rows if row[8] is not None)
        total_so = sum(row[9] for row in rows if row[9] is not None)
        total_sb = sum(row[10] for row in rows if row[10] is not None)

        # Overall stats
        features['milb_total_pa'] = total_pa
        features['milb_avg'] = total_h / total_ab if total_ab > 0 else None
        features['milb_obp'] = (total_h + total_bb) / total_pa if total_pa > 0 else None

        total_bases = total_h + total_2b + (2 * total_3b) + (3 * total_hr)
        features['milb_slg'] = total_bases / total_ab if total_ab > 0 else None
        features['milb_ops'] = (features['milb_obp'] or 0) + (features['milb_slg'] or 0) if features['milb_obp'] and features['milb_slg'] else None

        features['milb_bb_rate'] = total_bb / total_pa if total_pa > 0 else None
        features['milb_k_rate'] = total_so / total_pa if total_pa > 0 else None
        features['milb_bb_k_ratio'] = total_bb / total_so if total_so > 0 else None
        features['milb_iso'] = features['milb_slg'] - features['milb_avg'] if features['milb_slg'] and features['milb_avg'] else None
        features['milb_hr_rate'] = total_hr / total_pa if total_pa > 0 else None
        features['milb_sb_rate'] = total_sb / total_pa if total_pa > 0 else None

        # Performance by level (most recent at each level)
        level_stats = {}
        for row in rows:
            level = row[0]
            if level not in level_stats:
                level_stats[level] = row

        # AAA performance
        if 'AAA' in level_stats:
            aaa = level_stats['AAA']
            features['milb_aaa_pa'] = aaa[2]
            features['milb_aaa_avg'] = aaa[4] / aaa[3] if aaa[3] > 0 else None
        else:
            features['milb_aaa_pa'] = 0
            features['milb_aaa_avg'] = None

        # AA performance
        if 'AA' in level_stats:
            aa = level_stats['AA']
            features['milb_aa_pa'] = aa[2]
            features['milb_aa_avg'] = aa[4] / aa[3] if aa[3] > 0 else None
        else:
            features['milb_aa_pa'] = 0
            features['milb_aa_avg'] = None

        # A+ performance
        if 'A+' in level_stats:
            a_plus = level_stats['A+']
            features['milb_a_plus_pa'] = a_plus[2]
            features['milb_a_plus_avg'] = a_plus[4] / a_plus[3] if a_plus[3] > 0 else None
        else:
            features['milb_a_plus_pa'] = 0
            features['milb_a_plus_avg'] = None

        # Highest level reached
        level_hierarchy = {'AAA': 4, 'AA': 3, 'A+': 2, 'A': 1, 'Rookie': 0, 'Complex': 0}
        highest_level = max((level_hierarchy.get(row[0], 0) for row in rows), default=0)
        features['milb_highest_level'] = highest_level

        # Number of levels played
        features['milb_num_levels'] = len(level_stats)

        # Experience (seasons played)
        seasons_played = len(set(row[1] for row in rows))
        features['milb_seasons_played'] = seasons_played

        return features

    def engineer_progression_features(self, prospect_id: int, db) -> Dict:
        """Engineer progression/improvement features."""
        features = {}

        # Get season-by-season stats
        query = text("""
            SELECT season,
                   SUM(plate_appearances) as pa, SUM(at_bats) as ab, SUM(hits) as h,
                   SUM(walks) as bb, SUM(strikeouts) as so
            FROM milb_game_logs
            WHERE prospect_id = :prospect_id
            AND season <= :as_of_year
            GROUP BY season
            HAVING SUM(plate_appearances) >= 50
            ORDER BY season
        """)

        result = db.execute(query, {'prospect_id': prospect_id, 'as_of_year': self.as_of_year})
        rows = result.fetchall()

        if len(rows) < 2:
            # Not enough data
            return {f'prog_{i}': None for i in range(20)}

        # Calculate year-over-year improvements
        avgs = []
        obps = []
        k_rates = []
        bb_rates = []

        for row in rows:
            pa, ab, h, bb, so = row[1], row[2], row[3], row[4], row[5]
            avg = h / ab if ab > 0 else None
            obp = (h + bb) / pa if pa > 0 else None
            k_rate = so / pa if pa > 0 else None
            bb_rate = bb / pa if pa > 0 else None

            if avg: avgs.append(avg)
            if obp: obps.append(obp)
            if k_rate: k_rates.append(k_rate)
            if bb_rate: bb_rates.append(bb_rate)

        # Year-over-year improvement (latest - first)
        features['prog_avg_improvement'] = avgs[-1] - avgs[0] if len(avgs) >= 2 else None
        features['prog_obp_improvement'] = obps[-1] - obps[0] if len(obps) >= 2 else None
        features['prog_k_rate_improvement'] = k_rates[0] - k_rates[-1] if len(k_rates) >= 2 else None  # Lower is better
        features['prog_bb_rate_improvement'] = bb_rates[-1] - bb_rates[0] if len(bb_rates) >= 2 else None

        # Trend (linear regression slope)
        if len(avgs) >= 3:
            x = np.arange(len(avgs))
            features['prog_avg_trend'] = np.polyfit(x, avgs, 1)[0]  # Slope
        else:
            features['prog_avg_trend'] = None

        # Best season performance
        features['prog_best_avg'] = max(avgs) if avgs else None
        features['prog_best_obp'] = max(obps) if obps else None
        features['prog_best_bb_rate'] = max(bb_rates) if bb_rates else None
        features['prog_best_k_rate'] = min(k_rates) if k_rates else None

        # Most recent season performance
        features['prog_recent_avg'] = avgs[-1] if avgs else None
        features['prog_recent_obp'] = obps[-1] if obps else None
        features['prog_recent_k_rate'] = k_rates[-1] if k_rates else None
        features['prog_recent_bb_rate'] = bb_rates[-1] if bb_rates else None

        return features

    def engineer_consistency_features(self, prospect_id: int, db) -> Dict:
        """Engineer consistency/variance features."""
        features = {}

        # Get game-by-game stats (last 50 games)
        query = text("""
            SELECT batting_avg, on_base_pct, slugging_pct
            FROM milb_game_logs
            WHERE prospect_id = :prospect_id
            AND season <= :as_of_year
            AND plate_appearances > 0
            ORDER BY game_date DESC
            LIMIT 50
        """)

        result = db.execute(query, {'prospect_id': prospect_id, 'as_of_year': self.as_of_year})
        rows = result.fetchall()

        if len(rows) < 10:
            return {f'cons_{i}': None for i in range(15)}

        avgs = [row[0] for row in rows if row[0] is not None]
        obps = [row[1] for row in rows if row[1] is not None]
        slgs = [row[2] for row in rows if row[2] is not None]

        # Variance
        features['cons_avg_std'] = np.std(avgs) if len(avgs) >= 10 else None
        features['cons_obp_std'] = np.std(obps) if len(obps) >= 10 else None
        features['cons_slg_std'] = np.std(slgs) if len(slgs) >= 10 else None

        # Coefficient of variation (std / mean)
        if avgs and np.mean(avgs) > 0:
            features['cons_avg_cv'] = np.std(avgs) / np.mean(avgs)
        else:
            features['cons_avg_cv'] = None

        # Hot/cold streaks (number of games above/below mean)
        if avgs:
            mean_avg = np.mean(avgs)
            hot_games = sum(1 for a in avgs if a > mean_avg)
            features['cons_hot_game_pct'] = hot_games / len(avgs)
        else:
            features['cons_hot_game_pct'] = None

        return features

    def engineer_derived_features(self, prospect: Dict, scouting: Dict, milb: Dict) -> Dict:
        """Engineer derived/interaction features."""
        features = {}

        # Tool grade vs actual performance alignment
        if scouting.get('scout_hit_future') and milb.get('milb_avg'):
            # Expected AVG based on hit tool (rough mapping: 50 = .250, 60 = .300, etc.)
            expected_avg = 0.100 + (scouting['scout_hit_future'] / 100)
            features['derived_hit_vs_performance'] = milb['milb_avg'] - expected_avg
        else:
            features['derived_hit_vs_performance'] = None

        if scouting.get('scout_power_future') and milb.get('milb_iso'):
            expected_iso = (scouting['scout_power_future'] - 40) / 200  # Rough mapping
            features['derived_power_vs_performance'] = milb['milb_iso'] - expected_iso
        else:
            features['derived_power_vs_performance'] = None

        # Age vs production efficiency
        if prospect.get('age') and milb.get('milb_ops'):
            features['derived_ops_per_age'] = milb['milb_ops'] / prospect['age']
        else:
            features['derived_ops_per_age'] = None

        # Draft pedigree vs performance
        if prospect.get('draft_overall_pick') and milb.get('milb_ops'):
            features['derived_ops_per_draft_pick'] = milb['milb_ops'] * prospect['draft_overall_pick']
        else:
            features['derived_ops_per_draft_pick'] = None

        return features

    def _encode_risk(self, risk_level: str) -> Optional[int]:
        """Encode risk level to numeric."""
        if not risk_level:
            return None

        risk_map = {
            'Safe': 1,
            'Low': 1,
            'Medium': 2,
            'Med': 2,
            'Moderate': 2,
            'High': 3,
            'Extreme': 4,
            'Very High': 4
        }

        return risk_map.get(risk_level, 2)  # Default to Medium

    def save_features(self, prospect_id: int, features: Dict, db):
        """Save engineered features to database."""
        # Group features by category
        bio_features = {k: v for k, v in features.items() if k.startswith(('age', 'height', 'weight', 'bmi', 'draft', 'years', 'is_'))}
        scouting_features = {k: v for k, v in features.items() if k.startswith('scout_')}
        milb_performance = {k: v for k, v in features.items() if k.startswith('milb_')}
        milb_progression = {k: v for k, v in features.items() if k.startswith('prog_')}
        milb_consistency = {k: v for k, v in features.items() if k.startswith('cons_')}
        derived_features = {k: v for k, v in features.items() if k.startswith('derived_')}

        # Check if features already exist
        check_sql = text("""
            SELECT id FROM ml_features
            WHERE prospect_id = :prospect_id
            AND as_of_year = :as_of_year
            AND feature_set_version = :version
        """)

        result = db.execute(check_sql, {
            'prospect_id': prospect_id,
            'as_of_year': self.as_of_year,
            'version': self.feature_version
        })

        existing = result.fetchone()

        if existing:
            # Update - construct SQL with inline JSON to avoid parameterization issues
            update_sql = f"""
                UPDATE ml_features SET
                    bio_features = '{json.dumps(bio_features)}'::jsonb,
                    scouting_features = '{json.dumps(scouting_features)}'::jsonb,
                    milb_performance = '{json.dumps(milb_performance)}'::jsonb,
                    milb_progression = '{json.dumps(milb_progression)}'::jsonb,
                    milb_consistency = '{json.dumps(milb_consistency)}'::jsonb,
                    derived_features = '{json.dumps(derived_features)}'::jsonb,
                    feature_vector = '{json.dumps(features)}'::jsonb,
                    updated_at = NOW()
                WHERE id = {existing[0]}
            """

            db.execute(text(update_sql))
        else:
            # Insert - construct SQL with inline JSON to avoid parameterization issues
            insert_sql = f"""
                INSERT INTO ml_features (
                    prospect_id, feature_set_version, as_of_year,
                    bio_features, scouting_features, milb_performance,
                    milb_progression, milb_consistency, derived_features,
                    feature_vector, created_at, updated_at
                ) VALUES (
                    {prospect_id}, '{self.feature_version}', {self.as_of_year},
                    '{json.dumps(bio_features)}'::jsonb,
                    '{json.dumps(scouting_features)}'::jsonb,
                    '{json.dumps(milb_performance)}'::jsonb,
                    '{json.dumps(milb_progression)}'::jsonb,
                    '{json.dumps(milb_consistency)}'::jsonb,
                    '{json.dumps(derived_features)}'::jsonb,
                    '{json.dumps(features)}'::jsonb,
                    NOW(), NOW()
                )
            """

            db.execute(text(insert_sql))

        db.commit()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Engineer ML features for prospects')
    parser.add_argument('--year', type=int, default=2024, help='As-of year for features')
    parser.add_argument('--prospect-id', type=int, help='Single prospect to process (for testing)')

    args = parser.parse_args()

    print("=" * 80)
    print("ML FEATURE ENGINEERING PIPELINE")
    print("=" * 80)
    print(f"As-of year: {args.year}")
    print(f"Feature version: v1.0")
    print("=" * 80)

    db = get_db_sync()
    engineer = MLFeatureEngineer(as_of_year=args.year)

    try:
        # Get prospects to process
        if args.prospect_id:
            prospect_ids = [args.prospect_id]
        else:
            query = text("SELECT id FROM prospects WHERE id IS NOT NULL ORDER BY id")
            result = db.execute(query)
            prospect_ids = [row[0] for row in result.fetchall()]

        print(f"\nProcessing {len(prospect_ids)} prospects...")

        stats = {
            'processed': 0,
            'features_created': 0,
            'errors': 0
        }

        for i, prospect_id in enumerate(prospect_ids, 1):
            if i % 50 == 0:
                print(f"  [{i}/{len(prospect_ids)}] Processed {stats['processed']} prospects...")

            try:
                features = engineer.engineer_features_for_prospect(prospect_id, db)

                if features:
                    engineer.save_features(prospect_id, features, db)
                    stats['features_created'] += 1

                stats['processed'] += 1

            except Exception as e:
                print(f"  Error processing prospect {prospect_id}: {e}")
                stats['errors'] += 1
                db.rollback()

        print("\n" + "=" * 80)
        print("FEATURE ENGINEERING SUMMARY")
        print("=" * 80)
        print(f"Prospects processed: {stats['processed']}")
        print(f"Feature sets created: {stats['features_created']}")
        print(f"Errors: {stats['errors']}")
        print("=" * 80)
        print("\n✅ Feature engineering complete!")

    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == '__main__':
    main()
