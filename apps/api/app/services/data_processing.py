"""
Data processing service for historical MLB prospect data.
Handles extraction, cleaning, normalization, and feature engineering.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import asyncio
import aiohttp
from pydantic import ValidationError

from app.core.config import settings
from app.core.database import get_db
from app.models.prospect import ProspectBase
from app.models.prospect_stats import ProspectStatsBase
from app.models.scouting_grades import ScoutingGradesBase

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter for API requests."""

    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window  # in seconds
        self.requests = []

    async def wait_if_needed(self):
        """Wait if rate limit would be exceeded."""
        now = time.time()
        self.requests = [req_time for req_time in self.requests
                        if now - req_time < self.time_window]

        if len(self.requests) >= self.max_requests:
            sleep_time = self.time_window - (now - self.requests[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        self.requests.append(time.time())


def get_mlb_api_session() -> requests.Session:
    """Create a session with retry logic for MLB API."""
    session = requests.Session()
    retry = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=0.3,
        status_forcelist=(500, 502, 503, 504)
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


async def extract_mlb_historical_data(
    start_year: int = 2009,
    end_year: int = 2024,
    rate_limit: int = 1000,
    batch_size: int = 100,
    **kwargs
) -> Dict[str, Any]:
    """
    Extract historical data from MLB Stats API.

    Args:
        start_year: Starting year for historical data
        end_year: Ending year for historical data
        rate_limit: Maximum requests per day
        batch_size: Number of records to process at once

    Returns:
        Dictionary with extraction results and metrics
    """
    logger.info(f"Starting MLB historical data extraction from {start_year} to {end_year}")

    # Initialize rate limiter (1000 requests per day = ~0.7 requests per minute)
    rate_limiter = RateLimiter(max_requests=rate_limit, time_window=86400)

    session = get_mlb_api_session()
    extracted_data = []
    errors = []

    try:
        for year in range(start_year, end_year + 1):
            # MLB Stats API endpoints
            base_url = "https://statsapi.mlb.com/api/v1"

            # Get prospects for each year
            for level in ['Triple-A', 'Double-A', 'High-A', 'Low-A', 'Rookie']:
                await rate_limiter.wait_if_needed()

                try:
                    # Get minor league players for the year
                    players_url = f"{base_url}/sports/11/players?season={year}"
                    response = session.get(players_url, timeout=30)

                    if response.status_code == 200:
                        players_data = response.json()

                        # Process each player
                        for player in players_data.get('people', []):
                            player_data = {
                                'year': year,
                                'mlb_id': player.get('id'),
                                'name': player.get('fullName'),
                                'position': player.get('primaryPosition', {}).get('abbreviation'),
                                'age': calculate_age(player.get('birthDate'), year),
                                'level': level,
                                'organization': player.get('currentTeam', {}).get('name'),
                            }

                            # Get player stats for the year
                            await rate_limiter.wait_if_needed()
                            stats_url = f"{base_url}/people/{player['id']}/stats?stats=season&season={year}&group=hitting,pitching"
                            stats_response = session.get(stats_url, timeout=30)

                            if stats_response.status_code == 200:
                                stats_data = stats_response.json()
                                player_data['stats'] = process_player_stats(stats_data)

                            extracted_data.append(player_data)

                            # Save batch to database
                            if len(extracted_data) >= batch_size:
                                save_batch_to_db(extracted_data)
                                extracted_data = []

                except Exception as e:
                    logger.error(f"Error extracting data for {year} - {level}: {str(e)}")
                    errors.append({'year': year, 'level': level, 'error': str(e)})

        # Save remaining data
        if extracted_data:
            save_batch_to_db(extracted_data)

        return {
            'status': 'success',
            'records_extracted': len(extracted_data),
            'years_processed': end_year - start_year + 1,
            'errors': errors,
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Critical error in MLB data extraction: {str(e)}")
        raise
    finally:
        session.close()


async def extract_fangraphs_data(
    start_year: int = 2009,
    end_year: int = 2024,
    rate_limit_per_second: int = 1,
    **kwargs
) -> Dict[str, Any]:
    """
    Extract historical scouting data from Fangraphs.

    Args:
        start_year: Starting year for historical data
        end_year: Ending year for historical data
        rate_limit_per_second: Maximum requests per second

    Returns:
        Dictionary with extraction results
    """
    logger.info(f"Starting Fangraphs data extraction from {start_year} to {end_year}")

    rate_limiter = RateLimiter(max_requests=rate_limit_per_second, time_window=1)
    extracted_grades = []
    errors = []

    async with aiohttp.ClientSession() as session:
        for year in range(start_year, end_year + 1):
            await rate_limiter.wait_if_needed()

            try:
                # Fangraphs API endpoint (example - actual endpoint may vary)
                url = f"https://www.fangraphs.com/api/prospects/list/{year}"

                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()

                        for prospect in data.get('prospects', []):
                            grade_data = {
                                'year': year,
                                'player_name': prospect.get('name'),
                                'source': 'Fangraphs',
                                'overall_grade': standardize_grade(prospect.get('fv')),
                                'hit_grade': standardize_grade(prospect.get('hit')),
                                'power_grade': standardize_grade(prospect.get('power')),
                                'speed_grade': standardize_grade(prospect.get('speed')),
                                'field_grade': standardize_grade(prospect.get('field')),
                                'arm_grade': standardize_grade(prospect.get('arm')),
                                'date_recorded': datetime.utcnow()
                            }
                            extracted_grades.append(grade_data)

            except Exception as e:
                logger.error(f"Error extracting Fangraphs data for {year}: {str(e)}")
                errors.append({'year': year, 'error': str(e)})

        # Save grades to database
        if extracted_grades:
            save_scouting_grades_to_db(extracted_grades)

        return {
            'status': 'success',
            'grades_extracted': len(extracted_grades),
            'years_processed': end_year - start_year + 1,
            'errors': errors,
            'timestamp': datetime.utcnow().isoformat()
        }


def validate_ingested_data(
    check_schemas: bool = True,
    check_outliers: bool = True,
    check_consistency: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    Validate ingested data for quality and consistency.

    Args:
        check_schemas: Whether to validate data schemas
        check_outliers: Whether to detect statistical outliers
        check_consistency: Whether to check cross-source consistency

    Returns:
        Validation results and metrics
    """
    logger.info("Starting data validation")

    validation_results = {
        'schema_errors': [],
        'outliers': [],
        'consistency_issues': [],
        'total_records_validated': 0
    }

    db = next(get_db())

    try:
        # Schema validation using Pydantic models
        if check_schemas:
            query = text("SELECT * FROM prospects WHERE date_recorded >= NOW() - INTERVAL '1 day'")
            prospects = db.execute(query).fetchall()

            for prospect in prospects:
                try:
                    ProspectBase(**dict(prospect))
                    validation_results['total_records_validated'] += 1
                except ValidationError as e:
                    validation_results['schema_errors'].append({
                        'id': prospect.get('id'),
                        'error': str(e)
                    })

        # Outlier detection
        if check_outliers:
            stats_query = text("""
                SELECT prospect_id, batting_avg, on_base_pct, slugging_pct, era, whip
                FROM prospect_stats
                WHERE date_recorded >= NOW() - INTERVAL '1 day'
            """)
            stats_df = pd.read_sql(stats_query, db.bind)

            # Detect outliers using IQR method
            for col in ['batting_avg', 'on_base_pct', 'slugging_pct', 'era', 'whip']:
                if col in stats_df.columns:
                    Q1 = stats_df[col].quantile(0.25)
                    Q3 = stats_df[col].quantile(0.75)
                    IQR = Q3 - Q1

                    outliers = stats_df[
                        (stats_df[col] < Q1 - 1.5 * IQR) |
                        (stats_df[col] > Q3 + 1.5 * IQR)
                    ]

                    for _, row in outliers.iterrows():
                        validation_results['outliers'].append({
                            'prospect_id': row['prospect_id'],
                            'metric': col,
                            'value': row[col]
                        })

        # Cross-source consistency checks
        if check_consistency:
            consistency_query = text("""
                SELECT p.mlb_id, p.name, COUNT(DISTINCT sg.source) as source_count,
                       AVG(sg.overall_grade) as avg_grade, STDDEV(sg.overall_grade) as grade_stddev
                FROM prospects p
                JOIN scouting_grades sg ON p.id = sg.prospect_id
                WHERE sg.date_recorded >= NOW() - INTERVAL '1 day'
                GROUP BY p.mlb_id, p.name
                HAVING COUNT(DISTINCT sg.source) > 1 AND STDDEV(sg.overall_grade) > 10
            """)

            inconsistent = db.execute(consistency_query).fetchall()

            for record in inconsistent:
                validation_results['consistency_issues'].append({
                    'mlb_id': record['mlb_id'],
                    'name': record['name'],
                    'source_count': record['source_count'],
                    'grade_stddev': float(record['grade_stddev'])
                })

        return {
            'status': 'completed',
            'validation_results': validation_results,
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in data validation: {str(e)}")
        raise
    finally:
        db.close()


def clean_normalize_data(
    standardize_names: bool = True,
    normalize_stats: bool = True,
    handle_missing: str = 'interpolate',
    **kwargs
) -> Dict[str, Any]:
    """
    Clean and normalize ingested data.

    Args:
        standardize_names: Whether to standardize player names
        normalize_stats: Whether to normalize statistics
        handle_missing: Strategy for handling missing values

    Returns:
        Cleaning results and metrics
    """
    logger.info("Starting data cleaning and normalization")

    db = next(get_db())
    cleaning_metrics = {
        'names_standardized': 0,
        'stats_normalized': 0,
        'missing_handled': 0
    }

    try:
        # Standardize names
        if standardize_names:
            update_query = text("""
                UPDATE prospects
                SET name = TRIM(REGEXP_REPLACE(name, '\\s+', ' ', 'g'))
                WHERE date_recorded >= NOW() - INTERVAL '1 day'
            """)
            result = db.execute(update_query)
            cleaning_metrics['names_standardized'] = result.rowcount
            db.commit()

        # Normalize statistics
        if normalize_stats:
            # Get stats data
            stats_df = pd.read_sql(
                "SELECT * FROM prospect_stats WHERE date_recorded >= NOW() - INTERVAL '1 day'",
                db.bind
            )

            # Normalize rate stats to proper scale
            if not stats_df.empty:
                # Ensure batting average is between 0 and 1
                stats_df.loc[stats_df['batting_avg'] > 1, 'batting_avg'] /= 1000

                # Ensure percentages are decimals
                for col in ['on_base_pct', 'slugging_pct']:
                    if col in stats_df.columns:
                        stats_df.loc[stats_df[col] > 1, col] /= 100

                # Update database
                for _, row in stats_df.iterrows():
                    update_stmt = text("""
                        UPDATE prospect_stats
                        SET batting_avg = :ba, on_base_pct = :obp, slugging_pct = :slg
                        WHERE id = :id
                    """)
                    db.execute(update_stmt, {
                        'ba': row['batting_avg'],
                        'obp': row['on_base_pct'],
                        'slg': row['slugging_pct'],
                        'id': row['id']
                    })

                cleaning_metrics['stats_normalized'] = len(stats_df)
                db.commit()

        # Handle missing values
        if handle_missing == 'interpolate':
            # Interpolate missing values in time series data
            missing_query = text("""
                UPDATE prospect_stats
                SET batting_avg = COALESCE(
                    batting_avg,
                    (LAG(batting_avg) OVER (PARTITION BY prospect_id ORDER BY date_recorded) +
                     LEAD(batting_avg) OVER (PARTITION BY prospect_id ORDER BY date_recorded)) / 2
                )
                WHERE batting_avg IS NULL AND date_recorded >= NOW() - INTERVAL '1 day'
            """)
            result = db.execute(missing_query)
            cleaning_metrics['missing_handled'] = result.rowcount
            db.commit()

        return {
            'status': 'completed',
            'cleaning_metrics': cleaning_metrics,
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in data cleaning: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def deduplicate_records(
    merge_strategy: str = 'most_recent',
    conflict_resolution: str = 'weighted_average',
    **kwargs
) -> Dict[str, Any]:
    """
    Deduplicate records and resolve conflicts.

    Args:
        merge_strategy: Strategy for merging duplicates
        conflict_resolution: How to resolve conflicting values

    Returns:
        Deduplication results
    """
    logger.info("Starting record deduplication")

    db = next(get_db())
    dedup_metrics = {
        'duplicates_found': 0,
        'records_merged': 0
    }

    try:
        # Find duplicates
        duplicate_query = text("""
            SELECT mlb_id, COUNT(*) as count
            FROM prospects
            WHERE date_recorded >= NOW() - INTERVAL '1 day'
            GROUP BY mlb_id
            HAVING COUNT(*) > 1
        """)

        duplicates = db.execute(duplicate_query).fetchall()
        dedup_metrics['duplicates_found'] = len(duplicates)

        for dup in duplicates:
            if merge_strategy == 'most_recent':
                # Keep most recent record, delete others
                delete_query = text("""
                    DELETE FROM prospects
                    WHERE mlb_id = :mlb_id
                    AND id NOT IN (
                        SELECT id FROM prospects
                        WHERE mlb_id = :mlb_id
                        ORDER BY date_recorded DESC
                        LIMIT 1
                    )
                """)
                db.execute(delete_query, {'mlb_id': dup['mlb_id']})
                dedup_metrics['records_merged'] += dup['count'] - 1

        db.commit()

        return {
            'status': 'completed',
            'deduplication_metrics': dedup_metrics,
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in deduplication: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def perform_feature_engineering(
    calculate_age_adjusted: bool = True,
    calculate_progression_rates: bool = True,
    calculate_peer_comparisons: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    Perform feature engineering for ML training.

    Args:
        calculate_age_adjusted: Calculate age-adjusted metrics
        calculate_progression_rates: Calculate level progression rates
        calculate_peer_comparisons: Calculate peer comparisons

    Returns:
        Feature engineering results
    """
    logger.info("Starting feature engineering")

    db = next(get_db())
    feature_metrics = {
        'age_adjusted_calculated': 0,
        'progression_rates_calculated': 0,
        'peer_comparisons_calculated': 0
    }

    try:
        # Age-adjusted performance metrics
        if calculate_age_adjusted:
            # Get stats with age information
            query = text("""
                SELECT ps.*, p.age, p.level
                FROM prospect_stats ps
                JOIN prospects p ON ps.prospect_id = p.id
                WHERE ps.date_recorded >= NOW() - INTERVAL '1 day'
            """)

            stats_df = pd.read_sql(query, db.bind)

            if not stats_df.empty:
                # Calculate age-adjusted metrics
                for level in stats_df['level'].unique():
                    level_df = stats_df[stats_df['level'] == level]

                    # Calculate z-scores for each age group
                    for age in level_df['age'].unique():
                        age_mask = level_df['age'] == age

                        for stat in ['batting_avg', 'on_base_pct', 'slugging_pct']:
                            if stat in level_df.columns:
                                mean_val = level_df.loc[age_mask, stat].mean()
                                std_val = level_df.loc[age_mask, stat].std()

                                if std_val > 0:
                                    stats_df.loc[
                                        (stats_df['level'] == level) & (stats_df['age'] == age),
                                        f'{stat}_age_adjusted'
                                    ] = (stats_df.loc[
                                        (stats_df['level'] == level) & (stats_df['age'] == age),
                                        stat
                                    ] - mean_val) / std_val

                # Save age-adjusted metrics
                for _, row in stats_df.iterrows():
                    if 'batting_avg_age_adjusted' in row:
                        update_query = text("""
                            UPDATE prospect_stats
                            SET woba = :woba_adj
                            WHERE id = :id
                        """)
                        db.execute(update_query, {
                            'woba_adj': row.get('batting_avg_age_adjusted', 0),
                            'id': row['id']
                        })

                feature_metrics['age_adjusted_calculated'] = len(stats_df)
                db.commit()

        # Level progression rates
        if calculate_progression_rates:
            progression_query = text("""
                WITH progression AS (
                    SELECT prospect_id,
                           level,
                           date_recorded,
                           LAG(level) OVER (PARTITION BY prospect_id ORDER BY date_recorded) as prev_level,
                           LAG(date_recorded) OVER (PARTITION BY prospect_id ORDER BY date_recorded) as prev_date
                    FROM prospects
                )
                SELECT prospect_id,
                       COUNT(CASE WHEN level != prev_level THEN 1 END) as level_changes,
                       AVG(EXTRACT(EPOCH FROM date_recorded - prev_date) / 86400) as avg_days_between_levels
                FROM progression
                WHERE prev_level IS NOT NULL
                GROUP BY prospect_id
            """)

            progression_df = pd.read_sql(progression_query, db.bind)
            feature_metrics['progression_rates_calculated'] = len(progression_df)

        # Peer comparisons
        if calculate_peer_comparisons:
            peer_query = text("""
                SELECT ps.prospect_id,
                       ps.batting_avg,
                       AVG(ps2.batting_avg) as peer_avg,
                       STDDEV(ps2.batting_avg) as peer_stddev
                FROM prospect_stats ps
                JOIN prospects p ON ps.prospect_id = p.id
                JOIN prospects p2 ON p.age = p2.age AND p.level = p2.level
                JOIN prospect_stats ps2 ON p2.id = ps2.prospect_id
                WHERE ps.date_recorded >= NOW() - INTERVAL '1 day'
                GROUP BY ps.prospect_id, ps.batting_avg
            """)

            peer_df = pd.read_sql(peer_query, db.bind)

            # Calculate relative performance
            if not peer_df.empty:
                peer_df['relative_performance'] = (
                    peer_df['batting_avg'] - peer_df['peer_avg']
                ) / peer_df['peer_stddev'].replace(0, 1)

                feature_metrics['peer_comparisons_calculated'] = len(peer_df)

        return {
            'status': 'completed',
            'feature_metrics': feature_metrics,
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in feature engineering: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def update_prospect_rankings(**kwargs) -> Dict[str, Any]:
    """
    Update prospect rankings based on processed data.

    Returns:
        Ranking update results
    """
    logger.info("Updating prospect rankings")

    db = next(get_db())

    try:
        # Calculate composite scores and update rankings
        ranking_query = text("""
            WITH ranked_prospects AS (
                SELECT p.id,
                       p.mlb_id,
                       AVG(ps.batting_avg) as avg_batting,
                       AVG(sg.overall_grade) as avg_grade,
                       ROW_NUMBER() OVER (ORDER BY AVG(sg.overall_grade) DESC) as ranking
                FROM prospects p
                LEFT JOIN prospect_stats ps ON p.id = ps.prospect_id
                LEFT JOIN scouting_grades sg ON p.id = sg.prospect_id
                GROUP BY p.id, p.mlb_id
            )
            UPDATE prospects
            SET eta_year = EXTRACT(YEAR FROM NOW()) +
                          CASE
                              WHEN ranking <= 10 THEN 1
                              WHEN ranking <= 50 THEN 2
                              WHEN ranking <= 100 THEN 3
                              ELSE 4
                          END
            FROM ranked_prospects rp
            WHERE prospects.id = rp.id
        """)

        result = db.execute(ranking_query)
        db.commit()

        return {
            'status': 'completed',
            'rankings_updated': result.rowcount,
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error updating rankings: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def cache_processed_results(
    cache_type: str = 'redis',
    ttl_hours: int = 24,
    **kwargs
) -> Dict[str, Any]:
    """
    Cache processed results for faster access.

    Args:
        cache_type: Type of cache to use
        ttl_hours: Time to live in hours

    Returns:
        Caching results
    """
    logger.info(f"Caching processed results to {cache_type}")

    # For now, we'll just log the caching action
    # In production, this would connect to Redis or another cache

    return {
        'status': 'completed',
        'cache_type': cache_type,
        'ttl_hours': ttl_hours,
        'timestamp': datetime.utcnow().isoformat()
    }


# Helper functions

def calculate_age(birth_date: str, year: int) -> Optional[int]:
    """Calculate age for a given year."""
    if not birth_date:
        return None

    try:
        birth = datetime.strptime(birth_date, '%Y-%m-%d')
        return year - birth.year
    except:
        return None


def process_player_stats(stats_data: Dict) -> Dict:
    """Process raw player stats from API."""
    processed = {}

    for stat_group in stats_data.get('stats', []):
        if stat_group.get('group', {}).get('displayName') == 'hitting':
            hitting = stat_group.get('stats', {})
            processed['batting_avg'] = hitting.get('avg')
            processed['on_base_pct'] = hitting.get('obp')
            processed['slugging_pct'] = hitting.get('slg')
            processed['home_runs'] = hitting.get('homeRuns')
            processed['rbi'] = hitting.get('rbi')

        elif stat_group.get('group', {}).get('displayName') == 'pitching':
            pitching = stat_group.get('stats', {})
            processed['era'] = pitching.get('era')
            processed['whip'] = pitching.get('whip')
            processed['strikeouts_per_nine'] = pitching.get('strikeoutsPer9Inn')
            processed['innings_pitched'] = pitching.get('inningsPitched')

    return processed


def standardize_grade(grade: Any) -> Optional[float]:
    """Standardize scouting grades to 20-80 scale."""
    if grade is None:
        return None

    try:
        grade_val = float(grade)

        # If grade is 2-8 scale, convert to 20-80
        if grade_val <= 8:
            return grade_val * 10

        # If grade is 0-100 scale, convert to 20-80
        if grade_val > 80:
            return 20 + (grade_val / 100) * 60

        return grade_val
    except:
        return None


def save_batch_to_db(data: List[Dict]) -> None:
    """Save a batch of data to the database."""
    db = next(get_db())

    try:
        for record in data:
            # Insert prospect
            prospect_query = text("""
                INSERT INTO prospects (mlb_id, name, position, organization, level, age)
                VALUES (:mlb_id, :name, :position, :organization, :level, :age)
                ON CONFLICT (mlb_id) DO UPDATE
                SET name = EXCLUDED.name,
                    position = EXCLUDED.position,
                    organization = EXCLUDED.organization,
                    level = EXCLUDED.level,
                    age = EXCLUDED.age
                RETURNING id
            """)

            result = db.execute(prospect_query, {
                'mlb_id': record.get('mlb_id'),
                'name': record.get('name'),
                'position': record.get('position'),
                'organization': record.get('organization'),
                'level': record.get('level'),
                'age': record.get('age')
            })

            prospect_id = result.fetchone()[0]

            # Insert stats if available
            if 'stats' in record and record['stats']:
                stats = record['stats']
                stats_query = text("""
                    INSERT INTO prospect_stats (
                        prospect_id, date_recorded, batting_avg, on_base_pct,
                        slugging_pct, home_runs, rbi, era, whip, strikeouts_per_nine,
                        innings_pitched
                    ) VALUES (
                        :prospect_id, :date_recorded, :batting_avg, :on_base_pct,
                        :slugging_pct, :home_runs, :rbi, :era, :whip, :strikeouts_per_nine,
                        :innings_pitched
                    )
                """)

                db.execute(stats_query, {
                    'prospect_id': prospect_id,
                    'date_recorded': datetime.utcnow(),
                    'batting_avg': stats.get('batting_avg'),
                    'on_base_pct': stats.get('on_base_pct'),
                    'slugging_pct': stats.get('slugging_pct'),
                    'home_runs': stats.get('home_runs'),
                    'rbi': stats.get('rbi'),
                    'era': stats.get('era'),
                    'whip': stats.get('whip'),
                    'strikeouts_per_nine': stats.get('strikeouts_per_nine'),
                    'innings_pitched': stats.get('innings_pitched')
                })

        db.commit()

    except Exception as e:
        logger.error(f"Error saving batch to database: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def save_scouting_grades_to_db(grades: List[Dict]) -> None:
    """Save scouting grades to the database."""
    db = next(get_db())

    try:
        for grade in grades:
            # Find prospect by name
            prospect_query = text("""
                SELECT id FROM prospects
                WHERE name = :name
                LIMIT 1
            """)

            result = db.execute(prospect_query, {'name': grade.get('player_name')})
            prospect = result.fetchone()

            if prospect:
                grade_query = text("""
                    INSERT INTO scouting_grades (
                        prospect_id, source, overall_grade, hit_grade,
                        power_grade, speed_grade, field_grade, arm_grade,
                        date_recorded
                    ) VALUES (
                        :prospect_id, :source, :overall_grade, :hit_grade,
                        :power_grade, :speed_grade, :field_grade, :arm_grade,
                        :date_recorded
                    )
                """)

                db.execute(grade_query, {
                    'prospect_id': prospect[0],
                    'source': grade.get('source'),
                    'overall_grade': grade.get('overall_grade'),
                    'hit_grade': grade.get('hit_grade'),
                    'power_grade': grade.get('power_grade'),
                    'speed_grade': grade.get('speed_grade'),
                    'field_grade': grade.get('field_grade'),
                    'arm_grade': grade.get('arm_grade'),
                    'date_recorded': grade.get('date_recorded')
                })

        db.commit()

    except Exception as e:
        logger.error(f"Error saving scouting grades: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()