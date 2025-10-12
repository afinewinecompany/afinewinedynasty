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

        # 6. MLB Game Log Features (NEW)
        mlb_features = self.engineer_mlb_game_log_features(prospect_id, db)
        features.update(mlb_features)

        # 7. Derived Features
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

    def engineer_mlb_game_log_features(self, prospect_id: int, db) -> Dict:
        """
        Engineer features from MLB game log data.

        Creates ~55 features from MLB performance data:
        - Career aggregate stats (15 features)
        - Recent performance trends (10 features)
        - Consistency metrics (10 features)
        - Situational performance (10 features)
        - Performance progression (10 features)
        """
        features = {}

        # Get all MLB game logs for this prospect
        query = text("""
            SELECT
                game_date, season, is_home,
                games_played, at_bats, runs, hits, doubles, triples,
                home_runs, rbi, walks, strikeouts, stolen_bases,
                batting_avg, obp, slg, ops,
                innings_pitched, earned_runs, strikeouts_pitched, walks_allowed,
                era, whip
            FROM mlb_game_logs
            WHERE prospect_id = :prospect_id
            AND season <= :as_of_year
            ORDER BY game_date DESC
        """)

        result = db.execute(query, {'prospect_id': prospect_id, 'as_of_year': self.as_of_year})
        games = result.fetchall()

        # If no MLB experience, return null features
        if not games:
            feature_keys = [
                'mlb_career_games', 'mlb_career_ab', 'mlb_career_avg', 'mlb_career_obp',
                'mlb_career_slg', 'mlb_career_ops', 'mlb_career_hr', 'mlb_career_sb',
                'mlb_career_bb_rate', 'mlb_career_k_rate', 'mlb_career_iso',
                'mlb_career_babip', 'mlb_career_wrc_est', 'mlb_career_seasons',
                'mlb_has_experience',
                'mlb_l30_avg', 'mlb_l30_obp', 'mlb_l30_slg', 'mlb_l30_ops',
                'mlb_l30_hr', 'mlb_l30_bb_rate', 'mlb_l30_k_rate',
                'mlb_l7_avg', 'mlb_l7_obp', 'mlb_l7_ops',
                'mlb_trend_avg', 'mlb_trend_ops',
                'mlb_cons_avg_std', 'mlb_cons_ops_std', 'mlb_cons_avg_cv',
                'mlb_hot_game_pct', 'mlb_cold_game_pct', 'mlb_streak_variance',
                'mlb_multi_hit_pct', 'mlb_hitless_pct', 'mlb_hr_game_pct',
                'mlb_bb_rate_std', 'mlb_k_rate_std',
                'mlb_home_avg', 'mlb_away_avg', 'mlb_home_ops', 'mlb_away_ops',
                'mlb_home_away_split', 'mlb_recent_vs_career_avg',
                'mlb_recent_vs_career_ops', 'mlb_power_consistency',
                'mlb_days_since_debut', 'mlb_games_per_season',
                'mlb_peak_avg', 'mlb_peak_ops', 'mlb_slump_avg', 'mlb_slump_ops',
                'mlb_improvement_rate', 'mlb_volatility_score'
            ]
            return {k: None for k in feature_keys}

        # Parse games into arrays
        dates, seasons, is_homes = [], set(), []
        abs, hits, walks, strikeouts, hrs, sbs = [], [], [], [], [], []
        avgs, obps, slgs, opss = [], [], [], []

        for game in games:
            dates.append(game[0])
            seasons.add(game[1])
            is_homes.append(game[2])

            # Accumulate counting stats
            if game[4]:  # at_bats
                abs.append(game[4])
            if game[6]:  # hits
                hits.append(game[6])
            if game[11]: # walks
                walks.append(game[11])
            if game[12]: # strikeouts
                strikeouts.append(game[12])
            if game[9]:  # home_runs
                hrs.append(game[9])
            if game[13]: # stolen_bases
                sbs.append(game[13])

            # Rate stats
            if game[14]: # batting_avg
                avgs.append(game[14])
            if game[15]: # obp
                obps.append(game[15])
            if game[16]: # slg
                slgs.append(game[16])
            if game[17]: # ops
                opss.append(game[17])

        # === CAREER AGGREGATE FEATURES (15) ===
        features['mlb_has_experience'] = 1
        features['mlb_career_games'] = len(games)
        features['mlb_career_ab'] = sum(abs)
        features['mlb_career_avg'] = np.mean(avgs) if avgs else None
        features['mlb_career_obp'] = np.mean(obps) if obps else None
        features['mlb_career_slg'] = np.mean(slgs) if slgs else None
        features['mlb_career_ops'] = np.mean(opss) if opss else None
        features['mlb_career_hr'] = sum(hrs)
        features['mlb_career_sb'] = sum(sbs)

        total_pa = sum(abs) + sum(walks)
        features['mlb_career_bb_rate'] = sum(walks) / total_pa if total_pa > 0 else None
        features['mlb_career_k_rate'] = sum(strikeouts) / total_pa if total_pa > 0 else None

        # ISO = SLG - AVG
        if features['mlb_career_slg'] and features['mlb_career_avg']:
            features['mlb_career_iso'] = features['mlb_career_slg'] - features['mlb_career_avg']
        else:
            features['mlb_career_iso'] = None

        # BABIP estimate (hits - HR) / (AB - K - HR)
        denominator = sum(abs) - sum(strikeouts) - sum(hrs)
        if denominator > 0:
            features['mlb_career_babip'] = (sum(hits) - sum(hrs)) / denominator
        else:
            features['mlb_career_babip'] = None

        # wRC+ estimate (simple version)
        if features['mlb_career_ops']:
            features['mlb_career_wrc_est'] = (features['mlb_career_ops'] - 0.700) * 100
        else:
            features['mlb_career_wrc_est'] = None

        features['mlb_career_seasons'] = len(seasons)

        # === RECENT PERFORMANCE FEATURES (10) ===
        # Last 30 games
        recent_30 = games[:min(30, len(games))]
        if len(recent_30) >= 10:
            r30_avgs = [g[14] for g in recent_30 if g[14] is not None]
            r30_obps = [g[15] for g in recent_30 if g[15] is not None]
            r30_slgs = [g[16] for g in recent_30 if g[16] is not None]
            r30_opss = [g[17] for g in recent_30 if g[17] is not None]
            r30_hrs = [g[9] for g in recent_30 if g[9] is not None]
            r30_abs = [g[4] for g in recent_30 if g[4] is not None]
            r30_walks = [g[11] for g in recent_30 if g[11] is not None]
            r30_ks = [g[12] for g in recent_30 if g[12] is not None]

            features['mlb_l30_avg'] = np.mean(r30_avgs) if r30_avgs else None
            features['mlb_l30_obp'] = np.mean(r30_obps) if r30_obps else None
            features['mlb_l30_slg'] = np.mean(r30_slgs) if r30_slgs else None
            features['mlb_l30_ops'] = np.mean(r30_opss) if r30_opss else None
            features['mlb_l30_hr'] = sum(r30_hrs)

            r30_pa = sum(r30_abs) + sum(r30_walks)
            features['mlb_l30_bb_rate'] = sum(r30_walks) / r30_pa if r30_pa > 0 else None
            features['mlb_l30_k_rate'] = sum(r30_ks) / r30_pa if r30_pa > 0 else None
        else:
            features['mlb_l30_avg'] = None
            features['mlb_l30_obp'] = None
            features['mlb_l30_slg'] = None
            features['mlb_l30_ops'] = None
            features['mlb_l30_hr'] = None
            features['mlb_l30_bb_rate'] = None
            features['mlb_l30_k_rate'] = None

        # Last 7 games
        recent_7 = games[:min(7, len(games))]
        if len(recent_7) >= 5:
            r7_avgs = [g[14] for g in recent_7 if g[14] is not None]
            r7_obps = [g[15] for g in recent_7 if g[15] is not None]
            r7_opss = [g[17] for g in recent_7 if g[17] is not None]

            features['mlb_l7_avg'] = np.mean(r7_avgs) if r7_avgs else None
            features['mlb_l7_obp'] = np.mean(r7_obps) if r7_obps else None
            features['mlb_l7_ops'] = np.mean(r7_opss) if r7_opss else None
        else:
            features['mlb_l7_avg'] = None
            features['mlb_l7_obp'] = None
            features['mlb_l7_ops'] = None

        # Trend (last 30 vs first 30)
        if len(games) >= 60:
            first_30_avg = np.mean([g[14] for g in games[-30:] if g[14] is not None])
            last_30_avg = np.mean([g[14] for g in games[:30] if g[14] is not None])
            features['mlb_trend_avg'] = last_30_avg - first_30_avg if first_30_avg and last_30_avg else None

            first_30_ops = np.mean([g[17] for g in games[-30:] if g[17] is not None])
            last_30_ops = np.mean([g[17] for g in games[:30] if g[17] is not None])
            features['mlb_trend_ops'] = last_30_ops - first_30_ops if first_30_ops and last_30_ops else None
        else:
            features['mlb_trend_avg'] = None
            features['mlb_trend_ops'] = None

        # === CONSISTENCY FEATURES (10) ===
        if len(avgs) >= 20:
            features['mlb_cons_avg_std'] = np.std(avgs)
            features['mlb_cons_ops_std'] = np.std(opss) if opss else None
            features['mlb_cons_avg_cv'] = np.std(avgs) / np.mean(avgs) if np.mean(avgs) > 0 else None

            # Hot/cold games
            mean_avg = np.mean(avgs)
            hot_games = sum(1 for a in avgs if a > mean_avg)
            cold_games = sum(1 for a in avgs if a < mean_avg)
            features['mlb_hot_game_pct'] = hot_games / len(avgs)
            features['mlb_cold_game_pct'] = cold_games / len(avgs)
            features['mlb_streak_variance'] = np.var([1 if a > mean_avg else 0 for a in avgs])

            # Performance game types
            multi_hit_games = sum(1 for g in games if g[6] and g[6] >= 2)
            hitless_games = sum(1 for g in games if g[6] == 0 and g[4] and g[4] > 0)
            hr_games = sum(1 for g in games if g[9] and g[9] >= 1)

            features['mlb_multi_hit_pct'] = multi_hit_games / len(games)
            features['mlb_hitless_pct'] = hitless_games / len(games)
            features['mlb_hr_game_pct'] = hr_games / len(games)
        else:
            for key in ['mlb_cons_avg_std', 'mlb_cons_ops_std', 'mlb_cons_avg_cv',
                       'mlb_hot_game_pct', 'mlb_cold_game_pct', 'mlb_streak_variance',
                       'mlb_multi_hit_pct', 'mlb_hitless_pct', 'mlb_hr_game_pct']:
                features[key] = None

        # Plate discipline consistency
        if total_pa >= 100:
            game_bb_rates = []
            game_k_rates = []
            for g in games:
                g_pa = (g[4] or 0) + (g[11] or 0)
                if g_pa > 0:
                    game_bb_rates.append((g[11] or 0) / g_pa)
                    game_k_rates.append((g[12] or 0) / g_pa)

            features['mlb_bb_rate_std'] = np.std(game_bb_rates) if game_bb_rates else None
            features['mlb_k_rate_std'] = np.std(game_k_rates) if game_k_rates else None
        else:
            features['mlb_bb_rate_std'] = None
            features['mlb_k_rate_std'] = None

        # === SITUATIONAL PERFORMANCE (10) ===
        # Home vs Away splits
        home_games = [g for g in games if g[2] is True]
        away_games = [g for g in games if g[2] is False]

        if len(home_games) >= 10:
            home_avgs = [g[14] for g in home_games if g[14] is not None]
            home_opss = [g[17] for g in home_games if g[17] is not None]
            features['mlb_home_avg'] = np.mean(home_avgs) if home_avgs else None
            features['mlb_home_ops'] = np.mean(home_opss) if home_opss else None
        else:
            features['mlb_home_avg'] = None
            features['mlb_home_ops'] = None

        if len(away_games) >= 10:
            away_avgs = [g[14] for g in away_games if g[14] is not None]
            away_opss = [g[17] for g in away_games if g[17] is not None]
            features['mlb_away_avg'] = np.mean(away_avgs) if away_avgs else None
            features['mlb_away_ops'] = np.mean(away_opss) if away_opss else None
        else:
            features['mlb_away_avg'] = None
            features['mlb_away_ops'] = None

        # Home/Away differential
        if features['mlb_home_ops'] and features['mlb_away_ops']:
            features['mlb_home_away_split'] = features['mlb_home_ops'] - features['mlb_away_ops']
        else:
            features['mlb_home_away_split'] = None

        # Recent vs Career comparison
        if features['mlb_l30_avg'] and features['mlb_career_avg']:
            features['mlb_recent_vs_career_avg'] = features['mlb_l30_avg'] - features['mlb_career_avg']
        else:
            features['mlb_recent_vs_career_avg'] = None

        if features['mlb_l30_ops'] and features['mlb_career_ops']:
            features['mlb_recent_vs_career_ops'] = features['mlb_l30_ops'] - features['mlb_career_ops']
        else:
            features['mlb_recent_vs_career_ops'] = None

        # Power consistency (HR rate variance)
        if len(games) >= 50:
            hr_per_game = [g[9] or 0 for g in games]
            features['mlb_power_consistency'] = 1 - (np.std(hr_per_game) / (np.mean(hr_per_game) + 0.001))
        else:
            features['mlb_power_consistency'] = None

        # === PROGRESSION FEATURES (10) ===
        # Days since MLB debut
        if dates:
            debut_date = max(dates)  # Earliest game (list is DESC)
            days_since = (datetime.now().date() - debut_date).days
            features['mlb_days_since_debut'] = days_since
        else:
            features['mlb_days_since_debut'] = None

        # Games per season (experience rate)
        if features['mlb_career_seasons'] and features['mlb_career_seasons'] > 0:
            features['mlb_games_per_season'] = len(games) / features['mlb_career_seasons']
        else:
            features['mlb_games_per_season'] = None

        # Peak and slump performance
        if len(avgs) >= 20:
            # Rolling 10-game windows
            rolling_avgs = []
            rolling_opss = []
            for i in range(len(games) - 9):
                window_avgs = [g[14] for g in games[i:i+10] if g[14] is not None]
                window_opss = [g[17] for g in games[i:i+10] if g[17] is not None]
                if window_avgs:
                    rolling_avgs.append(np.mean(window_avgs))
                if window_opss:
                    rolling_opss.append(np.mean(window_opss))

            features['mlb_peak_avg'] = max(rolling_avgs) if rolling_avgs else None
            features['mlb_peak_ops'] = max(rolling_opss) if rolling_opss else None
            features['mlb_slump_avg'] = min(rolling_avgs) if rolling_avgs else None
            features['mlb_slump_ops'] = min(rolling_opss) if rolling_opss else None
        else:
            features['mlb_peak_avg'] = None
            features['mlb_peak_ops'] = None
            features['mlb_slump_avg'] = None
            features['mlb_slump_ops'] = None

        # Improvement rate (linear regression slope over time)
        if len(avgs) >= 30:
            x = np.arange(len(avgs))
            slope_avg = np.polyfit(x, avgs, 1)[0]
            features['mlb_improvement_rate'] = slope_avg
        else:
            features['mlb_improvement_rate'] = None

        # Volatility score (combines consistency metrics)
        if features['mlb_cons_avg_std'] and features['mlb_streak_variance'] is not None:
            features['mlb_volatility_score'] = (features['mlb_cons_avg_std'] * 10) + features['mlb_streak_variance']
        else:
            features['mlb_volatility_score'] = None

        return features

    def engineer_derived_features(self, prospect: Dict, scouting: Dict, milb: Dict) -> Dict:
        """
        Engineer derived/interaction features.

        CRITICAL: Age-to-level performance is heavily weighted for ML success.
        Younger players performing well at higher levels typically succeed in MLB.
        """
        features = {}

        # Tool grade vs actual performance alignment
        if scouting.get('scout_hit_future') and milb.get('milb_avg'):
            expected_avg = 0.100 + (scouting['scout_hit_future'] / 100)
            features['derived_hit_vs_performance'] = milb['milb_avg'] - expected_avg
        else:
            features['derived_hit_vs_performance'] = None

        if scouting.get('scout_power_future') and milb.get('milb_iso'):
            expected_iso = (scouting['scout_power_future'] - 40) / 200
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

        # === AGE-TO-LEVEL FEATURES (CRITICAL - TOP PREDICTOR) ===
        age = prospect.get('age')
        highest_level = milb.get('milb_highest_level')

        if age and highest_level is not None:
            # Age-to-level score (younger at higher level = better)
            features['derived_age_to_level_score'] = highest_level / age

            # Age vs typical age for level
            level_age_map = {0: 18.5, 1: 20.0, 2: 21.0, 3: 22.5, 4: 24.0}
            typical_age = level_age_map.get(highest_level)
            features['derived_age_vs_level'] = age - typical_age if typical_age else None

            # Age-adjusted performance at each level
            if milb.get('milb_aaa_ops'):
                features['derived_age_adj_aaa_ops'] = milb['milb_aaa_ops'] * (28 - age) / 4 if age < 28 else milb['milb_aaa_ops']
            else:
                features['derived_age_adj_aaa_ops'] = None

            if milb.get('milb_aa_ops'):
                features['derived_age_adj_aa_ops'] = milb['milb_aa_ops'] * (25 - age) / 3 if age < 25 else milb['milb_aa_ops']
            else:
                features['derived_age_adj_aa_ops'] = None

            if milb.get('milb_a_plus_ops'):
                features['derived_age_adj_a_plus_ops'] = milb['milb_a_plus_ops'] * (23 - age) / 3 if age < 23 else milb['milb_a_plus_ops']
            else:
                features['derived_age_adj_a_plus_ops'] = None

            # Aggressive promotion indicator
            if highest_level >= 4 and age <= 22:
                features['derived_aggressive_promotion'] = 1.0
            elif highest_level >= 3 and age <= 21:
                features['derived_aggressive_promotion'] = 0.8
            elif highest_level >= 2 and age <= 20:
                features['derived_aggressive_promotion'] = 0.6
            else:
                features['derived_aggressive_promotion'] = 0.0
        else:
            features['derived_age_to_level_score'] = None
            features['derived_age_vs_level'] = None
            features['derived_age_adj_aaa_ops'] = None
            features['derived_age_adj_aa_ops'] = None
            features['derived_age_adj_a_plus_ops'] = None
            features['derived_aggressive_promotion'] = None

        # Years to reach highest level
        if prospect.get('years_since_draft') and highest_level and highest_level >= 3:
            features['derived_years_to_highest_level'] = prospect['years_since_draft']
        else:
            features['derived_years_to_highest_level'] = None

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
