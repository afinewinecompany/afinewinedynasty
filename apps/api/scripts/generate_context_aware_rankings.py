"""
Generate prospect rankings using CONTEXT-AWARE ML MODEL.

Uses league, age, and position factors to generate fair, accurate prospect rankings.
Integrates the enhanced model from train_context_aware_predictor.py.
"""

import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text
from app.db.database import engine
import logging
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor
from typing import Dict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContextAwareRankingSystem:
    """Generate ML-based prospect rankings with context factors."""

    def __init__(self):
        self.models = {}
        self.feature_names = []

    async def load_milb_with_context(self) -> pd.DataFrame:
        """Load MiLB data with league and position context - 2024-2025 ONLY."""
        logger.info("Loading MiLB data WITH context factors (2024-2025 active prospects only)...")

        async with engine.begin() as conn:
            query = """
                SELECT
                    m.mlb_player_id,
                    m.level,
                    m.season,
                    p.position as primary_position,
                    p.name as full_name,
                    p.current_team,
                    p.birth_date,
                    EXTRACT(YEAR FROM MIN(m.game_date)) - EXTRACT(YEAR FROM p.birth_date) as age_at_level,
                    COUNT(*) as games_played,
                    SUM(m.plate_appearances) as total_pa,
                    SUM(m.at_bats) as total_ab,
                    SUM(m.hits) as total_hits,
                    SUM(m.doubles) as total_2b,
                    SUM(m.triples) as total_3b,
                    SUM(m.home_runs) as total_hr,
                    SUM(m.walks) as total_bb,
                    SUM(m.strikeouts) as total_so,
                    SUM(m.stolen_bases) as total_sb,
                    SUM(m.caught_stealing) as total_cs,
                    AVG(m.batting_avg) as avg_ba,
                    AVG(m.on_base_pct) as avg_obp,
                    AVG(m.slugging_pct) as avg_slg,
                    AVG(m.ops) as avg_ops,
                    -- League factors
                    lf.lg_ops,
                    lf.lg_iso,
                    lf.lg_bb_rate,
                    lf.lg_so_rate,
                    lf.lg_hr_rate,
                    lf.lg_avg_age,
                    -- Position factors
                    pf.pos_ops,
                    pf.pos_iso,
                    pf.pos_bb_rate,
                    pf.pos_so_rate
                FROM milb_game_logs m
                INNER JOIN prospects p ON m.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
                LEFT JOIN milb_league_factors lf ON m.season = lf.season AND m.level = lf.level
                LEFT JOIN milb_position_factors pf ON m.season = pf.season
                    AND m.level = pf.level
                    AND CASE
                        WHEN p.position = 'C' THEN 'C'
                        WHEN p.position IN ('SS', '2B', '3B', '1B') THEN 'IF'
                        WHEN p.position IN ('LF', 'CF', 'RF', 'OF') THEN 'OF'
                        WHEN p.position = 'DH' THEN 'DH'
                        ELSE 'TWP'
                    END = pf.position_group
                WHERE m.data_source = 'mlb_stats_api_gamelog'
                AND m.mlb_player_id IS NOT NULL
                AND p.birth_date IS NOT NULL
                AND (m.games_pitched IS NULL OR m.games_pitched = 0)
                AND m.season IN (2024, 2025)  -- ONLY 2024-2025 data
                GROUP BY m.mlb_player_id, m.level, m.season, p.birth_date, p.position,
                         p.name, p.current_team,
                         lf.lg_ops, lf.lg_iso, lf.lg_bb_rate, lf.lg_so_rate, lf.lg_hr_rate, lf.lg_avg_age,
                         pf.pos_ops, pf.pos_iso, pf.pos_bb_rate, pf.pos_so_rate
            """

            result = await conn.execute(text(query))
            rows = result.fetchall()

            df = pd.DataFrame(rows, columns=[
                'mlb_player_id', 'level', 'season', 'primary_position', 'full_name',
                'current_team', 'birth_date', 'age_at_level', 'games_played',
                'total_pa', 'total_ab', 'total_hits', 'total_2b', 'total_3b',
                'total_hr', 'total_bb', 'total_so', 'total_sb', 'total_cs',
                'avg_ba', 'avg_obp', 'avg_slg', 'avg_ops',
                'lg_ops', 'lg_iso', 'lg_bb_rate', 'lg_so_rate', 'lg_hr_rate', 'lg_avg_age',
                'pos_ops', 'pos_iso', 'pos_bb_rate', 'pos_so_rate'
            ])

        # Convert to numeric
        numeric_cols = df.columns.difference(['mlb_player_id', 'level', 'season', 'primary_position',
                                             'full_name', 'current_team', 'birth_date'])
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)

        logger.info(f"Loaded {len(df)} player-season-level records with context")
        return df

    def calculate_context_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate context-aware features."""

        # Basic rates
        df['bb_rate'] = np.where(df['total_pa'] > 0, df['total_bb'] / df['total_pa'] * 100, 0)
        df['so_rate'] = np.where(df['total_pa'] > 0, df['total_so'] / df['total_pa'] * 100, 0)
        df['hr_rate'] = np.where(df['total_pa'] > 0, df['total_hr'] / df['total_pa'] * 100, 0)
        df['iso'] = df['avg_slg'] - df['avg_ba']

        # League-relative features
        df['ops_vs_league'] = np.where(df['lg_ops'] > 0, df['avg_ops'] / df['lg_ops'], 1.0)
        df['iso_vs_league'] = np.where(df['lg_iso'] > 0, df['iso'] / df['lg_iso'], 1.0)
        df['bb_rate_vs_league'] = np.where(df['lg_bb_rate'] > 0, df['bb_rate'] / df['lg_bb_rate'], 1.0)
        df['so_rate_vs_league'] = np.where(df['lg_so_rate'] > 0, df['so_rate'] / df['lg_so_rate'], 1.0)

        # Age-relative features
        df['age_vs_league_avg'] = df['age_at_level'] - df['lg_avg_age']
        df['age_adj_ops'] = df['avg_ops'] * (1 + (df['age_vs_league_avg'] * -0.02))
        df['age_adj_iso'] = df['iso'] * (1 + (df['age_vs_league_avg'] * -0.02))

        # Position-relative features
        df['ops_vs_position'] = np.where(df['pos_ops'] > 0, df['avg_ops'] / df['pos_ops'], 1.0)
        df['iso_vs_position'] = np.where(df['pos_iso'] > 0, df['iso'] / df['pos_iso'], 1.0)

        # Comprehensive adjustment
        level_factor = df['ops_vs_league']
        age_factor = 1 + (df['age_vs_league_avg'] * -0.02)
        position_factor = np.where(df['pos_ops'] > 0, df['lg_ops'] / df['pos_ops'], 1.0)
        df['fully_adjusted_ops'] = df['avg_ops'] * level_factor * age_factor * position_factor

        # Prospect score
        df['prospect_age_score'] = np.where(
            df['age_vs_league_avg'] < -1.5, 2.0,
            np.where(df['age_vs_league_avg'] < 0, 1.5, 1.0)
        )
        df['prospect_value_score'] = df['prospect_age_score'] * ((df['ops_vs_league'] + df['ops_vs_position']) / 2)

        return df

    def aggregate_by_player(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate features by player (already filtered to 2024-2025 in SQL query)."""

        # Get player info (take from most recent season)
        player_info = df.sort_values('season', ascending=False).groupby('mlb_player_id').first()[
            ['full_name', 'current_team', 'primary_position', 'birth_date']
        ].reset_index()

        # Aggregate stats by level
        agg_dict = {
            'age_at_level': 'mean',
            'games_played': 'sum',
            'total_pa': 'sum',
            'total_ab': 'sum',
            'total_hits': 'sum',
            'total_hr': 'sum',
            'total_bb': 'sum',
            'total_so': 'sum',
            'avg_ops': 'mean',
            'iso': 'mean',
            'bb_rate': 'mean',
            'so_rate': 'mean',
            'ops_vs_league': 'mean',
            'iso_vs_league': 'mean',
            'age_vs_league_avg': 'mean',
            'age_adj_ops': 'mean',
            'ops_vs_position': 'mean',
            'fully_adjusted_ops': 'mean',
            'prospect_value_score': 'mean'
        }

        agg_features = df.groupby(['mlb_player_id', 'level']).agg(agg_dict).reset_index()

        # Pivot by level
        level_features = []
        for level in ['AAA', 'AA', 'A+', 'A']:
            level_df = agg_features[agg_features['level'] == level].copy()
            level_df = level_df.drop('level', axis=1)
            level_df.columns = [f'{col}_{level}' if col != 'mlb_player_id' else col
                               for col in level_df.columns]
            level_features.append(level_df)

        # Merge all levels
        player_features = level_features[0]
        for level_df in level_features[1:]:
            player_features = player_features.merge(level_df, on='mlb_player_id', how='outer')

        player_features = player_features.fillna(0)

        # Add summary features
        player_features['total_milb_pa'] = sum(
            player_features.get(f'total_pa_{level}', 0)
            for level in ['AAA', 'AA', 'A+', 'A']
        )

        # Highest level
        player_features['highest_level'] = 0
        player_features['highest_level_name'] = 'None'
        for i, level in enumerate(['A', 'A+', 'AA', 'AAA'], start=1):
            mask = player_features[f'total_pa_{level}'] > 0
            player_features.loc[mask, 'highest_level'] = i
            player_features.loc[mask, 'highest_level_name'] = level

        # Weighted scores (higher levels weighted more)
        player_features['weighted_prospect_score'] = (
            player_features.get('prospect_value_score_AAA', 0) * 4 +
            player_features.get('prospect_value_score_AA', 0) * 3 +
            player_features.get('prospect_value_score_A+', 0) * 2 +
            player_features.get('prospect_value_score_A', 0) * 1
        ) / 10

        # Merge player info
        player_features = player_features.merge(player_info, on='mlb_player_id', how='left')

        # Calculate current age
        current_date = datetime.now()
        player_features['current_age'] = (
            current_date - pd.to_datetime(player_features['birth_date'])
        ).dt.days / 365.25

        return player_features

    async def load_mlb_stats(self) -> pd.DataFrame:
        """Load MLB stats to identify prospects (exclude veterans with >130 AB)."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    mlb_player_id,
                    SUM(at_bats) as mlb_ab
                FROM mlb_game_logs
                GROUP BY mlb_player_id
            """))
            rows = result.fetchall()

        if not rows:
            return pd.DataFrame(columns=['mlb_player_id', 'mlb_ab'])

        df = pd.DataFrame(rows, columns=['mlb_player_id', 'mlb_ab'])
        df['mlb_ab'] = pd.to_numeric(df['mlb_ab'], errors='coerce').fillna(0)
        logger.info(f"Loaded MLB stats for {len(df)} players")
        return df

    async def load_training_targets(self) -> pd.DataFrame:
        """Load MLB performance for training."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    mlb_player_id,
                    AVG(ops) as mlb_avg_ops,
                    AVG(on_base_pct) as mlb_avg_obp,
                    AVG(slugging_pct) as mlb_avg_slg
                FROM mlb_game_logs
                WHERE mlb_player_id IS NOT NULL
                GROUP BY mlb_player_id
            """))
            rows = result.fetchall()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=['mlb_player_id', 'mlb_avg_ops', 'mlb_avg_obp', 'mlb_avg_slg'])
        for col in df.columns:
            if col != 'mlb_player_id':
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Calculate simple wRC+ proxy (OPS-based)
        df['mlb_wrc_plus'] = ((df['mlb_avg_ops'] - 0.700) / 0.003) + 100
        df['mlb_woba'] = df['mlb_avg_ops'] * 0.42  # Approximate conversion

        logger.info(f"Loaded training targets for {len(df)} players")
        return df

    def train_models(self, features: pd.DataFrame, targets: pd.DataFrame):
        """Train Random Forest models."""

        # Merge features with targets
        training_data = features.merge(targets, on='mlb_player_id', how='left')
        mlb_cols = [col for col in training_data.columns if col.startswith('mlb_')]
        training_data[mlb_cols] = training_data[mlb_cols].fillna(0)

        # Select features (context-aware)
        feature_cols = []
        for level in ['AAA', 'AA', 'A+', 'A']:
            feature_cols.extend([
                f'total_pa_{level}', f'total_hr_{level}', f'avg_ops_{level}',
                f'ops_vs_league_{level}', f'age_vs_league_avg_{level}',
                f'age_adj_ops_{level}', f'ops_vs_position_{level}',
                f'fully_adjusted_ops_{level}', f'prospect_value_score_{level}'
            ])

        feature_cols.extend([
            'total_milb_pa', 'highest_level', 'weighted_prospect_score', 'current_age'
        ])

        # Filter to existing columns
        feature_cols = [c for c in feature_cols if c in training_data.columns]

        X_train = training_data[feature_cols].fillna(0)
        self.feature_names = feature_cols

        target_metrics = ['mlb_wrc_plus', 'mlb_woba', 'mlb_avg_ops']

        for target in target_metrics:
            if target not in training_data.columns:
                continue

            logger.info(f"Training model for {target}...")

            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                min_samples_split=10,
                random_state=42,
                n_jobs=-1
            )

            model.fit(X_train, training_data[target])
            self.models[target] = model

            score = model.score(X_train, training_data[target])
            logger.info(f"  {target}: R² = {score:.3f}")

    async def generate_rankings(self) -> pd.DataFrame:
        """Generate context-aware prospect rankings."""

        # Load data with context
        milb_df = await self.load_milb_with_context()
        milb_features_calculated = self.calculate_context_features(milb_df)
        features = self.aggregate_by_player(milb_features_calculated)

        # Identify prospects (exclude veterans with MLB service time AND players >30 years old)
        mlb_stats = await self.load_mlb_stats()
        features = features.merge(mlb_stats, on='mlb_player_id', how='left')
        features['mlb_ab'] = features['mlb_ab'].fillna(0)

        # Filter criteria for true prospects:
        # 1. Less than 130 MLB at-bats (prospect threshold)
        # 2. Age <= 30 years old (no 35+ year old "prospects")
        # 3. At least 50 MiLB PAs (minimum sample size)
        prospects = features[
            (features['mlb_ab'] < 130) &
            (features['current_age'] <= 30) &
            (features['total_milb_pa'] >= 50)
        ].copy()

        logger.info(f"Identified {len(prospects)} true prospects")
        logger.info(f"  - Filtered out veterans with >=130 MLB AB")
        logger.info(f"  - Filtered out players >30 years old")
        logger.info(f"  - Required minimum 50 MiLB PAs")

        # Train models
        training_targets = await self.load_training_targets()
        self.train_models(features, training_targets)

        # Generate predictions
        X_prospects = prospects[self.feature_names].fillna(0)

        for target in self.models.keys():
            prospects[f'pred_{target}'] = self.models[target].predict(X_prospects)

        # Create composite score with AGE and CONTEXT PENALTY
        # Age penalty: older players get downweighted (29yo vs 22yo is massive)
        age_factor = np.maximum(0.1, 1.0 - ((prospects['current_age'] - 22) * 0.08))  # 22yo = 1.0, 30yo = 0.36

        # Context boost: high context score = young for level + performing well
        context_boost = 1.0 + (prospects['weighted_prospect_score'] * 0.3)  # Max ~1.6x boost

        # Base prediction score
        base_score = (
            prospects['pred_mlb_wrc_plus'] * 0.4 +
            prospects['pred_mlb_avg_ops'] * 100 * 0.3 +
            prospects['pred_mlb_woba'] * 200 * 0.3
        )

        # Final composite: base score × age penalty × context boost
        prospects['composite_score'] = base_score * age_factor * context_boost

        logger.info(f"Applied age penalty (22yo=1.0, 30yo=0.36) and context boost (max 1.6x)")

        # Sort and rank
        prospects = prospects.sort_values('composite_score', ascending=False)
        prospects['rank'] = range(1, len(prospects) + 1)

        logger.info(f"Generated context-aware rankings for {len(prospects)} prospects")
        return prospects

    async def save_rankings(self, rankings: pd.DataFrame):
        """Save rankings to database."""
        async with engine.begin() as conn:
            # Drop and recreate table
            await conn.execute(text("DROP TABLE IF EXISTS prospect_rankings_context_aware"))

            await conn.execute(text("""
                CREATE TABLE prospect_rankings_context_aware (
                    id SERIAL PRIMARY KEY,
                    mlb_player_id INTEGER NOT NULL,
                    rank INTEGER NOT NULL,
                    full_name VARCHAR(255),
                    current_age FLOAT,
                    primary_position VARCHAR(50),
                    current_team VARCHAR(255),
                    highest_level VARCHAR(20),
                    total_milb_pa INTEGER,
                    milb_ops FLOAT,
                    pred_wrc_plus FLOAT,
                    pred_woba FLOAT,
                    pred_ops FLOAT,
                    composite_score FLOAT,
                    context_prospect_score FLOAT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(mlb_player_id)
                )
            """))

        # Batch insert for performance
        rows_to_insert = []
        for _, row in rankings.iterrows():
            rows_to_insert.append({
                'mlb_player_id': int(row['mlb_player_id']),
                'rank': int(row['rank']),
                'full_name': row.get('full_name', 'Unknown'),
                'current_age': float(row.get('current_age', 0)),
                'primary_position': row.get('primary_position', 'Unknown'),
                'current_team': row.get('current_team', 'Unknown'),
                'highest_level': row.get('highest_level_name', 'Unknown'),
                'total_milb_pa': int(row.get('total_milb_pa', 0)),
                'milb_ops': float(row.get(f'avg_ops_{row.get("highest_level_name", "A")}', 0)),
                'pred_wrc_plus': float(row.get('pred_mlb_wrc_plus', 0)),
                'pred_woba': float(row.get('pred_mlb_woba', 0)),
                'pred_ops': float(row.get('pred_mlb_avg_ops', 0)),
                'composite_score': float(row.get('composite_score', 0)),
                'context_prospect_score': float(row.get('weighted_prospect_score', 0))
            })

        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO prospect_rankings_context_aware
                    (mlb_player_id, rank, full_name, current_age, primary_position, current_team,
                     highest_level, total_milb_pa, milb_ops, pred_wrc_plus, pred_woba, pred_ops,
                     composite_score, context_prospect_score)
                    VALUES
                    (:mlb_player_id, :rank, :full_name, :current_age, :primary_position, :current_team,
                     :highest_level, :total_milb_pa, :milb_ops, :pred_wrc_plus, :pred_woba, :pred_ops,
                     :composite_score, :context_prospect_score)
                """),
                rows_to_insert
            )

        logger.info(f"Saved {len(rankings)} rankings to database")

    def print_top_prospects(self, rankings: pd.DataFrame, top_n: int = 50):
        """Print top N prospects."""
        print("\n" + "="*160)
        print(f"TOP {top_n} PROSPECTS - CONTEXT-AWARE RANKINGS")
        print("="*160)
        print(f"{'Rank':<6} {'Name':<25} {'Age':<6} {'Pos':<6} {'Team':<20} {'Lvl':<6} {'PAs':<8} "
              f"{'MiLB OPS':<10} {'Pred wRC+':<12} {'Pred OPS':<10} {'Context Score':<14}")
        print("-"*160)

        for _, row in rankings.head(top_n).iterrows():
            milb_ops = row.get(f'avg_ops_{row.get("highest_level_name", "A")}', 0)
            print(f"{int(row['rank']):<6} {str(row.get('full_name', 'Unknown'))[:24]:<25} "
                  f"{row.get('current_age', 0):<6.1f} {str(row.get('primary_position', 'NA'))[:5]:<6} "
                  f"{str(row.get('current_team', 'Unknown'))[:19]:<20} "
                  f"{str(row.get('highest_level_name', 'NA')):<6} {int(row.get('total_milb_pa', 0)):<8} "
                  f"{milb_ops:<10.3f} {row.get('pred_mlb_wrc_plus', 0):<12.1f} "
                  f"{row.get('pred_mlb_avg_ops', 0):<10.3f} "
                  f"{row.get('weighted_prospect_score', 0):<14.2f}")


async def main():
    """Main execution."""
    logger.info("="*80)
    logger.info("CONTEXT-AWARE Prospect Ranking System")
    logger.info("Using League + Age + Position Factors")
    logger.info("="*80)

    system = ContextAwareRankingSystem()

    # Generate rankings
    rankings = await system.generate_rankings()

    # Save to database
    await system.save_rankings(rankings)

    # Print top 50
    system.print_top_prospects(rankings, top_n=50)

    # Export to CSV
    output_file = 'prospect_rankings_context_aware.csv'
    rankings_export = rankings[[
        'rank', 'mlb_player_id', 'full_name', 'current_age', 'primary_position',
        'current_team', 'highest_level_name', 'total_milb_pa',
        'pred_mlb_wrc_plus', 'pred_mlb_woba', 'pred_mlb_avg_ops',
        'composite_score', 'weighted_prospect_score'
    ]]
    rankings_export.to_csv(output_file, index=False)
    logger.info(f"\nExported rankings to {output_file}")

    logger.info("\n" + "="*80)
    logger.info("Context-Aware Ranking Generation Complete!")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
