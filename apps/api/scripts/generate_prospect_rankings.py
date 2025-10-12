"""
Generate prospect rankings based on ML predictions.

Ranks all prospects (players with <130 MLB ABs or 50 IP) by predicted MLB performance.
Uses the trained Random Forest model to predict wRC+, wOBA, OPS, and other metrics.
"""

import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text
from app.db.database import engine
import logging
from datetime import datetime
import pickle
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from typing import Tuple, Dict, List

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProspectRankingSystem:
    """Generate ML-based prospect rankings."""

    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.feature_names = []

    async def load_milb_features(self) -> pd.DataFrame:
        """Load and calculate MiLB features for all prospects."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    mlb_player_id,
                    season,
                    level,
                    game_date,
                    pa, ab, h, doubles, triples, hr, rbi, bb, so, sb, cs, hbp, sf
                FROM milb_game_logs
                WHERE data_source = 'mlb_stats_api_gamelog'
                AND pa > 0
                ORDER BY mlb_player_id, season, game_date
            """))
            rows = result.fetchall()

        if not rows:
            logger.error("No MiLB game logs found")
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[
            'mlb_player_id', 'season', 'level', 'game_date',
            'pa', 'ab', 'h', 'doubles', 'triples', 'hr', 'rbi', 'bb', 'so', 'sb', 'cs', 'hbp', 'sf'
        ])

        # Convert to numeric
        numeric_cols = ['pa', 'ab', 'h', 'doubles', 'triples', 'hr', 'rbi', 'bb', 'so', 'sb', 'cs', 'hbp', 'sf']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)

        logger.info(f"Loaded {len(df):,} MiLB game logs")
        return df

    async def load_mlb_stats(self) -> pd.DataFrame:
        """Load MLB career stats to identify who qualifies as a prospect."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    mlb_player_id,
                    SUM(ab) as mlb_ab,
                    SUM(pa) as mlb_pa
                FROM mlb_game_logs
                GROUP BY mlb_player_id
            """))
            rows = result.fetchall()

        if not rows:
            logger.warning("No MLB game logs found")
            return pd.DataFrame(columns=['mlb_player_id', 'mlb_ab', 'mlb_pa'])

        df = pd.DataFrame(rows, columns=['mlb_player_id', 'mlb_ab', 'mlb_pa'])
        df['mlb_ab'] = pd.to_numeric(df['mlb_ab'], errors='coerce').fillna(0)
        df['mlb_pa'] = pd.to_numeric(df['mlb_pa'], errors='coerce').fillna(0)

        logger.info(f"Loaded MLB stats for {len(df)} players")
        return df

    async def load_birth_dates(self) -> pd.DataFrame:
        """Load player birth dates for age calculations."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT mlb_player_id, full_name, birth_date, primary_position, current_team
                FROM prospects
                WHERE birth_date IS NOT NULL
            """))
            rows = result.fetchall()

        df = pd.DataFrame(rows, columns=['mlb_player_id', 'full_name', 'birth_date', 'primary_position', 'current_team'])
        logger.info(f"Loaded birth dates for {len(df)} prospects")
        return df

    async def load_statcast_metrics(self) -> pd.DataFrame:
        """Load aggregated Statcast metrics."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    mlb_player_id,
                    season,
                    level,
                    avg_ev,
                    max_ev,
                    ev_90th,
                    hard_hit_pct,
                    avg_la,
                    avg_la_hard,
                    fb_ev,
                    barrel_pct
                FROM milb_statcast_metrics
            """))
            rows = result.fetchall()

        if not rows:
            logger.warning("No Statcast metrics found")
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[
            'mlb_player_id', 'season', 'level', 'avg_ev', 'max_ev', 'ev_90th',
            'hard_hit_pct', 'avg_la', 'avg_la_hard', 'fb_ev', 'barrel_pct'
        ])

        logger.info(f"Loaded Statcast metrics for {len(df)} player-season-level combinations")
        return df

    def calculate_features(self, milb_df: pd.DataFrame, birth_dates: pd.DataFrame, statcast_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all ML features for each player."""

        # Calculate basic stats
        milb_df['singles'] = milb_df['h'] - milb_df['doubles'] - milb_df['triples'] - milb_df['hr']
        milb_df['tb'] = milb_df['singles'] + (milb_df['doubles'] * 2) + (milb_df['triples'] * 3) + (milb_df['hr'] * 4)

        # Aggregate by player
        player_stats = milb_df.groupby('mlb_player_id').agg({
            'pa': 'sum',
            'ab': 'sum',
            'h': 'sum',
            'doubles': 'sum',
            'triples': 'sum',
            'hr': 'sum',
            'bb': 'sum',
            'so': 'sum',
            'sb': 'sum',
            'cs': 'sum',
            'tb': 'sum',
            'season': 'nunique',
            'level': 'nunique',
            'game_date': ['min', 'max']
        }).reset_index()

        # Flatten column names
        player_stats.columns = [
            'mlb_player_id', 'total_pa', 'total_ab', 'total_h', 'total_doubles',
            'total_triples', 'total_hr', 'total_bb', 'total_so', 'total_sb', 'total_cs',
            'total_tb', 'seasons_active', 'levels_played', 'first_game', 'last_game'
        ]

        # Calculate rate stats
        player_stats['avg_ba'] = player_stats['total_h'] / player_stats['total_ab'].replace(0, np.nan)
        player_stats['avg_obp'] = (player_stats['total_h'] + player_stats['total_bb']) / (player_stats['total_pa'] - player_stats['total_cs']).replace(0, np.nan)
        player_stats['avg_slg'] = player_stats['total_tb'] / player_stats['total_ab'].replace(0, np.nan)
        player_stats['avg_ops'] = player_stats['avg_obp'] + player_stats['avg_slg']
        player_stats['iso'] = player_stats['avg_slg'] - player_stats['avg_ba']
        player_stats['bb_rate'] = player_stats['total_bb'] / player_stats['total_pa']
        player_stats['so_rate'] = player_stats['total_so'] / player_stats['total_pa']
        player_stats['hr_rate'] = player_stats['total_hr'] / player_stats['total_pa']
        player_stats['sb_rate'] = player_stats['total_sb'] / player_stats['total_pa']

        # Fill NaN values
        player_stats = player_stats.fillna(0)

        # Get highest level stats
        level_order = {'AAA': 6, 'AA': 5, 'A+': 4, 'A': 3, 'Rookie+': 2, 'Rookie': 1}
        milb_df['level_rank'] = milb_df['level'].map(level_order).fillna(0)

        highest_level_stats = milb_df.loc[milb_df.groupby('mlb_player_id')['level_rank'].idxmax()]
        highest_level_agg = highest_level_stats.groupby('mlb_player_id').agg({
            'level': 'first',
            'pa': 'sum',
            'ab': 'sum',
            'h': 'sum',
            'bb': 'sum',
            'so': 'sum',
            'tb': 'sum'
        }).reset_index()

        highest_level_agg['highest_level'] = highest_level_agg['level']
        highest_level_agg['highest_level_pa'] = highest_level_agg['pa']
        highest_level_agg['highest_level_obp'] = (highest_level_agg['h'] + highest_level_agg['bb']) / highest_level_agg['pa'].replace(0, np.nan)
        highest_level_agg['highest_level_slg'] = highest_level_agg['tb'] / highest_level_agg['ab'].replace(0, np.nan)
        highest_level_agg['highest_level_ops'] = highest_level_agg['highest_level_obp'] + highest_level_agg['highest_level_slg']
        highest_level_agg['highest_level_bb_rate'] = highest_level_agg['bb'] / highest_level_agg['pa']
        highest_level_agg['highest_level_so_rate'] = highest_level_agg['so'] / highest_level_agg['pa']

        highest_level_features = highest_level_agg[['mlb_player_id', 'highest_level', 'highest_level_pa',
                                                      'highest_level_ops', 'highest_level_bb_rate', 'highest_level_so_rate']].fillna(0)

        # Merge highest level features
        player_stats = player_stats.merge(highest_level_features, on='mlb_player_id', how='left')

        # Get most recent stats (last 100 PAs)
        recent_games = milb_df.sort_values('game_date').groupby('mlb_player_id').tail(20)
        recent_stats = recent_games.groupby('mlb_player_id').agg({
            'pa': 'sum',
            'ab': 'sum',
            'h': 'sum',
            'bb': 'sum',
            'tb': 'sum'
        }).reset_index()

        recent_stats['recent_obp'] = (recent_stats['h'] + recent_stats['bb']) / recent_stats['pa'].replace(0, np.nan)
        recent_stats['recent_slg'] = recent_stats['tb'] / recent_stats['ab'].replace(0, np.nan)
        recent_stats['recent_ops'] = recent_stats['recent_obp'] + recent_stats['recent_slg']

        recent_features = recent_stats[['mlb_player_id', 'recent_ops']].fillna(0)
        player_stats = player_stats.merge(recent_features, on='mlb_player_id', how='left')

        # Merge birth dates for age calculations
        player_stats = player_stats.merge(birth_dates, on='mlb_player_id', how='left')

        # Calculate current age
        current_date = datetime.now()
        player_stats['current_age'] = (current_date - pd.to_datetime(player_stats['birth_date'])).dt.days / 365.25

        # Age-adjusted features
        level_avg_ages = {'AAA': 25, 'AA': 23, 'A+': 22, 'A': 21, 'Rookie+': 20, 'Rookie': 19}
        player_stats['highest_level_avg_age'] = player_stats['highest_level'].map(level_avg_ages).fillna(22)
        player_stats['age_diff'] = player_stats['highest_level_avg_age'] - player_stats['current_age']
        player_stats['age_adj_ops'] = player_stats['avg_ops'] + (player_stats['age_diff'] * 0.010)
        player_stats['age_adj_iso'] = player_stats['iso'] + (player_stats['age_diff'] * 0.005)

        # Progression features
        player_stats['ops_improvement_per_year'] = (player_stats['recent_ops'] - player_stats['avg_ops']) / player_stats['seasons_active'].replace(0, 1)
        player_stats['ops_progression_rate'] = (player_stats['recent_ops'] - player_stats['avg_ops']) / player_stats['avg_ops'].replace(0, 1)

        # Merge Statcast metrics (use most recent season)
        if not statcast_df.empty:
            latest_statcast = statcast_df.sort_values('season', ascending=False).groupby('mlb_player_id').first().reset_index()
            statcast_features = latest_statcast[['mlb_player_id', 'avg_ev', 'max_ev', 'ev_90th',
                                                  'hard_hit_pct', 'avg_la', 'fb_ev', 'barrel_pct']]
            player_stats = player_stats.merge(statcast_features, on='mlb_player_id', how='left')

        # Fill remaining NaN
        player_stats = player_stats.fillna(0)

        logger.info(f"Calculated features for {len(player_stats)} players")
        return player_stats

    async def load_mlb_targets(self) -> pd.DataFrame:
        """Load MLB career stats as training targets."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    mlb_player_id,
                    SUM(pa) as mlb_total_pa,
                    SUM(ab) as mlb_total_ab,
                    SUM(h) as mlb_total_h,
                    SUM(doubles) as mlb_total_doubles,
                    SUM(triples) as mlb_total_triples,
                    SUM(hr) as mlb_total_hr,
                    SUM(bb) as mlb_total_bb,
                    SUM(so) as mlb_total_so,
                    AVG(wrc_plus) as mlb_wrc_plus,
                    AVG(woba) as mlb_woba,
                    AVG(babip) as mlb_babip
                FROM mlb_game_logs
                GROUP BY mlb_player_id
            """))
            rows = result.fetchall()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[
            'mlb_player_id', 'mlb_total_pa', 'mlb_total_ab', 'mlb_total_h',
            'mlb_total_doubles', 'mlb_total_triples', 'mlb_total_hr', 'mlb_total_bb',
            'mlb_total_so', 'mlb_wrc_plus', 'mlb_woba', 'mlb_babip'
        ])

        # Convert to numeric
        for col in df.columns:
            if col != 'mlb_player_id':
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)

        # Calculate MLB rate stats
        df['mlb_singles'] = df['mlb_total_h'] - df['mlb_total_doubles'] - df['mlb_total_triples'] - df['mlb_total_hr']
        df['mlb_tb'] = df['mlb_singles'] + (df['mlb_total_doubles'] * 2) + (df['mlb_total_triples'] * 3) + (df['mlb_total_hr'] * 4)
        df['mlb_obp'] = (df['mlb_total_h'] + df['mlb_total_bb']) / df['mlb_total_pa'].replace(0, np.nan)
        df['mlb_slg'] = df['mlb_tb'] / df['mlb_total_ab'].replace(0, np.nan)
        df['mlb_ops'] = df['mlb_obp'] + df['mlb_slg']
        df['mlb_bb_rate'] = df['mlb_total_bb'] / df['mlb_total_pa']
        df['mlb_so_rate'] = df['mlb_total_so'] / df['mlb_total_pa']

        df = df.fillna(0)

        logger.info(f"Loaded MLB targets for {len(df)} players")
        return df

    def train_models(self, X_train: pd.DataFrame, y_train: pd.DataFrame) -> Dict[str, float]:
        """Train Random Forest models for each target variable."""

        self.feature_names = X_train.columns.tolist()

        target_metrics = ['mlb_wrc_plus', 'mlb_woba', 'mlb_ops', 'mlb_obp', 'mlb_slg']
        scores = {}

        for target in target_metrics:
            if target not in y_train.columns:
                continue

            logger.info(f"Training model for {target}...")

            # Train Random Forest
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                min_samples_split=10,
                min_samples_leaf=5,
                random_state=42,
                n_jobs=-1
            )

            model.fit(X_train, y_train[target])
            self.models[target] = model

            # Calculate R² score
            score = model.score(X_train, y_train[target])
            scores[target] = score

            logger.info(f"  {target}: R² = {score:.3f}")

        return scores

    async def generate_rankings(self) -> pd.DataFrame:
        """Generate prospect rankings with ML predictions."""

        # Load all data
        milb_df = await self.load_milb_features()
        mlb_stats = await self.load_mlb_stats()
        birth_dates = await self.load_birth_dates()
        statcast_df = await self.load_statcast_metrics()
        mlb_targets = await self.load_mlb_targets()

        # Calculate features
        features = self.calculate_features(milb_df, birth_dates, statcast_df)

        # Identify prospects (<130 MLB ABs)
        features = features.merge(mlb_stats, on='mlb_player_id', how='left')
        features['mlb_ab'] = features['mlb_ab'].fillna(0)
        features['mlb_pa'] = features['mlb_pa'].fillna(0)

        prospects = features[features['mlb_ab'] < 130].copy()
        logger.info(f"Identified {len(prospects)} prospects with <130 MLB ABs")

        # Prepare training data (players with MLB experience)
        training_data = features.merge(mlb_targets, on='mlb_player_id', how='left')

        # Fill missing MLB stats with zeros
        mlb_cols = [col for col in training_data.columns if col.startswith('mlb_')]
        training_data[mlb_cols] = training_data[mlb_cols].fillna(0)

        # Select features
        feature_cols = [
            'total_pa', 'avg_ops', 'avg_obp', 'avg_slg', 'iso', 'bb_rate', 'so_rate', 'hr_rate',
            'highest_level_ops', 'highest_level_bb_rate', 'highest_level_so_rate',
            'recent_ops', 'current_age', 'age_adj_ops', 'age_adj_iso',
            'ops_improvement_per_year', 'ops_progression_rate',
            'seasons_active', 'levels_played'
        ]

        # Add Statcast features if available
        statcast_cols = ['avg_ev', 'max_ev', 'ev_90th', 'hard_hit_pct', 'avg_la', 'fb_ev', 'barrel_pct']
        for col in statcast_cols:
            if col in training_data.columns:
                feature_cols.append(col)

        X_train = training_data[feature_cols]
        y_train = training_data[['mlb_wrc_plus', 'mlb_woba', 'mlb_ops', 'mlb_obp', 'mlb_slg']]

        # Train models
        scores = self.train_models(X_train, y_train)

        # Generate predictions for prospects
        X_prospects = prospects[feature_cols]

        for target in self.models.keys():
            prospects[f'pred_{target}'] = self.models[target].predict(X_prospects)

        # Create composite ranking score
        prospects['composite_score'] = (
            prospects['pred_mlb_wrc_plus'] * 0.4 +
            prospects['pred_mlb_ops'] * 100 * 0.3 +
            prospects['pred_mlb_woba'] * 200 * 0.3
        )

        # Sort by composite score
        prospects = prospects.sort_values('composite_score', ascending=False)

        # Add rank
        prospects['rank'] = range(1, len(prospects) + 1)

        logger.info(f"Generated rankings for {len(prospects)} prospects")
        return prospects

    async def save_rankings(self, rankings: pd.DataFrame):
        """Save rankings to database."""
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS prospect_rankings (
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
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(mlb_player_id)
                )
            """))

            await conn.execute(text("DELETE FROM prospect_rankings"))

            logger.info("Saving rankings to database...")

        for _, row in rankings.iterrows():
            async with engine.begin() as conn:
                await conn.execute(text("""
                    INSERT INTO prospect_rankings
                    (mlb_player_id, rank, full_name, current_age, primary_position, current_team,
                     highest_level, total_milb_pa, milb_ops, pred_wrc_plus, pred_woba, pred_ops, composite_score)
                    VALUES
                    (:mlb_player_id, :rank, :full_name, :current_age, :primary_position, :current_team,
                     :highest_level, :total_milb_pa, :milb_ops, :pred_wrc_plus, :pred_woba, :pred_ops, :composite_score)
                """), {
                    'mlb_player_id': int(row['mlb_player_id']),
                    'rank': int(row['rank']),
                    'full_name': row['full_name'],
                    'current_age': float(row['current_age']),
                    'primary_position': row['primary_position'],
                    'current_team': row['current_team'],
                    'highest_level': row['highest_level'],
                    'total_milb_pa': int(row['total_pa']),
                    'milb_ops': float(row['avg_ops']),
                    'pred_wrc_plus': float(row['pred_mlb_wrc_plus']),
                    'pred_woba': float(row['pred_mlb_woba']),
                    'pred_ops': float(row['pred_mlb_ops']),
                    'composite_score': float(row['composite_score'])
                })

        logger.info(f"Saved {len(rankings)} rankings to database")

    def print_top_prospects(self, rankings: pd.DataFrame, top_n: int = 50):
        """Print top N prospects."""
        print("\n" + "="*150)
        print(f"TOP {top_n} PROSPECTS BY ML PREDICTION")
        print("="*150)
        print(f"{'Rank':<6} {'Name':<25} {'Age':<6} {'Pos':<6} {'Team':<20} {'Level':<8} {'PAs':<8} {'MiLB OPS':<10} {'Pred wRC+':<12} {'Pred wOBA':<12} {'Pred OPS':<10}")
        print("-"*150)

        for _, row in rankings.head(top_n).iterrows():
            print(f"{int(row['rank']):<6} {row['full_name'][:24]:<25} {row['current_age']:<6.1f} {row['primary_position'][:5]:<6} {row['current_team'][:19]:<20} "
                  f"{row['highest_level']:<8} {int(row['total_pa']):<8} {row['avg_ops']:<10.3f} {row['pred_mlb_wrc_plus']:<12.1f} "
                  f"{row['pred_mlb_woba']:<12.3f} {row['pred_mlb_ops']:<10.3f}")


async def main():
    """Main execution."""
    logger.info("="*80)
    logger.info("Prospect Ranking System")
    logger.info("="*80)

    system = ProspectRankingSystem()

    # Generate rankings
    rankings = await system.generate_rankings()

    # Save to database
    await system.save_rankings(rankings)

    # Print top 50
    system.print_top_prospects(rankings, top_n=50)

    # Export to CSV
    output_file = 'prospect_rankings.csv'
    rankings_export = rankings[[
        'rank', 'mlb_player_id', 'full_name', 'current_age', 'primary_position',
        'current_team', 'highest_level', 'total_pa', 'avg_ops',
        'pred_mlb_wrc_plus', 'pred_mlb_woba', 'pred_mlb_ops', 'composite_score'
    ]]
    rankings_export.to_csv(output_file, index=False)
    logger.info(f"\nExported rankings to {output_file}")

    logger.info("\n" + "="*80)
    logger.info("Ranking Generation Complete!")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
